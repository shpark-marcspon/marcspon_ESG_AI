"""Scope 3 줄 덧판의 순수 셈 — 몸 검사·지금 상태 접기·570 셈. 밴드 S3K2b-1 ①(결정 MARC-ENT-570, 발주서 Q1·Q2·Q4·Q6).

편집은 (회사, 실행, 줄 rowId)에 매인 불변 사건이다. 지금 상태는 축 둘이다(S3K2b-2): 제외 축(exclude·restore)과 계수 축
(factor) 마다 그 (실행, rowId) 의 가장 큰 id 사건 — 계수 사건이 제외 상태를 가리지 않는다. 히스토리 = 그 사건들.
새 실행에 옮겨 붙이지 않는다(570) — 그래서 접는 열쇠에 실행이 든다.

  SCOPE3_REASON_MAX  사유 글자 수 — 기획 RPT-21 §3.3 의 300(Scope 1·2 의 REASON_MAX 500 은 [우리 해석]이라 따로 둔다)
  ROW_ID_MAX         rowId 칸 길이 — 엑셀 시트 이름 상한 31 + `!` + 줄 7자리 + `#` + n 7자리 = 47 에 여유(C0-2)
  ROW_IDS_MAX        한 요청의 줄 수 상한
  check_body         몸 검사(Q4 ①) — 걷은 사유 또는 Invalid
  fold               사건들 → (실행, rowId, 축) 마다 가장 큰 id 사건
  edited_rows        그 실행 그 카테고리에서 지금 상태가 AI 원안과 다른 줄 수(제외 ∪ 계수 고침 — 한 줄이 둘 다여도 1)
  excluded_of        그 실행 그 카테고리의 제외된 rowId 집합
  co2e_of            그 실행 그 카테고리에서 계수가 AI 원안과 다른 줄의 고친 배출량(rowId → 글자)
  rows_of            결과 본문에서 그 카테고리 processed 시트의 rowId 들
  row_of             결과 본문에서 그 카테고리 processed 시트의 줄 하나
"""

from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, cast

from esgapi.inventory.service.utils.ghg_pool import Invalid
from esgapi.inventory.service.utils.scope3_factors import Factor
from esgapi.inventory.service.utils.scope3_state import engine_category

SCOPE3_REASON_MAX: Final = 300
ROW_ID_MAX: Final = 64
ROW_IDS_MAX: Final = 2000
EDIT_KINDS: Final = ("exclude", "restore", "factor")
ROW_AXIS: Final = "row"
FACTOR_AXIS: Final = "factor"

EditKind = Literal["exclude", "restore", "factor"]
Now = Mapping[tuple[int, str, str], "Event"]

ROW_IDS_EMPTY: Final = "줄을 하나 이상 고른다"
ROW_IDS_TOO_MANY: Final = f"한 번에 {ROW_IDS_MAX}줄까지다"
ROW_IDS_REPEATED: Final = "같은 줄이 두 번 들었다"
ROW_IDS_UNKNOWN: Final = "이 실행의 이 카테고리 줄이 아니다"
REASON_BAD: Final = f"사유는 앞뒤 공백을 걷고 1~{SCOPE3_REASON_MAX}자다"


@dataclass(frozen=True, slots=True)
class Event:
    """편집 한 번(표 inventory_scope3_row_edits 의 한 줄)."""

    id: int
    run_id: int
    category: str
    row_id: str
    kind: EditKind
    reason: str
    at: datetime
    actor_user_id: int
    batch_id: str | None
    factor: Factor | None = None  # kind 가 factor 일 때만


def axis_of(kind: EditKind) -> str:
    return FACTOR_AXIS if kind == "factor" else ROW_AXIS


def check_body(row_ids: Sequence[str], reason: str) -> str | Invalid:
    """몸 검사(Q4 ①): rowIds 1~ROW_IDS_MAX·겹침 0 · reason 앞뒤 공백 걷고 1~300자. 지나면 걷은 사유."""
    fields: dict[str, str] = {}
    if not row_ids:
        fields["rowIds"] = ROW_IDS_EMPTY
    elif len(row_ids) > ROW_IDS_MAX:
        fields["rowIds"] = ROW_IDS_TOO_MANY
    elif len(set(row_ids)) != len(row_ids):
        fields["rowIds"] = ROW_IDS_REPEATED
    stripped = reason.strip()
    if not 1 <= len(stripped) <= SCOPE3_REASON_MAX:
        fields["reason"] = REASON_BAD
    return Invalid(fields) if fields else stripped


def fold(events: Iterable[Event]) -> dict[tuple[int, str, str], Event]:
    """(실행, rowId, 축) → 그 축의 지금 상태 사건(가장 큰 id). 받는 차례에 기대지 않는다."""
    found: dict[tuple[int, str, str], Event] = {}
    for event in events:
        key = (event.run_id, event.row_id, axis_of(event.kind))
        last = found.get(key)
        if last is None or event.id > last.id:
            found[key] = event
    return found


def excluded_of(now: Now, run_id: int, category: str) -> frozenset[str]:
    """그 실행 그 카테고리에서 지금 제외된 줄."""
    return frozenset(
        row_id
        for (event_run, row_id, _), event in now.items()
        if event_run == run_id and event.category == category and event.kind == "exclude"
    )


def co2e_of(now: Now, run_id: int, category: str) -> dict[str, str | None]:
    """그 실행 그 카테고리에서 계수가 AI 원안과 다른 줄(recommended·custom)의 고친 배출량. applied 는 안 든다."""
    return {
        row_id: event.factor.co2e
        for (event_run, row_id, _), event in now.items()
        if event_run == run_id
        and event.category == category
        and event.factor is not None
        and event.factor.choice != "applied"
    }


def edited_rows(now: Now, run_id: int, category: str) -> int:
    """지금 상태가 AI 원안과 다른 줄 수 — 제외됐거나 계수를 고친 줄(한 줄이 둘 다여도 1). 제외 뒤 복구·applied 는 0."""
    return len(excluded_of(now, run_id, category) | co2e_of(now, run_id, category).keys())


def _mapping(value: object) -> Mapping[str, object] | None:
    return cast("Mapping[str, object]", value) if isinstance(value, Mapping) else None


def _items(value: object) -> list[object]:
    return cast("list[object]", value) if isinstance(value, list) else []


def rows_of(body: Mapping[str, object] | None, category: str) -> frozenset[str]:
    """결과 본문에서 그 카테고리 processed 시트의 rowId 들(카테고리 하나에 시트가 여럿일 수 있다 — C4-1·C4-2)."""
    if body is None:
        return frozenset()
    name = engine_category(category)
    found: set[str] = set()
    for item in _items(body.get("sheets")):
        sheet = _mapping(item)
        if sheet is None or sheet.get("category") != name or sheet.get("status") != "processed":
            continue
        for line in _items(sheet.get("rows")):
            row = _mapping(line)
            row_id = None if row is None else row.get("rowId")
            if isinstance(row_id, str):
                found.add(row_id)
    return frozenset(found)


def row_of(body: Mapping[str, object] | None, category: str, row_id: str) -> Mapping[str, object] | None:
    """결과 본문에서 그 카테고리 processed 시트의 줄 하나. 없으면 None."""
    if body is None:
        return None
    name = engine_category(category)
    for item in _items(body.get("sheets")):
        sheet = _mapping(item)
        if sheet is None or sheet.get("category") != name or sheet.get("status") != "processed":
            continue
        for line in _items(sheet.get("rows")):
            row = _mapping(line)
            if row is not None and row.get("rowId") == row_id:
                return row
    return None
