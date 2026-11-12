"""셀 비교 로직."""

from docparse.compare import norm, score_tables

GOLD = [
    ["구분", "단위", "2023", "2024"],
    ["화성 공장2)", "tCO₂eq", "1,886", "1,874"],
    ["평택 공장", "tCO₂eq", "-", "931"],
]


def test_norm_strips_space_comma_footnote_and_unifies_dash():
    assert norm(" 1,234 ") == "1234"
    assert norm("화성 공장2)") == "화성공장"
    assert norm("tCO₂eq") == "tCO2eq"
    assert norm("–") == "-"
    assert norm(None) == ""


def test_norm_keeps_footnote_like_tail_on_numbers():
    # 숫자 뒤의 '5)' 는 각주인지 값인지 글자만으로 알 수 없으므로 지우지 않는다
    assert norm("1,3045)") == "13045)"


def test_identical_grid_scores_one_on_every_metric():
    s = score_tables(GOLD, [list(r) for r in GOLD])
    assert s["gold_cells"] == 12
    assert s["recall"] == s["recall_strict"] == s["recall_position"] == s["numeric_recall"] == 1.0
    assert s["wrong_rows"] == []


def test_wrong_number_is_not_matched():
    pred = [list(r) for r in GOLD]
    pred[1][2] = "1,888"
    s = score_tables(GOLD, pred)
    assert s["correct"] == 11
    # 숫자 셀: 머리글의 연도 2개 + 값 3개('-' 는 숫자가 아니다)
    assert s["gold_numeric_cells"] == 5 and s["correct_numeric"] == 4


def test_extra_cell_in_row_zeroes_the_row_only_for_strict():
    pred = [list(r) for r in GOLD]
    pred[2] = pred[2] + ["옆 표의 값"]
    s = score_tables(GOLD, pred)
    assert s["recall"] == 1.0
    assert s["correct_strict"] == 8  # 셋째 행 4셀이 0점


def test_shifted_column_fails_position_but_not_relaxed():
    gold = [["a", "", "1", "2"], ["b", "x", "3", "4"]]
    pred = [["", "a", "1", "2"], ["b", "x", "3", "4"]]
    s = score_tables(gold, pred)
    assert s["recall"] == 1.0 and s["recall_strict"] == 1.0
    assert s["correct_position"] == 6 and s["gold_cells"] == 7


def test_missing_row_and_empty_prediction():
    s = score_tables(GOLD, GOLD[:2])
    assert s["rows_matched"] == 2 and s["correct"] == 8
    empty = score_tables(GOLD, [])
    assert empty["recall"] == 0.0 and empty["precision"] is None
    assert len(empty["wrong_rows"]) == 3
