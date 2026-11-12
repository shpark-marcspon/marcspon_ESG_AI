"""`value_raw` 읽기. 순수 층. TS 원본 `files.test.ts` 의 「value_raw 읽기」 셋(`it` 2 + `it.each` 1)을 옮겼다."""

import pytest

from esgapi.reference.calc import read_value_raw


def test_decimal_stays_and_grouped_commas_are_removed() -> None:
    assert read_value_raw("35.2") == "35.2"
    assert read_value_raw("43.0") == "43.0"
    assert read_value_raw("0") == "0"
    assert read_value_raw("73,200") == "73200"
    assert read_value_raw("1,234,567.89") == "1234567.89"


# TS 의 15개
TS_REJECTED = ["", "-", "1,2", "73,20", "7,3200", ",200", "1.2.3", "7e4", " 73200", "+1", "-1", "-1,000"]
TS_REJECTED_TAIL = ["0.99 ", "약 1", "1,000,00"]
# 파이썬에서만 생기는 구멍: `$` 는 끝의 줄바꿈 앞에서도 맞고, `\d` 는 전각·다른 문자의 숫자도 받는다
PYTHON_HOLES = ["73200\n", "７３２００", "٣", "7.32E4", "1e-3"]


@pytest.mark.parametrize("raw", [*TS_REJECTED, *TS_REJECTED_TAIL, *PYTHON_HOLES])
def test_everything_else_is_none(raw: str) -> None:
    assert read_value_raw(raw) is None


def test_non_strings_are_none() -> None:
    """문자열이 아니면 None(숫자를 받지 않는다)."""
    assert read_value_raw(73200) is None
    assert read_value_raw(73200.0) is None
    assert read_value_raw(None) is None


def test_the_rejections_named_in_the_rule() -> None:
    """거부 일곱 갈래: 지수 표기, 공백, 부호 +, 단위가 붙은 값, 자리가 틀린 쉼표, 빈 문자열(과 `-`), 음수."""
    rejected = {
        "지수 표기": "7.32e4",
        "공백": "73 200",
        "부호 +": "+73200",
        "단위가 붙은 값": "73200 kg",
        "자리가 틀린 쉼표": "73,20",
        "빈 문자열": "",
        "음수": "-73200",
    }
    assert {name: read_value_raw(raw) for name, raw in rejected.items()} == dict.fromkeys(rejected)
