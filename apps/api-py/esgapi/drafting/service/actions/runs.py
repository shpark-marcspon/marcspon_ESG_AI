"""프로젝트의 원고작성 실행 읽기(GET /drafting/projects/{project_id}/runs 의 몸 + 목록·프로젝트의 latestRun — 밴드
RPS1, 처분 ⓐ~ⓔ 가). drafting 의 selectors(프로젝트·지금 문서) + runs 의 selectors(실행·단계·결과) + core 의
documents_of(문서 이름)를 엮으므로 Action 이다(materiality service/actions/runs.py 꼴).

    project_runs(company_id, project_id, limit, offset)     실행 한 쪽(DraftingRunPage 꼴) · 프로젝트 없음 NotFound
    latest_runs(company_id, project_ids)                    프로젝트 id → 가장 새 실행 줄(없으면 열쇠가 없다)
    project_page(company_id, limit, offset)                 목록 한 쪽(DraftingProjectPage 꼴 — 문서 이름·목차 판 id·
                                                            latestRun)

규칙:
  - 실행은 run_page(module="drafting") 한 번(회사 조건·새 것 먼저)으로 많아야 RUN_SCAN_MAX 줄을 읽고, 옵션 projectId 로
    파이썬에서 거른다(runs 0줄 — 옵션 칸은 OrderedJSONField 라 SQL 로 열쇠를 조회하지 않는다, runs/models.py 머리말).
    회사 조건(run_page 의 company_id)과 projectId 둘 다 — 남의 회사의 같은 projectId 실행은 섞이지 않는다.
  - progress 는 processing 실행만(step_lines_of 한 쿼리 — 선언 차례로 처음 running 인 단계). queued 는 null.
  - rejected·leaves 는 done 실행만(results_of(schema_versions=[drafting.bullets@3]) 한 쿼리 — 결과를 읽기만). 결과가
    없거나 옛 꼴(@1·@2)이거나 꼴 밖이면 둘 다 null.
★ 쿼리 수(줄 수와 무관): 실행 쪽 = 프로젝트 1 + run_page 2 + 단계 ≤1 + 결과 ≤1 · 목록 한 쪽 = project_page 2 +
  지금 문서 1 + core 문서 1 + run_page 2 + 단계 ≤1 + 결과 ≤1. 실행마다 find_run·run_results 0.
★ RUN_SCAN_MAX 를 넘는 회사는 오래된 실행부터 안 보인다(새 것 먼저라 latestRun 은 맞다 — Not-tested, 처분 ⓐ).
"""

from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.core.service.selectors import documents as document_selectors
from esgapi.drafting.contracts.shapes import RESULT_SHAPE
from esgapi.drafting.service.selectors import projects as selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import Run

MODULE: Final = "drafting"
RUN_SCAN_MAX: Final = 1000
"""한 번에 읽는 회사의 원고작성 실행 위끝(새 것 먼저 — 1차 회사 하나, 처분 ⓐ)."""
OUTCOMES: Final[Mapping[str, str]] = {
    "done": "drafted",
    "no_material": "noMaterial",
    "failed": "failed",
    "not_run": "notRun",
}
"""잎 outcome.status → 잎 셈 칸."""


@dataclass(frozen=True, slots=True)
class NotFound:
    """프로젝트가 없다(남의 회사의 id 도)."""


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _base(run: Run) -> dict[str, object]:
    base = run.options.get("base")
    return cast("dict[str, object]", base) if isinstance(base, dict) else {}


def _rebuild(run: Run) -> list[str]:
    keys = _base(run).get("rebuild")
    if not isinstance(keys, list):
        return []
    return [key for key in cast("list[object]", keys) if isinstance(key, str)]


def _scan(company_id: int) -> list[Run]:
    """그 회사의 원고작성 실행(새 것 먼저, 많아야 RUN_SCAN_MAX). 쿼리 둘."""
    page = run_selectors.run_page(
        company_id=company_id, module=MODULE, status=None, document_id=None, limit=RUN_SCAN_MAX, offset=0
    )
    return [run for run, _document_name in page.runs]


def _progress(company_id: int, run_ids: Collection[int]) -> dict[int, dict[str, Any]]:
    """processing 실행의 지금 단계(실행 id → {step, done, total}). running 단계가 없으면 열쇠가 없다."""
    if not run_ids:
        return {}
    found: dict[int, dict[str, Any]] = {}
    for run_id, steps in run_selectors.step_lines_of(company_id=company_id, run_ids=run_ids).items():
        running = next((s for s in steps if s.status == "running"), None)
        if running is not None:
            found[run_id] = {"step": running.name, "done": running.done, "total": running.total}
    return found


def _leaves(body: object) -> tuple[bool, dict[str, int]] | None:
    """결과 본문(@3) → (rejected, 잎 셈). 꼴 밖이면 None."""
    if not isinstance(body, dict):
        return None
    result = cast("dict[str, object]", body)
    status, leaves = result.get("status"), result.get("leaves")
    if not isinstance(status, dict) or not isinstance(leaves, list):
        return None
    counts = {"total": 0, "drafted": 0, "noMaterial": 0, "failed": 0, "notRun": 0}
    for leaf in cast("list[object]", leaves):
        counts["total"] += 1
        outcome = cast("dict[str, object]", leaf).get("outcome") if isinstance(leaf, dict) else None
        name = (
            OUTCOMES.get(str(cast("dict[str, object]", outcome).get("status"))) if isinstance(outcome, dict) else None
        )
        if name is not None:
            counts[name] += 1
    return cast("dict[str, object]", status).get("status") == "rejected", counts


def _summaries(company_id: int, run_ids: Collection[int]) -> dict[int, tuple[bool, dict[str, int]]]:
    """done 실행의 (rejected, 잎 셈). @3 결과가 없거나 꼴 밖이면 열쇠가 없다. 쿼리 하나(비면 0)."""
    if not run_ids:
        return {}
    results = run_selectors.results_of(company_id=company_id, run_ids=run_ids, schema_versions=[RESULT_SHAPE])
    found: dict[int, tuple[bool, dict[str, int]]] = {}
    for run_id, rows in results.items():
        summary = _leaves(next((r.body for r in rows if r.schema_version == RESULT_SHAPE), None))
        if summary is not None:
            found[run_id] = summary
    return found


def _items(company_id: int, runs: Sequence[Run]) -> list[dict[str, Any]]:
    """실행 줄들(DraftingRunItem 꼴). 단계·결과는 묶음 쿼리 하나씩 — 줄마다 0."""
    progress = _progress(company_id, [r.id for r in runs if r.status == "processing"])
    summaries = _summaries(company_id, [r.id for r in runs if r.status == "done"])
    items: list[dict[str, Any]] = []
    for run in runs:
        summary = summaries.get(run.id)
        items.append(
            {
                "id": run.id,
                "status": run.status,
                "createdAt": run.created_at,
                "finishedAt": run.finished_at,
                "outlineId": _int(run.versions.get("outlineId")),
                "baseRunId": _int(_base(run).get("runId")),
                "rebuild": _rebuild(run),
                "progress": progress.get(run.id),
                "rejected": None if summary is None else summary[0],
                "leaves": None if summary is None else summary[1],
            }
        )
    return items


def project_runs(*, company_id: int, project_id: int, limit: int, offset: int) -> dict[str, Any] | NotFound:
    """그 프로젝트의 원고작성 실행 한 쪽(새 것 먼저)."""
    if selectors.project_head(company_id=company_id, project_id=project_id) is None:
        return NotFound()
    runs = [run for run in _scan(company_id) if _int(run.options.get("projectId")) == project_id]
    page = runs[offset : offset + limit]
    return {"count": len(runs), "isNext": offset + len(page) < len(runs), "results": _items(company_id, page)}


def latest_runs(*, company_id: int, project_ids: Collection[int]) -> dict[int, dict[str, Any]]:
    """프로젝트들의 가장 새 원고작성 실행 줄(프로젝트 id → 줄). 실행 없는 프로젝트는 열쇠가 없다. 비면 쿼리 0."""
    if not project_ids:
        return {}
    wanted = set(project_ids)
    latest: dict[int, Run] = {}
    for run in _scan(company_id):
        project_id = _int(run.options.get("projectId"))
        if project_id in wanted and project_id not in latest:
            latest[project_id] = run
    found = list(latest.items())
    items = _items(company_id, [run for _, run in found])
    return {project_id: item for (project_id, _), item in zip(found, items, strict=True)}


def project_page(*, company_id: int, limit: int, offset: int) -> dict[str, Any]:
    """목록 한 쪽(만든 시각 내림, 같으면 id 내림) + 줄마다 지금 문서 이름·지금 목차 판·가장 새 실행."""
    page = selectors.project_page(company_id=company_id, limit=limit, offset=offset)
    ids = [item.id for item in page.projects]
    attached = selectors.current_documents(company_id=company_id, project_ids=ids)
    documents = document_selectors.documents_of(
        company_id=company_id, document_ids={a.document_id for a in attached.values()}
    )
    latest = latest_runs(company_id=company_id, project_ids=ids)

    def document_name(project_id: int) -> str | None:
        found = attached.get(project_id)
        document = None if found is None else documents.get(found.document_id)
        return None if document is None else document.file_name

    return {
        "count": page.count,
        "isNext": offset + len(page.projects) < page.count,
        "results": [
            {
                "id": item.id,
                "year": item.year,
                "name": item.name,
                "createdAt": item.created_at,
                "hasDocument": item.has_document,
                "outlineRevision": item.outline_revision or None,  # 0 = 목차 없음 → null
                "documentName": document_name(item.id),
                "outlineId": item.outline_id,
                "latestRun": latest.get(item.id),
            }
            for item in page.projects
        ],
    }
