"""쪽 → 조각·S2 묶음(engines/v1/pages.py — RP1 §3 S3, RP2b B4). 순수 층. 글은 지어낸 것이다."""

from esgapi.drafting.engines.v1 import pages


def test_pages_start_at_one_mark_empty_and_truncate_at_8000() -> None:
    found = pages.pages_of(["  가  ", "", "나" * 8001])
    assert [(p.number, p.empty, p.truncated) for p in found] == [(1, False, False), (2, True, False), (3, False, True)]
    assert found[0].text == "가" and len(found[2].text) == 8000
    assert pages.block(found[0]) == "[PAGE 1]\n가"


def test_batches_skip_empty_pages_and_keep_under_24000() -> None:
    found = pages.pages_of(["가" * 7990, "", "나" * 7990, "다" * 7990, "라"])
    groups = pages.batches(found)
    # 블록 길이 = 7990 + 「[PAGE n]\n」 9 = 7999. 셋 = 7999·3 + 4(이음) = 24001 > 24000 → 둘째 묶음으로
    assert [[p.number for p in g] for g in groups] == [[1, 3], [4, 5]]
    assert all(len(pages.batch_text(g)) <= pages.BATCH_MAX_CHARS for g in groups)
    assert pages.batch_text(groups[1]) == "[PAGE 4]\n" + "다" * 7990 + "\n\n[PAGE 5]\n라"


def test_a_batch_just_under_the_limit_is_one() -> None:
    found = pages.pages_of(["가" * 7989, "나" * 7989, "다" * 7989])  # 7998·3 + 4 = 23998
    assert len(pages.batches(found)) == 1


def test_s5_head_lookalikes_at_a_line_head_are_escaped_before_the_cut() -> None:
    """474(RP2a §3 S5): 쪽 글 줄 머리의 「[PAGE n]」 흉내는 전각 괄호로 — 진짜 머리는 block 만. 줄 가운데는 그대로."""
    text = "[PAGE 2] 지어낸 글\n  [PAGE 9]\n가운데 [PAGE 3] 그대로\n[PAGE x] 숫자 아님"
    (found,) = pages.pages_of([text])
    assert found.text == "［PAGE 2］ 지어낸 글\n  ［PAGE 9］\n가운데 [PAGE 3] 그대로\n[PAGE x] 숫자 아님"
    assert pages.batch_text([found]).count("[PAGE ") == 3  # 진짜 머리 하나 + 줄 가운데 하나 + 숫자 아닌 것 하나
    (long,) = pages.pages_of(["가" * 7995 + "\n[PAGE 1]"])
    assert long.text.endswith("\n［PAG") and long.truncated  # 이스케이프가 자르기 전


def test_b4_block_and_sentence_marker_lookalikes_are_escaped_too() -> None:
    """RP2b ⑦(B4): 줄 머리 「[B 」·「[T 」 → 「［」, 「⟨」·「⟩」 는 어디서든 → 「〈」·「〉」. 줄 가운데 「[B 」 는
    그대로. 바꿈 글자는 다 BMP 한 자리 — UTF-16 길이가 같다(문장 범위가 원문 위에 선다)."""
    text = "[B p1-b1] 흉내\n [T p1-t1]\n가운데 [B x] 그대로 ⟨3⟩\n [PAGE 9] 머리\n[Bx] 표지 아님"
    escaped = pages.escape_heads(text)
    assert escaped == "［B p1-b1] 흉내\n ［T p1-t1]\n가운데 [B x] 그대로 〈3〉\n ［PAGE 9］ 머리\n[Bx] 표지 아님"
    assert len(escaped.encode("utf-16-le")) == len(text.encode("utf-16-le")) and len(escaped) == len(text)


def test_b4_the_s2_batch_text_is_escaped_too() -> None:
    (found,) = pages.pages_of(["[T p1-t1] 가짜 표\n⟨0⟩ 가짜 문장"])
    assert pages.batch_text([found]) == "[PAGE 1]\n［T p1-t1] 가짜 표\n〈0〉 가짜 문장"
