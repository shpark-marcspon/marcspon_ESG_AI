"""남은 한국어(MARC-ISSUE-212 의 1)와 검수 꼴 오류(MARC-ISSUE-196 L2)·폭 0 글자(L4).

- 쪽이 한국어 잔존으로 실패하면 조각의 `remaining_korean` = 잔존 셈의 줄 전부(메시지는 코랩대로 앞 10줄), `error` 글은
  코랩 메시지 그대로. 다른 예외로 실패한 조각·번역된 조각은 빈 것.
- 검수 이슈 JSON 의 값 꼴이 틀리면 셀 65 는 그대로 멈춘다(`call_failed`, 뒤 쪽 not_run) — 글 앞머리 `shape: ` 로 호출
  실패(`LlmCallFailed: …`)와 가른다.
"""

from esgapi.translation.engines.colab_158.gates import collect_untranslated_korean_lines
from esgapi.translation.engines.colab_158.glossary import normalize_space
from esgapi.translation.engines.colab_158.translate import KoreanRemaining
from esgapi.translation.tests.engines.colab_158.support import fail, make_input, ok, run_flow

NO_ISSUES = ok("[]")
KOREAN_LINES = [f"가상 남은 국문 {i}" for i in range(12)]
LEFT = "[BLOCK 1]\n" + "\n".join(KOREAN_LINES)
SRC = "[PAGE 1]\n[BLOCK 1]\n가상 원문"


def test_a_korean_failure_keeps_every_remaining_line_and_the_colab_message() -> None:
    flow = run_flow(make_input(SRC, autofix=False), [ok(LEFT), ok(LEFT), ok(LEFT), NO_ISSUES])
    (fragment,) = flow.run.variants[0].fragments
    remaining = collect_untranslated_korean_lines(LEFT)
    assert len(remaining) == 12
    assert fragment.status == "error"
    assert fragment.remaining_korean == tuple(remaining)
    assert fragment.error == (
        "[치명] 번역 결과에 한국어가 남아 있어 중단합니다.\n"
        "아래 문구를 GLOSSARY 또는 FINAL_GLOSSARY에 추가한 뒤 재실행하세요.\n"
        + "\n".join(f"- {x}" for x in remaining[:10])
    )


def test_korean_remaining_is_still_the_colab_value_error() -> None:
    e = KoreanRemaining("글", ["가"])
    assert isinstance(e, ValueError)
    assert (str(e), e.remaining) == ("글", ("가",))


def test_other_failures_and_translated_pages_carry_no_remaining_lines() -> None:
    two = SRC + "\n[PAGE 2]\n[BLOCK 1]\n가상 둘"
    flow = run_flow(make_input(two, autofix=False), [ok("[BLOCK 1]\nVirtual"), fail(), NO_ISSUES, NO_ISSUES])
    first, second = flow.run.variants[0].fragments
    assert (first.status, first.remaining_korean) == ("translated", ())
    assert (second.status, second.remaining_korean) == ("error", ())
    assert second.error == "section: provider_error"


def test_a_wrong_issue_shape_stops_the_review_with_the_shape_prefix() -> None:
    """이슈 목록 자리에 수 → 코랩은 TypeError 로 셀 65 가 멈춘다. 상태·멈춤은 그대로, 글만 `shape: ` 로 시작."""
    two = SRC + "\n[PAGE 2]\n[BLOCK 1]\n가상 둘"
    replies = [ok("[BLOCK 1]\nVirtual one"), ok("[BLOCK 1]\nVirtual two"), ok("7")]
    flow = run_flow(make_input(two, autofix=False), replies)
    first, second = flow.run.variants[0].pages
    assert (first.status, second.status) == ("call_failed", "not_run")
    assert first.message == "shape: TypeError: 'int' object is not iterable"


def test_a_wrong_field_shape_is_a_shape_error_too() -> None:
    replies = [ok("[BLOCK 1]\nVirtual one"), ok('[{"issue_type": 3}]')]
    flow = run_flow(make_input(SRC, autofix=False), replies)
    (page,) = flow.run.variants[0].pages
    assert page.status == "call_failed"
    assert page.message == "shape: AttributeError: 'int' object has no attribute 'strip'"


def test_a_failed_review_call_keeps_its_old_message() -> None:
    flow = run_flow(make_input(SRC, autofix=False), [ok("[BLOCK 1]\nVirtual one"), fail()])
    (page,) = flow.run.variants[0].pages
    assert page.message == "LlmCallFailed: review: provider_error"


def test_zero_width_characters_are_still_removed() -> None:
    """L4: 날글자를 이스케이프로 — 값은 같다."""
    assert normalize_space("a​b‌c‍d") == "abcd"
