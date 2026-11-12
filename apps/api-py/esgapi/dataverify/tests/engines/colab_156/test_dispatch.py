"""engines/colab_156/dispatch._run_local_tool 이 손으로 적은 dict 를 내는가(발주서 DV1a §3 S3, DV1c §2-2).

이름 아홉(도구 여덟 + 모르는 이름), 인자 빠짐·틀림(TypeError 갈래와 그 밖의 예외 갈래), search_items 의 기본값.
약점 1(sum_check 의 비수치가 runtime error 가 됨)과 약점 3(분배기의 limit 기본 200, 스키마는 50)을 못박는다.
「bad arguments」 뒤의 글은 파이썬 TypeError 글이라 앞머리와 args 만 본다. 코랩과의 견줌은 esg-lab `py/dvcolab`.
"""

import json
from typing import Any

import pytest

from esgapi.dataverify.engines.colab_156 import dispatch
from esgapi.dataverify.engines.colab_156 import tools as dispatch_tools
from esgapi.dataverify.engines.colab_156.schemas import TOOLS_RESPONSES
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
    environment,
    outcome,
)

TOLERANCE = 0.0  # 흐름이 넘기는 실행 값(prompts.TOLERANCE — 밴드 DV16, MARC-ENT-685)
NON_NUMERIC = dict(ok=False, status="FAIL", diff=None, note="non-numeric", explanation="Input values are not numeric.")
DIV_ZERO = dict(ok=False, status="FAIL", diff=None, note="division by zero", explanation="Cannot divide by zero.")
BAD = object()  # 기대값 자리: {"error": "bad arguments for <이름>: <TypeError 글>", "args": <받은 인자>}


def run(name: Any, args: Any) -> dict[str, Any]:
    got = outcome(lambda: dispatch._run_local_tool(name, args, data=data(), tolerance=TOLERANCE, cache=ValueCache()))
    assert got[0] == "ok"  # 분배기는 예외를 밖으로 내지 않는다
    return json.loads(got[1])


def quad(q: tuple[str, ...]) -> list[str]:
    return list(q)


def check(ok_: bool, diff: Any, explanation: str) -> dict[str, Any]:
    return {"ok": ok_, "status": "OK" if ok_ else "FAIL", "diff": diff, "explanation": explanation}


def listed(*ids: int) -> list[dict[str, Any]]:
    keys = ("대분류", "중분류", "소분류", "단위", "values", "메모", "핵심데이터")
    env = environment()
    return [{key: env[n - 1][key] for key in keys} for n in ids]


SUM_OK = check(True, 0.0, "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0).")
SUM_2023 = check(True, 0.0, "Sum(1250.0 + 12.0) - Target(1262.0) = 0.000000 → within tolerance (0.0).")
RATIO_OK = check(
    True,
    0.0,
    "Ratio = 25.0/100.0 × 100 = 25.0000%, Expected ≈ 25.0000%, Diff = 0.0000 → within tolerance (0.0 p.p.).",
)

CASES: list[tuple[Any, Any, Any]] = [  # (이름, 인자, 손으로 적은 기대 dict 또는 BAD)
    (
        "value_of_by_name",
        {"대분류": S1[0], "중분류": S1[1], "소분류": S1[2], "단위": S1[3], "year": "2022"},
        {"value": 1200.0},
    ),
    ("value_of_by_name", {"대분류": S1[0], "year": "2022"}, {"value": "N/A"}),
    ("value_of_by_name", {}, {"value": "N/A"}),
    ("value_of_by_name", {"대분류": ["목록"], "중분류": "가", "소분류": "나", "단위": "다", "year": "2022"}, BAD),
    ("sum_check", {"a": 1200, "b": 300, "c": 1500, "tolerance": 1.1}, SUM_OK),
    ("sum_check", {"a": 1200, "b": 300, "c": 1500}, SUM_OK),
    ("sum_check", {"a": 1200, "b": 300, "c": 1500, "tolerance": "1.1"}, SUM_OK),  # 모델 값은 무시(DV16)
    ("sum_check", {"a": "N/A", "b": 300, "c": 1500}, {"error": "runtime error in sum_check: name 'e' is not defined"}),
    ("sum_check", {}, {"error": "runtime error in sum_check: name 'e' is not defined"}),
    (
        "sum_n_check",
        {"addends": [1, 2], "target": 3},
        check(True, 0.0, "Sum([1.0, 2.0]) - Target(3.0) = 0.000000 → within tolerance (0.0)."),
    ),
    ("sum_n_check", {"addends": [1, "N/A"], "target": 3}, NON_NUMERIC),
    ("sum_n_check", {"target": 3}, NON_NUMERIC),
    (
        "sum_n_check",
        {"addends": [1, 2], "target": 3, "tolerance": None},  # 모델 값은 무시(DV16)
        check(True, 0.0, "Sum([1.0, 2.0]) - Target(3.0) = 0.000000 → within tolerance (0.0)."),
    ),
    ("ratio_check", {"d": 25, "e": 100, "f": 0.25}, RATIO_OK),
    ("ratio_check", {"d": 25, "e": 0, "f": 0.25}, DIV_ZERO),
    ("ratio_check", {"d": 25, "e": 100}, NON_NUMERIC),
    (
        "sum_check_by_name",
        {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022", "2023"]},
        {"results": [{"year": "2022", **SUM_OK}, {"year": "2023", **SUM_2023}]},
    ),
    (
        "sum_check_by_name",
        {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022", "2024"]},
        {"error": "runtime error in sum_check_by_name: name 'e' is not defined"},
    ),
    (
        "sum_check_by_name",
        {"a": quad(S1), "b": quad(S2), "years": ["2022"]},
        {"error": "runtime error in sum_check_by_name: 'total'"},
    ),
    (
        "sum_check_by_name",
        {"total": quad(TOTAL)[:3], "a": quad(S1), "b": quad(S2), "years": ["2022"]},
        {"error": "runtime error in sum_check_by_name: not enough values to unpack (expected 4, got 3)"},
    ),
    ("sum_check_by_name", {"total": None, "a": quad(S1), "b": quad(S2), "years": ["2022"]}, BAD),
    (
        "sum_check_by_name",
        {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": [["2022"]]},
        {"error": "runtime error in sum_check_by_name: name 'e' is not defined"},
    ),
    (
        "sum_n_check_by_names",
        {"addends": [quad(RECYCLED), quad(LANDFILL)], "target": quad(WASTE), "years": ["2022", "2024"]},
        {
            "results": [
                {"year": "2022", **NON_NUMERIC},
                {
                    "year": "2024",
                    **check(False, float("nan"), "Sum([nan, 25.0]) - Target(50.0) = nan → exceeds tolerance (0.0)."),
                },
            ]
        },
    ),
    (
        "sum_n_check_by_names",
        {"addends": [quad(S1), quad(S2)], "target": quad(TOTAL), "years": ["2022"], "tolerance": 0},
        {
            "results": [
                {
                    "year": "2022",
                    **check(True, 0.0, "Sum([1200.0, 300.0]) - Target(1500.0) = 0.000000 → within tolerance (0.0)."),
                }
            ]
        },
    ),
    ("sum_n_check_by_names", {"addends": 5, "target": quad(TOTAL), "years": ["2022"]}, BAD),
    (
        "ratio_check_by_name",
        {
            "numerator": quad(RENEW),
            "denominator": quad(ENERGY),
            "expected": quad(RATIO),
            "years": ["2022", "2023", "2024"],
        },
        {"results": [{"year": "2022", **RATIO_OK}, {"year": "2023", **DIV_ZERO}, {"year": "2024", **NON_NUMERIC}]},
    ),
    (
        "ratio_check_by_name",
        {"numerator": quad(RENEW), "denominator": quad(ENERGY), "years": ["2022"]},
        {"error": "runtime error in ratio_check_by_name: 'expected'"},
    ),
    ("search_items", {}, {"total": 12, "items": listed(*range(1, 13)), "limit": 200, "offset": 0}),
    ("search_items", {"대분류": "폐기물"}, {"total": 3, "items": listed(9, 10, 11), "limit": 200, "offset": 0}),
    (
        "search_items",
        {"소분류_contains": "Scope", "limit": 1, "offset": 1},
        {"total": 5, "items": listed(2), "limit": 1, "offset": 1},
    ),
    ("search_items", {"limit": "5"}, BAD),
    ("search_items", {"소분류_contains": 3}, BAD),
    ("value_of", {"대분류": "가"}, {"error": "unknown tool: value_of"}),
    ("", {}, {"error": "unknown tool: "}),
    ("sum_check", None, {"error": "runtime error in sum_check: 'NoneType' object has no attribute 'get'"}),
]


@pytest.mark.parametrize(("name", "args", "expected"), CASES)
def test_the_dispatcher_by_hand(name: Any, args: Any, expected: Any) -> None:
    got = run(name, args)
    if expected is BAD:
        assert list(got) == ["error", "args"]
        assert got["error"].startswith(f"bad arguments for {name}: ")
        assert json.dumps(got["args"], ensure_ascii=False) == json.dumps(args, ensure_ascii=False)
    else:
        assert json.dumps(got, ensure_ascii=False) == json.dumps(expected, ensure_ascii=False)


def test_all_nine_names_are_covered() -> None:
    names = {name for name, _, _ in CASES}
    assert {tool["name"] for tool in TOOLS_RESPONSES} < names
    assert "value_of" in names  # 모르는 이름


def test_weakness_1_sum_check_on_a_non_number_is_a_runtime_error() -> None:
    out = run("sum_check", {"a": "N/A", "b": 300, "c": 1500})
    assert out == {"error": "runtime error in sum_check: name 'e' is not defined"}
    out = run("sum_check_by_name", {"total": quad(TOTAL), "a": quad(S1), "b": quad(S2), "years": ["2022", "2024"]})
    assert out == {"error": "runtime error in sum_check_by_name: name 'e' is not defined"}


def test_bad_arguments_carry_the_args() -> None:
    args = {"total": None, "a": quad(S1), "b": quad(S2), "years": ["2022"]}
    out = run("sum_check_by_name", args)
    assert out["error"].startswith("bad arguments for sum_check_by_name: ")
    assert out["args"] == args


def test_unknown_tool() -> None:
    assert run("value_of", {"대분류": "가"}) == {"error": "unknown tool: value_of"}


def test_weakness_3_search_items_limit_defaults_to_200_here_and_50_in_the_schema() -> None:
    out = run("search_items", {})
    assert (out["limit"], out["offset"], out["total"], len(out["items"])) == (200, 0, 12, 12)
    search = next(tool for tool in TOOLS_RESPONSES if tool["name"] == "search_items")
    assert search["parameters"]["properties"]["limit"]["default"] == 50


def test_the_default_tolerance_comes_from_the_run() -> None:
    out = dispatch._run_local_tool(
        "sum_check", {"a": 1, "b": 2, "c": 4}, data=data(), tolerance=1.0, cache=ValueCache()
    )
    assert out["status"] == "OK"
    out = dispatch._run_local_tool(
        "sum_check", {"a": 1, "b": 2, "c": 4}, data=data(), tolerance=0.5, cache=ValueCache()
    )
    assert out["status"] == "FAIL"


# ── 판정 허용 오차 0(밴드 DV16, MARC-ENT-685) — 모델이 준 tolerance 는 무시, diff 는 9 자리 반올림으로 판정 ──


@pytest.mark.parametrize(
    ("name", "args"),
    [
        ("sum_check", {"a": 1, "b": 2, "c": 4, "tolerance": 5}),
        ("sum_n_check", {"addends": [1, 2], "target": 4, "tolerance": 5}),
        ("ratio_check", {"d": 1, "e": 4, "f": 30, "tolerance": 5}),
        (
            "sum_check_by_name",
            {"total": quad(TOTAL), "a": quad(S1), "b": quad(S1), "years": ["2022"], "tolerance": 5000},
        ),
    ],
)
def test_the_model_tolerance_is_ignored(name: str, args: dict[str, Any]) -> None:
    out = run(name, args)
    row = out["results"][0] if "results" in out else out
    assert (row["ok"], row["status"]) == (False, "FAIL")
    assert row["explanation"].endswith(("exceeds tolerance (0.0).", "exceeds tolerance (0.0 p.p.)."))


def test_any_nonzero_diff_fails_and_binary_noise_does_not() -> None:
    noise = run("sum_check", {"a": 0.1, "b": 0.2, "c": 0.3, "tolerance": 1.1})
    assert (noise["ok"], noise["diff"]) == (True, 0.0)  # 0.1 + 0.2 - 0.3 = 5.55e-17 → 반올림 0
    small = run("sum_check", {"a": 1, "b": 2, "c": 3.001, "tolerance": 1.1})
    assert (small["ok"], small["status"], small["diff"]) == (False, "FAIL", -0.001)
    n_noise = run("sum_n_check", {"addends": [0.1, 0.2], "target": 0.3})
    assert (n_noise["ok"], n_noise["diff"]) == (True, 0.0)
    n_small = run("sum_n_check", {"addends": [0.1, 0.2], "target": 0.301})
    assert (n_small["ok"], n_small["diff"]) == (False, -0.001)
    ratio_noise = run("ratio_check", {"d": 0.3, "e": 0.1, "f": 300})  # 0.3 / 0.1 × 100 = 299.99999999999994
    assert (ratio_noise["ok"], ratio_noise["diff"]) == (True, 0.0)
    ratio_small = run("ratio_check", {"d": 1, "e": 3, "f": 33.3333})
    assert (ratio_small["ok"], ratio_small["diff"]) == (False, round(100 / 3 - 33.3333, 9))
    assert dispatch_tools.DIFF_DECIMALS == 9


# ── 다시 던지기(MARC-ISSUE-414, 밴드 DVE1) — 판별은 흐름이 주입, 기본값 never 는 코랩 그대로 ──


class SoftTimeLimitExceeded(Exception):
    """시험의 가짜 Celery soft limit(이름만 같다 — 엔진은 이름을 모르고 주입한 판별만 본다)."""


def is_soft(error: BaseException) -> bool:
    return isinstance(error, SoftTimeLimitExceeded)


def raising(error: BaseException) -> Any:
    def tool(*_args: Any, **_kwargs: Any) -> Any:
        raise error

    return tool


def call_sum_check(**changes: Any) -> dict[str, Any]:
    return dispatch._run_local_tool(
        "sum_check", {"a": 1, "b": 2, "c": 3}, data=data(), tolerance=TOLERANCE, cache=ValueCache(), **changes
    )


def test_an_injected_reraise_lets_the_tool_error_out_as_the_same_object(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")
    monkeypatch.setattr(dispatch, "tool_sum_check", raising(error))
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        call_sum_check(reraise=is_soft)
    assert raised.value is error


def test_an_injected_reraise_also_covers_the_type_error_branch(monkeypatch: pytest.MonkeyPatch) -> None:
    error = TypeError("가상 인자 틀림")
    monkeypatch.setattr(dispatch, "tool_sum_check", raising(error))

    def this_one(candidate: BaseException) -> bool:
        return candidate is error

    with pytest.raises(TypeError) as raised:
        call_sum_check(reraise=this_one)
    assert raised.value is error


def test_the_default_never_keeps_the_colab_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(dispatch, "tool_sum_check", raising(SoftTimeLimitExceeded("가상 시간 제한")))
    assert call_sum_check() == {"error": "runtime error in sum_check: 가상 시간 제한"}
    assert dispatch.never(SoftTimeLimitExceeded()) is False


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (ValueError("가상 값 오류"), {"error": "runtime error in sum_check: 가상 값 오류"}),
        (
            TypeError("가상 인자 틀림"),
            {"error": "bad arguments for sum_check: 가상 인자 틀림", "args": {"a": 1, "b": 2, "c": 3}},
        ),
    ],
)
def test_an_injected_reraise_that_says_no_gives_the_default_dict(
    monkeypatch: pytest.MonkeyPatch, error: Exception, expected: dict[str, Any]
) -> None:
    monkeypatch.setattr(dispatch, "tool_sum_check", raising(error))
    injected = call_sum_check(reraise=is_soft)
    default = call_sum_check()
    assert json.dumps(injected, ensure_ascii=False) == json.dumps(default, ensure_ascii=False)
    assert injected == expected
