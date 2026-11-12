"""지출·폐기물 줄(C4-2·C9-2·C6-2·C5)과 거리 줄(C4-1·C9-1 — S3C-b2a, C6-1·C7 — S3C-b2b)의 줄 메타와 산정 출처, 월 합
도우미, C6·C7 후처리(`postprocess_category` — 시트 고리 뒤에 pipeline 이 부른다).

산정 출처(사용자 방향 「결과에 산정 출처 칸」, 발주서 2-5 — 코랩에는 없다, 값은 바꾸지 않는다):
    mapping(회사별 매핑이 그 줄을 채움) → rule · unit(C5) rule/ai/none → rule/ai/estimate
    fx(USD 갈래만) fx_month·fx_annual → rule, fx_default_1400 → estimate
    factor 운송 keyword·korean_name·title(+:expanded/:raw) → rule, default_title → estimate
    factor 출장 manual·scored → rule
    factor 폐기물 exact·partial·keyword·any_treatment → rule, treatment_average → estimate
    mode(C6) rule_fix·rule → rule, ai → ai, default_car → estimate
  거리 줄(S3C-b2a 2-6):
    unit(무게) rule → rule, ai → ai, ai_failed(1배) → estimate, 「화물중량(kg)」 입력이면 단계 없음
    mode(운송) template_alias·column·keyword·geo → rule, ai → ai, fallback → estimate
    distance input·geocode → rule, ai_*(+airport) → ai, 공항 AI 로 바꾼 geocode(+airport) → ai, none → 단계 없음
    factor(운송) db → rule, default → estimate
  출장·통근 거리 줄(S3C-b2b 2-2): mode 는 C6 과 같은 이동수단 규칙, distance 는 위와 같고 통근 100 km 갈음
    `commute_ai_check` → ai, factor(출장_통근) db·bus_subway_avg → rule, default·car_fallback(C6 `or car`) → estimate
줄 `origin` = 숫자에 닿는 단계 가운데 가장 약한 것(estimate > ai > rule), factor 단계가 없으면 None. 숫자에 닿는 단계는
kind 별이다: 지출·폐기물 kind 는 mapping·unit·fx·factor — mode 는 정규화이동수단 칸에만 닿아 넣지 않는다(감독 판단 3),
거리 kind(`transport_distance`·`travel_distance`·`commute`)는 거기에 mode·distance 를 더한다(운송수단이 계수를, 거리가
배출량을 정한다 — S3C-b2a 감독 처분 1).
"""

import math
import numbers
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.company_mapping import fill_missing_from_company_mapping
from esgapi.inventory.engines.scope3.colab_157.distance import DistanceRun, get_distance_km
from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    TRANSPORT_SHEET,
    TRANSPORT_SPEND_SHEET,
    TRAVEL_SHEET,
    TRAVEL_SPEND_SHEET,
    WASTE_C5_SHEET,
    FactorSheetRead,
    read_factor_sheet,
    read_initial_factor_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_loc_set
from esgapi.inventory.engines.scope3.colab_157.ports import Geocoder, NoGeocoder
from esgapi.inventory.engines.scope3.colab_157.purchase import (
    ColabOrigin,
    coerce_month_value,
    fix_num,
    fix_text,
    to_float,
)
from esgapi.inventory.engines.scope3.colab_157.spend import (
    FxVia,
    SpendCalc,
    calc_transport_spend_emission,
    calc_travel_spend_emission,
    standardize_c4_spend_sheet,
    standardize_c6_spend_sheet,
    standardize_c9_spend_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.template import (
    PURCHASE_WIDE_MONTH_COLS,
    TEMPLATE_ROW,
    read_template_rows,
    sum_monthly_spend,
)
from esgapi.inventory.engines.scope3.colab_157.transport import (
    TRANSPORT_EF_UNIT,
    TransportCalc,
    TransportEfMap,
    TransportModeCache,
    TransportModeVia,
    WeightConversion,
    WeightVia,
    calc_transport,
    patch_pick_first,
    patch_safe_text,
    patch_to_float,
    refresh_transport_ef_map,
    standardize_c4_dist_sheet,
    standardize_c9_dist_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.travel import (
    TRAVEL_EF_UNIT,
    TravelCalc,
    TravelEfMap,
    TravelEfVia,
    build_travel_ef_map,
    calc_business_travel,
    calc_commute,
    commute_formula,
    fix_c6_distance,
    normalize_commute_mode,
    standardize_c6_dist_sheet,
    standardize_c7_sheet,
)
from esgapi.inventory.engines.scope3.colab_157.travel_mode import (
    ModeVia,
    TravelMode,
    TravelModeCache,
    normalize_travel_mode,
)
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache, UnitVia
from esgapi.inventory.engines.scope3.colab_157.waste import WasteCalc, calc_waste_row, standardize_c5_sheet
from esgapi.inventory.tools.scope3_sheets.grid import Sheet, Workbook

ColabActivityKind = Literal[
    "transport_spend", "travel_spend", "waste", "transport_distance", "travel_distance", "commute"
]
ColabActivityStep = Literal["mapping", "unit", "fx", "factor", "mode", "distance"]

_STRENGTH: Final[dict[ColabOrigin, int]] = {"rule": 0, "ai": 1, "estimate": 2}
_UNIT_ORIGIN: Final[dict[UnitVia, ColabOrigin]] = {"rule": "rule", "ai": "ai", "none": "estimate"}
_MODE_ORIGIN: Final[dict[ModeVia, ColabOrigin]] = {
    "rule_fix": "rule",
    "rule": "rule",
    "ai": "ai",
    "default_car": "estimate",
}
_WEIGHT_ORIGIN: Final[dict[WeightVia, ColabOrigin]] = {"rule": "rule", "ai": "ai", "ai_failed": "estimate"}
_TRANSPORT_MODE_ORIGIN: Final[dict[TransportModeVia, ColabOrigin]] = {
    "template_alias": "rule",
    "column": "rule",
    "keyword": "rule",
    "geo": "rule",
    "ai": "ai",
    "fallback": "estimate",
}
_NUMERIC_STEPS: Final[frozenset[ColabActivityStep]] = frozenset({"mapping", "unit", "fx", "factor"})
DISTANCE_KINDS: Final[frozenset[ColabActivityKind]] = frozenset({"transport_distance", "travel_distance", "commute"})
_DISTANCE_NUMERIC_STEPS: Final[frozenset[ColabActivityStep]] = frozenset(
    {"mapping", "unit", "fx", "factor", "mode", "distance"}
)


@dataclass(frozen=True)
class ActivityOriginStep:
    step: ColabActivityStep
    origin: ColabOrigin
    via: str


def mapping_step() -> ActivityOriginStep:
    return ActivityOriginStep("mapping", "rule", "company_mapping")


def unit_step(via: UnitVia) -> ActivityOriginStep:
    return ActivityOriginStep("unit", _UNIT_ORIGIN[via], via)


def fx_step(via: FxVia) -> ActivityOriginStep:
    return ActivityOriginStep("fx", "estimate" if via == "fx_default_1400" else "rule", via)


def transport_factor_step(via: str) -> ActivityOriginStep:
    return ActivityOriginStep("factor", "estimate" if via.startswith("default_title") else "rule", via)


def travel_factor_step(via: str) -> ActivityOriginStep:
    return ActivityOriginStep("factor", "rule", via)


def waste_factor_step(via: str) -> ActivityOriginStep:
    return ActivityOriginStep("factor", "estimate" if via == "treatment_average" else "rule", via)


def mode_step(via: ModeVia) -> ActivityOriginStep:
    return ActivityOriginStep("mode", _MODE_ORIGIN[via], via)


def weight_step(via: WeightVia) -> ActivityOriginStep:
    return ActivityOriginStep("unit", _WEIGHT_ORIGIN[via], via)


def transport_mode_step(via: TransportModeVia) -> ActivityOriginStep:
    return ActivityOriginStep("mode", _TRANSPORT_MODE_ORIGIN[via], via)


def distance_step(via: str) -> ActivityOriginStep | None:
    """거리의 길 → 단계. `none`(거리 없음)이면 단계 없음. 공항 AI 로 지점을 바꿨으면(`+airport`) 적어도 ai."""
    base, _, rest = via.partition("+")
    if base == "none":
        return None
    origin: ColabOrigin = "rule" if base in ("input", "geocode") and not rest else "ai"
    return ActivityOriginStep("distance", origin, via)


def transport_ef_step(via: str) -> ActivityOriginStep:
    return ActivityOriginStep("factor", "estimate" if via == "default" else "rule", via)


def travel_ef_step(via: TravelEfVia) -> ActivityOriginStep:
    return ActivityOriginStep("factor", "estimate" if via in ("default", "car_fallback") else "rule", via)


def numeric_steps(kind: ColabActivityKind) -> frozenset[ColabActivityStep]:
    """줄 origin 에 넣는 단계(kind 별 — 거리 kind 만 mode·distance 를 더한다)."""
    return _DISTANCE_NUMERIC_STEPS if kind in DISTANCE_KINDS else _NUMERIC_STEPS


def row_origin(steps: tuple[ActivityOriginStep, ...], kind: ColabActivityKind) -> ColabOrigin | None:
    """숫자에 닿는 단계 가운데 가장 약한 출처. factor 단계가 없으면 None."""
    if not any(s.step == "factor" for s in steps):
        return None
    counted = numeric_steps(kind)
    numeric: list[ColabOrigin] = [s.origin for s in steps if s.step in counted]
    return max(numeric, key=_STRENGTH.__getitem__)


@dataclass(frozen=True)
class ActivityAmount:
    """활동량: Spend 는 금액(KRW), 폐기물은 처리량(입력 단위)과 kg 값·단위환산비고."""

    value: float | None
    unit: str
    base_value: float | None
    base_unit: str
    note: str | None


@dataclass(frozen=True)
class ActivityFactor:
    sheet: str
    title: str | None
    value: float | None
    unit: str
    column: str | None
    code: str | None


@dataclass(frozen=True)
class ActivityBiogenic:
    fossil: float | None
    biogenic: float | None
    fcf: float | None
    note: str | None


@dataclass(frozen=True)
class ActivityMode:
    value: str
    origin: ColabOrigin


@dataclass(frozen=True)
class ActivityDistance:
    """거리 줄의 거리(S3C-b2a 2-5). `km` 는 셈에 쓴 거리(두 번째 길 포함) — 코랩 결과 칸 「운송거리(km)」 와 다를 수
    있다.

    `geo_mode` 는 거리 길에 넘긴 mode(템플릿 입력 거리면 None). `round_trip`·`people`·`trips`·`workdays` 는 C6-1·C7 몫
    (S3C-b2b) — C4-1·C9-1 은 None.
    """

    km: float | None
    via: str
    geo_mode: str | None
    departure: str | None
    arrival: str | None
    round_trip: float | None = None
    people: float | None = None
    trips: float | None = None
    workdays: float | None = None


@dataclass(frozen=True)
class ActivityMeta:
    """코랩 결과 행에는 없는 것: 입력 줄, 활동량·계수의 출처, 처리방법·생물기원·이동수단·거리, 산정 출처 단계."""

    excel_row: int | None
    kind: ColabActivityKind
    month: int | None
    activity: ActivityAmount
    factor: ActivityFactor
    treatment: str | None
    biogenic: ActivityBiogenic | None
    mode: ActivityMode | None
    steps: tuple[ActivityOriginStep, ...]
    distance: ActivityDistance | None = None  # 거리 kind 만(S3C-b2a)

    @property
    def origin(self) -> ColabOrigin | None:
        return row_origin(self.steps, self.kind)


def sum_monthly(df: pd.DataFrame, value_col: str, month_cols_in_df: list[str]) -> pd.DataFrame:
    """코랩 `process_new_template` 안의 `_sum_monthly`(`:5928-5945`): 「월별」 줄의 1월~12월 합을 value_col 에."""
    df = df.copy()
    if not month_cols_in_df:
        return df
    input_type: pd.Series[Any] = df["입력방식"] if "입력방식" in df.columns else pd.Series("연간", index=df.index)
    monthly_mask = (input_type == "월별").astype(bool)
    if bool(monthly_mask.any()):
        monthly_sum = df.loc[monthly_mask, month_cols_in_df].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        if value_col not in df.columns:
            df[value_col] = None
        colab_loc_set(df, monthly_mask, value_col, monthly_sum.where(monthly_sum > 0, other=None))
    return df


# ── S3C-b1 경계 ②: 시트 입구(코랩 `process_new_template` `:5966-6147` 의 Category4·9·6·5 갈래 + C6 후처리 `:8821`) ──

WASTE_MAPPING_SHEET: Final = "회사별_폐기물매핑"  # 코랩 :5978
TRAVEL_MAPPING_SHEET: Final = "회사별_교통수단매핑"  # 코랩 :5983
# 코랩 :6223-6234 — 결과 파일에서 지우는 열(C6 후처리가 다시 읽는 파일에는 없다)
COLS_TO_DROP: Final[frozenset[str]] = frozenset(
    {
        "입력통화", "환율기준연도", "환율적용월", "적용환율(원/USD)", "원화환산금액", "EF적용금액(USD)", "환율적용여부",
        "EF(kgCO2e/USD)", "NAICS", "NAICS_Title", "Spend방식", "적용환율(KRW/USD)", "USD환산금액",
        "자동카테고리", "출처시트", *[f"{i}월" for i in range(1, 13)],
    }
)  # fmt: skip


def _empty_sheet(name: str) -> FactorSheetRead:
    return FactorSheetRead(name, pd.DataFrame(), "empty", None)


@dataclass
class ActivityRun:
    """실행 하나의 지출·폐기물·거리 상태(코랩 전역 계수 시트·`TRANSPORT_EF_MAP`·`FX_REFERENCE_YEAR`·lru_cache).

    거리 몫(S3C-b2a)은 기본값 필드다: 운송 계수 시트(`운송`)와 그것으로 지은 운송 계수 맵(`:7780` 의
    `refresh_transport_ef_map`), 지오코더와 거리 캐시 다섯(`DistanceRun`), 운송수단 AI 캐시. 무게 AI 배수는 C5 와 같은
    `units` 캐시다(코랩 lru_cache 하나). 출장·통근(S3C-b2b)은 계수 시트 `출장_통근`(첫 읽기만)과 그 맵이고, 이동수단
    AI 캐시는 C6-2 와 같은 `modes` 다.
    """

    year: int
    transport: FactorSheetRead
    travel: FactorSheetRead
    waste: FactorSheetRead
    llm: LlmContext
    units: UnitFactorCache = field(default_factory=UnitFactorCache)
    modes: TravelModeCache = field(default_factory=TravelModeCache)
    transport_distance: FactorSheetRead = field(default_factory=lambda: _empty_sheet(TRANSPORT_SHEET))
    geocoder: Geocoder = field(default_factory=NoGeocoder)
    transport_modes: TransportModeCache = field(default_factory=TransportModeCache)
    travel_commute: FactorSheetRead = field(default_factory=lambda: _empty_sheet(TRAVEL_SHEET))
    ef_map: TransportEfMap = field(init=False)
    travel_ef: TravelEfMap = field(init=False)
    distances: DistanceRun = field(init=False)

    def __post_init__(self) -> None:
        self.ef_map = refresh_transport_ef_map(self.transport_distance)
        self.travel_ef = build_travel_ef_map(self.travel_commute)  # 코랩 :473 — 첫 읽기로 한 번(S3C-b2b)
        self.distances = DistanceRun(self.geocoder, self.llm)


def activity_run(book: Workbook, year: int, llm: LlmContext, geocoder: Geocoder) -> ActivityRun:
    return ActivityRun(
        year,
        read_factor_sheet(book, TRANSPORT_SPEND_SHEET),
        read_factor_sheet(book, TRAVEL_SPEND_SHEET),
        read_factor_sheet(book, WASTE_C5_SHEET),
        llm,
        transport_distance=read_factor_sheet(book, TRANSPORT_SHEET),
        geocoder=geocoder,
        travel_commute=read_initial_factor_sheet(book, TRAVEL_SHEET),
    )


@dataclass(frozen=True)
class TravelLoopRow:
    """C6·C7 본 고리 줄 하나 — 후처리가 다시 셀 때 쓴다. `calc` 는 거리 줄(C6-1·C7)의 본 고리 셈(지출 줄은 None)."""

    mapped: bool
    calc: TravelCalc | None


@dataclass(frozen=True)
class PendingPost:
    """후처리를 기다리는 C6·C7 시트: 본 고리 줄(코랩 열 이름 dict — 후처리는 고친 사본을 낸다)과 줄마다 셈."""

    category: str
    rows: tuple[dict[str, object], ...]
    loop: tuple[TravelLoopRow, ...]


@dataclass(frozen=True)
class ActivitySheet:
    """C6·C7 이면 `metas` 는 본 고리 값의 메타다(후처리가 실패하면 그대로 남는다 — 코랩 `:8903-8905`)."""

    frame: pd.DataFrame
    metas: tuple[ActivityMeta, ...]
    pending: PendingPost | None = None


@dataclass(frozen=True)
class EmptyActivitySheet:
    """`read_template_sheet` 가 빈 frame 을 냈다(코랩 `[empty]`)."""


def _excel_row(row: "pd.Series[Any]") -> int | None:
    value = row.get(TEMPLATE_ROW)
    return int(value) if isinstance(value, numbers.Integral) else None


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    f = float(value)
    return f if math.isfinite(f) else None


def _text_or_none(value: object) -> str | None:
    s = fix_text(value)
    return s or None


def _spend_meta(
    kind: ColabActivityKind, row: "pd.Series[Any]", calc: SpendCalc, factor: FactorSheetRead, mapped: bool,
    mode: TravelMode | None,
) -> ActivityMeta:  # fmt: skip
    steps: list[ActivityOriginStep] = [mapping_step()] if mapped else []
    if calc.fx_via is not None:
        steps.append(fx_step(calc.fx_via))
    hit = calc.hit
    if hit is not None and (kind == "travel_spend" or hit.ef is not None):
        steps.append(travel_factor_step(hit.via) if kind == "travel_spend" else transport_factor_step(hit.via))
    if mode is not None:
        steps.append(mode_step(mode.via))
    usd = calc.spend_usd is not None
    amount = ActivityAmount(
        calc.spend_krw,
        "KRW",
        calc.spend_usd if usd else calc.spend_krw,
        "USD" if usd else "KRW",
        f"KRW → USD ({calc.fx:g} KRW/USD, {calc.fx_via})" if usd and calc.fx is not None else None,
    )
    title = None if hit is None else _text_or_none(hit.title)
    factor_info = ActivityFactor(
        factor.sheet,
        title,
        None if hit is None else _finite(hit.ef if kind == "transport_spend" else fix_num(hit.ef)),
        calc.unit,
        calc.ef_col,
        None if hit is None else _text_or_none(hit.code),
    )
    mode_info = None if mode is None else ActivityMode(mode.value, mode_step(mode.via).origin)
    month = coerce_month_value(row.get("발생월"))
    return ActivityMeta(_excel_row(row), kind, month, amount, factor_info, None, None, mode_info, tuple(steps))


def _waste_meta(row: "pd.Series[Any]", calc: WasteCalc, factor: FactorSheetRead, mapped: bool) -> ActivityMeta:
    steps: list[ActivityOriginStep] = [mapping_step()] if mapped else []
    if calc.conversion is not None:
        steps.append(unit_step(calc.conversion.via))
    via = calc.factor.via if calc.factor is not None else None
    if via is not None:
        steps.append(waste_factor_step(via))
    conv = calc.conversion
    note = calc.columns.get("단위환산비고")
    amount = ActivityAmount(
        calc.usage_raw,
        calc.unit_str,
        None if conv is None else conv.value,
        "kg" if conv is None else conv.unit,
        note if isinstance(note, str) else None,
    )
    column = (
        next((str(c) for c in factor.frame.columns if "배출계수" in str(c)), None)
        if via is not None and via != "treatment_average"
        else None
    )
    factor_info = ActivityFactor(
        factor.sheet, None, None if calc.factor is None else calc.factor.value, "kgCO2eq/kg", column, None
    )
    split = calc.split
    biogenic = ActivityBiogenic(split.fossil, split.biogenic, split.fcf, split.note)
    month = coerce_month_value(row.get("발생월"))
    return ActivityMeta(
        _excel_row(row), "waste", month, amount, factor_info, calc.treatment_std, biogenic, None, tuple(steps)
    )


def _transport_distance_meta(
    row: "pd.Series[Any]", calc: TransportCalc, standardized: WeightConversion | None, ef_map: TransportEfMap,
    main_loop: bool,
) -> ActivityMeta:  # fmt: skip
    """C4-1·C9-1 줄(2-5·2-6). `standardized` 는 표준화의 무게 환산(입력 무게면 None), `main_loop` 는 셈에 쓴 거리가 본
    고리(`:6012-6014`, road·KR 고정)의 값인가."""
    steps: list[ActivityOriginStep] = []
    weight = standardized if standardized is not None else calc.weight
    if weight is not None:
        steps.append(weight_step(weight.via))
    mode_step_ = transport_mode_step(calc.mode.via)
    steps.append(mode_step_)
    # 거리·출발·도착이 모두 빈 줄은 코랩 `infer_distance` 가 NaN 을 `input` 으로 넘긴다(배출량 NaN — 결함 후보).
    # 값은 그대로 두고 산정 출처만 「거리 없음」 으로 적는다
    via = calc.distance_via if _finite(calc.distance_km) is not None else "none"
    measured = distance_step(via)
    if measured is not None:
        steps.append(measured)
    ef_origin = ef_map.origins.get(calc.code)
    if ef_origin is not None:
        steps.append(transport_ef_step(ef_origin))
    raw = patch_to_float(patch_pick_first(row, ["월운송량", "연간운송량", "운송량"]))
    amount = ActivityAmount(raw, patch_safe_text(row.get("중량단위")) or "kg", calc.weight_kg, "kg", None)
    factor_info = ActivityFactor(
        TRANSPORT_SHEET,
        None,
        ef_map.factors.get(calc.code),
        TRANSPORT_EF_UNIT,
        ef_map.column if ef_origin == "db" else None,
        calc.code,
    )
    mode_info = ActivityMode(calc.code, mode_step_.origin)
    # 거리 길에 넘긴 mode: 본 고리면 road(고정), 두 번째 길이 거리 길을 불렀으면 추정한 코드, 그 밖(템플릿 입력·NaN
    # 입력·출발·도착 빈칸 — 거리 길을 안 부름)은 없음(덧붙임 1)
    geo_mode = "road" if main_loop else calc.code if calc.measured else None
    distance = ActivityDistance(
        _finite(calc.distance_km),
        via,
        geo_mode,
        _text_or_none(row.get("출발지")),
        _text_or_none(row.get("도착지")),
    )
    month = coerce_month_value(row.get("발생월"))
    kind: ColabActivityKind = "transport_distance"
    return ActivityMeta(
        _excel_row(row), kind, month, amount, factor_info, None, None, mode_info, tuple(steps), distance
    )


def _round_trip_view(frame: pd.DataFrame) -> pd.DataFrame:
    """코랩이 C6 후처리(`:8821`) 때 다시 읽는 결과 파일의 꼴: `COLS_TO_DROP`·전부 빈 열을 지우고 None → NaN.

    우리 줄 번호 열(`TEMPLATE_ROW`)도 뺀다(코랩에는 없다). 부르는 쪽(`postprocess_category`)이 같은 Category 의 시트를
    합친 frame 을 넘긴다(S3C-b2b — 코랩 결과 시트 하나가 C6-1+C6-2).
    """
    view = frame.drop(columns=[c for c in frame.columns if c in COLS_TO_DROP or c == TEMPLATE_ROW])
    view = view.loc[:, view.notna().any()]
    return view.astype(object).where(view.notna(), math.nan)


def process_activity_sheet(
    run: ActivityRun, template: Workbook, sheet: Sheet, key: str, category: str
) -> ActivitySheet | EmptyActivitySheet:
    """코랩 `process_new_template` 의 시트 하나(Category4·9·6·7·5 갈래). C6·C7 후처리는 시트 고리 뒤
    (`postprocess_category`)."""
    df = read_template_rows(sheet)
    if df.empty:
        return EmptyActivitySheet()
    weights: dict[object, WeightConversion | None] = {}
    if key == "c4_dist":
        df, weights = standardize_c4_dist_sheet(run.llm, run.units, df)
    elif key == "c9_dist":
        df, weights = standardize_c9_dist_sheet(run.llm, run.units, df)
    elif key == "c4_spend":
        df = standardize_c4_spend_sheet(df)
    elif key == "c9_spend":
        df = standardize_c9_spend_sheet(df)
    elif key == "c6_spend":
        df = standardize_c6_spend_sheet(df)
    elif key == "c6_dist":
        df = standardize_c6_dist_sheet(df)
    elif key == "c7":
        df = standardize_c7_sheet(df)
    else:
        df = standardize_c5_sheet(df)

    mapped_rows: frozenset[object] = frozenset()
    if category == "Category5":
        fill = fill_missing_from_company_mapping(df, template, WASTE_MAPPING_SHEET, "상세폐기물명", ["폐기물 종류"])
        df, mapped_rows = fill.frame, fill.filled
    elif category in ("Category6", "Category7") and "상세 교통수단명(선택)" in df.columns:  # 코랩 :5980
        fill = fill_missing_from_company_mapping(
            df, template, TRAVEL_MAPPING_SHEET, "상세 교통수단명(선택)", ["이동수단", "교통수단"]
        )
        df, mapped_rows = fill.frame, fill.filled
    df["자동카테고리"] = category
    df["출처시트"] = sheet.name

    rows_out: list[dict[str, object]] = []
    metas: list[ActivityMeta] = []
    if category in ("Category4", "Category9"):
        db = run.transport.frame
        for label, row in df.iterrows():
            row2 = {str(k): v for k, v in row.to_dict().items()}
            if (
                str(row.get("계산방식", "")).strip() == "Spend"
            ):  # C4-2·C9-2 는 늘, C4-1·C9-1 은 「계산방식」 열이 Spend 면
                calc = calc_transport_spend_emission(db, run.year, row)
                row2.update(calc.columns)
                rows_out.append(row2)
                metas.append(_spend_meta("transport_spend", row, calc, run.transport, label in mapped_rows, None))
                continue
            # 거리기반(`:6011-6018`): 거리 칸이 비고 출발·도착이 있으면 본 고리 길 — road·KR 고정(국가 칸을 안 본다)
            main_loop_via: str | None = None
            if (
                pd.isnull(row2.get("운송거리(km)"))
                and pd.notnull(row2.get("출발지"))
                and pd.notnull(row2.get("도착지"))
            ):
                found = get_distance_km(run.distances, row2.get("출발지"), row2.get("도착지"))
                row2["운송거리(km)"] = found.km
                main_loop_via = found.via if found.km is not None else None
            dist = calc_transport(
                run.llm, run.transport_modes, run.units, run.distances, run.ef_map, pd.Series(row2, dtype=object),
                main_loop_via,
            )  # fmt: skip
            row2["배출계수(거리기반)"] = dist.ef
            row2["배출량(tCO2e)"] = dist.emission_t
            rows_out.append(row2)
            main_loop = main_loop_via is not None and dist.picked  # 칸 값(본 고리가 채움)을 집었는가(덧붙임 2)
            metas.append(_transport_distance_meta(row, dist, weights.get(label), run.ef_map, main_loop))
        return ActivitySheet(pd.DataFrame(rows_out), tuple(metas))

    if category == "Category6":
        month_cols = [c for c in df.columns if c in set(PURCHASE_WIDE_MONTH_COLS)]
        if month_cols:
            df = sum_monthly(df, "이동횟수", month_cols)
            df = sum_monthly_spend(df, "출장비용")
        db = run.travel.frame
        loop: list[TravelLoopRow] = []
        for label, row in df.iterrows():
            row2 = {str(k): v for k, v in row.to_dict().items()}
            mapped = label in mapped_rows
            if row.get("계산방식") == "Spend":
                spend = calc_travel_spend_emission(db, run.year, row)
                row2.update(spend.columns)
                mode = normalize_travel_mode(run.llm, run.modes, row.get("출장수단") or row.get("이동수단"))
                row2["정규화이동수단"] = mode.value
                rows_out.append(row2)
                loop.append(TravelLoopRow(mapped, None))
                metas.append(_spend_meta("travel_spend", row, spend, run.travel, mapped, mode))
                continue
            # 거리기반(`:6037-6048`): 본 고리 배출량은 왕복 낱말을 보지 않는 ×2 — 후처리(`_fix_result_c6`)가 덮는다
            calc = calc_business_travel(run.llm, run.modes, run.distances, run.travel_ef, row)
            if pd.isnull(row.get("이동거리(km)")) and calc.distance_km is not None:
                row2["이동거리(km)"] = calc.distance_km
            n_trips = to_float(row2.get("이동횟수"))
            n_people = to_float(row2.get("출장인원") or row2.get("인원수")) or 1
            dist_km = to_float(row2.get("이동거리(km)")) or calc.distance_km
            emission = calc.emission_t
            if calc.ef and dist_km and n_trips:
                emission = dist_km * 2 * calc.ef * n_people * n_trips / 1000
            row2["배출계수"] = calc.ef
            row2["배출량"] = emission
            mode = normalize_travel_mode(run.llm, run.modes, row.get("출장수단") or row.get("이동수단"))
            row2["정규화이동수단"] = mode.value
            rows_out.append(row2)
            loop.append(TravelLoopRow(mapped, calc))
            metas.append(_loop_travel_meta("travel_distance", row, mapped, mode, calc, run.travel_ef))
        pending = PendingPost(category, tuple(rows_out), tuple(loop))
        return ActivitySheet(pd.DataFrame(rows_out), tuple(metas), pending)

    if category == "Category7":
        month_cols_c7 = [c for c in df.columns if c in set(PURCHASE_WIDE_MONTH_COLS)]
        df = sum_monthly(df, "근무일수", month_cols_c7)  # 코랩 :6056 — 달 열이 없어도 부름
        commute_loop: list[TravelLoopRow] = []
        for label, row in df.iterrows():
            row2 = {str(k): v for k, v in row.to_dict().items()}
            mapped = label in mapped_rows
            calc = calc_commute(run.llm, run.modes, run.distances, run.travel_ef, row)
            if pd.isnull(row.get("평균통근거리(km)")) and calc.distance_km is not None:
                row2["평균통근거리(km)"] = calc.distance_km
            row2["배출계수"] = calc.ef
            row2["배출량"] = calc.emission_t
            mode = normalize_commute_mode(run.llm, run.modes, row.get("교통수단") or row.get("이동수단"))
            row2["정규화이동수단"] = mode.value
            rows_out.append(row2)
            commute_loop.append(TravelLoopRow(mapped, calc))
            metas.append(_loop_travel_meta("commute", row, mapped, mode, calc, run.travel_ef))
        pending = PendingPost(category, tuple(rows_out), tuple(commute_loop))
        return ActivitySheet(pd.DataFrame(rows_out), tuple(metas), pending)

    month_cols_c5 = [c for c in df.columns if c in set(PURCHASE_WIDE_MONTH_COLS)]
    df = sum_monthly(df, "처리량", month_cols_c5)
    db = run.waste.frame
    for label, row in df.iterrows():
        row2 = {str(k): v for k, v in row.to_dict().items()}
        calc = calc_waste_row(db, run.llm, run.units, row)
        row2.update(calc.columns)
        rows_out.append(row2)
        metas.append(_waste_meta(row, calc, run.waste, label in mapped_rows))
    return ActivitySheet(pd.DataFrame(rows_out), tuple(metas))


# ── S3C-b2b: 출장·통근 거리 줄 메타와 C6·C7 후처리(코랩 `_postprocess_scope3_result_file` `:8878`) ──


def _travel_meta(
    kind: ColabActivityKind, source: "pd.Series[Any]", mapped: bool, mode: TravelMode, ef_via: TravelEfVia | None,
    ef_map: TravelEfMap, distance: ActivityDistance, ef: float | None, count: float | None,
) -> ActivityMeta:  # fmt: skip
    """C6-1(`travel_distance`)·C7(`commute`) 줄(2-2). `count` = 셈에 쓴 이동횟수(C6)·근무일수(C7)."""
    steps: list[ActivityOriginStep] = [mapping_step()] if mapped else []
    mode_step_ = mode_step(mode.via)
    steps.append(mode_step_)
    measured = distance_step(distance.via)
    if measured is not None:
        steps.append(measured)
    if ef is not None and ef_via is not None:
        steps.append(travel_ef_step(ef_via))
    km, round_trip, people = distance.km, distance.round_trip, distance.people
    base = None
    if km is not None and round_trip is not None and people is not None and count is not None:
        base = km * round_trip * people * count  # 인·km(거리 × 왕복 × 인원 × 횟수·일수)
    amount = ActivityAmount(count, "회" if kind == "travel_distance" else "일", base, "pkm", None)
    column = ef_map.column if ef_via == "db" else None
    factor_info = ActivityFactor(TRAVEL_SHEET, None, _finite(ef), TRAVEL_EF_UNIT, column, mode.value)
    mode_info = ActivityMode(mode.value, mode_step_.origin)
    month = coerce_month_value(source.get("발생월"))
    return ActivityMeta(
        _excel_row(source), kind, month, amount, factor_info, None, None, mode_info, tuple(steps), distance
    )


def _distance_of(
    source: "pd.Series[Any]", km: float | None, via: str, geo_mode: str | None, calc: TravelCalc, count: float | None,
    round_trip: float, people: float,
) -> ActivityDistance:  # fmt: skip
    finite_km = _finite(km)
    commute = calc.workdays is not None
    return ActivityDistance(
        finite_km,
        via if finite_km is not None else "none",
        geo_mode,
        _text_or_none(source.get("출발지")),
        _text_or_none(source.get("도착지")),
        float(round_trip),
        float(people),
        None if commute or count is None else float(count),
        float(count) if commute and count is not None else None,
    )


def _loop_travel_meta(
    kind: ColabActivityKind, row: "pd.Series[Any]", mapped: bool, mode: TravelMode, calc: TravelCalc,
    ef_map: TravelEfMap,
) -> ActivityMeta:  # fmt: skip
    """본 고리 값의 메타(후처리가 실패한 결과 시트에 남는다)."""
    count = calc.workdays if calc.workdays is not None else calc.trips
    distance = _distance_of(row, calc.distance_km, calc.distance_via, calc.geo_mode, calc, count, calc.round_trip,
                            calc.people)  # fmt: skip
    return _travel_meta(kind, row, mapped, mode, calc.ef_via, ef_map, distance, calc.ef, count)


def _fix_c6_row(run: ActivityRun, row: "pd.Series[Any]", out: dict[str, object], info: TravelLoopRow) -> ActivityMeta:
    """코랩 `_fix_result_c6`(`:8821-8842`)의 줄 하나. 고친 칸은 `out`(본 고리 줄의 사본)에 쓴다."""
    method = fix_text(row.get("계산방식"))
    spend: SpendCalc | None = None
    fix = None
    if method == "Distance":
        fix = fix_c6_distance(row)
        out["배출량(tCO2e)"] = fix.emission_t
        out["배출량"] = fix.emission_t
        out["출장비용"] = None
        out["거리왕복계수"] = fix.round_trip
        out["계산식"] = fix.formula
    elif method == "Spend":
        spend = calc_travel_spend_emission(run.travel.frame, run.year, row)
        out.update(spend.columns)
    mode = normalize_travel_mode(run.llm, run.modes, row.get("출장수단") or row.get("이동수단"))
    out["정규화이동수단"] = mode.value
    source = pd.Series(out, dtype=object)
    if spend is not None:
        return _spend_meta("travel_spend", source, spend, run.travel, info.mapped, mode)
    calc = info.calc
    if fix is None or calc is None:  # 표준화가 C6-1 은 Distance, C6-2 는 Spend 로 두므로 오지 않는다
        raise ValueError(f"C6 줄의 계산방식이 갈래와 맞지 않는다: {method!r}")
    # 셈에 쓴 거리 = 파일의 「이동거리(km)」 — 칸 값이면 input, 본 고리가 채운 값이면 그 길(B5·R2)
    via = "input" if calc.picked else calc.distance_via
    distance = _distance_of(source, fix.distance_km, via, calc.geo_mode, calc, fix.trips, fix.round_trip, fix.people)
    return _travel_meta("travel_distance", source, info.mapped, mode, calc.ef_via, run.travel_ef, distance, fix.ef,
                        fix.trips)  # fmt: skip


def _fix_c7_row(run: ActivityRun, row: "pd.Series[Any]", out: dict[str, object], info: TravelLoopRow) -> ActivityMeta:
    """코랩 `_fix_result_c7`(`:8845-8859`)의 줄 하나: `calc_commute` 를 파일 줄로 다시(거리 칸이 비었으면 거리 길도)."""
    post = calc_commute(run.llm, run.modes, run.distances, run.travel_ef, row)
    out["평균통근거리(km)"] = post.distance_km if post.distance_km is not None else row.get("평균통근거리(km)")
    out["배출계수"] = post.ef
    out["배출량(tCO2e)"] = post.emission_t
    out["배출량"] = post.emission_t
    out["거리왕복계수"] = post.round_trip
    mode = normalize_commute_mode(run.llm, run.modes, row.get("교통수단") or row.get("이동수단"))
    out["정규화이동수단"] = mode.value
    out["계산식"] = commute_formula(post)
    source = pd.Series(out, dtype=object)
    loop = info.calc
    filled = loop is not None and not loop.picked and loop.distance_km is not None  # 본 고리가 칸을 채웠다
    via, geo_mode = post.distance_via, post.geo_mode
    if post.picked and loop is not None:
        via, geo_mode = (loop.distance_via, loop.geo_mode) if filled else ("input", None)
    distance = _distance_of(source, post.distance_km, via, geo_mode, post, post.workdays, post.round_trip, post.people)
    return _travel_meta("commute", source, info.mapped, mode, post.ef_via, run.travel_ef, distance, post.ef,
                        post.workdays)  # fmt: skip


def postprocess_category(run: ActivityRun, category: str, pending: Sequence[PendingPost]) -> tuple[ActivitySheet, ...]:
    """코랩 후처리(`:8878-8905`)의 결과 시트 하나(C6_ 또는 C7_): 그 Category 의 시트들을 템플릿 차례로 합친 줄
    (`_round_trip_view` — `COLS_TO_DROP`·**합친 frame 에서** 전부 빈 열을 지움, 빈 글 → NaN 은 흉내 안 함)을 줄마다
    다시 센다. 시트마다 나눠 돌려준다. 예외는 밖으로(pipeline 이 그 결과 시트를 본 고리 값으로 둔다)."""
    rows = [dict(r) for p in pending for r in p.rows]
    loop = [info for p in pending for info in p.loop]
    view = _round_trip_view(pd.DataFrame(rows))
    fix_row = _fix_c6_row if category == "Category6" else _fix_c7_row
    metas = [fix_row(run, row, rows[i], loop[i]) for i, (_, row) in enumerate(view.iterrows())]
    sheets: list[ActivitySheet] = []
    start = 0
    for p in pending:
        end = start + len(p.rows)
        sheets.append(ActivitySheet(pd.DataFrame(rows[start:end]), tuple(metas[start:end])))
        start = end
    return tuple(sheets)
