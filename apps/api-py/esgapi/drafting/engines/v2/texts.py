"""v2 의 프롬프트 글(§2-0 ③ 가). 칸 넷의 꼴(PromptTexts)은 v1 그대로다 — map 칸 둘은 v1 글의 「쪽」을 「페이지」로
바꾼 글(map_system 은 거기에 요구 내용 대조 한 줄 — RPQ1, map_user 는 머리·자리 글자만 다름 — RPA4), draft 칸 둘은 새 글
(블록 표지 재료). 자리 넷 중 재료 자리는 v2 자기 슬롯 `{페이지 글}`(PAGES_SLOT — v1 슬롯과 글자가 다르다)이고 끼움은
engines/v2/prompts 다(v1 끼움은 이 슬롯을 모른다). 표지 뜻·답 꼴의 규칙(MARKER_RULES)과 출력 언어·문체 규칙
(WRITING_RULES — RPQ1)은 칸 밖 고정 꼬리로 흐름이 draft system 뒤에 붙인다(AI 설정 판 RPA1 이 칸을 갈음해도 남는다).
글의 지문은 prompts/README.md 「v2」 표."""

from typing import Final

from esgapi.drafting.engines.v1.texts import OUTLINE_SLOT, REQUIREMENT_SLOT, TITLE_SLOT, PromptTexts

__all__ = [
    "DEFAULT_TEXTS",
    "MARKER_RULES",
    "OUTLINE_SLOT",
    "PAGES_SLOT",
    "REQUIREMENT_SLOT",
    "TEXTS_VERSION",
    "TITLE_SLOT",
    "WRITING_RULES",
    "PromptTexts",
    "draft_system",
]

TEXTS_VERSION: Final = "drafting-texts@3"
"""글 판(versions 열쇠 texts). RPQ1 에서 처음 단 판(@1) — 열쇠 없는 실행은 RPQ1 앞 글. 칸 넷·MARKER_RULES·
WRITING_RULES 중 하나라도 바꾸면 올린다(핀 시험 tests/engines/v2/test_texts.py TEXTS_PINS).
RPA4: 「쪽」→「페이지」·자리 `{페이지 글}` · map 대조 줄을 세움(1페이지 인사말의 목표 문단 — 경계 ③)(@2).
RPS2: 표 숫자는 표 id·행으로(562 A)(@3)."""

PAGES_SLOT: Final = "{페이지 글}"
"""v2 의 재료 자리(v2 자기 슬롯 — v1 PAGES_SLOT 과 글자가 다르다). 끼움은 engines/v2/prompts 만 한다."""

DEFAULT_TEXTS: Final = PromptTexts(
    map_system=(
        "너는 지속가능경영 보고서 편집 도우미다. 전년도 보고서의 페이지 글과 올해 보고서의 목차 잎 목록을 받는다.\n"
        "각 페이지마다 그 페이지 내용이 쓰일 만한 목차 잎의 key 를 고른다. 관련된 잎이 없으면 빈 목록을 준다.\n"
        "목록에 없는 key 는 쓰지 않는다. 받은 페이지 번호만 답한다.\n"
        "한 페이지를 여러 잎에 달 수 있다. 페이지 전체 주제가 잎과 달라도, 한 문단이라도 잎의 요구 내용에 적힌 "
        "항목(목표·계획·수치 등)을 다루면 그 잎을 고른다. 인사말·보고서 개요 페이지 안의 목표·수치 문단도 그렇다. "
        "빈 목록은 그런 문단이 하나도 없을 때만 준다.\n"
        "JSON 으로만 답한다."
    ),
    map_user=f"[목차 잎 — key | 제목 경로 | 요구 내용]\n{OUTLINE_SLOT}\n\n[페이지 글]\n{PAGES_SLOT}",
    draft_system=(
        "너는 지속가능경영 보고서 초안 작성 도우미다. 목차 잎 하나와 전년도 보고서에서 뽑은 자료를 받는다.\n"
        "준 자료에 실제로 적힌 사실만으로 개조식 bullet 을 쓴다. bullet 마다 근거가 된 블록과 문장을 단다.\n"
        "자료에 없는 수치·성과·연도는 지어내지 않는다. 근거가 없으면 그 bullet 은 쓰지 않는다. JSON 으로만 답한다."
    ),
    draft_user=f"[목차 잎] {TITLE_SLOT}\n[요구 내용] {REQUIREMENT_SLOT}\n\n[자료]\n{PAGES_SLOT}",
)

MARKER_RULES: Final = (
    "[자료 표지]\n"
    "- `[PAGE n]` 줄은 페이지 머리다. `[B <id>]` 는 글 블록, `[T <id>]` 는 표 하나의 머리다.\n"
    "- 글 블록 안의 `⟨n⟩` 은 그 뒤 문장의 번호이고, 표 아래 줄 머리의 `⟨n⟩` 은 그 행의 번호다. 번호는 0부터다.\n"
    "- 표지가 없는 블록(제목)은 문장 번호 없이 댄다.\n"
    '- 근거는 sources 에 {"block": "<블록이나 표의 id>", "s": <문장이나 행 번호, 없으면 null>} 로 단다.\n'
    "- 자료에 표지로 나온 id·번호만 쓴다. 표지에 없는 id·번호를 지어내지 않는다.\n"
    "- 표에서 가져온 숫자는 표 위 제목·라벨 블록이 아니라 그 표의 `[T <id>]` 와 행 번호로 댄다."
)

WRITING_RULES: Final = (
    "[글 규칙]\n"
    "- bullet 은 늘 한국어로 쓴다. 자료가 영어 등 다른 말이어도 같다.\n"
    "- 수·단위·연도·고유명사(회사·사업장·인증·기관 이름)는 자료 그대로 둔다. 그 밖의 영문은 「Scope 1」·「tCO2eq」·"
    "「ISO 45001」 처럼 널리 쓰는 표준 이름일 때만 그대로 둔다.\n"
    "- 자료 문장을 다른 말 그대로 옮겨 붙이지 않고 한국어 개조식으로 다시 쓴다. 전문 용어는 뜻을 살려 옮긴다(낱말 대 "
    "낱말로 옮겨 뜻이 바뀌지 않게).\n"
    "- 모든 bullet 끝맺음은 개조식 명사형 「~함」·「~임」(「~됨」·「~있음」 포함)으로 맞춘다. "
    "「~했다」·「~이다」·「~합니다」 로 끝내지 않는다.\n"
    "- 한 bullet 에 사실 하나만 쓴다."
)


def draft_system(system: str) -> str:
    """draft system 칸 글 뒤에 고정 꼬리 둘(표지 규칙 → 글 규칙, 빈 줄 하나씩으로 이음)."""
    return f"{system}\n\n{MARKER_RULES}\n\n{WRITING_RULES}"
