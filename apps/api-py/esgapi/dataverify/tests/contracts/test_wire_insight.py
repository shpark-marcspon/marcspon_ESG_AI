"""contracts/wire 의 인사이트 표 읽기·출처(발주서 §2-3, §3 S12). 기대값은 손으로 적었다. 글은 전부 지은 것."""

from collections.abc import Mapping
from typing import Any

import pytest

from esgapi.dataverify.contracts.wire import to_insight_rows, to_sources

ROW_A = {
    "area": "환경",
    "indicator": "가상 지표 A",
    "observation": "관찰 A",
    "risk": "리스크 A",
    "interpretation": "해석 A",
}
ROW_B = {
    "area": "사회",
    "indicator": "가상 지표 B",
    "observation": "관찰 B",
    "risk": "리스크 B",
    "interpretation": "해석 B",
}
HEAD = "| 영역 | 지표 | 관찰 | 리스크 | 해석 |"
LINE_A = "| 환경 | 가상 지표 A | 관찰 A | 리스크 A | 해석 A |"
LINE_B = "| 사회 | 가상 지표 B | 관찰 B | 리스크 B | 해석 B |"


CASES: list[tuple[str, tuple[list[dict[str, str]], str]]] = [
    (f"## 가상\n\n{HEAD}\n|---|---|---|---|---|\n{LINE_A}\n", ([ROW_A], "parsed")),
    # 표 둘(영역별) — 사이의 글은 건너뛴다
    (
        f"### 환경\n{HEAD}\n|---|---|---|---|---|\n{LINE_A}\n\n가상 설명\n\n"
        f"### 사회\n{HEAD}\n| --- | --- | --- | --- | --- |\n{LINE_B}\n",
        ([ROW_A, ROW_B], "parsed"),
    ),
    # 구분선 꼴 변형: 정렬 콜론·앞뒤 「|」 없음·대시 하나
    (f"{HEAD}\n|:---|:---:|---:|-|---|\n{LINE_A}", ([ROW_A], "parsed")),
    (
        "영역 | 지표 | 관찰 | 리스크 | 해석\n--- | --- | --- | --- | ---\n"
        "환경 | 가상 지표 A | 관찰 A | 리스크 A | 해석 A",
        ([ROW_A], "parsed"),
    ),
    # 칸 글은 strip 만(안의 빈칸은 그대로)
    (
        f"{HEAD}\n|---|---|---|---|---|\n|  환경 |가상  지표 A| 관찰 A | 리스크 A | 해석 A  |",
        ([{**ROW_A, "indicator": "가상  지표 A"}], "parsed"),
    ),
    # 칸 넷이 섞인 데이터 줄 → 읽지 않음
    (f"{HEAD}\n|---|---|---|---|---|\n{LINE_A}\n| 환경 | 가상 | 관찰 | 리스크 |\n", ([], "unparsed")),
    # 머리줄이 넷 칸
    ("| 영역 | 지표 | 관찰 | 리스크 |\n|---|---|---|---|\n| 환경 | 가상 | 관찰 | 리스크 |", ([], "unparsed")),
    # 표가 둘인데 하나가 넷 칸
    (
        f"{HEAD}\n|---|---|---|---|---|\n{LINE_A}\n\n| 가 | 나 | 다 | 라 |\n|---|---|---|---|\n| 1 | 2 | 3 | 4 |",
        ([], "unparsed"),
    ),
    # 표 없음(구분선 없는 「|」 줄)
    (f"가상 글\n{HEAD}\n{LINE_A}\n", ([], "unparsed")),
    ("표가 없는 가상 리포트", ([], "unparsed")),
    # 머리줄·구분선만 있고 데이터 줄 0
    (f"{HEAD}\n|---|---|---|---|---|\n\n가상", ([], "unparsed")),
    ("", ([], "none")),
    ("  \n\n ", ([], "none")),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_insight_rows_by_hand(text: str, expected: Any) -> None:
    assert to_insight_rows(text) == expected


def test_sources_keep_the_first_url_and_the_order() -> None:
    citations: list[Mapping[str, Any]] = [
        {"url": "https://example.com/a", "title": "가상 A"},
        {"url": "https://example.org/b", "title": "가상 B"},
        {"url": "https://example.com/a", "title": "가상 A 다시"},
        {"url": "https://example.net/c", "title": None},
    ]
    assert to_sources(citations) == [
        {"title": "가상 A", "url": "https://example.com/a"},
        {"title": "가상 B", "url": "https://example.org/b"},
        {"title": None, "url": "https://example.net/c"},
    ]
    assert to_sources([]) == []
