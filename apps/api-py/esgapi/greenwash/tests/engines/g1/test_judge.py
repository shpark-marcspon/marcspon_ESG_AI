"""판정 엔진 몫(engines/g1/judge.py — 밴드 GE1 T11·T12): 기준 줄·카테고리는 인자, 실패 갈래는 그대로(Mid 구제 0),
「근거가 받침」은 level None 으로 남는다. 포트는 모의 함수 — 공급사 0. 글은 지어낸 것."""

from collections.abc import Mapping

import pytest

from esgapi.greenwash.engines.g1 import judge as J

LINES = (
    J.CriterionLine(id="made-high-1", group="high", text="가상 절대 표현 줄"),
    J.CriterionLine(id="made-exc-1", group="exception", text="가상 외부 인증 줄"),
)


def answer(**over: object) -> J.JudgeAnswer:
    base: dict[str, object] = {
        "criteria": [{"lineId": "made-high-1", "hit": True}, {"lineId": "made-exc-1", "hit": False}],
        "level": "Mid",
        "category": None,
        "reason": " 근거가 일부만 받친다. ",
        "confirmed": ["국내 사업장 전환율", " "],
        "missing": ["해외 사업장 수치"],
        "evidence": ["P3", "P3", " P5 "],
    }
    return J.JudgeAnswer.model_validate(base | over)


def port_of(reply: J.JudgeReply) -> tuple[J.JudgePort, list[Mapping[str, str]]]:
    seen: list[Mapping[str, str]] = []

    def port(variables: Mapping[str, str]) -> J.JudgeReply:
        seen.append(variables)
        return reply

    return port, seen


def test_criterion_lines_and_categories_come_from_the_arguments() -> None:
    v = J.judge_vars(claim="가상 주장", page=4, evidence="[P3 · p.9] 가상 근거", lines=LINES, categories=["가상 갈래"])
    assert (
        v["criteria"] == "[made-high-1] (High 조건) 가상 절대 표현 줄\n[made-exc-1] (예외(위험 아님)) 가상 외부 인증 줄"
    )
    assert v["categories"] == "가상 갈래"
    assert (v["claim"], v["page"], v["evidence"]) == ("가상 주장", "4", "[P3 · p.9] 가상 근거")
    other = J.judge_vars(claim="가상 주장", page=4, evidence="", lines=LINES[:1], categories=[])
    assert "made-exc-1" not in other["criteria"]
    assert "category 는 반드시 null" in other["categories"]
    assert other["evidence"] == "(이 문서에서 근거로 쓸 단락을 찾지 못했다)"


def test_a_judged_answer_is_tidied_and_unknown_lines_are_dropped() -> None:
    a = answer(criteria=[{"lineId": "made-high-1", "hit": True}, {"lineId": "made-up", "hit": True}])
    port, seen = port_of(J.JudgeReply(answer=a))
    got = J.judge(port, {"claim": "x"}, LINES)
    assert seen == [{"claim": "x"}]
    assert isinstance(got, J.Judged)
    assert got.level == "Mid"
    assert got.reason == "근거가 일부만 받친다."
    assert got.confirmed == ("국내 사업장 전환율",)
    assert got.criteria_hit == ("made-high-1",)
    assert got.cited == ("P3", "P5")


def test_supported_by_evidence_stays_level_none() -> None:
    """T12: 근거가 받친다는 답은 위험 아님(None)으로 남는다 — 버리거나 Low 로 바꾸지 않는다."""
    port, _ = port_of(J.JudgeReply(answer=answer(level="None", missing=[])))
    got = J.judge(port, {}, LINES)
    assert isinstance(got, J.Judged)
    assert (got.level, got.missing) == ("None", ())


@pytest.mark.parametrize("code", ["judge_failed", "judge_unparsed", "judge_cut_off"])
def test_failures_stay_failures(code: J.JudgeFailure) -> None:
    """T11: 판정 실패는 그 갈래 그대로 — Mid 로 구제하지 않는다(E0 흠 8 반대)."""
    port, _ = port_of(J.JudgeReply(answer=None, failure=code))
    assert J.judge(port, {}, LINES) == J.NotJudged(code=code)


def test_a_reply_without_answer_or_code_is_a_failure() -> None:
    port, _ = port_of(J.JudgeReply(answer=None))
    assert J.judge(port, {}, LINES) == J.NotJudged(code="judge_failed")


def test_the_answer_shape_refuses_unknown_keys_and_levels() -> None:
    with pytest.raises(ValueError, match="extra"):
        answer(score=3)
    with pytest.raises(ValueError, match="level"):
        answer(level="Medium")
