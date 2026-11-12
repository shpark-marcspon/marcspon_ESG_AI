"""engines/colab_156/loop.py — 도구 실행기·HINTS 읽기·검토 걸음·리포트 글(발주서 §2-2, §3 S2).

기대값은 손으로 적었다(엔진을 불러 나온 값을 붙이지 않는다). 모델에 돌려주는 글은 json.dumps 의 기본 구분자(", "·": ")와
ensure_ascii=False 꼴이라 한국어가 그대로다. 자료는 support.py 의 지어낸 「환경」 항목 열둘.
"""

import json
from typing import Any

import pytest

from esgapi.dataverify.engines.colab_156 import dispatch, loop
from esgapi.dataverify.engines.colab_156.loop import (
    ReviewSteps,
    ToolRecord,
    ToolRunner,
    parse_hints,
    report_text,
    review_steps,
)
from esgapi.dataverify.tests.engines.colab_156.support import data

S1_2022 = '{"대분류": "온실가스 배출량", "중분류": "직접 배출량", "소분류": "Scope 1", "단위": "tCO2eq", "year": 2022}'


def runner(max_output_chars: int = 100_000) -> ToolRunner:
    return ToolRunner(data=data(), tolerance=0.0, max_output_chars=max_output_chars)


@pytest.mark.parametrize(
    ("name", "arguments", "expected"),
    [
        ("value_of_by_name", S1_2022, '{"value": 1200.0}'),
        # 인자 글이 JSON 이 아니면 {} 로 둔다(R/555) → 네 칸이 다 None 이라 맞는 항목이 없다
        ("value_of_by_name", '{"대분류": ', '{"value": "N/A"}'),
        # JSON 이지만 객체가 아니면 그대로 분배기로 → args.get 에서 AttributeError → runtime error 글
        (
            "value_of_by_name",
            "[1]",
            "{\"error\": \"runtime error in value_of_by_name: 'list' object has no attribute 'get'\"}",
        ),
        ("nope", "{}", '{"error": "unknown tool: nope"}'),
        # 코랩은 web_search 이름의 함수 호출을 건너뛰지만(R/731) 우리는 분배기로 보낸다(「다른 자리」)
        ("web_search", "{}", '{"error": "unknown tool: web_search"}'),
        # 약점 1: 비수치 sum_check 는 NameError → runtime error 글
        (
            "sum_check",
            '{"a": "x", "b": 1, "c": 2}',
            '{"error": "runtime error in sum_check: name \'e\' is not defined"}',
        ),
        # 허용 오차는 실행기의 것(0.0)
        (
            "sum_check",
            '{"a": 1, "b": 2, "c": 3}',
            '{"ok": true, "status": "OK", "diff": 0.0, '
            '"explanation": "Sum(1.0 + 2.0) - Target(3.0) = 0.000000 → within tolerance (0.0)."}',
        ),
        # search_items 의 limit 기본 200(약점 3), 한국어 그대로·기본 구분자
        (
            "search_items",
            '{"소분류_contains": "Scope 2"}',
            '{"total": 1, "items": [{"대분류": "온실가스 배출량", "중분류": "간접 배출량", "소분류": "Scope 2", '
            '"단위": "tCO2eq", "values": {"2022": 300, "2023": " 12 ", "2024": "N/A"}, "메모": "", "핵심데이터": ""}], '
            '"limit": 200, "offset": 0}',
        ),
    ],
)
def test_the_runner_returns_the_json_text_by_hand(name: str, arguments: str, expected: str) -> None:
    run = runner()
    text = run(name, arguments)
    assert type(text) is str
    assert text == expected


def test_unparsable_arguments_are_counted_and_recorded_as_an_empty_object() -> None:
    run = runner()
    run("value_of_by_name", "not json")
    run("value_of_by_name", S1_2022)
    run("value_of_by_name", "")
    assert run.unparsable_args == 2
    assert [record.args for record in run.records] == [
        {},
        {"대분류": "온실가스 배출량", "중분류": "직접 배출량", "소분류": "Scope 1", "단위": "tCO2eq", "year": 2022},
        {},
    ]


def test_records_keep_the_order_and_the_output_dict() -> None:
    run = runner()
    run("nope", "{}")
    run("value_of_by_name", S1_2022)
    run("sum_check", "[1]")
    assert run.records == [
        ToolRecord(seq=1, name="nope", args={}, output={"error": "unknown tool: nope"}),
        ToolRecord(seq=2, name="value_of_by_name", args=run.records[1].args, output={"value": 1200.0}),
        ToolRecord(
            seq=3,
            name="sum_check",
            args=[1],
            output={"error": "runtime error in sum_check: 'list' object has no attribute 'get'"},
        ),
    ]


def test_the_output_limit_is_inclusive() -> None:
    """'{"value": 1200.0}' 는 17자다. 상한 17 이면 그대로, 16 이면 error 글로 바꾼다(처분 ③)."""
    at_limit = runner(max_output_chars=17)
    assert at_limit("value_of_by_name", S1_2022) == '{"value": 1200.0}'
    assert at_limit.too_large == 0

    over = runner(max_output_chars=16)
    text = over("value_of_by_name", S1_2022)
    assert type(text) is str
    assert text == '{"error": "tool output too large: 17 chars > 16"}'
    assert over.too_large == 1
    assert over.records == [
        ToolRecord(
            seq=1,
            name="value_of_by_name",
            args=over.records[0].args,
            output={"error": "tool output too large: 17 chars > 16"},
        )
    ]


def test_the_cache_lives_in_one_runner() -> None:
    """같은 실행기 안에서는 첫 조회 값이 남는다(코랩의 캐시). 실행기가 다르면 캐시도 다르다."""
    shared = data()
    first = ToolRunner(data=shared, tolerance=0.0, max_output_chars=100_000)
    assert first("value_of_by_name", S1_2022) == '{"value": 1200.0}'
    shared["환경"][0]["values"]["2022"] = 7
    assert first("value_of_by_name", S1_2022) == '{"value": 1200.0}'
    second = ToolRunner(data=shared, tolerance=0.0, max_output_chars=100_000)
    assert second("value_of_by_name", S1_2022) == '{"value": 7.0}'


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("['가상 산식 1', '가상 산식 2']", ["가상 산식 1", "가상 산식 2"]),
        ("('가상 산식',)", ["가상 산식"]),
        ("[]", []),
        ("{'가상': 1}", None),
        ("['가상 산식', 1]", None),
        ("42", None),
        ("['가상 산식'", None),
        ("```python\n['가상 산식']\n```", None),
        ("", None),
    ],
)
def test_parse_hints_by_hand(text: str, expected: Any) -> None:
    assert parse_hints(text) == expected


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, ReviewSteps(loop_steps=1, capped=False)),
        (4, ReviewSteps(loop_steps=12, capped=False)),
        (12, ReviewSteps(loop_steps=36, capped=False)),
        (13, ReviewSteps(loop_steps=36, capped=True)),
    ],
)
def test_review_steps_by_hand(count: int, expected: ReviewSteps) -> None:
    assert review_steps([f"가상 산식 {n}" for n in range(count)], 36) == expected


def test_report_text_strips_and_keeps_an_empty_text() -> None:
    assert report_text("  가상 리포트\n\n") == "가상 리포트"
    assert report_text("") == ""


# ── 다시 던지기(MARC-ISSUE-414, 밴드 DVE1) — 인자 읽기·HINTS 읽기 ──


class SoftTimeLimitExceeded(Exception):
    """시험의 가짜 Celery soft limit."""


def is_soft(error: BaseException) -> bool:
    return isinstance(error, SoftTimeLimitExceeded)


class RaisingJson:
    """loop.json 대역: loads 는 주어진 예외를 던지고 dumps 는 진짜."""

    def __init__(self, error: BaseException) -> None:
        self._error = error
        self.dumps = json.dumps

    def loads(self, _text: str) -> Any:
        raise self._error


def test_an_injected_reraise_lets_an_argument_read_error_out(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")
    monkeypatch.setattr(loop, "json", RaisingJson(error))
    run = ToolRunner(data=data(), tolerance=0.0, max_output_chars=100_000, reraise=is_soft)
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        run("value_of_by_name", S1_2022)
    assert raised.value is error
    assert (run.records, run.unparsable_args) == ([], 0)


@pytest.mark.parametrize("injected", [False, True])
def test_an_argument_read_error_without_reraise_is_still_an_empty_object(
    monkeypatch: pytest.MonkeyPatch, injected: bool
) -> None:
    """기본값, 그리고 주입했어도 판별이 거짓인 예외 → 지금과 같이 {}·unparsable_args 1."""
    error: BaseException = ValueError("가상 읽기 오류") if injected else SoftTimeLimitExceeded("가상 시간 제한")
    monkeypatch.setattr(loop, "json", RaisingJson(error))
    run = ToolRunner(data=data(), tolerance=0.0, max_output_chars=100_000, **({"reraise": is_soft} if injected else {}))
    assert run("value_of_by_name", S1_2022) == '{"value": "N/A"}'
    assert run.unparsable_args == 1
    assert [record.args for record in run.records] == [{}]


def test_an_injected_reraise_lets_a_tool_error_out_of_the_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise error

    monkeypatch.setattr(dispatch, "tool_sum_check", boom)
    run = ToolRunner(data=data(), tolerance=0.0, max_output_chars=100_000, reraise=is_soft)
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        run("sum_check", '{"a": 1, "b": 2, "c": 3}')
    assert raised.value is error
    assert run.records == []


def test_parse_hints_with_an_injected_reraise_lets_the_error_out(monkeypatch: pytest.MonkeyPatch) -> None:
    error = SoftTimeLimitExceeded("가상 시간 제한")

    def boom(_text: str) -> Any:
        raise error

    monkeypatch.setattr(loop.ast, "literal_eval", boom)
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        parse_hints("['가상 산식']", reraise=is_soft)
    assert raised.value is error
    assert parse_hints("['가상 산식']") is None  # 기본값: 읽기 실패
    assert parse_hints("['가상 산식']", reraise=lambda e: isinstance(e, ValueError)) is None
