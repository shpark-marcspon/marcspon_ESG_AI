"""회사 id 의 꼴(양의 정수) 하나. 순수하다(`.importlinter` 계약 다의 `esgapi.*.calc`).

토큰(core/auth/tokens.py)·세션(core/tenancy/session.py)·격리 매니저(core/isolation/managers.py)·저장소 키
(core/calc/documents.py)가 이것을 import 한다(밴드 CU1 전에는 넷이 글자까지 같은 몸을 따로 적었다).
글자로 받는 회사 id 의 꼴은 따로다(core/calc/documents.py 의 COMPANY_ID_TEXT).
"""

from typing import TypeGuard


def is_company_id(value: object) -> TypeGuard[int]:
    """회사 id 의 꼴: 양의 정수. bool 은 int 의 하위 타입이라 따로 뺀다. 위 상한은 두지 않는다."""
    return isinstance(value, int) and not isinstance(value, bool) and value > 0
