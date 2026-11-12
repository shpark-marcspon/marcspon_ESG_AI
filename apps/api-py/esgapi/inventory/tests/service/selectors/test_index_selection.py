"""인벤토리 해·고객사 인덱스 선택의 읽기(밴드 K1b-2b ② — service/selectors/index_selection.py). 업무 층.

읽기마다 회사로 가른다(남의 회사 행 0). 이름·값은 지어낸 것이다.
"""

import pytest
from django.utils import timezone

from esgapi.inventory.models import CompanyIndexSelection
from esgapi.inventory.service.selectors import index_selection as selectors
from esgapi.inventory.service.services import index_selection as services
from esgapi.inventory.service.utils.index_selection import Chosen
from esgapi.inventory.tests.index_selection_support import YEAR, current_version, two_leaves

pytestmark = pytest.mark.django_db


def test_a_year_is_read_and_locked_only_within_its_company(companies: tuple[int, int]) -> None:
    a, b = companies
    made = services.create_year(b, YEAR)
    assert isinstance(made, int)
    assert selectors.year_of(b, YEAR) == made  # 분모: B 의 행은 있다
    assert selectors.year_of(a, YEAR) is None
    assert selectors.lock_year(a, YEAR) is None
    assert selectors.lock_year(b, YEAR) == made


def test_selections_of_gives_the_alive_rows_of_that_year_and_company(companies: tuple[int, int]) -> None:
    a, b = companies
    boiler, burner = two_leaves()
    years = {company: services.create_year(company, YEAR) for company in (a, b)}
    for company, year_id in years.items():
        assert isinstance(year_id, int)
        rows = [services.NewSelection(leaf.id, current_version(leaf.id)) for leaf in (boiler, burner)]
        assert services.insert_selections(company, year_id, rows) == 2
    a_year = years[a]
    assert isinstance(a_year, int)
    gone = CompanyIndexSelection.for_company(a).get(facility_node_id=burner.id)
    CompanyIndexSelection.for_company(a).filter(pk=gone.pk).update(deleted_at=timezone.now())
    found = selectors.selections_of(a, a_year)
    assert list(found) == [boiler.id]
    assert found[boiler.id] == Chosen(
        id=CompanyIndexSelection.for_company(a).get(facility_node_id=boiler.id).pk,
        factor_version_id=current_version(boiler.id),
        hidden=False,
    )
    b_year = years[b]
    assert isinstance(b_year, int)
    assert selectors.selections_of(a, b_year) == {}  # 남의 회사 해 id 로는 0
    assert len(selectors.selections_of(b, b_year)) == 2  # 분모


# ── 회사 넘는 사용 중 판정(④ — MARC-ISSUE-432 · 옛 자리 단언 test_ghg_pool.py:107-109 를 옮김) ──


def test_in_use_sees_every_companys_alive_choices_hidden_or_not(companies: tuple[int, int]) -> None:
    a, b = companies
    boiler, burner = two_leaves()
    rows = [services.NewSelection(leaf.id, current_version(leaf.id)) for leaf in (boiler, burner)]
    b_year = services.create_year(b, YEAR)
    assert isinstance(b_year, int)
    assert services.insert_selections(b, b_year, rows) == 2  # B 만 골랐다(A 는 0)
    assert selectors.selections_of(a, b_year) == {}  # 분모: A 의 회사 범위로는 안 보인다
    assert selectors.nodes_in_use([boiler.id, burner.id, 10**9]) == frozenset({boiler.id, burner.id})
    assert boiler.factor_id is not None and burner.factor_id is not None
    assert selectors.factors_in_use([boiler.factor_id, burner.factor_id]) == frozenset(
        {boiler.factor_id, burner.factor_id}
    )
    ids = {leaf.id: CompanyIndexSelection.for_company(b).get(facility_node_id=leaf.id).pk for leaf in (boiler, burner)}
    assert services.set_hidden(b, [ids[boiler.id]], hidden=True) == 1
    assert services.mark_selections_deleted(b, [ids[burner.id]]) == 1
    assert selectors.nodes_in_use([boiler.id, burner.id]) == frozenset({boiler.id})  # 숨김은 쓰는 것 · 삭제는 아님
    assert selectors.factors_in_use([boiler.factor_id, burner.factor_id]) == frozenset({boiler.factor_id})


def test_in_use_answers_only_pool_ids(companies: tuple[int, int]) -> None:
    """입구가 내는 것은 물은 풀 id 의 부분집합뿐(회사 id·선택 id 0)."""
    _, b = companies
    boiler, _ = two_leaves()
    b_year = services.create_year(b, YEAR)
    assert isinstance(b_year, int)
    assert services.insert_selections(b, b_year, [services.NewSelection(boiler.id, current_version(boiler.id))]) == 1
    asked = [boiler.id, b, b_year]
    found = selectors.nodes_in_use(asked)
    assert found == frozenset({boiler.id})
    assert b not in found and b_year not in found  # 회사 id·해 id 를 물어도 그 값이 돌아오지 않는다
