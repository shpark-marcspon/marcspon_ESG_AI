"""판 사슬의 순수 규칙(core/calc/versions.py — X1b-2a). 순수 층: 사슬은 dict 두 개(앞 판·뒤 판)로 흉내 낸다."""

import pytest

from esgapi.core.calc.versions import (
    VERSION_CHAIN_MAX,
    ChainCycle,
    ChainFork,
    ChainSelf,
    ChainTooLong,
    chain_of,
    chain_problem,
)


def links(*pairs: tuple[int, int]) -> tuple[dict[int, int], dict[int, int]]:
    """(뒤 판, 앞 판) 짝들 → (앞 판 표, 뒤 판 표)."""
    previous = dict(pairs)
    following = {before: after for after, before in pairs}
    return previous, following


def problem(target: int, previous_id: int, *pairs: tuple[int, int], limit: int = VERSION_CHAIN_MAX) -> object:
    previous, following = links(*pairs)
    return chain_problem(target, previous_id, previous_of=previous.get, next_of=following.get, limit=limit)


def test_the_limit_is_the_written_guess() -> None:
    assert VERSION_CHAIN_MAX == 100


def test_linking_two_lone_documents_is_fine() -> None:
    assert problem(2, 1) is None
    assert problem(3, 2, (2, 1)) is None  # 1 ◀ 2 의 끝에 3 을 잇는다


def test_a_document_cannot_be_its_own_previous() -> None:
    assert problem(5, 5) == ChainSelf()


def test_a_previous_that_already_has_a_later_version_is_a_fork() -> None:
    assert problem(3, 1, (2, 1)) == ChainFork()  # 1 ◀ 2 가 있는데 3 도 1 을 가리키려 함
    # 같은 앞 판을 다시 보내면(멱등) 대상 자신이라 지난다
    assert problem(2, 1, (2, 1)) is None


@pytest.mark.parametrize(
    ("target", "previous_id", "pairs"),
    [
        (1, 2, [(2, 1)]),  # 1 ◀ 2 에서 1 의 앞 판을 2 로 → 돈다
        (1, 3, [(2, 1), (3, 2)]),  # 1 ◀ 2 ◀ 3 에서 1 의 앞 판을 3 으로
    ],
)
def test_linking_back_into_your_own_later_versions_is_a_cycle(
    target: int, previous_id: int, pairs: list[tuple[int, int]]
) -> None:
    assert problem(target, previous_id, *pairs) == ChainCycle()


def test_a_cycle_already_in_the_data_still_ends() -> None:
    # 7 ◀ 8 ◀ 9 ◀ 7 (데이터가 이미 돈다). 걷기가 방문 집합으로 끝나고 순환으로 답한다
    previous = {8: 7, 9: 8, 7: 9}
    nothing: dict[int, int] = {}
    assert chain_problem(1, 9, previous_of=previous.get, next_of=nothing.get) == ChainCycle()
    following = {7: 8, 8: 9, 9: 7}
    assert chain_problem(7, 1, previous_of=nothing.get, next_of=following.get) == ChainCycle()
    assert chain_of(7, previous_of=previous.get, next_of=following.get) == ChainTooLong(VERSION_CHAIN_MAX)


def test_the_length_counts_the_whole_chain_after_linking() -> None:
    # 1 ◀ 2 (앞쪽 둘) 과 3 ◀ 4 (대상 3 과 뒤쪽 하나) 를 이으면 넷
    pairs = ((2, 1), (4, 3))
    assert problem(3, 2, *pairs, limit=4) is None
    assert problem(3, 2, *pairs, limit=3) == ChainTooLong(3)  # 앞쪽만 재면(셋) 지나 버린다


def test_chain_of_lists_the_whole_chain_newest_first() -> None:
    previous, following = links((2, 1), (3, 2))
    for member in (1, 2, 3):
        assert chain_of(member, previous_of=previous.get, next_of=following.get) == (3, 2, 1)
    assert chain_of(9, previous_of=previous.get, next_of=following.get) == (9,)  # 사슬 없는 문서는 자기 하나


def test_chain_of_refuses_a_chain_over_the_limit() -> None:
    previous, following = links(*((i + 1, i) for i in range(1, 5)))  # 1 ◀ 2 ◀ 3 ◀ 4 ◀ 5
    assert chain_of(3, previous_of=previous.get, next_of=following.get, limit=5) == (5, 4, 3, 2, 1)
    assert chain_of(3, previous_of=previous.get, next_of=following.get, limit=4) == ChainTooLong(4)
