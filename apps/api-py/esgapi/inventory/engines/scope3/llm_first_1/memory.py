"""확정 매핑 기억. esg-lab `ts/scope3/src/domain/memory.ts` 를 옮긴 것이다.

파일 구현은 옮기지 않았다(저장은 뒤 밴드).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from esgapi.inventory.engines.scope3.llm_first_1.types import SupportedCategory


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    """사람이 확정한 매핑 한 건: 묶음 키 → 범주와 계수 id.

    `label` 은 사람이 알아볼 원래 품목명이다. 조회에는 쓰지 않는다. 없으면 JSON 에 그 키를 내지 않는다.
    """

    key: str
    category: SupportedCategory
    factor_id: str
    confirmed_by: str
    confirmed_at: str
    label: str | None = None


class MappingMemory(Protocol):
    """확정 매핑 기억. 저장 방식(파일, DB)은 이 뒤에 둔다."""

    def lookup(self, key: str) -> MemoryEntry | None:
        """없으면 None. 저장소를 읽지 못한 것은 예외다."""
        ...

    def confirm(self, entry: MemoryEntry) -> None:
        """같은 키가 있으면 덮어쓴다."""
        ...

    @property
    def size(self) -> int: ...


class InMemoryMappingMemory:
    def __init__(self, entries: Sequence[MemoryEntry] = ()) -> None:
        self._entries: dict[str, MemoryEntry] = {entry.key: entry for entry in entries}

    def lookup(self, key: str) -> MemoryEntry | None:
        return self._entries.get(key)

    def confirm(self, entry: MemoryEntry) -> None:
        self._entries[entry.key] = entry

    @property
    def size(self) -> int:
        return len(self._entries)
