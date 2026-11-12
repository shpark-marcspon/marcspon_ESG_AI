# pyright: reportUnknownMemberType=false
"""영문번역 PDF 흐름(translation.pdf@158 — 밴드 TRD2 D2)이 떠 있는 컨테이너에서 끝까지 서는가. 테스트 하나.

시험 안에서 지은 PDF(글자 층 있는 한 쪽 — 지어낸 영문 두 줄)를 올리고 POST /runs {flowId: translation.pdf@158} →
워커가 진짜 파서(services/parser, 분해 판 2)를 불러 태그 글을 짓고 모의 공급사로 번역해 done. 결과 행(주인 연결로
run_results 를 읽음)의 translation.layout@1 에 파서 판 2 와 상자가 있다.

★ 공급사는 모의뿐이다: 서버가 live 가 아니면 끼움이 모의 경로를 싣는다(MARC-ISSUE-331). 결과 result@1 의 경로가 모두
  `mock` 인지를 단언한다 — 키가 있어도 실호출 0 을 확인하는 줄.
★ 무효 조건: 이미지가 지금 소스로 빌드됐을 때만 지금 코드를 잰다(scripts/with-build-lock.sh docker compose build
  api-py worker-py parser 뒤). 옛 파서 이미지면 parser.layout 이 2 가 아니어서 실행이 step_error 로 끝난다. 모의 번역
  글이 태그를 따르지 않으므로 번역의 되붙임(level)은 재지 않는다 — 그것은 업무 층 tests/flows/test_pdf_158.py.
★ 원본은 시험 안에서 지은 PDF 다(저장소 고정물 0 — 공개 보고서 0).
"""

from collections.abc import Iterator
from typing import Any

import httpx
import psycopg
import pytest

from esgapi.greenwash.tests import pdfbuild
from tests_integration.conftest import company_id_of, wait_for
from tests_integration.test_flow import exchange

Owner = psycopg.Connection[tuple[Any, ...]]
RUN_WAIT_S = 120.0  # 워커가 파서 분해 + 모의 번역 사슬을 끝내기까지의 상한
MAX_BOXES = 10  # 지은 PDF 는 글 두 줄 — 상자가 이보다 많으면 분해·묶기가 어긋난 것


@pytest.fixture
def cleanup(owner: Owner, two_tenants: tuple[str, str]) -> Iterator[tuple[str, str]]:
    """이 실행이 만든 행을 끝에서 주인 연결로 지운다(conftest 의 two_tenants 가 회사를 지우기 전에)."""
    yield two_tenants
    companies = [company_id_of(owner, subdomain) for subdomain in two_tenants]
    tables = (
        "core_llm_call_logs",
        "run_results",
        "run_files",
        "run_steps",
        "run_runs",
        "run_jobs",
        "core_documents",
    )
    for table in tables:
        owner.execute(f"DELETE FROM {table} WHERE company_id = ANY(%s)", [companies])  # noqa: S608 — 표 이름은 위 상수


def synthetic_pdf() -> bytes:
    doc = pdfbuild.Doc()
    page = doc.new_page(width=595, height=842)
    page.insert_text((72, 100), "Water stewardship", fontsize=14)
    page.insert_text((72, 130), "The virtual site cut its water use this year.", fontsize=10)
    return doc.tobytes()


def test_a_pdf_translation_run_is_done_with_a_layout_from_the_running_parser(
    http: httpx.Client, owner: Owner, cleanup: tuple[str, str]
) -> None:
    tenant, _ = cleanup
    headers = exchange(http, tenant=tenant, sub="it-trd2-1")
    data = synthetic_pdf()
    created = http.post("/documents", headers=headers, json={"fileName": "virtual.pdf", "sizeBytes": len(data)})
    assert created.status_code == 201, created.text
    document_id = created.json()["document"]["id"]
    assert httpx.put(created.json()["upload"]["url"], content=data, timeout=20.0).status_code == 200
    assert http.post(f"/documents/{document_id}/confirm", headers=headers).status_code == 200

    options = {
        "company": {"name": "가상고객사", "preferredSubject": "가상 업종", "industryStandards": "GRI"},
        "part": "general",
        "style": {"compareAb": False, "single": "B"},
        "pages": {"start": None, "end": None},
        "ceoPageLimit": 6,
    }
    body = {"module": "translation", "flowId": "translation.pdf@158", "documentId": document_id, "options": options}
    response = http.post("/runs", headers=headers, json=body)
    assert response.status_code == 201, response.text
    run_id = response.json()["id"]

    def finished() -> dict[str, Any] | None:
        got = http.get(f"/runs/{run_id}", headers=headers)
        assert got.status_code == 200, got.text
        run: dict[str, Any] = got.json()
        return run if run["status"] in ("done", "failed") else None

    run = wait_for(f"실행 {run_id} 이 끝남", finished, timeout=RUN_WAIT_S)
    assert (run["status"], run.get("errorCode")) == ("done", None), run

    rows = owner.execute(
        "SELECT schema_version, body FROM run_results WHERE run_id = %s ORDER BY position", [run_id]
    ).fetchall()
    found = {str(version): body for version, body in rows}
    assert sorted(found) == ["translation.digest@1", "translation.layout@1", "translation.result@1"]
    result, layout = found["translation.result@1"], found["translation.layout@1"]
    assert set(result["settings"]["routes"].values()) == {"mock"}  # 키가 있어도 모의 — 실호출 0
    assert layout["source"]["parser"]["layout"] == 2
    assert [p["page"] for p in layout["pages"]] == [1] and layout["pages"][0]["textLayer"] == "present"
    boxes = [m["bbox"] for unit in layout["units"] for m in unit["members"]]
    assert 1 <= len(boxes) <= MAX_BOXES, boxes
    for x0, y0, x1, y1 in boxes:
        assert 0 <= x0 < x1 <= 595 and 0 <= y0 < y1 <= 842  # pt · 쪽 왼쪽 위 원점
