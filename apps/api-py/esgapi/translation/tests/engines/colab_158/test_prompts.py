"""프롬프트 글과 봉투(발주서 §3 S4·개정 2 N-B5). core.llm 은 prompts(parse_template·render_prompt·PackagePromptStore —
순수, 호출 0)만 쓴다.

- 평 문자열 상수 열다섯(과 함수 안의 평 문자열 일곱)은 sha256 이 `prompts/README.md` 표와 같다. 표의 값은 러너가
  읽기판에서
  잰 것이다(엔진 상수에서 잰 값이 아니다) — `scripts/section4-TR1a.sh` 16단계가 실행 때 읽기판과 다시 견준다.
- f-문자열 자리(user 글 함수·셀 42·44 의 조립)는 아래 고정 입력으로 낸 글의 sha256 이 기대값과 같다. 기대값은 러너가
  읽기판의 f-문자열을 같은 값으로 풀어 잰 것이다 — **러너 손셈, TR1-o 전 미검**(코랩과의 바이트 대조는 esg-lab TR1-o).
- 봉투 열 개는 정확히 `=== system ===\\n{{system}}\\n=== user ===\\n{{user}}\\n` 이고 넘긴 글을 한 바이트도
  바꾸지 않는다.
"""

import hashlib
import re
from pathlib import Path

import pytest

from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id, render_prompt
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.engines.colab_158.prompts import Site
from esgapi.translation.tools.llm_bridge import PROMPT_VERSIONS, prompt_id

PROMPTS_DIR = Path(prompts.__file__).parents[2] / "prompts"
ENVELOPE = "=== system ===\n{{system}}\n=== user ===\n{{user}}\n"

PLAIN_CONSTS = (
    "TERMINOLOGY_CONSISTENCY_PROMPT",
    "SUBJECT_PRONOUN_PROMPT",
    "NUMBER_UNIT_PROMPT",
    "FRAGMENTARY_CONTENT_PROMPT",
    "OFFICIAL_REPORT_STYLE_PROMPT",
    "LEXICAL_GUARDRAILS_PROMPT",
    "ANTI_MACHINE_TRANSLATION_PROMPT",
    "BILINGUAL_EDITORIAL_POLISH_PROMPT",
    "GENERIC_EDITORIAL_QA_PROMPT",
    "CEO_MESSAGE_TONE",
    "STORY_TONE",
    "GENERAL_TONE",
    "STYLE_A_PROMPT",
    "STYLE_B_PROMPT",
    "QA_SYSTEM_PROMPT",
)
INNER_CONSTS = (
    "TERMINOLOGY_NOTE",
    "TABLE_TRANSLATION_RULES",
    "GLOSSARY_REPAIR_TABLE_RULE",
    "GLOSSARY_REPAIR_STRUCTURE_RULE",
    "KOREAN_REPAIR_TABLE_RULE",
    "KOREAN_REPAIR_STRUCTURE_RULE",
    "CRITICAL_REPAIR_MODE",
)


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def readme_table() -> dict[str, str]:
    out: dict[str, str] = {}
    for line in (PROMPTS_DIR / "README.md").read_text(encoding="utf-8").splitlines():
        m = re.match(r"^\| `([A-Z_]+)` \|.*\| `([0-9a-f]{64})` \|$", line)
        if m:
            out[m.group(1)] = m.group(2)
    return out


def test_the_readme_pins_fifteen_plain_and_seven_inner_constants() -> None:
    assert set(readme_table()) == {*PLAIN_CONSTS, *INNER_CONSTS}


@pytest.mark.parametrize("name", [*PLAIN_CONSTS, *INNER_CONSTS])
def test_the_constant_is_the_value_measured_in_the_reading_copy(name: str) -> None:
    value = getattr(prompts, name)
    assert isinstance(value, str)
    assert sha(value) == readme_table()[name]


def test_the_plain_constants_start_with_the_newline_after_the_triple_quote() -> None:
    """N-B5 (1): 값은 `X = \"\"\"` 다음 줄부터라 앞 줄바꿈을 품는다 — R/5385 의 QA_SYSTEM_PROMPT 만 같은 줄에서 시작."""
    starts = {name: getattr(prompts, name).startswith("\n") for name in PLAIN_CONSTS}
    assert [name for name, s in starts.items() if not s] == ["QA_SYSTEM_PROMPT"]


def test_sites_and_max_tokens_are_the_colab_call_sites() -> None:
    """§0-1 의 호출 자리 열(R/2253·2286·2344·2514·2659·3005·3131·5325·6707·6752)과 각 자리의 max_tokens."""
    assert dict(prompts.MAX_TOKENS) == {
        "cell": 1024,
        "table-batch": 8192,
        "section": 4096,
        "polish": 4096,
        "editorial-qa": 4096,
        "glossary-repair": 4096,
        "korean-repair": 4096,
        "review": 4096,
        "autofix": 4096,
        "autofix-korean": 4096,
    }
    assert tuple(prompts.MAX_TOKENS) == prompts.SITES


def test_there_is_one_envelope_per_site_and_nothing_else() -> None:
    folders = {p.name for p in PROMPTS_DIR.iterdir() if p.is_dir() and p.name != "__pycache__"}
    assert folders == set(prompts.SITES)
    for site in prompts.SITES:
        names = ["1.md", "2.md"] if PROMPT_VERSIONS[site] == 2 else ["1.md"]
        assert sorted(p.name for p in (PROMPTS_DIR / site).iterdir()) == names


CACHED_SITES = ("cell", "table-batch", "section", "polish", "editorial-qa", "glossary-repair", "korean-repair")
CACHED_ENVELOPE = "=== system cache ===\n{{system}}\n=== user ===\n{{user}}\n"


def test_the_seven_page_system_sites_use_the_cache_envelope_and_the_rest_stay_at_1() -> None:
    """MARC-ISSUE-213 (Q10): 쪽 system 을 싣는 일곱 자리는 @2(system 에 캐시 표시), 검수·자동수정 셋은 @1.
    @1 파일은 남는다."""
    assert {site for site, version in PROMPT_VERSIONS.items() if version == 2} == set(CACHED_SITES)
    assert {site for site, version in PROMPT_VERSIONS.items() if version == 1} == {
        "review",
        "autofix",
        "autofix-korean",
    }
    assert tuple(PROMPT_VERSIONS) == prompts.SITES
    for site in CACHED_SITES:
        assert (PROMPTS_DIR / site / "2.md").read_bytes() == CACHED_ENVELOPE.encode()


@pytest.mark.parametrize("site", prompts.SITES)
def test_the_envelope_is_exactly_the_two_variables(site: str) -> None:
    assert (PROMPTS_DIR / site / "1.md").read_bytes() == ENVELOPE.encode()


@pytest.mark.parametrize("site", prompts.SITES)
def test_the_envelope_changes_no_byte(site: Site) -> None:
    system = "\n가상 system 첫 줄  \n\n둘째 줄\n\n"
    user = "\n\n[PAGE 3]\n가상 user\n   "
    template = PackagePromptStore().get(parse_prompt_id(prompt_id(site)))
    out = render_prompt(template, {"system": system, "user": user})
    assert len(out.system) == 1
    assert out.system[0].cache is (site in CACHED_SITES)
    assert (out.system[0].text, out.user) == (system, user)


# ── f-문자열 자리: 러너 손셈(TR1-o 전 미검) ──

V = {
    "glossary_text": "- 가상용어 -> Virtual Term\n- 탄소 -> carbon",
    "text": "가상 셀 글",
    "payload": '{"items": []}',
    "section_text": "[BLOCK 1]\n가상 본문",
    "source_text": "가상 원문",
    "translated_text": "Virtual draft",
    "violation_text": "- 가 -> A",
    "table_rule": "\nRule X\n",
    "leftover_text": "- 남은 글",
    "variant_label": "A",
    "source_for_review": "[PAGE 3]\n가상",
    "annotation_hint_text": "- 주석",
    "translated_for_model": "[PAGE 3]\nVirtual",
    "issue_json": "[]",
    "source_page_text": "[PAGE 3]\n가상",
    "current_page_text": "[PAGE 3]\nVirtual",
    "remaining_text": "- 가상",
    "page_num": 3,
}
"""지어낸 고정 입력. 자리마다 그 함수의 인자만 꺼내 쓴다."""

F_STRING_SHAS = {
    "cell_user": "d61173555e9ae6ef6325071ebe4b1068300bd578eadeacff0ebf9599b55de250",  # R/2257
    "table_batch_user": "0bcd0aa87dcba49f295160ff5db7f7fdf86e844d2ff4e6c6843d47873620275e",  # R/2300
    "section_user": "f707695da07a14feffd17a7c08d5f3ca5d027fc80f4b0f8d76ce5ff318598cd4",  # R/2348
    "polish_user": "782eeda90e00101c56e651095f73cf579ce736d82c91895e26d9eb393c2c34c1",  # R/2518
    "editorial_qa_user": "25d9409f150c1c3889bd79a5d8c810aaa5a9be9ee3a926756cc20ff87bcd3e4f",  # R/2663
    "glossary_repair_user": "11ec58c337f153f9fc879c5367b7196ea0158ddcfc5788dc7aeda58b1e832674",  # R/3009
    "korean_repair_user": "bd3b1d15f2c13f4e6d25d8ed4052e4763f1970645d16edb5c3c5d2ef00a48c45",  # R/3141
    "review_user": "acab814fad71bc4c994fae50abbc9e3b3a64ca3679fe8920aaf153b580a743e0",  # R/5277
    "autofix_system": "ec24f38bb42a218f2838c86d4492942033c76ee32f39e7c823651f4dd8833553",  # R/6665
    "autofix_user": "99360daee8fe09196ce48c69730e3266673c12b81762f90e0aab1cbd9ec9bb21",  # R/6684
    "autofix_korean_system": "cad3924caf565fdf02d5b9c6bea64b11236125331e347877742dd52684495216",  # R/6755
    "autofix_korean_user": "f360645423912994631ceb20ba9ac13bbe5a3b0343f6154c4a039668eacdbb3c",  # R/6765
}


@pytest.mark.parametrize("name", sorted(F_STRING_SHAS))
def test_the_f_string_site_gives_the_hand_worked_text(name: str) -> None:
    fn = getattr(prompts, name)
    params = fn.__code__.co_varnames[: fn.__code__.co_argcount]
    assert sha(fn(**{k: V[k] for k in params})) == F_STRING_SHAS[name]


def test_page_numbers_drop_out_of_the_source_heading_when_absent() -> None:
    """R/2361·2531·2673 `{f' - PAGE {page_num}' if page_num else ''}` — 쪽 번호가 없으면(표 구획은 쪽 번호 None)
    꼬리 없음. 0 도 거짓이다."""
    assert "[Source text - PAGE 3]\n" in prompts.section_user("g", "s", 3)
    assert "[Source text]\n" in prompts.section_user("g", "s", None)
    assert "[Original Korean source]\n" in prompts.polish_user("g", "s", "t", None)
    assert "[Original Korean source - PAGE 0]" not in prompts.editorial_qa_user("g", "s", "t", 0)  # 0 도 거짓


COMPANY_SHAS = {
    ("ceo_message", False): (
        "a25d63dc92f77c550a9863996b2e3aac3a5d7c424f17652016f2df21e1541521",
        "3c6fcbb67f4f22f2879c97e3319f7c5e6b6cdd5bb22c6f8b49b49de514d70312",
    ),
    ("story", False): (
        "0f635be263ae687136b9d5f2df38514fbeb4d8b8e03237321ed23024fedac82a",
        "a89d328f037727b48ac7be248737bde3d8dd185385c9673dfcb84e77302957dc",
    ),
    ("general", False): (
        "04539ffc24171334624d151e7e8cf086a33793ec75019301ad8a3a01e7ee5375",
        "c7c7c73785950b8dd2806a01ed4a90cef08e0564cc9efc0704b5b2eab7f36980",
    ),
    ("ceo_message", True): (
        "9605e28fcd0a2cbc9c558d7b49a0ae91091a52b4dc4df8885deb082f23a59047",
        "ad54cbfd77961901bddfb457e9bcee0b9be82d4a655da4f611b7a9d0ef326640",
    ),
    ("story", True): (
        "f30be56bc876f6b44c79b747c535dbce7135c4e274a9c7b86467256c8fc84c1e",
        "03764fd4344cbc46f40e3bf91f09d9b6edc44dbae4085bbce67da9d5be515e47",
    ),
    ("general", True): (
        "2d6fb9996de2d5bc0a1efd9350b61b783ce652e5641ebff2c733a9ee84ca1138",
        "0a4fc79a3ce367e48b39de67d4fcaa1758216852e9368d024784d0cc0142c923",
    ),
}
"""(파트, peer 글 있음) → (셀 42 `build_company_style_prompt` R/1912-2012 의 글,
셀 44 `build_system_prompt` R/2085 의 글)."""
PEER = "Peer A writes in short sentences.\n"


@pytest.mark.parametrize(("part", "with_peer"), sorted(COMPANY_SHAS))
def test_the_company_style_and_system_prompt_are_the_hand_worked_text(part: str, with_peer: bool) -> None:
    company = prompts.build_company_style_prompt(
        part, "가상고객사", "가상 업종", "GRI, ISSB", PEER if with_peer else None
    )
    system = prompts.build_system_prompt(company, "GRI, ISSB")
    assert (sha(company), sha(system)) == COMPANY_SHAS[(part, with_peer)]


def test_base_system_prompt_is_the_hand_worked_text() -> None:
    """셀 44 `BASE_SYSTEM_PROMPT`(R/2034-2079) — 코랩은 정의 때 INDUSTRY_STANDARDS 를 박는 f-문자열."""
    base = prompts.base_system_prompt("GRI, ISSB")
    assert sha(base) == "5141215d81c7474ecea017e273a8046be5f73a2712efc241a7ea0ccfd68aefe6"
    assert prompts.build_system_prompt("", "GRI, ISSB") == base


def test_an_unknown_part_takes_the_general_tone() -> None:
    """R/1919 `TONE_PRESETS.get(part, GENERAL_TONE)`."""
    assert prompts.build_company_style_prompt("x", "a", "b", "c", None) == prompts.build_company_style_prompt(
        "general", "a", "b", "c", None
    )


def test_w6_the_fixed_terminology_heading_is_followed_by_nothing() -> None:
    """W6(R/2006-2008): 「Fixed terminology …:」 머리 뒤가 비었다 — FIXED_TERMINOLOGY 가 주석 처리된 채(R/707-716)."""
    company = prompts.build_company_style_prompt("general", "가상고객사", "가상 업종", "GRI", None)
    # 머리 + 빈 줄 + 빈 peer 구획 + 빈 참고 구획 + 다음 구획의 앞 빈 줄 둘 = 줄바꿈 여섯
    assert (
        "Fixed terminology and company-specific expressions:\n\n\n\n\n\nSubject pronoun consistency guidance:"
        in company
    )


def test_w5_the_peer_text_goes_in_as_is_with_its_placeholders() -> None:
    """W5(R/1060-1088): 코랩은 peer 글의 자리표({KOREAN_SOURCE} 등)를 채우지 않은 채 system 에 넣는다 —
    우리도 받은 글 그대로."""
    peer = "Rewrite {KOREAN_SOURCE} as [REVISED ENGLISH]\n"
    company = prompts.build_company_style_prompt("general", "가상고객사", "가상 업종", "GRI", peer)
    assert "\n\nPeer group report style guidance:\nRewrite {KOREAN_SOURCE} as [REVISED ENGLISH]\n" in company


def test_the_page_system_prompt_is_company_style_terminology_note_and_style() -> None:
    """R/3280-3286."""
    sp = prompts.page_system_prompt("CS", prompts.STYLE_B_PROMPT, "GRI")
    assert (
        sp
        == prompts.base_system_prompt("GRI")
        + "\n\n"
        + ("CS\n\n" + prompts.TERMINOLOGY_NOTE + "\n\n" + prompts.STYLE_B_PROMPT).strip()
    )


def test_system_tails_are_joined_the_colab_way() -> None:
    """R/2289(+ 글자 그대로)·R/2509·2654(strip 한 둘을 빈 줄로)·R/3134(+ 글자 그대로)."""
    sp = "\nSP\n"
    assert prompts.table_batch_system(sp) == sp + prompts.TABLE_TRANSLATION_RULES
    assert prompts.korean_repair_system(sp) == sp + prompts.CRITICAL_REPAIR_MODE
    assert prompts.polish_system(sp) == "SP\n\n" + prompts.BILINGUAL_EDITORIAL_POLISH_PROMPT.strip()
    assert prompts.editorial_qa_system(sp) == "SP\n\n" + prompts.GENERIC_EDITORIAL_QA_PROMPT.strip()
