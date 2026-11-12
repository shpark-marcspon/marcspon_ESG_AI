"""흐름의 실행(X1b-1)이 떠 있는 컨테이너에서 서는지를 잰다. 둘만 잰다(발주서 처분 ⑲ (다)).

    ⓐ 워커 이미지에 태스크가 실렸다: 떠 있는 worker-py 안에서 autodiscover(워커 기동이 하는 import_default_modules)
       뒤 `"runs.execute" in app.tasks`. 분모: 옛 일감 태스크 `jobs.parse` 도 같은 목록에 있다.
    ⓑ 실제 서버의 실행 경로: 올린 문서 + 그린워싱 흐름(끼움은 G1b)으로 POST /runs → 201, 워커가 끝낸 실행은 키가
       없어 failed(index · setup_error). 분모: 같은 세션으로 GET /documents/{id} 200.
       (끼움 없는 흐름의 422 FLOW_NOT_RUNNABLE 은 업무 층 esgapi/runs/tests/service/apis/test_runs.py 가 잰다.)

★ 워커가 흐름을 끝까지(done) 도는 통합은 여기 없다: 워커는 이미지만 쓰고(소스 마운트 0) 대본 심은 모의 공급사를 실을
  길이 없다. 끝까지는 업무 층 esgapi/greenwash/tests 의 실행기 시험(모의 경로 끼움 + 대본)이 잰다. 실행기의 몸은 업무
  층 esgapi/runs/tests/test_executor.py.
★ 무효 조건: ⓐ 는 이미지가 지금 소스로 빌드됐을 때만 지금 코드를 잰다(scripts/with-build-lock.sh docker compose build
  worker-py 뒤). 옛 이미지면 옛 코드를 잰다.
★ 원본은 저장소에 있는 지은 PDF(data/ruled-table.pdf)다.
"""

import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest

from esgapi.greenwash.tests import pdfbuild
from tests_integration.conftest import company_id_of, compose
from tests_integration.test_flow import exchange

Owner = psycopg.Connection[tuple[Any, ...]]
PDF = Path(__file__).resolve().parent / "data" / "ruled-table.pdf"
TASKS_PROBE = (
    "import django; django.setup()\n"
    "from esgapi.config.celery import app\n"
    "app.loader.import_default_modules()\n"
    "print('runs.execute' in app.tasks, 'jobs.parse' in app.tasks)\n"
)
RUN_WAIT_S = 60.0  # 워커가 실행을 끝내기까지의 상한(키 없는 실패는 index 에서 곧바로 — 잰 값은 G1b 보고)


@pytest.fixture
def cleanup(owner: Owner, two_tenants: tuple[str, str]) -> Iterator[tuple[str, str]]:
    """이 실행이 만든 행을 끝에서 주인 연결로 지운다(conftest 의 two_tenants 가 회사를 지우기 전에)."""
    yield two_tenants
    companies = [company_id_of(owner, subdomain) for subdomain in two_tenants]
    for table in ("greenwash_review_marks", "greenwash_reviews", "run_steps", "run_runs", "run_jobs", "core_documents"):
        owner.execute(f"DELETE FROM {table} WHERE company_id = ANY(%s)", [companies])  # noqa: S608 — 표 이름은 위 상수


def test_the_worker_image_has_the_run_task() -> None:
    out = compose("exec", "-T", "worker-py", "python", "-c", TASKS_PROBE)
    assert out.split() == ["True", "True"], out


def test_a_greenwash_run_is_created_and_the_worker_ends_it_failed_without_real_keys(
    http: httpx.Client, owner: Owner, cleanup: tuple[str, str]
) -> None:
    """그린워싱 끼움(G1b)이 서서 POST /runs 가 201 이다. 끼움은 실제 경로 이름을 쓰고 실행기는 모의 공급사만 실어 키가
    없으므로(runs/context.py — 실호출 0) 워커는 index 의 임베딩에서 LiveSetupError 로 끝낸다: failed · failedStep
    index · errorCode setup_error, 다시 넣기 없음. 「끝까지 done」은 업무 층(모의 경로 끼움 + 대본)이 잰다.
    그 실행의 그린워싱 결과·검토 GET 은 409 RUN_NOT_DONE, 목록 줄(GET /greenwash/checks)에는 failed 로 하나.
    분모: 같은 세션으로 GET /documents/{id} 200, 만든 실행이 목록에 하나."""
    tenant, _ = cleanup
    headers = exchange(http, tenant=tenant, sub="it-run-1")
    data = PDF.read_bytes()
    created = http.post("/documents", headers=headers, json={"fileName": "ruled-table.pdf", "sizeBytes": len(data)})
    assert created.status_code == 201, created.text
    document_id = created.json()["document"]["id"]
    assert httpx.put(created.json()["upload"]["url"], content=data, timeout=20.0).status_code == 200
    confirmed = http.post(f"/documents/{document_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text
    assert http.get(f"/documents/{document_id}", headers=headers).status_code == 200  # 분모

    options = {"parts": {"ceo": [1], "company": [], "climate": []}}
    response = http.post(
        "/runs", headers=headers, json={"module": "greenwash", "documentId": document_id, "options": options}
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]
    run = wait_until_finished(http, headers, run_id)
    assert (run["status"], run["failedStep"], run["errorCode"]) == ("failed", "index", "setup_error"), run
    assert run["flowId"] == "greenwash.colab@E0" and run["options"] == options
    listed = http.get("/runs", headers=headers)
    assert (listed.status_code, [r["id"] for r in listed.json()["results"]]) == (200, [run_id])
    company = company_id_of(owner, tenant)
    row = owner.execute("SELECT versions, attempts FROM run_runs WHERE company_id = %s AND id = %s", [company, run_id])
    versions, attempts = row.fetchone() or (None, None)
    assert versions is not None and sorted(versions) == [
        "aiSetting",
        "aiSettingId",
        "evalPromptSha256",
        "flow",
        "modelSettingsSha256",
    ]
    assert attempts == 1  # 다시 넣기 없음
    # 그린워싱 경로(G1b ③): 실패한 실행의 결과·검토는 409 RUN_NOT_DONE, 목록 줄에는 그 실행이 failed 로 하나
    for path in (f"/greenwash/runs/{run_id}/result", f"/greenwash/runs/{run_id}/review"):
        refused = http.get(path, headers=headers)
        assert (refused.status_code, refused.json()["error"]["code"]) == (409, "RUN_NOT_DONE"), refused.text
    checks = http.get("/greenwash/checks", headers=headers)
    assert checks.status_code == 200, checks.text
    rows = [(r["runId"], r["status"], r["levelCounts"], r["review"]) for r in checks.json()["runs"]]
    assert rows == [(run_id, "failed", None, None)]
    assert [r["errorCode"] for r in checks.json()["runs"]] == ["setup_error"]  # 목록 줄의 code(밴드 G1e)
    assert [d["documentId"] for d in checks.json()["documents"]] == [document_id]


def test_a_pdf_without_a_text_layer_fails_in_extract_and_the_list_row_carries_the_code(
    http: httpx.Client, cleanup: tuple[str, str]
) -> None:
    """빈 쪽만 있는 PDF(코드로 지음 — 글자 층 없음) → POST /runs greenwash → 워커가 extract 에서 끝낸다: failed ·
    failedStep extract · errorCode no_text_layer(키 전 단계라 실호출 0). 목록 줄(GET /greenwash/checks)의 그 줄에도
    errorCode no_text_layer(밴드 G1e)."""
    tenant, _ = cleanup
    headers = exchange(http, tenant=tenant, sub="it-run-1")
    doc = pdfbuild.Doc()
    doc.new_page()
    doc.new_page()
    data = doc.tobytes()
    created = http.post("/documents", headers=headers, json={"fileName": "scan.pdf", "sizeBytes": len(data)})
    assert created.status_code == 201, created.text
    document_id = created.json()["document"]["id"]
    assert httpx.put(created.json()["upload"]["url"], content=data, timeout=20.0).status_code == 200
    confirmed = http.post(f"/documents/{document_id}/confirm", headers=headers)
    assert confirmed.status_code == 200, confirmed.text

    options = {"parts": {"ceo": [1], "company": [], "climate": []}}
    response = http.post(
        "/runs", headers=headers, json={"module": "greenwash", "documentId": document_id, "options": options}
    )
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]
    run = wait_until_finished(http, headers, run_id)
    assert (run["status"], run["failedStep"], run["errorCode"]) == ("failed", "extract", "no_text_layer"), run
    checks = http.get("/greenwash/checks", headers=headers)
    assert checks.status_code == 200, checks.text
    assert [(r["runId"], r["status"], r["errorCode"]) for r in checks.json()["runs"]] == [
        (run_id, "failed", "no_text_layer")
    ]


def wait_until_finished(http: httpx.Client, headers: dict[str, str], run_id: int) -> dict[str, Any]:
    """GET /runs/{id} 를 1초마다, done·failed 가 될 때까지(상한 RUN_WAIT_S)."""
    deadline = time.monotonic() + RUN_WAIT_S
    while True:
        got = http.get(f"/runs/{run_id}", headers=headers)
        assert got.status_code == 200, got.text
        body: dict[str, Any] = got.json()
        if body["status"] in ("done", "failed") or time.monotonic() > deadline:
            return body
        time.sleep(1.0)
