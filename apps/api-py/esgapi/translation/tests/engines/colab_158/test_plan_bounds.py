"""호출 계획의 위끝 둘(MARC-ISSUE-196 의 1)과 N6 대조: (a) 표 구획 번역 글의 위끝 = max(묶음 수 × 8192, 칸 수 × 1024),
(b) 자동수정 한국어 보정 입력 = max(쪽 번역 위끝, 자동수정 max_tokens). 실제 흐름(모의 공급사)의 요청마다 입력 어림이
계획 줄 하나에 든다(plan_fit — 집합 대조가 아니다).
"""

import pytest

from esgapi.core.llm.types import ProviderResponse
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.plan import plan, stand_in
from esgapi.translation.tests.engines.colab_158.plan_fit import input_tokens, misfits
from esgapi.translation.tests.engines.colab_158.support import make_input, ok, run_flow
from esgapi.translation.tests.engines.colab_158.test_plan import FLOWS

NO_ISSUES = ok("[]")

COLS = 5
ROWS = 6
TABLE_30 = "[PAGE 1]\n[TABLE 1]\n" + "\n".join(
    [
        "| " + " | ".join(f"머리{c}" for c in range(COLS)) + " |",
        "| " + " | ".join("---" for _ in range(COLS)) + " |",
        *("| " + " | ".join(f"칸{r}{c}" for c in range(COLS)) + " |" for r in range(ROWS - 1)),
    ]
)
"""국문 칸 30(머리 5 + 몸 25) — 묶음 2(24+6)."""

CELL_EN = "V" * 3000
"""칸 하나의 영문 답 3000자(약 750토큰) — 칸 30 이면 약 22,500토큰으로 묶음 위끝 2 × 8192 를 넘는다(칸 위끝 1024 안)."""


def table_30_replies() -> list[ProviderResponse]:
    """묶음 JSON 둘 다 실패 → 칸 대체(묶음 1 의 24칸, 묶음 2 의 6칸) → 검수 이슈 0."""
    return [ok("not json"), *[ok(CELL_EN)] * 24, ok("not json"), *[ok(CELL_EN)] * 6, NO_ISSUES]


LONG_KO = "[PAGE 1]\n[BLOCK 1]\n" + "\n".join(f"{i:02d}" + "가" * 298 for i in range(40))
"""국문 줄 40 × 300자 = 12,000자(cjk 1자 = 1토큰) — 자동수정 max_tokens 4096 보다 긴 쪽. 한국어 잔존 셈은 40줄·줄당
300자까지라 남은 줄 목록도 원문만큼 길다."""


def long_ko_replies() -> list[ProviderResponse]:
    """번역·한국어 보정 둘이 국문을 그대로 돌려 쪽이 실패(W7) → 쪽 글 = 원문. 검수 이슈 0 이어도 국문이 남아
    자동수정이 돈다 → 자동수정이 쪽을 그대로 돌려줌(그대로 갈래) → 한국어 보정 입력 = 원문 길이의 쪽."""
    body = LONG_KO.split("\n", 1)[1]
    return [
        ok(body),  # section(구획 윤문은 원문이 길어 돌지 않는다)
        ok(body),  # korean-repair 1
        ok(body),  # korean-repair 2
        NO_ISSUES,  # review
        ok(LONG_KO),  # autofix — 그대로
        ok("[PAGE 1]\n[BLOCK 1]\nVirtual fixed."),  # autofix-korean
    ]


def test_a_table_section_bound_covers_the_cell_fallback_output() -> None:
    """(a): 칸 30 이 다 대체되면 구획 번역 글은 칸 수 × 1024 까지 — 검수 입력의 자리 글이 그만큼."""
    p = plan(make_input(TABLE_30))
    (review,) = [c for c in p.calls if c.site == "review"]
    bound = max(2 * prompts.MAX_TOKENS["table-batch"], 30 * prompts.MAX_TOKENS["cell"])
    assert stand_in(bound) in review.user


def test_b_the_autofix_korean_input_covers_an_unchanged_page() -> None:
    """(b): 자동수정이 쪽을 그대로 두면 한국어 보정에 쪽 번역 글이 들어간다 — 자리 글이 쪽 위끝 이상."""
    p = plan(make_input(LONG_KO))
    (review,) = [c for c in p.calls if c.site == "review"]
    (ko,) = [c for c in p.calls if c.site == "autofix-korean"]
    page_stand_in = review.user.split("[PAGE 1]\n")[-1].split("\n")[0]
    assert len(page_stand_in) > prompts.MAX_TOKENS["autofix"] * 4
    assert page_stand_in in ko.user


def test_the_cell_fallback_flow_fits_the_plan() -> None:
    flow = run_flow(make_input(TABLE_30), table_30_replies())
    assert flow.sites.count("cell") == 30
    review = next(c for c in flow.calls if c.site == "review")
    assert input_tokens(review.system, review.user) > 2 * prompts.MAX_TOKENS["table-batch"]
    assert misfits(flow.calls, plan(make_input(TABLE_30))) == []


def test_the_unchanged_autofix_flow_fits_the_plan() -> None:
    flow = run_flow(make_input(LONG_KO), long_ko_replies())
    assert flow.sites[-2:] == ["autofix", "autofix-korean"]
    ko = flow.calls[-1]
    # BASE 의 위끝(자리 글 4096토큰 둘 + 원문)보다 실제 입력(남은 줄 + 원문 + 그대로인 쪽)이 크다
    base_bound = input_tokens(ko.system, stand_in(prompts.MAX_TOKENS["autofix"]) * 2 + LONG_KO)
    assert input_tokens(ko.system, ko.user) > base_bound
    assert misfits(flow.calls, plan(make_input(LONG_KO))) == []


@pytest.mark.parametrize("case", sorted(FLOWS))
def test_every_real_request_fits_one_plan_line(case: str) -> None:
    """N6: test_plan 의 흐름 여섯 — 요청마다 같은 (자리, system, max_tokens) 의 계획 줄 하나, 입력 어림 ≤ 계획."""
    inputs, replies = FLOWS[case]
    assert misfits(run_flow(inputs, replies).calls, plan(inputs)) == []


def test_a_wrong_system_in_the_plan_is_caught() -> None:
    """집합 대조는 계획 한 줄의 system 이 틀려도 다른 줄이 덮으면 가렸다 — 줄 대조는 가리지 않는다."""
    inputs, replies = FLOWS["glossary_repair"]
    p = plan(inputs)
    first = p.calls[0]
    p.calls[0] = type(first)(first.site, first.role, first.system + " ", first.user, first.max_tokens, 1, 1, "single")
    assert misfits(run_flow(inputs, replies).calls, p) != []
