"""프롬프트 끼우기(dataverify colab_156 prompts.render 의 꼴 — str.format 금지, 한 번에 끼움)와 호출 글 짓기.

render(template, values)          자리 → 값(alternation 하나 + 콜백). 표에 없는 `{…}` 는 그대로
outline_lines(leaves)             S2 의 목차 잎 줄 「key | 대 > … > 잎 | 요구 내용 앞 300자」
map_texts(texts, outline, pages)  S2 의 (system, user)
draft_texts(texts, path, requirement, pages)  S3 의 (system, user)
"""

import re
from collections.abc import Mapping, Sequence
from typing import Final

from .texts import OUTLINE_SLOT, PAGES_SLOT, REQUIREMENT_SLOT, TITLE_SLOT, PromptTexts

REQUIREMENT_HEAD_CHARS: Final = 300
PATH_JOIN: Final = " > "


def render(template: str, values: Mapping[str, str]) -> str:
    if not values:
        return template
    pattern = re.compile("|".join(re.escape(slot) for slot in sorted(values, key=len, reverse=True)))
    return pattern.sub(lambda match: values[match.group(0)], template)


def outline_lines(leaves: Sequence[tuple[str, Sequence[str], str]]) -> str:
    """leaves = (key, 제목 경로, 요구 내용) 목차 차례."""
    return "\n".join(
        f"{key} | {PATH_JOIN.join(path)} | {' '.join(requirement.split())[:REQUIREMENT_HEAD_CHARS]}"
        for key, path, requirement in leaves
    )


def map_texts(texts: PromptTexts, outline: str, pages: str) -> tuple[str, str]:
    return texts.map_system, render(texts.map_user, {OUTLINE_SLOT: outline, PAGES_SLOT: pages})


def draft_texts(texts: PromptTexts, path: Sequence[str], requirement: str, pages: str) -> tuple[str, str]:
    values = {TITLE_SLOT: PATH_JOIN.join(path), REQUIREMENT_SLOT: requirement, PAGES_SLOT: pages}
    return texts.draft_system, render(texts.draft_user, values)
