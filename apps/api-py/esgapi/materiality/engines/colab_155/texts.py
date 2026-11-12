"""중대성평가 IRO 의 템플릿 글 열일곱(밴드 IR4) — AI 설정 판의 프롬프트 칸과 같은 이름·차례(판 칸은 그중 열넷, IRA3).

PromptTexts 의 칸 이름 = 판의 칸 key(flows/prompt_model_155 가 묶음 여섯으로 연다). DEFAULT_TEXTS = 이 폴더의 기본
글이고 그 렌더는 IR4 앞 함수와 바이트 같다. 칸은 두 꼴로 렌더한다:
- 지시 글·입력 글(접두)·신뢰 출처 목록 = prompts.render(한 번 끼우기만 — 지시·접두는 자리가 없어 그대로, 규제 지시 글은
  `{신뢰 출처 목록}` 에 sector 로 고른 whitelist 칸 글).
- RAW_KEYS 여섯(1부 가변 입력 셋·2부 입력 글 셋) = prompts.render_raw(끼운 뒤 dedent — 코랩 f-문자열 + dedent 식).
PLACEHOLDERS = 칸마다 제 기본 글의 자리(그것만 끼운다 — 처분 Q4). REQUIRED = 지우면 안 되는 자리(처분 Q5 — 날 글 칸은
자리 전부, 규제 지시 글은 `{신뢰 출처 목록}`). 표준 라이브러리와 이 폴더만 import 한다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from textwrap import dedent
from typing import Final

from esgapi.materiality.engines.colab_155 import part2_prompts as p2
from esgapi.materiality.engines.colab_155 import prompts as p1
from esgapi.materiality.engines.colab_155 import whitelists
from esgapi.materiality.engines.colab_155.whitelists import WhitelistName


@dataclass(frozen=True, slots=True, kw_only=True)
class PromptTexts:
    """템플릿 글 열일곱(칸 이름 = AI 설정 판의 칸 key, 판은 열넷만 덮음). 엔진은 칸 key 를 모른다 — 이 이름은 판
    조합 쪽과 맞춘 것이다."""

    regulation_system: str
    regulation_prefix: str
    regulation_input: str
    keywords_system: str
    keywords_prefix: str
    keywords_input: str
    controversy_system: str
    controversy_prefix: str
    controversy_input: str
    impact_system: str
    impact_input: str
    financial_system: str
    financial_input: str
    pathway_system: str
    pathway_input: str
    whitelist_non_financial: str
    whitelist_financial: str


DEFAULT_TEXTS: Final = PromptTexts(
    regulation_system=p1.REGULATION_SYSTEM_TEMPLATE,
    regulation_prefix=p1.REGULATION_USER_PREFIX,
    regulation_input=p1.REGULATION_USER_RAW,
    keywords_system=p1.KEYWORDS_SYSTEM,
    keywords_prefix=p1.KEYWORDS_USER_PREFIX,
    keywords_input=p1.KEYWORDS_USER_RAW,
    controversy_system=p1.CONTROVERSY_SYSTEM,
    controversy_prefix=p1.CONTROVERSY_USER_PREFIX,
    controversy_input=p1.CONTROVERSY_USER_RAW,
    impact_system=p2.IMPACT_SYSTEM,
    impact_input=p2.IMPACT_USER_RAW,
    financial_system=p2.FINANCIAL_SYSTEM,
    financial_input=p2.FINANCIAL_USER_RAW,
    pathway_system=p2.PATHWAY_SYSTEM,
    pathway_input=p2.PATHWAY_USER_RAW,
    whitelist_non_financial=dedent(whitelists.WHITELIST_CELL73),
    whitelist_financial=dedent(whitelists.WHITELIST_CELL71),
)
"""기본 글(지금 코드). whitelist 둘은 dedent 한 판 글 — 틀에 끼우면 regulation_system(판) 과 바이트 같다."""

_PART2_SLOTS: Final = (
    p2.COMPANY_SLOT,
    p1.INDUSTRY_SLOT,
    p2.VALUE_CHAIN_SLOT,
    p1.TOPIC_SLOT,
    p2.SUBTOPIC_SLOT,
    p2.SUBTOPIC_DESC_SLOT,
    p2.CONTROVERSY_SLOT,
    p2.REGULATION_SLOT,
)

PLACEHOLDERS: Final[Mapping[str, tuple[str, ...]]] = {
    "regulation_system": (p1.WHITELIST_SLOT,),
    "regulation_prefix": (),
    "regulation_input": (p1.INDUSTRY_SLOT, p1.LOCATION_SLOT, p1.LANGUAGE_SLOT, p1.TOPIC_SLOT, p1.TOPIC_DESC_SLOT),
    "keywords_system": (),
    "keywords_prefix": (),
    "keywords_input": (p1.INDUSTRY_SLOT, p1.DATE_RANGE_SLOT, p1.LANGUAGE_SLOT, p1.TOPICS_SLOT),
    "controversy_system": (),
    "controversy_prefix": (),
    "controversy_input": (
        p1.INDUSTRY_SLOT,
        p1.LOCATION_SLOT,
        p1.LANGUAGE_SLOT,
        p1.KEYWORDS_SLOT,
        p1.TOPIC_SLOT,
        p1.TOPIC_DESC_SLOT,
    ),
    "impact_system": (),
    "impact_input": _PART2_SLOTS,
    "financial_system": (),
    "financial_input": _PART2_SLOTS,
    "pathway_system": (),
    "pathway_input": (p2.FINANCIAL_SLOT,),
    "whitelist_non_financial": (),
    "whitelist_financial": (),
}
"""칸 → 그 칸 기본 글의 자리(기본 글에 나오는 차례)."""

RAW_KEYS: Final = frozenset(
    {"regulation_input", "keywords_input", "controversy_input", "impact_input", "financial_input", "pathway_input"}
)
"""render_raw 로 짓는 칸(날 글 — 끼운 뒤 dedent)."""

REQUIRED: Final[Mapping[str, tuple[str, ...]]] = {
    "regulation_system": (p1.WHITELIST_SLOT,),
    **{key: PLACEHOLDERS[key] for key in sorted(RAW_KEYS)},
}
"""지우면 안 되는 자리(처분 Q5). 그 밖 칸(지시 글·접두·신뢰 출처 목록)은 통째로 바꿔도 된다."""

WHITELIST_KEYS: Final[Mapping[WhitelistName, str]] = {
    "cell71": "whitelist_financial",
    "cell73": "whitelist_non_financial",
}
"""whitelists.whitelist_for 가 고른 판 이름 → 칸."""


def whitelist_text(texts: PromptTexts, name: WhitelistName) -> str:
    """판 이름(whitelist_for 의 고름 그대로)의 신뢰 출처 목록 칸 글."""
    return texts.whitelist_financial if WHITELIST_KEYS[name] == "whitelist_financial" else texts.whitelist_non_financial


def missing_slots(text: str, slots: Sequence[str]) -> list[str]:
    """`slots` 중 `text` 에 나오지 않는 자리(차례 그대로)."""
    return [slot for slot in slots if slot not in text]
