"""engines/colab_155/part2_parsing.py(밴드 IR2a): 글 → 객체(셀 65 normalize 차례), 객체 → 행(셀 50 정규화), Pathway 잇기
(처분 ⑨), 읽기 실패의 까닭에 모델 글이 없음(발주서 §3 S6·S11 의 엔진 몫). 기대값은 손으로 적었다.
"""

import json
import math
from typing import Any

from esgapi.materiality.engines.colab_155 import part2_parsing as pp


def test_parse_order_is_cell65() -> None:
    body: dict[str, Any] = {"impacts": []}
    assert pp.parse_part2(json.dumps(body)) == (body, None)
    assert pp.parse_part2('```json\n{"impacts": []}\n```') == (body, None)  # 첫 { ~ 끝 }
    assert pp.parse_part2('가상 앞 {"a": {"b": 1}} 가상 뒤') == ({"a": {"b": 1}}, None)
    assert pp.parse_part2("") == (None, "JSONDecodeError: Expecting value: line 1 column 1 (char 0)")
    assert pp.parse_part2("가상 표 | 머리 |") == (None, "JSONDecodeError: Expecting value: line 1 column 1 (char 0)")
    assert pp.parse_part2('{"a": 1} 그리고 {"b": 2}')[0] is None  # 첫 { ~ 끝 } 가 JSON 이 아니다
    assert pp.parse_part2("[1, 2]") == (None, "JSON 객체가 아니다: list")
    assert pp.parse_part2('{"impacts": [') == (None, "JSONDecodeError: Expecting value: line 1 column 14 (char 13)")


def test_reason_has_no_model_text() -> None:
    _, reason = pp.parse_part2('비밀스러운 가상 문장 {"a": 비밀}')
    assert reason is not None and "비밀" not in reason
    assert reason.startswith("JSONDecodeError: ")


def test_nan_is_kept_as_python_float() -> None:
    parsed, _ = pp.parse_part2('{"impacts": [{"score": NaN}]}')
    assert parsed is not None and math.isnan(parsed["impacts"][0]["score"])


def test_read_rows_cell50_rules() -> None:
    parsed: dict[str, Any] = {
        "impacts": [
            {"impact_definition": "가", "context": {"regulations": "글", "controversies": [{"title": "t"}]}, "x": 1},
            "글 원소",
            {"impact_definition": "나", "context": None},
            {"impact_definition": "다", "context": ["목록"]},
            {"impact_definition": "라"},
            7,
        ]
    }
    rows, dropped = pp.read_rows(parsed, pp.IMPACTS)
    assert dropped == 2
    assert rows == [
        {"impact_definition": "가", "context": {"controversies": [{"title": "t"}], "regulations": []}, "x": 1},
        {"impact_definition": "나", "context": {"controversies": [], "regulations": []}},
        {"impact_definition": "다", "context": {"controversies": [], "regulations": []}},
        {"impact_definition": "라", "context": {"controversies": [], "regulations": []}},
    ]
    assert rows is not None
    assert list(rows[0]) == ["impact_definition", "context", "x"]  # context 는 제자리(코랩의 it["context"] = …)
    assert parsed["impacts"][0]["context"] == {
        "regulations": "글",
        "controversies": [{"title": "t"}],
    }  # 받은 것은 그대로
    assert pp.read_rows({"impacts": "가상"}, pp.IMPACTS) == (None, 0)
    assert pp.read_rows({}, pp.IMPACTS) == ([], 0)
    assert pp.read_rows({"pathways": [{"i": 1, "context": 5}, None]}, pp.PATHWAYS) == ([{"i": 1, "context": 5}], 1)


def test_read_answer_shapes() -> None:
    assert pp.read_answer('{"impacts": [1]}', pp.IMPACTS) == {
        "parsed": {"impacts": [1]},
        "parseError": None,
        "rows": [],
        "dropped": 1,
    }
    assert pp.read_answer('{"impacts": {}}', pp.IMPACTS) == {
        "parsed": {"impacts": {}},
        "parseError": "impacts 가 목록이 아니다",
        "rows": None,
        "dropped": 0,
    }
    assert pp.read_answer("가상", pp.PATHWAYS)["rows"] is None


def fin(definition: str, impact_type: str, risk: str | None) -> dict[str, object]:
    return {
        "impact_definition": definition,
        "impact_type": impact_type,
        "risk_type": risk,
        "context": {"controversies": [{"title": definition}], "regulations": []},
    }


def test_join_by_i_from_financial_rows() -> None:
    fins = [fin("가 정의", "리스크", "리스크-평판"), fin("나 정의", "기회", None)]
    paths = [
        {"i": 2, "impact_definition": "나 정의", "impact_driver": "d2", "impact_type": "모델이 쓴 값"},
        {"i": "1", "impact_definition": "가 정의", "impact_driver": "d1"},
    ]
    joined, mismatch = pp.join_pathway(paths, fins)
    assert mismatch is False
    assert joined == [
        {
            "i": 2,
            "impact_definition": "나 정의",
            "impact_driver": "d2",
            "impact_type": "기회",
            "risk_type": None,
            "context": {"controversies": [{"title": "나 정의"}], "regulations": []},
        },
        {
            "i": 1,
            "impact_definition": "가 정의",
            "impact_driver": "d1",
            "impact_type": "리스크",
            "risk_type": "리스크-평판",
            "context": {"controversies": [{"title": "가 정의"}], "regulations": []},
        },
    ]


def test_join_mismatches() -> None:
    fins = [fin("가 정의", "리스크", "리스크-시장")]
    assert pp.join_pathway([{"i": 1, "impact_definition": "다른 글"}], fins)[1] is True
    assert pp.join_pathway([{"i": 1, "impact_definition": "가 정의"}, {"i": 1, "impact_definition": "가 정의"}], fins)[
        1
    ]
    assert pp.join_pathway([], fins)[1] is True
    two = [fin("가 정의", "리스크", "리스크-시장"), fin("나 정의", "기회", None)]
    same = [{"i": 1, "impact_definition": "가 정의"}, {"i": 1, "impact_definition": "가 정의"}]
    assert pp.join_pathway(same, two)[1] is True  # 수는 같아도 i 가 겹쳐 둘째 재무 행을 못 덮음
    unjoined, mismatch = pp.join_pathway([{"i": 3, "impact_definition": "가 정의"}], fins)
    assert mismatch is True
    assert unjoined == [
        {
            "i": 3,
            "impact_definition": "가 정의",
            "impact_type": None,
            "risk_type": None,
            "context": {"controversies": [], "regulations": []},
        }
    ]
    for bad in (True, None, "첫째", 0, -1, 1.0):
        assert pp.join_pathway([{"i": bad, "impact_definition": "가 정의"}], fins)[1] is True
    assert pp.row_index(True) is None and pp.row_index(" 2 ") == 2 and pp.row_index(1.0) is None


def test_definition_copied_from_the_table_cell_still_matches() -> None:
    """모델이 입력 표 칸 글(`\\|`·`<br>`)을 그대로 옮긴 영향 정의도 같다고 본다(감독 처분 ⑤)."""
    fins = [fin("A|B\nC", "리스크", "리스크-시장")]
    joined, mismatch = pp.join_pathway([{"i": 1, "impact_definition": "A\\|B<br>C"}], fins)
    assert mismatch is False and joined[0]["impact_type"] == "리스크"
    assert pp.join_pathway([{"i": 1, "impact_definition": "A|B<br>C"}], fins)[1] is True  # 반만 옮긴 글은 다르다
    assert pp.same_definition(None, None) and not pp.same_definition(None, "") and not pp.same_definition("", None)
