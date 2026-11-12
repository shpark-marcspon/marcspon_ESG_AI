"""outputs/edits.py: 결과 글 칸 고침의 순수 규칙(밴드 IRS3 §2-2·§2-3·§4) — 주소 허용 꼴 · 바른 주소 · 퍼짐 묶음 ·
값 규칙 · url 겹침·비우기 · 덮기(결정적·꼴 보존·원본 그대로) · GET edits 목록 · ★C 웹 mergedItems 와 같은 묶음.

본문은 result2-sample.json(지어낸 「가상…」 합성)의 1부·설정에 2부를 손으로 지어 끼운 것이다(EDIT_BODY 아래 그림).
실재 기업·견본 값 0.

    토픽 0 「가상토픽 하나」, 쪽 regulations:
      s0 impact   r0 k0 A url U1 · r0 k1 B url "" · r1 k0 A2 url " U1 "(공백 — 같은 url)
      s0 financial r0 k0 D url U1 · r0 k1 E url U2 · r1 k0 G url null
      s0 pathway  r0 i=1(= financial r0 사본) · r1 i=2(= financial r1 사본) · r2 i=null(빈 context)
      s1 impact   r0 k0 H url U2 ;  s1 financial r0 k0 K url U1 ;  s1 pathway not_run
    묶음: G1 = {s0 imp r0 k0 · s0 imp r1 k0 · s0 fin r0 k0 · s1 fin r0 k0 · s0 pw r0 k0}(첫 자리 s0 imp r0 k0)
          G2 = {s1 imp r0 k0 · s0 fin r0 k1 · s0 pw r0 k1}(첫 자리 s1 imp r0 k0 — 둘째 서브토픽 impact 가 첫 서브토픽
               financial 보다 앞) · G3 = {s0 fin r1 k0 · s0 pw r1 k0}(financial 만) · B 홀로
    토픽 1 「가상토픽 둘」: s0 impact r0 k0 X url U1(다른 토픽 — 묶지 않음)
"""

import copy
import importlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from esgapi.materiality.contracts import shapes
from esgapi.materiality.contracts.edit_shapes import POINTER_PATTERN
from esgapi.materiality.outputs import edits, final_xlsx

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "examples"
U1 = "https://example.com/가상/하나"
U2 = "https://example.com/가상/둘"
T0 = "/part2/topics/0/subtopics/0"
T01 = "/part2/topics/0/subtopics/1"
REG = "context/regulations"


def item(title: str, url: str | None) -> dict[str, Any]:
    return {"title": title, "summary": f"{title}의 요약", "url": url}


def ctx(regs: list[dict[str, Any]], cons: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    return {"regulations": regs, "controversies": cons or []}


def impact_row(definition: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "impactDefinition": definition,
        "impactType": "부정",
        "valueChainActivities": ["가상 활동"],
        "context": context,
    }


def fin_row(definition: str, context: dict[str, Any]) -> dict[str, Any]:
    return {
        "impactDefinition": definition,
        "impactType": "리스크",
        "riskType": "리스크-시장",
        "valueChainActivities": [],
        "context": context,
    }


def path_row(i: int | None, fin: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "i": i,
        "impactDefinition": None if fin is None else fin["impactDefinition"],
        "impactDriver": "가상 동인",
        "businessImpact": "가상 사업 영향",
        "financialImpact": "가상 재무 영향",
        "impactType": None if fin is None else fin["impactType"],
        "riskType": None if fin is None else fin["riskType"],
        "context": ctx([]) if fin is None else copy.deepcopy(fin["context"]),
    }


def done(rows: list[dict[str, Any]], parsed: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"status": "done", "parsed": parsed or {"impacts": []}, "rows": rows}


NOT_RUN = {"status": "not_run", "message": "가상 — 돌리지 않음"}


def edit_body() -> dict[str, Any]:
    """머리말 그림의 본문(새 dict). result@2 strict 를 지난다."""
    base = cast("dict[str, Any]", json.loads((EXAMPLES / "result2-sample.json").read_text(encoding="utf-8")))
    i0 = impact_row(
        "가상 영향 정의 하나", ctx([item("가상 규정 A", U1), item("가상 규정 B", "")], [item("가상 사건 C", U1)])
    )
    i1 = impact_row("가상 영향 정의 둘", ctx([item("가상 규정 A2", f" {U1} ")]))
    f0 = fin_row("가상 재무 정의 하나", ctx([item("가상 규정 D", U1), item("가상 규정 E", U2)]))
    f1 = fin_row("가상 재무 정의 둘", ctx([item("가상 규정 G", None)]))
    s0 = {
        "name": "가상 서브토픽 가",
        "description": "가상 설명",
        "autofilled": False,
        "impact": done([i0, i1], {"impacts": [{"impact_definition": "가상 영향 정의 하나"}]}),
        "financial": done([f0, f1]),
        "pathway": done([path_row(1, f0), path_row(2, f1), path_row(None, None)], {"pathways": []}),
    }
    s1 = {
        "name": "가상 서브토픽 나",
        "description": "가상 설명",
        "autofilled": False,
        "impact": done([impact_row("가상 영향 정의 셋", ctx([item("가상 규정 H", U2)]))]),
        "financial": done([fin_row("가상 재무 정의 셋", ctx([item("가상 규정 K", U1)]))]),
        "pathway": NOT_RUN,
    }
    t1s0 = {
        "name": "가상 서브토픽 다",
        "description": "가상 설명",
        "autofilled": False,
        "impact": done([impact_row("가상 영향 정의 넷", ctx([item("가상 규정 X", U1)]))]),
        "financial": NOT_RUN,
        "pathway": NOT_RUN,
    }
    base["part2"] = {
        "status": "done",
        "input": {"source": "result"},
        "topics": [
            {"topic": "가상토픽 하나", "description": "가상 설명", "subtopics": [s0, s1]},
            {"topic": "가상토픽 둘", "description": "가상 설명", "subtopics": [t1s0]},
        ],
    }
    return base


def strict(body: dict[str, Any]) -> None:
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(body, strict=True)


def at(body: dict[str, Any], pointer: str) -> Any:
    node: Any = body
    for part in pointer.split("/")[1:]:
        node = cast("Any", node[int(part)] if isinstance(node, list) else node[part])
    return node


def ok(
    body: dict[str, Any], changes: list[tuple[str, str | None]], current: dict[str, str | None] | None = None
) -> Any:
    found = edits.check(body, current or {}, changes)
    assert not isinstance(found, edits.Invalid), found
    return found


def refused(
    body: dict[str, Any], changes: list[tuple[str, str | None]], current: dict[str, str | None] | None = None
) -> str:
    found = edits.check(body, current or {}, changes)
    assert isinstance(found, edits.Invalid), found
    return found.message


G1 = f"{T0}/impact/rows/0/{REG}/0"
G2 = f"{T01}/impact/rows/0/{REG}/0"
G3 = f"{T0}/financial/rows/1/{REG}/0"
B = f"{T0}/impact/rows/0/{REG}/1"
G1_MEMBERS = [
    f"{T0}/impact/rows/0/{REG}/0",
    f"{T0}/impact/rows/1/{REG}/0",
    f"{T0}/financial/rows/0/{REG}/0",
    f"{T01}/financial/rows/0/{REG}/0",
    f"{T0}/pathway/rows/0/{REG}/0",
]


def test_the_body_passes_the_result_shape() -> None:
    strict(edit_body())


# ── 주소 허용 꼴 ──

ALLOWED = [
    f"{T0}/impact/rows/0/impactDefinition",
    f"{T0}/pathway/rows/0/impactDefinition",
    f"{T0}/pathway/rows/0/impactDriver",
    f"{T0}/pathway/rows/0/businessImpact",
    f"{T0}/pathway/rows/0/financialImpact",
    f"{T0}/impact/rows/0/{REG}/0/title",
    f"{T0}/financial/rows/0/{REG}/0/summary",
    f"{T0}/pathway/rows/0/{REG}/0/url",
    f"{T0}/impact/rows/0/context/controversies/0/title",
]
REFUSED_FORMS = [
    f"{T0}/impact/rows/0/impactType",  # 분류 값(Q5)
    f"{T0}/pathway/rows/0/riskType",
    f"{T0}/impact/rows/0/valueChainActivities",  # 가치사슬 활동
    f"{T0}/financial/rows/0/impactDefinition",  # 2-2 영향 정의는 pathway 칸
    "/part2/topics/0/topic",  # 토픽 이름
    f"{T0}/name",  # 서브토픽 이름
    "/part2/topics/00/subtopics/0/impact/rows/0/impactDefinition",  # 앞 0
    f"{T0}/impact/rows/-1/impactDefinition",
    f"{T0}/impact/rows/0/impactDefinition/",
    f"{T0}/impact/parsed/impacts/0/impact_definition",  # 모델 원문
    "/part1/0/regulation",
    f"{T0}/impact/rows/0/{REG}/0/region",
]


@pytest.mark.parametrize("pointer", ALLOWED)
def test_allowed_pointer_forms_parse_and_round_trip(pointer: str) -> None:
    address = edits.parse(pointer)
    assert address is not None
    assert edits.pointer(address) == pointer


@pytest.mark.parametrize("pointer", REFUSED_FORMS)
def test_other_pointer_forms_are_refused(pointer: str) -> None:
    assert edits.parse(pointer) is None
    assert "1번째 고침의 자리" in refused(edit_body(), [(pointer, "가상 값")])


def test_a_classification_pointer_is_400() -> None:
    """P4: 분류 값(impactType)은 고칠 칸이 아니다."""
    message = refused(edit_body(), [(f"{T0}/impact/rows/0/impactType", "긍정")])
    assert message.startswith("1번째 고침의 자리")


def test_the_pointer_pattern_is_the_migration_text() -> None:
    migration = importlib.import_module("esgapi.materiality.migrations.0002_result_edits")
    assert migration.POINTER == POINTER_PATTERN


@pytest.mark.parametrize(
    ("pointer", "reason"),
    [
        (f"{T0}/impact/rows/2/impactDefinition", "줄이 결과에 없다"),
        ("/part2/topics/2/subtopics/0/impact/rows/0/impactDefinition", "줄이 결과에 없다"),
        (f"{T01}/pathway/rows/0/impactDriver", "줄이 결과에 없다"),  # not_run 갈래
        (f"{T0}/impact/rows/0/{REG}/2/title", "맥락 항목이 결과에 없다"),
        (f"{T0}/pathway/rows/2/{REG}/0/title", "맥락 항목이 결과에 없다"),
    ],
)
def test_a_pointer_outside_the_original_body_is_400(pointer: str, reason: str) -> None:
    assert reason in refused(edit_body(), [(f"{T0}/impact/rows/0/impactDefinition", "가상 값"), (pointer, "가상")])
    assert refused(edit_body(), [(f"{T0}/impact/rows/0/impactDefinition", "가상 값"), (pointer, "가상")]).startswith(
        "2번째 고침"
    )


def test_a_pathway_row_without_i_cannot_edit_context() -> None:
    body = edit_body()
    at(body, f"{T0}/pathway/rows/2/context")["regulations"].append(item("가상 규정 Z", None))
    assert "이어지지 않아" in refused(body, [(f"{T0}/pathway/rows/2/{REG}/0/title", "가상")])
    # 글 칸(①②③)은 i 없이도 고친다
    ok(body, [(f"{T0}/pathway/rows/2/impactDriver", "가상 동인 고침")])


# ── 바른 주소 ──


@pytest.mark.parametrize(
    ("given", "first"),
    [
        (f"{T0}/impact/rows/0/{REG}/0/title", f"{G1}/title"),  # 첫 자리 그대로
        (f"{T0}/impact/rows/1/{REG}/0/title", f"{G1}/title"),  # 공백 붙은 같은 url
        (f"{T0}/financial/rows/0/{REG}/0/summary", f"{G1}/summary"),
        (f"{T01}/financial/rows/0/{REG}/0/url", f"{G1}/url"),  # 다른 서브토픽의 재무
        (f"{T0}/pathway/rows/0/{REG}/0/title", f"{G1}/title"),  # pathway → i → 재무 → 묶음
        (f"{T0}/financial/rows/0/{REG}/1/title", f"{G2}/title"),  # 둘째 서브토픽 impact 가 앞
        (f"{T0}/pathway/rows/0/{REG}/1/title", f"{G2}/title"),
        (f"{T0}/financial/rows/1/{REG}/0/title", f"{G3}/title"),  # financial 만 있는 묶음
        (f"{T0}/pathway/rows/1/{REG}/0/title", f"{G3}/title"),  # 빈 url — i 로 이음
        (f"{B}/title", f"{B}/title"),  # 빈 url 홀로
        ("/part2/topics/1/subtopics/0/impact/rows/0/context/regulations/0/title",) * 2,  # 다른 토픽은 따로
        (f"{T0}/pathway/rows/1/impactDriver",) * 2,  # 글 칸은 그대로
    ],
)
def test_canonical_pointer(given: str, first: str) -> None:
    value = "https://example.com/가상/새" if given.endswith("/url") else "가상 고친 글"
    assert ok(edit_body(), [(given, value)]) == [(first, value)]


def test_two_changes_on_one_group_in_one_save_are_400() -> None:
    message = refused(
        edit_body(),
        [
            (f"{T0}/impact/rows/0/impactDefinition", "가상"),
            (f"{G1}/title", "가"),
            (f"{T0}/pathway/rows/0/{REG}/0/title", "나"),
        ],
    )
    assert message.startswith("3번째 고침은 앞 고침과 같은 칸")


def test_the_group_is_fixed_by_the_original_url() -> None:
    """P3: url 을 고친 뒤 다른 자리의 title 을 고쳐도 같은 묶음(첫 자리)이다 — 고친 url 로 다시 묶지 않는다."""
    current: dict[str, str | None] = {f"{G1}/url": "https://example.com/가상/새"}
    for member in G1_MEMBERS[1:]:
        assert ok(edit_body(), [(f"{member}/title", "가상 새 제목")], current) == [(f"{G1}/title", "가상 새 제목")]


# ── 값 ──


@pytest.mark.parametrize("blank", ["", " ", "\n\t "])
def test_blank_becomes_null(blank: str) -> None:
    assert ok(edit_body(), [(f"{G1}/summary", blank)]) == [(f"{G1}/summary", None)]


@pytest.mark.parametrize(
    ("value", "reason"),
    [
        ("가상\x00글", "제어 문자"),
        ("가상\x07글", "제어 문자"),
        ("가상\x1f글", "제어 문자"),
        ("가상\ud800글", "서로게이트"),
    ],
)
def test_control_characters_and_lone_surrogates_are_refused(value: str, reason: str) -> None:
    assert reason in refused(edit_body(), [(f"{T0}/impact/rows/0/impactDefinition", value)])


def test_tab_newline_and_return_are_kept() -> None:
    assert ok(edit_body(), [(f"{T0}/impact/rows/0/impactDefinition", "가\t상\r\n글")])[0][1] == "가\t상\r\n글"


@pytest.mark.parametrize(
    ("pointer", "limit"),
    [
        (f"{T0}/impact/rows/0/impactDefinition", 4000),
        (f"{T0}/pathway/rows/0/financialImpact", 4000),
        (f"{G1}/summary", 4000),
        (f"{G1}/title", 1000),
    ],
)
def test_limits_at_n_and_n_plus_one(pointer: str, limit: int) -> None:
    """P5: 상한 n 자는 받고 n+1 자는 400(코드포인트 — 한글 한 자도 하나)."""
    assert ok(edit_body(), [(pointer, "가" * limit)])[0][1] == "가" * limit
    assert f"{limit:,}자를 넘는다" in refused(edit_body(), [(pointer, "가" * (limit + 1))])


def test_url_limit_and_form() -> None:
    head = "https://example.com/"
    ok(edit_body(), [(f"{B}/url", head + "a" * (2048 - len(head)))])
    assert "2,048자를 넘는다" in refused(edit_body(), [(f"{B}/url", head + "a" * (2049 - len(head)))])
    assert ok(edit_body(), [(f"{B}/url", "  http://example.com/가상  ")])[0][1] == "  http://example.com/가상  "
    for bad in ("ftp://example.com/가상", "javascript:alert(1)", "example.com/가상", "HTTPS://example.com/가상"):
        assert "http:// 나 https://" in refused(edit_body(), [(f"{B}/url", bad)])
    assert ok(edit_body(), [(f"{B}/url", None)]) == [(f"{B}/url", None)]


# ── url 겹침·비우기 ──


def test_a_url_that_matches_another_group_is_400() -> None:
    """P7: 고친 판에서 같은 토픽·쪽의 다른 묶음과 url(strip)이 같아지면 400."""
    assert "출처(url)가 같아진다" in refused(edit_body(), [(f"{G3}/url", f" {U2}")])
    assert "출처(url)가 같아진다" in refused(edit_body(), [(f"{B}/title", "가상"), (f"{B}/url", U1)])
    assert refused(edit_body(), [(f"{B}/title", "가상"), (f"{B}/url", U1)]).startswith("2번째 고침")
    # 지금 고침과 이 저장이 겹쳐도 같다
    assert "출처(url)가 같아진다" in refused(
        edit_body(), [(f"{B}/url", "https://example.com/가상/새")], {f"{G3}/url": "https://example.com/가상/새"}
    )


def test_a_url_freed_by_an_edit_can_be_taken() -> None:
    current: dict[str, str | None] = {f"{G2}/url": "https://example.com/가상/새"}
    ok(edit_body(), [(f"{G3}/url", U2)], current)
    # 다른 토픽·다른 쪽의 같은 url 은 겹침이 아니다
    ok(edit_body(), [(f"{T0}/impact/rows/0/context/controversies/0/url", U2)])


def test_emptying_the_url_of_a_merged_group_is_400() -> None:
    assert "비울 수 없다" in refused(edit_body(), [(f"{G1}/url", "  ")])
    assert "비울 수 없다" in refused(
        edit_body(), [(f"{T0}/pathway/rows/0/{REG}/1/url", None)]
    )  # G2 = impact + financial
    ok(edit_body(), [(f"{G3}/url", None)])  # financial 하나 + pathway 사본
    ok(edit_body(), [(f"{B}/url", None)])


# ── 덮기 ──


def test_apply_spreads_over_the_group_and_keeps_the_shape() -> None:
    body = edit_body()
    out = edits.apply(body, {f"{G1}/title": "가상 고친 제목", f"{T0}/pathway/rows/1/impactDriver": "가상 고친 동인"})
    for member in G1_MEMBERS:
        assert at(out, f"{member}/title") == "가상 고친 제목"
    assert at(out, f"{T0}/pathway/rows/1/impactDriver") == "가상 고친 동인"
    assert at(out, f"{T0}/pathway/rows/0/impactDriver") == "가상 동인"
    assert at(out, "/part2/topics/1/subtopics/0/impact/rows/0/context/regulations/0/title") == "가상 규정 X"
    strict(out)


def test_apply_leaves_parsed_raw_and_the_original_alone() -> None:
    """P1: 덮기는 rows 의 칸만 — parsed(모델 원문)·part1·warnings·settings 와 원본 dict 는 그대로."""
    body = edit_body()
    before = copy.deepcopy(body)
    out = edits.apply(body, {f"{T0}/impact/rows/0/impactDefinition": "가상 고친 정의"})
    assert body == before
    assert out["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"] == {
        "impacts": [{"impact_definition": "가상 영향 정의 하나"}]
    }
    for key in ("part1", "warnings", "settings", "company", "scope", "schemaVersion"):
        assert out[key] == before[key]
    assert at(out, f"{T0}/impact/rows/0/impactDefinition") == "가상 고친 정의"


def test_apply_without_edits_is_the_same_body() -> None:
    body = edit_body()
    assert edits.apply(body, {}) is body


def test_the_pathway_copy_follows_and_the_2_2_summary_shows_it() -> None:
    """P2: 재무 항목의 Pathway 사본에도 퍼진다 — 엑셀 2-2 「컨텍스트 요약」이 고친 글."""
    out = edits.apply(edit_body(), {f"{G1}/summary": "가상 고친 요약", f"{G3}/summary": "가상 홀로 요약"})
    assert at(out, f"{T0}/pathway/rows/0/{REG}/0/summary") == "가상 고친 요약"
    assert at(out, f"{T0}/pathway/rows/1/{REG}/0/summary") == "가상 홀로 요약"
    path0 = at(out, f"{T0}/pathway/rows/0/context")
    assert final_xlsx.summaries(path0) == "1. 가상 고친 요약\n2. 가상 규정 E의 요약"


def test_apply_is_deterministic_and_writes_values_equal_to_the_original() -> None:
    """P7b: 되돌린 칸(원문과 같은 값)도 덮는다 — 묶음 전체가 첫 자리의 원문(다른 자리 원문이 남지 않음)."""
    body = edit_body()
    current: dict[str, str | None] = {f"{G1}/title": "가상 규정 A"}  # 첫 자리 원문 = 되돌림
    out = edits.apply(body, current)
    assert [at(out, f"{m}/title") for m in G1_MEMBERS] == ["가상 규정 A"] * len(G1_MEMBERS)
    assert at(body, f"{G1_MEMBERS[1]}/title") == "가상 규정 A2"  # 원문은 달랐다
    assert edits.apply(edit_body(), current) == out
    assert edits.listing(body, current) == []  # GET edits 에서는 빠진다


def test_every_allowed_edit_keeps_the_shape() -> None:
    body = edit_body()
    current: dict[str, str | None] = {}
    for given in ALLOWED:
        ((target, value),) = ok(body, [(given, "https://example.com/가상/새" if given.endswith("/url") else "가상")])
        current[target] = value
    strict(edits.apply(body, current))


# ── GET edits 목록 ──


def test_listing_is_in_body_order_with_the_original() -> None:
    body = edit_body()
    current: dict[str, str | None] = {
        f"{G2}/title": "가상 ㄴ",
        f"{T0}/pathway/rows/1/financialImpact": "가상 ㄷ",
        f"{G3}/summary": "가상 ㄹ",
        f"{G1}/url": "https://example.com/가상/새",
        f"{G1}/title": "가상 ㄱ",
        f"{T0}/impact/rows/0/impactDefinition": "가상 영향 정의 하나",  # 원문과 같음 — 빠짐
        "/part2/topics/1/subtopics/0/impact/rows/0/impactDefinition": None,
    }
    assert edits.listing(body, current) == [
        (f"{G1}/title", "가상 ㄱ", "가상 규정 A"),
        (f"{G1}/url", "https://example.com/가상/새", U1),
        (f"{G3}/summary", "가상 ㄹ", "가상 규정 G의 요약"),
        (f"{T0}/pathway/rows/1/financialImpact", "가상 ㄷ", "가상 재무 영향"),
        (f"{G2}/title", "가상 ㄴ", "가상 규정 H"),
        ("/part2/topics/1/subtopics/0/impact/rows/0/impactDefinition", None, "가상 영향 정의 넷"),
    ]


# ── ★C 웹 mergedItems(=final_xlsx.merged_items) 와 같은 묶음 ──


def test_groups_match_the_shortlist_merge() -> None:
    """1-1 의 합친 항목(SOC → FIN, url 같으면 하나)마다 묶음 하나, 같은 차례 — 웹 result.ts 의 mergedItems 도 같은
    규칙."""
    body = edit_body()
    found = edits.groups(body)
    for t, topic in enumerate(body["part2"]["topics"]):
        for side in edits.SIDES:
            soc = [row for sub in topic["subtopics"] for row in edits._rows(sub, "impact")]  # pyright: ignore[reportPrivateUsage]
            fin = [row for sub in topic["subtopics"] for row in edits._rows(sub, "financial")]  # pyright: ignore[reportPrivateUsage]
            merged = final_xlsx.merged_items(
                [i for r in soc for i in r["context"][side]], [i for r in fin for i in r["context"][side]]
            )
            firsts = [key for key in found.members if key[0] == t and key[4] == side]
            assert [id(edits._item(body, key)) for key in firsts] == [id(m) for _, m in merged]  # pyright: ignore[reportPrivateUsage]
    # 고친 판의 1-1: G1 은 한 항목, 라벨 [환경·사회·재무], 고친 제목
    out = edits.apply(body, {f"{G1}/title": "가상 고친 제목"})
    ((_, _, f, _), _) = final_xlsx.shortlist_rows(out)
    assert f is not None
    assert f.startswith("1) [환경·사회·재무] 제목: 가상 고친 제목\n")
    assert f.count("가상 고친 제목") == 1
