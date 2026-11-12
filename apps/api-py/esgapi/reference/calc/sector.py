"""사업장의 업종에서 CH4·N2O 계수의 부문을 정한다."""

import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, cast

from esgapi.reference.calc.types import AssemblyMapping, Json, Ok, SectorEntry, Step, fail, text_of

# 한국표준산업분류 코드: ASCII 숫자 2~5자리(앞 두 자리가 중분류).
_KSIC = re.compile(r"[0-9]{2,5}")


@dataclass(frozen=True)
class ResolvedSector:
    entry: SectorEntry
    # 근거: {key, label, basis: input | ksic_division | ksic_exception, ksicCode, locator}
    evidence: Json


def _evidence(entry: SectorEntry, basis: str, ksic_code: str | None, locator: str) -> Json:
    return {"key": entry.key, "label": entry.label, "basis": basis, "ksicCode": ksic_code, "locator": locator}


def resolve_sector(industry: object, mapping: AssemblyMapping) -> Step[ResolvedSector]:
    """부문을 직접 받거나 업종 코드에서 정한다.

    한 중분류 코드가 두 부문에 적혀 있으면(38, 58, 59) 고르지 않는다. 원문 주석이 더 자세한 코드로 부문을 정해 준
    경우에만 그 부문을 쓰고, 아니면 실패로 돌려 부문을 직접 받게 한다.
    """
    missing = fail("missing_input", field="industry", reason="사업장의 부문도 업종 코드도 없다 (기본값 없음)")
    if not isinstance(industry, Mapping):
        return missing
    given = cast(Mapping[str, Any], industry)
    sector: object = given.get("sector")
    ksic_code: object = given.get("ksicCode")

    def by_key(key: str) -> SectorEntry | None:
        return next((entry for entry in mapping.sectors if entry.key == key), None)

    if sector is not None:
        if ksic_code is not None:
            return fail(
                "invalid_input",
                field="industry",
                value=f"{text_of(sector)} + {text_of(ksic_code)}",
                reason="부문과 업종 코드 가운데 하나만 준다",
            )
        entry = by_key(sector) if isinstance(sector, str) else None
        if entry is None:
            return fail(
                "invalid_input",
                field="industry.sector",
                value=text_of(sector),
                reason=f"부문 키는 {', '.join(s.key for s in mapping.sectors)} 중 하나다",
            )
        return Ok(ResolvedSector(entry, _evidence(entry, "input", None, entry.locator)))

    if ksic_code is None:
        return missing
    if not isinstance(ksic_code, str) or _KSIC.fullmatch(ksic_code) is None:
        return fail(
            "invalid_input",
            field="industry.ksicCode",
            value=text_of(ksic_code),
            reason="한국표준산업분류 코드는 숫자 2~5자리 문자열이다 (앞 두 자리가 중분류)",
        )
    division = ksic_code[:2]
    holders = [entry for entry in mapping.sectors if division in entry.ksic_divisions]
    if not holders:
        return fail("sector_not_defined", ksicCode=ksic_code, division=division)
    if len(holders) == 1:
        only = holders[0]
        return Ok(ResolvedSector(only, _evidence(only, "ksic_division", ksic_code, only.locator)))

    overlap = next((entry for entry in mapping.sector_overlaps if entry.division == division), None)
    exceptions = overlap.exceptions if overlap is not None else ()
    matched = [exception for exception in exceptions if ksic_code.startswith(exception.code_prefix)]
    if overlap is not None and len(matched) == 1:
        entry = by_key(matched[0].sector)
        if entry is not None:
            locator = f"{overlap.locator}: {matched[0].raw}"
            return Ok(ResolvedSector(entry, _evidence(entry, "ksic_exception", ksic_code, locator)))
    return fail(
        "sector_ambiguous",
        ksicCode=ksic_code,
        division=division,
        candidates=[holder.key for holder in holders],
        notes=[item.raw for item in exceptions],
        locator=overlap.locator if overlap is not None else " / ".join(holder.locator for holder in holders),
    )
