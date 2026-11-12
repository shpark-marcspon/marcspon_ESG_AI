"""확정 매핑 기억(메모리 구현). 순수 층.

esg-lab `memory.test.ts` 넷 가운데 「없는 키」 하나를 옮겼다(나머지 셋은 파일 구현의 것이라 옮기지 않았다).
"""

from esgapi.inventory.engines.scope3.llm_first_1.memory import InMemoryMappingMemory, MappingMemory, MemoryEntry

ENTRY = MemoryEntry("a4용지80g|kg|", 1, "syn:steel-kg", "synthetic-reviewer", "2026-09-30T09:00:00+09:00")


def test_missing_key_is_none_and_confirm_overwrites() -> None:
    memory: MappingMemory = InMemoryMappingMemory([ENTRY])
    assert memory.lookup("없는 키") is None
    assert memory.lookup(ENTRY.key) == ENTRY
    assert memory.size == 1
    changed = MemoryEntry(ENTRY.key, 2, "syn:spend-computer", "other", "2026-10-01T09:00:00+09:00", label="A4")
    memory.confirm(changed)
    assert memory.lookup(ENTRY.key) == changed
    assert memory.size == 1
    assert InMemoryMappingMemory().size == 0
