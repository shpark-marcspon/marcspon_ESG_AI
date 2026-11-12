"""원고작성 프로젝트의 응답 꼴(JSON — 밴드 RP2d, contracts/api_shapes.py 의 TypedDict 에서 옮김). 칸 이름은 camelCase,
id 는 int 다.

★ 시각 칸은 KstDateTime(+09:00 — config/tests/test_api_times.py 가 openapi 의 date-time 을 다 센다): 프로젝트의
  createdAt·문서의 attachedAt(달린 행의 created_at).
★ 컴포넌트 이름은 옮기기 전과 같다(웹의 생성 타입 이름이 그대로). 칸마다 아래의 docstring 이 description 이 된다
  (use_attribute_docstrings — 옮기기 전의 TypedDict 와 같은 설명).
★ 응답 꼴은 모르는 칸을 거절한다(extra forbid → openapi additionalProperties: false — 옮기기 전 TypedDict 의 FORBID 와
  같다. ninja Schema 의 기본은 열려 있다). 조회 인자(DraftingProjectListQuery)는 core 목록 꼴대로 열어 둔다.
★ 요청 꼴(`*In`)과 목차 넣기의 답(DraftingOutlinePut)은 contracts/api_shapes.py 에 있다. 테넌트·회사의 칸은 싣지 않는다.
★ (RPS1) 프로젝트의 실행 줄 DraftingRunItem 은 실행 목록·목록 줄·프로젝트의 latestRun 이 같이 쓴다 — 시각 칸은
  createdAt·finishedAt(실행의 created_at·finished_at). 몸은 service/actions/runs.py.
"""

from typing import Literal

from ninja import Schema
from pydantic import ConfigDict, Field

from esgapi.core.schemas import KstDateTime, LimitOffsetPage
from esgapi.drafting.contracts.shapes import DraftingOutline

OUT = ConfigDict(extra="forbid", use_attribute_docstrings=True)


class DraftingProjectDocument(Schema):
    """프로젝트의 지금 문서(가장 늦게 단 것)."""

    model_config = OUT

    documentId: int
    kind: str
    """`prior_report`(전년도 보고서) 하나."""
    attachedByUserId: int
    attachedAt: KstDateTime
    """문서를 단 시각."""


class DraftingProjectOutline(Schema):
    """프로젝트의 지금 목차 판(가장 큰 revision)."""

    model_config = OUT

    outlineId: int
    revision: int
    """1부터. 목차를 바꿀 때마다 +1(같은 sha 면 그대로)."""
    sha256: str
    """정규형 목차의 sha256(contracts/wire.outline_sha256)."""
    outline: DraftingOutline


class DraftingRunProgress(Schema):
    """진행 중(processing) 실행의 지금 단계(선언 차례로 처음 running 인 단계)."""

    model_config = OUT

    step: str
    """단계 이름(흐름이 선언한 이름)."""
    done: int | None
    """그 단계에서 끝낸 수(단계가 세지 않으면 null)."""
    total: int | None
    """그 단계의 전부의 수(단계가 세지 않으면 null)."""


class DraftingRunLeaves(Schema):
    """끝난 실행의 결과(drafting.bullets@3) 잎 셈 — 잎의 outcome.status 별."""

    model_config = OUT

    total: int
    """잎 전부의 수."""
    drafted: int
    """outcome done(초안을 지음 — bullet 0 줄도)."""
    noMaterial: int
    """outcome no_material(달린 쪽이 없어 호출하지 않음)."""
    failed: int
    """outcome failed(호출이나 답 읽기가 실패)."""
    notRun: int
    """outcome not_run(실행이 rejected 로 멈춤)."""


class DraftingRunItem(Schema):
    """프로젝트의 원고작성 실행 한 줄(옵션 projectId 가 그 프로젝트인 실행). 결과 본문은 싣지 않는다
    (GET /drafting/runs/{run_id}/result 다)."""

    model_config = OUT

    id: int
    status: Literal["queued", "processing", "done", "failed"]
    createdAt: KstDateTime
    """실행을 만든 시각(실행 목록은 이것의 내림차순, 같으면 id 내림차순)."""
    finishedAt: KstDateTime | None
    """끝난 시각(done·failed). 끝나지 않았으면 null."""
    outlineId: int | None
    """실행이 읽은 목차 판 id(만들 때 박은 판 — versions.outlineId). 없으면 null."""
    baseRunId: int | None
    """이어 받은 앞 실행 id(옵션 base.runId). 없으면 null."""
    rebuild: list[str]
    """다시 짓게 한 잎 key(옵션 base.rebuild). 없으면 빈 목록."""
    progress: DraftingRunProgress | None
    """processing 실행의 지금 단계. queued·끝난 실행·running 단계가 없으면 null."""
    rejected: bool | None
    """끝났고 결과(drafting.bullets@3)가 있으면 결과가 rejected(공급사를 부르기 전에 멈춤)인가. 아니면 null."""
    leaves: DraftingRunLeaves | None
    """끝났고 결과(drafting.bullets@3)가 있을 때만 잎 셈. 아니면(진행 중·실패·옛 결과) null."""


class DraftingRunPage(LimitOffsetPage[DraftingRunItem]):
    model_config = ConfigDict(extra="forbid")


class DraftingProjectRunsQuery(Schema):
    """`GET /drafting/projects/{project_id}/runs` 의 조회 인자(결과 본문을 읽는 쪽이라 위끝 50)."""

    limit: int = Field(default=20, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


class DraftingProject(Schema):
    """프로젝트 하나 + 지금 문서 + 지금 목차."""

    model_config = OUT

    id: int
    year: int
    name: str
    createdByUserId: int
    createdAt: KstDateTime
    """프로젝트를 만든 시각."""
    document: DraftingProjectDocument | None
    """달린 문서가 없으면 null."""
    outline: DraftingProjectOutline | None
    """목차가 없으면 null."""
    latestRun: DraftingRunItem | None
    """이 프로젝트의 가장 새 원고작성 실행. 없으면 null."""


class DraftingProjectListItem(Schema):
    """목록의 한 줄. 문서는 있는지와 지금 문서의 파일 이름, 목차는 지금 판의 번호·id, 실행은 가장 새 것 하나만
    싣는다(전부는 GET /drafting/projects/{project_id}/runs 다)."""

    model_config = OUT

    id: int
    year: int
    name: str
    createdAt: KstDateTime
    """프로젝트를 만든 시각(목록은 이것의 내림차순, 같으면 id 내림차순)."""
    hasDocument: bool
    """달린 문서가 하나라도 있는가."""
    outlineRevision: int | None
    """지금 목차 판 번호(1부터). 목차가 없으면 null."""
    documentName: str | None
    """지금 문서(가장 늦게 단 것)의 파일 이름. 문서가 없으면 null."""
    outlineId: int | None
    """지금 목차 판 id(latestRun.outlineId 와 견주면 목차가 바뀌었는지 안다). 목차가 없으면 null."""
    latestRun: DraftingRunItem | None
    """가장 새 원고작성 실행. 없으면 null."""


class DraftingProjectPage(LimitOffsetPage[DraftingProjectListItem]):
    model_config = ConfigDict(extra="forbid")


class DraftingProjectListQuery(Schema):
    """`GET /drafting/projects` 의 조회 인자(core 목록과 같은 기본값)."""

    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


class DraftingOutlineLeafChange(Schema):
    """지금 목차 잎 하나의 차이(앞 실행이 읽은 목차 판과 견줌 — 잎 key + 제목 경로·요구 내용)."""

    model_config = OUT

    key: str
    """지금 목차의 잎 key(지금 목차 차례)."""
    change: Literal["same", "changed", "added"]
    """same = 제목 경로·요구 내용이 같음 · changed = 다름(조상 제목이 바뀌어도) · added = 앞 목차에 없던 잎."""


class DraftingOutlineChanges(Schema):
    """앞 실행의 목차 판 → 프로젝트의 지금 목차 판의 잎 차이(목차 차이만 — 실제로 옮겼는지는 결과의 base·
    reusedFrom 이 말한다)."""

    model_config = OUT

    baseRunId: int
    """견준 앞 실행 id."""
    baseOutlineId: int
    """앞 실행이 읽은 목차 판 id."""
    outlineId: int
    """프로젝트의 지금 목차 판 id."""
    document: Literal["same", "changed"]
    """앞 실행이 읽은 문서(documentId·etag)와 프로젝트의 지금 문서가 같은가(지금 문서가 없으면 changed)."""
    leaves: list[DraftingOutlineLeafChange]
    """지금 목차의 잎 전부(목차 차례)."""
    removed: list[str]
    """앞 목차에 있고 지금 목차에 잎으로 없는 key(앞 목차 차례 — 잎이 가지가 된 것도)."""


class DraftingOutlineChangesQuery(Schema):
    """`GET /drafting/projects/{project_id}/outline/changes` 의 조회 인자."""

    baseRunId: int = Field(ge=1)
    """견줄 앞 실행 id(같은 프로젝트의 끝난 원고작성 실행)."""
