"""골든: esg-lab 의 TS 엔진(f1b2c77, `ts/ghg-calc` 의 `cli.ts calc`)이 낸 JSON 과 순수 층의 출력이 글자까지 같은가.

골든과 그것을 만든 명령은 tests/data/golden/ 에 있다(README.md, make-golden.sh). 순수 층: DB 도 Django 도 쓰지 않는다.
견주는 것은 파일의 글자 전체다: 값, 키의 이름, 키의 순서, null 과 「키 없음」의 구분, 한국어 문장.
"""

import json
from collections.abc import Sequence
from typing import Any

import pytest

from esgapi.inventory.engines.scope12.engine_1.aggregate import GroupKey, aggregate
from esgapi.inventory.engines.scope12.engine_1.calc import calculate_raw
from esgapi.inventory.engines.scope12.engine_1.serialize import output_to_dict
from esgapi.inventory.engines.scope12.engine_1.tables import TablesInvalid, merge_tables, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import CalcOptions
from esgapi.inventory.tests.support import GOLDEN, TEST_DATA, package_parts, synthetic_tables, validated

DEFAULT_BY: tuple[GroupKey, ...] = ("scope", "sourceType")
ALL_KEYS: tuple[GroupKey, ...] = ("orgUnit", "period", "scope", "sourceType")

# (골든 파일, 활동 데이터 파일, 표: synthetic|package|all, 묶음 기준). make-golden.sh 의 calc 줄과 하나씩 짝이다.
PURE_GOLDENS: list[tuple[str, str, str, tuple[GroupKey, ...]]] = [
    ("a-example.json", "examples/activity.synthetic.json", "synthetic", DEFAULT_BY),
    (
        "b-handcalc.kr-ets-decree-annex2.json",
        "golden/inputs/handcalc.kr-ets-decree-annex2.activity.json",
        "all",
        DEFAULT_BY,
    ),
    (
        "b-handcalc.ipcc-ar5-100y-kr-nid-2025.json",
        "golden/inputs/handcalc.ipcc-ar5-100y-kr-nid-2025.activity.json",
        "all",
        DEFAULT_BY,
    ),
    ("b-handcalc.synthetic-gwp.json", "golden/inputs/handcalc.synthetic-gwp.activity.json", "all", DEFAULT_BY),
    ("b2-package-default.json", "golden/inputs/package-default.activity.json", "package", DEFAULT_BY),
    ("c-unknown-source.json", "golden/inputs/unknown-source.activity.json", "synthetic", DEFAULT_BY),
    ("d-failed-row.json", "golden/inputs/failed-row.activity.json", "synthetic", DEFAULT_BY),
    ("e-ordering.json", "golden/inputs/ordering.activity.json", "synthetic", ALL_KEYS),
]


def raw_tables_for(which: str) -> dict[str, object]:
    """골든을 만들 때 CLI 에 준 --factors 와 같은 표(같은 순서)."""
    if which == "synthetic":
        return merge_tables(synthetic_tables())
    if which == "package":
        return merge_tables(*package_parts())
    return merge_tables(*package_parts(), synthetic_tables())


def render(activity: dict[str, Any], tables: dict[str, object], by: Sequence[GroupKey]) -> str:
    """CLI 가 표준 출력에 쓰던 것: JSON.stringify(값, null, 2) 와 줄바꿈 하나."""
    gwp_set_id: str = activity["gwpSetId"]
    rows = calculate_raw(activity["activities"], validated(tables), CalcOptions(gwp_set_id=gwp_set_id))
    output = output_to_dict(gwp_set_id=gwp_set_id, rows=rows, aggregation=aggregate(rows, by))
    return json.dumps(output, ensure_ascii=False, indent=2) + "\n"


@pytest.mark.parametrize(("golden", "activity", "which", "by"), PURE_GOLDENS, ids=[g[0] for g in PURE_GOLDENS])
def test_pure_output_equals_the_ts_engine_letter_for_letter(
    golden: str, activity: str, which: str, by: tuple[GroupKey, ...]
) -> None:
    activity_file: dict[str, Any] = json.loads((TEST_DATA / activity).read_text(encoding="utf-8"))
    assert render(activity_file, raw_tables_for(which), by) == (GOLDEN / golden).read_text(encoding="utf-8")


def test_every_golden_file_is_compared() -> None:
    """골든 폴더에 견주지 않는 파일이 없다(분모)."""
    on_disk = sorted(path.name for path in GOLDEN.glob("*.json"))
    assert on_disk == sorted(golden for golden, _, _, _ in PURE_GOLDENS)
    assert len(on_disk) == 8


def test_the_goldens_cover_what_they_are_for() -> None:
    """골든이 비어서 통과하는 일을 막는다: 성공 행, 두 가지 실패 행, null 과 「키 없음」이 실제로 들어 있다."""

    def load(name: str) -> dict[str, Any]:
        loaded: dict[str, Any] = json.loads((GOLDEN / name).read_text(encoding="utf-8"))
        return loaded

    example = load("a-example.json")
    assert [r["status"] for r in example["rows"]] == ["ok"] * 5
    steps = [s for r in example["rows"] for s in r["evidence"]["steps"]]
    assert any("conversion" in s for s in steps) and any("conversion" not in s for s in steps)
    assert example["rows"][3]["energy"] is None and example["rows"][0]["evidence"]["sector"] is None
    hand = [r for name in sorted(p.name for p in GOLDEN.glob("b-handcalc.*.json")) for r in load(name)["rows"]]
    assert sorted(r["rowId"] for r in hand) == [f"H{n:02d}" for n in range(1, 15)]
    assert all(r["status"] == "ok" for r in hand)
    unknown = load("c-unknown-source.json")["rows"][-1]
    assert (unknown["scope"], unknown["sourceType"], unknown["failure"]["kind"]) == (None, None, "invalid_activity")
    assert load("d-failed-row.json")["rows"][-1]["failure"]["kind"] == "factor_not_found"
    assert len(load("e-ordering.json")["aggregation"]["groups"]) == 6


def test_table_problems_equal_the_ts_validator_letter_for_letter() -> None:
    """틀린 표를 CLI 에 주면 문제 목록이 표준 오류로 나온다(종료 코드 2). 그 글자와 표 검사의 문제 목록이 같은가.

    문제 문장 끝의 받은 값(JSON.stringify 흉내)과 객체의 키 순서, 없는 키의 "undefined" 까지 잰다.
    """
    raw: dict[str, object] = json.loads((GOLDEN / "inputs" / "invalid-tables.json").read_text(encoding="utf-8"))
    result = validate_tables(merge_tables(raw))  # CLI 도 mergeTables 를 거친 뒤 검사한다
    assert isinstance(result, TablesInvalid)
    lines = "\n".join(f"  {p.where}: {p.problem}" for p in result.problems)
    expected = (GOLDEN / "f-invalid-tables.stderr.txt").read_text(encoding="utf-8")
    assert f"기준정보 표에 문제가 있다:\n{lines}\n" == expected
    assert len(result.problems) == 58
