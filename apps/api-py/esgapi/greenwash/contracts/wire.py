"""엔진(engines/e0)이 내는 snake 결과 → greenwash.result@1 의 camelCase 키(밴드 GC3). 밖으로 나가는 결과는 이 경계
하나를 거친다.

engines/e0 의 사본 열·engines/e0/result.py(GW1 결과 조립)·단계 자료(StepOutput.data)는 snake 그대로다.
colab_e0.assemble 이 snake dict 를 지은 뒤 return 에서 `result_to_wire` 를 부른다. GW1 과의 대조(tests/flows/support.py,
scripts/g1a_compare.py)도 GW1 쪽을 이 함수로 사상해서 견준다 — 두 번째 사상은 짓지 않는다.

규칙: 사전 키를 pydantic `to_camel` 로 바꾸며 끝까지 내려간다(목록 안의 사전도). 값이 키인 자리는 바꾸지 않는다 —
`by_level` 아래(High·Mid·Low = level 값)와 `by_part` 아래 두 층(파트 이름, 그 아래 High·Mid·Low). 입력을 바꾸지 않고
새 값을 돌려준다. 바꾼 뒤 키가 겹치면 ValueError.
"""

from collections.abc import Mapping
from typing import Any, Final, cast

from pydantic.alias_generators import to_camel

VALUE_KEYED: Final = {"byLevel": 1, "byPart": 2}
"""값이 키인 자리(바꾼 이름 — snake `by_level`·`by_part` 도 이것으로 찾는다) → 그 아래 키를 그대로 두는 층 수."""


def _keep(value: Any, depth: int) -> Any:
    """키를 바꾸지 않고 depth 층을 내려가 복사한다."""
    if depth == 0 or not isinstance(value, Mapping):
        return _wire(value)
    return {k: _keep(v, depth - 1) for k, v in cast("Mapping[str, Any]", value).items()}


def _wire(value: Any) -> Any:
    if isinstance(value, Mapping):
        out: dict[str, Any] = {}
        for key, inner in cast("Mapping[str, Any]", value).items():
            name = to_camel(key)
            if name in out:
                raise ValueError(f"camelCase 로 바꾼 키가 겹친다: {key!r} → {name!r}")
            out[name] = _keep(inner, VALUE_KEYED[name]) if name in VALUE_KEYED else _wire(inner)
        return out
    if isinstance(value, list):
        return [_wire(v) for v in cast("list[Any]", value)]
    return value


def result_to_wire(result: Mapping[str, Any]) -> dict[str, Any]:
    """snake 결과 한 건 → camelCase 키의 새 dict(입력은 그대로)."""
    return _wire(result)
