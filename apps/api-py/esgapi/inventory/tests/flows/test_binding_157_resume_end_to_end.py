# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""Scope 3 코랩 흐름(scope3.colab@157)이 진짜 DB·실행기에서 협조 마감으로 여러 번 끊겨도 저장된 자리에서 이어
done 에 닿는가(밴드 S3R1 T3, 업무 층 — 컨테이너).

    시계      실행기(tasks.monotonic)와 흐름 일지(scope3_journal_157.monotonic)가 같은 시계 객체를 본다. 시도마다
              execute_run 앞에서 0 으로 되돌리고, 모의 공급사가 실제 부름마다 D 초씩 늘린다. 협조 마감 = 240 − 60 = 180,
              soft = 240(넘은 뒤 들어온 부름은 soft limit 꼴)
    셈        C1 시트 한 장에 지은 품목 ROWS = 80 줄(규칙에 안 걸림) → 줄마다 실제 부름 하나 = CALLS 번.
              CALLS × D = 80 × 7 = 560s > 240 — 한 시도(180s 남짓)로는 못 끝나 시도 넷 꼴(어림 ⌈560 ÷ 180⌉ + 1)
    끝까지    시도를 되풀이(상한 = 기대 시도 수 × 3) → done · 결과 = 같은 입력의 run_flow 바로 · 공급사 총수 = 한 번
              돌기 · attempts = 끊긴 수 + 1 > max_attempts · stalled_attempts 0 · 단계 열다섯 done · 카테고리 단계
              data 는 일지 꼴만
    반대(N2)  시도마다 첫 실제 부름에서 soft limit → 나가기 전 체크포인트에 새 칸이 없어 진행 0 → stalled 가 쌓여
              failed·attempts_exhausted, stalled_attempts = max_attempts(claims 셈 뜻 그대로)
★ soft limit 은 Celery 의 진짜 클래스(실행기 _transient 가 isinstance 로 본다 — 번역 test_runs_translation_journal 꼴).
★ 공급사: context.build_client 의 make 를 갈아 openai 에 모의 공급사(실제 공급사·키·네트워크 0). 계수 책은 포트를
  지어낸 바이트로 갈아 끼운다. 스위치는 시험 안에서만 켠다. 템플릿·책·답은 전부 지어낸 것이다.
"""

import contextlib
import dataclasses
import hashlib
import json
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import pytest
from celery.exceptions import SoftTimeLimitExceeded
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.flows.run import run_flow
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderRequest, ProviderResponse, Tags
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.inventory.engines.scope3.colab_157.ports import NoGeocoder
from esgapi.inventory.flows import binding_157
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.flows import scope3_journal_157 as journal
from esgapi.inventory.service.utils import scope3_files
from esgapi.inventory.tests.engines.scope3.colab_157.support import sheet, workbook, xlsx_bytes
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_HEAD, C1_SUB
from esgapi.inventory.tests.scope3_llm_support import user_text
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
ROWS = 80
CALLS = ROWS  # 줄마다 실제 부름 하나(BASE 꼴 run_flow 바로로 잰 값 — direct 가 대 본다)
D = 7.0  # 지어낸 한 호출 시간(초) — 체크포인트(2 호출 = 14s) < 20s
SOFT = 240.0
EXPECTED_ATTEMPTS = int(CALLS * D // (SOFT - 60)) + 2
TEMPLATE = xlsx_bytes(
    workbook(
        sheet(
            "C1_구매품서비스",
            {
                4: C1_HEAD,
                5: C1_SUB,
                **{6 + n: ["가상국", "가상사업장", None, f"가상 물품{n}호", None, 9100 + n] for n in range(ROWS)},
            },
        ),
        sheet("표지", {1: ["가상"]}),
    )
)
BOOK = xlsx_bytes(workbook(sheet("구매_USEPA", BOOK_ROWS)))


class Clock:
    """실행기·일지가 같이 보는 시계. 공급사만 늘린다."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class Script(MockProvider):
    """openai 자리의 모의 공급사: 부름이 들어올 때 세고 시계를 D 만큼 늘린다. soft 를 넘었거나 soft_first 의 시도 첫
    부름이면 soft limit 꼴."""

    def __init__(self, clock: Clock, *, soft_first: bool = False) -> None:
        super().__init__("openai")
        self.clock = clock
        self.real = 0
        self.soft_first = soft_first
        self.attempt_calls = 0

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.real += 1
        self.attempt_calls += 1
        if self.clock.now >= SOFT or (self.soft_first and self.attempt_calls == 1):
            raise SoftTimeLimitExceeded("가상 시간 제한")
        self.clock.now += D
        self.enqueue(self.reply)
        return super().invoke(request, options)

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        text = user_text(request)
        answer = '{"generic_english": "Coffee and Tea"}' if "Original ERP text:" in text else "가상그룹"
        return Completed(text=answer, usage=SYNTHETIC_USAGE)


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    clock: Clock
    mock: Script
    sink: MemorySink = field(default_factory=MemorySink)

    def retry(self, **kwargs: Any) -> RetryAsked:
        return RetryAsked()


def make_world(
    monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], settings: Any, *, soft_first: bool
) -> World:
    settings.ESG_CONFIG = dataclasses.replace(settings.ESG_CONFIG, inventory_scope3_runs_enabled=True)
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    clock = Clock()
    made = World(storage, companies[0], clock, Script(clock, soft_first=soft_first))
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", clock)
    monkeypatch.setattr(journal, "monotonic", clock)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: int(SOFT))
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)

    def make(name: str, **kwargs: Any) -> Any:
        return made.mock if name == "openai" else llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))
    real_read = scope3_files.PackagedXlsx.read

    def read(self: scope3_files.PackagedXlsx) -> bytes | binding_157.FileMissing:
        return BOOK if self.name == scope3_files.FACTOR_BOOK.name else real_read(self)

    monkeypatch.setattr(scope3_files.PackagedXlsx, "read", read)
    return made


def start(client: Client, world: World) -> int:
    """웹의 uploadDocument → POST /runs(실행 id)."""
    login(client)
    made = client.post(
        "/api/documents",
        data={"fileName": "가상-scope3.xlsx", "sizeBytes": len(TEMPLATE)},
        content_type="application/json",
    )
    assert made.status_code == 201, made.content.decode()
    document_id: int = made.json()["document"]["id"]
    world.storage.put(DocumentRow.unscoped.get(pk=document_id).storage_key, TEMPLATE)
    assert client.post(f"/api/documents/{document_id}/confirm").status_code == 200
    body = {"module": "inventory.scope3", "documentId": document_id, "options": {"reportYear": 2025}}
    run = client.post("/api/runs", data=body, content_type="application/json")
    assert run.status_code == 201, run.content.decode()
    return run.json()["id"]


def run_of(world: World, run_id: int) -> run_selectors.Run:
    found = run_selectors.find_run(company_id=world.company_a, run_id=run_id)
    assert found is not None
    return found


def attempts_until_finished(world: World, run_id: int, limit: int) -> int:
    """시도마다 시계를 0 으로 되돌리고 execute_run. 끝(done·failed)까지의 부른 수."""
    for n in range(1, limit + 1):
        world.clock.now = 0.0
        world.mock.attempt_calls = 0
        with contextlib.suppress(RetryAsked):
            tasks.execute_run(world, company_id=str(world.company_a), run_id=str(run_id))
        if run_of(world, run_id).status in ("done", "failed"):
            return n
    raise AssertionError(f"시도 상한 {limit} 에 닿았다: {run_of(world, run_id)}")


def sha(body: object) -> str:
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def direct(company_id: int) -> tuple[dict[str, Any], int]:
    """같은 입력을 run_flow 에 바로(시계가 안 늘게 soft 판정 밖) — (결과, 공급사 수)."""
    book = read_workbook(BOOK)
    assert not isinstance(book, ReaderProblem)
    script = Script(Clock())
    script.clock.now = -1e9  # soft 판정에 닿지 않게
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": script},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    inputs = colab.ColabInputs(
        template=TEMPLATE,
        report_year=2025,
        route=binding_157.ROUTE,
        tags=Tags(tenant=str(company_id), module="inventory.scope3"),
    )
    result = run_flow(colab.FLOW, inputs, colab.ColabAdapters(llm=client, factor_book=book, geocoder=NoGeocoder()))
    (only,) = result.output.results
    return only, script.real


def test_a_long_template_survives_many_cooperative_yields_to_done(
    client: Client, monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], settings: Any
) -> None:
    assert CALLS * D > SOFT  # 한 시도로는 못 끝난다(머리말의 셈)
    world = make_world(monkeypatch, companies, settings, soft_first=False)
    run_id = start(client, world)
    attempts = attempts_until_finished(world, run_id, limit=EXPECTED_ATTEMPTS * 3)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("done", None), run.error_message
    want, calls = direct(world.company_a)
    (only,) = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert sha(only.body) == sha(want)
    assert world.mock.real == calls == CALLS
    assert run.attempts == attempts > SETTINGS.max_attempts
    assert run.stalled_attempts == 0
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    assert [s.name for s in steps] == [*colab.CATEGORY_STEPS, colab.ASSEMBLE]
    assert {s.status for s in steps} == {"done"}
    assert all(s.data is not None and set(s.data) == {"journal"} for s in steps[:-1])
    (c1,) = [s for s in steps if s.name == "c1"]
    assert c1.done == CALLS


def test_attempts_without_progress_are_exhausted_as_before(
    client: Client, monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], settings: Any
) -> None:
    world = make_world(monkeypatch, companies, settings, soft_first=True)
    run_id = start(client, world)
    attempts_until_finished(world, run_id, limit=SETTINGS.max_attempts * 3)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("failed", "attempts_exhausted")
    assert run.stalled_attempts == SETTINGS.max_attempts


def test_an_assemble_short_of_journal_does_not_pass_for_progress(
    client: Client, monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int], settings: Any
) -> None:
    """카테고리 단계 data 의 일지가 모자라면(soft limit 이 엔진 except 에 삼켜진 꼴 — 대역으로 일지를 비움) assemble 이
    실제로 부르고 그 호출은 저장되지 않는다. 시도마다 처음부터 다시 내므로 진행이 아니다 → stalled 가 쌓여
    attempts_exhausted 로 드러난다(가지 리뷰 MEDIUM 1 — assemble 체크포인트의 done 은 0)."""
    world = make_world(monkeypatch, companies, settings, soft_first=False)

    def short(self: journal.JournalGateway) -> list[dict[str, object]]:
        return []

    monkeypatch.setattr(journal.JournalGateway, "journal", short)
    run_id = start(client, world)
    attempts_until_finished(world, run_id, limit=EXPECTED_ATTEMPTS * 3 + SETTINGS.max_attempts * 2)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("failed", "attempts_exhausted")
    assert run.stalled_attempts == SETTINGS.max_attempts
    steps = {s.name: s for s in run_selectors.step_rows(company_id=world.company_a, run_id=run_id)}
    assert steps["c1"].status == "done"
    assert steps[colab.ASSEMBLE].status != "done"
    assert steps[colab.ASSEMBLE].done in (None, 0)  # 저장 안 된 실제 호출을 진행으로 세지 않았다
    assert world.mock.real > CALLS  # assemble 이 실제로 불렀다
