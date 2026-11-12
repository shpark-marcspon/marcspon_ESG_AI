"""재판단(밴드 GRJ1 — 결정 MARC-ENT-617, 화면 GW-05 r4)의 꼴 둘. TypedDict(모르는 키 금지).

    GreenwashEvidenceAdded     사람이 더한 근거 조각 {text, page|null} — 검토 PUT 본문·검토 GET·재판단 옵션·결과
    GreenwashRejudgeOptions    흐름 greenwash.rejudge@E0 의 실행 옵션(서버가 굳힌다 — 웹은 POST /runs 로 만들지 못한다)
    GreenwashRejudgeResult     그 실행의 결과 greenwash.rejudge@1
    GreenwashRejudgeCreated    재판단 만들기(POST …/items/{itemIndex}/rejudge)의 202 응답

**이 파일에 로직은 없다.** 규칙(service/actions/rejudge.py·review.py, flows/rejudge_e0.py):
- 재판단은 원 실행(fromRunId, 흐름 greenwash.colab@E0)의 문장 하나(itemIndex)를 **원 실행의 AI 설정 판 그대로** 다시
  판정한다(MARC-ENT-617 Q2). 판정 함수는 엔진(engines/e0/checker.py)의 것을 부르기만 한다(ENT-442 — 엔진 사본 0).
- 근거 = 남긴 AI 칩(kept — 기준 판단의 confirmedInEvidence 에서 지우지 않은 것, 쪽 없음) + 더한 조각(added)(Q1).
  칩은 AI 가 근거에서 확인한 「사실」이지 근거 원문이 아니다 — 원문은 결과에 저장되지 않는다.
- 갈래: lowOnly(원 판단이 Low — 선언적 문장)면 eval_low_only, 아니면 eval_high_mid_or_nonrisk. 후자가 NonRisk 를
  내면 outcome = nonrisk(문장을 지우지 않는다 — Q3), item.level = null.
- 결과의 item 은 결과 꼴(result@1)의 Item 가운데 판정이 내는 칸만이다(page·parts·sentence·position·exampleSentence 는
  원 항목 그대로라 싣지 않는다).

이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, Literal, NotRequired, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, with_config

from esgapi.greenwash.contracts.shapes import FORBID, Count, Level, Page

SHAPE: Final = "greenwash.rejudge@1"

# 본문(PUT)·옵션에도 드는 꼴이라 strict 를 따로 둔다(review_shapes.STRICT_FORBID 와 같은 까닭 — 중첩 TypedDict).
STRICT_FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True, strict=True)


@with_config(STRICT_FORBID)
class GreenwashEvidenceAdded(TypedDict):
    """사람이 더한 근거 조각."""

    text: Annotated[str, Field(min_length=1)]
    """조각 글(앞뒤 공백을 지운 1~1,000자 — 서버가 다듬어 저장한다)."""
    page: Page | None
    """조각이 나온 쪽(1부터). 고르지 않았으면 null."""


@with_config(STRICT_FORBID)
class GreenwashRejudgeOptions(TypedDict):
    """greenwash.rejudge@E0 실행의 옵션. 서버(검토 화면의 재판단 경로)가 만들 때 굳힌다."""

    fromRunId: Annotated[int, Field(ge=1)]
    """원 실행 id(흐름 greenwash.colab@E0, 끝난 실행)."""
    itemIndex: Count
    """원 실행 결과 items 의 차례(0부터)."""
    sentence: Annotated[str, Field(min_length=1)]
    """다시 판정할 문장(원 항목의 sentence 그대로)."""
    lowOnly: bool
    """원 판단이 Low(선언적 문장)인가. 갈래를 정한다."""
    kept: list[str]
    """남긴 AI 칩(기준 판단의 confirmedInEvidence 차례 그대로, 지운 것 뺌)."""
    added: list[GreenwashEvidenceAdded]
    """더한 조각(받은 차례)."""
    maxCharsPerChunk: Annotated[int, Field(ge=1)]
    """조각 하나의 글자 상한(원 실행 config.checker 그대로)."""
    maxCharsEvidenceTotal: Annotated[int, Field(ge=1)]
    """근거 글 합의 상한(원 실행 config.checker 그대로)."""
    promptVersion: NotRequired[Annotated[str, Field(min_length=1)]]
    """판정 프롬프트 판 글자 — 만들 때 원 실행 결과의 config.checker 로 셈한 것(GRS1 — MARC-ISSUE-632). 이 칸이 없는
    옛 재판단 옵션은 지금 코드의 SCAN_CONFIG 로 셈한다(flows/rejudge_e0.judge)."""


@with_config(FORBID)
class GreenwashRejudgeItem(TypedDict):
    """재판단이 낸 판정 칸. 칸 뜻은 result@1 의 Item 과 같다. nonrisk 이면 level 이 null."""

    level: Level | None
    riskTags: list[str]
    confirmedInEvidence: list[str]
    missingFields: list[str]
    reasonBullets: list[str]
    fixParagraph: str
    evidencePages: list[Page]
    """보낸 근거 가운데 쪽이 있는 조각의 쪽(오름·겹침 없음)."""
    evidenceInternal: str


@with_config(FORBID)
class GreenwashRejudgeResult(TypedDict):
    """greenwash.rejudge@1 — 재판단 실행 하나의 결과. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.rejudge@1"]
    fromRunId: int
    itemIndex: Count
    sentence: str
    kept: list[str]
    """보낸 남긴 칩(옵션 그대로)."""
    added: list[GreenwashEvidenceAdded]
    """보낸 더한 조각(옵션 그대로)."""
    outcome: Literal["judged", "nonrisk"]
    """judged = 등급이 났다 · nonrisk = AI 가 리스크 아님으로 봤다(문장은 지우지 않는다)."""
    item: GreenwashRejudgeItem


@with_config(FORBID)
class GreenwashRejudgeCreated(TypedDict):
    """재판단 실행을 만들었다(queued). 상태는 검토 GET(review@3)의 rejudges 로 읽는다."""

    rejudgeRunId: int
    """만든 재판단 실행의 id."""


REJUDGE_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashRejudgeResult]]] = {SHAPE: TypeAdapter(GreenwashRejudgeResult)}
OPTIONS: Final = TypeAdapter(GreenwashRejudgeOptions)
