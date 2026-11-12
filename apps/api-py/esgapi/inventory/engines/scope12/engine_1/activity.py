"""바깥에서 온 활동 데이터 행(JSON 을 읽은 값)을 계산 함수가 받는 dataclass 로 바꾼다. 행 검사 층이다.

꼴이 틀린 행은 예외가 아니라 `invalid_activity` 로 실패한 행이 된다(다른 행의 계산을 막지 않는다).
esg-lab `ts/ghg-calc/src/calc.ts` 의 calculateRow 머리(배출원 유형·사용량 검사)를 옮기고, TS 가 타입을 믿고
넘기던 칸(문자열이어야 할 칸에 수가 온 것 등)을 여기서 실패로 가른다.
"""

from esgapi.core.calc.decimal import Decimal, is_negative, parse_external_decimal
from esgapi.inventory.engines.scope12.engine_1.types import (
    SCOPE_OF,
    ActivityRow,
    InvalidActivity,
    ParameterTiers,
    RowFailed,
    SourceType,
)
from esgapi.inventory.tools.jsrepr import MISSING, as_integer, as_object, get, js_json, js_string

_OPTIONAL_TEXT_KEYS = ("fuel", "factorId", "sector", "facilityUse", "variant")


def _as_source_type(value: object) -> SourceType | None:
    return next((known for known in SCOPE_OF if known == value), None) if isinstance(value, str) else None


def _or_empty(value: object) -> object:
    """JS 의 `value ?? ""`."""
    return "" if value is None or value is MISSING else value


def check_amount(amount: str) -> Decimal | InvalidActivity:
    """사용량은 음이 아닌 십진 문자열이다(64자까지)."""
    parsed = parse_external_decimal(amount)
    if parsed is None:
        return InvalidActivity(field="amount", value=amount, reason="십진 문자열이 아니다")
    if is_negative(parsed):
        return InvalidActivity(field="amount", value=amount, reason="음수 사용량")
    return parsed


def _tiers(value: object) -> ParameterTiers | None:
    obj = as_object(value)
    if obj is None:
        return None
    calorific, co2, non_co2 = (as_integer(get(obj, key)) for key in ("calorific", "co2", "nonCo2"))
    oxidation = get(obj, "oxidation")
    oxidation_tier = None if oxidation is None else as_integer(oxidation)
    if calorific is None or co2 is None or non_co2 is None or (oxidation is not None and oxidation_tier is None):
        return None
    return ParameterTiers(calorific=calorific, co2=co2, non_co2=non_co2, oxidation=oxidation_tier)


def check_activity_row(raw: object) -> ActivityRow | RowFailed:
    # 바깥 JSON 에서 온 행은 꼴을 믿을 수 없다. 배출원 유형을 모르면 어떤 계수로도 계산하지 않는다.
    obj = as_object(raw)
    source_type = _as_source_type(get(obj, "sourceType")) if obj is not None else None
    if obj is None or source_type is None:
        loose = obj if obj is not None else {}
        return RowFailed(
            row_id=js_string(_or_empty(get(loose, "id"))),
            org_unit=js_string(_or_empty(get(loose, "orgUnit"))),
            period=js_string(_or_empty(get(loose, "period"))),
            scope=None,
            source_type=None,
            failure=InvalidActivity(
                field="sourceType",
                value=js_string(_or_empty(get(loose, "sourceType"))),
                reason="알 수 없는 배출원 유형이거나 행이 객체가 아니다",
            ),
        )

    def failed(field: str, value: str, reason: str) -> RowFailed:
        return RowFailed(
            row_id=js_string(_or_empty(get(obj, "id"))),
            org_unit=js_string(_or_empty(get(obj, "orgUnit"))),
            period=js_string(_or_empty(get(obj, "period"))),
            scope=SCOPE_OF[source_type],
            source_type=source_type,
            failure=InvalidActivity(field=field, value=value, reason=reason),
        )

    row_id, org_unit, period, amount, unit = (get(obj, key) for key in ("id", "orgUnit", "period", "amount", "unit"))
    if not isinstance(row_id, str):
        return failed("id", js_string(row_id), "문자열이 아니다")
    if not isinstance(org_unit, str):
        return failed("orgUnit", js_string(org_unit), "문자열이 아니다")
    if not isinstance(period, str):
        return failed("period", js_string(period), "문자열이 아니다")
    # 사용량: 수(JSON number)로 적힌 것도 거부한다. 문자열만 받는다.
    if not isinstance(amount, str):
        return failed("amount", js_string(amount), "십진 문자열이 아니다")
    checked_amount = check_amount(amount)
    if isinstance(checked_amount, InvalidActivity):
        return failed(checked_amount.field, checked_amount.value, checked_amount.reason)
    if not isinstance(unit, str):
        return failed("unit", js_string(unit), "문자열이 아니다")

    # 선택 칸: 없으면 키를 뺀다. null 은 「없음」이 아니다.
    texts: dict[str, str] = {}
    for key in _OPTIONAL_TEXT_KEYS:
        value = get(obj, key)
        if value is MISSING:
            continue
        if not isinstance(value, str):
            return failed(key, js_string(value), "문자열이 아니다 (없으면 키를 뺀다)")
        texts[key] = value

    factor_year: int | None = None
    if "factorYear" in obj:
        factor_year = as_integer(obj["factorYear"])
        if factor_year is None:
            return failed("factorYear", js_string(obj["factorYear"]), "정수가 아니다 (없으면 키를 뺀다)")

    parameter_tiers: ParameterTiers | None = None
    if "parameterTiers" in obj:
        parameter_tiers = _tiers(obj["parameterTiers"])
        if parameter_tiers is None:
            return failed(
                "parameterTiers",
                js_json(obj["parameterTiers"]),
                "산정등급 넷(calorific·co2·nonCo2 는 정수, oxidation 은 정수나 null)을 적은 객체가 아니다",
            )

    return ActivityRow(
        id=row_id,
        org_unit=org_unit,
        period=period,
        source_type=source_type,
        amount=amount,
        unit=unit,
        fuel=texts.get("fuel"),
        factor_year=factor_year,
        factor_id=texts.get("factorId"),
        sector=texts.get("sector"),
        parameter_tiers=parameter_tiers,
        facility_use=texts.get("facilityUse"),
        variant=texts.get("variant"),
    )
