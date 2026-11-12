"""계획과 실제 요청의 대조(MARC-ISSUE-196 N6): 실제 요청마다 같은 (자리, system, max_tokens) 의 계획 줄 하나를 쓴다
(계획 줄은 count 번까지). 실제 입력 어림(core 의 어림 — system·user 를 줄바꿈으로 이은 글)이 그 계획 줄의 입력 어림을
넘으면 안 된다. 집합 대조와 달리 계획 한 줄의 system 이 틀리거나 계획이 입력을 작게 세면 가려지지 않는다.

계획의 user 는 앞 호출의 출력 자리를 자리 글(`stand_in`)로 채우므로 실제 user 와 글이 같지 않다 — 그래서 user 는
글이 아니라 어림 토큰으로 견준다(맞춤은 작은 실제부터 그것을 덮는 가장 작은 계획 줄로 — 한 줄 문제의 최적 맞춤).
"""

from bisect import bisect_left
from collections import defaultdict
from collections.abc import Sequence

from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.cost import HeuristicTokenEstimator
from esgapi.translation.engines.colab_158.plan import CallPlan
from esgapi.translation.tests.engines.colab_158.support import Call

ESTIMATOR = HeuristicTokenEstimator(load_config(default_config_sources(synthetic=False)).token_estimate)


def input_tokens(system: str, user: str) -> int:
    return ESTIMATOR.estimate("\n".join([system, user]))


def misfits(calls: Sequence[Call], plan: CallPlan) -> list[str]:
    """계획에 들지 않는 실제 요청(빈 목록이면 다 든다)."""
    planned: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for p in plan.calls:
        planned[(p.site, p.system, p.max_tokens)] += [input_tokens(p.system, p.user)] * p.count
    for units in planned.values():
        units.sort()
    actual: dict[tuple[str, str, int], list[int]] = defaultdict(list)
    for c in calls:
        actual[(c.site, c.system, c.max_tokens)].append(input_tokens(c.system, c.user))
    out: list[str] = []
    for key, tokens in actual.items():
        units = planned.get(key, [])
        for t in sorted(tokens):
            i = bisect_left(units, t)
            if i == len(units):
                biggest = units[-1] if units else "없음"
                out.append(f"{key[0]} max_tokens={key[2]} 입력 {t} 토큰 — 덮는 계획 줄 없음(남은 가장 큰 줄 {biggest})")
                continue
            del units[i]
    return out
