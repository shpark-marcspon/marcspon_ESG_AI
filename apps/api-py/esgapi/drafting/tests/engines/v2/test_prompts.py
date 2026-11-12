"""v2 호출 글 짓기(engines/v2/prompts.py — RPA4 B3): v2 자리 `{페이지 글}` 을 끼운다 · 한 번에 끼운다(재료 안의 자리
글자를 다시 훑지 않는다 — v1 test_prompts 꼴) · v1 끼움은 v2 글의 재료 자리를 모른다(그래서 흐름은 v2 끼움만 부른다).
순수 층."""

from esgapi.drafting.engines.v1 import prompts as v1_prompts
from esgapi.drafting.engines.v2 import prompts
from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS, PAGES_SLOT


def test_map_texts_fills_the_v2_slots() -> None:
    outline = v1_prompts.outline_lines([("k", ("환경", "기후"), "요구")])
    system, user = prompts.map_texts(DEFAULT_TEXTS, outline, "[PAGE 1]\n지어낸 글")
    assert system == DEFAULT_TEXTS.map_system
    assert user == "[목차 잎 — key | 제목 경로 | 요구 내용]\nk | 환경 > 기후 | 요구\n\n[페이지 글]\n[PAGE 1]\n지어낸 글"


def test_draft_texts_fills_the_v2_slots() -> None:
    system, user = prompts.draft_texts(DEFAULT_TEXTS, ("환경", "기후"), "배출량", "[PAGE 2]\n[B b1] ⟨0⟩지어낸 문장")
    assert system == DEFAULT_TEXTS.draft_system
    assert user == "[목차 잎] 환경 > 기후\n[요구 내용] 배출량\n\n[자료]\n[PAGE 2]\n[B b1] ⟨0⟩지어낸 문장"


def test_a_slot_glyph_inside_the_material_is_not_filled_again() -> None:
    _, user = prompts.draft_texts(DEFAULT_TEXTS, ("가",), "{제목 경로}", f"[PAGE 3]\n{PAGES_SLOT}")
    assert user == f"[목차 잎] 가\n[요구 내용] {{제목 경로}}\n\n[자료]\n[PAGE 3]\n{PAGES_SLOT}"
    _, user = prompts.map_texts(DEFAULT_TEXTS, "{목차}", PAGES_SLOT)
    assert user.endswith(f"\n{{목차}}\n\n[페이지 글]\n{PAGES_SLOT}")


def test_the_v1_fill_leaves_the_v2_material_slot_empty() -> None:
    """함정의 분모: v1 끼움에 v2 글을 넘기면 재료 자리가 글자 그대로 남는다(거절 0)."""
    _, user = v1_prompts.map_texts(DEFAULT_TEXTS, "k | 가 | 나", "[PAGE 1]\n지어낸 글")
    assert user.endswith(f"[페이지 글]\n{PAGES_SLOT}") and "[PAGE 1]" not in user
