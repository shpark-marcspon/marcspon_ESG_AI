"""기록을 JSONL 파일에 한 줄씩 덧붙인다. 줄의 꼴은 `CallRecord.to_json()` 이다.

★ 무효 조건: 누적 비용(`spent`)은 **이 프로세스가 이 객체로 쓴 기록의 합**이다. 파일에 이미 있던 줄이나 다른 프로세스가
  쓴 줄은 세지 않는다. 예산 상한이 이 싱크를 읽으면 상한은 프로세스마다 따로 서고, 프로세스가 다시 뜨면 0 에서 시작한다.
"""

from pathlib import Path

from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.log import CallRecord, json_line
from esgapi.core.llm.types import Scope


class JsonlFileSink:
    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._costs: list[tuple[str, str, float]] = []

    def record(self, record: CallRecord) -> None:
        with self._path.open("a", encoding="utf-8") as file:
            file.write(json_line(record.to_json()) + "\n")
        if record.cost_usd is not None:
            self._costs.append((record.tenant, record.module, record.cost_usd))

    def spent(self, scope: Scope) -> float:
        return round_usd(sum(cost for tenant, module, cost in self._costs if scope.matches(tenant, module)))
