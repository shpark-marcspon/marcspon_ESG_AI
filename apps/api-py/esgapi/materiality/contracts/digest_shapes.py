"""둘째 결과 꼴 materiality.digest@1 — 중대성평가 IRO 실행 하나의 작은 요약(밴드 IR3c, 데이터 검증 DV1g 선례).

흐름(flows/iro_155.py report_iro)이 결과 materiality.result@2 곁에 둘째 결과로 남긴다. 결과 본문(1부 조사 글·2부 모델
답 전부)을 목록 화면(GET /materiality/runs)이 읽지 않게 하려는 것이다 — 목록은 이것만 읽는다. 값은 결과에서 셈한
것뿐이다(셈은 outputs/digest.py — 이 파일에 로직은 없다). 결과 본문은 바이트 그대로다(MARC-ENT-442).

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 고정 파일은
tests/data/flow-shapes/materiality.digest@1.schema.json.
칸을 더하는 것은 @1 안, 빼거나 바꾸면 @2 다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.materiality.contracts.shapes import FORBID, Count

DIGEST_SHAPE: Final = "materiality.digest@1"


@with_config(FORBID)
class MaterialityDigest(TypedDict):
    """materiality.digest@1 — 중대성평가 IRO 실행 하나의 요약."""

    schemaVersion: Literal["materiality.digest@1"]
    impactRows: Count | None
    """환경·사회 영향 줄 수 — 서브토픽마다 impact 가 done 인 것의 rows 를 더한 수(최종 엑셀 「2-1. 환경사회 영향
    식별」 시트의 데이터 줄 수). 2부를 돌리지 않았으면(part2 not_run) null."""
    pathwayRows: Count | None
    """재무 영향 경로 줄 수 — 서브토픽마다 pathway 가 done 인 것의 rows 를 더한 수(최종 엑셀 「2-2. 재무 영향 식별」
    시트의 데이터 줄 수). 2부를 돌리지 않았으면 null."""


DIGEST_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    DIGEST_SHAPE: TypeAdapter[MaterialityDigest](
        Annotated[MaterialityDigest, Field(title=DIGEST_SHAPE, description="중대성평가 IRO 한 건의 요약.")]
    )
}
"""꼴 id → 검사기. validate_python(요약, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
