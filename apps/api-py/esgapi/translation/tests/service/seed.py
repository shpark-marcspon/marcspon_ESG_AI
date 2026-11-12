# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""영문번역 묶음 시험(TR3b 업무 층)의 행 심기. 실행·단계·결과·파일 행은 runs.models 를 import 하지 않고(계약 나)
`apps.get_model` 로 심는다(greenwash tests/service/seed.py 꼴). 문서·숫자·글은 전부 지어낸 것이다(synthetic).
"""

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from django.apps import apps

from esgapi.core.models import DocumentRow
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE

START = datetime(2026, 10, 1, tzinfo=UTC)
STEPS = ("prepare", "translate", "report")
_clock = [0]


def document(company_id: int, *, uploaded_by: str = "1", name: str = "지은 보고서.docx") -> int:
    row = DocumentRow.for_company(company_id).create(
        company_id=company_id,
        uploaded_by=uploaded_by,
        file_name=name,
        storage_key=f"companies/{company_id}/documents/tr3b-{uuid.uuid4().hex}/original",
        size_bytes=10,
        etag="e",
        status="uploaded",
        uploaded_at=START,
    )
    return row.pk


def options(part: str, batch_id: str | None, *, base: int = 2, final: int = 3) -> dict[str, Any]:
    found: dict[str, Any] = {
        "company": {"name": "지어낸 회사", "preferredSubject": "지어낸 산업", "industryStandards": "지어낸 기준"},
        "part": part,
        "style": {"compareAb": True, "single": "B"},
        "pages": {"start": 3, "end": None},
        "ceoPageLimit": 6,
        "glossary": {
            "base": [{"ko": f"가{i}", "en": f"a{i}"} for i in range(base)],
            "final": [{"ko": f"나{i}", "en": f"b{i}"} for i in range(final)],
        },
    }
    return found if batch_id is None else {"batchId": batch_id, **found}


def digest(outcome: str = "done", *, autofix: str | None = "translation-autofix-a.docx") -> dict[str, Any]:
    rejected = outcome == "rejected"
    return {
        "schemaVersion": DIGEST_SHAPE,
        "status": "rejected" if rejected else "done",
        "rejectionKind": "over_budget" if rejected else None,
        "outcome": outcome,
        "pageCount": 0 if rejected else 2,
        "failedPages": [2] if outcome == "partial" else [],
        "variants": []
        if rejected
        else [
            {
                "label": "A",
                "reviewStatus": "reviewed",
                "reviewStoppedAt": None,
                "parseFailedPages": 0,
                "issueCount": 1,
                "issueCounts": {"high": 0, "medium": 1, "low": 0},
                "glossaryMisses": 0,
                "autofixStatus": "done" if autofix else "not_run",
                "autofixChangedPages": 1 if autofix else 0,
                "files": {
                    "bilingual": "translation-bilingual-a.docx",
                    "qa": "translation-qa-a.docx",
                    "autofix": autofix,
                },
            }
        ],
        "warningCount": 0,
    }


def run(
    company_id: int,
    document_id: int,
    part: str,
    *,
    batch_id: str | None = None,
    status: str = "done",
    created_by: int = 1,
    result: dict[str, Any] | None = None,
    digest_body: dict[str, Any] | bool | None = None,
    error_code: str | None = None,
    failed_step: str | None = None,
    steps: tuple[tuple[str, int | None, int | None], ...] | None = None,
    body: dict[str, Any] | None = None,
    flow_id: str = "translation.colab_158@1",
) -> int:
    """실행 행 하나(created_at 은 부를 때마다 1분씩 뒤)와 단계 행(steps — 이름 차례대로 (상태, done, total) — 없으면
    status 에 맞춘 셋), 결과 행(result·digest — done 이면 둘째 결과 digest)."""
    _clock[0] += 1
    at = START + timedelta(minutes=_clock[0])
    run_row = apps.get_model("runs", "RunRow")
    made = run_row.for_company(company_id).create(
        company_id=company_id,
        document_id=document_id,
        module="translation",
        flow_id=flow_id,
        options=body if body is not None else options(part, batch_id),
        versions={},
        status=status,
        created_by_user_id=created_by,
        started_at=None if status == "queued" else at,
        finished_at=at + timedelta(seconds=30) if status in ("done", "failed") else None,
        error_code=error_code,
        failed_step=failed_step,
    )
    run_row.for_company(company_id).filter(pk=made.pk).update(created_at=at)  # auto_now_add 를 넘어 차례를 박는다
    if steps is None:
        steps = {
            "done": (("done", None, None),) * 3,
            "failed": (("done", None, None), ("failed", 1, 4), ("pending", None, None)),
            "processing": (("done", None, None), ("running", 2, 5), ("pending", None, None)),
            "queued": (("pending", None, None),) * 3,
        }[status]
    for position, (name, (step_status, done, total)) in enumerate(zip(STEPS, steps, strict=True)):
        apps.get_model("runs", "RunStepRow").for_company(company_id).create(
            company_id=company_id,
            run_id=made.pk,
            name=name,
            position=position,
            status=step_status,
            done=done,
            total=total,
            data={"secret": "data"} if step_status == "done" else None,
        )
    rows: list[dict[str, Any]] = []
    if status == "done":
        rows.append(result or {"schemaVersion": "translation.result@1", "big": "본문"})
        if digest_body is None:
            rows.append(digest())
        elif isinstance(digest_body, dict):
            rows.append(digest_body)  # False = 요약을 남기기 전의 옛 실행
    for position, body_row in enumerate(rows):
        apps.get_model("runs", "RunResultRow").for_company(company_id).create(
            company_id=company_id,
            run_id=made.pk,
            position=position,
            schema_version=body_row["schemaVersion"],
            body=body_row,
        )
    return int(made.pk)


def output(company_id: int, run_id: int, name: str, data: bytes | None, storage: Any) -> None:
    """흐름의 출력 파일 행 하나와(data 가 None 이면 행만 — 객체 없음) 저장소의 바이트."""
    key = f"runs/{company_id}/{run_id}/{name}"
    if data is not None:
        storage.put(key, data)
    apps.get_model("runs", "RunFileRow").for_company(company_id).create(
        company_id=company_id,
        run_id=run_id,
        step=None,
        name=name,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        storage_key=key,
        size_bytes=len(data) if data is not None else 10,
        sha256="0" * 64,
    )
