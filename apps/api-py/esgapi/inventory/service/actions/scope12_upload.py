"""Scope 1·2 일괄 올리기의 몸(밴드 S12b-2 ② — 결정 MARC-ENT-472). HTTP 를 모른다.

    upload(company_id, year, data, actor)   양식 바이트 → 빈 칸만 채움. 전부-아니면-전무

판정 차례(`@transaction.atomic` 하나):
  ⓪ 해 잠금(`lock_year`). 없으면 NotFound. 아래는 전부 그 잠금 아래다 — 판정과 쓰기 사이에 같은 해 저장이 끼지 못한다.
     해를 잠그지 않는 쓰기(잠그기·지움)는 ⑤ 의 `Locked`·거절로 나온다.
  ② 숨기지 않은 선택 0 → NotFound(쓸 곳이 없는 해에서는 파일을 읽지 않는다 — 틀린 파일이어도 404).
  ① 읽기(`tools/scope12_upload.py`) — 파일 오류는 Invalid `file`.
  ③ 읽을 일의 양(`UPLOAD_WORK_MAX`)을 넘으면 상세를 읽지 않고 Invalid `file` — 그래서 줄 오류보다 먼저 나온다.
  ④ 줄마다 판정, 오류를 모아 Invalid(주소 → 글, 앞 100개, 넘으면 `more`) — 0 씀.
  ④' 읽기 + 쓰기의 일의 양을 넘으면 Invalid `file` — 0 씀(줄 오류가 먼저다). 빈 칸만 채우므로 나눠 올려도 된다.
  ⑤ 블록마다 `entries.save_rows`. 검사·히스토리·셈은 거기 한 벌뿐이다. 하나라도 거절이면 되돌린다.
  ⑥ UploadDone.

★ 양식 줄 = (잎, 사업장). 그 블록의 자산/시설이 정확히 하나일 때만 받는다 — 여럿이면 어느 행인지 양식이 말하지 않는다.
★ 빈 칸만 채운다: 값 있는 칸에 같은 값(값 비교 — 「1.50」=「1.5」)은 unchanged, 다른 값은 오류. 그래서 나눠 올려도 되고
  같은 파일을 두 번 올리면 두 번째는 쓰기 0 이다.
★ 조용히 바꾸지 않는다: 있는 행의 N/A(`na=before.na`)·단위(다르면 오류)·값 비고 추정만 켜진 칸의 추정(옛 값 그대로).
★ ⑤ 는 사업장 id 오름차순으로 돈다: 조직구조의 일괄 지움(`lock_branches`)이 id 차례로 사업장을 잠그므로, 잎 차례로 돌면
  서로 다른 차례로 잠가 교착(40P01)이 날 수 있다.
★ 오류 글에 받은 칸 값·양식의 사업장 이름을 싣지 않는다(남의 이름의 있고 없음이 글로 갈리지 않는다). 없는 잎·고르지 않은
  잎·숨긴 잎은 같은 글이고, 남의·지운·꺼진 사업장도 같은 글이다.
★ 무효 조건: 양식에 사업장 id 가 없어 내려받은 뒤 두 사업장 이름을 맞바꾸면 값이 다른 사업장에 든다 — 이름이 유일하다는
  것만 지킨다.
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from django.db import transaction

from esgapi.inventory.service.actions import entries
from esgapi.inventory.service.selectors import index_selection as selections
from esgapi.inventory.service.utils.entries import (
    Actor,
    IndexDetail,
    Locked,
    RowInput,
    RowView,
    SiteBlock,
    SlotInput,
    SlotValue,
    amount_problem,
    slots,
)
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound, parse_decimal
from esgapi.inventory.tools.scope3_sheets.grid import AddressProblem, parse_address
from esgapi.inventory.tools.scope12_upload import LineProblem, UploadLine, UploadProblem, read_upload
from esgapi.inventory.tools.scope12_xlsx import PERIOD_LABELS, TEMPLATE_SHEETS, slot_labels
from esgapi.organization.service.selectors.branches import facilities_of, search_sites

UPLOAD_ERRORS_MAX: Final = 100
UPLOAD_WORK_MAX: Final = 340_000
"""상세를 만드는 횟수 × 한 번의 값(`_detail_work`)의 상한. 상세는 ③ 에서 잎마다, ⑤ 에서 저장마다 한 번 만들어지고
그때마다 켠 사업장 전부와 그 시설 전부를 돈다. 그동안 해 잠금을 쥐므로 업로드 전체를 15초 안으로 잡는다
(가지 리뷰 M1 · 검증 B3).
잰 값(시험 DB, 부하 5 안, 칸 12 씩, 읽기 + 쓰기, 값 · 시간 · 사업장 × 시설):
327천 12.5s 120 × 1 · 333천 12.9s 10 × 30 · 313천 9.3~9.9s 3 × 300(일부만 채움) · 372천 14.4~15.9s 20 × 15 ·
410천 15.6~15.8s 90 × 2 · 514천 18.5~19.7s 1 × 300.
튄 판이 있다: 3 × 300 의 첫 재기가 17.5·29.6s(시작 부하 4.6·4.5)였고 다시 잰 6판은 위의 값이다. 원인은 못 밝혔다.
15초는 풀이 씨앗 크기이고 기계가 조용할 때의 값이지 보장이 아니다. 식 밖의 것으로 상한 안 꼴(값 33만)이 넘는다:
풀 +1,000 노드 17.6s · +3,000 노드 29.3s · 풀 +1,000 에 통계가 낡음 51.9s · 행마다 다른 판을 덮어씀 17.5s(값 32만).
상세가 풀 전체를 읽기 때문이다. 시간의 바깥 안전장치는 MARC-ISSUE-586(DB 시간 상한)의 몫이다."""
DETAIL_WORK: Final = 540
"""상세 한 번의 고정 값. 단위는 시설 한 줄을 읽는 시간이다. 이것과 `SITE_WORK` 는 시험 DB 의 18 꼴에 맞춘 값이다
(약 20ms · 0.66ms · 38µs) — 운영 DB 에서 잰 값이 아니다."""
SITE_WORK: Final = 17
"""사업장 하나를 도는 값(시설 조회 한 번)."""
FILE: Final = "file"
MORE: Final = "more"
NO_LEAF: Final = "이 회사가 고른 인덱스가 아니에요"
NO_SITE: Final = "켜져 있는 사업장이 아니에요"
LOCKED_LEAF: Final = "잠긴 인덱스예요"
NO_FACILITY: Final = "자산/시설이 없어요"
MANY_FACILITIES: Final = "상세 시설이 여럿이에요 — 상세 화면에서 넣어 주세요"
NA_ROW: Final = "N/A 로 둔 행이에요 — 상세 화면에서"
BAD_NEW_UNIT: Final = "이 시설의 단위로 넣을 수 없어요 — 상세 화면에서 넣어 주세요"
PAST_YEAR: Final = "지난 해는 그 해 화면에서"
HAS_VALUE: Final = "이미 값이 있어요 — 상세 화면에서 고쳐 주세요"
CHANGED: Final = "그 사이 바뀌었어요 — 다시 올려 주세요"
TOO_MUCH_WORK: Final = "한 번에 올리기에 줄이 많아요 — 나눠서 올려 주세요"


@dataclass(frozen=True)
class UploadDone:
    added: int  # 새로 세운 행
    filled: int  # 채운 칸
    unchanged: int  # 같은 값이라 그대로 둔 칸
    unresolved: int  # 올린 잎에서 셈하지 못한 행


@dataclass(frozen=True)
class _Plan:
    """블록 하나의 저장 한 번."""

    node_id: int
    site_id: int
    row: RowInput


def _row_input(line: UploadLine, facility_id: int, before: RowView | None, values: Sequence[SlotInput]) -> RowInput:
    """있는 행은 N/A 를 그대로 넘긴다(`RowInput.na` 기본값 False 가 na_off 줄을 쓴다)."""
    return RowInput(
        site_facility_id=facility_id,
        unit=line.unit,
        na=before.na if before is not None else False,
        values=tuple(values),
        row_id=before.id if before is not None else None,
    )


def _slot_input(slot: str, text: str, old: SlotValue | None) -> SlotInput:
    """빈 칸을 채운다. 값 비고 추정만 켜진 칸의 추정 표시는 옛 값 그대로다(양식에 추정 칸이 없다)."""
    return SlotInput(slot, text, old.estimated if old is not None else False)


def _block_problem(line: UploadLine, detail: IndexDetail | None, sites: Mapping[str, int]) -> str | None:
    """잎·사업장·잠금 — 블록을 찾기 전의 글."""
    if detail is None:
        return NO_LEAF
    if line.site not in sites:
        return NO_SITE
    return LOCKED_LEAF if detail.locked_at is not None else None


def _row_problem(line: UploadLine, block: SiteBlock, before: RowView | None, units: tuple[str, ...]) -> str | None:
    """주기·N/A·단위 — 행까지 찾은 뒤의 글."""
    if line.period != block.period:
        return f"이 사업장은 {PERIOD_LABELS[block.period]} 입력이에요"
    if before is not None and before.na:
        return NA_ROW
    if before is not None and line.unit != before.unit:
        return f"이 행은 {before.unit}로 넣어요"
    if before is None and line.unit not in units:
        return BAD_NEW_UNIT
    return None


def _cells(
    line: UploadLine, block: SiteBlock, before: RowView | None, year: int
) -> tuple[list[SlotInput], int, list[LineProblem]]:
    """칸마다: 채울 칸 · 같은 값 수 · 오류."""
    by_label = dict(zip(slot_labels(year, block.period), slots(year, block.period), strict=True))
    old_values = {value.slot: value for value in before.values} if before is not None else {}
    values: list[SlotInput] = []
    unchanged = 0
    problems: list[LineProblem] = []
    for cell in line.cells:
        slot = by_label.get(cell.label)
        if slot is None:
            problems.append(LineProblem(cell.address, PAST_YEAR))
            continue
        wrong = amount_problem(cell.text)
        if wrong is not None:
            problems.append(LineProblem(cell.address, wrong))
            continue
        old = old_values.get(slot)
        if old is None or old.amount is None:
            values.append(_slot_input(slot, cell.text, old))
        elif old.amount == parse_decimal(cell.text):
            unchanged += 1
        else:
            problems.append(LineProblem(cell.address, HAS_VALUE))
    return values, unchanged, problems


def _judge_line(
    line: UploadLine, detail: IndexDetail | None, sites: Mapping[str, int], year: int
) -> tuple[_Plan | None, int, list[LineProblem]]:
    wrong = _block_problem(line, detail, sites)
    if wrong is not None or detail is None:
        return None, 0, [LineProblem(line.address, wrong or NO_LEAF)]
    site_id = sites[line.site]
    block = next((found for found in detail.sites if found.site_id == site_id), None)
    if block is None:  # 그 잎 코드의 자산/시설이 없는 사업장은 블록이 없다
        return None, 0, [LineProblem(line.address, NO_FACILITY)]
    if len(block.facilities) != 1:
        return None, 0, [LineProblem(line.address, MANY_FACILITIES)]
    (facility,) = block.facilities
    facility_id = facility.id
    before = next((row for row in block.rows if row.site_facility_id == facility_id), None)
    wrong = _row_problem(line, block, before, detail.unit_options)
    if wrong is not None:
        return None, 0, [LineProblem(line.address, wrong)]
    values, unchanged, problems = _cells(line, block, before, year)
    if not values:
        return None, unchanged, problems
    return _Plan(detail.node_id, site_id, _row_input(line, facility_id, before, values)), unchanged, problems


def _place(problem: LineProblem) -> tuple[int, int, int]:
    """오류의 자리(시트 차례 · 행 · 열)."""
    sheet, _, cell = problem.address.partition("!")
    where = parse_address(cell)
    row, column = (0, 0) if isinstance(where, AddressProblem) else (where.row, where.column)
    return TEMPLATE_SHEETS.index(sheet), row, column


def _refused(problems: Sequence[LineProblem]) -> Invalid:
    ordered = sorted(problems, key=_place)
    fields = {problem.address: problem.message for problem in ordered[:UPLOAD_ERRORS_MAX]}
    if len(ordered) > UPLOAD_ERRORS_MAX:
        fields[MORE] = f"그 밖에 {len(ordered) - UPLOAD_ERRORS_MAX}개가 더 있어요"
    return Invalid(fields)


def _detail_work(company_id: int, sites: Mapping[str, int]) -> int:
    """상세 한 번의 값. 사업장 수만으로는 묶이지 않는다 — 사업장마다 시설 수가 다르다."""
    facilities = sum(len(facilities_of(company_id, site_id)) for site_id in sites.values())
    return DETAIL_WORK + SITE_WORK * len(sites) + facilities


def _details(company_id: int, year: int, leaves: Collection[int]) -> dict[int, IndexDetail]:
    """그 잎들의 상세. 잎·판이 지워져 NotFound 인 잎은 없는 잎과 같다."""
    found: dict[int, IndexDetail] = {}
    for node_id in sorted(leaves):
        detail = entries.index_detail(company_id, year, node_id)
        if isinstance(detail, IndexDetail):
            found[node_id] = detail
    return found


def _unresolved(details: Mapping[int, IndexDetail]) -> int:
    return sum(1 for detail in details.values() for block in detail.sites for row in block.rows if row.emission_problem)


@transaction.atomic
def upload(company_id: int, year: int, data: bytes, actor: Actor) -> UploadDone | NotFound | Invalid | Locked:
    """일괄업로드 양식을 올린다. 하나라도 틀리면 0 씀(머리말의 판정 차례)."""
    if selections.lock_year(company_id, year) is None:
        return NotFound()
    rows = entries.list_rows(company_id, year)
    if isinstance(rows, Invalid) or not rows.configured:
        return NotFound()
    book = read_upload(data, year)
    if isinstance(book, UploadProblem):
        return Invalid({FILE: book.message})
    chosen = {row.node_id for group in rows.scopes for row in group.rows}
    leaves = {line.node_id for line in book.lines} & chosen
    sites = {site.name: site.id for site in search_sites(company_id).branches if site.inventory_enabled}
    work = _detail_work(company_id, sites)
    if len(leaves) * work > UPLOAD_WORK_MAX:
        return Invalid({FILE: TOO_MUCH_WORK})
    details = _details(company_id, year, leaves)
    plans: list[_Plan] = []
    unchanged = 0
    problems = list(book.problems)
    for line in book.lines:
        plan, same, wrong = _judge_line(line, details.get(line.node_id), sites, year)
        unchanged += same
        problems += wrong
        if plan is not None:
            plans.append(plan)
    if problems:
        return _refused(problems)
    if (len(leaves) + len(plans)) * work > UPLOAD_WORK_MAX:
        return Invalid({FILE: TOO_MUCH_WORK})
    for plan in sorted(plans, key=lambda found: (found.site_id, found.node_id)):
        saved = entries.save_rows(company_id, year, plan.node_id, plan.site_id, [plan.row], actor)
        if not isinstance(saved, IndexDetail):
            transaction.set_rollback(True)
            return saved if isinstance(saved, Locked) else Invalid({FILE: CHANGED})
        details[plan.node_id] = saved
    return UploadDone(
        added=sum(1 for plan in plans if plan.row.row_id is None),
        filled=sum(len(plan.row.values) for plan in plans),
        unchanged=unchanged,
        unresolved=_unresolved(details),
    )
