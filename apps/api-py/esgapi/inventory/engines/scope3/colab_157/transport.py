"""거리기반 운송(C4-1·C9-1) — 코랩 셀 22·27 의 마지막 판(늦은 묶임 포함).

- 운송수단: `infer_transport_mode`(`:7699`) → 템플릿 표시명 `_template_transport_code`(`:7644`) → 붙잡은 옛 판
  `:1153`(`_INFER_TRANSPORT_MODE_BEFORE_ALIAS_PATCH` `:7250-7251` — 키워드 사전은 `:6573-6579` 보강 뒤) 의 답을
  `_patch_normalize_transport_code`(`:7667`)로 → AI `_ai_infer_transport_mode`(`:7684`) → `"road"`. 판단근거(via)는
  `template_alias|column|keyword|geo|ai|fallback`. `:7667` 판은 템플릿 표시명 → 붙잡은 옛 판 `:6582`
  (`:7252-7253`) → 글 그대로.
- 무게: `_patch_weight_to_kg`(`:6486`) — 규칙표 `WEIGHT_TO_KG_PATCH`(`:6479`) → 부분 낱말 → AI 배수
  `_ai_unit_conversion_factor(unit, "kg") or 1.0`(b1 `units` 의 캐시 — C5 와 같은 lru_cache). via `rule|ai|ai_failed`.
- 운송 계수 맵: 셀 25 다음 `refresh_transport_ef_map()`(`:7780`, 정의 `:6611`) — 기본값 다섯
  (`DEFAULT_TRANSPORT_EF_MAP_PATCH` `:6563`) 위에 다시 읽은 운송 시트(`_build_transport_ef_map_from_db` `:419`)의 코드를
  `:7667` 판으로 정규화해 덮는다. 코드마다 `db|default`.
- 수치(기본 계수·중량 배수)는 코랩 값이다(constants.py 머리 — 출처 확인 안 함).
"""

import contextlib
import math
from dataclasses import dataclass, field
from typing import Any, Final, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.constants import (
    AIR_KEYWORDS,
    AIRPORT_HINTS,
    DEFAULT_TRANSPORT_EF_MAP_PATCH,
    DOMESTIC_SITE_HINTS,
    PARCEL_KEYWORDS,
    PORT_HINTS,
    RAIL_KEYWORDS,
    ROAD_KEYWORDS,
    SEA_KEYWORDS,
    WEIGHT_TO_KG_PATCH,
)
from esgapi.inventory.engines.scope3.colab_157.distance import DistanceRun, contains_any, infer_distance, safe_text2
from esgapi.inventory.engines.scope3.colab_157.factor_book import FactorSheetRead
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext, call_claude_json, json_get
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_fillna
from esgapi.inventory.engines.scope3.colab_157.spend import (
    collapse_monthly_to_value,
    ef_safe_text,
    template_transport_code,
)
from esgapi.inventory.engines.scope3.colab_157.template import normalize_template_columns
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache, ai_unit_conversion_factor

TRANSPORT_MODE_PROMPT: Final = "inventory/scope3-colab-transport-mode@1"
TRANSPORT_EF_UNIT: Final = "kgCO2e/ton-km"  # 코랩 calc_transport 머리글(:6631)
TransportModeVia = Literal["template_alias", "column", "keyword", "geo", "ai", "fallback"]
WeightVia = Literal["rule", "ai", "ai_failed"]
EfOrigin = Literal["db", "default"]
_AI_MODES: Final = {"road", "parcel", "rail", "sea", "air", "sea_bulk", "inland_water"}
# 코랩 :7706-7709
_MODE_FIELDS: Final = [
    "운송수단", "운송방법", "교통수단", "운송구분", "운송수단(선택)", "설명/적요", "비고", "자재명", "품목명", "제품명",
]  # fmt: skip
# 코랩 :1162 · :1176-1179
_DIRECT_FIELDS: Final = ["운송수단", "배송수단", "mode", "shipment mode", "transport_mode"]
_KEYWORD_FIELDS: Final = ["설명/적요", "비고", "거래처명", "운송사명", "송장번호", "B/L", "AWB", "Booking", "운송구분"]
_ORDERED_KEYWORDS: Final[list[tuple[str, list[str]]]] = [
    ("parcel", PARCEL_KEYWORDS),
    ("air", AIR_KEYWORDS),
    ("sea", SEA_KEYWORDS),
    ("rail", RAIL_KEYWORDS),
    ("road", ROAD_KEYWORDS),
]


# ── 값 하나(코랩 :6435 · :6445 · :6471) ──


def patch_safe_text(x: object) -> str:
    """코랩 `_patch_safe_text`(`:6435`)."""
    if x is None:
        return ""
    if isinstance(x, float) and math.isnan(x):  # 코랩 `pd.isna(x)`(칸 값은 글·수·None·NaN)
        return ""
    return str(x).strip()


def patch_to_float(x: object) -> float | None:
    """코랩 `_patch_to_float`(`:6445`)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):
        return None
    s = str(x).replace(",", "").strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except Exception:
        return None


def patch_pick_first(row: "pd.Series[Any]", cols: list[str]) -> object:
    """코랩 `_patch_pick_first`(`:6471`): 글로 비지 않은 첫 칸의 값(원값 그대로)."""
    for c in cols:
        if c in row.index:
            v = row.get(c)
            if patch_safe_text(v) != "":
                return v
    return None


# ── 운송수단(코랩 :1153 옛 판 · :6582 · :7644 · :7667 · :7684 · :7699) ──


@dataclass(frozen=True)
class TransportMode:
    code: str
    via: TransportModeVia


@dataclass
class TransportModeCache:
    """코랩 `_ai_infer_transport_mode` 의 lru_cache 자리(실행 하나). 실패(None)도 기억한다."""

    modes: dict[str, str | None] = field(default_factory=dict[str, str | None])


def normalize_transport_code_6582(code: object) -> str | None:
    """코랩 `_patch_normalize_transport_code`(`:6582`, 붙잡은 옛 판)."""
    s = patch_safe_text(code).lower()
    if not s:
        return None
    if any(k in s for k in ["road", "truck", "도로", "육로", "화물", "차량"]):
        return "road"
    if any(k in s for k in ["parcel", "courier", "택배", "소포", "특송"]):
        return "parcel"
    if any(k in s for k in ["rail", "train", "철도", "철송", "ktx", "srt"]):
        return "rail"
    if any(k in s for k in ["sea", "ocean", "ship", "vessel", "해상", "선박", "해운"]):
        return "sea"
    if any(k in s for k in ["air", "flight", "항공", "공항"]):
        return "air"
    return s


def normalize_transport_code(code: object) -> str | None:
    """코랩 `_patch_normalize_transport_code`(`:7667`, 마지막 판)."""
    mapped = template_transport_code(code)
    if mapped:
        return mapped
    with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
        return normalize_transport_code_6582(code)
    s = ef_safe_text(code).strip()
    return s or None


def _concat_row_text(row: "pd.Series[Any]", fields: list[str]) -> str:
    """코랩 `_concat_row_text`(`:1113`)."""
    vals = [safe_text2(row.get(f)) for f in fields if f in row.index]
    return " ".join([v for v in vals if v]).lower()


def infer_transport_mode_1153(row: "pd.Series[Any]") -> tuple[str, TransportModeVia | Literal["default"]]:
    """코랩 `infer_transport_mode`(`:1153-1208`, 붙잡은 옛 판) — (mode, mode_source). 확신도는 쓰는 곳이 없어 뺐다."""
    direct_mode_text = _concat_row_text(row, _DIRECT_FIELDS)
    if direct_mode_text:
        for code, keywords in _ORDERED_KEYWORDS:
            if contains_any(direct_mode_text, keywords):
                return code, "column"
    keyword_text = _concat_row_text(row, _KEYWORD_FIELDS)
    for code, keywords in _ORDERED_KEYWORDS:
        if contains_any(keyword_text, keywords):
            return code, "keyword"
    origin = safe_text2(row.get("출발지")).lower()
    dest = safe_text2(row.get("도착지")).lower()
    geo_text = f"{origin} {dest}"
    if contains_any(geo_text, AIRPORT_HINTS):
        return "air", "geo"
    if contains_any(geo_text, PORT_HINTS):
        return "sea", "geo"
    if any(k in geo_text for k in DOMESTIC_SITE_HINTS):
        return "road", "geo"
    return "unknown", "default"


def ai_infer_transport_mode(context: LlmContext, cache: TransportModeCache, text: str) -> str | None:
    """코랩 `_ai_infer_transport_mode`(`:7684-7697`, `max_tokens=40`) + lru_cache. dict 아닌 JSON 은 AttributeError."""
    if text in cache.modes:
        return cache.modes[text]
    parsed = call_claude_json(context, TRANSPORT_MODE_PROMPT, {"text": text}, 40)
    mode = ef_safe_text(json_get(parsed, "mode")) if parsed else ""
    found = mode if mode in _AI_MODES else None
    cache.modes[text] = found
    return found


def infer_transport_mode(context: LlmContext, cache: TransportModeCache, row: "pd.Series[Any]") -> TransportMode:
    """코랩 `infer_transport_mode`(`:7699-7739`, 마지막 판)."""
    parts = [ef_safe_text(row.get(f)) for f in _MODE_FIELDS]
    joined = " ".join(p for p in parts if p)
    code = template_transport_code(joined)
    if code:
        return TransportMode(code, "template_alias")
    with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
        mode, source = infer_transport_mode_1153(row)
        mode2 = normalize_transport_code(mode)
        mode2 = mode2 if mode2 and mode2 != "unknown" else None
        if mode2 and source != "default":  # "default" 면 mode 가 "unknown" 이라 mode2 가 이미 None(타입 좁힘)
            return TransportMode(mode2, source)
    if joined:
        ai_mode = ai_infer_transport_mode(context, cache, joined)
        if ai_mode:
            return TransportMode(ai_mode, "ai")
    return TransportMode("road", "fallback")


# ── 무게(코랩 :6486) ──


@dataclass(frozen=True)
class WeightConversion:
    kg: float
    via: WeightVia


def weight_to_kg(context: LlmContext, cache: UnitFactorCache, value: object, unit: object) -> WeightConversion | None:
    """코랩 `_patch_weight_to_kg`(`:6486-6506`). 값이 없으면 None."""
    v = patch_to_float(value)
    if v is None:
        return None
    u = patch_safe_text(unit).lower().replace(" ", "")
    if u in ["", "nan"]:
        u = "kg"
    if u == "metricton":  # 코랩: 공백 제거로 놓치는 영문 단위 보정
        u = "metric ton"
    factor = WEIGHT_TO_KG_PATCH.get(u)
    if factor is not None:
        return WeightConversion(v * factor, "rule")
    if "ton" in u or "톤" in u:
        return WeightConversion(v * 1000.0, "rule")
    if "kg" in u or "킬로" in u:
        return WeightConversion(v * 1.0, "rule")
    if u == "g" or "gram" in u or "그램" in u:
        return WeightConversion(v * 0.001, "rule")
    ai = ai_unit_conversion_factor(context, cache, f"{unit}", "kg")  # 코랩 f-문자열이 단위 원값을 글로 넣는다
    return WeightConversion(v * ai, "ai") if ai else WeightConversion(v * 1.0, "ai_failed")


# ── 운송 계수 맵(코랩 :419 · :6611 — 부름 :7780) ──


@dataclass(frozen=True)
class TransportEfMap:
    """코랩 전역 `TRANSPORT_EF_MAP`(셀 25 뒤의 값). `column` 은 다시 읽은 운송 시트의 배출계수 열(기본값만이면 None)."""

    factors: dict[str, float]
    origins: dict[str, EfOrigin]
    column: str | None


def build_transport_ef_map_from_db(db: pd.DataFrame) -> tuple[dict[str, float], str | None] | None:
    """코랩 `_build_transport_ef_map_from_db`(`:419-432`). db 가 비었거나 열이 없으면 None(코랩은 기본 다섯을 낸다)."""
    if db.empty:
        return None
    code_col = next((c for c in db.columns if "표준코드" in c), None)
    ef_col = next((c for c in db.columns if "배출계수" in c), None)
    if not code_col or not ef_col:
        return None
    result: dict[str, float] = {}
    for _, row in db.iterrows():
        code = str(row.get(code_col, "")).strip()  # 코랩 그대로 — NaN 은 "nan"
        ef = pd.to_numeric(pd.Series([row.get(ef_col)], dtype=object), errors="coerce").iloc[0]
        if code and pd.notna(ef):
            result[code] = float(ef)
    return result, str(ef_col)


def refresh_transport_ef_map(sheet: FactorSheetRead) -> TransportEfMap:
    """코랩 `refresh_transport_ef_map`(`:6611-6626`): 기본 다섯 위에 db 코드(`:7667` 판 정규화)를 덮는다."""
    factors = dict(DEFAULT_TRANSPORT_EF_MAP_PATCH)
    origins: dict[str, EfOrigin] = dict.fromkeys(factors, "default")
    column: str | None = None
    with contextlib.suppress(Exception):  # 코랩 `except Exception: pass` — 그때까지 덮은 것은 남는다
        built = build_transport_ef_map_from_db(sheet.frame)
        if built is not None:
            raw, column = built
            for k, v in raw.items():
                code = normalize_transport_code(k)
                fv = patch_to_float(v)
                if code and fv is not None:
                    factors[code] = fv
                    origins[code] = "db"
    return TransportEfMap(factors, origins, column if any(o == "db" for o in origins.values()) else None)


# ── 경계 ②: 시트 표준화와 줄 셈(코랩 :6628 · :6657 · :6696) ──


def standardize_c4_dist_sheet(
    context: LlmContext, cache: UnitFactorCache, df: pd.DataFrame
) -> tuple[pd.DataFrame, dict[object, WeightConversion | None]]:
    """코랩 `standardize_c4_dist_sheet`(`:6657-6694`). 둘째 값 = 줄마다 표준화의 무게 환산(입력 무게면 없음).

    무게 AI 배수는 `df.apply` 라 시트의 **모든 줄에서 먼저** 불린다(2-0 d). 0 kg 은 `or` 라 다시 환산한다(결함 후보).
    """
    df = normalize_template_columns(df)
    rename = {c: str(c).lstrip("*").strip() for c in df.columns if str(c).startswith("*")}
    if rename:
        df = df.rename(columns=rename)
    pairs = [
        ("자재명/품목명", "자재명"),
        ("제품명/품목명", "제품명"),
        ("운송수단(선택)", "운송수단"),
        ("출도착지", "출발지"),
        ("운송거리(km)(선택)", "운송거리(km)"),
    ]
    rename2 = {old: new for old, new in pairs if old in df.columns and new not in df.columns}
    if "비고(선택)" in df.columns:
        rename2["비고(선택)"] = "비고"
    if rename2:
        df = df.rename(columns=rename2)
    df = collapse_monthly_to_value(df, "월운송량", annual_cols=["연간운송량"])
    if "화물중량(kg)" not in df.columns:
        df["화물중량(kg)"] = None
    weights: dict[object, WeightConversion | None] = {}
    values: list[float | None] = []
    for label, r in df.iterrows():
        given = patch_to_float(r.get("화물중량(kg)"))
        if given:  # 코랩 `_patch_to_float(...) or _patch_weight_to_kg(...)` — 0 은 거짓
            values.append(given)
            continue
        conv = weight_to_kg(
            context, cache, patch_pick_first(r, ["월운송량", "연간운송량", "운송량"]), r.get("중량단위")
        )
        weights[label] = conv
        values.append(conv.kg if conv is not None else None)
    df["화물중량(kg)"] = pd.Series(values, index=df.index, dtype=object)
    df["운송구분"] = "입고"
    if "계산방식" in df.columns:
        df["계산방식"] = colab_fillna(df["계산방식"], "Distance")
    else:
        df["계산방식"] = "Distance"
    return df, weights


def standardize_c9_dist_sheet(
    context: LlmContext, cache: UnitFactorCache, df: pd.DataFrame
) -> tuple[pd.DataFrame, dict[object, WeightConversion | None]]:
    """코랩 `standardize_c9_dist_sheet`(`:6696`) = C4 + 「운송구분」 출고."""
    df, weights = standardize_c4_dist_sheet(context, cache, df)
    df["운송구분"] = "출고"
    return df, weights


@dataclass(frozen=True)
class TransportCalc:
    """코랩 `calc_transport`(`:6628-6654`)의 (ef, emission_t)와 그 길."""

    ef: float | None
    emission_t: float | None
    mode: TransportMode
    code: str
    distance_km: float | None
    distance_via: str
    weight_kg: float | None
    weight: WeightConversion | None  # calc 안에서 다시 환산했을 때(표준화가 None 을 남긴 줄)
    picked: bool = False  # 거리를 거리 칸에서 집었는가(`pick_first` — 본 고리가 채운 값 포함, 덧붙임 2)
    measured: bool = False  # 두 번째 길이 거리 길(`get_distance_km`)을 실제로 불렀는가(덧붙임 1)


def calc_transport(
    context: LlmContext,
    modes: TransportModeCache,
    units: UnitFactorCache,
    distances: DistanceRun,
    ef_map: TransportEfMap,
    row: "pd.Series[Any]",
    main_loop_via: str | None,
) -> TransportCalc:
    """코랩 `calc_transport`(`:6628`): 운송수단(AI 가능) → 거리 칸(검증 없음) 없으면 두 번째 길 → 무게 → 맵.

    `main_loop_via` 는 본 고리(`:6012-6014`)가 「운송거리(km)」 를 채웠을 때 그 길(B5 — 그 값은 `input` 이 아니다).
    """
    mode = infer_transport_mode(context, modes, row)
    code = normalize_transport_code(mode.code) or "road"
    distance_km = patch_to_float(patch_pick_first(row, ["운송거리(km)", "운송거리(km)(선택)", "거리(km)"]))
    via = main_loop_via or "input"
    picked = distance_km is not None
    measured = False
    if distance_km is None:
        found = infer_distance(distances, row, code)
        distance_km, via = found.km, found.via
        # `infer_distance` 가 입력 검증을 지나면(NaN 칸 포함) 거리 길을 안 부르고, 출발·도착이 비어도 안 부른다
        measured = found.via != "input" and bool(safe_text2(row.get("출발지"))) and bool(safe_text2(row.get("도착지")))
    weight_kg = patch_to_float(row.get("화물중량(kg)"))
    weight: WeightConversion | None = None
    if weight_kg is None:
        raw = patch_pick_first(row, ["월운송량", "연간운송량", "운송량", "화물중량"])
        weight = weight_to_kg(context, units, raw, row.get("중량단위"))
        weight_kg = weight.kg if weight is not None else None
    if distance_km is None or weight_kg is None:
        return TransportCalc(None, None, mode, code, distance_km, via, weight_kg, weight, picked, measured)
    ef = ef_map.factors.get(code)
    if ef is None:
        return TransportCalc(None, None, mode, code, distance_km, via, weight_kg, weight, picked, measured)
    emission_t = distance_km * (weight_kg / 1000.0) * ef / 1000.0
    return TransportCalc(ef, emission_t, mode, code, distance_km, via, weight_kg, weight, picked, measured)
