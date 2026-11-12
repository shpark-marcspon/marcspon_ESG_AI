"""골든의 입력(활동 데이터 파일)을 만든다. make-golden.sh 가 부른다.   사용: python make_inputs.py

재료는 esg-lab 에서 옮겨 둔 사본 둘이다: ../handcalc-cases.json, ../examples/activity.synthetic.json
결과는 inputs/ 아래에 쓴다. 같은 재료면 늘 같은 글자가 나온다.
"""

import json
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
DATA = HERE.parent
INPUTS = HERE / "inputs"

# 패키지에 실린 자료(표본 계수 + 환산 + GWP)만으로 계산되는 검산 사례. 가상 계수를 쓰는 사례는 빠진다.
PACKAGE_ONLY = ("H01", "H03", "H04", "H06", "H12", "H13")


def write(name: str, gwp_set_id: str, activities: list[dict[str, Any]], comment: str) -> None:
    body = {"$comment": comment, "gwpSetId": gwp_set_id, "activities": activities}
    (INPUTS / name).write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    INPUTS.mkdir(exist_ok=True)
    cases: list[dict[str, Any]] = json.loads((DATA / "handcalc-cases.json").read_text(encoding="utf-8"))["cases"]
    example: dict[str, Any] = json.loads((DATA / "examples" / "activity.synthetic.json").read_text(encoding="utf-8"))
    example_rows: list[dict[str, Any]] = example["activities"]

    # (나) 검산 사례 H01~H14 를 GWP 세트마다 한 파일로. CLI 는 실행마다 세트 하나다.
    gwp_set_ids: list[str] = sorted({case["gwpSetId"] for case in cases})
    for gwp_set_id in gwp_set_ids:
        rows = [case["activity"] for case in cases if case["gwpSetId"] == gwp_set_id]
        write(f"handcalc.{gwp_set_id}.activity.json", gwp_set_id, rows, "검산 사례의 activity (가상의 조직과 사용량)")

    # (나′) 패키지 자료만으로 되는 사례. 엔드포인트에 tables 를 싣지 않고 부른 것과 견준다.
    rows = [case["activity"] for case in cases if case["id"] in PACKAGE_ONLY]
    write("package-default.activity.json", "kr-ets-decree-annex2", rows, "패키지 자료만으로 계산되는 검산 사례")

    # (다) 순수 층 전용: 알 수 없는 배출원 유형 행 하나를 더한 묶음. 엔드포인트는 이 행을 400 으로 막는다.
    unknown = {
        "id": "r6",
        "orgUnit": "synthetic-plant-2",
        "period": "2025-02",
        "sourceType": "scope3_travel",
        "amount": "1",
        "unit": "GJ",
    }
    write(
        "unknown-source.activity.json", example["gwpSetId"], [*example_rows, unknown], "synthetic + 모르는 배출원 유형"
    )

    # (라) 엔드포인트 전용: HTTP 로 닿는 실패 행(없는 연료 → factor_not_found)을 더한 묶음.
    no_fuel = {
        "id": "r6",
        "orgUnit": "synthetic-plant-2",
        "period": "2025-02",
        "sourceType": "stationary_combustion",
        "fuel": "no-such-fuel",
        "amount": "10",
        "unit": "L",
    }
    write("failed-row.activity.json", example["gwpSetId"], [*example_rows, no_fuel], "synthetic + 계수가 없는 연료")

    # (마) 묶음의 순서: BMP 밖의 글자(이모지)와 U+E000 뒤의 글자(전각 엔 기호)가 섞인 조직 이름.
    #      JS 는 UTF-16 코드 단위로 견주어 이모지가 앞, 파이썬의 문자열 비교는 코드 포인트라 이모지가 뒤다.
    org_units = ["￥-site", "😀-site", "가-site", 'a"site', "Z-site", "a-site"]
    rows = [
        {
            "id": f"o{i}",
            "orgUnit": org_unit,
            "period": "2025-01",
            "sourceType": "purchased_heat",
            "amount": str(i + 1),
            "unit": "GJ",
        }
        for i, org_unit in enumerate(org_units)
    ]
    write("ordering.activity.json", example["gwpSetId"], rows, "synthetic. 묶음의 순서를 재는 조직 이름")

    # (바) 틀린 기준정보 표. CLI 는 문제 목록을 표준 오류로 내고 종료 코드 2 로 끝난다. 문제 문장의 글자를 견준다.
    (INPUTS / "invalid-tables.json").write_text(
        json.dumps(invalid_tables(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )


def invalid_tables() -> dict[str, Any]:
    """표 검사가 내는 문제 문장을 한 번씩 건드리는 표. 값은 전부 가상이다."""
    synthetic = {"kind": "synthetic", "note": "n"}
    # 십진 문자열이 아닌 값들: 문제 문장 끝에 JSON.stringify(값) 이 붙는다.
    odd_values: list[Any] = [
        None,
        True,
        1.5,
        2.0,
        1e21,
        1e-7,
        123456789012345678901234567890,
        0.000001,
        -0.0,
        "1e3",
        "１２",
        'a"b\\c\n',
        "😀",
        [1, "2", None, [2.50]],
        {"b": 1, "10": "x", "2": [True], "a": {"k": None}},
        "-21",
        "-0.5",
    ]
    conversions: list[Any] = [{"from": "a", "to": "b", "factor": value, "source": synthetic} for value in odd_values]
    conversions.append({"from": "a", "to": "b", "source": synthetic})  # factor 없음 → undefined
    conversions += ["x", {"from": "", "to": "b", "factor": "1", "source": {"kind": "definition", "note": ""}}]
    return {
        "$comment": "synthetic. 일부러 틀리게 적은 표다.",
        "unitConversions": conversions,
        "gwpSets": [
            7,
            {"id": "", "label": "l", "source": synthetic, "values": []},
            {"id": "g", "label": "l", "source": {"note": "kind 가 없다"}, "values": {"CO2": "1", "CH4": 21, "1": "x"}},
            {"id": "g2", "label": "l", "source": {"kind": ["cited"], "note": "n"}, "values": {}},
            {"id": "g3", "label": "l", "source": "출처", "values": {}},
            {
                "id": "g4",
                "label": "l",
                "source": {"kind": "cited", "title": "t", "url": "", "checkedOn": "어제"},
                "values": {},
            },
        ],
        "factors": [
            None,
            {"id": "f", "version": "", "source": synthetic, "emissionFactors": "none"},
            {
                "kind": "combustion",
                "id": "c",
                "version": "v",
                "source": {"kind": "cited", "title": "", "url": "ftp://x", "checkedOn": "2026-10-01"},
                "emissionFactors": [3, {"gas": "", "value": "1", "massUnit": "kg"}, {"gas": "CO2", "massUnit": "kg"}],
                "fuel": "",
                "combustionType": "both",
                "calorific": {"value": "x", "basis": "low", "energyUnit": "", "perUnit": "L"},
                "oxidationFactor": None,
                "sector": "",
                "facilityUse": "발전",
                "parameterTiers": {"calorific": 5, "co2": "2", "oxidation": True},
            },
            {
                "kind": "combustion",
                "id": "c2",
                "version": "v",
                "source": synthetic,
                "emissionFactors": [],
                "fuel": "f",
                "combustionType": "mobile",
            },
            {
                "kind": "combustion",
                "id": "c3",
                "version": "v",
                "source": synthetic,
                "emissionFactors": [],
                "fuel": "f",
                "combustionType": "mobile",
                "calorific": {"value": "1", "basis": "net", "energyUnit": "MJ", "perUnit": "L"},
                "parameterTiers": {"calorific": 1, "co2": 2.0, "nonCo2": 4, "oxidation": 2},
            },
            {
                "kind": "combustion",
                "id": "c4",
                "version": "v",
                "source": synthetic,
                "emissionFactors": [],
                "fuel": "f",
                "combustionType": "mobile",
                "calorific": {"value": "1", "basis": "net", "energyUnit": "MJ", "perUnit": "L"},
                "parameterTiers": "tier2",
            },
            {
                "kind": "purchased_energy",
                "id": "p",
                "version": "v",
                "source": synthetic,
                "emissionFactors": [],
                "energyType": "steam",
            },
            {"kind": "scope3", "id": "s", "version": "v", "source": synthetic, "emissionFactors": []},
            {"id": "n", "version": "v", "source": synthetic, "emissionFactors": []},
        ],
    }


if __name__ == "__main__":
    main()
