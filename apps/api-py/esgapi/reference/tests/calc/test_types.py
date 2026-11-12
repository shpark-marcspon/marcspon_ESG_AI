"""조립 결과의 JSON 꼴(`result_to_json`)과 실패에 싣는 「받은 값」의 글자(`text_of`). 순수 층.

`result_to_json` 은 API 가 내보내는 꼴이다(`service` 가 `FailureOut` 으로 옮긴다). 실패 쪽 갈래를 타는 순수 시험이
따로 없으면 주간 변이 실행(DB 를 쓰는 시험을 빼고 돈다)이 이 함수의 변이를 못 본다.
"""

from esgapi.reference.calc.types import Assembled, Failed, Ok, fail, result_to_json, text_of
from esgapi.reference.tests.helpers import assemble, value_of


def test_a_failure_is_ok_false_and_the_failure_with_its_kind_first() -> None:
    out = result_to_json(fail("missing_input", field="fuel", reason="국내 연료명이 없다"))
    assert out == {"ok": False, "failure": {"kind": "missing_input", "field": "fuel", "reason": "국내 연료명이 없다"}}
    assert list(out) == ["ok", "failure"]
    assert out["ok"] is False
    assert list(out["failure"]) == ["kind", "field", "reason"]


def test_an_assembled_factor_is_ok_true_and_the_factor_with_its_evidence() -> None:
    result = assemble()
    done = value_of(result)
    out = result_to_json(result)
    assert out == {"ok": True, "value": {"factor": done.factor, "evidence": done.evidence}}
    assert list(out) == ["ok", "value"]
    assert out["ok"] is True
    assert list(out["value"]) == ["factor", "evidence"]
    # 직접 지은 값으로도 같은 꼴
    built = Ok(Assembled(factor={"id": "synthetic"}, evidence={"note": "가"}))
    assert result_to_json(built) == {"ok": True, "value": {"factor": {"id": "synthetic"}, "evidence": {"note": "가"}}}
    assert isinstance(fail("record_not_found"), Failed)
    assert result_to_json(fail("record_not_found")) == {"ok": False, "failure": {"kind": "record_not_found"}}


def test_text_of_writes_each_kind_of_value() -> None:
    """글자는 그대로, 그 밖은 JSON 표기(빈칸 없음, 한글 그대로). JSON 이 못 적는 값은 repr."""
    assert text_of("가") == "가"
    assert text_of("") == ""
    assert text_of(None) == "null"
    assert text_of(True) == "true"
    assert text_of(False) == "false"
    assert text_of(1) == "1"
    assert text_of(0) == "0"
    assert text_of(1.5) == "1.5"
    assert text_of({"a": [1, "가"]}) == '{"a":[1,"가"]}'
    assert text_of({"a": 1, "b": None}) == '{"a":1,"b":null}'
    assert text_of(["가", 2.0]) == '["가",2.0]'
    assert text_of(("가",)) == '["가"]'
    assert text_of({1, 2}) == "{1, 2}"
    assert text_of(b"x") == "b'x'"
