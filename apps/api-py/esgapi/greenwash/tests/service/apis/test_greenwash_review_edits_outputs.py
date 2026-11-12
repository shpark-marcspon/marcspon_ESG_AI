# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""검토 고침이 닿는 출력(밴드 G1b-3 ② — §2-4·§2-5). 업무 층: 진짜 DB, 세션은 EDK 교환(login — 회사 A 의 고객사 사용자).

    확정본 엑셀 DB 왕복   고친 값·칸 넷(AI 원래 판단)·요약 고친 등급·「고친 문장」 줄 · 고침 0 이면 칸 넷 빈 칸
    미확정 보고서        고침이 있어도 AI 값·칸 넷 없음
    목록 levelCounts     효력 등급(High→Low 하나면 High −1·Low +1) · 실행 여럿 섞음 · 남의 실행 고침은 안 섞임 ·
                         review.reviewed 는 표시 수 그대로(고침만 있는 행은 안 셈)
    목록 쿼리 수         고친 문장 있는 실행 1개와 5개에서 같은 k

★ 실행·결과 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나). 글은 지은 것이다.
"""

import io
from typing import Any

import pytest
from django.test import Client
from openpyxl import load_workbook

from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.tests.service import seed
from esgapi.greenwash.tests.service.apis.test_greenwash_checks import FIXED_QUERIES, checks
from tests.support.http import login

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")  # items 넷: 0 CEO High · 1 CEO Mid · 2 회사소개+기후 Mid · 3 기후 Low
ITEMS = NORMAL["items"]
TAIL = len(xlsx.SENTENCE_HEADER)
FIX = "기준연도와 목표연도를 함께 밝혀 주세요."


def put(client: Client, run_id: int, body: dict[str, Any]) -> dict[str, Any]:
    response = client.put(f"/api/greenwash/runs/{run_id}/review", data=body, content_type="application/json")
    assert response.status_code == 200, response.content.decode()
    found: dict[str, Any] = response.json()
    return found


def edit(
    index: int, level: str | None = None, bullets: list[str] | None = None, fix: str | None = None
) -> dict[str, Any]:
    return {"itemIndex": index, "level": level, "reasonBullets": bullets, "fixParagraph": fix}


def report(client: Client, run_id: int, query: str = "") -> dict[str, list[tuple[Any, ...]]]:
    response = client.get(f"/api/greenwash/runs/{run_id}/report{query}")
    assert response.status_code == 200, response.content
    book = load_workbook(io.BytesIO(response.content), read_only=True)
    return {name: [tuple(row) for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}


def blank(value: object) -> bool:
    return value in (None, "")


@pytest.fixture
def done_run(client: Client, companies: tuple[int, int]) -> int:
    login(client)
    return seed.run(companies[0], result=NORMAL)


# ── 확정본 엑셀 ──


def test_the_confirmed_workbook_carries_the_edits_and_the_ai_judgement(client: Client, done_run: int) -> None:
    """0 등급 High→Low · 2 사유·수정 방향 고침 · 1 제외(그 고침은 안 실림) → 확정."""
    put(client, done_run, {"marks": [], "edits": [edit(0, level="Low"), edit(1, fix="제외할 문장의 고침")]})
    put(
        client,
        done_run,
        {
            "state": "confirmed",
            "marks": [{"itemIndex": 1, "decision": "excluded", "excludeReason": "근거 있음"}],
            "edits": [
                edit(0, level="Low"),
                edit(1, fix="제외할 문장의 고침"),
                edit(2, bullets=["  사람 사유  ", ""], fix=FIX),
            ],
        },
    )
    book = report(client, done_run, "?confirmed=true")
    header, rows = book["문장"][0], book["문장"][1:]
    assert header == xlsx.SENTENCE_HEADER + xlsx.EDIT_HEADER + xlsx.REJUDGE_HEADER
    level, reasons, fix = (xlsx.SENTENCE_HEADER.index(name) for name in ("등급", "사유", "수정 방향"))
    assert [row[3] for row in rows] == [ITEMS[i]["sentence"] for i in (0, 2, 3)]
    assert (rows[0][level], rows[0][TAIL], rows[0][TAIL + 1]) == ("Low", "등급", "High")
    assert rows[0][reasons] == "\n".join(ITEMS[0]["reasonBullets"])
    assert (rows[1][reasons], rows[1][fix], rows[1][TAIL]) == ("사람 사유", FIX, "사유·수정 방향")  # strip·빈 줄 버림
    assert (rows[1][TAIL + 2], rows[1][TAIL + 3]) == ("\n".join(ITEMS[2]["reasonBullets"]), ITEMS[2]["fixParagraph"])
    assert blank(rows[1][TAIL + 1])
    assert all(blank(v) for v in rows[2][TAIL:])  # 3 은 안 고침
    summary = dict(book["요약"][1:])
    assert (summary["등급 High"], summary["등급 Mid"], summary["등급 Low"]) == (0, 1, 2)  # 0 이 Low 로
    assert [summary[f"CEO 메시지 · {lv}"] for lv in xlsx.LEVELS] == [0, 0, 1]
    assert book["설정"][-2:] == [("고친 문장", "2"), ("판", "확정본 — 채택 3 / 전체 4")]


def test_a_confirmed_review_without_edits_stands_the_columns_up_blank(client: Client, done_run: int) -> None:
    put(client, done_run, {"state": "confirmed", "marks": []})
    book = report(client, done_run, "?confirmed=true")
    assert book["문장"][0] == xlsx.SENTENCE_HEADER + xlsx.EDIT_HEADER + xlsx.REJUDGE_HEADER
    assert all(all(blank(v) for v in row[TAIL:]) for row in book["문장"][1:])
    assert book["설정"][-2:] == [("고친 문장", "0"), ("판", "확정본 — 채택 4 / 전체 4")]


def test_the_unconfirmed_report_stays_the_ai_judgement(client: Client, done_run: int) -> None:
    put(client, done_run, {"marks": [], "edits": [edit(0, level="Low", fix=FIX)]})
    before_confirm = report(client, done_run)
    put(client, done_run, {"state": "confirmed", "marks": []})
    after_confirm = report(client, done_run)
    for book in (before_confirm, after_confirm):
        assert book["문장"][0] == xlsx.SENTENCE_HEADER
        assert book["문장"][1][2] == "High"
        assert book["문장"][1][xlsx.SENTENCE_HEADER.index("수정 방향")] == ITEMS[0]["fixParagraph"]
        assert all(row[0] not in ("고친 문장", "판") for row in book["설정"])


# ── 목록 levelCounts ──


def test_the_list_counts_the_effective_levels(client: Client, companies: tuple[int, int]) -> None:
    login(client)
    a, b = companies
    edited = seed.run(a, result=NORMAL)
    untouched = seed.run(a, result=NORMAL)
    mixed = seed.run(a, result=NORMAL)
    put(client, edited, {"marks": [], "edits": [edit(0, level="Low")]})  # High → Low
    put(
        client,
        mixed,
        {
            "marks": [{"itemIndex": 3, "decision": "adopted", "excludeReason": None}],
            "edits": [edit(1, level="High"), edit(2, level="Low"), edit(3, bullets=["사유만 고침"])],
        },
    )
    seed.run(b, result=NORMAL)  # 남의 회사 실행 — 실리지 않는다
    runs = {r["runId"]: r for r in checks(client)["runs"]}
    assert runs[edited]["levelCounts"] == {"High": 0, "Mid": 2, "Low": 2}
    assert runs[untouched]["levelCounts"] == {"High": 1, "Mid": 2, "Low": 1}
    assert runs[mixed]["levelCounts"] == {"High": 2, "Mid": 0, "Low": 2}
    assert (runs[edited]["review"]["reviewed"], runs[mixed]["review"]["reviewed"]) == (0, 1)  # 고침만은 표시가 아니다
    assert runs[edited]["review"]["state"] == "in_review"


def test_clearing_an_edit_returns_the_ai_count(client: Client, done_run: int) -> None:
    put(client, done_run, {"marks": [], "edits": [edit(0, level="Low")]})
    put(client, done_run, {"marks": [], "edits": []})
    (row,) = checks(client)["runs"]
    assert row["levelCounts"] == NORMAL["counts"]["byLevel"]


def test_the_list_query_count_stays_k_with_edited_runs(
    client: Client, companies: tuple[int, int], django_assert_num_queries: Any
) -> None:
    login(client)
    a = companies[0]
    first = seed.run(a, result=NORMAL)
    put(client, first, {"marks": [], "edits": [edit(0, level="Low")]})
    with django_assert_num_queries(FIXED_QUERIES):
        one = checks(client)
    for index in range(4):
        run_id = seed.run(a, result=NORMAL)
        put(client, run_id, {"marks": [], "edits": [edit(index, level="High" if index else "Mid")]})
    with django_assert_num_queries(FIXED_QUERIES):
        five = checks(client)
    assert (len(one["runs"]), len(five["runs"])) == (1, 5)  # 분모
    assert (
        sum(r["levelCounts"]["High"] for r in five["runs"]) == 0 + 0 + 2 + 2 + 2
    )  # 고침이 실행마다 제자리(Low·Mid·High·High·High)
