"""정수 칸에 들어온 불리언(NotBool)과 정수가 아닌 수(IntOnly)를 거른다. pydantic 만 import 한다(순수 층).

파이썬에서는 `True == 1` 이고 `bool` 이 `int` 의 아래 타입이다. 그래서
  - `Literal[1, 2, 3, 4]` 는 엄격 모드(strict=True)에서도 `true` 를 1 로 받는다(값이 같은지만 본다).
  - `int` 칸은 엄격 모드에서는 `true` 를 거절하지만, 느슨한 모드에서는 1 로 바꿔 받는다.
정수 Literal 칸에는 `Annotated[Literal[...], NotBool]` 을 붙인다. 붙였는지는 기계가 잰다:
요청 스키마 전부를 훑는 `esgapi/config/tests/test_request_schemas_reject_bool.py`.

`IntOnly`(밴드 E2, MARC-ISSUE-92): 정수 Literal 은 엄격 모드에서도 `1.0` 을 1 로 받는다(값이 같은지만 본다).
요청 스키마의 정수 Literal 별칭에는 `Annotated[Literal[...], NotBool, IntOnly]` 로 붙인다.
글자(`"1"`)는 그대로 넘긴다 — 정수 Literal 이 거절한다.
LLM 출력 꼴(inventory/engines/scope3/llm_first_1/llm_steps.py 의 CategoryOut)에는 붙이지 않았다(1.0 을 받는다).

다른 뜻의 `isinstance(…, bool)`(손 검사·JS 표기: reconcile/calc/shape.py, inventory/tools/jsrepr.py,
reference/calc/types.py·assemble.py, core/llm/client.py)은 이것과 무관하다.
"""

from decimal import Decimal

from pydantic import BeforeValidator


def reject_bool(value: object) -> object:
    """불리언이면 거절하고, 아니면 그대로 넘긴다(뒤의 검사가 이어서 본다)."""
    if isinstance(value, bool):
        raise ValueError("불리언은 받지 않는다(true 는 1 이 아니다)")
    return value


NotBool = BeforeValidator(reject_bool)


def reject_non_int_number(value: object) -> object:
    """int 가 아닌 수(float·Decimal 등)를 거절하고, 아니면 그대로 넘긴다. 불리언은 NotBool 이 먼저 본다."""
    if isinstance(value, float | complex | Decimal):
        raise ValueError("정수가 아닌 수는 받지 않는다(1.0 은 1 이 아니다)")
    return value


IntOnly = BeforeValidator(reject_non_int_number)
