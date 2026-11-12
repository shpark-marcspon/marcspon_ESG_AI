"""읽기. 실행마다 붙은 LLM 호출 기록의 합(표 core_llm_call_logs — AU1b-2 의 AD-04 운영 관리자 실행 기록). 쓰지 않는다.

    usage_by_run(company_id, run_ids)   실행 id → RunUsage(토큰 넷·비용의 합, NULL 은 0). 한 쿼리(빈 집합이면 0)
    usage_by_step(company_id, run_id)   실행 하나의 단계 이름 → RunUsage + recorded(그 실행의 줄 가운데 단계 칸이
                                        NULL 인 줄이 0 인가 — AD4D). 한 쿼리
    usage_by_segment(company_id, run_id, fanout_steps)   실행 하나의 (단계, 구획 sha) → RunUsage + recorded(펼침
                                        단계의 줄 가운데 구획 칸이 NULL 인 줄이 0 인가 — RM1a). 한 쿼리

회사 범위는 LlmCallLogRow.for_company(company_id) 하나다 — 남의 회사 줄은 같은 run_id 값이어도 합에 들지 않는다.
권한은 보지 않는다: 부르는 경로가 첫 문장(permitted)에서, 실행을 고르는 runs 의 selector 가 첫 줄에서 본다
(core/tests/test_permissions.py 의 ALSO_INSIDE 는 동작마다 함수 하나 — 이 함수는 그 함수가 고른 id 만 받는다).
thinking_tokens 는 더하지 않는다(output_tokens 에 이미 든 몫 — core/llm/types.py).

무효 조건:
  - MARC-ISSUE-199 의 5(꼬리표 덮어쓰기를 안 막음)로 실행 A 의 호출이 다른 회사 꼬리표로 적히면 그 줄은 A 의 합에서
    빠진다(새지는 않는다).
  - 실행기는 지금 모의 공급사만 싣는다(runs/context.py, MARC-ENT-262) — 실호출 전의 토큰·비용은 모의 값이다.
  - 비용(cost_usd)은 web_search 건당 요금도 품는다. NULL(상한에 막혀 안 부른 줄)은 0 이다(「추정」).
  - 단계 칸(step)은 AD4D 뒤의 실행기 줄에만 있다. 그 앞의 줄·단계 사이의 호출은 NULL 이라 단계별 합을 모른다 —
    recorded=False(부르는 쪽이 단계별 값을 통째로 「모름」으로 낸다, 합계는 그대로).
  - 구획 칸(segment)은 RM1a 뒤 펼침 단계의 구획 안 호출에만 있다. 장벽 단계의 줄은 늘 NULL 이라 recorded 는
    부르는 쪽이 넘긴 펼침 단계(fanout_steps)의 줄만 본다(그 단계의 plan 안 호출·RM1a 앞의 줄이 NULL — 모듈 계약상
    plan 은 LLM 0 이다). 구획별 합은 같은 실행의 usage_by_run 몫 안이다(다른 회사·다른 실행의 줄은 0). 끊긴 시도의
    호출도 그 구획의 줄로 든다(실지출 — 구획 하나를 두 시도가 불렀으면 둘 다).
  - run_ids 가 수만이 되면 run_id__in 이 psycopg 매개 상한(65,535)에 닿는다 — 그때 다시 짠다.
"""

from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum

from esgapi.core.calc.run_metrics import RunUsage
from esgapi.core.models import LlmCallLogRow


def usage_by_run(*, company_id: int, run_ids: frozenset[int]) -> dict[int, RunUsage]:
    """그 회사의 LLM 줄 가운데 run_id 가 run_ids 안인 것을 실행마다 더한다. 줄이 없는 실행은 열쇠가 없다."""
    if not run_ids:
        return {}
    rows = (
        LlmCallLogRow.for_company(company_id)
        .filter(run_id__in=run_ids)
        .order_by()
        .values("run_id")
        .annotate(
            input=Sum("input_tokens"),
            cache_read=Sum("cache_read_tokens"),
            cache_write=Sum("cache_write_tokens"),
            output=Sum("output_tokens"),
            cost=Sum("cost_usd"),
        )
    )
    return {
        row["run_id"]: RunUsage(
            input=row["input"] or 0,
            cache_read=row["cache_read"] or 0,
            cache_write=row["cache_write"] or 0,
            output=row["output"] or 0,
            cost_usd=row["cost"] or Decimal(0),
        )
        for row in rows
    }


@dataclass(frozen=True, slots=True)
class StepUsage:
    by_step: dict[str, RunUsage]  # 단계 이름 → 합(줄이 없는 단계는 열쇠가 없다)
    recorded: bool  # 그 실행의 줄 가운데 step 이 NULL 인 줄이 0(줄이 없어도 True)


def usage_by_step(*, company_id: int, run_id: int) -> StepUsage:
    """그 회사의 LLM 줄 가운데 run_id 가 그 실행인 것을 단계 이름마다 더한다(usage_by_run 과 같은 셈)."""
    rows = (
        LlmCallLogRow.for_company(company_id)
        .filter(run_id=run_id)
        .order_by()
        .values("step")
        .annotate(
            input=Sum("input_tokens"),
            cache_read=Sum("cache_read_tokens"),
            cache_write=Sum("cache_write_tokens"),
            output=Sum("output_tokens"),
            cost=Sum("cost_usd"),
        )
    )
    by_step: dict[str, RunUsage] = {}
    recorded = True
    for row in rows:
        if row["step"] is None:
            recorded = False
            continue
        by_step[row["step"]] = RunUsage(
            input=row["input"] or 0,
            cache_read=row["cache_read"] or 0,
            cache_write=row["cache_write"] or 0,
            output=row["output"] or 0,
            cost_usd=row["cost"] or Decimal(0),
        )
    return StepUsage(by_step=by_step, recorded=recorded)


@dataclass(frozen=True, slots=True)
class SegmentUsage:
    by_segment: dict[tuple[str, str], RunUsage]  # (단계 이름, 구획 열쇠 sha) → 합(줄이 없는 구획은 열쇠가 없다)
    recorded: bool  # 펼침 단계(fanout_steps)의 줄 가운데 segment 가 NULL 인 줄이 0(줄이 없어도 True)


def usage_by_segment(*, company_id: int, run_id: int, fanout_steps: frozenset[str]) -> SegmentUsage:
    """그 회사의 LLM 줄 가운데 run_id 가 그 실행인 것을 (단계, 구획)마다 더한다(usage_by_run 과 같은 셈)."""
    rows = (
        LlmCallLogRow.for_company(company_id)
        .filter(run_id=run_id)
        .order_by()
        .values("step", "segment")
        .annotate(
            input=Sum("input_tokens"),
            cache_read=Sum("cache_read_tokens"),
            cache_write=Sum("cache_write_tokens"),
            output=Sum("output_tokens"),
            cost=Sum("cost_usd"),
        )
    )
    by_segment: dict[tuple[str, str], RunUsage] = {}
    recorded = True
    for row in rows:
        step, segment = row["step"], row["segment"]
        if segment is None or step is None:
            if step in fanout_steps:
                recorded = False
            continue
        by_segment[(step, segment)] = RunUsage(
            input=row["input"] or 0,
            cache_read=row["cache_read"] or 0,
            cache_write=row["cache_write"] or 0,
            output=row["output"] or 0,
            cost_usd=row["cost"] or Decimal(0),
        )
    return SegmentUsage(by_segment=by_segment, recorded=recorded)
