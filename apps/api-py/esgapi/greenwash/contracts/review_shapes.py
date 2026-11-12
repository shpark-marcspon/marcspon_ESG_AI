"""검토 꼴 greenwash.review@3 의 정의 — 한 실행의 판정 문장마다 사람이 매긴 채택·제외(marks)와 고친 등급·판정 사유·수정
방향(edits), 근거 고침(evidence)과 재판단(rejudges). **굳힌 판 — 칸을 바꾸면 새 판(@4).** (@1 은 초안 판이었다. @2 는
edits 를 더하고 굳혔다 — 밴드 G1b-3, MARC-ISSUE-96 (1), 결정 MARC-ENT-354 6. @3 은 @2 에 evidence·rejudges 두 목록을
더한 것이다 — 밴드 GRJ1, 결정 MARC-ENT-617, 화면 GW-05 r4. 나머지 칸은 @2 와 같다. 검토 JSON 은 저장하지 않으므로 앞
판을 읽는 길은 없다.)

TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/review/greenwash.review@3.schema.json.
클래스 이름이 openapi 의 구성요소 이름이 되므로 `Greenwash` 로 시작한다.

**이 파일에 로직은 없다.** 규칙(저장·잠금·상태 바꾸기·미검토 채우기·고침 정규화 — service/actions/review.py):
- 문장의 열쇠는 (runId, itemIndex) 다. itemIndex 는 그 실행의 결과(greenwash.result@1) items 의 차례(0부터).
  결과는 실행마다 한 번 쓰면 바뀌지 않으므로 이 열쇠도 바뀌지 않는다.
- 표시(mark)가 없는 문장은 미검토다.
- `excludeReason` 은 `excluded` 일 때만 글이고 그 밖에는 null 이다. 1차에는 자유 글이다(사유 코드 목록은 출처가
  없다 — 마크스폰 확인 전).
- `confirmedAt`·`confirmedBy` 는 `confirmed` 일 때만 값(때는 +09:00 이 붙은 ISO 8601, 사람은 {id, name})이고 그
  밖에는 null 이다.
- 상태는 서버가 바꾼다(PUT 본문의 state 는 confirmed 만 받는다):
  (a) 표시나 고침이 하나라도 있는 PUT 이면 pending → in_review(고침은 정규화 뒤 — 아래). 둘 다 0 이고 state 가 없으면
      pending 그대로, in_review 에서 marks = [] 로 PUT 해도 in_review 그대로다.
  (b) state = confirmed 로 PUT 하면 표시 없는 문장을 서버가 adopted 로 채우고 confirmedAt·confirmedBy 를 넣는다.
      응답의 marks 는 그 실행 결과의 items 수만큼 전부다(화면이 다 채워 보내도 결과는 같다).
  (c) 확정하면 잠긴다: 확정된 실행에 PUT 하면(edits 만 실어도) 409 `REVIEW_LOCKED`(legacyCode `review_locked`).
      확정본이 엑셀·지표와 비교(greenwash.compare@1)의 기준이다. 대기·진행 중인 재판단이 하나라도 있으면 확정 PUT 은
      409 `REJUDGE_RUNNING`(legacyCode `rejudge_running`) — 확정 뒤에 기준 판단이 바뀌지 않게(GRJ1 ④).
      evidence 를 실은 PUT 이 재판단이 대기·진행 중인 문장의 근거를 지금 값과 다르게 바꿔도 409
      `REJUDGE_RUNNING`(같은 값을 다시 실음·다른 문장·표시·고침은 받는다 — GRJ3).
- 고침(edits — 밴드 G1b-3):
  - **AI 원본은 결과 GET(greenwash.result@1)의 items[itemIndex] 다(불변).** 이 꼴에 AI 사본은 없다. 화면이 보일 값 =
    고친 값 ?? AI 값(칸마다).
  - 칸 셋(level·reasonBullets·fixParagraph)은 칸마다 따로다: null = 그 칸은 AI 그대로, 값 = {value, editedAt,
    editedBy}. editedAt·editedBy 는 그 칸 값이 바뀐 PUT 의 때·사람이다(다른 칸만 바꾼 PUT 에서는 그대로).
  - edits 에는 고친 칸이 하나 이상인 문장만 itemIndex 오름차순으로 겹치지 않게 실린다(없으면 []). 제외한 문장도 고칠 수
    있다. 고침의 이력(앞 값들)은 없다 — 칸마다 마지막 값과 AI 원본뿐.
  - PUT 의 edits: 생략·null = 고침 그대로, 목록 = 그 실행의 고침 전부를 갈아 넣기([] = 다 지움). 서버는 앞뒤 공백을
    지우고(판정 사유는 항목마다, 빈 항목은 버림) AI 값과 같은 칸은 null 로 접는다. marks 갈아 넣기는 고침을, edits
    갈아 넣기는 채택·제외를 건드리지 않는다.
- 기준 판단(GRJ1): 문장마다 AI 판단은 첫 판단(결과 GET 의 items[itemIndex] — 불변)과, 재판단이 있으면 그 가운데 가장
  늦게 끝난(done) 재판단의 판단이 있다. **기준 판단** = 가장 늦은 done 재판단 판단, 없으면 첫 판단. 화면이 보일 값 =
  고친 값 ?? 기준 판단 ?? 첫 판단(칸마다). 고침 정규화(「AI 값과 같으면 null」)도 기준 판단과 견준다.
  재판단은 AI 값만 바꾼다 — 고친 칸은 그대로다(물음: 마크스폰 r4 ③).
- 근거 고침(evidence — GRJ1): 문장마다 removed(기준 판단의 confirmedInEvidence 차례 가운데 지운 것, 오름·겹침 없음)와
  added(더한 조각, 받은 차례). 재판단이 끝나 기준 판단이 바뀌면 removed 는 옛 칩을 가리키므로 [] 로 읽는다(added 는
  남는다). removed·added 가 둘 다 비면 그 문장은 evidence 에 없다. PUT 의 evidence: 생략·null = 근거 고침 그대로,
  목록 = 그 실행의 근거 고침 전부를 갈아 넣기([] = 다 지움). 확정 뒤에는 409 `REVIEW_LOCKED`.
- 재판단(rejudges — GRJ1): 재판단 실행이 하나라도 있는 문장만. status 는 가장 늦게 만든 재판단 실행의 상태(running =
  대기·진행 · failed · done), count 는 끝난(done) 재판단 수, current 는 기준 판단(done 재판단이 없으면 null — 첫 판단은
  결과 GET). 실패해도 current 는 앞 값 그대로다. 재판단 만들기는 POST /greenwash/runs/{runId}/items/{itemIndex}/rejudge.
- 오류 code: 확정 뒤 PUT 409 `REVIEW_LOCKED` · 재판단 대기·진행 중 확정 409 `REJUDGE_RUNNING` · 실행이 done 이
  아니면 409 `RUN_NOT_DONE`(legacyCode `run_not_done`) ·
  dry-run 실행의 review PUT 은 409 `NO_REVIEW`(legacyCode `no_review`) · 실행이 없거나 남의 회사면 404 · 표시·고침
  규칙 어김 400 `INVALID_REVIEW`(한국어 한 문장).
- 저장은 그린워싱 모듈의 표시 표 greenwash_review_marks 한 행(회사, run_id, item_index) — 표시와 고침 칸이 같은 행이다.

PUT 의 본문(GreenwashReviewUpdate)은 경로 쪽(service/apis/greenwash.py)의 Schema 다. 본문에 드는 표시·고침 꼴은
여기 둔다. 이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, Literal, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, with_config

from esgapi.greenwash.contracts.rejudge_shapes import GreenwashEvidenceAdded
from esgapi.greenwash.contracts.shapes import FORBID, Count, Level, Page

SHAPE: Final = "greenwash.review@3"

GreenwashReviewStateName = Literal["pending", "in_review", "confirmed"]
"""실행의 검토 상태: 검토 대기 · 검토 중 · 확정."""


# 표시·고침은 PUT 본문(GreenwashReviewUpdate)에도 들어간다. 본문 Schema 의 strict(StrictIn)는 자기 config 가 있는 중첩
# TypedDict 에 내려가지 않아(2026-10-15 실측: item_index 가 true·1.0·"1" 을 받았다) 이 꼴에 strict 를 따로 둔다.
# JSON 스키마는 바뀌지 않는다(strict 는 스키마에 나오지 않는다).
STRICT_FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True, strict=True)


@with_config(STRICT_FORBID)
class GreenwashReviewMark(TypedDict):
    """문장 하나의 표시."""

    itemIndex: Count
    """결과 items 의 차례(0부터)."""
    decision: Literal["adopted", "excluded"]
    """채택 · 제외."""
    excludeReason: str | None
    """제외 사유. excluded 일 때만 글, 그 밖에는 null."""


@with_config(FORBID)
class GreenwashReviewer(TypedDict):
    """확정한 사람. 응답 전용(본문에 오지 않는다 — 사람은 세션에서 온다)."""

    id: int
    """사용자 id(int). 세션의 user_id(글자)를 int 로 바꾸는 것은 G1b 몫이다."""
    name: Annotated[str, Field(min_length=1)]
    """화면에 보일 이름(빈 글자 아님)."""


@with_config(FORBID)
class GreenwashReviewEditedLevel(TypedDict):
    """고친 등급. 칸의 값과 그 값을 넣은 때·사람."""

    value: Level
    """고친 등급."""
    editedAt: str
    """이 칸을 고친 때(+09:00 ISO 8601). 이 칸 값이 바뀐 PUT 의 때."""
    editedBy: GreenwashReviewer
    """이 칸을 고친 사람(못 풀면 이름 「알 수 없는 사용자」)."""


@with_config(FORBID)
class GreenwashReviewEditedReasons(TypedDict):
    """고친 판정 사유. 칸의 값과 그 값을 넣은 때·사람."""

    value: list[str]
    """고친 판정 사유(줄마다 하나, 빈 줄 없음)."""
    editedAt: str
    """이 칸을 고친 때(+09:00 ISO 8601). 이 칸 값이 바뀐 PUT 의 때."""
    editedBy: GreenwashReviewer
    """이 칸을 고친 사람(못 풀면 이름 「알 수 없는 사용자」)."""


@with_config(FORBID)
class GreenwashReviewEditedFix(TypedDict):
    """고친 수정 방향. 칸의 값과 그 값을 넣은 때·사람."""

    value: str
    """고친 수정 방향(빈 글자 아님)."""
    editedAt: str
    """이 칸을 고친 때(+09:00 ISO 8601). 이 칸 값이 바뀐 PUT 의 때."""
    editedBy: GreenwashReviewer
    """이 칸을 고친 사람(못 풀면 이름 「알 수 없는 사용자」)."""


@with_config(FORBID)
class GreenwashReviewEdit(TypedDict):
    """문장 하나의 고침. 칸 셋 중 하나 이상이 값이다. AI 원본은 결과 items[itemIndex]."""

    itemIndex: Count
    """결과 items 의 차례(0부터)."""
    level: GreenwashReviewEditedLevel | None
    """고친 등급. null 이면 AI 등급 그대로."""
    reasonBullets: GreenwashReviewEditedReasons | None
    """고친 판정 사유. null 이면 AI 판정 사유 그대로."""
    fixParagraph: GreenwashReviewEditedFix | None
    """고친 수정 방향. null 이면 AI 수정 방향 그대로."""


@with_config(STRICT_FORBID)
class GreenwashReviewEditIn(TypedDict):
    """PUT 본문의 문장 하나의 고침(평평한 값 — 때·사람은 서버가 넣는다). null = 그 칸은 고침 없음."""

    itemIndex: Count
    """결과 items 의 차례(0부터)."""
    level: Level | None
    """고친 등급. null 이면 고침 없음."""
    reasonBullets: list[str] | None
    """고친 판정 사유(줄마다 하나). null 이면 고침 없음."""
    fixParagraph: str | None
    """고친 수정 방향. null 이면 고침 없음."""


@with_config(FORBID)
class GreenwashReviewEvidence(TypedDict):
    """문장 하나의 근거 고침. removed·added 가운데 하나 이상이 비지 않는다."""

    itemIndex: Count
    """결과 items 의 차례(0부터)."""
    removed: list[Count]
    """기준 판단의 confirmedInEvidence 차례 가운데 지운 것(오름·겹침 없음)."""
    added: list[GreenwashEvidenceAdded]
    """더한 조각(받은 차례)."""
    editedAt: str
    """근거를 마지막으로 고친 때(+09:00 ISO 8601)."""
    editedBy: GreenwashReviewer
    """근거를 마지막으로 고친 사람(못 풀면 이름 「알 수 없는 사용자」)."""


@with_config(STRICT_FORBID)
class GreenwashReviewEvidenceIn(TypedDict):
    """PUT 본문의 문장 하나의 근거 고침(때·사람은 서버가 넣는다)."""

    itemIndex: Count
    """결과 items 의 차례(0부터)."""
    removed: list[Count]
    """기준 판단의 confirmedInEvidence 차례 가운데 지운 것(서버가 오름·겹침 없음으로 다듬는다)."""
    added: list[GreenwashEvidenceAdded]
    """더한 조각(10개까지, 한 조각 앞뒤 공백을 지운 1~1,000자)."""


GreenwashRejudgeStatus = Literal["running", "failed", "done"]
"""가장 늦게 만든 재판단 실행의 상태: 대기·진행 중 · 실패 · 끝남."""


@with_config(FORBID)
class GreenwashRejudged(TypedDict):
    """기준 판단(가장 늦게 끝난 재판단의 판단). 칸 뜻은 결과 꼴의 Item 과 같다."""

    runId: int
    """그 재판단 실행의 id."""
    judgedAt: str
    """재판단이 끝난 때(+09:00 ISO 8601)."""
    judgedBy: GreenwashReviewer
    """재판단을 누른 사람(못 풀면 이름 「알 수 없는 사용자」)."""
    outcome: Literal["judged", "nonrisk"]
    """judged = 등급이 났다 · nonrisk = AI 가 리스크 아님으로 봤다(level null — 문장은 지우지 않는다)."""
    level: Level | None
    riskTags: list[str]
    confirmedInEvidence: list[str]
    missingFields: list[str]
    reasonBullets: list[str]
    fixParagraph: str
    evidencePages: list[Page]
    added: list[GreenwashEvidenceAdded]
    """이 판단에 보낸 더한 조각. 근거 고침의 added 가 이것과 같고 removed 가 비면 다시 판단할 것이 없다."""


@with_config(FORBID)
class GreenwashReviewRejudge(TypedDict):
    """문장 하나의 재판단 상태."""

    itemIndex: Count
    """결과 items 의 차례(0부터)."""
    status: GreenwashRejudgeStatus
    """가장 늦게 만든 재판단 실행의 상태."""
    count: Count
    """끝난(done) 재판단 수."""
    current: GreenwashRejudged | None
    """기준 판단. 끝난 재판단이 없으면 null(첫 판단은 결과 GET 의 items[itemIndex])."""


@with_config(FORBID)
class GreenwashReviewState(TypedDict):
    """greenwash.review@3 — 한 실행의 검토 상태. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.review@3"]
    runId: int
    """검토하는 실행의 id."""
    state: GreenwashReviewStateName
    """검토 상태."""
    confirmedAt: str | None
    """확정한 때(+09:00 ISO 8601). confirmed 일 때만 값, 그 밖에는 null."""
    confirmedBy: GreenwashReviewer | None
    """확정한 사람. confirmed 일 때만 값, 그 밖에는 null(confirmedAt 과 같은 규칙)."""
    marks: list[GreenwashReviewMark]
    """표시한 문장(itemIndex 오름차순, 겹치지 않음). 없는 문장은 미검토. confirmed 이면 결과의 items 전부다."""
    edits: list[GreenwashReviewEdit]
    """고친 문장(itemIndex 오름차순, 겹치지 않음). 고친 칸이 하나 이상인 문장만, 없으면 []."""
    evidence: list[GreenwashReviewEvidence]
    """근거를 고친 문장(itemIndex 오름차순, 겹치지 않음). 없으면 []."""
    rejudges: list[GreenwashReviewRejudge]
    """재판단 실행이 있는 문장(itemIndex 오름차순, 겹치지 않음). 없으면 []."""


REVIEW_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashReviewState]]] = {SHAPE: TypeAdapter(GreenwashReviewState)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
