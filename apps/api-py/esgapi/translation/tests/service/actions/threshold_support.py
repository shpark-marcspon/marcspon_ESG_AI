"""문턱 재기(TR3b ★H·§3-2-7)의 자료: 지어낸 영문번역 실행 1,000 건(옵션 약 166KB 꼴 — 용어집 500+500짝·peer 문체 글).

★ 글은 전부 지어낸 것이다(synthetic). 실재 기업명·실제 보고서 문장 0.
"""

import json
import os
import resource
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from typing import Any

from django.apps import apps
from django.db import connection

from esgapi.core.models import DocumentRow
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE

RUNS = 1000
DIGEST: dict[str, Any] = {
    "schemaVersion": DIGEST_SHAPE,
    "status": "done",
    "rejectionKind": None,
    "outcome": "done",
    "pageCount": 40,
    "failedPages": [],
    "variants": [],
    "warningCount": 0,
}
PARTS = ("ceo_message", "story", "general")


def big_options(n: int, batch_id: str | None, part: str) -> dict[str, object]:
    """옵션 하나(raw JSON 약 166KB). 짝마다 국문 열쇠·영문 값이 조금씩 달라 압축·중복 제거가 덜 먹는다."""
    pairs = [
        {"ko": f"지어낸 용어 {n}-{i} 가나다라마바사아자차", "en": f"synthetic term {n}-{i} alpha beta gamma delta"}
        for i in range(500)
    ]
    options: dict[str, object] = {
        "company": {"name": "지어낸 회사", "preferredSubject": "지어낸 산업", "industryStandards": "지어낸 기준"},
        "part": part,
        "style": {"compareAb": True, "single": "B"},
        "pages": {"start": None, "end": None},
        "ceoPageLimit": 6,
        "glossary": {"base": pairs, "final": pairs},
        "peerGroupStyle": {"prompt": f"지어낸 문체 글 {n} " * 2400},
    }
    if batch_id is not None:
        options = {"batchId": batch_id, **options}
    return options


def seed(company_id: int, *, documents: int = 40, runs: int = RUNS) -> int:
    """문서 documents 개에 실행 runs 개를 고루 심는다. 묶음은 셋째마다 새 batchId(파트 셋), 묶음 하나에 회차 여럿
    (같은 파트 다시)을 섞고, 열에 하나는 batchId 없는 실행. 상태는 done·failed·processing·queued 를 섞는다.
    돌려주는 것: 옵션 하나의 raw JSON 바이트."""
    docs = [
        DocumentRow.for_company(company_id)
        .create(
            company_id=company_id,
            uploaded_by=str(1 + d % 2),
            file_name=f"지은 문서 {d}.docx",
            storage_key=f"companies/{company_id}/documents/t-{d}/original",
            size_bytes=1,
            status="uploaded",
        )
        .pk
        for d in range(documents)
    ]
    start = datetime(2026, 10, 1, tzinfo=UTC)
    run_row: Any = apps.get_model(
        "runs", "RunRow"
    )  # 모듈끼리 models import 0(.importlinter 계약 나) — greenwash 시험 꼴
    rows: list[Any] = []
    for n in range(runs):
        batch = None if n % 10 == 9 else f"00000000-0000-4000-8000-{n // 5:012x}"  # 다섯 실행 = 묶음 하나(회차 섞임)
        status = (
            ("done", "done", "failed", "processing", "queued")[n % 5]
            if n >= runs - 50
            else ("done", "failed")[n % 7 == 0]
        )
        rows.append(
            run_row(
                company_id=company_id,
                document_id=docs[(n // 5) % documents],
                module="translation",
                flow_id="translation.colab_158@1",
                options=big_options(n, batch, PARTS[n % 3]),
                status=status,
                created_by_user_id=1 + n % 2,
                created_at=start + timedelta(minutes=n),
            )
        )
    made = run_row.unscoped.bulk_create(rows, batch_size=50)
    _children(company_id, made)
    return len(json.dumps(big_options(0, "00000000-0000-4000-8000-000000000000", "story"), ensure_ascii=False).encode())


RESULT_FILLER = "지어낸 결과 본문 " * 4000
"""끝난 실행의 주 결과 본문(약 90KB) — 목록이 읽지 않아야 하는 것."""


def _children(company_id: int, runs: list[Any]) -> None:
    """실행마다 단계 셋(끝난 단계는 data 를 싣는다)과, 끝난 실행이면 주 결과(큰 본문)·요약(digest@1)."""
    step_row: Any = apps.get_model("runs", "RunStepRow")
    result_row: Any = apps.get_model("runs", "RunResultRow")
    steps: list[Any] = []
    results: list[Any] = []
    for run in runs:
        done = run.status == "done"
        for position, name in enumerate(("prepare", "translate", "report")):
            status = "done" if done or position == 0 else ("running" if position == 1 else "pending")
            data = {"filler": RESULT_FILLER[:2000]} if status == "done" else None
            steps.append(
                step_row(company_id=company_id, run_id=run.pk, name=name, position=position, status=status, data=data)
            )
        if done:
            body = {"schemaVersion": "translation.result@1", "filler": RESULT_FILLER}
            results.append(
                result_row(
                    company_id=company_id, run_id=run.pk, position=0, schema_version=body["schemaVersion"], body=body
                )
            )
            results.append(
                result_row(company_id=company_id, run_id=run.pk, position=1, schema_version=DIGEST_SHAPE, body=DIGEST)
            )
    step_row.unscoped.bulk_create(steps, batch_size=200)
    result_row.unscoped.bulk_create(results, batch_size=100)


def p95(seconds: list[float]) -> float:
    ordered = sorted(seconds)
    return ordered[max(0, round(0.95 * len(ordered)) - 1)]


def maxrss_bytes() -> int:
    used = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return used if sys.platform == "darwin" else used * 1024


def subprocess_maxrss(code: str) -> int:
    """따로 띄운 파이썬 한 번의 최고 RSS(바이트) — 같은 테스트 DB 로 붙는다(자료는 커밋돼 있어야 한다)."""
    s = connection.settings_dict
    url = f"postgres://{s['USER']}:{s['PASSWORD']}@{s['HOST']}:{s['PORT']}/{s['NAME']}"
    env = {
        **os.environ,
        "TEST_DATABASE_URL_PY_OWNER": url,
        "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.test_business",
    }
    script = (
        "import django, json, resource, sys\n"
        "django.setup()\n"
        f"{code}\n"
        "used = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss\n"
        "print(json.dumps(used if sys.platform == 'darwin' else used * 1024))\n"
    )
    done = subprocess.run(
        [sys.executable, "-c", script], env=env, capture_output=True, text=True, check=True, timeout=300
    )
    return int(done.stdout.strip().splitlines()[-1])
