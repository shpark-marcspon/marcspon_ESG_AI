# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""블록·좌표 결과 읽기(GET /translation/runs/{run_id}/layout — service/actions/layout.py, 밴드 TRS3 L1·L2). 업무 층.

몸은 셋째 결과 행 translation.layout@1 그대로(done·rejected 둘 다 200), 워드 흐름의 끝난 실행·다른 모듈·없는 id 는
404 NOT_FOUND, 안 끝남은 409 RUN_NOT_DONE — 오류 봉투 바이트는 발주서 §1-2 의 두 예 그대로. openapi 의 200 은
components TranslationLayout 을 가리킨다. ★ 행은 seed(apps.get_model)로 심는다(runs.models import 0). 전부 지어낸 것.
"""

import copy
import json
from typing import Any

import pytest
from django.apps import apps
from django.test import Client

from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE, LAYOUT_SHAPES
from esgapi.translation.flows import colab_158, pdf_158
from esgapi.translation.tests.contracts.test_layout_shapes import a_layout
from esgapi.translation.tests.service import seed
from tests.support.http import login

pytestmark = pytest.mark.django_db

ADAPTER = LAYOUT_SHAPES[LAYOUT_SHAPE]
NOT_FOUND = {"error": {"code": "NOT_FOUND", "message": "그런 실행이 없다", "fields": None, "legacyCode": "not_found"}}
NOT_DONE = {
    "error": {
        "code": "RUN_NOT_DONE",
        "message": "실행이 아직 끝나지 않았다",
        "fields": None,
        "legacyCode": "run_not_done",
    }
}


def url(run_id: int) -> str:
    return f"/api/translation/runs/{run_id}/layout"


def a_rejected_layout() -> dict[str, Any]:
    """파서 앞 거절의 꼴(흐름 pdf_158 의 _refused — 쪽·단위·문체 0, parser·pageCount null)."""
    base = a_layout()
    return {
        **base,
        "status": "rejected",
        "source": {**base["source"], "pageCount": None, "parser": None},
        "pages": [],
        "units": [],
        "variants": [],
        "skipped": {"emptyTables": [], "imageOnlyPages": []},
        "warnings": [],
    }


def pdf_run(company_id: int, *, status: str = "done", layout: dict[str, Any] | None = None) -> int:
    """PDF 흐름의 실행 하나. 끝났으면 seed 의 결과 둘(result@1·digest@1) 뒤에 셋째 결과 layout@1."""
    run_id = seed.run(company_id, seed.document(company_id), "general", status=status, flow_id=pdf_158.FLOW_ID)
    if status == "done":
        body = layout if layout is not None else a_layout()
        apps.get_model("runs", "RunResultRow").for_company(company_id).create(
            company_id=company_id, run_id=run_id, position=2, schema_version=LAYOUT_SHAPE, body=body
        )
    return run_id


@pytest.fixture
def client_a(client: Client, companies: tuple[int, int]) -> Client:
    login(client, tenant_id="tenant-a")
    return client


def test_a_done_pdf_run_answers_its_stored_layout(client_a: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    stored = a_layout()
    run_id = pdf_run(a, layout=copy.deepcopy(stored))
    got = client_a.get(url(run_id))
    assert got.status_code == 200, got.content.decode()
    assert json.loads(got.content) == stored
    ADAPTER.validate_python(got.json(), strict=True)


def test_a_rejected_pdf_run_answers_its_rejected_layout(client_a: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = pdf_run(a, layout=a_rejected_layout())
    got = client_a.get(url(run_id))
    assert got.status_code == 200, got.content.decode()
    assert (got.json()["status"], got.json()["variants"], got.json()["source"]["parser"]) == ("rejected", [], None)
    assert json.loads(got.content) == a_rejected_layout()


def test_a_done_word_run_has_no_layout_and_is_404(client_a: Client, companies: tuple[int, int]) -> None:
    a, _ = companies
    word = seed.run(a, seed.document(a), "general", flow_id=colab_158.FLOW_ID)
    got = client_a.get(url(word))
    assert (got.status_code, got.json()) == (404, NOT_FOUND)


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_an_unfinished_pdf_run_is_409(client_a: Client, companies: tuple[int, int], status: str) -> None:
    a, _ = companies
    run_id = pdf_run(a, status=status)
    got = client_a.get(url(run_id))
    assert (got.status_code, got.json()) == (409, NOT_DONE)


def test_another_module_a_missing_id_and_another_company_are_404(client_a: Client, companies: tuple[int, int]) -> None:
    a, b = companies
    green = pdf_run(a)
    apps.get_model("runs", "RunRow").for_company(a).filter(pk=green).update(module="greenwash")
    theirs = pdf_run(b)
    for run_id in (green, theirs, theirs + 1000):
        got = client_a.get(url(run_id))
        assert (got.status_code, got.json()) == (404, NOT_FOUND), run_id


def test_the_error_envelopes_are_the_contract_bytes(client_a: Client, companies: tuple[int, int]) -> None:
    """§1-2 의 두 예를 실제 응답 바이트로(칸 차례·fields null·legacyCode 소문자까지). 렌더러는 빈칸
    `, `·`: ` 에 한글을 \\uXXXX 로 적는다(json.dumps 기본) — JSON 값은 예와 같다."""
    a, _ = companies
    missing = client_a.get(url(10_000_000))
    running = client_a.get(url(pdf_run(a, status="processing")))
    assert missing.content.decode() == json.dumps(NOT_FOUND)
    assert running.content.decode() == json.dumps(NOT_DONE)


# ── L2 꼴 ──


def test_openapi_points_the_200_at_translation_layout() -> None:
    from esgapi.config.api import api

    document = api.get_openapi_schema()
    operation = document["paths"]["/translation/runs/{run_id}/layout"]["get"]
    assert operation["operationId"] == "translation_layout_get"
    assert operation["responses"][200]["content"]["application/json"]["schema"] == {
        "$ref": "#/components/schemas/TranslationLayout"
    }
    names = set(document["components"]["schemas"])
    assert {n for n in names if "Layout" in n or n in {"Skipped", "Unplaced", "PlacedUnit", "PlacedCell"}} == {
        "TranslationLayout",
        "TranslationLayoutCell",
        "TranslationLayoutMember",
        "TranslationLayoutPage",
        "TranslationLayoutParser",
        "TranslationLayoutPlacedCell",
        "TranslationLayoutPlacedUnit",
        "TranslationLayoutSkipped",
        "TranslationLayoutSource",
        "TranslationLayoutUnit",
        "TranslationLayoutUnplaced",
        "TranslationLayoutVariant",
        "TranslationLayoutWarning",
    }
