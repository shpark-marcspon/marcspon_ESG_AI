"""목록 꼴 — 중대성평가 IRO 실행 목록 GET /materiality/runs 의 줄·쪽(밴드 IR3c, 데이터 검증 DV1g 꼴 — MARC-ENT-419).

한 줄이 실행 하나다(새 것 먼저). 옵션에서는 기업명·산업(기준·이름)·토픽 수·조사 기간·최신 이슈 반영만, 결과에서는
둘째 결과 materiality.digest@1(contracts/digest_shapes.py)의 두 수만 싣는다 — 옵션의 토픽 이름·설명, 산업 설명,
서브토픽·가치사슬과 결과 본문(result@2)은 싣지 않는다. **이 파일에 로직은 없다**(짓기는 service/actions/runs.py).
- 옵션·요약의 값은 응답에 싣기 전에 꼴을 다시 잰다 — 꼴이 아니면(꼴 밖 옵션·요약 없는 옛 실행) 그 칸만 null 이고
  줄은 낸다.
- 시각은 +09:00 ISO 8601 글자다(짓기가 core.schemas.to_seoul_iso). 계약은 ninja·core.schemas 를 import 하지 않는다.
- 이름은 전부 `Materiality` 로 시작하고 contracts/shapes.py 의 이름과 겹치지 않는다(generated/ 의 schema 이름 — 같은
  이름이면 하나로 합쳐진다).
칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 칸을 더하는 것은 같은 판 안, 빼거나 바꾸면 새 경로다.
"""

from typing import Annotated, Literal, TypedDict

from pydantic import Field, with_config

from esgapi.materiality.contracts.shapes import FORBID, Count

MaterialityRunStatus = Literal["queued", "processing", "done", "failed"]
"""실행의 상태(runs 의 실행 행 그대로)."""


@with_config(FORBID)
class MaterialityPerson(TypedDict):
    """사람 — id 와 지금 이름(지운·모르는 사람이면 「알 수 없는 사용자」)."""

    userId: Annotated[int, Field(ge=1)]
    name: str


@with_config(FORBID)
class MaterialityRunIndustry(TypedDict):
    """입력의 산업 하나(기준·이름 — 설명은 싣지 않는다)."""

    standard: str
    """산업 분류 기준(입력 그대로, 예: SASB)."""
    industryName: str


@with_config(FORBID)
class MaterialityRunRow(TypedDict):
    """중대성평가 IRO 실행 한 줄."""

    id: Annotated[int, Field(ge=1)]
    """실행 id(GET /runs/{id} · GET /materiality/runs/{id}/result)."""
    status: MaterialityRunStatus
    createdAt: str
    """만든 시각(+09:00 ISO 8601)."""
    startedAt: str | None
    """처음 돌기 시작한 시각(+09:00). 「오늘까지」 기간의 끝 날은 이 시각의 서울 날이다. 아직 안 돌았으면 null."""
    finishedAt: str | None
    """끝난 시각(done·failed). 안 끝났으면 null."""
    createdBy: MaterialityPerson
    """실행을 만든 사람."""
    companyName: str | None
    """입력의 기업명(옵션 input.company.name). 꼴이 아니면 null."""
    industries: list[MaterialityRunIndustry] | None
    """입력의 산업(옵션 input.industries — 입력 차례, 기준·이름만). 하나라도 꼴이 아니면 null."""
    topicCount: Count | None
    """입력의 토픽 수(옵션 input.topics 의 길이 — 안 끝난 실행도). 꼴이 아니면 null. 끝난 실행은 결과
    scope.topicCount 와 같다."""
    dateRange: str | None
    """입력의 조사 기간 글(옵션 input.dateRange 그대로 — 「YYYY-MM-DD~오늘까지」 또는 「YYYY-MM-DD~YYYY-MM-DD」).
    꼴이 아니면 null."""
    latestEventMode: bool | None
    """입력의 최신 이슈 반영(옵션 input.latestEventMode). 꼴이 아니면 null."""
    failedStep: str | None
    """failed 실행이 멈춘 단계 이름(실행기의 실패면 null). 그 밖의 상태는 null."""
    currentStep: str | None
    """processing 실행의 지금 도는 단계 이름(GET /runs/{id} 의 steps 이름 — running 단계가 없으면 null). 그 밖의
    상태는 null."""
    impactRows: Count | None
    """done 실행의 환경·사회 영향 줄 수(요약 materiality.digest@1). 안 끝났거나 2부를 돌리지 않았거나 요약이 없는 옛
    실행이면 null."""
    pathwayRows: Count | None
    """done 실행의 재무 영향 경로 줄 수(요약 materiality.digest@1). null 은 impactRows 와 같다."""


@with_config(FORBID)
class MaterialityRunPage(TypedDict):
    """실행 목록 한 쪽(새 것 먼저 — 만든 시각·id 내림)."""

    count: Count
    """거른 뒤 실행 수."""
    isNext: bool
    results: list[MaterialityRunRow]
