"""키워드 점수 후보의 산정 출처(`MARC-ISSUE-193` 의 1): 키워드 몫 0 · LLM 그룹 이름 몫만으로 선 후보는 `ai`.

점수 합(정렬·`score`)은 코랩 `_fix_rank_spend_candidates`(`:8341`) 그대로다 — 그룹 몫 +35 는 손으로 짚은 값이다.
    (가) 품목군 없음 · 규칙 낱말 없음 · LLM 그룹 「가상군」 이 계수 책 품목군에 걸림 · 키워드 0 → ai
    (나) (가)와 같은 줄, 계수 책에 그 줄의 키워드 하나(「가상무엇」 80 + 4) → 걸린 후보만 rule
    (다) 품목군 칸에 사용자가 「가상군」 · 키워드 0 → rule
그룹 이름이 힌트가 되는 것은 템플릿에 품목군 열이 없을 때뿐이다: 열이 있으면 표준화가 「분류」 로 바꾸고 빈 칸은
NaN 이라, 코랩 `or` 사슬(`:8475`)에서 NaN 이 참으로 이겨 힌트가 빈 글이 된다(그룹 몫 0 — 코랩 그대로).
그래서 (가)·(나)는 품목군 열이 없는 시트, (다)는 있는 시트다.
"""

from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, ProcessedSheet, run
from esgapi.inventory.engines.scope3.colab_157.purchase import Candidate, RowMeta
from esgapi.inventory.tests.engines.scope3.colab_157.support import ColabReplies, FakeGeocoder, Value, sheet, workbook
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import (
    BOOK_ROWS,
    C1_HEAD,
    C1_SUB,
    COFFEE,
    MISC,
    TAGS,
)
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client

NO_GROUP_HEAD = [h for h in C1_HEAD if h != "*품목군"]
NO_GROUP_SUB = C1_SUB[: C1_HEAD.index("*품목군")] + C1_SUB[C1_HEAD.index("*품목군") + 1 :]
NO_GROUP_ROWS: dict[int, list[Value]] = {
    4: NO_GROUP_HEAD,
    5: NO_GROUP_SUB,
    6: ["가상국", "가상사업장", "가상 무엇", None, 9100],
}
USER_GROUP_ROWS: dict[int, list[Value]] = {
    4: C1_HEAD,
    5: C1_SUB,
    6: ["가상국", "가상사업장", "가상군", "가상 무엇", None, 9200],
}
KEYWORD_BOOK_ROWS: dict[int, list[Value]] = {**BOOK_ROWS, 8: [*BOOK_ROWS[8][:2], "가상무엇", *BOOK_ROWS[8][3:]]}


def meta_of(template_rows: dict[int, list[Value]], book_rows: dict[int, list[Value]]) -> RowMeta:
    mock = ColabReplies(groups={"가상 무엇": "가상군"})
    template = workbook(sheet("C1_구매품서비스", template_rows))
    result = run(
        template, workbook(sheet("구매_USEPA", book_rows)), 2025, mock_client(mock), FakeGeocoder(), TAGS, ROUTE
    )
    assert isinstance(result, ColabRun)
    processed = result.sheets[0]
    assert isinstance(processed, ProcessedSheet)
    assert [m.excel_row for m in processed.metas] == [6]
    meta = processed.metas[0]
    assert isinstance(meta, RowMeta)  # metas 는 RowMeta | ActivityMeta 의 튜플(S3C-b1 ②) — C1 은 RowMeta
    return meta


def keyword_candidates(meta: RowMeta) -> list[tuple[str, int, str]]:
    return [(c.title, c.score, c.origin) for c in meta.candidates if c.source == "db_keyword"]


def first(meta: RowMeta) -> Candidate:
    return meta.candidates[0]


def test_llm_group_share_alone_is_ai() -> None:
    """(가)"""
    meta = meta_of(NO_GROUP_ROWS, BOOK_ROWS)
    assert (meta.group.origin, meta.group.via, meta.group.name) == ("ai", "group_llm", "가상군")
    assert keyword_candidates(meta) == [(MISC, 35, "ai"), (COFFEE, 35, "ai")]  # 코랩 점수·차례(동점은 계수 책 차례)
    assert (first(meta).source, meta.origin) == ("db_keyword", "ai")
    assert meta.origin_steps[1].origin == "ai"


def test_a_keyword_share_keeps_rule() -> None:
    """(나) 키워드가 걸린 후보는 rule, 같은 줄의 그룹 몫만 받은 후보는 ai."""
    meta = meta_of(NO_GROUP_ROWS, KEYWORD_BOOK_ROWS)
    assert meta.group.origin == "ai"
    assert keyword_candidates(meta) == [(MISC, 80 + 4 + 35, "rule"), (COFFEE, 35, "ai")]
    assert meta.origin == "rule"
    assert meta.origin_steps[1].origin == "rule"


def test_user_group_share_is_rule() -> None:
    """(다)"""
    meta = meta_of(USER_GROUP_ROWS, BOOK_ROWS)
    assert (meta.group.origin, meta.group.via) == ("rule", "group_user")
    assert keyword_candidates(meta) == [(MISC, 35, "rule"), (COFFEE, 35, "rule")]
    assert meta.origin == "rule"


# ── S3C-b0 검증 R1·R2(purchase.py 는 그대로) ──
PACKAGING = "Virtual Packaging Materials"
PACKAGING_BOOK_ROWS: dict[int, list[Value]] = {
    **BOOK_ROWS,
    10: ["포장재", "가상세부", None, 9007, PACKAGING, 9.7, 9.7e-05],
}
RULE_GROUP_ROWS: dict[int, list[Value]] = {
    4: NO_GROUP_HEAD,
    5: NO_GROUP_SUB,
    6: ["가상국", "가상사업장", "가상 에어캡", None, 9100],
}
PARTIAL_BOOK_ROWS: dict[int, list[Value]] = {**BOOK_ROWS, 8: [*BOOK_ROWS[8][:2], "가상-무엇들", *BOOK_ROWS[8][3:]]}


def test_a_rule_group_share_is_rule() -> None:
    """R1: 품목군 열 없음 · 품목명 「가상 에어캡」 이 규칙 「포장재」 에 걸림(group_rule)
    → 그룹 몫 35 만으로 선 후보도 rule.

    수작업 규칙(`MANUAL_PURCHASE_TITLE_RULES`)의 낱말은 「가상에어캡」 에 없다 — 1단계 후보 0.
    """
    meta = meta_of(RULE_GROUP_ROWS, PACKAGING_BOOK_ROWS)
    assert (meta.group.origin, meta.group.via, meta.group.name) == ("rule", "group_rule", "포장재")
    assert keyword_candidates(meta) == [(PACKAGING, 35, "rule")]
    assert not any(c.source == "manual_keyword" for c in meta.candidates)
    assert (first(meta).source, meta.origin) == ("db_keyword", "rule")


def test_a_partial_keyword_share_keeps_rule() -> None:
    """R2: (가)와 같은 줄(LLM 그룹 「가상군」), 키워드 「가상-무엇들」 은 통째로는 안 걸리고
    조각 「가상」 만 걸림 → +15.

    「가상무엇들」(5자 ≥ 3) ⊄ 「가상무엇」, 조각 「가상」 ⊂ → 키워드 몫 15 + 그룹 몫 35 = 50, rule.
    """
    meta = meta_of(NO_GROUP_ROWS, PARTIAL_BOOK_ROWS)
    assert meta.group.origin == "ai"
    assert keyword_candidates(meta) == [(MISC, 15 + 35, "rule"), (COFFEE, 35, "ai")]
    assert meta.origin == "rule"
    assert meta.origin_steps[1].origin == "rule"
