"""seed_company: 없으면 만들고, 같은 값이면 그대로, 다른 값이면 1(업무 층, 주인 역할 연결)."""

import io

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import transaction

from esgapi.organization.models import Company, Site

pytestmark = pytest.mark.django_db
A = {"name": "가 회사", "business_licence_number": "111-11-11111", "subdomain": "tenant-a"}


def seed(name: str, licence: str, subdomain: str) -> str:
    out = io.StringIO()
    call_command(
        "seed_company", "--name", name, "--business-licence-number", licence, "--subdomain", subdomain, stdout=out
    )
    return out.getvalue().strip()


def rows() -> list[tuple[int, str, str, str, bool]]:
    return list(
        Company.unscoped.order_by("id").values_list("id", "name", "business_licence_number", "subdomain", "is_active")
    )


def test_a_new_company_is_made_active_and_its_id_printed() -> None:
    printed = seed(*A.values())
    assert rows() == [(int(printed), *A.values(), True)]


def test_the_same_values_twice_leave_one_row() -> None:
    first = seed(*A.values())
    second = seed(*A.values())
    assert first == second
    assert len(rows()) == 1


def test_the_same_subdomain_with_other_values_is_refused() -> None:
    seed(*A.values())
    before = rows()
    with pytest.raises(CommandError, match="다른 값"):
        seed("다른 이름", A["business_licence_number"], A["subdomain"])
    assert rows() == before


def test_a_licence_number_taken_by_another_company_is_refused() -> None:
    seed(*A.values())
    before = rows()
    # 명령은 자동 커밋으로 돌지만 테스트는 바깥 트랜잭션 안이라, 겹침으로 깨진 문을 블록 하나로 가둔다.
    with pytest.raises(CommandError, match="겹친다"), transaction.atomic():
        seed("나 회사", A["business_licence_number"], "tenant-b")
    assert rows() == before


def test_a_second_company_can_be_made() -> None:
    seed(*A.values())
    seed("나 회사", "222-22-22222", "tenant-b")
    assert [row[3] for row in rows()] == ["tenant-a", "tenant-b"]


# ── 본사(K1b-1 ①) ────────────────────────────────────────────────────


def headquarters(company_id: int) -> list[tuple[str, bool, bool]]:
    return list(
        Site.unscoped.filter(company_id=company_id, is_headquarters=True).values_list(
            "name", "inventory_enabled", "is_headquarters"
        )
    )


def test_a_new_company_gets_one_headquarters() -> None:
    company_id = int(seed(*A.values()))
    assert headquarters(company_id) == [("본사", True, True)]
    assert Site.unscoped.filter(company_id=company_id).count() == 1


def test_seeding_twice_leaves_one_headquarters() -> None:
    company_id = int(seed(*A.values()))
    seed(*A.values())
    assert headquarters(company_id) == [("본사", True, True)]
    assert Site.unscoped.filter(company_id=company_id).count() == 1


def test_other_values_are_refused_and_add_no_site() -> None:
    company_id = int(seed(*A.values()))
    before = list(Site.unscoped.order_by("id").values_list("id", "name", "is_headquarters"))
    with pytest.raises(CommandError, match="다른 값"):
        seed("다른 이름", A["business_licence_number"], A["subdomain"])
    assert list(Site.unscoped.order_by("id").values_list("id", "name", "is_headquarters")) == before
    assert headquarters(company_id) == [("본사", True, True)]


def test_seeding_again_fills_a_company_left_without_its_headquarters() -> None:
    """회사 만들기와 본사 세우기는 자동 커밋 둘이다 — 사이에서 끊겨 본사 없는 회사가 남은 상태를 지어 다시 돌린다."""
    made = Company.register(
        name=A["name"], business_licence_number=A["business_licence_number"], subdomain=A["subdomain"]
    )
    assert Site.unscoped.filter(company_id=made.pk).count() == 0  # 분모: 본사 없는 회사
    assert seed(*A.values()) == str(made.pk)
    assert headquarters(made.pk) == [("본사", True, True)]


def test_a_site_already_named_headquarters_is_raised_not_duplicated() -> None:
    made = Company.register(
        name=A["name"], business_licence_number=A["business_licence_number"], subdomain=A["subdomain"]
    )
    plain = Site.for_company(made.pk).create(name="본사", inventory_enabled=False)
    seed(*A.values())
    assert list(Site.unscoped.filter(company_id=made.pk).values_list("id", "is_headquarters", "inventory_enabled")) == [
        (plain.pk, True, True)
    ]
