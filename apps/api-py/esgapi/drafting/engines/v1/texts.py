"""프롬프트 글 칸 넷(처분 ③ 가) — 글의 정본은 이 파일이고 `prompts/<이름>/1.md` 는 봉투다. AI 설정 판(RPA1)은 이 칸을
갈음할 뿐 엔진·흐름은 그대로다. 자리(`{…}`)는 prompts.render 가 한 번에 끼운다(끼운 값을 다시 훑지 않는다)."""

from dataclasses import dataclass
from typing import Final

OUTLINE_SLOT: Final = "{목차}"
PAGES_SLOT: Final = "{쪽 글}"
TITLE_SLOT: Final = "{제목 경로}"
REQUIREMENT_SLOT: Final = "{요구 내용}"


@dataclass(frozen=True, slots=True, kw_only=True)
class PromptTexts:
    map_system: str
    map_user: str
    draft_system: str
    draft_user: str


DEFAULT_TEXTS: Final = PromptTexts(
    map_system=(
        "너는 지속가능경영 보고서 편집 도우미다. 전년도 보고서의 쪽 글과 올해 보고서의 목차 잎 목록을 받는다.\n"
        "각 쪽마다 그 쪽 내용이 쓰일 만한 목차 잎의 key 를 고른다. 관련된 잎이 없으면 빈 목록을 준다.\n"
        "목록에 없는 key 는 쓰지 않는다. 받은 쪽 번호만 답한다. JSON 으로만 답한다."
    ),
    map_user=f"[목차 잎 — key | 제목 경로 | 요구 내용]\n{OUTLINE_SLOT}\n\n[쪽 글]\n{PAGES_SLOT}",
    draft_system=(
        "너는 지속가능경영 보고서 초안 작성 도우미다. 목차 잎 하나와 전년도 보고서의 쪽 글 몇 개를 받는다.\n"
        "준 쪽 글에 실제로 적힌 사실만으로 개조식 bullet 을 쓴다. bullet 마다 근거가 된 쪽 번호를 단다.\n"
        "쪽 글에 없는 수치·성과·연도는 지어내지 않는다. 근거가 없으면 그 bullet 은 쓰지 않는다. JSON 으로만 답한다."
    ),
    draft_user=f"[목차 잎] {TITLE_SLOT}\n[요구 내용] {REQUIREMENT_SLOT}\n\n[쪽 글]\n{PAGES_SLOT}",
)
