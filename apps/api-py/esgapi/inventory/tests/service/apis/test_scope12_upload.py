"""Scope 1·2 일괄 올리기 경로(밴드 S12b-2 ③ — service/apis/scope12_excel.py 의 POST …/uploads). 업무 층.

두 역할 200 · 회사 둘 400 · 빈·JSON·zip 아닌 바이트 422 `fields.file` · 20MB(GHG_UPLOAD_MAX_BYTES — MARC-ENT-593) 넘음
413 · 상한 그대로는 받음 · 10~20MiB 양식 200 · 다른 경로는 2.5MB 그대로 · 응답 꼴 · 422 몸 · 409. 판정
갈래는 actions 시험(test_scope12_upload)이 잰다. 격리는 tests/security/test_scope12_upload.py 가 앱 역할로 잰다.
값은 지어낸 것이다.
"""

from typing import Any

import pytest
from django.conf import settings
from django.http import HttpRequest
from django.test import Client

from esgapi.core.exceptions import ApplicationError
from esgapi.inventory.models import InventoryEntryHistory
from esgapi.inventory.service.actions import entries
from esgapi.inventory.service.actions import scope12_upload as actions
from esgapi.inventory.service.apis import scope12_excel
from esgapi.inventory.tests.index_selection_support import YEAR
from esgapi.inventory.tests.s3sheets_support import MiB, padded
from esgapi.inventory.tests.service.actions.test_scope12_upload import CUSTOMER, World, address, filled, leaves, world
from esgapi.inventory.tests.service.apis.test_entries import customer, operator_access, operator_on
from esgapi.inventory.tools import xlsx_reader
from esgapi.inventory.tools.scope12_upload import NOT_XLSX, TOO_LARGE
from esgapi.inventory.tools.scope12_xlsx import MEDIA_TYPE
from esgapi.inventory.tools.xlsx_reader import GHG_UPLOAD_MAX_BYTES

pytestmark = pytest.mark.django_db
SHARED_FIXTURES = (leaves, world)  # actions 시험의 고정물을 이 모듈에서도 이름으로 찾게

URL = f"/api/inventory/scope12/years/{YEAR}/uploads"


def post(client: Client, data: bytes, content_type: str = MEDIA_TYPE, url: str = URL) -> Any:
    return client.post(url, data=data, content_type=content_type)


def good(world: World) -> bytes:
    return filled(world.template(), (world.a, "가상 가", "월", "1월", 1000))


def test_a_customer_uploads_and_gets_the_counts(world: World) -> None:
    response = post(customer(world.company_id, "tenant-a"), good(world))
    assert response.status_code == 200, response.content
    assert response.json() == {"added": 1, "filled": 1, "unchanged": 0, "unresolved": 0}


def test_an_operator_uploads_to_the_working_company(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    response = post(operator_on(world.company_id, monkeypatch), good(world))
    assert response.status_code == 200, response.content
    assert world.amounts(world.a, world.ga)  # 작업 회사에 들었다
    kinds = InventoryEntryHistory.for_company(world.company_id).values_list("actor_kind", flat=True)
    assert list(kinds) == ["admin"]  # 히스토리에 운영 관리자로 남는다


def test_an_operator_with_two_companies_is_asked_to_choose(world: World) -> None:
    operator = Client(headers={"Authorization": f"Bearer {operator_access()}"})  # 진짜 포트 — 시험 DB 는 회사 둘
    response = post(operator, good(world))
    assert (response.status_code, response.json()["error"]["code"]) == (400, "COMPANY_AMBIGUOUS")
    assert world.amounts(world.a, world.ga) == {}


@pytest.mark.parametrize(
    ("body", "content_type"),
    [(b"", MEDIA_TYPE), (b'{"a": 1}', "application/json"), (b"not a zip", "application/octet-stream")],
)
def test_bytes_that_are_not_a_workbook_are_a_422_on_file(world: World, body: bytes, content_type: str) -> None:
    response = post(customer(world.company_id, "tenant-a"), body, content_type)
    assert response.status_code == 422, response.content
    assert response.json() == {
        "error": {
            "code": "INVALID_UPLOAD",
            "legacyCode": "invalid_upload",
            "message": "올린 파일을 확인한다",
            "fields": {"file": [NOT_XLSX]},
        }
    }


def test_a_cell_problem_comes_back_by_address_in_the_common_shape(world: World) -> None:
    template = world.template()
    data = filled(template, (world.a, "가상 가", "월", "1월", "가상"))
    response = post(customer(world.company_id, "tenant-a"), data)
    at = address(template, world.a, "가상 가", "월", "1월")
    assert response.status_code == 422
    body = response.json()["error"]
    assert (body["code"], body["legacyCode"], list(body["fields"])) == ("INVALID_UPLOAD", "invalid_upload", [at])
    assert isinstance(body["fields"][at], list)


def test_a_file_over_the_cell_limit_is_a_422_not_a_500(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    data = good(world)
    monkeypatch.setattr(xlsx_reader, "MAX_CELLS", 3)
    response = post(customer(world.company_id, "tenant-a"), data)
    assert response.status_code == 422
    assert response.json()["error"]["fields"] == {"file": [TOO_LARGE]}


def test_the_limit_is_twenty_mib() -> None:
    assert GHG_UPLOAD_MAX_BYTES == 20 * MiB == 20_971_520
    assert settings.DATA_UPLOAD_MAX_MEMORY_SIZE == 2_621_440  # 전역은 그대로다(config 0줄)


def test_a_body_over_the_limit_is_a_413(world: World) -> None:
    data = b"0" * (GHG_UPLOAD_MAX_BYTES + 1)
    response = post(customer(world.company_id, "tenant-a"), data)
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")
    assert world.amounts(world.a, world.ga) == {}


def test_a_declared_length_over_the_limit_is_a_413_before_reading(world: World) -> None:
    """머리 CONTENT_LENGTH 가 상한을 넘으면 본문을 읽기 전에 413 이다(실은 본문은 작은 양식)."""
    client = customer(world.company_id, "tenant-a")
    response = client.post(URL, data=good(world), content_type=MEDIA_TYPE, CONTENT_LENGTH=str(GHG_UPLOAD_MAX_BYTES + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")
    assert world.amounts(world.a, world.ga) == {}


def test_permission_is_judged_before_the_body_size(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    """차례: permitted() 가 먼저다 — 허락 없는 주체는 머리 값이 상한을 넘어도 413 이 아니라 403 이다."""

    def refused(request: HttpRequest, operation_id: str) -> Any:
        raise ApplicationError("forbidden", "forbidden", "지어낸 거절")

    monkeypatch.setattr(scope12_excel, "permitted", refused)
    client = customer(world.company_id, "tenant-a")
    response = client.post(URL, data=b"0", content_type=MEDIA_TYPE, CONTENT_LENGTH=str(GHG_UPLOAD_MAX_BYTES + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (403, "FORBIDDEN")


def test_the_read_length_is_checked_even_when_the_declared_length_is_not(
    world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """머리 값만 믿지 않는다: 머리 검사가 못 본 꼴(0)이어도 읽은 길이가 상한을 넘으면 413 이다."""

    def unseen(request: HttpRequest) -> int:
        return 0

    monkeypatch.setattr(scope12_excel, "_declared_length", unseen)
    response = post(customer(world.company_id, "tenant-a"), b"0" * (GHG_UPLOAD_MAX_BYTES + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")


def test_a_body_of_exactly_the_limit_is_read_not_refused_for_size(world: World) -> None:
    response = post(customer(world.company_id, "tenant-a"), b"0" * GHG_UPLOAD_MAX_BYTES)
    assert response.status_code == 422  # 크기가 아니라 xlsx 가 아니라서
    assert response.json()["error"]["fields"] == {"file": [NOT_XLSX]}


def test_a_template_between_ten_and_twenty_mib_is_uploaded(world: World) -> None:
    data = padded(good(world), 15 * MiB)
    assert xlsx_reader.MAX_BYTES < len(data) == 15 * MiB < GHG_UPLOAD_MAX_BYTES
    response = post(customer(world.company_id, "tenant-a"), data)
    assert response.status_code == 200, response.content
    assert response.json() == {"added": 1, "filled": 1, "unchanged": 0, "unresolved": 0}


def test_another_body_path_keeps_the_global_limit(world: World) -> None:
    """이 경로만 넓혔다: 다른 본문 경로(inventory_calc)는 전역 2.5MB + 1 바이트에 413 이다."""
    data = b"x" * (settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1)
    response = post(customer(world.company_id, "tenant-a"), data, "application/json", "/api/inventory/calc")
    assert (response.status_code, response.json()["error"]["code"]) == (413, "BODY_TOO_LARGE")


def test_no_year_is_a_404(world: World) -> None:
    url = f"/api/inventory/scope12/years/{YEAR + 1}/uploads"
    response = post(customer(world.company_id, "tenant-a"), b"", url=url)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")


def test_a_lock_race_is_a_409(world: World, monkeypatch: pytest.MonkeyPatch) -> None:
    data = good(world)
    real = actions._details  # pyright: ignore[reportPrivateUsage]

    def locked_after_judging(company_id: int, *rest: Any) -> object:
        found = real(company_id, *rest)
        entries.lock_index(company_id, YEAR, world.a.id, CUSTOMER)  # 판정을 지난 뒤 잠긴 꼴
        return found

    monkeypatch.setattr(actions, "_details", locked_after_judging)
    response = post(customer(world.company_id, "tenant-a"), data)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "LOCKED")
