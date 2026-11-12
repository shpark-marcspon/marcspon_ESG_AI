"""정책: 「어느 산정등급을 쓰는가」를 지침에서 끌어내는 부분. 낱줄을 고르는 일은 하지 않는다(assemble.py)."""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Final, Literal, cast

from esgapi.reference.calc.types import AssemblyMapping, FacilityGroup, FuelState, Ok, Step, fail, text_of

# 규칙의 근거 자리(지침 원문). 값이 아니라 조문 위치다.
RULES: Final = {
    "nonCo2TierOne": "별표 6 고정연소 각 절 「3. 보고대상 온실가스」 표: CH4·N2O 의 산정방법론은 Tier 1 뿐이다",
    "oxidationFollowsCo2": (
        "별표 6 고정연소 각 절 「4. 배출량 산정방법론」: 산화계수는 CO2 배출계수와 동일한 산정등급을 사용하여야 한다"
    ),
    "siteValues": (
        "별표 6 고정연소 각 절 「5. 매개변수별 관리기준」 Tier 3: 사업자가 개발하거나 공급자가 분석한 값 (제16조), "
        "Tier 4: 연속측정"
    ),
}

_GROUPS: Final[tuple[str, ...]] = ("A", "B", "C")
# 그룹 최소기준에서 읽는 매개변수: 대응표의 이름 → 엔진의 자리.
_MINIMUM_PARAMETERS: Final = (("순발열량", "calorific"), ("배출계수", "co2"), ("산화계수", "oxidation"))
_SLOTS: Final = ("calorific", "co2", "oxidation")


def is_tier(value: object) -> bool:
    """1~4 의 정수. `True`(파이썬에서 1 과 같다)와 "2"(글자)는 등급이 아니다."""
    return type(value) is int and value in (1, 2, 3, 4)


@dataclass(frozen=True)
class ResolvedTiers:
    # 엔진의 ParameterTiers 와 같은 꼴: {calorific, co2, nonCo2, oxidation}
    values: dict[str, int]
    basis: Literal["explicit", "group_minimum"]
    group: FacilityGroup | None
    locators: list[str]


def resolve_tiers(policy: object, fuel_state: FuelState, mapping: AssemblyMapping) -> Step[ResolvedTiers]:
    """정책을 매개변수별 산정등급으로 푼다.

    조립은 고시의 표에서 값을 가져오므로 Tier 1·2 만 조립할 수 있다. Tier 3·4 는 사업장이 가진 값이 있어야 해서
    실패로 돌려준다.
    """
    if not isinstance(policy, Mapping):
        return fail("missing_input", field="tiers", reason="적용할 산정등급을 정하지 않았다 (기본값 없음)")
    given = cast(Mapping[str, Any], policy)
    kind = given.get("kind")

    chosen: dict[str, int] = {}
    basis: Literal["explicit", "group_minimum"]
    group: FacilityGroup | None = None
    locators: list[str] = []

    if kind == "explicit":
        for slot in _SLOTS:
            if given.get(slot) is None:
                return fail("missing_input", field=f"tiers.{slot}", reason="매개변수별 산정등급이 빠졌다 (기본값 없음)")
            if not is_tier(given[slot]):
                return fail(
                    "invalid_input",
                    field=f"tiers.{slot}",
                    value=text_of(given[slot]),
                    reason="산정등급은 1~4 의 정수다",
                )
        non_co2 = given.get("nonCo2")
        if non_co2 is not None and not (type(non_co2) is int and non_co2 == 1):
            return fail(
                "tier_combination_invalid",
                reason=f"CH4·N2O 에 Tier {text_of(non_co2)} 은 없다",
                locator=RULES["nonCo2TierOne"],
            )
        chosen = {slot: given[slot] for slot in _SLOTS}
        basis = "explicit"
    elif kind == "group_minimum":
        given_group = given.get("group")
        if given_group is None:
            return fail("missing_input", field="tiers.group", reason="시설 규모 그룹(A·B·C)이 빠졌다 (기본값 없음)")
        if not isinstance(given_group, str) or given_group not in _GROUPS:
            return fail(
                "invalid_input",
                field="tiers.group",
                value=text_of(given_group),
                reason="시설 규모 그룹은 A, B, C 중 하나다",
            )
        group = given_group
        for parameter, slot in _MINIMUM_PARAMETERS:
            found = [
                entry
                for entry in mapping.tier_minimums
                if entry.activity == "고정연소"
                and entry.fuel_state == fuel_state
                and entry.parameter == parameter
                and entry.group == group
            ]
            # 정확히 하나여야 한다. 없거나 둘이면 고르지 않는다.
            if len(found) != 1 or not is_tier(found[0].tier):
                return fail(
                    "tier_minimum_not_found", fuelState=fuel_state, group=group, parameter=parameter, found=len(found)
                )
            only = found[0]
            chosen[slot] = only.tier
            locators.append(f"별표 5 {only.locator} → Tier {only.tier}")
        basis = "group_minimum"
    elif kind is None:
        return fail(
            "missing_input",
            field="tiers.kind",
            reason="산정등급을 직접 줄지(explicit) 그룹 최소기준을 따를지(group_minimum) 정하지 않았다",
        )
    else:
        return fail("invalid_input", field="tiers.kind", value=text_of(kind), reason="explicit 또는 group_minimum")

    # 산화계수는 CO2 배출계수와 같은 등급이어야 한다(별표 6).
    if chosen["co2"] != chosen["oxidation"]:
        return fail(
            "tier_combination_invalid",
            reason=f"CO2 배출계수는 Tier {chosen['co2']} 인데 산화계수는 Tier {chosen['oxidation']} 이다",
            locator=RULES["oxidationFollowsCo2"],
        )
    for parameter, slot in (("발열량", "calorific"), ("CO2 배출계수", "co2"), ("산화계수", "oxidation")):
        if chosen[slot] >= 3:
            return fail("tier_requires_site_values", parameter=parameter, tier=chosen[slot], reason=RULES["siteValues"])
    locators.append(RULES["nonCo2TierOne"])
    values = {"calorific": chosen["calorific"], "co2": chosen["co2"], "nonCo2": 1, "oxidation": chosen["oxidation"]}
    return Ok(ResolvedTiers(values=values, basis=basis, group=group, locators=locators))
