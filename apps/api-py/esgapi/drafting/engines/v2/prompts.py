"""v2 의 호출 글 짓기(RPA4 — 자리 `{페이지 글}` 은 v2 자기 슬롯이라 v1 끼움(engines/v1/prompts.map_texts·draft_texts)이
모른다. v1 render 는 표에 없는 `{…}` 를 그대로 두므로 v2 글을 v1 끼움에 넘기면 재료 0 인 글이 공급사로 간다 — 흐름은
이 파일만 부른다). 끼움 규칙(render — 한 번에 끼움, 끼운 값을 다시 훑지 않음)과 목차 줄(outline_lines)은 v1 그대로.

map_texts(texts, outline, pages)              S2 의 (system, user)
draft_texts(texts, path, requirement, pages)  S3 의 (system, user)
"""

from collections.abc import Sequence

from esgapi.drafting.engines.v1.prompts import PATH_JOIN, render

from .texts import OUTLINE_SLOT, PAGES_SLOT, REQUIREMENT_SLOT, TITLE_SLOT, PromptTexts


def map_texts(texts: PromptTexts, outline: str, pages: str) -> tuple[str, str]:
    return texts.map_system, render(texts.map_user, {OUTLINE_SLOT: outline, PAGES_SLOT: pages})


def draft_texts(texts: PromptTexts, path: Sequence[str], requirement: str, pages: str) -> tuple[str, str]:
    values = {TITLE_SLOT: PATH_JOIN.join(path), REQUIREMENT_SLOT: requirement, PAGES_SLOT: pages}
    return texts.draft_system, render(texts.draft_user, values)
