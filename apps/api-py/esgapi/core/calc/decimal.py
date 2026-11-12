"""십진 정확 연산. 값 = coef / 10^scale (coef 는 파이썬의 정수라 자릿수에 끝이 없다).

수량·금액·계수는 십진 문자열로 들어와 여기서만 연산된다. float 는 쓰지 않는다.
나눗셈이 없다: 식은 곱셈과 덧셈뿐이고 단위 환산도 곱셈 계수로 주어지므로 결과는 늘 유한 소수이고
중간 반올림이 없다. 반올림은 round_decimal 한 곳에만 있다.

표준 라이브러리의 decimal.Decimal 을 쓰지 않는 까닭: 그것은 문맥의 정밀도(기본 28자리)를 넘는 결과를
말없이 반올림한다. 여기 값은 「문자열까지 같아야」 하므로 반올림이 끼어들 자리를 아예 두지 않는다.
무효 조건: 나눗셈이 필요해지면(비율·평균) 이 꼴로는 못 한다. 그때 다시 정한다.

esg-lab `ts/kernel/src/decimal.ts` 를 옮긴 것이다(동작을 옮겼고 파일을 복사하지 않았다).

자리: 모듈들이 같이 쓰는 커널이라 core 에 있다(inventory 와 reconcile 이 쓴다. 밴드 PY8a 가 inventory/calc 에서 옮겼다).
옛 자리(inventory 의 calc 폴더)에 다시 내보내는 껍데기를 두지 않는다: 이름이 둘이면 다시 갈린다.
"""

import re
from dataclasses import dataclass
from typing import Final, Literal, TypeGuard

RoundingMode = Literal["half_up", "half_even", "down"]

# ASCII 숫자만 받는다. `\d` 는 파이썬에서 전각·아랍 숫자까지 받으므로 쓰지 않는다.
# `$` 는 끝의 줄바꿈 앞에서도 맞으므로 fullmatch 로 문자열 전체를 본다.
_DECIMAL_PATTERN: Final = re.compile(r"-?[0-9]+(\.[0-9]+)?")

# 바깥에서 온 수(행의 사용량, 기준정보 표의 값)의 글자 수 상한. 엔진이 자기가 낸 문자열을 다시 읽을 때는 걸지 않는다.
# 까닭: 파이썬은 4,300자리를 넘는 정수 ↔ 문자열 변환을 ValueError 로 막는다. 입력이 64자면 식 하나(곱 여덟 번쯤)의
# 결과는 수백 자리라 거기 닿지 않는다.
EXTERNAL_MAX_LENGTH: Final = 64


@dataclass(frozen=True, slots=True)
class Decimal:
    coef: int
    scale: int


ZERO: Final = Decimal(0, 0)


def is_decimal_string(text: object) -> TypeGuard[str]:
    return isinstance(text, str) and _DECIMAL_PATTERN.fullmatch(text) is not None


def _normalize(coef: int, scale: int) -> Decimal:
    """뒤의 0 을 지운다. 0 은 늘 (0, 0) 이다. 그래서 같은 값은 같은 (coef, scale) 이다."""
    if coef == 0:
        return ZERO
    while scale > 0 and coef % 10 == 0:
        coef //= 10
        scale -= 1
    return Decimal(coef, scale)


def parse_decimal(text: object) -> Decimal | None:
    """십진 문자열만 받는다. 지수 표기, 쉼표, 공백, `+` 부호, 빈 문자열, 전각 숫자, 문자열이 아닌 값은 None."""
    if not is_decimal_string(text):
        return None
    negative = text.startswith("-")
    body = text[1:] if negative else text
    int_part, _, frac_part = body.partition(".")
    try:
        coef = int(int_part + frac_part)
    except ValueError:
        # 4,300자리를 넘는 수(파이썬의 정수 변환 상한). 바깥 입력은 parse_external_decimal 이 64자에서 먼저 막는다.
        return None
    return _normalize(-coef if negative else coef, len(frac_part))


def parse_external_decimal(text: object) -> Decimal | None:
    """바깥에서 온 수를 읽는 자리에서 쓴다: parse_decimal 과 같되 64자를 넘으면 None."""
    if isinstance(text, str) and len(text) > EXTERNAL_MAX_LENGTH:
        return None
    return parse_decimal(text)


def format_decimal(d: Decimal) -> str:
    negative = d.coef < 0
    digits = str(-d.coef if negative else d.coef)
    sign = "-" if negative else ""
    if d.scale == 0:
        return sign + digits
    padded = digits.rjust(d.scale + 1, "0")
    return f"{sign}{padded[: len(padded) - d.scale]}.{padded[len(padded) - d.scale :]}"


def mul(a: Decimal, b: Decimal) -> Decimal:
    return _normalize(a.coef * b.coef, a.scale + b.scale)


def add(a: Decimal, b: Decimal) -> Decimal:
    scale = max(a.scale, b.scale)
    ac = a.coef * 10 ** (scale - a.scale)
    bc = b.coef * 10 ** (scale - b.scale)
    return _normalize(ac + bc, scale)


def is_negative(d: Decimal) -> bool:
    return d.coef < 0


def equals(a: Decimal, b: Decimal) -> bool:
    return a.coef == b.coef and a.scale == b.scale


def round_decimal(d: Decimal, digits: int, mode: RoundingMode) -> str:
    """유일한 반올림. 계산과 집계는 이 함수를 부르지 않는다.

    표시·보고 단계에서 부르는 쪽이 자릿수와 방식을 명시해 부른다.
    결과는 소수 `digits` 자리로 고정된 문자열이다 (예: digits=3 → "2.560").
    반올림은 절댓값에 하고 부호를 뒤에 붙인다: half_up 은 -2.5 → -3, down 은 -2.5 → -2.
    """
    if type(digits) is not int or digits < 0:
        raise ValueError(f"digits must be a non-negative integer: {digits}")
    if d.scale <= digits:
        coef = d.coef * 10 ** (digits - d.scale)
    else:
        divisor = 10 ** (d.scale - digits)
        negative = d.coef < 0
        magnitude = -d.coef if negative else d.coef
        quotient = magnitude // divisor
        twice_remainder = (magnitude % divisor) * 2
        if mode == "half_up":
            if twice_remainder >= divisor:
                quotient += 1
        elif mode == "half_even" and (twice_remainder > divisor or (twice_remainder == divisor and quotient % 2 == 1)):
            quotient += 1
        coef = -quotient if negative else quotient
    negative = coef < 0
    text = str(-coef if negative else coef).rjust(digits + 1, "0")
    sign = "-" if negative else ""
    if digits == 0:
        return sign + text
    return f"{sign}{text[: len(text) - digits]}.{text[len(text) - digits :]}"
