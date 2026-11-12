"""v2 프롬프트 글(engines/v2/texts.py — RP2b B12 · RPQ1 B1·B2·B6 · RPA4 B1·B2): README 「v2」 지문 표 == 코드 ·
map_user 는 v1 의 「쪽 글」을 「페이지 글」로, map_system 은 v1 글의 「쪽」을 「페이지」로 + 요구 내용 대조 한 줄 ·
v2 자리 `{페이지 글}` · 고정 꼬리 둘은 draft system 뒤 · 글을 바꾸면 판을 올린다(핀) ·
봉투 draft/2.md 는 draft/1.md 와 같은 바이트."""

import hashlib
import re
from pathlib import Path

from esgapi.drafting.engines.v1 import texts as v1_texts
from esgapi.drafting.engines.v1.texts import DEFAULT_TEXTS as V1
from esgapi.drafting.engines.v2 import texts
from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS, MARKER_RULES, TEXTS_VERSION, WRITING_RULES

PROMPTS = Path(texts.__file__).resolve().parents[2] / "prompts"
FIELDS = ("map_system", "map_user", "draft_system", "draft_user")
# 글 판 → 칸 넷 + 꼬리 둘의 지문. 글을 바꾸면 TEXTS_VERSION 을 올리고 여기에 새 줄을 단다(옛 줄은 지우지 않는다).
TEXTS_PINS = {
    "drafting-texts@1": "94e9f8c577910f8157847c89e0012bd689d26d937bfea5168e8badf1474f8484",
    "drafting-texts@2": "e3c55469a40a41af8fdee8c7413b308dea9f1347d92384d5c43c5623d11bad75",
    "drafting-texts@3": "74976d43ca529856e6d78ca6882e09903fcb753f4d3eaf3bd0c2c5be0e5f2a55",
}


def sha(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def test_readme_v2_fingerprints_match() -> None:
    readme = (PROMPTS / "README.md").read_text(encoding="utf-8")
    rows = dict(re.findall(r"^\| v2 `([A-Za-z_]+)` \| `([0-9a-f]{64})` \|$", readme, re.M))
    expected = {name: sha(getattr(DEFAULT_TEXTS, name)) for name in FIELDS} | {"MARKER_RULES": sha(MARKER_RULES)}
    expected["WRITING_RULES"] = sha(WRITING_RULES)
    assert rows == expected


def test_rpa4_b1_map_user_is_v1_with_the_page_words_and_map_system_and_draft_fields_are_new() -> None:
    assert DEFAULT_TEXTS.map_user == V1.map_user.replace("쪽 글", "페이지 글")
    assert DEFAULT_TEXTS.map_user != V1.map_user
    assert DEFAULT_TEXTS.map_system != V1.map_system
    assert DEFAULT_TEXTS.draft_system != V1.draft_system and DEFAULT_TEXTS.draft_user != V1.draft_user


def test_rpq1_b2_map_system_is_the_v1_text_plus_one_line() -> None:
    head = V1.map_system.removesuffix("JSON 으로만 답한다.").rstrip().replace("쪽", "페이지")
    assert head != V1.map_system
    added = DEFAULT_TEXTS.map_system.removeprefix(head + "\n")
    assert added != DEFAULT_TEXTS.map_system  # v1 글로 시작한다
    line, end = added.split("\n")
    assert end == "JSON 으로만 답한다."
    for word in ("여러 잎", "요구 내용", "한 문단", "인사말"):
        assert word in line


def test_rpa4_b1_draft_system_did_not_move_and_draft_user_and_marker_rules_moved_by_the_page_word() -> None:
    assert sha(DEFAULT_TEXTS.draft_system) == "fd800423dafcba437957f28f7faf2e7c33a6d2bb4a145180c0c2eeb1f954775e"
    assert sha(DEFAULT_TEXTS.draft_user) == "7daeeb60de373acaf2f4749d6e238ce6def34e3d92be73cee4253fcd96a29ba8"
    assert sha(MARKER_RULES) == "89bf99b3172eaaf316ef0422aa82ec5e75e0a818e97a55baca3841d9d0abe914"


def test_the_marker_rules_follow_the_system_field() -> None:
    assert texts.draft_system("칸 글") == "칸 글\n\n" + MARKER_RULES + "\n\n" + WRITING_RULES
    for word in ("[B <id>]", "[T <id>]", "⟨n⟩", "0부터", '"block"', '"s"', "null"):
        assert word in MARKER_RULES


def test_rpq1_b1_the_writing_rules_say_all_five_things() -> None:
    lines = WRITING_RULES.split("\n")
    assert lines[0] == "[글 규칙]" and len(lines) == 6
    language, names, rewrite, ending, one_fact = lines[1:]
    assert "한국어" in language and "영어" in language
    for word in ("수·단위·연도·고유명사", "Scope 1", "tCO2eq", "ISO 45001"):
        assert word in names
    assert "옮겨 붙이지" in rewrite and "뜻을 살려" in rewrite
    for word in ("~함", "~임", "~됨", "~있음", "~했다", "~이다", "~합니다"):
        assert word in ending
    assert "사실 하나" in one_fact


def test_rpq1_b6_changing_a_text_needs_a_new_version() -> None:
    joined = "\0".join([*(getattr(DEFAULT_TEXTS, name) for name in FIELDS), MARKER_RULES, WRITING_RULES])
    assert sha(joined) == TEXTS_PINS[TEXTS_VERSION]


def test_the_envelope_is_the_same_bytes() -> None:
    assert (PROMPTS / "draft" / "2.md").read_bytes() == (PROMPTS / "draft" / "1.md").read_bytes()


def test_rpa4_b1_no_page_word_is_left_in_the_v2_texts() -> None:
    for name in FIELDS:
        assert "쪽" not in getattr(DEFAULT_TEXTS, name), name
    assert "쪽" not in MARKER_RULES and "쪽" not in WRITING_RULES
    assert "`[PAGE n]` 줄은 페이지 머리다." in MARKER_RULES


def test_rpa4_b1_the_first_three_map_system_lines_are_v1_with_the_page_word() -> None:
    v1_lines = V1.map_system.removesuffix("JSON 으로만 답한다.").rstrip().split("\n")
    assert len(v1_lines) == 3
    assert DEFAULT_TEXTS.map_system.split("\n")[:3] == [line.replace("쪽", "페이지") for line in v1_lines]
    line = DEFAULT_TEXTS.map_system.split("\n")[3]
    for word in ("여러 잎", "요구 내용", "한 문단", "인사말"):
        assert word in line


def test_rpa4_b1_draft_system_and_writing_rules_are_the_base_bytes() -> None:
    assert sha(DEFAULT_TEXTS.draft_system) == "fd800423dafcba437957f28f7faf2e7c33a6d2bb4a145180c0c2eeb1f954775e"
    assert sha(WRITING_RULES) == "2aa9bdf49db994f8b23a96b8db89acf33d62f3d313519ef24ba34ce9f11fc0e2"


def test_rpa4_b1_v2_has_its_own_pages_slot_and_v1_keeps_its_own() -> None:
    assert texts.PAGES_SLOT == "{페이지 글}"
    assert v1_texts.PAGES_SLOT == "{쪽 글}"
    assert texts.PAGES_SLOT in DEFAULT_TEXTS.map_user and texts.PAGES_SLOT in DEFAULT_TEXTS.draft_user
    assert v1_texts.PAGES_SLOT not in DEFAULT_TEXTS.map_user + DEFAULT_TEXTS.draft_user
    for slot in ("OUTLINE_SLOT", "TITLE_SLOT", "REQUIREMENT_SLOT"):
        assert getattr(texts, slot) == getattr(v1_texts, slot)


def test_rpa4_b2_the_version_is_2_and_the_old_pin_stays() -> None:
    assert TEXTS_VERSION == "drafting-texts@3"
    assert set(TEXTS_PINS) == {"drafting-texts@1", "drafting-texts@2", "drafting-texts@3"}


def test_rpa4_b1_the_map_match_line_says_whole_page_topic_greetings_and_when_empty() -> None:
    """경계 ③(L3): map 대조 줄 — 페이지 주제가 달라도 항목 문단이 있으면 고름 · 인사말·개요 안의 목표·수치 문단 · 빈
    목록은 그런 문단이 없을 때만."""
    line = DEFAULT_TEXTS.map_system.split("\n")[3]
    for word in (
        "페이지 전체 주제가 잎과 달라도",
        "한 문단이라도",
        "인사말·보고서 개요 페이지 안의 목표·수치 문단",
        "빈 목록은",
    ):
        assert word in line, word
    assert line.endswith("그런 문단이 하나도 없을 때만 준다.")


def test_rps2_t1_the_marker_rules_end_with_the_table_number_line() -> None:
    """562 A: 표에서 가져온 숫자는 표 위 제목·라벨이 아니라 표 id·행 번호로 — MARKER_RULES 끝 줄(@3)."""
    *before, line = MARKER_RULES.split("\n")
    assert before[-1] == "- 자료에 표지로 나온 id·번호만 쓴다. 표지에 없는 id·번호를 지어내지 않는다."
    for word in ("표", "[T <id>]", "행", "제목"):
        assert word in line
    assert "쪽" not in line
