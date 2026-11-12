# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""EDK 인벤토리 엑셀 두 경로 POST /dataverify/edk/read · GET /dataverify/edk/template 를 진짜 DB·인증으로 잰다(밴드 DVX1
§3 ①, 업무 층 — materiality/tests/service/apis/test_value_chain.py 꼴을 옮김). 엑셀은 메모리에서 지은 것이다(가상 기업·
가상 값). 저장소는 가짜(FakeStorage — 읽기가 아무것도 두지 않는지 객체 수로 잰다).

    읽기: 정상 200 ok:true(대상 테마만 · skipped 수) · 거절 200 ok:false(kind·row·column·글) · 빈 본문·JSON 본문
    200 not_xlsx · 본문 상한 넘음 413 · 세션 없이 401 · 운영 관리자 Bearer 200(회사를 고르지 않는다) · 앞뒤 DB 표 행
    수·저장소 객체 수 그대로 · 로그에 칸 값 0
    양식: 200 + 머리 셋(Content-Type·Content-Disposition·nosniff) · 401 · 운영 관리자 200 · DB·저장소 그대로 · year
    생략 = 시계의 해 − 1 · 꼴 밖 year 422 · 두 번 같은 바이트 · 내려받은 양식을 읽기에 넣으면 예시 한 항목(왕복)
"""

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import quote
from uuid import uuid4

import pytest
from django.db import connection
from django.test import Client
from django.urls import get_resolver
from pydantic import TypeAdapter

from esgapi.core.auth import bearer as bearer_module
from esgapi.core.auth.tokens import new_access_claims, sign_access
from esgapi.core.conf import app_config, now
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.dataverify.contracts.edk_read_shapes import DataverifyEdkRead
from esgapi.dataverify.service.actions import edk as actions
from esgapi.dataverify.tests.tools import edk_xlsx_support as s
from tests.support.http import bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

READ = "/api/dataverify/edk/read"
TEMPLATE = "/api/dataverify/edk/template"
XLSX = actions.MEDIA_TYPE
BODY_LIMIT = 2_621_440
"""DATA_UPLOAD_MAX_MEMORY_SIZE(config/settings/base.py) — 넘으면 413 body_too_large."""
SECRET = "비밀가상항목"
"""로그에 새지 않아야 하는 칸 값(지어낸 것)."""
OTHER = "가상사회"

SHAPE: TypeAdapter[Any] = TypeAdapter(DataverifyEdkRead)


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)


def post(client: Client, data: bytes, content_type: str = XLSX, **extra: Any) -> Any:
    return client.generic("POST", READ, data, content_type=content_type, **extra)


def table_counts() -> dict[str, int]:
    """DB 의 모든 표의 행 수(읽기 앞뒤를 견준다)."""
    with connection.cursor() as cursor:
        counts: dict[str, int] = {}
        for table in connection.introspection.table_names(cursor):
            cursor.execute(f'SELECT count(*) FROM "{table}"')  # 이름은 introspection 이 준 것
            found = cursor.fetchone()
            assert found is not None
            counts[table] = int(found[0])
    return counts


def book() -> bytes:
    return s.book(
        [
            s.row(1.0, "환경", "가상 직접 배출량", [100, 110.0, None]),
            [None] * 14,
            s.row(2, OTHER, "가상 임직원", [1, 2, 3]),
            s.row(3, OTHER, "가상 교육", [1, 2, 3]),
        ]
    )


def operator_headers() -> dict[str, Any]:
    claims = new_access_claims(
        user_id="9104",
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    return bearer(sign_access(claims, secret=app_config().session_secret))


@pytest.fixture
def no_company_choice(monkeypatch: pytest.MonkeyPatch) -> list[bool]:
    """MARC-ENT-419 꼴: 테넌트 행을 읽지 않으므로 작업 회사 포트를 부르지 않는다 — 부르면 빨강."""
    asked: list[bool] = []

    def chosen() -> int:
        asked.append(True)
        raise AssertionError("작업 회사를 고르지 않는다")

    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", chosen)
    return asked


# ── 읽기 ──


def test_a_book_is_read_into_the_target_theme_data(client: Client, storage: FakeStorage) -> None:
    login(client)
    response = post(client, book())
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    SHAPE.validate_python(body, strict=True)
    assert body == {
        "ok": True,
        "data": {
            "환경": [
                {
                    "ID": 1,
                    "테마": "환경",
                    "항목": "가상 직접 배출량",
                    "대분류": "가상대분류",
                    "중분류": "가상중분류",
                    "소분류": "가상소분류",
                    "입력 방식": "숫자",
                    "단위": "tCO2eq",
                    "values": {"2022": 100, "2023": 110, "2024": None},
                    "핵심데이터": "Y",
                    "메모": None,
                }
            ]
        },
        "itemCount": 1,
        "skipped": {"themes": 1, "items": 2},
        "years": ["2022", "2023", "2024"],
        "skippedEmptyRows": 1,
        "ignoredColumns": 1,
    }
    assert OTHER not in response.content.decode()


def test_a_rejected_book_is_200_with_its_kind_row_column_and_sentence(client: Client, storage: FakeStorage) -> None:
    login(client)
    response = post(client, s.book([s.row(1, "환경", "가상", [1, True, 3])]))
    assert response.status_code == 200
    body = response.json()
    SHAPE.validate_python(body, strict=True)
    assert body == {
        "ok": False,
        "kind": "bad_cell",
        "row": 2,
        "column": 10,
        "message": "2행 10열에 날짜나 참/거짓 칸이 있어요 — 숫자나 글자로 바꿔 주세요.",
    }


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(b"", XLSX), ('{"환경": []}'.encode(), "application/json"), (b"not a zip", "application/octet-stream")],
    ids=["empty", "json", "octet"],
)
def test_an_empty_or_json_body_is_200_not_xlsx(
    client: Client, storage: FakeStorage, data: bytes, content_type: str
) -> None:
    login(client)
    response = post(client, data, content_type)
    assert response.status_code == 200
    body = response.json()
    assert (body["ok"], body["kind"], body["row"], body["column"]) == (False, "not_xlsx", None, None)


def test_a_body_over_the_upload_limit_is_413(client: Client, storage: FakeStorage) -> None:
    login(client)
    response = post(client, b"\0" * (BODY_LIMIT + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")
    within = post(client, b"\0" * BODY_LIMIT)  # 상한 그대로는 본문으로 받는다 — 도구가 too_large 로 거절
    assert (within.status_code, within.json()["kind"]) == (200, "too_large")


def test_an_unsafe_xlsx_is_200_unsafe(client: Client, storage: FakeStorage) -> None:
    login(client)
    data = s.rezip(book(), add={"docProps/pad.xml": s.with_doctype(b"<a/>")})
    body = post(client, data).json()
    assert (body["ok"], body["kind"]) == (False, "unsafe_xlsx")


def test_without_a_session_the_read_is_401(client: Client, storage: FakeStorage) -> None:
    response = post(Client(), s.book([s.row(1, "환경", SECRET, [1, 2, 3])]))
    assert response.status_code == 401
    assert SECRET not in response.content.decode()


def test_an_operator_reads_without_choosing_a_company(
    client: Client, storage: FakeStorage, no_company_choice: list[bool]
) -> None:
    response = post(Client(), book(), **operator_headers())
    assert response.status_code == 200, response.content.decode()
    assert (response.json()["ok"], response.json()["itemCount"]) == (True, 1)
    assert no_company_choice == []


def test_reading_writes_nothing_and_logs_no_cell_value(
    client: Client, storage: FakeStorage, caplog: pytest.LogCaptureFixture
) -> None:
    """상태 없음: 읽은 뒤 DB 의 모든 표 행 수와 저장소 객체 수가 그대로다. 로그(접근 줄 포함)·거절 글에 칸 값이 없다."""
    login(client)
    before = (table_counts(), dict(storage.objects))
    caplog.set_level(logging.DEBUG)
    good = post(client, s.book([s.row(1, "환경", SECRET, [1, 2, 3])]))
    bad = post(client, s.book([s.row(1, None, SECRET, [1, 2, 3])]))
    assert good.json()["ok"] is True and bad.json()["kind"] == "no_theme"
    assert (table_counts(), dict(storage.objects)) == before
    assert sum(before[0].values()) > 0  # 분모: 로그인이 행을 남겼다 — 빈 DB 를 견준 것이 아니다
    assert caplog.records  # 분모: 접근 줄이 잡혔다
    assert SECRET not in caplog.text
    assert SECRET not in bad.content.decode()


# ── 양식 ──


def test_the_template_is_an_attachment_with_three_headers(client: Client, storage: FakeStorage) -> None:
    login(client)
    response = client.get(TEMPLATE, {"year": 2025})
    assert response.status_code == 200, response.content.decode()
    assert response["Content-Type"] == XLSX
    assert response["Content-Disposition"] == f"attachment; filename*=utf-8''{quote(actions.FILE_NAME)}"
    assert response["X-Content-Type-Options"] == "nosniff"
    assert response.content == actions.template(2025)


def test_the_template_round_trips_through_the_read(client: Client, storage: FakeStorage) -> None:
    login(client)
    first = client.get(TEMPLATE, {"year": 2025}).content
    assert client.get(TEMPLATE, {"year": 2025}).content == first  # 두 번 같은 바이트
    body = post(client, first).json()
    SHAPE.validate_python(body, strict=True)
    assert (body["ok"], body["itemCount"], body["years"]) == (True, 1, ["2023", "2024", "2025"])
    assert body["data"]["환경"][0]["항목"] == "가상 직접 배출량"


def test_the_template_year_defaults_to_last_year_of_the_clock(
    client: Client, storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(actions, "now", lambda: datetime(2031, 3, 1, tzinfo=UTC))
    login(client)
    assert client.get(TEMPLATE).content == actions.template(2030)
    assert post(client, client.get(TEMPLATE).content).json()["years"] == ["2028", "2029", "2030"]


@pytest.mark.parametrize("year", ["1001", "10000", "abc", "-1"])
def test_a_year_off_the_shape_is_422(client: Client, storage: FakeStorage, year: str) -> None:
    login(client)
    assert client.get(TEMPLATE, {"year": year}).status_code == 422
    assert client.get(TEMPLATE, {"year": "1002"}).status_code == 200  # 분모: 아래 끝은 받는다


def test_without_a_session_the_template_is_401(client: Client, storage: FakeStorage) -> None:
    assert Client().get(TEMPLATE).status_code == 401


def test_an_operator_downloads_the_template_and_nothing_is_written(
    client: Client, storage: FakeStorage, no_company_choice: list[bool]
) -> None:
    login(client)  # 분모의 행(로그인) — 빈 DB 를 견주지 않게
    before = (table_counts(), dict(storage.objects))
    response = Client().get(TEMPLATE, {"year": 2024}, **operator_headers())
    assert (response.status_code, response["Content-Type"]) == (200, XLSX)
    assert (table_counts(), dict(storage.objects)) == before
    assert sum(before[0].values()) > 0
    assert no_company_choice == []
