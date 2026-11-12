"""실행 문맥의 셈 합·시험 설정·지운 칸(밴드 LH1 — MARC-ISSUE-306 의 LV1 가지 리뷰 ①·③, m6).

  S11 합     그 실행의 앞 시도 DB 합(시드) 0.3 + 이 시도 0.4 → spent 0.7, 상한 0.5 에서 다음 호출이 공급사 전에 막힌다
             (시드·시도 각각은 상한 아래). 업무 층(시드는 DB 의 호출 기록 줄).
  S12 설정   LLM_RUN_MODE=live 가 든 셸에서도 시험 설정 둘(test_business·test_security)을 읽으면 모의다 — 다른
             프로세스에서 설정 모듈을 import 해 잰다(이 프로세스의 설정은 이미 읽혔다). 키는 없다(지운 환경).
  S10 칸     ExecutorContext·RunContext 에 dry_run 이 없다(읽는 곳이 없어 지움 — LH1 Q4).
★ 공급사는 모의뿐이다. 돈의 수는 지어낸 것이다.
"""

import json
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.flows.binding import RunContext
from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.setup import build_client
from esgapi.core.llm.sink_db import DbSink
from esgapi.core.llm.types import BudgetExceeded, Scope, Tags
from esgapi.core.tests.test_llm_sinks import RECORD
from esgapi.runs.context import ExecutorContext, RunCallSink
from esgapi.runs.tests import test_executor
from esgapi.runs.tests.test_context_live import seeded
from esgapi.runs.tests.test_executor import World, new_run

API_PY = Path(__file__).resolve().parents[3]
executor_world = test_executor.world  # 픽스처(이 이름으로 선다)


# ── S11 합 ─────────────────────────────────────────────────────────


@pytest.mark.django_db
def test_the_seed_and_this_attempt_add_up_and_the_sum_blocks_the_next_call(executor_world: World) -> None:
    world = executor_world
    run_id = new_run(world)
    seeded(world, run_id, "0.3")
    sink = RunCallSink(DbSink(), run_id)
    sink.count_run(world.company_id)
    limit = 0.5
    assert sink.spent(Scope()) == 0.3 < limit  # 시드만
    sink.record(replace(RECORD, tenant=str(world.company_id), cost_usd=0.4))  # 이 시도의 한 줄(0.4 < 상한)
    assert sink.spent(Scope()) == 0.7
    client = build_client(LlmSettings(log_sink="db"), mock=True, sink=sink, limits=(BudgetLimit(Scope(), limit),))
    mock = client.provider("mock")
    assert isinstance(mock, MockProvider)
    mock.enqueue_text("막혀야 한다")
    request = CallRequest(
        prompt="core/hello@1", vars={"name": "김"}, route="mock", tags=Tags(str(world.company_id), "probe")
    )
    result = client.call(request)
    assert isinstance(result, BudgetExceeded)
    assert (result.spent_usd, mock.calls) == (0.7, [])


# ── S12 시험 설정 ────────────────────────────────────────────────────

PROBE = """
import importlib, json, sys
module = importlib.import_module(sys.argv[1])
print(json.dumps({"run_mode": module.ESG_CONFIG.llm.run_mode, "shell": __import__("os").environ.get("LLM_RUN_MODE")}))
"""


@pytest.mark.parametrize("settings", ["esgapi.config.settings.test_business", "esgapi.config.settings.test_security"])
def test_the_test_settings_stay_mock_in_a_live_shell(settings: str) -> None:
    keys = ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "LLM_OPENAI_API_KEY", "LLM_ANTHROPIC_API_KEY", "LLM_GEMINI_API_KEY")
    env = {name: value for name, value in os.environ.items() if name not in keys}
    env |= {"LLM_RUN_MODE": "live", "LLM_RUN_MAX_USD": "0.01", "PYTHONDONTWRITEBYTECODE": "1"}
    done = subprocess.run(
        [sys.executable, "-c", PROBE, settings], cwd=API_PY, env=env, capture_output=True, text=True, check=False
    )
    assert done.returncode == 0, done.stderr[-2000:]
    assert json.loads(done.stdout.strip().splitlines()[-1]) == {"run_mode": "mock", "shell": None}


# ── S10 dry_run 칸 ───────────────────────────────────────────────────


def test_the_run_context_has_no_dry_run() -> None:
    ctx = ExecutorContext(company_id=1, run_id=1, module="probe", flow_id="f", attempt=1, sink=RunCallSink(DbSink(), 1))
    assert not hasattr(ctx, "dry_run")
    assert "dry_run" not in dir(RunContext)
