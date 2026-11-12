"""데이터 검증 코랩 셀 7 의 분배기 `_run_local_tool`(읽기판 R/583-622) — 도구 이름과 인자(dict)로 로컬 도구를 부른다.

코랩 그대로다: search_items 의 limit 기본값 200(스키마의 기본 50 과 다르다 — 약점 3), 인자 틀림(TypeError)과 그 밖의
예외를 error dict 로 돌려주는 글. 코랩과 다른 자리는 둘이다: 캐시를 키워드 인자 `cache` 로 받는 것(tools.py 머리),
그리고 주입한 판별 `reraise` 가 참인 예외는 error dict 로 바꾸지 않고 다시 던지는 것(Celery soft limit — 흐름이
core 의 soft_deadline_in 으로 짓는다, MARC-ISSUE-414). 기본값 `never` 는 코랩 그대로(절대 안 던짐).

밴드 DV16(MARC-ENT-685 — 판정 허용 오차 0): 모델이 도구 인자로 준 `tolerance` 는 판정에 쓰지 않는다. 코랩은
`args.get("tolerance", tolerance)` 로 모델 값을 먼저 썼다. 이제 늘 실행 값 `tolerance`(흐름이 prompts.TOLERANCE = 0.0
을 넘김)로 견준다. 도구 스키마의 required `tolerance` 는 그대로다(프롬프트·도구 정의 불변 — 모델이 넣어도 무시된다).
"""

from collections.abc import Callable, Mapping
from typing import Any

from esgapi.dataverify.engines.colab_156.tools import (
    ValueCache,
    tool_ratio_check,
    tool_ratio_check_by_name,
    tool_search_items,
    tool_sum_check,
    tool_sum_check_by_name,
    tool_sum_n_check,
    tool_sum_n_check_by_names,
    tool_value_of_by_name,
)

__all__ = ["_run_local_tool", "never"]  # 코랩 이름 그대로 밖(흐름 DV1b·시험)에서 부른다


def never(error: BaseException) -> bool:
    """다시 던질지의 기본 판별 — 늘 거짓(코랩 그대로: 어떤 예외든 error dict)."""
    return False


def _run_local_tool(
    name: str,
    args: Any,
    *,
    data: Mapping[str, Any],
    tolerance: Any,
    cache: ValueCache,
    reraise: Callable[[BaseException], bool] = never,
) -> dict[str, Any]:
    try:
        if name == "value_of_by_name":
            return tool_value_of_by_name(
                data,
                args.get("대분류"),
                args.get("중분류"),
                args.get("소분류"),
                args.get("단위"),
                args.get("year"),
                cache=cache,
            )
        elif name == "sum_check":
            return tool_sum_check(args.get("a"), args.get("b"), args.get("c"), tolerance)
        elif name == "sum_n_check":
            return tool_sum_n_check(args.get("addends"), args.get("target"), tolerance)
        elif name == "ratio_check":
            return tool_ratio_check(args.get("d"), args.get("e"), args.get("f"), tolerance)
        elif name == "sum_check_by_name":
            # 캐시(dict key)로 쓰기 위해서 리스트(불변X->hash불가)를 튜플로
            return tool_sum_check_by_name(
                data,
                tuple(args["total"]),
                tuple(args["a"]),
                tuple(args["b"]),
                args["years"],
                tolerance,
                cache=cache,
            )
        elif name == "sum_n_check_by_names":
            addends = [tuple(t) for t in args["addends"]]
            target = tuple(args["target"])
            return tool_sum_n_check_by_names(data, addends, target, args["years"], tolerance, cache=cache)
        elif name == "ratio_check_by_name":
            return tool_ratio_check_by_name(
                data,
                tuple(args["numerator"]),
                tuple(args["denominator"]),
                tuple(args["expected"]),
                args["years"],
                tolerance,
                cache=cache,
            )
        elif name == "search_items":
            return tool_search_items(
                data,
                args.get("대분류"),
                args.get("중분류"),
                args.get("소분류_contains"),
                args.get("limit", 200),
                args.get("offset", 0),
            )
        else:
            return {"error": f"unknown tool: {name}"}
    except TypeError as te:
        if reraise(te):
            raise
        return {"error": f"bad arguments for {name}: {te}", "args": args}
    except Exception as e:
        if reraise(e):
            raise
        return {"error": f"runtime error in {name}: {e}"}
