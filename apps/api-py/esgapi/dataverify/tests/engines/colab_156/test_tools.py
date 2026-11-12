"""engines/colab_156/tools.py 의 도구 여덟이 손으로 셈한 값을 내는가(발주서 DV1a §3 S1·S2·S4, DV1c §2-2).

S1 = 손으로 고른 인자(지어낸 항목 열둘)와 손으로 적은 기대값, S2 = hypothesis 와 말로 쓴 명세 판정(감독 결정 ④),
S4 = 캐시. 결과는 json 글자로 견준다(값·키 차례·NaN). 코랩과의 견줌은 esg-lab `py/dvcolab`(MARC-ENT-310).
약점: 1(sum_check 의 비수치 → NameError, 이름형은 호출 전체가 예외), 4(기대값 0~1 은 비율 → ×100, 1.0 도 100%),
5(캐시 열쇠에 데이터가 없음), 6(같은 네 칸이 둘이면 첫 것만) — 각각 이름 붙인 시험이 있다. 약점 3 은 test_dispatch.py.
"""

import contextlib
import json
import math
from typing import Any

import pytest
from hypothesis import example, given
from hypothesis import strategies as st

from esgapi.dataverify.engines.colab_156 import tools
from esgapi.dataverify.engines.colab_156.tools import ValueCache
from esgapi.dataverify.engines.colab_156.tools import _safe_float as safe_float  # pyright: ignore[reportPrivateUsage]
from esgapi.dataverify.tests.engines.colab_156.support import (
    ENERGY,
    LANDFILL,
    RATIO,
    RECYCLED,
    RENEW,
    S1,
    S1_TON,
    S2,
    TOTAL,
    WASTE,
    WATER,
    YEARS,
    data,
    environment,
    outcome,
)

CACHED = {"tool_value_of_by_name", "tool_sum_check_by_name", "tool_sum_n_check_by_names", "tool_ratio_check_by_name"}
NAME_ERROR = ("raise", "NameError: name 'e' is not defined")  # 약점 1(코랩 R/137)
NON_NUMERIC = dict(ok=False, status="FAIL", diff=None, note="non-numeric", explanation="Input values are not numeric.")
DIV_ZERO = dict(ok=False, status="FAIL", diff=None, note="division by zero", explanation="Cannot divide by zero.")


def call(name: str, *args: Any) -> tuple[str, str]:
    """우리 함수를 부른다(캐시를 받는 것은 빈 캐시에서)."""
    if name in CACHED:
        return outcome(lambda: getattr(tools, name)(*args, cache=ValueCache()))
    return outcome(lambda: getattr(tools, name)(*args))


def ok(value: Any) -> tuple[str, str]:
    return ("ok", json.dumps(value, ensure_ascii=False))


def check(ok_: bool, diff: float, explanation: str) -> dict[str, Any]:
    return {"ok": ok_, "status": "OK" if ok_ else "FAIL", "diff": diff, "explanation": explanation}


# ── S1 value_of_by_name: 손으로 읽은 값 표 ──
# 항목(support.environment)의 값 글자를 손으로 읽었다: 쉼표·빈칸을 지우고 float, None·""·"N/A"·수로 못 읽는 글은 "N/A".
# 같은 네 칸이 둘이면 첫째(약점 6) — S1 은 첫째 항목(1200…)이지 다섯째(99999)가 아니다.
VALUES_BY_HAND: dict[tuple[str, str, str, str], tuple[Any, Any, Any]] = {
    S1: (1200.0, 1250.0, 1300.5),  # 1200 · "1,250" · 1300.5
    S1_TON: (9.0, 8.0, 7.0),
    S2: (300.0, 12.0, "N/A"),  # 300 · " 12 " · "N/A"
    TOTAL: (1500.0, 1262.0, 1605.0),
    ENERGY: (100.0, 0.0, 100.0),  # 100 · 0 · "100"
    RENEW: (25.0, 5.0, "N/A"),  # 25 · 5 · ""
    RATIO: (0.25, 1.0, 25.0),
    WASTE: ("N/A", "N/A", 50.0),  # None · "abc" · 50
    RECYCLED: (10.0, 20.0, math.nan),  # 10 · 20 · "nan"
    LANDFILL: (5.0, math.inf, 25.0),  # 5 · "inf" · 25
    WATER: (1234.0, 1234.0, 1234.0),  # "1,234" · "1 234" · "12,34"
}


@pytest.mark.parametrize("quad", list(VALUES_BY_HAND))
@pytest.mark.parametrize("year", [*YEARS, "2025", 2022, None])
def test_value_of_by_name_by_hand(quad: tuple[str, str, str, str], year: Any) -> None:
    """연도는 str(year) 로 찾는다 — 정수 2022 는 "2022" 와 같고, 없는 해(2025·None → "None")는 "N/A"."""
    by_year: dict[str, Any] = dict(zip(YEARS, VALUES_BY_HAND[quad], strict=True))
    expected = by_year.get(str(year), "N/A")
    assert call("tool_value_of_by_name", data(), *quad, year) == ok({"value": expected})


def test_value_of_by_name_reads_like_the_colab() -> None:
    """쉼표·빈칸을 지우고 float, None·""·"N/A" 와 수로 못 읽는 글은 "N/A"(약점 6 의 뒷말, 코랩 R/306-345)."""
    d = data()
    assert call("tool_value_of_by_name", d, *S1, "2023") == ("ok", '{"value": 1250.0}')
    assert call("tool_value_of_by_name", d, *S2, "2023") == ("ok", '{"value": 12.0}')
    assert call("tool_value_of_by_name", d, *S2, "2024") == ("ok", '{"value": "N/A"}')
    assert call("tool_value_of_by_name", d, *RENEW, "2024") == ("ok", '{"value": "N/A"}')
    assert call("tool_value_of_by_name", d, *WASTE, "2022") == ("ok", '{"value": "N/A"}')
    assert call("tool_value_of_by_name", d, *WASTE, "2023") == ("ok", '{"value": "N/A"}')
    assert call("tool_value_of_by_name", d, *WATER, "2023") == ("ok", '{"value": 1234.0}')
    assert call("tool_value_of_by_name", d, *WATER, "2024") == ("ok", '{"value": 1234.0}')
    assert call("tool_value_of_by_name", d, *RECYCLED, "2024") == ("ok", '{"value": NaN}')
    assert call("tool_value_of_by_name", d, "없는", "가상", "항목", "t", "2022") == ("ok", '{"value": "N/A"}')


def test_weakness_6_only_the_first_of_two_same_items_is_read() -> None:
    assert call("tool_value_of_by_name", data(), *S1, "2022") == ("ok", '{"value": 1200.0}')  # 다섯째의 99999 가 아님


def test_the_unit_tells_two_items_apart() -> None:
    assert call("tool_value_of_by_name", data(), *S1_TON, "2022") == ("ok", '{"value": 9.0}')


# ── S1 sum_check: diff = round((a+b)-c, 9), ok = |diff| <= 허용 오차(DV16 — 코랩은 날 값 판정·10자리 기록) ──
SUM_CASES: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
    (
        (1200, 300, 1500, 0.0),
        check(True, 0.0, "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0)."),
    ),
    (
        (1200, 300, 1505, 0.0),
        check(False, -5.0, "Sum(1200.0 + 300.0) - Target(1505.0) = -5.000000 → exceeds tolerance (0.0)."),
    ),
    (
        ("1200", 300, 1500, 0.0),
        check(True, 0.0, "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0)."),
    ),
    (
        (1200.5, 300, 1500, 0.0),
        check(False, 0.5, "Sum(1200.5 + 300.0) - Target(1500.0) = 0.500000 → exceeds tolerance (0.0)."),
    ),
    # 0.1+0.2 = 0.30000000000000004 — diff 5.55e-17 은 9자리 반올림으로 0.0, 허용 오차 0 안(2진 잡음은 맞음)
    ((0.1, 0.2, 0.3, 0), check(True, 0.0, "Sum(0.1 + 0.2) - Target(0.3) = 0.000000 → within tolerance (0).")),
    # 0.001 차이는 허용 오차 0 을 넘는다(아주 작은 차이도 어긋남)
    ((1, 2, 3.001, 0.0), check(False, -0.001, "Sum(1.0 + 2.0) - Target(3.001) = -0.001000 → exceeds tolerance (0.0).")),
    # 1.00000000005 - 1 = 5.0000004e-11 — 9자리 반올림이면 0.0(코랩의 10자리는 1e-10)
    (
        (1.00000000005, 0, 1, 0.0),
        check(True, 0.0, "Sum(1.00000000005 + 0.0) - Target(1.0) = 0.000000 → within tolerance (0.0)."),
    ),
    # 1.000000002 - 1 = 2e-09 — 9자리에 남는 차이는 어긋남
    (
        (1.000000002, 0, 1, 0.0),
        check(False, 2e-09, "Sum(1.000000002 + 0.0) - Target(1.0) = 0.000000 → exceeds tolerance (0.0)."),
    ),
    # |−1| <= 1.0 — 경계는 같음도 통과(P1)
    ((1, 2, 4, 1.0), check(True, -1.0, "Sum(1.0 + 2.0) - Target(4.0) = -1.000000 → within tolerance (1.0).")),
]


@pytest.mark.parametrize(("args", "expected"), SUM_CASES)
def test_sum_check_by_hand(args: tuple[Any, ...], expected: dict[str, Any]) -> None:
    assert call("tool_sum_check", *args) == ok(expected)


@pytest.mark.parametrize("bad", ["N/A", None, "", "1,234", [1]])
def test_weakness_1_sum_check_raises_name_error_on_a_non_number(bad: Any) -> None:
    """코랩 R/137 의 print(f"…{e}") — 비수치 갈래가 note="non-numeric" 대신 NameError 를 낸다."""
    assert call("tool_sum_check", bad, 1, 2, 0.0) == NAME_ERROR
    assert call("tool_sum_check", 1, 2, bad, 0.0) == NAME_ERROR


# ── S1 sum_n_check: 하나라도 float 로 못 바꾸면 non-numeric(sum_check 와 달리 note 를 낸다) ──
SUM_N_CASES: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
    (([1, 2], 3, 0.0), check(True, 0.0, "Sum([1.0, 2.0]) - Target(3.0) = 0.000000 → within tolerance (0.0).")),
    (([1, "N/A"], 3, 0.0), NON_NUMERIC),
    ((None, 3, 0.0), NON_NUMERIC),  # None 은 돌 수 없다(TypeError)
    (([], 0, 0.0), check(True, 0.0, "Sum([]) - Target(0.0) = 0.000000 → within tolerance (0.0).")),
    (([1.5, "2"], 3.5, 0), check(True, 0.0, "Sum([1.5, 2.0]) - Target(3.5) = 0.000000 → within tolerance (0).")),
    ((["1,2"], 1, 1), NON_NUMERIC),  # 쉼표 글은 float 가 못 읽는다(_safe_float 와 다르다)
]


@pytest.mark.parametrize(("args", "expected"), SUM_N_CASES)
def test_sum_n_check_by_hand(args: tuple[Any, ...], expected: dict[str, Any]) -> None:
    assert call("tool_sum_n_check", *args) == ok(expected)


# ── S1 ratio_check: 계산 % = d/e×100, 기대 % = f(0~1 이면 ×100), diff 는 소수 9자리 반올림(DV16 — 코랩은 6자리) ──
RATIO_CASES: list[tuple[tuple[Any, ...], dict[str, Any]]] = [
    (
        (25, 100, 0.25, 0.0),
        check(
            True,
            0.0,
            "Ratio = 25.0/100.0 × 100 = 25.0000%, Expected ≈ 25.0000%, Diff = 0.0000 → within tolerance (0.0 p.p.).",
        ),
    ),
    (
        (25, 100, 25, 0.0),
        check(
            True,
            0.0,
            "Ratio = 25.0/100.0 × 100 = 25.0000%, Expected ≈ 25.0000%, Diff = 0.0000 → within tolerance (0.0 p.p.).",
        ),
    ),
    (
        (100, 100, 1.0, 0.0),
        check(
            True,
            0.0,
            "Ratio = 100.0/100.0 × 100 = 100.0000%, Expected ≈ 100.0000%, Diff = 0.0000 → within tolerance (0.0 p.p.).",
        ),
    ),
    (
        (1, 100, 1.0, 0.0),
        check(
            False,
            -99.0,
            "Ratio = 1.0/100.0 × 100 = 1.0000%, Expected ≈ 100.0000%, Diff = -99.0000 → exceeds tolerance (0.0 p.p.).",
        ),
    ),
    ((5, 0, 1, 0.0), DIV_ZERO),
    ((5, 1e-16, 1, 0.0), DIV_ZERO),  # |e| < 1e-15 도 0 으로 본다
    (("x", 1, 1, 0.0), NON_NUMERIC),
    # 1/3×100 = 33.333333…, 기대 33.3333 → diff 0.0000333… → 소수 9자리 3.3333e-05, 허용 0.001 안
    (
        (1, 3, 33.3333, 0.001),
        check(
            True,
            3.3333e-05,
            "Ratio = 1.0/3.0 × 100 = 33.3333%, Expected ≈ 33.3333%, Diff = 0.0000 → within tolerance (0.001 p.p.).",
        ),
    ),
    (
        (0, 5, 0, 0),
        check(
            True, 0.0, "Ratio = 0.0/5.0 × 100 = 0.0000%, Expected ≈ 0.0000%, Diff = 0.0000 → within tolerance (0 p.p.)."
        ),
    ),
    # f = -0.5 는 0~1 밖 — 이미 % 로 본다. 2 - (-0.5) = 2.5
    (
        (2, 100, -0.5, 0.0),
        check(
            False,
            2.5,
            "Ratio = 2.0/100.0 × 100 = 2.0000%, Expected ≈ -0.5000%, Diff = 2.5000 → exceeds tolerance (0.0 p.p.).",
        ),
    ),
]


@pytest.mark.parametrize(("args", "expected"), RATIO_CASES)
def test_ratio_check_by_hand(args: tuple[Any, ...], expected: dict[str, Any]) -> None:
    assert call("tool_ratio_check", *args) == ok(expected)


def test_weakness_4_an_expected_value_from_0_to_1_is_a_ratio() -> None:
    """f 가 0~1 이면 ×100 — 1.0 은 1% 가 아니라 100% 로 읽는다."""
    ok_100 = tools.tool_ratio_check(100, 100, 1.0, 0.0)
    assert (ok_100["status"], ok_100["diff"]) == ("OK", 0.0)
    one_pct = tools.tool_ratio_check(1, 100, 1.0, 0.0)
    assert (one_pct["status"], one_pct["diff"]) == ("FAIL", -99.0)
    quarter = tools.tool_ratio_check(25, 100, 0.25, 0.0)
    assert (quarter["status"], quarter["diff"]) == ("OK", 0.0)
    assert tools.tool_ratio_check(25, 100, 25, 0.0)["diff"] == 0.0


# ── S1 이름형 셋: 해마다 값 표(위)로 셈 ──
SCOPE_2022 = check(True, 0.0, "Sum(1200.0 + 300.0) - Target(1500.0) = 0.000000 → within tolerance (0.0).")
SCOPE_2023 = check(True, 0.0, "Sum(1250.0 + 12.0) - Target(1262.0) = 0.000000 → within tolerance (0.0).")


def test_sum_check_by_name_by_hand() -> None:
    by_name = "tool_sum_check_by_name"
    assert call(by_name, data(), TOTAL, S1, S2, ["2022"], 0.0) == ok({"results": [{"year": "2022", **SCOPE_2022}]})
    assert call(by_name, data(), TOTAL, S1, S2, ["2023"], 0.0) == ok({"results": [{"year": "2023", **SCOPE_2023}]})
    assert call(by_name, data(), TOTAL, S1, S2, [], 0.0) == ok({"results": []})
    assert call(by_name, data(), TOTAL, S1, S2, [2022], 0.0) == ok({"results": [{"year": 2022, **SCOPE_2022}]})


def test_weakness_1_one_missing_year_turns_the_whole_by_name_call_into_an_exception() -> None:
    """2024 의 Scope 2 가 N/A — 2022 의 결과까지 사라지고 호출 전체가 NameError."""
    assert call("tool_sum_check_by_name", data(), TOTAL, S1, S2, ["2022", "2024"], 0.0) == NAME_ERROR


def test_sum_n_check_by_names_by_hand() -> None:
    # 폐기물: 2022 합계 N/A(None), 2023 합계 N/A("abc") → non-numeric.
    # 2024 재활용 NaN + 매립 25 → NaN, |NaN| <= 0.0 은 거짓
    got = call("tool_sum_n_check_by_names", data(), [RECYCLED, LANDFILL], WASTE, list(YEARS), 0.0)
    nan_row = check(False, math.nan, "Sum([nan, 25.0]) - Target(50.0) = nan → exceeds tolerance (0.0).")
    rows = [{"year": "2022", **NON_NUMERIC}, {"year": "2023", **NON_NUMERIC}, {"year": "2024", **nan_row}]
    assert got == ok({"results": rows})
    got = call("tool_sum_n_check_by_names", data(), [S1, S2], TOTAL, ["2022", "2023"], 0.0)
    rows = [
        {
            "year": "2022",
            **check(True, 0.0, "Sum([1200.0, 300.0]) - Target(1500.0) = 0.000000 → within tolerance (0.0)."),
        },
        {
            "year": "2023",
            **check(True, 0.0, "Sum([1250.0, 12.0]) - Target(1262.0) = 0.000000 → within tolerance (0.0)."),
        },
    ]
    assert got == ok({"results": rows})


QUARTER_OK = "Ratio = 25.0/100.0 × 100 = 25.0000%, Expected ≈ 25.0000%, Diff = 0.0000 → within tolerance (0.0 p.p.)."


def test_ratio_check_by_name_by_hand() -> None:
    # 재생에너지/총 에너지/비율: 2022 25/100 대 0.25, 2023 분모 0, 2024 분자 N/A("")
    got = call("tool_ratio_check_by_name", data(), RENEW, ENERGY, RATIO, list(YEARS), 0.0)
    rows = [
        {"year": "2022", **check(True, 0.0, QUARTER_OK)},
        {"year": "2023", **DIV_ZERO},
        {"year": "2024", **NON_NUMERIC},
    ]
    assert got == ok({"results": rows})


# ── S1 search_items: 대·중분류는 같음, 소분류는 부분, 빈 글은 거르지 않음. 기본 limit 50(도구) ──
def listed(n: int) -> dict[str, Any]:
    """항목 n(1부터)이 검색 결과에 실리는 꼴: 칸 일곱, 메모·핵심데이터는 없으면 ""."""
    rec = environment()[n - 1]
    keys = ("대분류", "중분류", "소분류", "단위", "values", "메모", "핵심데이터")
    return {key: rec[key] for key in keys}


ALL = list(range(1, 13))
SEARCH_CASES: list[tuple[dict[str, Any], int, list[int], int, int]] = [  # (인자, total, 실린 항목, limit, offset)
    ({}, 12, ALL, 50, 0),
    ({"대분류": "온실가스 배출량"}, 5, [1, 2, 3, 4, 5], 50, 0),
    ({"중분류": "처리 방법"}, 2, [10, 11], 50, 0),
    ({"소분류_contains": "Scope"}, 5, [1, 2, 3, 4, 5], 50, 0),
    ({"대분류": "폐기물", "소분류_contains": "량"}, 3, [9, 10, 11], 50, 0),
    ({"limit": 3, "offset": 2}, 12, [3, 4, 5], 3, 2),
    ({"limit": 0}, 12, [], 0, 0),
    ({"offset": 50}, 12, [], 50, 50),
    ({"대분류": ""}, 12, ALL, 50, 0),
]


@pytest.mark.parametrize(("kwargs", "total", "ids", "limit", "offset"), SEARCH_CASES)
def test_search_items_by_hand(kwargs: dict[str, Any], total: int, ids: list[int], limit: int, offset: int) -> None:
    expected = {"total": total, "items": [listed(n) for n in ids], "limit": limit, "offset": offset}
    assert outcome(lambda: tools.tool_search_items(data(), **kwargs)) == ok(expected)


def test_search_items_without_a_memo_key_gives_an_empty_memo() -> None:
    d = data()
    del d["환경"][0]["메모"]
    del d["환경"][0]["핵심데이터"]
    first = json.loads(outcome(lambda: tools.tool_search_items(d))[1])["items"][0]
    assert (first["메모"], first["핵심데이터"]) == ("", "")
    assert list(first) == ["대분류", "중분류", "소분류", "단위", "values", "메모", "핵심데이터"]


# ── S2 hypothesis: 관계 성질만(감독 결정 ④·critic §7-2) — 글과 값은 위 손 표가, 무작위 대조는 esg-lab dvcolab 이 ──
def as_float(v: Any) -> float | None:
    """파이썬 float() 가 받으면 그 수, 못 받으면(TypeError·ValueError) None."""
    number: float | None = None
    with contextlib.suppress(TypeError, ValueError):
        number = float(v)
    return number


def holds(got: tuple[str, str], raw: float, tolerance: Any) -> None:
    """키 차례 ok·status·diff·explanation, diff 는 raw 를 9 자리 반올림(DIFF_DECIMALS — 밴드 DV16),
    ok ⇔ |반올림한 diff| <= 허용 오차, ok ⇔ status == "OK"."""
    assert got[0] == "ok"
    out = json.loads(got[1])
    assert list(out) == ["ok", "status", "diff", "explanation"]
    rounded = round(raw, 9)
    assert out["ok"] is (abs(rounded) <= tolerance)
    assert out["ok"] is (out["status"] == "OK")
    assert json.dumps(out["diff"]) == json.dumps(rounded)


NUMBERS = st.floats(allow_nan=False, allow_infinity=False) | st.integers(min_value=-(10**9), max_value=10**9)
ODD = st.sampled_from(["N/A", "", "1,234", " 12 ", "abc", "nan", "inf", "-0", "1e3", "0.5"]) | st.none()
EDGES = st.sampled_from([0, 0.0, -0.0, 1, 1.0, 0.5, 0.999999, 1.000001, -1e-16, 1e-16])
VALUE = NUMBERS | ODD | EDGES | st.text(max_size=6)
TOLERANCE = st.floats(min_value=0, max_value=1e9, allow_nan=False) | st.sampled_from([0, 1.1, 1e-6, 1])


@given(a=VALUE, b=VALUE, c=VALUE, tolerance=TOLERANCE)
@example(a=0.1, b=0.2, c=0.3, tolerance=abs((0.1 + 0.2) - 0.3))
@example(a=1, b=2, c=4, tolerance=1.0)
@example(a=1200, b=300, c=1501.1, tolerance=abs((1200 + 300) - 1501.1))
def test_sum_check_hypothesis(a: Any, b: Any, c: Any, tolerance: Any) -> None:
    """셋 다 수면 raw = (a+b)-c 로 위 성질. 하나라도 float 로 못 바꾸면 NameError(약점 1)."""
    got = call("tool_sum_check", a, b, c, tolerance)
    fa, fb, fc = as_float(a), as_float(b), as_float(c)
    if fa is None or fb is None or fc is None:
        assert got == NAME_ERROR
        return
    holds(got, (fa + fb) - fc, tolerance)


@given(addends=st.lists(VALUE, max_size=5) | st.none() | VALUE, target=VALUE, tolerance=TOLERANCE)
@example(addends=[0.1, 0.2], target=0.3, tolerance=abs((0.1 + 0.2) - 0.3))
def test_sum_n_check_hypothesis(addends: Any, target: Any, tolerance: Any) -> None:
    """돌 수 없거나(None·수) 원소·목표 가운데 float 로 못 바꾸는 것이 있으면 non-numeric. 아니면 raw = sum - 목표."""
    got = call("tool_sum_n_check", addends, target, tolerance)
    try:
        nums = [as_float(x) for x in addends]
    except TypeError:
        nums = [None]
    goal = as_float(target)
    if goal is None or any(n is None for n in nums):
        assert got == ok(NON_NUMERIC)
        return
    holds(got, sum(n for n in nums if n is not None) - goal, tolerance)


@given(d=VALUE, e=VALUE, f=VALUE, tolerance=TOLERANCE)
@example(d=1, e=100, f=1.0, tolerance=1.1)
@example(d=1, e=100, f=1.000001, tolerance=0)
@example(d=50, e=100, f=0.5, tolerance=0)
@example(d=1, e=-1e-16, f=1, tolerance=1)
def test_ratio_check_hypothesis(d: Any, e: Any, f: Any, tolerance: Any) -> None:
    """수가 아니면 non-numeric, |분모| < 1e-15 면 division by zero.
    아니면 raw = 계산 % − 기대 %(f 가 0~1 이면 f×100)."""
    got = call("tool_ratio_check", d, e, f, tolerance)
    fd, fe, ff = as_float(d), as_float(e), as_float(f)
    if fd is None or fe is None or ff is None:
        assert got == ok(NON_NUMERIC)
        return
    if abs(fe) < 1e-15:
        assert got == ok(DIV_ZERO)
        return
    holds(got, (fd / fe) * 100.0 - (ff * 100.0 if 0.0 <= ff <= 1.0 else ff), tolerance)


# _safe_float: 손으로 적은 표. 글이면 쉼표와 빈칸(" ")을 지우고 float — 탭은 지우지 않는다(float 가 앞뒤 탭만 견딘다).
SAFE_FLOAT_BY_HAND: list[tuple[Any, Any]] = [
    ("1,234", 1234.0),
    (" 1 2 ", 12.0),
    ("1,2,3.5", 123.5),
    ("1 234", 1234.0),
    ("12,34", 1234.0),
    (" 12 ", 12.0),
    ("\t7\t", 7.0),
    ("1\t2", None),
    ("abc", None),
    ("", None),
    (", ,", None),
    ("nan", math.nan),
    ("-inf", -math.inf),
    (None, None),
    ([1], None),
    (3, 3.0),
    (True, 1.0),
]


@pytest.mark.parametrize(("value", "expected"), SAFE_FLOAT_BY_HAND)
def test_safe_float_by_hand(value: Any, expected: Any) -> None:
    assert outcome(lambda: safe_float(value)) == ok(expected)


@given(v=VALUE, at=st.integers(min_value=0, max_value=6), mark=st.sampled_from([",", " "]))
def test_safe_float_hypothesis(v: Any, at: int, mark: str) -> None:
    """글 안 어디에 쉼표나 빈칸을 하나 더 끼워도 값이 같다. 글이 아니면 float() 와 같다(못 읽으면 None)."""
    if not isinstance(v, str):
        assert outcome(lambda: safe_float(v)) == ok(as_float(v))
        return
    widened = v[:at] + mark + v[at:]
    assert outcome(lambda: safe_float(widened)) == outcome(lambda: safe_float(v))


# ── S4 캐시 ──
def test_the_same_key_twice_gives_the_same_object() -> None:
    cache = ValueCache()
    first = tools.tool_value_of_by_name(data(), *S1, "2022", cache=cache)
    again = tools.tool_value_of_by_name(data(), *S1, "2022", cache=cache)
    assert again is first
    assert tools.tool_value_of_by_name(data(), *S1, 2022, cache=cache) is first  # 열쇠의 연도는 str(year)


def test_a_key_that_differs_only_in_the_unit_is_its_own_entry() -> None:
    cache = ValueCache()
    tools.tool_value_of_by_name(data(), *S1, "2022", cache=cache)
    tools.tool_value_of_by_name(data(), *S1_TON, "2022", cache=cache)
    assert dict(cache) == {(*S1, "2022"): {"value": 1200.0}, (*S1_TON, "2022"): {"value": 9.0}}


def test_weakness_5_the_cache_does_not_know_the_data_so_a_run_takes_a_new_cache() -> None:
    """열쇠에 데이터가 없어 같은 캐시면 입력이 바뀌어도 옛 값을 준다
    (코랩은 그래서 입력마다 손으로 비웠다 — R/93-96·R/304). 우리는 실행마다 새 캐시."""
    changed = data()
    changed["환경"][0]["values"]["2022"] = 7
    cache = ValueCache()
    tools.tool_value_of_by_name(data(), *S1, "2022", cache=cache)
    assert tools.tool_value_of_by_name(changed, *S1, "2022", cache=cache) == {"value": 1200.0}  # 같은 캐시면 옛 값
    assert tools.tool_value_of_by_name(changed, *S1, "2022", cache=ValueCache()) == {"value": 7.0}  # 새 실행
