"""엑셀 검토 반영본의 재판단(xlsx.build 의 bases·notes — 밴드 GRJ1 ② §2-5, 결정 MARC-ENT-617). 순수 층(DB 없음).

잰다: 판정 칸은 「사용자 고침 > 기준 판단 > 첫 판단」 · 「AI …」 칸도 기준 판단 · 끝 칸 둘(「근거 고침」·「재판단」) ·
기준 판단이 리스크 아님이면 등급 칸 「리스크 아님」·요약 등급 셋에서 빠지고 「리스크 아님(재판단)」 줄에 셈 · 원 결과는
안 바뀜 · bases·notes 는 edits 길에만(흐름 엑셀은 칸·줄 0 — g2d-baseline 그대로). 결과는 계약 예시(지어낸 것)다 —
result-normal: 0 CEO High · 1 CEO Mid · 2 회사소개+기후 Mid · 3 기후 Low.
"""

import copy
import json
from typing import Any

import pytest

from esgapi.greenwash.flows.colab_e0 import frequency_extras
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.tests.outputs.test_xlsx_edits import ALL, blank, example, read

LEVEL, REASONS, FIX = (xlsx.SENTENCE_HEADER.index(name) for name in ("등급", "사유", "수정 방향"))
TAIL = len(xlsx.SENTENCE_HEADER)
EDIT_TAIL = TAIL + len(xlsx.EDIT_HEADER)


def basis(level: str | None, reason: str, fix: str) -> dict[str, Any]:
    return {
        "level": level,
        "riskTags": ["지어낸 유형"],
        "confirmedInEvidence": ["지어낸 사실"],
        "missingFields": [],
        "reasonBullets": [reason],
        "fixParagraph": fix,
        "evidencePages": [2],
    }


def build(
    result: dict[str, Any],
    edits: dict[int, xlsx.Edit],
    bases: dict[int, dict[str, Any]],
    notes: dict[int, xlsx.Note],
) -> dict[str, list[tuple[Any, ...]]]:
    content = xlsx.build(
        result,
        added_terms=frequency_extras(result["extraTerms"]),
        adopted=ALL,
        edits=edits,
        bases=bases,
        notes=notes,
    )
    return read(content)


def test_the_basis_leads_unless_a_person_edited_and_the_ai_columns_follow_the_basis() -> None:
    result = example("result-normal")
    before = json.dumps(result, ensure_ascii=False, sort_keys=True)
    bases = {1: basis("High", "다시 본 사유", "다시 본 수정 방향"), 2: basis("Low", "둘째 사유", "둘째 수정 방향")}
    edits: dict[int, xlsx.Edit] = {2: ("Mid", None, None)}  # 첫 판단과 같은 등급이지만 기준과 달라 고침
    notes = {1: ("지움 1 · 더함 1", "1회 · 2026-11-09 10:05 · 지어낸 사람"), 2: ("", "2회 · 2026-11-09 11:00 · 사람")}
    book = build(result, edits, bases, notes)
    assert book["문장"][0] == xlsx.SENTENCE_HEADER + xlsx.EDIT_HEADER + xlsx.REJUDGE_HEADER
    rows = book["문장"][1:]
    assert (rows[1][LEVEL], rows[1][REASONS], rows[1][FIX]) == ("High", "다시 본 사유", "다시 본 수정 방향")
    assert all(blank(v) for v in rows[1][TAIL:EDIT_TAIL])  # 사람 고침 없음
    assert rows[1][EDIT_TAIL:] == notes[1]
    assert (rows[2][LEVEL], rows[2][REASONS]) == ("Mid", "둘째 사유")  # 고친 등급 > 기준 · 사유는 기준
    assert (rows[2][TAIL], rows[2][TAIL + 1]) == ("등급", "Low")  # 「AI 등급」 = 기준 판단
    assert blank(rows[2][EDIT_TAIL]) and rows[2][EDIT_TAIL + 1] == notes[2][1]  # 빈 글 칸은 읽으면 None
    assert rows[0][LEVEL] == result["items"][0]["level"]  # 재판단 없는 문장은 첫 판단
    assert all(blank(v) for v in rows[0][TAIL:])
    summary = dict(book["요약"][1:])
    assert (summary["등급 High"], summary["등급 Mid"], summary["등급 Low"]) == (2, 1, 1)
    assert summary[xlsx.NONRISK_SUMMARY] == 0
    assert json.dumps(result, ensure_ascii=False, sort_keys=True) == before  # 원 결과(첫 AI 판단)는 그대로


def test_a_nonrisk_basis_reads_as_not_a_risk_and_leaves_the_three_levels() -> None:
    result = example("result-normal")
    book = build(result, {}, {0: basis(None, "", "")}, {0: ("지움 0 · 더함 1", "1회 · 2026-11-09 10:05 · 사람")})
    rows = book["문장"][1:]
    assert rows[0][LEVEL] == xlsx.NONRISK
    summary = dict(book["요약"][1:])
    assert (summary["등급 High"], summary["등급 Mid"], summary["등급 Low"]) == (0, 2, 1)  # 합 3 < 문장 4
    assert summary[xlsx.NONRISK_SUMMARY] == 1
    assert summary["CEO 메시지 · High"] == 0  # 파트 칸은 남고 0
    assert summary["전체 문장 수"] == 4
    # 사람이 등급을 고치면 그 등급으로 센다(고친 등급 > 기준 판단)
    edited = build(result, {0: ("Low", None, None)}, {0: basis(None, "", "")}, {})
    assert edited["문장"][1][LEVEL] == "Low"
    assert edited["문장"][1][TAIL + 1] == xlsx.NONRISK  # 「AI 등급」 = 기준 판단(리스크 아님)
    assert dict(edited["요약"][1:])[xlsx.NONRISK_SUMMARY] == 0


def test_bases_and_notes_ride_only_the_edits_path() -> None:
    result = example("result-normal")
    with pytest.raises(ValueError, match="edits"):
        xlsx.build(result, added_terms=[], adopted=ALL, edits=None, bases={0: basis("Low", "a", "b")})
    with pytest.raises(ValueError, match="edits"):
        xlsx.build(copy.deepcopy(result), added_terms=[], adopted=None, edits=None, notes={0: ("a", "b")})
    plain = read(xlsx.build(result, added_terms=frequency_extras(result["extraTerms"])))
    assert plain["문장"][0] == xlsx.SENTENCE_HEADER
    assert all(row[0] != xlsx.NONRISK_SUMMARY for row in plain["요약"])
