"""POST /inventory/calc 를 세션과 진짜 DB 로 잰다. 업무 층: 테스트마다 되돌린다.

계산은 DB 를 쓰지 않는다. 그래도 업무 층인 까닭: 세션이 있어야 하는 경로라 테넌트 미들웨어가 DB 에 닿는다.
esg-lab `ts/ghg-calc/test/cli.test.ts` 3건이 여기로 왔다(CLI 의 종료 코드 0/1/2 → 응답의 갈래 200/200+실패 행/400).
"""

import json
from typing import Any

import pytest
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.config.api import api
from esgapi.inventory.engines.scope12.engine_1.tables import merge_tables
from esgapi.inventory.tests.support import (
    DIESEL_ID,
    ETS_GWP,
    GOLDEN,
    TEST_DATA,
    hand_cases,
    package_parts,
    read_test_data,
    synthetic_tables,
)
from tests.support.http import login

pytestmark = pytest.mark.django_db

H01: dict[str, Any] = hand_cases()[0]["activity"]


def post(client: Client, body: Any) -> Any:
    return client.post("/api/inventory/calc", data=json.dumps(body), content_type="application/json")


def error_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


# ── 되는 길 ───────────────────────────────────────────────────────────


def test_sample_rows_with_the_packaged_tables(client: Client, tenants: None) -> None:
    """표를 싣지 않으면 패키지에 실린 표(표본 계수 + 환산 + GWP)로 계산한다. 합계는 검산 사례 H01 의 손계산 값이다."""
    login(client)
    response = post(client, {"rows": [H01], "gwpSetId": ETS_GWP})
    assert response.status_code == 200
    body = response.json()
    assert body["gwpSetId"] == ETS_GWP
    assert [r["status"] for r in body["rows"]] == ["ok"]
    assert body["rows"][0]["co2e"] == "2.5596384"
    assert body["rows"][0]["evidence"]["factor"]["id"] == DIESEL_ID
    assert body["aggregation"]["total"] == {
        "co2e": "2.5596384",
        "co2eByGas": {"CO2": "2.5508736", "CH4": "0.0022176", "N2O": "0.0065472"},
        "okRowCount": 1,
        "failedRowIds": [],
        "complete": True,
    }
    # 묶음 기준을 안 주면 Scope × 배출원 유형이다.
    assert body["aggregation"]["by"] == ["scope", "sourceType"]
    assert [g["key"] for g in body["aggregation"]["groups"]] == [{"scope": "1", "sourceType": "stationary_combustion"}]


def test_synthetic_example_with_tables_in_the_body(client: Client, tenants: None) -> None:
    """TS 의 CLI 테스트 1: 예제 활동 데이터와 가상 계수. 가상 계수는 패키지에 없으므로 본문에 싣는다."""
    login(client)
    example = read_test_data("examples/activity.synthetic.json")
    body = post(
        client, {"rows": example["activities"], "tables": synthetic_tables(), "gwpSetId": example["gwpSetId"]}
    ).json()
    assert body["gwpSetId"] == "synthetic-gwp"
    assert [r["status"] for r in body["rows"]] == ["ok", "ok", "ok", "ok", "ok"]
    # r1 은 검산 사례 H08, r5 는 H11 과 같은 입력이다
    assert body["rows"][0]["co2e"] == "1.8225"
    assert body["rows"][4]["co2e"] == "0.88023725"
    assert body["aggregation"]["total"]["complete"] is True


def test_a_failed_row_is_still_200_and_is_named(client: Client, tenants: None) -> None:
    login(client)
    bad = {**H01, "id": "bad", "fuel": "no-such-fuel"}
    non_decimal = {**H01, "id": "nan", "amount": "1e3"}
    too_long = {**H01, "id": "long", "amount": "1" * 65}
    response = post(client, {"rows": [H01, bad, non_decimal, too_long], "gwpSetId": ETS_GWP})
    assert response.status_code == 200
    body = response.json()
    assert [(r["rowId"], r["status"]) for r in body["rows"]] == [
        ("H01", "ok"),
        ("bad", "failed"),
        ("nan", "failed"),
        ("long", "failed"),
    ]
    assert [r["failure"]["kind"] for r in body["rows"][1:]] == [
        "factor_not_found",
        "invalid_activity",
        "invalid_activity",
    ]
    assert "co2e" not in body["rows"][1]
    assert (body["rows"][1]["scope"], body["rows"][1]["sourceType"]) == (1, "stationary_combustion")
    assert body["rows"][3]["failure"]["reason"] == "십진 문자열이 아니다"
    total = body["aggregation"]["total"]
    assert (total["co2e"], total["okRowCount"], total["failedRowIds"], total["complete"]) == (
        "2.5596384",
        1,
        ["bad", "nan", "long"],
        False,
    )


def test_an_unknown_gwp_set_fails_every_row_not_the_request(client: Client, tenants: None) -> None:
    """TS 의 CLI 테스트 2 (--gwp no-such-set → 종료 코드 1): 기본 세트로 대신하지 않는다."""
    login(client)
    body = post(client, {"rows": [H01], "gwpSetId": "no-such-set"}).json()
    assert body["rows"][0]["failure"] == {"kind": "gwp_set_not_found", "gwpSetId": "no-such-set"}
    total = body["aggregation"]["total"]
    assert (total["co2e"], total["okRowCount"], total["complete"]) == ("0", 0, False)


def test_a_viewer_can_calculate(client: Client, tenants: None) -> None:
    """열람자도 계산한다(쿠키 세션의 역할은 권한에 쓰지 않는다 — 계산 칸은 고객사 사용자)."""
    assert login(client, role="viewer")["role"] == "viewer"
    assert post(client, {"rows": [H01], "gwpSetId": ETS_GWP}).status_code == 200


def test_group_by_is_honoured_and_no_rows_is_fine(client: Client, tenants: None) -> None:
    login(client)
    body = post(client, {"rows": [H01], "gwpSetId": ETS_GWP, "groupBy": ["orgUnit", "period"]}).json()
    assert body["aggregation"]["by"] == ["orgUnit", "period"]
    assert body["aggregation"]["groups"][0]["key"] == {"orgUnit": "synthetic-site", "period": "2025"}
    empty = post(client, {"rows": [], "gwpSetId": ETS_GWP, "groupBy": []})
    assert empty.status_code == 200
    assert empty.json()["aggregation"] == {
        "by": [],
        "groups": [],
        "total": {"co2e": "0", "co2eByGas": {}, "okRowCount": 0, "failedRowIds": [], "complete": True},
    }


def test_absent_keys_stay_absent_and_nulls_stay_null(client: Client, tenants: None) -> None:
    """선택 칸은 키가 없고(null 로 채우지 않는다), 「없음」이 값인 칸은 null 로 나온다."""
    login(client)
    heat = {"id": "h", "orgUnit": "o", "period": "p", "sourceType": "purchased_heat", "amount": "15.5", "unit": "GJ"}
    row = post(client, {"rows": [heat], "tables": synthetic_tables(), "gwpSetId": "synthetic-gwp"}).json()["rows"][0]
    steps = row["evidence"]["steps"]
    assert [("conversion" in step) for step in steps] == [True, False, True, False]
    assert set(row["evidence"]["factor"]["source"]) == {"kind", "note"}  # locator 같은 선택 키가 생기지 않았다
    assert row["energy"] is None
    assert row["gases"][0]["gwp"] is None
    evidence = row["evidence"]
    assert [evidence[k] for k in ("calorificBasis", "oxidationFactor", "sector", "parameterTiers", "facilityUse")] == [
        None,
        None,
        None,
        None,
        None,
    ]


def test_nothing_is_written(client: Client, tenants: None) -> None:
    """저장하지 않는다: 요청이 지나는 동안 나간 SQL 이 없다(쓰는 문장 0 보다 세다. 요청마다의 트랜잭션이 없다)."""
    login(client)
    with CaptureQueriesContext(connection) as queries:
        assert post(client, {"rows": [H01], "gwpSetId": ETS_GWP}).status_code == 200
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")  # 분모: 잡는 장치가 살아 있다(0건이라 통과하는 일을 막는다)
    statements = [q["sql"].lstrip().split(None, 1)[0].upper() for q in queries.captured_queries]
    assert statements == ["SELECT"], statements  # 잡힌 문장은 그 하나뿐 — 요청의 SQL 은 0
    assert not {"INSERT", "UPDATE", "DELETE", "CREATE", "ALTER", "DROP"} & set(statements), statements


# ── 골든: TS 엔진이 낸 JSON 과 응답이 같은가 ──────────────────────────

# (골든 파일, 활동 데이터 파일, 본문에 싣는 표: synthetic|all|None(패키지 표), 묶음 기준|None(기본))
HTTP_GOLDENS: list[tuple[str, str, str | None, list[str] | None]] = [
    ("a-example.json", "examples/activity.synthetic.json", "synthetic", None),
    ("b-handcalc.kr-ets-decree-annex2.json", "golden/inputs/handcalc.kr-ets-decree-annex2.activity.json", "all", None),
    (
        "b-handcalc.ipcc-ar5-100y-kr-nid-2025.json",
        "golden/inputs/handcalc.ipcc-ar5-100y-kr-nid-2025.activity.json",
        "all",
        None,
    ),
    ("b-handcalc.synthetic-gwp.json", "golden/inputs/handcalc.synthetic-gwp.activity.json", "all", None),
    ("b2-package-default.json", "golden/inputs/package-default.activity.json", None, None),
    ("d-failed-row.json", "golden/inputs/failed-row.activity.json", "synthetic", None),
    (
        "e-ordering.json",
        "golden/inputs/ordering.activity.json",
        "synthetic",
        ["orgUnit", "period", "scope", "sourceType"],
    ),
]


@pytest.mark.parametrize(("golden", "activity", "which", "by"), HTTP_GOLDENS, ids=[g[0] for g in HTTP_GOLDENS])
def test_response_equals_the_ts_engine(
    client: Client, tenants: None, golden: str, activity: str, which: str | None, by: list[str] | None
) -> None:
    login(client)
    activity_file: dict[str, Any] = json.loads((TEST_DATA / activity).read_text(encoding="utf-8"))
    body: dict[str, Any] = {"rows": activity_file["activities"], "gwpSetId": activity_file["gwpSetId"]}
    if which == "synthetic":
        body["tables"] = merge_tables(synthetic_tables())
    elif which == "all":
        body["tables"] = merge_tables(*package_parts(), synthetic_tables())
    if by is not None:
        body["groupBy"] = by
    response = post(client, body)
    assert response.status_code == 200
    expected_text = (GOLDEN / golden).read_text(encoding="utf-8")
    # 값으로: 키 하나, null 하나, 「키 없음」 하나까지 같다.
    assert response.json() == json.loads(expected_text)
    # 글자로: 키의 순서까지 같다(응답을 CLI 가 쓰던 꼴로 다시 적어 견준다).
    assert json.dumps(response.json(), ensure_ascii=False, indent=2) + "\n" == expected_text


def test_the_pure_only_golden_is_not_reachable_over_http(client: Client, tenants: None) -> None:
    """골든 (다)의 모르는 배출원 유형 행은 HTTP 로는 400 이다. 그 골든은 순수 층만 견준다(HTTP 골든은 7/8)."""
    login(client)
    activity_file = read_test_data("golden/inputs/unknown-source.activity.json")
    response = post(
        client, {"rows": activity_file["activities"], "tables": synthetic_tables(), "gwpSetId": "synthetic-gwp"}
    )
    assert error_of(response) == (422, "VALIDATION_ERROR")
    assert len(HTTP_GOLDENS) == len(list(GOLDEN.glob("*.json"))) - 1 == 7


# ── 막는 길 ───────────────────────────────────────────────────────────


def test_no_session_is_401(client: Client, tenants: None) -> None:
    assert error_of(post(client, {"rows": [H01], "gwpSetId": ETS_GWP})) == (401, "NO_SESSION")


def test_more_than_1000_rows_is_413(client: Client, tenants: None) -> None:
    login(client)
    small = {"id": "r", "orgUnit": "o", "period": "p", "sourceType": "purchased_heat", "amount": "1", "unit": "GJ"}
    over = post(client, {"rows": [small] * 1001, "gwpSetId": ETS_GWP})
    assert error_of(over) == (413, "TOO_MANY_ROWS")
    assert set(over.json()) == {"error"}  # 계산 결과가 섞여 나오지 않는다
    at_limit = post(client, {"rows": [small] * 1000, "gwpSetId": ETS_GWP})
    assert at_limit.status_code == 200
    assert len(at_limit.json()["rows"]) == 1000


BAD_BODIES: list[tuple[str, Any]] = [
    ("본문이 객체가 아니다", [H01]),
    ("rows 가 없다", {"gwpSetId": ETS_GWP}),
    ("gwpSetId 가 없다 (기본 세트가 없다)", {"rows": [H01]}),
    ("rows 가 배열이 아니다", {"rows": H01, "gwpSetId": ETS_GWP}),
    ("모르는 칸 (본문)", {"rows": [H01], "gwpSetId": ETS_GWP, "tenantId": "tenant-b"}),
    # requireCalorificBasis 는 본문에 없다(의도). 그래서 calorific_basis_mismatch 는 HTTP 로 닿지 않는다.
    ("모르는 칸 (requireCalorificBasis)", {"rows": [H01], "gwpSetId": ETS_GWP, "requireCalorificBasis": "net"}),
    ("모르는 칸 (행)", {"rows": [{**H01, "memo": "x"}], "gwpSetId": ETS_GWP}),
    ("알 수 없는 sourceType", {"rows": [{**H01, "sourceType": "scope3_travel"}], "gwpSetId": ETS_GWP}),
    ("sourceType 이 없다", {"rows": [{k: v for k, v in H01.items() if k != "sourceType"}], "gwpSetId": ETS_GWP}),
    ("amount 가 수다", {"rows": [{**H01, "amount": 1000}], "gwpSetId": ETS_GWP}),
    ("amount 가 없다", {"rows": [{k: v for k, v in H01.items() if k != "amount"}], "gwpSetId": ETS_GWP}),
    ("id 가 수다", {"rows": [{**H01, "id": 1}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: fuel", {"rows": [{**H01, "fuel": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: sector", {"rows": [{**H01, "sector": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: factorId", {"rows": [{**H01, "factorId": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: factorYear", {"rows": [{**H01, "factorYear": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: parameterTiers", {"rows": [{**H01, "parameterTiers": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: facilityUse", {"rows": [{**H01, "facilityUse": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: variant", {"rows": [{**H01, "variant": None}], "gwpSetId": ETS_GWP}),
    ("선택 칸의 null: tables", {"rows": [H01], "gwpSetId": ETS_GWP, "tables": None}),
    ("선택 칸의 null: groupBy", {"rows": [H01], "gwpSetId": ETS_GWP, "groupBy": None}),
    ("factorYear 가 문자열", {"rows": [{**H01, "factorYear": "2025"}], "gwpSetId": ETS_GWP}),
    ("factorYear 가 true", {"rows": [{**H01, "factorYear": True}], "gwpSetId": ETS_GWP}),
    ("등급이 true", {"rows": [{**H01, "parameterTiers": {**H01["parameterTiers"], "co2": True}}], "gwpSetId": ETS_GWP}),
    ("등급이 5", {"rows": [{**H01, "parameterTiers": {**H01["parameterTiers"], "co2": 5}}], "gwpSetId": ETS_GWP}),
    (
        "등급의 oxidation 키가 없다",
        {"rows": [{**H01, "parameterTiers": {"calorific": 2, "co2": 2, "nonCo2": 1}}], "gwpSetId": ETS_GWP},
    ),
    ("모르는 facilityUse", {"rows": [{**H01, "facilityUse": "발전"}], "gwpSetId": ETS_GWP}),
    ("모르는 묶음 기준", {"rows": [H01], "gwpSetId": ETS_GWP, "groupBy": ["fuel"]}),
    ("tables 가 배열", {"rows": [H01], "gwpSetId": ETS_GWP, "tables": []}),
    ("gwpSetId 가 수", {"rows": [H01], "gwpSetId": 1}),
]


@pytest.mark.parametrize(("why", "body"), BAD_BODIES, ids=[why for why, _ in BAD_BODIES])
def test_a_malformed_body_is_422(client: Client, tenants: None, why: str, body: Any) -> None:
    login(client)
    response = post(client, body)
    assert error_of(response) == (422, "VALIDATION_ERROR"), why
    # 받은 값을 되돌려 보내지 않는다(바닥의 처리기가 loc·type 만 적는다).
    assert "scope3_travel" not in response.content.decode()


def test_a_body_that_is_not_json_is_400(client: Client, tenants: None) -> None:
    login(client)
    response = client.post("/api/inventory/calc", data="{not json", content_type="application/json")
    assert response.status_code == 400


def test_tables_that_fail_the_check_are_400_invalid_tables(client: Client, tenants: None) -> None:
    """TS 의 CLI 테스트 3 (입력 오류 → 종료 코드 2)의 자리. 그 표로는 한 행도 계산하지 않는다."""
    login(client)
    tables = merge_tables(*package_parts())
    received = "-21.000000000000000000000001"
    broken: Any = json.loads(json.dumps(tables))
    broken["gwpSets"][0]["values"]["CH4"] = received
    del broken["factors"][0]["source"]
    response = post(client, {"rows": [H01], "gwpSetId": ETS_GWP, "tables": broken})
    assert error_of(response) == (400, "INVALID_TABLES")
    message: str = response.json()["error"]["message"]
    # 받은 값을 싣는다(TS 원본과 같은 문장). 2026-10-08 사용자 결정, MARC-ISSUE-45 의 3번.
    assert message == (
        f'기준정보 표에 문제가 있다: gwpSets[0].values.CH4: 음수다: "{received}"; factors[0]: 출처(source)가 없다'
    )
    assert "rows" not in response.json()

    # 배열이 빠진 표
    assert error_of(post(client, {"rows": [H01], "gwpSetId": ETS_GWP, "tables": {}})) == (400, "INVALID_TABLES")
    # 표 검사의 둘째 단계(TS 가 보지 않던 칸)에 걸린 것도 같은 갈래다
    unbuilt: Any = json.loads(json.dumps(tables))
    unbuilt["factors"][0]["year"] = "2025"
    response = post(client, {"rows": [H01], "gwpSetId": ETS_GWP, "tables": unbuilt})
    assert error_of(response) == (400, "INVALID_TABLES")
    assert "factors[0]: year 가 정수가 아니다" in response.json()["error"]["message"]


def test_the_invalid_tables_message_carries_the_received_value(client: Client, tenants: None) -> None:
    """거절 응답은 받은 값을 품은 문장(TableProblem.problem)을 싣는다. 값 없는 문장(summary)이 아니다.

    service/apis/inventory.py 를 p.summary 로 되돌리면 이 테스트가 빨개진다(심은 파손의 자리).
    """
    login(client)
    synthetic = {"kind": "synthetic", "note": "n"}
    tables = {
        "unitConversions": [{"from": "a", "to": "b", "factor": "-7.25", "source": synthetic}],
        "factors": [],
        "gwpSets": [{"id": "g", "label": "g", "source": synthetic, "values": {"CH4": "abc"}}],
    }
    response = post(client, {"rows": [], "gwpSetId": "g", "tables": tables})
    assert error_of(response) == (400, "INVALID_TABLES")
    assert response.json()["error"]["message"] == (
        '기준정보 표에 문제가 있다: unitConversions[0].factor: 음수다: "-7.25"; '
        'gwpSets[0].values.CH4: 십진 문자열이 아니다: "abc"'
    )


_HEAD = "기준정보 표에 문제가 있다: "
_SYNTHETIC = {"kind": "synthetic", "note": "n"}
# service/apis/inventory.py 의 _PROBLEM_CHARS · _SHOWN_PROBLEMS 와 같은 값을 여기 따로 못 박는다
# (그쪽 값을 바꾸면 이 테스트들이 빨개진다).
PROBLEM_CHARS = 200
SHOWN_PROBLEMS = 20


def _gwp_tables(values: Any, *, source: Any = None) -> dict[str, Any]:
    gwp = {"id": "g", "label": "g", "source": source or _SYNTHETIC, "values": values}
    return {"unitConversions": [], "factors": [], "gwpSets": [gwp]}


def _combustion_tables(tiers: Any) -> dict[str, Any]:
    factor: dict[str, Any] = {
        "id": "f",
        "version": "v",
        "source": _SYNTHETIC,
        "emissionFactors": [],
        "kind": "combustion",
        "fuel": "diesel",
        "combustionType": "stationary",
        "calorific": {"value": "1", "basis": "net", "energyUnit": "MJ", "perUnit": "L"},
        "parameterTiers": tiers,
    }
    return {"unitConversions": [], "factors": [factor], "gwpSets": []}


# 문제 하나의 문장이 상한(service/apis/inventory.py 의 _PROBLEM_CHARS)을 넘는 갈래들.
# 음수 갈래 말고는 받은 값이 통째로 문장에 든다.
LONG_PROBLEMS: list[tuple[str, dict[str, Any], str]] = [
    ("65자 넘는 문자열", _gwp_tables({"CH4": "9" * 5000}), 'gwpSets[0].values.CH4: 십진 문자열이 아니다: "999'),
    (
        "큰 객체",
        _gwp_tables({"CH4": {"k" + str(i): "v" * 50 for i in range(100)}}),
        'gwpSets[0].values.CH4: 십진 문자열이 아니다: {"k0":"vvv',
    ),
    ("긴 kind", _gwp_tables({}, source={"kind": "K" * 5000}), "gwpSets[0]: 알 수 없는 출처 종류: KKK"),
    ("긴 gas 키", _gwp_tables({"G" * 5000: "x"}), "gwpSets[0].values.GGG"),
    (
        "등급 자리의 큰 값",
        _combustion_tables({"calorific": "T" * 5000, "co2": 1, "nonCo2": 1, "oxidation": None}),
        'factors[0].parameterTiers.calorific: 산정등급(1~4)이 아니다: "TTT',
    ),
    # BMP 밖의 글자(파이썬에서는 코드 포인트 하나). 자른 자리에서 반쪽 대리쌍이 나오지 않는다.
    ("BMP 밖의 글자", _gwp_tables({"CH4": "😀" * 5000}), 'gwpSets[0].values.CH4: 십진 문자열이 아니다: "😀😀'),
]


@pytest.mark.parametrize(("why", "tables", "starts"), LONG_PROBLEMS, ids=[why for why, _, _ in LONG_PROBLEMS])
def test_a_long_problem_sentence_is_cut_at_the_limit(
    client: Client, tenants: None, why: str, tables: dict[str, Any], starts: str
) -> None:
    """문제 하나의 문장(`where: problem`)은 상한까지만 실리고 끝에 … 가 붙는다(최대 상한 + 1자).

    service/apis/inventory.py 의 _shown 에서 자르기를 빼면 이 테스트가 빨개진다(심은 파손의 자리).
    """
    login(client)
    response = post(client, {"rows": [], "gwpSetId": "g", "tables": tables})
    assert error_of(response) == (400, "INVALID_TABLES"), why
    message: str = response.json()["error"]["message"]
    assert message.startswith(_HEAD)
    sentences = message[len(_HEAD) :].split("; ")
    assert [len(s) <= PROBLEM_CHARS + 1 for s in sentences] == [True] * len(sentences), why
    cut = [s for s in sentences if s.endswith("…")]
    assert len(cut) == 1, why
    assert len(cut[0]) == PROBLEM_CHARS + 1
    assert cut[0].startswith(starts), why
    # 응답 본문이 UTF-8 로 그대로 읽힌다(반쪽 대리쌍이 없다)
    response.content.decode("utf-8").encode("utf-8")


def test_a_received_value_that_fits_the_limit_is_shown_whole(client: Client, tenants: None) -> None:
    """상한 안의 값은 자르지 않는다: 음수는 64자까지 수로 읽히고, 65자는 「십진 문자열이 아니다」 갈래로 실린다."""
    login(client)
    longest = "-" + "9" * 63
    assert len(longest) == 64
    conversions = [
        {"from": "a", "to": "b", "factor": longest, "source": _SYNTHETIC},
        {"from": "a", "to": "b", "factor": longest + "9", "source": _SYNTHETIC},
    ]
    tables = {"unitConversions": conversions, "factors": [], "gwpSets": []}
    message: str = post(client, {"rows": [], "gwpSetId": "g", "tables": tables}).json()["error"]["message"]
    assert message == (
        f'{_HEAD}unitConversions[0].factor: 음수다: "{longest}"; '
        f'unitConversions[1].factor: 십진 문자열이 아니다: "{longest}9"'
    )
    assert "…" not in message


def test_the_whole_invalid_tables_message_is_bounded(client: Client, tenants: None) -> None:
    """응답 문장 전체의 상한: 싣는 문제 수 × (문제 하나의 상한 + … 1자 + 사이의 `; ` 2자) + 머리·꼬리."""
    login(client)
    conversions = [{"from": "a", "to": "b", "factor": "x" * 5000, "source": _SYNTHETIC} for _ in range(25)]
    tables = {"unitConversions": conversions, "factors": [], "gwpSets": []}
    message: str = post(client, {"rows": [], "gwpSetId": "g", "tables": tables}).json()["error"]["message"]
    assert message.count("십진 문자열이 아니다") == SHOWN_PROBLEMS == 20
    assert message.endswith("(외 5건)")
    limit = SHOWN_PROBLEMS * (PROBLEM_CHARS + 1 + 2)
    assert len(message) <= len(_HEAD) + limit + len(" (외 5건)")
    assert len(message) > SHOWN_PROBLEMS * PROBLEM_CHARS  # 상한 가까이 찼다


def test_a_long_problem_list_is_cut(client: Client, tenants: None) -> None:
    login(client)
    synthetic = {"kind": "synthetic", "note": "n"}
    conversions = [{"from": "a", "to": "b", "factor": "x", "source": synthetic} for _ in range(25)]
    tables = {"unitConversions": conversions, "factors": [], "gwpSets": []}
    message: str = post(client, {"rows": [], "gwpSetId": "g", "tables": tables}).json()["error"]["message"]
    assert message.count("십진 문자열이 아니다") == 20
    assert message.endswith("(외 5건)")


def test_client_tables_replace_the_packaged_ones(client: Client, tenants: None) -> None:
    """표를 실으면 그 표만 쓴다(패키지의 표와 섞지 않는다): 가상 표만 실으면 경유 표본 계수는 없다."""
    login(client)
    body = post(client, {"rows": [H01], "gwpSetId": "synthetic-gwp", "tables": synthetic_tables()}).json()
    assert body["rows"][0]["failure"]["kind"] == "factor_not_found"


# ── 본문 크기 ─────────────────────────────────────────────────────────


def test_a_body_over_the_django_limit_is_413(client: Client, tenants: None) -> None:
    """본문 상한(settings 의 DATA_UPLOAD_MAX_MEMORY_SIZE, 2.5MB)을 넘는 요청은 413 `body_too_large` 다.

    Django 가 본문을 읽다 RequestDataTooBig 을 던지고 바닥(config/api.py)의 처리기가 받는다.
    밴드 PY8a 전에는 「예상 못 한 오류」 처리기가 503 으로 답했다. 받은 내용은 되돌려 보내지 않는다.
    """
    login(client)
    padding = "x" * (3 * 1024 * 1024)
    response = post(client, {"rows": [], "gwpSetId": padding})
    assert error_of(response) == (413, "BODY_TOO_LARGE")
    assert "xxx" not in response.content.decode()


# ── 계약(OpenAPI) ─────────────────────────────────────────────────────


def test_openapi_declares_the_path_and_its_shapes() -> None:
    document: dict[str, Any] = json.loads(json.dumps(api.get_openapi_schema(path_prefix="")))
    operation = document["paths"]["/inventory/calc"]["post"]
    assert operation["operationId"] == "inventory_calc"
    # 444: Bearer 를 받는다(K2b — 회사 경로는 Bearer 먼저, 머리가 없으면 옛 교환 쿠키)
    assert sorted(operation["responses"]) == ["200", "400", "401", "403", "409", "413", "422", "444", "500", "503"]
    schemas: dict[str, dict[str, Any]] = document["components"]["schemas"]
    for name in ("CalcIn", "CalcRowIn", "CalcTiersIn"):
        assert schemas[name]["additionalProperties"] is False
        fields = {field.lower() for field in schemas[name]["properties"]}
        assert not fields & {"tenantid", "tenant_id", "userid", "user_id", "role"}
    # 선택 칸은 required 에 없고, null 을 받는다고도 적지 않는다.
    row = schemas["CalcRowIn"]
    assert sorted(row["required"]) == ["amount", "id", "orgUnit", "period", "sourceType", "unit"]
    assert row["properties"]["fuel"] == {"title": "Fuel", "type": "string"}
    assert sorted(schemas["CalcIn"]["required"]) == ["gwpSetId", "rows"]
    # 「없음」이 값인 칸은 required 이고 null 을 받는다.
    assert "energy" in schemas["RowOkJson"]["required"]
    assert "conversion" not in schemas["StepJson"]["required"]
    assert "from" in schemas["UnitConversionJson"]["properties"]
