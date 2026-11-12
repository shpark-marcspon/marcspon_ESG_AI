"""드롭다운(입력 템플릿)과 계수 책의 어긋남 검사. 파일도 DB 도 없다.

**어느 쪽도 정본으로 삼지 않는다.** 결과에는 「옳은 쪽」·「고칠 값」·「권고」 칸이 없다. 있는 것은 자리와 수뿐이다:
목록에 있고 책의 그 열에 없다 / 책의 그 열에 있고 목록에 없다 / 둘 다에 있다.
「계수가 없다」고 적지 않는다(뜻을 붙이지 않는다). 「고르지 않음」을 뜻하는 항목도 빼지 않는다(빼는 것은 읽는 쪽이다).

견주기는 **글자까지 같음**이다. 다듬지 않는다. 다듬으면(NFKC, 앞뒤 공백) 맞는 짝은 `near` 로 따로 센다 —
맞았다고 치지 않는다.

검사의 목록은 자료다(`LIST_CHECKS`, `MAPPING_TARGETS`, `UNIT_TEXT_CHECK`). 번호는 발주서(밴드 S3a)의 대조표의 것이다.
- K9 의 겹친 짝(같은 (종류, 처리방법)이 두 줄)은 줄을 다 싣는다. 어느 줄도 고르지 않는다.
- K11 의 `unit` 묶음은 단위 목록 셋과 **따로따로** 견준다. 어느 목록이 상대인지는 파일이 정하지 않는다. 합치지 않는다.
- K15 는 이름이 같은 짝의 단위 원문 둘을 나란히 싣고 글자가 다른 짝을 세기만 한다. 값을 견주지 않는다
  (두 시트의 값 열은 뜻이 다르다). 환산하지 않는다.
- K12·K16 은 여기 없다(템플릿의 행 파서와 같이 다음 밴드 S3b 의 일).

★ `MAPPING_TARGETS`(매핑검토의 묶음 ↔ 드롭다운)는 파일이 이름으로 적어 준 것이 아니다. 매핑검토의 요약 줄과
  드롭다운 시트 2행의 설명을 읽고 사람이 이은 것이다. 틀렸으면 이 자료를 고친다.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Final, Literal

from esgapi.inventory.tools.scope3_sheets.dropdowns import Dropdowns, ListItem
from esgapi.inventory.tools.scope3_sheets.factors import FactorBook
from esgapi.inventory.tools.scope3_sheets.grid import Cell, NumberCell, TextCell

# ── 검사의 목록(자료) ──────────────────────────────────────────────────────

TRAVEL_CODES: Final = "@표준코드"  # `배출계수_드롭다운` N 열(정의된 이름이 없다)
C12_MINOR: Final = "@C12소분류"  # `C12` 시트의 AG 열(정의된 이름이 없다)
C12_SEPARATOR: Final = " | "  # 그 목록의 항목은 `코드 | 이름` 꼴이다

KeyParts = Literal["whole", "first", "all"]


@dataclass(frozen=True, slots=True)
class ListCheck:
    check: str
    lists: tuple[str, ...]  # 하나면 그 목록, 둘이면 두 목록의 모든 짝(곱)
    key_parts: KeyParts  # whole: 항목 그대로 · first: 구분자 앞 조각 · all: 구분자로 나눈 조각 전부
    book_sheet: str
    book_columns: tuple[str, ...]
    duplicates: bool  # 책 쪽에서 같은 열쇠가 여러 줄이면 따로 낸다
    basis: str


LIST_CHECKS: Final[tuple[ListCheck, ...]] = (
    ListCheck("K1", ("DD_PURCHASE_GROUP",), "whole", "구매_USEPA", ("A",), False, "목록 ↔ 책의 A 열"),
    ListCheck("K2", ("DD_ENERGY",), "whole", "에너지", ("C",), False, "목록 ↔ 책의 C 열"),
    ListCheck("K3", ("DD_ENERGY",), "whole", "에너지_C3", ("B",), False, "목록 ↔ 책의 B 열"),
    ListCheck("K4a", ("DD_ENERGY_UNIT",), "whole", "에너지", ("D",), False, "목록 ↔ 책의 단위 열(D)"),
    ListCheck("K4b", ("DD_ENERGY_UNIT",), "whole", "에너지_C3", ("C",), False, "목록 ↔ 책의 단위 열(C)"),
    ListCheck("K5", ("DD_TRANSPORT_DISTANCE",), "whole", "운송", ("C",), False, "목록 ↔ 책의 C 열(원본명)"),
    ListCheck("K6", ("DD_TRANSPORT_SPEND",), "whole", "운송_Spend", ("D",), False, "목록 ↔ 책의 D 열(운송)"),
    ListCheck("K7", (TRAVEL_CODES,), "whole", "출장_통근", ("D",), False, "드롭다운 시트의 N 열 ↔ 책의 D 열(코드)"),
    ListCheck("K8", ("DD_TRAVEL_SPEND",), "whole", "출장_Spend", ("D",), False, "목록 ↔ 책의 D 열(출장)"),
    ListCheck(
        "K9",
        ("DD_WASTE_C5_TYPE", "DD_WASTE_METHOD"),
        "whole",
        "폐기물_C5",
        ("A", "B"),
        True,
        "두 목록의 모든 짝 ↔ 책의 (A, B) 줄",
    ),
    ListCheck("K10a", (C12_MINOR,), "first", "폐기물_C12", ("C",), False, "시트 안 목록(AG)의 앞 조각 ↔ 책의 C 열"),
    ListCheck(
        "K10b",
        (C12_MINOR,),
        "all",
        "폐기물_C12",
        ("C", "D"),
        False,
        "시트 안 목록(AG)의 두 조각 ↔ 책의 (C, D)",
    ),
)

# 매핑검토의 묶음 → 그 「DB 기준값」을 견줄 드롭다운(들). 머리말의 ★.
MAPPING_TARGETS: Final[dict[str, tuple[str, ...]]] = {
    "purchase_group": ("DD_PURCHASE_GROUP",),
    "capital_group": ("DD_PURCHASE_GROUP",),
    "energy": ("DD_ENERGY",),
    "transport_distance": ("DD_TRANSPORT_DISTANCE",),
    "transport_spend": ("DD_TRANSPORT_SPEND",),
    "travel_distance": ("DD_TRAVEL_DISTANCE",),
    "travel_spend": ("DD_TRAVEL_SPEND",),
    "waste_c5": ("DD_WASTE_C5_TYPE",),
    # 어느 단위 목록이 상대인지 파일이 정하지 않는다. 셋과 따로따로 견준다(합치지 않는다).
    "unit": ("DD_ENERGY_UNIT", "DD_WASTE_UNIT", "DD_TRANSPORT_WEIGHT_UNIT"),
}


MAPPING_TARGETS_BASIS: Final = "사람이 이은 것(파일에 이름으로 적혀 있지 않다). 마크스폰 확인 전"


@dataclass(frozen=True, slots=True)
class UnitTextCheck:
    check: str
    via: str  # 이름이 같은 짝을 정한 검사(K3)
    left_sheet: str
    left_name_column: str
    left_unit_column: str
    right_sheet: str
    right_name_column: str
    right_unit_column: str


UNIT_TEXT_CHECK: Final = UnitTextCheck("K15", "K3", "에너지", "C", "D", "에너지_C3", "B", "C")

# Scope 3 의 카테고리 번호(시트 이름의 `C<번호>`). 발주서의 K14 가 1~15 로 본다.
CATEGORY_NUMBERS: Final = tuple(range(1, 16))
_CATEGORY: Final = re.compile(r"C([0-9]+)")

# ── 결과의 갈래 ────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class Located:
    key: tuple[str, ...]
    where: tuple[str, ...]  # `시트!칸` 들


@dataclass(frozen=True, slots=True)
class NearPair:
    """글자는 다르지만 다듬으면(NFKC, 앞뒤 공백) 같은 짝. 맞은 것으로 세지 않는다."""

    template: Located
    db: Located


@dataclass(frozen=True, slots=True)
class ListComparison:
    check: str
    list_total: int  # 목록 쪽 항목 수(분모)
    db_distinct: int  # 책 쪽의 서로 다른 열쇠 수
    matched: tuple[Located, ...]  # 목록의 항목 가운데 책의 그 열에도 있는 것
    template_only: tuple[Located, ...]  # 목록에 있고 책의 그 열에 없다
    db_only: tuple[Located, ...]  # 책의 그 열에 있고 목록에 없다(서로 다른 열쇠마다 하나)
    near: tuple[NearPair, ...]


@dataclass(frozen=True, slots=True)
class DuplicateKey:
    check: str
    key: tuple[str, ...]
    where: tuple[str, ...]  # 그 열쇠의 줄 전부. 어느 줄도 고르지 않는다


@dataclass(frozen=True, slots=True)
class MappingComparison:
    """매핑검토 사전의 한 묶음의 「DB 기준값」을 드롭다운 하나와 견준 것."""

    check: str
    group: str
    target_list: str
    target_basis: str  # 그 묶음을 그 드롭다운에 이은 근거. 파일이 적어 준 것이 아니다
    total: int  # 그 묶음의 줄 수(분모)
    present: tuple[Located, ...]
    absent: tuple[Located, ...]  # 사전에 있고 그 드롭다운에 없다
    near: tuple[NearPair, ...]


@dataclass(frozen=True, slots=True)
class UnitTextPair:
    name: str
    left_where: str
    left_unit: str | None
    right_where: str
    right_unit: str | None


@dataclass(frozen=True, slots=True)
class UnitTextPairs:
    check: str
    pairs: tuple[UnitTextPair, ...]
    differing: int  # 단위의 글자가 다른 짝의 수(값은 견주지 않는다)


@dataclass(frozen=True, slots=True)
class SheetIndexProblem:
    """`목록` 시트가 적은 탭과 실제 시트 이름."""

    check: str
    template_tabs: int  # 목록이 적은 템플릿 탭 수
    same_order: bool  # 템플릿의 앞쪽 시트 이름과 차례까지 같은가
    mismatched: tuple[Located, ...]  # 그 자리의 템플릿 시트 이름과 다른 줄
    book_tabs_not_sheets: tuple[Located, ...]  # 책 쪽 탭의 글자가 책의 시트 이름이 아닌 줄


@dataclass(frozen=True, slots=True)
class AbsentCategoryNumbers:
    check: str
    expected: tuple[int, ...]
    present: tuple[int, ...]
    absent: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class CheckSkipped:
    """검사의 재료(목록이나 시트)가 없어 재지 못했다. 0 으로 세지 않는다."""

    check: str
    reason: str


Finding = (
    ListComparison
    | DuplicateKey
    | MappingComparison
    | UnitTextPairs
    | SheetIndexProblem
    | AbsentCategoryNumbers
    | CheckSkipped
)

# ── 검사 ───────────────────────────────────────────────────────────────────


def crosscheck(
    factor_book: FactorBook, dropdowns: Dropdowns, template_sheet_names: tuple[str, ...]
) -> tuple[Finding, ...]:
    findings: list[Finding] = []
    comparisons: dict[str, ListComparison] = {}
    for check in LIST_CHECKS:
        result = _list_check(check, factor_book, dropdowns)
        findings.extend(result)
        for finding in result:
            if isinstance(finding, ListComparison):
                comparisons[finding.check] = finding
    findings.extend(_mapping_checks(dropdowns))
    findings.append(_sheet_index(factor_book, template_sheet_names))
    findings.append(_category_numbers(template_sheet_names))
    findings.append(_unit_texts(UNIT_TEXT_CHECK, factor_book, comparisons.get(UNIT_TEXT_CHECK.via)))
    return tuple(findings)


def _cell_text(cell: Cell | None) -> str | None:
    if isinstance(cell, TextCell):
        return cell.text
    if isinstance(cell, NumberCell):
        return cell.decimal
    return None


def _normalized(key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(unicodedata.normalize("NFKC", part).strip() for part in key)


def _near(template_only: list[Located], db_only: list[Located]) -> tuple[NearPair, ...]:
    return tuple(
        NearPair(template, db)
        for template in template_only
        for db in db_only
        if _normalized(template.key) == _normalized(db.key)
    )


def _list_items(name: str, dropdowns: Dropdowns) -> list[ListItem] | None:
    if name == TRAVEL_CODES:
        return [
            ListItem("배출계수_드롭다운", f"N{code.row}", code.code)
            for code in dropdowns.travel_codes
            if code.code is not None
        ] or None
    if name == C12_MINOR:
        return [
            ListItem("C12_판매제품폐기", f"AG{item.row}", item.item)
            for item in dropdowns.c12.minor
            if item.item is not None
        ] or None
    for named in dropdowns.named_lists:
        if named.name == name:
            return list(named.items)
    return None


def _list_entries(check: ListCheck, dropdowns: Dropdowns) -> list[Located] | None:
    sources: list[list[ListItem]] = []
    for name in check.lists:
        items = _list_items(name, dropdowns)
        if items is None:
            return None
        sources.append(items)
    if len(sources) == 2:
        return [
            Located((first.text, second.text), (f"{first.sheet}!{first.cell}", f"{second.sheet}!{second.cell}"))
            for first in sources[0]
            for second in sources[1]
        ]
    entries: list[Located] = []
    for item in sources[0]:
        if check.key_parts == "whole":
            key: tuple[str, ...] = (item.text,)
        elif check.key_parts == "first":
            key = (item.text.split(C12_SEPARATOR)[0],)
        else:
            key = tuple(item.text.split(C12_SEPARATOR))
        entries.append(Located(key, (f"{item.sheet}!{item.cell}",)))
    return entries


def _book_rows(book: FactorBook, sheet: str, columns: tuple[str, ...]) -> list[tuple[tuple[str, ...], str]]:
    """계수 행마다 (그 열들의 글자, `시트!첫 열 칸`). 그 열 가운데 빈 칸이 있는 줄은 열쇠가 없으므로 없다."""
    found: list[tuple[tuple[str, ...], str]] = []
    for row in book.rows:
        if row.sheet != sheet:
            continue
        cells = {entry.column: entry.cell for entry in row.labels}
        parts = [_cell_text(cells.get(column)) for column in columns]
        key = tuple(part for part in parts if part is not None)
        if len(key) == len(columns):
            found.append((key, f"{sheet}!{columns[0]}{row.row}"))
    return found


def _list_check(check: ListCheck, book: FactorBook, dropdowns: Dropdowns) -> list[Finding]:
    entries = _list_entries(check, dropdowns)
    if entries is None:
        return [CheckSkipped(check.check, "목록 쪽 재료(정의된 이름이나 시트 안 목록)가 없다")]
    if not any(account.sheet == check.book_sheet for account in book.accounts):
        return [CheckSkipped(check.check, f"책의 시트 {check.book_sheet} 가 적재되지 않았다")]
    # 책 쪽: 열쇠 → 그 열쇠의 줄 전부(덮어쓰지 않는다).
    by_key: dict[tuple[str, ...], list[str]] = {}
    for key, where in _book_rows(book, check.book_sheet, check.book_columns):
        by_key.setdefault(key, []).append(where)
    list_keys = {entry.key for entry in entries}
    matched = [entry for entry in entries if entry.key in by_key]
    template_only = [entry for entry in entries if entry.key not in by_key]
    db_only = [Located(key, tuple(where)) for key, where in by_key.items() if key not in list_keys]
    findings: list[Finding] = [
        ListComparison(
            check.check,
            len(entries),
            len(by_key),
            tuple(matched),
            tuple(template_only),
            tuple(db_only),
            _near(template_only, db_only),
        )
    ]
    if check.duplicates:
        findings.extend(DuplicateKey(check.check, key, tuple(where)) for key, where in by_key.items() if len(where) > 1)
    return findings


def _mapping_checks(dropdowns: Dropdowns) -> list[Finding]:
    findings: list[Finding] = []
    entries = dropdowns.mapping_review.entries
    groups: list[str] = []
    for entry in entries:
        if entry.group is not None and entry.group not in groups:
            groups.append(entry.group)
    for group in groups:
        rows = [entry for entry in entries if entry.group == group]
        if group not in MAPPING_TARGETS:
            findings.append(CheckSkipped("K11", f"매핑검토의 묶음 {group} 을 어느 드롭다운과 견줄지 자료에 없다"))
            continue
        for target in MAPPING_TARGETS[group]:
            items = _list_items(target, dropdowns)
            if items is None:
                findings.append(CheckSkipped("K11", f"드롭다운 {target} 이 없다"))
                continue
            texts = {item.text for item in items}
            located = [
                Located((entry.new,), (f"드롭다운_매핑검토!C{entry.row}",)) for entry in rows if entry.new is not None
            ]
            absent = [entry for entry in located if entry.key[0] not in texts]
            others = [Located((item.text,), (f"{item.sheet}!{item.cell}",)) for item in items]
            findings.append(
                MappingComparison(
                    "K11",
                    group,
                    target,
                    MAPPING_TARGETS_BASIS,
                    len(rows),
                    tuple(entry for entry in located if entry.key[0] in texts),
                    tuple(absent),
                    _near(absent, others),
                )
            )
    # (묶음, 기존값)이 겹치는 줄. 어느 줄도 고르지 않고 다 싣는다.
    seen: dict[tuple[str, str], list[str]] = {}
    for entry in entries:
        if entry.group is not None and entry.old is not None:
            seen.setdefault((entry.group, entry.old), []).append(f"드롭다운_매핑검토!B{entry.row}")
    findings.extend(DuplicateKey("K11", key, tuple(where)) for key, where in seen.items() if len(where) > 1)
    return findings


def _sheet_index(book: FactorBook, template_sheet_names: tuple[str, ...]) -> Finding:
    if not any(account.sheet == "목록" for account in book.accounts):
        return CheckSkipped("K13", "책의 목록 시트가 적재되지 않았다")
    tabs = [(link.row, _cell_text(link.template_tab)) for link in book.sheet_links if link.template_tab is not None]
    mismatched = [
        Located(("" if text is None else text,), (f"목록!B{row}",))
        for index, (row, text) in enumerate(tabs)
        if index >= len(template_sheet_names) or text != template_sheet_names[index]
    ]
    not_sheets = [
        Located(("" if (text := _cell_text(link.book_tab)) is None else text,), (f"목록!C{link.row}",))
        for link in book.sheet_links
        if link.book_tab is not None and _cell_text(link.book_tab) not in book.sheet_names
    ]
    return SheetIndexProblem("K13", len(tabs), not mismatched, tuple(mismatched), tuple(not_sheets))


def _category_numbers(template_sheet_names: tuple[str, ...]) -> Finding:
    present: set[int] = set()
    for name in template_sheet_names:
        match = _CATEGORY.match(name)
        if match is not None:
            present.add(int(match.group(1)))
    return AbsentCategoryNumbers(
        "K14",
        CATEGORY_NUMBERS,
        tuple(sorted(present)),
        tuple(number for number in CATEGORY_NUMBERS if number not in present),
    )


def _unit_texts(check: UnitTextCheck, book: FactorBook, via: ListComparison | None) -> Finding:
    if via is None:
        return CheckSkipped(check.check, f"{check.via} 가 재지지 않아 이름이 같은 짝을 모른다")
    names = [entry.key[0] for entry in via.matched]
    left = _unit_rows(book, check.left_sheet, check.left_name_column, check.left_unit_column)
    right = _unit_rows(book, check.right_sheet, check.right_name_column, check.right_unit_column)
    pairs: list[UnitTextPair] = []
    for name in names:
        # 같은 이름의 줄이 여럿이면 모든 짝을 싣는다(고르지 않는다).
        for left_where, left_unit in left.get(name, []):
            for right_where, right_unit in right.get(name, []):
                pairs.append(UnitTextPair(name, left_where, left_unit, right_where, right_unit))
    return UnitTextPairs(check.check, tuple(pairs), sum(1 for pair in pairs if pair.left_unit != pair.right_unit))


def _unit_rows(
    book: FactorBook, sheet: str, name_column: str, unit_column: str
) -> dict[str, list[tuple[str, str | None]]]:
    found: dict[str, list[tuple[str, str | None]]] = {}
    for row in book.rows:
        if row.sheet != sheet:
            continue
        cells = {entry.column: entry.cell for entry in row.labels}
        name = _cell_text(cells.get(name_column))
        if name is not None:
            found.setdefault(name, []).append((f"{sheet}!{unit_column}{row.row}", _cell_text(cells.get(unit_column))))
    return found
