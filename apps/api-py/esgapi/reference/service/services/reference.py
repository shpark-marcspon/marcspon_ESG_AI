"""조립을 부르는 얇은 층: DB 에서 낱줄과 대응표를 읽어 순수 함수(`calc`)에 넘긴다. 쓰지 않는다.

조립이 「못 했다」고 답하는 것(낱줄 없음, 입력 누락 …)은 오류가 아니라 결과다: `Assembly.result` 의 실패 갈래로 나간다.
여기서 따로 갈리는 것은 「조립을 부를 수조차 없다」 둘이다: 대응표가 없다 / 대응표가 여럿이다.
"""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from esgapi.reference.calc import (
    GIR_EDITIONS,
    SOURCE_IDS,
    TABLE69,
    AssemblyMapping,
    AssemblyResult,
    FactorRecord,
    Failed,
    assemble_combustion_factor,
    assemble_purchased_electricity_factor,
)
from esgapi.reference.service.selectors import reference as selectors
from esgapi.reference.service.selectors.reference import MappingAbsent, MappingAmbiguous, MappingFound, SourceView

# 고정연소 조립이 읽는 출처: 지침의 별표 넷(6·10·11·12).
COMBUSTION_SOURCES: tuple[str, ...] = tuple(sorted(SOURCE_IDS.values()))
# 구매 전력 조립이 읽는 출처: 별표 6(표-69)과 GIR 공표 판들.
ELECTRICITY_SOURCES: tuple[str, ...] = (TABLE69["sourceId"], *sorted(GIR_EDITIONS.values()))


@dataclass(frozen=True)
class Assembly:
    """조립의 결과(성공이든 실패 갈래든)와, 성공했을 때 쓰인 낱줄들의 출처(이용 조건을 같이 내보내려고)."""

    result: AssemblyResult
    sources: list[SourceView]


type AssemblyOutcome = Assembly | MappingAbsent | MappingAmbiguous
type _Assembler = Callable[[object, Sequence[FactorRecord], AssemblyMapping], AssemblyResult]


def _assemble(request: object, source_ids: tuple[str, ...], assembler: _Assembler) -> AssemblyOutcome:
    found = selectors.current_mapping()
    if not isinstance(found, MappingFound):
        return found
    result = assembler(request, selectors.records_for_assembly(source_ids), found.mapping)
    if isinstance(result, Failed):
        return Assembly(result, [])
    used = {parameter["sourceId"] for parameter in result.value.evidence["parameters"]}
    return Assembly(result, selectors.sources_by_id(used))


def assemble_combustion(request: object) -> AssemblyOutcome:
    """고정연소 계수 한 건. request 는 JSON 을 푼 dict(꼴은 calc/assemble.py 의 머리말)."""
    return _assemble(request, COMBUSTION_SOURCES, assemble_combustion_factor)


def assemble_electricity(request: object) -> AssemblyOutcome:
    """구매 전력 계수 한 건. request 는 JSON 을 푼 dict(꼴은 calc/electricity.py 의 머리말)."""
    return _assemble(request, ELECTRICITY_SOURCES, assemble_purchased_electricity_factor)
