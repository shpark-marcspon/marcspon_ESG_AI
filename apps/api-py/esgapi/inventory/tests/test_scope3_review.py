"""검토 항목의 상태 전이. esg-lab `ts/scope3/test/review.test.ts` 의 여섯을 옮겼다. 순수 층.

「허용되지 않는 전이는 타입에서 막힌다」(TS 의 @ts-expect-error)는 뜻이 바뀌었다: 여기서는 6×6 = 36쌍을 전부 돌려
전이표(허용 18쌍)와 `apply_action` 의 결과가 하나도 어긋나지 않는 것을 잰다.
"""

from typing import get_args

from esgapi.inventory.engines.scope3.llm_first_1.review import (
    REVIEW_STATES,
    TARGET,
    TRANSITIONS,
    AcceptAction,
    ActionApplied,
    ActionRejected,
    Actor,
    AiProposal,
    AiProposed,
    ConfirmedMapping,
    EditAction,
    FinalAcceptedAi,
    FinalEdited,
    FinalizeAction,
    FinalRejected,
    HumanEdit,
    ReceiveProposalAction,
    RejectAction,
    RequestRerecommendAction,
    ReviewAction,
    ReviewItem,
    ReviewState,
    accept,
    apply_action,
    confirmed_mapping,
    edit,
    finalize,
    propose,
    receive_proposal,
    reject,
    request_rerecommend,
    to_memory_entry,
)
from esgapi.inventory.engines.scope3.llm_first_1.types import FactorPick

PROPOSAL = AiProposal(
    category=1,
    picks=(
        FactorPick("syn:steel-kg", "테스트 (synthetic)", "high"),
        FactorPick("syn:steel-t", "테스트 (synthetic)", "low"),
    ),
    proposed_at="2026-10-01T10:00:00+09:00",
)
WHO = Actor("reviewer-synthetic", "2026-10-01T11:00:00+09:00")
EDIT = HumanEdit(2, "syn:spend-computer", "reviewer-synthetic", "2026-10-01T11:30:00+09:00", "자본재로 본다")
SECOND = AiProposal(1, (FactorPick("syn:pp-kg", "다시 (synthetic)", "medium"),), "2026-10-01T12:00:00+09:00")


def start() -> AiProposed:
    return propose("r1", "합성강판|kg|", PROPOSAL)


def test_proposed_then_accepted_then_finalized() -> None:
    done = finalize(accept(start(), WHO), WHO)
    assert done.state == "finalized"
    assert done.outcome == FinalAcceptedAi()
    assert confirmed_mapping(done) == ConfirmedMapping(1, "syn:steel-kg", "ai")
    entry = to_memory_entry(done, "합성 강판")
    assert entry is not None
    assert (entry.key, entry.category, entry.factor_id, entry.label) == ("합성강판|kg|", 1, "syn:steel-kg", "합성 강판")
    assert (entry.confirmed_by, entry.confirmed_at) == (WHO.by, WHO.at)
    unlabeled = to_memory_entry(done)
    assert unlabeled is not None
    assert unlabeled.label is None


def test_edit_keeps_both_the_human_value_and_the_ai_proposal() -> None:
    edited = edit(start(), EDIT)
    assert edited.human_edit == EDIT
    assert edited.ai_proposal == PROPOSAL
    done = finalize(edited, WHO)
    assert done.outcome == FinalEdited(EDIT)
    assert done.ai_proposal == PROPOSAL
    assert confirmed_mapping(done) == ConfirmedMapping(2, "syn:spend-computer", "human")


def test_finalized_rejection_has_no_mapping_and_is_not_remembered() -> None:
    done = finalize(reject(start(), WHO, "맞는 계수가 없다"), WHO)
    assert done.outcome == FinalRejected("맞는 계수가 없다")
    assert confirmed_mapping(done) is None
    assert to_memory_entry(done) is None
    assert finalize(reject(start(), WHO), WHO).outcome == FinalRejected(None)


def test_rerecommendation_moves_the_old_proposal_to_history() -> None:
    requested = request_rerecommend(start(), WHO, "다른 후보를 보고 싶다")
    assert (requested.requested, requested.note) == (WHO, "다른 후보를 보고 싶다")
    again = receive_proposal(requested, SECOND)
    assert again.state == "ai_proposed"
    assert again.ai_proposal == SECOND
    assert again.proposal_history == (PROPOSAL,)
    third = receive_proposal(request_rerecommend(again, WHO), PROPOSAL)
    assert third.proposal_history == (PROPOSAL, SECOND)


def test_an_accepted_proposal_without_picks_confirms_nothing() -> None:
    empty = propose("r1", "k", AiProposal(1, (), "2026-10-01T10:00:00+09:00"))
    assert confirmed_mapping(finalize(accept(empty, WHO), WHO)) is None


def items() -> dict[ReviewState, ReviewItem]:
    """상태마다 항목 하나."""
    proposed = start()
    return {
        "ai_proposed": proposed,
        "accepted": accept(proposed, WHO),
        "rejected": reject(proposed, WHO),
        "edited": edit(proposed, EDIT),
        "rerecommend_requested": request_rerecommend(proposed, WHO),
        "finalized": finalize(accept(proposed, WHO), WHO),
    }


ACTIONS: dict[ReviewState, ReviewAction] = {
    "accepted": AcceptAction(WHO.by, WHO.at),
    "rejected": RejectAction(WHO.by, WHO.at),
    "edited": EditAction(EDIT),
    "rerecommend_requested": RequestRerecommendAction(WHO.by, WHO.at),
    "ai_proposed": ReceiveProposalAction(SECOND),
    "finalized": FinalizeAction(WHO.by, WHO.at),
}


def test_the_table_has_six_states_and_eighteen_allowed_pairs() -> None:
    assert set(get_args(ReviewState)) == set(REVIEW_STATES) == set(TRANSITIONS)
    assert [len(TRANSITIONS[state]) for state in REVIEW_STATES] == [4, 4, 4, 5, 1, 0]
    assert sum(len(targets) for targets in TRANSITIONS.values()) == 18
    assert {TARGET[action.type] for action in ACTIONS.values()} == set(REVIEW_STATES)


def test_all_36_pairs_follow_the_one_table() -> None:
    allowed = 0
    for source, item in items().items():
        for target, action in ACTIONS.items():
            result = apply_action(item, action)
            if target in TRANSITIONS[source]:
                allowed += 1
                assert isinstance(result, ActionApplied), (source, target)
                assert result.item.state == target
                # 어느 전이도 AI 원본 제안을 잃지 않는다(재추천을 받았을 때만 이력으로 간다).
                kept = (result.item.ai_proposal, *result.item.proposal_history)
                assert PROPOSAL in kept
            else:
                assert result == ActionRejected(f"{source} 에서 {target} 로 갈 수 없다"), (source, target)
    assert allowed == 18


def test_runtime_actions_carry_their_fields() -> None:
    rejected = apply_action(start(), RejectAction(WHO.by, WHO.at, "사유"))
    assert isinstance(rejected, ActionApplied)
    assert rejected.item == reject(start(), WHO, "사유")
    requested = apply_action(start(), RequestRerecommendAction(WHO.by, WHO.at, "메모"))
    assert isinstance(requested, ActionApplied)
    assert requested.item == request_rerecommend(start(), WHO, "메모")
    finalized = apply_action(edit(start(), EDIT), FinalizeAction(WHO.by, WHO.at))
    assert isinstance(finalized, ActionApplied)
    assert finalized.item == finalize(edit(start(), EDIT), WHO)
