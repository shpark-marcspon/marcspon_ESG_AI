"""템플릿 글 열일곱(engines/colab_155/texts.py, 밴드 IR4 §3-1 — 순수): 기본 글의 렌더가 IR4 앞 f-문자열 식과 바이트
같음 · 자리 표 = 기본 글에서 센 자리 · 끼우기는 한 번 · 날 글 칸은 끼운 뒤 dedent · 규제 틀 글자 수.

견줄 값(oracle)은 IR4 앞(BASE 54a38aaa) prompts.py·part2_prompts.py 의 f-문자열 함수 여섯을 이 파일에 그대로 옮긴
것이다 — 엔진 함수가 같은 render 를 두 번 부르는 동어반복을 피한다. 입력은 전부 지어낸 「가상…」.
"""

import re
from dataclasses import fields, replace
from textwrap import dedent

import pytest

from esgapi.materiality.engines.colab_155 import part2_prompts, prompts, texts, whitelists
from esgapi.materiality.engines.colab_155.inputs import industry_text
from esgapi.materiality.engines.colab_155.texts import DEFAULT_TEXTS, PLACEHOLDERS, RAW_KEYS, REQUIRED, PromptTexts

# ── IR4 앞 f-문자열 식(BASE 그대로 — 견줄 값) ─────────────────────────────────────────────────


def colab_regulation_user(
    topic_name: str, topic_desc: str, industry_text: str, location: str, main_language: str
) -> str:
    return dedent(f"""\
      [가변 입력]
      industry_definition:
      {industry_text}

      geo_scope: {location}
      preferred_language: {main_language}

      topic_name: {topic_name}
      topic_desc: {topic_desc}""")


def colab_keywords_user(industry: object, date_range: str, main_language: str, topics: object) -> str:
    return dedent(f"""\
      [가변 입력]
      industry: {industry}
      date_range: {date_range}
      main_language: {main_language}
      topics: {topics}
      """)


def colab_controversy_user(
    topic_name: str, topic_desc: str, industry: object, location: str, main_language: str, keyword_str: str
) -> str:
    return dedent(f"""\
      [가변 입력]
      industry_definition:
      {industry}

      geo_scope: {location}
      preferred_language: {main_language}

      keyword: {keyword_str}
      topic_name: {topic_name}
      topic_desc: {topic_desc}
      """)


def colab_impact_user(
    company: str,
    industry: object,
    value_chain: object,
    topic_each: str,
    sub_name: str,
    sub_desc: str,
    controversies: str,
    regulation_updates: str,
) -> str:
    return dedent(f"""
      [Company]
      - Name: {company}
      - Industry: {industry}


      <value_chain_list>
        {value_chain}
        </value_chain_list>

      <ESRS Topic, Subtopic>
      - Topic: {topic_each}
      - Subtopic: {sub_name}
      - Subtopic description: {sub_desc}
      </ESRS Topic, Subtopic>

      <Controversies for this topic>
      {controversies if controversies.strip() else "제공된 컨트로버시 정보 없음"}
      </Controversies for this topic>

      <Regulation & Policy Updates for this topic>
     {regulation_updates if regulation_updates.strip() else "제공된 정책/규정/가이드라인 정보 없음"}
      </Regulation & Policy Updates for this topic>
      """)


def colab_financial_user(
    company: str,
    industry: object,
    value_chain: object,
    topic_each: str,
    sub_name: str,
    sub_desc: str,
    controversies_text: str,
    regulation_text: str,
) -> str:
    return dedent(f"""
      [Company]
      - Name: {company}
      - Industry: {industry}

      <value_chain_list>
        {value_chain}
      </value_chain_list>

      <ESRS Topic, Subtopic>
      - Topic: {topic_each}
      - Subtopic: {sub_name}
      - Subtopic description: {sub_desc}
      </ESRS Topic, Subtopic>

      <Controversies for this topic>
      {controversies_text}
      </Controversies for this topic>

      <Regulation & Policy Updates for this topic>
      {regulation_text}
      </Regulation & Policy Updates for this topic>
      """)


def colab_pathway_user(fin_impact: str) -> str:
    return dedent(f"""아래는 Topic–Subtopic—영향 정의 표의 결과물이다.
각 표의 “행(row)”마다 1개씩, 입력된 ‘Topic’,‘Subtopic’, ‘영향 정의’별로 “재무 Impact Pathway”를 생성해줘.

요구사항:
- 각 ‘Topic’,‘Subtopic’, ‘영향 정의’마다 ① Impact Driver → ② 비즈니스 영향 → ③ 재무 영향을 모두 출력할 것
- ESRS/ISSB 기준에 따라 재무 영향 매핑은 정합성 있게 추론

주의:
- 헤더를 제외한 각 행 = 1개의 i 행(영향 정의의 행)으로 작성할 것.
- 총 행 개수와 i 행(영향 정의의 행) 개수는 반드시 같아야 한다.
- 영향 정의를 서로 합치거나 “대표 사례만” 다루지 말 것.

[INPUT TABLE BELOW]
{fin_impact}""")


# ── 지어낸 입력 ─────────────────────────────────────────────────────────────────────────────

ONE = [{"standard": "SASB", "industry_name": "가상 산업 하나", "description": "가상 설명 — 가상의 시설"}]
THREE = [
    {"standard": "SASB", "industry_name": f"가상 산업 {n}", "description": f"가상 설명 {n}\n  둘째 줄"}
    for n in range(3)
]
DESCRIPTIONS = ("가상토픽의 설명", "가상 설명 첫 줄\n둘째 줄\n    들여 쓴 셋째 줄")
BUNDLE = '{\n  "items": [\n    {\n      "title": "가상 사건"\n    }\n  ]\n}'
CONTEXTS = (
    ("", "  \n"),
    (BUNDLE, BUNDLE),
    ("가상 사건 글", ""),
    ("  가상 사건 글\n", "\n  가상 규제 글  "),  # 앞뒤 공백(① 검증 권고 R2)
)
VALUE_CHAIN = [{"activity": "가상 활동", "stage": "가상 단계"}]
TOPICS = [{"topic": "가상토픽 하나", "description": "가상토픽 하나의 설명"}]

HANGUL_SLOT = re.compile(r"\{[^{}\n]*[가-힣][^{}\n]*\}")


@pytest.mark.parametrize("industry", [ONE, THREE], ids=["one", "three"])
@pytest.mark.parametrize("description", DESCRIPTIONS, ids=["line", "lines"])
def test_part1_defaults_render_the_colab_bytes(industry: list[dict[str, str]], description: str) -> None:
    text = industry_text(industry)
    assert prompts.regulation_user("가상토픽", description, text, "KR", "ko") == colab_regulation_user(
        "가상토픽", description, text, "KR", "ko"
    )
    topics = [{"topic": "가상토픽", "description": description}]
    assert prompts.keywords_user(industry, "2025-01-01~오늘까지", "ko", topics) == colab_keywords_user(
        industry, "2025-01-01~오늘까지", "ko", topics
    )
    keyword = "가상 키워드 1, 가상 키워드 2"
    assert prompts.controversy_user("가상토픽", description, industry, "KR", "ko", keyword) == colab_controversy_user(
        "가상토픽", description, industry, "KR", "ko", keyword
    )
    if len(industry) > 1:  # 산업 셋이면 dedent 가 6칸을 못 벗긴다(W4) — 그 꼴이 그대로 남는다
        assert "\n      geo_scope: KR" in prompts.regulation_user("가상토픽", description, text, "KR", "ko")


@pytest.mark.parametrize(("controversies", "regulations"), CONTEXTS, ids=["empty", "bundle", "text", "padded"])
@pytest.mark.parametrize("description", DESCRIPTIONS, ids=["line", "lines"])
def test_part2_defaults_render_the_colab_bytes(controversies: str, regulations: str, description: str) -> None:
    for industry in (ONE, THREE):
        given = ("가상 회사", industry, VALUE_CHAIN, "가상토픽", "가상 서브", description, controversies, regulations)
        assert part2_prompts.impact_user(*given) == colab_impact_user(*given)
        assert part2_prompts.financial_user(*given) == colab_financial_user(*given)
    table = "| Topic | Subtopic |\n|---|---|\n| 가상토픽 | 가상 서브 |"
    assert part2_prompts.pathway_user(table) == colab_pathway_user(table)


def test_the_regulation_template_takes_each_whitelist_cut_to_the_byte() -> None:
    for raw in (whitelists.WHITELIST_COLAB17, whitelists.WHITELIST_CELL71, whitelists.WHITELIST_CELL73):
        assert prompts.render(DEFAULT_TEXTS.regulation_system, {prompts.WHITELIST_SLOT: dedent(raw)}) == dedent(
            prompts._REGULATION_SYSTEM_HEAD + raw + prompts._REGULATION_SYSTEM_TAIL  # pyright: ignore[reportPrivateUsage]
        )
    template = DEFAULT_TEXTS.regulation_system
    assert (len(template), len(template.encode())) == (7_659, 12_258)  # 판을 뗀 틀(★F) — 8,000 까지 341
    assert template.count(prompts.WHITELIST_SLOT) == 1


def test_default_texts_are_the_engine_constants() -> None:
    assert [f.name for f in fields(PromptTexts)] == list(PLACEHOLDERS)
    assert len(PLACEHOLDERS) == 17
    assert DEFAULT_TEXTS.keywords_system == prompts.KEYWORDS_SYSTEM
    assert DEFAULT_TEXTS.regulation_prefix == prompts.REGULATION_USER_PREFIX
    assert DEFAULT_TEXTS.impact_system == part2_prompts.IMPACT_SYSTEM
    assert DEFAULT_TEXTS.whitelist_financial == dedent(whitelists.WHITELIST_CELL71)
    assert DEFAULT_TEXTS.whitelist_non_financial == dedent(whitelists.WHITELIST_CELL73)
    assert all(len(getattr(DEFAULT_TEXTS, f.name)) <= 8_000 for f in fields(PromptTexts))  # core 글 상한
    # 날 글의 시작(1-3 M1): 1부 셋은 6칸 [가변 입력], 2부 영향·재무는 앞 줄바꿈 하나, 경로는 줄바꿈 없음
    assert [DEFAULT_TEXTS.regulation_input[:13], DEFAULT_TEXTS.keywords_input[:13]] == ["      [가변 입력]"] * 2
    assert DEFAULT_TEXTS.controversy_input.startswith("      [가변 입력]")
    assert DEFAULT_TEXTS.impact_input.startswith("\n      [Company]")
    assert DEFAULT_TEXTS.financial_input.startswith("\n      [Company]")
    assert DEFAULT_TEXTS.pathway_input.startswith("아래는")


def test_placeholders_are_the_slots_counted_in_each_default_text() -> None:
    for f in fields(PromptTexts):
        found = list(dict.fromkeys(HANGUL_SLOT.findall(getattr(DEFAULT_TEXTS, f.name))))
        assert found == list(PLACEHOLDERS[f.name]), f.name  # 자리 밖 한글 {…} 0 · 차례 = 기본 글의 차례
    assert {
        "regulation_input",
        "keywords_input",
        "controversy_input",
        "impact_input",
        "financial_input",
        "pathway_input",
    } == RAW_KEYS
    assert {key: len(slots) for key, slots in REQUIRED.items()} == {
        "regulation_system": 1,
        "controversy_input": 6,
        "financial_input": 8,
        "impact_input": 8,
        "keywords_input": 4,
        "pathway_input": 1,
        "regulation_input": 5,
    }


def test_values_are_put_in_once() -> None:
    """끼운 값 안의 자리 글자·`{{` 는 다시 끼우지 않는다(한 번 끼우기)."""
    made = prompts.regulation_user("{토픽 설명}", "{산업 정의} {{x}}", "- {검색 지역}\n", "KR", "ko")
    assert "topic_name: {토픽 설명}\ntopic_desc: {산업 정의} {{x}}" in made
    assert "- {검색 지역}\n" in made
    impact = part2_prompts.impact_user("가상 {가치사슬 활동}", ONE, VALUE_CHAIN, "{서브토픽}", "s", "d", "{기업명}", "")
    assert "- Name: 가상 {가치사슬 활동}" in impact
    assert "- Topic: {서브토픽}" in impact
    assert "{기업명}\n" in impact
    assert part2_prompts.pathway_user("{재무 영향 정의의 답}").endswith("[INPUT TABLE BELOW]\n{재무 영향 정의의 답}")


def test_a_stored_raw_text_is_dedented_after_the_values() -> None:
    """저장 가변 글을 4칸으로 줄여도 render_raw 는 코랩 식(끼운 뒤 dedent)대로 — 값의 0칸 줄이 dedent 를 막는다."""
    stored = "    [가변 입력]\n    industry_definition:\n    {산업 정의}\n\n    topic_name: {토픽}"
    given = replace(DEFAULT_TEXTS, regulation_input=stored)
    one = prompts.regulation_user("가상토픽", "d", "- 가상 산업\n", "KR", "ko", texts=given)
    assert one == "[가변 입력]\nindustry_definition:\n- 가상 산업\n\n\ntopic_name: 가상토픽"
    three = prompts.regulation_user("가상토픽", "d", "- 가상 산업 1\n- 가상 산업 2\n", "KR", "ko", texts=given)
    assert three == (
        "    [가변 입력]\n    industry_definition:\n    - 가상 산업 1\n- 가상 산업 2\n\n\n    topic_name: 가상토픽"
    )


def test_missing_slots_names_the_removed_ones_in_order() -> None:
    text = DEFAULT_TEXTS.impact_input.replace("{기업명}", "").replace("{서브토픽 설명}", "")
    assert texts.missing_slots(text, REQUIRED["impact_input"]) == ["{기업명}", "{서브토픽 설명}"]
    assert texts.missing_slots(DEFAULT_TEXTS.impact_input, REQUIRED["impact_input"]) == []


def test_the_whitelist_name_picks_its_cell() -> None:
    marked = replace(DEFAULT_TEXTS, whitelist_financial="⟦금융⟧", whitelist_non_financial="⟦비금융⟧")
    assert texts.whitelist_text(marked, whitelists.whitelist_for("financial")[0]) == "⟦금융⟧"
    assert texts.whitelist_text(marked, whitelists.whitelist_for("non_financial")[0]) == "⟦비금융⟧"
