"""흐름 greenwash.engine@G1 의 끼움(core/flows/binding.py 의 RunBinding + RunFactsBinding — 밴드 GE1b ②).

check_options(options)
    ① 실행 스위치(runs_enabled — 기본 꺼짐, D4)가 거짓이면 RunOptionsRejected(SWITCH_OFF) → 400 INVALID_OPTIONS,
    행 0. ② 옵션 꼴 greenwash.g1-options@1 = {parts} + 칸만 셋(criteriaId·industry·humanEvidence — null 만).
    parts 의 받기 차례·글은 binding_e0.accept_options 그대로(같은 함수를 부른다). 이어 돌기·고른 다시도 이 길이다.
inputs(document, options)
    G1Inputs(parts · ③ 칸 기본 = 기본 판 켠 줄·빈 카테고리). 문서 바이트는 쓰지 않는다 — 문서는 문서 포트(B3).
adapters(ctx)
    client = ctx.llm() · 임베딩 ClientEmbeddingPort(ctx.embedding(), route=EMBEDDING_ROUTE) · 탐지
    LlmChatBridge(같은 client, route=ROUTE, temperature None — D3) · 문서 포트 documents.for_run(회사, 실행) ·
    꼬리표 tenant = 회사 id 글자, module = 실행의 모듈.
versions_with(options, *, company_id)
    판 열쇠(아래). 회사와 무관(G1 은 회사별 판이 아직 없다 — ② 판 저장은 뒤).
inputs_with(..., versions)
    지금 지은 판 열쇠가 실행에 박힌 것(flow 뺌)과 다르면 RunVersionsMismatch(versions_mismatch).

판 열쇠(MARC-ENT-651 설정 세 층 — ① 엔진 고정은 흐름 판 G1, ② 운영 설정·③ 업무 지식은 판 열쇠만):
    engine "G1" · promptIds{facets, rerank, judge, detect} · promptTextsSha256{같은 넷}(core ai_versions 의
    promptsSha256 과 다른 이름 — R2) · routes{chat: {route, models: [경로의 모델 목록 그대로]}, embedding: {route,
    model}}(models.json — 감독 답) · parserLayout 2 · epoch(core 문서 산출물 EPOCH) · criteriaId null(기본 판만 —
    D2) · criteriaVersion · criteriaSha256 · categoriesSha256 · variant null(자리만).
    지시문 sha: facets·rerank·judge 는 템플릿 원문의 sha(PromptTemplate.hash), detect 는 E0 의 감싼 템플릿(detect@1 —
    {{system}}·{{user}} 만)이라 그 sha 와 E0 탐지 지시 글(PromptPack.detect_system_prompt)을 이어 다시 sha.
    ★ 무효 조건: 문턱(RRF·근거 12,000자 등)·답 상한·경로 밖의 모델 설정이 바뀌어도 판 열쇠로 못 가른다(후속 ⓐ).
    Directive: 엔진 동작(passages·상한·지시문 밖 코드)을 바꾸면 흐름 판을 올린다 — 판 열쇠에 엔진 코드 판이 없다.
    첫 켜기 전까지는 G1 을 고쳐 쓴다 — 켠 뒤부터 판을 올린다(GE1c: 도표 단위·근거 예산 12,000 을 G1 에 넣음.
    greenwash_g1_runs_enabled 가 켜진 적 없어 G1 실행 0 — 랩 기록의 「G1」은 GE1c 앞 동작이라 esg-app 커밋으로 부른다).
models(ModelConfigSource — E0 의 RunModelSource 와 같은 원천)·prompts(PromptStore)·documents·runs_enabled 는 기본값
없이 받는다(apps.py 가 꽂는다). 이 파일은 순수다(django 0 — .importlinter 계약 다).
"""

import json
from collections.abc import Callable, Mapping
from typing import Final, Protocol

from esgapi.core.documents.contract import EPOCH
from esgapi.core.flows.binding import (
    DocumentInput,
    RunContext,
    RunOptionsRejected,
    RunVersionsMismatch,
    RunVersionsRejected,
)
from esgapi.core.llm.config import LlmConfig
from esgapi.core.llm.embedding import ClientEmbeddingPort
from esgapi.core.llm.log import sha256_text
from esgapi.core.llm.prompts import PromptStore, parse_prompt_id
from esgapi.core.llm.types import Tags
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.engines.g1 import judge as jd
from esgapi.greenwash.flows import binding_e0, colab_e0, criteria_e0
from esgapi.greenwash.flows import engine_g1 as E

OPTIONS_SHAPE: Final = "greenwash.g1-options@1"
NULL_ONLY: Final = ("criteriaId", "industry", "humanEvidence")
OPTION_KEYS: Final = frozenset({"parts", *NULL_ONLY})
SWITCH_OFF: Final = "그린워싱 2차 엔진 실행은 아직 열려 있지 않아요. 운영자에게 알려 주세요"
NULL_ONLY_REFUSED: Final = "기준 판·산업·사람 근거는 이 판에서 칸만 있어요(null)"
PARSER_LAYOUT: Final = 2
PROMPT_IDS: Final[Mapping[str, str]] = {
    "facets": E.PLAN_PROMPT,
    "rerank": E.RERANK_PROMPT,
    "judge": E.JUDGE_PROMPT,
    "detect": colab_e0.PROMPT_IDS["detect"],
}


class G1DocumentSource(Protocol):
    """실행 하나의 문서 포트를 짓는다(몸 service/actions/engine_g1.RunG1Documents)."""

    def for_run(self, company_id: int, run_id: int) -> E.G1Document: ...


class ModelConfigSource(Protocol):
    """경로 → 모델 이름의 원천(service/selectors/ai_settings.RunModelSource 가 채운다)."""

    def config(self) -> LlmConfig: ...


def _keys(keys: list[str]) -> str:
    return ", ".join(sorted(keys))


def accept_options(options: Mapping[str, object]) -> dict[str, tuple[int, ...]]:
    """greenwash.g1-options@1 → 파트별 쪽. 차례: 모르는 열쇠 → parts(binding_e0.accept_options 의 차례·글) → 칸만 셋."""
    unknown = [k for k in options if k not in OPTION_KEYS]
    if unknown:
        raise RunOptionsRejected(f"알 수 없는 옵션이에요: {_keys(unknown)}")
    pages, _extra = binding_e0.accept_options({k: v for k, v in options.items() if k == "parts"})
    if any(options.get(k) is not None for k in NULL_ONLY):
        raise RunOptionsRejected(NULL_ONLY_REFUSED)
    return {part: tuple(pages[part]) for part in E.PARTS}


def _json_sha(value: object) -> str:
    return sha256_text(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")))


def criteria_sha256(lines: tuple[jd.CriterionLine, ...]) -> str:
    return _json_sha([{"id": c.id, "group": c.group, "text": c.text} for c in lines])


def categories_sha256(categories: tuple[str, ...]) -> str:
    return _json_sha(list(categories))


class G1Binding:
    def __init__(
        self,
        *,
        runs_enabled: Callable[[], bool],
        documents: G1DocumentSource,
        models: ModelConfigSource,
        prompts: PromptStore,
    ) -> None:
        self.runs_enabled = runs_enabled
        self.documents = documents
        self.models = models
        self.prompts = prompts

    def check_options(self, options: Mapping[str, object]) -> None:
        if not self.runs_enabled():
            raise RunOptionsRejected(SWITCH_OFF)
        accept_options(options)

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> E.G1Inputs:
        return E.G1Inputs(parts=accept_options(options))

    def adapters(self, ctx: RunContext) -> E.G1Adapters:
        tags = Tags(tenant=str(ctx.company_id), module=ctx.module)
        client = ctx.llm()
        return E.G1Adapters(
            client=client,
            embedding=ClientEmbeddingPort(ctx.embedding(), route=E.EMBEDDING_ROUTE, tags=tags),
            detect=colab_e0.LlmChatBridge(client, route=E.ROUTE, tags=tags, temperature=None),
            tags=tags,
            document=self.documents.for_run(ctx.company_id, ctx.run_id),
        )

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return self.keys()

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        return self.keys()

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> E.G1Inputs:
        made = {k: v for k, v in versions.items() if k != "flow"}
        try:
            now = self.keys()
        except RunVersionsRejected as refused:
            raise RunVersionsMismatch(refused.message) from refused
        if made != now:
            changed = sorted(k for k in {*made, *now} if made.get(k) != now.get(k))
            raise RunVersionsMismatch(f"G1 판 열쇠가 실행을 만들 때와 다르다: {', '.join(changed)}")
        return self.inputs(document, options)

    def prompt_shas(self) -> dict[str, str]:
        shas = {name: self.prompts.get(parse_prompt_id(pid)).hash for name, pid in PROMPT_IDS.items()}
        shas["detect"] = sha256_text(shas["detect"] + "\n" + default_prompts(PROMPT_VERSION).detect_system_prompt)
        return shas

    def routes(self) -> dict[str, object]:
        config = self.models.config()
        chat = config.routes.get(E.ROUTE)
        embedding = config.embedding_routes.get(E.EMBEDDING_ROUTE)
        if not chat or embedding is None:
            raise RunVersionsRejected("그린워싱 2차 엔진의 모델 경로를 찾지 못했어요. 운영자에게 알려 주세요")
        return {
            "chat": {"route": E.ROUTE, "models": list(chat)},
            "embedding": {"route": E.EMBEDDING_ROUTE, "model": embedding},
        }

    def keys(self) -> dict[str, object]:
        """판 열쇠 한 벌(머리말). 같은 설정이면 늘 같은 값."""
        lines = E.default_criterion_lines()
        return {
            "engine": "G1",
            "promptIds": dict(PROMPT_IDS),
            "promptTextsSha256": self.prompt_shas(),
            "routes": self.routes(),
            "parserLayout": PARSER_LAYOUT,
            "epoch": EPOCH,
            "criteriaId": None,
            "criteriaVersion": criteria_e0.DEFAULT_VERSION,
            "criteriaSha256": criteria_sha256(lines),
            "categoriesSha256": categories_sha256(E.CATEGORIES),
            "variant": None,
        }
