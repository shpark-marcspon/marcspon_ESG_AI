"""엑셀 확정본의 검토 고침(xlsx.build 의 edits — 밴드 G1b-3 §2-5, MARC-ENT-354 6). 순수 층(DB 없음).

잰다: edits None 이면 확정본 그대로(칸 넷·「고친 문장」 줄 없음) · edits 값이면 「문장」의 등급·사유·수정 방향이 고친
값, 끝 칸 넷(「고침」 칸 이름 이음, 고친 칸만 AI 값) · 「요약」은 고친 등급으로(두 파트 문장·빈 파트 0) · 「고친
문장」 줄이 「판」 앞 · 빈 dict 면 칸 넷이 서고 빈 칸 · 채택하지 않은 문장의 고침은 세지 않음 · edits 만이면
ValueError. 결과는 계약 예시(지어낸 것)다 — result-normal: 0 CEO High · 1 CEO Mid · 2 회사소개+기후 Mid · 3 기후 Low.
"""

import io
import json
from pathlib import Path
from typing import Any

import pytest
from openpyxl import load_workbook

from esgapi.greenwash.flows.colab_e0 import frequency_extras
from esgapi.greenwash.outputs import xlsx

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "contract-examples"
ALL = {0, 1, 2, 3}


def example(name: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return body


def read(content: bytes) -> dict[str, list[tuple[Any, ...]]]:
    book = load_workbook(io.BytesIO(content), read_only=True)
    return {name: [tuple(row) for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}


def build(
    result: dict[str, Any], adopted: set[int] | None, edits: dict[int, xlsx.Edit] | None
) -> dict[str, list[tuple[Any, ...]]]:
    return read(xlsx.build(result, added_terms=frequency_extras(result["extraTerms"]), adopted=adopted, edits=edits))


def blank(value: object) -> bool:
    return value in (None, "")


def test_no_edits_is_the_confirmed_workbook_without_the_edit_columns() -> None:
    result = example("result-normal")
    plain = build(result, {0, 3}, None)
    assert plain["문장"][0] == xlsx.SENTENCE_HEADER
    assert all(len(row) == len(xlsx.SENTENCE_HEADER) for row in plain["문장"])
    assert all(row[0] != "고친 문장" for row in plain["설정"])


def test_edited_values_lead_and_the_ai_values_follow_only_for_edited_columns() -> None:
    result = example("result-normal")
    edits: dict[int, xlsx.Edit] = {
        0: ("Low", None, None),
        2: (None, ["사람이 고친 사유 하나", "둘"], "사람이 고친 수정 방향"),
    }
    book = build(result, ALL, edits)
    header, rows = book["문장"][0], book["문장"][1:]
    assert header == xlsx.SENTENCE_HEADER + xlsx.EDIT_HEADER + xlsx.REJUDGE_HEADER
    level, reasons, fix = (xlsx.SENTENCE_HEADER.index(name) for name in ("등급", "사유", "수정 방향"))
    tail = len(xlsx.SENTENCE_HEADER)
    ai = result["items"]
    # 0: 등급만 고침
    assert rows[0][level] == "Low"
    assert rows[0][reasons] == "\n".join(ai[0]["reasonBullets"])
    assert rows[0][fix] == ai[0]["fixParagraph"]
    assert rows[0][tail] == "등급"
    assert rows[0][tail + 1] == "High"
    assert blank(rows[0][tail + 2])
    assert blank(rows[0][tail + 3])
    # 1: 안 고침 — 칸 넷 빈 칸
    assert rows[1][level] == ai[1]["level"]
    assert all(blank(v) for v in rows[1][tail:])
    # 2: 사유·수정 방향 고침
    assert rows[2][level] == "Mid"
    assert rows[2][reasons] == "사람이 고친 사유 하나\n둘"
    assert rows[2][fix] == "사람이 고친 수정 방향"
    assert rows[2][tail] == "사유·수정 방향"
    assert blank(rows[2][tail + 1])
    assert rows[2][tail + 2] == "\n".join(ai[2]["reasonBullets"])
    assert rows[2][tail + 3] == ai[2]["fixParagraph"]


def test_every_column_edited_joins_all_three_names() -> None:
    result = example("result-normal")
    book = build(result, ALL, {3: ("High", ["가"], "나")})
    assert book["문장"][4][len(xlsx.SENTENCE_HEADER)] == "등급·사유·수정 방향"


def test_the_summary_counts_the_edited_levels_across_both_parts() -> None:
    """2(회사소개+기후 Mid)를 High 로, 3(기후 Low)을 Mid 로. 채택 {2, 3} — CEO 메시지는 빈 파트 0 줄."""
    result = example("result-normal")
    summary = dict(build(result, {2, 3}, {2: ("High", None, None), 3: ("Mid", None, None)})["요약"][1:])
    assert (summary["등급 High"], summary["등급 Mid"], summary["등급 Low"]) == (1, 1, 0)
    assert [summary[f"회사소개 · {level}"] for level in xlsx.LEVELS] == [1, 0, 0]
    assert [summary[f"기후/환경 토픽 · {level}"] for level in xlsx.LEVELS] == [1, 1, 0]
    assert [summary[f"CEO 메시지 · {level}"] for level in xlsx.LEVELS] == [0, 0, 0]
    assert summary["전체 문장 수"] == 2


def test_the_edited_count_row_sits_right_before_the_version_row() -> None:
    result = example("result-normal")
    edits: dict[int, xlsx.Edit] = {0: ("Low", None, None), 1: (None, None, "고침"), 3: (None, ["가"], None)}
    settings = build(result, {0, 1, 2}, edits)["설정"]
    assert settings[-1] == ("판", "확정본 — 채택 3 / 전체 4")
    assert settings[-2] == ("고친 문장", "2")  # 3 은 채택하지 않아 세지 않는다
    assert settings[:-2] == build(result, {0, 1, 2}, None)["설정"][:-1]


def test_an_empty_edits_mapping_stands_the_columns_up_blank() -> None:
    result = example("result-normal")
    book = build(result, ALL, {})
    assert book["문장"][0] == xlsx.SENTENCE_HEADER + xlsx.EDIT_HEADER + xlsx.REJUDGE_HEADER
    tail = len(xlsx.SENTENCE_HEADER)
    assert all(all(blank(v) for v in row[tail:]) for row in book["문장"][1:])
    assert [row[:tail] for row in book["문장"][1:]] == build(result, ALL, None)["문장"][1:]
    plain = build(result, ALL, None)["요약"]
    low = plain.index(("등급 Low", 1))
    # 검토 반영 엑셀은 등급 셋 뒤에 「리스크 아님(재판단)」 줄이 늘 있다(GRJ1) — 나머지 줄은 같음
    assert book["요약"] == [*plain[: low + 1], (xlsx.NONRISK_SUMMARY, 0), *plain[low + 1 :]]
    assert book["설정"][-2] == ("고친 문장", "0")


def test_edits_without_adopted_is_refused() -> None:
    result = example("result-normal")
    with pytest.raises(ValueError, match="확정본"):
        xlsx.build(result, added_terms=[], edits={})


def test_the_result_is_not_touched() -> None:
    result = example("result-normal")
    before = json.dumps(result, ensure_ascii=False, sort_keys=True)
    build(result, ALL, {0: ("Low", ["가"], "나")})
    assert json.dumps(result, ensure_ascii=False, sort_keys=True) == before
