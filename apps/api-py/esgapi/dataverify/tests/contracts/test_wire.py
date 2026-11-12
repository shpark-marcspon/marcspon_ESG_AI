"""contracts/wire.to_check: 도구 출력 → 검사 기록 Check 가 꼴을 지나고, 수가 repr 왕복하고, N/A·error·FAIL·계산 불가가
서로 다른 칸·갈래로 남는가(발주서 §3 S7). 도구 출력은 엔진의 분배기로 지어낸 항목 열둘에서 실제로 낸 것이다.
"""

import math
from typing import Any

import pytest

from esgapi.dataverify.contracts import wire
from esgapi.dataverify.contracts.shapes import CHECK
from esgapi.dataverify.engines.colab_156.dispatch import _run_local_tool
from esgapi.dataverify.engines.colab_156.tools import ValueCache
from esgapi.dataverify.tests.engines.colab_156.support import (
    ENERGY,
    LANDFILL,
    RATIO,
    RECYCLED,
    RENEW,
    S1,
    S2,
    TOTAL,
    WASTE,
    data,
)

TOLERANCE = 0.0  # 흐름이 넘기는 실행 값(prompts.TOLERANCE — 밴드 DV16)


def call(name: str, args: Any) -> tuple[dict[str, Any], Any]:
    output = _run_local_tool(name, args, data=data(), tolerance=TOLERANCE, cache=ValueCache())
    record = wire.to_check(1, name, args, output, tolerance=TOLERANCE)
    CHECK.validate_python(record, strict=True)
    return output, record


def quad(q: tuple[str, ...]) -> list[str]:
    return list(q)


def value_args(q: tuple[str, ...], year: Any) -> dict[str, Any]:
    return {"대분류": q[0], "중분류": q[1], "소분류": q[2], "단위": q[3], "year": year}


CALLS: list[tuple[str, Any]] = [
    ("value_of_by_name", value_args(S1, "2022")),
    ("value_of_by_name", value_args(S2, "2024")),
    ("value_of_by_name", value_args(RECYCLED, "2024")),
    ("value_of_by_name", {"대분류": S1[0], "year": 2022}),
    ("sum_check", {"a": 1200, "b": 300, "c": 1500}),
    ("sum_check", {"a": 1200, "b": 300, "c": 1505, "tolerance": 2}),
    ("sum_check", {"a": "N/A", "b": 300, "c": 1500}),
    ("sum_n_check", {"addends": [1, "N/A"], "target": 3}),
    ("sum_n_check", {"addends": [1, 2], "target": 3, "tolerance": 0}),
    ("ratio_check", {"d": 25, "e": 0, "f": 0.25}),
    ("ratio_check", {"d": 1, "e": 100, "f": 1.0}),
    ("sum_check_by_name", {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022", "2023"]}),
    ("sum_check_by_name", {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022", "2024"]}),
    (
        "sum_n_check_by_names",
        {"addends": [quad(RECYCLED), quad(LANDFILL)], "target": quad(WASTE), "years": ["2022", "2023", "2024"]},
    ),
    (
        "ratio_check_by_name",
        {"numerator": quad(RENEW), "denominator": quad(ENERGY), "expected": quad(RATIO), "years": ["2022", "2023"]},
    ),
    ("search_items", {"대분류": "폐기물", "limit": 2}),
    ("search_items", {}),
    ("value_of", {"대분류": "가"}),
    ("sum_check", {"a": 1, "b": 2, "c": 3, "tolerance": "1.1"}),
]


@pytest.mark.parametrize(("name", "args"), CALLS)
def test_every_tool_output_becomes_a_check_that_fits_the_shape(name: str, args: Any) -> None:
    _, record = call(name, args)
    assert record["seq"] == 1
    assert record["tool"] == name
    assert not str(record.get("message", "")).startswith("shape mismatch")


def test_a_value_is_a_repr_that_round_trips() -> None:
    output, record = call("value_of_by_name", value_args(S1, "2023"))
    assert (record["kind"], record["value"], record["na"]) == ("value", "1250.0", False)
    assert float(record["value"]) == output["value"]
    assert record["item"] == quad(S1)
    assert record["year"] == "2023"


def test_n_a_is_null_with_na_true() -> None:
    _, record = call("value_of_by_name", value_args(S2, "2024"))
    assert (record["value"], record["na"]) == (None, True)
    _, record = call("value_of_by_name", {"대분류": S1[0], "year": 2022})
    assert record["item"] == [S1[0], None, None, None]
    assert record["year"] == 2022  # 받은 그대로(글자로 바꾸지 않는다)


def test_nan_is_kept_as_a_string() -> None:
    _, record = call("value_of_by_name", value_args(RECYCLED, "2024"))
    assert record["value"] == "nan"
    assert math.isnan(float(record["value"]))


def test_a_check_keeps_ok_fail_and_not_computable_apart() -> None:
    _, ok = call("sum_check", {"a": 1200, "b": 300, "c": 1500})
    assert ok["kind"] == "check"
    assert ok["rule"] == "sum"
    assert ok["items"] == {"byName": None, "raw": {"a": 1200, "b": 300, "c": 1500}}
    assert ok["tolerance"] == "0.0"
    assert ok["years"] == [
        {
            "year": None,
            "ok": True,
            "status": "OK",
            "diff": "0.0",
            "note": None,
            "explanation": "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0).",
        }
    ]
    output, fail = call("sum_check", {"a": 1200, "b": 300, "c": 1505, "tolerance": 2})
    assert fail["tolerance"] == "0.0"  # 모델이 준 2 는 싣지 않는다(DV16)
    assert (fail["years"][0]["status"], fail["years"][0]["diff"]) == ("FAIL", "-5.0")
    assert float(fail["years"][0]["diff"]) == output["diff"]
    _, skip = call("sum_n_check", {"addends": [1, "N/A"], "target": 3})
    assert skip["years"][0] | {"explanation": ""} == {
        "year": None,
        "ok": False,
        "status": "FAIL",
        "diff": None,
        "note": "non-numeric",
        "explanation": "",
    }
    _, zero = call("ratio_check", {"d": 25, "e": 0, "f": 0.25})
    assert (zero["rule"], zero["years"][0]["note"]) == ("ratio", "division by zero")


def test_weakness_1_is_an_error_record_not_a_fail() -> None:
    _, record = call("sum_check", {"a": "N/A", "b": 300, "c": 1500})
    assert record == {
        "seq": 1,
        "tool": "sum_check",
        "kind": "error",
        "message": "runtime error in sum_check: name 'e' is not defined",
        "args": {"a": "N/A", "b": 300, "c": 1500},
    }


def test_a_by_name_check_has_a_year_each() -> None:
    args = {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022", "2023"]}
    output, record = call("sum_check_by_name", args)
    assert record["items"] == {"byName": {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2)}, "raw": None}
    assert [row["year"] for row in record["years"]] == ["2022", "2023"]
    for row, out in zip(record["years"], output["results"], strict=True):
        assert row["status"] == out["status"]
        assert float(row["diff"]) == out["diff"]
    args = {"addends": [quad(RECYCLED), quad(LANDFILL)], "target": quad(WASTE), "years": ["2022"]}
    _, record = call("sum_n_check_by_names", args)
    assert record["items"]["byName"] == {"addends": [quad(RECYCLED), quad(LANDFILL)], "target": quad(WASTE)}


def test_search_and_unknown_tool() -> None:
    _, record = call("search_items", {"대분류": "폐기물", "limit": 2})
    assert record == {
        "seq": 1,
        "tool": "search_items",
        "kind": "search",
        "filter": {"대분류": "폐기물"},
        "total": 3,
        "limit": 2,
        "offset": 0,
        "returned": 2,
    }
    _, record = call("value_of", {"대분류": "가"})
    assert record["kind"] == "error"
    assert record["message"] == "unknown tool: value_of"


def test_a_non_number_model_tolerance_is_ignored() -> None:
    _, record = call("sum_n_check", {"addends": ["N/A"], "target": 3, "tolerance": "넉넉히"})
    assert record["tolerance"] == "0.0"
    assert record["years"][0]["note"] == "non-numeric"


def test_what_the_model_gave_is_echoed_as_is_and_the_tool_result_kept() -> None:
    """모델 인자를 비추는 칸은 받은 그대로라 도구가 낸 결과가 error 로 바뀌지 않는다(가지 리뷰 중요 1)."""
    _, record = call("value_of_by_name", value_args(S1, 2023.0))
    assert (record["kind"], record["year"], record["value"], record["na"]) == ("value", 2023.0, None, True)
    _, record = call("value_of_by_name", {"대분류": 5, "중분류": True, "소분류": None, "단위": "t", "year": "2022"})
    assert (record["kind"], record["item"]) == ("value", [5, True, None, "t"])
    _, record = call("search_items", {"대분류": 5})
    assert (record["kind"], record["filter"], record["total"]) == ("search", {"대분류": 5}, 0)
    _, record = call("search_items", {"limit": -1, "offset": True})
    assert (record["kind"], record["limit"], record["offset"]) == ("search", -1, True)
    args = {"numerator": quad(RENEW), "denominator": quad(ENERGY), "expected": [1, 2, 3, 4], "years": ["2022"]}
    _, record = call("ratio_check_by_name", args)
    assert record["kind"] == "check"  # 기대값 네 칸이 수라 N/A → 도구는 non-numeric 을 냈다
    assert record["items"]["byName"] == {
        "numerator": quad(RENEW),
        "denominator": quad(ENERGY),
        "expected": [1, 2, 3, 4],
    }
    assert record["years"][0]["note"] == "non-numeric"
    args = {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": [2022.0, None]}
    _, record = call("sum_check_by_name", args)
    assert record["kind"] == "error"  # 2022.0 → str 「2022.0」 열쇠라 N/A → 약점 1 의 NameError(도구가 낸 오류)
    assert record["message"] == "runtime error in sum_check_by_name: name 'e' is not defined"


def test_args_that_are_not_an_object_are_kept_as_they_are() -> None:
    output, record = call("sum_check", [1, 2])
    assert record == {"seq": 1, "tool": "sum_check", "kind": "error", "message": output["error"], "args": [1, 2]}
    output, record = call("search_items", None)
    assert (record["kind"], record["args"], record["message"]) == ("error", None, output["error"])


@pytest.mark.parametrize(
    ("name", "output"),
    [
        ("value_of_by_name", {"value": "abc"}),
        ("value_of_by_name", {}),
        ("sum_check_by_name", {"results": [{"year": "2022", "ok": True}]}),
        ("sum_check", {"ok": "yes", "status": "OK", "diff": 0.0, "explanation": ""}),
        ("search_items", {"total": -1, "items": [], "limit": 1, "offset": 0}),
        ("가상_도구", {"value": 1.0}),
    ],
)
def test_shape_mismatch_is_only_for_an_engine_output_that_does_not_fit(name: str, output: dict[str, Any]) -> None:
    """도구 출력 자체가 어긋날 때(엔진의 결함)만 「shape mismatch」이고, 글은 짧다(pydantic 안내·URL 없음)."""
    args = {"a": 1}
    record = wire.to_check(2, name, args, output, tolerance=TOLERANCE)
    CHECK.validate_python(record, strict=True)
    assert record["kind"] == "error"
    assert record["message"].startswith("shape mismatch: ")
    assert "http" not in record["message"]
    assert "\n" not in record["message"]
    assert len(record["message"]) < 120
    assert record["args"] is args


def test_no_real_tool_output_is_a_shape_mismatch() -> None:
    for name, args in CALLS:
        _, record = call(name, args)
        assert not str(record.get("message", "")).startswith("shape mismatch"), (name, args)


def test_the_tolerance_is_what_the_tool_compared_with() -> None:
    """도구는 늘 실행 값(0.0)으로 견주고 기록도 그 값이다 — 모델이 준 값(bool·큰 수·글자)은 싣지 않는다(밴드 DV16)."""
    output, record = call("sum_check", {"a": 1, "b": 1, "c": 3, "tolerance": True})
    assert record["tolerance"] == "0.0"
    assert (record["years"][0]["status"], output["status"]) == ("FAIL", "FAIL")  # |−1| > 0
    _, record = call("sum_check", {"a": 1, "b": 1, "c": 2, "tolerance": False})
    assert (record["tolerance"], record["years"][0]["status"]) == ("0.0", "OK")
    _, record = call("sum_check", {"a": 1, "b": 1, "c": 3, "tolerance": 10**400})
    assert (record["tolerance"], record["years"][0]["status"]) == ("0.0", "FAIL")
    _, record = call(
        "sum_check_by_name", {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": [], "tolerance": "x"}
    )
    assert (record["kind"], record["tolerance"], record["years"]) == ("check", "0.0", [])
    made: Any = wire.to_check(1, "sum_check", {"a": 1, "b": 1, "c": 3, "tolerance": 5}, output, tolerance=0.0)
    assert (made["kind"], made["tolerance"]) == ("check", "0.0")
    for name, args in CALLS:
        _, record = call(name, args)
        if record["kind"] == "check" and any(year["note"] is None for year in record["years"]):
            assert record["tolerance"] is not None, (name, args)  # 계산한 해가 있으면 허용 오차를 썼다


def test_value_and_na_always_agree() -> None:
    """꼴이 한 갈래라 막지 못하는 모순(null+false, 값+true)을 wire 가 만들지 않는다(가지 리뷰 5)."""
    for name, args in [
        *CALLS,
        ("value_of_by_name", value_args(WASTE, "2023")),
        ("value_of_by_name", value_args(S1, 2023.0)),
    ]:
        _, record = call(name, args)
        if record["kind"] == "value":
            assert record["na"] is (record["value"] is None), args
    for value, na in (({"value": 1.0}, False), ({"value": "N/A"}, True)):
        made = wire.to_check(1, "value_of_by_name", value_args(S1, "2022"), value, tolerance=TOLERANCE)
        assert made["kind"] == "value"
        assert made["na"] is na


def test_the_wire_does_not_change_its_inputs() -> None:
    args = {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022"]}
    output = _run_local_tool("sum_check_by_name", args, data=data(), tolerance=TOLERANCE, cache=ValueCache())
    before = (repr(args), repr(output))
    wire.to_check(3, "sum_check_by_name", args, output, tolerance=TOLERANCE)
    assert (repr(args), repr(output)) == before


def test_a_diff_that_is_not_round_is_a_repr_that_round_trips() -> None:
    for name, args in (
        ("ratio_check", {"d": 1, "e": 3, "f": 33.3333, "tolerance": 0.001}),
        ("sum_check", {"a": 0.1234567, "b": 0, "c": 0}),
    ):
        output, record = call(name, args)
        diff = record["years"][0]["diff"]
        assert diff == repr(output["diff"])
        assert float(diff) == output["diff"]
        assert len(diff) > 6  # 둥근 수가 아니다(반올림하면 빨갛다)
