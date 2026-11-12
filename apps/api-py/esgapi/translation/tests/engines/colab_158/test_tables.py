"""tables.py(코랩 셀 46 판 표 도우미) — 손으로 지은 기대값(발주서 §3 S1 의 표 범위)."""

import pytest

from esgapi.translation.engines.colab_158 import tables

SECTION = "\n".join(
    [
        "[TABLE 1]",
        "에너지 사용량",
        "| 항목 | 2025 |",
        "| --- | --- |",
        "| 전력 | 1,200 MWh |",
        "| 합계 | 3 | 4 |",
        "- merged_cells",
        "* 출처: 가상",
    ]
)


def test_table_ranges_need_a_separator_right_below() -> None:
    """R/2211-2228."""
    lines = ["제목", "| a | b |", "| --- | :---: |", "| 1 | 2 |", "끝", "| x |", "| y |"]
    assert tables.find_table_ranges(lines) == [(1, 4)]
    assert tables.is_separator("| --- | ---: |")
    assert not tables.is_separator("| -- | --- |")
    assert tables.split_md_row("| a &#124; b | c |") == ["a | b", "c"]
    assert tables.make_pipe_row(["a | b", "x\ny"]) == "| a &#124; b | x<br>y |"
    assert tables.make_separator(3) == "| --- | --- | --- |"


def test_fragments_and_reassembly() -> None:
    """R/2819-2936: 표 밖 국문 줄(L<줄>)이 먼저, 다음 머리·몸 칸(T<표>_H<열>·T<표>_R<행>C<열>). 열이 넘치는 행은 마지막
    칸에 ` | ` 로 잇는다. 번역이 없는 조각은 원래 글이고, 순수 구조 진단 줄과 태그 줄은 그대로."""
    plan = tables.collect_table_fragments(SECTION)
    assert plan is not None
    assert plan.fragments == [
        {"id": "L1", "text": "에너지 사용량"},
        {"id": "L7", "text": "* 출처: 가상"},
        {"id": "T0_H0", "text": "항목"},
        {"id": "T0_R0C0", "text": "전력"},
        {"id": "T0_R1C0", "text": "합계"},
    ]
    assert plan.ranges[0].body == [["전력", "1,200 MWh"], ["합계", "3 | 4"]]
    out = tables.reassemble_table(plan, {"L1": "Energy Use", "T0_H0": "Item", "T0_R0C0": "Electricity", "X": "y"})
    assert out == "\n".join(
        [
            "[TABLE 1]",
            "Energy Use",
            "| Item | 2025 |",
            "| --- | --- |",
            "| Electricity | 1,200 MWh |",
            "| 합계 | 3 &#124; 4 |",
            "- merged_cells",
            "* 출처: 가상",
        ]
    )
    assert tables.collect_table_fragments("[TABLE 2]\n표 아님") is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ('```json\n{"a": 1}\n```', {"a": 1}),
        ('설명 {"a": 2} 끝', {"a": 2}),
        ("[1, 2]", [1, 2]),  # 목록도 읽는다 — 부르는 쪽이 .get 에서 멈춘다(코랩대로)
    ],
)
def test_parse_json_loose(raw: str, expected: object) -> None:
    assert tables.parse_json_loose(raw) == expected


@pytest.mark.parametrize("raw", ["nope", "{bad", "} {"])
def test_parse_json_loose_raises_value_error(raw: str) -> None:
    with pytest.raises(ValueError):
        tables.parse_json_loose(raw)
