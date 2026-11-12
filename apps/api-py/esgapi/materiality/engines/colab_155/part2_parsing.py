"""중대성평가 IRO 코랩 2부의 답 읽기(밴드 IR2a) — 셀 65 normalize 의 글 → 객체, 셀 50 정규화의 객체 → 행, Pathway 잇기.

- parse_part2: json.loads 를 먼저, 안 되면 첫 `{` ~ 마지막 `}`(셀 65 _extract_json_object)를 json.loads(처분 ⑤ —
  프롬프트로만 받고 core 의 schema 는 쓰지 않는다). 코랩과 다른 자리: 객체(dict)가 아니면 못 읽음(코랩 normalize 는
  list 도 그대로 두고, 못 읽으면 {"_raw_text", "pathways": []} 로 감싼다 — 여기는 그 갈래를 unparsable 로 둔다).
- read_rows: 셀 50 R/2659-2691 — 목록 칸(impacts·pathways)이 목록이 아니면 못 읽음, 객체가 아닌 원소는 뺀다(수를 센다).
  impacts 의 context 는 객체가 아니면 빈 것, controversies·regulations 가 목록이 아니면 빈 목록(셀 50 의 키 차례).
  코랩은 원소를 제자리에서 고치지만 여기는 고친 복사본을 낸다(parsed 는 받은 그대로 남는다). utm 은 지우지 않는다(코랩
  2부대로).
- join_pathway: Pathway 행의 i(1부터)로 재무 행을 찾아 impact_type·risk_type·context 를 잇는다(처분 ⑨ — 모델 칸이
  아니라 재무 행에서). 행 수가 다르거나, i 가 없거나 범위 밖이거나 겹치거나, 영향 정의 글이 다르면 mismatch.
엔진은 dict 만 낸다 — 결과 꼴의 칸으로 옮기는 것은 contracts/wire.py 다.
"""

import json
from collections.abc import Mapping, Sequence
from typing import Any, Final, cast

from .part2_render import table_cell

IMPACTS: Final = "impacts"
"""셀 46·50 JSON 꼴의 목록 칸."""
PATHWAYS: Final = "pathways"
"""셀 55 JSON 절의 목록 칸."""
CONTEXT_KEYS: Final = ("controversies", "regulations")
"""셀 50 정규화가 context 에 남기는 두 칸(그 차례)."""


def extract_json_object(text: str) -> str | None:
    """셀 65 _extract_json_object(R/3574-3582)의 규칙: 첫 `{` ~ 마지막 `}`. 없거나 차례가 뒤집히면 None."""
    first, last = text.find("{"), text.rfind("}")
    if first < 0 or last <= first:
        return None
    return text[first : last + 1]


def _reason(error: Exception) -> str:
    """읽기 실패의 까닭(예외 이름과 json 의 위치 글 — 모델 글을 싣지 않는다)."""
    if isinstance(error, json.JSONDecodeError):
        return f"JSONDecodeError: {error.msg}: line {error.lineno} column {error.colno} (char {error.pos})"
    return type(error).__name__


def parse_part2(text: str) -> tuple[dict[str, Any] | None, str | None]:
    """답 글 → (JSON 객체, 못 읽은 까닭). 셀 65 normalize 의 차례: json.loads → 첫 `{`~끝 `}` 를 json.loads."""
    try:
        value = json.loads(text)
    except Exception as first:  # 코랩대로 무엇이든 잡는다
        extracted = extract_json_object(text)
        if extracted is None:
            return None, _reason(first)
        try:
            value = json.loads(extracted)
        except Exception as second:
            return None, _reason(second)
    if not isinstance(value, dict):
        return None, f"JSON 객체가 아니다: {type(value).__name__}"
    return cast("dict[str, Any]", value), None


def _context(value: Any) -> dict[str, Any]:
    """셀 50 R/2670-2683 의 규칙: context 가 객체가 아니면 빈 것, 두 칸은 목록이 아니면 빈 목록(키 차례 controversies·
    regulations)."""
    given = cast("dict[str, Any]", value) if isinstance(value, dict) else {}
    found = {key: given.get(key, []) for key in CONTEXT_KEYS}
    return {key: item if isinstance(item, list) else [] for key, item in found.items()}


def read_rows(parsed: Mapping[str, Any], key: str) -> tuple[list[dict[str, Any]] | None, int]:
    """객체 → (행 목록, 뺀 원소 수). 목록 칸이 목록이 아니면 (None, 0) — 셀 50 의 ValueError("impacts is not a list").
    impacts 는 context 를 정규화한다(셀 50), pathways 는 원소를 그대로 둔다."""
    items = parsed.get(key, [])
    if not isinstance(items, list):
        return None, 0
    rows: list[dict[str, Any]] = []
    dropped = 0
    for item in cast("list[Any]", items):
        if not isinstance(item, dict):
            dropped += 1
            continue
        row = dict(cast("dict[str, Any]", item))
        if key == IMPACTS:
            row["context"] = _context(row.get("context") or {})
        rows.append(row)
    return rows, dropped


def read_answer(text: str, key: str) -> dict[str, Any]:
    """답 글 → 엔진의 읽기 {parsed, parseError, rows, dropped}(contracts/wire 의 *_outcome 이 받는 꼴). 못 읽으면 rows
    None."""
    parsed, reason = parse_part2(text)
    if parsed is None:
        return {"parsed": None, "parseError": reason, "rows": None, "dropped": 0}
    rows, dropped = read_rows(parsed, key)
    if rows is None:
        return {"parsed": parsed, "parseError": f"{key} 가 목록이 아니다", "rows": None, "dropped": 0}
    return {"parsed": parsed, "parseError": None, "rows": rows, "dropped": dropped}


def row_index(value: Any) -> int | None:
    """Pathway 행의 i → 정수(bool 아님) 또는 숫자 글이면 그 수, 아니면 None."""
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdecimal():
        return int(value.strip())
    return None


def same_definition(pathway_value: Any, financial_value: Any) -> bool:
    """Pathway 의 영향 정의가 재무 행의 것과 같은가 — 글자째 같거나, 모델이 입력 표 칸 글(part2_render.table_cell —
    줄바꿈 `<br>`·`\\|`)을 그대로 옮겼으면 같다고 본다(감독 처분 ⑤)."""
    return pathway_value == financial_value or (
        isinstance(pathway_value, str)
        and isinstance(financial_value, str)
        and pathway_value == table_cell(financial_value)
    )


def join_pathway(
    pathway_rows: Sequence[Mapping[str, Any]], financial_rows: Sequence[Mapping[str, Any]]
) -> tuple[list[dict[str, Any]], bool]:
    """Pathway 행마다 i 번째(1부터) 재무 행의 impact_type·risk_type·context 를 잇는다(모델이 낸 같은 이름 칸은 덮는다).
    잇지 못한 행은 셋이 null·null·빈 context. 돌려주는 bool 은 mismatch."""
    mismatch = len(pathway_rows) != len(financial_rows)
    joined: list[dict[str, Any]] = []
    seen: set[int] = set()
    for row in pathway_rows:
        i = row_index(row.get("i"))
        fin = financial_rows[i - 1] if i is not None and 1 <= i <= len(financial_rows) else None
        if fin is None or i in seen or not same_definition(row.get("impact_definition"), fin.get("impact_definition")):
            mismatch = True
        if i is not None:
            seen.add(i)
        joined.append(
            {
                **row,
                "i": i,
                "impact_type": None if fin is None else fin.get("impact_type"),
                "risk_type": None if fin is None else fin.get("risk_type"),
                "context": _context(None) if fin is None else fin.get("context"),
            }
        )
    return joined, mismatch
