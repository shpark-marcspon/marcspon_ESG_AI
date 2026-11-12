"""둘째 결과 꼴 dataverify.digest@1 — 데이터 검증 실행 하나의 작은 요약(밴드 DV1g, MARC-ENT-392 의 영문번역 선례).

흐름(flows/colab_156.py report)이 결과 dataverify.result@2 곁에 둘째 결과로 남긴다. 결과 본문(검토 리포트 글·검사
기록 전부)을 목록 화면(GET /dataverify/runs)이 읽지 않게 하려는 것이다. 값은 결과에서 셈한 것뿐이다(셈은
outputs/digest.py — 이 파일에 로직은 없다). 결과 본문은 바이트 그대로다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 고정 파일은
tests/data/flow-shapes/dataverify.digest@1.schema.json.
칸을 더하는 것은 @1 안, 빼거나 바꾸면 @2 다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.dataverify.contracts.shapes import FORBID, Count

DIGEST_SHAPE: Final = "dataverify.digest@1"


@with_config(FORBID)
class DataverifyStageHead(TypedDict):
    """단계 하나의 머리(결과의 그 단계 status·partial 그대로)."""

    status: Literal["done", "failed", "not_run"]
    partial: bool | None
    """done 이면 true(최대 횟수에 닿아 마지막 답을 씀)·false, failed·not_run 이면 null."""


@with_config(FORBID)
class DataverifyStageHeads(TypedDict):
    """단계 셋의 머리(계산 Plan·계산 검토·인사이트)."""

    plan: DataverifyStageHead
    review: DataverifyStageHead
    insight: DataverifyStageHead


@with_config(FORBID)
class DataverifyCheckCounts(TypedDict):
    """계산 검토의 검사 기록 셈(review.checks — 실패한 검토도 그때까지의 기록). 엑셀 「검증 결과」 시트와 갈래별로
    맞는다: ok + fail + notComputed = 판정이 OK·FAIL·「계산 불가」인 줄 수, naValues = 「값 없음(N/A)」 줄 수,
    toolErrors = 판정 「오류」 줄 수. 값이 있는 조회·검색 줄은 셈 밖이다."""

    ok: Count
    """합계·부분합·비율 검사의 해 가운데 계산했고(note null) OK 인 수."""
    fail: Count
    """그 가운데 계산했고(note null) FAIL 인 수."""
    notComputed: Count
    """계산하지 못한 해(note 있음 — 수가 아님·0 으로 나눔)의 수."""
    naValues: Count
    """값 조회 가운데 도구가 「N/A」를 돌려준 수(na true)."""
    toolErrors: Count
    """도구가 오류를 돌려준 호출 수(kind error)."""


@with_config(FORBID)
class DataverifyDigest(TypedDict):
    """dataverify.digest@1 — 데이터 검증 실행 하나의 요약."""

    schemaVersion: Literal["dataverify.digest@1"]
    stages: DataverifyStageHeads
    checks: DataverifyCheckCounts


DIGEST_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    DIGEST_SHAPE: TypeAdapter[DataverifyDigest](
        Annotated[DataverifyDigest, Field(title=DIGEST_SHAPE, description="데이터 검증 한 건의 요약.")]
    )
}
"""꼴 id → 검사기. validate_python(요약, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
