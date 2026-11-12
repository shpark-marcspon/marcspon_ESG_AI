"""engines/colab_155/prompts.py 의 글(코랩 셀 17·20·22 의 system·접두·가변)이 고정한 지문과 같고, 코랩의 약점
W3·W4·W5 를 그대로 내며, 규제 system 의 판끼리는 [8] 블록만 다른가(발주서 §3 S2).

지문은 아래 지어낸 입력(산업 1개·3개 — W4)으로 낸 글의 sha256 이고 prompts/README.md 「낸 글 지문」 표에 있다
(러너 손셈).
코랩 글과의 바이트 견줌은 scripts/section4-IR1a.sh 7단계가 실행 때 읽기판에서 한다(MARC-ENT-310 — 저장소에 사본 0).
"""

import hashlib
import re
from pathlib import Path

import pytest

import esgapi.materiality as package
from esgapi.materiality.engines.colab_155 import prompts, whitelists

README = Path(package.__file__).parent / "prompts" / "README.md"

INDUSTRY_1 = [{"standard": "SASB", "industry_name": "가상 산업 하나", "description": "가상 설명 하나 — {괄호}"}]
INDUSTRY_3 = [
    {"standard": "SASB", "industry_name": "가상 산업 하나", "description": "가상 설명 하나"},
    {"standard": "GICS", "industry_name": "가상 산업 둘(Virtual)", "description": "가상 설명 둘 'quote'"},
    {"standard": "KSIC", "industry_name": "가상 산업 셋", "description": "가상 설명 셋"},
]
# 셀 11 R/369-371 의 industry_text 를 손으로 적은 것(줄마다 끝 줄바꿈)
INDUSTRY_TEXT_1 = "- 기준: SASB, 산업명: 가상 산업 하나, 설명: 가상 설명 하나 — {괄호}\n"
INDUSTRY_TEXT_3 = (
    "- 기준: SASB, 산업명: 가상 산업 하나, 설명: 가상 설명 하나\n"
    "- 기준: GICS, 산업명: 가상 산업 둘(Virtual), 설명: 가상 설명 둘 'quote'\n"
    "- 기준: KSIC, 산업명: 가상 산업 셋, 설명: 가상 설명 셋\n"
)
TOPICS = [
    {"topic": "가상토픽 하나", "description": "가상토픽 하나의 설명"},
    {"topic": "가상토픽 둘", "description": "가상토픽 둘의 설명 {x}"},
]
TOPIC, DESC = "가상토픽 하나", "가상토픽 하나의 설명"
LOCATION, LANG, DATES = "가상 범위(대한민국/EU)", "한국어", "2025-01-01~오늘까지"
KEYWORDS = "가상 키워드 1, 가상 키워드 2"


def outputs() -> dict[str, str]:
    return {
        "regulation_system[colab17]": prompts.regulation_system(whitelists.WHITELIST_COLAB17),
        "regulation_system[cell71]": prompts.regulation_system(whitelists.WHITELIST_CELL71),
        "regulation_system[cell73]": prompts.regulation_system(whitelists.WHITELIST_CELL73),
        "REGULATION_USER_PREFIX": prompts.REGULATION_USER_PREFIX,
        "regulation_user[1]": prompts.regulation_user(TOPIC, DESC, INDUSTRY_TEXT_1, LOCATION, LANG),
        "regulation_user[3]": prompts.regulation_user(TOPIC, DESC, INDUSTRY_TEXT_3, LOCATION, LANG),
        "KEYWORDS_SYSTEM": prompts.KEYWORDS_SYSTEM,
        "KEYWORDS_USER_PREFIX": prompts.KEYWORDS_USER_PREFIX,
        "keywords_user[1]": prompts.keywords_user(INDUSTRY_1, DATES, LANG, TOPICS),
        "keywords_user[3]": prompts.keywords_user(INDUSTRY_3, DATES, LANG, TOPICS),
        "CONTROVERSY_SYSTEM": prompts.CONTROVERSY_SYSTEM,
        "CONTROVERSY_USER_PREFIX": prompts.CONTROVERSY_USER_PREFIX,
        "controversy_user[1]": prompts.controversy_user(TOPIC, DESC, INDUSTRY_1, LOCATION, LANG, KEYWORDS),
        "controversy_user[3]": prompts.controversy_user(TOPIC, DESC, INDUSTRY_3, LOCATION, LANG, KEYWORDS),
    }


def pinned() -> dict[str, str]:
    """README 「낸 글 지문」 표의 이름 → sha256."""
    rows = re.findall(r"^\| `([^`]+)` \| `([0-9a-f]{64})` \|$", README.read_text(encoding="utf-8"), re.M)
    return dict(rows)


def test_every_output_matches_its_pinned_fingerprint() -> None:
    got = {name: hashlib.sha256(text.encode("utf-8")).hexdigest() for name, text in outputs().items()}
    assert got == pinned()


@pytest.mark.parametrize("name", ["regulation_user[3]"])
def test_three_industries_keep_six_spaces(name: str) -> None:
    """W4: 산업이 둘 이상이면 industry_text 둘째 줄부터 0칸이라 dedent 가 6칸을 못 벗긴다."""
    text = outputs()[name]
    assert text.startswith("      [가변 입력]\n      industry_definition:\n      - 기준: SASB")
    assert "\n- 기준: GICS" in text  # 둘째 줄은 0칸
    assert "가상 설명 셋\n\n\n      geo_scope:" in text  # 끝 줄바꿈 + 빈 줄
    assert text.endswith("      topic_desc: 가상토픽 하나의 설명")


def test_one_industry_is_dedented() -> None:
    """W4: 산업이 하나면 벗긴다. industry_text 끝 줄바꿈으로 빈 줄이 하나 더 있다. 기간은 안 간다(W1)."""
    text = outputs()["regulation_user[1]"]
    assert text == (
        "[가변 입력]\nindustry_definition:\n- 기준: SASB, 산업명: 가상 산업 하나, 설명: 가상 설명 하나 — {괄호}\n\n\n"
        "geo_scope: 가상 범위(대한민국/EU)\npreferred_language: 한국어\n\n"
        "topic_name: 가상토픽 하나\ntopic_desc: 가상토픽 하나의 설명"
    )
    assert DATES not in text


def test_keywords_prefix_keeps_double_braces() -> None:
    """W3: 셀 20 접두는 f-문자열이 아니라 `{{`·`}}` 가 그대로 간다."""
    prefix = prompts.KEYWORDS_USER_PREFIX
    assert prefix.count("{{") == 3
    assert prefix.count("}}") == 3
    assert "\n{{\n" in prefix
    assert prefix.endswith("\n}}\n위 형식을 그대로 따르되, topic 값에는 내가 입력한 토픽명을 그대로 사용해.")


def test_keywords_user_carries_reprs_and_the_date_range() -> None:
    """W2: industry·topics 는 파이썬 repr. 기간은 키워드 호출에만 간다. 끝 빈칸 줄은 줄바꿈 하나."""
    text = outputs()["keywords_user[1]"]
    assert text == (
        "[가변 입력]\n"
        f"industry: {INDUSTRY_1!r}\n"
        "date_range: 2025-01-01~오늘까지\n"
        "main_language: 한국어\n"
        f"topics: {TOPICS!r}\n"
    )
    assert "'industry_name': '가상 산업 하나'" in text


def test_controversy_user_carries_the_industry_repr_and_no_dates() -> None:
    text = outputs()["controversy_user[3]"]
    assert text.startswith(f"[가변 입력]\nindustry_definition:\n{INDUSTRY_3!r}\n\ngeo_scope: ")
    assert f"keyword: {KEYWORDS}\ntopic_name: 가상토픽 하나\n" in text
    assert text.endswith("topic_desc: 가상토픽 하나의 설명\n")
    assert DATES not in text


def test_controversy_system_keeps_two_spaces_in_the_first_part() -> None:
    """W4: 셀 22 system 의 최소 들여쓰기는 0(뒤 [OUTPUT] 단락)이라 앞 단락에 2칸이 남는다."""
    system = prompts.CONTROVERSY_SYSTEM
    assert system.startswith("  너는 ESG 컨설턴트로서")
    assert "\n=====" in system
    assert "\n[OUTPUT] 출력 형식 강제 — JSON ONLY\n" in system


def test_regulation_prefix_keeps_the_bracket_typo() -> None:
    """W5: 「토픽(설명 포함}」."""
    assert "토픽(설명 포함}에 관련된" in prompts.REGULATION_USER_PREFIX
    assert prompts.REGULATION_USER_PREFIX.startswith("아래 정의한 산업을 기반으로,\n")


def test_regulation_systems_differ_only_in_block_8() -> None:
    """판끼리는 [8] 블록만 다르고, dedent 뒤 6칸이 벗겨진다(★c — 판의 최소 들여쓰기가 6 그대로)."""
    texts = {
        name: prompts.regulation_system(raw)
        for name, raw in (
            ("colab17", whitelists.WHITELIST_COLAB17),
            ("cell71", whitelists.WHITELIST_CELL71),
            ("cell73", whitelists.WHITELIST_CELL73),
        )
    }
    head_end = "[8] 신뢰할 수 있는 출처 리스트"
    tail_start = "[9] URL 출력 형식 규칙"
    heads = {t[: t.index(head_end)] for t in texts.values()}
    tails = {t[t.index(tail_start) :] for t in texts.values()}
    assert len(heads) == 1
    assert len(tails) == 1
    assert len(set(texts.values())) == 3
    for text in texts.values():
        assert text.startswith("너는 ESG 및 규제 전문가이며")
        assert text.endswith("국가별로 작성한다.")
        assert "\n    1. 한국\n" in text  # 블록 안 10칸이 6칸 벗겨져 4칸
