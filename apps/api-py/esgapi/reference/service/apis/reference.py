"""기준정보의 경로 넷. config/api.py 가 이 router 를 /reference 아래에 걸어 두었다.

    GET  /reference/sources                 출처 전부와 이용 조건
    GET  /reference/factors                 낱줄 찾기(걸러서, 쪽 나눠)
    POST /reference/assemble                고정연소 계수 한 건을 조립
    POST /reference/assemble-electricity    구매 전력 계수 한 건을 조립

전부 읽기다(쓰기 경로가 없다. 계수는 주인 역할의 관리 명령만 들인다). 세션이 있어야 하고 역할은 가리지 않는다
(viewer 도 읽는다). 기준정보는 전역 자료라 테넌트와 무관하게 같은 답이 나간다.
models 를 직접 import 하지 않는다(`.importlinter` 계약 라).
"""

from typing import Any

from django.http import HttpRequest
from ninja import Query, Router

from esgapi.core.auth.bearer import company_scoped_auth_or_next, permitted
from esgapi.core.exceptions import ApplicationError
from esgapi.core.schemas import TOKEN_BODY_ERROR_RESPONSES, TOKEN_ERROR_RESPONSES, limit_offset_page
from esgapi.reference.calc.types import result_to_json
from esgapi.reference.licenses import DEFAULT_LICENSES, LicenseListInvalid, parse_license_list
from esgapi.reference.service.schemas.reference import (
    AssembleElectricityOut,
    AssembleIn,
    AssembleOut,
    ElectricityIn,
    FactorQuery,
    FactorsOut,
    SourceOut,
    SourcesOut,
)
from esgapi.reference.service.selectors import reference as selectors
from esgapi.reference.service.selectors.reference import FactorView, MappingAbsent, MappingAmbiguous, SourceView
from esgapi.reference.service.services import reference as services
from esgapi.user.service.apis.auth import session_cookie

router = Router()


def _source_out(source: SourceView) -> SourceOut:
    return SourceOut(
        id=source.id,
        name=source.name,
        publisher=source.publisher,
        url=source.url,
        version=source.version,
        retrieved=source.retrieved,
        fileName=source.file_name,
        fileSha256=source.file_sha256,
        licenseName=source.license_name,
        licenseUrl=source.license_url,
        licenseNote=source.license_note,
        licenseStatus=source.license_status,  # pyright: ignore[reportArgumentType]  DB 의 CHECK 가 셋으로 묶는다
        recordCount=source.record_count,
    )


def _factor_out(factor: FactorView) -> dict[str, Any]:
    # dict 로 내보내 응답 스키마(FactorOut)가 꼴을 본다: DB 에 스키마 밖의 값이 들어 있으면 여기서 드러난다.
    return {
        "id": factor.id,
        "sourceId": factor.source_id,
        "licenseStatus": factor.license_status,
        "licenseNote": factor.license_note,
        "locator": factor.locator,
        "recordType": factor.record_type,
        "scope": factor.scope,
        "scope3Categories": list(factor.scope3_categories),
        "scope3MappingBasis": factor.scope3_mapping_basis,
        "factorType": factor.factor_type,
        "nameOriginal": factor.name_original,
        "nameKo": factor.name_ko,
        "nameEn": factor.name_en,
        "categoryPath": list(factor.category_path),
        "classification": factor.classification,
        "value": factor.value,
        "valueRaw": factor.value_raw,
        "valueStatus": factor.value_status,
        "unit": factor.unit,
        "unitNumerator": factor.unit_numerator,
        "unitDenominator": factor.unit_denominator,
        "gas": factor.gas,
        "gasBasis": factor.gas_basis,
        "heatingValueBasis": factor.heating_value_basis,
        "conditions": factor.conditions,
        "region": factor.region,
        "year": factor.year,
        "spend": factor.spend,
        "synthetic": factor.synthetic,
    }


@router.get(
    "/sources",
    response={200: SourcesOut, **TOKEN_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    operation_id="reference_sources",
    tags=["기준정보"],
)
def sources(request: HttpRequest) -> SourcesOut:
    """출처 전부. 이용 조건 상태(licenseStatus)와 덧붙인 말(licenseNote)이 늘 같이 나간다. disputed 인 출처도 보인다."""
    permitted(request, "reference_sources")
    return SourcesOut(sources=[_source_out(source) for source in selectors.list_sources()])


@router.get(
    "/factors",
    response={200: FactorsOut, **TOKEN_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    operation_id="reference_factors",
    tags=["기준정보"],
)
def factors(request: HttpRequest, query: Query[FactorQuery]) -> dict[str, Any]:
    """낱줄을 찾는다. 조건은 전부 「같다」이고 `q` 만 부분 일치다. id 순이다(검색 순위가 없다).

    ★ `license` 를 주지 않으면 ok·unverified 만 낸다. disputed 를 명시해 들인 DB 에서도 그렇다.
    """
    permitted(request, "reference_factors")
    try:
        licenses = DEFAULT_LICENSES if query.license is None else parse_license_list(query.license)
    except LicenseListInvalid as err:
        raise ApplicationError("invalid_input", "invalid_input", f"요청의 꼴이 틀렸다: {err}") from err
    page = selectors.find_factors(
        licenses=licenses,
        source=query.source,
        record_type=query.record_type_given,
        scope=query.scope,
        gas=query.gas,
        q=query.q,
        limit=query.limit,
        offset=query.offset,
    )
    results = [_factor_out(item) for item in page.items]
    return {
        **limit_offset_page(page.total, query.offset, results),
        "licenses": sorted(licenses),
        # 옛 넷 — 같은 값을 한 판 함께 싣는다(deprecated, C1 이 걷는다)
        "total": page.total,
        "limit": query.limit,
        "offset": query.offset,
        "items": results,
    }


def _assembly_out(outcome: services.AssemblyOutcome) -> dict[str, Any]:
    if isinstance(outcome, MappingAbsent):
        raise ApplicationError(
            "unavailable", "reference_not_loaded", "기준정보가 들어와 있지 않다(관리자가 import_factors 를 돌려야 한다)"
        )
    if isinstance(outcome, MappingAmbiguous):
        raise ApplicationError(
            "conflict", "mapping_ambiguous", f"대응표가 둘 이상이다({', '.join(outcome.versions)}). 고를 입력이 없다"
        )
    licenses = [
        {
            "sourceId": source.id,
            "licenseStatus": source.license_status,
            "licenseName": source.license_name,
            "licenseUrl": source.license_url,
            "licenseNote": source.license_note,
        }
        for source in outcome.sources
    ]
    return {**result_to_json(outcome.result), "licenses": licenses}


# exclude_unset: 조립이 싣지 않은 칸(facilityUse, year, 실패일 때의 value …)은 null 로 채우지 않고 아예 뺀다.
# 조립이 null 로 실은 칸(nameMapping, locator, co2eGwp …)은 그대로 null 이다. TS 조립기의 JSON 과 같아진다.


@router.post(
    "/assemble",
    response={200: AssembleOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    operation_id="reference_assemble",
    exclude_unset=True,
    tags=["기준정보"],
)
def assemble(request: HttpRequest, body: AssembleIn) -> dict[str, Any]:
    """고정연소 계수 한 건을 지침의 규칙대로 조립한다. 못 하면 200 에 `{ok: false, failure}` 로 까닭을 답한다.

    기본값이 없다: 연료·업종·산정등급이 빠지면 `missing_input` 이고, 낱줄이 없거나 둘이면 고르지 않는다.
    """
    permitted(request, "reference_assemble")
    return _assembly_out(services.assemble_combustion(body.model_dump(exclude_none=True)))


@router.post(
    "/assemble-electricity",
    response={200: AssembleElectricityOut, **TOKEN_BODY_ERROR_RESPONSES},
    auth=[company_scoped_auth_or_next, session_cookie],
    operation_id="reference_assemble_electricity",
    exclude_unset=True,
    tags=["기준정보"],
)
def assemble_electricity(request: HttpRequest, body: ElectricityIn) -> dict[str, Any]:
    """구매 전력 계수 한 건을 조립한다. 어느 계수를 쓸지(표-69 / GIR 공표, 판·기간·발전단/소비단)는 전부 입력이다."""
    permitted(request, "reference_assemble_electricity")
    return _assembly_out(services.assemble_electricity(body.model_dump(exclude_none=True, by_alias=True)))
