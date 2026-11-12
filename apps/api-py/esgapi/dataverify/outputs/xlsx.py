"""엑셀 dataverify-report.xlsx — 결과 dataverify.result@2 한 건에서만 칸을 채운다(새 셈 없음, 밴드 DV1a 발주서 §2-4).

코랩은 엑셀이 아니라 Code Interpreter 로 docx 를 지었다(셀 28·30 — 옮기지 않음, B18). 시트 일곱:
  요약       기업 정보·대상 테마·항목 수·핵심 항목 수·연도·단계 상태·경고(이름 · 값)
  계산 계획  산식 하나에 한 줄(번호 · 산식)
  검증 결과  검사 기록 하나에 한 줄, check 는 연도마다 한 줄(열은 VERIFY_HEADER)
  검토 글    계산 검토 리포트 원문(한 칸, 줄바꿈 유지)
  리스크     리스크 진단 표의 다섯 열. 표를 읽지 못했으면(rowsParsed ≠ parsed) 리포트 원문 한 칸
  출처       웹 검색 출처(제목 · URL — URL 끝의 「/?utm_source=openai」를 뗀다. 코랩 셀 30 의 규칙 R/1764 을 엑셀에 옮긴
             것이라 「코랩과 다른 자리」)
  설정       모델·판정 허용 오차(0.0 — 검사마다 쓴 값은 검증 결과 시트)·temperature·최대 횟수·프롬프트 id
글자 칸은 greenwash/outputs/xlsx.py 꼴로 다듬는다(판별 복사 — greenwash 를 import 하지 않는다): xlsx 가 담지 못하는 제어
문자를 지우고, `=` 로 시작해도 글자 칸으로 둔다. 다듬은 글이 한 칸의 한도(UTF-16 단위 32,767)를 넘으면 같은 열의
아랫줄(이어 칸)로 나눠 싣는다 — 이어 줄에는 넘친 열만 차 있다. 수(value·diff·tolerance)는 결과 꼴 그대로 repr 글자다.
openpyxl 의 xlsx 는 만든 시각이 들어가 바이트가 실행마다 다르다 — 시험은 읽어 들인 칸 값을 결과와 견준다.
"""

import io
import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.worksheet.worksheet import Worksheet

FILE_NAME: Final = "dataverify-report.xlsx"
MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEETS: Final = ("요약", "계산 계획", "검증 결과", "검토 글", "리스크", "출처", "설정")
CELL_LIMIT: Final = 32_767
"""xlsx 한 칸의 글자 한도. Excel 은 UTF-16 단위로 센다 — BMP 밖 글자(이모지 등)는 둘로 센다."""
PAIR_HEADER: Final = ("이름", "값")
PLAN_HEADER: Final = ("번호", "산식")
VERIFY_HEADER: Final = (
    "순번",
    "도구",
    "규칙",
    "항목",
    "연도",
    "판정",
    "차이(diff)",
    "허용 오차",
    "메모(note)",
    "설명(explanation)",
)
REVIEW_HEADER: Final = ("계산 검토 리포트",)
RISK_HEADER: Final = (
    "영역(환경/사회/지배구조)",
    "지표(소분류)",
    "관찰 내용 및 스토리",
    "잠재 리스크(데이터 품질·정보·해석)",
    "해석·가설",
)
RISK_RAW_HEADER: Final = ("리스크 진단 원문(표를 읽지 못함)",)
SOURCE_HEADER: Final = ("제목", "URL")
UTM_SUFFIX: Final = "/?utm_source=openai"
RULE_NAMES: Final = {"sum": "합계", "sum_n": "부분합", "ratio": "비율"}
KIND_NAMES: Final = {"value": "값 조회", "search": "검색", "error": "오류"}
STATUS_NAMES: Final = {"done": "마침", "failed": "실패", "not_run": "돌리지 않음"}
STAGES: Final = (("plan", "계산 계획"), ("review", "계산 검토"), ("insight", "리스크 진단"))

Cell = str | int | None


def _text(value: Any) -> str:
    """칸에 넣을 글. None 은 빈 글, 글자는 그대로, 그 밖(수·목록·dict)은 JSON 글."""
    if value is None:
        return ""
    if isinstance(value, str):
        return value
    return json.dumps(value, ensure_ascii=False)


def _quad(item: Any) -> str:
    """[대분류, 중분류, 소분류, 단위] 를 「 | 」로 잇는다. 목록이 아니면(모델이 준 그대로) 그 값의 글."""
    if isinstance(item, list):
        return " | ".join(_text(part) for part in cast("list[Any]", item))
    return _text(item)


def _stage(stage: Mapping[str, Any]) -> str:
    status = STATUS_NAMES[stage["status"]]
    if stage["partial"]:
        status += "(최대 횟수에 닿음 — 남은 도구 호출을 버림)"
    if stage["failure"] is not None:
        status += f" — {stage['failure']['kind']}: {stage['failure']['message']}"
    return status


def summary_rows(result: Mapping[str, Any]) -> list[tuple[Cell, ...]]:
    company = result["company"]
    scope = result["scope"]
    rows: list[tuple[Cell, ...]] = [
        ("기업명", company["name"]),
        ("SASB 산업분류", company["sasbIndustry"]),
        ("주요 중대토픽", "\n".join(company["materialTopics"])),
        ("보고연도", company["reportingYear"]),
        ("대상 테마", "\n".join(scope["themes"])),
        ("항목 수", int(scope["itemCount"])),
        ("핵심 항목 수", int(scope["keyItemCount"])),
        ("연도", ", ".join(scope["years"])),
    ]
    rows.extend((f"단계 · {label}", _stage(result[key])) for key, label in STAGES)
    rows.append(("경고", "\n".join(f"{w['code']}: {w['message']}" for w in result["warnings"])))
    return rows


def plan_rows(result: Mapping[str, Any]) -> list[tuple[Cell, ...]]:
    return [(n, formula) for n, formula in enumerate(result["plan"]["formulas"], start=1)]


def _items(check: Mapping[str, Any]) -> str:
    items = check["items"]
    if items["byName"] is not None:
        lines: list[str] = []
        for key, value in items["byName"].items():
            quads = cast("list[Any]", value) if key == "addends" and isinstance(value, list) else [value]
            lines.extend(f"{key}: {_quad(q)}" for q in quads)
        return "\n".join(lines)
    raw: Mapping[str, Any] = items["raw"]  # 단건 도구 — byName 이 null 이면 raw 가 찬다(결과 꼴)
    return "\n".join(f"{key} = {_text(value)}" for key, value in raw.items())


def verify_rows(result: Mapping[str, Any]) -> list[tuple[Cell, ...]]:
    rows: list[tuple[Cell, ...]] = []
    for check in result["review"]["checks"]:
        seq, tool, kind = int(check["seq"]), check["tool"], check["kind"]
        if kind == "value":
            told = "값 없음(N/A)" if check["na"] else f"값 = {check['value']}"
            rows.append((seq, tool, KIND_NAMES[kind], _quad(check["item"]), _text(check["year"]), "", "", "", "", told))
        elif kind == "search":
            told = (
                f"맞은 항목 {check['total']} · 돌려준 항목 {check['returned']} "
                f"(limit {_text(check['limit'])}, offset {_text(check['offset'])})"
            )
            where = "\n".join(f"{key} = {_text(value)}" for key, value in check["filter"].items())
            rows.append((seq, tool, KIND_NAMES[kind], where, "", "", "", "", "", told))
        elif kind == "error":
            args = _text(check["args"])
            rows.append((seq, tool, KIND_NAMES[kind], args, "", "오류", "", "", "", check["message"]))
        else:
            for year in check["years"]:
                verdict = "계산 불가" if year["note"] is not None else year["status"]
                rows.append(
                    (
                        seq,
                        tool,
                        RULE_NAMES[check["rule"]],
                        _items(check),
                        _text(year["year"]),
                        verdict,
                        _text(year["diff"]),
                        _text(check["tolerance"]),
                        _text(year["note"]),
                        year["explanation"],
                    )
                )
    return rows


def risk_rows(result: Mapping[str, Any]) -> tuple[tuple[str, ...], list[tuple[Cell, ...]]]:
    insight = result["insight"]
    if insight["rowsParsed"] == "parsed":
        keys = ("area", "indicator", "observation", "risk", "interpretation")
        return RISK_HEADER, [tuple(row[key] for key in keys) for row in insight["rows"]]
    return RISK_RAW_HEADER, [(_text(insight["report"]),)]


def source_rows(result: Mapping[str, Any]) -> list[tuple[Cell, ...]]:
    return [(_text(s["title"]), s["url"].removesuffix(UTM_SUFFIX)) for s in result["insight"]["sources"]]


def settings_rows(result: Mapping[str, Any]) -> list[tuple[Cell, ...]]:
    settings = result["settings"]
    rows: list[tuple[Cell, ...]] = [
        ("모델", _text(settings["model"])),
        ("판정 허용 오차", settings["tolerance"]),
        ("temperature", _text(settings["temperature"])),
    ]
    rows.extend((f"최대 횟수 · {label}", settings["maxSteps"][key]) for key, label in STAGES)
    rows.extend((f"프롬프트 id · {label}", _text(settings["promptIds"][key])) for key, label in STAGES)
    return rows


def cell_text(value: str) -> str:
    """xlsx 가 담지 못하는 제어 문자를 지운다(그대로 두면 openpyxl 이 IllegalCharacterError)."""
    return ILLEGAL_CHARACTERS_RE.sub("", value)


def utf16_length(value: str) -> int:
    """Excel 이 세는 길이(UTF-16 단위)."""
    return len(value.encode("utf-16-le")) // 2


def split_text(value: str) -> list[str]:
    """한 칸의 한도(UTF-16 단위)로 나눈다. BMP 밖 글자는 둘로 나뉘지 않는다. 빈 글은 빈 글 하나."""
    parts: list[str] = []
    start = 0
    used = 0
    for i, char in enumerate(value):
        width = 2 if ord(char) > 0xFFFF else 1
        if used + width > CELL_LIMIT:
            parts.append(value[start:i])
            start, used = i, 0
        used += width
    parts.append(value[start:])
    return parts


def _put(sheet: Worksheet, row: Sequence[Cell]) -> None:
    """한 줄을 싣는다. 한도를 넘는 글은 같은 열의 아랫줄(이어 줄)로 나눈다."""
    parts = [split_text(cell_text(v)) if isinstance(v, str) else [v] for v in row]
    for k in range(max(len(p) for p in parts)):
        sheet.append([p[k] if k < len(p) else None for p in parts])
        for cell in sheet[sheet.max_row]:
            if cell.data_type == "f":  # `=` 로 시작하는 글 — 수식이 아니라 글자로
                cell.data_type = "s"


def build(result: Mapping[str, Any]) -> bytes:
    """결과 한 건 → xlsx 바이트."""
    book = Workbook()
    first = book.active
    assert first is not None  # noqa: S101 — 새 Workbook 은 시트 하나를 갖고 시작한다
    first.title = SHEETS[0]
    risk_header, risks = risk_rows(result)
    pages: list[tuple[tuple[str, ...], list[tuple[Cell, ...]]]] = [
        (PAIR_HEADER, summary_rows(result)),
        (PLAN_HEADER, plan_rows(result)),
        (VERIFY_HEADER, verify_rows(result)),
        (REVIEW_HEADER, [(_text(result["review"]["report"]),)]),
        (risk_header, risks),
        (SOURCE_HEADER, source_rows(result)),
        (PAIR_HEADER, settings_rows(result)),
    ]
    for n, (header, rows) in enumerate(pages):
        sheet = first if n == 0 else book.create_sheet(SHEETS[n])
        _put(sheet, header)
        for row in rows:
            _put(sheet, row)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
