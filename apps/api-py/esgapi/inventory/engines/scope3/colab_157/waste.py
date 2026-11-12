"""폐기물(C5)의 계수 찾기와 생물기원 나눔 — 코랩 셀 8 `:353-416`·`:626-716`.

- `lookup_waste_ef`(`:653`): 처리방법을 정규화(`_TREATMENT_ALIAS` `:626` — 「기타」 포함)하고 폐기물_C5 시트에서
  정확 일치 → 부분 일치 → 키워드 → (처리방법 무시) 전체 부분 일치, 안 걸리면 처리방법 평균(`WASTE_AVG_EF` `:353`,
  처리방법이 없으면 「소각」 평균). 평균 표에 「기타」 가 없어 「기타」 가 DB 에 안 걸리면 계수는 None.
- 생물기원(`:362-416`): 음식물·폐지·폐목재의 「소각」 만 생물기원 = 소각 배출량 × (1−FCF), 화석기원 = 전체 − 생물기원.
  C5 의 배출량(tCO2e)은 화석기원으로 갈음된다(`:6140-6145`).
계수 시트(코랩 전역 `waste_c5_db`)는 인자다. 찾은 갈래(via)를 함께 낸다(값은 바꾸지 않는다).
"""

from dataclasses import dataclass
from typing import Any

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.constants import BIOGENIC_WASTE_FCF, TREATMENT_ALIAS, WASTE_AVG_EF
from esgapi.inventory.engines.scope3.colab_157.llm import LlmContext
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.engines.scope3.colab_157.purchase import coerce_month_value, fix_text, to_float
from esgapi.inventory.engines.scope3.colab_157.template import PURCHASE_WIDE_MONTH_COLS, normalize_template_columns
from esgapi.inventory.engines.scope3.colab_157.units import UnitConversion, UnitFactorCache, convert_weight_to_kg


@dataclass(frozen=True)
class WasteFactor:
    """찾은 계수(kgCO2eq/kg)와 갈래. `value` 가 None 이면 via 도 None(평균 표에도 없음)."""

    value: float | None
    via: str | None


def normalize_treatment(raw: object) -> str | None:
    """코랩 `_normalize_treatment`(`:645-651`)."""
    s = str(raw).strip().lower()
    for alias, std in TREATMENT_ALIAS.items():
        if alias in s:
            return std
    return None


def _numeric(value: object) -> float | None:
    val = pd.to_numeric(pd.Series([value], dtype=object), errors="coerce").iloc[0]
    return None if pd.isna(val) else float(val)


def lookup_waste_ef(db: pd.DataFrame, waste_name: str, treatment: str) -> WasteFactor:
    """코랩 `lookup_waste_ef`(`:653-716`)."""
    treatment_std = normalize_treatment(treatment) if treatment else None
    fallback_value = WASTE_AVG_EF.get(treatment_std or "소각")
    fallback = WasteFactor(fallback_value, "treatment_average" if fallback_value is not None else None)
    if db.empty:
        return fallback
    columns = [str(c) for c in db.columns]
    type_col = next((c for c in columns if "폐기물 종류" in c), None)
    treat_col = next((c for c in columns if "처리방법" in c), None)
    kw_col = next((c for c in columns if "키워드" in c), None)
    ef_col = next((c for c in columns if "배출계수" in c), None)
    if not type_col or not treat_col or not ef_col:
        return fallback

    treat_df = db[colab_str(db[treat_col]).str.strip() == (treatment_std or "")]
    if treat_df.empty:
        return fallback
    name_q = str(waste_name).strip().lower()

    exact = treat_df[colab_str(treat_df[type_col]).str.strip().str.lower() == name_q]  # 1) 정확 일치
    if not exact.empty:
        val = _numeric(exact.iloc[0][ef_col])
        if val is not None:
            return WasteFactor(val, "exact")
    partial = treat_df[colab_str(treat_df[type_col]).str.lower().str.contains(name_q, na=False, regex=False)]
    if not partial.empty:  # 2) 부분 일치
        val = _numeric(partial.iloc[0][ef_col])
        if val is not None:
            return WasteFactor(val, "partial")
    if kw_col:  # 3) 키워드
        for _, row in treat_df.iterrows():
            kws = str(row.get(kw_col, "")).lower().split(",")
            if any(k.strip() and k.strip() in name_q for k in kws):
                val = _numeric(row[ef_col])
                if val is not None:
                    return WasteFactor(val, "keyword")
    all_partial = db[colab_str(db[type_col]).str.lower().str.contains(name_q, na=False, regex=False)]
    if not all_partial.empty:  # 4) 처리방법 무시
        treat_match = all_partial[colab_str(all_partial[treat_col]).str.strip() == (treatment_std or "")]
        target = treat_match if not treat_match.empty else all_partial
        val = _numeric(target.iloc[0][ef_col])
        if val is not None:
            return WasteFactor(val, "any_treatment")
    return fallback


def biogenic_group_from_name(name: object) -> str | None:
    """코랩 `_biogenic_group_from_name`(`:372-383`)."""
    s = str(name if name is not None else "").strip().lower().replace(" ", "")
    if not s or s == "nan":
        return None
    if any(k in s for k in ("음식물", "식품", "food")):
        return "음식물류"
    if any(k in s for k in ("폐지", "골판지", "신문지", "종이", "paper")):
        return "폐지류"
    if any(k in s for k in ("폐목", "목재", "팔레트", "wood")):
        return "폐목재류"
    return None


@dataclass(frozen=True)
class BiogenicSplit:
    """코랩 `biogenic_fossil_split` 의 dict 넷(화석기원·생물기원 tCO2e, FCF, 바이오매스 구분)."""

    fossil: float | None
    biogenic: float | None
    fcf: float | None
    note: str | None

    def colab_columns(self) -> dict[str, object]:
        return {
            "화석기원 CO2e(tCO2e)": self.fossil,
            "생물기원 CO2e(tCO2e)": self.biogenic,
            "화석탄소비율(FCF)": self.fcf,
            "바이오매스 구분": self.note,
        }


def biogenic_fossil_split(
    total_tco2e: float | None, incineration_tco2e: float | None, group: str | None
) -> BiogenicSplit:
    """코랩 `biogenic_fossil_split`(`:395-416`): 생물기원 = 소각 × (1−FCF), 화석기원 = 전체 − 생물기원."""
    if total_tco2e is None:
        return BiogenicSplit(None, None, None, None)
    fcf = BIOGENIC_WASTE_FCF.get(group) if group else None
    if fcf is None or not incineration_tco2e:
        return BiogenicSplit(total_tco2e, 0.0, None, "해당없음")
    bio = incineration_tco2e * (1 - fcf)
    return BiogenicSplit(
        total_tco2e - bio, bio, fcf, f"{group} 소각: 생물기원 {(1 - fcf) * 100:g}% / 화석기원 {fcf * 100:g}%"
    )


# ── S3C-b1 경계 ②: C5 시트 표준화와 줄 셈(코랩 :5198 · :4858 · :6110-6147) ──


def melt_monthly_or_annual(
    df: pd.DataFrame, month_var_name: str = "발생월", value_name: str = "월간값", annual_col_hint: str | None = None
) -> pd.DataFrame:
    """코랩 `_melt_monthly_or_annual`(`:4858-4916`). 월별 줄이 먼저, 연간 줄이 뒤에 이어진다.

    v1 C5 는 「연간처리량」 이 이미 「처리량」 으로 바뀌어 `melt(value_name="처리량")` 이 ValueError 를 내고 녹이지 않은
    월별 줄이 그대로 남는다(코랩 `except Exception: results.append(df_m)`) — 월 합은 뒤의 `_sum_monthly`(`:5928`).
    """
    month_cols = [c for c in df.columns if str(c).strip() in PURCHASE_WIDE_MONTH_COLS]
    if not month_cols:
        if annual_col_hint and annual_col_hint in df.columns:
            df = df.rename(columns={annual_col_hint: value_name})
        return df
    if "입력방식" in df.columns:
        df_m = df[df["입력방식"] == "월별"].copy()
        df_a = df[df["입력방식"] != "월별"].copy()
    else:

        def _has_monthly(r: "pd.Series[Any]") -> bool:
            return any(pd.notnull(r.get(m)) and str(r.get(m)).strip() not in ("", "nan") for m in month_cols)

        mask = df.apply(_has_monthly, axis=1).astype(bool)
        df_m = df[mask].copy()
        df_a = df[~mask].copy()
    results: list[pd.DataFrame] = []
    if not df_m.empty:
        id_cols = [c for c in df_m.columns if c not in month_cols]
        try:
            long = df_m.melt(id_vars=id_cols, value_vars=month_cols, var_name=month_var_name, value_name=value_name)
            long = long.dropna(subset=[value_name]).reset_index(drop=True)
            long = long[colab_str(long[value_name]).str.strip() != ""]
            long[month_var_name] = long[month_var_name].apply(coerce_month_value)
            results.append(long)
        except Exception:  # 코랩 그대로
            results.append(df_m)
    if not df_a.empty:
        if annual_col_hint and annual_col_hint in df_a.columns and annual_col_hint != value_name:
            df_a = df_a.rename(columns={annual_col_hint: value_name})
        df_a = df_a.drop(columns=[c for c in month_cols if c in df_a.columns], errors="ignore")
        results.append(df_a)
    if results:
        return pd.concat(results, ignore_index=True)
    return df


def standardize_c5_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c5_sheet`(`:5198-5216`)."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if "상세 폐기물명(선택)" in df.columns:
        rename["상세 폐기물명(선택)"] = "상세폐기물명"
    if "연간처리량" in df.columns and "처리량" not in df.columns:
        rename["연간처리량"] = "처리량"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    return melt_monthly_or_annual(df, month_var_name="발생월", value_name="처리량", annual_col_hint="연간처리량")


@dataclass(frozen=True)
class WasteCalc:
    """C5 줄 하나의 셈: 코랩이 줄에 더하는 칸과 산정 출처에 쓸 것."""

    columns: dict[str, object]
    usage_raw: float | None
    unit_str: str
    conversion: UnitConversion | None
    factor: WasteFactor | None
    treatment_std: str | None
    split: BiogenicSplit


def calc_waste_row(db: pd.DataFrame, context: LlmContext, cache: UnitFactorCache, row: "pd.Series[Any]") -> WasteCalc:
    """코랩 `process_new_template` 의 Category5 갈래 줄 하나(`:6115-6146`)."""
    columns: dict[str, object] = {}
    waste_name = fix_text(row.get("폐기물 종류") or row.get("상세폐기물명"))
    treatment = fix_text(row.get("처리방법"))
    usage_raw = to_float(row.get("처리량") or row.get("월처리량"))
    unit_str = fix_text(row.get("단위") or "kg")  # 「단위」 열이 있고 칸이 비면 NaN 이 참 → ""(코랩 그대로)
    conversion: UnitConversion | None = None
    if usage_raw is not None:
        conversion = convert_weight_to_kg(context, cache, usage_raw, unit_str)
        usage_kg = conversion.value
        if conversion.ratio != 1.0:
            note_prefix = "AI 판단: " if conversion.via == "ai" else ""
            columns["단위환산비고"] = f"{note_prefix}{unit_str}→kg (×{conversion.ratio})"
    else:
        usage_kg = None
    factor = lookup_waste_ef(db, waste_name, treatment) if waste_name else None
    ef_val = factor.value if factor else None
    emission = (usage_kg * ef_val / 1000) if (usage_kg and ef_val) else None
    treatment_std = normalize_treatment(treatment)
    columns["배출계수(kgCO2eq/kg)"] = ef_val
    columns["처리방법_정규화"] = treatment_std
    bio_group = biogenic_group_from_name(waste_name) if treatment_std == "소각" else None
    split = biogenic_fossil_split(emission, emission, bio_group)
    columns.update(split.colab_columns())
    columns["배출량(tCO2e)"] = split.fossil
    return WasteCalc(columns, usage_raw, unit_str, conversion, factor, treatment_std, split)
