"""회사 id 의 꼴 하나(core/calc/ids.py, 밴드 CU1). 순수 층.

밴드 CU1 전에는 토큰·세션·격리 매니저·저장소 키가 글자까지 같은 몸을 따로 적었다. 이제 넷이 이 함수를 import 한다.
표는 넷이 걷기 전에 같은 값을 냈던 표다(보고 band-reports/CU1-dedup.md).
"""

from types import ModuleType

import pytest

from esgapi.core.auth import tokens
from esgapi.core.calc import documents, ids
from esgapi.core.isolation import managers
from esgapi.core.tenancy import session

TABLE: list[tuple[object, bool]] = [
    (0, False),
    (-1, False),
    (True, False),  # bool 은 int 의 하위 타입이다
    (False, False),
    (1, True),
    (2**63, True),  # 위 상한은 두지 않는다(BigInt 칸을 넘는 값은 DB 가 거절한다)
    ("1", False),
    (1.0, False),
    (None, False),
]


@pytest.mark.parametrize(("value", "expected"), TABLE)
def test_the_shape_of_a_company_id(value: object, expected: bool) -> None:
    assert ids.is_company_id(value) is expected


@pytest.mark.parametrize("module", [tokens, session, managers, documents])
def test_the_four_users_share_the_one_function(module: ModuleType) -> None:
    assert module.is_company_id is ids.is_company_id
