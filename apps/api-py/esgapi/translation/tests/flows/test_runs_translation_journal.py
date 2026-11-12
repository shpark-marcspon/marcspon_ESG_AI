# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""T5(MARC-ISSUE-268 의 1, 밴드 TRR1 — 닫는 시험): 지어낸 100쪽을 진짜 실행기로 돌리며 시도 경계를 여럿 넘긴다. 호출
기록은 DB 싱크(usage_by_run 이 실행의 지출을 읽는 바닥 — memory 싱크면 0 이라 빨개질 수 없다), 모의 사용량엔 값이
매겨진다(가상 모델 mock-synthetic 의 단가). 시도 사이 같은 호출 0(공급사 호출 합 = 한 시도로 돈 실행의 합)·done·
실행의 Σ cost_usd ≤ max_usd. 소프트 제한이 호출 안에서 나면 쪽 오류가 아니라 RunDeferred 이고 다음 시도가 잇는다(T6).

★ 시계 둘을 흘린다: 실행기의 마감(tasks.monotonic — 시도 시작 + 240 − 60)과 일지의 체크포인트 간격
  (call_journal.monotonic, 20초). 일지 시계를 부를 때마다 3초 — 체크포인트는 약 7호출마다, 시도는 약 60호출에서
  협조 마감으로 접힌다. 실행 시도 상한(max_attempts 3)보다 많은 시도를 넘어 이어 간다(★③ — 진행한 시도는 세지 않음).
★ 공급사: 끼움 mock 그대로(경로 mock) — context.build_client 의 make 가 `mock` 에 늘 답하는 모의 공급사를 준다.
"""

import contextlib
import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from functools import partial
from typing import Any, cast

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.flows.binding import BINDINGS
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sink_db import DbSink
from esgapi.core.llm.types import Completed, ProviderRequest, ProviderResponse, Usage
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.service.selectors import llm_usage
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.tests.flows.support import options
from esgapi.translation.tests.flows.test_runs_translation import RetryAsked, new_run
from esgapi.translation.tests.tools.budget_support import worst
from esgapi.translation.tools import call_journal
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
USAGE = Usage(input_tokens=1_000, output_tokens=500, cache_read_tokens=0, cache_write_tokens=0)
PARA = "가상기업은 지속가능한 경영을 위해 위험과 기회를 점검하고 이해관계자와 소통합니다. "
EN = "The virtual company reviews its risks and opportunities. "


def hundred_pages(pages: int = 100) -> str:
    """지어낸 100쪽(쪽당 국문 약 1,300자 — 쪽마다 머리가 달라 요청 열쇠가 겹치지 않는다)."""
    return "\n".join(f"[PAGE {n}]\n[BLOCK 1]\n가상 {n}쪽\n" + (PARA * 40)[:1300] for n in range(1, pages + 1))


def answer(request: ProviderRequest) -> ProviderResponse:
    """검수는 이슈 0, 그 밖은 영문 2,000자(값 매긴 사용량 — 가상 모델 단가)."""
    if "".join(s.text for s in request.system) == prompts.QA_SYSTEM_PROMPT:
        return Completed(text="[]", usage=USAGE)
    return Completed(text="[BLOCK 1]\n" + (EN * 100)[:2000], usage=USAGE)


@dataclass
class Clock:
    """실행기의 시계(now 그대로)와 일지의 시계(부를 때마다 step 초씩 간다)."""

    now: float = 0.0
    step: float = 3.0

    def tasks(self) -> float:
        return self.now

    def journal(self) -> float:
        self.now += self.step
        return self.now


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    mock: MockProvider = field(default_factory=lambda: MockProvider("mock"))
    clock: Clock = field(default_factory=Clock)
    keys: list[str] = field(default_factory=lambda: [])

    def retry(self, **kwargs: Any) -> RetryAsked:
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=4_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", made.clock.tasks)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(call_journal, "monotonic", made.clock.journal)
    monkeypatch.setattr(context, "call_sink", DbSink)
    return made


def scripted(
    monkeypatch: pytest.MonkeyPatch, world: World, reply: Callable[[ProviderRequest], ProviderResponse]
) -> None:
    """경로 mock 의 공급사가 늘 답한다(부를 때마다 하나 더 심는다). 요청 열쇠를 모은다."""

    def recorded(request: ProviderRequest) -> ProviderResponse:
        body = json.dumps(request.to_json(), ensure_ascii=False, sort_keys=True).encode()
        world.keys.append(hashlib.sha256(body).hexdigest())
        world.mock.enqueue(recorded)
        return reply(request)

    world.mock.enqueue(recorded)

    def make(name: str, **kwargs: Any) -> Any:
        return world.mock if name == "mock" else llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))


def run_until_done(world: World, run_id: int, limit: int = 60) -> int:
    """끝날 때까지 시도를 거듭한다 → 시도 수."""
    for n in range(1, limit + 1):
        with contextlib.suppress(RetryAsked):
            tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))
        found = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
        assert found is not None
        if found.status in ("done", "failed"):
            return n
    raise AssertionError(f"{limit} 시도에 끝나지 않았다")


def spent(world: World, run_id: int) -> float:
    found = llm_usage.usage_by_run(company_id=world.company_a, run_ids=frozenset({run_id})).get(run_id)
    return 0.0 if found is None else float(found.cost_usd)


def result_of(world: World, run_id: int) -> dict[str, Any]:
    rows = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    (found,) = [r for r in rows if r.schema_version == "translation.result@1"]
    assert isinstance(found.body, dict)
    return found.body  # pyright: ignore[reportReturnType]


def test_t5_a_hundred_page_run_crosses_attempts_without_calling_twice(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world, answer)
    text = hundred_pages().encode()
    binding = BINDINGS.get(colab.FLOW_ID)
    monkeypatch.setattr(binding, "max_usd", lambda: 50.0)
    run_id = new_run(client, world, options(), content=text)  # type: ignore[arg-type]
    attempts = run_until_done(world, run_id)
    run = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert run is not None and (run.status, run.error_code) == ("done", None)
    assert attempts > SETTINGS.max_attempts  # ★③ 진행한 시도는 상한에 세지 않는다
    body = result_of(world, run_id)
    assert body["status"] == "done"
    assert len(world.keys) == len(set(world.keys))  # 시도 사이 같은 요청 0
    calls = len(world.keys)
    # 같은 문서를 한 시도로(시계를 멈춰) 돌린 실행의 공급사 호출 수와 같다
    world.keys.clear()
    world.clock.step = 0.0
    single = new_run(client, world, options(), content=text)  # type: ignore[arg-type]
    assert run_until_done(world, single) == 1
    assert len(world.keys) == calls
    assert json.dumps(result_of(world, single)["variants"], sort_keys=True) == json.dumps(
        body["variants"], sort_keys=True
    )
    assert 0 < spent(world, run_id) <= 50.0
    steps = {s.name: s for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id)}
    done = steps["translate"].done
    assert done is not None and calls - 10 <= done <= calls  # 마지막 체크포인트 뒤 호출(7개 안팎)은 단계 끝이 덮는다
    print(f"\nT5 pages=100 attempts={attempts} calls={calls} done={done} spent_usd={spent(world, run_id):.4f}")


def test_t6_a_soft_limit_inside_a_call_defers_and_the_next_attempt_resumes(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen = [0]

    def reply(request: ProviderRequest) -> ProviderResponse:
        seen[0] += 1
        if seen[0] == 30:
            raise SoftTimeLimitExceeded("가짜 소프트 제한")
        return answer(request)

    scripted(monkeypatch, world, reply)
    run_id = new_run(client, world, options(), content=hundred_pages(10).encode())  # type: ignore[arg-type]
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))
    first = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert first is not None and (first.status, first.error_code) == ("queued", None)  # RunDeferred(쪽 오류 아님)
    assert seen[0] == 30  # 그 뒤 공급사 호출 0
    run_until_done(world, run_id)
    body = result_of(world, run_id)
    statuses = {f["status"] for v in body["variants"] for f in v["fragments"]}
    assert statuses == {"translated"}


def one_attempt(world: World, run_id: int) -> run_selectors.Run:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))
    found = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert found is not None
    return found


@pytest.mark.parametrize(("delta", "expect"), [(-1e-6, "over_budget"), (1e-6, "done")])
def test_t5_the_db_spend_of_earlier_attempts_counts_against_the_cap(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch, delta: float, expect: str
) -> None:
    """검증 B1(밴드 TRE1 에서 새 뜻으로): 실행기·DB 싱크로 첫 시도를 협조 마감으로 접은 뒤 상한을 건다. −ε 갈래:
    상한 = DB 지출 − ε → 이은 시도가 over_budget·공급사 0(지출 ≥ 상한). +ε 갈래: 상한 = DB 지출 + (이은 시도들의 모의
    비용 합 + 마지막 호출 여유) + ε → done 이고 이은 시도가 실제로 공급사를 부른다 · DB Σ cost_usd ≤ 상한. 이은 시도들의
    비용은 같은 문서를 한 번에 끝까지 돌린 기준 실행의 DB 지출에서 뺀다(같은 답이면 같은 호출 열). 지출은 apps.py 가
    꽂은 _spent_usd(core usage_by_run)가 읽는다 — 이 길을 지나는 시험(그것을 늘 0 으로 심으면 −ε 갈래가 done)."""
    scripted(monkeypatch, world, answer)
    binding = BINDINGS.get(colab.FLOW_ID)
    monkeypatch.setattr(binding, "max_usd", lambda: 50.0)
    content = hundred_pages(30).encode()
    reference = new_run(client, world, options(), content=content)  # type: ignore[arg-type]
    run_until_done(world, reference)
    assert result_of(world, reference)["status"] == "done"
    whole = spent(world, reference)
    run_id = new_run(client, world, options(), content=content)  # type: ignore[arg-type]
    assert one_attempt(world, run_id).status == "queued"  # 분모: 첫 시도가 협조 마감으로 접혔다
    steps = {s.name: s for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id)}
    prepared = steps["prepare"].data
    assert prepared is not None and steps["translate"].partial is not None
    already = spent(world, run_id)
    assert 0 < already < whole  # 분모: 첫 시도가 DB 장부에 값 매긴 지출을 남겼고 남은 호출이 있다
    per_site = cast("dict[str, dict[str, float]]", prepared["perSite"])
    total = float(cast("float", prepared["totalEstimateUsd"]))
    guard = total - sum(v["ratio"] * v["estimateUsd"] for v in per_site.values())
    limit = already + delta if expect == "over_budget" else whole + guard + delta
    assert limit < total  # 실행 중 상한 = min(max_usd, 위끝) 의 max_usd 쪽이 문다
    monkeypatch.setattr(binding, "max_usd", lambda: limit)
    before = len(world.keys)
    run_until_done(world, run_id)
    body = result_of(world, run_id)
    if expect == "over_budget":
        assert (body["status"], body["rejection"]["kind"]) == ("rejected", "over_budget")
        assert len(world.keys) == before  # 이은 시도의 공급사 0
    else:
        assert body["status"] == "done" and len(world.keys) > before
        assert spent(world, run_id) <= limit


def test_s2_the_db_spend_of_a_worst_case_run_stays_within_the_estimate(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """S2(밴드 TRE1): 최악 사용량 공급사(출력 상한 · 어림 입력 × 2)로 지어낸 30쪽이 협조 마감으로 시도 경계를 넘어도
    끝(done | over_budget)에서 DB Σ cost_usd ≤ prepare 위끝 — 실행 중 상한 min(max_usd, 위끝)이 시도를 넘어 문다
    (max_usd 는 위끝보다 커서 min 을 지우면 위끝을 넘는다 — P1)."""
    scripted(monkeypatch, world, worst(answer))
    binding = BINDINGS.get(colab.FLOW_ID)
    monkeypatch.setattr(binding, "max_usd", lambda: 10_000.0)
    run_id = new_run(client, world, options(), content=hundred_pages(30).encode())  # type: ignore[arg-type]
    attempts = run_until_done(world, run_id)
    steps = {s.name: s for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id)}
    prepared = steps["prepare"].data
    assert prepared is not None and prepared["rejection"] is None
    body = result_of(world, run_id)
    assert body["status"] == "done" or body["rejection"]["kind"] == "over_budget"
    assert attempts >= 2 and len(world.keys) > 0  # 분모: 시도 경계를 넘었고 공급사를 불렀다
    assert spent(world, run_id) <= float(cast("float", prepared["totalEstimateUsd"]))
