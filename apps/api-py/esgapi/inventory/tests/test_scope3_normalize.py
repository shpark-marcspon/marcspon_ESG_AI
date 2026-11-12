"""품목 정규화·단위 차원·묶음. esg-lab `ts/scope3/test/normalize.test.ts` 의 여덟을 옮겼다. 순수 층."""

from esgapi.inventory.engines.scope3.llm_first_1.normalize import group_key, group_rows, normalize_item_name
from esgapi.inventory.engines.scope3.llm_first_1.types import InputRow, is_supported_category
from esgapi.inventory.engines.scope3.llm_first_1.units import activity_dim, conversion_factor, js_trim, unit_dim
from esgapi.inventory.tests.scope3_support import row, transport


def key(entry: InputRow) -> str:
    return group_key(entry.item_name, entry.unit, entry.transport)


def test_spacing_case_fullwidth_and_brackets_are_erased() -> None:
    variants = ["A4 용지 80g", "a4용지 80G", "A4용지(80g)", "Ａ４ 용지  80ｇ", " A4-용지_80g "]
    assert {normalize_item_name(name) for name in variants} == {"a4용지80g"}


def test_different_spec_numbers_are_different_keys() -> None:
    assert normalize_item_name("A4 용지 80g") != normalize_item_name("A4 용지 70g")
    assert normalize_item_name("볼트 M8x1.25") == "볼트m8x1.25"
    assert normalize_item_name("볼트 M8×1.25") == normalize_item_name("볼트 m8*1.25")
    assert normalize_item_name("볼트 M8x1.25") != normalize_item_name("볼트 M8x125")


def test_punctuation_dots_go_and_decimal_points_stay() -> None:
    assert normalize_item_name("황산 98%.") == "황산98"
    assert normalize_item_name("필름 0.5T") == "필름0.5t"
    # JS 의 `\d` 는 ASCII 숫자뿐이다: 아랍 숫자 사이의 점은 소수점으로 치지 않는다.
    assert normalize_item_name("필름 ٠.٥") == "필름٠٥"
    assert normalize_item_name("_a_b_") == "ab"


def test_unit_text_becomes_a_dimension_and_unknown_units_are_unknown() -> None:
    assert unit_dim("KG") == "kg"
    assert unit_dim("톤") == "tonne"
    assert unit_dim("tonnes") == "tonne"
    assert unit_dim("인km") == "passenger_km"
    assert unit_dim("Room per night") == "room_night"
    assert unit_dim("대") == "unknown"
    assert unit_dim(None) == "unknown"
    assert unit_dim(" ㎥ ") == "m3"
    assert unit_dim("﻿kg　") == "kg"


def test_js_trim_strips_the_js_set_not_the_python_set() -> None:
    assert js_trim("﻿ x  ") == "x"
    # 파이썬의 str.strip() 은 U+001F 와 U+0085 를 떼지만 JS 의 trim 은 떼지 않는다.
    assert js_trim("\x1fx\x85") == "\x1fx\x85"


def test_conversion_is_only_the_exact_kg_tonne_pair() -> None:
    assert conversion_factor("kg", "kg") == "1"
    assert conversion_factor("kg", "tonne") == "0.001"
    assert conversion_factor("tonne", "kg") == "1000"
    assert conversion_factor("ea", "kg") is None
    assert conversion_factor("unknown", "unknown") is None
    assert activity_dim("kg", transport(weight_kg="1")) == "tonne_km"
    assert activity_dim("kg", transport(weight_kg=None)) == "kg"


def test_bool_is_not_a_category() -> None:
    assert is_supported_category(1)
    assert not is_supported_category(True)
    assert not is_supported_category(3)
    assert not is_supported_category("1")
    assert not is_supported_category(1.0)


def test_same_item_and_dimension_group_together_in_input_order() -> None:
    rows = [
        row("A4 용지 80g", row_id="a"),
        row("폴리프로필렌 수지", row_id="b"),
        row("a4용지 80G", row_id="c"),
        row("A4용지(80g)", row_id="d", unit="KG"),
    ]
    assert [[entry.row_id for entry in group.rows] for group in group_rows(rows)] == [["a", "c", "d"], ["b"]]


def test_different_dimension_is_a_different_group() -> None:
    assert key(row("A4 용지", unit="kg")) != key(row("A4 용지", unit="box"))
    assert key(row("A4 용지", unit="t")) == key(row("A4 용지", unit="톤"))
    assert key(row("A4 용지", unit="box")) != key(row("A4 용지", unit="대"))
    assert key(row("A4 용지", unit="kg")) == "a4용지|kg|"
    assert key(row("A4 용지", unit=None)) == "a4용지|?|"


def test_transport_rows_split_by_mode() -> None:
    def moved(mode: str, distance_km: str | None = "300") -> InputRow:
        info = transport(origin="부산", destination="평택", mode=mode, weight_kg="1000", distance_km=distance_km)
        return row("원자재 운송", unit=None, transport=info)

    truck = moved("트럭")
    rail = moved("철도")
    assert key(truck) != key(rail)
    loose = moved(" 트럭 ", None)
    assert key(truck) == key(loose) == "원자재운송|tonne_km|트럭"


def test_names_with_no_letters_left_do_not_group() -> None:
    groups = group_rows([row("---", row_id="a"), row("---", row_id="b"), row("***", row_id="c")])
    assert [group.key for group in groups] == ["|kg|#a", "|kg|#b", "xxx|kg|"]
