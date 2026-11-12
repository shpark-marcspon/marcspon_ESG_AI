"""입력 템플릿 v1 의 시트 읽기와 시트 → 처리기 대응.

코랩 셀 19 `:2076-2290`, 셀 23 `:4833-4916`·`:5641-5715`, 셀 24 `:6540-6560`.

코랩은 파일 경로와 시트 이름을 받아 `pd.read_excel` 로 연다. 여기는 읽힌 시트(`Sheet`)를 받아 `frames.read_frame` 으로
같은 frame 을 짓는다(처분 ⑤). 나머지 줄은 코랩 그대로다.
- `KNOWN_TEMPLATE_HEADERS` 는 넷의 합집합이다(`:2076` + `:2293` + `:3451` + `:5681`). 코랩 함수는 부를 때 전역을 읽으니
  마지막 합집합이 쓰인다(개정 1 N1).
- `read_template_sheet` 는 패치 판(`:6542`)이 옛 판(`:2128`)을 불러 `_col*` 열을 걷는다. 두 판의 중간 `reset_index` 는
  하지 않고 시트의 줄 자리를 index 로 들고 가다 끝에서 한 번 푼다(마스크·`.loc` 은 index 로 맞추니 값은 같다) —
  `read_template_rows` 가 그 자리로 엑셀 줄 번호(`TEMPLATE_ROW` 열)를 붙인다(결과의 rowId, 코랩에는 없다).
- `SHEET_PROCESSOR_MAP`(`:5641`)은 21키 전부를 옮긴다. 처리기는 이름(`ProcessorKey`)만 — C1·C2 의 처리는 `purchase.py`,
  나머지 열아홉은 아직 지원하지 않는다(S3C-b·c). dict 차례와 앞 4글자 겹침(`_match_sheet_processor` `:5665`)은 그대로.
"""

import math
from dataclasses import dataclass
from typing import Any, Final, Literal

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.frames import read_frame
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_loc_set, colab_str
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

# ── KNOWN_TEMPLATE_HEADERS: :2076 → :2293 → :3451 → :5681 의 합집합 ──
_HEADERS_2076: Final = {
    "사업장", "법인명", "품목명", "자산명", "수량", "단위", "구매금액", "금액",
    "설명/적요", "비고", "거래처명", "운송수단", "운송거리(km)", "화물중량(kg)",
    "운송구분", "출발지", "도착지", "출장비용", "출장인원", "출장수단", "이동거리(km)",
    "교통수단", "직원수", "평균통근거리(km)", "데이터유형", "판매제품명", "폐기물종류",
    "에너지원/연료명", "투자대상명", "지분율(%)", "임차자산여부", "다운스트림여부", "프랜차이즈여부",
}  # fmt: skip
_HEADERS_2293: Final = {
    "국가", "사업장", "품목군", "자산분류",
    "상세 품목명/서비스명", "상세 자산명",
    "계정과목(선택)", "거래처명(선택)",
    "연간지출금액(원)", "연간취득금액(원)", "자산번호(선택)",
    "연료/에너지명",
    "운송수단(선택)", "자재명/품목명", "중량단위",
    "운송거리(km)(선택)", "연간운송량", "연간운송금액(원)",
    "폐기물 종류", "상세 폐기물명(선택)", "처리방법", "연간처리량",
    "출장주체", "편도거리(km)(선택)", "연간이동횟수", "연간근무일수",
    "출장항목",
    "임차자산명", "임대자산명", "에너지종류",
    "건물전체 면적", "사용 면적",
    "건물전체 인원수", "자사 인원수",
    "건물전체 연간사용량",
    "보고연도", "에너지명",
    "제품당 연간 에너지 사용량",
    "수명(개월) 혹은 평균 사용기간(개월)",
    "폐기물 대분류(선택)", "폐기물 중분류(선택)", "폐기물 소분류(선택)",
    "판매량", "제품중량", "제품중량 단위",
    "프랜차이즈명", "가맹점 수", "연료 종류", "연료 사용량", "연료 단위",
    "피투자기업명 (필수)", "지분율(%) (선택)",
    "피투자기업 Scope1배출량", "피투자기업 Scope2배출량",
    "비고(선택)",
}  # fmt: skip
_HEADERS_3451: Final = {
    "구매 월", "구매월", "발생월", "분류", "자재명",
    "비용", "이동거리", "인원수",
    "03_출장_Template", "04_통근_Template",
}  # fmt: skip
_HEADERS_5681: Final = {
    "국가", "사업장", "품목군", "자산분류", "상세 품목명/서비스명", "상세 자산명",
    "계정과목(선택)", "거래처명(선택)", "연간지출금액(원)", "연간취득금액(원)",
    "자산번호(선택)", "비고(선택)",
    "연료/에너지명", "연간사용량", "월사용량",
    "운송수단(선택)", "자재명/품목명", "중량단위", "출발지", "도착지",
    "운송거리(km)(선택)", "연간운송량", "연간운송금액(원)", "월운송량",
    "폐기물 종류", "상세 폐기물명(선택)", "처리방법", "연간처리량",
    "출장주체", "교통수단", "편도거리(km)(선택)",
    "연간이동횟수", "연간근무일수", "출장항목", "임차자산명", "임대자산명", "에너지종류",
    "건물전체 면적", "사용 면적", "건물전체 인원수", "자사 인원수",
    "건물전체 연간사용량",
    "보고연도", "제품명", "제품수량", "에너지명",
    "제품당 연간 에너지 사용량", "수명(개월) 혹은 평균 사용기간(개월)",
    "폐기물 대분류(선택)", "폐기물 중분류(선택)", "폐기물 소분류(선택)",
    "판매량", "제품중량", "제품중량 단위",
    "재활용 비중(%)(선택)", "소각 비중(%)(선택)", "매립 비중(%)(선택)", "기타 비중(%)(선택)",
    "프랜차이즈명", "가맹점 수", "연료 종류", "연료 사용량", "연료 단위",
    "피투자기업명 (필수)", "지분율(%) (선택)",
    "피투자기업 Scope1배출량", "피투자기업 Scope2배출량",
}  # fmt: skip
KNOWN_TEMPLATE_HEADERS: Final[frozenset[str]] = frozenset(_HEADERS_2076 | _HEADERS_2293 | _HEADERS_3451 | _HEADERS_5681)

# 코랩 :4833 — 월 이름(셀 22 `:3483-3484`)
MONTH_NAME_TO_NUM: Final[dict[str, int]] = {f"{i}월": i for i in range(1, 13)}
PURCHASE_WIDE_MONTH_COLS: Final[list[str]] = list(MONTH_NAME_TO_NUM.keys())

ProcessorKey = Literal[
    "c1", "c2", "c3", "c4_dist", "c4_spend", "c5", "c6_dist", "c6_spend", "c7", "c8_energy", "c8_area",
    "c8_person", "c9_dist", "c9_spend", "c11", "c12", "c13_energy", "c13_area", "c13_person", "c14", "c15",
]  # fmt: skip
Band = Literal["S3C-a", "S3C-b", "S3C-c"]


@dataclass(frozen=True)
class SheetProcessor:
    key: ProcessorKey
    category: str  # 코랩의 "Category1" 꼴
    theme: str
    band: Band  # 이 처리기를 옮기는(옮길) 밴드


# 코랩 :5641-5663 — 키·차례·카테고리 그대로, 테마는 뒤 셀의 `update` 뒤 값(c8·c13 셋 → energy `:7109-7124`,
# c11 → sold_product_use `:7786-7789` — `ISSUE-193` 6, S3C-b1). 테마를 읽는 곳은 0 이다.
# 처리 함수 대신 이름과 맡는 밴드(C1·C2 = a,
# 거리·지출·폐기물·출장·통근 = b, 나머지 = c 로 둔다 — 발주서 §5「C3~C15·생물기원·거리 … — S3C-b·c」의 가르기는 감독이
# b 발주 때 다시 정한다).
SHEET_PROCESSOR_MAP: Final[dict[str, SheetProcessor]] = {
    "c1_구매품서비스": SheetProcessor("c1", "Category1", "purchase", "S3C-a"),
    "c2_자본재": SheetProcessor("c2", "Category2", "purchase", "S3C-a"),
    "c3_연료에너지": SheetProcessor("c3", "Category3", "energy", "S3C-c"),
    "c4-1_운송거리": SheetProcessor("c4_dist", "Category4", "transport", "S3C-b"),
    "c4-2_운송금액": SheetProcessor("c4_spend", "Category4", "transport", "S3C-b"),
    "c5_사업장폐기물": SheetProcessor("c5", "Category5", "waste", "S3C-b"),
    "c6-1_출장거리": SheetProcessor("c6_dist", "Category6", "travel", "S3C-b"),
    "c6-2_출장비": SheetProcessor("c6_spend", "Category6", "travel", "S3C-b"),
    "c7_임직원통근": SheetProcessor("c7", "Category7", "travel", "S3C-b"),
    "c8-1_에너지사용량 아는 경우": SheetProcessor("c8_energy", "Category8", "energy", "S3C-c"),
    "c8-2_면적": SheetProcessor("c8_area", "Category8", "energy", "S3C-c"),
    "c8-3_인원": SheetProcessor("c8_person", "Category8", "energy", "S3C-c"),
    "c9-1_운송거리": SheetProcessor("c9_dist", "Category9", "transport", "S3C-b"),
    "c9-2_운송금액": SheetProcessor("c9_spend", "Category9", "transport", "S3C-b"),
    "c11_판매제품사용": SheetProcessor("c11", "Category11", "sold_product_use", "S3C-c"),
    "c12_판매제품폐기": SheetProcessor("c12", "Category12", "product_eol", "S3C-c"),
    "c13-1_에너지사용량 아는경우": SheetProcessor("c13_energy", "Category13", "energy", "S3C-c"),
    "c13-2_면적": SheetProcessor("c13_area", "Category13", "energy", "S3C-c"),
    "c13-3_인원": SheetProcessor("c13_person", "Category13", "energy", "S3C-c"),
    "c14_프랜차이즈": SheetProcessor("c14", "Category14", "franchise", "S3C-c"),
    "c15_투자": SheetProcessor("c15", "Category15", "investment", "S3C-c"),
}


def match_sheet_processor(sheet_name: str) -> SheetProcessor | None:
    """코랩 `_match_sheet_processor`(`:5665`) 그대로: 정확히 같으면 그것, 아니면 dict 차례로 포함·앞 4글자."""
    n = str(sheet_name).strip().lower()
    if n in SHEET_PROCESSOR_MAP:
        return SHEET_PROCESSOR_MAP[n]
    for key, val in SHEET_PROCESSOR_MAP.items():
        if key in n or n.startswith(key[:4]):
            return val
    return None


def is_new_template(sheet_names: list[str]) -> bool:
    """코랩 `process_template_inventory`(`:6387-6391`): 「c + 숫자」로 시작하는 시트가 하나라도 있으면 새 v1 템플릿."""
    lowered = [str(s).strip().lower() for s in sheet_names]
    return any(s.startswith("c") and len(s) > 1 and s[1].isdigit() for s in lowered)


def _is_null(value: object) -> bool:
    """코랩 `pd.isnull(v)` 의 자리. frame 의 칸 값은 글·수·NaN·None 뿐이다(frames.py) — 그 넷에서 같다."""
    return value is None or (isinstance(value, float) and math.isnan(value))


def _normalize_header_token(v: object) -> str:
    """코랩 `:2085`."""
    if _is_null(v):
        return ""
    return str(v).strip().lower()


def _row_values(frame: pd.DataFrame, i: int) -> list[object]:
    return list(frame.iloc[i].tolist())


def detect_template_header_row(sheet: Sheet, max_rows: int = 20) -> int:
    """코랩 `:2091-2125` 그대로(파일 대신 읽힌 시트)."""
    preview = read_frame(sheet, header=None, nrows=max_rows)
    best_row = 0
    best_score = -1
    normalized_known = {_normalize_header_token(x) for x in KNOWN_TEMPLATE_HEADERS}
    normalized_known |= {_normalize_header_token(x).lstrip("*").strip() for x in KNOWN_TEMPLATE_HEADERS}
    for i in range(min(max_rows, len(preview))):
        row_vals_raw = [str(v).strip() if not _is_null(v) else "" for v in _row_values(preview, i)]
        star_count = sum(1 for v in row_vals_raw if v.startswith("*") and len(v) > 1)
        row_vals_norm = [v.lstrip("*").strip().lower() for v in row_vals_raw if v]
        match_score = sum(1 for v in row_vals_norm if v in normalized_known)
        score = match_score + star_count * 2
        if score > best_score:
            best_score = score
            best_row = i
    return best_row if best_score >= 2 else 0


_MONTH_SET: Final = {f"{i}월" for i in range(1, 13)}
_ANNUAL_SET: Final = {
    "연간지출금액(원)", "연간취득금액(원)", "연간사용량",
    "연간운송량", "연간운송금액(원)", "연간처리량",
    "연간이동횟수", "연간근무일수",
}  # fmt: skip
_GROUP_HEADERS: Final = {
    "연간 입력", "월별 지출금액", "월별 취득금액", "월별 사용량",
    "월별 운송량", "월별 운송금액", "월별 처리량", "월별 이동횟수",
    "월별 근무일수", "건물전체 월별사용량", "출도착지",
}  # fmt: skip
_AI_GUIDE_VALS: Final = {"AI 추천", "AI 자동산정", "ai 추천", "ai 자동산정"}
_GUIDE_PATTERNS: Final = [
    "카테고리", "작성 기준", "※", "1)", "2)", "3)", "4)", "5)",
    "- ", "Scope", "배출계수는", "온실가스 산정",
]  # fmt: skip


def _read_template_sheet_2128(sheet: Sheet) -> pd.DataFrame:
    """코랩 `read_template_sheet`(`:2128-2284`, 옛 판) 그대로(파일 대신 읽힌 시트). index = 시트의 줄 자리(0부터)."""
    df_raw = read_frame(sheet, header=None)
    if df_raw.empty:
        return pd.DataFrame()

    # Step 1: 주헤더 행 찾기
    main_header_row: int | None = None
    for i in range(min(25, len(df_raw))):
        row_vals = [str(v).strip() for v in _row_values(df_raw, i) if not _is_null(v) and str(v).strip()]
        star_count = sum(1 for v in row_vals if v.startswith("*"))
        group_count = sum(1 for v in row_vals if v in _GROUP_HEADERS)
        if star_count >= 2 or (star_count >= 1 and group_count >= 1):
            main_header_row = i
            break
    if main_header_row is None:
        main_header_row = detect_template_header_row(sheet)
    if main_header_row >= len(df_raw):
        return pd.DataFrame()

    # Step 2: 서브헤더 행
    main_vals = [str(v).strip() if not _is_null(v) else "" for v in _row_values(df_raw, main_header_row)]
    sub_row = main_header_row + 1
    has_sub = False
    sub_vals_raw: list[str] = []
    if sub_row < len(df_raw):
        sub_vals_raw = [str(v).strip() if not _is_null(v) else "" for v in _row_values(df_raw, sub_row)]
        month_cnt = sum(1 for v in sub_vals_raw if v in _MONTH_SET)
        annual_cnt = sum(1 for v in sub_vals_raw if v in _ANNUAL_SET)
        has_sub = month_cnt >= 2 or annual_cnt >= 1

    # Step 3: 최종 컬럼명
    if has_sub:
        final_cols: list[str] = []
        for ci, (main, sub) in enumerate(zip(main_vals, sub_vals_raw, strict=False)):
            if (main in _GROUP_HEADERS and sub) or (not main and sub):
                final_cols.append(sub)
            elif main.startswith("Unnamed"):
                final_cols.append(sub if sub else f"_col{ci}")
            else:
                final_cols.append(main if main else f"_col{ci}")
        data_start = sub_row + 1
    else:
        final_cols = [v if v else f"_col{ci}" for ci, v in enumerate(main_vals)]
        data_start = main_header_row + 1

    # Step 4: 데이터
    df = df_raw.iloc[data_start:].copy()
    n_cols = min(len(final_cols), len(df.columns))
    df = df.iloc[:, :n_cols]
    df.columns = pd.Index(final_cols[:n_cols])

    # Step 5: 완전 빈 행 제거(코랩은 여기서 reset_index — 줄 자리를 들고 가려고 끝에서 푼다)
    df = df.dropna(how="all")

    # Step 6: * 제거, 불필요 컬럼 제거
    df.columns = pd.Index([str(c).lstrip("*").strip() for c in df.columns])

    def _col_has_real_data(col: str) -> bool:
        vals = df[col].dropna()
        real = [v for v in vals if str(v).strip() not in ("", "nan", *_AI_GUIDE_VALS)]
        return len(real) > 0

    keep_cols: list[str] = []
    for c in df.columns:
        name = str(c)
        if name.startswith("_col"):
            if _col_has_real_data(name):
                keep_cols.append(name)
        else:
            keep_cols.append(name)
    df = df[keep_cols]

    cols_to_drop: list[str] = []
    for c in df.columns:
        if any(k in str(c) for k in ["배출계수", "배출량"]):
            vals = colab_str(df[c].dropna()).str.strip()  # 코랩 `df[c].dropna().astype(str).str.strip()`
            if vals.empty or bool(vals.isin(_AI_GUIDE_VALS).all()):
                cols_to_drop.append(str(c))
    if cols_to_drop:
        df = df.drop(columns=cols_to_drop)

    # Step 7: 연간/월별 행 구분 태깅
    annual_cols = [c for c in df.columns if c in _ANNUAL_SET]
    month_cols = [str(c) for c in df.columns if c in _MONTH_SET]
    if annual_cols and month_cols:

        def _has_monthly(r: "pd.Series[Any]") -> bool:
            return any(not _is_null(r.get(m)) and str(r.get(m)).strip() not in ("", "nan", "0") for m in month_cols)

        monthly_mask = df.apply(_has_monthly, axis=1).astype(bool)
        df.loc[~monthly_mask, "입력방식"] = "연간"
        df.loc[monthly_mask, "입력방식"] = "월별"
    elif month_cols:
        df["입력방식"] = "월별"
    else:
        df["입력방식"] = "연간"

    # Step 8: 작성가이드 잔재 행 제거
    first_col = df.columns[0] if len(df.columns) > 0 else None
    if first_col:  # 코랩 그대로: 「*」 하나뿐인 머리글은 빈 글자가 되어 이 단계를 건너뛴다

        def _is_guide(v: object) -> bool:
            s = str(v).strip()
            return any(s.startswith(p) for p in _GUIDE_PATTERNS) or len(s) > 80

        guide_mask = df[first_col].apply(_is_guide).astype(bool)
        if bool(guide_mask.any()):
            df = df[~guide_mask]

    return df


def _read_template_sheet_6542(sheet: Sheet) -> pd.DataFrame:
    """코랩 `read_template_sheet`(`:6542-6560`, 패치 판): 옛 판을 부르고 `_col*` 보조열을 걷는다. index 는 줄 자리."""
    df = _read_template_sheet_2128(sheet)
    if df.empty:
        return pd.DataFrame()
    df = df.copy()
    helper_cols = [c for c in df.columns if str(c).startswith("_col")]
    if helper_cols:
        df = df.drop(columns=helper_cols, errors="ignore")
    return df.dropna(how="all")


def read_template_sheet(sheet: Sheet) -> pd.DataFrame:
    """코랩 `read_template_sheet`(`:6542`)가 내는 frame(index 0부터)."""
    return _read_template_sheet_6542(sheet).reset_index(drop=True)


TEMPLATE_ROW: Final = "__excel_row__"
"""`read_template_rows` 가 끝에 붙이는 열: 그 줄의 엑셀 줄 번호(1부터). 템플릿 머리글이 될 수 없는 이름이다."""


def read_template_rows(sheet: Sheet) -> pd.DataFrame:
    """`read_template_sheet` 와 같은 frame 의 끝에 `TEMPLATE_ROW` 열을 더한 것. 빈 frame 이면 열을 더하지 않는다."""
    df = _read_template_sheet_6542(sheet)
    if df.empty:
        return pd.DataFrame()
    rows = [int(position) + 1 for position in df.index]
    df = df.reset_index(drop=True)
    df[TEMPLATE_ROW] = rows
    return df


def _strip_asterisk(col: str) -> str:
    """코랩 `:4833`."""
    return str(col).strip().lstrip("*").strip()


def normalize_template_columns(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `:4837-4848`."""
    df = df.copy()
    new_cols: list[str] = []
    for c in df.columns:
        s = str(c).strip()
        if s.startswith("Unnamed") or s == "nan":
            new_cols.append(s)
        else:
            new_cols.append(_strip_asterisk(s))
    df.columns = pd.Index(new_cols)
    return df


def sum_monthly_spend(df: pd.DataFrame, spend_col: str) -> pd.DataFrame:
    """코랩 `process_new_template` 안의 `_sum_monthly_spend`(`:5947-5958`): 「월별」 행의 1월~12월 합을 spend_col 에."""
    month_cols = [c for c in df.columns if c in set(PURCHASE_WIDE_MONTH_COLS)]
    if not month_cols:
        return df
    df = df.copy()
    input_type = df["입력방식"] if "입력방식" in df.columns else pd.Series("연간", index=df.index)
    monthly_mask = (input_type == "월별").astype(bool)
    if bool(monthly_mask.any()):
        s = df.loc[monthly_mask, month_cols].apply(pd.to_numeric, errors="coerce").sum(axis=1)
        if spend_col not in df.columns:
            df[spend_col] = None
        colab_loc_set(df, monthly_mask, spend_col, s.where(s > 0, other=None))  # 코랩 `df.loc[…] = …`(2.x 올림)
    return df
