"""운송·출장 지출 계수 찾기(C4-2·C9-2·C6-2) — 코랩 셀 3·25·26·27 의 마지막 판(늦은 묶임 포함).

운송(C4-2·C9-2): `lookup_transport_spend_ef`(`:7752` 판)가 붙잡은 옛 판 `:865`(`_LOOKUP_TRANSPORT_SPEND_EF_BEFORE_
ALIAS_PATCH` `:7255`)를 **확장 글**(원문 + 운송 표준코드 힌트 `:7742`)로 한 번, **원문**으로 한 번 부른다. 옛 판 안의
`_get_spend_ef_col` 은 부를 때의 마지막 판(`:7979` — 보고연도 원화 열, 없으면 USD 열)으로 풀린다.
옛 판 차례: 한국어 키워드 → 한국어명 부분 일치 → NAICS Title 부분 일치 → 「General Freight Trucking, Local」.
q="" 버릇: 2단계(`q in 한국어명`)가 계수 있는 첫 줄에 걸린다(코랩 그대로).

출장(C6-2): `lookup_travel_spend_ef`(`:8628`)는 `_fix_lookup_travel_spend_candidate`(`:8576`) — 수동 표 → 점수
(키워드 `100+len` · 「출장 항목」 30 · Title 20, 처음 가장 큰 줄). 안 걸리면 붙잡은 옛 판을 찾지만
`_LOOKUP_TRAVEL_SPEND_EF_BEFORE_FULL_FIX`·`_BEFORE_ALIAS_PATCH` 는 지어지지 않는다(읽는 곳 `:8632` 뿐) →
`(None, None, None)`. 「출장 항목」 칸이 빈 줄은 `"" in qn` 이 참이라 늘 30점을 받는다(코랩 그대로).

계수 시트(코랩 전역 `transport_spend_db`·`travel_spend_db`)와 보고연도(`FX_REFERENCE_YEAR`)는 인자다. 찾은 갈래(via)를
함께 내어 산정 출처를 남긴다(값은 바꾸지 않는다).
"""

import contextlib
import math
import re
import unicodedata
from dataclasses import dataclass
from typing import Any, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.constants import (
    BOK_USD_KRW_MONTHLY_AVG_2025,
    TRANSPORT_CODE_KEYWORDS,
    TRANSPORT_CODE_TO_SPEND_HINT,
    TRAVEL_SPEND_MANUAL,
)
from esgapi.inventory.engines.scope3.colab_157.factor_book import (
    find_precomputed_krw_ef_col,
    find_usd_ef_col,
    is_precomputed_krw_ef_col,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.engines.scope3.colab_157.purchase import (
    FX_REFERENCE_YEAR,
    coerce_month_value,
    fix_norm,
    fix_num,
    fix_split_keywords,
    fix_text,
    to_float,
)
from esgapi.inventory.engines.scope3.colab_157.template import normalize_template_columns

FxVia = Literal["fx_month", "fx_annual", "fx_default_1400"]


@dataclass(frozen=True)
class SpendHit:
    """찾은 계수 한 줄: 코랩의 (NAICS_title, ef, naics_code)와 갈래. title 은 칸 값 그대로(글이 아닐 수 있다)."""

    title: object
    ef: float | None
    code: str | None
    via: str


# ── 공통 정규화(코랩 :7265 · :7276) ──


def ef_safe_text(v: object) -> str:
    """코랩 `_ef_safe_text`(`:7265`) — `fix_text` 와 글자까지 같다."""
    return fix_text(v)


def ef_norm_text(v: object) -> str:
    """코랩 `_ef_norm_text`(`:7276-7287`)."""
    s = ef_safe_text(v)
    if not s:
        return ""
    s = unicodedata.normalize("NFKC", s).lower()
    s = s.replace("㎥", "m3").replace("m³", "m3").replace("nm³", "nm3")
    s = s.replace("co₂", "co2").replace("co₂e", "co2e")
    s = re.sub(r"[\(\)\[\]\{\}]", "", s)
    return re.sub(r"[\s_\-\/,·・|]+", "", s)


def template_transport_code(text: object) -> str | None:
    """코랩 `_template_transport_code`(`:7644-7666`)."""
    s = ef_norm_text(text)
    if not s:
        return None
    for code, keywords in TRANSPORT_CODE_KEYWORDS:
        if any(k in s for k in keywords):
            return code
    return None


# ── 계수 열(코랩 :7979 · :7987 — 늦은 묶임의 마지막 판) ──


def get_spend_ef_col(db: pd.DataFrame, year: int) -> str | None:
    """코랩 `_get_spend_ef_col`(`:7979`): 보고연도의 원화 계수 열, 없으면 USD 열."""
    krw_col = find_precomputed_krw_ef_col(db, year)
    if krw_col:
        return krw_col
    return find_usd_ef_col(db)


def current_spend_ef_unit(db: pd.DataFrame, year: int) -> str:
    """코랩 `_current_spend_ef_unit_from_db`(`:7987`)."""
    col = get_spend_ef_col(db, year)
    if col and is_precomputed_krw_ef_col(col):
        return "kgCO2e/KRW"
    return "kgCO2e/USD"


def _first(db: pd.DataFrame, *needles: str) -> str | None:
    return next((str(c) for c in db.columns if any(n in str(c) for n in needles)), None)


def _numeric(value: object) -> float | None:
    """`pd.to_numeric(값, errors="coerce")` 이 NaN 이 아니면 float."""
    ef = pd.to_numeric(pd.Series([value], dtype=object), errors="coerce").iloc[0]
    return None if pd.isna(ef) else float(ef)


# ── 운송 Spend(코랩 :865 옛 판 · :7752 감쌈) ──


def _hit(row: "pd.Series[Any]", title_col: str, ef: float, naics_col: str | None, via: str) -> SpendHit:
    return SpendHit(row[title_col], ef, str(row.get(naics_col, "")), via)  # 코랩 str(row.get(naics_col, ""))


def lookup_transport_spend_ef_865(db: pd.DataFrame, year: int, mode_or_item: str) -> SpendHit | None:
    """코랩 `lookup_transport_spend_ef`(`:865-913`, 옛 판). 못 찾으면 None(코랩의 `(None, None, None)`)."""
    if db.empty:
        return None
    ef_col = get_spend_ef_col(db, year)
    kw_col = _first(db, "키워드")
    ko_col = next((str(c) for c in db.columns if "한국어 품목명" in str(c) or "한국어명" in str(c)), None)
    title_col = next((str(c) for c in db.columns if "NAICS Title" in str(c) or "Title" in str(c)), None)
    naics_col = next((str(c) for c in db.columns if "NAICS 코드" in str(c) or "NAICS코드" in str(c)), None)
    if not ef_col or not title_col:
        return None
    q = str(mode_or_item).strip().lower()

    if kw_col:  # 1) 한국어 키워드
        for _, row in db.iterrows():
            kws = str(row.get(kw_col, "")).lower().split(",")
            if any(k.strip() and k.strip() in q for k in kws):
                ef = _numeric(row[ef_col])
                if ef is not None:
                    return _hit(row, title_col, ef, naics_col, "keyword")
    if ko_col:  # 2) 한국어명 부분 일치
        for _, row in db.iterrows():
            if q in str(row.get(ko_col, "")).lower():
                ef = _numeric(row[ef_col])
                if ef is not None:
                    return _hit(row, title_col, ef, naics_col, "korean_name")
    for _, row in db.iterrows():  # 3) NAICS Title 부분 일치
        if q in str(row.get(title_col, "")).lower():
            ef = _numeric(row[ef_col])
            if ef is not None:
                return _hit(row, title_col, ef, naics_col, "title")
    default = db[colab_str(db[title_col]).str.contains("General Freight Trucking, Local", na=False, regex=True)]
    if not default.empty:
        ef = _numeric(default.iloc[0][ef_col])
        return SpendHit(default.iloc[0][title_col], ef, None, "default_title")
    return None


def lookup_transport_spend_ef(db: pd.DataFrame, year: int, mode_or_item: object) -> SpendHit | None:
    """코랩 `lookup_transport_spend_ef`(`:7752-7774`): 확장 글로 옛 판, 계수가 없으면 원문으로 한 번 더.

    via 끝에 `:expanded`·`:raw` 를 단다. 둘 다 계수가 없으면 None(코랩은 그때 `(None, None, None)`).
    """
    q = ef_safe_text(mode_or_item)
    code = template_transport_code(q)
    expanded = q
    if code:
        expanded = f"{q} {TRANSPORT_CODE_TO_SPEND_HINT.get(code, '')}".strip()
    for text, tag in ((expanded, "expanded"), (q, "raw")):
        with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
            hit = lookup_transport_spend_ef_865(db, year, text)
            if hit is not None and hit.ef is not None:
                return SpendHit(hit.title, hit.ef, hit.code, f"{hit.via}:{tag}")
    return None


# ── 출장 Spend(코랩 :8576 · :8628) ──


def fix_lookup_travel_spend_candidate(db: pd.DataFrame | None, year: int, text: object) -> SpendHit | None:
    """코랩 `_fix_lookup_travel_spend_candidate`(`:8576-8625`). via = `manual` · `scored`."""
    if db is None or db.empty:
        return None
    try:
        ef_col = find_precomputed_krw_ef_col(db, year)
    except Exception:
        ef_col = None
    if not ef_col:
        try:
            ef_col = get_spend_ef_col(db, year)
        except Exception:
            ef_col = next((str(c) for c in db.columns if "EF" in str(c)), None)
    item_col = _first(db, "출장 항목")
    title_col = next((str(c) for c in db.columns if "NAICS Title" in str(c) or "Title" in str(c)), None)
    kw_col = _first(db, "키워드")
    code_col = next((str(c) for c in db.columns if "NAICS 코드" in str(c) or "NAICS" in str(c)), None)
    qn = fix_norm(text)
    for keys, title in TRAVEL_SPEND_MANUAL:
        if any(fix_norm(k) in qn for k in keys):
            subset = (
                db[[title in [p.strip() for p in t.split(" / ")] for t in colab_str(db[title_col])]]
                if title_col
                else pd.DataFrame()
            )
            if not subset.empty:
                r = subset.iloc[0]
                return SpendHit(fix_text(r.get(title_col)), fix_num(r.get(ef_col)), fix_text(r.get(code_col)), "manual")
    scored: list[tuple[int, pd.Series[Any]]] = []
    for _, r in db.iterrows():
        score = 0
        for kw in fix_split_keywords(r.get(kw_col)) if kw_col else []:
            kn = fix_norm(kw)
            if kn and kn in qn:
                score += 100 + len(kn)
        if item_col and fix_norm(r.get(item_col)) in qn:
            score += 30
        if title_col and fix_norm(r.get(title_col)) in qn:
            score += 20
        if score > 0:
            scored.append((score, r))
    if scored:
        _, r = max(scored, key=lambda x: x[0])
        return SpendHit(fix_text(r.get(title_col)), fix_num(r.get(ef_col)), fix_text(r.get(code_col)), "scored")
    return None


def lookup_travel_spend_ef(db: pd.DataFrame | None, year: int, item: object) -> SpendHit | None:
    """코랩 `lookup_travel_spend_ef`(`:8628-8638`): 붙잡은 옛 판이 없어 후보가 없으면 None."""
    return fix_lookup_travel_spend_candidate(db, year, item)


# ── S3C-b1 경계 ②: 시트 표준화와 줄 셈(코랩 :6509 · :6701-6746 · :8032 · :8641) ──


def _patch_to_float(x: object) -> float | None:
    """코랩 `_patch_to_float`(`:6444`)."""
    if x is None or (isinstance(x, float) and math.isnan(x)):  # 코랩 `pd.isna(x)`(칸 값은 글·수·None·NaN)
        return None
    s = str(x).replace(",", "").strip()
    if s == "" or s.lower() == "nan":
        return None
    try:
        return float(s)
    except Exception:
        return None


def collapse_monthly_to_value(df: pd.DataFrame, value_col: str, annual_cols: list[str]) -> pd.DataFrame:
    """코랩 `_patch_collapse_monthly_to_value`(`:6509-6536`, drop_month_cols=True)."""
    df = df.copy()
    month_cols = [c for c in df.columns if str(c).strip() in {f"{i}월" for i in range(1, 13)}]
    if value_col not in df.columns:
        df[value_col] = None

    def _row_value(r: "pd.Series[Any]") -> float | None:
        vals = [v for v in (_patch_to_float(r.get(c)) for c in month_cols) if v is not None]
        monthly_sum = sum(vals) if vals else None
        if monthly_sum is not None and monthly_sum != 0:
            return monthly_sum
        cur = _patch_to_float(r.get(value_col))
        if cur is not None:
            return cur
        for c in annual_cols:
            v = _patch_to_float(r.get(c))
            if v is not None:
                return v
        return None

    df[value_col] = df.apply(_row_value, axis=1)
    if month_cols:
        df = df.drop(columns=month_cols, errors="ignore")
    for c in annual_cols:
        if c in df.columns and c != value_col:
            df = df.drop(columns=[c], errors="ignore")
    return df


def standardize_c4_spend_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c4_spend_sheet`(`:6701-6719`): 시트 전체를 Spend 로, 월별 운송금액은 연간 합으로."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if "자재명/품목명" in df.columns and "자재명" not in df.columns:
        rename["자재명/품목명"] = "자재명"
    if "제품명/품목명" in df.columns and "제품명" not in df.columns:
        rename["제품명/품목명"] = "제품명"
    if "운송수단(선택)" in df.columns and "운송수단" not in df.columns:
        rename["운송수단(선택)"] = "운송수단"
    if "거래처명(선택)" in df.columns:
        rename["거래처명(선택)"] = "거래처명"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    df = collapse_monthly_to_value(df, "운송금액", annual_cols=["연간운송금액(원)"])
    df["운송구분"] = "입고"
    df["계산방식"] = "Spend"
    return df


def standardize_c9_spend_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c9_spend_sheet`(`:6722`)."""
    df = standardize_c4_spend_sheet(df)
    df["운송구분"] = "출고"
    df["계산방식"] = "Spend"
    return df


def standardize_c6_spend_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c6_spend_sheet`(`:6728-6746`). 「출장항목」 → 「이동수단」, 「출장수단」 은 그 복사."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if "출장주체" in df.columns and "사업장" not in df.columns:
        rename["출장주체"] = "사업장"
    if "출장항목" in df.columns and "이동수단" not in df.columns:
        rename["출장항목"] = "이동수단"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)
    df = collapse_monthly_to_value(df, "출장비용", annual_cols=["연간지출금액(원)"])
    if "출장인원" not in df.columns and "인원수" in df.columns:
        df["출장인원"] = df["인원수"]
    if "출장수단" not in df.columns and "이동수단" in df.columns:
        df["출장수단"] = df["이동수단"]
    df["구분"] = "출장"
    df["계산방식"] = "Spend"
    return df


@dataclass(frozen=True)
class SpendCalc:
    """줄 하나의 Spend 셈: 코랩이 줄에 더하는 칸(dict)과 산정 출처에 쓸 것."""

    columns: dict[str, object]
    spend_krw: float | None
    hit: SpendHit | None
    ef_col: str | None
    unit: str
    fx: float | None
    fx_via: FxVia | None
    spend_usd: float | None


def usd_krw_rate(month: object, year: int) -> tuple[float, FxVia]:
    """코랩 `get_bok_usd_krw_monthly_avg`(`:3632`): 그 달 → 연평균(round 2) → 1400. 표는 2025 하나(`:3462`)."""
    mm = coerce_month_value(month)
    fx_map = {FX_REFERENCE_YEAR: BOK_USD_KRW_MONTHLY_AVG_2025}.get(int(year), {})
    if mm is not None:
        rate = fx_map.get(int(mm))
        if rate is not None:
            return float(rate), "fx_month"
    if fx_map:
        return round(sum(fx_map.values()) / len(fx_map), 2), "fx_annual"
    return 1400.0, "fx_default_1400"


def calc_transport_spend_emission(db: pd.DataFrame, year: int, row: "pd.Series[Any]") -> SpendCalc:
    """코랩 `calc_transport_spend_emission`(`:8032-8073`, 마지막 판)."""
    spend_krw = to_float(row.get("운송금액") or row.get("월운송금액") or row.get("연간운송금액(원)"))
    mode = fix_text(row.get("운송수단") or row.get("자재명") or "")
    unit = current_spend_ef_unit(db, year)
    if spend_krw is None:
        return SpendCalc({"배출량(tCO2e)": None, "Spend방식": "운송"}, None, None, None, unit, None, None, None)
    hit = lookup_transport_spend_ef(db, year, mode)
    title = hit.title if hit else None
    ef = hit.ef if hit else None
    naics = hit.code if hit else None
    ef_col = get_spend_ef_col(db, year)
    if unit == "kgCO2e/KRW":
        emission = (spend_krw * ef / 1000) if ef is not None else None  # 코랩은 spend_krw 도 본다(여기서는 늘 수)
        columns: dict[str, object] = {
            "배출량(tCO2e)": emission,
            "EF(kgCO2e/KRW)": ef,
            "배출계수단위": unit,
            "NAICS": naics,
            "NAICS_Title": title,
            "Spend방식": "운송_Spend_KRW_EF",
            "EF적용금액(KRW)": spend_krw,
        }
        return SpendCalc(columns, spend_krw, hit, ef_col, unit, None, None, None)
    month = to_float(row.get("발생월"))
    fx, fx_via = usd_krw_rate(int(month) if month else None, year)
    spend_usd = spend_krw / fx if fx else spend_krw / 1400
    emission = (spend_usd * ef / 1000) if ef is not None else None  # 코랩은 spend_usd 도 본다(늘 수)
    columns = {
        "배출량(tCO2e)": emission,
        "EF(kgCO2e/USD)": ef,
        "배출계수단위": unit,
        "NAICS": naics,
        "NAICS_Title": title,
        "Spend방식": "운송_Spend_USD_EF_fallback",
        "적용환율(KRW/USD)": fx,
        "USD환산금액": spend_usd,
    }
    return SpendCalc(columns, spend_krw, hit, ef_col, unit, fx, fx_via, spend_usd)


def travel_ef_col(db: pd.DataFrame, year: int) -> str | None:
    """`_fix_lookup_travel_spend_candidate` 가 고르는 계수 열(결과의 열 이름 칸에)."""
    if db.empty:
        return None
    return find_precomputed_krw_ef_col(db, year) or get_spend_ef_col(db, year)


def calc_travel_spend_emission(db: pd.DataFrame, year: int, row: "pd.Series[Any]") -> SpendCalc:
    """코랩 `calc_travel_spend_emission`(`:8641-8659`, 마지막 판). 원화 열이 없으면 USD 계수 × 원화 금액(코랩대로)."""
    spend_krw = fix_num(row.get("출장비용") or row.get("월출장비용") or row.get("연간출장비용(원)"))
    item = fix_text(
        row.get("출장항목") or row.get("출장수단") or row.get("이동수단") or row.get("비고") or row.get("설명/적요")
    )
    if spend_krw is None:
        return SpendCalc({"배출량(tCO2e)": None, "Spend방식": "출장"}, None, None, None, "kgCO2e/KRW", None, None, None)
    hit = lookup_travel_spend_ef(db, year, item)
    title = hit.title if hit else None
    naics = hit.code if hit else None
    ef = fix_num(hit.ef if hit else None)
    emission_t = (spend_krw * ef / 1000.0) if ef is not None else None
    formula = (
        f"배출량(tCO2e) = 출장비용(KRW) × EF(kgCO2e/KRW) / 1000 = {spend_krw:g} × {ef:g} / 1000 = {emission_t:g}"
        if emission_t is not None and ef is not None
        else ""
    )
    columns: dict[str, object] = {
        "배출량(tCO2e)": emission_t,
        "배출량": emission_t,
        "Spend방식": "출장",
        "EF_DB": title,
        "NAICS": naics,
        "배출계수": ef,
        "배출계수단위": "kgCO2e/KRW",
        "계산식": formula,
    }
    return SpendCalc(columns, spend_krw, hit, travel_ef_col(db, year), "kgCO2e/KRW", None, None, None)
