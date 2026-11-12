"""운영 관리자 실행 기록 엑셀(user/service/utils/run_log_xlsx.py — AD4S ②)을 잰다. 순수 층(DB 없음).

재는 것: 파일 이름(KST·naive 거절) · 시트 하나와 머리 차례 · 칸 값(모듈·상태·검토 한국어, 담당자 대체, 시험용) ·
AI 설정 버전 칸 · 수 칸의 「–」(queued 셋·처리 시간 null) · 글 칸 빈칸 · 수식 꼴 글자가 전부 글자 칸 · 제어 문자 지움.
칸 값은 openpyxl 로 읽어 들여 견준다(바이트는 만든 시각이 들어 실행마다 다르다).
"""

import io
from dataclasses import replace
from datetime import UTC, datetime, timedelta, timezone

import pytest
from openpyxl import load_workbook

from esgapi.user.service.utils.run_log_xlsx import (
    DEFAULT_SETTING,
    HEADER,
    MEDIA_TYPE,
    RunLogLine,
    file_name,
    workbook,
)

LINE = RunLogLine(
    created_at="2026-10-22T09:30:00+09:00",
    module="greenwash",
    document_name="지어낸 보고서.pdf",
    flow_id="greenwash.colab@E0",
    ai_setting="v3",
    created_by_name="담당자 가",
    created_by_username="user11",
    duration_sec=485,
    tokens=108100,
    cost_usd=0.58,
    status="done",
    review="in_review",
    is_test=True,
)


def cells(content: bytes) -> list[tuple[object, ...]]:
    book = load_workbook(io.BytesIO(content))
    assert book.sheetnames == ["실행 기록"]
    sheet = book["실행 기록"]
    return [tuple(cell.value for cell in row) for row in sheet.iter_rows()]


def kinds(content: bytes, column: int) -> list[str]:
    sheet = load_workbook(io.BytesIO(content))["실행 기록"]
    return [row[column].data_type for row in sheet.iter_rows(min_row=2)]


def test_the_file_name_is_the_kst_minute() -> None:
    kst = timezone(timedelta(hours=9))
    assert file_name(datetime(2026, 10, 22, 0, 30, tzinfo=kst)) == "실행기록_2026-10-22_0030.xlsx"
    # UTC 15:30 은 KST 다음 날 00:30
    assert file_name(datetime(2026, 10, 21, 15, 30, tzinfo=UTC)) == "실행기록_2026-10-22_0030.xlsx"
    with pytest.raises(ValueError, match="시간대"):
        file_name(datetime(2026, 10, 22, 0, 30))


def test_the_header_and_a_full_line() -> None:
    content = workbook([LINE])
    assert MEDIA_TYPE == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    header, row = cells(content)
    assert (
        header
        == HEADER
        == (
            "시각",
            "모듈",
            "문서",
            "흐름",
            "AI 설정 버전",
            "담당자",
            "처리 시간(초)",
            "토큰",
            "비용(추정, USD)",
            "상태",
            "검토",
            "시험용",
        )
    )
    assert row == (
        "2026-10-22T09:30:00+09:00",
        "그린워싱",
        "지어낸 보고서.pdf",
        "greenwash.colab@E0",
        "v3",
        "담당자 가",
        485,
        108100,
        0.58,
        "완료",
        "검토 중",
        "예",
    )


def test_labels_and_fallbacks() -> None:
    lines = [
        replace(LINE, module="inventory.scope3", status="failed", review="pending"),
        replace(LINE, module="newmodule", status="processing", review="confirmed", created_by_name=None),
        replace(LINE, created_by_name=None, created_by_username=None),
    ]
    rows = cells(workbook(lines))[1:]
    assert [(r[1], r[9], r[10]) for r in rows] == [
        ("온실가스 Scope 3", "실패", "미검토"),
        ("newmodule", "처리 중", "확정"),  # 모르는 모듈 id 는 그대로
        ("그린워싱", "완료", "검토 중"),
    ]
    assert [r[5] for r in rows] == ["담당자 가", "user11", "알 수 없는 사람"]


def test_empty_numbers_are_an_en_dash_and_empty_words_are_blank() -> None:
    """M6: 수 칸 셋은 값이 없으면 「–」(queued 줄은 셋 다, 그 밖은 처리 시간 null).
    글 칸(AI 설정·검토·테스트)은 빈칸."""
    queued = replace(LINE, status="queued", duration_sec=None, tokens=0, cost_usd=0.0)
    failed = replace(LINE, status="failed", duration_sec=None, tokens=12, cost_usd=0.0)
    blank = replace(LINE, ai_setting=None, review=None, is_test=False)
    q, f, b = cells(workbook([queued, failed, blank]))[1:]
    assert (q[6], q[7], q[8]) == ("–", "–", "–")
    assert (f[6], f[7], f[8]) == ("–", 12, 0)
    assert (b[4], b[10], b[11]) == (None, None, None)
    assert (b[6], b[7], b[8]) == (485, 108100, 0.58)  # 분모: 값이 있으면 수


def test_formula_shaped_names_stay_text() -> None:
    names = ["=1+1", "+1+1", "-1", "@SUM(A1)", "\t=1", "\x01=2+2"]
    content = workbook([replace(LINE, document_name=name) for name in names])
    assert kinds(content, 2) == ["s"] * len(names)
    # 제어 문자만 지운다
    assert [row[2] for row in cells(content)[1:]] == ["=1+1", "+1+1", "-1", "@SUM(A1)", "\t=1", "=2+2"]


def test_no_lines_is_the_header_only() -> None:
    assert cells(workbook([])) == [HEADER]


def test_a_documentless_run_has_a_blank_document_cell() -> None:
    """ND1: 문서 없는 흐름의 실행은 문서 이름이 None — 칸은 빈칸(「–」 는 수 칸만 — 글 칸 AI 설정·검토와 같은 꼴).
    분모: 문서 실행은 이름."""
    bare, named = cells(workbook([replace(LINE, document_name=None), LINE]))[1:]
    assert bare[2] is None
    assert named[2] == LINE.document_name


def test_the_ai_setting_cell_is_the_version_name_or_the_default() -> None:
    """RL1(286): 기본 판은 경로가 「기본 설정」(웹 aiSettingText 와 같은 글)을 넘기고, 판은 이름, 없으면 빈칸."""
    assert DEFAULT_SETTING == "기본 설정"
    lines = [replace(LINE, ai_setting=DEFAULT_SETTING), LINE, replace(LINE, ai_setting=None)]
    assert [row[4] for row in cells(workbook(lines))[1:]] == ["기본 설정", "v3", None]
