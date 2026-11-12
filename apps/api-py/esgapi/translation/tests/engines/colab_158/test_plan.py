"""호출 계획(engines/colab_158/plan.py — 발주서 §3 S5 앞, 처분 ⑬): 지어낸 3쪽 문서의 계획 호출 수가 손셈과 같고,
실제 흐름(support.run_flow)이 부른 호출이 계획 안에 든다(자리마다 횟수 ≤ 계획,
(자리, system, max_tokens) 가 계획에 있음).
"""

from collections import Counter
from collections.abc import Sequence

import pytest

from esgapi.core.llm.types import ProviderResponse
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.engines.colab_158.plan import CallPlan, plan, stand_in
from esgapi.translation.tests.engines.colab_158.support import make_input, ok, run_flow

TABLE_ROWS = [
    "| " + " | ".join(f"머리{c}" for c in range(5)) + " |",
    "| --- | --- | --- | --- | --- |",
    *("| " + " | ".join(f"칸{r}{c}" for c in range(5)) + " |" for r in range(4)),
]
THREE_PAGES = (
    "[PAGE 1]\n[BLOCK 1]\n가상용어 소개\n"
    "[PAGE 2]\n[TABLE 1]\n" + "\n".join(TABLE_ROWS) + "\n"
    "[PAGE 3]\n[BLOCK 1]\nvirtual english only"
)
GLOSSARY = [("가상용어", "Virtual Term")]


def per_site(p: CallPlan) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for call in p.calls:
        counts[call.site] += call.count
    return dict(counts)


# 손셈(R/ 줄은 plan.py 머리):
# 쪽 1 — [PAGE 1] 구획: 국문 0·120자 미만 → 0. [BLOCK 1]: 구획 번역 1 · 구획 윤문 1(국문) · 용어집 보정 1(key 있음) ·
#        한국어 보정 2. 쪽: 표 꼴 0 → 쪽 윤문 1 · 범용 QA 1.                                   = 7
# 쪽 2 — [TABLE 1] 국문 칸 25: 묶음 2(24+1) · 칸 대체 25 · 한국어 보정 2(용어집 key 0). 쪽: 표 꼴 → 0.  = 29
# 쪽 3 — [BLOCK 1] 국문 0·120자 미만 → 0. 쪽: 표 꼴 0 → 쪽 윤문 1 · 범용 QA 1.                     = 2
# 검수 쪽마다 1 · 자동수정 쪽마다 1 · 자동수정 한국어 쪽마다 1(R/6368)                              = 9
GENERAL = {
    "section": 1,
    "polish": 3,
    "glossary-repair": 1,
    "korean-repair": 4,
    "editorial-qa": 2,
    "table-batch": 2,
    "cell": 25,
    "review": 3,
    "autofix": 3,
    "autofix-korean": 3,
}


def test_three_pages_general_match_the_hand_count() -> None:
    p = plan(make_input(THREE_PAGES, base=GLOSSARY))
    assert p.rejection is None
    assert per_site(p) == GENERAL
    assert sum(GENERAL.values()) == 47
    assert len(p.calls) == 45  # 한국어 보정 둘이 count 2 짜리 한 줄씩
    assert [c.page_num for c in p.calls if c.site == "review"] == [1, 2, 3]
    assert {c.role for c in p.calls if c.site == "review"} == {"review"}


def test_ceo_adds_a_polish_for_every_short_section_and_a_b_doubles() -> None:
    """CEO 는 윤문 최소 길이를 보지 않는다(R/2499) — [PAGE n] 구획 셋과 쪽 3 의 영문 구획에 윤문 하나씩 더(+4)."""
    ceo = plan(make_input(THREE_PAGES, base=GLOSSARY, part="ceo_message"))
    assert per_site(ceo) == {**GENERAL, "polish": 3 + 4}
    ab = plan(make_input(THREE_PAGES, base=GLOSSARY, compare_ab=True))
    assert per_site(ab) == {site: 2 * n for site, n in GENERAL.items()}
    assert {c.variant for c in ab.calls} == {"A", "B"}
    no_fix = plan(make_input(THREE_PAGES, base=GLOSSARY, autofix=False))
    assert per_site(no_fix) == {k: v for k, v in GENERAL.items() if not k.startswith("autofix")}


def test_a_rejection_plans_no_call() -> None:
    seven = "".join(f"[PAGE {n}]\n[BLOCK 1]\n가상 {n}\n" for n in range(1, 8))
    rejected = plan(make_input(seven, part="ceo_message"))
    assert rejected.rejection is not None and rejected.rejection.kind == "ceo_page_limit"
    assert rejected.calls == []
    assert plan(make_input(THREE_PAGES, start=4)).calls == []


def test_the_stand_in_counts_four_latin_chars_per_token() -> None:
    assert stand_in(3) == "x" * 12


def test_the_plan_states_its_assumptions() -> None:
    p = plan(make_input(THREE_PAGES))
    assert any("max_tokens 만큼의 자리 글" in a for a in p.assumptions)
    assert any("칸 대체" in a for a in p.assumptions)


SIMPLE = "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."
SIMPLE_EN = "[BLOCK 1]\nVirtual Title\nVirtual body."
TABLE_SRC = "[PAGE 1]\n[TABLE 1]\n표 제목\n| 머리 | Value |\n| --- | --- |\n| 가상 | 1 |"
NO_ISSUES = ok("[]")

FLOWS: dict[str, tuple[EngineInput, Sequence[ProviderResponse]]] = {
    "short_general": (make_input(SIMPLE), [ok(SIMPLE_EN), NO_ISSUES]),
    "ceo": (
        make_input(SIMPLE, part="ceo_message"),
        [ok("[PAGE 1]"), ok(SIMPLE_EN), ok("[BLOCK 1]\nVirtual Title\nVirtual polished body."), NO_ISSUES],
    ),
    "glossary_repair": (
        make_input("[PAGE 1]\n[BLOCK 1]\n가상용어 소개", base=GLOSSARY),
        [ok("[BLOCK 1]\nvirtual word intro"), ok("[BLOCK 1]\nVirtual Term intro"), NO_ISSUES],
    ),
    "table_fallback": (
        make_input(TABLE_SRC),
        [ok("not json"), ok("Table Title"), ok("Header"), ok("Virtual"), NO_ISSUES],
    ),
    "korean_left_w7": (
        make_input(SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n남는 국문"),
        [
            ok(SIMPLE_EN),
            ok("[BLOCK 1]\nleft 국문"),
            ok("[BLOCK 1]\nstill 국문"),
            ok("[BLOCK 1]\nagain 국문"),
            NO_ISSUES,
            NO_ISSUES,
            ok("[PAGE 2]\n[BLOCK 1]\nRemaining text"),
        ],
    ),
    "a_b": (make_input(SIMPLE, compare_ab=True), [ok(SIMPLE_EN), ok(SIMPLE_EN), NO_ISSUES, NO_ISSUES]),
}


@pytest.mark.parametrize("case", sorted(FLOWS))
def test_the_calls_of_a_real_flow_fit_in_the_plan(case: str) -> None:
    inputs, replies = FLOWS[case]
    flow = run_flow(inputs, replies)
    p = plan(inputs)
    planned = per_site(p)
    actual = Counter(flow.sites)
    assert all(actual[site] <= planned.get(site, 0) for site in actual), (dict(actual), planned)
    shapes = {(c.site, c.system, c.max_tokens) for c in p.calls}
    assert {(c.site, c.system, c.max_tokens) for c in flow.calls} <= shapes
    assert {c.max_tokens for c in p.calls if c.site == "table-batch"} <= {prompts.MAX_TOKENS["table-batch"]}
