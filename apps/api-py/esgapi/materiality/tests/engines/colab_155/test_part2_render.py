"""engines/colab_155/part2_render.py(밴드 IR2a): 셀 50 꼴 토픽별 글(contracts 의 판별 복사와 같음), Pathway 입력
표(처분 ⑧ — 셀 51 머리, 행 차례 = 재무 행, 영향 유형 칸, 맥락 칸 규제 → 컨트로버시, `<br>`·`\\|`). 기대 글은
손으로 적었다.
"""

from typing import Any

from esgapi.materiality.contracts import wire
from esgapi.materiality.engines.colab_155 import part2_render as pr

HEADER = "| Topic | Subtopic | 영향 정의 | 영향 유형 | 컨트로버시/규제/정책 |\n|---|---|---|---|---|"


def test_context_text_is_the_cell50_text_and_matches_the_contract_copy() -> None:
    bundle = {"parsed": {"가": [1]}, "raw": None, "parse_error": None}
    expected = '{\n  "parsed": {\n    "가": [\n      1\n    ]\n  },\n  "raw": null,\n  "parse_error": null\n}'
    assert pr.context_text(bundle, "regulation") == expected
    assert pr.context_text(None, "regulation") == "제공된 정책/규정/가이드라인 정보 없음"
    assert pr.context_text(None, "controversy") == "제공된 컨트로버시 정보 없음"
    assert pr.context_text({}, "controversy") == "제공된 컨트로버시 정보 없음"  # 빈 dict 도 코랩 if 에서 거짓
    for value in (bundle, None, {}):
        for kind in ("regulation", "controversy"):
            assert pr.context_text(value, kind) == wire.context_text(value, kind)
    assert (pr.NO_REGULATION_TEXT, pr.NO_CONTROVERSY_TEXT) == (wire.NO_REGULATION_TEXT, wire.NO_CONTROVERSY_TEXT)


def test_pathway_table_by_hand() -> None:
    rows: list[dict[str, Any]] = [
        {
            "impact_definition": "가상 정의 | 하나\n둘째 줄",
            "impact_type": "리스크",
            "risk_type": "리스크-평판",
            "context": {
                "controversies": [{"title": "사건", "summary": "사건 요약", "url": "https://example.com/c"}],
                "regulations": [{"title": "규정", "summary": None, "url": "https://example.com/r"}, "글"],
            },
        },
        {"impact_definition": "가상 기회", "impact_type": "기회", "risk_type": None, "context": {}},
        {"impact_definition": None, "impact_type": "중립", "risk_type": "x", "context": None},
    ]
    assert pr.pathway_table("가상토픽", "가상 서브", rows) == (
        HEADER + "\n"
        "| 가상토픽 | 가상 서브 | 가상 정의 \\| 하나<br>둘째 줄 | 리스크(리스크-평판) | "
        "제목: 규정<br>요약: <br>출처: https://example.com/r<br><br>"
        "제목: 사건<br>요약: 사건 요약<br>출처: https://example.com/c |\n"
        "| 가상토픽 | 가상 서브 | 가상 기회 | 기회 |  |\n"
        "| 가상토픽 | 가상 서브 |  | 중립 |  |"
    )


def test_empty_rows_and_types() -> None:
    assert pr.pathway_table("t", "s", []) == HEADER
    assert pr.impact_type_text({"impact_type": "리스크", "risk_type": None}) == "리스크"
    assert pr.impact_type_text({"impact_type": 3}) == "3"
    assert pr.table_cell({"a": "b|c"}) == '{"a": "b\\|c"}'
    assert pr.table_cell("가\r\n나") == "가<br>나"
