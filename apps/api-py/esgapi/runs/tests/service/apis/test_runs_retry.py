"""고른 구획 다시 요청 칸(`RunIn.retrySegments`)과 구획 목록(`GET /runs/{run_id}/segments`)의 API 몫(RM1c ③ — T14·T15).
업무 층.

흐름·끼움은 RM1c ① 시험의 틀(`test_executor_carry` 의 bench — `probe.segmented@1` 과 판만 바꾼 `@2`, 시험 레지스트리
에만, 제품 흐름 등록 0)을 쓰고, 경로의 REGISTRY 도 같은 시험 레지스트리로 바꿔 끼운다. 앞 실행은 가짜 실행기로 끝까지
돌리거나(done) 행을 손으로 쓴다. 값은 지어낸 것이다. 회사 격리는 tests/security/test_runs.py 가 잰다.
"""

import json
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from time import perf_counter
from typing import Any

import pytest
from django.test import Client

from esgapi.core.flows.types import segment_key_fields, segment_key_sha256
from esgapi.runs.models import RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.apis import runs as apis
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.tests.test_executor_carry import Bench, done_run_with_failures, failed_run, shas
from esgapi.runs.tests.test_executor_carry import make_bench as make_bench  # 픽스처(bench 가 부른다)
from esgapi.runs.tests.test_executor_segments import FAIL_RUN, PLAIN, SEGMENTED, key_at, new_run, run_row
from tests.support.errors import error_of
from tests.support.http import login

pytestmark = pytest.mark.django_db

IDEMPOTENCY_KEY = "0b0e6c1e-1111-4222-8333-444455556666"
T0 = datetime(2026, 11, 10, 1, 0, tzinfo=UTC)


@pytest.fixture
def bench(
    make_bench: Callable[[int], Bench],
    monkeypatch: pytest.MonkeyPatch,
    client: Client,
) -> Bench:
    made = make_bench(1)
    from esgapi.runs.service.actions import runs as actions

    monkeypatch.setattr(apis, "REGISTRY", actions.REGISTRY)  # 경로의 펼침 이름도 시험 레지스트리에서
    login(client)
    assert client.get("/api/me").json()["companyId"] == made.company_id  # 분모: 세션 회사 = bench 회사
    return made


def document_of(bench: Bench, run_id: int) -> int:
    document = run_row(bench.par, run_id).document_id
    assert document is not None
    return document


def body(bench: Bench, previous: int, keys: list[str] | tuple[str, ...], **extra: Any) -> dict[str, Any]:
    return {
        "module": "probe",
        "flowId": SEGMENTED.id,
        "documentId": document_of(bench, previous),
        "retrySegments": {"fromRunId": previous, "step": "spread", "keys": list(keys)},
        **extra,
    }


def post(client: Client, data: dict[str, Any], *, key: str | None = None) -> Any:
    headers = {} if key is None else {"Idempotency-Key": key}
    return client.post("/api/runs", data=data, content_type="application/json", headers=headers)


def counts(bench: Bench) -> tuple[int, int, int]:
    company = bench.company_id
    return (
        RunRow.for_company(company).count(),
        RunStepRow.for_company(company).count(),
        RunSegmentRow.for_company(company).count(),
    )


# ── T14 만들기 ─────────────────────────────────────────────────────────


def test_a_retry_body_makes_a_new_run_with_only_the_chosen_segments_pending(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    response = post(client, body(bench, previous, shas(7, 3)))
    assert response.status_code == 201, response.content
    new = int(response.json()["id"])
    assert response.json()["status"] == "queued"
    assert run_row(bench.par, new).resumed_from_run_id == previous
    statuses = [s.status for s in RunSegmentRow.for_company(bench.company_id).filter(run_id=new).order_by("position")]
    assert statuses == ["done", "done", "pending", "done", "done", "done", "pending", "done", "done", "done"]
    assert client.get(f"/api/runs/{new}").json()["resumedFromRunId"] == previous  # RunOut 칸은 그대로(R12)


def test_each_retry_refusal_is_its_code_and_writes_nothing(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    failed = failed_run(bench, ["done", "failed"])
    before = counts(bench)
    failed_body = body(bench, failed, shas(2), flowId=FAIL_RUN.id)
    missing = body(bench, previous, shas(3))
    missing["retrySegments"]["fromRunId"] = 999_999  # 없는 앞 실행
    cases: list[tuple[dict[str, Any], tuple[int, str]]] = [
        (missing, (404, "NOT_FOUND")),
        (body(bench, previous, shas(3), resumeFromRunId=previous), (422, "RETRY_MISMATCH")),
        (body(bench, previous, shas(3), options={"pages": "2"}), (422, "RETRY_MISMATCH")),
        (failed_body, (409, "RETRY_NOT_DONE")),
        (body(bench, previous, shas(99)), (422, "RETRY_SEGMENTS_UNKNOWN")),
        (body(bench, previous, shas(3, 3)), (422, "RETRY_SEGMENTS_UNKNOWN")),
        (
            body(bench, previous, shas(3))
            | {"retrySegments": {"fromRunId": previous, "step": "prepare", "keys": list(shas(3))}},
            (422, "RETRY_SEGMENTS_UNKNOWN"),
        ),
    ]
    for data, expected in cases:
        assert error_of(post(client, data)) == expected, data
    bench.version[0] = {"probe": "v2"}  # 지금 끼움이 앞 옵션으로 짓는 판 ≠ 앞 판
    answer = post(client, body(bench, previous, shas(3)))
    assert error_of(answer) == (409, "RETRY_VERSION_CHANGED")
    assert "처음부터" in answer.json()["error"]["message"]
    assert counts(bench) == before


@pytest.mark.parametrize(
    "retry",
    [
        {"fromRunId": 1, "step": "spread", "keys": []},  # 빈 keys
        {"fromRunId": 1, "step": "spread", "keys": ["A" * 64]},  # 대문자
        {"fromRunId": 1, "step": "spread", "keys": ["a" * 63]},  # 짧음
        {"fromRunId": 1, "step": "s" * 101, "keys": ["a" * 64]},  # 단계 이름 101자
        {"fromRunId": True, "step": "spread", "keys": ["a" * 64]},  # 불리언 id
        {"fromRunId": 1, "step": "spread", "keys": ["a" * 64], "companyId": 1},  # 모르는 칸
        {"step": "spread", "keys": ["a" * 64]},  # fromRunId 없음
    ],
)
def test_a_malformed_retry_is_a_validation_error_before_anything(
    client: Client, bench: Bench, retry: dict[str, Any]
) -> None:
    previous = done_run_with_failures(bench)
    before = counts(bench)
    data = body(bench, previous, shas(3)) | {"retrySegments": retry}
    assert error_of(post(client, data)) == (422, "VALIDATION_ERROR")
    assert counts(bench) == before


def ten_thousand_done(bench: Bench, count: int) -> int:
    """구획 count 개가 전부 done 인 done 실행을 손으로 짓는다(prepare·spread·gather done)."""
    run_id = new_run(bench.par, SEGMENTED)
    company = bench.company_id
    RunRow.for_company(company).filter(pk=run_id).update(status="done", attempts=1, finished_at=T0)
    steps = RunStepRow.for_company(company).filter(run_id=run_id)
    steps.filter(name="prepare").update(status="done", data={"count": count}, started_at=T0, finished_at=T0)
    steps.filter(name__in=("spread", "gather")).update(status="done", data={"n": 0}, started_at=T0, finished_at=T0)
    rows: list[RunSegmentRow] = []
    for position in range(count):
        key = key_at(position + 1)
        rows.append(
            RunSegmentRow(
                company_id=company,
                run_id=run_id,
                step="spread",
                position=position,
                kind=key.kind,
                key=segment_key_fields(key),
                key_sha256=segment_key_sha256(key),
                status="done",
                attempts=1,
                data={"square": position},
                started_at=T0,
                finished_at=T0,
            )
        )
    RunSegmentRow.for_company(company).bulk_create(rows, batch_size=2000)
    return run_id


def test_ten_thousand_keys_fit_the_body_and_ten_thousand_and_one_do_not(client: Client, bench: Bench) -> None:
    """keys 상한 10,000(FanoutStep max_segments 상한 — D7): 10,000개 본문(≈0.67MB)은 본문 상한 안이라 201,
    10,001 은 꼴 검사 422. 10,000 구획 옮김 시간을 보고에 싣는다(§6)."""
    previous = ten_thousand_done(bench, 10_000)
    keys = [segment_key_sha256(key_at(n)) for n in range(1, 10_001)]
    data = body(bench, previous, keys)
    assert error_of(post(client, data | {"retrySegments": data["retrySegments"] | {"keys": [*keys, "f" * 64]}})) == (
        422,
        "VALIDATION_ERROR",
    )
    started = perf_counter()
    response = post(client, data)
    elapsed = perf_counter() - started
    assert response.status_code == 201, response.content
    new = int(response.json()["id"])
    assert RunSegmentRow.for_company(bench.company_id).filter(run_id=new, status="pending").count() == 10_000
    print(f"RM1c ③ 10,000 구획 고른 다시 만들기 {elapsed:.2f}s")


def test_the_same_idempotency_key_replays_and_a_reordered_key_list_is_409(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    first = post(client, body(bench, previous, shas(3, 7)), key=IDEMPOTENCY_KEY)
    assert first.status_code == 201
    before = counts(bench)
    again = post(client, body(bench, previous, shas(3, 7)), key=IDEMPOTENCY_KEY)
    assert (again.status_code, again.json()["id"]) == (201, first.json()["id"])
    assert error_of(post(client, body(bench, previous, shas(7, 3)), key=IDEMPOTENCY_KEY)) == (
        409,
        "IDEMPOTENCY_KEY_REUSED",
    )
    plain = {k: v for k, v in body(bench, previous, shas(3, 7)).items() if k != "retrySegments"}
    assert error_of(post(client, plain, key=IDEMPOTENCY_KEY)) == (409, "IDEMPOTENCY_KEY_REUSED")
    assert counts(bench) == before


def test_a_tuple_version_is_the_same_version_after_the_jsonb_round_trip(client: Client, bench: Bench) -> None:
    """645-1(GE1b T1): 끼움이 tuple 을 내도 앞 판(jsonb 왕복 — list)과 같은 판이면 201, 값이 다르면 409 그대로."""
    previous = done_run_with_failures(bench)
    RunRow.for_company(bench.company_id).filter(pk=previous).update(versions={"probe": ["v1", 2], "flow": SEGMENTED.id})
    bench.version[0] = {"probe": ("v1", 2)}
    made = post(client, body(bench, previous, shas(3)))
    assert made.status_code == 201, made.content
    assert run_row(bench.par, int(made.json()["id"])).versions == {"probe": ["v1", 2], "flow": SEGMENTED.id}
    bench.version[0] = {"probe": ("v1", 3)}
    assert error_of(post(client, body(bench, previous, shas(7)))) == (409, "RETRY_VERSION_CHANGED")


def test_json_shaped_versions_are_stored_as_built(client: Client, bench: Bench) -> None:
    """645-1(permits 7a-1): 이미 JSON 꼴인 판(1차 흐름의 꼴)은 정규화 앞뒤 같은 값 — 저장 값이 끼움이 지은 그대로."""
    built: dict[str, object] = {"probe": "v1", "n": 2, "nested": {"a": [1, None], "b": True}}
    bench.version[0] = built
    previous = done_run_with_failures(bench)
    plain = {k: v for k, v in body(bench, previous, shas(3)).items() if k != "retrySegments"}
    made = post(client, plain)
    assert made.status_code == 201, made.content
    stored = run_row(bench.par, int(made.json()["id"])).versions
    assert stored == {**built, "flow": SEGMENTED.id} == json.loads(json.dumps(stored))


# ── T15 목록 ───────────────────────────────────────────────────────────


def test_the_segment_list_pages_in_plan_order_without_data(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    response = client.get(f"/api/runs/{previous}/segments?step=spread&limit=4&offset=2")
    assert response.status_code == 200
    page = response.json()
    assert (page["count"], page["isNext"]) == (10, True)
    assert [line["position"] for line in page["results"]] == [2, 3, 4, 5]
    line = page["results"][0]
    assert set(line) == {
        "position",
        "keySha256",
        "key",
        "status",
        "attempts",
        "errorCode",
        "startedAt",
        "finishedAt",
    }  # data 0
    assert line["keySha256"] == segment_key_sha256(key_at(3))
    assert line["key"] == {"kind": "block", "span": "b3", "documentSha256": None, "parserVersion": "p1"}
    assert (line["status"], line["errorCode"], line["attempts"]) == ("failed", "step_error", 1)
    assert line["startedAt"].endswith("+09:00")  # 시각은 서울
    last = client.get(f"/api/runs/{previous}/segments?step=spread&limit=4&offset=8").json()
    assert ([x["position"] for x in last["results"]], last["isNext"]) == ([8, 9], False)
    default = client.get(f"/api/runs/{previous}/segments?step=spread").json()
    assert len(default["results"]) == 10  # 기본 limit 20


def test_the_status_filter_and_the_retry_keys_round_trip(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    failed = client.get(f"/api/runs/{previous}/segments?step=spread&status=failed").json()
    assert ([x["position"] for x in failed["results"]], failed["count"]) == ([2, 6], 2)
    keys = [x["keySha256"] for x in failed["results"]]
    assert post(client, body(bench, previous, keys)).status_code == 201  # 목록의 열쇠 = 다시 고를 열쇠(GE1b)


def test_a_carried_segment_shows_zero_attempts(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    new = int(post(client, body(bench, previous, shas(3))).json()["id"])
    lines = client.get(f"/api/runs/{new}/segments?step=spread").json()["results"]
    assert [(x["status"], x["attempts"]) for x in lines][:3] == [("done", 0), ("done", 0), ("pending", 0)]


def test_a_step_that_is_not_a_fanout_is_422_and_a_missing_step_is_422(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    assert error_of(client.get(f"/api/runs/{previous}/segments?step=prepare")) == (422, "NOT_A_FANOUT")
    assert error_of(client.get(f"/api/runs/{previous}/segments?step=nope")) == (422, "NOT_A_FANOUT")
    assert error_of(client.get(f"/api/runs/{previous}/segments")) == (422, "VALIDATION_ERROR")
    assert error_of(client.get(f"/api/runs/{previous}/segments?step=spread&limit=101")) == (422, "VALIDATION_ERROR")
    plain = new_run(bench.par, PLAIN)
    assert error_of(client.get(f"/api/runs/{plain}/segments?step=spread")) == (422, "NOT_A_FANOUT")


def test_a_missing_run_is_404_before_the_step_check(client: Client, bench: Bench) -> None:
    assert error_of(client.get("/api/runs/999999/segments?step=prepare")) == (404, "NOT_FOUND")


def test_before_planning_the_list_is_empty(client: Client, bench: Bench) -> None:
    run_id = new_run(bench.par, SEGMENTED)
    page = client.get(f"/api/runs/{run_id}/segments?step=spread").json()
    assert (page["count"], page["isNext"], page["results"]) == (0, False, [])


def test_the_selector_reads_only_the_company_rows(bench: Bench, companies: tuple[int, int]) -> None:
    previous = done_run_with_failures(bench)
    other = selectors.segment_page(
        company_id=companies[1], run_id=previous, step="spread", status=None, limit=20, offset=0
    )
    assert (other.count, other.lines) == (0, ())
    mine = selectors.segment_page(
        company_id=bench.company_id, run_id=previous, step="spread", status="done", limit=20, offset=0
    )
    assert mine.count == 8


def test_the_segment_times_are_the_row_times(client: Client, bench: Bench) -> None:
    previous = done_run_with_failures(bench)
    first = RunSegmentRow.for_company(bench.company_id).get(run_id=previous, position=0)
    line = client.get(f"/api/runs/{previous}/segments?step=spread&limit=1").json()["results"][0]
    assert datetime.fromisoformat(line["startedAt"]) == first.started_at
    assert datetime.fromisoformat(line["finishedAt"]) - datetime.fromisoformat(line["startedAt"]) >= timedelta(0)


def test_the_operator_gets_404_on_the_segments_of_another_modules_run(
    client: Client, bench: Bench, monkeypatch: pytest.MonkeyPatch
) -> None:
    """운영 관리자(작업 회사 = bench 회사)는 OPERATOR_RUN_MODULES 밖(probe)의 실행 구획 목록이 404 — step 검사 앞.
    분모: 고객사 사용자는 같은 실행의 목록을 200 으로 본다."""
    from django.urls import get_resolver

    from esgapi.core.auth import bearer as bearer_module
    from esgapi.runs.tests.service.apis.test_runs_operator import operator

    previous = done_run_with_failures(bench)
    get_resolver().url_patterns  # noqa: B018 — config.api(포트를 꽂는 자리)를 먼저 들인 뒤에 바꿔 끼운다
    monkeypatch.setattr(bearer_module, "_operator_company", lambda: bench.company_id)
    admin = Client()
    for query in ("?step=spread", "?step=prepare"):
        assert error_of(admin.get(f"/api/runs/{previous}/segments{query}", **operator())) == (404, "NOT_FOUND"), query
    assert client.get(f"/api/runs/{previous}/segments?step=spread").status_code == 200
