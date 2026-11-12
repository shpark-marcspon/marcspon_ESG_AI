"""말 목록과 갈래 차례(engines/g1/facets.py — 밴드 GE1 T6 곁)."""

from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id, render_prompt
from esgapi.greenwash.engines.g1 import facets as F
from esgapi.greenwash.engines.g1.passages import Built, Unit


def built(units: list[Unit], titles: dict[str, str]) -> Built:
    return Built(passages=(), stat={}, units=tuple(units), titles=titles, block_text={})


def test_vocab_counts_titles_headings_and_table_heads() -> None:
    units = [
        Unit("h1", "heading", 1, "s1", "기후 대응"),
        Unit("h2", "heading", 2, "s1", "기후 대응"),
        Unit("t1", "table", 3, "s1", "", (("구분", "2025"), ("전력 사용량", "12"), ("123", "4"))),
    ]
    got = F.vocab(built(units, {"s1": "환경"}))
    assert got == "기후 대응(2) · 구분(1) · 전력 사용량(1) · 환경(1)"


def test_vocab_stops_at_the_char_budget() -> None:
    units = [Unit(f"h{i}", "heading", 1, "s1", f"가상 제목 {i:05d}") for i in range(2000)]
    got = F.vocab(built(units, {}))
    assert len(got) <= F.VOCAB_CHARS


def test_facets_are_cut_at_eight_and_ordered_by_likelihood() -> None:
    plan = F.FacetPlan.model_validate(
        {
            "facets": [
                {"name": f"갈래{i}", "keywords": ["가"], "likelihood": "low" if i % 2 else "high", "reason": "-"}
                for i in range(10)
            ]
        }
    )
    fs = F.facets_of(plan)
    assert len(fs) == 8
    per = [(fs[1], ["P9", "P8"]), (fs[0], ["P1", "P9"])]
    assert F.order_by_likelihood(per, 2) == ["P1", "P9", "P8"]


def test_the_two_prompts_render_with_the_vocab_in_the_cached_segment() -> None:
    store = PackagePromptStore()
    facets = render_prompt(
        store.get(parse_prompt_id("greenwash/ge-facets@1")), {"vocab": "말(1)", "claim": "가상 주장"}
    )
    assert [s.cache for s in facets.system] == [True]
    assert facets.system[0].text.endswith("[보고서 말 목록]\n말(1)")
    assert facets.user.endswith("[질의]\n가상 주장")
    rerank = render_prompt(
        store.get(parse_prompt_id("greenwash/ge-rerank@1")), {"claim": "가상 주장", "lines": "[P1] 글"}
    )
    assert rerank.user == "[질의]\n가상 주장\n\n[단락]\n[P1] 글"
