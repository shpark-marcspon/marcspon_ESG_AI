"""드롭다운과 계수 책의 어긋남 검사(`tools/scope3_sheets/crosscheck.py`). 순수 층. 표본은 지은 것이다.

표본은 발주서(밴드 S3a) §3 의 대조표와 같은 수의 어긋남을 심어 지었다.
「원본에서 그 수가 나온다」는 여기서 재지지 않는다.
"""

from dataclasses import fields

import pytest

from esgapi.inventory.tests.s3sheets_support import sample_factor_book, sample_template, text, with_cell
from esgapi.inventory.tools.scope3_sheets import crosscheck as module
from esgapi.inventory.tools.scope3_sheets.crosscheck import (
    AbsentCategoryNumbers,
    CheckSkipped,
    DuplicateKey,
    Finding,
    ListComparison,
    Located,
    MappingComparison,
    NearPair,
    SheetIndexProblem,
    UnitTextPair,
    UnitTextPairs,
    crosscheck,
)
from esgapi.inventory.tools.scope3_sheets.dropdowns import DROPDOWN_SHEET, MAPPING_SHEET, read_dropdowns
from esgapi.inventory.tools.scope3_sheets.factors import load_factor_book
from esgapi.inventory.tools.scope3_sheets.grid import Workbook


def run(book: Workbook | None = None, template: Workbook | None = None) -> tuple[Finding, ...]:
    drops = read_dropdowns(template if template is not None else sample_template())
    factors = load_factor_book(book if book is not None else sample_factor_book())
    return crosscheck(factors, drops, drops.sheet_names)


def comparison(findings: tuple[Finding, ...], check: str) -> ListComparison:
    return next(f for f in findings if isinstance(f, ListComparison) and f.check == check)


def counts(found: ListComparison) -> tuple[int, int, int, int, int]:
    return (found.list_total, len(found.matched), len(found.template_only), len(found.db_only), len(found.near))


# 검사 → (목록 쪽 수(분모), 같음, 목록에만, 책에만, near). 발주서 §3 의 대조표의 수.
EXPECTED = {
    "K1": (17, 14, 3, 3, 0),
    "K2": (14, 13, 1, 1, 0),
    "K3": (14, 6, 8, 6, 0),
    "K4a": (5, 4, 1, 1, 0),
    "K4b": (5, 4, 1, 0, 0),
    "K5": (7, 6, 1, 0, 0),
    "K6": (27, 17, 10, 0, 0),
    "K7": (33, 11, 22, 0, 0),
    "K8": (14, 11, 3, 0, 0),
    "K9": (64, 63, 1, 0, 0),
    "K10a": (71, 70, 1, 0, 0),
    "K10b": (71, 70, 1, 0, 0),
}


@pytest.mark.parametrize("check", list(EXPECTED))
def test_each_list_check_finds_the_planted_differences(check: str) -> None:
    found = comparison(run(), check)
    assert counts(found) == EXPECTED[check]
    assert len(found.matched) + len(found.template_only) == found.list_total  # 분모


def test_every_check_in_the_table_ran_and_none_was_skipped() -> None:
    findings = run()
    assert [f for f in findings if isinstance(f, CheckSkipped)] == []
    ran = {f.check for f in findings if not isinstance(f, CheckSkipped)}
    assert ran == {*EXPECTED, "K11", "K13", "K14", "K15"}
    assert [check.check for check in module.LIST_CHECKS] == list(EXPECTED)
    assert all(check.basis for check in module.LIST_CHECKS)


def test_the_places_of_a_difference_are_cells() -> None:
    found = comparison(run(), "K5")
    assert found.template_only == (Located(("가상운송수단07",), (f"{DROPDOWN_SHEET}!D9",)),)
    assert found.matched[0] == Located(("가상운송수단01",), (f"{DROPDOWN_SHEET}!D3",))
    k1 = comparison(run(), "K1")
    assert [item.key for item in k1.db_only] == [("가상책품목군01",), ("가상책품목군02",), ("가상책품목군03",)]
    assert len(k1.db_only[0].where) == 11 and k1.db_only[0].where[0] == "구매_USEPA!A18"  # 그 품목군의 줄 전부
    assert k1.db_distinct == 17


def test_the_direction_is_not_flipped() -> None:
    """목록에만 있는 것은 template_only, 책에만 있는 것은 db_only. 자리의 시트 이름으로 본다."""
    for check in ("K1", "K2", "K3", "K4a"):
        found = comparison(run(), check)
        assert found.template_only and found.db_only
        assert all(where.startswith(f"{DROPDOWN_SHEET}!") for item in found.template_only for where in item.where)
        assert all(not where.startswith(f"{DROPDOWN_SHEET}!") for item in found.db_only for where in item.where)
    assert [item.key for item in comparison(run(), "K2").db_only] == [("가상에너지책01",)]
    assert [item.key for item in comparison(run(), "K2").template_only] == [("가상에너지14",)]


def test_a_trailing_space_is_not_a_match_and_is_counted_as_near() -> None:
    """글자까지 같아야 맞는다. 끝 공백 하나만 다른 짝은 「없음」이고, 다듬으면 맞는다는 것만 near 로 따로 센다."""
    template = with_cell(sample_template(), DROPDOWN_SHEET, "D3", text("가상운송수단01 "))
    found = comparison(run(template=template), "K5")
    assert counts(found) == (7, 5, 2, 1, 1)
    assert found.near == (
        NearPair(Located(("가상운송수단01 ",), (f"{DROPDOWN_SHEET}!D3",)), Located(("가상운송수단01",), ("운송!C3",))),
    )
    # 책 쪽에 공백이 있어도 같다. 전각 글자(NFKC)도 near 다.
    book = with_cell(sample_factor_book(), "운송", "C4", text(" 가상운송수단０２"))
    found = comparison(run(book=book), "K5")
    assert counts(found) == (7, 5, 2, 1, 1)
    assert found.near[0].db == Located((" 가상운송수단０２",), ("운송!C4",))


def test_both_rows_of_a_repeated_pair_are_reported() -> None:
    """K9: 같은 (종류, 처리방법)이 두 줄인 짝 둘. 줄을 다 싣는다(어느 줄도 고르지 않는다)."""
    duplicates = [f for f in run() if isinstance(f, DuplicateKey) and f.check == "K9"]
    assert [duplicate.where for duplicate in duplicates] == [
        ("폐기물_C5!A10", "폐기물_C5!A11"),
        ("폐기물_C5!A31", "폐기물_C5!A32"),
    ]
    found = comparison(run(), "K9")
    assert found.db_distinct == 63
    assert found.template_only == (
        Located(("가상폐기물종류16", "가상처리방법04"), (f"{DROPDOWN_SHEET}!H18", f"{DROPDOWN_SHEET}!I6")),
    )


def test_the_c12_list_is_compared_by_code_and_by_code_and_name() -> None:
    findings = run()
    assert comparison(findings, "K10a").template_only == (Located(("가상고르지않음",), ("C12_판매제품폐기!AG2",)),)
    # 이름 하나가 다르면 코드는 그대로 70, (코드, 이름)은 69.
    book = with_cell(sample_factor_book(), "폐기물_C12", "D5", text("가상 다른 이름"))
    changed = run(book=book)
    assert counts(comparison(changed, "K10a")) == (71, 70, 1, 0, 0)
    assert counts(comparison(changed, "K10b")) == (71, 69, 2, 1, 0)


def test_the_mapping_review_is_compared_group_by_group() -> None:
    found = [f for f in run() if isinstance(f, MappingComparison)]
    others = [f for f in found if f.group != "unit"]
    assert sum(f.total for f in others) == 104  # 분모
    assert {f.group: len(f.absent) for f in others if f.absent} == {"energy": 1, "transport_spend": 9}
    assert sum(len(f.absent) for f in others) == 10
    assert all(len(f.present) + len(f.absent) == f.total for f in found)
    spend = next(f for f in others if f.group == "transport_spend")
    assert spend.absent[0].where == (f"{MAPPING_SHEET}!C79",)
    assert [f for f in run() if isinstance(f, DuplicateKey) and f.check == "K11"] == []


def test_the_unit_group_is_compared_with_each_unit_list_separately() -> None:
    """어느 단위 목록이 상대인지는 파일이 정하지 않는다. 셋과 따로 견준 수 셋을 낸다(합치지 않는다)."""
    units = [f for f in run() if isinstance(f, MappingComparison) and f.group == "unit"]
    assert [(f.target_list, f.total, len(f.absent)) for f in units] == [
        ("DD_ENERGY_UNIT", 16, 3),
        ("DD_WASTE_UNIT", 16, 12),
        ("DD_TRANSPORT_WEIGHT_UNIT", 16, 12),
    ]


def test_the_mapping_review_is_compared_to_the_letter_and_says_who_made_the_pairing() -> None:
    """K11 도 글자까지 같아야 맞는다(사전 쪽이든 드롭다운 쪽이든 끝 공백 하나면 「없음」이고 near 로만 센다)."""
    assert all("사람이 이은 것" in f.target_basis for f in run() if isinstance(f, MappingComparison))
    spaced_word = with_cell(sample_template(), MAPPING_SHEET, "C15", text("가상품목군01 "))
    found = next(
        f for f in run(template=spaced_word) if isinstance(f, MappingComparison) and f.group == "purchase_group"
    )
    assert (len(found.absent), len(found.near)) == (1, 1)
    assert found.absent[0] == Located(("가상품목군01 ",), (f"{MAPPING_SHEET}!C15",))
    spaced_list = with_cell(sample_template(), DROPDOWN_SHEET, "A3", text("가상품목군01 "))
    found = next(
        f for f in run(template=spaced_list) if isinstance(f, MappingComparison) and f.group == "purchase_group"
    )
    assert (len(found.absent), len(found.near)) == (1, 1)
    assert found.absent[0].where == (f"{MAPPING_SHEET}!C15",)


def test_a_repeated_group_and_old_value_in_the_mapping_review_is_reported_with_both_rows() -> None:
    template = with_cell(sample_template(), MAPPING_SHEET, "B16", text("가상옛값15"))
    duplicates = [f for f in run(template=template) if isinstance(f, DuplicateKey) and f.check == "K11"]
    assert duplicates == [
        DuplicateKey("K11", ("purchase_group", "가상옛값15"), (f"{MAPPING_SHEET}!B15", f"{MAPPING_SHEET}!B16"))
    ]


def test_a_group_the_data_does_not_know_is_skipped_not_guessed() -> None:
    template = with_cell(sample_template(), MAPPING_SHEET, "A15", text("가상묶음"))
    skipped = [f for f in run(template=template) if isinstance(f, CheckSkipped)]
    assert [f.check for f in skipped] == ["K11"]


def test_the_sheet_index_is_compared_with_the_template_sheet_names() -> None:
    index = next(f for f in run() if isinstance(f, SheetIndexProblem))
    assert (index.template_tabs, index.same_order, index.mismatched) == (21, True, ())
    assert [item.where for item in index.book_tabs_not_sheets] == [("목록!C26",)]
    swapped = with_cell(sample_factor_book(), "목록", "B7", text("C3_연료에너지"))
    index = next(f for f in run(book=swapped) if isinstance(f, SheetIndexProblem))
    assert (index.same_order, [item.where for item in index.mismatched]) == (False, [("목록!B7",)])


def test_the_absent_category_number_is_ten() -> None:
    absent = next(f for f in run() if isinstance(f, AbsentCategoryNumbers))
    assert absent.expected == tuple(range(1, 16))
    assert absent.absent == (10,)
    assert len(absent.present) == 14


def test_unit_texts_of_same_named_rows_are_laid_side_by_side_and_only_counted() -> None:
    """K15: K3 에서 이름이 같았던 짝 여섯의 단위 원문 둘을 나란히. 글자가 다른 짝 둘. 값은 견주지 않는다."""
    pairs = next(f for f in run() if isinstance(f, UnitTextPairs))
    assert (len(pairs.pairs), pairs.differing) == (6, 2)
    assert [pair for pair in pairs.pairs if pair.left_unit != pair.right_unit] == [
        UnitTextPair("가상에너지01", "에너지!D5", "L", "에너지_C3!C4", "kg"),
        UnitTextPair("가상에너지02", "에너지!D6", "L", "에너지_C3!C5", "kg"),
    ]


def test_a_check_whose_material_is_missing_is_skipped_not_counted_as_zero() -> None:
    broken_book = with_cell(sample_factor_book(), "운송", "A2", text("가상 머리글"))
    skipped = [f for f in run(book=broken_book) if isinstance(f, CheckSkipped)]
    assert [f.check for f in skipped] == ["K5"]
    broken_template = with_cell(sample_template(), DROPDOWN_SHEET, "N2", text("가상 머리글"))
    skipped = [f for f in run(template=broken_template) if isinstance(f, CheckSkipped)]
    assert [f.check for f in skipped] == ["K7"]


def test_no_finding_has_a_field_that_says_which_side_is_right() -> None:
    """결과의 꼴에 「옳은 쪽」·「고칠 값」·「권고」 칸이 없다. 갈래마다 필드 이름을 못 박는다."""
    names = {
        ListComparison: ["check", "list_total", "db_distinct", "matched", "template_only", "db_only", "near"],
        DuplicateKey: ["check", "key", "where"],
        MappingComparison: ["check", "group", "target_list", "target_basis", "total", "present", "absent", "near"],
        UnitTextPairs: ["check", "pairs", "differing"],
        UnitTextPair: ["name", "left_where", "left_unit", "right_where", "right_unit"],
        SheetIndexProblem: ["check", "template_tabs", "same_order", "mismatched", "book_tabs_not_sheets"],
        AbsentCategoryNumbers: ["check", "expected", "present", "absent"],
        CheckSkipped: ["check", "reason"],
        Located: ["key", "where"],
        NearPair: ["template", "db"],
    }
    for kind, expected in names.items():
        assert [f.name for f in fields(kind)] == expected, kind.__name__
    forbidden = ("canonical", "correct", "preferred", "recommend", "fix", "chosen", "default", "winner", "truth")
    every = [name for expected in names.values() for name in expected]
    assert [name for name in every if any(word in name for word in forbidden)] == []
