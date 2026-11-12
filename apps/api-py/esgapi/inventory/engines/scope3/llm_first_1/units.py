"""단위의 차원과 환산. 환산 계수는 정의상 정확한 값(1 t = 1000 kg)뿐이고 여기 말고는 두지 않는다.

차원이 다르면 환산하지 않는다(예: 개수 → 무게). 그런 행은 활동 기반 후보가 없는 것으로 보고 지출 기반으로 넘긴다.
esg-lab `ts/scope3/src/domain/units.ts` 를 옮긴 것이다.
"""

import unicodedata
from typing import TYPE_CHECKING, Final, Literal

if TYPE_CHECKING:
    from esgapi.inventory.engines.scope3.llm_first_1.types import TransportInfo

UnitDim = Literal[
    "kg",
    "tonne",
    "km",
    "mile",
    "passenger_km",
    "tonne_km",
    "room_night",
    "fte_hour",
    "kwh",
    "mj",
    "m3",
    "megalitre",
    "m2",
    "ea",
    "usd_2022_purchaser",
    "unknown",
]

_ALIASES: Final[dict[UnitDim, tuple[str, ...]]] = {
    "kg": ("kg", "킬로그램", "키로"),
    "tonne": ("t", "ton", "tons", "tonne", "tonnes", "톤"),
    "km": ("km", "킬로미터"),
    "mile": ("mile", "miles", "마일"),
    "passenger_km": ("passenger.km", "pkm", "인km", "인·km", "인.km"),
    "tonne_km": ("tonne.km", "ton.km", "tkm", "톤km", "톤·km", "톤.km"),
    "room_night": ("room per night", "room night", "박", "객실박"),
    "fte_hour": ("per fte working hour", "fte시간", "fte hour"),
    "kwh": ("kwh",),
    "mj": ("mj",),
    "m3": ("m3", "㎥", "m³", "cubic metres", "세제곱미터"),
    "megalitre": ("million litres",),
    "m2": ("m2", "㎡", "m²"),
    "ea": ("ea", "개"),
    "usd_2022_purchaser": ("2022 usd, purchaser price",),
}

_LOOKUP: Final[dict[str, UnitDim]] = {name: dim for dim, names in _ALIASES.items() for name in names}

# JS 의 String.prototype.trim 이 떼는 글자(WhiteSpace + LineTerminator). 파이썬의 str.strip() 은 범위가 다르다:
# 그것은 U+001C~U+001F·U+0085 도 떼고 U+FEFF 는 떼지 않는다. 그래서 글자 집합을 직접 적는다.
_JS_WHITESPACE: Final = "\t\n\x0b\x0c\r \xa0                　﻿"


def js_trim(text: str) -> str:
    """JS 의 `text.trim()`."""
    return text.strip(_JS_WHITESPACE)


def unit_dim(text: str | None) -> UnitDim:
    """단위 표기를 차원으로 바꾼다. 모르는 표기(대, 식, 건, box 등)는 "unknown" 이다."""
    if text is None:
        return "unknown"
    return _LOOKUP.get(js_trim(unicodedata.normalize("NFKC", text)).lower(), "unknown")


def conversion_factor(source: UnitDim, target: UnitDim) -> str | None:
    """`source` 단위의 양에 곱하면 `target` 단위의 양이 되는 계수(십진 문자열). 환산할 수 없으면 None."""
    if source == "unknown" or target == "unknown":
        return None
    if source == target:
        return "1"
    if source == "kg" and target == "tonne":
        return "0.001"
    if source == "tonne" and target == "kg":
        return "1000"
    return None


def activity_dim(unit: str | None, transport: "TransportInfo | None") -> UnitDim:
    """행의 활동량이 어떤 단위 차원인지. 운송 행에 무게가 있으면 톤·km 이다. 숫자를 읽지 않는다."""
    if transport is not None and transport.weight_kg is not None:
        return "tonne_km"
    return unit_dim(unit)
