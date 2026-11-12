"""기록을 프로세스 메모리에 쌓는다. 테스트와, 기록을 남길 곳을 정하지 않은 실행의 기본값이다.

★ 무효 조건: 누적 비용(`spent`)은 이 객체가 본 기록의 합이다. 프로세스가 끝나면 사라지고 일꾼 프로세스끼리 나누지
않는다.
  예산 상한이 이 싱크를 읽으면 상한은 프로세스마다 따로 선다.
"""

from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.log import CallRecord
from esgapi.core.llm.types import Scope


class MemorySink:
    def __init__(self) -> None:
        self.records: list[CallRecord] = []

    def record(self, record: CallRecord) -> None:
        self.records.append(record)

    def spent(self, scope: Scope) -> float:
        return round_usd(
            sum(
                record.cost_usd
                for record in self.records
                if record.cost_usd is not None and scope.matches(record.tenant, record.module)
            )
        )
