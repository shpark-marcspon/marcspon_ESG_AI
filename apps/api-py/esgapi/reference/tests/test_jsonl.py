"""jsonl 한 줄의 꼴 검사와 사본의 성질. 순수 층(파일은 패키지 사본만 읽는다. DB 가 없다).

TS 원본 `files.test.ts` 의 「파일 어댑터」 넷 가운데 셋의 뜻을 옮겼다(출처별 건수, 대응표의 항목 수, 꼴이 다른 줄은
예외). 넷째(조립 함수가 파일·시계를 쓰지 않는다)는 test_calc_is_pure.py 에 있다. 「CLI」 여섯은 옮기지 않았다:
CLI 가 없고(읽기 API 가 그 자리다) 그 가운데 셋은 엔진 재통과·덮인 범위다.
"""

import json
from collections import Counter
from typing import Any

import pytest

from esgapi.reference.calc import MappingShapeError, mapping_from_json, read_value_raw
from esgapi.reference.jsonl import LineInvalid, read_records
from esgapi.reference.tests.helpers import ALL_RECORDS, DATA, MAPPING


def _lines() -> list[str]:
    return DATA.joinpath("factors.kr.jsonl").read_text(encoding="utf-8").splitlines()


def _first() -> dict[str, Any]:
    line: dict[str, Any] = json.loads(next(line for line in _lines() if '"kr-ets-byl12"' in line))
    return line


def _read(record: dict[str, Any]) -> list[Any]:
    return list(read_records([json.dumps(record, ensure_ascii=False)]))


def test_the_copy_holds_600_rows_from_six_sources() -> None:
    """사본의 출처별 건수가 esg-lab `data/factors/SUMMARY.md` 의 수와 같다(지침 560 + GIR 40 = 600)."""
    assert dict(Counter(r.source.id for r in ALL_RECORDS)) == {
        "gir-2025": 32,
        "gir-2024": 8,
        "kr-ets-byl12": 108,
        "kr-ets-byl11": 55,
        "kr-ets-byl10": 385,
        "kr-ets-byl06": 12,
    }
    assert len({r.id for r in ALL_RECORDS}) == 600
    assert not any(r.synthetic for r in ALL_RECORDS)
    # 조립이 받는 낱줄에는 value(float) 칸이 아예 없다.
    assert "value" not in {name for r in ALL_RECORDS[:1] for name in vars(r)}


def test_the_mapping_copy_has_the_counted_entries() -> None:
    assert [s.key for s in MAPPING.sectors] == [
        "energy_industries",
        "manufacturing_construction",
        "commercial_public",
        "residential_other",
    ]
    assert [o.division for o in MAPPING.sector_overlaps] == ["38", "58", "59"]
    assert len(MAPPING.tier_minimums) == 45
    assert len([e for e in MAPPING.fuel_names if e.basis == "assumed"]) == 25
    assert len(MAPPING.national_ef_names) == 8
    assert len(MAPPING.fuel_states) == 34


def test_the_two_number_rules_agree_on_every_row_of_the_copy() -> None:
    """★ esg-lab 의 적재기(지수 표기·음수를 받는다)와 조립(`read_value_raw`)이 갈리는 낱줄이 사본에 없다.

    분모: 사본에서 값이 있는(value_status = ok) 낱줄 599. 값 없는 1건(별표 11)은 value_raw 가 「-」 다.
    무효 조건: 사본 600건에서만 잰 것이다. 다른 출처(DEFRA·EPA·KEITI)는 조립이 읽지 않는다.
    """
    with_value = without = 0
    for _, record in read_records(_lines()):
        if record.value_status == "ok":
            with_value += 1
            read = read_value_raw(record.value_raw)
            assert read is not None, record.id
            assert float(read) == record.value, record.id
        else:
            without += 1
            assert read_value_raw(record.value_raw) is None
    assert (with_value, without) == (599, 1)


def test_a_malformed_line_is_an_error_with_its_line_number() -> None:
    first = json.dumps(_first(), ensure_ascii=False)
    assert len(list(read_records([first, "", "  "]))) == 1
    with pytest.raises(LineInvalid, match=r"^2행: ") as not_json:
        list(read_records([first, "{not json"]))
    assert not_json.value.line_no == 2
    broken = _first()
    del broken["value_raw"]
    with pytest.raises(LineInvalid, match=r"^1행: value_raw \(missing"):
        _read(broken)


@pytest.mark.parametrize(
    ("patch", "where"),
    [
        ({"schema_version": "0.2"}, "schema_version"),
        ({"unknown_field": 1}, "unknown_field"),
        ({"license_status": "public"}, "license_status"),
        ({"value": "45.0"}, "value"),
        ({"value_raw": None}, "value_status 가 ok 이면"),
        ({"id": "other-source:hv:1"}, "id 는"),
        ({"heating_value_basis": None}, "발열량 낱줄은"),
        ({"scope3_categories": [1]}, "scope3_categories 는"),
        ({"factor_type": "spend"}, "spend 는"),
    ],
)
def test_shape_rules(patch: dict[str, Any], where: str) -> None:
    """판(schema_version 0.1)을 못 박고, 모르는 칸을 거절하고, 정본 스키마의 allOf 규칙을 같이 본다."""
    with pytest.raises(LineInvalid) as caught:
        _read({**_first(), **patch})
    assert where in caught.value.where


def test_a_mapping_without_its_sectors_is_an_error() -> None:
    body: dict[str, Any] = json.loads(DATA.joinpath("mappings.kr-ets.json").read_text(encoding="utf-8"))
    assert mapping_from_json(body) == MAPPING
    del body["sectors"]
    with pytest.raises(MappingShapeError, match="sectors"):
        mapping_from_json(body)
