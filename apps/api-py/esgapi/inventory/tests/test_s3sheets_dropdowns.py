"""템플릿의 드롭다운 정의 읽기(`tools/scope3_sheets/dropdowns.py`). 순수 층. 표본은 지은 것이다."""

from dataclasses import replace

from esgapi.inventory.tests.s3sheets_support import (
    MAPPING_GROUPS,
    NAMED_LISTS,
    sample_template,
    sheet_named,
    text,
    with_cell,
    with_sheet,
)
from esgapi.inventory.tools.scope3_sheets.dropdowns import (
    C12_OFFSET_FORMULAS,
    C12_SHEET,
    DROPDOWN_SHEET,
    MAPPING_SHEET,
    DropdownProblem,
    c12_lists,
    mapping_review,
    named_lists,
    read_dropdowns,
    travel_codes,
    validation_shape,
    validations_of,
)
from esgapi.inventory.tools.scope3_sheets.grid import DefinedName, NumberCell, Validation, Workbook


def kinds(problems: tuple[DropdownProblem, ...]) -> list[tuple[str, str]]:
    return [(problem.kind, problem.where) for problem in problems]


def test_the_eleven_named_lists_have_the_lengths_of_the_sample() -> None:
    lists, problems = named_lists(sample_template())
    assert problems == ()
    assert {named.name: len(named.items) for named in lists} == {
        "DD_PURCHASE_GROUP": 17,
        "DD_ENERGY": 14,
        "DD_ENERGY_UNIT": 5,
        "DD_TRANSPORT_DISTANCE": 7,
        "DD_TRANSPORT_SPEND": 27,
        "DD_TRAVEL_DISTANCE": 33,
        "DD_TRAVEL_SPEND": 14,
        "DD_WASTE_C5_TYPE": 16,
        "DD_WASTE_METHOD": 4,
        "DD_WASTE_UNIT": 2,
        "DD_TRANSPORT_WEIGHT_UNIT": 2,
    }
    assert {named.name: len(named.items) for named in lists} == {name: n for name, (_, n) in NAMED_LISTS.items()}
    energy = next(named for named in lists if named.name == "DD_ENERGY")
    assert (energy.refers_to, energy.items[0].cell, energy.items[-1].cell) == (
        f"{DROPDOWN_SHEET}!$B$3:$B$16",
        "B3",
        "B16",
    )
    assert energy.items[0].text == "가상에너지01"


def test_list_items_are_not_trimmed_and_a_number_item_is_its_decimal() -> None:
    workbook = with_cell(sample_template(), DROPDOWN_SHEET, "B3", text(" 가상에너지01 "))
    workbook = with_cell(workbook, DROPDOWN_SHEET, "B4", NumberCell("9.50", "9.5"))  # 파일 속 글자가 아니라 십진 표기
    lists, problems = named_lists(workbook)
    energy = next(named for named in lists if named.name == "DD_ENERGY")
    assert problems == ()
    assert [item.text for item in energy.items[:2]] == [" 가상에너지01 ", "9.5"]


def test_an_empty_cell_inside_a_named_range_is_a_problem_not_an_item() -> None:
    workbook = with_cell(sample_template(), DROPDOWN_SHEET, "I4", None)
    lists, problems = named_lists(workbook)
    assert kinds(problems) == [("empty_list_cell", f"{DROPDOWN_SHEET}!I4")]
    assert len(next(named for named in lists if named.name == "DD_WASTE_METHOD").items) == 3


def test_a_name_that_is_not_a_sheet_range_or_points_nowhere_is_a_problem() -> None:
    template = sample_template()
    names = (
        DefinedName("가상_이름1", "#REF!"),
        DefinedName("가상_이름2", "없는시트!$A$1:$A$3"),
        DefinedName("가상_이름3", f"{DROPDOWN_SHEET}!$A$1:$XFD$1048576"),
        *template.defined_names,
    )
    lists, problems = named_lists(replace(template, defined_names=names))
    assert kinds(problems) == [
        ("bad_name_range", "가상_이름1"),
        ("missing_sheet", "가상_이름2"),
        ("bad_name_range", "가상_이름3"),
    ]
    assert len(lists) == 11


def test_validation_formulas_are_sorted_by_shape_without_evaluating_them() -> None:
    drops = read_dropdowns(sample_template())
    assert len(drops.validations) == 39
    counts: dict[str, int] = {}
    for validation in drops.validations:
        counts[validation.shape] = counts.get(validation.shape, 0) + 1
    assert counts == {"defined_name": 32, "range": 1, "offset": 2, "quoted_list": 1, "number_range": 3}
    assert validation_shape("list", "DD_ENERGY") == "defined_name"
    assert validation_shape("list", "$AA$2:$AA$6") == "range"
    assert validation_shape("list", "AA2") == "range"  # 칸 하나는 이름이 아니라 범위다
    assert validation_shape("list", '"g,kg,ton"') == "quoted_list"
    assert validation_shape("list", C12_OFFSET_FORMULAS[0]) == "offset"
    assert validation_shape("decimal", "0") == "number_range"
    assert validation_shape("whole", "0") == "number_range"
    assert validation_shape("list", "INDIRECT(A1)") == "other"
    assert validation_shape("list", None) == "other"
    assert validation_shape("", "DD_ENERGY") == "other"
    c12 = validations_of(sheet_named(sample_template(), C12_SHEET))
    assert [validation.shape for validation in c12] == ["number_range", "range", "offset", "offset", "quoted_list"]
    assert c12[0].formula2 == "100"


def test_a_validation_pointing_at_a_name_that_is_not_defined_is_a_problem() -> None:
    template = sample_template()
    sheet = sheet_named(template, "C1_구매품서비스")
    changed = replace(sheet, validations=(Validation("list", "D21:D220", "DD_NO_SUCH_LIST", None),))
    drops = read_dropdowns(with_sheet(template, changed))
    assert kinds(drops.problems) == [("unknown_list_name", "C1_구매품서비스!D21:D220")]


def test_the_travel_code_table_is_thirty_three_rows_of_four_columns() -> None:
    codes, problems = travel_codes(sample_template())
    assert problems == ()
    assert [code.row for code in codes] == list(range(3, 36))
    assert (codes[0].display, codes[0].code, codes[0].defra_type, codes[0].keywords) == (
        "가상교통수단01",
        "가상코드01",
        "가상유형01",
        "가상키워드01",
    )
    changed, problems = travel_codes(with_cell(sample_template(), DROPDOWN_SHEET, "N2", text("가상 머리글")))
    assert (changed, kinds(problems)) == ((), [("header_mismatch", f"{DROPDOWN_SHEET}!N2")])


def test_the_c12_lists_are_read_from_their_columns() -> None:
    lists, problems = c12_lists(sample_template())
    assert problems == ()
    assert (len(lists.major), len(lists.middle), len(lists.minor)) == (5, 29, 71)
    assert [item.row for item in lists.middle] == [row for row in range(2, 32) if row != 19]
    assert [item.row for item in lists.minor] == [row for row in range(2, 74) if row != 19]
    assert (lists.minor[0].item, lists.minor[1].item) == ("가상고르지않음", "가상소분류-01 | 가상폐기물명01")
    assert lists.major[0].cell == "AA2"


def test_an_offset_formula_that_differs_from_the_layout_is_a_problem_and_is_not_evaluated() -> None:
    template = sample_template()
    sheet = sheet_named(template, C12_SHEET)
    changed_formula = C12_OFFSET_FORMULAS[1].replace("$AF$73", "$AF$74")
    validations = tuple(
        replace(v, formula1=changed_formula) if v.formula1 == C12_OFFSET_FORMULAS[1] else v for v in sheet.validations
    )
    lists, problems = c12_lists(with_sheet(template, replace(sheet, validations=validations)))
    assert kinds(problems) == [("offset_formula_mismatch", C12_SHEET)]
    assert len(lists.minor) == 71  # 목록은 식을 셈해서가 아니라 열에서 읽는다
    assert c12_lists(sample_template())[1] == ()


def test_the_mapping_review_is_nine_summary_rows_and_a_hundred_and_twenty_entries() -> None:
    review, problems = mapping_review(sample_template())
    assert problems == ()
    assert [row.row for row in review.summary] == list(range(2, 11))
    assert all(len(row.cells) == 5 for row in review.summary)
    assert [entry.row for entry in review.entries] == list(range(15, 135))
    counts: dict[str, int] = {}
    for entry in review.entries:
        assert entry.group is not None
        counts[entry.group] = counts.get(entry.group, 0) + 1
    assert counts == dict(MAPPING_GROUPS)
    assert sum(counts.values()) == 120
    assert (review.entries[0].old, review.entries[0].new) == ("가상옛값15", "가상품목군01")
    assert len({(entry.group, entry.old) for entry in review.entries}) == 120  # (묶음, 기존값)의 겹침 0


def test_missing_sheets_and_changed_headers_are_problems_not_exceptions() -> None:
    template = sample_template()
    kept = tuple(s for s in template.sheets if s.name not in (C12_SHEET, MAPPING_SHEET))
    without = Workbook(kept, template.defined_names)
    drops = read_dropdowns(without)
    assert kinds(drops.problems) == [("missing_sheet", C12_SHEET), ("missing_sheet", MAPPING_SHEET)]
    assert (len(drops.named_lists), drops.mapping_review.entries, drops.c12.minor) == (11, (), ())
    assert len(drops.travel_codes) == 33
    changed = with_cell(with_cell(template, MAPPING_SHEET, "C14", text("가상 머리글")), C12_SHEET, "AG1", None)
    assert kinds(read_dropdowns(changed).problems) == [
        ("header_mismatch", f"{C12_SHEET}!AG1"),
        ("header_mismatch", f"{MAPPING_SHEET}!C14"),
    ]


def test_the_whole_sample_reads_without_problems() -> None:
    drops = read_dropdowns(sample_template())
    assert drops.problems == ()
    assert len(drops.sheet_names) == 23
    assert drops.sheet_names[-2:] == (DROPDOWN_SHEET, MAPPING_SHEET)
