"""설정(환경 변수에서 온 Config)을 읽어 LlmClient 를 세운다. ★ core/llm 에서 Django 를 아는 파일은 둘이다:
이 파일과 sink_db.py(DB 싱크). 이 파일은 sink_db 를 `db` 싱크를 세울 때만 import 한다(모델을 끌고 오므로).

    llm_client()      이 프로세스의 클라이언트(한 번 세워 다시 쓴다). 모듈의 services 가 부른다(서버 요청 길).
                      실제 공급사 키를 싣지 않는다(LH2) — 실호출은 실행기(runs/context.py)와 관리 명령 llm_call 뿐
    build_client(…)   설정 값을 받아 세운다. 관리 명령과 테스트가 부른다(Django 설정을 읽지 않는다)
    build_embedding_client(…)  같은 꼴로 임베딩 클라이언트를 세운다(프로세스 하나의 임베딩 클라이언트는 아직 없다)

키는 여기서 설정에서 꺼내 어댑터의 make 에 **명시로** 넘긴다. 키가 없는 공급사는 미리 만들지 않는다: 그 공급사의
모델을 처음
부를 때 make 가 LiveSetupError 를 던진다(SDK 객체는 만들어지지 않는다). 키가 하나도 없어도 서버는 뜬다.

★ 무효 조건:
  - 싱크 memory·jsonl 의 누적 비용과 호출 간격은 프로세스 하나의 것이다. gunicorn 일꾼이 둘이면 상한(limits)과
    분당 요청 수(rpm)는 일꾼마다 따로 선다.
  - 싱크 db(LLM_LOG_SINK=db, sink_db.py)는 「테넌트(·모듈)」 범위의 상한에서 **커밋된 행을 일꾼을 넘어 센다**.
    거기까지다:
    미커밋 행, 다른 일꾼의 블록 안에서 되돌려진 줄의 비용, 전역·모듈만의 범위에서 다른 일꾼의 것은 세지 못한다
    (최악은 여전히 상한 × 일꾼 수쯤). 뜻과 세지 못하는 몫의 전부는 sink_db.py 의 머리말.
  - llm_client() 는 상한 없이 서지만 키도 싣지 않는다(LH2, MARC-ISSUE-411 S1): 실제 공급사 경로를 부르면
    LiveSetupError(키가 없다)다. 상한을 거는 실호출 길은 실행기(LLM_RUN_MODE=live — 실행 하나의 상한)와 관리 명령
    (--limit-usd)뿐이다. Scope 3 이 실경로로 가려면 실행기로 옮기거나 그때 상한을 세운다.
  - db 싱크의 기록은 요청의 트랜잭션에 기대지 않는다(요청마다의 트랜잭션이 없다): 트랜잭션 밖이면 줄마다 스스로
    커밋한다. 요청이 4xx·5xx 로 끝나도 그때까지 쓴 기록 줄은 남는다. 블록 안에서 쓴 줄만 그 블록과 같이 되돌려진다.
  - gunicorn 의 timeout 은 30초이고 호출의 기본 시간 제한은 120초다(client.DEFAULT_TIMEOUT_MS). 요청 안에서 부른
    호출이 30초를 넘으면 일꾼이 죽는다. 그때까지 커밋된 기록 줄은 남고, 끝나지 못한 호출의 줄은 없다(그 일꾼의
    메모리 누계도 같이 사라진다).
    긴 호출은 Celery 가 선 뒤의 일이다. 이 밴드(PY3b)는 두 값을 고치지 않았다.
  - openai·anthropic 은 SDK 재시도 0 + 호출 층 재시도 2(LH1)라 한 호출의 벽시계 최악은 client.py 머리의 셈(모델 하나에
    timeout × 3 + 대기)이다. Celery 작업의 soft·hard 시간(config/env.py)보다 길 수 있다.
"""

from collections.abc import Iterator, Mapping, Sequence
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Protocol

from esgapi.config.env import LlmSettings
from esgapi.core.conf import app_config
from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import ConfigSource, default_config_sources, load_config
from esgapi.core.llm.embedding import EmbeddingClient
from esgapi.core.llm.errors import LiveSetupError
from esgapi.core.llm.log import CallLogSink
from esgapi.core.llm.prompts import PackagePromptStore, PromptStore
from esgapi.core.llm.sinks.jsonl import JsonlFileSink
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.throttle import throttled
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.resources.ports.llm import EmbeddingProvider, Provider


class MakeProvider(Protocol):
    def __call__(self, name: str, *, api_key: str | None = None, assemble_only: bool = False) -> Provider: ...


class LazyProviders(Mapping[str, Provider]):
    """공급사 이름 → 어댑터. 처음 찾을 때 만든다(안 쓰는 공급사의 SDK 를 읽어 들이지 않고, 없는 키로 멈추지 않는다)."""

    def __init__(
        self, *, keys: Mapping[str, str | None], assemble_only: bool, rpm: float | None, make: MakeProvider
    ) -> None:
        self._keys = keys
        self._assemble_only = assemble_only
        self._rpm = rpm
        self._make = make
        self._made: dict[str, Provider] = {}

    def __getitem__(self, name: str) -> Provider:
        if name not in self._keys:
            raise KeyError(name)
        if name not in self._made:
            if name in llm_adapters.MOCK_PROVIDERS:
                self._made[name] = self._make(name)
            else:
                provider = self._make(name, api_key=self._keys[name], assemble_only=self._assemble_only)
                # 호출 간격은 실제 공급사에만 둔다.
                self._made[name] = provider if self._rpm is None else throttled(provider, self._rpm)
        return self._made[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)


class MakeEmbeddingProvider(Protocol):
    def __call__(self, name: str, *, api_key: str | None = None, assemble_only: bool = False) -> EmbeddingProvider: ...


class LazyEmbeddingProviders(Mapping[str, EmbeddingProvider]):
    """LazyProviders 의 임베딩 판. 호출 간격 조절(rpm)은 걸지 않는다(throttled 는 채팅 Provider 의 것이다)."""

    def __init__(self, *, keys: Mapping[str, str | None], assemble_only: bool, make: MakeEmbeddingProvider) -> None:
        self._keys = keys
        self._assemble_only = assemble_only
        self._make = make
        self._made: dict[str, EmbeddingProvider] = {}

    def __getitem__(self, name: str) -> EmbeddingProvider:
        if name not in self._keys:
            raise KeyError(name)
        if name not in self._made:
            if name in llm_adapters.MOCK_PROVIDERS:
                self._made[name] = self._make(name)
            else:
                self._made[name] = self._make(name, api_key=self._keys[name], assemble_only=self._assemble_only)
        return self._made[name]

    def __iter__(self) -> Iterator[str]:
        return iter(self._keys)

    def __len__(self) -> int:
        return len(self._keys)


def make_sink(settings: LlmSettings) -> CallLogSink:
    if settings.log_sink == "jsonl":
        if settings.jsonl_path is None:
            raise LiveSetupError("LLM_LOG_SINK 가 jsonl 인데 LLM_JSONL_PATH 가 없다")
        return JsonlFileSink(settings.jsonl_path)
    if settings.log_sink == "db":
        # 여기서만 import 한다: sink_db 는 모델(esgapi.core.models)을 읽는다. 순수 층의 setup import 가 끌지 않게.
        from esgapi.core.llm.sink_db import DbSink

        return DbSink()
    return MemorySink()


def build_client(
    settings: LlmSettings,
    *,
    limits: Sequence[BudgetLimit] = (),
    mock: bool = False,
    assemble_only: bool = False,
    sink: CallLogSink | None = None,
    prompts: PromptStore | None = None,
    store_bodies: bool = False,
    make: MakeProvider | None = None,
) -> LlmClient:
    """
    mock           모의 공급사 둘(mock, mock-b)과 가상 모델 파일을 같이 싣는다. 관리 명령과 테스트용.
                   서버의 클라이언트(llm_client)는 싣지 않는다.
    assemble_only  실제 공급사를 SDK 객체 없이(키 없이) 요청 조립만 하게 만든다. dry-run 용.
    store_bodies   기록에 요청 본문과 응답 글자를 남긴다. ★ DB 싱크와는 같이 쓰지 못한다(LiveSetupError):
                   본문은 공시 전 고객 데이터라 DB 에 두지 않는다(표에 칸이 없다).
    """
    log = sink or make_sink(settings)
    if store_bodies and not getattr(log, "accepts_bodies", True):
        raise LiveSetupError("DB 싱크(LLM_LOG_SINK=db)는 본문을 저장하지 않는다. store_bodies(--store-bodies)를 뺀다")
    sources = config_sources(settings, mock=mock)

    keys: dict[str, str | None] = {
        "openai": settings.openai_api_key,
        "anthropic": settings.anthropic_api_key,
        "gemini": settings.gemini_api_key,
    }
    if mock:
        keys.update(dict.fromkeys(llm_adapters.MOCK_PROVIDERS))
    return LlmClient(
        config=load_config(sources),
        providers=LazyProviders(
            keys=keys, assemble_only=assemble_only, rpm=settings.rpm, make=make or llm_adapters.make
        ),
        prompts=prompts or PackagePromptStore(),
        log=log,
        limits=limits,
        store_bodies=store_bodies,
    )


def config_sources(settings: LlmSettings, *, mock: bool) -> tuple[ConfigSource, ...]:
    """클라이언트가 읽는 모델 설정 파일들: LLM_MODELS_FILE 이 있으면 그것(mock 이면 가상 모델 파일을 뒤에), 없으면 기본.
    관리 명령(llm_call)의 live 판단도 이것을 읽는다 — 클라이언트와 같은 모델 파일로 가른다(LH3 Q5)."""
    if settings.models_file is None:
        return default_config_sources(synthetic=mock)
    sources: tuple[ConfigSource, ...] = (Path(settings.models_file),)
    return (*sources, *default_config_sources(synthetic=True)[1:]) if mock else sources


def build_embedding_client(
    settings: LlmSettings,
    *,
    limits: Sequence[BudgetLimit] = (),
    mock: bool = False,
    assemble_only: bool = False,
    sink: CallLogSink | None = None,
    make: MakeEmbeddingProvider | None = None,
) -> EmbeddingClient:
    """build_client 와 같은 꼴(설정 파일 고르기, 키는 설정에서 명시로, 공급사는 처음 찾을 때 만든다).

    mock           모의 임베딩 공급사(mock, mock-b)와 가상 모델 파일을 같이 싣는다(가상 임베딩 경로 mock-gw1).
    assemble_only  실제 공급사를 SDK 객체 없이(키 없이) 요청 조립만 하게 만든다. dry-run 용.
    sink           주지 않으면 make_sink(settings) 로 **채팅 클라이언트와 다른 싱크 객체**가 선다(메모리 싱크면 누계가
                   따로, DB 싱크면 행은 같은 표). 한 실행의 채팅·임베딩 줄과 상한을 한곳에 모으려면 부르는 쪽(실행기)이
                   같은 싱크를 sink= 로 넘긴다.
    ★ 무효 조건: 호출 간격 조절(settings.rpm)은 임베딩에 걸지 않는다. 상한 없이 세우는 것이 기본이다.
    """
    log = sink or make_sink(settings)
    sources = config_sources(settings, mock=mock)

    keys: dict[str, str | None] = {"openai": settings.openai_api_key}
    if mock:
        keys.update(dict.fromkeys(llm_adapters.MOCK_PROVIDERS))
    return EmbeddingClient(
        config=load_config(sources),
        providers=LazyEmbeddingProviders(
            keys=keys, assemble_only=assemble_only, make=make or llm_adapters.make_embedding
        ),
        log=log,
        limits=limits,
    )


@cache
def llm_client() -> LlmClient:
    """서버 요청 길(모듈 services)의 클라이언트 — 실제 공급사 키를 싣지 않는다(LH2, MARC-ISSUE-411 S1). 실호출은
    실행기(runs/context.py — 상한)와 관리 명령 llm_call(`--limit-usd`)뿐. LLM_RUN_MODE 와 무관하다(live 여도 비운다).
    설정의 나머지(기록 싱크·모델 파일·rpm)는 Django 설정에 실린 Config 에서 온다(환경 변수 LLM_*).
    """
    settings = replace(app_config().llm, openai_api_key=None, anthropic_api_key=None, gemini_api_key=None)
    return build_client(settings)
