"""문서 판 사슬의 순수 규칙(X1b-2a): 앞 판을 이어도 되는가, 한 문서가 든 사슬은 무엇인가.

순수하다(django·ninja·psycopg 를 모른다. `.importlinter` 계약 다). DB 를 모르는 걷기다: 부르는 쪽이
「이 문서의 앞 판 id」(`previous_of`)와 「이 문서를 앞 판으로 가리키는 문서 id」(`next_of`)를 내는 함수를 넘긴다
(selector 의 회사 조건 안에서).

    판 사슬   v1 ◀── v2 ◀── v3        (화살표 = previous_document_id. 한 문서의 뒤 판은 하나 — 갈래 금지)

★ 갈래 금지는 DB 의 부분 UNIQUE core_documents_previous_uniq 도 진다(FOR UPDATE 사이의 경합까지). 여기의 갈래 판정은
  그 앞에서 값으로 돌려주는 길이다.
★ 걷기는 늘 방문 집합을 든다: 데이터에 순환이 이미 들어 있어도 끝난다(상한만 믿지 않는다).
무효 조건: 두 함수가 보는 것은 부르는 순간의 행이다. 잠그지 않은 행이 걷는 동안 바뀌면 그 바뀐 행으로 판정한다
(잠금 집합이 겹치지 않는 두 PATCH 가 함께 순환을 만드는 꼴 — 서비스 머리 글).
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final

VERSION_CHAIN_MAX: Final = 100  # 어림 — 한 사슬의 판 수 상한(잇고 난 뒤 전체)

PreviousOf = Callable[[int], int | None]
NextOf = Callable[[int], int | None]


@dataclass(frozen=True, slots=True)
class ChainSelf:
    """자기 자신을 앞 판으로 가리켰다."""


@dataclass(frozen=True, slots=True)
class ChainFork:
    """그 앞 판에는 이미 다른 뒤 판이 있다(갈래)."""


@dataclass(frozen=True, slots=True)
class ChainCycle:
    """이으면 사슬이 돈다(앞 판의 앞쪽에 대상이 있다)."""


@dataclass(frozen=True, slots=True)
class ChainTooLong:
    """사슬이 VERSION_CHAIN_MAX 판을 넘는다."""

    limit: int


ChainProblem = ChainSelf | ChainFork | ChainCycle | ChainTooLong


def _walk(start: int, step: Callable[[int], int | None], *, stop_after: int) -> tuple[list[int], bool]:
    """start 에서 step 을 따라간 id 들(start 제외)과 「돌았는가」. stop_after 개를 넘으면 거기서 멈춘다."""
    seen = {start}
    found: list[int] = []
    current = step(start)
    while current is not None:
        if current in seen:
            return found, True
        seen.add(current)
        found.append(current)
        if len(found) > stop_after:
            break
        current = step(current)
    return found, False


def chain_problem(
    target_id: int, previous_id: int, *, previous_of: PreviousOf, next_of: NextOf, limit: int = VERSION_CHAIN_MAX
) -> ChainProblem | None:
    """대상(target)의 앞 판을 previous 로 이어도 되면 None, 아니면 까닭 하나.

    차례: 자기 자신 → 갈래(앞 판의 뒤 판이 대상 밖의 문서 — 같은 앞 판을 다시 보내는 멱등 호출은 대상 자신이라 지난다)
    → 순환(앞 판에서 앞쪽으로 걷다 대상을 만남) → 길이(앞 판의 앞쪽 + 앞 판 + 대상 + 대상의 뒤쪽 > limit).
    """
    if target_id == previous_id:
        return ChainSelf()
    following = next_of(previous_id)
    if following is not None and following != target_id:
        return ChainFork()
    before, looped = _walk(previous_id, previous_of, stop_after=limit)
    if looped or target_id in before:
        return ChainCycle()
    after, looped_after = _walk(target_id, next_of, stop_after=limit)
    if looped_after or previous_id in after:
        return ChainCycle()
    if len(before) + 1 + 1 + len(after) > limit:
        return ChainTooLong(limit)
    return None


def chain_of(
    document_id: int, *, previous_of: PreviousOf, next_of: NextOf, limit: int = VERSION_CHAIN_MAX
) -> tuple[int, ...] | ChainTooLong:
    """그 문서가 든 사슬의 id 전부, 새 판 먼저. 사슬이 limit 판을 넘으면(또는 데이터가 돌면) ChainTooLong."""
    after, looped_after = _walk(document_id, next_of, stop_after=limit)
    before, looped = _walk(document_id, previous_of, stop_after=limit)
    if looped or looped_after or set(after) & set(before) or len(after) + 1 + len(before) > limit:
        return ChainTooLong(limit)
    return (*reversed(after), document_id, *before)
