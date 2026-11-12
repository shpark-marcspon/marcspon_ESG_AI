"""실행 하나·시도 하나의 문맥(core/flows/binding.py 의 RunContext)과 그 실행의 LLM 호출 기록 싱크.

    StepCursor                   실행 하나·시도 하나의 「지금 단계」(AD4D). 실행기의 사건(RowEvents)이 단계 시작에
                                 적고 끝·실패에 비운다
    RunCallSink(inner, run_id, cursor)
                                 기록마다 run_id 와 step(커서의 지금 단계)을 그 실행으로 **덮어 적어** inner 에 넘긴다
                                 (꼬리표·끼움과 무관 — 끼움이 run 없는 Tags 로 불러도 그 실행·그 단계의 줄이 된다).
                                 커서가 없으면 step 은 None. accepts_bodies 는 inner 의 것. spent 는 mock 이면 inner 의
                                 것, live(count_run 뒤)면 그 실행의 누적(아래 ★)
    ExecutorContext              끼움의 adapters 가 받는 것. llm()·embedding() 은 이 실행의 싱크 하나로 짓는다

★ 실행기가 실제 공급사의 키를 싣는가는 LLM_RUN_MODE 하나가 정한다(LV1, MARC-ENT-262 — 사용자 승인 뒤 켬):
    mock(기본·빈 값)  키를 비운 설정 + build_client(…, mock=True) — 실제 공급사 경로를 부르면 LiveSetupError(키가 없다)
                      → setup_error. 상한 없음(BASE 그대로). 프로세스에 키가 있어도 싣지 않는다
    live              키를 그대로 + mock=False + 실행 하나의 상한 BudgetLimit(Scope(), LLM_RUN_MAX_USD) 하나를
                      대화·임베딩 클라이언트에 같이. 기동 조건(config/env.py): LLM_LOG_SINK=db · 키 하나 이상 ·
                      LLM_RUN_MAX_USD 명시
  공급사는 모델 설정의 경로가 고른다(그린워싱 openai·영문번역 경로 상수) — 이 파일은 「키를 싣는가」만 정한다.
★ live 의 상한은 **그 실행의 누적**이다: 싱크의 spent 가 (처음 한 번 읽은 그 실행의 앞 시도 DB 합 = 시드) + (이 시도가
  기록한 줄의 cost_usd) 를 낸다(범위·꼬리표와 무관 — 대화와 임베딩이 같은 몫을 나눠 쓴다). 무효 조건:
    - 시드를 읽은 뒤의 하한이다. 같은 실행의 시도 둘이 겹쳐 돌면(임대가 풀린 뒤 앞 시도가 아직 살아 있음) 둘이 같은 몫을
      따로 센다(sink_db.py 머리말 「상한의 뜻」과 같은 꼴). 하루·회사 상한은 서버에 없다(공급사 쪽 예산 경보는 사람 몫)
    - 줄을 쓰기 전에 죽은 호출의 비용은 세지 않는다. 상한은 「하한이 닿으면 막는다」라 실제 지출은 한 호출만큼
      넘을 수 있다
    - 실패 시도의 보수 어림(LH2 S2 — 시간 초과·상태 없는 실패·2xx 오류 줄의 cost_bound_usd, core/llm/client.py 머리)은
      **이 시도 몫에만** 더한다. DB 시드(앞 시도)에는 없다(그 칸은 DB 에 싣지 않는다 — 장부 cost_usd 는 실비만). 그래서
      시도당 상한 넘침 최악 ≈ 2 × 한 번 최악(앞 시도에서 센 어림이 다음 시도에 없음 + 닿으면 막는 한 호출). 시도를 넘는
      셈은 **받아들임**(LH3 Q1 — MARC-ISSUE-413 I1): 앞 시도의 실패 어림은 시드에 없다. 진행 없이 끝난 시도는
      JOB_MAX_ATTEMPTS(기본 3 — config/env.py:84 JobSettings.max_attempts)에서 끝나므로(runs/calc/claims.py:46-50 —
      stalled_attempts 만 센다) 그 몫의 넘침 최악 ≈ 2 × 한 번 최악 × JOB_MAX_ATTEMPTS. 진행한 시도는 그 셈에 들지 않아
      시도 수 전체의 상한은 없다(소프트 제한의 RunDeferred 가 시도를 늘린다 — LH2 S3) — 각 시도의 넘침은 그 시도 실패
      어림 하나 몫이다. 실패 줄의 비용 칸(DB)은 2차 MARC-ENT-465 때
★ 싱크의 바닥(inner)은 이 프로세스의 설정(LLM_LOG_SINK — memory·jsonl·db)으로 실행마다 새로 진다(call_sink — 이음매).
"""

from dataclasses import dataclass, field, replace

from esgapi.config.env import LlmSettings
from esgapi.core.conf import app_config
from esgapi.core.llm.budget import BudgetLimit
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.embedding import EmbeddingClient
from esgapi.core.llm.log import CallLogSink, CallRecord
from esgapi.core.llm.setup import build_client, build_embedding_client, make_sink
from esgapi.core.llm.types import Scope
from esgapi.core.service.selectors import llm_usage


class StepCursor:
    """실행 하나·시도 하나의 지금 단계 이름(단계 밖·단계 사이는 None)과 지금 구획 열쇠의 sha(펼침 단계의 구획 안만 —
    RM1a. 장벽 단계·구획 밖은 None).

    단계는 차례로 돌아 적는 쪽이 하나라 잠금이 없다(단계 안의 스레드는 읽기만 한다).
    ★ 단계 사건의 예외(RunYield — 내 시도가 아님·마감)는 step_failed 를 거치지 않는다(core/flows/run.py) — 그 뒤
      커서는 비지 않지만 그 시도는 끝나 호출이 더 없다(다음 시도는 새 커서).
    """

    __slots__ = ("current", "segment")

    def __init__(self) -> None:
        self.current: str | None = None
        self.segment: str | None = None


class RunCallSink:
    """그 실행의 호출 기록 싱크. 기록마다 run_id 와 step(커서의 지금 단계)·segment(지금 구획)를 덮어 적는다.

    count_run(company_id) 뒤에는 spent 가 그 실행의 누적이다(live 의 상한 — 머리말). 그 전에는 inner 의 것(mock).
    """

    def __init__(self, inner: CallLogSink, run_id: int, cursor: StepCursor | None = None) -> None:
        self._inner = inner
        self._run_id = str(run_id)
        self._cursor = cursor
        # DB 싱크는 본문을 받지 않는다(setup.build_client 가 이것을 보고 store_bodies 를 막는다) — 그대로 넘긴다.
        self.accepts_bodies: bool = bool(getattr(inner, "accepts_bodies", True))
        self._company_id: int | None = None
        self._seed: float | None = None  # 그 실행의 앞 시도 DB 합(처음 spent 때 한 번 읽는다)
        self._attempt_usd = 0.0  # 이 시도가 기록한 줄의 cost_usd 합(NULL 이면 cost_bound_usd — 없으면 0, LH2)

    @property
    def inner(self) -> CallLogSink:
        return self._inner

    def count_run(self, company_id: int) -> None:
        """spent 를 그 실행의 누적으로 바꾼다(live). 여러 번 불러도 같다."""
        self._company_id = company_id

    def record(self, record: CallRecord) -> None:
        step = None if self._cursor is None else self._cursor.current
        segment = None if self._cursor is None else self._cursor.segment
        # 실비가 없는 실패 시도는 보수 어림(cost_bound_usd)을 센다 — 이 시도의 live 상한 셈에만(머리말 ★, LH2 S2).
        self._attempt_usd += record.cost_usd if record.cost_usd is not None else (record.cost_bound_usd or 0.0)
        self._inner.record(replace(record, run_id=self._run_id, step=step, segment=segment))

    def spent(self, scope: Scope) -> float:
        if self._company_id is None:
            return self._inner.spent(scope)
        if self._seed is None:
            usage = llm_usage.usage_by_run(company_id=self._company_id, run_ids=frozenset({int(self._run_id)}))
            found = usage.get(int(self._run_id))
            self._seed = 0.0 if found is None else float(found.cost_usd)
        return round_usd(self._seed + self._attempt_usd)


def llm_settings() -> LlmSettings:
    """실행기의 LLM 설정: mock 이면 이 프로세스의 것에서 실제 공급사의 키를 비운 것, live 면 그대로(머리말).

    ★ 이음매다.
    """
    settings = app_config().llm
    if settings.run_mode == "live":
        return settings
    return replace(settings, openai_api_key=None, anthropic_api_key=None, gemini_api_key=None)


def call_sink() -> CallLogSink:
    """이 프로세스 설정의 싱크를 새로 짓는다(실행마다 하나). ★ 이음매다."""
    return make_sink(app_config().llm)


@dataclass(frozen=True, slots=True, kw_only=True)
class ExecutorContext:
    """RunContext 의 구현. 실행기가 시도마다 하나 짓는다."""

    company_id: int
    run_id: int
    module: str
    flow_id: str
    attempt: int
    sink: RunCallSink = field(repr=False, compare=False)

    def llm(self) -> LlmClient:
        """이 실행의 LLM 클라이언트(호출 기록은 이 실행의 싱크로). mock 이면 모의 공급사만, live 면 실제 키와 상한."""
        settings = llm_settings()
        return build_client(settings, mock=settings.run_mode != "live", sink=self.sink, limits=self._limits(settings))

    def embedding(self) -> EmbeddingClient:
        settings = llm_settings()
        return build_embedding_client(
            settings, mock=settings.run_mode != "live", sink=self.sink, limits=self._limits(settings)
        )

    def _limits(self, settings: LlmSettings) -> tuple[BudgetLimit, ...]:
        """live 면 그 실행의 누적에 거는 상한 하나(싱크를 그 실행의 셈으로 바꾼다), mock 이면 없음(BASE 그대로)."""
        if settings.run_mode != "live":
            return ()
        self.sink.count_run(self.company_id)
        return (BudgetLimit(Scope(), settings.run_max_usd),)
