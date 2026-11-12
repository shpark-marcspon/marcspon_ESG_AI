"""에너지 계수 사슬·C3 계수·에너지 단위 환산 — 코랩 셀 8·20·24·25·27·29 의 에너지 몫(S3C-c1a).

결과 시트 일곱 가운데 에너지를 쓰는 C3·C8·C13(이 밴드)과 C11·C14(S3C-c1b — 이 파일을 고치지 않고 쓴다)의 셈 함수다.

- 계수 사슬 `lookup_energy_ef`(이기는 정의 = 셀 27 `:8229`, 따를 표 7): 가스+단위 우선 별칭
  (`_fix_lookup_energy_title_exact` `:8213`) → 셀 25 `:7508`(`resolve_energy_ef_row` `:7436` — 정확·별칭·포함·
  fuzzy, TJ→GJ 정규화) → 셀 24 `:6822`(그 안에서 셀 8 `:479` 를 먼저, 실패면 폴백 계수 `ENERGY_FALLBACK_EF_PATCH`).
  붙잡은 옛 정의 사슬(`_ORIGINAL_*`·`_LOOKUP_ENERGY_EF_BEFORE_ALIAS_PATCH`)을 그대로 잇는다. 모두 같은 계수 시트
  `에너지`(셀 25 다시 읽기 뒤 — 늦은 묶임)를 본다.
- 코랩 전역 `_LAST_EF_MATCH_INFO["energy"]`(match_type·score — C11·C14 의 EF매핑방식·EF매핑점수)는 부를 때마다 덮인다.
  여기서는 부름의 값(`EnergyMatch`)으로 돌려준다. 어느 고리가 답했는지(`via` — 산정 출처의 글)는 코랩에 없고 우리가
  단다: 폴백 계수와 `:479` 의 답은 코랩 match_type 이 둘 다 `legacy_lookup` 이다.
- C3 계수 `lookup_energy_ef_c3`(`:9113`)는 사슬을 쓰지 않고 `에너지_C3` 시트(셀 29 `:9048`, 다시 읽지 않음)만 본다.
- 단위 환산 `convert_energy_unit`(`:3846`)의 AI 배수는 `units.ai_unit_conversion_factor`(코랩
  `_ai_unit_conversion_factor` `:3809` 의 lru_cache — 실행 하나에 하나, C5 무게 배수와 같은 캐시)다. 발열량 다리
  `_bridge_convert_via_lhv`(`:9146`).
- 코랩 `globals()` 의 `energy_ef_db`·`energy_c3_ef_db` 는 인자(`db` frame)로 받는다. fuzzy 는 코랩과 같은
  `difflib.SequenceMatcher`(`:7147`)다.
"""

import math
import numbers
from collections.abc import Callable
from dataclasses import dataclass
from difflib import SequenceMatcher
from typing import Any, Final, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.activity import (
    ActivityAmount,
    ActivityFactor,
    ActivityOriginStep,
    sum_monthly,
)
from esgapi.inventory.engines.scope3.colab_157.constants import (
    EF_UNIT_MAP,
    ENERGY_ALIAS_479,
    ENERGY_ALIAS_CONTAINS_SCORE,
    ENERGY_ALIAS_EXACT_SCORE,
    ENERGY_BASE_UNIT,
    ENERGY_CONTAINS_SIMILARITY,
    ENERGY_FALLBACK_EF_PATCH,
    ENERGY_FUZZY_CAP,
    ENERGY_FUZZY_THRESHOLD,
    ENERGY_GAS_FACTORS,
    ENERGY_GJ_FACTORS,
    ENERGY_KG_FACTORS,
    ENERGY_KWH_FACTORS,
    ENERGY_MJ_PER_INPUT,
    ENERGY_NAME_ALIAS,
    ENERGY_QUERY_CONTAINS_SCORE,
    ENERGY_UNIT_BONUS,
    ENERGY_VOLUME_FACTORS,
)
from esgapi.inventory.engines.scope3.colab_157.factor_book import ENERGY_C3_SHEET, ENERGY_SHEET, FactorSheetRead
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext, reraises
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.engines.scope3.colab_157.purchase import (
    ColabOrigin,
    coerce_month_value,
    fix_norm,
    fix_num,
    fix_text,
    to_float,
)
from esgapi.inventory.engines.scope3.colab_157.spend import collapse_monthly_to_value, ef_norm_text, ef_safe_text
from esgapi.inventory.engines.scope3.colab_157.template import (
    PURCHASE_WIDE_MONTH_COLS,
    TEMPLATE_ROW,
    normalize_template_columns,
    read_template_rows,
)
from esgapi.inventory.engines.scope3.colab_157.transport import patch_pick_first, patch_safe_text, patch_to_float
from esgapi.inventory.engines.scope3.colab_157.units import UnitFactorCache, ai_unit_conversion_factor
from esgapi.inventory.engines.scope3.colab_157.waste import melt_monthly_or_annual
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

# 결과 꼴의 줄 kind(일곱 결과 시트 — C3·C8·C13 은 이 밴드, 나머지 넷은 S3C-c1b). 계약 `ColabEnergyKind` 와 같은 값·차례
ColabEnergyKind = Literal[
    "fuel_energy", "leased_asset", "leased_out_asset", "product_use", "product_eol", "franchise", "investment"
]
# 사슬에서 답한 고리(우리 글 — 산정 출처). `none` = 못 찾음
EnergyFactorVia = Literal[
    "unit_priority_alias", "exact_raw", "alias_exact", "alias_contains", "contains", "fuzzy", "legacy_479",
    "fallback_patch", "none",
]  # fmt: skip
C3FactorVia = Literal["exact_raw", "alias_exact", "contains", "none"]
# 환산의 길: 같은 단위(환산 없음) · 규칙표 · 발열량 경유 · AI 배수 · AI 실패(값 그대로) · 모르는 에너지원(값 그대로)
EnergyUnitVia = Literal["same", "rule", "lhv", "ai", "ai_failed", "none"]

GAS_WORDS: Final = ["천연가스", "도시가스", "lng", "naturalgas"]  # 코랩 :8234
# `resolve_energy_ef_row` 가 줄을 낸 갈래 다섯(코랩 match_type 글자 그대로)
RESOLVED_VIA: Final[dict[str, EnergyFactorVia]] = {
    "exact_raw": "exact_raw",
    "alias_exact": "alias_exact",
    "alias_contains": "alias_contains",
    "contains": "contains",
    "fuzzy": "fuzzy",
}


@dataclass(frozen=True)
class EnergyMatch:
    """코랩 `_LAST_EF_MATCH_INFO["energy"]` 한 번의 값. score 는 코랩처럼 `round(…, 4)`(legacy 면 None)."""

    input: str
    unit_hint: str
    raw_name: object
    raw_unit: object
    match_type: str
    score: float | None


@dataclass(frozen=True)
class EnergyLookup:
    """사슬의 답 (활동유형명, kgCO2eq/단위, 단위) 과 답한 고리·그때의 매칭 정보. 이름·단위는 코랩이 낸 칸 값 그대로."""

    name: object
    ef: float | None
    unit: object
    via: EnergyFactorVia
    match: EnergyMatch


@dataclass(frozen=True)
class C3Lookup:
    """`lookup_energy_ef_c3` 의 답. 못 찾으면 셋 다 None(via `none`)."""

    name: object
    ef: float | None
    unit: object
    via: C3FactorVia


@dataclass(frozen=True)
class EnergyConversion:
    """코랩 `convert_energy_unit` 의 (환산값, 기준단위, 환산비고) 와 그 길."""

    value: float | None
    unit: str
    note: str
    via: EnergyUnitVia


def _is_na(value: object) -> bool:
    """코랩 `pd.isna(x)`(값 하나 — 칸 값은 글·수·None·NaN 뿐이다)."""
    if value is None or value is pd.NA or value is pd.NaT:
        return True
    if isinstance(value, numbers.Real) and not isinstance(value, numbers.Integral):
        return math.isnan(float(value))
    return False


def _where(series: "pd.Series[Any]", test: Callable[[object], bool]) -> "pd.Series[bool]":
    """코랩 `series.apply(lambda x: …)` 의 참거짓 거르개(값마다 차례대로)."""
    return pd.Series([test(v) for v in series], index=series.index, dtype=bool)


def _numeric(value: object) -> float | None:
    """코랩 `pd.to_numeric(x, errors="coerce")` 뒤 `pd.notna` 이면 float."""
    number = pd.to_numeric(pd.Series([value], dtype=object), errors="coerce").iloc[0]
    return None if _is_na(number) else float(number)


# ── 공통 정규화(코랩 :7290 · :7337 · :7423) ──


def ef_norm_unit(unit: object) -> str:
    """코랩 `_ef_norm_unit`(`:7290-7318`)."""
    s = ef_norm_text(unit)
    if not s:
        return ""
    return EF_UNIT_MAP.get(s, s)


def ef_similarity(a: object, b: object) -> float:
    """코랩 `_ef_similarity`(`:7337-7345`)."""
    a, b = ef_norm_text(a), ef_norm_text(b)
    if not a or not b:
        return 0.0
    if a == b:
        return 1.0
    if a in b or b in a:
        return ENERGY_CONTAINS_SIMILARITY
    return SequenceMatcher(None, a, b).ratio()


def unit_match_score(row_unit: object, unit_hint: object) -> float:
    """코랩 `_unit_match_score`(`:7423-7433`)."""
    same, mixed, other = ENERGY_UNIT_BONUS
    ru = ef_norm_unit(row_unit)
    uh = ef_norm_unit(unit_hint)
    if not uh or not ru:
        return 0.0
    if ru == uh:
        return same
    if {ru, uh} <= {"nm3", "m3"}:
        return mixed
    return other


def fix_unit_norm(x: object) -> str:
    """코랩 `_fix_unit_norm`(`:8185-8188`)."""
    s = fix_text(x).lower().replace(" ", "").replace("㎥", "m3").replace("m³", "m3").replace("nm³", "nm3")
    return s.replace("co₂", "co2")


# ── 에너지 시트의 열(코랩 :7351 — 셀 27 `_fix_energy_db_cols` `:8202` 도 이것을 부른다) ──


@dataclass(frozen=True)
class EnergyColumns:
    name: str | None
    ef: str | None
    unit: str | None


def energy_db_cols(db: pd.DataFrame) -> EnergyColumns:
    """코랩 `_energy_db_cols`(`:7351-7361`). `:479` 의 열 찾기(`:490-492`)와 글자가 같다."""
    if db.empty:
        return EnergyColumns(None, None, None)
    columns = [str(c) for c in db.columns]
    name_col = next((c for c in columns if "활동유형" in c or "에너지원" in c), None)
    ef_col = next((c for c in columns if "CO2eq" in c and "★" in c), None) or next(
        (c for c in columns if "CO2eq" in c), None
    )
    unit_col = next((c for c in columns if "기준단위" in c or ("단위" in c and "발열량" not in c)), None)
    return EnergyColumns(name_col, ef_col, unit_col)


def _get(row: "pd.Series[Any]", column: str | None) -> object:
    """코랩 `r.get(col)` — 열이 None 이면 None."""
    return None if column is None else row.get(column)


# ── 셀 8 `:479`(붙잡힌 첫 정의) ──


def lookup_energy_ef_479(db: pd.DataFrame, energy_name: object) -> tuple[object, float | None, object]:
    """코랩 첫 `lookup_energy_ef`(`:479-536`): 정확 → 쌍방향 부분 → 낱말 별칭. 단위 힌트를 보지 않는다."""
    if db.empty:
        return None, None, None
    cols = energy_db_cols(db)
    name_col, ef_col, unit_col = cols.name, cols.ef, cols.unit
    if not name_col or not ef_col:
        return None, None, None
    q = str(energy_name).strip().lower()
    names = colab_str(db[name_col]).str.strip().str.lower()
    exact = db[names == q]
    if not exact.empty:
        r = exact.iloc[0]
        return r[name_col], _numeric(r[ef_col]), _get(r, unit_col)
    for _, r in db.iterrows():
        rname = str(r[name_col]).strip().lower()
        if q in rname or rname in q:
            return r[name_col], _numeric(r[ef_col]), _get(r, unit_col)
    mapped = ENERGY_ALIAS_479.get(q)
    if mapped:
        for _, r in db.iterrows():
            if mapped in str(r[name_col]).lower():
                return r[name_col], _numeric(r[ef_col]), _get(r, unit_col)
    return None, None, None


# ── 셀 24 `:6822`(`:479` → 폴백 계수) ──


def lookup_energy_ef_6822(
    db: pd.DataFrame, energy_name: object
) -> tuple[object, float | None, object, EnergyFactorVia]:
    """코랩 셀 24 `lookup_energy_ef`(`:6822-6841`): 붙잡은 `:479` 가 계수를 내면 그것, 아니면 폴백 계수(dict 차례로
    「키 ⊂ 입력 또는 입력 ⊂ 키」 — 빈 이름은 첫 키에 걸린다). 붙잡은 `:479` 의 예외는 삼키고 폴백으로 간다(코랩
    `:6825-6837` 의 `except TypeError: 이름만 다시 … except Exception: pass` — 우리 `:479` 는 단위 힌트를 받지 않는 같은
    함수라 이름만 다시 불러도 같은 예외다. MARC-ISSUE-395 1번)."""
    try:
        name, ef, unit = lookup_energy_ef_479(db, energy_name)
    except Exception:
        name, ef, unit = None, None, None
    if ef is not None:
        return name, ef, unit, "legacy_479"
    q = patch_safe_text(energy_name).lower()
    for key, (fb_name, fb_ef, fb_unit) in ENERGY_FALLBACK_EF_PATCH.items():
        if key in q or q in key:
            return fb_name, fb_ef, fb_unit, "fallback_patch"
    return None, None, None, "none"


# ── 셀 25 `:7364` · `:7436` · `:7508` ──


def energy_alias_candidates(energy_name: object, unit_hint: object = None) -> list[str]:
    """코랩 `_energy_alias_candidates`(`:7364-7420`)."""
    raw = ef_safe_text(energy_name)
    q = ef_norm_text(raw)
    u = ef_norm_unit(unit_hint)
    candidates: list[str] = []

    def add(*vals: str) -> None:
        for v in vals:
            if v and v not in candidates:
                candidates.append(v)

    add(raw)
    if any(k in q for k in ["전기", "전력", "electricity", "electric", "power", "gridpower"]):
        add("전력")
    if any(k in q for k in ["스팀", "steam", "열스팀", "열"]):
        add("열(스팀)")
    if "cng" in q or "압축천연가스" in q:
        add("CNG(차량)")
    if any(k in q for k in ["lng", "천연가스", "도시가스", "액화천연가스", "naturalgas"]):
        if any(k in q for k in ["차량", "자동차", "vehicle", "truck", "bus"]):
            add("LNG(차량)")
        elif u == "kg" or "천연가스" in q:
            add("천연가스(LNG)", "도시가스(LNG)")
        else:
            add("도시가스(LNG)", "천연가스(LNG)")
    if any(k in q for k in ["lpg", "액화석유가스", "프로판", "부탄"]):
        if any(k in q for k in ["차량", "자동차", "vehicle", "truck", "bus"]):
            add("LPG(차량)")
        elif "도시가스" in q or u in {"nm3", "m3"}:
            add("도시가스(LPG)", "액화석유가스(LPG)")
        else:
            add("액화석유가스(LPG)", "도시가스(LPG)", "LPG(차량)")
    if any(k in q for k in ["경유", "diesel", "dieseloil"]):
        add("경유")
    if any(k in q for k in ["휘발유", "가솔린", "gasoline", "petrol"]):
        add("휘발유")
    if any(k in q for k in ["등유", "kerosene"]):
        add("보일러 등유", "실내 등유")
    if any(k in q for k in ["항공유", "jetfuel", "jet", "aviationfuel"]):
        add("항공유")
    return candidates


@dataclass(frozen=True)
class ResolvedRow:
    """코랩 `resolve_energy_ef_row` 의 (row, match_type, score)."""

    row: "pd.Series[Any] | None"
    match_type: str
    score: float


def resolve_energy_ef_row(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> ResolvedRow:
    """코랩 `resolve_energy_ef_row`(`:7436-7505`). 같은 점수의 줄 차례는 코랩처럼 `sort_values(ascending=False)`."""
    cols = energy_db_cols(db)
    name_col, ef_col, unit_col = cols.name, cols.ef, cols.unit
    if db.empty or not name_col or not ef_col:
        return ResolvedRow(None, "db_empty_or_columns_missing", 0.0)
    work = db.dropna(subset=[name_col]).copy()
    if work.empty:
        return ResolvedRow(None, "db_empty", 0.0)
    q = ef_norm_text(energy_name)
    candidates = energy_alias_candidates(energy_name, unit_hint=unit_hint)

    def _sort_subset(subset: pd.DataFrame, base_score: float) -> "tuple[pd.Series[Any] | None, float]":
        if subset.empty:
            return None, 0.0
        tmp = subset.copy()
        if unit_col:
            tmp["_unit_bonus"] = [unit_match_score(x, unit_hint) for x in tmp[unit_col]]
        else:
            tmp["_unit_bonus"] = 0.0
        tmp["_score"] = base_score + tmp["_unit_bonus"]
        tmp = tmp.sort_values("_score", ascending=False)
        return tmp.iloc[0], float(tmp.iloc[0]["_score"])

    names = work[name_col]
    for idx, cand in enumerate(candidates):
        cn = ef_norm_text(cand)
        subset = work[_where(names, lambda x, cn=cn: ef_norm_text(x) == cn)]
        row, score = _sort_subset(subset, 1.0 if idx == 0 else ENERGY_ALIAS_EXACT_SCORE)
        if row is not None:
            return ResolvedRow(row, "exact_raw" if idx == 0 else "alias_exact", min(score, 1.0))
    base, cap = ENERGY_ALIAS_CONTAINS_SCORE
    for cand in candidates:
        cn = ef_norm_text(cand)
        if not cn:
            continue
        subset = work[_where(names, lambda x, cn=cn: cn in ef_norm_text(x) or ef_norm_text(x) in cn)]
        row, score = _sort_subset(subset, base)
        if row is not None:
            return ResolvedRow(row, "alias_contains", min(score, cap))
    if q:
        base, cap = ENERGY_QUERY_CONTAINS_SCORE
        subset = work[_where(names, lambda x: q in ef_norm_text(x) or ef_norm_text(x) in q)]
        row, score = _sort_subset(subset, base)
        if row is not None:
            return ResolvedRow(row, "contains", min(score, cap))
    scored: list[tuple[float, pd.Series[Any]]] = []
    for _, r in work.iterrows():
        similarity = ef_similarity(energy_name, r.get(name_col))
        scored.append((similarity + (unit_match_score(r.get(unit_col), unit_hint) if unit_col else 0), r))
    if scored:
        best, row_ = max(scored, key=lambda x: x[0])  # 같은 점수면 앞 줄(코랩 `max`)
        if best >= ENERGY_FUZZY_THRESHOLD:
            return ResolvedRow(row_, "fuzzy", min(float(best), ENERGY_FUZZY_CAP))
    return ResolvedRow(None, "not_found", 0.0)


def _match(
    energy_name: object, unit_hint: object, raw_name: object, raw_unit: object, kind: str, score: float | None
) -> EnergyMatch:
    return EnergyMatch(ef_safe_text(energy_name), ef_safe_text(unit_hint), raw_name, raw_unit, kind, score)


def lookup_energy_ef_7508(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> EnergyLookup:
    """코랩 셀 25 `lookup_energy_ef`(`:7508-7568`): 해석한 줄의 계수(DB 단위 TJ 면 GJ 로 ÷1000) → 붙잡은 셀 24 판."""
    cols = energy_db_cols(db)
    name_col, ef_col, unit_col = cols.name, cols.ef, cols.unit
    resolved = resolve_energy_ef_row(db, energy_name, unit_hint=unit_hint)
    row = resolved.row
    if row is not None and ef_col:
        ef = _numeric(row.get(ef_col))
        raw_name = _get(row, name_col)
        raw_unit = _get(row, unit_col)
        # 코랩 `if pd.notna(ef) and raw_unit and str(raw_unit).strip().upper() == "TJ"`(NaN 단위도 참 → "NAN")
        if ef is not None and _truthy(raw_unit) and str(raw_unit).strip().upper() == "TJ":
            ef = ef / 1000.0
            raw_unit = "GJ"
        match = _match(energy_name, unit_hint, raw_name, raw_unit, resolved.match_type, round(float(resolved.score), 4))
        if ef is not None:
            return EnergyLookup(raw_name, ef, raw_unit, RESOLVED_VIA[resolved.match_type], match)
    # 코랩 셀 25 는 이 부름을 `try … except TypeError … except Exception: None` 으로 감싼다(`:7540-7545`). 셀 24 판이
    # `:479` 예외를 삼키고 폴백 고리(글자 다루기·dict 돌기)에 예외 날 길이 없어 그 바깥 try 는 닿지 않는다
    # (S3C-r1 2-0 d).
    name, ef_legacy, unit, legacy_via = lookup_energy_ef_6822(db, energy_name)
    if ef_legacy is not None:
        return EnergyLookup(
            name, ef_legacy, unit, legacy_via, _match(energy_name, unit_hint, name, unit, "legacy_lookup", None)
        )
    match = _match(energy_name, unit_hint, None, None, resolved.match_type, round(float(resolved.score), 4))
    return EnergyLookup(None, None, None, "none", match)


def _truthy(value: object) -> bool:
    """코랩의 `if x` — NaN 은 참, 빈 글·None 은 거짓."""
    if value is None:
        return False
    if isinstance(value, str):
        return value != ""
    return bool(value) or _is_na(value)


# ── 셀 27 `:8213` · `:8229`(이기는 정의) ──


def fix_lookup_energy_title_exact(db: pd.DataFrame, title: str) -> tuple[object, float | None, object]:
    """코랩 `_fix_lookup_energy_title_exact`(`:8213-8224`): `_fix_norm` 이 같은 첫 줄, 계수가 비면 못 찾음."""
    cols = energy_db_cols(db)
    name_col, ef_col, unit_col = cols.name, cols.ef, cols.unit
    if db.empty or not name_col or not ef_col:
        return None, None, None
    subset = db[colab_str(db[name_col]).map(fix_norm) == fix_norm(title)]
    if subset.empty:
        return None, None, None
    r = subset.iloc[0]
    ef = _numeric(r.get(ef_col))
    if ef is None:
        return None, None, None
    return r.get(name_col), ef, _get(r, unit_col)


def lookup_energy_ef(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> EnergyLookup:
    """코랩 전역 `lookup_energy_ef`(`:8229-8257`). 가스 낱말 + 단위 Nm³·m³ → 「도시가스(LNG)」, + kg →
    「천연가스(LNG)」 를 먼저 정확히 찾고(match_type `unit_priority_alias`, score 1.0), 아니면 붙잡은 셀 25 판
    (`:7508`)."""
    q = fix_norm(energy_name)
    u = fix_unit_norm(unit_hint)
    is_gas = any(k in q for k in GAS_WORDS)
    title = "도시가스(LNG)" if is_gas and u in {"nm3", "m3"} else "천연가스(LNG)" if is_gas and u == "kg" else None
    if title is not None:
        name, ef, unit = fix_lookup_energy_title_exact(db, title)
        if ef is not None:
            match = EnergyMatch(fix_text(energy_name), fix_text(unit_hint), name, unit, "unit_priority_alias", 1.0)
            return EnergyLookup(name, ef, unit, "unit_priority_alias", match)
    return lookup_energy_ef_7508(db, energy_name, unit_hint=unit_hint)


# ── 셀 29: C3 계수(`:9053` · `:9057` · `:9061` · `:9069` · `:9113`) ──


def c3_norm(x: object) -> str:
    """코랩 `_c3_norm`(`:9053`) — 셀 25 의 `_ef_norm_text` 가 있으니 그것."""
    return ef_norm_text(x)


def c3_norm_unit(x: object) -> str:
    """코랩 `_c3_norm_unit`(`:9057`) — `_ef_norm_unit`."""
    return ef_norm_unit(x)


def c3_alias_candidates(energy_name: object, unit_hint: object = None) -> list[str]:
    """코랩 `_c3_energy_alias_candidates`(`:9069-9110`)."""
    raw = str(energy_name or "").strip()
    q = c3_norm(raw)
    u = c3_norm_unit(unit_hint)
    candidates: list[str] = []

    def add(*vals: str) -> None:
        for v in vals:
            if v and v not in candidates:
                candidates.append(v)

    add(raw)
    if any(k in q for k in ["전기", "전력", "electricity", "electric", "power"]):
        add("전력")
    if any(k in q for k in ["스팀", "steam", "열"]):
        if "열병합" in q or "chp" in q:
            add("스팀(열병합발전)", "스팀")
        else:
            add("스팀")
    if any(k in q for k in ["lng", "천연가스", "도시가스", "액화천연가스", "naturalgas"]):
        if u == "kg":
            add("천연가스(LNG)", "도시가스(LNG)")
        else:
            add("도시가스(LNG)", "천연가스(LNG)")
    if any(k in q for k in ["lpg", "액화석유가스", "프로판", "부탄"]):
        add("액화석유가스(LPG)")
    if any(k in q for k in ["경유", "diesel"]):
        add("경유")
    if any(k in q for k in ["휘발유", "가솔린", "gasoline", "petrol"]):
        add("휘발유")
    if any(k in q for k in ["등유", "kerosene"]):
        add("등유")
    if any(k in q for k in ["무연탄"]):
        add("무연탄")
    if any(k in q for k in ["벙커c", "bunkerc", "벙커씨"]):
        add("벙커C유")
    if any(k in q for k in ["중유", "heavyoil"]):
        add("중유")
    if any(k in q for k in ["석탄", "유연탄", "coal"]):
        add("석탄")
    return candidates


def lookup_energy_ef_c3(db: pd.DataFrame, energy_name: object, unit_hint: object = None) -> C3Lookup:
    """코랩 `lookup_energy_ef_c3`(`:9113-9143`): 후보마다 정확 → 입력과의 쌍방향 포함. 계수가 빈 줄은 건너뛴다."""
    if db.empty:
        return C3Lookup(None, None, None, "none")
    columns = [str(c) for c in db.columns]
    name_col = next((c for c in columns if "활동유형" in c or "에너지원" in c), None)
    unit_col = next((c for c in columns if "기준단위" in c), None)
    ef_col = next((c for c in columns if "EF" in c and "kgCO2" in c), None)
    if not name_col or not ef_col:
        return C3Lookup(None, None, None, "none")
    names = db[name_col]
    for idx, cand in enumerate(c3_alias_candidates(energy_name, unit_hint=unit_hint)):
        cn = c3_norm(cand)
        subset = db[_where(names, lambda x, cn=cn: c3_norm(x) == cn)]
        if not subset.empty:
            r = subset.iloc[0]
            ef = _numeric(r[ef_col])
            if ef is not None:
                return C3Lookup(
                    r[name_col], ef, r[unit_col] if unit_col else None, "exact_raw" if idx == 0 else "alias_exact"
                )
    q = c3_norm(energy_name)
    if q:
        subset = db[_where(names, lambda x: q in c3_norm(x) or c3_norm(x) in q)]
        if not subset.empty:
            r = subset.iloc[0]
            ef = _numeric(r[ef_col])
            if ef is not None:
                return C3Lookup(r[name_col], ef, r[unit_col] if unit_col else None, "contains")
    return C3Lookup(None, None, None, "none")


# ── 셀 20: 에너지 단위 환산(`:3766` · `:3846`) ──


def detect_energy_name(raw: object) -> str:
    """코랩 `_detect_energy_name`(`:3766-3805`): 별칭 정확 → 표준명 정확 → 별칭 ⊂ 입력. 모르면 원문(글로)."""
    q = str(raw).strip().lower().replace(" ", "").replace("(", "").replace(")", "")
    for std_name, aliases in ENERGY_NAME_ALIAS.items():
        for a in aliases:
            if a.replace(" ", "") == q:
                return std_name
    for std_name in ENERGY_BASE_UNIT:
        if std_name.lower().replace(" ", "") == q:
            return std_name
    for std_name, aliases in ENERGY_NAME_ALIAS.items():
        for a in aliases:
            a_norm = a.replace(" ", "")
            if a_norm and a_norm in q:
                return std_name
    return str(raw)


def _ai(context: LlmContext, cache: UnitFactorCache, input_unit: str, base: str, energy_name: str) -> float | None:
    return ai_unit_conversion_factor(context, cache, input_unit, base, energy_name)


def convert_energy_unit(
    context: LlmContext, cache: UnitFactorCache, value: float | None, input_unit: str, energy_name: str
) -> EnergyConversion:
    """코랩 `convert_energy_unit`(`:3846-3990`): 입력 단위 → 그 에너지원의 기준단위. AI 배수의 맥락은 에너지원 이름."""
    if value is None:
        return EnergyConversion(None, input_unit, "", "none")
    u_in = str(input_unit).strip().lower().replace(" ", "")
    info = ENERGY_BASE_UNIT.get(detect_energy_name(energy_name))
    if info is None:
        return EnergyConversion(value, input_unit, "", "none")
    base_unit, lhv_mj = info
    base_norm = base_unit.lower().replace(" ", "").replace("³", "3").replace("²", "2")
    u_in_norm = u_in.replace("³", "3").replace("²", "2")
    if u_in_norm == base_norm:
        return EnergyConversion(value, base_unit, "", "same")

    if base_norm == "kwh":
        factor = ENERGY_KWH_FACTORS.get(u_in_norm)
        if factor:
            return EnergyConversion(value * factor, "kWh", f"{input_unit}→kWh (×{factor:.6g})", "rule")
        ai_factor = _ai(context, cache, input_unit, "kWh", energy_name)
        if ai_factor:
            return EnergyConversion(value * ai_factor, "kWh", f"{input_unit}→kWh (AI 판단: ×{ai_factor:.6g})", "ai")
        note = f"{input_unit}→kWh (AI 환산 재시도 필요 - 값 미변환, 수동 확인 권장)"
        return EnergyConversion(value, input_unit, note, "ai_failed")

    if base_norm in ("gj", "gj"):
        factor = ENERGY_GJ_FACTORS.get(u_in_norm)
        if factor:
            return EnergyConversion(value * factor, "GJ", f"{input_unit}→GJ (×{factor:.6g})", "rule")
        ai_factor = _ai(context, cache, input_unit, "GJ", energy_name)
        if ai_factor:
            return EnergyConversion(value * ai_factor, "GJ", f"{input_unit}→GJ (AI 판단: ×{ai_factor:.6g})", "ai")
        note = f"{input_unit}→GJ (AI 환산 재시도 필요 - 값 미변환, 수동 확인 권장)"
        return EnergyConversion(value, input_unit, note, "ai_failed")

    if lhv_mj is None or lhv_mj <= 0:
        return EnergyConversion(value, input_unit, "", "none")
    if base_norm == "kg":
        f = ENERGY_KG_FACTORS.get(u_in_norm)
        if f:
            return EnergyConversion(value * f, "kg", f"{input_unit}→kg (×{f})", "rule")
    if base_norm == "l":
        f = ENERGY_VOLUME_FACTORS.get(u_in_norm)
        if f:
            return EnergyConversion(value * f, "L", f"{input_unit}→L (×{f})", "rule")
    if base_norm in ("nm3", "nm³"):
        f = ENERGY_GAS_FACTORS.get(u_in_norm)
        if f:
            return EnergyConversion(value * f, "Nm³", f"{input_unit}→Nm³ (×{f})", "rule")
    mj_factor = ENERGY_MJ_PER_INPUT.get(u_in_norm)
    if mj_factor:
        converted = value * mj_factor / lhv_mj
        note = f"{input_unit}→{base_unit} (발열량 환산: ×{mj_factor / lhv_mj:.6g})"
        return EnergyConversion(converted, base_unit, note, "lhv")
    ai_factor = _ai(context, cache, input_unit, base_unit, energy_name)
    if ai_factor:
        note = f"{input_unit}→{base_unit} (AI 판단: ×{ai_factor:.6g})"
        return EnergyConversion(value * ai_factor, base_unit, note, "ai")
    note = f"{input_unit}→{base_unit} (AI 환산 재시도 필요 - 값 미변환, 수동 확인 권장)"
    return EnergyConversion(value, input_unit, note, "ai_failed")


def bridge_unit_norm(u: object) -> str:
    """코랩 `_bridge_convert_via_lhv` 안의 `_u_norm`(`:9154`) 그대로: `str(u or "")` — 0·0.0·False 도 빈 글자, NaN 은
    「nan」(MARC-ISSUE-395 3번). 시험이 값을 직접 재려고 함수 밖으로 꺼냈다(그 함수 안에서는 거짓 값이 갈래를
    바꾸지 않는다)."""
    return str(u or "").strip().lower().replace(" ", "").replace("³", "3").replace("²", "2")


def bridge_convert_via_lhv(
    value: float | None, value_unit: str, from_energy_name: str, to_energy_name: object, to_unit: object
) -> EnergyConversion:
    """코랩 `_bridge_convert_via_lhv`(`:9146-9171`): 대체 매칭된 연료의 기준단위로 두 발열량을 거쳐(같은 열량 가정)."""
    _u_norm = bridge_unit_norm

    from_info = ENERGY_BASE_UNIT.get(detect_energy_name(from_energy_name))
    to_info = ENERGY_BASE_UNIT.get(detect_energy_name(to_energy_name))
    if not from_info or not to_info:
        return EnergyConversion(value, value_unit, "", "none")
    from_unit, from_lhv = from_info
    to_unit_expected, to_lhv = to_info
    if from_lhv is None or to_lhv is None or to_lhv <= 0:
        return EnergyConversion(value, value_unit, "", "none")
    if _u_norm(value_unit) != _u_norm(from_unit) or _u_norm(to_unit) != _u_norm(to_unit_expected):
        return EnergyConversion(value, value_unit, "", "none")
    if value is None:  # 코랩은 None × 수에서 TypeError(그 시트가 `[error]`) — 부르는 쪽이 값이 있을 때만 부른다
        raise TypeError("unsupported operand type(s) for *: 'NoneType' and 'float'")
    converted = value * from_lhv / to_lhv
    note = f"{value_unit}→{to_unit} (발열량 환산: {from_energy_name}→{to_energy_name}, ×{(from_lhv / to_lhv):.6g})"
    return EnergyConversion(converted, str(to_unit), note, "lhv")


# ── 계수 단위로 맞추기(셀 24 `:6843` · 셀 27 `:8260`)와 한 줄 셈(`:6866` · `:8278`) — C11·C14(S3C-c1b)가 쓴다 ──


def patch_convert_energy_to_ef_unit(
    context: LlmContext, cache: UnitFactorCache, value: object, input_unit: object, energy_name: str, ef_unit: object
) -> EnergyConversion:
    """코랩 `_patch_convert_energy_to_ef_unit`(`:6843-6864`)."""
    v = patch_to_float(value)
    if v is None:
        return EnergyConversion(None, patch_safe_text(input_unit), "", "none")
    in_u = patch_safe_text(input_unit)
    target_u = patch_safe_text(ef_unit) or in_u
    converted: EnergyConversion | None
    try:
        converted = convert_energy_unit(context, cache, v, in_u, energy_name)
    except Exception as error:  # 코랩 `except Exception: pass` — 아래 최소 폴백으로
        if reraises(context, error):
            raise
        converted = None
    if converted is not None:
        if not target_u or patch_safe_text(converted.unit).lower() == target_u.lower():
            return converted
        if in_u.lower() == target_u.lower():
            return EnergyConversion(v, in_u, "", "same")
        return converted
    if not target_u or in_u.lower() == target_u.lower():
        return EnergyConversion(v, in_u, "", "same")
    return EnergyConversion(v, in_u, f"단위확인 필요({in_u}→{target_u})", "none")


def fix_convert_to_ef_unit(
    context: LlmContext, cache: UnitFactorCache, value: object, input_unit: object, energy_name: str, ef_unit: object
) -> EnergyConversion:
    """코랩 `_fix_convert_to_ef_unit`(`:8260-8275`): 계수 단위와 다르면 값 None(산정 보류)."""
    v = fix_num(value)
    if v is None:
        return EnergyConversion(None, fix_text(input_unit), "", "none")
    in_u = fix_text(input_unit)
    target_u = fix_text(ef_unit) or in_u
    try:
        conv = convert_energy_unit(context, cache, v, in_u, energy_name)
        if fix_unit_norm(conv.unit) == fix_unit_norm(target_u):
            return conv
        if fix_unit_norm(in_u) == fix_unit_norm(target_u):
            return EnergyConversion(v, in_u, "", "same")
        return EnergyConversion(None, conv.unit, f"[단위 불일치로 산정 보류: {in_u}→{target_u}]", conv.via)
    except Exception as error:  # 코랩 그대로
        if reraises(context, error):
            raise
        if fix_unit_norm(in_u) == fix_unit_norm(target_u):
            return EnergyConversion(v, in_u, "", "same")
        return EnergyConversion(None, in_u, f"[단위 확인 필요: {in_u}→{target_u}]", "none")


@dataclass(frozen=True)
class EnergyUsageRow:
    """코랩 `_fix_calc_energy_usage_row` 의 (usage, std_unit, unit_note, std_name, ef_val, ef_unit, emission_t)."""

    usage_raw: float | None
    unit_raw: str
    lookup: EnergyLookup
    ef: float | None
    conversion: EnergyConversion
    emission_t: float | None


ENERGY_COLUMNS_8278: Final = ("에너지원", "에너지종류", "에너지명", "연료/에너지명", "연료 종류")


def fix_calc_energy_usage_row(
    context: LlmContext, cache: UnitFactorCache, db: pd.DataFrame, row: "pd.Series[Any]", usage_col: str = "사용량",
    energy_cols: tuple[str, ...] = ENERGY_COLUMNS_8278,
) -> EnergyUsageRow:  # fmt: skip
    """코랩 `_fix_calc_energy_usage_row`(`:8278-8290`): 단위 힌트를 넘겨 사슬을 부르고, 환산의 맥락은 찾은 이름."""
    energy_name = ""
    for c in energy_cols:
        if c in row.index and fix_text(row.get(c)):
            energy_name = fix_text(row.get(c))
            break
    usage_raw = fix_num(row.get(usage_col))
    unit_raw = fix_text(row.get("단위"))
    found = lookup_energy_ef(db, energy_name, unit_hint=unit_raw)
    ef = fix_num(found.ef)
    std_name = found.name
    # std_name 이 NaN 이면 코랩은 NaN 객체, 우리는 "nan" 글자를 넘기지만 소비자(`detect_energy_name` → 기준단위 없음 →
    # 값 그대로)에서 갈림이 없다 — AI 배수·발열량에 닿지 않는다(MARC-ISSUE-395 2번, S3C-r1 2-0 e: 그대로 + 시험)
    context_name = str(std_name) if _truthy(std_name) else energy_name  # 코랩 `std_name or energy_name`
    conv = fix_convert_to_ef_unit(context, cache, usage_raw, unit_raw, context_name, found.unit)
    emission = (conv.value * ef / 1000.0) if (conv.value is not None and ef is not None) else None
    return EnergyUsageRow(usage_raw, unit_raw, found, ef, conv, emission)


def patch_pick_energy_name(row: "pd.Series[Any]") -> str:
    """코랩 `_patch_calc_energy_row`(`:6866`)의 이름 고르기 — C11 의 셀 24 판(`:6961`)이 쓴다."""
    return patch_safe_text(patch_pick_first(row, ["에너지원", "에너지종류", "에너지명", "연료/에너지명"]))


# ── S3C-c1a ②: 시트 갈래 C3·C8·C13(코랩 `process_new_template` `:6070-6113` · `:6146-6168`) ──
# 산정 출처(코랩에는 없다 — 값은 바꾸지 않는다): factor 사슬 `fallback_patch` → estimate, 그 밖의 고리 → rule ·
# unit(환산) rule·lhv → rule, ai → ai, ai_failed → estimate, same·none → 단계 없음. 줄 origin = 숫자에 닿는 단계(unit·
# factor) 가운데 가장 약한 것, factor 단계가 없으면 None(활동 줄과 같은 규칙).

ENERGY_SHEET_KINDS: Final[dict[str, ColabEnergyKind]] = {
    "c3": "fuel_energy",
    "c8_energy": "leased_asset",
    "c8_area": "leased_asset",
    "c8_person": "leased_asset",
    "c13_energy": "leased_out_asset",
    "c13_area": "leased_out_asset",
    "c13_person": "leased_out_asset",
}
_STRENGTH: Final[dict[ColabOrigin, int]] = {"rule": 0, "ai": 1, "estimate": 2}
_UNIT_ORIGIN: Final[dict[EnergyUnitVia, ColabOrigin]] = {
    "rule": "rule",
    "lhv": "rule",
    "ai": "ai",
    "ai_failed": "estimate",
}


def unit_origin_step(via: EnergyUnitVia) -> ActivityOriginStep | None:
    origin = _UNIT_ORIGIN.get(via)
    return None if origin is None else ActivityOriginStep("unit", origin, via)


def energy_factor_step(via: EnergyFactorVia | C3FactorVia) -> ActivityOriginStep | None:
    if via == "none":
        return None
    return ActivityOriginStep("factor", "estimate" if via == "fallback_patch" else "rule", via)


@dataclass(frozen=True)
class EnergyAllocation:
    """C8·C13 의 배분(코랩 표준화 칸 「산정방식」·「건물전체사용량」·「면적비율」·「인원비율」)."""

    method: str
    building_total: float | None
    area_ratio: float | None
    person_ratio: float | None


@dataclass(frozen=True)
class EnergyMeta:
    """에너지 줄의 메타(코랩 결과 행에는 없는 것): 입력 줄·사용량과 환산·쓴 계수·사슬 매칭·배분·산정 출처."""

    excel_row: int | None
    kind: ColabEnergyKind
    month: int | None
    activity: ActivityAmount
    factor: ActivityFactor | None
    steps: tuple[ActivityOriginStep, ...]
    match: EnergyMatch | None = None
    allocation: EnergyAllocation | None = None

    @property
    def origin(self) -> ColabOrigin | None:
        if not any(s.step == "factor" for s in self.steps):
            return None
        return max((s.origin for s in self.steps if s.step in ("unit", "factor")), key=_STRENGTH.__getitem__)


@dataclass
class EnergyRun:
    """실행 하나의 에너지 상태: 계수 시트 둘(코랩 `energy_ef_db`·`energy_c3_ef_db`)과 AI 배수 캐시(C5 와 같음)."""

    energy: FactorSheetRead
    energy_c3: FactorSheetRead
    llm: LlmContext
    units: UnitFactorCache


@dataclass(frozen=True)
class EnergySheet:
    frame: pd.DataFrame
    metas: tuple[EnergyMeta, ...]


@dataclass(frozen=True)
class EmptyEnergySheet:
    """`read_template_sheet` 가 빈 frame 을 냈다(코랩 `[empty]`)."""


def standardize_c3_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c3_sheet`(`:5078-5097`): 월별 줄이 먼저, 연간 줄이 뒤(녹이기는 「사용량」 이 이미 있어 실패 —
    월 합은 본 고리 `_sum_monthly`)."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if "연료/에너지명" in df.columns and "에너지원" not in df.columns:
        rename["연료/에너지명"] = "에너지원"
    if "연간사용량" in df.columns and "사용량" not in df.columns:
        rename["연간사용량"] = "사용량"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    return melt_monthly_or_annual(df, month_var_name="사용월", value_name="사용량", annual_col_hint="연간사용량")


_LEASED_RENAMES: Final = [
    ("에너지종류", "에너지원"),
    ("연간사용량", "사용량"),
    ("건물전체 연간사용량", "건물전체사용량"),
    ("건물전체 면적", "건물전체면적"),
    ("사용 면적", "사용면적"),
    ("건물전체 인원수", "건물전체인원수"),
    ("자사 인원수", "자사인원수"),
]


def patch_prepare_leased_usage(df: pd.DataFrame, asset_col: str) -> pd.DataFrame:
    """코랩 `_patch_prepare_leased_usage`(`:6875-6898`)."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if asset_col in df.columns and "자산명" not in df.columns:
        rename[asset_col] = "자산명"
    for old, new in _LEASED_RENAMES:
        if old in df.columns and new not in df.columns:
            rename[old] = new
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    return df


def _standardize_leased_energy(df: pd.DataFrame, asset_col: str, flag_col: str) -> pd.DataFrame:
    """코랩 뒤 정의 `standardize_c8_energy_sheet`·`standardize_c13_energy_sheet`(`:6901` · `:6908`)."""
    df = patch_prepare_leased_usage(df, asset_col)
    df = collapse_monthly_to_value(df, "사용량", annual_cols=["연간사용량"])
    df[flag_col] = True
    df["산정방식"] = "에너지사용량"
    return df


def _standardize_share(
    df: pd.DataFrame, asset_col: str, flag_col: str, ratio_col: str, total_col: str, own_col: str, method: str
) -> pd.DataFrame:
    """코랩 `_patch_standardize_area`·`_patch_standardize_person`(`:6915` · `:6932`)."""
    df = patch_prepare_leased_usage(df, asset_col)
    df = collapse_monthly_to_value(df, "건물전체사용량", annual_cols=["건물전체사용량", "건물전체 연간사용량"])

    def _ratio(r: "pd.Series[Any]") -> float | None:
        total = patch_to_float(r.get(total_col))
        part = patch_to_float(r.get(own_col))
        if not total:
            return None
        if part is None:  # 코랩 `(used / total)` 은 None 에서 TypeError(그 시트가 `[error]`)
            raise TypeError("unsupported operand type(s) for /: 'NoneType' and 'float'")
        return part / total

    df[ratio_col] = [_ratio(r) for _, r in df.iterrows()]

    def _usage(r: "pd.Series[Any]") -> float | None:
        building = patch_to_float(r.get("건물전체사용량"))
        ratio = r.get(ratio_col)
        if building is not None and not _is_na(ratio):
            return building * float(cast_float(ratio))
        return None

    df["사용량"] = [_usage(r) for _, r in df.iterrows()]
    df[flag_col] = True
    df["산정방식"] = method
    return df


def cast_float(value: object) -> float:
    """배분 비율 칸(이미 수)."""
    if isinstance(value, numbers.Real):
        return float(value)
    raise TypeError(f"비율이 수가 아니다: {value!r}")


_LEASED: Final[dict[str, tuple[str, str]]] = {
    "c8": ("임차자산명", "임차자산여부"),
    "c13": ("임대자산명", "임대자산여부"),
}


def standardize_energy_sheet(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """열쇠 → 이기는 표준화(C3 `:5078`, C8·C13 은 셀 24 뒤 정의 `:6901`·`:6908`·`:6949-6958` — `:7109` 가 다시 단다)."""
    if key == "c3":
        return standardize_c3_sheet(df)
    family, _, variant = key.partition("_")
    asset_col, flag_col = _LEASED[family]
    if variant == "energy":
        return _standardize_leased_energy(df, asset_col, flag_col)
    if variant == "area":
        return _standardize_share(df, asset_col, flag_col, "면적비율", "건물전체면적", "사용면적", "면적배분")
    return _standardize_share(df, asset_col, flag_col, "인원비율", "건물전체인원수", "자사인원수", "인원배분")


def _excel_row(row: "pd.Series[Any]") -> int | None:
    value = row.get(TEMPLATE_ROW)
    return int(value) if isinstance(value, numbers.Integral) else None


def _text_or_none(value: object) -> str | None:
    s = fix_text(value)
    return s or None


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    f = float(value)
    return f if math.isfinite(f) else None


def _or(*values: object) -> object:
    """코랩 `a or b`(NaN 은 참)."""
    for value in values[:-1]:
        if _truthy(value):
            return value
    return values[-1]


def _c3_row(run: EnergyRun, row: "pd.Series[Any]", out: dict[str, object]) -> EnergyMeta:
    """코랩 C3 본 고리 한 줄(`:6077-6112`). 「사용량」 칸은 환산 전 값 그대로 둔다."""
    energy_name = fix_text(_or(row.get("에너지원"), row.get("연료/에너지명")))
    usage_raw = to_float(_or(row.get("사용량"), row.get("월사용량")))
    unit_raw = fix_text(row.get("단위"))
    found = lookup_energy_ef_c3(run.energy_c3.frame, energy_name)
    ef_val = to_float(found.ef)
    ef_unit = found.unit
    conv = convert_energy_unit(run.llm, run.units, usage_raw, unit_raw, energy_name)
    usage, std_unit, unit_note = conv.value, conv.unit, conv.note
    vias: list[EnergyUnitVia] = [conv.via]
    if std_unit and std_unit != ef_unit:
        second = convert_energy_unit(run.llm, run.units, usage, std_unit, energy_name)
        if second.unit == ef_unit:
            usage, std_unit, unit_note = second.value, second.unit, (unit_note + " → " + second.note).strip(" → ")  # noqa: B005 — 코랩 글자 그대로(글자 모음 strip)
            vias.append(second.via)
        elif _truthy(found.name) and found.name != energy_name:
            bridged = bridge_convert_via_lhv(usage, std_unit, energy_name, found.name, ef_unit)
            if bridged.unit == ef_unit:
                usage, std_unit = bridged.value, bridged.unit
                unit_note = (unit_note + " → " + bridged.note).strip(" → ")  # noqa: B005 — 코랩 글자 그대로(글자 모음 strip)
                vias.append(bridged.via)
    emission = (usage * ef_val / 1000) if (usage is not None and ef_val) else None
    out["배출계수(kgCO2eq/단위)"] = ef_val
    out["EF단위"] = ef_unit
    out["EF매핑명"] = found.name
    if unit_note:
        out["단위환산비고"] = unit_note
    out["배출량(tCO2e)"] = emission
    steps = [s for s in (unit_origin_step(v) for v in vias) if s is not None]
    factor_step = energy_factor_step(found.via)
    if factor_step is not None:
        steps.append(factor_step)
    ef_col = next((str(c) for c in run.energy_c3.frame.columns if "EF" in str(c) and "kgCO2" in str(c)), None)
    factor = ActivityFactor(
        ENERGY_C3_SHEET, _text_or_none(found.name), _finite(ef_val), fix_text(ef_unit), ef_col if factor_step else None,
        None,
    )  # fmt: skip
    amount = ActivityAmount(usage_raw, unit_raw, _finite(usage), str(std_unit), unit_note or None)
    month = coerce_month_value(row.get("사용월"))
    return EnergyMeta(_excel_row(row), "fuel_energy", month, amount, factor, tuple(steps))


def _leased_row(run: EnergyRun, row: "pd.Series[Any]", out: dict[str, object], kind: ColabEnergyKind) -> EnergyMeta:
    """코랩 C8·C13 본 고리 한 줄(`:6153-6167`) — 사슬은 **단위 힌트 없이**(`:6157`)."""
    energy_name = fix_text(_or(row.get("에너지원"), row.get("에너지종류")))
    usage_raw = to_float(row.get("사용량"))
    unit_raw = fix_text(row.get("단위"))
    found = lookup_energy_ef(run.energy.frame, energy_name)
    ef_val = to_float(found.ef)
    conv = convert_energy_unit(run.llm, run.units, usage_raw, unit_raw, energy_name)
    emission = (conv.value * ef_val / 1000) if (conv.value is not None and ef_val) else None
    out["배출계수(kgCO2eq/단위)"] = ef_val
    out["EF단위"] = found.unit
    if conv.note:
        out["단위환산비고"] = conv.note
    out["배출량(tCO2e)"] = emission
    steps = [s for s in (unit_origin_step(conv.via),) if s is not None]
    factor_step = energy_factor_step(found.via)
    if factor_step is not None:
        steps.append(factor_step)
    column = energy_db_cols(run.energy.frame).ef if found.via not in ("fallback_patch", "none") else None
    factor = ActivityFactor(
        ENERGY_SHEET, _text_or_none(found.name), _finite(ef_val), fix_text(found.unit), column, None
    )
    amount = ActivityAmount(usage_raw, unit_raw, _finite(conv.value), conv.unit, conv.note or None)
    allocation = EnergyAllocation(
        fix_text(row.get("산정방식")),
        _finite(patch_to_float(row.get("건물전체사용량"))),
        _finite(row.get("면적비율")),
        _finite(row.get("인원비율")),
    )
    return EnergyMeta(_excel_row(row), kind, None, amount, factor, tuple(steps), found.match, allocation)


def process_energy_sheet(run: EnergyRun, sheet: Sheet, key: str, category: str) -> EnergySheet | EmptyEnergySheet:
    """코랩 `process_new_template` 의 시트 하나(Category3·8·13 갈래). C8·C13 의 시트 셋은 결과 시트에서 이어 붙는다
    (`pd.concat` `:6238` — 부르는 쪽·dump 의 몫)."""
    df = read_template_rows(sheet)
    if df.empty:
        return EmptyEnergySheet()
    df = standardize_energy_sheet(df, key)
    df["자동카테고리"] = category
    df["출처시트"] = sheet.name
    month_cols = [c for c in df.columns if c in set(PURCHASE_WIDE_MONTH_COLS)]
    df = sum_monthly(df, "사용량", month_cols)
    kind = ENERGY_SHEET_KINDS[key]
    rows_out: list[dict[str, object]] = []
    metas: list[EnergyMeta] = []
    for _, row in df.iterrows():
        out = {str(k): v for k, v in row.to_dict().items()}
        metas.append(_c3_row(run, row, out) if key == "c3" else _leased_row(run, row, out, kind))
        rows_out.append(out)
    return EnergySheet(pd.DataFrame(rows_out), tuple(metas))
