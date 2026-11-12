"""검토 고침의 AI 견줌·strip 전 상한(actions/review._checked_edits — 밴드 GRV1, MARC-ISSUE-282). 순수 층(DB 없음).

잰다: 앞뒤 공백·줄바꿈·빈 항목이 섞인 AI 값을 그대로 보내면 고침 0 · 진짜로 고치면 다듬은 값이 남음 · AI 값이 None·꼴이
다르면 날것끼리 견줌 · strip 전 항목 수·한 줄 길이·수정 방향 길이가 넘으면 InvalidReview(기존 상한 문구) · 경계
값은 통과. AI 항목은 지어낸 것이다.
"""

from typing import Any

from esgapi.greenwash.contracts.review_shapes import GreenwashReviewEditIn
from esgapi.greenwash.models import (
    EDIT_FIX_MAX_CHARS,
    EDIT_FIX_RAW_MAX_CHARS,
    EDIT_REASON_MAX_CHARS,
    EDIT_REASON_RAW_MAX_CHARS,
    EDIT_REASONS_MAX_LINES,
    EDIT_REASONS_RAW_MAX_LINES,
)
from esgapi.greenwash.service.actions.review import InvalidReview, _checked_edits  # pyright: ignore[reportPrivateUsage]

MESSY: dict[str, Any] = {
    "level": "Mid",
    "reasonBullets": ["  친환경이라는 말의 근거가 없어요 ", "", "   ", "- 비교 기준이 빠졌어요\n"],
    "fixParagraph": "\n  감축 실적과 기준 연도를 함께 적어 주세요.  \n",
}


def edit(
    reasons: list[str] | None = None, fix: str | None = None, level: Any = None, index: int = 0
) -> GreenwashReviewEditIn:
    return {"itemIndex": index, "level": level, "reasonBullets": reasons, "fixParagraph": fix}


def test_messy_ai_values_sent_back_untouched_are_no_edit() -> None:
    got = _checked_edits([edit(list(MESSY["reasonBullets"]), MESSY["fixParagraph"], "Mid")], [MESSY])
    assert got == {}


def test_each_column_alone_is_no_edit() -> None:
    assert _checked_edits([edit(reasons=list(MESSY["reasonBullets"]))], [MESSY]) == {}
    assert _checked_edits([edit(fix=MESSY["fixParagraph"])], [MESSY]) == {}


def test_human_tidied_value_equal_to_tidied_ai_is_no_edit() -> None:
    reasons = ["친환경이라는 말의 근거가 없어요", "- 비교 기준이 빠졌어요"]
    assert _checked_edits([edit(reasons, "감축 실적과 기준 연도를 함께 적어 주세요.")], [MESSY]) == {}


def test_real_change_keeps_the_tidied_human_value() -> None:
    got = _checked_edits([edit([" 바꾼 사유 ", ""], " 바꾼 방향 ")], [MESSY])
    assert got == {0: (None, ["바꾼 사유"], "바꾼 방향")}


def test_ai_value_missing_or_odd_shape_compares_raw() -> None:
    odd: dict[str, Any] = {"level": "Low", "reasonBullets": None, "fixParagraph": 7}
    got = _checked_edits([edit(["사유"], "방향")], [odd])
    assert got == {0: (None, ["사유"], "방향")}


def test_too_many_raw_reason_items_is_refused_with_the_line_limit_message() -> None:
    raw = ["사유"] + [""] * EDIT_REASONS_RAW_MAX_LINES
    got = _checked_edits([edit(raw)], [MESSY])
    assert got == InvalidReview(f"판정 사유는 {EDIT_REASONS_MAX_LINES}줄까지 쓸 수 있어요")
    assert _checked_edits([edit(raw[:EDIT_REASONS_RAW_MAX_LINES])], [MESSY]) == {0: (None, ["사유"], None)}


def test_too_long_raw_reason_line_is_refused_with_the_char_limit_message() -> None:
    padded = "사유" + " " * (EDIT_REASON_RAW_MAX_CHARS - 1)
    got = _checked_edits([edit([padded])], [MESSY])
    assert got == InvalidReview(f"판정 사유는 한 줄에 {EDIT_REASON_MAX_CHARS}자까지 쓸 수 있어요")
    assert _checked_edits([edit([padded[:-1]])], [MESSY]) == {0: (None, ["사유"], None)}


def test_too_long_raw_fix_is_refused_with_the_fix_limit_message() -> None:
    padded = "방향" + "\n" * (EDIT_FIX_RAW_MAX_CHARS - 1)
    got = _checked_edits([edit(fix=padded)], [MESSY])
    assert got == InvalidReview(f"수정 방향은 {EDIT_FIX_MAX_CHARS}자까지 쓸 수 있어요")
    assert _checked_edits([edit(fix=padded[:-1])], [MESSY]) == {0: (None, None, "방향")}
