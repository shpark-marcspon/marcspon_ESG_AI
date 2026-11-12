"""인벤토리 해·고객사 인덱스 선택의 쓰기(밴드 K1b-2b ② — service/services/index_selection.py). 업무 층.

경합은 제약 이름으로 갈래가 되고, 모르는 제약은 다시 던진다. 지우기는 삭제 표시(숨김을 끈다). 이름·값은 지어낸 것이다.
"""

import pytest
from django.db import IntegrityError

from esgapi.inventory.models import CompanyIndexSelection
from esgapi.inventory.service.services import index_selection as services
from esgapi.inventory.tests.index_selection_support import YEAR, current_version, two_leaves

pytestmark = pytest.mark.django_db


def year(company_id: int) -> int:
    made = services.create_year(company_id, YEAR)
    assert isinstance(made, int), made
    return made


def test_a_second_year_is_year_taken(companies: tuple[int, int]) -> None:
    a, b = companies
    year(a)
    assert services.create_year(a, YEAR) == services.YearTaken()
    year(b)  # 짝: 다른 회사는 따로


def test_a_second_alive_selection_is_selection_taken(companies: tuple[int, int]) -> None:
    a, _ = companies
    boiler, _ = two_leaves()
    row = services.NewSelection(boiler.id, current_version(boiler.id))
    year_id = year(a)
    assert services.insert_selections(a, year_id, [row]) == 1
    assert services.insert_selections(a, year_id, [row]) == services.SelectionTaken()
    assert CompanyIndexSelection.for_company(a).count() == 1


def test_an_unknown_constraint_is_raised(companies: tuple[int, int]) -> None:
    """남의 회사 해를 가리키면 같은 회사 외래 키(23503) — 갈래가 아니라 그대로 던진다(500 — 앱이 그 길을 막는다)."""
    a, b = companies
    boiler, _ = two_leaves()
    with pytest.raises(IntegrityError, match="same_company_fk"):
        services.insert_selections(a, year(b), [services.NewSelection(boiler.id, current_version(boiler.id))])


def test_hide_and_delete_only_touch_the_given_company(companies: tuple[int, int]) -> None:
    a, b = companies
    boiler, _ = two_leaves()
    row = services.NewSelection(boiler.id, current_version(boiler.id))
    for company in (a, b):
        assert services.insert_selections(company, year(company), [row]) == 1
    ids = [selection.pk for selection in CompanyIndexSelection.unscoped.all()]
    assert len(ids) == 2  # 분모
    assert services.set_hidden(a, ids, hidden=True) == 1  # B 의 id 가 섞여도 A 의 것만
    assert services.mark_selections_deleted(a, ids) == 1
    mine = CompanyIndexSelection.for_company(a).get()
    assert (mine.hidden, mine.deleted_at is not None) == (False, True)  # 지우며 숨김을 끈다
    theirs = CompanyIndexSelection.for_company(b).get()
    assert (theirs.hidden, theirs.deleted_at) == (False, None)
    assert (services.set_hidden(a, [], hidden=True), services.mark_selections_deleted(a, [])) == (0, 0)
