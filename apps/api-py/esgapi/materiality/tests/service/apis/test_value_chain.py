# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""가치사슬 엑셀 읽기 경로 POST /materiality/value-chain/read 를 진짜 DB·인증으로 잰다(밴드 IRW2 §2-1, 업무 층 —
translation/tests/flows/test_glossary_paths.py 의 read 꼴을 옮김). 엑셀은 메모리에서 지은 것이다(지어낸 행 — 실제
가치사슬 0). 저장소는 가짜(FakeStorage — 읽기가 아무것도 두지 않는지 객체 수로 잰다).

    정상 200 ok:true(마크스폰 템플릿 꼴 포함) · 거절 200 ok:false(kind·row·column·글) · 빈 본문·JSON 본문 200 not_xlsx
    · 본문 상한 넘음 413 · 세션 없이 401 · 운영 관리자 Bearer 200(회사를 고르지 않는다 — 작업 회사 포트를 부르지 않음)
    · 읽은 뒤 DB 의 모든 표 행 수·저장소 객체 수 그대로 · 로그에 칸 값 0
"""

import logging
from typing import Any
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
from esgapi.materiality.contracts.value_chain_shapes import MaterialityValueChainRead
from esgapi.materiality.service.actions import value_chain as actions
from esgapi.materiality.tests.tools import value_chain_support as s
from tests.support.http import bearer, login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

READ = "/api/materiality/value-chain/read"
XLSX = actions.MEDIA_TYPE
BODY_LIMIT = 2_621_440
"""DATA_UPLOAD_MAX_MEMORY_SIZE(config/settings/base.py) — 넘으면 413 body_too_large."""
SECRET = "비밀가상부문"
"""로그에 새지 않아야 하는 칸 값(지어낸 것)."""
FIRST = ("가상부문", "가상 시공 사업", "업스트림", "가상협력사", "자재 조달")
KEYS = ("business_unit", "business_unit_description", "value_chain_stage", "stakeholder", "business_activity")

SHAPE: TypeAdapter[Any] = TypeAdapter(MaterialityValueChainRead)


@pytest.fixture
def storage(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> FakeStorage:
    return plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)


def post(client: Client, data: bytes, content_type: str = XLSX, **extra: Any) -> Any:
    return client.generic("POST", READ, data, content_type=content_type, **extra)


def row(values: tuple[str, ...]) -> dict[str, str]:
    return dict(zip(KEYS, values, strict=True))


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


def test_a_table_is_read_into_rows(client: Client, storage: FakeStorage) -> None:
    login(client)
    second = ("가상부문둘", "", "다운스트림", "가상고객", "점검")
    response = post(client, s.table([FIRST, second]))
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    SHAPE.validate_python(body, strict=True)
    assert body == {"ok": True, "rows": [row(FIRST), row(second)], "rowCount": 2}


def test_the_template_like_sheet_is_read(client: Client, storage: FakeStorage) -> None:
    login(client)
    body = post(client, s.template_like()).json()
    assert (body["ok"], body["rowCount"]) == (True, 4)
    assert [r["value_chain_stage"] for r in body["rows"]] == ["업스트림", "자체운영", "자체운영", "다운스트림"]
    assert {r["business_unit"] for r in body["rows"]} == {"ex.) 가상건설부문"}


def test_a_rejected_table_is_200_with_its_kind_row_column_and_sentence(client: Client, storage: FakeStorage) -> None:
    login(client)
    response = post(client, s.book([list(FIRST), ["가상", "", "업스트림", 7, ""]]))
    assert response.status_code == 200
    body = response.json()
    SHAPE.validate_python(body, strict=True)
    assert body == {
        "ok": False,
        "kind": "not_text",
        "row": 2,
        "column": 3,
        "message": "2행의 이해관계자 칸이 글자가 아니에요 — 셀 서식을 텍스트로 바꿔 주세요.",
    }


@pytest.mark.parametrize(
    ("data", "content_type"),
    [(b"", XLSX), (b'{"rows": []}', "application/json"), (b"not a zip", "application/octet-stream")],
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
    data = s.rezip(s.table([FIRST]), add={"docProps/pad.xml": s.with_doctype(b"<a/>")})
    body = post(client, data).json()
    assert (body["ok"], body["kind"]) == (False, "unsafe_xlsx")


def test_without_a_session_it_is_401(client: Client, storage: FakeStorage) -> None:
    response = post(Client(), s.table([FIRST]))
    assert response.status_code == 401
    assert "가상부문" not in response.content.decode()


def test_an_operator_reads_without_choosing_a_company(
    client: Client, storage: FakeStorage, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MARC-ENT-419: 운영 관리자도 같은 화면 — 테넌트 행을 읽지 않으므로 작업 회사 포트를 부르지 않고 200."""
    asked: list[bool] = []

    def chosen() -> int:
        asked.append(True)
        raise AssertionError("작업 회사를 고르지 않는다")

    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", chosen)
    claims = new_access_claims(
        user_id="9103",
        kind="admin",
        level=99,
        company_id=None,
        company_is_active=None,
        is_initial=False,
        jti=uuid4(),
        now=now(),
    )
    response = post(Client(), s.table([FIRST]), **bearer(sign_access(claims, secret=app_config().session_secret)))
    assert response.status_code == 200, response.content.decode()
    assert response.json() == {"ok": True, "rows": [row(FIRST)], "rowCount": 1}
    assert asked == []


def test_reading_writes_nothing_and_logs_no_cell_value(
    client: Client, storage: FakeStorage, caplog: pytest.LogCaptureFixture
) -> None:
    """상태 없음: 읽은 뒤 DB 의 모든 표 행 수와 저장소 객체 수가 그대로다. 로그(접근 줄 포함)에 칸의 값이 없다."""
    login(client)
    before = (table_counts(), dict(storage.objects))
    caplog.set_level(logging.DEBUG)
    good = post(client, s.table([(SECRET, "", "업스트림", "", ""), FIRST]))
    bad = post(client, s.book([[SECRET, "", "업스트림", "", "v" * 201]]))
    assert good.json()["ok"] is True and bad.json()["kind"] == "too_long"
    assert (table_counts(), dict(storage.objects)) == before
    assert sum(before[0].values()) > 0  # 분모: 로그인이 행을 남겼다 — 빈 DB 를 견준 것이 아니다
    assert caplog.records  # 분모: 접근 줄이 잡혔다
    assert SECRET not in caplog.text
    assert SECRET not in bad.content.decode()  # 거절 글에도 칸 값이 없다
