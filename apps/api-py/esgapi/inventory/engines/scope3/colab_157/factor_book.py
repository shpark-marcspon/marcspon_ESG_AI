"""배출계수 통합 DB(계수 책) 읽기 — 코랩 셀 5 `:96`, 셀 8 `:283-350`, 셀 9 `:538-583`, 셀 26 `:7816-7975`.

코랩은 Drive 의 `배출계수_통합_DB.xlsx` 를 경로로 연다. 여기는 흐름이 읽어 넘긴 `Workbook` 의 시트를
`frames.read_frame` 으로 같은 frame 으로 짓는다(처분 ⑤). **보고연도는 입력이다** — 엔진은 시계를 모른다.

C1·C2 가 쓰는 것은 구매_USEPA 하나다:
- 노트북을 열 때(셀 9) 한 번 `spend_db` 를 짓고(`initial_spend_db` — 보고연도 2025 의 원화 열, 없으면 가장 뒤 열,
  그것도 비면 USD),
- `process_new_template` 이 보고연도로 다시 짓는다(`reload_spend_db` = `_reload_spend_ef_dbs_for_report_year` `:7935`,
  마지막 판). 다시 짓기가 실패하면 코랩은 경고를 찍고 셀 9 의 것을 그대로 쓴다(`:5911-5919`) — `SpendDbChoice` 가 그
  갈래를 남긴다.
`load_ef_sheet`(`_load_ef_sheet` `:307`, `dtype=str`)는 다른 시트(에너지·운송 …)의 읽개다 — C1·C2 는 부르지
않는다(S3C-b·c).
"""

import re
from dataclasses import dataclass
from typing import Any, Final, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.frames import read_frame
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.tools.scope3_sheets.grid import Sheet, Workbook

USEPA_SHEET = "구매_USEPA"


def sheet_named(book: Workbook, name: str) -> Sheet:
    """코랩 `pd.read_excel(sheet_name=name)` 처럼 없으면 예외(ValueError — pandas 도 ValueError 를 낸다)."""
    for sheet in book.sheets:
        if sheet.name == name:
            return sheet
    raise ValueError(f"Worksheet named '{name}' not found")


def to_numeric_ignore(series: "pd.Series[Any]") -> "pd.Series[Any]":
    """코랩 `_to_numeric_ignore`(`:96`): 전부 수로 바뀌면 바꾸고, 하나라도 못 바꾸면 그대로."""
    try:
        return pd.to_numeric(series)
    except (ValueError, TypeError):
        return series


def fix_cached_krw_ef_columns(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `_fix_cached_krw_ef_columns`(`:283-304`): 비어 있는 원화 수식 열을 USD 열 ÷ 머리글 안 환율로 채운다."""
    usd_col = next((c for c in df.columns if "kgCO2" in str(c) and "USD" in str(c)), None)
    if usd_col is None:
        return df
    usd_series = pd.to_numeric(df[usd_col], errors="coerce")
    for c in list(df.columns):
        cs = str(c)
        if "kgCO2e/KRW" in cs.replace(" ", "") and "년말" in cs:
            cached = pd.to_numeric(df[c], errors="coerce")
            if int(cached.notna().sum()) == 0:
                m = re.search(r"([\d,]+\.?\d*)\s*KRW/USD", cs)
                if m:
                    rate = float(m.group(1).replace(",", ""))
                    df[c] = usd_series / rate
    return df


def load_ef_sheet(
    book: Workbook, sheet_name: str, header_row: int = 1, str_cols: list[str] | None = None
) -> pd.DataFrame:
    """코랩 `_load_ef_sheet`(`:307-325`). 실패하면 빈 frame(코랩 `except Exception: return pd.DataFrame()`)."""
    try:
        df = read_frame(sheet_named(book, sheet_name), header=header_row, as_text=True)
        df.columns = pd.Index([str(c).strip() for c in df.columns])
        for col in df.columns:
            if str_cols and col in str_cols:
                continue
            df[col] = to_numeric_ignore(df[col])
        df = fix_cached_krw_ef_columns(df)
        return df.dropna(how="all").reset_index(drop=True)
    except Exception:  # 코랩 그대로(경고를 찍고 빈 frame)
        return pd.DataFrame()


def read_integrated_db_sheet(book: Workbook, sheet_name: str, header_row: int = 2) -> pd.DataFrame:
    """코랩 `_read_integrated_db_sheet`(`:7877-7887`): dtype 없이 읽고 원화 열을 채운다."""
    df = read_frame(sheet_named(book, sheet_name), header=header_row)
    df.columns = pd.Index([str(c).strip() for c in df.columns])
    df = fix_cached_krw_ef_columns(df)
    return df.dropna(how="all").reset_index(drop=True)


def _header_norm_for_ef(col: object) -> str:
    return re.sub(r"\s+", "", str(col)).lower()


def _is_precomputed_krw_ef_col(col: object) -> bool:
    """코랩 `:7821-7832`."""
    t = _header_norm_for_ef(col)
    return "ef" in t and ("kgco2e/krw" in t or "kgco2eq/krw" in t or "kgco₂e/krw" in t or "kgco₂eq/krw" in t)


def _extract_years_from_header(col: object) -> list[int]:
    return [int(y) for y in re.findall(r"20\d{2}", str(col))]


def find_precomputed_krw_ef_col(df: pd.DataFrame, report_year: int | None = None) -> str | None:
    """코랩 `_find_precomputed_krw_ef_col`(`:7840-7863`): 보고연도 글자가 든 첫 원화 열, 없으면 가장 뒤 연도."""
    if df.empty:
        return None
    candidates = [str(c) for c in df.columns if _is_precomputed_krw_ef_col(c)]
    if not candidates:
        return None
    if report_year is not None:
        y = str(int(report_year))
        year_matches = [c for c in candidates if y in c]
        if year_matches:
            return year_matches[0]

    def _latest_year(c: str) -> int:
        ys = _extract_years_from_header(c)
        return max(ys) if ys else -1

    return sorted(candidates, key=_latest_year, reverse=True)[0]


def find_usd_ef_col(df: pd.DataFrame) -> str | None:
    """코랩 `_find_usd_ef_col`(`:7866-7874`)."""
    if df.empty:
        return None
    for c in df.columns:
        t = _header_norm_for_ef(c)
        if "ef" in t and ("kgco2e/usd" in t or "kgco2eq/usd" in t):
            return str(c)
    return next((str(c) for c in df.columns if "EF" in str(c) and "USD" in str(c) and "KRW" not in str(c)), None)


def _first_col(columns: list[str], *needles: str) -> str | None:
    return next((c for c in columns if any(n in c for n in needles)), None)


@dataclass(frozen=True)
class SpendDb:
    """코랩 전역 `spend_db` 와 `SPEND_DB_NAMES`·`SPEND_DB_NAME_SET`(보고연도 다시 짓기 뒤의 값)."""

    frame: pd.DataFrame  # 칸: name, ef(+ ef_usd, naics_code, 품목군, 상세카테고리, 한국어매핑키워드 — 있으면)
    names: tuple[str, ...]
    ef_col: str | None  # 쓴 계수 열의 머리글
    year: int  # 계수 열을 고른 보고연도


@dataclass(frozen=True)
class SpendDbReloaded:
    db: SpendDb
    kind: Literal["reloaded"] = "reloaded"


@dataclass(frozen=True)
class SpendDbKeptInitial:
    """보고연도 다시 짓기가 실패해 셀 9 의 것을 쓴다(코랩 `:5918-5919` 의 경고 자리)."""

    db: SpendDb
    reason: str
    kind: Literal["kept_initial"] = "kept_initial"


type SpendDbChoice = SpendDbReloaded | SpendDbKeptInitial


def _names_of(frame: pd.DataFrame) -> tuple[str, ...]:
    # 코랩 spend_db["name"].dropna().astype(str).str.strip().drop_duplicates().tolist()
    return tuple(str(v) for v in colab_str(frame["name"].dropna()).str.strip().drop_duplicates().tolist())


def _with_extras(out: pd.DataFrame, raw: pd.DataFrame, columns: list[str], usd_col: str | None) -> pd.DataFrame:
    code_col = next((c for c in columns if "NAICS 코드" in c or ("NAICS" in c and "코드" in c)), None)
    cat_col = _first_col(columns, "품목군")
    sub_col = _first_col(columns, "상세 카테고리", "카테고리")
    kw_col = _first_col(columns, "키워드")
    if usd_col:
        out["ef_usd"] = pd.to_numeric(raw[usd_col], errors="coerce")
    if code_col:
        out["naics_code"] = raw[code_col]
    if cat_col:
        out["품목군"] = raw[cat_col]
    if sub_col:
        out["상세카테고리"] = raw[sub_col]
    if kw_col:
        out["한국어매핑키워드"] = raw[kw_col]
    return out


def initial_spend_db(book: Workbook) -> SpendDb:
    """코랩 셀 9(`:538-583`) — 노트북을 열 때의 `spend_db`. 보고연도는 셀 5 의 전역 `report_year = 2025`."""
    raw = read_frame(sheet_named(book, USEPA_SHEET), header=2)
    raw.columns = pd.Index([str(c).strip() for c in raw.columns])
    raw = fix_cached_krw_ef_columns(raw)
    raw = raw.dropna(how="all").reset_index(drop=True)
    columns = [str(c) for c in raw.columns]
    title_col = _first_col(columns, "NAICS Title", "Title")
    usd_col = next((c for c in columns if "kgCO2" in c and "USD" in c), None)
    target_year = "2025"
    krw_candidates = [c for c in columns if "kgCO2e/KRW" in c.replace(" ", "")]
    krw_col = next((c for c in krw_candidates if f"{target_year}년말" in c.replace(" ", "")), None)
    if krw_col is None and krw_candidates:
        krw_col = sorted(krw_candidates)[-1]
    ef_col = krw_col
    krw_series = pd.to_numeric(raw[krw_col], errors="coerce") if krw_col else None
    if krw_series is None or int(krw_series.notna().sum()) == 0:
        ef_col = usd_col
        krw_series = pd.to_numeric(raw[usd_col], errors="coerce") if usd_col else None
    if title_col is None:
        raise KeyError("구매_USEPA 에 NAICS Title 열이 없다")  # 코랩은 raw[None] 에서 KeyError
    out = pd.DataFrame({"name": colab_str(raw[title_col]).str.strip(), "ef": krw_series})
    out = _with_extras(out, raw, columns, usd_col)
    out = out.dropna(subset=["name"]).drop_duplicates(subset=["name"]).reset_index(drop=True)
    return SpendDb(out, _names_of(out), ef_col, 2025)


def load_purchase_usepa_as_krw_spend_db(book: Workbook, report_year: int) -> SpendDb:
    """코랩 `_load_purchase_usepa_as_krw_spend_db`(`:7890-7932`): 보고연도의 원화 계수 열로 짓는다."""
    year = int(report_year)
    raw = read_integrated_db_sheet(book, USEPA_SHEET, header_row=2)
    columns = [str(c) for c in raw.columns]
    title_col = _first_col(columns, "NAICS Title", "Title")
    krw_col = find_precomputed_krw_ef_col(raw, year)
    usd_col = find_usd_ef_col(raw)
    if not title_col:
        raise ValueError("구매_USEPA 시트에서 NAICS Title 컬럼을 찾지 못했습니다.")
    if not krw_col:
        raise ValueError("구매_USEPA 시트에서 EF (kgCO2e/KRW) 기계산 컬럼을 찾지 못했습니다.")
    out = pd.DataFrame(
        {
            "name": colab_str(raw[title_col]).str.strip(),
            "ef": pd.to_numeric(raw[krw_col], errors="coerce"),
            "ef_unit": "kgCO2e/KRW",
            "ef_source_col": krw_col,
        }
    )
    out = _with_extras(out, raw, columns, usd_col)
    out = out.dropna(subset=["name", "ef"]).drop_duplicates(subset=["name"]).reset_index(drop=True)
    return SpendDb(out, _names_of(out), krw_col, year)


def reload_spend_db(book: Workbook, report_year: int, initial: SpendDb) -> SpendDbChoice:
    """코랩 `process_new_template` 머리(`:5911-5919`)의 다시 짓기와 그 실패 갈래."""
    try:
        return SpendDbReloaded(load_purchase_usepa_as_krw_spend_db(book, report_year))
    except Exception as error:  # 코랩 `except Exception as e: print(...)`
        return SpendDbKeptInitial(initial, f"{type(error).__name__}: {error}")


# ── S3C-b1: 지출·폐기물이 읽는 계수 시트 셋(코랩 두 단 읽기) ──
# 노트북을 열 때 `_load_ef_sheet(이름, header_row=2)`(`:338`·`:346-347`)로 한 번 읽고, 셀 25
# `refresh_integrated_ef_db_mapping_patch`(`:7202`)가 `_ef_auto_header_row`(`:7154`)로 머리글 줄을 찾아 다시 읽어
# **비지 않으면** 갈음한다. 보고연도와 무관하다(보고연도는 부를 때 원화 열을 고를 뿐 — spend.py).

WASTE_C5_SHEET: Final = "폐기물_C5"
TRANSPORT_SPEND_SHEET: Final = "운송_Spend"
TRAVEL_SPEND_SHEET: Final = "출장_Spend"
TRANSPORT_SHEET: Final = "운송"  # S3C-b2a — 거리기반 운송 계수(코랩 `transport_ef_db`)
TRAVEL_SHEET: Final = "출장_통근"  # S3C-b2b — 출장·통근 거리 계수(코랩 `travel_ef_db`)
# S3C-c1a — 에너지 계수(코랩 `energy_ef_db` — C8·C13·C11·C14)와 C3 계수(`energy_c3_ef_db` 셀 29 `:9048`, 다시 읽지 않음)
ENERGY_SHEET: Final = "에너지"
ENERGY_C3_SHEET: Final = "에너지_C3"
# 코랩 :7218·:7224·:7227 의 must_contain(시트마다), 운송은 :7210
AUTO_HEADER_WORDS: Final[dict[str, list[str]]] = {
    WASTE_C5_SHEET: ["처리방법", "배출계수"],
    TRANSPORT_SPEND_SHEET: ["운송 구분", "NAICS", "EF"],
    TRAVEL_SPEND_SHEET: ["출장 항목", "NAICS", "EF"],
    TRANSPORT_SHEET: ["표준코드", "배출계수"],
}
INITIAL_HEADER_ROW: Final = 2  # 코랩 :338·:346-347
# 시트마다 첫 읽기의 머리글 줄(0부터). 운송은 `_load_ef_sheet("운송", header_row=1)`(:330)
INITIAL_HEADER_ROWS: Final[dict[str, int]] = {
    WASTE_C5_SHEET: INITIAL_HEADER_ROW,
    TRANSPORT_SPEND_SHEET: INITIAL_HEADER_ROW,
    TRAVEL_SPEND_SHEET: INITIAL_HEADER_ROW,
    TRANSPORT_SHEET: 1,
    TRAVEL_SHEET: 1,  # `_load_ef_sheet("출장_통근", header_row=1)`(:334)
}

# `initial` 은 맵을 첫 읽기로만 짓는 시트(S3C-b2b 의 `출장_통근` — 코랩 `TRAVEL_EF_MAP` `:473`). 이 파일의
# `read_factor_sheet` 는 내지 않는다.
FactorSheetHow = Literal["reloaded", "kept_initial", "empty", "initial"]


@dataclass(frozen=True)
class FactorSheetRead:
    """계수 시트 하나의 읽기: 다시 읽음 / 첫 읽기를 그대로 씀 / 둘 다 비었음 / 첫 읽기만 씀(`initial`). `header` 는 쓴
    머리글 줄(0부터)."""

    sheet: str
    frame: pd.DataFrame
    how: FactorSheetHow
    header: int | None


def ef_auto_header_row(book: Workbook, sheet_name: str, must_contain: list[str], scan_rows: int = 10) -> int | None:
    """코랩 `_ef_auto_header_row`(`:7154-7170`): 줄마다 (값 있는 칸 수 + 낱말마다 20), 처음 가장 큰 줄. 실패 None."""
    try:
        preview = read_frame(sheet_named(book, sheet_name), header=None, nrows=scan_rows)
        best_row, best_score = 0, -1
        for i in range(len(preview)):
            vals = [str(v).strip() for v in preview.iloc[i].tolist() if pd.notna(v) and str(v).strip()]
            joined = " ".join(vals)
            score = len(vals)
            for kw in must_contain:
                if kw in joined:
                    score += 20
            if score > best_score:
                best_row, best_score = i, score
        return best_row
    except Exception:  # 코랩 `except Exception: return None`
        return None


def ef_reload_sheet_auto(
    book: Workbook, sheet_name: str, must_contain: list[str], str_cols: list[str] | None = None
) -> tuple[pd.DataFrame, int | None]:
    """코랩 `_ef_reload_sheet_auto`(`:7173-7199`): 찾은 머리글 줄로 `dtype=str` 다시 읽기. 실패면 빈 frame."""
    header_row = ef_auto_header_row(book, sheet_name, must_contain)
    if header_row is None:
        return pd.DataFrame(), None
    try:
        df = read_frame(sheet_named(book, sheet_name), header=header_row, as_text=True)
        df.columns = pd.Index([str(c).strip() for c in df.columns])
        for col in df.columns:
            if str_cols and col in str_cols:
                continue
            df[col] = to_numeric_ignore(df[col])
        df = fix_cached_krw_ef_columns(df)
        return df.dropna(how="all").reset_index(drop=True), header_row
    except Exception:  # 코랩 그대로(경고를 찍고 빈 frame)
        return pd.DataFrame(), header_row


def read_factor_sheet(book: Workbook, sheet_name: str) -> FactorSheetRead:
    """첫 읽기(`:338`, 운송은 `:330`) → 자동 머리글 다시 읽기(`:7218` 꼴 — 비지 않으면 갈음)."""
    initial_header = INITIAL_HEADER_ROWS[sheet_name]
    initial = load_ef_sheet(book, sheet_name, header_row=initial_header)
    reloaded, header = ef_reload_sheet_auto(book, sheet_name, AUTO_HEADER_WORDS[sheet_name])
    if not reloaded.empty:
        return FactorSheetRead(sheet_name, reloaded, "reloaded", header)
    if not initial.empty:
        return FactorSheetRead(sheet_name, initial, "kept_initial", initial_header)
    return FactorSheetRead(sheet_name, initial, "empty", None)


def is_precomputed_krw_ef_col(col: object) -> bool:
    """코랩 `_is_precomputed_krw_ef_col`(`:7821`) — spend.py 가 읽는 이름."""
    return _is_precomputed_krw_ef_col(col)


def read_initial_factor_sheet(book: Workbook, sheet_name: str) -> FactorSheetRead:
    """첫 읽기만(`initial`) — 코랩이 그 읽기로 맵을 한 번 짓고(`출장_통근` → `TRAVEL_EF_MAP` `:473`) 셀 25 의 다시
    읽기(`:7213`)는 맵에 닿지 않는 시트. 비었으면(시트 없음 포함) `empty`."""
    header = INITIAL_HEADER_ROWS[sheet_name]
    initial = load_ef_sheet(book, sheet_name, header_row=header)
    if initial.empty:
        return FactorSheetRead(sheet_name, initial, "empty", None)
    return FactorSheetRead(sheet_name, initial, "initial", header)


# ── S3C-c1a: 에너지 계수 시트 둘(위 표들은 그대로 두고 따로 읽는다) ──
# `에너지`: 노트북을 열 때 `_load_ef_sheet("에너지", header_row=3)`(`:326`) → 셀 25
# `refresh_integrated_ef_db_mapping_patch` 가 자동 머리글로 다시 읽어(`:7205`) 비지 않으면 갈음
# (`read_factor_sheet` 와 같은 두 단).
# `에너지_C3`: 셀 29 `_load_ef_sheet("에너지_C3", header_row=2)`(`:9048`) 한 번 — 다시 읽지 않는다(`initial`).
ENERGY_INITIAL_HEADER_ROW: Final = 3
ENERGY_AUTO_HEADER_WORDS: Final = ["활동유형", "CO2eq", "기준단위"]
ENERGY_C3_HEADER_ROW: Final = 2


def read_energy_sheet(book: Workbook) -> FactorSheetRead:
    """`에너지` 의 두 단 읽기(`:326` → `:7205`)."""
    initial = load_ef_sheet(book, ENERGY_SHEET, header_row=ENERGY_INITIAL_HEADER_ROW)
    reloaded, header = ef_reload_sheet_auto(book, ENERGY_SHEET, ENERGY_AUTO_HEADER_WORDS)
    if not reloaded.empty:
        return FactorSheetRead(ENERGY_SHEET, reloaded, "reloaded", header)
    if not initial.empty:
        return FactorSheetRead(ENERGY_SHEET, initial, "kept_initial", ENERGY_INITIAL_HEADER_ROW)
    return FactorSheetRead(ENERGY_SHEET, initial, "empty", None)


def read_energy_c3_sheet(book: Workbook) -> FactorSheetRead:
    """`에너지_C3` 의 한 번 읽기(`:9048`). 비었으면(시트 없음 포함) `empty`."""
    initial = load_ef_sheet(book, ENERGY_C3_SHEET, header_row=ENERGY_C3_HEADER_ROW)
    if initial.empty:
        return FactorSheetRead(ENERGY_C3_SHEET, initial, "empty", None)
    return FactorSheetRead(ENERGY_C3_SHEET, initial, "initial", ENERGY_C3_HEADER_ROW)


# ── S3C-c1b-1: C12 계수 시트 `폐기물_C12`(위 표들은 그대로 두고 따로 읽는다) ──
# 노트북을 열 때 `_load_ef_sheet("폐기물_C12", header_row=1, str_cols=…)`(`:342`) → 셀 25
# `refresh_integrated_ef_db_mapping_patch` 가 자동 머리글로 다시 읽어(`:7219`) 비지 않으면 갈음. 코드 칸 셋은 두 읽기
# 모두 글(`str_cols` — 수로 바꾸지 않는다).
WASTE_C12_SHEET: Final = "폐기물_C12"
WASTE_C12_INITIAL_HEADER_ROW: Final = 1
WASTE_C12_AUTO_HEADER_WORDS: Final = ["폐기물 명칭", "매립 EF"]
WASTE_C12_CODE_COLUMNS: Final = ["대분류\n코드", "중분류\n코드", "소분류\n코드"]


def read_waste_c12_sheet(book: Workbook) -> FactorSheetRead:
    """`폐기물_C12` 의 두 단 읽기(`:342` → `:7219`)."""
    codes = list(WASTE_C12_CODE_COLUMNS)
    initial = load_ef_sheet(book, WASTE_C12_SHEET, header_row=WASTE_C12_INITIAL_HEADER_ROW, str_cols=codes)
    reloaded, header = ef_reload_sheet_auto(book, WASTE_C12_SHEET, WASTE_C12_AUTO_HEADER_WORDS, str_cols=codes)
    if not reloaded.empty:
        return FactorSheetRead(WASTE_C12_SHEET, reloaded, "reloaded", header)
    if not initial.empty:
        return FactorSheetRead(WASTE_C12_SHEET, initial, "kept_initial", WASTE_C12_INITIAL_HEADER_ROW)
    return FactorSheetRead(WASTE_C12_SHEET, initial, "empty", None)
