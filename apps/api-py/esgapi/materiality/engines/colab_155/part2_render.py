"""중대성평가 IRO 코랩 2부의 입력 글 짓기(밴드 IR2a) — 토픽별 규제·컨트로버시 글(셀 50), Pathway 의 입력 표(셀 51 꼴).

- context_text: 셀 50 R/2604-2615 — 묶음이 있으면 json.dumps(묶음, ensure_ascii=False, indent=2), 없으면 「제공된 … 정보
  없음」(처분 ③). contracts/wire.context_text 가 판별 복사다(시험이 견준다).
- pathway_table: 셀 55 의 user 는 「Topic–Subtopic—영향 정의 표의 결과물」(셀 51 의 Markdown 표 글)을 받는다. 재무를
  셀 50(JSON)으로 돌리므로 그 행을 셀 51 표 머리 `Topic | Subtopic | 영향 정의 | 영향 유형 | 컨트로버시/규제/정책` 의
  Markdown 표로 결정적으로 짓는다(처분 ⑧). 행 차례 = 재무 행 차례 = Pathway 의 i. 맥락 칸은 셀 51 이 시킨
  `제목: …<br>요약: …<br>출처: …` 를 규제 → 컨트로버시 차례로 `<br><br>` 로 잇는다. 영향 유형 칸은 리스크면
  `리스크(<risk_type>)`, 기회면 `기회`, 그 밖은 값 그대로.
코랩과 다른 자리(표 글은 코랩이 모델에게 짓게 했다 — 여기는 결정적): 칸 안 줄바꿈은 `<br>`, `|` 는 `\\|`(표가 깨지지
않게), null 은 빈 칸.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

NO_REGULATION_TEXT: Final = "제공된 정책/규정/가이드라인 정보 없음"
"""셀 50 R/2615."""
NO_CONTROVERSY_TEXT: Final = "제공된 컨트로버시 정보 없음"
"""셀 50 R/2610."""
TABLE_HEADER: Final = ("Topic", "Subtopic", "영향 정의", "영향 유형", "컨트로버시/규제/정책")
"""셀 51 [최종 Output Format] 3 의 머리(R/2815)."""


def context_text(bundle: Mapping[str, Any] | None, kind: str) -> str:
    """셀 50 R/2604-2615. kind 는 regulation·controversy."""
    if bundle:
        return json.dumps(bundle, ensure_ascii=False, indent=2)
    return NO_REGULATION_TEXT if kind == "regulation" else NO_CONTROVERSY_TEXT


def _text(value: Any) -> str:
    """표 칸 하나의 글: null 은 빈 글, 글이 아니면 json.dumps(ensure_ascii=False)."""
    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)


def table_cell(value: Any) -> str:
    """칸 글: 줄바꿈 → `<br>`, `|` → `\\|`."""
    return _text(value).replace("\r\n", "\n").replace("\n", "<br>").replace("|", "\\|")


def impact_type_text(row: Mapping[str, Any]) -> str:
    """영향 유형 칸: 리스크면 `리스크(<risk_type>)`(risk_type 이 없으면 `리스크`), 그 밖은 impact_type 그대로."""
    impact_type = _text(row.get("impact_type"))
    if impact_type == "리스크" and row.get("risk_type") is not None:
        return f"리스크({_text(row.get('risk_type'))})"
    return impact_type


def _items(value: Any) -> list[dict[str, Any]]:
    return (
        [cast("dict[str, Any]", e) for e in cast("list[Any]", value) if isinstance(e, dict)]
        if isinstance(value, list)
        else []
    )


def context_cell(context: Any) -> str:
    """맥락 칸: 규제 → 컨트로버시 차례로 `제목: …<br>요약: …<br>출처: …` 를 `<br><br>` 로 잇는다(객체가 아닌 원소는
    뺀다)."""
    ctx = cast("dict[str, Any]", context) if isinstance(context, dict) else {}
    entries = [
        f"제목: {_text(e.get('title'))}<br>요약: {_text(e.get('summary'))}<br>출처: {_text(e.get('url'))}"
        for e in _items(ctx.get("regulations")) + _items(ctx.get("controversies"))
    ]
    return "<br><br>".join(entries)


def pathway_table(topic: str, subtopic: str, financial_rows: Sequence[Mapping[str, Any]]) -> str:
    """재무 행(part2_parsing.read_rows 의 impacts — context 정규화됨) → 셀 51 꼴 Markdown 표 글(끝 줄바꿈 없음)."""
    lines = [
        "| " + " | ".join(TABLE_HEADER) + " |",
        "|" + "---|" * len(TABLE_HEADER),
    ]
    for row in financial_rows:
        cells = (
            table_cell(topic),
            table_cell(subtopic),
            table_cell(row.get("impact_definition")),
            table_cell(impact_type_text(row)),
            table_cell(context_cell(row.get("context"))),
        )
        lines.append("| " + " | ".join(cells) + " |")
    return "\n".join(lines)
