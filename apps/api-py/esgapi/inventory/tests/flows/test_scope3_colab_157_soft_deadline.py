"""흐름 scope3.colab@157 에서 Celery soft limit 이 「실패 값 → 다음」·「시트 실패」로 굳지 않고 밖으로 나가는가
(MARC-ISSUE-414, 밴드 S3L1).

엔진은 core.llm.errors 를 모르니(test_purity 의 ALLOWED_LLM) 흐름이 「다시 던질지」 판별(core 의 soft_deadline_in)을
엔진 문맥(LlmContext.reraise)에 주입한다. 포트 길을 감싼 넓은 except 열하나를 길 종류마다 잰다 — 번역 LLM
(purchase 598·743)·시트 고리(pipeline 241)·후처리 suppress(pipeline 265·275)·출력 짓기(pipeline 299)·지오코더와
도시 이름 LLM(distance 130)·거리 재기(travel 229·271)·단위 환산 LLM(energy 703·732).
soft limit 은 시험 안 가짜 클래스로 짓는다 — soft_deadline_in 은 조상 클래스의 **이름**으로 가른다. 대조로 같은 자리의
보통 예외(ValueError·TranslateFailed)는 판별이 없을 때(BASE)와 같은 값이 된다.
글·계수는 전부 지은 것(inventory 시험 고정물), 공급사는 모의다.
"""

import dataclasses
from collections.abc import Callable, Sequence
from typing import Any

import pytest

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import LlmResult
from esgapi.inventory.engines.scope3.colab_157 import energy, output_files, pipeline, travel
from esgapi.inventory.engines.scope3.colab_157.distance import DistanceRun, estimate_straight_distance
from esgapi.inventory.engines.scope3.colab_157.energy import EnergyConversion
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, FailedSheet, run
from esgapi.inventory.engines.scope3.colab_157.ports import Coordinates, LlmGateway, NotFound
from esgapi.inventory.engines.scope3.colab_157.purchase import NAICS_PROMPT, TranslateFailed
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.engines.scope3.colab_157.travel import TravelCalc
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    FakeGeocoder,
    activity_factor_sheets,
    annual,
    c14_sheet,
    commute_sheet,
    energy_factor_sheets,
    llm_context,
    sheet,
    transport_ef_sheet,
    travel_ef_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS, book, replies
from esgapi.inventory.tests.engines.scope3.colab_157.test_travel import Ctx, trip
from esgapi.inventory.tests.flows.test_scope3_colab_157 import TEMPLATE
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet, Workbook
from esgapi.inventory.tools.xlsx_reader import read_workbook


class SoftTimeLimitExceeded(Exception):
    """시험의 가짜 Celery soft limit(이름만 같다)."""


def soft() -> SoftTimeLimitExceeded:
    return SoftTimeLimitExceeded("가상 시간 제한")


def raising(error: BaseException) -> Callable[..., Any]:
    """부르면 error 를 내는 대역."""

    def stand_in(*_args: object, **_kwargs: object) -> Any:
        raise error

    return stand_in


def guarded(context: LlmContext) -> LlmContext:
    """흐름이 주입하는 판별을 단 엔진 문맥."""
    return dataclasses.replace(context, reraise=colab._soft_deadline)  # pyright: ignore[reportPrivateUsage]


# ── 번역 LLM(purchase 598 → 743 → 시트 고리 241) — 흐름 단계째 ──


class FailingOnPrompt:
    """LlmGateway 를 감싸, `prompt` 의 k 번째 부름에서 error 를 낸다(그 앞뒤는 안쪽 그대로). `product` 를 주면 순번
    대신 그 품목 글(vars 의 product)의 부름마다 낸다(결정적 — 카테고리 단계가 앞 단계를 되감으며 같은 요청을 다시
    부르므로 순번 가짜는 시도·단계마다 다른 자리에서 던진다. 일지는 게이트웨이 예외를 적지 않는다 — 밴드 S3R1)."""

    def __init__(
        self, inner: LlmGateway, prompt: str, error: BaseException, k: int = 1, product: str | None = None
    ) -> None:
        self.inner = inner
        self.prompt = prompt
        self.error = error
        self.k = k
        self.product = product
        self.seen = 0
        self.raised = 0

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        if request.prompt == self.prompt:
            self.seen += 1
            if (self.product is not None and request.vars.get("product") == self.product) or (
                self.product is None and self.seen == self.k
            ):
                self.raised += 1
                raise self.error
        return self.inner.call(request)


def flow_on(llm: LlmGateway) -> dict[str, object]:
    inputs = colab.ColabInputs(template=xlsx_bytes(TEMPLATE), report_year=2025, route=ROUTE, tags=TAGS)
    adapters = colab.ColabAdapters(llm=llm, factor_book=book(), geocoder=FakeGeocoder())
    (only,) = run_flow(colab.FLOW, inputs, adapters).output.results
    return only


def test_a_soft_limit_in_the_translation_leaves_the_flow() -> None:
    """(a) 번역 부름의 soft limit 은 598·743·241 어디서도 삼켜지지 않고 흐름 단계 밖으로 나간다."""
    error = soft()
    llm = FailingOnPrompt(mock_client(replies()), NAICS_PROMPT, error, k=2)
    with pytest.raises(FlowStepFailed) as raised:
        flow_on(llm)
    assert raised.value.step == "c1"  # 번역 부름은 C1 시트 — 카테고리 단계 c1(S3R1)
    # 실행기 outcome_of 가 보는 자리(바로 위 한 겹) — 다른 예외로 싸서 던지면 미뤄지지 않는다
    assert raised.value.__cause__ is error
    assert soft_deadline_in(raised.value) is error
    assert llm.seen == 2


# 순번 가짜(k=2)였던 자리의 품목 — BASE 엔진의 NAICS 둘째 부름(C1 「가상 무엇」 줄)
SECOND_NAICS_PRODUCT = "가상 무엇 가상 무엇 가상 무엇"


@pytest.mark.parametrize("error", [ValueError("가상 값 오류"), TranslateFailed("가상")], ids=["value", "translate"])
def test_a_plain_error_in_the_translation_is_still_an_empty_generic_english(error: Exception) -> None:
    """(b) 보통 예외는 BASE 그대로 `generic_english = ""` — 실행은 끝까지 가고, 판별 없는 엔진 run 과 결과가 같다."""
    failing = FailingOnPrompt(mock_client(replies()), NAICS_PROMPT, error, product=SECOND_NAICS_PRODUCT)
    flowed = flow_on(failing)
    read = read_workbook(xlsx_bytes(TEMPLATE))
    assert isinstance(read, Workbook)
    llm = FailingOnPrompt(mock_client(replies()), NAICS_PROMPT, error, product=SECOND_NAICS_PRODUCT)
    direct = run(read, book(), 2025, llm, FakeGeocoder(), TAGS, ROUTE)
    assert isinstance(direct, ColabRun)
    assert flowed == result_to_dict(direct, colab.RESULT_SHAPE)
    assert flowed["status"] == "done"
    assert all(not isinstance(o, FailedSheet) for o in direct.sheets)
    # 고정물이 실제로 던졌다(없는 품목 글이면 0 — 검증 권고 R1): 엔진 한 번 1, 흐름은 c1·c2·assemble 이 되감으며 3
    assert (llm.raised, failing.raised) == (1, 3)


# ── 시트 고리(pipeline 241)·후처리(265·275)·출력 짓기(299) — 엔진 run ──


def run_on(template: Sequence[Sheet], *, guard: bool = True) -> ColabRun:
    factors = workbook(
        sheet("구매_USEPA", BOOK_ROWS), *activity_factor_sheets(), transport_ef_sheet(), travel_ef_sheet(),
        *energy_factor_sheets(),
    )  # fmt: skip
    reraise = colab._soft_deadline if guard else None  # pyright: ignore[reportPrivateUsage]
    result = run(
        workbook(*template), factors, 2025, mock_client(MockProvider()), FakeGeocoder(), TAGS, ROUTE, reraise=reraise
    )
    assert isinstance(result, ColabRun)
    return result


def commute_and_franchise() -> list[Sheet]:
    commute = commute_sheet(
        "c7_임직원통근", annual(["가상국", "가상사업장", "가상승용차", 9, "가상시카", "가상시타", None], 99)
    )
    return [commute, c14_sheet()]


@pytest.mark.parametrize(
    "name",
    ["process_activity_sheet", "process_product_sheet", "postprocess_category", "postprocess_product_category",
     "build_outputs"],
)  # fmt: skip
def test_a_soft_limit_in_the_pipeline_leaves_run(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """(c) 시트 고리(241 — 활동·제품 시트)·후처리 둘(275·265)·출력 짓기(299): soft limit 은 run 밖으로 나간다."""
    error = soft()
    monkeypatch.setattr(pipeline, name, raising(error))
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        run_on(commute_and_franchise())
    assert raised.value is error


def test_a_plain_error_in_the_sheet_loop_is_still_a_failed_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    """(c) 보통 예외는 BASE 그대로 FailedSheet 로 적고 다음 시트로 간다."""
    monkeypatch.setattr(pipeline, "process_activity_sheet", raising(ValueError("가상 값 오류")))
    result = run_on(commute_and_franchise())
    statuses = [(o.sheet, o.status) for o in result.sheets]
    assert statuses == [("c7_임직원통근", "failed"), ("c14_프랜차이즈", "processed")]
    failed = result.sheets[0]
    assert isinstance(failed, FailedSheet) and failed.error == "ValueError: 가상 값 오류"


def test_a_soft_limit_while_standardizing_for_the_filled_template_leaves_run(monkeypatch: pytest.MonkeyPatch) -> None:
    """출력 짓기 안쪽(output_files 695 — 채운 템플릿의 다시 표준화, 단위 환산 LLM 길)의 soft limit 도 run 밖으로."""
    error = soft()
    monkeypatch.setattr(output_files, "standardize_for_cursor", raising(error))
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        run_on(commute_and_franchise())
    assert raised.value is error


def test_a_plain_error_while_standardizing_is_still_standardize_failed(monkeypatch: pytest.MonkeyPatch) -> None:
    """보통 예외는 BASE 그대로 그 시트를 standardize_failed 로 적고, 판별이 없을 때와 결과가 같다."""
    monkeypatch.setattr(output_files, "standardize_for_cursor", raising(ValueError("가상 값 오류")))
    with_guard = run_on(commute_and_franchise())
    assert repr(with_guard) == repr(run_on(commute_and_franchise(), guard=False))
    assert isinstance(with_guard.outputs, output_files.OutputFiles)
    assert {f.status for f in with_guard.outputs.filled_sheets} == {"standardize_failed"}


@pytest.mark.parametrize("name", ["postprocess_category", "postprocess_product_category", "build_outputs"])
def test_a_plain_error_after_the_loop_is_as_without_the_guard(monkeypatch: pytest.MonkeyPatch, name: str) -> None:
    """후처리·출력 짓기의 보통 예외는 판별이 없을 때(BASE)와 같은 결과(후처리 실패 → 처리 때 값, 출력 실패 갈래)."""
    monkeypatch.setattr(pipeline, name, raising(ValueError("가상 값 오류")))
    with_guard = run_on(commute_and_franchise())
    without = run_on(commute_and_franchise(), guard=False)
    assert repr(with_guard) == repr(without)


# ── 지오코더·도시 이름 LLM(distance 130) ──


class RaisingGeocoder:
    def __init__(self, error: BaseException) -> None:
        self.error = error

    def geocode(self, query: str) -> Coordinates | NotFound:
        raise self.error


def straight(error: BaseException, *, guard: bool = True) -> float | None:
    context = llm_context(MockProvider().enqueue_text("A").enqueue_text("B"))
    distances = DistanceRun(RaisingGeocoder(error), guarded(context) if guard else context)
    return estimate_straight_distance(distances, "가상시가", "가상시다", "KR")


def test_a_soft_limit_in_the_geocoder_leaves_the_straight_distance() -> None:
    error = soft()
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        straight(error)
    assert raised.value is error


def test_a_plain_geocoder_error_is_still_none() -> None:
    assert straight(ValueError("가상 값 오류")) is None
    assert straight(ValueError("가상 값 오류"), guard=False) is None


# ── 거리 재기(travel 229 출장·271 통근) ──


def measured(monkeypatch: pytest.MonkeyPatch, error: BaseException, which: str, *, guard: bool = True) -> TravelCalc:
    monkeypatch.setattr(travel, "_measure", raising(error))
    ctx = Ctx()
    if guard:
        ctx.context = guarded(ctx.context)
    values = trip("가상버스")
    return ctx.business(values) if which == "business" else ctx.commute({**values, "교통수단": "가상버스"})


@pytest.mark.parametrize("which", ["business", "commute"])
def test_a_soft_limit_while_measuring_leaves_the_travel_calc(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    error = soft()
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        measured(monkeypatch, error, which)
    assert raised.value is error


@pytest.mark.parametrize("which", ["business", "commute"])
def test_a_plain_error_while_measuring_is_still_no_distance(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    plain = measured(monkeypatch, ValueError("가상 값 오류"), which)
    assert plain == measured(monkeypatch, ValueError("가상 값 오류"), which, guard=False)
    assert plain.distance_km is None and plain.distance_via == "none"


# ── 단위 환산 LLM(energy 703 patch·732 fix) ──

CONVERSIONS = {"patch": energy.patch_convert_energy_to_ef_unit, "fix": energy.fix_convert_to_ef_unit}


def converted(
    monkeypatch: pytest.MonkeyPatch, error: BaseException, which: str, *, guard: bool = True
) -> EnergyConversion:
    monkeypatch.setattr(energy, "convert_energy_unit", raising(error))
    context = llm_context(MockProvider())
    return CONVERSIONS[which](guarded(context) if guard else context, UnitFactorCache(), 9.0, "L", "경유", "kg")


@pytest.mark.parametrize("which", list(CONVERSIONS))
def test_a_soft_limit_in_the_unit_conversion_leaves(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    error = soft()
    with pytest.raises(SoftTimeLimitExceeded) as raised:
        converted(monkeypatch, error, which)
    assert raised.value is error


@pytest.mark.parametrize("which", list(CONVERSIONS))
def test_a_plain_error_in_the_unit_conversion_is_the_fallback(monkeypatch: pytest.MonkeyPatch, which: str) -> None:
    plain = converted(monkeypatch, ValueError("가상 값 오류"), which)
    assert plain == converted(monkeypatch, ValueError("가상 값 오류"), which, guard=False)
    assert plain.via == "none"
