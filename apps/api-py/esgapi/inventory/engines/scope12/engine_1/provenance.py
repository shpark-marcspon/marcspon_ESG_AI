"""수치의 출처. 출처 없는 수치는 표에 들어올 수 없다(tables.validate_tables 가 막는다).

esg-lab `ts/kernel/src/provenance.ts` 의 세 갈래를 옮긴 것이다. 갈래는 `kind` 로 가른다.
"""

from dataclasses import dataclass
from typing import Literal


@dataclass(frozen=True, slots=True, kw_only=True)
class Cited:
    """공표된 값. 어디서 언제 확인했는지가 붙는다."""

    kind: Literal["cited"] = "cited"
    title: str
    url: str
    checked_on: str
    locator: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True, kw_only=True)
class Definition:
    """정의상 정확한 값 (SI 접두어, 1 kWh = 3.6 MJ). 측정값이나 고시값이 아니다."""

    kind: Literal["definition"] = "definition"
    note: str


@dataclass(frozen=True, slots=True, kw_only=True)
class Synthetic:
    """테스트용 가상 값. 실제 산정에 쓰면 안 된다."""

    kind: Literal["synthetic"] = "synthetic"
    note: str


Provenance = Cited | Definition | Synthetic
