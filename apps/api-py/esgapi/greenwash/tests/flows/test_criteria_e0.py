"""flows/criteria_e0: 기본 판 조립 == 엔진 글(바이트), 줄 끄기·빈 구분·글 고치기는 그 줄만, 주입은 글자 그대로, 받기의
거절과 문장, 판 묶음 값. 대조 기준은 엔진의 글 하나다(engines/e0/prompts.py — 코랩 사본·원문 사본 없음, MARC-ENT-310).

기대 글은 조립 함수를 쓰지 않고 엔진 글의 줄 자리(LINE)에서 짓는다. 실제 AI 호출 0.
"""

import copy
import difflib
import hashlib
from collections.abc import Callable
from itertools import pairwise
from typing import Any, cast, get_args

import pytest

from esgapi.greenwash.contracts.criteria_shapes import GreenwashCriteria, GreenwashCriterionId
from esgapi.greenwash.engines.e0.checker import GWConfig
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows import criteria_e0 as c

ENGINE_SHA256 = "1eb626446da6942b93aca4991f4057de2e15a5b66adf167ea226c8399ab49b0f"
"""엔진 EVAL(PROMPT_VERSION 판)의 sha256 — 발주서 ★A(1,872자, 3,722바이트, 49줄)."""
ENGINE_SHA256_X = "4750ce99518f924269d17a8332785f1044be195520e58d187fd1ea2d2106c937"
"""판 글자를 "X" 로 지은 엔진 EVAL 의 sha256."""

ROW_IDS = [
    "keyword-ghg",
    "keyword-exclusion",
    "evidence-quantity",
    "evidence-baseline",
    "evidence-boundary",
    "evidence-offset",
    "high-1",
    "high-2",
    "high-3",
    "high-4",
    "mid-1",
    "exception-1",
    "exception-2",
    "exception-3",
    "exception-4",
]
LINE = dict(zip(ROW_IDS, [14, 15, 17, 18, 19, 20, 24, 25, 26, 27, 30, 34, 35, 36, 37], strict=True))
"""줄 id → 엔진 EVAL 을 "\\n" 으로 나눈 줄 자리(0부터). 조립 함수와 따로 센 것."""
CATEGORY_IDS = {
    "targetKeyword": ROW_IDS[0:2],
    "coreEvidence": ROW_IDS[2:6],
    "high": ROW_IDS[6:10],
    "mid": ROW_IDS[10:11],
    "exception": ROW_IDS[11:15],
}
HEADS = ("[온실가스/배제용어(강화 규칙)]", "[등급]", "▶ High", "▶ Mid", "[예외 조항 (Safe Harbor Rules)]")


def engine(version: str = PROMPT_VERSION) -> str:
    return default_prompts(version).eval_system_prompt


def engine_lines() -> list[str]:
    return engine().split("\n")


def criteria() -> dict[str, Any]:
    return cast("dict[str, Any]", c.default_criteria())


def row(value: dict[str, Any], row_id: str) -> dict[str, Any]:
    return next(r for r in value["rows"] if r["id"] == row_id)


def build(value: dict[str, Any]) -> str:
    return c.build_eval_prompt(cast("GreenwashCriteria", value), PROMPT_VERSION)


def opcodes(before: list[str], after: list[str]) -> list[tuple[str, int, int, int, int]]:
    return [op for op in difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_opcodes() if op[0] != "equal"]


def blank_pairs(lines: list[str]) -> int:
    return sum(1 for a, b in pairwise(lines) if a == "" and b == "")


# ── 1. 바이트 같음 ──


@pytest.mark.parametrize(("version", "sha"), [(PROMPT_VERSION, ENGINE_SHA256), ("X", ENGINE_SHA256_X)])
def test_the_default_criteria_build_the_engine_text_byte_for_byte(version: str, sha: str) -> None:
    built = c.build_eval_prompt(c.default_criteria(), version).encode("utf-8")
    assert built == engine(version).encode("utf-8")
    assert hashlib.sha256(built).hexdigest() == sha
    if version == PROMPT_VERSION:
        assert (len(engine()), len(built), len(engine().split("\n"))) == (1872, 3722, 49)


def test_the_engine_version_is_the_checker_default() -> None:
    """judge 가 짓는 pack 의 판 글자(checker 의 GWConfig)와 엔진 상수가 같다 — 다르면 기본 판 요청이 갈린다."""
    assert GWConfig().prompt_version == PROMPT_VERSION


def test_the_default_criteria_are_new_every_time() -> None:
    first = c.default_criteria()
    first["rows"][0]["enabled"] = False
    cast("list[str]", first["rows"][0]["terms"]).append("x")
    first["version"] = "changed"
    assert c.default_criteria() == c.accept_criteria(c.default_criteria())
    assert c.build_eval_prompt(c.default_criteria(), PROMPT_VERSION) == engine()


def test_the_default_rows_are_the_engine_lines() -> None:
    lines = engine_lines()
    for r in c.default_criteria()["rows"]:
        assert c.row_line(r) == lines[LINE[r["id"]]]
        assert (r["enabled"], r["guideline"]) == (True, None)
    assert all(
        lines[LINE[i]].startswith("-") and not lines[LINE[i]].startswith("- ") for i in CATEGORY_IDS["exception"]
    )


# ── 2. 묶음 ──


def test_the_pack_changes_only_the_eval_text() -> None:
    for version in (PROMPT_VERSION, "X"):
        assert c.eval_pack(c.default_criteria(), version) == default_prompts(version)
    edited = criteria()
    row(edited, "high-2")["text"] = "지어낸 기준 글"
    pack, base = c.eval_pack(cast("GreenwashCriteria", edited), PROMPT_VERSION), default_prompts(PROMPT_VERSION)
    assert pack.eval_system_prompt == build(edited) != base.eval_system_prompt
    for name in ("detect_system_prompt", "repair_fix_prompt", "low_only_prompt"):
        assert getattr(pack, name).encode("utf-8") == getattr(base, name).encode("utf-8")


# ── 3. 줄 하나 끄기 ──


@pytest.mark.parametrize("row_id", ROW_IDS)
def test_turning_one_row_off_drops_that_line_only(row_id: str) -> None:
    value = criteria()
    row(value, row_id)["enabled"] = False
    before, after = engine_lines(), build(value).split("\n")
    assert opcodes(before, after) == [("delete", LINE[row_id], LINE[row_id] + 1, LINE[row_id], LINE[row_id])]
    assert after == before[: LINE[row_id]] + before[LINE[row_id] + 1 :]


# ── 3a. 빈 구분(MARC-ENT-329): 절 머리는 남고 줄만 빠진다 ──

EMPTY_CASES = {
    "mid": ["mid"],
    "keywords": ["targetKeyword"],
    "exceptions": ["exception"],
    "high": ["high"],
    "evidence": ["coreEvidence"],
    "all": list(CATEGORY_IDS),
}


@pytest.mark.parametrize("case", list(EMPTY_CASES))
def test_an_empty_category_keeps_its_head_and_adds_nothing(case: str) -> None:
    off = [i for category in EMPTY_CASES[case] for i in CATEGORY_IDS[category]]
    value = criteria()
    for row_id in off:
        row(value, row_id)["enabled"] = False
    gone = {LINE[i] for i in off}
    want = "\n".join(line for n, line in enumerate(engine_lines()) if n not in gone)
    built = c.build_eval_prompt(c.accept_criteria(value), PROMPT_VERSION)
    assert built.encode("utf-8") == want.encode("utf-8")
    lines = built.split("\n")
    assert all(head in lines for head in HEADS)
    assert not any("없음" in line for line in lines)
    assert blank_pairs(lines) == blank_pairs(engine_lines()) == 0
    assert built.count("[PromptVersion: ") == 1


def test_an_empty_mid_leaves_a_blank_line_under_its_head() -> None:
    value = criteria()
    row(value, "mid-1")["enabled"] = False
    lines = build(value).split("\n")
    at = lines.index("▶ Mid")
    assert lines[at + 1 : at + 3] == ["", "[예외 조항 (Safe Harbor Rules)]"]
    keywords = criteria()
    for row_id in CATEGORY_IDS["targetKeyword"]:
        row(keywords, row_id)["enabled"] = False
    lines = build(keywords).split("\n")
    intro = lines.index("다음 키워드가 문장에 포함되면 '온실가스/배제용어 Claim'으로 간주합니다:")
    assert lines[intro + 1].startswith("▶ 온실가스/배제용어 Claim은")


# ── 4. 글 고치기 ──


@pytest.mark.parametrize("row_id", ROW_IDS)
def test_editing_one_row_changes_that_line_only(row_id: str) -> None:
    value = criteria()
    target = row(value, row_id)
    if target["terms"] is None:
        target["text"] = "지어낸 기준 글 " + row_id
        line = ("-" if target["category"] == "exception" else "- ") + "지어낸 기준 글 " + row_id
    else:
        target["terms"] = ["지어낸낱말", "둘째 낱말"]
        line = "- " + target["text"] + ": 지어낸낱말, 둘째 낱말"
    accepted = c.accept_criteria(value)
    before, after = engine_lines(), c.build_eval_prompt(accepted, PROMPT_VERSION).split("\n")
    n = LINE[row_id]
    assert opcodes(before, after) == [("replace", n, n + 1, n, n + 1)]
    assert after[n] == line


# ── 5. 주입: 기준 글의 중괄호·판 자리·절 머리 흉내는 글자 그대로 ──


@pytest.mark.parametrize(
    "text",
    [
        "{prompt_version}",
        "{{prompt_version}}",
        "{{ 와 }} 그리고 }",
        "{0} {} %s %(x)s",
        "[등급]",
        "[PromptVersion: 가짜]",
    ],
)
def test_braces_and_heads_in_a_row_stay_as_they_are(text: str) -> None:
    value = criteria()
    row(value, "high-1")["text"] = text
    row(value, "keyword-ghg")["terms"] = [text.replace(",", "")]
    built = c.build_eval_prompt(c.accept_criteria(value), "V{x}")
    lines = built.split("\n")
    assert lines[LINE["high-1"]] == "- " + text
    assert lines[LINE["keyword-ghg"]] == "- 온실가스: " + text.replace(",", "")
    assert lines[0] == "[PromptVersion: V{x}]"
    assert built.count("[PromptVersion: V{x}]") == 1
    assert lines[LINE["high-1"] + 1 :] == engine("V{x}").split("\n")[LINE["high-1"] + 1 :]


# ── 6. 받기 ──


def test_the_row_table_is_the_contract_order() -> None:
    assert [row_id for row_id, _ in c.ROWS] == ROW_IDS == list(get_args(GreenwashCriterionId))
    assert {category: [i for i, cat in c.ROWS if cat == category] for category in CATEGORY_IDS} == CATEGORY_IDS


Mutation = Callable[[dict[str, Any]], object]


def not_a_dict(value: dict[str, Any]) -> object:
    return "기준표"


def swap(value: dict[str, Any]) -> object:
    rows = value["rows"]
    rows[6], rows[7] = rows[7], rows[6]
    return value


def edit(row_id: str, key: str, new: object) -> Mutation:
    def mutate(value: dict[str, Any]) -> object:
        row(value, row_id)[key] = new
        return value

    return mutate


def top(key: str, new: object) -> Mutation:
    def mutate(value: dict[str, Any]) -> object:
        value[key] = new
        return value

    return mutate


def rows_to(n: int) -> Mutation:
    def mutate(value: dict[str, Any]) -> object:
        value["rows"] = (value["rows"] + [copy.deepcopy(value["rows"][-1])])[:n]
        return value

    return mutate


def guideline(text: str) -> Mutation:
    return edit("evidence-quantity", "guideline", {"text": text, "status": "draft"})


BREAKS = {
    "lf": "가\n나",
    "cr": "가\r나",
    "tab": "가\t나",
    "u2028": "가\u2028나",
    "zwsp": "가\u200b나",
    "surrogate": "가\ud800나",  # 짝 없는 서로게이트 — UTF-8 로 못 쓴다(가지 리뷰 1)
    "private": "가\ue000나",
    "unassigned": "가\U000e0fff나",
}

REFUSED: list[Any] = [
    pytest.param(not_a_dict, "CRITERIA_SHAPE", id="not-a-dict"),
    pytest.param(top("extra", 1), "CRITERIA_SHAPE", id="unknown-key"),
    pytest.param(edit("high-1", "id", "high-9"), "CRITERIA_SHAPE", id="unknown-id"),
    pytest.param(top("schemaVersion", "greenwash.criteria@2"), "CRITERIA_SCHEMA_VERSION", id="schema-version"),
    pytest.param(top("version", ""), "CRITERIA_VERSION", id="version-empty"),
    pytest.param(top("version", "-v1"), "CRITERIA_VERSION", id="version-head"),
    pytest.param(top("version", "a b"), "CRITERIA_VERSION", id="version-space"),
    pytest.param(top("version", "v" * 65), "CRITERIA_VERSION", id="version-65"),
    pytest.param(top("version", "v1\n"), "CRITERIA_VERSION", id="version-newline"),
    pytest.param(rows_to(14), "CRITERIA_ROWS_FIXED", id="rows-14"),
    pytest.param(rows_to(16), "CRITERIA_ROWS_FIXED", id="rows-16"),
    pytest.param(swap, "CRITERIA_ROW_ORDER", id="ids-swapped"),
    pytest.param(edit("evidence-baseline", "order", 9), "CRITERIA_ROW_ORDER", id="order-wrong"),
    pytest.param(edit("high-1", "verdict", "Mid"), "CRITERIA_ROW_KIND", id="verdict-pair"),
    pytest.param(edit("exception-1", "verdict", "High"), "CRITERIA_ROW_KIND", id="verdict-pair-exception"),
    pytest.param(edit("high-1", "category", "mid"), "CRITERIA_ROW_KIND", id="category-pair"),
    pytest.param(edit("keyword-ghg", "text", "탄소 낱말"), "CRITERIA_KEYWORD_NAME", id="keyword-name"),
    pytest.param(edit("keyword-ghg", "terms", []), "CRITERIA_TERMS_COUNT", id="terms-0"),
    pytest.param(edit("keyword-ghg", "terms", None), "CRITERIA_TERMS_COUNT", id="terms-null"),
    pytest.param(edit("keyword-ghg", "terms", [f"낱말{n}" for n in range(31)]), "CRITERIA_TERMS_COUNT", id="terms-31"),
    pytest.param(edit("keyword-ghg", "terms", ["가" * 31]), "CRITERIA_TERM_LENGTH", id="term-31-chars"),
    pytest.param(edit("keyword-ghg", "terms", ["탄소", "  "]), "CRITERIA_TERM_LENGTH", id="term-blank"),
    pytest.param(edit("keyword-ghg", "terms", ["탄소,배출"]), "CRITERIA_TERM_COMMA", id="term-comma"),
    pytest.param(edit("keyword-ghg", "terms", ["탄소", " 탄소 "]), "CRITERIA_TERM_DUPLICATE", id="term-duplicate"),
    pytest.param(edit("high-1", "terms", ["탄소"]), "CRITERIA_TERMS_NOT_ALLOWED", id="terms-off-keyword"),
    pytest.param(edit("high-1", "text", ""), "CRITERIA_TEXT_LENGTH", id="text-empty"),
    pytest.param(edit("high-1", "text", "   "), "CRITERIA_TEXT_LENGTH", id="text-blank"),
    pytest.param(edit("high-1", "text", "가" * 301), "CRITERIA_TEXT_LENGTH", id="text-301"),
    *[
        pytest.param(edit("mid-1", "text", s), "CRITERIA_TEXT_MULTILINE", id=f"text-{name}")
        for name, s in BREAKS.items()
    ],
    *[
        pytest.param(edit("keyword-exclusion", "terms", ["친환경", s]), "CRITERIA_TEXT_MULTILINE", id=f"term-{name}")
        for name, s in BREAKS.items()
    ],
    *[pytest.param(guideline(s), "CRITERIA_TEXT_MULTILINE", id=f"guideline-{name}") for name, s in BREAKS.items()],
    pytest.param(guideline("가" * 201), "CRITERIA_GUIDELINE_LENGTH", id="guideline-201"),
    pytest.param(guideline(" "), "CRITERIA_GUIDELINE_LENGTH", id="guideline-blank"),
]


@pytest.mark.parametrize(("mutate", "code"), REFUSED)
def test_accept_refuses_with_its_sentence(mutate: Mutation, code: str) -> None:
    with pytest.raises(c.CriteriaRejected) as refused:
        c.accept_criteria(mutate(criteria()))
    assert refused.value.code == code
    assert str(refused.value) == c.MESSAGES[code]
    assert isinstance(refused.value, ValueError)


def test_the_sentences_are_one_haeyo_sentence_each() -> None:
    assert c.MESSAGES["CRITERIA_ROWS_FIXED"] == "기준표의 줄은 15줄 그대로여야 해요"
    assert c.MESSAGES["CRITERIA_TEXT_LENGTH"] == "기준 글은 1~300자로 써 주세요"
    assert c.MESSAGES["CRITERIA_TEXT_MULTILINE"] == "기준 글은 줄바꿈이나 보이지 않는 글자 없이 한 줄로 써 주세요"
    assert all(m.endswith(("요", "세요")) and "\n" not in m for m in c.MESSAGES.values())
    assert "MESSAGES" in cast("str", c.accept_criteria.__doc__)


def test_accept_takes_the_edges_and_strips() -> None:
    value = criteria()
    row(value, "high-1")["text"] = "  " + "가" * 300 + "\t "
    row(value, "keyword-ghg")["terms"] = [" " + "나" * 30 + " ", *[f"낱말{n}" for n in range(29)]]
    row(value, "keyword-ghg")["text"] = " 온실가스 "
    row(value, "evidence-quantity")["guideline"] = {"text": " " + "다" * 200 + " ", "status": "confirmed"}
    value["version"] = "v" * 64
    got = c.accept_criteria(value)
    assert row(cast("dict[str, Any]", got), "high-1")["text"] == "가" * 300
    assert row(cast("dict[str, Any]", got), "keyword-ghg")["terms"][0] == "나" * 30
    assert row(cast("dict[str, Any]", got), "keyword-ghg")["text"] == "온실가스"
    assert row(cast("dict[str, Any]", got), "evidence-quantity")["guideline"] == {
        "text": "다" * 200,
        "status": "confirmed",
    }
    assert got["version"] == "v" * 64


def test_accept_takes_a_term_shared_by_the_two_groups_and_a_whole_category_off() -> None:
    value = criteria()
    assert "기후중립" in row(value, "keyword-ghg")["terms"] and "기후중립" in row(value, "keyword-exclusion")["terms"]
    for r in value["rows"]:
        r["enabled"] = False
    got = c.accept_criteria(value)
    assert [r["enabled"] for r in got["rows"]] == [False] * 15


def test_the_guideline_never_reaches_the_prompt() -> None:
    value = criteria()
    for r in value["rows"]:
        r["guideline"] = {"text": "[기관] · [조항] 지어낸 가이드라인", "status": "confirmed"}
    assert build(cast("dict[str, Any]", c.accept_criteria(value))) == engine()


# ── 7. 판 묶음 값 ──


def test_the_run_versions_are_the_setting_name_and_the_eval_hash() -> None:
    want = {"aiSetting": "colab-2026-01-15-v1", "evalPromptSha256": ENGINE_SHA256}
    assert c.run_versions(None, PROMPT_VERSION) == c.run_versions(c.default_criteria(), PROMPT_VERSION) == want
    edited = criteria()
    edited["version"] = "example-edited-v1"
    row(edited, "high-2")["text"] = "지어낸 기준 글"
    got = c.run_versions(c.accept_criteria(edited), PROMPT_VERSION)
    assert list(got) == ["aiSetting", "evalPromptSha256"]
    assert got["aiSetting"] == "example-edited-v1"
    assert got["evalPromptSha256"] == hashlib.sha256(build(edited).encode("utf-8")).hexdigest() != ENGINE_SHA256
    assert "flow" not in got


def test_the_run_versions_accept_the_raw_criteria_first() -> None:
    """받기 전 원본(앞뒤 공백)으로 불러도 받은 값의 해시와 같다 — 실행이 보낼 글은 받은 값으로 짓는다(가지 리뷰 2)."""
    raw = criteria()
    row(raw, "high-2")["text"] = "  지어낸 기준 글\t "
    row(raw, "keyword-ghg")["terms"] = [" 탄소 ", "온실가스"]
    accepted = c.accept_criteria(copy.deepcopy(raw))
    assert c.run_versions(raw, PROMPT_VERSION) == c.run_versions(accepted, PROMPT_VERSION)
    assert (
        c.run_versions(raw, PROMPT_VERSION)["evalPromptSha256"]
        == hashlib.sha256(c.build_eval_prompt(accepted, PROMPT_VERSION).encode("utf-8")).hexdigest()
    )
    bad = criteria()
    row(bad, "high-1")["text"] = "abc\ud800"
    with pytest.raises(c.CriteriaRejected) as refused:
        c.run_versions(bad, PROMPT_VERSION)
    assert refused.value.code == "CRITERIA_TEXT_MULTILINE"
