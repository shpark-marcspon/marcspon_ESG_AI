"""POST /inventory/scope3/shortlist · /inventory/scope3/classify 를 세션과 진짜 DB 로 잰다.

업무 층: 테스트마다 되돌린다.

계수는 가상 표(tests/data/scope3/factors.synthetic.jsonl. G1 골든의 것과 같은 파일)를 `import_factors` 로 심는다
(`reference` 의 models 를 import 하지 않는다). 분류는 이음매(`services.scope3_gateway`)에 모의 클라이언트를 꽂아 잰다.

★ 이 파일에는 소켓 문지기가 걸리지 않는다(`django_db` 표시가 있으면 문지기가 물러난다. DB 연결도 소켓이다).
  「실호출 0」을 문지기로 잰 것은 test_scope3_services.py 와 순수 층의 테스트다.
"""

import json
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.db import connection
from django.test import Client
from django.test.utils import CaptureQueriesContext

from esgapi.core.exceptions import ApplicationError
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.permissions import OPERATION_POLICY, OPERATOR
from esgapi.inventory.service.actions import scope3_shortlist as actions
from esgapi.inventory.service.services import inventory as services
from esgapi.inventory.tests.scope3_catalog_support import G1_FACTORS, G1_GOLDEN
from esgapi.inventory.tests.scope3_llm_support import classification, mock_client, user_texts
from esgapi.reference.service.selectors import reference as selectors
from tests.support.http import login

CLASSIFY_AS_IS = OPERATION_POLICY["inventory_scope3_classify"]  # 표 그대로의 칸(고객사 사용자)

pytestmark = pytest.mark.django_db

ALL_LICENSES = "ok,unverified,disputed"
# 가상 표의 후보 34(ok 31 · disputed 3)와 후보가 아닌 줄 셋.
NOT_CANDIDATES = {"syn:steel-kg-ch4", "syn:empty", "syn:nocat"}
DISPUTED = {"syn-d:pp-kg", "syn-d:cement-kg", "syn-d:truck-5t"}


def lines() -> list[dict[str, Any]]:
    return [json.loads(line) for line in G1_FACTORS.read_text(encoding="utf-8").splitlines() if line.strip()]


def seed(path: Path, *, drop: frozenset[str] = frozenset(), extra: tuple[dict[str, Any], ...] = ()) -> None:
    """가상 표(일부를 빼거나 줄을 더해)를 DB 에 들인다. disputed 까지 들인다: 걸러 내는 것은 경로의 일이다."""
    records = [line for line in lines() if line["id"] not in drop] + list(extra)
    path.write_text("".join(json.dumps(record, ensure_ascii=False) + "\n" for record in records), encoding="utf-8")
    call_command("import_factors", str(path), "--include-license", ALL_LICENSES, stdout=StringIO())


@pytest.fixture
def table(tenants: None, tmp_path: Path) -> None:
    seed(tmp_path / "factors.jsonl")


def shortlist(client: Client, row: dict[str, Any], category: Any = 1, **more: Any) -> Any:
    body = {"row": row, "category": category, **more}
    return client.post("/api/inventory/scope3/shortlist", data=json.dumps(body), content_type="application/json")


def classify(client: Client, rows: list[dict[str, Any]]) -> Any:
    return client.post(
        "/api/inventory/scope3/classify", data=json.dumps({"rows": rows}), content_type="application/json"
    )


def error_of(response: Any) -> tuple[int, str]:
    return response.status_code, response.json()["error"]["code"]


def candidate_ids(body: dict[str, Any]) -> list[str]:
    return [candidate["id"] for candidate in body["candidates"]]


STEEL = {"itemName": "합성 강판", "unit": "kg"}

# ── 후보 추리기: 갈래 ─────────────────────────────────────────────────


def test_a_row_with_a_matching_unit_gets_activity_candidates(client: Client, table: None) -> None:
    login(client)
    response = shortlist(client, STEEL)
    assert response.status_code == 200
    body = response.json()
    assert (body["status"], body["basis"], body["fallbackReason"]) == ("shortlisted", "physical", None)
    assert body["method"] == "lexical-v2"
    assert body["description"] == "lexical-v2: 낱말 단위 BM25 (k1=1.2, b=0.75), 한글 두 글자 조각 씀, 동점은 표 순서"
    # 범주 1 의 활동 기반 후보 12 가운데 disputed 둘을 뺀 10. 분모가 kg·톤이라 전부 단위가 맞는다.
    assert (body["total"], body["shown"], body["lexicalMatches"]) == (10, 10, 7)
    assert candidate_ids(body)[0] == "syn:steel-kg"
    assert body["candidates"][0] == {
        "id": "syn:steel-kg",
        "name": "합성 강판 (synthetic)",
        "path": "합성 자재 > 금속",
        "per": "kg",
        "source": "syn",
        "region": "GLOBAL",
        "licenseStatus": "ok",
    }
    first = body["evidence"][0]
    assert (first["id"], first["rank"], first["lexical"]["rank"]) == ("syn:steel-kg", 1, 1)
    assert first["lexical"]["matchedTerms"] == ["합성", "#합성", "강판", "#강판"]
    assert [entry["rank"] for entry in body["evidence"]] == list(range(1, 11))
    # 낱말이 겹치지 않아 표 순서로 채워진 후보에는 lexical 키가 없다(null 이 아니다).
    assert "lexical" not in body["evidence"][-1]
    assert body["catalog"] == {"rejected": [], "rejectedTotal": 0}
    # 계수 값은 나가지 않는다.
    assert "value" not in response.content.decode().lower()


def test_an_unknown_unit_falls_back_to_spend_with_the_reason(client: Client, table: None) -> None:
    login(client)
    body = shortlist(client, {"itemName": "노트북 구매", "unit": "대"}).json()
    assert (body["status"], body["basis"], body["fallbackReason"]) == ("shortlisted", "spend", "unit_mismatch")
    assert (body["total"], body["shown"], body["lexicalMatches"]) == (7, 7, 0)
    # 이름에 경로가 없는 후보에는 path 키가 없다.
    assert all("path" not in candidate for candidate in body["candidates"])


def test_a_category_without_activity_candidates_falls_back_to_spend(
    client: Client, tenants: None, tmp_path: Path
) -> None:
    seed(tmp_path / "f.jsonl", drop=frozenset({"syn:server-ea"}))  # 범주 2 의 하나뿐인 활동 기반 후보를 뺀다.
    login(client)
    body = shortlist(client, {"itemName": "서버 장비", "unit": "ea"}, category=2).json()
    assert (body["status"], body["basis"], body["fallbackReason"]) == ("shortlisted", "spend", "no_activity_candidates")


def test_no_candidates_on_either_basis_is_a_status_not_an_empty_list(client: Client, table: None) -> None:
    login(client)
    response = shortlist(client, {"itemName": "출장 렌터카", "unit": "대"}, category=6)
    assert response.status_code == 200
    assert response.json() == {
        "status": "no_candidates",
        "physical": "unit_mismatch",
        "catalog": {"rejected": [], "rejectedTotal": 0},
    }
    # 기반을 골라 물었을 때: 지출 기반만 물었으면 활동 쪽은 보지 않았다(null).
    assert shortlist(client, STEEL, category=6, basis="spend").json()["physical"] is None
    physical = shortlist(client, {"itemName": "출장 렌터카", "unit": "대"}, category=6, basis="physical").json()
    assert (physical["status"], physical["physical"]) == ("no_candidates", "unit_mismatch")


def test_an_empty_table_answers_no_candidates(client: Client, tenants: None) -> None:
    """패키지에 실린 사본만 들인 DB 처럼 Scope 3 후보가 한 건도 없을 때."""
    login(client)
    body = shortlist(client, STEEL).json()
    assert (body["status"], body["physical"]) == ("no_candidates", "no_activity_candidates")


def test_an_explicit_basis_is_used_as_given(client: Client, table: None) -> None:
    login(client)
    spend = shortlist(client, STEEL, basis="spend").json()
    assert (spend["basis"], spend["fallbackReason"], spend["total"]) == ("spend", None, 7)
    physical = shortlist(client, STEEL, basis="physical").json()
    assert (physical["basis"], physical["fallbackReason"], physical["total"]) == ("physical", None, 10)


def test_a_transport_row_with_a_weight_gets_tonne_km_factors(client: Client, table: None) -> None:
    login(client)
    row = {"itemName": "원자재 운송", "transport": {"mode": "트럭", "weightKg": "21000"}}
    body = shortlist(client, row, category=4).json()
    # 범주 4 의 활동·거리 후보 7 가운데 분모가 tonne.km 인 것 6, 그 가운데 disputed 하나를 뺀 5.
    assert (body["basis"], body["total"]) == ("physical", 5)
    assert candidate_ids(body)[0] == "syn:hgv"
    assert {candidate["per"] for candidate in body["candidates"]} == {"tonne.km"}
    # 무게가 없으면 단위로 본다.
    by_km = shortlist(client, {"itemName": "원자재 운송", "unit": "km", "transport": {"mode": "트럭"}}, category=4)
    assert candidate_ids(by_km.json()) == ["syn:van-km"]


def test_english_keywords_are_searched_too(client: Client, table: None) -> None:
    login(client)
    body = shortlist(client, {"itemName": "법률 자문 용역", "unit": "식"}, keywords=["legal", "services"]).json()
    assert candidate_ids(body)[0] == "syn:spend-legal"
    assert body["evidence"][0]["lexical"]["matchedTerms"] == ["legal", "service"]
    assert body["lexicalMatches"] == 1


# ── 후보 추리기: 이용 조건 ────────────────────────────────────────────


def test_disputed_factors_appear_only_when_asked_for(client: Client, table: None) -> None:
    login(client)
    row = {"itemName": "폴리프로필렌 수지", "unit": "kg"}
    default = shortlist(client, row).json()
    assert default["total"] == 10
    assert not set(candidate_ids(default)) & DISPUTED
    assert {candidate["licenseStatus"] for candidate in default["candidates"]} == {"ok"}
    explicit = shortlist(client, row, license=ALL_LICENSES).json()
    assert explicit["total"] == 12
    assert candidate_ids(explicit)[0] == "syn-d:pp-kg"
    assert explicit["candidates"][0]["licenseStatus"] == "disputed"
    only = shortlist(client, row, license="disputed").json()
    assert set(candidate_ids(only)) == {"syn-d:pp-kg", "syn-d:cement-kg"}


@pytest.mark.parametrize("text", ["ok,bogus", "ok,ok", "OK", ","])
def test_an_unknown_license_name_is_rejected_not_dropped(client: Client, table: None, text: str) -> None:
    login(client)
    assert error_of(shortlist(client, STEEL, license=text)) == (400, "INVALID_LICENSE")


# ── 후보 추리기: 방식 ─────────────────────────────────────────────────


def test_the_method_and_bigram_switch(client: Client, table: None) -> None:
    login(client)
    first = shortlist(client, STEEL, method="lexical-v1").json()
    assert first["method"] == "lexical-v1"
    assert first["description"].startswith("lexical-v1: ")
    assert first["evidence"][0]["lexical"] == {
        "rank": 1,
        "score": 8,
        "matchedTerms": ["합성", "강판", "#합성", "#강판"],
    }
    row = {"itemName": "프로필렌 원료", "unit": "kg"}
    with_bigrams = shortlist(client, row, license=ALL_LICENSES).json()
    assert candidate_ids(with_bigrams)[0] == "syn-d:pp-kg"
    assert with_bigrams["lexicalMatches"] == 1
    without = shortlist(client, row, license=ALL_LICENSES, bigrams=False).json()
    assert "안 씀" in without["description"]
    assert without["lexicalMatches"] == 0


def test_size_bounds(client: Client, table: None) -> None:
    login(client)
    one = shortlist(client, STEEL, size=1).json()
    assert (one["total"], one["shown"], candidate_ids(one)) == (10, 1, ["syn:steel-kg"])
    assert shortlist(client, STEEL, size=50).status_code == 200
    for size in (0, 51, -1, "5", 2.5, True):
        assert error_of(shortlist(client, STEEL, size=size)) == (422, "VALIDATION_ERROR"), size


# ── 후보 추리기: 거절 ─────────────────────────────────────────────────


@pytest.mark.parametrize("category", [3, 5, 8, 0, True, "1", 1.5, None, "other"])
def test_only_the_six_categories_are_accepted(client: Client, table: None, category: Any) -> None:
    login(client)
    assert error_of(shortlist(client, STEEL, category=category)) == (422, "VALIDATION_ERROR")


@pytest.mark.parametrize(
    "more",
    [
        {"method": "embedding"},
        {"method": "hybrid"},
        {"basis": "activity"},
        {"bigrams": "yes"},
        {"keywords": ["a"] * 9},
        {"keywords": [""]},
        {"keywords": ["k" * 61]},
        {"tenantId": "t"},
        {"route": "light"},
    ],
)
def test_unknown_methods_fields_and_out_of_range_values_are_rejected(
    client: Client, table: None, more: dict[str, Any]
) -> None:
    login(client)
    assert error_of(shortlist(client, STEEL, **more)) == (422, "VALIDATION_ERROR")


def test_row_shape_limits(client: Client, table: None) -> None:
    login(client)
    assert shortlist(client, {"itemName": "가" * 200}).status_code == 200
    for row in (
        {"itemName": "가" * 201},
        {"itemName": ""},
        {"unit": "kg"},
        {"itemName": "x", "unit": None},
        {"itemName": "x", "quantity": "1"},
        {"itemName": "x", "transport": {"weightKg": "1"}},
        {"itemName": "x", "transport": {"mode": "트럭", "weightKg": "1" * 65}},
    ):
        assert error_of(shortlist(client, row)) == (422, "VALIDATION_ERROR"), row


def test_any_role_can_shortlist_and_no_session_cannot(client: Client, table: None) -> None:
    assert error_of(shortlist(client, STEEL)) == (401, "NO_SESSION")
    assert login(client, role="viewer")["role"] == "viewer"
    assert shortlist(client, STEEL).status_code == 200


# ── 후보 추리기: value_raw 와 표 순서 ─────────────────────────────────


def exponent_line() -> dict[str, Any]:
    """자격은 갖췄는데(CO2e·값 있음·범주 있음) value_raw 가 지수 표기인 가상 줄."""
    base = next(line for line in lines() if line["id"] == "syn:steel-kg")
    return {**base, "id": "syn:exponent", "value": 9e-05, "value_raw": "9e-05"}


def test_a_qualified_line_with_exponent_notation_is_left_out_and_reported(
    client: Client, tenants: None, tmp_path: Path
) -> None:
    seed(tmp_path / "f.jsonl", extra=(exponent_line(),))
    login(client)
    body = shortlist(client, STEEL).json()
    assert "syn:exponent" not in candidate_ids(body)
    assert body["total"] == 10  # 그 줄만 빠진다(표 전체를 거부하지 않는다).
    assert body["catalog"] == {"rejected": [{"id": "syn:exponent", "reason": "invalid_value_raw"}], "rejectedTotal": 1}
    # 후보가 없다는 답에도 실린다.
    none = shortlist(client, {"itemName": "출장 렌터카", "unit": "대"}, category=6).json()
    assert (none["status"], none["catalog"]["rejectedTotal"]) == ("no_candidates", 1)


def test_the_selector_returns_the_qualified_lines_in_code_point_order_with_two_queries(table: None) -> None:
    with CaptureQueriesContext(connection) as queries:
        everything = selectors.scope3_candidate_records(licenses=frozenset({"ok", "unverified", "disputed"}))
    # 쿼리 수는 낱줄의 수와 무관하게 둘이다(낱줄, 범주 연결).
    assert len(queries) == 2
    ids = [view.id for view in everything]
    assert len(ids) == 34
    # 자격 넷: 기체별 행·값 없는 행·범주 없는 행은 나오지 않는다.
    assert not set(ids) & NOT_CANDIDATES
    assert set(ids) >= DISPUTED
    # 차례는 id 의 코드 포인트 순이다(`-` 0x2D < `:` 0x3A, `_` 0x5F < `b` 0x62). DB 의 로캘 정렬이 아니다.
    assert ids == sorted(ids)
    assert ids[:3] == ["syn-d:cement-kg", "syn-d:pp-kg", "syn-d:truck-5t"]
    assert ids.index("syn:a_b") < ids.index("syn:ab")
    default = selectors.scope3_candidate_records(licenses=frozenset({"ok", "unverified"}))
    assert len(default) == 31
    assert {view.license_status for view in default} == {"ok"}
    steel = next(view for view in default if view.id == "syn:steel-kg")
    assert (steel.scope3_categories, steel.value_raw, steel.category_path) == ((1,), "2.5", ("합성 자재", "금속"))
    truck = next(view for view in default if view.id == "syn:truck")
    assert truck.scope3_categories == (4, 9)


def test_the_action_catalog_keeps_that_order(table: None) -> None:
    catalog = actions.scope3_catalog(frozenset({"ok", "unverified"}))
    ids = [factor.id for factor in catalog.all()]
    assert ids == sorted(ids)
    assert catalog.candidate_count == 31


def test_ties_are_broken_by_id_order_not_by_file_order(client: Client, table: None) -> None:
    """같은 이름의 두 계수(`syn:ab`, `syn:a_b`)는 점수가 같다. 파일에서는 ab 가 앞 줄이고(TS 의 골든이 그 차례다)
    서버는 id 의 코드 포인트 순이라 a_b 가 앞이다. DB 의 로캘 정렬에 맡겼다면 이 차례가 환경에 따라 달라진다."""
    golden = json.loads((G1_GOLDEN / "a-default" / "rows.json").read_text(encoding="utf-8"))
    by_file = next(row for row in golden if row["rowId"] == "g06")["shortlists"][0]
    assert by_file["shownIds"][:2] == ["syn:ab", "syn:a_b"]

    login(client)
    body = shortlist(client, {"itemName": "포장재", "unit": "kg"}, license=ALL_LICENSES).json()
    assert candidate_ids(body)[:2] == ["syn:a_b", "syn:ab"]
    scores = [entry["lexical"]["score"] for entry in body["evidence"][:2]]
    assert scores[0] == scores[1]
    # 차례 말고는 같다: 후보의 집합과 점수는 파일 순의 골든과 같다.
    assert body["total"] == by_file["total"]
    assert set(candidate_ids(body)) == set(by_file["shownIds"])


# ── 분류 ──────────────────────────────────────────────────────────────


@pytest.fixture
def mock(monkeypatch: pytest.MonkeyPatch) -> MockProvider:
    """이음매(`services.scope3_gateway`)에 모의 공급사 하나짜리 클라이언트를 꽂는다."""
    provider = MockProvider()
    client = mock_client(provider)
    monkeypatch.setattr(services, "scope3_gateway", lambda: client)
    return provider


def item(row_id: str, name: str, **more: Any) -> dict[str, Any]:
    return {"rowId": row_id, "itemName": name, "unit": "kg", **more}


def test_two_groups_are_two_calls(client: Client, tenants: None, mock: MockProvider) -> None:
    login(client)
    mock.enqueue_text(classification(1, ["steel"])).enqueue_text(classification(6))
    response = classify(client, [item("a", "합성 강판"), item("b", "출장 항공권")])
    assert response.status_code == 200
    body = response.json()
    assert (body["synthetic"], body["route"]) == (True, "mock")
    assert body["groups"] == [
        {
            "key": "합성강판|kg|",
            "rowIds": ["a"],
            "status": "classified",
            "classification": {
                "category": 1,
                "keywords": ["steel"],
                "confidence": "medium",
                "reason": "테스트 응답 (synthetic)",
            },
        },
        {
            "key": "출장항공권|kg|",
            "rowIds": ["b"],
            "status": "classified",
            "classification": {
                "category": 6,
                "keywords": [],
                "confidence": "medium",
                "reason": "테스트 응답 (synthetic)",
            },
        },
    ]
    assert len(mock.calls) == 2
    usage = body["usage"]
    assert (usage["calls"], usage["attempts"]) == (2, 2)
    assert list(usage["byPrompt"]) == ["inventory/scope3-classify@1"]


def test_rows_that_differ_only_in_notation_are_one_group_and_one_call(
    client: Client, tenants: None, mock: MockProvider
) -> None:
    login(client)
    mock.enqueue_text(classification(1))
    rows = [item("a", "A4 용지 80g"), item("b", "a4용지 80G"), item("c", "Ａ４용지(80g)", unit="KG")]
    body = classify(client, rows).json()
    assert [(group["key"], group["rowIds"]) for group in body["groups"]] == [("a4용지80g|kg|", ["a", "b", "c"])]
    assert len(mock.calls) == 1
    assert body["usage"]["calls"] == 1


def test_an_answer_off_schema_is_a_failed_group_with_status_200(
    client: Client, tenants: None, mock: MockProvider
) -> None:
    login(client)
    for _ in range(3):
        mock.enqueue_text(classification(5))
    response = classify(client, [item("a", "합성 강판")])
    assert response.status_code == 200
    [group] = response.json()["groups"]
    assert (group["status"], group["llm"]["kind"]) == ("classification_failed", "schema_mismatch")
    assert "classification" not in group
    assert response.json()["usage"]["attempts"] == 3


def test_category_other_is_passed_through_as_classified(client: Client, tenants: None, mock: MockProvider) -> None:
    login(client)
    mock.enqueue_text(classification("other"))
    [group] = classify(client, [item("a", "폐기물 처리")]).json()["groups"]
    assert (group["status"], group["classification"]["category"]) == ("classified", "other")


def test_more_than_twenty_groups_is_413_and_nothing_is_called(
    client: Client, tenants: None, mock: MockProvider
) -> None:
    login(client)
    rows = [item(str(index), f"품목 {index}") for index in range(21)]
    assert error_of(classify(client, rows)) == (413, "TOO_MANY_GROUPS")
    assert mock.calls == []
    # 스무 묶음은 된다. 행이 스물을 넘어도 묶음이 스물이면 된다.
    for _ in range(20):
        mock.enqueue_text(classification(1))
    twenty = [*rows[:20], item("dup", "품목 0")]
    assert len(classify(client, twenty).json()["groups"]) == 20


def test_more_than_1000_rows_is_413_before_grouping_and_nothing_is_called(
    client: Client, tenants: None, mock: MockProvider
) -> None:
    login(client)
    # 품목이 전부 같아 묶음은 하나다: 걸리는 것은 묶음의 상한이 아니라 행의 상한이다.
    rows = [item(str(index), "합성 강판") for index in range(1001)]
    over = classify(client, rows)
    assert error_of(over) == (413, "TOO_MANY_ROWS")
    assert set(over.json()) == {"error"}
    assert mock.calls == []
    # 1,000행은 행의 상한에 걸리지 않는다(묶음 하나, 호출 한 번).
    mock.enqueue_text(classification(1))
    at_limit = classify(client, rows[:1000])
    assert at_limit.status_code == 200
    assert [len(group["rowIds"]) for group in at_limit.json()["groups"]] == [1000]
    assert len(mock.calls) == 1


def test_duplicate_row_ids_are_400(client: Client, tenants: None, mock: MockProvider) -> None:
    login(client)
    assert error_of(classify(client, [item("a", "x1"), item("a", "x2")])) == (400, "DUPLICATE_ROW_ID")
    assert mock.calls == []


def test_quantities_and_amounts_do_not_reach_the_prompt(client: Client, tenants: None, mock: MockProvider) -> None:
    login(client)
    mock.enqueue_text(classification(4))
    moved = {"mode": "트럭", "origin": "부산", "destination": "평택", "weightKg": "98765", "distanceKm": "43210"}
    row = item("a", "원자재 운송 80g", quantity="13579", amount="24680000", currency="KRW", transport=moved)
    assert classify(client, [row]).status_code == 200
    [sent] = user_texts(mock)
    for number in ("98765", "43210", "13579", "24680000"):
        assert number not in sent
    expected = '{"item_name":"원자재 운송 80g","unit":"kg","currency":"KRW",'
    assert sent == f'ITEM_JSON: {expected}"transport":{{"origin":"부산","destination":"평택","mode":"트럭"}}}}'


def test_without_the_seam_swap_classify_is_503_llm_not_configured(client: Client, tenants: None) -> None:
    """떠 있는 서버와 같다: 프로세스의 클라이언트에는 경로 `mock` 이 없다. 실제 공급사를 부르는 길이 없다."""
    login(client)
    response = classify(client, [item("a", "합성 강판")])
    assert error_of(response) == (503, "LLM_NOT_CONFIGURED")
    body = response.json()
    assert set(body) == {"error"}
    assert set(body["error"]) == {"code", "message", "fields", "legacyCode"}
    assert body["error"]["message"] == "생성 모델 경로 mock 가 이 서버에 준비되어 있지 않다"


def test_classify_needs_a_session_and_rejects_unknown_fields(client: Client, tenants: None, mock: MockProvider) -> None:
    assert error_of(classify(client, [item("a", "합성 강판")])) == (401, "NO_SESSION")
    assert login(client, role="viewer")["role"] == "viewer"
    for rows in (
        [item("a", "x", route="light")],
        [item("a", "x", quantity=3)],
        [item("a", "x", quantity=None)],
        [{"itemName": "x"}],
        [item("", "x")],
    ):
        assert error_of(classify(client, rows)) == (422, "VALIDATION_ERROR"), rows
    assert mock.calls == []
    # 여기부터는 editor 다(쿠키 세션의 역할은 권한에 쓰지 않는다 — 가2. 분류 칸은 고객사 사용자).
    login(client)
    # 빈 목록은 부를 것이 없다.
    assert classify(client, []).json()["groups"] == []
    mock.enqueue_text(classification(1))
    assert classify(client, [item("a", "합성 강판")]).status_code == 200


# ── 분류: 권한(고객사 사용자. 결정 MARC-ENT-276 의 2) ─────────────────
# 쿠키 세션은 역할과 무관하게 고객사 사용자다(가2 — viewer 도 분류한다). 막힘은 칸을 운영 관리자 몫으로 옮겨 잰다.


def test_a_customer_cannot_classify_when_the_cell_is_operator_only_and_nothing_is_called(
    client: Client, tenants: None, mock: MockProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    assert login(client, role="viewer")["role"] == "viewer"
    monkeypatch.setitem(OPERATION_POLICY, "inventory_scope3_classify", OPERATOR)
    response = classify(client, [item("a", "합성 강판")])
    assert error_of(response) == (403, "FORBIDDEN")
    assert response.json()["error"]["message"] == "이 일은 운영 관리자만 한다"
    # 빈 목록도 막힌다(권한이 먼저다).
    assert error_of(classify(client, [])) == (403, "FORBIDDEN")
    assert mock.calls == []
    monkeypatch.setitem(OPERATION_POLICY, "inventory_scope3_classify", CLASSIFY_AS_IS)
    mock.enqueue_text(classification(1))
    assert classify(client, [item("a", "합성 강판")]).status_code == 200  # 분모: 옮기기 전에는 viewer 세션도 분류한다


def test_the_role_is_checked_before_the_row_limit(
    client: Client, tenants: None, mock: MockProvider, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [item(str(index), "합성 강판") for index in range(1001)]
    assert login(client, role="viewer")["role"] == "viewer"
    monkeypatch.setitem(OPERATION_POLICY, "inventory_scope3_classify", OPERATOR)
    assert error_of(classify(client, rows)) == (403, "FORBIDDEN")
    monkeypatch.setitem(OPERATION_POLICY, "inventory_scope3_classify", CLASSIFY_AS_IS)
    assert error_of(classify(client, rows)) == (413, "TOO_MANY_ROWS")
    assert mock.calls == []


def test_an_admin_can_classify(client: Client, tenants: None, mock: MockProvider) -> None:
    assert login(client, role="admin")["role"] == "admin"
    mock.enqueue_text(classification(1))
    assert classify(client, [item("a", "합성 강판")]).status_code == 200
    assert len(mock.calls) == 1


# ── Action: 기준정보를 읽어 추리기에 넘긴다 ───────────────────────────


def test_the_action_reads_reference_once_and_hands_the_catalog_to_the_service(
    table: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    handed: list[dict[str, Any]] = []

    def spy(**kwargs: Any) -> dict[str, object]:
        handed.append(kwargs)
        return {"status": "spied"}

    monkeypatch.setattr(services, "scope3_shortlist_output", spy)
    with CaptureQueriesContext(connection) as queries:
        output = actions.scope3_shortlist_output(
            row=STEEL, category=1, keywords=None, basis=None, method=None, bigrams=None, size=None, license_text=None
        )
    assert output == {"status": "spied"}
    # 기준정보는 한 번 읽는다(쿼리 둘: 낱줄, 범주 연결). Service 는 읽지 않고 받은 카탈로그로 추린다.
    assert len(queries) == 2
    [call] = handed
    assert set(call) == {"row", "category", "keywords", "basis", "method", "bigrams", "size", "catalog"}
    assert call["catalog"].candidate_count == 31
    assert (call["row"], call["category"]) == (STEEL, 1)


def test_an_unknown_license_is_rejected_before_any_query(table: None) -> None:
    with CaptureQueriesContext(connection) as queries, pytest.raises(ApplicationError) as caught:
        actions.scope3_shortlist_output(
            row=STEEL, category=1, keywords=None, basis=None, method=None, bigrams=None, size=None, license_text="nope"
        )
    assert caught.value.code == "invalid_license"
    assert len(queries) == 0


def test_the_service_no_longer_knows_reference() -> None:
    assert not hasattr(services, "scope3_catalog")
    assert not hasattr(services, "selectors")
