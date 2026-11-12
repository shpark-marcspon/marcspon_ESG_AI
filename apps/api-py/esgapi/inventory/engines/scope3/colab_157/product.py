"""판매제품 폐기(C12)·투자(C15) — 코랩 셀 8·22·24·28 의 몫(S3C-c1b-1). C11·C14 는 S3C-c1b-2 가 이 파일에 더한다.

- C12 표준화는 셀 24 `standardize_c12_sheet`(`:7000` — `SHEET_PROCESSOR_MAP.update` `:7109` 가 다시 단다, `:5485` 는
  타지 않는다): 「(선택)」 을 뗀 처리비중 열, 드롭다운 보조목록 열 지우기, 제품명·판매량·제품중량이 다 든 줄만.
- C12 셈은 본 고리(`:6170-6188`)가 `globals()` 로 찾는 `calc_c12_ef_and_emission`(셀 28 `:8949`, 정의 하나 —
  `calc_c12_emission` 은 쓰이지 않는다): 코드(`"<코드> | <이름>"` 의 `|` 앞, 「선택안함」 은 빈 코드 — `_c12_clean_code`
  `:8941`)를 소분류 → 중분류 → 대분류 차례로 `폐기물_C12` 에서 찾고(`lookup_waste_ef_by_code` `:720`), 코드가 없으면
  제품명으로 `폐기물_C5` 를(`lookup_waste_ef` `:653`), 그것도 없으면 처리방법 평균. 처리비중으로 가중한 계수, 처리비중이
  하나도 없으면 세 평균의 평균(`:8998`). 생물기원은 코드 접두(`BIOGENIC_C12_CODE_PREFIX` `:365`)나 제품명
  (`_biogenic_group_from_name`)으로 고른 그룹의 「소각」 몫만 나누고, 배출량(tCO2e)은 화석기원으로 갈음된다.
- C15 는 표준화(`:5610`)가 「배출량」(단위 없는 이름) = (Scope1 + Scope2) × 지분율 / 100 을 짓고 본 고리는
  `pass`(`:6192`)다. 계수를 쓰지 않는다.
- 코랩과 같은 흠 셋(`MARC-ISSUE-390`, 고치지 않음 — `MARC-ENT-442`): ① C12 처리비중 칸이 비면 NaN 이 None 이 아니라서
  계수·배출량·화석기원이 빈다(셋 다 비어도 평균 갈래로 안 감) ② 중·소분류 칸이 비면 코드가 글 「nan」 이 되어 소분류
  「nan」 을 찾다 처리방법 평균으로 떨어진다 ③ C15 칸이 비면 `to_float(NaN) or 0` 이 NaN 을 지나 배출량이 빈다.
- 코랩 전역 `waste_c12_db`·`waste_c5_db` 는 인자(`ProductRun`)로 받는다. C12·C15 는 AI·지오코더를 부르지 않는다.

C11(판매제품 사용)·C14(프랜차이즈) — S3C-c1b-2. 둘 다 계수 시트 `에너지`(C8·C13 과 같은 사슬
`energy.lookup_energy_ef`)와 C5·C3·C8 과 같은 AI 배수 캐시(`EnergyRun.units`)를 쓴다.
- 처리 때: C11 은 셀 24 `standardize_c11_sheet`(`:6961` — 수량 × 제품당 연간 사용량 × 수명/12, 환산
  `_patch_convert_energy_to_ef_unit` `:6844` 은 날 이름 맥락)를, C14 는 `standardize_c14_sheet`(`:5590`, rename 만)를
  하고, 셀 25 `:7613`·`:7623`(`:7787` 이 다시 닮)이 `annotate_energy_mapping_columns`(`:7583`)로 EF매핑명·EF매핑방식·
  EF매핑점수를 덧붙인다. 본 고리 갈래는 없다(`:6070-6192`).
- 최종 값은 결과 후처리(`_postprocess_scope3_result_file` `:8878` — pipeline 이 시트 고리 뒤 결과 시트 차례로 부름):
  C11_ 은 전역 `standardize_c11_sheet`(셀 27 `:8720` — 이름은 `에너지명 or 에너지원`, 사슬에 단위 힌트, 환산
  `_fix_convert_to_ef_unit` `:8257` 은 `std_name or energy_name` 맥락 — 단위가 계수와 다르면 「산정 보류」),
  C14_ 는 `_fix_result_energy_sheet`(`:8862` → `_fix_calc_energy_usage_row` `:8277`, 계산식). 후처리는 코랩이 다시
  읽는 결과 파일의 꼴(`result_view`)에서 센다. EF매핑방식·EF매핑점수는 처리 때 값 그대로 남는다.
"""

import math
import numbers
import re
from dataclasses import dataclass
from typing import Any, Final

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.activity import (
    COLS_TO_DROP,
    ActivityAmount,
    ActivityFactor,
    ActivityOriginStep,
)
from esgapi.inventory.engines.scope3.colab_157.constants import BIOGENIC_C12_CODE_PREFIX, WASTE_AVG_EF
from esgapi.inventory.engines.scope3.colab_157.energy import (
    ColabEnergyKind,
    EnergyConversion,
    EnergyLookup,
    EnergyMatch,
    EnergyRun,
    energy_db_cols,
    energy_factor_step,
    fix_calc_energy_usage_row,
    fix_convert_to_ef_unit,
    lookup_energy_ef,
    patch_convert_energy_to_ef_unit,
    unit_origin_step,
)
from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    ENERGY_SHEET,
    WASTE_C5_SHEET,
    WASTE_C12_SHEET,
    FactorSheetRead,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.engines.scope3.colab_157.purchase import ColabOrigin, fix_num, fix_text, to_float
from esgapi.inventory.engines.scope3.colab_157.spend import ef_safe_text
from esgapi.inventory.engines.scope3.colab_157.template import (
    TEMPLATE_ROW,
    normalize_template_columns,
    read_template_rows,
)
from esgapi.inventory.engines.scope3.colab_157.transport import patch_safe_text, patch_to_float
from esgapi.inventory.engines.scope3.colab_157.waste import (
    BiogenicSplit,
    WasteFactor,
    biogenic_fossil_split,
    biogenic_group_from_name,
    lookup_waste_ef,
    normalize_treatment,
)
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

PRODUCT_SHEET_KINDS: Final[dict[str, ColabEnergyKind]] = {
    "c12": "product_eol",
    "c15": "investment",
    "c11": "product_use",
    "c14": "franchise",
}
C12_FACTOR_UNIT: Final = "kgCO2eq/kg"
INVESTMENT_UNIT: Final = "tCO2eq"


# ── C12 표준화(`:7000-7036`) ──

_C12_OPTIONAL_COLS: Final = ["재활용 비중(%)(선택)", "소각 비중(%)(선택)", "매립 비중(%)(선택)", "기타 비중(%)(선택)"]
_C12_ALLOWED: Final = frozenset(
    {
        "국가", "폐기물 대분류(선택)", "폐기물 중분류(선택)", "폐기물 소분류(선택)",
        "제품명", "판매량", "제품중량", "제품중량 단위",
        "재활용 비중(%)", "소각 비중(%)", "매립 비중(%)", "기타 비중(%)",
        "설명/적요", "입력방식", "비고", "배출량(tCO2e)", "배출량",
    }
)  # fmt: skip
_C12_HELPER_CODE: Final = re.compile(r"^\d{2}(?:-\d{2}){0,2}\b")
_C12_REQUIRED: Final = ["제품명", "판매량", "제품중량"]


def standardize_c12_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 셀 24 `standardize_c12_sheet`(`:7000-7036`)."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    for col in _C12_OPTIONAL_COLS:
        clean = col.replace("(선택)", "").strip()
        if col in df.columns:
            rename[col] = clean
    if "설명/적요(선택)" in df.columns:
        rename["설명/적요(선택)"] = "설명/적요"
    if rename:
        df = df.rename(columns=rename)
    helper_cols: list[object] = []
    for c in df.columns:  # 시트 오른쪽 드롭다운 보조목록이 머리글처럼 읽힌 열
        cs = patch_safe_text(c).strip()
        if cs in _C12_ALLOWED:
            continue
        if "|" in cs or _C12_HELPER_CODE.match(cs):
            helper_cols.append(c)
    if helper_cols:
        df = df.drop(columns=helper_cols, errors="ignore")
    present = [c for c in _C12_REQUIRED if c in df.columns]
    if present:
        mask = df[present].notna().any(axis=1)
        if all(c in df.columns for c in _C12_REQUIRED):
            mask = df[_C12_REQUIRED].notna().all(axis=1)
        df = df[mask].reset_index(drop=True)
    return df


# ── C12 셈(`:8941-9014`) ──


def c12_clean_code(x: object) -> str:
    """코랩 `_c12_clean_code`(`:8941`). 빈 칸(NaN)은 글 「nan」 이 된다(흠 ② — 코랩 그대로)."""
    s = str(x if x is not None else "").strip()
    if not s or s == "-" or "선택안함" in s:
        return ""
    return s.split("|")[0].strip() if "|" in s else s


def biogenic_group_from_code(code: object) -> str | None:
    """코랩 `_biogenic_group_from_code`(`:386-391`)."""
    c = str(code if code is not None else "").strip()
    for prefix, group in BIOGENIC_C12_CODE_PREFIX:
        if c.startswith(prefix):
            return group
    return None


def _numeric(value: object) -> float | None:
    val = pd.to_numeric(pd.Series([value], dtype=object), errors="coerce").iloc[0]
    return None if pd.isna(val) else float(val)


def lookup_waste_ef_by_code(
    db: pd.DataFrame, big: str | None = None, mid: str | None = None, sub: str | None = None, treatment: str = "소각"
) -> WasteFactor:
    """코랩 `lookup_waste_ef_by_code`(`:720-765`). 소분류 → 중분류 → 대분류 차례로 그 코드의 첫 줄, 계수가 비면 평균.
    못 찾으면 처리방법 평균(via `treatment_average`)."""
    treatment_std = normalize_treatment(treatment) if treatment else "소각"
    fallback_value = WASTE_AVG_EF.get(treatment_std) if treatment_std is not None else None
    fallback = WasteFactor(fallback_value, "treatment_average" if fallback_value is not None else None)
    if db.empty:
        return fallback
    columns = [str(c) for c in db.columns]
    big_col = next((c for c in columns if "대분류" in c and "코드" in c), None)
    mid_col = next((c for c in columns if "중분류" in c and "코드" in c), None)
    sub_col = next((c for c in columns if "소분류" in c and "코드" in c), None)
    ef_map = {
        "매립": next((c for c in columns if "매립 EF" in c or ("매립" in c and "EF" in c)), None),
        "소각": next((c for c in columns if "소각 EF" in c or ("소각" in c and "EF" in c)), None),
        "재활용": next((c for c in columns if "재활용 EF" in c or ("재활용" in c and "EF" in c)), None),
    }
    ef_col = ef_map.get(treatment_std) if treatment_std is not None else None
    if not ef_col:
        return fallback
    for code, col, via in ((sub, sub_col, "sub_code"), (mid, mid_col, "mid_code"), (big, big_col, "big_code")):
        if code and col:
            filtered = db[colab_str(db[col]).str.strip() == str(code).strip()]
            if not filtered.empty:
                val = _numeric(filtered.iloc[0][ef_col])
                return WasteFactor(val, via) if val is not None else fallback
    return fallback


@dataclass(frozen=True)
class C12Factor:
    """처리방법 셋의 계수를 고른 길: 코드 / 제품명(폐기물_C5) / 처리방법 평균 / 처리비중이 없어 세 평균의 평균."""

    branch: str  # code · name · average(처리방법 평균 — 코드·제품명이 없거나, 처리비중이 하나도 없어 세 평균의 평균)
    code: str | None  # 실제로 찾은 코드(코드 길에서 계수 시트에 걸린 것), 그 밖은 None
    sheet: str
    parts: tuple[WasteFactor, ...]  # 처리비중이 든 처리방법의 찾은 계수(가중에 들어간 것)


C12_TREATMENTS: Final = ("매립", "소각", "재활용")
"""처리방법 셋의 엔진 차례(`calc_c12_ef_and_emission` 의 가중 고리 차례 — 「기타」 칸은 없다)."""


@dataclass(frozen=True)
class C12Part:
    """처리방법 하나(S3Q1 — 보기 칸). share 는 `_pct` 뒤 0~1 수(NaN 그대로), factor 는 찾은 계수(비중이 하나도 없는
    줄은 처리방법 평균), used 는 가중에 들었는가(가중 고리의 조건 그대로)."""

    treatment: str
    share: float | None
    factor: float | None
    used: bool


@dataclass(frozen=True)
class C12Treatments:
    """C12 줄의 처리방법별 값(S3Q1 Q5~Q7 — 셈에 닿지 않는 적기만). branch 는 C12Factor.branch(비중이 하나도 없으면
    average), share_total 은 used 비중의 합(표시용 — 배출량에 안 닿음, 비중이 하나도 없으면 None)."""

    branch: str
    share_total: float | None
    parts: tuple[C12Part, ...]


def _c12_treatments(branch: str, no_pct: bool, found: tuple[tuple[float | None, WasteFactor], ...]) -> C12Treatments:
    """가중 고리가 이미 쓴 값(pct·찾은 계수)을 처리방법 줄로 적는다. 셈 0 — 합계 비중만 더한다(표시용)."""
    if no_pct:
        averages = tuple(C12Part(name, None, WASTE_AVG_EF.get(name), False) for name in C12_TREATMENTS)
        return C12Treatments("average", None, averages)
    parts = tuple(
        C12Part(name, pct, part.value, pct is not None and part.value is not None)
        for name, (pct, part) in zip(C12_TREATMENTS, found, strict=True)
    )
    used = [part.share for part in parts if part.used and part.share is not None]
    return C12Treatments(branch, sum(used) if used else None, parts)


@dataclass(frozen=True)
class C12Calc:
    """C12 줄 하나의 셈: 코랩이 줄에 더하는 칸과 메타에 쓸 것. 판매량·제품중량이 수가 아니면 factor·split 이 None."""

    columns: dict[str, object]
    total_weight: float | None  # 판매량 × 제품중량(입력 단위)
    unit: str
    total_weight_kg: float | None
    weighted_ef: float | None
    factor: C12Factor | None
    split: BiogenicSplit | None
    treatments: C12Treatments | None = None  # S3Q1 — 처리방법별 보기 칸(셈에 닿지 않음)


def _pct(v: float | None) -> float | None:
    if v is None:
        return None
    return v / 100.0 if v > 1 else v


def _colab_or(a: object, b: object) -> object:
    """코랩 `a or b`(NaN 은 참이라 그대로, 0·빈 글은 거짓이라 b)."""
    if a is None:
        return b
    if isinstance(a, float) and math.isnan(a):
        return a
    return a if a else b


def calc_c12_ef_and_emission(waste_c12: pd.DataFrame, waste_c5: pd.DataFrame, row: "pd.Series[Any]") -> C12Calc:
    """코랩 `calc_c12_ef_and_emission`(`:8949-9014`)."""
    qty = to_float(row.get("판매량"))
    weight = to_float(row.get("제품중량"))
    unit = str(_colab_or(row.get("제품중량 단위"), "kg")).strip().lower()
    if qty is None or weight is None:
        return C12Calc({"배출계수": None, "배출량(tCO2e)": None}, None, unit, None, None, None, None)
    total_weight = qty * weight
    if unit in ["g", "gram", "그램"]:
        weight = weight / 1000.0
    elif unit in ["ton", "t", "톤"]:
        weight = weight * 1000.0
    total_weight_kg = qty * weight

    pct_lf = _pct(to_float(_colab_or(row.get("매립 비중(%)"), row.get("매립비중(%)"))))
    pct_inc = _pct(to_float(_colab_or(row.get("소각 비중(%)"), row.get("소각비중(%)"))))
    pct_rec = _pct(to_float(_colab_or(row.get("재활용 비중(%)"), row.get("재활용비중(%)"))))

    sub = c12_clean_code(row.get("폐기물 소분류(선택)"))
    mid = c12_clean_code(row.get("폐기물 중분류(선택)"))
    big = c12_clean_code(row.get("폐기물 대분류(선택)"))
    product = str(_colab_or(row.get("제품명"), "")).strip()

    def _ef(treatment: str) -> WasteFactor:
        if sub:
            return lookup_waste_ef_by_code(waste_c12, sub=sub, treatment=treatment)
        if mid:
            return lookup_waste_ef_by_code(waste_c12, mid=mid, treatment=treatment)
        if big:
            return lookup_waste_ef_by_code(waste_c12, big=big, treatment=treatment)
        if product:
            return lookup_waste_ef(waste_c5, product, treatment)
        value = WASTE_AVG_EF.get(normalize_treatment(treatment) or "")
        return WasteFactor(value, "treatment_average" if value is not None else None)

    f_lf, f_inc, f_rec = _ef("매립"), _ef("소각"), _ef("재활용")
    code = sub or mid or big or None
    if code is not None:
        branch, sheet = "code", WASTE_C12_SHEET
    elif product:
        branch, sheet = "name", WASTE_C5_SHEET
    else:
        branch, sheet = "average", WASTE_C12_SHEET

    no_pct = pct_lf is None and pct_inc is None and pct_rec is None
    if no_pct:
        weighted_ef = (WASTE_AVG_EF["매립"] + WASTE_AVG_EF["소각"] + WASTE_AVG_EF["재활용"]) / 3
        factor = C12Factor("average", None, WASTE_C12_SHEET, ())
    else:
        weighted_ef = 0.0
        parts: list[WasteFactor] = []
        for pct, found in ((pct_lf, f_lf), (pct_inc, f_inc), (pct_rec, f_rec)):
            if pct is not None and found.value is not None:
                weighted_ef += found.value * pct
                parts.append(found)
        if parts and all(part.via == "treatment_average" for part in parts):
            branch, sheet = "average", WASTE_C12_SHEET  # 코드·제품명이 계수 시트에 안 걸림(흠 ② 의 「nan」 포함)
        found_code = code if branch == "code" and any(p.via != "treatment_average" for p in parts) else None
        factor = C12Factor(branch, found_code, sheet, tuple(parts))
    treatments = _c12_treatments(factor.branch, no_pct, ((pct_lf, f_lf), (pct_inc, f_inc), (pct_rec, f_rec)))

    emission = total_weight_kg * weighted_ef / 1000.0

    # 「소각」 배출분만 생물기원·화석기원으로 나눈다(처리비중이 하나도 없으면 나누지 않음)
    bio_group = None
    incineration_part = None
    if not no_pct:
        bio_code = sub or mid
        if bio_code:
            bio_group = biogenic_group_from_code(bio_code)
        elif product and not big:
            bio_group = biogenic_group_from_name(product)
        if bio_group and pct_inc is not None and f_inc.value is not None:
            incineration_part = total_weight_kg * pct_inc * f_inc.value / 1000.0

    split = biogenic_fossil_split(emission, incineration_part, bio_group)
    columns: dict[str, object] = {"배출계수": weighted_ef, "배출량(tCO2e)": emission}
    columns.update(split.colab_columns())
    columns["배출량(tCO2e)"] = columns["화석기원 CO2e(tCO2e)"]  # 생물기원은 Scope 3 집계에서 뺀다
    return C12Calc(columns, total_weight, unit, total_weight_kg, weighted_ef, factor, split, treatments)


# ── C15 표준화(`:5610-5634`) ──


def standardize_c15_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c15_sheet`(`:5610-5634`): 산정 배출량 = (Scope1 + Scope2) × 지분율 / 100."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if "피투자기업명 (필수)" in df.columns:
        rename["피투자기업명 (필수)"] = "피투자기업명"
    if "지분율(%) (선택)" in df.columns:
        rename["지분율(%) (선택)"] = "지분율(%)"
    if "피투자기업 Scope1배출량" in df.columns:
        rename["피투자기업 Scope1배출량"] = "Scope1배출량"
    if "피투자기업 Scope2배출량" in df.columns:
        rename["피투자기업 Scope2배출량"] = "Scope2배출량"
    if rename:
        df = df.rename(columns=rename)
    if "Scope1배출량" in df.columns and "Scope2배출량" in df.columns and "지분율(%)" in df.columns:
        df["배출량"] = [
            (or_zero(to_float(r.get("Scope1배출량"))) + or_zero(to_float(r.get("Scope2배출량"))))
            * (or_zero(to_float(r.get("지분율(%)"))) / 100)
            for _, r in df.iterrows()
        ]
    return df


def or_zero(value: float | None) -> float:
    """코랩 `to_float(x) or 0` — NaN 은 참이라 그대로 지나간다(흠 ③)."""
    return value if value else 0.0


# ── 줄 메타와 시트 갈래(본 고리 `:6170-6192`) ──
# 산정 출처(코랩에는 없다 — 값은 바꾸지 않는다): C12 factor 단계 하나, via = 실제 갈래(code · name · average —
# 가중에 든 계수가 모두 처리방법 평균이면 average). 처리방법 평균이 하나라도 가중에 들었으면 estimate, 그 밖은 rule.
# C15 는 계수를 쓰지 않아 단계 0(줄 origin None, missing `factor`).

_STRENGTH: Final[dict[ColabOrigin, int]] = {"rule": 0, "ai": 1, "estimate": 2}


@dataclass(frozen=True)
class ProductInvestment:
    """C15 의 입력 칸(지분율(%)·Scope1배출량·Scope2배출량)."""

    share: float | None
    scope1: float | None
    scope2: float | None


@dataclass(frozen=True)
class ProductUse:
    """C11 의 「사용기간(년)」·「총사용량」(제품수량 × 제품당 사용량(계수 단위) × 사용기간)."""

    years: float | None
    total_usage: float | None


@dataclass(frozen=True)
class ProductMeta:
    """C11·C12·C14·C15 줄의 메타(코랩 결과 행에는 없는 것): 입력 줄·활동량·쓴 계수·산정 출처·생물기원·투자 칸.

    `EnergyMeta`(energy.py)와 같은 자리를 갖고 C12 의 `biogenic`·C15 의 `investment`·C11·C14 의 `match`(처리 때
    EF매핑방식·EF매핑점수)·C11 의 `product` 를 더한다."""

    excel_row: int | None
    kind: ColabEnergyKind
    month: int | None
    activity: ActivityAmount
    factor: ActivityFactor | None
    steps: tuple[ActivityOriginStep, ...]
    biogenic: BiogenicSplit | None = None
    investment: ProductInvestment | None = None
    match: EnergyMatch | None = None
    product: ProductUse | None = None
    treatments: C12Treatments | None = None  # S3Q1 — C12 만(처리방법별 보기 칸)

    @property
    def origin(self) -> ColabOrigin | None:
        if not any(s.step == "factor" for s in self.steps):
            return None
        return max((s.origin for s in self.steps if s.step in ("unit", "factor")), key=_STRENGTH.__getitem__)


@dataclass(frozen=True)
class ProductRun:
    """실행 하나의 계수 시트: `폐기물_C12`(코드 길)와 `폐기물_C5`(제품명 길 — C5 와 같은 읽기), C11·C14 의 에너지 몫
    (계수 시트 `에너지`·LLM·AI 배수 캐시 — C3·C8·C13 과 같은 `EnergyRun`)."""

    waste_c12: FactorSheetRead
    waste_c5: FactorSheetRead
    energy: EnergyRun


@dataclass(frozen=True)
class ProductPending:
    """후처리를 기다리는 C11·C14 시트: 처리 때 줄(코랩 열 이름 dict — 후처리는 고친 사본을 낸다)과 줄마다 EF매핑
    (`:7613`·`:7623` 의 값 — 후처리가 덮지 않는다)."""

    key: str
    category: str
    rows: tuple[dict[str, object], ...]
    matches: tuple[EnergyMatch | None, ...]


@dataclass(frozen=True)
class ProductSheet:
    """C11·C14 면 `metas` 는 처리 때 값의 메타다(후처리가 실패하면 그대로 남는다 — 코랩 `:8903-8905`)."""

    frame: pd.DataFrame
    metas: tuple[ProductMeta, ...]
    pending: ProductPending | None = None


@dataclass(frozen=True)
class EmptyProductSheet:
    """`read_template_sheet` 가 빈 frame 을 냈다(코랩 `[empty]`)."""


def _excel_row(row: "pd.Series[Any]") -> int | None:
    value = row.get(TEMPLATE_ROW)
    return int(value) if isinstance(value, numbers.Integral) else None


def _finite(value: object) -> float | None:
    if isinstance(value, bool) or not isinstance(value, numbers.Real):
        return None
    f = float(value)
    return f if math.isfinite(f) else None


def c12_factor_step(factor: C12Factor) -> ActivityOriginStep:
    averaged = factor.branch == "average" or any(part.via == "treatment_average" for part in factor.parts)
    return ActivityOriginStep("factor", "estimate" if averaged else "rule", factor.branch)


def _c12_row(run: ProductRun, row: "pd.Series[Any]", out: dict[str, object]) -> ProductMeta:
    """코랩 C12 본 고리 한 줄(`:6177-6188`)."""
    calc = calc_c12_ef_and_emission(run.waste_c12.frame, run.waste_c5.frame, row)
    out["배출계수"] = calc.columns.get("배출계수")
    out["배출량(tCO2e)"] = calc.columns.get("배출량(tCO2e)")
    for key in ("화석기원 CO2e(tCO2e)", "생물기원 CO2e(tCO2e)", "화석탄소비율(FCF)", "바이오매스 구분"):
        if key in calc.columns:
            out[key] = calc.columns[key]
    amount = ActivityAmount(_finite(calc.total_weight), calc.unit, _finite(calc.total_weight_kg), "kg", None)
    if calc.factor is None:
        return ProductMeta(_excel_row(row), "product_eol", None, amount, None, ())
    factor = ActivityFactor(calc.factor.sheet, None, _finite(calc.weighted_ef), C12_FACTOR_UNIT, None, calc.factor.code)
    return ProductMeta(
        _excel_row(row),
        "product_eol",
        None,
        amount,
        factor,
        (c12_factor_step(calc.factor),),
        calc.split,
        treatments=calc.treatments,
    )


def _c15_row(row: "pd.Series[Any]") -> ProductMeta:
    """C15 한 줄(본 고리 `pass` — 표준화가 지은 「배출량」 그대로). 활동량은 코랩 셈의 Scope1 + Scope2."""
    scope1, scope2 = to_float(row.get("Scope1배출량")), to_float(row.get("Scope2배출량"))
    amount = ActivityAmount(_finite(or_zero(scope1) + or_zero(scope2)), INVESTMENT_UNIT, None, INVESTMENT_UNIT, None)
    investment = ProductInvestment(_finite(to_float(row.get("지분율(%)"))), _finite(scope1), _finite(scope2))
    return ProductMeta(_excel_row(row), "investment", None, amount, None, (), None, investment)


def standardize_product_sheet(df: pd.DataFrame, key: str) -> pd.DataFrame:
    """열쇠 → 이기는 표준화(C12 `:7000`, C15 `:5610`). C11·C14 는 셈이 들어 `process_product_sheet` 가 따로 한다."""
    return standardize_c12_sheet(df) if key == "c12" else standardize_c15_sheet(df)


def process_product_sheet(run: ProductRun, sheet: Sheet, key: str, category: str) -> ProductSheet | EmptyProductSheet:
    """코랩 `process_new_template` 의 시트 하나(Category12·15 갈래)."""
    df = read_template_rows(sheet)
    if df.empty:
        return EmptyProductSheet()
    if key in ("c11", "c14"):
        return _process_energy_product(run, df, key, category, sheet.name)
    df = standardize_product_sheet(df, key)
    df["자동카테고리"] = category
    df["출처시트"] = sheet.name
    if PRODUCT_SHEET_KINDS[key] == "investment":  # 본 고리 `pass`(`:6192`)
        return ProductSheet(df, tuple(_c15_row(row) for _, row in df.iterrows()))
    rows_out: list[dict[str, object]] = []
    metas: list[ProductMeta] = []
    for _, row in df.iterrows():
        out = {str(k): v for k, v in row.to_dict().items()}
        metas.append(_c12_row(run, row, out))
        rows_out.append(out)
    return ProductSheet(pd.DataFrame(rows_out), tuple(metas))


# ── C11·C14(S3C-c1b-2): 처리 때(`:6961`·`:5590` → `:7613`·`:7623`)와 결과 후처리(`:8720`·`:8862`) ──
# 산정 출처(코랩에는 없다 — 값은 바꾸지 않는다): C8·C13 과 같은 규칙(energy.py) — unit(환산) rule·lhv → rule, ai → ai,
# ai_failed → estimate, factor 사슬 `fallback_patch` → estimate, 그 밖의 고리 → rule.

_C11_RENAMES: Final = (
    ("그룹(선택)", "그룹"),
    ("설명/적요(선택)", "설명/적요"),
    ("수명(개월) 혹은 평균 사용기간(개월)", "수명(개월)"),
)
_C14_RENAMES: Final = (
    ("연료 종류", "에너지원"),
    ("연료 사용량", "사용량"),
    ("연료 단위", "단위"),
    ("가맹점 수", "가맹점수"),
)
# `annotate_energy_mapping_columns` 의 이름 열(`:7620` · `:7636`)
_ANNOTATE_ENERGY_COLS: Final[dict[str, tuple[str, ...]]] = {
    "c11": ("에너지명", "에너지원"),
    "c14": ("에너지원", "연료 종류"),
}


def rename_c11_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """`:6961`·`:8720` 이 같이 하는 열 정리(rename 셋)."""
    df = normalize_template_columns(df)
    rename = {old: new for old, new in _C11_RENAMES if old in df.columns}
    return df.rename(columns=rename) if rename else df


def standardize_c14_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c14_sheet`(`:5590-5607` — `:7623` 이 붙잡은 판, 「전력사용량」·월 접기 `:8757` 은 안 쓰임)."""
    df = normalize_template_columns(df)
    rename = {old: new for old, new in _C14_RENAMES if old in df.columns and new not in df.columns}
    return df.rename(columns=rename) if rename else df


@dataclass(frozen=True)
class C11Calc:
    """C11 줄 하나의 셈(`:6961` 판과 `:8720` 판이 같은 꼴): 제품당 연간 사용량(입력)·사용기간·총사용량·사슬·환산."""

    annual_use: float | None
    unit_raw: str
    years: float
    total_usage: float | None
    lookup: EnergyLookup
    ef: float | None
    conversion: EnergyConversion
    emission: float | None

    def columns(self, *, mapped_name: bool = False) -> dict[str, object]:
        """코랩이 줄에 쓰는 칸(차례 그대로 — 단위환산비고는 비고가 있을 때만). EF매핑명은 `:8720` 판만 쓴다."""
        out: dict[str, object] = {
            "사용기간(년)": self.years,
            "총사용량": self.total_usage,
            "배출계수(kgCO2eq/단위)": self.ef,
            "EF단위": self.lookup.unit,
        }
        if mapped_name:
            out["EF매핑명"] = self.lookup.name
        if self.conversion.note:
            out["단위환산비고"] = self.conversion.note
        out["배출량(tCO2e)"] = self.emission
        return out


def _c11_total(qty: float | None, conv: EnergyConversion, years: float, ef: float | None) -> tuple[float | None, ...]:
    total = qty * conv.value * years if (qty is not None and conv.value is not None) else None
    emission = (total * ef / 1000.0) if (total is not None and ef is not None) else None
    return total, emission


def _c11_qty(row: "pd.Series[Any]") -> object:
    """코랩 `row2.get("제품수량") or row2.get("판매수량") or row2.get("판매량")`(NaN 은 참)."""
    return _colab_or(_colab_or(row.get("제품수량"), row.get("판매수량")), row.get("판매량"))


def calc_c11_6961(energy: EnergyRun, row: "pd.Series[Any]") -> C11Calc:
    """코랩 셀 24 `standardize_c11_sheet`(`:6961-7000`)의 한 줄 — 처리 때. 환산(`:6844`)의 AI 맥락은 날 이름."""
    qty = patch_to_float(_c11_qty(row))
    annual_use = patch_to_float(row.get("제품당 연간 에너지 사용량"))
    months = patch_to_float(row.get("수명(개월)"))
    years = (months / 12.0) if months is not None else 1.0
    energy_name = patch_safe_text(_colab_or(row.get("에너지명"), row.get("에너지원")))
    unit_raw = patch_safe_text(row.get("단위"))
    found = lookup_energy_ef(energy.energy.frame, energy_name, unit_hint=unit_raw)
    ef = patch_to_float(found.ef)
    conv = patch_convert_energy_to_ef_unit(energy.llm, energy.units, annual_use, unit_raw, energy_name, found.unit)
    total, emission = _c11_total(qty, conv, years, ef)
    return C11Calc(annual_use, unit_raw, years, total, found, ef, conv, emission)


def calc_c11_8720(energy: EnergyRun, row: "pd.Series[Any]") -> C11Calc:
    """코랩 셀 27 `standardize_c11_sheet`(`:8720-8754`)의 한 줄 — 결과 후처리 `:8898` 가 다시 부르는 최종 값.
    사슬에 단위 힌트, 환산은 `_fix_convert_to_ef_unit`(계수 단위와 다르면 None — 산정 보류)이고 그 맥락은
    `std_name or energy_name`(`:8742`)."""
    qty = fix_num(_c11_qty(row))
    annual_use = fix_num(row.get("제품당 연간 에너지 사용량"))
    months = fix_num(row.get("수명(개월)"))
    years = (months / 12.0) if months is not None else 1.0
    energy_name = fix_text(_colab_or(row.get("에너지명"), row.get("에너지원")))
    unit_raw = fix_text(row.get("단위"))
    found = lookup_energy_ef(energy.energy.frame, energy_name, unit_hint=unit_raw)
    ef = fix_num(found.ef)
    # NaN 이면 "nan" 글자 — 코랩 NaN 객체와 소비자에서 같다(S3C-r1 2-0 e, energy.fix_calc_energy_usage_row 주석)
    context_name = str(_colab_or(found.name, energy_name))  # 코랩 `std_name or energy_name`(MARC-ISSUE-395 2번 꼴)
    conv = fix_convert_to_ef_unit(energy.llm, energy.units, annual_use, unit_raw, context_name, found.unit)
    total, emission = _c11_total(qty, conv, years, ef)
    return C11Calc(annual_use, unit_raw, years, total, found, ef, conv, emission)


def annotate_energy_match(energy: EnergyRun, row: "pd.Series[Any]", energy_cols: tuple[str, ...]) -> EnergyMatch | None:
    """코랩 `annotate_energy_mapping_columns`(`:7583-7608`)의 한 줄: 이름 열에서 비지 않은 첫 글, 단위는 「단위」 칸
    날값을 힌트로 사슬을 불러 그때의 매칭(`_LAST_EF_MATCH_INFO["energy"]`). 이름이 없으면 None(칸은 빈 채)."""
    name = ""
    for c in energy_cols:
        if c in row.index and ef_safe_text(row.get(c)):
            name = ef_safe_text(row.get(c))
            break
    if not name:
        return None
    unit = row.get("단위") if "단위" in row.index else None
    return lookup_energy_ef(energy.energy.frame, name, unit_hint=unit).match


def _match_columns(match: EnergyMatch | None) -> dict[str, object]:
    if match is None:
        return {"EF매핑명": None, "EF매핑방식": None, "EF매핑점수": None}
    return {"EF매핑명": match.raw_name, "EF매핑방식": match.match_type, "EF매핑점수": match.score}


def _text_or_none(value: object) -> str | None:
    return fix_text(value) or None


def _energy_steps(lookup: EnergyLookup, conv: EnergyConversion) -> tuple[ActivityOriginStep, ...]:
    steps = [s for s in (unit_origin_step(conv.via), energy_factor_step(lookup.via)) if s is not None]
    return tuple(steps)


def _energy_factor(energy: EnergyRun, lookup: EnergyLookup, ef: float | None) -> ActivityFactor:
    column = energy_db_cols(energy.energy.frame).ef if lookup.via not in ("fallback_patch", "none") else None
    return ActivityFactor(ENERGY_SHEET, _text_or_none(lookup.name), _finite(ef), fix_text(lookup.unit), column, None)


def _c11_meta(energy: EnergyRun, excel_row: int | None, calc: C11Calc, match: EnergyMatch | None) -> ProductMeta:
    """activity = 제품당 연간 에너지 사용량·단위 날값 → 환산값·단위(산정 보류면 None), note = 단위환산비고 ·
    product = 사용기간·총사용량(감독 보정 4)."""
    conv = calc.conversion
    amount = ActivityAmount(_finite(calc.annual_use), calc.unit_raw, _finite(conv.value), conv.unit, conv.note or None)
    return ProductMeta(
        excel_row, "product_use", None, amount, _energy_factor(energy, calc.lookup, calc.ef),
        _energy_steps(calc.lookup, conv), None, None, match, ProductUse(_finite(calc.years), _finite(calc.total_usage)),
    )  # fmt: skip


def _c14_raw_meta(row: "pd.Series[Any]", match: EnergyMatch | None) -> ProductMeta:
    """C14 처리 때(셈 없음 — 후처리가 실패하면 남는 값): 사용량·단위 날값, 계수 없음."""
    unit = fix_text(row.get("단위"))
    amount = ActivityAmount(_finite(fix_num(row.get("사용량"))), unit, None, unit, None)
    return ProductMeta(_excel_row(row), "franchise", None, amount, None, (), None, None, match)


def _process_energy_product(
    run: ProductRun, df: pd.DataFrame, key: str, category: str, sheet_name: str
) -> ProductSheet:
    """C11·C14 처리 때: 표준화(C11 은 셈까지 `:6961`) → 매핑 칸 덧붙임(`:7613`·`:7623`) → 자동카테고리·출처시트."""
    df = rename_c11_sheet(df) if key == "c11" else standardize_c14_sheet(df)
    rows_out: list[dict[str, object]] = []
    metas: list[ProductMeta] = []
    matches: list[EnergyMatch | None] = []
    calcs = [calc_c11_6961(run.energy, row) if key == "c11" else None for _, row in df.iterrows()]
    for (_, row), calc in zip(df.iterrows(), calcs, strict=True):
        out = {str(k): v for k, v in row.to_dict().items()}
        if calc is not None:
            out.update(calc.columns())
        rows_out.append(out)
    # `:7583` 는 표준화가 다 끝난 frame 에 칸 셋을 먼저 None 으로 짓고 줄마다 채운다
    for out, (_, row) in zip(rows_out, df.iterrows(), strict=True):
        match = annotate_energy_match(run.energy, row, _ANNOTATE_ENERGY_COLS[key])
        out.update(_match_columns(match))
        matches.append(match)
    for out, (_, row), calc, match in zip(rows_out, df.iterrows(), calcs, matches, strict=True):
        out["자동카테고리"] = category
        out["출처시트"] = sheet_name
        metas.append(_c14_raw_meta(row, match) if calc is None else _c11_meta(run.energy, _excel_row(row), calc, match))
    frame = pd.DataFrame(rows_out)
    return ProductSheet(frame, tuple(metas), ProductPending(key, category, tuple(rows_out), tuple(matches)))


def result_view(rows: list[dict[str, object]]) -> pd.DataFrame:
    """코랩이 후처리(`:8878`) 때 다시 읽는 결과 파일의 꼴: `COLS_TO_DROP`·우리 줄 번호 열·전부 빈 열을 지우고 None →
    NaN(activity.py `_round_trip_view` 와 같은 규칙 — 같은 Category 의 시트를 합친 줄 위에서)."""
    frame = pd.DataFrame(rows)
    view = frame.drop(columns=[c for c in frame.columns if c in COLS_TO_DROP or c == TEMPLATE_ROW])
    view = view.loc[:, view.notna().any()]
    return view.astype(object).where(view.notna(), math.nan)


def _row_number(value: object) -> int | None:
    return int(value) if isinstance(value, numbers.Integral) else None


def _fix_c11_row(
    energy: EnergyRun, row: "pd.Series[Any]", out: dict[str, object], match: EnergyMatch | None
) -> ProductMeta:
    """결과 후처리의 C11_ 한 줄(`:8898` → `:8720`). `out` 은 처리 때 줄의 사본 — 코랩이 덮는 칸만 덮는다."""
    calc = calc_c11_8720(energy, row)
    out.update(calc.columns(mapped_name=True))
    return _c11_meta(energy, _row_number(out.get(TEMPLATE_ROW)), calc, match)


def _fix_c14_row(
    energy: EnergyRun, row: "pd.Series[Any]", out: dict[str, object], match: EnergyMatch | None
) -> ProductMeta:
    """결과 후처리의 C14_ 한 줄(`_fix_result_energy_sheet` `:8862-8875`, usage_col 「사용량」)."""
    calc = fix_calc_energy_usage_row(energy.llm, energy.units, energy.energy.frame, row, usage_col="사용량")
    conv, found = calc.conversion, calc.lookup
    if conv.value is not None:
        out["사용량"] = conv.value
    out["배출계수(kgCO2eq/단위)"] = calc.ef
    out["EF단위"] = found.unit
    out["EF매핑명"] = found.name
    if conv.note:
        out["단위환산비고"] = conv.note
    out["배출량(tCO2e)"] = calc.emission_t
    out["계산식"] = (
        f"배출량(tCO2e) = 사용량 × EF / 1000 = {conv.value:g} × {calc.ef:g} / 1000 = {calc.emission_t:g}"
        if calc.emission_t is not None and conv.value is not None and calc.ef is not None
        else ""
    )
    amount = ActivityAmount(_finite(calc.usage_raw), calc.unit_raw, _finite(conv.value), conv.unit, conv.note or None)
    return ProductMeta(
        _row_number(out.get(TEMPLATE_ROW)), "franchise", None, amount, _energy_factor(energy, found, calc.ef),
        _energy_steps(found, conv), None, None, match,
    )  # fmt: skip


def postprocess_product_category(
    run: ProductRun, category: str, pending: list[ProductPending]
) -> tuple[ProductSheet, ...]:
    """코랩 후처리(`:8878-8905`)의 결과 시트 하나(C11_ 또는 C14_): 그 Category 의 시트들을 템플릿 차례로 합친 줄
    (`result_view`)을 줄마다 다시 센다. 시트마다 나눠 돌려준다. 예외는 밖으로(pipeline 이 그 결과 시트를 처리 때
    값으로 둔다)."""
    rows = [dict(r) for p in pending for r in p.rows]
    matches = [m for p in pending for m in p.matches]
    view = result_view(rows)
    c11 = category == "Category11"
    if c11:
        view = rename_c11_sheet(view)
    fix_row = _fix_c11_row if c11 else _fix_c14_row
    metas = [fix_row(run.energy, row, rows[i], matches[i]) for i, (_, row) in enumerate(view.iterrows())]
    sheets: list[ProductSheet] = []
    start = 0
    for p in pending:
        end = start + len(p.rows)
        sheets.append(ProductSheet(pd.DataFrame(rows[start:end]), tuple(metas[start:end])))
        start = end
    return tuple(sheets)
