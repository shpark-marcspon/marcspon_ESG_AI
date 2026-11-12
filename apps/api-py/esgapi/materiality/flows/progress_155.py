"""materiality 흐름의 단계 안 자리 진행(밴드 IRW6, MARC-ISSUE-378) — 토픽(1부 regulation·controversy)이나
토픽×서브토픽 자리(2부 impact·financial·pathway)마다 checkpoint 를 내고, 같은 실행의 다시 넣은 시도가 resume 으로 받은
부분 산출물에서 이어 돈다.

부분 산출물은 그 단계 data 와 같은 꼴의 앞부분이다: {answers: 끝난 자리의 답(자리 차례), calls: 그 호출 기록,
spentUsd: 마지막 자리 뒤 실행 누계}. 끝난 단계의 data 는 마지막 부분 산출물과 같다.

resume 없이 checkpoint 만 내면 안 된다: 실행기는 checkpoint 뒤마다 협조 마감으로 양보하고 다시 넣은 시도에 그 단계의
부분 산출물을 resume 으로 주며, 시도 상한은 진행 없는 시도만 센다(runs/tasks.py·runs/calc/claims.py). resume 을 버리면
긴 단계가 시도마다 처음부터 몇 자리 하고 양보 — 「진행」이라 상한에 걸리지 않고 같은 호출을 되풀이한다(돈).

이 파일은 core.flows.types 만 읽는다(설정·SDK·시계 0).
"""

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.core.flows.types import StepContext

KEY_FIELDS: Final = ("topic", "subtopic")
"""자리 열쇠의 칸 이름(차례대로) — 1부 열쇠는 (topic,), 2부는 (topic, subtopic)."""
STATE_KEYS: Final = frozenset({"answers", "calls", "spentUsd"})


@dataclass(slots=True, kw_only=True)
class Progress:
    """한 단계의 자리 진행. answers·calls 는 끝난 자리까지, spent 는 마지막 자리 뒤 실행 누계."""

    ctx: StepContext
    keys: tuple[tuple[str, ...], ...]
    answers: list[dict[str, Any]]
    calls: list[dict[str, Any]]
    spent: float

    def add(self, answer: dict[str, Any], call: dict[str, Any] | None, spent: float) -> None:
        """자리 하나를 끝낸다(call None = 부르지 않은 자리 — pathway 건너뜀)."""
        self.answers.append(answer)
        if call is not None:
            self.calls.append(call)
        self.spent = spent
        self.ctx.checkpoint(self.data(), done=len(self.answers), total=len(self.keys))

    def data(self) -> dict[str, Any]:
        return {"answers": self.answers, "calls": self.calls, "spentUsd": self.spent}


def start(ctx: StepContext, keys: Sequence[tuple[str, ...]], spent: float) -> Progress:
    """resume 이 없으면 빈 상태(자리가 있으면 시작 checkpoint done 0), 있으면 검사한 그 상태(시작 checkpoint 0)."""
    fixed = tuple(keys)
    if ctx.resume is None:
        progress = Progress(ctx=ctx, keys=fixed, answers=[], calls=[], spent=spent)
        if fixed:
            ctx.checkpoint(progress.data(), done=0, total=len(fixed))
        return progress
    return _resumed(ctx, ctx.resume, fixed, spent)


def _key(answer: object, width: int) -> tuple[object, ...] | None:
    if not isinstance(answer, Mapping):
        return None
    fields = cast("Mapping[str, object]", answer)
    return tuple(fields.get(name) for name in KEY_FIELDS[:width])


def _resumed(
    ctx: StepContext, resume: Mapping[str, object], keys: tuple[tuple[str, ...], ...], spent: float
) -> Progress:
    if frozenset(resume) != STATE_KEYS:
        raise ValueError("resume 이 이 단계의 부분 산출물 꼴이 아니다(열쇠)")
    answers, calls, resumed_spent = resume["answers"], resume["calls"], resume["spentUsd"]
    if not isinstance(answers, list) or len(cast("list[object]", answers)) > len(keys):
        raise ValueError("resume 의 answers 가 목록이 아니거나 자리 수보다 길다")
    done = cast("list[Mapping[str, Any]]", answers)
    for at, answer in enumerate(done):
        if _key(answer, len(keys[at])) != keys[at]:
            raise ValueError(f"resume 의 {at} 번째 답의 자리가 이번 자리 차례와 다르다")
    if not isinstance(calls, list):
        raise ValueError("resume 의 calls 가 목록이 아니다")
    if (
        isinstance(resumed_spent, bool)
        or not isinstance(resumed_spent, int | float)
        or not math.isfinite(resumed_spent)
        or resumed_spent < spent
    ):
        raise ValueError("resume 의 spentUsd 가 유한한 수가 아니거나 앞 단계까지의 누계보다 작다")
    return Progress(
        ctx=ctx,
        keys=keys,
        answers=[dict(answer) for answer in done],
        calls=list(cast("list[dict[str, Any]]", calls)),
        spent=float(resumed_spent),
    )
