"""흐름(발주서 §3 S2·S8): 대본(심은 모의 답)으로 `pipeline.run` 을 돌려 호출 열 `(자리, max_tokens, 모델, 경로)` 과
쪽마다의 글이 손으로 적은 기대값과 같은가. 기대값은 러너가 코랩 줄(R/)을 읽고 적은 것이다 —
코랩과의 바이트 대조는 esg-lab TR1-o.

실제 설정 + 모의 공급사 둘(anthropic·openai — 개정 1 B3), 다리는 tools/llm_bridge.py. 실호출 0. 심은 답은 support 의
ok·cut·refuse·fail(키워드 인자로 지은 Completed·Truncated·Refusal·ProviderError).
"""

import json
import re
from collections.abc import Sequence

import pytest

from esgapi.core.llm.types import ProviderResponse
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.glossary import build_glossary_text
from esgapi.translation.engines.colab_158.records import AutofixStop, PageReview, Rejection
from esgapi.translation.tests.engines.colab_158.support import (
    LIGHT,
    LIGHT_MODEL,
    STANDARD,
    STANDARD_MODEL,
    cut,
    fail,
    make_input,
    ok,
    refuse,
    run_flow,
)

SECTION = ("section", 4096, LIGHT_MODEL, LIGHT)
POLISH = ("polish", 4096, LIGHT_MODEL, LIGHT)
QA = ("editorial-qa", 4096, LIGHT_MODEL, LIGHT)
REVIEW = ("review", 4096, LIGHT_MODEL, LIGHT)
AUTOFIX = ("autofix", 4096, LIGHT_MODEL, LIGHT)
AUTOFIX_KO = ("autofix-korean", 4096, LIGHT_MODEL, LIGHT)
KO_REPAIR = ("korean-repair", 4096, LIGHT_MODEL, LIGHT)
BATCH = ("table-batch", 8192, LIGHT_MODEL, LIGHT)
CELL = ("cell", 1024, LIGHT_MODEL, LIGHT)

SIMPLE = "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."
SIMPLE_EN = "[BLOCK 1]\nVirtual Title\nVirtual body."
NO_ISSUES = ok("[]")
NO_TERMS = "(No relevant glossary terms for this source text.)"
"""쪽에 나온 용어집 key 가 없을 때의 용어집 글(R/487-498)."""


def j(value: object) -> str:
    return json.dumps(value, ensure_ascii=False)


def plain_len(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


# 쪽 단위 윤문·범용 QA 를 돌리는 쪽(R/3333·2621): 구획 번역은 공백 뺀 115자(< 120 — 구획 윤문 안 돎, R/2499), 쪽 글은
# [PAGE 1] 7자를 더해 122자(≥ 120 — 쪽 윤문·QA 돎). 대문자 낱말 0 이라 제목·본문 가르기(R/2405-2460)에 걸리지 않는다.
LONG_SRC = "[PAGE 1]\n[BLOCK 1]\n가상 긴 본문입니다."
LONG_EN = (
    "[BLOCK 1]\nvirtual words keep going here with plain lowercase text and nothing that looks like a heading at all ok"
    " abcdefghij klmnopqrst uv"
)
PAGE_OUT = "[PAGE 1]\n\n" + LONG_EN
POLISHED = PAGE_OUT.replace("virtual", "polishd")  # 같은 길이(쪽 QA 가 돈다)
REVISED = PAGE_OUT.replace("virtual", "revised")


def test_the_long_page_fixture_sits_between_the_two_gates() -> None:
    assert (plain_len(LONG_EN), plain_len(PAGE_OUT)) == (115, 122)


def qa_reply(
    score: object = 99, issues: Sequence[object] = (), critical: bool = False, revised: str = REVISED
) -> ProviderResponse:
    """범용 QA 의 답(R/1419-1431 의 꼴): quality_score·has_critical_issue·issues·revised_text."""
    return ok(
        j({"quality_score": score, "has_critical_issue": critical, "issues": list(issues), "revised_text": revised})
    )


# ── 흐름 경우 ──


def test_a_short_general_page_is_one_section_call_and_one_review() -> None:
    """R/2340(구획) — 115자 미만이라 윤문 0(R/2499), 쪽 QA 는 건너뜀 로그만(R/2621-2633). 검수 R/5325, 자동수정은 이슈·
    한국어 0 이라 그 쪽을 건너뜀(R/6873-6876)."""
    flow = run_flow(make_input(SIMPLE), [ok(SIMPLE_EN), NO_ISSUES])
    assert flow.rows == [SECTION, REVIEW]
    (variant,) = flow.run.variants
    assert variant.label == "single"
    # 셀 49 의 파일: 조각을 빈 줄 하나로 이음(쪽 글 = "[PAGE 1]" 구획 + 빈 줄 + BLOCK 구획, R/3329)
    assert variant.translated_text == "[PAGE 1]\n\n[BLOCK 1]\nVirtual Title\nVirtual body."
    # 셀 52: BLOCK 의 첫 글 줄에 원문 첫 국문 줄(R/3846-3888)
    assert variant.bilingual_text == "[PAGE 1]\n[BLOCK 1]\nVirtual Title (가상 제목)\nVirtual body."
    (fragment,) = variant.fragments
    assert (fragment.page_num, fragment.status, fragment.error) == (1, "translated", None)
    assert fragment.editorial_qa is not None
    assert (fragment.editorial_qa.reason, fragment.editorial_qa.ran) == ("skipped_table_or_short_text", False)
    assert variant.pages == [
        PageReview(
            1,
            "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body.",
            "[PAGE 1]\n[BLOCK 1]\nVirtual Title (가상 제목)\nVirtual body.",
            "reviewed",
            (),
            None,
            (),
        )
    ]
    assert variant.autofix.status == "done"
    assert variant.autofix.pages == ()
    # 셀 67 은 쪽 map 을 strip 해 이어 쓴다(R/6800-6804) — [PAGE 1] 뒤 빈 줄이 없어진다
    assert variant.autofix.translated_text == "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body."
    assert variant.autofix.bilingual_text == variant.bilingual_text
    assert flow.run.warnings == []
    assert flow.anthropic.calls == []


def test_the_section_and_review_calls_carry_the_colab_prompts() -> None:
    """★c: 검수 system 은 QA_SYSTEM_PROMPT 그대로(번역 system 조립을 거치지 않음, R/5328). 번역 system 은 쪽 system."""
    flow = run_flow(make_input(SIMPLE), [ok(SIMPLE_EN), NO_ISSUES])
    section, review = flow.calls
    company = prompts.build_company_style_prompt("general", "가상고객사", "가상 업종", "GRI", None)
    assert section.system == prompts.page_system_prompt(company, prompts.STYLE_B_PROMPT, "GRI")
    assert build_glossary_text({}) == NO_TERMS
    assert section.user == prompts.section_user(NO_TERMS, "[BLOCK 1]\n가상 제목\n가상 본문입니다.", 1)
    assert review.system == prompts.QA_SYSTEM_PROMPT
    assert "[Variant]\nStyle single\n" in review.user
    assert "[Korean source - PAGE 1]\n[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다.\n" in review.user
    # 검수 모델 입력은 병기를 걷은 글(R/5268-5269), 병기 국문은 힌트로(R/5270-5275)
    assert "[English translation for QA - PAGE 1]\n[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body.\n" in review.user
    assert "- 가상 제목\n" in review.user


def test_a_25_cell_table_goes_in_two_batches_of_24_and_1() -> None:
    """R/2282 묶음 24. 머리 칸 5 + 본문 칸 20 = 국문 칸 25 → 묶음 둘. 표 쪽은 쪽 윤문·QA 를 건너뜀(R/2554-2575)."""
    rows = ["| " + " | ".join(f"머리{c}" for c in range(5)) + " |", "| --- | --- | --- | --- | --- |"]
    rows += ["| " + " | ".join(f"칸{r}{c}" for c in range(5)) + " |" for r in range(4)]
    src = "[PAGE 1]\n[TABLE 1]\n" + "\n".join(rows)
    ids = [f"T0_H{c}" for c in range(5)] + [f"T0_R{r}C{c}" for r in range(4) for c in range(5)]
    first = ok(j({"items": [{"id": i, "translation": f"E{i}"} for i in ids[:24]]}))
    second = ok(j({"items": [{"id": ids[24], "translation": f"E{ids[24]}"}]}))
    flow = run_flow(make_input(src), [first, second, NO_ISSUES])
    assert flow.rows == [BATCH, BATCH, REVIEW]
    batch_one = json.loads(flow.calls[0].user.split("[Items to translate]\n")[1].split("\n\nTranslate each")[0])
    assert [item["id"] for item in batch_one["items"]] == ids[:24]
    assert flow.calls[0].system.endswith(prompts.TABLE_TRANSLATION_RULES)
    expected = ["| " + " | ".join(f"ET0_H{c}" for c in range(5)) + " |", "| --- | --- | --- | --- | --- |"]
    expected += ["| " + " | ".join(f"ET0_R{r}C{c}" for c in range(5)) + " |" for r in range(4)]
    assert flow.run.variants[0].translated_text == "[PAGE 1]\n\n[TABLE 1]\n" + "\n".join(expected)
    (fragment,) = flow.run.variants[0].fragments
    assert fragment.editorial_qa is not None and fragment.editorial_qa.reason == "skipped_table_or_short_text"


def test_a_story_page_runs_section_polish_page_polish_and_the_qa_gate() -> None:
    """story: 구획 115자 이상이면 구획 윤문(R/2499), 쪽 122자 이상이면 쪽 윤문(R/3333)과 QA(R/2659). 톤은 STORY_TONE."""
    flow = run_flow(
        make_input(LONG_SRC, part="story"),
        [ok(LONG_EN), ok(POLISHED), qa_reply(98, revised=REVISED), NO_ISSUES],
    )
    assert flow.rows == [SECTION, POLISH, QA, REVIEW]
    assert prompts.STORY_TONE.strip() in flow.calls[0].system
    assert flow.calls[1].system == prompts.polish_system(flow.calls[0].system)
    assert flow.calls[1].user == prompts.polish_user(NO_TERMS, LONG_SRC, PAGE_OUT, 1)
    assert flow.calls[2].system == prompts.editorial_qa_system(flow.calls[0].system)
    assert flow.calls[2].user == prompts.editorial_qa_user(NO_TERMS, LONG_SRC, POLISHED, 1)
    # 점수 98·이슈 0 → 적용 안 함(R/2735-2746) — 쪽 글은 윤문본
    assert flow.run.variants[0].translated_text == POLISHED
    log = flow.run.variants[0].fragments[0].editorial_qa
    assert log is not None
    assert (log.reason, log.quality_score, log.applied, log.ran) == ("score_and_issues_acceptable", 98, False, True)


def test_a_section_of_120_chars_gets_its_own_polish_first() -> None:
    """R/2499: 구획 번역이 공백 뺀 120자 이상이면 구획 윤문. 쪽은 그 뒤 다시 쪽 윤문·QA."""
    section = LONG_EN + " moreX"
    assert plain_len(section) == 120
    polished_section = section.replace("virtual", "virtualx")
    flow = run_flow(
        make_input(LONG_SRC),
        [ok(section), ok(polished_section), ok("[PAGE 1]\n\n" + polished_section), qa_reply(99), NO_ISSUES],
    )
    assert flow.rows == [SECTION, POLISH, POLISH, QA, REVIEW]
    assert flow.calls[1].user == prompts.polish_user(NO_TERMS, "[BLOCK 1]\n가상 긴 본문입니다.", section, 1)


def test_ceo_translates_on_the_standard_route_and_reviews_on_the_light_one() -> None:
    """R/2110-2112 의 자리: CEO 는 경로 standard-openai-41(gpt-4.1 — MARC-ENT-402), anthropic 0. CEO 는 윤문의 최소
    길이를 보지 않아(R/2499) "[PAGE 1]" 구획에도 윤문을 부른다. 검수는 light-openai-41 고정(R/5326 의 자리 — W3)."""
    ceo_polish = ("polish", 4096, STANDARD_MODEL, STANDARD)
    ceo_section = ("section", 4096, STANDARD_MODEL, STANDARD)
    flow = run_flow(
        make_input(SIMPLE, part="ceo_message"),
        [ok("[PAGE 1]"), ok(SIMPLE_EN), ok("[BLOCK 1]\nVirtual Title\nVirtual polished body."), NO_ISSUES],
    )
    assert flow.rows == [ceo_polish, ceo_section, ceo_polish, REVIEW]
    assert flow.calls[0].user == prompts.polish_user(NO_TERMS, "[PAGE 1]", "[PAGE 1]", 1)
    assert prompts.CEO_MESSAGE_TONE.strip() in flow.calls[1].system
    assert flow.anthropic.calls == []
    assert flow.run.variants[0].translated_text == "[PAGE 1]\n\n[BLOCK 1]\nVirtual Title\nVirtual polished body."


def test_ceo_page_limit_six_runs_and_seven_is_rejected_before_any_call() -> None:
    """R/3442-3457: 쪽 수 > 6 이면 eval_js 경고 + SystemExit — 우리는 rejection(ceo_page_limit), 호출 0."""
    six = "\n".join(f"[PAGE {n}]\n[BLOCK 1]\n가{n}" for n in range(1, 7))
    replies: list[ProviderResponse] = []
    for n in range(1, 7):
        replies += [ok(f"[PAGE {n}]"), ok(f"[BLOCK 1]\nE{n}"), ok(f"[BLOCK 1]\nE{n}")]
    replies += [NO_ISSUES] * 6
    flow = run_flow(make_input(six, part="ceo_message"), replies)
    assert (
        flow.rows
        == [
            ("polish", 4096, STANDARD_MODEL, STANDARD),
            ("section", 4096, STANDARD_MODEL, STANDARD),
            ("polish", 4096, STANDARD_MODEL, STANDARD),
        ]
        * 6
        + [REVIEW] * 6
    )
    assert flow.run.rejection is None
    assert flow.anthropic.calls == []

    seven = six + "\n[PAGE 7]\n[BLOCK 1]\n가7"
    rejected = run_flow(make_input(seven, part="ceo_message"), [])
    assert rejected.calls == []
    assert rejected.run.rejection == Rejection(
        kind="ceo_page_limit", message="CEO 페이지 수 초과로 실행 중단", page_count=7, limit=6
    )
    assert rejected.run.variants == []
    # 한도는 CEO 파트에만(R/3442)
    general = run_flow(make_input(seven), [ok(f"[BLOCK 1]\nE{n}") for n in range(1, 8)] + [NO_ISSUES] * 7)
    assert general.run.rejection is None


def test_a_b_translates_each_page_twice_and_reviews_and_fixes_a_then_b() -> None:
    """R/3362-3367(A 다음 B, 쪽마다), 셀 65·67 은 A 를 다 돌고 B(R/6190·6833)."""
    two = SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n둘째 쪽"
    replies = [ok("[BLOCK 1]\nA1"), ok("[BLOCK 1]\nB1"), ok("[BLOCK 1]\nA2"), ok("[BLOCK 1]\nB2")] + [NO_ISSUES] * 4
    flow = run_flow(make_input(two, compare_ab=True), replies)
    assert flow.rows == [SECTION] * 4 + [REVIEW] * 4
    assert prompts.STYLE_A_PROMPT.strip() in flow.calls[0].system
    assert prompts.STYLE_B_PROMPT.strip() in flow.calls[1].system
    assert [c.user.split("[Variant]\n")[1].split("\n")[0] for c in flow.calls[4:]] == ["Style A"] * 2 + ["Style B"] * 2
    a, b = flow.run.variants
    assert (a.label, b.label) == ("A", "B")
    assert a.translated_text == "[PAGE 1]\n\n[BLOCK 1]\nA1\n\n[PAGE 2]\n\n[BLOCK 1]\nA2"
    assert b.translated_text == "[PAGE 1]\n\n[BLOCK 1]\nB1\n\n[PAGE 2]\n\n[BLOCK 1]\nB2"
    assert (a.autofix.status, b.autofix.status) == ("done", "done")


def test_single_style_a_uses_style_a() -> None:
    """R/3370-3379 SINGLE_STYLE."""
    flow = run_flow(make_input(SIMPLE, single="A"), [ok(SIMPLE_EN), NO_ISSUES])
    assert prompts.STYLE_A_PROMPT.strip() in flow.calls[0].system
    assert prompts.STYLE_B_PROMPT.strip() not in flow.calls[0].system


def test_polish_that_moves_tags_or_adds_korean_is_thrown_away() -> None:
    """R/2537-2546: 윤문이 구조 태그를 바꾸면(쪽 윤문이 [PAGE 1] 뒤 빈 줄을 지움 — 시그니처가 이웃 빈 줄을 품는다)
    원 번역 유지. QA 수정본이 한국어를 늘리면 원 번역 유지(R/2768-2782)."""
    no_blank = "[PAGE 1]\n[BLOCK 1]\npolished"
    korean = "[PAGE 1]\n\n[BLOCK 1]\nrevised 남은 국문"
    flow = run_flow(
        make_input(LONG_SRC),
        [ok(LONG_EN), ok(no_blank), qa_reply(90, revised=korean), NO_ISSUES],
    )
    assert flow.rows == [SECTION, POLISH, QA, REVIEW]
    assert flow.codes() == ["polish_tags_changed", "editorial_qa_korean_increased"]
    assert flow.run.variants[0].translated_text == PAGE_OUT
    log = flow.run.variants[0].fragments[0].editorial_qa
    assert log is not None and (log.reason, log.applied) == ("korean_leftover_increased", False)


def test_polish_that_adds_korean_is_thrown_away() -> None:
    """R/2542-2546."""
    flow = run_flow(
        make_input(LONG_SRC),
        [ok(LONG_EN), ok("[PAGE 1]\n\n[BLOCK 1]\n윤문 국문"), qa_reply(99), NO_ISSUES],
    )
    assert flow.codes() == ["polish_korean_increased"]
    assert flow.calls[2].user == prompts.editorial_qa_user(NO_TERMS, LONG_SRC, PAGE_OUT, 1)


@pytest.mark.parametrize(
    ("reply", "reason", "applied", "score", "defaulted"),
    [
        (
            qa_reply(99, issues=[{"type": "grammar"}]),
            "revised_text_applied",
            True,
            99,
            False,
        ),  # critical 유형(소문자도)
        (qa_reply(99, critical=True), "revised_text_applied", True, 99, False),  # has_critical_issue
        (qa_reply(95), "revised_text_applied", True, 95, False),  # 95 < 96
        (qa_reply(96), "score_and_issues_acceptable", False, 96, False),  # 경계 — 96 은 통과
        (qa_reply(94, issues=[{"type": "FLOW"}, {"type": "COLLOCATION"}]), "revised_text_applied", True, 94, False),
        (
            qa_reply(99, issues=[{"type": "FLOW"}, {"type": "COLLOCATION"}]),
            "score_and_issues_acceptable",
            False,
            99,
            False,
        ),
        (qa_reply("abc"), "score_and_issues_acceptable", False, 100, True),  # W2 — 정수로 못 읽으면 100
        (
            ok(j({"has_critical_issue": False, "issues": [], "revised_text": REVISED})),
            "score_and_issues_acceptable",
            False,
            100,
            True,
        ),
        (qa_reply("95.7"), "score_and_issues_acceptable", False, 100, True),  # int("95.7") 는 ValueError → 100
        (qa_reply(95.7), "revised_text_applied", True, 95, False),  # int(95.7) = 95
        (qa_reply(90, revised=""), "no_revised_text", False, 90, False),
        (qa_reply(90, revised="[PAGE 1]\n[BLOCK 1]\nrevised"), "structure_tag_changed", False, 90, False),
    ],
)
def test_the_editorial_qa_gate_applies_the_colab_rule(
    reply: ProviderResponse, reason: str, applied: bool, score: int, defaulted: bool
) -> None:
    """R/2693-2789: must_apply = critical ∪ critical 유형 ∪ 점수 < 96 ∪ (점수 < 95 · 이슈 ≥ 2 · soft 유형)."""
    flow = run_flow(make_input(LONG_SRC), [ok(LONG_EN), ok(POLISHED), reply, NO_ISSUES])
    log = flow.run.variants[0].fragments[0].editorial_qa
    assert log is not None
    assert (log.reason, log.applied, log.quality_score, log.score_defaulted) == (reason, applied, score, defaulted)
    assert flow.run.variants[0].translated_text == (REVISED if applied else POLISHED)


def test_unreadable_qa_json_keeps_the_translation() -> None:
    """R/2683-2691."""
    flow = run_flow(make_input(LONG_SRC), [ok(LONG_EN), ok(POLISHED), ok("점수는 높습니다"), NO_ISSUES])
    log = flow.run.variants[0].fragments[0].editorial_qa
    assert log is not None
    assert (log.reason, log.quality_score, log.revised_preview) == ("json_parse_failed", None, "점수는 높습니다")
    assert flow.codes() == ["editorial_qa_json_failed"]


def test_a_missing_glossary_value_calls_the_glossary_repair_once() -> None:
    """R/2980-3041: 원문에 key 가 정확히 있고 번역에 value 가 없으면 보정 1회. 용어집은 쪽에 나온 key 만(R/3253)."""
    src = "[PAGE 1]\n[BLOCK 1]\n가상용어 소개"
    flow = run_flow(
        make_input(src, base=[("가상용어", "Virtual Term"), ("없는말", "Absent")]),
        [ok("[BLOCK 1]\nvirtual word intro"), ok("[BLOCK 1]\nVirtual Term intro"), NO_ISSUES],
    )
    assert flow.rows == [SECTION, ("glossary-repair", 4096, LIGHT_MODEL, LIGHT), REVIEW]
    assert "[Mandatory glossary for this source text]\n- 가상용어 -> Virtual Term\n" in flow.calls[0].user
    assert "[Missing or incorrect glossary applications]\n- 가상용어 -> Virtual Term\n" in flow.calls[1].user
    assert prompts.GLOSSARY_REPAIR_STRUCTURE_RULE in flow.calls[1].user
    assert flow.calls[1].system == flow.calls[0].system
    assert flow.run.variants[0].translated_text == "[PAGE 1]\n\n[BLOCK 1]\nVirtual Term intro"
    assert flow.run.variants[0].glossary_misses == []


def test_korean_left_after_two_repairs_turns_the_page_into_a_translation_error() -> None:
    """W7(R/3235-3236 → R/3497-3505): 한국어 보정 두 번(R/3051) 뒤에도 남으면 ValueError, 그 쪽은 원문 + 오류 표지.
    파일 왕복에서 그 표지 줄은 앞 쪽(1) 끝에 붙는다. 그 국문 쪽은 병기·검수·자동수정으로 흘러간다."""
    src = SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n남는 국문"
    replies = [
        ok(SIMPLE_EN),
        ok("[BLOCK 1]\nleft 국문"),
        ok("[BLOCK 1]\nstill 국문"),  # 잔존 줄 수가 줄지 않음 → 채택 안 함(R/3180-3184)
        ok("[BLOCK 1]\nagain 국문"),
        NO_ISSUES,
        NO_ISSUES,
        ok("[PAGE 2]\n[BLOCK 1]\nRemaining text"),  # 자동수정: 이슈 0 인데 한국어가 남은 쪽(R/6873-6889)
    ]
    flow = run_flow(make_input(src), replies)
    assert flow.rows == [SECTION, SECTION, KO_REPAIR, KO_REPAIR, REVIEW, REVIEW, AUTOFIX]
    assert flow.calls[2].system == prompts.korean_repair_system(flow.calls[0].system)
    assert "[Untranslated Korean detected]\n- left 국문\n" in flow.calls[2].user
    variant = flow.run.variants[0]
    assert [(f.page_num, f.status) for f in variant.fragments] == [(1, "translated"), (2, "error")]
    assert variant.fragments[1].error is not None and variant.fragments[1].error.startswith(
        "[치명] 번역 결과에 한국어가"
    )
    assert variant.translated_text == (
        "[PAGE 1]\n\n[BLOCK 1]\nVirtual Title\nVirtual body.\n\n"
        "[TRANSLATION_ERROR page=2]\n[PAGE 2]\n[BLOCK 1]\n남는 국문"
    )
    assert [p.translated for p in variant.pages] == [
        "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body.\n\n[TRANSLATION_ERROR page=2]",
        "[PAGE 2]\n[BLOCK 1]\n남는 국문",
    ]
    assert "\n- Raw English translation still contains Korean Hangul text." not in flow.calls[6].user
    assert '"issue_type": "UNTRANSLATED"' in flow.calls[6].user
    assert variant.autofix.status == "done"
    assert variant.autofix.translated_text == (
        "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body.\n\n"
        "[TRANSLATION_ERROR page=2]\n\n[PAGE 2]\n[BLOCK 1]\nRemaining text"
    )


def test_a_korean_repair_that_reduces_the_leftover_is_taken() -> None:
    """R/3180-3184: 잔존 줄이 줄면 채택, 0 이 되면 둘째 바퀴는 없다."""
    flow = run_flow(
        make_input("[PAGE 1]\n[BLOCK 1]\n가\n나"),
        [ok("[BLOCK 1]\n가\n나"), ok("[BLOCK 1]\nA\nB"), NO_ISSUES],
    )
    assert flow.rows == [SECTION, KO_REPAIR, REVIEW]
    assert flow.run.variants[0].translated_text == "[PAGE 1]\n\n[BLOCK 1]\nA\nB"


TABLE_SRC = "[PAGE 1]\n[TABLE 1]\n표 제목\n| 머리 | Value |\n| --- | --- |\n| 가상 | 1 |"


def test_unreadable_table_json_falls_back_to_one_call_per_cell() -> None:
    """R/2324-2333: 묶음 답을 JSON 으로 못 읽으면 그 묶음의 칸마다 한 번(1024). 표 밖 국문 줄(제목)도 칸이다(L1)."""
    flow = run_flow(
        make_input(TABLE_SRC),
        [ok("not json"), ok("Table Title"), ok("Header"), ok("Virtual"), NO_ISSUES],
    )
    assert flow.rows == [BATCH, CELL, CELL, CELL, REVIEW]
    assert flow.calls[1].user == prompts.cell_user(NO_TERMS, "표 제목")
    assert flow.codes() == ["table_json_fallback"]
    assert flow.run.variants[0].translated_text == (
        "[PAGE 1]\n\n[TABLE 1]\nTable Title\n| Header | Value |\n| --- | --- |\n| Virtual | 1 |"
    )


def test_a_truncated_table_batch_falls_back_to_cells_and_is_recorded() -> None:
    """개정 1 B4: 표 묶음 8192 가 잘리면 잘린 글로 계속 → JSON 실패 → 칸 대체. 경고 llm_truncated(+ 쪽 번호)."""
    flow = run_flow(
        make_input(TABLE_SRC),
        [cut('{"items": [{"id": "L1", "translation": "Ta'), ok("Table Title"), ok("Header"), ok("Virtual"), NO_ISSUES],
    )
    assert flow.rows == [BATCH, CELL, CELL, CELL, REVIEW]
    assert flow.codes() == ["llm_truncated", "table_json_fallback"]
    assert (flow.run.warnings[0].page_num, flow.run.warnings[0].variant) == (1, "single")


def test_a_refusal_flows_on_as_the_translation() -> None:
    """개정 1 B4: 코랩은 stop_reason 을 보지 않는다 — 거절 글이 번역 글로 들어가 검수까지 간다. 경고 llm_refused."""
    flow = run_flow(make_input(SIMPLE), [refuse("I can't help with that."), NO_ISSUES])
    assert flow.codes() == ["llm_refused"]
    assert flow.run.variants[0].translated_text == "[PAGE 1]\n\nI can't help with that."
    assert "\n[PAGE 1]\nI can't help with that.\n" in flow.calls[1].user


def test_each_site_strips_like_the_colab() -> None:
    """R/2153(_response_text 의 strip)·R/5332(검수 첫 블록 strip)·R/6396(자동수정 strip). 다리는 strip 하지 않는다."""
    issues = [
        {
            "issue_type": "GRAMMAR",
            "severity": "LOW",
            "original_span": "Virtual body.",
            "suggestion": "Virtual text.",
            "reason": "문법",
        }
    ]
    flow = run_flow(
        make_input(SIMPLE),
        [
            ok("\n\n  " + SIMPLE_EN + "\n  \n"),
            ok("  \n" + j(issues) + "\n "),
            ok("\n [PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text.\n\n"),
        ],
    )
    variant = flow.run.variants[0]
    assert variant.translated_text == "[PAGE 1]\n\n" + SIMPLE_EN
    assert [i.original_span for i in variant.pages[0].issues] == ["Virtual body."]
    assert variant.autofix.translated_text == "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text."


def test_unreadable_review_json_keeps_only_the_glossary_rule_issues() -> None:
    """W8(R/5335-5340): 검수 JSON 을 못 읽으면 모델 이슈 0(print 뿐). 결정적 용어집 위반은 남는다(R/5346-5350)."""
    src = "[PAGE 1]\n[BLOCK 1]\n가상용어 소개"
    flow = run_flow(
        make_input(src, base=[("가상용어", "Virtual Term")], autofix=False),
        [ok("[BLOCK 1]\nvirtual word"), ok("[BLOCK 1]\nvirtual word again"), ok("이슈 없음")],
    )
    (page,) = flow.run.variants[0].pages
    assert page.status == "parse_failed"
    assert [(i.issue_type, i.source) for i in page.issues] == [("GLOSSARY_VIOLATION", "glossary_rule")]
    assert "review_json_failed" in flow.codes()
    assert flow.run.variants[0].autofix.status == "not_run"
    assert flow.run.variants[0].autofix.not_run_reason == "disabled"
    assert [(m[0], m[1], m[2], m[3]) for m in flow.run.variants[0].glossary_misses] == [
        (1, "가상용어", "Virtual Term", 1)
    ]


def test_autofix_replaces_the_exact_span_first_then_asks_the_model() -> None:
    """R/6891-6907: 구간·제안이 그대로면 먼저 직접 치환, 그 글로 LLM 최소 수정."""
    issues = [
        {
            "issue_type": "GRAMMAR",
            "severity": "LOW",
            "original_span": "Virtual body.",
            "suggestion": "Virtual text.",
            "reason": "문법",
        }
    ]
    flow = run_flow(
        make_input(SIMPLE),
        [ok(SIMPLE_EN), ok(j(issues)), ok("[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text, fixed.")],
    )
    assert flow.rows == [SECTION, REVIEW, AUTOFIX]
    fix = flow.calls[2]
    assert fix.system == prompts.autofix_system(1)
    assert "[Current English translation PAGE 1]\n[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual text.\n" in fix.user
    (page,) = flow.run.variants[0].autofix.pages
    assert (page.reason, page.changed, page.issue_count) == ("llm_repair_applied", True, 1)
    assert [(s.original_span, s.suggestion) for s in page.span_replacements] == [("Virtual body.", "Virtual text.")]
    assert (
        flow.run.variants[0].autofix.bilingual_text
        == "[PAGE 1]\n[BLOCK 1]\nVirtual Title (가상 제목)\nVirtual text, fixed."
    )


def test_autofix_that_changes_table_pipes_keeps_the_current_page() -> None:
    """R/6716-6731: 표 pipe 시그니처가 바뀌면 LLM 보정본을 버리고 지금 글(설명 줄 걷고 쪽 태그)을 쓴다."""
    issues = [
        {"issue_type": "TABLE_CONTENT", "severity": "LOW", "original_span": "", "suggestion": "Fix it", "reason": "표"}
    ]
    table_en = "[TABLE 1]\nTable Title\n| Header | Value |\n| --- | --- |\n| Virtual | 1 |"
    flow = run_flow(
        make_input(TABLE_SRC),
        [
            ok(
                j(
                    {
                        "items": [
                            {"id": "L1", "translation": "Table Title"},
                            {"id": "T0_H0", "translation": "Header"},
                            {"id": "T0_R0C0", "translation": "Virtual"},
                        ]
                    }
                )
            ),
            ok(j(issues)),
            ok("[PAGE 1]\n[TABLE 1]\n| a |\n| --- |"),
        ],
    )
    assert flow.rows == [BATCH, REVIEW, AUTOFIX]
    (page,) = flow.run.variants[0].autofix.pages
    assert (page.reason, page.changed) == ("table_pipe_signature_changed_safe_current_used", False)
    assert flow.codes() == ["autofix_table_changed"]
    assert flow.run.variants[0].autofix.translated_text == "[PAGE 1]\n" + table_en


def test_autofix_stops_when_korean_is_left_after_one_extra_round() -> None:
    """W7(R/6925-6929): 자동수정 한국어 보정 1회(R/6368) 뒤에도 남으면 ValueError — 셀이 멈춘다. 결과는 stopped,
    앞 쪽들의
    결과도 버린다(처분 ⑪). 번역·검수 결과는 남는다."""
    two = SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n둘째 쪽"
    flow = run_flow(
        make_input(two),
        [
            ok(SIMPLE_EN),
            ok("[BLOCK 1]\nSecond 국문"),
            ok("[BLOCK 1]\nSecond again 국문"),
            ok("[BLOCK 1]\nSecond still 국문"),
            NO_ISSUES,
            NO_ISSUES,
            ok("[PAGE 2]\n[BLOCK 1]\nSecond 국문 left"),
            ok("[PAGE 2]\n[BLOCK 1]\nSecond 국문 still"),
        ],
    )
    assert flow.rows == [SECTION, SECTION, KO_REPAIR, KO_REPAIR, REVIEW, REVIEW, AUTOFIX, AUTOFIX_KO]
    autofix = flow.run.variants[0].autofix
    assert autofix.status == "stopped"
    assert autofix.pages == () and autofix.translated_text is None
    assert autofix.stop == AutofixStop(
        kind="remaining_korean",
        page_num=2,
        remaining_korean=("Second 국문 still",),
        message="STYLE single / PAGE 2 자동수정 후에도 한국어가 남아 있습니다.\n- Second 국문 still",
    )
    assert flow.calls[7].system == prompts.autofix_korean_system(2)


def test_a_b_autofix_stop_in_a_leaves_b_not_run() -> None:
    """셀 67 이 A 에서 멈추면 B 는 돌지 않는다(R/6833 의 for 가 끊김)."""
    flow = run_flow(
        make_input("[PAGE 1]\n[BLOCK 1]\n가", compare_ab=True),
        [
            ok("[BLOCK 1]\nA"),
            ok("[BLOCK 1]\nB"),
            ok(
                j(
                    [
                        {
                            "issue_type": "OMISSION",
                            "severity": "HIGH",
                            "original_span": "",
                            "suggestion": "add",
                            "reason": "빠짐",
                        }
                    ]
                )
            ),
            NO_ISSUES,
            fail(),
        ],
    )
    assert flow.rows == [SECTION, SECTION, REVIEW, REVIEW, AUTOFIX]
    a, b = flow.run.variants
    assert a.autofix.status == "stopped"
    assert a.autofix.stop is not None and (a.autofix.stop.kind, a.autofix.stop.page_num) == ("call_failed", 1)
    assert (b.autofix.status, b.autofix.not_run_reason) == ("not_run", "earlier_variant_stopped")


def test_a_review_call_failure_stops_the_review_and_the_autofix() -> None:
    """셀 65 는 검수 호출 예외에서 멈춘다(잡지 않음): 그 쪽 call_failed, 뒤 쪽 not_run, 자동수정은 review_stopped."""
    two = SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n둘째 쪽"
    flow = run_flow(make_input(two), [ok(SIMPLE_EN), ok("[BLOCK 1]\nSecond"), fail()])
    assert flow.rows == [SECTION, SECTION, REVIEW]
    variant = flow.run.variants[0]
    assert [(p.page_num, p.status) for p in variant.pages] == [(1, "call_failed"), (2, "not_run")]
    assert variant.pages[0].message == "LlmCallFailed: review: provider_error"
    assert (variant.autofix.status, variant.autofix.not_run_reason) == ("not_run", "review_stopped")


def test_a_translation_call_failure_is_a_page_error_like_any_exception() -> None:
    """R/3497: 공급사 오류도 쪽의 except 에 잡혀 W7 갈래(원문 + 표지)."""
    flow = run_flow(make_input(SIMPLE, autofix=False), [fail(), NO_ISSUES])
    (fragment,) = flow.run.variants[0].fragments
    assert (fragment.status, fragment.error) == ("error", "section: provider_error")
    # 첫 쪽의 표지 줄은 파일 왕복에서 [PAGE 1] 앞에 있어 다음 셀의 쪽 나누기가 버린다(R/550-579)
    assert flow.run.variants[0].translated_text == "[TRANSLATION_ERROR page=1]\n" + SIMPLE
    assert flow.run.variants[0].pages[0].translated == SIMPLE


def test_page_range_and_no_pages() -> None:
    """R/3433-3455: 쪽 범위로 거르고, 남는 쪽이 없으면 거절(no_pages). 태그 없는 글도 no_pages."""
    two = SIMPLE + "\n[PAGE 2]\n[BLOCK 1]\n둘째 쪽"
    flow = run_flow(make_input(two, start=2), [ok("[BLOCK 1]\nSecond"), NO_ISSUES])
    assert flow.run.page_numbers == [2]
    assert [p.page_num for p in flow.run.variants[0].pages] == [2]
    assert run_flow(make_input(two, start=3), []).run.rejection == Rejection(
        kind="no_pages", message="번역 대상 페이지가 없습니다. PAGE_START/PAGE_END 또는 INPUT_FILE을 확인하세요."
    )
    assert run_flow(make_input("태그 없는 글"), []).run.rejection is not None


def test_the_same_page_twice_is_translated_twice_and_merged_for_review() -> None:
    """R/3448·3481: 번역은 조각마다(같은 번호 둘이면 두 번), 검수는 합친 쪽(R/614-648) — 경고 duplicate_pages."""
    src = SIMPLE + "\n[PAGE 1]\n[BLOCK 2]\n덧붙은 조각"
    flow = run_flow(make_input(src), [ok(SIMPLE_EN), ok("[BLOCK 2]\nExtra"), NO_ISSUES])
    assert flow.rows == [SECTION, SECTION, REVIEW]
    assert [f.page_num for f in flow.run.variants[0].fragments] == [1, 1]
    assert flow.run.duplicate_pages == {1: 2}
    (page,) = flow.run.variants[0].pages
    assert page.translated == "[PAGE 1]\n[BLOCK 1]\nVirtual Title\nVirtual body.\n\n[BLOCK 2]\nExtra"
    assert "duplicate_pages" in flow.codes()


def test_the_glossary_check_sees_only_the_pages_of_the_run() -> None:
    """T1(MARC-ENT-451 — 코랩 셀 57 과 다름): 반영 검사는 그 실행의 쪽 범위만 본다. 범위 밖 쪽(1·4·5)의 용어는
    번역에 없어도 미반영이 아니다."""
    pages = [
        "[PAGE 1]\n[BLOCK 1]\n가상용어 소개",
        "[PAGE 2]\n[BLOCK 1]\n둘째 쪽",
        "[PAGE 3]\n[BLOCK 1]\n셋째 쪽",
        "[PAGE 4]\n[BLOCK 1]\n가상용어 정리",
        "[PAGE 5]\n[BLOCK 1]\n가상용어 끝",
    ]
    flow = run_flow(
        make_input("\n".join(pages), base=[("가상용어", "Virtual Term")], start=2, end=3),
        [ok("[BLOCK 1]\nSecond"), ok("[BLOCK 1]\nThird"), NO_ISSUES, NO_ISSUES],
    )
    assert flow.run.page_numbers == [2, 3]
    assert flow.run.variants[0].glossary_misses == []


def test_the_glossary_check_merges_fragments_of_the_same_page() -> None:
    """T2·T4(MARC-ENT-451 — 코랩 셀 57 과 다름): 같은 번호 조각은 합쳐 본다 — 영문이 앞 조각에만 있어도 반영. 합침
    경고 duplicate_pages 는 BASE 와 같은 다섯·같은 차례(셀 65 원문·병기·raw, 셀 67 원문·raw — 반영 검사 자리는 경고를
    더하지 않는다)."""
    src = "[PAGE 1]\n[BLOCK 1]\n가상용어 소개\n[PAGE 1]\n[BLOCK 2]\n덧붙은 조각"
    flow = run_flow(
        make_input(src, base=[("가상용어", "Virtual Term")]),
        [ok("[BLOCK 1]\nVirtual Term intro"), ok("[BLOCK 2]\nExtra"), NO_ISSUES],
    )
    assert flow.run.variants[0].glossary_misses == []
    assert [w.message for w in flow.run.warnings if w.code == "duplicate_pages"] == [
        "원문 중복 PAGE 감지 및 병합: {1: 2}",
        "병기 번역 single 중복 PAGE 감지 및 병합: {1: 2}",
        "raw 영문 번역 single 중복 PAGE 감지 및 병합: {1: 2}",
        "원문 중복 PAGE 감지 및 병합: {1: 2}",
        "raw 번역 single 중복 PAGE 감지 및 병합: {1: 2}",
    ]


def test_the_glossary_check_merges_source_fragments_of_the_same_page() -> None:
    """R1(MARC-ENT-451): 원문 쪽도 같은 번호 조각을 합쳐 본다 — 용어가 앞 조각에만 있고 번역 어느 조각에도 영문이 없으면
    미반영 하나(뒤 조각만 보면 놓친다)."""
    src = "[PAGE 1]\n[BLOCK 1]\n가상용어 소개\n[PAGE 1]\n[BLOCK 2]\n덧붙은 조각"
    flow = run_flow(
        make_input(src, base=[("가상용어", "Virtual Term")], autofix=False),
        [ok("[BLOCK 1]\nvirtual word"), ok("[BLOCK 1]\nvirtual word again"), ok("[BLOCK 2]\nExtra"), NO_ISSUES],
    )
    assert flow.run.variants[0].glossary_misses == [(1, "가상용어", "Virtual Term", 1)]


def test_w4_autofix_has_no_part_issues_and_skips_clean_pages() -> None:
    """W4(R/6870): 파트 이슈는 늘 빈 목록 — 이슈·한국어가 없는 쪽은 자동수정 호출 0."""
    flow = run_flow(make_input(SIMPLE), [ok(SIMPLE_EN), NO_ISSUES])
    assert "autofix" not in flow.sites


def test_w3_review_is_haiku_even_for_ceo() -> None:
    """W3(R/5326)."""
    flow = run_flow(make_input(SIMPLE, part="ceo_message"), [ok("[PAGE 1]"), ok(SIMPLE_EN), ok(SIMPLE_EN), NO_ISSUES])
    assert flow.calls[-1].row == REVIEW


def test_flow_case_count() -> None:
    """S2 경우 수(발주서 — 적어도 열다섯): 이 파일의 흐름 시험 함수."""
    names = [
        name
        for name in globals()
        if name.startswith("test_")
        and name not in {"test_flow_case_count", "test_the_long_page_fixture_sits_between_the_two_gates"}
    ]
    assert len(names) == 34
