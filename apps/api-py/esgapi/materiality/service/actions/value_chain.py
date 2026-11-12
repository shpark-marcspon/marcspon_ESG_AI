"""가치사슬 표 엑셀 읽기 경로의 몸(POST /materiality/value-chain/read — 밴드 IRW2 ①, MARC-ENT-464).

상태가 없다: DB·저장소·디스크에 쓰지 않고 감사 줄도 남기지 않는다. 테넌트 행을 읽지 않으므로 회사 id 를 받지 않는다
(영문번역 용어집 읽기와 같은 꼴 — 운영 관리자도 같은 결과). 읽기는 도구(tools/value_chain_xlsx.py)가 하고, 여기서는
도구의 갈래를 응답 꼴(contracts/value_chain_shapes.py)로 옮길 뿐이다. 칸의 값은 로그에 싣지 않는다.
"""

from typing import Final

from esgapi.materiality.contracts.value_chain_shapes import (
    MaterialityValueChainReadOk,
    MaterialityValueChainReadRejected,
)
from esgapi.materiality.tools import value_chain_xlsx

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def read(data: bytes) -> MaterialityValueChainReadOk | MaterialityValueChainReadRejected:
    """xlsx 바이트 → 행 목록(ok true) 또는 거절 갈래(ok false). 어떤 바이트도 예외 대신 갈래다."""
    match value_chain_xlsx.read_value_chain(data):
        case value_chain_xlsx.ValueChainRead(rows=rows):
            return {
                "ok": True,
                "rows": [
                    {
                        "business_unit": unit,
                        "business_unit_description": description,
                        "value_chain_stage": stage,
                        "stakeholder": stakeholder,
                        "business_activity": activity,
                    }
                    for unit, description, stage, stakeholder, activity in rows
                ],
                "rowCount": len(rows),
            }
        case value_chain_xlsx.ValueChainRejected(kind=kind, row=row, column=column, message=message):
            return {"ok": False, "kind": kind, "row": row, "column": column, "message": message}
