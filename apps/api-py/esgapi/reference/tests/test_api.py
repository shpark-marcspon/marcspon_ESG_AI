"""기준정보의 경로 넷을 진짜 DB 로 잰다. 업무 층: 주인 역할, 테스트마다 되돌린다.

자료는 패키지 사본(600건)을 관리 명령으로 들인 것이다. disputed 인 낱줄은 사본에 없어 가상 출처 한 줄로 심는다.
★ 이 층의 연결은 주인 역할이다. 「앱 역할이 이 표를 읽기만 한다」 는 tests/security/test_reference.py 가 잰다.
"""

import json
from io import StringIO
from typing import Any

import pytest
from django.core.management import call_command
from django.test import Client

from esgapi.reference.models import FactorRecordRow, MappingRow, SourceRow
from esgapi.reference.tests.helpers import ALL_RECORDS, GOLDEN
from tests.support.errors import error_of, fields_of
from tests.support.http import login

pytestmark = pytest.mark.django_db

DIESEL: dict[str, Any] = {
    "fuel": "경유",
    "combustionType": "stationary",
    "industry": {"sector": "manufacturing_construction"},
    "tiers": {"kind": "explicit", "calorific": 2, "co2": 2, "oxidation": 2},
}
TABLE69: dict[str, Any] = {"energyType": "electricity", "source": "guideline_table69", "gasForm": "per_gas"}


@pytest.fixture
def loaded(tenants: None) -> None:
    call_command("import_factors", stdout=StringIO())


@pytest.fixture
def disputed_row(loaded: None) -> str:
    """이용 조건이 disputed 인 가상 출처와 그 낱줄 하나(synthetic)."""
    base = FactorRecordRow.objects.select_related("source").get(id="kr-ets-byl12:hv:p1r5:net")
    SourceRow.objects.create(
        id="synthetic-disputed",
        name="synthetic 출처",
        publisher="synthetic",
        url="https://example.invalid/source",
        version="synthetic",
        retrieved="2026-10-08",
        file_name="synthetic.csv",
        file_sha256="0" * 64,
        license_name="synthetic 조건",
        license_url="https://example.invalid/license",
        license_note="synthetic: 두 문면이 충돌한다",
        license_status="disputed",
    )
    base.pk = "synthetic-disputed:row1"
    base.source_id = "synthetic-disputed"
    base.name_original = "synthetic 경유"
    base.synthetic = True
    base.save(force_insert=True)
    return "synthetic-disputed:row1"


def get(client: Client, path: str, **query: Any) -> Any:
    return client.get(path, query)


def post(client: Client, path: str, body: Any) -> Any:
    return client.post(path, data=json.dumps(body), content_type="application/json")


# ── 세션 ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/api/reference/sources"),
        ("get", "/api/reference/factors"),
        ("post", "/api/reference/assemble"),
        ("post", "/api/reference/assemble-electricity"),
    ],
)
def test_every_path_needs_a_session(client: Client, loaded: None, method: str, path: str) -> None:
    response = client.get(path) if method == "get" else post(client, path, DIESEL)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "NO_SESSION"


@pytest.mark.parametrize("role", ["viewer", "editor", "admin"])
def test_any_role_reads_including_viewer(client: Client, loaded: None, role: str) -> None:
    login(client, role=role)
    assert client.get("/api/reference/sources").status_code == 200
    assert client.get("/api/reference/factors").status_code == 200
    assert post(client, "/api/reference/assemble", DIESEL).json()["ok"] is True
    assert post(client, "/api/reference/assemble-electricity", TABLE69).json()["ok"] is True


def test_there_is_no_write_path(client: Client, loaded: None) -> None:
    login(client, role="admin")
    before = FactorRecordRow.objects.count()
    for method in (client.post, client.put, client.patch, client.delete):
        assert method("/api/reference/factors", data="{}", content_type="application/json").status_code == 405
        assert method("/api/reference/sources", data="{}", content_type="application/json").status_code == 405
    assert FactorRecordRow.objects.count() == before == 600


# ── 출처 ──────────────────────────────────────────────────────────────


def test_sources_carry_their_license_status_and_counts(client: Client, loaded: None) -> None:
    login(client, role="viewer")
    sources = {s["id"]: s for s in client.get("/api/reference/sources").json()["sources"]}
    assert {source_id: s["recordCount"] for source_id, s in sources.items()} == {
        "gir-2024": 8,
        "gir-2025": 32,
        "kr-ets-byl05": 0,
        "kr-ets-byl06": 12,
        "kr-ets-byl10": 385,
        "kr-ets-byl11": 55,
        "kr-ets-byl12": 108,
    }
    assert {s["licenseStatus"] for s in sources.values()} == {"unverified"}
    byl12 = sources["kr-ets-byl12"]
    assert byl12["version"] == "환경부고시 제2025-64호 (2025-04-11 시행)"
    assert (byl12["retrieved"], byl12["url"]) == (
        "2026-10-01",
        "https://www.law.go.kr/LSW/admRulLsInfoP.do?admRulSeq=2100000257748",
    )
    assert "저작권법 제7조" in byl12["licenseNote"]
    assert len(byl12["fileSha256"]) == 64


def test_a_disputed_source_is_listed_with_its_status_and_note(client: Client, disputed_row: str) -> None:
    login(client)
    sources = {s["id"]: s for s in client.get("/api/reference/sources").json()["sources"]}
    disputed = sources["synthetic-disputed"]
    assert (disputed["licenseStatus"], disputed["licenseNote"]) == ("disputed", "synthetic: 두 문면이 충돌한다")


# ── 낱줄 찾기 ─────────────────────────────────────────────────────────


def test_factors_filter_by_source_type_scope_and_gas(client: Client, loaded: None) -> None:
    login(client)

    def total(**query: Any) -> int:
        response = get(client, "/api/reference/factors", **query)
        assert response.status_code == 200, response.content.decode()
        return int(response.json()["total"])

    assert total() == 600
    assert total(source="kr-ets-byl12") == 108
    assert total(source="kr-ets-byl06", record_type="oxidation_factor") == 9
    assert total(record_type="heating_value") + total(record_type="emission_factor") + 9 == 600
    assert total(scope="scope2") == total(source="gir-2025") + total(source="gir-2024") + 3 + 4
    assert total(source="gir-2025", gas="CO2e") == 8
    assert total(source="keiti-epd") == 0
    assert total(scope="scope3") == 0  # 사본에는 Scope 3 낱줄이 없다


def test_q_is_a_substring_match_on_the_names(client: Client, loaded: None) -> None:
    login(client)
    body = get(client, "/api/reference/factors", q="경유", source="kr-ets-byl12").json()
    # 분모는 파일에서 센다: 별표 12 의 낱줄 가운데 이름에 「경유」 가 든 것.
    expected = sorted(r.id for r in ALL_RECORDS if r.source.id == "kr-ets-byl12" and "경유" in r.name_original)
    assert [item["id"] for item in body["items"]] == expected
    assert body["total"] == len(expected) > 0
    assert {item["nameOriginal"] for item in body["items"]} == {"경유"}
    # 대소문자를 가리지 않는다.
    lower = get(client, "/api/reference/factors", q="b-c유").json()["total"]
    assert lower == len([r for r in ALL_RECORDS if "b-c유" in r.name_original.lower()]) > 0
    assert get(client, "/api/reference/factors", q="없는 이름 synthetic").json()["total"] == 0


def test_an_item_carries_every_field_and_its_license(client: Client, loaded: None) -> None:
    login(client)
    body = get(client, "/api/reference/factors", source="kr-ets-byl12", record_type="emission_factor", q="경유").json()
    items = {item["id"]: item for item in body["items"]}
    co2 = items["kr-ets-byl12:ef:p3r3:CO2"]
    assert (co2["valueRaw"], co2["value"], co2["unit"], co2["gas"], co2["gasBasis"]) == (
        "73,200",
        73200.0,
        "kgCO2/TJ",
        "CO2",
        "gas_mass",
    )
    assert (co2["sourceId"], co2["licenseStatus"]) == ("kr-ets-byl12", "unverified")
    assert co2["licenseNote"] is not None
    assert co2["conditions"] == {"병합 셀": "원문 표에서 등유 행과 한 칸을 같이 쓴다"}
    assert co2["scope3Categories"] == []
    assert "PDF 3쪽" in co2["locator"]


def test_pages_by_limit_and_offset(client: Client, loaded: None) -> None:
    login(client)

    def page(**query: Any) -> list[str]:
        return [
            item["id"] for item in get(client, "/api/reference/factors", source="kr-ets-byl06", **query).json()["items"]
        ]

    everything = page()
    assert len(everything) == 12 and everything == sorted(everything)
    assert page(limit=5) == everything[:5]
    assert page(limit=5, offset=5) == everything[5:10]
    assert page(limit=5, offset=10) == everything[10:]
    assert page(offset=12) == []
    default = get(client, "/api/reference/factors").json()
    assert (default["total"], default["limit"], default["offset"], len(default["items"])) == (600, 50, 0, 50)
    assert len(get(client, "/api/reference/factors", limit=200).json()["items"]) == 200


@pytest.mark.parametrize(
    ("query", "expected"),
    [
        # 쿼리의 꼴 틀림은 422(바닥의 처리기), 꼴은 맞는데 업무가 거절하는 것(license 목록)은 400 이다(밴드 E2)
        ({"limit": 201}, (422, "VALIDATION_ERROR")),
        ({"limit": 0}, (422, "VALIDATION_ERROR")),
        ({"offset": -1}, (422, "VALIDATION_ERROR")),
        ({"record_type": "nope"}, (422, "VALIDATION_ERROR")),
        ({"license": "ok,public"}, (400, "BAD_REQUEST")),
        ({"license": ""}, (400, "BAD_REQUEST")),
    ],
)
def test_bad_queries_are_refused(
    client: Client, loaded: None, query: dict[str, Any], expected: tuple[int, str]
) -> None:
    login(client)
    response = get(client, "/api/reference/factors", **query)
    assert (response.status_code, response.json()["error"]["code"]) == expected


def test_disputed_rows_are_hidden_unless_the_license_is_named(client: Client, disputed_row: str) -> None:
    """★ disputed 를 들인 DB 에서도 기본 조회는 그것을 내지 않는다. 명시하면 상태와 덧붙인 말이 같이 나온다."""
    login(client)
    assert FactorRecordRow.objects.count() == 601  # 분모: DB 에는 disputed 한 줄이 있다
    default = get(client, "/api/reference/factors").json()
    assert (default["total"], default["licenses"]) == (600, ["ok", "unverified"])
    assert get(client, "/api/reference/factors", source="synthetic-disputed").json()["total"] == 0
    assert get(client, "/api/reference/factors", q="synthetic 경유").json()["total"] == 0

    named = get(client, "/api/reference/factors", source="synthetic-disputed", license="ok,unverified,disputed").json()
    assert (named["total"], named["licenses"]) == (1, ["disputed", "ok", "unverified"])
    item = named["items"][0]
    assert (item["id"], item["licenseStatus"], item["licenseNote"]) == (
        disputed_row,
        "disputed",
        "synthetic: 두 문면이 충돌한다",
    )
    assert get(client, "/api/reference/factors", license="disputed").json()["total"] == 1
    assert get(client, "/api/reference/factors", license="ok").json()["total"] == 0


# ── 조립 ──────────────────────────────────────────────────────────────


def golden(name: str, part: str) -> Any:
    return json.loads((GOLDEN / f"{name}.{part}.json").read_text(encoding="utf-8"))


def test_assemble_diesel_tier2_shows_its_evidence(client: Client, loaded: None) -> None:
    """경유 고정연소 제조업 Tier 2 → 순발열량 35.2 · CO2 73200 · 산화 0.99 가 근거에 있다."""
    login(client, role="viewer")
    response = post(client, "/api/reference/assemble", DIESEL)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    assert body["ok"] is True and "failure" not in body
    evidence = {p["parameter"]: (p["value"], p["recordId"]) for p in body["value"]["evidence"]["parameters"]}
    assert evidence["calorific"] == ("35.2", "kr-ets-byl12:hv:p1r5:net")
    assert evidence["CO2"] == ("73200", "kr-ets-byl12:ef:p3r3:CO2")
    assert evidence["oxidation"] == ("0.99", "kr-ets-byl06:ox:3:t2")
    factor = body["value"]["factor"]
    assert factor["oxidationFactor"] == "0.99"
    assert "facilityUse" not in factor  # 조립이 싣지 않은 칸은 null 로 채우지 않는다
    # 쓰인 낱줄의 출처마다 이용 조건이 같이 나간다.
    assert [(s["sourceId"], s["licenseStatus"]) for s in body["licenses"]] == [
        ("kr-ets-byl06", "unverified"),
        ("kr-ets-byl10", "unverified"),
        ("kr-ets-byl12", "unverified"),
    ]


@pytest.mark.parametrize(
    ("path", "name"),
    [
        ("/api/reference/assemble", "diesel-manufacturing-tier2"),
        ("/api/reference/assemble", "lng-commercial-tier2"),
        ("/api/reference/assemble-electricity", "electricity-table69"),
        ("/api/reference/assemble-electricity", "electricity-gir2025-co2e"),
    ],
)
def test_the_http_answer_equals_the_ts_assembler(client: Client, loaded: None, path: str, name: str) -> None:
    """DB 와 HTTP 를 거친 답이 TS 조립기의 JSON 과 전체 일치한다(licenses 는 이쪽에서 더한 칸이라 뺀다)."""
    login(client)
    body = post(client, path, golden(name, "request")).json()
    del body["licenses"]
    assert body == golden(name, "expected")


def test_electricity_table_69(client: Client, loaded: None) -> None:
    login(client)
    body = post(client, "/api/reference/assemble-electricity", TABLE69).json()
    factor = body["value"]["factor"]
    assert factor["emissionFactors"][0] == {"gas": "CO2", "value": "0.4567", "massUnit": "t"}
    assert "year" not in factor
    assert body["value"]["evidence"]["co2eGwp"] is None  # 조립이 null 로 실은 칸은 그대로 null 이다
    assert [s["sourceId"] for s in body["licenses"]] == ["kr-ets-byl06"]


def test_failures_come_back_as_200_with_the_branch_name(client: Client, loaded: None) -> None:
    login(client)

    def failure(path: str, body: dict[str, Any]) -> dict[str, Any]:
        response = post(client, path, body)
        assert response.status_code == 200, response.content.decode()
        answer: dict[str, Any] = response.json()
        assert answer["ok"] is False and "value" not in answer and answer["licenses"] == []
        return answer["failure"]

    # 낱줄 없음: 별표 12 에 「LPG」 라는 이름의 발열량 낱줄은 없다(비슷한 이름으로 대신하지 않는다).
    assert failure("/api/reference/assemble", {**DIESEL, "fuel": "LPG", "fuelState": "기체"}) == {
        "kind": "record_not_found",
        "parameter": "calorific",
        "criteria": {
            "source": "kr-ets-byl12",
            "record_type": "heating_value",
            "heating_value_basis": "net",
            "name": "LPG",
        },
    }
    # 빠진 칸은 400 이 아니라 갈래다(기본값이 없다).
    missing = failure("/api/reference/assemble", {key: value for key, value in DIESEL.items() if key != "tiers"})
    assert (missing["kind"], missing["field"]) == ("missing_input", "tiers")
    assert failure("/api/reference/assemble", {})["field"] == "fuel"
    assert failure("/api/reference/assemble", {**DIESEL, "industry": {"ksicCode": "38"}})["kind"] == "sector_ambiguous"
    assert failure("/api/reference/assemble-electricity", {"energyType": "electricity", "gasForm": "per_gas"}) == {
        "kind": "missing_input",
        "field": "source",
        "reason": "전력배출계수의 출처(지침 표-69 / GIR 공표)를 정하지 않았다. 기본값이 없다 (MARC-ISSUE-20 15·17번)",
    }
    gir = {
        "energyType": "electricity",
        "source": "gir_published",
        "gasForm": "co2e",
        "gir": {
            "edition": 2025,
            "period": {"kind": "three_year_average", "from": 2022, "to": 2024},
            "boundary": "consumption",
            "methodology": "ipcc_2006",
        },
    }
    assert failure("/api/reference/assemble-electricity", gir)["kind"] == "record_not_found"


@pytest.mark.parametrize(
    ("path", "body"),
    [
        ("/api/reference/assemble", {**DIESEL, "tenantId": "tenant-b"}),
        (
            "/api/reference/assemble",
            {**DIESEL, "tiers": {"kind": "explicit", "calorific": "2", "co2": 2, "oxidation": 2}},
        ),
        ("/api/reference/assemble", {**DIESEL, "industry": {"ksicCode": 20}}),
        ("/api/reference/assemble", {**DIESEL, "powerGeneration": "yes"}),
        ("/api/reference/assemble-electricity", {**TABLE69, "gasForm": ["co2e", "per_gas"]}),
    ],
)
def test_a_malformed_body_is_422(client: Client, loaded: None, path: str, body: dict[str, Any]) -> None:
    """모르는 칸, 글자 자리의 숫자(와 그 반대)는 조립까지 가지 않고 400 이다."""
    login(client)
    response = post(client, path, body)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_without_the_reference_data_the_answer_is_a_named_error(client: Client, tenants: None) -> None:
    """기준정보를 들이지 않은 DB: 목록은 비어 있고, 조립은 이름 있는 오류로 답한다(빈 성공이 아니다)."""
    login(client)
    assert client.get("/api/reference/sources").json() == {"sources": []}
    assert client.get("/api/reference/factors").json()["total"] == 0
    response = post(client, "/api/reference/assemble", DIESEL)
    assert (response.status_code, response.json()["error"]["code"]) == (503, "REFERENCE_NOT_LOADED")


def test_two_mappings_are_a_named_conflict(client: Client, loaded: None) -> None:
    only = MappingRow.objects.get()
    MappingRow.objects.create(guideline_version="synthetic 다른 판", body=only.body)
    login(client)
    response = post(client, "/api/reference/assemble", DIESEL)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "MAPPING_AMBIGUOUS")


# ── 목록 꼴과 recordType(밴드 E2 ④) ──


def test_factors_carry_the_list_shape_and_the_old_four_with_the_same_values(client: Client, loaded: None) -> None:
    login(client)
    first = get(client, "/api/reference/factors", source="kr-ets-byl06", limit=5).json()
    assert (first["count"], first["isNext"], len(first["results"])) == (12, True, 5)
    assert (first["total"], first["limit"], first["offset"], first["items"]) == (12, 5, 0, first["results"])
    last = get(client, "/api/reference/factors", source="kr-ets-byl06", limit=5, offset=10).json()
    assert (last["count"], last["isNext"], len(last["results"])) == (12, False, 2)
    assert last["items"] == last["results"]


def test_record_type_is_taken_by_the_new_and_the_old_name(client: Client, loaded: None) -> None:
    login(client)
    new = get(client, "/api/reference/factors", source="kr-ets-byl06", recordType="oxidation_factor").json()
    old = get(client, "/api/reference/factors", source="kr-ets-byl06", record_type="oxidation_factor").json()
    assert new["count"] == old["count"] == 9
    assert new["results"] == old["results"]


def test_both_record_type_names_at_once_are_422(client: Client, loaded: None) -> None:
    login(client)
    response = get(client, "/api/reference/factors", recordType="heating_value", record_type="heating_value")
    assert error_of(response) == (422, "VALIDATION_ERROR")
    assert fields_of(response) is not None
