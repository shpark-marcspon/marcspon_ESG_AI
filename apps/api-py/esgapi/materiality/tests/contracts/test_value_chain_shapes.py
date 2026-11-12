"""가치사슬 엑셀 읽기의 응답 꼴(contracts/value_chain_shapes.py — 밴드 IRW2 §1-3): kind 아홉은 읽개의 RejectionKind 와
같고(계약은 도구를 import 하지 않는다 — 여기서 견준다), 두 갈래는 strict 로 받고 칸이 하나라도 더 붙으면 거절한다.
행 열쇠 다섯은 실행 입력 input@1 의 valueChain 원소와 같다(웹이 표를 그대로 싣는다)."""

import typing
from typing import Any

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.materiality.contracts.shapes import MaterialityValueChainRow
from esgapi.materiality.contracts.value_chain_shapes import MaterialityValueChainRead, ValueChainRejectionKind
from esgapi.materiality.tools import value_chain_xlsx

SHAPE: TypeAdapter[Any] = TypeAdapter(MaterialityValueChainRead)
ROW = {
    "business_unit": "가상부문",
    "business_unit_description": "",
    "value_chain_stage": "업스트림",
    "stakeholder": "가상협력사",
    "business_activity": "자재 조달",
}


def test_the_kinds_are_the_readers_nine() -> None:
    assert typing.get_args(ValueChainRejectionKind) == typing.get_args(value_chain_xlsx.RejectionKind)
    assert len(typing.get_args(ValueChainRejectionKind)) == 9


def test_the_row_keys_are_the_input_value_chain_keys() -> None:
    assert list(ROW) == list(MaterialityValueChainRow.__annotations__)


def test_both_branches_are_accepted_strictly() -> None:
    SHAPE.validate_python({"ok": True, "rows": [ROW], "rowCount": 1}, strict=True)
    SHAPE.validate_python(
        {"ok": False, "kind": "too_long", "row": 3, "column": 4, "message": "3행의 … 칸이 너무 길어요."}, strict=True
    )
    SHAPE.validate_python({"ok": False, "kind": "not_xlsx", "row": None, "column": None, "message": "…"}, strict=True)


@pytest.mark.parametrize(
    "body",
    [
        {"ok": True, "rows": [{**ROW, "extra": ""}], "rowCount": 1},
        {"ok": True, "rows": [ROW], "rowCount": 1, "extra": 0},
        {"ok": True, "rows": [], "rowCount": 0},
        {"ok": True, "rows": [ROW] * 101, "rowCount": 101},
        {"ok": False, "kind": "empty_cell", "row": None, "column": None, "message": "…"},
        {"ok": False, "kind": "too_long", "row": 0, "column": 0, "message": "…"},
        {"ok": False, "kind": "too_long", "row": 1, "column": 5, "message": "…"},
        {"ok": False, "kind": "too_long", "row": 1, "column": 0},
    ],
    ids=["row_extra", "body_extra", "no_rows", "101_rows", "unknown_kind", "row_0", "column_5", "no_message"],
)
def test_a_body_off_the_shape_is_refused(body: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        SHAPE.validate_python(body, strict=True)
