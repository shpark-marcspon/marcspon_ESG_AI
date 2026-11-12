"""검토 항목 모델(PRD GHG.14~17). esg-lab `ts/scope3/src/domain/review.ts` 를 옮긴 것이다.

행마다 AI 제안을 사람이 반영·미반영·수정·재추천 요청한 뒤 최종 확정한다.
AI 원본 제안(`ai_proposal`, `proposal_history`)과 사람의 수정값(`human_edit`)은 다른 칸에 두고 서로 덮어쓰지 않는다.

TS 와 다르게 한 것: TS 는 허용되지 않는 전이를 함수 인자의 타입으로 막았다. 파이썬에서는 전이 함수의 인자 타입을
「그 상태로 갈 수 있는 출발 상태들의 합」으로 적어 pyright 가 볼 수 있는 만큼 막고, 타입을 모르는 입력은
`apply_action` 이 전이표 하나(`TRANSITIONS`)로 검사해 `ActionRejected` 로 돌려준다.
"""

from dataclasses import dataclass
from typing import Final, Literal

from esgapi.inventory.engines.scope3.llm_first_1.memory import MemoryEntry
from esgapi.inventory.engines.scope3.llm_first_1.types import FactorPick, SupportedCategory

ReviewState = Literal["ai_proposed", "accepted", "rejected", "edited", "rerecommend_requested", "finalized"]
REVIEW_STATES: Final[tuple[ReviewState, ...]] = (
    "ai_proposed",
    "accepted",
    "rejected",
    "edited",
    "rerecommend_requested",
    "finalized",
)


@dataclass(frozen=True, slots=True)
class AiProposal:
    """AI 가 낸 제안 원본. 만든 뒤 바꾸지 않는다."""

    category: SupportedCategory
    picks: tuple[FactorPick, ...]
    proposed_at: str


@dataclass(frozen=True, slots=True)
class HumanEdit:
    """사람이 고친 값."""

    category: SupportedCategory
    factor_id: str
    edited_by: str
    edited_at: str
    note: str | None


@dataclass(frozen=True, slots=True)
class Actor:
    by: str
    at: str


# ── 확정의 결과: 3갈래 ──


@dataclass(frozen=True, slots=True)
class FinalAcceptedAi:
    kind: Literal["accepted_ai"] = "accepted_ai"


@dataclass(frozen=True, slots=True)
class FinalEdited:
    human_edit: HumanEdit
    kind: Literal["edited"] = "edited"


@dataclass(frozen=True, slots=True)
class FinalRejected:
    """미반영으로 확정. 배출량에 넣지 않는다."""

    reason: str | None
    kind: Literal["rejected"] = "rejected"


type Final_ = FinalAcceptedAi | FinalEdited | FinalRejected

# ── 검토 항목: 상태마다 하나 ──
# 앞의 넷은 모든 상태가 같이 가진다: `ai_proposal` 은 지금 검토 대상인 AI 제안, `proposal_history` 는 재추천으로 밀려난
# 이전 AI 제안들(오래된 것부터).


@dataclass(frozen=True, slots=True)
class AiProposed:
    row_id: str
    group_key: str
    ai_proposal: AiProposal
    proposal_history: tuple[AiProposal, ...]
    state: Literal["ai_proposed"] = "ai_proposed"


@dataclass(frozen=True, slots=True)
class Accepted:
    row_id: str
    group_key: str
    ai_proposal: AiProposal
    proposal_history: tuple[AiProposal, ...]
    decided: Actor
    state: Literal["accepted"] = "accepted"


@dataclass(frozen=True, slots=True)
class Rejected:
    row_id: str
    group_key: str
    ai_proposal: AiProposal
    proposal_history: tuple[AiProposal, ...]
    decided: Actor
    reason: str | None
    state: Literal["rejected"] = "rejected"


@dataclass(frozen=True, slots=True)
class Edited:
    row_id: str
    group_key: str
    ai_proposal: AiProposal
    proposal_history: tuple[AiProposal, ...]
    human_edit: HumanEdit
    state: Literal["edited"] = "edited"


@dataclass(frozen=True, slots=True)
class RerecommendRequested:
    row_id: str
    group_key: str
    ai_proposal: AiProposal
    proposal_history: tuple[AiProposal, ...]
    requested: Actor
    note: str | None
    state: Literal["rerecommend_requested"] = "rerecommend_requested"


@dataclass(frozen=True, slots=True)
class Finalized:
    row_id: str
    group_key: str
    ai_proposal: AiProposal
    proposal_history: tuple[AiProposal, ...]
    finalized: Actor
    outcome: Final_
    state: Literal["finalized"] = "finalized"


type ReviewItem = AiProposed | Accepted | Rejected | Edited | RerecommendRequested | Finalized

# 허용되는 전이(18쌍). 아래 함수들의 인자 타입과 `apply_action` 의 검사가 이 표 하나를 따른다.
TRANSITIONS: Final[dict[ReviewState, tuple[ReviewState, ...]]] = {
    "ai_proposed": ("accepted", "rejected", "edited", "rerecommend_requested"),
    "accepted": ("rejected", "edited", "rerecommend_requested", "finalized"),
    "rejected": ("accepted", "edited", "rerecommend_requested", "finalized"),
    "edited": ("accepted", "rejected", "edited", "rerecommend_requested", "finalized"),
    "rerecommend_requested": ("ai_proposed",),
    "finalized": (),
}


def propose(row_id: str, group_key: str, proposal: AiProposal) -> AiProposed:
    return AiProposed(row_id, group_key, proposal, ())


def accept(item: AiProposed | Rejected | Edited, decided: Actor) -> Accepted:
    """반영: AI 제안의 대표 결과를 그대로 받는다."""
    return Accepted(item.row_id, item.group_key, item.ai_proposal, item.proposal_history, decided)


def reject(item: AiProposed | Accepted | Edited, decided: Actor, reason: str | None = None) -> Rejected:
    """미반영."""
    return Rejected(item.row_id, item.group_key, item.ai_proposal, item.proposal_history, decided, reason)


def edit(item: AiProposed | Accepted | Rejected | Edited, human_edit: HumanEdit) -> Edited:
    """수정: 사람의 값을 따로 적는다. AI 제안은 그대로 남는다."""
    return Edited(item.row_id, item.group_key, item.ai_proposal, item.proposal_history, human_edit)


def request_rerecommend(
    item: AiProposed | Accepted | Rejected | Edited, requested: Actor, note: str | None = None
) -> RerecommendRequested:
    return RerecommendRequested(item.row_id, item.group_key, item.ai_proposal, item.proposal_history, requested, note)


def receive_proposal(item: RerecommendRequested, proposal: AiProposal) -> AiProposed:
    """재추천 결과를 받는다. 이전 제안은 이력으로 옮긴다."""
    return AiProposed(item.row_id, item.group_key, proposal, (*item.proposal_history, item.ai_proposal))


def finalize(item: Accepted | Rejected | Edited, finalized: Actor) -> Finalized:
    """최종 확정. 반영·미반영·수정 중 하나를 거친 항목만 확정할 수 있다."""
    outcome: Final_
    match item:
        case Accepted():
            outcome = FinalAcceptedAi()
        case Edited():
            outcome = FinalEdited(item.human_edit)
        case Rejected():
            outcome = FinalRejected(item.reason)
    return Finalized(item.row_id, item.group_key, item.ai_proposal, item.proposal_history, finalized, outcome)


# ── 타입을 모르는 입력(파일, 화면)에서 온 동작 ──


@dataclass(frozen=True, slots=True)
class AcceptAction:
    by: str
    at: str
    type: Literal["accept"] = "accept"


@dataclass(frozen=True, slots=True)
class RejectAction:
    by: str
    at: str
    reason: str | None = None
    type: Literal["reject"] = "reject"


@dataclass(frozen=True, slots=True)
class EditAction:
    human_edit: HumanEdit
    type: Literal["edit"] = "edit"


@dataclass(frozen=True, slots=True)
class RequestRerecommendAction:
    by: str
    at: str
    note: str | None = None
    type: Literal["request_rerecommend"] = "request_rerecommend"


@dataclass(frozen=True, slots=True)
class ReceiveProposalAction:
    proposal: AiProposal
    type: Literal["receive_proposal"] = "receive_proposal"


@dataclass(frozen=True, slots=True)
class FinalizeAction:
    by: str
    at: str
    type: Literal["finalize"] = "finalize"


type ReviewAction = (
    AcceptAction | RejectAction | EditAction | RequestRerecommendAction | ReceiveProposalAction | FinalizeAction
)

TARGET: Final[dict[str, ReviewState]] = {
    "accept": "accepted",
    "reject": "rejected",
    "edit": "edited",
    "request_rerecommend": "rerecommend_requested",
    "receive_proposal": "ai_proposed",
    "finalize": "finalized",
}


@dataclass(frozen=True, slots=True)
class ActionApplied:
    item: ReviewItem


@dataclass(frozen=True, slots=True)
class ActionRejected:
    """허용되지 않는 전이. 예외가 아니다."""

    error: str


def apply_action(item: ReviewItem, action: ReviewAction) -> ActionApplied | ActionRejected:
    target = TARGET[action.type]
    refused = ActionRejected(f"{item.state} 에서 {target} 로 갈 수 없다")
    if target not in TRANSITIONS[item.state]:
        return refused
    # 위에서 전이를 확인했다. 아래의 isinstance 는 pyright 에게 같은 것을 보여 주는 것이고 표와 어긋나지 않는다
    # (어긋나면 test_scope3_review 의 6×6 전수 검사가 빨개진다).
    match action:
        case AcceptAction():
            if isinstance(item, (AiProposed, Rejected, Edited)):
                return ActionApplied(accept(item, Actor(action.by, action.at)))
        case RejectAction():
            if isinstance(item, (AiProposed, Accepted, Edited)):
                return ActionApplied(reject(item, Actor(action.by, action.at), action.reason))
        case EditAction():
            if isinstance(item, (AiProposed, Accepted, Rejected, Edited)):
                return ActionApplied(edit(item, action.human_edit))
        case RequestRerecommendAction():
            if isinstance(item, (AiProposed, Accepted, Rejected, Edited)):
                return ActionApplied(request_rerecommend(item, Actor(action.by, action.at), action.note))
        case ReceiveProposalAction():
            if isinstance(item, RerecommendRequested):
                return ActionApplied(receive_proposal(item, action.proposal))
        case FinalizeAction():
            if isinstance(item, (Accepted, Rejected, Edited)):
                return ActionApplied(finalize(item, Actor(action.by, action.at)))
    return refused


@dataclass(frozen=True, slots=True)
class ConfirmedMapping:
    category: SupportedCategory
    factor_id: str
    origin: Literal["ai", "human"]


def confirmed_mapping(item: Finalized) -> ConfirmedMapping | None:
    """확정된 항목이 배출량에 쓰는 매핑. 미반영으로 확정했으면 None. 확정 전 항목은 받지 않는다."""
    match item.outcome:
        case FinalRejected():
            return None
        case FinalEdited(human_edit=human_edit):
            return ConfirmedMapping(human_edit.category, human_edit.factor_id, "human")
        case FinalAcceptedAi():
            if not item.ai_proposal.picks:
                return None
            return ConfirmedMapping(item.ai_proposal.category, item.ai_proposal.picks[0].factor_id, "ai")


def to_memory_entry(item: Finalized, label: str | None = None) -> MemoryEntry | None:
    """확정된 항목을 확정 매핑 기억에 넣을 항목으로 바꾼다. 미반영 확정은 기억하지 않는다(None)."""
    mapping = confirmed_mapping(item)
    if mapping is None:
        return None
    return MemoryEntry(
        key=item.group_key,
        category=mapping.category,
        factor_id=mapping.factor_id,
        confirmed_by=item.finalized.by,
        confirmed_at=item.finalized.at,
        label=label,
    )
