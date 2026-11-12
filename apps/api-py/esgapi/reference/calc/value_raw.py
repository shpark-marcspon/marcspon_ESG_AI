"""낱줄의 `value_raw`(출처 표기 그대로의 글자)를 엔진이 받는 십진 문자열로 바꾼다. float 를 거치지 않는다.

규칙(TS `readValueRaw` 그대로):
  (1) 이미 십진 표기면 그대로            35.2 → "35.2",  43.0 → "43.0"
  (2) 세 자리 쉼표 표기면 쉼표만 걷는다   73,200 → "73200"
  (3) 그 밖은 전부 None — 지수 표기, 공백, 부호 `+`, 단위가 붙은 값, 자리가 틀린 쉼표, 빈 문자열, `-`, 전각 숫자.
      음수도 None 이다: 계수·발열량·산화계수에 음수는 있을 수 없다.

★ esg-lab 의 적재기(`py/factors/record.py` 의 `parse_number`)는 지수 표기와 음수를 받아 `value`(float)를 만든다.
  조립은 그 `value` 를 읽지 않는다. 두 규칙이 갈리는 낱줄은 여기서 `invalid_value_raw` 로 멈춘다.
"""

import re

# 숫자는 ASCII 0-9 만이다(`\\d` 는 파이썬에서 전각 숫자 「７」 도 받는다). fullmatch 라 끝의 줄바꿈도 받지 않는다.
_DECIMAL = re.compile(r"-?[0-9]+(\.[0-9]+)?")
# 세 자리마다 쉼표를 찍은 표기(73,200 / 1,234,567.8). 쉼표 자리가 틀린 것(1,2 / 73,20)은 받지 않는다.
_GROUPED = re.compile(r"[0-9]{1,3}(,[0-9]{3})+(\.[0-9]+)?")


def read_value_raw(raw: object) -> str | None:
    if not isinstance(raw, str):
        return None
    if _DECIMAL.fullmatch(raw) is not None:
        return None if raw.startswith("-") else raw
    if _GROUPED.fullmatch(raw) is not None:
        return raw.replace(",", "")
    return None
