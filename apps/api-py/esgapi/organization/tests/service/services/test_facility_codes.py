"""services/facility_codes.py(밴드 K1b-1 ②): 코드 목록(전 고객사 공통)의 쓰기 — 운영 관리자만. code 는 F<네 자리>로
INSERT 뒤 같은 블록의 UPDATE 가 채우고(감독 판단 3), 그 사이에서 깨지면 code 빈 행이 남지 않는다(검증자 조건 —
unique 아래에서도 NULL 둘은 들어간다). 이름을 고쳐도 code 는 그대로다. 업무 층. 이름·글은 지어낸 것이다."""

import re
from collections.abc import Collection

import pytest

from esgapi.organization.models import FacilityCode
from esgapi.organization.service.permissions.organization import Forbidden
from esgapi.organization.service.selectors import facility_codes as selectors
from esgapi.organization.service.services import facility_codes as services
from esgapi.organization.service.services.branches import InUse
from esgapi.organization.service.utils.entities import FacilityCodeInfo

pytestmark = pytest.mark.django_db
CODE = re.compile(r"^F\d{4}$")


def make(name: str) -> FacilityCodeInfo:
    made = services.create_code(actor_kind="admin", name=name)
    assert isinstance(made, FacilityCodeInfo), made
    return made


def test_a_new_code_is_f_and_four_digits_and_sorted_by_creation() -> None:
    first, second = make("보일러"), make("냉동기")
    assert CODE.match(first.code) and first.code == f"F{first.id:04d}"
    assert list(FacilityCode.objects.order_by("id").values_list("code", "sort_order")) == [
        (first.code, first.id),
        (second.code, second.id),
    ]


def test_a_failure_between_insert_and_update_leaves_no_row_without_a_code(monkeypatch: pytest.MonkeyPatch) -> None:
    make("보일러")

    def broken(code_id: int) -> str:
        raise RuntimeError("심은 실패 — INSERT 뒤 UPDATE 전")

    monkeypatch.setattr(services, "code_text", broken)
    for name in ("냉동기", "압축기"):  # 둘 — unique 는 NULL 둘을 막지 못한다
        with pytest.raises(RuntimeError):
            services.create_code(actor_kind="admin", name=name)
    assert FacilityCode.objects.filter(code__isnull=True).count() == 0
    assert list(FacilityCode.objects.values_list("name", flat=True)) == ["보일러"]


def test_renaming_keeps_the_code() -> None:
    made = make("보일러")
    renamed = services.rename_code(actor_kind="admin", code_id=made.id, name="증기 보일러")
    assert renamed == FacilityCodeInfo(id=made.id, code=made.code, name="증기 보일러")
    assert FacilityCode.objects.get(pk=made.id).code == made.code


def test_a_taken_name_is_refused_and_a_missing_code_is_not_found() -> None:
    made = make("보일러")
    other = make("냉동기")
    assert services.create_code(actor_kind="admin", name="보일러") == services.CodeNameTaken()
    assert services.rename_code(actor_kind="admin", code_id=other.id, name="보일러") == services.CodeNameTaken()
    assert services.rename_code(actor_kind="admin", code_id=made.id + 999, name="x") == services.CodesMissing()
    assert services.delete_codes(actor_kind="admin", ids=[made.id, made.id + 999]) == services.CodesMissing()
    assert FacilityCode.objects.filter(deleted_at__isnull=False).count() == 0  # 일부만 처리 0


def test_a_code_in_use_is_not_deleted() -> None:
    made = make("보일러")
    calls: list[frozenset[int]] = []

    def fake(ids: Collection[int]) -> frozenset[int]:
        calls.append(frozenset(ids))
        return frozenset({made.id})

    assert services.delete_codes(actor_kind="admin", ids=[made.id], facility_codes_in_use=fake) == InUse(
        frozenset({made.id})
    )
    assert calls == [frozenset({made.id})]
    assert FacilityCode.objects.get(pk=made.id).deleted_at is None
    assert selectors.facility_codes_in_use([made.id]) == frozenset()  # 진짜는 지금 늘 빈 집합
    assert services.delete_codes(actor_kind="admin", ids=[made.id]) == 1


def test_a_customer_kind_is_forbidden_before_any_write() -> None:
    assert services.create_code(actor_kind="service", name="보일러") == Forbidden(
        "organization_admin_facility_codes_create"
    )
    assert selectors.admin_code_page(actor_kind="service", offset=0, limit=20) == Forbidden(
        "organization_admin_facility_codes_list"
    )
    assert FacilityCode.objects.count() == 0
