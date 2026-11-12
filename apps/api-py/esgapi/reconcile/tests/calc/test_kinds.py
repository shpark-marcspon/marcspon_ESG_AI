"""값 후보의 종류 — 문서 하나의 종류 표(ID → 종류) 전체를 == 로 견준다.

`calc/test_kinds_ts.py` 는 값 후보 하나의 글자를 뽑아 본다. 여기서는 `extract_document(…, kinds=True).kinds`
dict 전체를 견주고(MARC-ENT-280, 밴드 NK1), 규칙마다 「맞는 쪽 / 한 칸 비켜 안 맞는 쪽」을 짝으로 둔다. 눈금 판정의
순수 도우미(`_round_pair`·`_evenly_spaced`)는 직접 부른다. 대상 함수는 시험 안에서 부른다.

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

from collections.abc import Mapping, Sequence

import pytest

from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.kinds import _evenly_spaced, _round_pair  # pyright: ignore[reportPrivateUsage]
from esgapi.reconcile.calc.types import DocModel, ValueKind
from esgapi.reconcile.tests.support import HEADER, BlockSpec, TableSpec, synthetic_document


def kinds_of(document: DocModel) -> Mapping[str, ValueKind] | None:
    return extract_document(document, "s", titles="own", kinds=True).kinds


def kinds_in(text: str) -> Mapping[str, ValueKind] | None:
    """글 블록 하나(`p1-b1`)의 종류 표."""
    return kinds_of(synthetic_document("s", [], [BlockSpec("p1-b1", text)]))


def blocks(*specs: tuple[str, tuple[float, float, float, float]]) -> DocModel:
    """한 쪽에 블록만 둔 문서. 블록 id 는 `p1-b1` 부터 차례로."""
    return synthetic_document(
        "s", [], [BlockSpec(f"p1-b{i + 1}", text, bbox=box) for i, (text, box) in enumerate(specs)]
    )


# ── 앞뒤 글자의 규칙 (kind_of) ───────────────────────────────────────────────


@pytest.mark.parametrize(
    ("text", "kinds"),
    [
        # 단위가 붙은 값은 약어 뒤 번호 규칙을 타지 않는다.
        ("ABCD 410톤", {"p1-b1#n1": "value"}),
        # 낱개 수: 두 자리까지는 센 수, 세 자리는 값.
        ("1개", {"p1-b1#n1": "count"}),
        ("12개", {"p1-b1#n1": "count"}),
        ("123개", {"p1-b1#n1": "value"}),
        # 쉼표 든 수는 앞자리 0 을 지워 두 자리가 되어도 센 수가 아니다.
        ("0,012개", {"p1-b1#n1": "value"}),
        # 음수의 자릿수는 부호를 빼고 센다.
        ("감소 -12개", {"p1-b1#n1": "count"}),
        ("ABCD -41 기준", {"p1-b1#n1": "value"}),
        # 괄호: 앞이 ) 이고 뒤가 ) 일 때만 번호다.
        ("가)1) 끝", {"p1-b1#n1": "identifier"}),
        ("주석 (123) 참조", {"p1-b1#n1": "value"}),
        # 조항 낱말 뒤, 괄호 번호 앞은 따로 번호다.
        ("문단 123", {"p1-b1#n1": "identifier"}),
        ("123(1)", {"p1-b1#n1": "identifier"}),
        # 쪽 사선: 앞의 것도 뒤의 것도 번호다.
        ("1/123", {"p1-b1#n1": "identifier", "p1-b1#n2": "identifier"}),
        ("123/4", {"p1-b1#n1": "identifier", "p1-b1#n2": "identifier"}),
        ("5쪽", {"p1-b1#n1": "identifier"}),
        # 대문자 약어 뒤: 쉼표 없는 세 자리 이상 정수는 조사가 붙어도 번호, 그보다 짧거나 소수·쉼표면 한글이 바로 오지
        # 않을 때만 번호.
        ("ABCD 410", {"p1-b1#n1": "identifier"}),
        ("ABCD 410 기준", {"p1-b1#n1": "identifier"}),
        ("ABCD 41", {"p1-b1#n1": "identifier"}),
        ("ABCD 41 기준", {"p1-b1#n1": "value"}),
        ("ABCD 4.5", {"p1-b1#n1": "identifier"}),
        ("ABCD 4.5 기준", {"p1-b1#n1": "value"}),
        ("ABCD 1,234 기준", {"p1-b1#n1": "value"}),
        ("ABCD 410명", {"p1-b1#n1": "value"}),
        ("ABCD 41명", {"p1-b1#n1": "value"}),
        ("ABCD 1,234명", {"p1-b1#n1": "value"}),
        # 차례 줄과 글 끝 쪽 번호는 세 자리까지.
        ("123 지속가능경영", {"p1-b1#n1": "identifier"}),
        ("1234 지속가능경영", {"p1-b1#n1": "value"}),
        ("글 끝. 123", {"p1-b1#n1": "identifier"}),
        ("글 끝. 1234", {"p1-b1#n1": "value"}),
        # 기간: 따옴표 뒤(세 자리라 연도 갈래가 아님), 기간 단위, 개년.
        ("’123 목표", {"p1-b1#n1": "duration"}),
        ("10년", {"p1-b1#n1": "duration"}),
        ("3개년", {"p1-b1#n1": "duration"}),
        # 빈도: 빈도 낱말이 앞에 있거나 「이상」이 뒤에 있을 때만.
        ("연 3회", {"p1-b1#n1": "count"}),
        ("3회 이상", {"p1-b1#n1": "count"}),
        ("3회 점검", {"p1-b1#n1": "value"}),
    ],
)
def test_each_rule_and_its_neighbour_give_the_whole_kind_table(text: str, kinds: dict[str, ValueKind]) -> None:
    assert kinds_in(text) == kinds


# ── 표 글 칸의 문맥과 눈금 칸 (classify_kinds) ───────────────────────────────


def test_a_text_cell_is_read_with_its_own_text_column_header_and_scale_cells() -> None:
    document = synthetic_document(
        "s",
        [
            TableSpec(
                "p1-t1",
                cells=[
                    ["항목", "GRI 번호", "비고"],
                    # 머리글 「GRI 번호」 아래(차례 줄 꼴이 아닌 글) · 칸 글의 약어 문맥
                    ["가", "항목 405 해당", "ABCD 4100 기준"],
                    # 칸 글 뒤의 문맥(회 뒤) · 글이 든 칸의 같은 간격 수는 눈금이 아니다
                    ["나", "연 3회 점검", "구간 10 20 30"],
                    # 숫자만 든 칸의 같은 간격 수는 눈금이다(앞 칸들이 눈금 판정을 건너뛴 뒤에도)
                    ["다", "10 20 30", "1"],
                ],
                header=HEADER,
            )
        ],
    )
    assert kinds_of(document) == {
        "p1-t1:r1c1#n1": "identifier",
        "p1-t1:r1c2#n1": "identifier",
        "p1-t1:r2c1#n1": "count",
        "p1-t1:r2c2#n1": "value",
        "p1-t1:r2c2#n2": "value",
        "p1-t1:r2c2#n3": "value",
        "p1-t1:r3c1#n1": "scale",
        "p1-t1:r3c1#n2": "scale",
        "p1-t1:r3c1#n3": "scale",
        "p1-t1:r3c2": "value",
    }


# ── 숫자뿐인 블록의 세로줄 (classify_kinds) ──────────────────────────────────


def test_a_block_with_two_numbers_is_left_out_of_a_column_and_does_not_stop_the_rest() -> None:
    document = blocks(
        ("40 50", (40, 160, 60, 170)),
        ("10", (40, 100, 60, 110)),
        ("20", (40, 120, 60, 130)),
        ("30", (40, 140, 60, 150)),
    )
    assert kinds_of(document) == {
        "p1-b1#n1": "value",
        "p1-b1#n2": "value",
        "p1-b2#n1": "scale",
        "p1-b3#n1": "scale",
        "p1-b4#n1": "scale",
    }


@pytest.mark.parametrize(
    "boxes",
    [
        # 왼쪽 끝만 맞춘 셋 + 멀리 있는 넷째
        [(40, 100, 60, 110), (40, 120, 70, 130), (40, 140, 80, 150), (300, 400, 330, 410)],
        # 오른쪽 끝만 맞춘 셋 + 멀리 있는 넷째
        [(40, 100, 90, 110), (50, 120, 90, 130), (60, 140, 90, 150), (300, 400, 330, 410)],
    ],
)
def test_three_blocks_on_one_edge_are_a_scale_and_a_far_fourth_is_not(
    boxes: Sequence[tuple[float, float, float, float]],
) -> None:
    document = blocks(*zip(("10", "20", "30", "75"), boxes, strict=True))
    assert kinds_of(document) == {"p1-b1#n1": "scale", "p1-b2#n1": "scale", "p1-b3#n1": "scale", "p1-b4#n1": "value"}


def test_right_edges_within_two_points_are_one_column() -> None:
    document = blocks(("10", (40, 100, 121.0, 110)), ("20", (50, 120, 121.6, 130)), ("30", (60, 140, 122.4, 150)))
    assert kinds_of(document) == {"p1-b1#n1": "scale", "p1-b2#n1": "scale", "p1-b3#n1": "scale"}


def test_percent_unit_and_sentence_blocks_in_a_column_are_not_a_scale() -> None:
    document = blocks(
        ("10%", (40, 100, 60, 110)),
        ("20%", (40, 120, 60, 130)),
        ("30%", (40, 140, 60, 150)),
        ("10톤", (200, 100, 260, 110)),
        ("20톤", (200, 120, 260, 130)),
        ("30톤", (200, 140, 260, 150)),
        ("올해 10", (400, 100, 460, 110)),
        ("올해 20", (400, 120, 460, 130)),
        ("올해 30", (400, 140, 460, 150)),
    )
    assert kinds_of(document) == {f"p1-b{i}#n1": "value" for i in range(1, 10)}


# ── 눈금 꼴의 순수 도우미 ────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("raws", "expected"),
    [
        (["600", "400"], True),
        # 소수 자릿수가 다른 둘(정규형: 0.50 → 5·10⁻¹, 0.3750 → 375·10⁻³): 500 과 375, 간격 125.
        (["0.50", "0.3750"], True),
        (["0.3750", "0.50"], True),
        # 정규형 간격이 1 인 둘(1·10⁻¹ 과 2·10⁻¹).
        (["0.10", "0.20"], True),
        # 같은 값 둘은 간격이 0 이라 눈금이 아니다.
        (["600", "600"], False),
        # 간격(80)의 배수가 아닌 둘.
        (["180", "100"], False),
        # 끝자리가 0 이 아닌 것이 있으면 아니다.
        (["18.2", "18.1"], False),
        (["1.50", "25"], False),
    ],
)
def test_two_numbers_are_a_round_pair_only_when_both_are_multiples_of_their_gap(
    raws: list[str], expected: bool
) -> None:
    assert _round_pair(raws, raws) is expected


@pytest.mark.parametrize(
    ("values", "expected"),
    [
        (["10", "20", "30"], True),
        (["30", "20", "10"], True),
        (["10", "10", "10"], False),
        (["10", "20", "40"], False),
        (["10", "20"], False),
    ],
)
def test_evenly_spaced_needs_three_and_a_gap_that_is_not_zero(values: list[str], expected: bool) -> None:
    assert _evenly_spaced(values) is expected
