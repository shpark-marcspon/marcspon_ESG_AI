"""흐름 scope3.colab@157 의 카테고리 단계 + 호출 일지(밴드 S3R1 T2·T4 — DB 0, `run_flow` 직접).

    (a) 끊김 없음: 결과 바이트(assemble data 의 JSON sha256) = BASE 꼴 한 번 돌기 · 공급사 수 같음 · assemble 실제 0
    (b) 협조 마감 흉내: 사건 받는 쪽이 k 번째 사건(단계 시작·체크포인트)에서 BaseException 을 던지고, 저장된 자리
        (끝난 단계 data + 그 단계 partial)에서 다시 돈다 → sha 같음 · 공급사 총수 = 한 번 돌기
    (c) 호출 한가운데 soft limit: 공급사가 j 번째 부름에서 soft limit 꼴 → FlowStepFailed 로 끊기고 이어 돎 →
        sha 같음 · 총수 = 한 번 돌기 + 1(부름이 들어올 때 센다)
    (d) 되감기만 하는 단계에서 마감: 일지가 다 있는 채 다시 돌며 흐름 시계가 되감은 호출마다 30s 씩 → 실제 0 인 채
        체크포인트(done 같음) · 양보가 흐름 밖으로. assemble 안에서도
    (e) 시트 차례를 뒤섞은 판에서 (a)(b)
    (f) 거른 템플릿에 회사별 매핑·기업정보 시트가 남는다
    T4  입력 품목의 표지 글이 단계 data·partial 에 0 번(결과에는 있다 — 양성 대조)

공급사는 시험 안 가짜 게이트웨이(엔진 포트 꼴): 프롬프트마다 지은 답, 같은 열쇠의 두 번째 부름부터 다른 답(같은
줄이 거듭 쓰이면 결과가 바뀐다 — P3). 템플릿·계수·답은 전부 지은 것이다.
"""

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import cast

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowStepFailed, StepOutput
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.types import LlmResult
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, run
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import SHEET_PROCESSOR_MAP
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.flows import scope3_journal_157 as journal
from esgapi.inventory.flows.scope3_journal_157 import Entry, call_key, result_of
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    FakeGeocoder,
    activity_factor_sheets,
    annual,
    commute_sheet,
    sheet,
    transport_distance_sheet,
    transport_ef_sheet,
    travel_distance_sheet,
    travel_ef_sheet,
    travel_spend_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_ROWS, C2_ROWS, TAGS
from esgapi.inventory.tests.flows.test_scope3_colab_157_soft_deadline import SoftTimeLimitExceeded
from esgapi.inventory.tests.scope3_llm_support import ROUTE
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

MARKER = "가상표지품목"
C1 = sheet(
    "C1_구매품서비스",
    {
        **C1_ROWS,
        13: ["가상국", "가상사업장", None, "가상 무엇", None, 9.5],  # 8행과 같은 글 — 그룹 부름이 같은 열쇠로 두 번
        14: ["가상국", "가상사업장", None, f"{MARKER} 어떤것", None, 9700],  # 규칙에 안 걸려 그룹 이름 = 품목 글
    },
)
COMPANY = sheet("기업정보", {7: [None, None, "가상회사"]})
MAPPING = sheet(
    "회사별_교통수단매핑", {1: ["회사", "상세명", "교통수단"], 2: ["가상회사", "가상상세비행", "가상 항공권"]}
)
# 거리 칸이 빈 줄 — 도시 이름·거리·수단 부름이 생긴다(거리판 꼴, 지명은 지은 것)
ROAD = annual(["가상국", "가상사업장", "가상트럭", "가상 철강 코일", "ton", "가상시가", "가상시나", None], 9.1)
ROAD2 = annual(["가상국", "가상사업장", "가상화물차", "가상 상자 자재", "kg", "가상시가", "가상시다", None], 920)
TRIP = annual(["가상국", "가상본부", "가상비행기", 9, "가상시자", "가상시차", None], 9)
TRIP2 = annual(["가상국", "가상지사", "가상기차", 9, "가상시가", "가상시다", None], 9)
COMMUTE = annual(["가상국", "가상사업장", "가상버스", 9, "가상시카", "가상시타", None], 99)
SHEETS: tuple[Sheet, ...] = (
    COMPANY,
    C1,
    sheet("C2_자본재", C2_ROWS),
    transport_distance_sheet("c4-1_운송거리", ROAD, ROAD2),
    travel_spend_sheet("c6-2_출장비"),
    travel_distance_sheet("c6-1_출장거리", TRIP, TRIP2),
    commute_sheet("c7_임직원통근", COMMUTE),
    transport_distance_sheet("c9-1_운송거리", ROAD2),
    MAPPING,
)
SHUFFLED: tuple[Sheet, ...] = (
    SHEETS[7],
    SHEETS[0],
    SHEETS[5],
    SHEETS[3],
    SHEETS[1],
    SHEETS[8],
    SHEETS[6],
    SHEETS[2],
    SHEETS[4],
)
BOOK = workbook(sheet("구매_USEPA", BOOK_ROWS), *activity_factor_sheets(), transport_ef_sheet(), travel_ef_sheet())

ANSWERS: Mapping[str, Sequence[str]] = {
    "inventory/scope3-colab-group-name@1": ("", "가상장비", "가상기타"),
    "inventory/scope3-colab-naics-pick@1": ('{"generic_english": "Coffee and Tea"}',),
    "inventory/scope3-colab-city-name@1": ("Synthetic Ga", "Synthetic Gb"),
    "inventory/scope3-colab-distance-straight@1": ('{"distance_km": 92}', '{"distance_km": 93}'),
    "inventory/scope3-colab-distance-road@1": ('{"distance_km": 99}', '{"distance_km": 98}'),
    "inventory/scope3-colab-airport@1": ('{"airport_name": "Synthetic Ja Airport", "iata": ""}',),
    "inventory/scope3-colab-transport-mode@1": ('{"mode": "rail"}',),
    "inventory/scope3-colab-travel-mode@1": ('{"mode": "train"}', '{"mode": "bus"}'),
    "inventory/scope3-colab-unit-factor@1": ('{"factor": 9.5}',),
    "inventory/scope3-colab-unit-factor-simple@1": ("9.5",),
}


class Yield(BaseException):
    """실행기의 RunYield 꼴(시험 안)."""


class Provider:
    """가짜 공급사 게이트웨이. 같은 열쇠의 n 번째 부름은 그 프롬프트 답의 n 번째(끝에서 멈춤). 부름이 들어올 때 센다."""

    def __init__(self, soft_on: int | None = None) -> None:
        self.calls = 0
        self.seen: dict[str, int] = {}
        self.soft_on = soft_on

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        self.calls += 1
        if self.soft_on is not None and self.calls == self.soft_on:
            raise SoftTimeLimitExceeded("가상 시간 제한")
        key = call_key(cast("CallRequest[object]", request))
        n = self.seen.get(key, 0)
        self.seen[key] = n + 1
        options = ANSWERS[request.prompt]
        return cast("LlmResult[T]", result_of(Entry(key, "success", options[min(n, len(options) - 1)])))


def inputs_of(sheets: Sequence[Sheet]) -> colab.ColabInputs:
    return colab.ColabInputs(template=xlsx_bytes(workbook(*sheets)), report_year=2025, route=ROUTE, tags=TAGS)


def adapters_of(provider: Provider) -> colab.ColabAdapters:
    return colab.ColabAdapters(llm=provider, factor_book=BOOK, geocoder=FakeGeocoder())


def sha(results_data: Mapping[str, object]) -> str:
    return hashlib.sha256(json.dumps(results_data, ensure_ascii=False).encode("utf-8")).hexdigest()


def base(sheets: Sequence[Sheet]) -> tuple[str, int]:
    """BASE 꼴(단계 calculate 하나 — 엔진 run 한 번 + serializer)의 결과 바이트 sha 와 공급사 수."""
    provider = Provider()
    result = run(workbook(*sheets), BOOK, 2025, provider, FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(result, ColabRun)
    return sha({"results": [result_to_dict(result, colab.RESULT_SHAPE)]}), provider.calls


@dataclass
class Rows:
    """실행기의 단계 행 흉내: 끝난 단계 data, 단계마다 마지막 partial·done. yield_at 번째 사건에서 Yield."""

    finished: dict[str, StepOutput] = field(default_factory=dict[str, StepOutput])
    partials: dict[str, dict[str, object]] = field(default_factory=dict[str, dict[str, object]])
    dones: list[tuple[str, int]] = field(default_factory=list[tuple[str, int]])
    yield_at: int | None = None
    events: int = 0
    moved: bool = False  # 이 시도에 진행(체크포인트·단계 끝)이 있었나 — 진행 없이 접히는 시도를 막는다

    def _tick(self) -> None:
        self.events += 1
        if self.yield_at is not None and self.moved and self.events >= self.yield_at:
            raise Yield

    def step_started(self, flow_id: str, step: str) -> None:
        self._tick()

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.partials[step] = dict(partial)
        self.dones.append((step, done))
        self.moved = True
        self._tick()

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        self.finished[step] = output
        self.moved = True

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        return None

    def next_attempt(self) -> None:
        self.events = 0
        self.moved = False


def resumed_run(rows: Rows, inputs: colab.ColabInputs, provider: Provider, limit: int = 200) -> tuple[str, int]:
    """끊길 때마다 저장된 자리에서 다시 돈다(실행기 _plan 꼴). (결과 sha, 시도 수)."""
    for attempt in range(1, limit + 1):
        start = next((s for s in colab.FLOW.steps if s not in rows.finished), None)
        assert start is not None
        rows.next_attempt()
        try:
            done = run_flow(
                colab.FLOW,
                inputs,
                adapters_of(provider),
                start_at=start,
                carried={s: rows.finished[s] for s in colab.FLOW.steps[: colab.FLOW.steps.index(start)]},
                resume=rows.partials.get(start),
                events=rows,
            )
        except Yield:
            continue
        except FlowStepFailed as failed:
            assert isinstance(failed.__cause__, SoftTimeLimitExceeded)
            continue
        return sha(done.steps[colab.ASSEMBLE].data), attempt
    raise AssertionError("시도 상한")


# ── (a)·(e) 끊김 없음 ──


@pytest.mark.parametrize("sheets", [SHEETS, SHUFFLED], ids=["ordered", "shuffled"])
def test_an_unbroken_run_gives_the_base_bytes_with_the_same_provider_calls(sheets: tuple[Sheet, ...]) -> None:
    want, calls = base(sheets)
    provider = Provider()
    done = run_flow(colab.FLOW, inputs_of(sheets), adapters_of(provider))
    assert list(done.steps) == [*colab.CATEGORY_STEPS, colab.ASSEMBLE]
    assert sha(done.steps[colab.ASSEMBLE].data) == want
    assert provider.calls == calls > 10
    journals = [cast("list[object]", done.steps[s].data["journal"]) for s in colab.CATEGORY_STEPS]
    assert sum(len(j) for j in journals) == calls  # 실제 호출은 카테고리 단계에만 — assemble 실제 0
    assert done.steps[colab.ASSEMBLE].data.keys() == {"results"}


def test_assemble_makes_no_real_call() -> None:
    provider = Provider()
    done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(provider))
    entries = [
        Entry(cast("str", e["k"]), cast("str", e["kind"]), cast("str", e["text"]))
        for s in colab.CATEGORY_STEPS
        for e in cast("list[dict[str, object]]", done.steps[s].data["journal"])
    ]
    again = Provider()
    result = colab.assemble_run(inputs_of(SHEETS), adapters_of(again), entries)
    assert isinstance(result, ColabRun)
    assert again.calls == 0
    assert sha({"results": [result_to_dict(result, colab.RESULT_SHAPE)]}) == base(SHEETS)[0]


# ── (b)·(e) 협조 마감 흉내 ──


@pytest.mark.parametrize("sheets", [SHEETS, SHUFFLED], ids=["ordered", "shuffled"])
@pytest.mark.parametrize("k", [1, 2, 3, 5, 8])
def test_a_cooperative_yield_resumes_where_it_stopped(sheets: tuple[Sheet, ...], k: int) -> None:
    want, calls = base(sheets)
    provider = Provider()
    rows = Rows(yield_at=k)
    got, attempts = resumed_run(rows, inputs_of(sheets), provider)
    assert got == want
    assert provider.calls == calls
    assert attempts > 1
    done_by_step: dict[str, list[int]] = {}
    for step, done in rows.dones:
        done_by_step.setdefault(step, []).append(done)
    assert all(d == sorted(d) for d in done_by_step.values())  # done 은 시도를 넘어 줄지 않는다


def test_a_yield_right_before_assemble_resumes_at_assemble() -> None:
    want, calls = base(SHEETS)
    provider = Provider()

    class BeforeAssemble(Rows):
        armed = True

        def step_started(self, flow_id: str, step: str) -> None:
            if step == colab.ASSEMBLE and self.armed:
                self.armed = False
                raise Yield

    rows = BeforeAssemble()
    got, attempts = resumed_run(rows, inputs_of(SHEETS), provider)
    assert (got, attempts, provider.calls) == (want, 2, calls)


# ── (c) 호출 한가운데 soft limit ──


@pytest.mark.parametrize("j", [1, 2, 4, 7, 12])
def test_a_soft_limit_inside_a_call_costs_one_call_more(j: int) -> None:
    want, calls = base(SHEETS)
    provider = Provider(soft_on=j)
    got, attempts = resumed_run(Rows(), inputs_of(SHEETS), provider)
    assert (got, attempts) == (want, 2)
    assert provider.calls == calls + 1


# ── (d) 되감기만 하는 단계에서 마감 ──


def full_steps() -> dict[str, StepOutput]:
    return dict(run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(Provider())).steps)


class Clock:
    def __init__(self, step: float) -> None:
        self.now = 0.0
        self.step = step

    def __call__(self) -> float:
        self.now += self.step
        return self.now


class YieldOnCheckpoint(Rows):
    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        self.partials[step] = dict(partial)
        self.dones.append((step, done))
        raise Yield


def test_a_replay_only_step_still_checkpoints_and_yields(monkeypatch: pytest.MonkeyPatch) -> None:
    steps = full_steps()
    journal_c4 = cast("list[object]", steps["c4"].data["journal"])
    assert len(journal_c4) >= 2
    resume = {
        "v": 1,
        "templateSha256": hashlib.sha256(inputs_of(SHEETS).template).hexdigest(),
        "factorBookSha256": colab.book_sha256(BOOK),
        "step": "c4",
        "done": len(journal_c4),
        "journal": journal_c4,
    }
    monkeypatch.setattr(journal, "monotonic", Clock(30.0))
    provider, rows = Provider(), YieldOnCheckpoint()
    carried = {s: steps[s] for s in ("c1", "c2", "c3")}
    with pytest.raises(Yield):
        run_flow(
            colab.FLOW,
            inputs_of(SHEETS),
            adapters_of(provider),
            start_at="c4",
            carried=carried,
            resume=resume,
            events=rows,
        )
    assert provider.calls == 0
    assert rows.dones == [("c4", len(journal_c4))]


def test_a_replay_in_assemble_still_checkpoints_and_yields(monkeypatch: pytest.MonkeyPatch) -> None:
    steps = full_steps()
    monkeypatch.setattr(journal, "monotonic", Clock(30.0))
    provider, rows = Provider(), YieldOnCheckpoint()
    carried = {s: steps[s] for s in colab.CATEGORY_STEPS}
    with pytest.raises(Yield):
        run_flow(
            colab.FLOW, inputs_of(SHEETS), adapters_of(provider), start_at=colab.ASSEMBLE, carried=carried, events=rows
        )
    assert provider.calls == 0
    assert rows.dones == [(colab.ASSEMBLE, 0)]
    assert rows.partials[colab.ASSEMBLE] == {"v": 1, "step": colab.ASSEMBLE, "done": 0, "journal": []}


# ── (f) 거른 템플릿 ──


def test_the_filtered_template_keeps_sheets_without_a_processor_in_order() -> None:
    book = workbook(*SHUFFLED)
    names = [s.name for s in colab.filtered(book, "c4").sheets]
    assert names == ["기업정보", "c4-1_운송거리", "C1_구매품서비스", "회사별_교통수단매핑", "C2_자본재"]
    assert [s.name for s in colab.filtered(book, "c1").sheets] == ["기업정보", "C1_구매품서비스", "회사별_교통수단매핑"]
    assert [s.name for s in colab.filtered(book, "c15").sheets] == [s.name for s in SHUFFLED]
    assert colab.filtered(book, "c1").defined_names == book.defined_names


def test_every_sheet_processor_has_a_category_step() -> None:
    """처리기 표의 카테고리가 모두 단계에 있다(없으면 그 시트는 어느 단계에서도 걸러져 나간다 — 가지 리뷰 LOW 3)."""
    assert {colab.category_step(name) for name in SHEET_PROCESSOR_MAP} <= set(colab.CATEGORY_STEPS)


def test_a_step_without_its_sheets_does_not_run_the_engine() -> None:
    provider = Provider()
    done = run_flow(colab.FLOW, inputs_of(SHEETS), adapters_of(provider))
    for step in ("c3", "c5", "c8", "c11", "c12", "c13", "c14", "c15"):
        assert done.steps[step].data == {"journal": []}


def test_an_unreadable_template_is_still_rejected_at_assemble() -> None:
    provider = Provider()
    inputs = colab.ColabInputs(template=b"PK\x03\x04 not a zip", report_year=2025, route=ROUTE, tags=TAGS)
    done = run_flow(colab.FLOW, inputs, adapters_of(provider))
    (result,) = done.output.results
    assert result["status"] == "rejected"
    assert provider.calls == 0


# ── T4 진행 저장의 원문 ──


def test_step_data_and_partials_carry_no_input_text_beyond_the_result() -> None:
    rows = Rows(yield_at=2)
    provider = Provider()
    resumed_run(rows, inputs_of(SHEETS), provider)
    result = json.dumps(rows.finished[colab.ASSEMBLE].data, ensure_ascii=False)
    saved = json.dumps(
        {
            "data": {s: rows.finished[s].data for s in colab.CATEGORY_STEPS},
            "partials": rows.partials,
        },
        ensure_ascii=False,
    )
    assert result.count(MARKER) > 0  # 양성 대조: 결과(그룹의 품목/자산명)에는 있다
    assert saved.count(MARKER) == 0
    assert rows.partials, "체크포인트가 하나도 없다"
