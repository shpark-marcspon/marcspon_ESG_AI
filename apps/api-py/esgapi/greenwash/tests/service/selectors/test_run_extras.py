# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportAttributeAccessIssue=false
"""운영 관리자 실행 기록의 그린워싱 몫(service/selectors/run_extras.py — AD4S)을 잰다.

순수: AI 설정 판 읽기 다섯 꼴(m5) · 결과 꼴 글자가 contracts/shapes.py 의 SHAPE 와 같다 · 검토 상태 셋이 runs 의
operator.REVIEW_STATES 와 같다(M4).
업무(진짜 DB): 술어 일치 다섯 — review_shown(파이썬, checks.py 가 부름)과 reviewable_q(실행 행 Q, runs 의 목록이 부름)가
같은 답 · 검토 상태 셋 · 회사 경계(남의 회사 검토 행이 같은 run_id 를 가리켜도 안 섞임 — M2).
무효 조건: reviewable_q 는 결과 본문이 dict 인지 못 본다(본문은 꼴 검사를 지나 저장되니 dict 아닌 결과는 없다고 본다 —
run_extras.py 머리말).
"""

from datetime import UTC, datetime
from typing import Any

import pytest
from django.apps import apps

from esgapi.greenwash.contracts.shapes import SHAPE
from esgapi.greenwash.models import REVIEW_STATES, GreenwashReviewRow
from esgapi.greenwash.service.selectors.run_extras import RESULT_SHAPE, RunReviewSource, review_shown, reviewable_q
from esgapi.greenwash.tests.service.seed import example, run
from esgapi.runs.service.selectors import operator

SOURCE = RunReviewSource()
DEFAULT_NAME = "colab-2026-01-15-v1"


# ── 순수 ─────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("versions", "expected"),
    [
        ({"aiSetting": "v3", "aiSettingId": 12}, (12, "v3")),  # 저장 판
        ({"aiSetting": DEFAULT_NAME, "aiSettingId": None}, (None, DEFAULT_NAME)),  # 기본 판(binding_e0 — id None)
        ({"aiSetting": DEFAULT_NAME}, (None, DEFAULT_NAME)),  # id 열쇠 없음(G2c2 앞의 실행)
        ({"aiSettingId": 12}, None),  # 이름 없음
        ({"aiSetting": 3, "aiSettingId": 12}, None),  # 이름이 글자가 아님
        ({"aiSetting": "v3", "aiSettingId": "12"}, None),  # id 가 글자
        ({"aiSetting": "v3", "aiSettingId": True}, None),  # id 가 bool
        ({}, None),
    ],
    ids=["saved", "default", "no_id_key", "no_name", "name_not_text", "id_text", "id_bool", "empty"],
)
def test_the_ai_setting_is_read_from_the_versions(versions: dict[str, object], expected: object) -> None:
    assert SOURCE.ai_setting(versions) == expected


def test_the_result_shape_and_the_review_states_match_their_sources() -> None:
    assert RESULT_SHAPE == SHAPE  # 글자로 베낀 것(머리말)
    assert REVIEW_STATES == operator.REVIEW_STATES  # runs 는 그린워싱을 import 하지 않아 값을 따로 둔다(M4)


# ── 업무 ─────────────────────────────────────────────────────────────


def reviewable_ids(company_id: int) -> set[int]:
    rows = apps.get_model("runs", "RunRow").for_company(company_id)
    return set(rows.filter(reviewable_q()).values_list("id", flat=True))


def without_dry_run_key() -> dict[str, Any]:
    body = example("result-normal")
    del body["dryRun"]
    return body


@pytest.mark.django_db
def test_the_two_predicates_agree(companies: tuple[int, int]) -> None:
    """다섯 꼴: done+결과 dryRun null · done+결과 dryRun 키 없음 · done+dryRun 값 · done+결과 없음 · failed+결과."""
    a, _ = companies
    normal = example("result-normal")
    cases: dict[str, tuple[str, dict[str, Any] | None, bool]] = {
        "dry_run_null": ("done", normal, True),
        "dry_run_missing": ("done", without_dry_run_key(), True),
        "dry_run_value": ("done", example("result-dry-run"), False),
        "no_result": ("done", None, False),
        "failed": ("failed", normal, False),
    }
    ids = {name: run(a, status=status, result=result) for name, (status, result, _) in cases.items()}
    by_q = reviewable_ids(a)
    for name, (status, result, shown) in cases.items():
        assert review_shown(status, result) is shown, name
        assert (ids[name] in by_q) is shown, name
    assert len(by_q) == 2  # 분모: 둘은 맞는다


@pytest.mark.django_db
def test_another_shapes_result_is_not_reviewable(companies: tuple[int, int]) -> None:
    a, _ = companies
    run_id = run(a, result={**example("result-normal"), "schemaVersion": "greenwash.other@1"})
    assert run_id not in reviewable_ids(a)
    assert run(a, result=example("result-normal")) in reviewable_ids(a)  # 분모


def reviewed(company_id: int, run_id: int, state: str) -> None:
    confirmed = state == "confirmed"
    GreenwashReviewRow.for_company(company_id).create(
        company_id=company_id,
        run_id=run_id,
        state=state,
        confirmed_at=datetime(2026, 10, 1, tzinfo=UTC) if confirmed else None,
        confirmed_by_user_id=1 if confirmed else None,
    )


@pytest.mark.django_db
def test_states_and_run_ids_in_read_the_three_states(companies: tuple[int, int]) -> None:
    a, _ = companies
    runs = {state: run(a, result=example("result-normal")) for state in REVIEW_STATES}
    untouched = run(a, result=example("result-normal"))
    for state, run_id in runs.items():
        reviewed(a, run_id, state)
    assert SOURCE.states(a, [*runs.values(), untouched]) == {run_id: state for state, run_id in runs.items()}
    for state, run_id in runs.items():
        assert {row["run_id"] for row in SOURCE.run_ids_in(a, {state})} == {run_id}
    assert {row["run_id"] for row in SOURCE.run_ids_in(a, {"in_review", "confirmed"})} == {
        runs["in_review"],
        runs["confirmed"],
    }


@pytest.mark.django_db
def test_another_companys_review_row_is_not_seen(companies: tuple[int, int]) -> None:
    """M2: 회사 A 의 검토 행이 run_id = B 의 실행을 가리킨다(run_id 는 외래 키가 아니다). B 로 읽으면 0."""
    a, b = companies
    r_b = run(b, result=example("result-normal"))
    reviewed(a, r_b, "confirmed")  # 교차 행
    assert SOURCE.states(b, [r_b]) == {}
    assert list(SOURCE.run_ids_in(b, {"confirmed"})) == []
    # 분모: A 로 읽으면 그 행이 보이고, B 에 행을 심으면 B 로 보인다
    assert SOURCE.states(a, [r_b]) == {r_b: "confirmed"}
    reviewed(b, r_b, "in_review")
    assert SOURCE.states(b, [r_b]) == {r_b: "in_review"}
    assert {row["run_id"] for row in SOURCE.run_ids_in(b, {"in_review"})} == {r_b}
