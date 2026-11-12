"""실패 쪽만 다시(코랩 셀 50, R/3560-3616 — MARC-ISSUE-212 의 2): 고른 쪽만 다시 번역하고 셀 52~67 을 전 쪽에 돈다.

base = 앞 실행의 문체별 번역 글(자동수정 전). 코랩 약점 그대로(MARC-ENT-297): 옛 `[TRANSLATION_ERROR page=n]` 줄은
`parse_pages` 로 앞 쪽 꼬리에 붙어 남는다.
"""

from collections import Counter
from collections.abc import Mapping, Sequence

from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderResponse
from esgapi.translation.engines.colab_158 import pipeline
from esgapi.translation.engines.colab_158.pipeline import EngineInput
from esgapi.translation.engines.colab_158.plan import retry_plan
from esgapi.translation.engines.colab_158.records import VariantLabel
from esgapi.translation.tests.engines.colab_158.plan_fit import misfits
from esgapi.translation.tests.engines.colab_158.support import Flow, Recording, client, fail, make_input, ok
from esgapi.translation.tools.llm_bridge import LlmBridge

NO_ISSUES = ok("[]")
SRC = "[PAGE 1]\n[BLOCK 1]\n가상 하나\n[PAGE 2]\n[BLOCK 1]\n가상 둘\n[PAGE 3]\n[BLOCK 1]\n가상 셋"


def base_text(label: str) -> str:
    """앞 실행이 쪽 3 에서 실패한 글(셀 49 꼴 — 실패 쪽은 표지 줄 + 원문)."""
    return (
        f"[PAGE 1]\n[BLOCK 1]\nVirtual one {label}\n\n"
        f"[PAGE 2]\n[BLOCK 1]\nVirtual two {label}\n\n"
        "[TRANSLATION_ERROR page=3]\n[PAGE 3]\n[BLOCK 1]\n가상 셋"
    )


AB_BASE: dict[VariantLabel, str] = {"A": base_text("A"), "B": base_text("B")}


def retry_flow(
    inputs: EngineInput, base: Mapping[VariantLabel, str], pages: Sequence[int], replies: Sequence[ProviderResponse]
) -> Flow:
    anthropic, openai = MockProvider("anthropic"), MockProvider("openai")
    for reply in replies:
        openai.enqueue(reply)
    providers = {"anthropic": anthropic, "openai": openai}
    recording = Recording(
        LlmBridge(client(providers), part=inputs.part, tenant="tenant-synthetic"), inputs.part, providers
    )
    result = pipeline.retry(inputs, recording, base, pages)
    assert openai.pending == 0, f"심은 답 {openai.pending} 개가 남았다"
    return Flow(result, recording.calls, anthropic, openai)


def test_only_the_chosen_page_is_translated_and_every_page_is_reviewed() -> None:
    inputs = make_input(SRC, compare_ab=True)
    replies = [ok("[BLOCK 1]\nVirtual three A"), ok("[BLOCK 1]\nVirtual three B"), *[NO_ISSUES] * 6]
    flow = retry_flow(inputs, AB_BASE, [3, 7], replies)
    assert flow.sites == ["section", "section", *["review"] * 6]
    a, b = flow.run.variants
    assert "Virtual three A" in a.translated_text and "Virtual three B" in b.translated_text
    assert "Virtual one A" in a.translated_text and "Virtual two B" in b.translated_text
    # 코랩 약점: 옛 실패 표지 줄은 쪽 2 꼬리에 남는다
    assert "Virtual two A\n\n[TRANSLATION_ERROR page=3]\n\n[PAGE 3]" in a.translated_text
    assert [(w.code, w.page_num) for w in flow.run.warnings] == [("retry_page_missing", 7)]
    assert [(f.page_num, f.status) for f in a.fragments] == [(3, "translated")]
    assert [p.page_num for p in a.pages] == [1, 2, 3] and [p.page_num for p in b.pages] == [1, 2, 3]
    plan = retry_plan(inputs, AB_BASE, [3, 7])
    assert Counter(c.site for c in plan.calls if c.site == "review")["review"] == flow.sites.count("review")
    assert misfits(flow.calls, plan) == []


def test_one_failing_style_keeps_the_old_text_for_every_style() -> None:
    inputs = make_input(SRC, compare_ab=True)
    replies = [ok("[BLOCK 1]\nVirtual three A"), fail(), *[NO_ISSUES] * 6]
    flow = retry_flow(inputs, AB_BASE, [3], replies)
    a, b = flow.run.variants
    assert "Virtual three A" not in a.translated_text
    assert a.translated_text.endswith("[PAGE 3]\n[BLOCK 1]\n가상 셋")
    assert b.translated_text.endswith("[PAGE 3]\n[BLOCK 1]\n가상 셋")
    assert [(w.code, w.page_num) for w in flow.run.warnings if w.code.startswith("retry")] == [("retry_failed", 3)]
    assert [(f.page_num, f.status, f.error) for f in a.fragments] == [(3, "error", "section: provider_error")]


def test_the_later_chunk_of_a_page_number_wins_in_both_maps() -> None:
    """원문 지도·base 지도 둘 다 번호로 — 같은 번호면 뒤 조각(R/3568-3569·3577-3579), 범위 거름 없음."""
    src = "[PAGE 1]\n[BLOCK 1]\n가상 앞쪽\n[PAGE 1]\n[BLOCK 1]\n가상 뒤쪽\n[PAGE 2]\n[BLOCK 1]\n가상 둘"
    base: dict[VariantLabel, str] = {
        "single": "[PAGE 1]\nold first\n\n[PAGE 1]\nold second\n\n[PAGE 2]\n[BLOCK 1]\nVirtual two"
    }
    inputs = make_input(src, start=2, end=2)
    flow = retry_flow(inputs, base, [1], [ok("[BLOCK 1]\nVirtual back"), NO_ISSUES])
    assert "가상 뒤쪽" in flow.calls[0].user and "가상 앞쪽" not in flow.calls[0].user
    (variant,) = flow.run.variants
    assert "old first" not in variant.translated_text and "old second" not in variant.translated_text
    assert variant.translated_text.startswith("[PAGE 1]")
    assert [p.page_num for p in variant.pages] == [2]  # 셀 65 의 범위 거름은 그대로


def test_the_pages_are_written_back_in_number_order() -> None:
    base: dict[VariantLabel, str] = {"single": "[PAGE 2]\n[BLOCK 1]\nVirtual two\n\n[PAGE 1]\n[BLOCK 1]\nVirtual one"}
    flow = retry_flow(make_input(SRC), base, [3], [ok("[BLOCK 1]\nVirtual three"), NO_ISSUES, NO_ISSUES, NO_ISSUES])
    text = flow.run.variants[0].translated_text
    assert text.index("Virtual one") < text.index("Virtual two") < text.index("Virtual three")
