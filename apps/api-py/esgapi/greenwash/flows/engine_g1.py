"""흐름 greenwash.engine@G1(밴드 GE1)의 다리: 엔진 G1 판(engines/g1)의 포트 넷(갈래·임베딩·재순위·판정)을
core.llm 으로 채운다.

이 파일이 G1 판에서 엔진과 계약(contracts/result2_shapes)을 잇는 자리다(④ 에서 흐름 조립이 붙는다). 설정·환경 변수·
키·파일을 읽지 않고 SDK 클라이언트를 짓지 않는다(tests/flows/test_boundary.py) — 클라이언트는 부르는 쪽이 지어 넘긴다.

공통 값(③):
  경로 light-openai(= gpt-6-luna, D3·628) · temperature 를 싣지 않는다(luna 는 받지 않는다 — core
  TEMPERATURE_UNSUPPORTED_MODELS) · 구조화 출력(schema → json_schema) · 답 상한은 걸음마다(갈래 2000 · 재순위 4000 ·
  판정 2000 — 호출 층이 luna 추론 여유 2000 을 더해 보낸다).
  ★ 랩(SG1·MB1 GM2)은 추론 강도 low 로 불렀고 core 어댑터는 추론 강도를 싣지 않는다(기본 medium). 같은 모델·같은
    글이어도 추론 토큰·비용이 다를 수 있다(GE1 보고 「랩과 다르게 옮긴 것」).
실패 옮김: 갈래·재순위·임베딩의 공급사 실패 → SearchFailed(엔진의 「찾기 실패」 갈래). 재순위가 출력 상한에서
잘리거나 꼴이 틀리면 답 글자에서 id 를 건진다(complete=False). 판정은 성공 = 답, 꼴 어긋남·거절 = judge_unparsed,
잘림 = judge_cut_off, 공급사·시간 = judge_failed, 실행 비용 상한 = budget_exceeded(근거 찾기에서 걸려도 — 642-2)
— Mid 로 구제하지 않는다.
"""

import hashlib
import io
import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal, Protocol, cast

import numpy as np
from langchain_core.documents import Document

from esgapi.core.documents.contract import ArtifactRef, ArtifactRefused, ArtifactUnreadable
from esgapi.core.documents.view import ChartLabels, ChartLabelsUnavailable, DocArtifactView
from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import (
    FANOUT_DATA_MAX_OCTETS,
    Carried,
    FanoutStep,
    Flow,
    FlowStep,
    OutputFile,
    Segment,
    SegmentKey,
    SegmentOutput,
    StepContext,
    StepOutput,
)
from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.embedding import EmbeddingFailed, EmbeddingPort
from esgapi.core.llm.types import BudgetExceeded, CutOff, Refused, SchemaMismatch, Success, Tags
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.engines.e0 import heuristics
from esgapi.greenwash.engines.e0.checker import GreenwashingChecker, GWConfig
from esgapi.greenwash.engines.e0.heuristics import collect_rule_based_declaratives, is_low_declarative
from esgapi.greenwash.engines.e0.ports import ChatPort
from esgapi.greenwash.engines.g1 import checks as ck
from esgapi.greenwash.engines.g1 import claims as cl
from esgapi.greenwash.engines.g1 import evidence as ev
from esgapi.greenwash.engines.g1 import facets
from esgapi.greenwash.engines.g1 import judge as jd
from esgapi.greenwash.engines.g1 import ranges as rg
from esgapi.greenwash.engines.g1.facets import FacetPlan
from esgapi.greenwash.engines.g1.passages import Built, build_passages, units_of
from esgapi.greenwash.flows import criteria_e0

FLOW_ID: Final = "greenwash.engine@G1"
RESULT_SHAPE: Final = "greenwash.result@2"
INPUT_SHAPE: Final = "greenwash.g1-input@1"
ROUTE: Final = "light-openai"
EMBEDDING_ROUTE: Final = "light-openai"
PLAN_PROMPT: Final = "greenwash/ge-facets@1"
RERANK_PROMPT: Final = "greenwash/ge-rerank@1"
JUDGE_PROMPT: Final = jd.PROMPT_ID
PLAN_MAX_TOKENS: Final = 2000
RERANK_MAX_TOKENS: Final = 4000
JUDGE_MAX_TOKENS: Final = jd.ANSWER_MAX_TOKENS
TEMPERATURE: Final = None
BUDGET_CODE: Final = "budget_exceeded"
"""실행 비용 상한의 이름(core BudgetExceeded·EmbedBudgetExceeded 의 kind — 근거 찾기 SearchFailed.code 로도 이 글).
642-2: 항목 errorCode 로 남기고, 처음 걸린 뒤 그 구획의 남은 후보는 부르지 않는다."""


def default_criterion_lines() -> tuple[jd.CriterionLine, ...]:
    """기본 기준 판(flows/criteria_e0 의 15줄, 켠 줄만) → 엔진에 넘길 기준 줄. 글은 E0 줄 본문(키워드 줄은
    「이름: 낱말, …」)."""
    rows = criteria_e0.default_criteria()["rows"]
    return tuple(
        jd.CriterionLine(
            id=row["id"],
            group=row["category"],
            text=row["text"]
            if row["terms"] is None
            else row["text"] + criteria_e0.KEYWORD_SEPARATOR + criteria_e0.TERMS_SEPARATOR.join(row["terms"]),
        )
        for row in rows
        if row["enabled"]
    )


class G1Calls:
    """한 실행(한 문서)의 대화 호출. 말 목록은 문서마다 하나라 여기 쥔다(갈래 프롬프트의 캐시 구획)."""

    def __init__(self, client: LlmClient, embedding: EmbeddingPort, *, tags: Tags, vocab: str) -> None:
        self.client = client
        self.embedding = embedding
        self.tags = tags
        self.vocab = vocab

    # ── 요청(부르기와 어림이 같은 것을 쓴다) ──

    def plan_request(self, claim: str) -> CallRequest[FacetPlan]:
        return CallRequest[FacetPlan](
            prompt=PLAN_PROMPT,
            route=ROUTE,
            tags=self.tags,
            vars={"vocab": self.vocab, "claim": claim},
            schema=FacetPlan,
            schema_name="facets",
            max_output_tokens=PLAN_MAX_TOKENS,
            temperature=TEMPERATURE,
        )

    def rerank_request(self, claim: str, lines: str) -> CallRequest[ev.RerankOrder]:
        return CallRequest[ev.RerankOrder](
            prompt=RERANK_PROMPT,
            route=ROUTE,
            tags=self.tags,
            vars={"claim": claim, "lines": lines},
            schema=ev.RerankOrder,
            schema_name="rerank",
            max_output_tokens=RERANK_MAX_TOKENS,
            temperature=TEMPERATURE,
        )

    def judge_request(self, variables: Mapping[str, str]) -> CallRequest[jd.JudgeAnswer]:
        return CallRequest[jd.JudgeAnswer](
            prompt=JUDGE_PROMPT,
            route=ROUTE,
            tags=self.tags,
            vars=dict(variables),
            schema=jd.JudgeAnswer,
            schema_name="judge",
            max_output_tokens=JUDGE_MAX_TOKENS,
            temperature=TEMPERATURE,
        )

    # ── 포트 ──

    def plan(self, claim: str) -> FacetPlan:
        result = self.client.call(self.plan_request(claim))
        if isinstance(result, Success):
            return result.data
        raise ev.SearchFailed("plan", result.kind)

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        try:
            return self.embedding.embed_documents(list(texts))
        except EmbeddingFailed as err:
            raise ev.SearchFailed("embed", err.result.kind) from err

    def rerank(self, claim: str, lines: str) -> ev.RerankReply:
        result = self.client.call(self.rerank_request(claim, lines))
        if isinstance(result, Success):
            return ev.RerankReply(ids=tuple(ev.pid_of(x) for x in result.data.order), complete=True)
        if isinstance(result, CutOff):
            return ev.RerankReply(ids=ev.salvage_ids(result.partial_text), complete=False)
        if isinstance(result, SchemaMismatch):
            return ev.RerankReply(ids=ev.salvage_ids(result.raw_text), complete=False)
        raise ev.SearchFailed("rerank", result.kind)

    def judge(self, variables: Mapping[str, str]) -> jd.JudgeReply:
        result = self.client.call(self.judge_request(variables))
        if isinstance(result, Success):
            return jd.JudgeReply(answer=result.data)
        if isinstance(result, SchemaMismatch | Refused):
            return jd.JudgeReply(answer=None, failure="judge_unparsed")
        if isinstance(result, CutOff):
            return jd.JudgeReply(answer=None, failure="judge_cut_off")
        if isinstance(result, BudgetExceeded):
            return jd.JudgeReply(answer=None, failure=BUDGET_CODE)
        return jd.JudgeReply(answer=None, failure="judge_failed")

    def ports(self) -> ev.Ports:
        return ev.Ports(plan=self.plan, embed=self.embed, rerank=self.rerank)


# ══ ④ 흐름 조립(전역 등록은 registration.FLOWS — GE1b ③. 시험은 g1_flow() 를 새 레지스트리에 달아도 된다) ══
#
# 단계: extract(장벽 — 뷰 → 단락·말 목록) → index(장벽 — 단락 벡터를 StepOutput.files 로) → candidates(장벽 — E0 탐지
# 몫을 읽어 부르고 문장을 블록에 짝) → judge(펼침 — 구획 = 후보 8, 근거 F-b′ → 판정 → 검사) → gather(장벽 — 같은
# stableKey 합침 · result@2 조립 · check_result). 단락은 단계마다 문서 포트(adapters.document)의 산출물 뷰에서 다시
# 짓는다(순수·결정적 — 같은 산출물이면 같은 단락·같은 id). 벡터만 앞 단계의 파일(Carried)로 읽는다.
# 문서 포트(GE1b ② B3): extract 가 ensure(판 2 · 쪽 상한 300)로 산출물을 받아 data 에 {sha256·parserVersion·pageCount·
# fileName}(DB id 0 — 묶음이 id 를 싣지 않는다)을 싣고, 뒤 단계·구획은 ensure(있으면 찾기만)로 다시 받아
# sha·parserVersion 이 extract 와 다르면 G1ArtifactChanged(이름 있는 실패). 거절·못 읽음은 extract 의
# G1DocumentFailed(step_error).
# 도표 라벨(GE1c ④): 뷰의 chart_labels() 로 단락 풀에 도표 단위를 넣는다(built_of). 라벨 = used · 칸 없음 = absent ·
# 못 지음 = unavailable — 셋 다 돌고(뒤 둘은 도표 단위 0) extract data 「chartLabels」에 적는다. 안 실은 뷰
# (ChartLabelsNotLoaded)는 포트 잘못이라 올려 보낸다(step_error). 단계 data 라 계약(result@2) 밖이다.
# 이어 돌기 막기(GE1c ④ critic M2): extract 가 단락(차례대로 글·구성 블록)의 sha256(passagesSha256)과 근거 예산
# (evidenceBudget)을 싣고, index·judge 는 다시 지은 단락·지금 예산과 견줘 다르면 G1ArtifactChanged(check_built). 단락
# 수가 같아도(도표 단위가 생겨도 단락 수가 안 변하는 문서) 글·차례·구성 블록이 다르면 잡는다 — 벡터 행 수 대조
# (ev.Index)만으로는 조용히 어긋난다.

PARTS: Final = ("ceo", "company", "climate")
page_text_of = cast("Callable[[Document, int], str]", heuristics.get_page_text)  # pyright: ignore[reportUnknownMemberType]
"""E0 get_page_text(꼴 표시 없는 원판)의 꼴 붙인 이름 — 고침 0."""
PAGE_MAX: Final = 300
INPUT_KEYS: Final = frozenset({"parts", "evidenceScope", "criteriaId", "variant", "industry", "humanEvidence"})
CRITERIA_MAX: Final = 15
CRITERION_ID_MAX: Final = 24
CRITERION_TEXT_MAX: Final = 300
VECTORS_FILE: Final = "g1-passage-vectors.npy"
MAX_SEGMENTS: Final = 150
"""후보 최대 = 쪽 300 × 쪽당 4(E0 analyze_page 상한 3 + Low 1) = 1,200 → ÷ 8 = 150(발주서 2-4 ★)."""
RESULT_BODY_MAX_OCTETS: Final = 8 * 1024 * 1024
"""runs/models.py RUN_RESULT_BODY_MAX_OCTETS 의 사본(흐름은 runs 를 import 하지 않는다 — translation 시험과 같은 꼴).
넘으면 실행기가 result_too_large."""
BUDGET_OCTETS: Final = int(0.9 * min(FANOUT_DATA_MAX_OCTETS, RESULT_BODY_MAX_OCTETS))
"""실행 바이트 예산(펼침 단계 data 합·result@2 본문 상한 가운데 작은 값의 90% — 감독 답 ⓒ ②, 11-10)."""
SEGMENT_BUDGET_OCTETS: Final = BUDGET_OCTETS // MAX_SEGMENTS
"""구획 하나의 예산 몫. 펼침 단계 data 합은 모음 **전에** core 가 재므로(run._FanoutSize) 구획이 제 몫을 지켜야 1,200
후보 꽉 참이 모음에 닿는다. 몫을 넘는 자리부터 그 뒤 항목을 비운다(budget)."""
CATEGORIES: Final[tuple[str, ...]] = ()
"""기본 카테고리 목록(MARC-ENT-612 전 — 빈 목록이라 category 는 null 만). ③ 업무 지식 칸 G1Inputs.categories 의 기본."""


class G1Document(Protocol):
    """그 실행의 문서 포트(B3). 몸은 service/actions/engine_g1.RunG1Document(DB), 시험은 JSON 산출물 가짜.

    ensure()     판 2 · 쪽 상한 300 산출물(있으면 찾기만 — 넣어 온 실행이면 그 회사에서 지음). 거절·못 읽음은 그 값
    view(ref)    그 산출물의 읽기 뷰(도표 라벨 실음 — charts=True, GE1c ④. 글자 자리는 안 읽음)
    file_name()  원본 파일 이름(result@2 source.fileName)"""

    def ensure(self) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable: ...

    def view(self, ref: ArtifactRef) -> DocArtifactView: ...

    def file_name(self) -> str: ...


class G1DocumentFailed(Exception):
    """문서 산출물을 받지 못했다(거절·못 읽음 — code 는 core 의 것). extract 단계 실패(step_error)."""

    def __init__(self, code: str) -> None:
        super().__init__(f"문서 산출물을 받지 못했다: {code}")
        self.code = code


class G1ArtifactChanged(Exception):
    """뒤 단계가 받은 산출물의 sha·parserVersion 이 extract 의 것과 다르다(같은 실행 안에서 문서가 바뀌었다), 또는
    다시 지은 단락 글·근거 예산이 extract 의 것과 다르다(이어 돌기 사이에 엔진 코드·라벨 읽기가 바뀌었다 — GE1c)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class G1Inputs:
    """greenwash.g1-input@1. 쓰는 칸 = 파트 쪽 셋 · 근거 범위(document 고정) · ③ 업무 지식(기준 줄·카테고리 —
    MARC-ENT-651 설정 세 층, 기본 = 기본 판 켠 줄·빈 목록). 문서는 입력이 아니라 문서 포트(G1Adapters.document)다.
    칸만(null 만) = 기준 판 id · 금융/비금융(variant — GFC1 「못 가름」) · 산업 · 사람 근거(G4). 어기면 ValueError.
    ③ 이 지시문을 채우는 것은 ge-judge 의 {{criteria}}·{{categories}} 뿐이다(지시문 글을 고치는 길 0)."""

    parts: Mapping[str, tuple[int, ...]]
    criteria: tuple[jd.CriterionLine, ...] = field(default_factory=lambda: default_criterion_lines())
    categories: tuple[str, ...] = CATEGORIES
    evidence_scope: Literal["document"] = "document"
    criteria_id: None = None
    variant: None = None
    industry: None = None
    human_evidence: None = None

    def __post_init__(self) -> None:
        if set(self.parts) != set(PARTS):
            raise ValueError("파트 셋(ceo·company·climate)의 페이지를 모두 넣어 주세요")
        for pages in self.parts.values():
            given = cast("tuple[object, ...]", pages)
            if not all(isinstance(p, int) and not isinstance(p, bool) and 1 <= p <= PAGE_MAX for p in given):
                raise ValueError(f"페이지 번호는 1~{PAGE_MAX} 사이 정수여야 해요")
        if not any(self.parts.values()):
            raise ValueError("점검할 페이지를 하나 이상 골라 주세요")
        if self.evidence_scope != "document":
            raise ValueError("근거 범위는 document 만 돼요")
        if (self.criteria_id, self.variant, self.industry, self.human_evidence) != (None, None, None, None):
            raise ValueError("기준 판·금융/비금융·산업·사람 근거는 이 판에서 칸만 있어요(null)")
        check_criteria(self.criteria, self.categories)


def check_criteria(criteria: Sequence[jd.CriterionLine], categories: Sequence[str]) -> None:
    """③ 칸 꼴: 기준 줄 1~15(id 1~24자 · 무리 다섯 · 글 1~300자 한 줄 · id 겹침 0), 카테고리는 빈 줄 없는 한 줄 글자
    (겹침 0). 어기면 ValueError."""
    if not 1 <= len(criteria) <= CRITERIA_MAX:
        raise ValueError(f"기준 줄은 1~{CRITERIA_MAX}개여야 해요")
    ids = [c.id for c in criteria]
    if len(set(ids)) != len(ids):
        raise ValueError("기준 줄 id 가 겹쳐요")
    for c in criteria:
        if not 1 <= len(c.id) <= CRITERION_ID_MAX or c.group not in jd.GROUP_NAME:
            raise ValueError("기준 줄의 id·무리가 맞지 않아요")
        if not 1 <= len(c.text) <= CRITERION_TEXT_MAX or "\n" in c.text:
            raise ValueError(f"기준 줄 글은 한 줄 1~{CRITERION_TEXT_MAX}자여야 해요")
    if len(set(categories)) != len(categories) or any(not x.strip() or "\n" in x for x in categories):
        raise ValueError("카테고리는 겹치지 않는 한 줄 글자여야 해요")


def inputs_from(given: Mapping[str, object]) -> G1Inputs:
    """JSON 꼴 입력 → G1Inputs. 모르는 열쇠는 거절(binding_e0 꼴)."""
    unknown = sorted(k for k in given if k not in INPUT_KEYS)
    if unknown:
        raise ValueError(f"알 수 없는 입력이에요: {', '.join(unknown)}")
    parts = given.get("parts")
    if not isinstance(parts, Mapping):
        raise ValueError("파트별 점검 페이지(parts)를 넣어 주세요")
    given_parts = cast("Mapping[object, object]", parts)
    # 642-7: 파트 값이 정수 하나면 TypeError 가 아니라 거절(끼움이 RunOptionsRejected 로 옮긴다)
    if not all(isinstance(v, list | tuple) for v in given_parts.values()):
        raise ValueError("파트마다 페이지 번호 목록을 넣어 주세요")
    pages = {str(k): tuple(cast("list[int]", v)) for k, v in given_parts.items()}
    return G1Inputs(
        parts=pages,
        evidence_scope=cast("Literal['document']", given.get("evidenceScope", "document")),
        criteria_id=cast("None", given.get("criteriaId")),
        variant=cast("None", given.get("variant")),
        industry=cast("None", given.get("industry")),
        human_evidence=cast("None", given.get("humanEvidence")),
    )


@dataclass(frozen=True, slots=True, kw_only=True)
class G1Adapters:
    """client·embedding = 갈래·재순위·판정·임베딩(G1Calls), detect = E0 탐지 대화 포트(LlmChatBridge, 경로 luna ·
    temperature None — D3). tags 는 호출 꼬리표. document = 그 실행의 문서 포트(B3)."""

    client: LlmClient
    embedding: EmbeddingPort
    detect: ChatPort
    tags: Tags
    document: G1Document


def _ensured(adapters: G1Adapters) -> ArtifactRef:
    got = adapters.document.ensure()
    if isinstance(got, ArtifactRefused | ArtifactUnreadable):
        raise G1DocumentFailed(got.code)
    return got


def view_of(adapters: G1Adapters, carried: Carried) -> DocArtifactView:
    """뒤 단계의 산출물 뷰: ensure 로 다시 받아 extract 가 적은 sha·parserVersion 과 견준다(다르면
    G1ArtifactChanged)."""
    ref = _ensured(adapters)
    data = carried["extract"].data
    if (ref.source_sha256, ref.parser.version) != (data["sha256"], data["parserVersion"]):
        raise G1ArtifactChanged("산출물이 extract 때와 다르다(sha256·parserVersion)")
    return adapters.document.view(ref)


ChartLabelsState = Literal["used", "absent", "unavailable"]


def chart_labels_of(view: DocArtifactView) -> tuple[ChartLabels | None, ChartLabelsState]:
    """뷰의 도표 라벨과 그 상태. 칸 없음(None — EPOCH 1·판 1) = absent · 못 지음(ChartLabelsUnavailable) = unavailable
    — 둘 다 라벨 None(도표 단위 0)으로 돈다. ChartLabelsNotLoaded(안 실은 뷰 — 포트 잘못)는 잡지 않는다."""
    try:
        labels = view.chart_labels()
    except ChartLabelsUnavailable:
        return None, "unavailable"
    return (None, "absent") if labels is None else (labels, "used")


def built_of(view: DocArtifactView) -> Built:
    return build_passages(view, chart_labels=chart_labels_of(view)[0])


def passages_sha256(built: Built) -> str:
    """단락(차례대로 — 차례가 벡터 행과 맞물린다)의 [글, 구성 블록]의 sha256 — 이어 돌기에서 단락이 바뀌었는지 가르는
    값. 구성 블록(members)은 result@2 의 blockRanges 가 되므로 글이 같아도 members 만 바뀌면 다르다(GE1c ⑤ 검증 4 권고).
    id 는 차례라 따로 넣지 않는다."""
    rows = [[p.text, p.members] for p in built.passages]
    return hashlib.sha256(json.dumps(rows, ensure_ascii=False).encode("utf-8")).hexdigest()


def check_built(built: Built, carried: Carried) -> None:
    """다시 지은 단락 글 sha·지금 근거 예산이 extract 가 적은 것과 다르면(칸이 없는 옛 extract 도) G1ArtifactChanged."""
    data = carried["extract"].data
    if data.get("passagesSha256") != passages_sha256(built):
        raise G1ArtifactChanged("단락이 extract 때와 다르다(passagesSha256)")
    if data.get("evidenceBudget") != ev.BUDGET_CHARS:
        raise G1ArtifactChanged("근거 예산이 extract 때와 다르다(evidenceBudget)")


def _source(carried: Carried) -> dict[str, object]:
    data = carried["extract"].data
    return {"fileName": str(data["fileName"]), "sha256": str(data["sha256"]), "pageCount": int(str(data["pageCount"]))}


# ── 장벽 extract · index ──


def extract(inputs: G1Inputs, adapters: G1Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    ref = _ensured(adapters)
    view = adapters.document.view(ref)
    labels, state = chart_labels_of(view)
    built = build_passages(view, chart_labels=labels)
    return StepOutput(
        data={
            "sha256": ref.source_sha256,
            "parserVersion": ref.parser.version,
            "pageCount": ref.page_count,
            "fileName": adapters.document.file_name(),
            "passages": len(built.passages),
            "passagesSha256": passages_sha256(built),
            "evidenceBudget": ev.BUDGET_CHARS,
            "chartLabels": state,
            "vocab": facets.vocab(built),
            "stat": dict(built.stat),
        }
    )


def index(inputs: G1Inputs, adapters: G1Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    built = built_of(view_of(adapters, carried))
    check_built(built, carried)
    texts = [p.text for p in built.passages]
    # 단락 0(642-1)이면 부르기 0 · 빈 (0, 0) 행렬(dim 0) — 판정 구획의 근거 찾기가 부르기 0 으로 Empty
    vectors = (
        np.asarray(adapters.embedding.embed_documents(texts), dtype=np.float32)
        if texts
        else np.zeros((0, 0), dtype=np.float32)
    )
    buf = io.BytesIO()
    np.save(buf, vectors, allow_pickle=False)
    out = OutputFile(name=VECTORS_FILE, media_type="application/octet-stream", content=buf.getvalue())
    return StepOutput(
        data={"count": len(texts), "dim": int(vectors.shape[1]) if vectors.ndim == 2 else 0}, files=(out,)
    )


def vectors_of(carried: Carried) -> np.ndarray:
    (file,) = [f for f in carried["index"].files if f.name == VECTORS_FILE]
    return np.load(io.BytesIO(file.content), allow_pickle=False)


# ── 장벽 candidates(E0 analyze_page 의 후보 몫 — checker.py:402-445 차례, 함수는 읽어 부름) ──


def page_candidates(checker: GreenwashingChecker, page_text: str, page_no: int) -> list[str]:
    """E0 analyze_page 의 (A) 규칙 후보 + (B) 탐지 → (C) 합침·중복 접기 → Low·비-Low 나눔 → filter_and_rank →
    비-Low 상한 + Low 1. 고침 0(같은 입력이면 같은 후보 — T18)."""
    rule = collect_rule_based_declaratives(page_text, max_n=max(3, int(checker.cfg.max_candidates_per_page)))
    llm = checker.detect_candidates(page_text, page_no)
    seen: set[str] = set()
    merged: list[str] = []
    for c in rule + llm:
        s = (c.get("sentence") or "").strip()
        if not s:
            continue
        key = re.sub(r"\s+", " ", s)
        if key in seen:
            continue
        seen.add(key)
        merged.append(s)
    low = [{"sentence": s} for s in merged if is_low_declarative(s)]
    nonlow = [{"sentence": s} for s in merged if not is_low_declarative(s)]
    nonlow_kept, _ = checker.filter_and_rank(nonlow)
    low_kept, _ = checker.filter_and_rank(low)
    cands = nonlow_kept[: int(checker.cfg.max_candidates_per_page)] + low_kept[:1]
    return [str(c["sentence"]).strip() for c in cands if str(c.get("sentence") or "").strip()]


def target_pages(inputs: G1Inputs) -> list[tuple[int, list[str]]]:
    """대상 쪽 = 파트 셋의 합집합(겹침 접음, 오름차순)과 그 쪽이 든 파트 이름(PARTS 차례)."""
    pages = sorted({p for ps in inputs.parts.values() for p in ps})
    return [(p, [part for part in PARTS if p in inputs.parts[part]]) for p in pages]


def candidates(inputs: G1Inputs, adapters: G1Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    view = view_of(adapters, carried)
    by_page = cl.pages_of(units_of(view))
    sha = str(_source(carried)["sha256"])
    cfg = GWConfig()
    checker = GreenwashingChecker(docs=None, vectorstore=None, llm=adapters.detect, cfg=cfg)
    found: list[cl.Candidate] = []
    per_page: dict[str, int] = {}
    for page_no, parts in target_pages(inputs):
        page = by_page.get(page_no)
        if page is None:
            continue
        text = page_text_of(Document(page_content=page.text), int(cfg.max_chars_page_text))
        if not text:
            continue
        sentences = page_candidates(checker, text, page_no)
        per_page[str(page_no)] = len(sentences)
        found += [cl.make_candidate(sha, s, page, parts) for s in sentences]
    merged = cl.merge(found)
    return StepOutput(
        data={
            "candidates": [c.to_json() for c in merged],
            "perPage": per_page,
            "merged": len(found) - len(merged),
            "unplaced": sum(c.block_ids is None for c in merged),
        }
    )


# ── 펼침 judge ──


def plan(inputs: G1Inputs, carried: Carried) -> tuple[Segment, ...]:
    rows = cast("list[dict[str, object]]", carried["candidates"].data["candidates"])
    cands = [cl.candidate_of(r) for r in rows]
    sha = str(_source(carried)["sha256"])
    parser = str(carried["extract"].data["parserVersion"])
    return tuple(
        Segment(
            key=SegmentKey(kind=cl.SEGMENT_KIND, span=span, document_sha256=sha, parser_version=parser),
            input={"candidates": [c.to_json() for c in part]},
        )
        for span, part in cl.chunks(cands)
    )


def _cut(text: str, limit: int, name: r2.TruncatedField, cut: list[r2.TruncatedField]) -> str:
    if len(text) <= limit:
        return text
    cut.append(name)
    return text[:limit]


def _lines(lines: Sequence[str], name: r2.TruncatedField, cut: list[r2.TruncatedField]) -> list[str]:
    kept = [x[: r2.NOTE_LINE_MAX] for x in lines[: r2.NOTE_LINES_MAX]]
    if len(lines) > r2.NOTE_LINES_MAX or any(len(x) > r2.NOTE_LINE_MAX for x in lines):
        cut.append(name)
    return kept


def document_evidence(
    idx: ev.Index, order: Mapping[str, int], passage_id: str, cut: list[r2.TruncatedField]
) -> dict[str, object]:
    p = idx.by_id[passage_id]
    ranges, over = rg.cap(rg.fold(p.members, order), r2.EVIDENCE_RANGES_MAX)
    if over and "evidence.blockRanges" not in cut:
        cut.append("evidence.blockRanges")
    out: dict[str, object] = {
        "kind": "document",
        "passageId": p.id,
        "blockRanges": [[a, b] for a, b in ranges],
        "page": p.page,
    }
    if p.span is not None and len(ranges) == 1 and ranges[0][0] == ranges[0][1]:
        out["span"] = [p.span[0], p.span[1]]
    return out


def _skipped(cut: list[r2.TruncatedField], quote: r2.CheckState = "skipped") -> dict[str, object]:
    return {
        "quoteInBlock": quote,
        "evidenceInPool": "skipped",
        "categoryInList": "skipped",
        "levelRule": "skipped",
        "truncated": cut,
    }


def item_of(
    c: cl.Candidate,
    got: ev.Outcome,
    judged: jd.JudgeOutcome | None,
    idx: ev.Index,
    order: Mapping[str, int],
    block_text: Mapping[str, str],
    parts: Sequence[str],
    categories: Sequence[str] = CATEGORIES,
) -> dict[str, object]:
    """후보 하나 → result@2 항목(key 는 모음이 다시 매김). 실패는 버리지 않는다."""
    cut: list[r2.TruncatedField] = []
    blocks = list(c.block_ids or ())
    target: dict[str, object] = {
        "kind": "sentence",
        "text": _cut(c.sentence, r2.TARGET_TEXT_MAX, "target.text", cut),
        "page": c.page,
        "blockIds": blocks,
    }
    quote = ck.quote_in_block(c.sentence, [block_text.get(b, "") for b in blocks])
    base: dict[str, object] = {"key": "i0", "stableKey": c.stable_key, "target": target}
    empty_module: dict[str, object] = {"confirmed": [], "missing": [], "criteriaLines": [], "parts": list(parts)}
    code: str | None = None
    if isinstance(got, ev.Failed) and got.code == BUDGET_CODE:
        code = BUDGET_CODE
    elif isinstance(got, ev.Failed) or judged is None:
        code = "evidence_search_failed"
    elif isinstance(judged, jd.NotJudged):
        code = judged.code
    if code is not None or not isinstance(judged, jd.Judged):
        return base | {
            "status": "failed",
            "errorCode": code,
            "verdict": None,
            "reason": "",
            "evidence": cast("list[object]", []),
            "checks": _skipped(cut, "pass" if quote.ok else "fail"),
            "module": empty_module,
        }
    pool = list(got.passage_ids) if isinstance(got, ev.Found) else []
    checks = (
        quote,
        ck.evidence_in_pool(judged.cited, pool),
        ck.category_in_list(judged.category, categories),
        ck.level_rule(judged.level, c.sentence),
    )
    failure = ck.first_failure(checks)
    cited = [pid for pid in judged.cited if pid in set(pool)]
    evidence: list[dict[str, object]] = [document_evidence(idx, order, pid, cut) for pid in cited]
    criteria: list[dict[str, object]] = [{"kind": "criteria", "lineId": lid} for lid in judged.criteria_hit]
    evidence += criteria
    if len(evidence) > r2.EVIDENCE_MAX:
        evidence = evidence[: r2.EVIDENCE_MAX]
        cut.append("evidence")
    lines = list(judged.criteria_hit)
    if len(lines) > r2.CRITERIA_LINES_MAX:
        lines = lines[: r2.CRITERIA_LINES_MAX]
        cut.append("criteriaLines")
    module = {
        "confirmed": _lines(judged.confirmed, "module.confirmed", cut),
        "missing": _lines(judged.missing, "module.missing", cut),
        "criteriaLines": lines,
        "parts": list(parts),
    }
    reason = _cut(judged.reason, r2.REASON_MAX, "reason", cut)
    names = ("quoteInBlock", "evidenceInPool", "categoryInList", "levelRule")
    check_out: dict[str, object] = {n: "pass" if r.ok else "fail" for n, r in zip(names, checks, strict=True)}
    check_out["truncated"] = cut
    return base | {
        "status": "failed" if failure else "done",
        "errorCode": failure,
        "verdict": {"level": judged.level, "category": judged.category},
        "reason": reason if reason or failure else "(이유 없음)",
        "evidence": evidence,
        "checks": check_out,
        "module": module,
    }


def octets(value: object) -> int:
    """core run._octets 와 같은 셈(json 기본 구분자, ensure_ascii=False, UTF-8)."""
    return len(json.dumps(value, ensure_ascii=False).encode("utf-8"))


def trim_for_budget(item: dict[str, object]) -> dict[str, object]:
    """예산 잘림: 문서 근거는 passageId·page 만(blockRanges → [], span 뺌), confirmed·missing → [],
    truncated 에 budget."""
    none: list[object] = []
    evidence: list[dict[str, object]] = [
        {"kind": "document", "passageId": e["passageId"], "blockRanges": none, "page": e["page"]}
        if e["kind"] == "document"
        else e
        for e in cast("list[dict[str, object]]", item["evidence"])
    ]
    module: dict[str, object] = cast("dict[str, object]", item["module"]) | {"confirmed": none, "missing": none}
    checks = cast("dict[str, object]", item["checks"])
    truncated = list(cast("list[str]", checks["truncated"]))
    if "budget" not in truncated:
        truncated.append("budget")
    return item | {"evidence": evidence, "module": module, "checks": checks | {"truncated": truncated}}


def fit(items: Sequence[dict[str, object]], budget: int, used: int = 0) -> tuple[list[dict[str, object]], int]:
    """항목을 차례대로 싣되 누적(used + 항목 합)이 budget 을 넘으면 **뒤 항목부터** 하나씩 비운다(앞 항목이 자세함을
    지킨다 — 결정적). 다 비워도 넘으면 그대로 돌려준다(core 펼침 상한·모음의 ResultTooLarge 가 이름 있게 실패).
    (항목, 누적)."""
    out = list(items)
    sizes = [octets(i) for i in out]
    k = len(out)
    while used + sum(sizes) > budget and k > 0:
        k -= 1
        out[k] = trim_for_budget(out[k])
        sizes[k] = octets(out[k])
    return out, used + sum(sizes)


OVER_BUDGET: Final = ev.Failed(stage="plan", code=BUDGET_CODE)
"""상한 뒤 부르지 않은 후보의 근거 자리(item_of 가 budget_exceeded 항목으로 싣는다 — stage 는 쓰지 않는다)."""


def judge_segment(
    inputs: G1Inputs, adapters: G1Adapters, carried: Carried, segment: Segment, ctx: StepContext
) -> SegmentOutput:
    view = view_of(adapters, carried)
    built = built_of(view)
    check_built(built, carried)
    idx = ev.Index(built, vectors_of(carried))
    order = rg.block_order(view)
    vocab = str(carried["extract"].data["vocab"])
    calls = G1Calls(adapters.client, adapters.embedding, tags=adapters.tags, vocab=vocab)
    lines = inputs.criteria
    items: list[dict[str, object]] = []
    unplaced: list[dict[str, object]] = []
    over = False  # 642-2: 비용 상한에 한 번 걸리면 이 구획의 남은 후보는 부르지 않는다(같은 이름의 failed 항목)
    for row in cast("list[dict[str, object]]", segment.input["candidates"]):
        c = cl.candidate_of(row)
        if c.block_ids is None:
            unplaced.append({"text": c.sentence[: r2.TARGET_TEXT_MAX], "page": c.page, "errorCode": "quote_not_found"})
            continue
        if over:
            items.append(item_of(c, OVER_BUDGET, None, idx, order, built.block_text, c.parts, inputs.categories))
            continue
        got = ev.find_evidence(
            idx, ev.Claim(text=c.sentence, block_ids=c.block_ids), calls.ports(), budget=ev.BUDGET_CHARS
        )
        judged: jd.JudgeOutcome | None = None
        if not isinstance(got, ev.Failed):
            ids = list(got.passage_ids) if isinstance(got, ev.Found) else []
            variables = jd.judge_vars(
                claim=c.sentence,
                page=c.page,
                evidence=ev.evidence_text(idx, ids),
                lines=lines,
                categories=inputs.categories,
            )
            judged = jd.judge(calls.judge, variables, lines)
        items.append(item_of(c, got, judged, idx, order, built.block_text, c.parts, inputs.categories))
        over = items[-1]["errorCode"] == BUDGET_CODE
    kept, _ = fit(items, SEGMENT_BUDGET_OCTETS, octets({"items": [], "unplaced": unplaced}))
    return SegmentOutput(data={"items": kept, "unplaced": unplaced})


# ── 장벽 gather ──


class ResultTooLarge(Exception):
    """예산 잘림 뒤에도 result@2 본문이 RESULT_BODY_MAX_OCTETS 를 넘는다(실행기의 result_too_large 와 같은 뜻 — 조용히
    버리지 않는다)."""

    code: Final = "result_too_large"


def gather(inputs: G1Inputs, adapters: G1Adapters, carried: Carried, ctx: StepContext) -> StepOutput:
    entries = cast("list[dict[str, Any]]", carried["judge"].data["segments"])
    seen: set[str] = set()
    segments: list[dict[str, object]] = []
    for e in entries:
        if e["status"] != "done":
            segments.append(
                {
                    "key": e["key"],
                    "keySha256": e["keySha256"],
                    "status": "failed",
                    "errorCode": e["errorCode"],
                    "items": [],
                    "unplaced": [],
                }
            )
            continue
        data = cast("dict[str, Any]", e["data"])
        items: list[dict[str, object]] = []
        for item in cast("list[dict[str, object]]", data["items"]):
            key = str(item["stableKey"])
            if key in seen:
                continue
            seen.add(key)
            items.append(item | {"key": f"i{len(items) + 1}"})
        segments.append(
            {
                "key": e["key"],
                "keySha256": e["keySha256"],
                "status": "done",
                "errorCode": None,
                "items": items,
                "unplaced": data["unplaced"],
            }
        )
    # 방어 길: 구획 몫(150 × SEGMENT_BUDGET = BUDGET)이 먼저 지키므로 여기서 더 자를 일은 보통 없다(검증 4 R5).
    used = octets({"schemaVersion": RESULT_SHAPE, "source": _source(carried), "segments": [], "failures": {}})
    for seg in segments:
        empty: list[object] = []
        shell = octets(
            {
                "key": seg["key"],
                "keySha256": seg["keySha256"],
                "status": seg["status"],
                "errorCode": seg["errorCode"],
                "items": empty,
            }
        )
        shell += octets(seg["unplaced"]) + len(', "unplaced": ')
        seg["items"], used = fit(cast("list[dict[str, object]]", seg["items"]), BUDGET_OCTETS, used + shell)
    trimmed = sum(
        "budget" in cast("dict[str, list[str]]", i["checks"])["truncated"]
        for seg in segments
        for i in cast("list[dict[str, Any]]", seg["items"])
    )
    result: dict[str, object] = {
        "schemaVersion": RESULT_SHAPE,
        "source": _source(carried),
        "failures": r2.count_failures(segments),
        "budgetTrimmed": trimmed,
        "segments": segments,
    }
    r2.check_result(result)
    if octets(result) > RESULT_BODY_MAX_OCTETS:
        raise ResultTooLarge(f"result@2 본문이 예산 잘림 뒤에도 {RESULT_BODY_MAX_OCTETS}바이트를 넘는다")
    return StepOutput(data={"results": [result]})


def check_results(results: tuple[dict[str, object], ...]) -> None:
    """끝 결과 검사 훅(types.ResultCheck) — result@2 꼴과 꼴 밖 규칙."""
    for result in results:
        r2.check_result(result)


def g1_flow(*, max_segments: int = MAX_SEGMENTS) -> Flow:
    """흐름 greenwash.engine@G1. 전역 REGISTRY 에는 registration.FLOWS 가 단다(GE1b ③ — 기본값 아님, 실행 시작은 끼움의
    환경 스위치). 시험·드라이버는 새 FlowRegistry 나 run_flow 에 바로 넘겨도 된다(max_segments 를 줄여서)."""
    return make_flow(
        module="greenwash",
        id=FLOW_ID,
        input_shape=INPUT_SHAPE,
        inputs=G1Inputs,
        adapters=G1Adapters,
        result_shapes=(RESULT_SHAPE,),
        steps=(
            FlowStep(name="extract", run=extract),
            FlowStep(name="index", run=index),
            FlowStep(name="candidates", run=candidates),
            FanoutStep(
                name="judge",
                plan=plan,
                run=judge_segment,
                on_failure="pass_to_gather",
                allow_empty=True,
                max_segments=max_segments,
            ),
            FlowStep(name="gather", run=gather),
        ),
        result_checks=(check_results,),
    )
