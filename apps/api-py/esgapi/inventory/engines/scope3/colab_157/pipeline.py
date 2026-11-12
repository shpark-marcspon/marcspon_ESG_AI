"""엔진 판의 바깥 입구 `run` — 코랩 `run_scope3_pipeline`(`:9476`) → `process_template_inventory`(`:6377`)
→ `process_new_template`(`:8916` 감쌈 → `:5898`)의 C1·C2 몫.

    run(template, factor_book, report_year, llm, geocoder, tags, route) -> ColabRun | ColabRejected

- 셈 전부는 `pdcompat.legacy_strings()` 안에서 돈다(pandas 2.x 의 글 열 추론 — 경계 ② 검증 N1). 코랩이 돈 2.x 처럼
  글 열이 object 다(pandas 3.0.6 기본 문맥의 `str` 열은 수를 받지 않는다).
- 실행을 멈추는 것은 둘이다: 계수 책에서 셀 9 의 `spend_db` 를 못 지음(코랩은 노트북을 열 때 그 셀에서 멈춘다)과
  새 v1 템플릿이 아님(옛 테마 라우터는 옮기지 않았다 — 「코랩과 다른 자리」). 나머지는 시트의 갈래다: 코랩은 시트
  실패를 `print` 하고 넘어간다(`:6199`) — 여기서는 `FailedSheet` 로 남긴다.
- 시트 대응은 `template.match_sheet_processor`(21키). 처리하는 것은 `SUPPORTED_KEYS` 스물하나 전부(C1·C2 = purchase.py,
  C4-2·C9-2·C6-2·C5 = activity.py — S3C-b1, C4-1·C9-1 = activity.py·transport.py·distance.py — S3C-b2a,
  C6-1·C7 = activity.py·travel.py — S3C-b2b, C3·C8 셋·C13 셋 = energy.py — S3C-c1a, C12·C15 = product.py —
  S3C-c1b-1, C11·C14 = product.py — S3C-c1b-2). `NotYetSupportedSheet` 는 남지 않는다(갈래는 그대로 둔다).
- 계수 시트 여덟(운송_Spend·출장_Spend·폐기물_C5, 거리 운송 계수 `운송` — S3C-b2a, 출장·통근 계수 `출장_통근` —
  S3C-b2b, 에너지 계수 `에너지`·`에너지_C3` — S3C-c1a, C12 계수 `폐기물_C12` — S3C-c1b-1, 이 차례)은 실행 머리에서
  읽는다(코랩이 노트북을 열 때 읽는 자리 — 시트가 없어도 실행은 멈추지 않는다, `factorSheets` 의 `empty`). 앞 넷과
  `에너지`·`폐기물_C12` 는 두 단, `출장_통근`·
  `에너지_C3` 은 첫 읽기만(맵 `:473` · `:9048`). `운송` 은 읽은 뒤 운송 계수 맵(`:7780`)을 짓는다(없으면 코랩 기본값
  다섯).
- 지오코더는 C4-1·C9-1·C6-1·C7 의 거리 길이 부른다(S3C-b2a·b2b — 실행 하나의 캐시, 못 찾음까지 기억).
- C6·C7·C11·C14 후처리(코랩 `_fix_result_c6`·`_fix_result_c7`·`standardize_c11_sheet` `:8720`·
  `_fix_result_energy_sheet` `:8862`)는 **시트 고리 뒤**에 결과 시트 차례(Category 첫 처리 시트) **하나**로 한다 —
  코랩이 결과 파일을 다 쓴 뒤 다시 읽어 고치는 차례(`_postprocess_scope3_result_file` `:8878`, 부름 `:8920`). 넷의 AI
  배수·이동수단 부름이 이 차례로 섞인다(S3C-c1b-2). C6 은 C6-1+C6-2 를 합친 줄 위에서(S3C-b2b, `ISSUE-193` 2).
  후처리 예외는 그 결과 시트를 본 고리(처리 때) 값으로 둔다(시트 상태는 processed 그대로).

S3C-o(코랩 대조 하네스)가 부르는 꼴이 이 `run` 이고, `ProcessedSheet.frame` 이 코랩 결과 시트(후처리 뒤, 코랩 열 이름 —
「진단 파일」 몫의 열을 빼기 전)와 견줄 frame 이다.
"""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Literal

import pandas as pd

from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.colab_157.activity import (
    ActivityMeta,
    ActivitySheet,
    EmptyActivitySheet,
    PendingPost,
    activity_run,
    postprocess_category,
    process_activity_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.energy import (
    EmptyEnergySheet,
    EnergyMeta,
    EnergyRun,
    process_energy_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    FactorSheetRead,
    SpendDbChoice,
    initial_spend_db,
    read_energy_c3_sheet,
    read_energy_sheet,
    read_waste_c12_sheet,
    reload_spend_db,
)
from esgapi.inventory.engines.scope3.colab_157.llm import LlmCalls, LlmContext, reraises
from esgapi.inventory.engines.scope3.colab_157.output_files import (
    OutputFiles,
    OutputsFailed,
    ProcessedPart,
    Runs,
    build_outputs,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.engines.scope3.colab_157.ports import Geocoder, LlmGateway
from esgapi.inventory.engines.scope3.colab_157.product import (
    EmptyProductSheet,
    ProductMeta,
    ProductPending,
    ProductRun,
    ProductSheet,
    postprocess_product_category,
    process_product_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.purchase import (
    EmptyPurchaseSheet,
    PurchaseRun,
    RowMeta,
    process_purchase_sheet,
    purchase_book,
)
from esgapi.inventory.engines.scope3.colab_157.template import SheetProcessor, is_new_template, match_sheet_processor
from esgapi.inventory.tools.scope3_sheets.grid import Workbook


@dataclass(frozen=True)
class ProcessedSheet:
    sheet: str
    processor: SheetProcessor
    frame: pd.DataFrame  # 코랩 결과 시트(후처리 뒤, 코랩 열 이름). metas 와 같은 차례
    metas: tuple[RowMeta, ...] | tuple[ActivityMeta, ...] | tuple[EnergyMeta, ...] | tuple[ProductMeta, ...]
    status: Literal["processed"] = "processed"


@dataclass(frozen=True)
class NotTargetSheet:
    """시트 이름이 21키 어디에도 닿지 않는다(코랩 `[skip] 처리 대상 시트 아님` — `:5962`)."""

    sheet: str
    status: Literal["not_target"] = "not_target"


@dataclass(frozen=True)
class NotYetSupportedSheet:
    """코랩은 처리하지만 이 판은 아직 옮기지 않은 시트(S3C-b·c)."""

    sheet: str
    processor: SheetProcessor
    status: Literal["not_yet_supported"] = "not_yet_supported"


@dataclass(frozen=True)
class EmptySheet:
    sheet: str
    processor: SheetProcessor
    status: Literal["empty"] = "empty"


@dataclass(frozen=True)
class FailedSheet:
    """시트를 읽거나 셈하다 예외가 났다(코랩 `[error] 시트: 예외` 후 다음 시트 — `:6199`)."""

    sheet: str
    processor: SheetProcessor
    error: str
    status: Literal["failed"] = "failed"


type SheetOutcome = ProcessedSheet | NotTargetSheet | NotYetSupportedSheet | EmptySheet | FailedSheet


@dataclass(frozen=True)
class ColabRun:
    report_year: int
    spend_db: SpendDbChoice
    sheets: tuple[SheetOutcome, ...]
    llm_calls: LlmCalls
    factor_sheets: tuple[FactorSheetRead, ...] = ()
    # 출력 파일 둘의 내용(S3C-c2 — output_files.py). 결과 dict(serialize.py)는 읽지 않는다. None 은 지어지지 않음
    outputs: OutputFiles | OutputsFailed | None = None
    kind: Literal["done"] = "done"


PURCHASE_KEYS: Final[frozenset[str]] = frozenset({"c1", "c2"})
ACTIVITY_KEYS: Final[frozenset[str]] = frozenset(
    {"c4_dist", "c4_spend", "c9_dist", "c9_spend", "c6_dist", "c6_spend", "c7", "c5"}
)
ENERGY_KEYS: Final[frozenset[str]] = frozenset(
    {"c3", "c8_energy", "c8_area", "c8_person", "c13_energy", "c13_area", "c13_person"}
)
PRODUCT_KEYS: Final[frozenset[str]] = frozenset({"c12", "c15"})
# 결과 후처리가 최종 값을 짓는 판매제품 사용·프랜차이즈(S3C-c1b-2 — product.py, 에너지 계수·AI 배수 캐시는 EnergyRun)
PRODUCT_POST_KEYS: Final[frozenset[str]] = frozenset({"c11", "c14"})
SUPPORTED_KEYS: Final[frozenset[str]] = PURCHASE_KEYS | ACTIVITY_KEYS | ENERGY_KEYS | PRODUCT_KEYS | PRODUCT_POST_KEYS

RejectKind = Literal["factor_book", "legacy_template"]


@dataclass(frozen=True)
class ColabRejected:
    reason: RejectKind
    detail: str
    kind: Literal["rejected"] = "rejected"


def run(
    template: Workbook,
    factor_book: Workbook,
    report_year: int,
    llm: LlmGateway,
    geocoder: Geocoder,
    tags: Tags,
    route: str,
    *,
    reraise: Callable[[BaseException], bool] | None = None,
) -> ColabRun | ColabRejected:
    """읽힌 템플릿·계수 책과 보고연도로 C1·C2 를 셈한다. 실제 호출은 포트(llm·geocoder) 뒤에만 있다.

    reraise 는 포트 길을 감싼 넓은 except 가 다시 던질지의 판별이다(S3L1, MARC-ISSUE-414 — 흐름이 Celery soft limit 으로
    짓는다). 참이면 그 예외는 시트 실패·실패 값으로 남지 않고 run 밖으로 나간다. None 이면 BASE 그대로.
    """
    with legacy_strings():
        return _run(template, factor_book, report_year, llm, geocoder, tags, route, reraise)


def _run(
    template: Workbook,
    factor_book: Workbook,
    report_year: int,
    llm: LlmGateway,
    geocoder: Geocoder,
    tags: Tags,
    route: str,
    reraise: Callable[[BaseException], bool] | None,
) -> ColabRun | ColabRejected:
    try:
        initial = initial_spend_db(factor_book)
    except Exception as error:  # 코랩 셀 9 가 노트북을 열 때 멈출 자리
        return ColabRejected("factor_book", f"{type(error).__name__}: {error}")
    if not is_new_template([sheet.name for sheet in template.sheets]):
        names = ", ".join(sheet.name for sheet in template.sheets)
        return ColabRejected("legacy_template", f"「c + 숫자」 로 시작하는 시트가 없다: {names}")

    choice = reload_spend_db(factor_book, report_year, initial)  # 실패하면 셀 9 의 것(SpendDbKeptInitial)
    book = purchase_book(choice.db, initial, report_year)  # FX_REFERENCE_YEAR 는 다시 짓기와 무관하게 보고연도(:5909)
    calls = LlmCalls()
    context = LlmContext(llm, route, tags, calls, reraise)
    purchase = PurchaseRun(book, context)
    activity = activity_run(
        factor_book, report_year, context, geocoder
    )  # 셀 8·25 의 계수 시트 다섯(FX_REFERENCE_YEAR = 보고연도)
    # 에너지 계수 시트 둘(셀 8 `:326` 첫 읽기 → 셀 25 `:7205` 다시 읽기, `에너지_C3` `:9048` 한 번)
    # — AI 배수 캐시는 C5 와 같은 것(따를 표 5)
    energy = EnergyRun(read_energy_sheet(factor_book), read_energy_c3_sheet(factor_book), context, activity.units)
    # C12 계수 시트(셀 8 `:342` 첫 읽기 → 셀 25 `:7219` 다시 읽기), 제품명 길은 C5 와 같은 `폐기물_C5`(`:653`·`:7215`)
    # C11·C14 는 C8·C13 과 같은 `에너지` 와 같은 AI 배수 캐시(따를 표 5)
    product = ProductRun(read_waste_c12_sheet(factor_book), activity.waste, energy)

    outcomes: list[SheetOutcome] = []
    # 후처리를 기다리는 C6·C7 시트: Category(첫 등장 차례 — 코랩 결과 시트 차례) → (outcomes 자리, 본 고리 줄)
    pending: dict[str, list[tuple[int, str, SheetProcessor, PendingPost]]] = {}
    # 후처리를 기다리는 C11·C14 시트(같은 꼴 — 처리 때 줄)
    product_pending: dict[str, list[tuple[int, str, SheetProcessor, ProductPending]]] = {}
    for sheet in template.sheets:
        processor = match_sheet_processor(sheet.name)
        if processor is None:
            outcomes.append(NotTargetSheet(sheet.name))
            continue
        if processor.key not in SUPPORTED_KEYS:
            outcomes.append(NotYetSupportedSheet(sheet.name, processor))
            continue
        try:
            if processor.key in PURCHASE_KEYS:
                done = process_purchase_sheet(purchase, sheet, processor.category)
            elif processor.key in ENERGY_KEYS:
                done = process_energy_sheet(energy, sheet, processor.key, processor.category)
            elif processor.key in PRODUCT_KEYS or processor.key in PRODUCT_POST_KEYS:
                done = process_product_sheet(product, sheet, processor.key, processor.category)
            else:
                done = process_activity_sheet(activity, template, sheet, processor.key, processor.category)
        except Exception as error:  # 코랩 `except Exception as e: print(f"  [error] {sheet_name}: {e}")`
            if reraises(context, error):
                raise
            outcomes.append(FailedSheet(sheet.name, processor, f"{type(error).__name__}: {error}"))
            continue
        if isinstance(done, EmptyPurchaseSheet | EmptyActivitySheet | EmptyEnergySheet | EmptyProductSheet):
            outcomes.append(EmptySheet(sheet.name, processor))
        else:
            if isinstance(done, ActivitySheet) and done.pending is not None:
                waiting = (len(outcomes), sheet.name, processor, done.pending)
                pending.setdefault(done.pending.category, []).append(waiting)
            elif isinstance(done, ProductSheet) and done.pending is not None:
                product_pending.setdefault(done.pending.category, []).append(
                    (len(outcomes), sheet.name, processor, done.pending)
                )
            outcomes.append(ProcessedSheet(sheet.name, processor, done.frame, done.metas))
    # 코랩 후처리(`:8920` — 감싼 `process_new_template` 이 시트를 다 돈 뒤): 결과 시트(C6_·C7_·C11_·C14_)마다 합친
    # 줄로, 결과 파일의 시트 차례(코랩 `results` 에 Category 가 처음 들어간 차례 = 첫 처리 시트)로 한 번(`:8887`)
    order = [o.processor.category for o in outcomes if isinstance(o, ProcessedSheet)]
    before = {index: p.rows for posts in pending.values() for index, *_, p in posts}
    before.update({index: p.rows for posts in product_pending.values() for index, *_, p in posts})
    post_failed: set[str] = set()  # 후처리 예외가 난 Category(코랩 `:8903-8905` — 결과 파일은 다시 읽은 그대로)
    for category in dict.fromkeys(c for c in order if c in pending or c in product_pending):
        if category in product_pending:
            posts = product_pending[category]
            fixed_products: tuple[ProductSheet, ...] | None = None  # None = 예외(빈 튜플은 예외가 아니다)
            try:  # 코랩 `[경고] … 후처리 실패` → 처리 때 값(`:8903-8905`)
                fixed_products = postprocess_product_category(product, category, [p for *_, p in posts])
            except Exception as error:
                if reraises(context, error):
                    raise
            if fixed_products is None:
                post_failed.add(category)
            for (index, name, processor, _), done in zip(posts, fixed_products or (), strict=False):
                outcomes[index] = ProcessedSheet(name, processor, done.frame, done.metas)
            continue
        waiting = pending[category]
        fixed: tuple[ActivitySheet, ...] | None = None  # None = 예외(빈 튜플은 예외가 아니다 — S3C-c2 검증 권고 2)
        # 코랩 `[경고] … 후처리 실패` → 그 결과 시트는 후처리 전 값(`:8903-8905`) — 시트 상태는 processed 그대로
        try:
            fixed = postprocess_category(activity, category, [p for *_, p in waiting])
        except Exception as error:
            if reraises(context, error):
                raise
        if fixed is None:
            post_failed.add(category)
        for (index, name, processor, _), done in zip(waiting, fixed or (), strict=False):
            outcomes[index] = ProcessedSheet(name, processor, done.frame, done.metas)
    sheets = (
        activity.transport,
        activity.travel,
        activity.waste,
        activity.transport_distance,
        activity.travel_commute,
        energy.energy,
        energy.energy_c3,
        product.waste_c12,
    )
    parts = [
        ProcessedPart(o.sheet, o.processor, o.frame, tuple(o.metas), before.get(index))
        for index, o in enumerate(outcomes)
        if isinstance(o, ProcessedSheet)
    ]
    outputs: OutputFiles | OutputsFailed
    try:  # 코랩은 이 자리에서 실행이 죽는다 — 여기서는 시트 결과를 지키고 갈래로 남긴다(「코랩과 다른 자리」)
        outputs = build_outputs(template, parts, frozenset(post_failed), Runs(activity, energy))
    except Exception as error:
        if reraises(context, error):
            raise
        outputs = OutputsFailed(f"{type(error).__name__}: {error}")
    return ColabRun(report_year, choice, tuple(outcomes), calls, sheets, outputs)
