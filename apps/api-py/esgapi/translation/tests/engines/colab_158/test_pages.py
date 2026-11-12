"""pages.py(코랩 셀 17·18) — 손으로 지은 기대값(발주서 §3 S1)."""

from esgapi.translation.engines.colab_158.pages import (
    PageChunk,
    file_roundtrip,
    filter_range,
    join_pages,
    last_wins_map,
    pages_to_map_merge,
    parse_pages,
    remove_page_tag_lines,
)


def test_parse_pages_splits_on_whole_page_tag_lines_only() -> None:
    """R/545-579: 한 줄 전체가 [PAGE n](굵게·역슬래시 꼴 포함)일 때만. 첫 태그 앞 글은 버린다. 본문 앞 빈 줄은 빼고
    끝은 rstrip."""
    text = "머리말\n[PAGE 1]\n\n가\n**[PAGE 2]**\n나\n\n\\[PAGE 3\\]\n다 [PAGE 9] 안\n [page 4] \n라\n[PAGE 5] 본문\n"
    assert parse_pages(text) == [
        PageChunk(1, "[PAGE 1]\n가"),
        PageChunk(2, "[PAGE 2]\n나"),
        PageChunk(3, "[PAGE 3]\n다 [PAGE 9] 안"),
        PageChunk(4, "[PAGE 4]\n라\n[PAGE 5] 본문"),
    ]
    assert parse_pages("태그 없음") == []
    assert parse_pages(None) == []


def test_the_error_line_of_a_failed_page_lands_on_the_previous_page() -> None:
    """코랩은 조각을 빈 줄로 이어 쓰고(R/3524) 다음 셀이 다시 나눈다 — 실패 쪽의 [TRANSLATION_ERROR page=n] 줄(R/3499)은
    앞 쪽 끝에 붙는다. 첫 쪽이 실패하면 그 줄은 사라진다."""
    joined = join_pages(["[PAGE 1]\nA", "[TRANSLATION_ERROR page=2]\n[PAGE 2]\n가"])
    assert parse_pages(joined) == [
        PageChunk(1, "[PAGE 1]\nA\n\n[TRANSLATION_ERROR page=2]"),
        PageChunk(2, "[PAGE 2]\n가"),
    ]
    assert parse_pages("[TRANSLATION_ERROR page=1]\n[PAGE 1]\n가") == [PageChunk(1, "[PAGE 1]\n가")]


def test_merge_duplicate_pages() -> None:
    """R/614-648: 같은 번호는 본문을 빈 줄로 잇되, 이미 든 본문은 다시 넣지 않는다. 겹친 횟수는 처음을 1 로 센다."""
    pages = [
        PageChunk(3, "[PAGE 3]\n[HEADER]\n머리"),
        PageChunk(1, "[PAGE 1]\n가"),
        PageChunk(3, "[PAGE 3]\n[BLOCK 1]\n나"),
        PageChunk(3, "[PAGE 3]\n[HEADER]\n머리"),
    ]
    merged, dups = pages_to_map_merge(pages)
    assert merged == {3: "[PAGE 3]\n[HEADER]\n머리\n\n[BLOCK 1]\n나", 1: "[PAGE 1]\n가"}
    assert list(merged) == [3, 1]
    assert dups == {3: 3}
    assert last_wins_map(pages) == {3: "[PAGE 3]\n[HEADER]\n머리", 1: "[PAGE 1]\n가"}


def test_remove_page_tag_lines_and_range_and_roundtrip() -> None:
    assert remove_page_tag_lines("[PAGE 1]\n가\n  **[PAGE 2]**  \n나\n") == "가\n나"
    assert remove_page_tag_lines("") == ""
    pages = {1: "a", 2: "b", 3: "c"}
    assert filter_range(pages, 2, None) == {2: "b", 3: "c"}
    assert filter_range(pages, None, 1) == {1: "a"}
    assert filter_range(pages, None, None) is pages
    assert file_roundtrip("a\r\nb\rc\n") == "a\nb\nc\n"
