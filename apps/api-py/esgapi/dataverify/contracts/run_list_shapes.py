"""목록 꼴 — 데이터 검증 실행 목록 GET /dataverify/runs 의 줄·쪽(밴드 DV1g, MARC-ISSUE-336·MARC-ENT-420).

한 줄이 실행 하나다(새 것 먼저). 옵션에서는 입력 출처 source·기업명·보고연도·항목 수만, 결과에서는 둘째 결과
dataverify.digest@1(contracts/digest_shapes.py)의 단계 머리와 검토 셈만 싣는다 — 옵션의 입력 데이터(input.data)·
중대토픽과 결과 본문(result@2)은 싣지 않는다. **이 파일에 로직은 없다**(짓기는 service/actions/runs.py).
- 옵션·요약의 값은 응답에 싣기 전에 꼴을 다시 잰다 — 꼴이 아니면(DV1f 앞 실행의 source 없음·꼴 밖 행·요약 없는 옛
  실행) 그 칸만 null 이고 줄은 낸다.
- source 는 옵션 꼴의 DataverifySource(contracts/options_shapes.py) 그 객체다 — 두 번째 정본 0.
- 시각은 +09:00 ISO 8601 글자다(짓기가 core.schemas.to_seoul_iso). 계약은 ninja·core.schemas 를 import 하지 않는다.
- 이름은 전부 `Dataverify` 로 시작한다(generated/ 의 schema 이름 — 다른 모듈의 것과 겹치면 하나로 합쳐진다).
칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 칸을 더하는 것은 같은 판 안, 빼거나 바꾸면 새 경로다.
"""

from typing import Annotated, Literal, TypedDict

from pydantic import Field, with_config

from esgapi.dataverify.contracts.digest_shapes import DataverifyCheckCounts, DataverifyStageHeads
from esgapi.dataverify.contracts.options_shapes import DataverifySource
from esgapi.dataverify.contracts.shapes import FORBID, Count

DataverifyRunStatus = Literal["queued", "processing", "done", "failed"]
"""실행의 상태(runs 의 실행 행 그대로)."""


@with_config(FORBID)
class DataverifyPerson(TypedDict):
    """사람 — id 와 지금 이름(지운·모르는 사람이면 「알 수 없는 사용자」)."""

    userId: Annotated[int, Field(ge=1)]
    name: str


@with_config(FORBID)
class DataverifyRunRow(TypedDict):
    """데이터 검증 실행 한 줄."""

    id: Annotated[int, Field(ge=1)]
    """실행 id(GET /runs/{id} · GET /dataverify/runs/{id}/result)."""
    status: DataverifyRunStatus
    createdAt: str
    """만든 시각(+09:00 ISO 8601)."""
    finishedAt: str | None
    """끝난 시각(done·failed). 안 끝났으면 null."""
    createdBy: DataverifyPerson
    """실행을 만든 사람."""
    source: DataverifySource | None
    """입력의 출처(옵션 source 그대로 — 올린 파일 이름 / 붙여 넣기). 없거나(DV1f 앞 실행) 꼴이 아니면 null."""
    companyName: str | None
    """입력의 기업명(옵션 input.company.name). 꼴이 아니면 null."""
    reportingYear: str | None
    """입력의 보고연도(옵션 input.company.reportingYear — 글자). 꼴이 아니면 null."""
    itemCount: Count | None
    """검증 대상 테마 「환경」의 항목 수(옵션 input.data — 안 끝난 실행도). 꼴이 아니면 null. 끝난 실행은 결과
    scope.itemCount 와 같다."""
    failedStep: str | None
    """failed 실행이 멈춘 단계 이름(실행기의 실패면 null). 그 밖의 상태는 null."""
    currentStep: str | None
    """processing 실행의 지금 도는 단계 이름(running 단계가 없으면 null). 그 밖의 상태는 null."""
    stages: DataverifyStageHeads | None
    """done 실행의 단계 셋 머리(요약 dataverify.digest@1). 안 끝났거나 요약이 없는 옛 실행이면 null."""
    checks: DataverifyCheckCounts | None
    """done 실행의 검토 셈(요약 dataverify.digest@1). 안 끝났거나 요약이 없는 옛 실행이면 null."""


@with_config(FORBID)
class DataverifyRunPage(TypedDict):
    """실행 목록 한 쪽(새 것 먼저 — 만든 시각·id 내림)."""

    count: Count
    """거른 뒤 실행 수."""
    isNext: bool
    results: list[DataverifyRunRow]
