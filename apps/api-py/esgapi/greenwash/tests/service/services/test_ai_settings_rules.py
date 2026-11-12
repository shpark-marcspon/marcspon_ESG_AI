"""AI 설정 판의 순수 규칙 둘(밴드 G2c2 §3-1-7): 응답의 상태 셈과 이름 매김. 순수 층(DB 0)."""

from datetime import UTC, datetime

import pytest

from esgapi.greenwash.models import AI_SETTING_NAME_PATTERN
from esgapi.greenwash.service.selectors.ai_settings import status_of
from esgapi.greenwash.service.services.ai_settings import next_name

AT = datetime(2026, 10, 20, tzinfo=UTC)


@pytest.mark.parametrize(
    ("applied", "applied_at", "status"),
    [(True, AT, "applied"), (False, AT, "past"), (False, None, "testing")],
)
def test_the_status_is_counted_from_the_two_cells(applied: bool, applied_at: datetime | None, status: str) -> None:
    assert status_of(applied, applied_at) == status


@pytest.mark.parametrize(
    ("names", "name"),
    [
        pytest.param((), "v1", id="first"),
        pytest.param(("v1",), "v2", id="second"),
        pytest.param(("v2", "v10", "v9"), "v11", id="largest-not-latest"),
        pytest.param(("v1", "v3"), "v4", id="gap-is-not-filled"),
        pytest.param(("x7", "v01", "V5"), "v1", id="other-names-ignored"),
    ],
)
def test_the_next_name_is_the_largest_plus_one(names: tuple[str, ...], name: str) -> None:
    assert next_name(names) == name


def test_a_next_name_fits_the_table_check() -> None:
    import re

    assert re.fullmatch(AI_SETTING_NAME_PATTERN, next_name(("v99",)))
    assert not re.fullmatch(AI_SETTING_NAME_PATTERN, "v0")
