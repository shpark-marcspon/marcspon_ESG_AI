"""지은 문서(synthetic)를 만든다: document.json · char-places.json · cases.json.

    실행: (cd apps/api-py && uv run python -m esgapi.reconcile.tests.golden.synthetic.build)

★ 문서와 숫자는 전부 지어낸 것이다. 어느 회사의 실제 값도 아니다.
꼴은 esg-lab `ts/reconcile/test/fixtures/chart-doc.synthetic.json` 을 본떴다(파일을 베끼지 않고 직접 지었다).

이 문서가 재는 것: 네 보고서에는 하나도 없는 글자들 — 보충 평면 글자(이모지), U+FEFF, U+0085, U+001C, U+2028,
아랍-인도 숫자, 전각 숫자, 끝 줄바꿈 — 과 JS·파이썬이 달리 읽는 꼴(`위\\b`, `Math.round`, `$`, `\\s`, `\\d`).
본보기 번호 ①~⑧ 은 발주서 PY6 §2 의 「언어 차이 본보기」 번호다.
"""

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SHA = "5" * 64  # 지어낸 값. 진짜 PDF 의 해시가 아니다
FILE_NAME = "reconcile-doc.synthetic.pdf"


def units(text: str) -> int:
    """UTF-16 자리 수."""
    return len(text.encode("utf-16-le", "surrogatepass")) // 2


LONG_TITLE = "가" * 199 + "😀" + "나다 (제목 후보 200자 자르기: 이모지가 경계에 걸린다)"

# (id, kind, page, bbox, text | None, table_id | None)
BLOCKS: list[tuple[str, str, int, list[float], str | None, str | None]] = [
    ("p1-b1", "heading", 1, [50, 60, 500, 80], "2025 지속가능경영 요약 (지어낸 문서)", None),
    # ① 위\b · 기\b · 종\b
    (
        "p1-b2",
        "paragraph",
        1,
        [50, 100, 500, 140],
        "배출량은 1,234.5 tCO2eq 로 전년 대비 -3.2% 줄었다. Scope 1 은 800톤, 제3조와 2단계. "
        "3위 안에 든다 3위A 2기 운영 2기B 4종 설비 4종",
        None,
    ),
    # ② 아랍-인도 숫자와 전각 숫자
    ("p1-b3", "paragraph", 1, [50, 150, 500, 170], "아랍 숫자 ١٢٣ 과 전각 １２３ 그리고 45명, 전각 뒤 ６7 과 ١8", None),
    # ③ U+FEFF · U+0085 · U+001C · U+00A0
    ("p1-b4", "paragraph", 1, [50, 180, 500, 200], "앞﻿12\u0085 뒤 \u001c34 56 원 그리고﻿-7 과 \u0085-8", None),
    # ⑥ 숫자 앞의 이모지 (UTF-16 자리, 앞뒤 글의 창)
    (
        "p1-b5",
        "paragraph",
        1,
        [50, 210, 500, 230],
        "성과 😀 +7.5% 달성 🎉🎉🎉🎉🎉🎉 Scope 12개 과제 🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉XKCD 77 😀9ton",
        None,
    ),
    # ④ `$` 와 끝 줄바꿈: 종류 규칙이 보는 블록 원문의 `.\n` 뒤 숫자
    ("p1-b6", "paragraph", 1, [50, 240, 500, 270], "문장의 끝.\n7", None),
    ("p1-b7", "paragraph", 1, [50, 280, 500, 300], "글 끝. 9", None),
    # ⑤ U+2028 이 든 글
    ("p1-b8", "paragraph", 1, [50, 310, 500, 330], "합계 77 다음 줄 88건", None),
    ("p1-b9", "table", 1, [50, 340, 500, 560], None, "p1-t1"),
    # ⑧ Math.round 의 경계: 왼쪽 끝 101.0 / 2 = 50.5 (JS 51, 파이썬 round 50). 셋이 한 세로줄이면 눈금이다
    ("p1-b10", "paragraph", 1, [101.0, 600, 110.0, 610], "10", None),
    ("p1-b11", "paragraph", 1, [102.0, 620, 121.0, 630], "20", None),
    ("p1-b12", "paragraph", 1, [102.4, 640, 133.3, 650], "30", None),
    # 오른쪽 끝이 같은 세로줄(2pt 안)이지만 간격이 같지 않다 → 눈금이 아니다
    ("p1-b13", "paragraph", 1, [300, 600, 401.0, 610], "5", None),
    ("p1-b14", "paragraph", 1, [310, 620, 400.2, 630], "7", None),
    ("p1-b15", "paragraph", 1, [320, 640, 400.9, 650], "12", None),
    ("p1-b16", "table", 1, [50, 660, 500, 730], None, "p1-t2"),
    ("p1-b17", "paragraph", 1, [280, 770, 300, 780], "3", None),  # 쪽 번호 (아래 8%)
    ("p1-b18", "paragraph", 1, [280, 10, 300, 20], "2025", None),  # 쪽 머리의 네 자리 수 (위 8%)
    ("p2-b1", "heading", 2, [50, 80, 500, 100], "2. 사회", None),
    ("p2-b2", "paragraph", 2, [50, 110, 500, 130], LONG_TITLE, None),
    ("p2-b3", "paragraph", 2, [50, 140, 500, 150], "단위: 백만 원", None),
    ("p2-b4", "table", 2, [50, 160, 500, 260], None, "p2-t2"),
    ("p2-b5", "paragraph", 2, [50, 270, 500, 280], "1) 각주: 2024년 기준, 연 1회 이상 점검", None),
    ("p2-b6", "paragraph", 2, [50, 290, 500, 300], "※ 참고 5점 척도, 1에 가까울수록 낮다", None),
    (
        "p2-b7",
        "paragraph",
        2,
        [50, 310, 500, 350],
        "ISO 14001 인증, 문단 12, 3개년 계획, 10년간 유지, 1억 원당 2.5톤, 3종의 설비, 5개 주제, ’25 목표, "
        "12/31 마감, 45쪽 참조, 각주*3, KPI 7 과 KPI 8개, Scope 1, 2 합계 1,000 tCO2e",
        None,
    ),
    ("p2-b8", "table", 2, [50, 360, 500, 400], None, "p2-t1"),
    ("p2-b9", "paragraph", 2, [50, 410, 500, 420], "2,345", None),  # 숫자뿐인 블록 (가장자리 아님)
    (
        "p2-b10",
        "paragraph",
        2,
        [50, 430, 500, 440],
        "https://example.invalid/a1/2025 문의 02-1234-5678, 2025.7.1 발간 v1.2.3",
        None,
    ),
    ("p2-b11", "paragraph", 2, [50, 450, 500, 460], "12 차례의 제목 줄", None),
    ("p2-b12", "paragraph", 2, [50, 470, 500, 480], "글자만 있는 블록", None),
    ("p2-b13", "paragraph", 2, [50, 490, 500, 500], "", None),
    ("p2-b14", "table", 2, [50, 510, 500, 560], None, "p2-t3"),
    (
        "p2-b15",
        "paragraph",
        2,
        [50, 570, 500, 590],
        "1. 첫째 항목 30%p 상승\n2. 둘째 항목 10,20,30% 범위 10~20 과 3 ~ 5\n· 3. 셋째 (1) 가) 2) 끝",
        None,
    ),
    ("p2-b16", "paragraph", 2, [280, 775, 300, 785], "17", None),  # 쪽 번호
]

TABLES: list[dict[str, Any]] = [
    {
        "id": "p1-t1",
        "page": 1,
        "cells": [
            ["구분", "단위", "2023", "2024", "2025"],
            ["Scope 1", "tCO2eq", "1,234", "1,100.5", "(980)"],
            ["Scope 2", "tCO2eq", "△2,000", "▲15", "-"],
            ["감축률", "%", "3.2%", "+4.0%", "N/A"],
            ["비고", "", "기준연도 대비 42% 감축", "10~20", "116,818 15,649"],
            ["구분", "단위", "남성", "여성", "합계"],
            ["임직원", "명", "1,200명", "800 명", "2,000"],
            ["", "", "04", "2025.7.1", "1.2.3"],
            ["평균", "", "Ｎ／Ａ", "n/a", "5 명"],  # ⑦ ⑤
            ["끝줄", "", "12\n", "١٢٣", "１２３"],  # ④ ②
            ["연도", "", "2025", "FY2025", "6(1)"],
            ["언어", "", "3위 ", "3위A", "😀 7개 달성"],  # ① ⑥
            ["빈칸", "", "﻿34\u0085", "\u001c56", "−0.0"],  # ③
            ["", "", "0.50 MWh", "▼3%p", "(1,5)"],
        ],
        "header": {"rows": [0], "cols": [0, 1], "basis": "rows_before_first_numeric_row"},
        "method": "lines",
        "status": "ok",
        "footnote_marks": [{"row": 1, "col": 2, "mark": "1)"}, {"row": 1, "col": 2, "mark": "*"}],
    },
    {
        "id": "p1-t2",
        "page": 1,
        "cells": [
            ["항목", "페이지", "값"],
            ["지배구조", "12", "34"],
            ["전략", "13~15", "56 %"],
            ["눈금", "", "600 400"],
            ["축", "", "0 20 40 60"],
            ["값 둘", "", "18.2 18.1"],
            ["글", "글", "글"],
        ],
        "header": {"rows": [0], "cols": [0], "basis": "rows_before_first_numeric_row"},
        "method": "text",
        "status": "low_confidence",
        "footnote_marks": [],
    },
    {
        "id": "p2-t1",
        "page": 2,
        "cells": [],
        "header": {"rows": [], "cols": [], "basis": "empty"},
        "method": "none",
        "status": "failed",
        "footnote_marks": [],
    },
    {
        "id": "p2-t2",
        "page": 2,
        "cells": [
            ["지표", "GRI 번호", "2024", "2025"],
            ["매출 (단위: 백만 원)", "201-1", "1,000", "1,200"],
            ["", "2-7", "50", "55"],
            ["합계", "405", "1,050", "1,255"],
        ],
        "header": {"rows": [0], "cols": [0], "basis": "rows_before_first_numeric_row"},
        "method": "lines",
        "status": "ok",
        "footnote_marks": [],
    },
    {
        "id": "p2-t3",
        "page": 2,
        "cells": [["이름", "값"], ["가", "1"], ["나", "2"]],
        "header": {"rows": [0], "cols": [0], "basis": "rows_before_first_numeric_row"},
        "method": "lines",
        "status": "ok",
        "footnote_marks": [],
    },
]

# 글자 자리를 일부러 다르게 만드는 그릇.
UNLINKED = {"p2-b9": "glyphs_not_aligned"}  # 분해가 글자 자리를 잇지 못했다
MISSING = {"p2-t3:r1c1", "p2-b11"}  # 글자 자리에 그릇이 없다
SPLIT = {"p1-b2": 7, "p1-b6": 6, "p2-b15": 20}  # 이 자리에서 줄이 바뀐다 (p1-b2 는 `1,234.5` 의 한가운데)
SAME_LINE_SPLIT = {"p1-b8": 5}  # 같은 줄의 토막 둘 (상자가 하나로 합쳐진다)
SHORT = {"p2-b7": 10}  # 앞의 몇 글자만 좌표가 있다 (뒤의 숫자는 좌표 있는 글자가 없다)
GAP = {"p1-b6"}  # 줄바꿈 글자에는 좌표가 없다 (토막 사이에 자리 하나가 빈다)


def runs_for(container_id: str, text: str, box: list[float]) -> list[dict[str, Any]]:
    n = units(text)
    x, y = box[0], box[1]

    def run(start: int, count: int, line: int, y_shift: float = 0.0) -> dict[str, Any]:
        xs = [round(x + 4.5 * (start + k) * (0 if line else 1) + 4.5 * k * (1 if line else 0), 2) for k in range(count)]
        top = y + 12.0 * line + y_shift
        return {"start": start, "y0": top, "y1": top + 10.0, "x0": xs, "x1": [round(v + 4.25, 2) for v in xs]}

    if container_id in SHORT:
        return [run(0, min(n, SHORT[container_id]), 0)]
    if container_id in SPLIT:
        at = SPLIT[container_id]
        skip = 1 if container_id in GAP else 0
        return [run(0, at, 0), run(at + skip, n - at - skip, 1)]
    if container_id in SAME_LINE_SPLIT:
        at = SAME_LINE_SPLIT[container_id]
        first = run(0, at, 0)
        second = run(at, n - at, 0, y_shift=1.5)  # 조금 어긋났지만 절반 넘게 겹친다
        return [first, second]
    return [run(0, n, 0)]


def build() -> tuple[dict[str, Any], dict[str, Any]]:
    blocks: list[dict[str, Any]] = []
    order: dict[int, int] = {}
    for block_id, kind, page, bbox, text, table_id in BLOCKS:
        order[page] = order.get(page, 0) + 1
        block: dict[str, Any] = {
            "id": block_id,
            "kind": kind,
            "page": page,
            "bbox": bbox,
            "order": order[page],
            "section_id": None,
        }
        if text is not None:
            block["text"] = text
        if table_id is not None:
            block["table_id"] = table_id
        blocks.append(block)
    tables: list[dict[str, Any]] = [
        {**t, "n_rows": len(t["cells"]), "n_cols": len(t["cells"][0]) if t["cells"] else 0, "notes": []} for t in TABLES
    ]
    source = {"file_name": FILE_NAME, "sha256": SHA, "page_count": 3}
    document: dict[str, Any] = {
        "schema_version": "0.1",
        "source": source,
        "parser": {
            "name": "docparse",
            "version": "synthetic",
            "table_strategy": "auto",
            "llm_used": False,
            "ocr_used": False,
        },
        "pages": [
            {
                "page": 1,
                "width": 600.0,
                "height": 800.0,
                "text_layer": "present",
                "char_count": 900,
                "image_coverage": 0.0,
                "columns": 1,
                "notes": [],
            },
            {
                "page": 2,
                "width": 600.0,
                "height": 800,
                "text_layer": "present",
                "char_count": 700,
                "image_coverage": 0.0,
                "columns": 1,
                "notes": [],
            },
            {
                "page": 3,
                "width": 600.0,
                "height": 800.0,
                "text_layer": "none",
                "char_count": 0,
                "image_coverage": 1.0,
                "columns": 1,
                "notes": ["지어낸 스캔 쪽"],
            },
        ],
        "sections": [],
        "blocks": blocks,
        "tables": tables,
    }

    containers: list[dict[str, Any]] = []
    unlinked: list[dict[str, Any]] = []

    def add(container_id: str, kind: str, page: int, box: list[float], text: str) -> None:
        if container_id in MISSING or text == "":
            return
        if container_id in UNLINKED:
            unlinked.append({"id": container_id, "page": page, "reason": UNLINKED[container_id]})
            return
        runs = runs_for(container_id, text, box)
        xs0 = [v for r in runs for v in r["x0"]]
        xs1 = [v for r in runs for v in r["x1"]]
        bbox = [min(xs0), min(r["y0"] for r in runs), max(xs1), max(r["y1"] for r in runs)]
        containers.append({"id": container_id, "kind": kind, "page": page, "bbox": bbox, "runs": runs})

    table_box = {b[5]: b[3] for b in BLOCKS if b[5] is not None}
    for block_id, kind, page, bbox, text, _ in BLOCKS:
        if kind != "table" and text is not None:
            add(block_id, "block", page, bbox, text)
    for table in TABLES:
        box = table_box[table["id"]]
        for r, cells in enumerate(table["cells"]):
            for c, raw in enumerate(cells):
                add(f"{table['id']}:r{r}c{c}", "cell", table["page"], [box[0] + 90.0 * c, box[1] + 15.0 * r, 0, 0], raw)
    places: dict[str, Any] = {
        "schema_version": "0.1",
        "source": source,
        "parser": {"name": "docparse", "version": "synthetic", "table_strategy": "auto"},
        "unit": "utf16",
        "containers": containers,
        "unlinked": unlinked,
    }
    return document, places


# 낱개 본보기: 십진 도우미와 표기 규칙. 네 문서로는 TS 와 견줄 길이 없는 것들이다.
CASES: dict[str, Any] = {
    "dec": {
        "shift10": [
            ["12.5", 3],
            ["12.5", -2],
            ["0", 5],
            ["-0.050", 1],
            ["1200", -2],
            ["-7", 0],
            ["0.001", 3],
            ["12.5", 1.5],
            ["x", 1],
        ],
        "roundToPow10": [
            ["1250", 2, "half_up"],
            ["1250", 2, "half_even"],
            ["1250", 2, "down"],
            ["1350", 2, "half_even"],
            ["-1250", 2, "half_up"],
            ["-1250", 2, "down"],
            ["12.345", -2, "half_up"],
            ["12.345", -2, "half_even"],
            ["12.345", -2, "down"],
            ["12.5", 0, "half_even"],
            ["13.5", 0, "half_even"],
            ["0.4", 0, "half_up"],
            ["999", 3, "half_up"],
            ["499", 3, "half_up"],
        ],
        "compare": [["1", "1.0"], ["1", "2"], ["-1", "-2"], ["0.30", "0.3"], ["-0", "0"], ["10", "9.999"]],
        "sub": [["1", "0.9"], ["0.1", "0.3"], ["100", "100.00"], ["-5", "-5"], ["12.50", "2.25"]],
    },
    "notation": {
        # 칸: 갈래 열(blank·value·no_value_marker·year·code·date·range·multi_number·text_with_digits·text)과 부호·표시
        "cells": [
            "",
            "  ",
            "\t\n",
            "1,234",
            "1,234.50",
            "0.5",
            "(123)",
            "-45",
            "−45",
            "–45",
            "+45",
            "△1,000",
            "▲3",
            "▼3",
            "-",
            "—",
            "ㅡ",
            "N/A",
            "Ｎ／Ａ",
            "n/a",
            "N / A",
            "해당없음",
            "해당 사항 없음",
            "미집계",
            "2025",
            "2100",
            "1899",
            "FY2025",
            "'25",
            "2025년",
            "2025년도",
            "04",
            "007",
            "1.2.3",
            "6(1)",
            "6(1)(가)",
            "2025.7.1",
            "2025-07-01",
            "2025. 7.",
            "10~20",
            "65-66",
            "3~17%",
            "-5~+5%p",
            "116,818 15,649",
            "64, 216",
            "기준연도 대비 42% 감축",
            "글자만",
            "12명",
            "12 명",
            "3.5배",
            "45%",
            "45%p",
            "12년",
            "3분기",
            "5위",
            "12 tCO2eq",
            "0.50 MWh",
            "7 ㎡",
            "30 ℃",
            "1,2",
            "12,34",
            "(12",
            "12)",
            "-(12)",
            "( 12 )",
            "1 2",
            "12abcdefghijk",
            "12 개 사",
            # ④ 끝 줄바꿈 ⑤ U+2028 ③ 빈칸의 집합 ② 숫자의 집합 ⑦ NFKC 와 소문자 ⑥ 이모지
            "12\n",
            "12\r\n",
            "5 명",
            "5 ",
            "﻿34",
            "34﻿",
            "\u008534",
            "34\u0085",
            "\u001c56",
            "56\u001f",
            "7 명",
            "١٢٣",
            "１２３",
            "１，２３４",
            "۱۲۳",
            "１２명",
            "①",
            "12①",
            "Ⅳ",
            "ｎ／ａ",
            "ＮＡ",
            "😀",
            "😀 7",
            "7😀",
            "12 😀개",
            "3위",
            "3위 ",
            "K2",
            "12 ℓ",
            "5µm",
            "−0",
            "-0.00",
            "(0)",
            "0",
            "00",
            "0.0",
            "1e5",
            "1.",
            ".5",
            "1,000,000",
            "1,00",
            "12.5.",
            "+",
            "%",
            "12 %",
            "12% 증가",
        ],
        # 글: 갈래 일곱(value·year·date_part·identifier·ordinal·marker·range_part)과 부호, 그리고 언어 차이 본보기
        "texts": [
            "배출량 1,234.5 tCO2eq, 전년 대비 -3.2% (△5, ▲7, +9)",
            "2025년 3월 15일, 2025.7.1 과 2025-07-01, ’25 와 '24",
            "Scope 1, GRI 305-1, CO2, 02-1234-5678",
            "https://example.invalid/2025/a1 와 a@b1.invalid 77",
            "제3조 1차 2단계 3위 4등급 5호 6번 7조 8항 9기 10회차 11순위 12세대 13종",
            "1) 첫째 (2) 둘째 가) 3) 셋",
            "1. 줄 머리\n2. 다음 줄\n · 3. 점 뒤 4. 줄 가운데",
            "10~20, 3 ~ 5, 7∼9, 30〜40%",
            "333.6조 원, 187조 9,673억 원, 3조 2항",
            "2050 탄소중립, 2025 kWh, 2025MW, 1999A",
            "28MW 34.4ton 940ppm 3R 24X365 5kg 7km/h 9 L",
            "10,20,30% 와 007, 04",
            "5년간 3년차 2년 이상 10년 동안 2025년간",
            "3월간 5일 평균 12월 25일, 월 3일",
            "100만 톤이다 50억 원으로 3천 명의 7건씩 2시간까지 4배",
            "값은(-5)이고 x-5 는 a−5, 3-5",
            # ① JS 의 \b 는 ASCII 낱말 기준
            "3위 ",
            "3위A",
            "3위",
            "3위_",
            "3위가",
            "2기 ",
            "2기B",
            "2기",
            "4종",
            "4종 ",
            "4종9",
            "4종류",
            # ② ③ ⑥ ④ ⑤
            "١٢٣ 과 １２３ 사이의 45",
            "６7 과 ١8 과 ８",
            "앞﻿12\u0085 뒤 \u001c34 56 원",
            "﻿-7 과 \u0085-8 과 \u001c-9 과  -10 과  -11",
            "😀 +7.5% 달성",
            "😀😀😀😀😀😀 12개 Scope 😀3",
            "🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉🎉XKCD 77",
            "Scope😀😀😀😀 5",
            "7😀😀😀😀😀😀원",
            "7 😀😀😀😀😀😀😀😀😀😀😀😀😀 MW",
            "끝.\n7",
            "5원\n",
            "5\n",
            "1\n. 가",
            "합계 77 다음 88건",
            "7 원",
            " 1. 가",
            "\u00851. 가",
            "﻿1. 가",
            "\u001c1. 가",
            "제\n3",
            "’\n25",
            "",
            "글자만",
            "12",
            "-12",
            "－12",
            "1.5.2",
            "v1.2.3",
            "2025.13",
            "2025.7.",
            "19991231",
            "1,2345",
            "12,345,67",
        ],
        "quotes": [
            ["가 12 나 12 다 12", "12", 2],
            ["가 12 나 12", "12", 3],
            ["😀 12 😀 12", "12", 2],
            ["가나다", "", 1],
            ["가 12", "12", 0],
            ["😀😀", "😀", 2],
            ["aaa", "aa", 2],
            ["가 12", "12", 1.5],
        ],
        # (글, 그 글 속 값 후보의 원문 글자) → kindOf. 종류 규칙의 언어 차이 본보기.
        "kindOf": [
            ["문장의 끝.\n7", "7"],
            ["글 끝. 9", "9"],
            ["글 끝.9", "9"],
            ["12 차례의 제목 줄", "12"],
            ["12 😀", "12"],
            ["12 😀😀", "12"],
            ["12 " + "가" * 40, "12"],
            ["12 " + "가" * 41, "12"],
            ["12 " + "😀" * 40, "12"],
            ["12 " + "😀" * 41, "12"],
            ["﻿12 차례의 줄﻿", "12"],
            ["\u008512 차례의 줄", "12"],
            ["12 차례의\n줄", "12"],
            ["Scope 1, 2 합계", "2"],
            ["KPI 7 과", "7"],
            ["KPI 8개", "8"],
            ["ISO 14001에 따라", "14001"],
            ["😀" * 15 + "AKPI 7", "7"],
            ["😀" * 16 + "KPI 7", "7"],
            ["가" * 29 + "AKPI 7", "7"],
            ["가" * 28 + "AKPI 7", "7"],
            ["문단 12 참조", "12"],
            ["12/31 마감", "31"],
            ["45쪽 참조", "45"],
            ["45쪽지", "45"],
            ["각주*3 과", "3"],
            ["’25 목표", "25"],
            ["3개년 계획", "3"],
            ["10년간 유지", "10"],
            ["5점 척도", "5"],
            ["1에 가까울수록", "1"],
            ["1억 원당 2.5톤", "1"],
            ["3종의 설비", "3"],
            ["5개 주제", "5"],
            ["5개월", "5"],
            ["연 1회 이상", "1"],
            ["2회 실시", "2"],
            ["분기 2회", "2"],
            ["값은 42% 다", "42%"],
            ["1,000 tCO2e", "1,000"],
        ],
    },
}


def main() -> None:
    document, places = build()
    for name, value in (("document.json", document), ("char-places.json", places), ("cases.json", CASES)):
        (HERE / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", errors="surrogatepass"
        )
    print(
        f"블록 {len(document['blocks'])} · 표 {len(document['tables'])} · "
        f"그릇 {len(places['containers'])} · 못 이은 그릇 {len(places['unlinked'])}"
    )


if __name__ == "__main__":
    main()
