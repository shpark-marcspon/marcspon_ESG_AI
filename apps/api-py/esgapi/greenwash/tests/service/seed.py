# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""그린워싱 업무 층 시험의 행 심기. 실행·결과 행은 runs.models 를 import 하지 않고(계약 나) `apps.get_model` 로 심는다.
문서·숫자는 전부 지어낸 것이다(synthetic). 결과 본문은 계약 예시(tests/data/contract-examples/result-*.json).
"""

import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any

from django.apps import apps

from esgapi.core.models import DocumentRow

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "contract-examples"
FILE_NAME = "가상-보고서.pdf"


def example(name: str) -> dict[str, Any]:
    """계약 예시 하나(result-normal·result-many·result-dry-run …)."""
    body: dict[str, Any] = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return body


def document(company_id: int, *, name: str = FILE_NAME, uploaded_by: str = "1") -> int:
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by=uploaded_by,
        file_name=name,
        storage_key=f"companies/{company_id}/documents/seed-{uuid.uuid4().hex}/original",
        size_bytes=10,
        etag="e",
        status="uploaded",
    )
    return row.pk


def run(
    company_id: int,
    *,
    status: str = "done",
    module: str = "greenwash",
    result: dict[str, Any] | None = None,
    document_id: int | None = None,
    created_by: int = 1,
    options: dict[str, Any] | None = None,
    error_code: str | None = None,
    failed_step: str | None = None,
    flow_id: str | None = None,
    finished_at: datetime | None = None,
) -> int:
    """실행 행 하나(단계 행 없음)와, result 가 있으면 결과 행 하나(position 0). finished_at 은 주면 그 값(GCB1)."""
    run_row = apps.get_model("runs", "RunRow")
    result_row = apps.get_model("runs", "RunResultRow")
    made = run_row.for_company(company_id).create(
        company_id=company_id,
        document_id=document_id if document_id is not None else document(company_id),
        module=module,
        flow_id=flow_id or ("greenwash.colab@E0" if module == "greenwash" else f"{module}.probe@1"),
        options=options or {},
        versions={},
        status=status,
        created_by_user_id=created_by,
        error_code=error_code,
        failed_step=failed_step,
        finished_at=finished_at,
    )
    if result is not None:
        result_row.for_company(company_id).create(
            company_id=company_id, run_id=made.pk, position=0, schema_version=result["schemaVersion"], body=result
        )
    return int(made.pk)


def step(
    company_id: int,
    run_id: int,
    name: str,
    position: int,
    status: str,
    done: int | None = None,
    total: int | None = None,
) -> None:
    """실행의 단계 행 하나(목록 줄 — G1b ③)."""
    apps.get_model("runs", "RunStepRow").for_company(company_id).create(
        company_id=company_id, run_id=run_id, name=name, position=position, status=status, done=done, total=total
    )
