"""결과 꼴 greenwash.result@2 의 정의(밴드 GE1 — 새 흐름 greenwash.engine@G1 의 결과). TypedDict(모르는 키 금지) → JSON
스키마. result@1(shapes.py)은 그대로다 — 이 꼴은 새 판이고 1차 흐름은 이것을 쓰지 않는다.

뼈대(공통 결과 계약 안 `band-handoffs/core-io/6-result-contract-proposal.md` 리뷰 반영 판):
    실행 → 구획(segments) → 항목(items)
  - 실행 머리(모델·비용·시간·판)는 싣지 않는다. runs(`RunRow.versions`)와 사용량 기록이 진실이다
    (shapes.py 머리말과 같다).
  - 실패는 구획·항목 자리마다 status 판별 칸이다. 꼭대기 failures 는 그 셈뿐이다(check_result 가 다시 센다).
  - 열쇠 둘: key(구획 안 유일, 필수) · stableKey(문서 sha · 정규화 문장 · 쪽의 해시 앞 32자 —
    engines/g1/checks.stable_key).
    실행을 넘는 짝은 stableKey 로 짝 목록을 셈한다(자동 옮겨 붙임 0 — MARC-ENT-211).
  - 근거는 갈래 판별(kind)이고 문서 근거는 자리만 둔다(단락 id·블록 범위·첫 쪽, 글은 문서 산출물에서 읽는다).
    블록 범위 [첫 블록, 끝 블록] = 문서의 body 블록 읽는 차례에서 그 둘 사이(끝 포함)의 블록 전부
    (engines/g1/ranges — 감독 답 C1, 11-10).
  - 「위험 아님」도 싣는다(verdict.level "None"). 판정을 못 한 항목도 버리지 않는다(status failed, verdict null).
  - 문장을 원문 블록에 못 붙인 후보는 항목이 아니라 그 구획의 unplaced 에 싣는다(blockIds 0개 항목은 없다).

글자·개수 상한은 꼴이 거절한다. 흐름(flows/engine_g1 의 모음)은 넘는 값을 미리 자르고 항목 checks.truncated 에 칸 이름을
적는다 — 그래서 꼴의 상한은 흐름이 지킬 값이자 크기 셈의 바탕이다.

클래스 이름은 전부 `GreenwashResult2` 접두(GE1b — openapi 구성요소가 result@1 의 같은 이름과 겹치지 않게). 접두는
cross 결정 전 잠정이다 — 바꿔도 generated 만 바뀐다(JSON 값의 꼴은 그대로).

이 파일은 엔진·흐름을 import 하지 않는다(.importlinter 「아」). 공통 칸을 core 로 올리는 것은 영문번역에서 두 번째로
맞춘 뒤의 cross 결정이다(D8).
"""

from collections.abc import Mapping, Sequence
from typing import Annotated, Final, Literal, NotRequired, TypedDict, cast

from pydantic import ConfigDict, Field, TypeAdapter, with_config

SHAPE: Final = "greenwash.result@2"
FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)

TARGET_TEXT_MAX: Final = 300
REASON_MAX: Final = 500
NOTE_LINES_MAX: Final = 4
NOTE_LINE_MAX: Final = 150
EVIDENCE_MAX: Final = 12
EVIDENCE_RANGES_MAX: Final = 8
"""문서 근거 하나의 블록 범위 상한(네 권 실측 단락 범위 최대 5 — 넘으면 앞 8 + checks.truncated)."""
CRITERIA_LINES_MAX: Final = 15
CRITERIA_LINE_MAX: Final = 300
TARGET_BLOCKS_MAX: Final = 2
STABLE_KEY_CHARS: Final = 32
UNPLACED_MAX: Final = 64
"""구획 하나의 unplaced 상한(구획 = 후보 8 이라 넉넉한 그물)."""

Page = Annotated[int, Field(ge=1)]
Count = Annotated[int, Field(ge=0)]
ID_MAX: Final = 16
"""항목 key·단락 id·블록 id 의 글자 상한(실측 네 권 블록 id 최대 8자 — 감독 답 ⓒ ①, 11-10. 64 에서 줄임:
크기 셈 T17)."""
LINE_ID_MAX: Final = 24
"""기준 줄 id 의 글자 상한(기준 판 15줄 id 최대 17자 — criteria_shapes GreenwashCriterionId)."""
Id = Annotated[str, Field(min_length=1, max_length=ID_MAX)]
LineId = Annotated[str, Field(min_length=1, max_length=LINE_ID_MAX)]
NoteLine = Annotated[str, Field(max_length=NOTE_LINE_MAX)]
Notes = Annotated[list[NoteLine], Field(max_length=NOTE_LINES_MAX)]
StableKey = Annotated[str, Field(pattern=r"^[0-9a-f]{32}$")]
BlockRange = Annotated[list[Id], Field(min_length=2, max_length=2)]
"""[첫 블록 id, 끝 블록 id] — 블록 하나면 둘이 같다."""

Level = Literal["High", "Mid", "Low", "None"]
"""판정 등급. High·Mid 는 위험(근거와 견줘 근거가 모자라거나 과장된 주장 — High 가 더 무겁다), Low 는 「선언적 문장」
(수치·검증 없이 다짐만 하는 문장 — E0 어미 규칙 heuristics.is_low_declarative 가 정한다), None 은 위험 아님(근거가
주장을 받친다). result@1 과 달리 위험 아님도 항목에 싣는다."""

ItemErrorCode = Literal[
    "quote_not_found",
    "evidence_outside_pool",
    "category_unknown",
    "level_rule_broken",
    "judge_failed",
    "judge_unparsed",
    "judge_cut_off",
    "evidence_search_failed",
    "budget_exceeded",
]
"""항목이 failed 인 까닭. 검사 넷(quote_not_found·evidence_outside_pool·category_unknown·level_rule_broken)은 코드가
판정 뒤에 잰 것이고, judge_*·evidence_search_failed 는 공급사·응답의 실패다(Mid 로 구제하지 않는다 — E0 흠 8 반대).
budget_exceeded = 실행 비용 상한(근거 찾기·판정 어느 쪽에서 걸려도 이 이름 — 642-2). 처음 걸린 뒤 그 구획의 남은 후보는
부르지 않고 같은 이름으로 싣는다(구획은 done). 다시 돌리는 길은 고른 구획 다시(구획 keySha256 → retrySegments.keys)."""

CheckState = Literal["pass", "fail", "skipped"]
TruncatedField = Literal[
    "target.text",
    "reason",
    "module.confirmed",
    "module.missing",
    "evidence",
    "evidence.blockRanges",
    "criteriaLines",
    "budget",
]
"""budget = 실행 바이트 예산을 지키려 모음이 그 항목의 근거 범위(blockRanges → [])와 발췌 칸(confirmed·missing → [])을
비웠다(감독 답 ⓒ ②). 글은 문서 산출물에서 passageId 로 다시 읽을 수 있다."""


@with_config(FORBID)
class GreenwashResult2Source(TypedDict):
    """점검한 문서."""

    fileName: str
    sha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    pageCount: Count


@with_config(FORBID)
class GreenwashResult2Failures(TypedDict):
    """실패 셈(구획 status failed 수, 항목 status failed 수 — 모든 구획의 항목 합)."""

    segments: Count
    items: Count


@with_config(FORBID)
class GreenwashResult2SegmentKeyFields(TypedDict):
    """구획 열쇠(core.flows.types.segment_key_fields 와 같은 칸). span 은 위치 표지(블록 번호)뿐이다."""

    kind: str
    span: str
    documentSha256: str | None
    parserVersion: str | None


@with_config(FORBID)
class GreenwashResult2Target(TypedDict):
    """판단 대상 문장."""

    kind: Literal["sentence"]
    text: Annotated[str, Field(min_length=1, max_length=TARGET_TEXT_MAX)]
    page: Page
    blockIds: Annotated[list[Id], Field(min_length=1, max_length=TARGET_BLOCKS_MAX)]
    """문장이 든 블록(읽는 차례). 블록 경계를 넘는 문장은 이어진 블록 둘."""


@with_config(FORBID)
class GreenwashResult2Verdict(TypedDict):
    level: Level
    category: str | None
    """판의 카테고리 목록 안의 이름. 목록이 비면(MARC-ENT-612 전) null 만."""


@with_config(FORBID)
class GreenwashResult2DocumentEvidence(TypedDict):
    """문서 근거 = 단락 하나의 자리. 글은 문서 산출물에서 blockRanges 로 읽는다."""

    kind: Literal["document"]
    passageId: Id
    blockRanges: Annotated[list[BlockRange], Field(max_length=EVIDENCE_RANGES_MAX)]
    """단락을 이루는 블록의 범위(읽는 차례, 이어진 블록은 한 범위). 넘는 범위는 모음이 자르고 truncated 에 적는다.
    빈 목록은 그 항목 truncated 에 budget 이 있을 때만(check_result)."""
    page: Page
    """단락의 첫 쪽."""
    span: NotRequired[Annotated[list[Annotated[int, Field(ge=0)]], Field(min_length=2, max_length=2)]]
    """[start, end) — 글머리 쪼갬 단락이 블록 하나일 때 그 블록 글 안의 글자 범위. 없으면 블록 글 전부.
    있으면 blockRanges 는 블록 하나의 범위 하나다(check_result)."""


@with_config(FORBID)
class GreenwashResult2CriteriaEvidence(TypedDict):
    """참조 기준 줄 하나(기준 판의 줄 id)."""

    kind: Literal["criteria"]
    lineId: LineId


@with_config(FORBID)
class GreenwashResult2HumanEvidence(TypedDict):
    """사람이 넣은 근거(칸만 — G4. 이 판의 흐름은 싣지 않는다)."""

    kind: Literal["human"]
    text: Annotated[str, Field(min_length=1, max_length=2000)]
    at: str


Evidence = Annotated[
    GreenwashResult2DocumentEvidence | GreenwashResult2CriteriaEvidence | GreenwashResult2HumanEvidence,
    Field(discriminator="kind"),
]


@with_config(FORBID)
class GreenwashResult2Checks(TypedDict):
    """코드가 판정 뒤에 잰 것. skipped = 잴 것이 없었다(판정 실패 등)."""

    quoteInBlock: CheckState
    evidenceInPool: CheckState
    categoryInList: CheckState
    levelRule: CheckState
    truncated: list[TruncatedField]
    """상한을 넘어 모음이 자른 칸."""


@with_config(FORBID)
class GreenwashResult2Module(TypedDict):
    """그린워싱만의 칸."""

    confirmed: Notes
    """근거에서 확인된 것(줄마다 150자, 4줄까지)."""
    missing: Notes
    """근거에 빠진 것."""
    criteriaLines: Annotated[list[LineId], Field(max_length=CRITERIA_LINES_MAX)]
    """걸린 기준 줄 id."""
    parts: list[str]
    """문장 쪽이 든 파트 이름(겹치면 여럿)."""


@with_config(FORBID)
class GreenwashResult2DoneItem(TypedDict):
    """판정과 검사를 다 지난 항목."""

    key: Id
    stableKey: StableKey
    status: Literal["done"]
    errorCode: None
    target: GreenwashResult2Target
    verdict: GreenwashResult2Verdict
    reason: Annotated[str, Field(min_length=1, max_length=REASON_MAX)]
    evidence: Annotated[list[Evidence], Field(max_length=EVIDENCE_MAX)]
    checks: GreenwashResult2Checks
    module: GreenwashResult2Module


@with_config(FORBID)
class GreenwashResult2FailedItem(TypedDict):
    """실패한 항목(버리지 않는다). 판정은 됐는데 검사에 걸리면 verdict 가 남고, 판정 자체가 안 됐으면 null."""

    key: Id
    stableKey: StableKey
    status: Literal["failed"]
    errorCode: ItemErrorCode
    target: GreenwashResult2Target
    verdict: GreenwashResult2Verdict | None
    reason: Annotated[str, Field(max_length=REASON_MAX)]
    evidence: Annotated[list[Evidence], Field(max_length=EVIDENCE_MAX)]
    checks: GreenwashResult2Checks
    module: GreenwashResult2Module


Item = Annotated[GreenwashResult2DoneItem | GreenwashResult2FailedItem, Field(discriminator="status")]


@with_config(FORBID)
class GreenwashResult2Unplaced(TypedDict):
    """원문 블록에 못 붙인 후보 문장."""

    text: Annotated[str, Field(min_length=1, max_length=TARGET_TEXT_MAX)]
    page: Page
    errorCode: Literal["quote_not_found"]


@with_config(FORBID)
class GreenwashResult2Segment(TypedDict):
    """구획 하나(후보 묶음). failed 면 items·unplaced 가 빈 목록이고 errorCode 는 실행기가 지은 code 다."""

    key: GreenwashResult2SegmentKeyFields
    keySha256: Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
    """구획 열쇠의 sha256(펼침 단계 data 의 keySha256 그대로 — core segment_key_sha256). 구획 목록
    `GET /runs/{run_id}/segments` 의 짝이자 고른 구획 다시(`retrySegments.keys`)에 넣는 값(GE1b D7)."""
    status: Literal["done", "failed"]
    errorCode: str | None
    items: list[Item]
    unplaced: Annotated[list[GreenwashResult2Unplaced], Field(max_length=UNPLACED_MAX)]


@with_config(FORBID)
class GreenwashResult2(TypedDict):
    """greenwash.result@2. schemaVersion 이 첫 키다. 구획 차례 = 계획 차례(문서 읽는 차례), 항목 차례 = 구획 안
    후보 차례."""

    schemaVersion: Literal["greenwash.result@2"]
    source: GreenwashResult2Source
    failures: GreenwashResult2Failures
    budgetTrimmed: Count
    """실행 바이트 예산으로 근거 범위·발췌 칸을 비운 항목 수(truncated 에 budget — check_result 가 다시 센다)."""
    segments: list[GreenwashResult2Segment]


RESULT2: Final = TypeAdapter[GreenwashResult2](GreenwashResult2)
"""validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""


class Result2Invalid(ValueError):
    """꼴 밖의 규칙(실패 셈·첫 키·열쇠 겹침·stableKey 겹침·status 와 errorCode·checks 짝·블록 범위 끝 겹침·span 짝)을
    어겼다."""


def count_failures(segments: Sequence[Mapping[str, object]]) -> dict[str, int]:
    """구획·항목 status 에서 다시 센 실패 셈."""
    items = [item for seg in segments for item in cast("list[Mapping[str, object]]", seg["items"])]
    return {
        "segments": sum(1 for seg in segments if seg["status"] == "failed"),
        "items": sum(1 for item in items if item["status"] == "failed"),
    }


def check_result(result: Mapping[str, object]) -> None:
    """꼴(strict) + 꼴 밖 규칙. 틀리면 pydantic ValidationError 나 Result2Invalid."""
    if next(iter(result), None) != "schemaVersion":
        raise Result2Invalid("첫 키가 schemaVersion 이 아니다")
    RESULT2.validate_python(result, strict=True)
    segments = cast("list[Mapping[str, object]]", result["segments"])
    if dict(cast("Mapping[str, int]", result["failures"])) != count_failures(segments):
        raise Result2Invalid("failures 가 구획·항목 status 셈과 다르다")
    seen_spans: set[str] = set()
    seen_stable: set[str] = set()
    trimmed = 0
    for seg in segments:
        span = cast("Mapping[str, str]", seg["key"])["span"]
        if span in seen_spans:
            raise Result2Invalid(f"구획 열쇠가 겹친다: {span}")
        seen_spans.add(span)
        items = cast("list[Mapping[str, object]]", seg["items"])
        if seg["status"] == "failed" and (items or seg["unplaced"] or seg["errorCode"] is None):
            raise Result2Invalid("failed 구획은 항목·unplaced 가 비고 errorCode 가 있어야 한다")
        if seg["status"] == "done" and seg["errorCode"] is not None:
            raise Result2Invalid("done 구획의 errorCode 는 null 이어야 한다")
        keys = [item["key"] for item in items]
        if len(set(keys)) != len(keys):
            raise Result2Invalid("구획 안 항목 key 가 겹친다")
        for item in items:
            truncated = cast("list[str]", cast("Mapping[str, object]", item["checks"])["truncated"])
            check_document_evidence(cast("list[Mapping[str, object]]", item["evidence"]), budget="budget" in truncated)
            trimmed += "budget" in truncated
            check_item_checks(item)
            stable = str(item["stableKey"])
            if stable in seen_stable:
                raise Result2Invalid(f"stableKey 가 결과 안에서 겹친다: {stable}")
            seen_stable.add(stable)
    if result["budgetTrimmed"] != trimmed:
        raise Result2Invalid("budgetTrimmed 가 truncated 에 budget 이 든 항목 수와 다르다")


CHECK_OF_CODE: Final[Mapping[str, str]] = {
    "quote_not_found": "quoteInBlock",
    "evidence_outside_pool": "evidenceInPool",
    "category_unknown": "categoryInList",
    "level_rule_broken": "levelRule",
}
"""검사 실패 errorCode → 그 검사 칸."""


def check_item_checks(item: Mapping[str, object]) -> None:
    """항목 status ↔ checks 짝(검증 1 R2): done 은 fail 인 검사가 없고, 검사 실패 errorCode 면 그 칸이 fail 이다."""
    checks = cast("Mapping[str, object]", item["checks"])
    failed = {name for name in CHECK_OF_CODE.values() if checks[name] == "fail"}
    code = item["errorCode"]
    if item["status"] == "done" and failed:
        raise Result2Invalid(f"done 항목에 fail 인 검사가 있다: {sorted(failed)}")
    if isinstance(code, str) and code in CHECK_OF_CODE and checks[CHECK_OF_CODE[code]] != "fail":
        raise Result2Invalid(f"errorCode {code} 인데 {CHECK_OF_CODE[code]} 가 fail 이 아니다")


def check_document_evidence(evidence: Sequence[Mapping[str, object]], *, budget: bool = False) -> None:
    """문서 근거의 블록 범위: 범위 끝 블록이 다른 범위와 겹치지 않고, span 이 있으면 블록 하나의 범위 하나다. 빈 범위
    목록은 budget(그 항목이 예산으로 비워짐)일 때만이고 그때 span 도 없다.
    범위가 차례를 지키는지(첫 ≤ 끝)는 블록 차례가 문서에 있어 여기서 못 잰다 — 모음(ranges.fold)이 지어서 지킨다."""
    for ev in evidence:
        if ev["kind"] != "document":
            continue
        ranges = cast("list[list[str]]", ev["blockRanges"])
        if not ranges and not budget:
            raise Result2Invalid(f"근거 {ev['passageId']} 의 블록 범위가 비었다(예산 잘림 표시 없이)")
        ends = [b for first, last in ranges for b in dict.fromkeys((first, last))]
        if len(set(ends)) != len(ends):
            raise Result2Invalid(f"근거 {ev['passageId']} 의 블록 범위 끝이 겹친다")
        if "span" in ev and not (len(ranges) == 1 and ranges[0][0] == ranges[0][1]):
            raise Result2Invalid(f"근거 {ev['passageId']} 의 span 은 블록 하나의 범위 하나에만 붙는다")
