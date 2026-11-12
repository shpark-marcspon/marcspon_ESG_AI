"""엔진이 쓰는 고칠 수 있는 글 열넷(밴드 TR4 — AI 설정 판, MARC-ENT-399). 순수하다.

`PromptTexts` 는 글만 갖는다 — AI 설정의 칸 key 는 모른다(칸 key → 이 칸의 표는 flows/prompt_model_158.py 하나).
`DEFAULT_TEXTS` 는 prompts.py 의 상수에서 짓는다: 기본 글로 지은 요청은 이 밴드 앞과 바이트 같다.

조립 자리(prompts.py 의 키워드 인자로 넘긴다):
    파트 톤 셋           build_company_style_prompt 의 tone(파트로 하나 — 모르는 파트는 일반 톤, R/1919)
    style_rules          build_company_style_prompt 의 덩어리(톤 앞) — 기본 prompts.STYLE_RULES_BLOCK
    subject_fragment     build_company_style_prompt 의 덩어리(톤 뒤) — 기본 prompts.SUBJECT_FRAGMENT_RULES_BLOCK
    terminology_note     page_system_prompt(회사 문체와 고른 문체 사이)
    style_a·style_b      page_system_prompt 의 고른 문체(pipeline.style_prompts)
    table_rules          table_batch_system · polish → polish_system · editorial_qa → editorial_qa_system
    review               검수 system 그대로(review.py)
    autofix·autofix_korean   틀 — `{page_num}` 을 쪽 번호로 바꾼 글이 system(코랩은 f-문자열, R/6665·6755)
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, cast

from esgapi.translation.engines.colab_158 import prompts

PAGE_NUM_SLOT: Final = "{page_num}"
"""자동 수정 틀 둘의 쪽 번호 자리표."""


@dataclass(frozen=True)
class PromptTexts:
    ceo_message_tone: str
    story_tone: str
    general_tone: str
    style_a: str
    style_b: str
    style_rules: str
    subject_fragment_rules: str
    terminology_note: str
    table_rules: str
    polish: str
    editorial_qa: str
    review: str
    autofix: str
    autofix_korean: str

    def tone_for(self, part: str) -> str:
        """`TONE_PRESETS.get(part, GENERAL_TONE)` 의 자리(R/1919)."""
        return {"ceo_message": self.ceo_message_tone, "story": self.story_tone}.get(part, self.general_tone)

    def company_style(
        self,
        part: str,
        company_name: str,
        preferred_subject: str,
        industry_standards: str,
        peer_group_style_prompt: str | None,
    ) -> str:
        return prompts.build_company_style_prompt(
            part,
            company_name,
            preferred_subject,
            industry_standards,
            peer_group_style_prompt,
            tone=self.tone_for(part),
            style_rules=self.style_rules,
            subject_fragment_rules=self.subject_fragment_rules,
        )

    def page_system(self, company_style_prompt: str, style_prompt: str, industry_standards: str) -> str:
        return prompts.page_system_prompt(
            company_style_prompt, style_prompt, industry_standards, terminology_note=self.terminology_note
        )

    def table_batch_system(self, system_prompt: str) -> str:
        return prompts.table_batch_system(system_prompt, table_rules=self.table_rules)

    def polish_system(self, system_prompt: str) -> str:
        return prompts.polish_system(system_prompt, polish=self.polish)

    def editorial_qa_system(self, system_prompt: str) -> str:
        return prompts.editorial_qa_system(system_prompt, editorial_qa=self.editorial_qa)

    def autofix_system(self, page_num: int) -> str:
        return self.autofix.replace(PAGE_NUM_SLOT, str(page_num))

    def autofix_korean_system(self, page_num: int) -> str:
        return self.autofix_korean.replace(PAGE_NUM_SLOT, str(page_num))


def _template(system: Callable[[int], str]) -> str:
    """f-문자열 함수(쪽 번호 하나를 받는)에 자리표 글을 넘겨 틀을 얻는다 — 글을 두 벌 두지 않는다. 틀이 함수와 같은
    글을 내는지는 tests/engines/colab_158/test_texts.py 가 쪽 번호 여럿으로 잰다."""
    return system(cast("int", PAGE_NUM_SLOT))


DEFAULT_TEXTS: Final = PromptTexts(
    ceo_message_tone=prompts.CEO_MESSAGE_TONE,
    story_tone=prompts.STORY_TONE,
    general_tone=prompts.GENERAL_TONE,
    style_a=prompts.STYLE_A_PROMPT,
    style_b=prompts.STYLE_B_PROMPT,
    style_rules=prompts.STYLE_RULES_BLOCK,
    subject_fragment_rules=prompts.SUBJECT_FRAGMENT_RULES_BLOCK,
    terminology_note=prompts.TERMINOLOGY_NOTE,
    table_rules=prompts.TABLE_TRANSLATION_RULES,
    polish=prompts.BILINGUAL_EDITORIAL_POLISH_PROMPT,
    editorial_qa=prompts.GENERIC_EDITORIAL_QA_PROMPT,
    review=prompts.QA_SYSTEM_PROMPT,
    autofix=_template(prompts.autofix_system),
    autofix_korean=_template(prompts.autofix_korean_system),
)
"""코드 글(이 밴드 앞의 엔진 그대로)."""
