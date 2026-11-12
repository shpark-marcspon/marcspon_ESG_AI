"""비용 상한. 누적이 상한에 닿았으면 다음 호출을 공급사에 보내기 전에 막는다.

누적 비용은 스스로 세지 않고 호출 기록의 싱크에서 읽는다(`CallLogSink.spent`): 기록에 남은 것과 상한이 본 것이 늘 같다.
★ 무효 조건: 메모리·JSONL 싱크의 누적은 프로세스 하나의 것이다. 일꾼 프로세스가 여럿이면 상한은 일꾼마다 따로 선다
  (합친 지출은 상한 × 일꾼 수까지 갈 수 있다). 프로세스를 넘는 상한은 DB 합계를 읽는 싱크가 생긴 뒤의 일이다.
"""

from collections.abc import Sequence
from dataclasses import dataclass

from esgapi.core.llm.log import CallLogSink
from esgapi.core.llm.types import Scope, Tags


@dataclass(frozen=True)
class BudgetLimit:
    """상한 하나. `scope` 에 적은 꼬리표가 모두 맞는 호출의 누적 비용에 적용된다."""

    scope: Scope
    limit_usd: float


@dataclass(frozen=True)
class BudgetExhausted:
    """걸린 상한과 그때의 누적 비용."""

    limit: BudgetLimit
    spent_usd: float


class BudgetGuard:
    def __init__(self, limits: Sequence[BudgetLimit], ledger: CallLogSink) -> None:
        self._limits = tuple(limits)
        self._ledger = ledger

    def spent(self, scope: Scope) -> float:
        return self._ledger.spent(scope)

    def check(self, tags: Tags) -> BudgetExhausted | None:
        """이 꼬리표의 호출을 보내도 되면 None, 상한에 닿았으면 걸린 상한."""
        for limit in self._limits:
            if not limit.scope.matches(tags.tenant, tags.module):
                continue
            spent_usd = self.spent(limit.scope)
            if spent_usd >= limit.limit_usd:
                return BudgetExhausted(limit=limit, spent_usd=spent_usd)
        return None
