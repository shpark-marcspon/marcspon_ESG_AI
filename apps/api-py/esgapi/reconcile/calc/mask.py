"""숫자 가림. 값 후보 숫자를 고정 기호 하나로 바꾼다(길이가 같지 않아 자릿수가 새지 않는다).

esg-lab `ts/reconcile/src/compare/render.ts` 의 `MASK`·`maskText`·`cellText` 만 옮겼다(render.ts:7-23).
그 파일의 나머지(`renderDocument` 등 요청 글 조립)는 옮기지 않았다.
`compare/hybrid.ts` 의 `unmaskedValues`(요청 글에 남은 숫자 검사)도 옮기지 않았다: 그 함수가 떼는 줄 꼴은
요청 조립의 것이라, 조립을 옮기는 밴드(PY6b)에서 같이 옮긴다(감독 결정 2026-10-08).
"""

from collections.abc import Mapping
from typing import Final

from esgapi.reconcile.calc.jstext import from_units, to_units
from esgapi.reconcile.calc.notation import normalize_text, scan_numbers
from esgapi.reconcile.calc.types import Fact, Grid

MASK: Final = "▒"


def mask_text(text: str) -> str:
    """글 속의 값 후보 숫자를 가린다. 연도·식별자·순번은 값 후보가 아니라 남는다."""
    out = to_units(text)
    values = [token for token in scan_numbers(text) if token.kind == "value"]
    for token in sorted(values, key=lambda item: -item.start):
        out = f"{out[: token.start]}{MASK}{out[token.end :]}"
    return from_units(out)


def cell_text(grid: Grid, row: int, col: int, raw: str, facts: Mapping[str, Fact], mask: bool) -> str:
    """표 칸 하나의 글. `mask` 면 숫자 칸은 칸 전체를 기호 하나로(단위 접미는 남긴다), 글 칸은 그 안의 값 후보만."""
    text = normalize_text(raw)
    if not mask:
        return text
    fact = facts.get(f"{grid.id}:r{row}c{col}")
    if fact is not None and fact.bucket == "table_cell":
        return f"{MASK}{fact.unit_suffix or ''}"
    return mask_text(text)
