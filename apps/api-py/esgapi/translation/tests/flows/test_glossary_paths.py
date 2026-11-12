# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""용어집 엑셀 두 경로를 진짜 DB·인증으로 잰다(밴드 TR3a §3-2-2, 업무 층). 엑셀은 메모리에서 지은 것이다(지어낸 짝 —
실제 용어집 0). 저장소는 가짜(FakeStorage — 읽기가 아무것도 두지 않는지 객체 수로 잰다).

    read      정상 200 ok:true · 거절 200 ok:false(kind·row·글) · 빈 본문·JSON 본문 200 not_xlsx · 본문 상한 넘음 413
              · 읽은 뒤 DB 의 모든 표 행 수·저장소 객체 수 그대로 · 로그에 칸 값 0
    template  200 · xlsx 머리·Content-Disposition·nosniff · 그 바이트를 read 에 보내면 no_rows
"""

import logging
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from pydantic import TypeAdapter

from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.translation.contracts.glossary_shapes import TranslationGlossaryRead
from esgapi.translation.service.actions import glossary as actions
from esgapi.translation.tests.tools import glossary_support as s
from esgapi.translation.tools import glossary_xlsx
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

READ = "/api/translation/glossary/read"
TEMPLATE = "/api/translation/glossary/template"
XLSX = actions.MEDIA_TYPE
BODY_LIMIT = 2_621_440
"""DATA_UPLOAD_MAX_MEMORY_SIZE(config/settings/base.py) — 넘으면 413 body_too_large."""
SECRET_KO = "비밀가상용어"
SECRET_EN = "Secret Virtual Term"
"""로그에 새지 않아야 하는 칸 값(지어낸 것)."""

SHAPE: TypeAdapter[Any] = TypeAdapter(TranslationGlossaryRead)


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)


def post(client: Client, data: bytes, content_type: str = XLSX) -> Any:
    return client.generic("POST", READ, data, content_type=content_type)


def table_counts() -> dict[str, int]:
    """DB 의 모든 표의 행 수(읽기 앞뒤를 견준다)."""
    with connection.cursor() as cursor:
        counts: dict[str, int] = {}
        for table in connection.introspection.table_names(cursor):
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # 이름은 introspection 이 준 것
            row = cursor.fetchone()
            assert row is not None
            counts[table] = int(row[0])
    return counts


def test_a_glossary_is_read_into_pairs(client: Client, storage: FakeStorage) -> None:
    login(client)
    pairs = [("가상설비", "Virtual Facility"), ("가상사업장", "Virtual Site")]
    response = post(client, s.glossary(pairs))
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    SHAPE.validate_python(body, strict=True)
    assert body == {"ok": True, "pairs": [{"ko": k, "en": e} for k, e in pairs], "rowCount": 2}


def test_five_hundred_pairs_are_read_in_order(client: Client, storage: FakeStorage) -> None:
    login(client)
    pairs = s.synthetic_pairs(500)
    body = post(client, s.glossary(pairs)).json()
    assert body["ok"] is True and body["rowCount"] == 500
    assert [(p["ko"], p["en"]) for p in body["pairs"]] == pairs


def test_a_rejected_glossary_is_200_with_its_kind_row_and_sentence(client: Client, storage: FakeStorage) -> None:
    login(client)
    data = s.glossary([("가상설비", "Virtual Facility"), ("가상설비", "Another Facility")])
    response = post(client, data)
    assert response.status_code == 200
    body = response.json()
    SHAPE.validate_python(body, strict=True)
    assert body == {
        "ok": False,
        "kind": "duplicate_ko",
        "row": 3,
        "message": "3행의 한국어가 2행과 같아요 — 한 번만 적어 주세요.",
    }


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(b"", XLSX), (b'{"pairs": []}', "application/json"), (b"not a zip", "application/octet-stream")],
    ids=["empty", "json", "octet"],
)
def test_an_empty_or_json_body_is_200_not_xlsx(
    client: Client, storage: FakeStorage, data: bytes, content_type: str
) -> None:
    login(client)
    response = post(client, data, content_type)
    assert response.status_code == 200
    assert (response.json()["ok"], response.json()["kind"], response.json()["row"]) == (False, "not_xlsx", None)


def test_a_body_over_the_upload_limit_is_413(client: Client, storage: FakeStorage) -> None:
    login(client)
    response = post(client, b"\0" * (BODY_LIMIT + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")
    within = post(client, b"\0" * BODY_LIMIT)  # 상한 그대로는 본문으로 받는다 — 도구가 too_large 로 거절
    assert (within.status_code, within.json()["kind"]) == (200, "too_large")


def test_an_unsafe_xlsx_is_200_unsafe(client: Client, storage: FakeStorage) -> None:
    login(client)
    data = s.rezip(s.glossary([("가상설비", "Virtual Facility")]), add={"docProps/pad.xml": s.with_doctype(b"<a/>")})
    body = post(client, data).json()
    assert (body["ok"], body["kind"]) == (False, "unsafe_xlsx")


def test_reading_writes_nothing_and_logs_no_cell_value(
    client: Client, storage: FakeStorage, caplog: pytest.LogCaptureFixture
) -> None:
    """상태 없음: 읽은 뒤 DB 의 모든 표 행 수와 저장소 객체 수가 그대로다. 로그(접근 줄 포함)에 칸의 값이 없다."""
    login(client)
    before = (table_counts(), dict(storage.objects))
    caplog.set_level(logging.DEBUG)
    good = post(client, s.glossary([(SECRET_KO, SECRET_EN), ("가상설비", "Virtual Facility")]))
    bad = post(client, s.glossary([(SECRET_KO, SECRET_EN), (SECRET_KO, SECRET_EN)]))
    assert good.json()["ok"] is True and bad.json()["kind"] == "duplicate_ko"
    assert (table_counts(), dict(storage.objects)) == before
    assert sum(before[0].values()) > 0  # 분모: 로그인이 행을 남겼다 — 빈 DB 를 견준 것이 아니다
    logged = caplog.text
    assert caplog.records  # 분모: 접근 줄이 잡혔다
    assert SECRET_KO not in logged and SECRET_EN not in logged
    assert SECRET_KO not in bad.content.decode()  # 거절 글에도 칸 값이 없다


def test_the_template_is_an_xlsx_attachment_that_reads_as_no_rows(client: Client, storage: FakeStorage) -> None:
    login(client)
    before = table_counts()
    response = client.get(TEMPLATE)
    assert response.status_code == 200
    assert response["Content-Type"] == XLSX
    assert response["Content-Disposition"] == 'attachment; filename="translation-glossary-template.xlsx"'
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response.content == glossary_xlsx.template()
    assert response.content[:2] == b"PK"
    assert post(client, response.content).json()["kind"] == "no_rows"
    assert table_counts() == before
    assert storage.objects == {}
