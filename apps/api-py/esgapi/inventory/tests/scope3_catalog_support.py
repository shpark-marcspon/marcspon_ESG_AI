"""Scope 3 추리기 테스트(커밋 경계 ②)가 같이 쓰는 것: 계수 jsonl·예제 폴더의 로더와 JS 수 표기.

★ 여기서만 파일을 읽는다(테스트 지원). 순수 층(`engines/scope3/llm_first_1/`)은 파일을 모른다.
"""

import json
import math
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Literal, cast

from esgapi.inventory.engines.scope3.llm_first_1.catalog import ListFactorCatalog, RawRecord
from esgapi.inventory.engines.scope3.llm_first_1.lexical_v1 import ShortlistQuery
from esgapi.inventory.engines.scope3.llm_first_1.types import (
    CandidateBasis,
    CandidateQuery,
    Factor,
    InputRow,
    LicenseStatus,
    TransportInfo,
)
from esgapi.inventory.engines.scope3.llm_first_1.units import activity_dim, conversion_factor
from esgapi.inventory.tools.jsrepr import js_string

DATA: Final = Path(__file__).parent / "data"
G1: Final = DATA / "scope3"
G1_FACTORS: Final = G1 / "factors.synthetic.jsonl"
G1_EXAMPLES: Final = G1 / "examples"
G1_GOLDEN: Final = G1 / "golden"
PRIOR_ROWS: Final = DATA / "scope3-s25-rows.json"

TableOrder = Literal["file", "id"]


def record_from_json(line: dict[str, Any]) -> RawRecord:
    """jsonl 의 한 줄(esg-lab `schemas/factor.schema.json` 0.1) → 순수 층의 낱줄."""
    return RawRecord(
        id=line["id"],
        record_type=line["record_type"],
        gas=line["gas"],
        value=line["value"],
        value_raw=line["value_raw"],
        scope3_categories=tuple(line["scope3_categories"]),
        factor_type=line["factor_type"],
        name_original=line["name"]["original"],
        category_path=tuple(line["category_path"]),
        unit=line["unit"],
        unit_numerator=line["unit_numerator"],
        unit_denominator=line["unit_denominator"],
        license_status=line["license_status"],
        source_id=line["source"]["id"],
        region=line["region"],
        classification=line["classification"],
        spend=line["spend"],
    )


def read_records(path: Path) -> list[RawRecord]:
    """파일의 차례대로. 빈 줄은 건너뛴다."""
    with path.open(encoding="utf-8") as lines:
        return [record_from_json(json.loads(line)) for line in lines if line.strip()]


def catalog_from(records: Iterable[RawRecord], order: TableOrder) -> ListFactorCatalog:
    """`file` 은 받은 차례 그대로(TS 의 표 순서), `id` 는 id 의 유니코드 코드 포인트 순(서버의 표 순서)."""
    return ListFactorCatalog(records if order == "file" else sorted(records, key=lambda record: record.id))


def load_catalog(path: Path = G1_FACTORS, order: TableOrder = "file") -> ListFactorCatalog:
    return catalog_from(read_records(path), order)


@dataclass(frozen=True, slots=True)
class Gold:
    category: int | None
    factor_ids: tuple[str, ...]
    note: str


@dataclass(frozen=True, slots=True)
class Example:
    row: InputRow
    gold: Gold


def load_examples(directory: Path = G1_EXAMPLES) -> list[Example]:
    """예제 폴더의 `rows.synthetic.jsonl`. 전부 가상 내역이다(`synthetic: true` 가 아니면 읽지 않는다)."""
    examples: list[Example] = []
    with (directory / "rows.synthetic.jsonl").open(encoding="utf-8") as lines:
        for line in lines:
            if not line.strip():
                continue
            data = json.loads(line)
            if data["synthetic"] is not True:
                raise ValueError(f"가상 표시가 없는 예제 행: {data['row_id']}")
            moved = data["transport"]
            transport = (
                None
                if moved is None
                else TransportInfo(
                    moved["origin"], moved["destination"], moved["mode"], moved["weight_kg"], moved["distance_km"]
                )
            )
            row = InputRow(
                row_id=data["row_id"],
                item_name=data["item_name"],
                quantity=data["quantity"],
                unit=data["unit"],
                amount=data["amount"],
                currency=data["currency"],
                date=data["date"],
                org_unit=data["org_unit"],
                transport=transport,
            )
            gold = data["gold"]
            examples.append(Example(row, Gold(gold["category"], tuple(gold["factor_ids"]), gold["note"])))
    return examples


def query_of(row: InputRow, keywords: Iterable[str]) -> ShortlistQuery:
    """파이프라인과 같은 질의: 원문 글자는 품목명과 (있으면) 운송 수단."""
    texts = (row.item_name, row.transport.mode) if row.transport is not None else (row.item_name,)
    return ShortlistQuery(texts=texts, keywords=tuple(keywords))


def candidates_for(
    catalog: ListFactorCatalog,
    row: InputRow,
    category: int,
    basis: CandidateBasis,
    exclude: tuple[LicenseStatus, ...] = (),
) -> list[Factor]:
    """파이프라인과 같은 후보 집합: 범주·기반·이용 조건으로 거르고, 활동·거리 기반은 단위 차원으로 한 번 더."""
    found = catalog.candidates(CandidateQuery(category, basis, exclude))
    if basis == "spend":
        return found
    dim = activity_dim(row.unit, row.transport)
    return [factor for factor in found if conversion_factor(dim, factor.denominator_dim) is not None]


class JsFloat(str):
    """JSON 파일에 적힌 소수의 글자 그대로(JS 가 적은 수 표기). 보통의 문자열과 가르려고 따로 둔 타입이다."""

    __slots__ = ()


def load_json_keeping_floats(path: Path) -> Any:
    """JSON 을 읽되 소수는 파일에 적힌 글자 그대로 둔다(`JsFloat`)."""
    return json.loads(path.read_text(encoding="utf-8"), parse_float=JsFloat)


# 점수의 허용 오차(발주서 ★ 가). TS 의 `Math.log`(V8 의 자체 구현)와 파이썬의 `math.log`(플랫폼 libm)는 마지막 자리가
# 다를 수 있다. 그래서 점수만 이 오차로 견주고, id·순위·겹친 낱말·그 밖의 모든 값은 글자까지 같아야 한다.
SCORE_REL_TOL: Final = 1e-12


@dataclass(slots=True)
class FloatTally:
    """견준 소수의 수, 그 가운데 글자까지 같은 수, 다른 것의 최대 상대 오차."""

    total: int = 0
    same_text: int = 0
    max_rel_error: float = 0.0

    def add(self, other: "FloatTally") -> None:
        self.total += other.total
        self.same_text += other.same_text
        self.max_rel_error = max(self.max_rel_error, other.max_rel_error)

    def line(self) -> str:
        return (
            f"소수 {self.same_text}/{self.total} 이 글자까지 같다 (다른 것의 최대 상대 오차 {self.max_rel_error:.3g})"
        )


def compare_with_ts(mine: object, theirs: object, tally: FloatTally, where: str = "$") -> list[str]:
    """내 값(파이썬)과 TS 가 낸 JSON(`load_json_keeping_floats`)의 다른 자리 목록. 비어 있으면 같다.

    소수는 `SCORE_REL_TOL` 안이면 같다고 치고 `tally` 에 센다. 나머지는 값·타입·키의 차례까지 같아야 한다.
    """
    if isinstance(theirs, JsFloat):
        if isinstance(mine, bool) or not isinstance(mine, (int, float)):
            return [f"{where}: 수가 아니다 ({mine!r} != {theirs})"]
        tally.total += 1
        if js_string(mine) == theirs:
            tally.same_text += 1
            return []
        expected = float(theirs)
        if not math.isclose(mine, expected, rel_tol=SCORE_REL_TOL, abs_tol=0.0):
            return [f"{where}: {js_string(mine)} != {theirs}"]
        tally.max_rel_error = max(tally.max_rel_error, abs(mine - expected) / abs(expected))
        return []
    if isinstance(theirs, dict):
        if not isinstance(mine, dict):
            return [f"{where}: 객체가 아니다"]
        mine_map = cast("dict[str, object]", mine)
        their_map = cast("dict[str, object]", theirs)
        if list(mine_map) != list(their_map):
            return [f"{where}: 키가 다르다 ({list(mine_map)} != {list(their_map)})"]
        return [d for key in their_map for d in compare_with_ts(mine_map[key], their_map[key], tally, f"{where}.{key}")]
    if isinstance(theirs, list):
        their_list = cast("list[object]", theirs)
        if not isinstance(mine, (list, tuple)):
            return [f"{where}: 배열이 아니다"]
        mine_list = list(cast("list[object]", mine))
        if len(mine_list) != len(their_list):
            return [f"{where}: 길이가 다르다 ({len(mine_list)} != {len(their_list)})"]
        return [
            d
            for index, (a, b) in enumerate(zip(mine_list, their_list, strict=True))
            for d in compare_with_ts(a, b, tally, f"{where}[{index}]")
        ]
    if isinstance(mine, float) and mine.is_integer() and type(theirs) is int:
        # JS 는 정수 값의 수를 소수점 없이 적는다(1.0 → 1).
        return [] if int(mine) == theirs else [f"{where}: {mine!r} != {theirs!r}"]
    if type(mine) is not type(theirs) or mine != theirs:
        return [f"{where}: {mine!r} != {theirs!r}"]
    return []


# ── 가상 낱줄(esg-lab `ts/scope3/test/helpers.ts` 의 가상 계수 열을 낱줄로) ──

USD_2022: Final = "2022 USD, purchaser price"


def synthetic_record(
    record_id: str,
    name: str,
    categories: tuple[int, ...],
    factor_type: str,
    per: str,
    value: str | None,
    *,
    license_status: str = "ok",
    gas: str = "CO2e",
    naics: str | None = None,
    path: tuple[str, ...] = (),
    record_type: str = "emission_factor",
) -> RawRecord:
    """★ 가상(synthetic)이다. 값은 계산하기 쉬운 숫자로 지어냈고 실제 배출계수가 아니다."""
    return RawRecord(
        id=record_id,
        record_type=record_type,
        gas=gas,
        value=None if value is None else 1.0,  # 「값이 있는가」만 보는 칸이다. 계산은 value_raw 로 한다.
        value_raw=value,
        scope3_categories=categories,
        factor_type=factor_type,
        name_original=name,
        category_path=path,
        unit=f"kg CO2e/{per}",
        unit_numerator="kg CO2e",
        unit_denominator=per,
        license_status=license_status,
        source_id="synthetic",
        region="GLOBAL",
        classification={"system": "NAICS 2017", "code": naics} if naics is not None else None,
        spend={"currency": "USD", "price_year": 2022, "price_basis": "purchaser"} if factor_type == "spend" else None,
    )


HELPER_RECORDS: Final[tuple[RawRecord, ...]] = (
    synthetic_record(
        "syn:steel-kg", "합성 강판 (synthetic)", (1,), "activity", "kg", "2.5", path=("합성 자재", "금속")
    ),
    synthetic_record(
        "syn:steel-t", "Synthetic steel sheet", (1,), "activity", "tonnes", "2400", path=("Synthetic material", "Metal")
    ),
    synthetic_record(
        "syn:pp-kg",
        "합성 폴리프로필렌 (synthetic)",
        (1,),
        "activity",
        "kg",
        "1.25",
        license_status="disputed",
        path=("합성 자재", "플라스틱"),
    ),
    synthetic_record(
        "syn:truck", "Synthetic truck", (4, 9), "distance", "tonne.km", "0.1", path=("Synthetic freight", "Road")
    ),
    synthetic_record(
        "syn:rail", "Synthetic rail", (6, 7), "distance", "passenger.km", "0.04", path=("Synthetic travel", "Rail")
    ),
    synthetic_record(
        "syn:spend-computer", "Synthetic Computer Manufacturing", (1, 2), "spend", USD_2022, "0.5", naics="334111"
    ),
    synthetic_record(
        "syn:spend-storage", "Synthetic Storage Device Manufacturing", (1, 2), "spend", USD_2022, "0.2", naics="334112"
    ),
    synthetic_record("syn:spend-legal", "Synthetic Legal Services", (1, 2), "spend", USD_2022, "0.1", naics="541199"),
    synthetic_record("syn:steel-kg-ch4", "합성 강판 (synthetic)", (1,), "activity", "kg", "0.01", gas="CH4"),
    synthetic_record("syn:empty", "합성 빈 값 (synthetic)", (1,), "activity", "kg", None),
)


def spend_factors(names: Iterable[str]) -> list[Factor]:
    """이름만 다른 가상 지출 계수들(`syn:s0`, `syn:s1`, …)."""
    records = [
        synthetic_record(f"syn:s{index}", name, (1,), "spend", USD_2022, "0.1") for index, name in enumerate(names)
    ]
    return ListFactorCatalog(records).candidates(CandidateQuery(1, "spend"))
