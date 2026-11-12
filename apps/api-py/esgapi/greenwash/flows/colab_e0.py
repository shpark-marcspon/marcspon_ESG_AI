"""흐름 greenwash.colab@E0 — 마크스폰 Colab 노트북을 약점까지 옮긴 GW1(engines/e0 의 사본)을 단계 여섯으로 끊어 돈다.

    extract → index → judge → wordcount → locate → report

입력 꼴 greenwash.document@1(GreenwashInputs), 결과 꼴 greenwash.result@1(contracts/shapes.py),
출력 파일 greenwash-report.xlsx.
같은 입력이면 GW1 `cli scan` 과 같은 결과·같은 호출 차례를 낸다(tests/flows 의 대조 A·B·D, OUT 의 PDF 판·대조 C).

- extract   PDF bytes → 쪽 글, sha256, 쪽 수, 파트별 쪽(parts.build_section_pages).
            data.pages 는 안정 계약(MARC-TICK-74 노트). 모든 쪽의 글이 공백뿐이면(글자 층 없는 스캔 PDF) NoTextLayer
            (core.flows.types) — 실행기는 failed·no_text_layer(failedStep extract)로 끝낸다(밴드 G1b,
            runs/calc/errors.py)
- index     문서 전체를 조각내고(GW1 cli.run_scan 과 같은 설정) 조각 벡터를 짓는다. 점검 쪽이 없으면 건너뛴다(노트북은
            스캔을 부르지 않는다). dry-run 이면 조각만 내고 임베딩을 부르지 않는다. 벡터는 파일 index-vectors.f32
            (float32 little-endian, 줄 차례 = 조각 차례) — GW1 VectorIndex 가 float32 로 담으므로 왕복해도 순위가 같다
- judge     checker.scan_report_greenwashing_pages 를 부르고 쪽마다 체크포인트한다(ctx.checkpoint, resume).
            쪽 안의 예외는 GW1 처럼 삼켜 failed_pages 에 적는다(흠 12·19) — 그래서 이 단계가 「실패」로 끝나는 길은
            어댑터 밖(사건 받는 쪽의 예외, 프로세스 죽음)뿐이고 이어 돌기의 근거는 step_progress 의 partial 이다.
            dry-run 이면 llm·embedding 을 부르지 않고 tokens 로 GW1 dryrun.dry_run 을 돈다
- wordcount 의심 낱말을 문서 전체에서 센다(AI 없음, dry-run 에도 돈다)
- locate    판정 문장마다 쪽 위 자리. coordinates 가 없거나 dry-run 이면 전부 null. 닫는 좌표(ClosingCoordinatesPort —
            끼움의 PdfiumCoordinates)면 끝에(예외에도) 닫고 data.stats 에 셈을 싣는다(dry-run 이면 닫기만, G1b-2b)
- report    greenwash.result@1 조립과 엑셀(dry-run 이면 엑셀 없음)

단계는 순수 함수다: 앞 단계의 산출물은 carried[<이름>].data(JSON 왕복한 값)와 .files 에서만 읽는다.

추가 단어(입력 extra_terms, G1c): 노트북의 스위치 env_keywords_extra(판정 대상 키워드 = 환경 낱말)를 켜고 낱말 빈도
목록에도 더한다. 엔진 사본은 그대로다. 사용자 글자는 re.escape 뒤에 환경 낱말 정규식으로 가고, 노트북이 바꾸고 되돌리지
않는 모듈 전역(heuristics._ENV_KEYWORDS_RE, 흠 18)은 judge 가 끝날 때(성공·실패·예외) 기본으로 되돌린다. 추가 단어가
없으면 전역을 건드리지 않는다 — 그래서 결과가 추가 단어 이전(G1a)과 extra_terms 칸 밖에서 바이트까지 같다.
무효 조건: 한 프로세스에서 스레드 둘이 judge 를 동시에 돌리면 전역을 다툰다(Celery prefork — 프로세스마다 하나 — 가정).

판정 기준표(입력 criteria, greenwash.criteria@1 — G2c): 판정(EVAL) 프롬프트를 flows/criteria_e0 의 고정 틀 + 기준표로
조립해 노트북 스캔에 prompts 로 넘기고, 대화 다리(LlmChatBridge)를 그 묶음으로 바꿔 끼운다(with_pack). 엔진 사본은
그대로다. 기준표가 없으면(None) prompts 를 넘기지 않는 지금 길 그대로다 — 기본 판 기준표를 넣어도 조립 글이 엔진 글과
바이트가 같으므로 요청·결과가 기준표 이전과 바이트까지 같다(tests/flows/test_criteria_flow.py). dry-run 은 엔진
dryrun 이 안에서 기본 프롬프트를 지어 어림하므로(엔진 사본 그대로), 기준표가 있으면 judge 가 그 뒤에 판정(eval) 몫만
보정한다(밴드 G2c2 Q8): 아래끝·위끝의 eval 요청 수 × (고친 EVAL − 기본 EVAL)의 글자·토큰을 eval 칸과 합(chat)에
더한다. 표지는 judge 단계 산출의 `eval_prompt_adjustment` 칸(결과 꼴 result@1 은 그대로 — 그 칸은 결과로 가지 않는다).
기준표가 없으면 지금 갈래 그대로(결과 바이트 같음).

이 파일이 E0 판에서 엔진(engines/e0)과 계약(contracts)을 잇는 자리다. 어댑터 꼴(GreenwashAdapters)과 E0 에 묶인 구현
(LlmChatBridge — 노트북 프롬프트 넷 검사, PROMPT_IDS·CHAT_ROUTE·MAX_OUTPUT_TOKENS, TiktokenCounter, 읽개 PDF_TEXT)도
여기 있다. 판 무관 도구는 tools/ 에 있다. 이 파일은 설정·환경 변수·키를 읽지 않고 SDK 클라이언트를 짓지 않는다
(tests/flows/test_boundary.py 가 AST 로 잰다). 클라이언트·읽개·좌표는 부르는 쪽이 지어 GreenwashAdapters 로 넘긴다.
"""

import copy
import hashlib
import re
from collections import Counter
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

import numpy as np
from langchain_core.documents import Document

from esgapi.core.calc.ai_settings import AcceptedPrompts, AcceptedStep, PromptLayout
from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowStep, NoTextLayer, OutputFile, StepContext, StepOutput
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.core.llm.types import Tags
from esgapi.greenwash.contracts import wire
from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria
from esgapi.greenwash.engines.e0 import checker as checker_mod
from esgapi.greenwash.engines.e0 import result as gw1_result
from esgapi.greenwash.engines.e0 import wordcount as wordcount_mod
from esgapi.greenwash.engines.e0.checker import (
    GWConfig,
    sanitize_config_dict,
    scan_report_greenwashing_pages,  # pyright: ignore[reportUnknownVariableType]
)
from esgapi.greenwash.engines.e0.chunking import build_chunks_from_docs
from esgapi.greenwash.engines.e0.gw1 import (
    GREEN_TERMS,
    build_results_by_part,
    count_green_terms,
    dry_run,
    frequency_extras,
    set_env_keywords,
    term_key,
)
from esgapi.greenwash.engines.e0.parts import build_section_pages
from esgapi.greenwash.engines.e0.pdftext import docs_from_texts
from esgapi.greenwash.engines.e0.ports import (
    CHAT_ENCODING,
    EMBEDDING_MODEL,
    ChatPort,
    ChatReply,
    EmbeddingPort,
    Message,
    TokenCounter,
    prompt_kind,
    tiktoken_counter,
)
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, PromptPack, default_prompts
from esgapi.greenwash.engines.e0.retrieval import VectorIndex
from esgapi.greenwash.flows import criteria_e0
from esgapi.greenwash.flows.criteria_e0 import accept_criteria, eval_pack
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.tools.llm_bridge import LlmTextCall
from esgapi.greenwash.tools.pdftext_pypdf import PypdfText
from esgapi.greenwash.tools.ports import ClosingCoordinatesPort, CoordinatesPort, PdfTextPort, TokenCounterPort

FLOW_ID: Final = "greenwash.colab@E0"
RESULT_SHAPE: Final = "greenwash.result@1"
REPORT_FILE: Final = "greenwash-report.xlsx"
VECTORS_FILE: Final = "index-vectors.f32"
PDF: Final = "application/pdf"
LEVELS: Final = ("High", "Mid", "Low")
DEFAULT_TERMS: Final = wordcount_mod.GREEN_TERMS
"""경로 GET terms/default 가 내는 기본 단어 — 엔진의 노트북 목록 그대로(같은 객체). 표면은 엔진을 직접 들이지 않고 이
이름으로 받는다(흐름이 엔진과 계약을 잇는 유일한 자리)."""

SCAN_CONFIG: Final[dict[str, Any]] = {"debug": True, "debug_pages": 2}
"""노트북 셀 16 의 스캔 설정. GW1 cli.SCAN_CONFIG 와 같은 값(cli 는 복사하지 않는다 — section4 다-16 이 견준다)."""
CHUNK_ARGS: Final[dict[str, Any]] = {
    "chunk_size": 800,
    "chunk_overlap": 150,
    "embedding_model": "text-embedding-3-small",
    "embedding_batch_size": 50,
    "normalize": True,
}
"""GW1 cli.run_scan 이 build_chunks_from_docs 에 주는 값."""
MODEL_NAME: Final = checker_mod.MODEL_NAME
TEMPERATURE: Final = checker_mod.TEMPERATURE
MAX_TOKENS: Final = checker_mod.MAX_TOKENS
EMPTY_AGG: Final = ("raw", "hard_dropped", "non_env_dropped", "promo_dropped", "table_dropped", "kept")
EXTRA_TERMS_MAX: Final = 30
EXTRA_TERM_CHARS: Final = 30
EXTRA_TERM_REFUSED: Final = re.compile(r"[(){}\[\]\"'“”‘’]")
"""engines/e0/wordcount.normalize_text 가 본문에서 공백으로 바꾸는 괄호·따옴표 — 이 글자가 든 단어는 결코
세어지지 않는다."""


# ── 어댑터: 꼴과 E0 에 묶인 구현(옛 flows/adapters.py) ─────────────────────────────────────

MAX_OUTPUT_TOKENS: Final = 1300
"""노트북의 max_tokens(GW1 checker.MAX_TOKENS). section4 다-16 이 GW1 의 값과 견준다."""


@dataclass(frozen=True, slots=True, kw_only=True)
class GreenwashAdapters:
    """흐름의 어댑터. 칸 이름이 곧 어댑터 이름표다. coordinates·tokens 는 선택(없으면 흐름이 그 일을 건너뛴다).

    pdf_text     PDF bytes → 쪽 글(extract)
    llm          GW1 의 대화 포트: invoke(messages) -> ChatReply(judge, dry-run 이면 부르지 않음)
    embedding    GW1 의 임베딩 포트: embed_documents·embed_query(index·judge, dry-run 이면 부르지 않음).
                 L1 의 core.llm.embedding.ClientEmbeddingPort 가 같은 꼴이다
    coordinates  문장의 쪽 위 자리(locate). None 이면 position 이 전부 null
    tokens       토큰 세기(dry-run 의 judge 에 필수. 없으면 judge 가 실패한다 — 발주서 ★C)
    """

    pdf_text: PdfTextPort
    llm: ChatPort
    embedding: EmbeddingPort
    coordinates: CoordinatesPort | None = None
    tokens: TokenCounterPort | None = None


TiktokenCounter: Callable[[], TokenCounter] = tiktoken_counter
"""GW1 의 tiktoken 토큰 세기(engines/e0/ports.tiktoken_counter). 부호화 파일이 없으면 그 부호화는 「못 쟀다」로 남는다 —
pytest 는 이것을 부르지 않는다(부호화 파일을 내려받을 수 있다). 대조 C 는 G1a.out 에서 받아 둔 파일로만 쓴다."""


PROMPT_IDS: Final[Mapping[str, str]] = {
    "detect": "greenwash/detect@1",
    "eval": "greenwash/eval@1",
    "repair": "greenwash/repair@1",
    "low_only": "greenwash/low-only@1",  # core 의 id 문법에 밑줄이 없다
}
"""GW1 프롬프트 종류(e0 ports.prompt_kind) → core.llm 프롬프트 id. 템플릿은 esgapi/greenwash/prompts/<이름>/1.md 이고
넷 다 `=== system ===\n{{system}}\n=== user ===\n{{user}}` 꼴이다 — 노트북의 글에는 `{{` 가 있어 템플릿에 그대로
넣으면 변수로 치환되므로, 글은 변수로 넘긴다(core 는 한 번만 치환하고 넣은 값을 다시 훑지 않는다)."""

JUDGE_STEP: Final = "judge"
"""프롬프트 넷을 부르는 단계(모델 설정·프롬프트 글의 단계 key — flows/prompt_model_e0.JUDGE)."""
LAYOUT: Final[PromptLayout] = ((JUDGE_STEP, tuple(PROMPT_IDS)),)
"""core check_prompts 에 넘기는 명세(단계 key, 칸 key 차례 — PROMPT_IDS 차례). 판 저장·보기(prompt_model_e0.LAYOUT 은
이것)와 워커(binding_e0)가 같은 이것을 본다 — binding_e0 는 prompt_model_e0 을 들이지 않는다(밴드 AS3a-2 M2)."""
PROMPT_FIELDS: Final[Mapping[str, str]] = {
    "detect": "detect_system_prompt",
    "eval": "eval_system_prompt",
    "repair": "repair_fix_prompt",
    "low_only": "low_only_prompt",
}
"""칸 key → PromptPack 칸. 열쇠 차례는 PROMPT_IDS 와 같다(tests/flows/test_prompt_model_e0.py)."""


def pack_from(accepted: AcceptedPrompts) -> PromptPack:
    """판의 저장 글(core check_prompts(…, layout=LAYOUT) 를 지난 값) → 노트북 스캔에 넘길 프롬프트 넷. 글은 바이트
    그대로다(판 글자 [PromptVersion: …] 도 저장 글의 것)."""
    (judge,) = (step for step in accepted.steps if step.key == JUDGE_STEP)
    texts = {prompt.key: prompt.text for prompt in judge.prompts}
    return PromptPack(**{field: texts[key] for key, field in PROMPT_FIELDS.items()})


CHAT_ROUTE: Final = "light-openai-41"
"""대화 다리의 기본 경로 — core/llm/data/models.json 의 경로 이름(gpt-4.1-mini 하나. 밴드 GM1 `MARC-TICK-134`).
노트북의 모델(GW1 checker.MODEL_NAME)이고, temperature 를 받는 모델만 든 경로라 코랩 온도를 넘길 수 있다."""


class LlmChatBridge:
    """GW1 의 대화 포트(invoke(messages) -> ChatReply) → core.llm 의 LlmClient.call(tools/llm_bridge.LlmTextCall 로).

    messages 는 [system, user] 둘이어야 하고, system 글로 프롬프트 종류를 가른다(넷이 아니면 예외). 결과 갈래가
    Success 가 아니면 예외 — 노트북에서 대화 예외는 그 쪽을 실패로 넘긴다(흠 12 와 같은 길).
    temperature 는 코랩 온도(GW1 checker.TEMPERATURE, 0.0)를 core.llm 에 넘긴다(밴드 LT1 `MARC-TICK-136`). 경로의
    모델이 전부 temperature 를 받아야 한다 — 받지 않는 모델이 있으면 공급사를 부르기 전에 LlmConfigError.
    클라이언트는 부르는 쪽이 짓는다.

    pack 은 system 글을 가르는 프롬프트 넷(없으면 노트북 기본). 판정 기준표가 있는 실행에서는 judge 가
    with_pack(<기준표로 지은 묶음>) 으로 바꿔 끼운다 — 끼움의 adapters(ctx) 는 실행 옵션을 보지 못해
    (core/flows/binding.py 의 RunBinding.adapters) 다리를 지을 때 기준표를 모르기 때문이다.
    판의 모델 설정(밴드 AS2b)도 같은 까닭으로 judge 가 with_model(경로, temperature, 출력 상한)으로 바꿔 끼운다.
    기본값(CHAT_ROUTE·TEMPERATURE·MAX_OUTPUT_TOKENS)으로 지은 다리의 요청은 AS2b 앞과 바이트 같다. with_pack·
    with_model 은 서로의 값을 물려받는다(부르는 차례와 무관).
    """

    def __init__(
        self,
        client: LlmClient,
        *,
        route: str = CHAT_ROUTE,
        tags: Tags,
        pack: PromptPack | None = None,
        temperature: float | None = TEMPERATURE,
        max_output_tokens: int = MAX_OUTPUT_TOKENS,
    ) -> None:
        self.client = client
        self.route = route
        self.tags = tags
        self.pack = pack if pack is not None else default_prompts(PROMPT_VERSION)
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def with_pack(self, pack: PromptPack) -> "LlmChatBridge":
        """같은 client·route·tags·temperature·출력 상한으로 프롬프트 넷만 바꾼 새 다리."""
        return LlmChatBridge(
            self.client,
            route=self.route,
            tags=self.tags,
            pack=pack,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )

    def with_model(self, route: str, temperature: float | None, max_output_tokens: int) -> "LlmChatBridge":
        """같은 client·tags·pack 으로 경로·temperature(None = 싣지 않음)·출력 상한만 바꾼 새 다리(AS2b)."""
        return LlmChatBridge(
            self.client,
            route=route,
            tags=self.tags,
            pack=self.pack,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

    def invoke(self, messages: Sequence[Message]) -> ChatReply:
        if len(messages) != 2 or (messages[0].role, messages[1].role) != ("system", "user"):
            raise ValueError(f"메시지는 [system, user] 둘이어야 한다: {[m.role for m in messages]}")
        system, user = messages[0].content, messages[1].content
        kind = prompt_kind(system, self.pack)
        if kind not in PROMPT_IDS:
            raise ValueError("system 글이 노트북의 프롬프트 넷 가운데 하나가 아니다")
        call = LlmTextCall(
            self.client,
            route=self.route,
            tags=self.tags,
            temperature=self.temperature,
            max_output_tokens=self.max_output_tokens,
        )
        return ChatReply(content=call.complete(PROMPT_IDS[kind], system, user))


PDF_TEXT: Final = PypdfText
"""이 판이 고른 PDF 읽개(MARC-ENT-267 「판이 고른다」). 부르는 쪽이 `colab_e0.PDF_TEXT()` 로 짓는다.
다른 읽개를 쓰는 판은 자기 흐름 파일에서 이 한 줄을 바꾼다(그때 tools/coordinates.py 의 찾기 상수를 다시 잰다)."""


# ── 입력과 단계 ──────────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True, kw_only=True)
class GreenwashInputs:
    """greenwash.document@1. 쪽 입력 셋은 노트북 셀 16 의 input() 셋 — "5", "6~14", "25-37,55~74", ""(그 파트 없음)."""

    document: bytes
    media_type: str
    file_name: str
    ceo: str
    company: str
    climate: str
    dry_run: bool = False
    extra_terms: tuple[str, ...] = ()
    """추가 단어. 만들 때 accept_extra_terms 로 정규화·검사한다(어기면 ValueError — 문장은 화면에 그대로 보일 꼴)."""
    criteria: GreenwashCriteria | None = None
    """판정 기준표(greenwash.criteria@1). None 이면 기본 판(지금 길). 만들 때 criteria_e0.accept_criteria 로 검사한다
    (어기면 CriteriaRejected — ValueError)."""
    model: AcceptedStep | None = None
    """판정(judge) 단계의 모델 설정(받기를 거친 값 — 밴드 AS2b). None = 다리를 지은 그대로(기본값)."""
    prompts: PromptPack | None = None
    """판의 저장 글 넷(pack_from — 밴드 AS3a-2). None = 코드 글(기준표 묶음 또는 지금 길). 값이면 기준표 묶음보다 앞선다
    (저장 글이 있으면 EVAL 도 저장 글)."""
    terms: tuple[str, ...] | None = None
    """판의 켠 대상 단어(판 차례 — 밴드 G2d, 끼움이 terms_e0 로 받은 값). None = 코드 기본 목록 GREEN_TERMS(지금 길).
    빈도 목록(wordcount)만 바꾼다 — 판정할 문장을 고르는 환경 신호(scan_config)에는 닿지 않는다(MARC-ENT-394)."""

    def __post_init__(self) -> None:
        object.__setattr__(self, "extra_terms", accept_extra_terms(self.extra_terms))
        if self.criteria is not None:
            object.__setattr__(self, "criteria", accept_criteria(self.criteria))


def accept_extra_terms(given: object) -> tuple[str, ...]:
    """추가 단어 받기(발주서 G1c 「정한 것」 4). 차례: 앞뒤 공백을 지우고 빈 것을 버림 → 괄호·따옴표가 든 단어 거절 →
    비교 키에 글자·숫자(str.isalnum)가 없는 단어 거절 → 비교 키(gw1.term_key)가 같은 것은 처음 것만 → 한 단어 1~30자,
    30개까지. 받은 꼴(앞뒤 공백만 지운 것)을 받은 차례로 돌려준다. 기본 목록과 겹친 단어는 거절하지 않는다(빈도에
    더하지 않을 뿐 — frequency_extras)."""
    if isinstance(given, str) or not isinstance(given, (list, tuple)):
        raise ValueError("추가 단어는 단어의 목록으로 넣어요")
    stripped: list[str] = []
    for term in cast("list[object] | tuple[object, ...]", given):
        if not isinstance(term, str):
            raise ValueError("추가 단어는 글자여야 해요")
        if term.strip():
            stripped.append(term.strip())
    if any(EXTRA_TERM_REFUSED.search(term) for term in stripped):
        raise ValueError("추가 단어에는 괄호나 따옴표를 쓸 수 없어요")
    if not all(any(c.isalnum() for c in term_key(term)) for term in stripped):
        # `.` 하나가 거의 모든 문장을, `-` 가 하이픈이 든 모든 문장을 환경 문장으로 만든다(감독 결정, G1c 검증 지적 1)
        raise ValueError("추가 단어에는 글자나 숫자가 하나 이상 있어야 해요")
    seen: set[str] = set()
    accepted: list[str] = []
    for term in stripped:
        key = term_key(term)
        if key not in seen:
            seen.add(key)
            accepted.append(term)
    if any(len(term) > EXTRA_TERM_CHARS for term in accepted):
        raise ValueError(f"추가 단어는 1~{EXTRA_TERM_CHARS}자여야 해요")
    if len(accepted) > EXTRA_TERMS_MAX:
        raise ValueError(f"추가 단어는 {EXTRA_TERMS_MAX}개까지 넣을 수 있어요")
    return tuple(accepted)


def scan_config(inputs: GreenwashInputs) -> dict[str, Any]:
    """judge 가 노트북 스캔(과 dry-run)에 넘기는 설정: SCAN_CONFIG 의 사본. 추가 단어가 있으면 노트북의 갈래
    env_keywords_extra 를 켠다 — 단어마다 re.escape(heuristics.build_env_keywords_re 는 조각을 그대로 `|` 로 잇는다)."""
    config = dict(SCAN_CONFIG)
    if inputs.extra_terms:
        config["env_keywords_extra"] = [re.escape(term) for term in inputs.extra_terms]
    return config


def scan_cfg() -> GWConfig:
    """GW1 cli._cfg(SCAN_CONFIG)."""
    cfg = GWConfig()
    for k, v in sanitize_config_dict(dict(SCAN_CONFIG)).items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg


def judge_chat(
    llm: ChatPort,
    *,
    prompts: PromptPack | None,
    criteria: GreenwashCriteria | None,
    model: AcceptedStep | None,
    version: str,
) -> tuple[ChatPort, PromptPack | None]:
    """판정에 쓸 대화 포트와 프롬프트 묶음 — 판의 저장 글(prompts)이 값이면 그 묶음, 아니고 기준표가 있으면
    기준표로 지은 묶음(eval_pack), 둘 다 없으면 None(엔진 기본). 모델 설정(model)이 값이면 with_model, 묶음이
    있으면 with_pack. judge(_judge)와 재판단(flows/rejudge_e0.judge, 밴드 GRJ1)이 같은 이 길을
    탄다(원 실행과 같은 판의 같은 다리)."""
    pack = prompts if prompts is not None else (None if criteria is None else eval_pack(criteria, version))
    if model is not None:
        if not isinstance(llm, LlmChatBridge):
            raise TypeError(f"모델 설정이 있는 실행은 대화 포트가 LlmChatBridge 여야 한다: {type(llm).__name__}")
        llm = llm.with_model(model.route, model.temperature, model.max_output_tokens)
    if pack is not None:
        if isinstance(llm, LlmChatBridge):
            llm = llm.with_pack(pack)
        elif pack != default_prompts(version):
            # 다리를 감싼 포트는 고친 글을 가르지 못해 쪽마다 예외 → checker 가 삼켜 전 쪽 실패인 「완료」가 된다.
            # 그 전에 쪽 루프 밖에서 실패시킨다(가지 리뷰 3). 기준표 묶음은 EVAL 만 다르니 넷 견줌이 같은 뜻이다.
            raise TypeError(f"프롬프트가 기본과 다른 실행은 대화 포트가 LlmChatBridge 여야 한다: {type(llm).__name__}")
    return llm, pack


def judged_prompt_version(config: dict[str, Any]) -> str:
    """노트북 스캔(checker.scan_report_greenwashing_pages)이 쓸 프롬프트 판 글자 — 같은 길(sanitize_config_dict →
    GWConfig)로 얻는다. 기준표로 지은 묶음의 판 글자가 checker 의 것과 같아야 한다."""
    cfg = GWConfig()
    for k, v in sanitize_config_dict(dict(config)).items():
        if hasattr(cfg, k):
            setattr(cfg, k, v)
    return cfg.prompt_version


def run_versions(criteria: object) -> dict[str, object]:
    """실행 판 묶음에 실을 값 {"aiSetting", "evalPromptSha256"} — 그린워싱 끼움의 versions(options) 가 부른다(G1b).
    판 글자는 judge 와 같은 길(judged_prompt_version(SCAN_CONFIG))로 얻는다. 추가 단어가 scan_config 에 더하는
    env_keywords_extra 는 판 글자에 닿지 않는다. criteria 는 받기 전 원본도 된다(criteria_e0.run_versions)."""
    return criteria_e0.run_versions(criteria, judged_prompt_version(dict(SCAN_CONFIG)))


def _data(carried: Carried, step: str) -> dict[str, Any]:
    return cast("dict[str, Any]", carried[step].data)


def _docs(carried: Carried) -> list[Document]:
    return docs_from_texts(cast("list[str]", _data(carried, "extract")["pages"]))


# ── extract ──────────────────────────────────────────────────────────────────


def extract(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    if inputs.media_type != PDF:
        raise ValueError(f"PDF 가 아니다: {inputs.media_type!r}")
    pages = adapters.pdf_text.page_texts(inputs.document)
    if not any(page.strip() for page in pages):
        raise NoTextLayer("글자 층이 없는 문서예요")
    section_pages, manual_pages = build_section_pages(inputs.ceo, inputs.company, inputs.climate, len(pages))
    return StepOutput(
        data={
            "pages": pages,
            "sha256": hashlib.sha256(inputs.document).hexdigest(),
            "page_count": len(pages),
            "section_pages": section_pages,
            "manual_pages": manual_pages,
        }
    )


# ── index ────────────────────────────────────────────────────────────────────


def index(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    if not _data(carried, "extract")["manual_pages"]:
        # GW1 cli.run_scan: 점검 쪽이 없으면 조각내기·임베딩을 하지 않는다.
        return StepOutput(data={"chunks": [], "chunk_config": None, "empty_chunks": 0, "vectors": None})
    built = build_chunks_from_docs(_docs(carried), **CHUNK_ARGS)
    chunks = cast("list[Document]", built["chunks"])
    data: dict[str, Any] = {
        "chunks": [{"page_content": c.page_content, "metadata": c.metadata} for c in chunks],
        "chunk_config": built["config"],
        # L1 의 임베딩 포트는 빈 글자를 거절한다. 흐름은 빈 조각을 거르지 않고(거르면 색인의 줄이 노트북과 달라진다)
        # 수만 싣는다 — 표본·공개 보고서에서 0 임을 대조로 보인다.
        "empty_chunks": sum(1 for c in chunks if not c.page_content),
        "vectors": None,
    }
    if inputs.dry_run:
        return StepOutput(data=data)
    vectors = np.asarray(adapters.embedding.embed_documents([c.page_content for c in chunks]), dtype=np.float32)
    matrix = vectors.reshape(len(chunks), -1)
    data["vectors"] = {"file": VECTORS_FILE, "rows": int(matrix.shape[0]), "dim": int(matrix.shape[1])}
    blob = matrix.astype("<f4").tobytes()
    return StepOutput(
        data=data, files=(OutputFile(name=VECTORS_FILE, media_type="application/octet-stream", content=blob),)
    )


def _vector_index(carried: Carried, adapters: GreenwashAdapters) -> VectorIndex:
    """index 의 산출물(조각 + 벡터 파일)에서 GW1 VectorIndex 를 다시 짓는다."""
    out = carried["index"]
    data = cast("dict[str, Any]", out.data)
    chunks = [Document(page_content=c["page_content"], metadata=c["metadata"]) for c in data["chunks"]]
    meta = cast("dict[str, int]", data["vectors"])
    blob = next(f.content for f in out.files if f.name == VECTORS_FILE)
    matrix = np.frombuffer(blob, dtype="<f4").reshape(meta["rows"], meta["dim"])
    return VectorIndex(chunks, matrix.tolist(), adapters.embedding)


# ── judge ────────────────────────────────────────────────────────────────────


def _empty_scan() -> dict[str, Any]:
    return {
        "results": [],
        "agg": dict.fromkeys(EMPTY_AGG, 0),
        "failed": 0,
        "failed_pages": [],
        "pages_norm": [],
        "allowed_norm": [],
    }


def judge(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """추가 단어가 있으면 노트북이 바꾼 환경 낱말 전역을 끝에(성공·실패·예외) 기본으로 되돌린다(흠 18).
    이어 돌기도 judge 를 다시 부르므로 같은 단어로 다시 설정된다."""
    config = scan_config(inputs)
    try:
        return _judge(inputs, adapters, carried, ctx, config)
    finally:
        if inputs.extra_terms:
            set_env_keywords(None, False)


def _judge(
    inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext, config: dict[str, Any]
) -> StepOutput:
    ext = _data(carried, "extract")
    manual_pages = cast("list[int]", ext["manual_pages"])
    docs = _docs(carried)
    if inputs.dry_run:
        if inputs.prompts is not None:
            raise ValueError("dry-run 은 저장 글 판을 셈하지 않는다(서버 실행은 dry-run 이 아니다 — AS3a-2 ★F)")
        if adapters.tokens is None:
            raise ValueError("dry-run 에는 tokens 어댑터가 필요하다(토큰 세기 없이는 dry-run 의 셈을 낼 수 없다)")
        counter = cast("TokenCounter", adapters.tokens)
        dry = dry_run(docs, manual_pages, manual_pages, config, counter)
        if inputs.criteria is None:
            return StepOutput(data={"dry_run": dry})
        version = judged_prompt_version(config)
        adjusted, adjustment = adjusted_dry_run(
            dry,
            counter,
            default_eval=default_prompts(version).eval_system_prompt,
            edited_eval=eval_pack(inputs.criteria, version).eval_system_prompt,
        )
        return StepOutput(data={"dry_run": adjusted, DRY_EVAL_ADJUSTMENT: adjustment})
    if not manual_pages:
        return StepOutput(data=_empty_scan())  # GW1 cli.run_scan: 노트북은 스캔을 부르지 않는다
    return StepOutput(data=_scan_pages(inputs, docs, manual_pages, adapters, carried, ctx, config))


DRY_EVAL_ADJUSTMENT: Final = "eval_prompt_adjustment"
"""judge 단계 산출(dry-run)의 표지 칸: 판정 몫을 고친 기준표로 보정했다는 것과 요청 하나의 차이(글자·토큰)."""


def adjusted_dry_run(
    dry: dict[str, Any], counter: TokenCounter, *, default_eval: str, edited_eval: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """엔진 dry-run 의 셈(snake, Tally.to_json 꼴)에 판정 몫의 차이를 더한 새 값과 표지. 아래끝·위끝마다 eval 요청 수
    × 차이를 eval 칸과 합(chat)에 더한다(판정 요청은 system 글을 따로 한 번 센다 — dryrun 의 Tally.add). 토큰을 못
    세면 그 칸은 「못 쟀다」가 된다(합계 규칙과 같다)."""
    chars = len(edited_eval) - len(default_eval)
    edited_tokens, default_tokens = (
        counter.count(CHAT_ENCODING, edited_eval),
        counter.count(CHAT_ENCODING, default_eval),
    )
    tokens = None if edited_tokens is None or default_tokens is None else edited_tokens - default_tokens
    out = copy.deepcopy(dry)
    for end in ("lower", "upper"):
        requests = int(out[end]["chat_by_kind"]["eval"]["requests"])
        for tally in (out[end]["chat_by_kind"]["eval"], out[end]["chat"]):
            tally["input_chars"] += requests * chars
            counted = tally["input_tokens"]
            if counted["status"] != "measured":
                continue
            if tokens is None:
                tally["input_tokens"] = {
                    "status": "unmeasured",
                    "encoding": counted["encoding"],
                    "reason": counter.reason(CHAT_ENCODING),
                }
            else:
                counted["value"] += requests * tokens
    return out, {"per_request_chars": chars, "per_request_tokens": tokens}


def _soft_deadline(error: BaseException) -> bool:
    """엔진의 쪽 고리에 주입하는 「다시 던질지」 판별 — Celery soft limit 이 사슬에 있으면 참(MARC-ISSUE-414, 밴드 GSL1.
    엔진은 core 를 모른다). 참이면 그 쪽은 failed_pages 에 남지 않고, 이어 돈 실행이 그 쪽부터 다시 판정한다."""
    return soft_deadline_in(error) is not None


def _scan_pages(
    inputs: GreenwashInputs,
    docs: list[Document],
    pages: list[int],
    adapters: GreenwashAdapters,
    carried: Carried,
    ctx: StepContext,
    config: dict[str, Any],
) -> dict[str, Any]:
    """GW1 checker.scan_report_greenwashing_pages(docs, pages, evidence_allowed_pages=pages, config=config,
    vectorstore=<색인>, llm=adapters.llm) 를 부르고, 쪽 하나가 끝날 때마다 체크포인트한다(꼭지 resume·checkpoint).
    config 는 scan_config(SCAN_CONFIG 의 사본 + 추가 단어). 바뀐 환경 낱말 전역(흠 18)은 judge 가 되돌린다.

    판의 모델 설정(inputs.model)이 값이면 대화 포트가 LlmChatBridge 여야 하고 with_model 로 바꿔 끼운다(아니면 쪽 루프
    밖에서 TypeError — AS2b). 판의 저장 글(inputs.prompts)이 값이면 그 묶음을, 아니고 기준표가 있으면 기준표로 지은
    묶음을 prompts= 로 넘기고, 대화 포트가 LlmChatBridge 이면 with_pack 으로 바꿔 끼운다.
    그 밖의 대화 포트는 묶음이 기본 판과 같을 때만 그대로 넘기고, 다르면 쪽 루프 밖에서 TypeError(그 포트는 고친 글을
    모른다 — 저장 글은 넷 전부, 기준표 묶음은 EVAL 만 다를 수 있다). 둘 다 없으면 prompts 를 넘기지 않는다(지금 길)."""

    def checkpoint(partial: dict[str, Any], done: int, total: int) -> None:
        ctx.checkpoint(partial, done=done, total=total)

    llm, pack = judge_chat(
        adapters.llm,
        prompts=inputs.prompts,
        criteria=inputs.criteria,
        model=inputs.model,
        version=judged_prompt_version(config),
    )
    given: dict[str, Any] = {} if pack is None else {"prompts": pack}
    outcome = scan_report_greenwashing_pages(
        docs,
        pages,
        evidence_allowed_pages=pages,
        config=config,
        vectorstore=_vector_index(carried, adapters),
        llm=llm,
        resume=cast("dict[str, Any] | None", ctx.resume),
        checkpoint=checkpoint,
        reraise=_soft_deadline,
        **given,
    )
    return {
        "results": outcome.results,
        "agg": outcome.agg,
        "failed": outcome.failed,
        "failed_pages": outcome.failed_pages,
        "pages_norm": outcome.pages_norm,
        "allowed_norm": outcome.allowed_norm,
    }


# ── wordcount ────────────────────────────────────────────────────────────────


def frequency_terms(inputs: GreenwashInputs) -> list[str]:
    """빈도에 셀 낱말: 기준 목록(판의 켠 단어, 없으면 GREEN_TERMS) 뒤에 추가 단어 가운데 비교 키가 기준 목록에 없는
    것(받은 차례). 판이 없으면 지금 줄 그대로다. 판 쪽은 flows/terms_e0.extras_beyond 와 같은 셈이다(시험이 견준다 —
    이 파일은 등록 길에 있어 결과 꼴을 들이는 terms_e0 를 들이지 않는다)."""
    if inputs.terms is None:
        return [*GREEN_TERMS, *frequency_extras(inputs.extra_terms)]
    keys = {term_key(t) for t in inputs.terms}
    return [*inputs.terms, *(t for t in inputs.extra_terms if term_key(t) not in keys)]


def wordcount(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    total, per_page = count_green_terms(_docs(carried), frequency_terms(inputs))
    return StepOutput(data={"total": dict(total), "per_page": [[p, dict(c)] for p, c in per_page]})


# ── locate ───────────────────────────────────────────────────────────────────


def locate(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    results = cast("list[dict[str, Any]]", _data(carried, "judge").get("results", []))
    coordinates = adapters.coordinates
    if coordinates is None or inputs.dry_run:
        if isinstance(coordinates, ClosingCoordinatesPort):
            coordinates.close()
        return StepOutput(data={"positions": [None for _ in results]})
    if not isinstance(coordinates, ClosingCoordinatesPort):
        positions = [coordinates.locate(inputs.document, int(r["page"]), str(r["sentence"])) for r in results]
        return StepOutput(data={"positions": positions})
    try:
        positions = [coordinates.locate(inputs.document, int(r["page"]), str(r["sentence"])) for r in results]
        stats = coordinates.stats()
    finally:
        coordinates.close()
    return StepOutput(data={"positions": positions, "stats": stats})


# ── report ───────────────────────────────────────────────────────────────────


def counts_of(items: list[dict[str, Any]], section_pages: dict[str, list[int]]) -> dict[str, Any]:
    """items 의 건수. by_part 는 parts.build_results_by_part 의 셈(두 파트 쪽은 두 번 — 노트북 동작)."""
    by_level = dict.fromkeys(LEVELS, 0)
    for item in items:
        by_level[item["level"]] += 1
    by_part = {
        part: {level: sum(1 for r in rows if r["level"] == level) for level in LEVELS}
        for part, rows in build_results_by_part(items, section_pages).items()
    }
    return {"total": len(items), "by_level": by_level, "by_part": by_part}


PART_ORDER: Final = tuple(build_section_pages("", "", "", 0)[0])
"""노트북의 파트 차례 — engines/e0/parts.build_section_pages 가 내는 dict 의 열쇠 차례(그 함수에서 읽는다)."""


def notebook_order(section_pages: dict[str, list[int]]) -> dict[str, list[int]]:
    """section_pages 를 노트북의 파트 차례로 다시 짓는다(모르는 열쇠는 뒤에 원래 차례). 실행기가 이어 돌 때 extract 의
    data 는 jsonb 를 거쳐 오고 jsonb 는 객체 열쇠를 다시 늘어세운다 — 그래도 결과의 parts 차례가 같게(밴드 G1b)."""
    known = {name: section_pages[name] for name in PART_ORDER if name in section_pages}
    return {**known, **{name: pages for name, pages in section_pages.items() if name not in known}}


def assemble(inputs: GreenwashInputs, carried: Carried) -> dict[str, Any]:
    """greenwash.result@1 한 건. 머리는 GW1 result.header, 몸은 GW1 result.scan_body 의 칸(span → position 등)."""
    ext = _data(carried, "extract")
    section_pages = notebook_order(cast("dict[str, list[int]]", ext["section_pages"]))
    manual_pages = cast("list[int]", ext["manual_pages"])
    cfg = scan_cfg()
    chunk_config = gw1_result.chunk_defaults()
    wc = _data(carried, "wordcount")
    total = Counter(cast("dict[str, int]", wc["total"]))
    per_page = [(int(p), Counter(cast("dict[str, int]", c))) for p, c in cast("list[list[Any]]", wc["per_page"])]
    judged = _data(carried, "judge")
    dry = judged.get("dry_run")

    items: list[dict[str, Any]] = []
    candidate_stats: dict[str, Any] | None = None
    counts: dict[str, Any] | None = None
    if dry is None:
        positions = cast("list[Any]", _data(carried, "locate")["positions"])
        for r, position in zip(cast("list[dict[str, Any]]", judged["results"]), positions, strict=True):
            item = gw1_result.item_json(r, section_pages)
            del item["span"]
            item["position"] = position
            item["example_sentence"] = None
            items.append(item)
        agg = cast("dict[str, Any]", judged["agg"])
        candidate_stats = {**{k: int(v) for k, v in agg.items()}, "failed_pages": list(judged["failed_pages"])}
        counts = counts_of(items, section_pages)

    snake: dict[str, Any] = {
        "schemaVersion": RESULT_SHAPE,
        "source": {"file_name": inputs.file_name, "sha256": ext["sha256"], "page_count": ext["page_count"]},
        "config": gw1_result.config_json(cfg, chunk_config),
        "models": {"chat": MODEL_NAME, "embedding": chunk_config.get("embedding_model", EMBEDDING_MODEL)},
        "prompt_version": cfg.prompt_version,
        "parts": [{"name": name, "pages": list(pages)} for name, pages in section_pages.items()],
        "pages": list(manual_pages),
        "extra_terms": list(inputs.extra_terms),
        "items": items,
        "candidate_stats": candidate_stats,
        "counts": counts,
        "word_counts": gw1_result.word_counts_json(total, per_page),
        "dry_run": dry,
        "report": None if dry is not None else {"file": REPORT_FILE},
    }
    if inputs.terms is not None:  # 판 단어로 센 실행만, extra_terms 바로 뒤 — 칸이 없으면 결과 바이트 그대로(G2d)
        pairs = list(snake.items())
        at = [key for key, _ in pairs].index("extra_terms") + 1
        snake = dict([*pairs[:at], ("terms", frequency_terms(inputs)), *pairs[at:]])
    return wire.result_to_wire(snake)


def report(inputs: GreenwashInputs, adapters: GreenwashAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    result = assemble(inputs, carried)
    if result["dryRun"] is not None:
        return StepOutput(data={"results": [result]})
    book = OutputFile(
        name=REPORT_FILE,
        media_type=xlsx.MEDIA_TYPE,
        content=xlsx.build(result, added_terms=frequency_extras(result["extraTerms"])),
    )
    return StepOutput(data={"results": [result]}, files=(book,))


STEPS: Final[tuple[FlowStep[GreenwashInputs, GreenwashAdapters], ...]] = (
    FlowStep(name="extract", run=extract),
    FlowStep(name="index", run=index),
    FlowStep(name="judge", run=judge),
    FlowStep(name="wordcount", run=wordcount),
    FlowStep(name="locate", run=locate),
    FlowStep(name="report", run=report),
)

FLOW: Final = make_flow(
    module="greenwash",
    id=FLOW_ID,
    input_shape="greenwash.document@1",
    inputs=GreenwashInputs,
    adapters=GreenwashAdapters,
    result_shapes=(RESULT_SHAPE,),
    output_files=(REPORT_FILE,),
    steps=STEPS,
)
