"""품목명의 묶음 키. esg-lab `ts/scope3/src/domain/normalize.ts` 를 옮긴 것이다."""

import re
import unicodedata
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from esgapi.inventory.engines.scope3.llm_first_1.types import InputRow, TransportInfo
from esgapi.inventory.engines.scope3.llm_first_1.units import activity_dim

# JS 의 `\d` 는 ASCII 숫자다. 파이썬의 `\d` 는 전각·아랍 숫자까지 받으므로 `[0-9]` 로 적는다.
_DOT_NOT_BEFORE_DIGIT: Final = re.compile(r"\.(?![0-9])")
_DOT_NOT_AFTER_DIGIT: Final = re.compile(r"(?<![0-9])\.")
_CROSSES: Final = str.maketrans({"×": "x", "✕": "x", "*": "x"})


def is_letter_or_number(ch: str) -> bool:
    r"""JS 의 `/[\p{L}\p{N}]/u`: 유니코드 일반 범주가 L* 또는 N* 인 글자.

    파이썬 `re` 의 `\w` 는 밑줄을 받고 결합 문자(Mn)의 처리가 달라 쓰지 않는다.
    """
    return unicodedata.category(ch)[0] in "LN"


def normalize_item_name(name: str) -> str:
    """품목명을 묶음 키로 바꾼다. 공백, 대소문자, 전각·반각, 괄호와 구두점 같은 규격 표기 차이를 지운다.

    예: "A4 용지 80g", "a4용지 80G", "Ａ４용지(80g)" → "a4용지80g".
    글자와 숫자가 하나도 남지 않으면 빈 문자열이다(묶지 않는다).
    """
    text = unicodedata.normalize("NFKC", name).lower().translate(_CROSSES)
    text = "".join(ch for ch in text if ch == "." or is_letter_or_number(ch))
    return _DOT_NOT_AFTER_DIGIT.sub("", _DOT_NOT_BEFORE_DIGIT.sub("", text))


def group_key(item_name: str, unit: str | None, transport: TransportInfo | None) -> str:
    """같은 판단을 공유할 행의 키. 품목명 키에 단위 차원과 운송 수단을 붙인다.

    단위가 다르면 맞는 계수가 달라지므로 같은 품목이라도 따로 묶는다.
    """
    name = normalize_item_name(item_name)
    dim = activity_dim(unit, transport)
    unit_key = f"?{normalize_item_name(unit or '')}" if dim == "unknown" else dim
    mode = normalize_item_name(transport.mode) if transport is not None else ""
    return "|".join([name, unit_key, mode])


@dataclass(frozen=True, slots=True)
class RowGroup:
    key: str
    rows: tuple[InputRow, ...]


def group_rows(rows: Sequence[InputRow]) -> list[RowGroup]:
    """행을 묶음 키로 묶는다. 묶음과 묶음 안 행의 순서는 입력 순서를 따른다. 품목명 키가 비면 행 하나가 한 묶음이다."""
    groups: dict[str, list[InputRow]] = {}
    for row in rows:
        base = group_key(row.item_name, row.unit, row.transport)
        key = f"{base}#{row.row_id}" if normalize_item_name(row.item_name) == "" else base
        groups.setdefault(key, []).append(row)
    return [RowGroup(key=key, rows=tuple(members)) for key, members in groups.items()]
