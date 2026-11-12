"""코랩 대조(esg-lab `scope3colab`, `MARC-ENT-294`)에 줄 엔진 쪽 JSON 을 낸다. pytest 가 모으지 않는 스크립트다.

    uv run python -m esgapi.inventory.tests.scope3colab_dump --template <xlsx> --factor-book <xlsx> --answers <json>
        [--report-year <n>] [--geocode-queries <json>] [--result-file <xlsx>] [--filled-file <xlsx>] > engine.json

- `pipeline.run` 을 그대로 부른다. LLM 은 `--answers`(esg-lab `py/scope3colab/answers.synthetic.json` 꼴 —
  `{"synthetic": true, "answers": [{"text": …, "expect": …}, …]}`)를 차례대로 답하는 모의 공급사, 지오코더는 물음을
  기록하고 늘 못 찾음을 내는 가짜다(esg-lab 거리판 하네스의 가짜 `Nominatim.geocode` 와 같은 규칙 — S3C-b2a). 그 물음
  목록은 `--geocode-queries` 로 따로 쓴다(esg-lab `run.json` 의 `geocode_queries` 와 견줄 것). 네트워크·키 0. 답이
  모자라거나 `expect` 글이 프롬프트에 없거나 쓰이지 않은 답이 남으면 도구 실패.
- 출력은 esg-lab `py/scope3colab/rows.py` 머리의 `scope3colab.rows/1` 꼴(`side: "engine"`). esg-lab 을 import 하지
  않는다 — 칸 이름(`SHEET_FIELDS`)과 품목 열 후보는 그 파일(esg-lab 49e4515)과 S3C-o2 보고 「b1 이 따를 표」 에 맞춰
  여기 다시 적었다. 견주는 열쇠는 C1·C2·C4·C9·C6·C7·C5·C3·C8·C13·C12·C15·C11·C14(처리기 `category` — C3·C8·C13 은
  S3C-c1a, C12·C15 는 S3C-c1b-1, C11·C14 는 S3C-c1b-2 — 21키 전부), row 는
  같은 열쇠 안에서 템플릿 시트 차례로 이어 센다(코랩이 C4-1+C4-2·C6-1+C6-2·C8-1~3·C13-1~3 을 한 결과 시트로 합침
  `:6237-6246`). 견주지 않는 열쇠(S3C-c1b-2 뒤에는 없다)의 시트에 데이터 줄이 있으면 `not_compared` 에 시트 이름이
  남는다. 견주는 열쇠의 지원 안 함 시트(S3C-c1a 뒤에는 없다)에 데이터 줄이 있으면 도구 실패, 머리글만이면 지나간다.
- 줄 갈래(S3C-o3 보고 「b2 가 따를 표」 3): 줄 메타의 kind 가 `transport_distance`·`travel_distance` 인 줄만
  `"branch": "Distance"` 를 달고 `BRANCH_FIELDS` 칸으로 낸다. 지출 줄·`commute`(C7) 줄은 키 없음(o2·b1 꼴 그대로).
  frame 에 「계산방식」 이 있으면 kind 와 대 보고 어긋나면 도구 실패.
- 견줄 frame 은 `ProcessedSheet.frame`(코랩 결과 시트, 후처리 뒤 — pipeline.py 머리). 빈 값은 null, 정수는 그대로,
  소수는 **코랩 결과 파일에 적히는 값**: openpyxl 이 수를 `"%.16g"` 로 쓰고(`openpyxl.compat.strings.safe_string`) 읽을
  때 float 로 되돌리므로 `repr(float("%.16g" % x))`. esg-lab 견줌은 `Decimal` 같음·허용 오차 0 이고 코랩 쪽을 파일에서
  읽으니 엔진 쪽이 같은 자름을 해야 17자리 float(예: 1845000 × 0.000914 / 1000 = 1.6863299999999999 → 파일 1.68633)가
  끝자리 차이를 내지 않는다(S3C-b1 대조에서 처음 만남).
- 출력 파일 둘(S3C-c2): `--result-file`·`--filled-file` 을 주면 `ColabRun.outputs`(내용은 엔진 `output_files.py`)를
  openpyxl 로 바이트에 쓴다 — 결과 파일은 `pd.ExcelWriter(engine="openpyxl")` + `to_excel(index=False)` 한 번, 채운
  템플릿은 **원래 템플릿 바이트**(우리 읽개가 읽은 그 바이트)를 `openpyxl.load_workbook` 으로 열어 칸에 넣고
  `save`(코랩 `:9367`·`:9469`). 쓰개 둘은 메모리 → 끝에 파일 한 번. 흐름에 파일을 실을 때(S3C-c3) `outputs/` 로 옮긴다.
  주지 않으면 JSON 은 바이트까지 그대로다.
- 종료 코드: 냄 0, 도구 실패 2(입력을 못 읽음·실행 거절·답 어긋남·청한 파일의 내용이 `OutputsFailed`·없음).
"""

import argparse
import io
import json
import math
import numbers
import sys
from pathlib import Path
from typing import Any, Final, cast

import openpyxl
import pandas as pd

from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider
from esgapi.core.llm.types import Completed, InvokeOptions, ProviderError, ProviderRequest, ProviderResponse, Tags
from esgapi.inventory.engines.scope3.colab_157.activity import ActivityMeta
from esgapi.inventory.engines.scope3.colab_157.output_files import CellWrite, OutputFiles, ResultSheet
from esgapi.inventory.engines.scope3.colab_157.pdcompat import legacy_strings
from esgapi.inventory.engines.scope3.colab_157.pipeline import (
    ColabRejected,
    ColabRun,
    NotTargetSheet,
    NotYetSupportedSheet,
    ProcessedSheet,
    SheetOutcome,
    run,
)
from esgapi.inventory.engines.scope3.colab_157.ports import Coordinates, NotFound
from esgapi.inventory.engines.scope3.colab_157.template import read_template_rows
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client, user_text
from esgapi.inventory.tools.scope3_sheets.grid import Workbook
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

SCHEMA: Final = "scope3colab.rows/1"
TAGS: Final = Tags(tenant="가상회사", module="inventory")
type Field = tuple[str, str, bool]  # (JSON 칸, 코랩 결과 열, 숫자인가)

# esg-lab rows.py(49e4515) 의 `FIELDS`·`TRANSPORT_SPEND_FIELDS`·`TRAVEL_SPEND_FIELDS`·`WASTE_FIELDS` 와 같은 차례·글자
# (S3C-o2 보고 「b1 이 따를 표」).
FIELDS: Final[tuple[Field, ...]] = (
    ("구매금액(KRW)", "EF적용금액(KRW)", True),
    ("대표EF", "EF_DB", False),
    ("대표EF_배출계수", "배출계수", True),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
    ("산정출처", "EF_DB_추천사유", False),
    *(
        item
        for i in range(1, 5)
        for item in ((f"추천EF{i}", f"추천EF{i}", False), (f"추천EF{i}_배출계수", f"추천EF{i}_배출계수", True))
    ),
)
TRANSPORT_SPEND_FIELDS: Final[tuple[Field, ...]] = (
    ("운송금액", "운송금액", True),
    ("EF(kgCO2e/KRW)", "EF(kgCO2e/KRW)", True),
    ("배출계수단위", "배출계수단위", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
)
TRAVEL_SPEND_FIELDS: Final[tuple[Field, ...]] = (
    ("출장비용", "출장비용", True),
    ("EF_DB", "EF_DB", False),
    ("NAICS", "NAICS", False),
    ("배출계수", "배출계수", True),
    ("배출계수단위", "배출계수단위", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
    ("계산식", "계산식", False),
    ("정규화이동수단", "정규화이동수단", False),
)
WASTE_FIELDS: Final[tuple[Field, ...]] = (
    ("처리량", "처리량", True),
    ("배출계수(kgCO2eq/kg)", "배출계수(kgCO2eq/kg)", True),
    ("처리방법_정규화", "처리방법_정규화", False),
    ("화석기원 CO2e(tCO2e)", "화석기원 CO2e(tCO2e)", True),
    ("생물기원 CO2e(tCO2e)", "생물기원 CO2e(tCO2e)", True),
    ("화석탄소비율(FCF)", "화석탄소비율(FCF)", True),
    ("바이오매스 구분", "바이오매스 구분", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
    ("단위환산비고", "단위환산비고", False),
)
# esg-lab rows.py(c1ac9c4) 의 `TRANSPORT_DISTANCE_FIELDS`(S3C-o3 보고 「b2 가 따를 표」 4 — C4·C9 거리 갈래)
TRANSPORT_DISTANCE_FIELDS: Final[tuple[Field, ...]] = (
    ("월운송량", "월운송량", True),
    ("화물중량(kg)", "화물중량(kg)", True),
    ("운송거리(km)", "운송거리(km)", True),
    ("배출계수(거리기반)", "배출계수(거리기반)", True),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
)
# esg-lab rows.py(c1ac9c4) 의 `TRAVEL_DISTANCE_FIELDS`·`COMMUTE_FIELDS`(S3C-o3 보고 「b2 가 따를 표」 4 — C6 거리
# 갈래·C7)
TRAVEL_DISTANCE_FIELDS: Final[tuple[Field, ...]] = (
    ("이동거리(km)", "이동거리(km)", True),
    ("출장인원", "출장인원", True),
    ("이동횟수", "이동횟수", True),
    ("거리왕복계수", "거리왕복계수", True),
    ("정규화이동수단", "정규화이동수단", False),
    ("배출계수", "배출계수", True),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
    ("계산식", "계산식", False),
)
COMMUTE_FIELDS: Final[tuple[Field, ...]] = (
    ("평균통근거리(km)", "평균통근거리(km)", True),
    ("직원수", "직원수", True),
    ("근무일수", "근무일수", True),
    ("거리왕복계수", "거리왕복계수", True),
    ("정규화이동수단", "정규화이동수단", False),
    ("배출계수", "배출계수", True),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
    ("계산식", "계산식", False),
)
# esg-lab rows.py(302d8ec) 의 `ENERGY_C3_FIELDS`·`LEASED_FIELDS`(S3C-o4a 보고 「S3C-c1 이 따를 표」 3 — C3·C8·C13).
# C8·C13 의 계수 이름은 결과에 없다(EF매핑명 열 없음).
ENERGY_C3_FIELDS: Final[tuple[Field, ...]] = (
    ("사용량", "사용량", True),
    ("배출계수(kgCO2eq/단위)", "배출계수(kgCO2eq/단위)", True),
    ("EF단위", "EF단위", False),
    ("EF매핑명", "EF매핑명", False),
    ("단위환산비고", "단위환산비고", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
)
LEASED_FIELDS: Final[tuple[Field, ...]] = (
    ("산정방식", "산정방식", False),
    ("건물전체사용량", "건물전체사용량", True),
    ("면적비율", "면적비율", True),
    ("인원비율", "인원비율", True),
    ("사용량", "사용량", True),
    ("배출계수(kgCO2eq/단위)", "배출계수(kgCO2eq/단위)", True),
    ("EF단위", "EF단위", False),
    ("단위환산비고", "단위환산비고", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
)
# esg-lab rows.py(302d8ec) 의 `PRODUCT_EOL_FIELDS`·`INVESTMENT_FIELDS`(S3C-o4a 보고 「S3C-c1 이 따를 표」 3 — C12·C15).
# C15 의 배출량은 단위 없는 이름 「배출량」(`:5630`).
PRODUCT_EOL_FIELDS: Final[tuple[Field, ...]] = (
    ("배출계수", "배출계수", True),
    ("화석기원 CO2e(tCO2e)", "화석기원 CO2e(tCO2e)", True),
    ("생물기원 CO2e(tCO2e)", "생물기원 CO2e(tCO2e)", True),
    ("화석탄소비율(FCF)", "화석탄소비율(FCF)", True),
    ("바이오매스 구분", "바이오매스 구분", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
)
INVESTMENT_FIELDS: Final[tuple[Field, ...]] = (("배출량", "배출량", True),)
# esg-lab rows.py(302d8ec) 의 C11·C14 칸(S3C-o4a 보고 「S3C-c1 이 따를 표」 3 — 결과 후처리 `:8720`·`:8862` 뒤 값).
# EF매핑방식·EF매핑점수는 견주지 않는다(따를 표 4).
PRODUCT_USE_FIELDS: Final[tuple[Field, ...]] = (
    ("사용기간(년)", "사용기간(년)", True),
    ("총사용량", "총사용량", True),
    ("배출계수(kgCO2eq/단위)", "배출계수(kgCO2eq/단위)", True),
    ("EF단위", "EF단위", False),
    ("EF매핑명", "EF매핑명", False),
    ("단위환산비고", "단위환산비고", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
)
FRANCHISE_FIELDS: Final[tuple[Field, ...]] = (
    ("사용량", "사용량", True),
    ("배출계수(kgCO2eq/단위)", "배출계수(kgCO2eq/단위)", True),
    ("EF단위", "EF단위", False),
    ("EF매핑명", "EF매핑명", False),
    ("단위환산비고", "단위환산비고", False),
    ("배출량(tCO2e)", "배출량(tCO2e)", True),
    ("계산식", "계산식", False),
)
DISTANCE: Final = "Distance"
BRANCH_COLUMN: Final = "계산방식"
# (열쇠, 갈래) → 칸. 이 표에 없는 줄(지출 줄·C7 통근 줄 — C7 결과에는 「계산방식」 열이 없다)은 `SHEET_FIELDS[열쇠]`.
BRANCH_FIELDS: Final[dict[tuple[str, str], tuple[Field, ...]]] = {
    ("C4", DISTANCE): TRANSPORT_DISTANCE_FIELDS,
    ("C9", DISTANCE): TRANSPORT_DISTANCE_FIELDS,
    ("C6", DISTANCE): TRAVEL_DISTANCE_FIELDS,
}
DISTANCE_BRANCH_KINDS: Final = frozenset({"transport_distance", "travel_distance"})
SHEET_FIELDS: Final[dict[str, tuple[Field, ...]]] = {
    "C1": FIELDS,
    "C2": FIELDS,
    "C4": TRANSPORT_SPEND_FIELDS,
    "C5": WASTE_FIELDS,
    "C6": TRAVEL_SPEND_FIELDS,
    "C7": COMMUTE_FIELDS,
    "C9": TRANSPORT_SPEND_FIELDS,
    "C3": ENERGY_C3_FIELDS,
    "C8": LEASED_FIELDS,
    "C13": LEASED_FIELDS,
    "C12": PRODUCT_EOL_FIELDS,
    "C15": INVESTMENT_FIELDS,
    "C11": PRODUCT_USE_FIELDS,
    "C14": FRANCHISE_FIELDS,
}
# 줄 열쇠의 sheet = 처리기 `category`(코랩은 같은 Category 의 템플릿 시트를 한 결과 시트로 합친다 `:6237-6246`)
COMPARED_CATEGORIES: Final[dict[str, str]] = {f"Category{key[1:]}": key for key in SHEET_FIELDS}
# 품목 열 후보(앞에서부터, 합친 결과에 있고 값이 하나라도 든 첫 열 — 코랩은 쓰기 전 전부 빈 열을 지운다)
ITEM_COLUMNS: Final[dict[str, tuple[str, ...]]] = {
    "C1": ("품목명", "자산명"),
    "C2": ("품목명", "자산명"),
    "C4": ("자재명", "제품명"),
    "C9": ("제품명", "자재명"),
    "C6": ("이동수단", "출장수단"),
    "C7": ("이동수단", "교통수단"),
    "C5": ("폐기물 종류", "상세폐기물명"),
    "C3": ("에너지원", "연료/에너지명"),  # S3C-o4a 「따를 표」 1 — 표준화가 「연료/에너지명」·「에너지종류」를 rename
    "C8": ("에너지원", "에너지종류"),
    "C13": ("에너지원", "에너지종류"),
    "C12": ("제품명",),  # S3C-o4a 「따를 표」 1
    "C15": ("피투자기업명",),  # 표준화가 「피투자기업명 (필수)」 를 rename
    "C11": ("제품명", "에너지명"),  # S3C-o4a 「따를 표」 1
    "C14": ("프랜차이즈명",),
}
TOOL_FAILED: Final = 2


class DumpFailed(Exception):
    pass


class OrderedAnswers(MockProvider):
    """짜 둔 답을 부른 차례대로 낸다(esg-lab 하네스의 가짜 `messages.create` 와 같은 규칙)."""

    def __init__(self, answers: list[tuple[str, str | None]]) -> None:
        super().__init__()
        self.answers = answers
        self.problems: list[str] = []
        self.used = 0

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.enqueue(self.reply)
        return super().invoke(request, options)

    def reply(self, request: ProviderRequest) -> ProviderResponse:
        prompt = user_text(request)
        n = self.used
        self.used += 1
        if n >= len(self.answers):
            self.problems.append(f"부름 {n + 1}: 짜 둔 답이 {len(self.answers)}개뿐")
            return ProviderError(status=None, retryable=False, message="가상: 짜 둔 답이 모자란다")
        text, expect = self.answers[n]
        if expect is not None and expect not in prompt:
            self.problems.append(f"부름 {n + 1}: 프롬프트에 {expect!r} 가 없다(부름 차례가 어긋남)")
            return ProviderError(status=None, retryable=False, message="가상: 답이 어긋났다")
        return Completed(text=text, usage=SYNTHETIC_USAGE)


class RecordingGeocoder:
    """물음을 기록하고 늘 못 찾음을 낸다(esg-lab 거리판의 가짜 `Nominatim.geocode` 가 None 을 내는 것과 같은 규칙)."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def geocode(self, query: str) -> Coordinates | NotFound:
        self.queries.append(query)
        return NotFound(query)


def load_answers(path: Path) -> list[tuple[str, str | None]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("synthetic") is not True:
        raise DumpFailed(f'{path}: 짜 둔 답 파일은 `"synthetic": true` 를 달아야 한다')
    return [(str(a["text"]), a.get("expect")) for a in data["answers"]]


def read_book(path: Path) -> Workbook:
    book = read_workbook(path.read_bytes())
    if isinstance(book, ReaderProblem):
        raise DumpFailed(f"{path}: 못 읽었다 — {book}")
    return book


def _is_empty(value: object) -> bool:
    return value is None or value is pd.NA or (isinstance(value, float) and math.isnan(value))


def number_text(value: object) -> str | None:
    if _is_empty(value):
        return None
    if isinstance(value, numbers.Integral):
        return str(int(value))  # numpy 정수 포함
    if isinstance(value, numbers.Real):
        number = float(value)
        if not math.isfinite(number):
            return None  # openpyxl 은 inf 를 빈 칸으로 쓴다
        return repr(float(f"{number:.16g}"))  # 결과 파일의 값(openpyxl `safe_string`)을 다시 읽은 float
    text = str(value).strip()
    return text or None


def text_value(value: object) -> str | None:
    if _is_empty(value):
        return None
    text = str(value)
    return text if text.strip() else None


def compared_key(outcome: SheetOutcome) -> str | None:
    """줄 열쇠의 sheet(`C4` 등). 처리기가 없거나 견주지 않는 Category 면 None."""
    if isinstance(outcome, NotTargetSheet):
        return None
    return COMPARED_CATEGORIES.get(outcome.processor.category)


def has_data_rows(template: Workbook, name: str) -> bool:
    """그 템플릿 시트를 `read_template_rows` 로 읽어 데이터 줄이 하나라도 있는가(머리글만이면 False).

    머리글만인 시트는 읽기가 ValueError(「cannot set a frame with no defined index and a scalar」 — 빈 frame 의 입력방식
    태깅 `:2128` Step 7)를 낸다. 코랩도 같은 자리에서 `[error] <시트>: …` 를 찍고 그 시트를 건너뛰어(S3C-b1 대조의
    colab-stdout.log) 결과에 줄이 없으니 「데이터 줄 없음」 이다.
    """
    sheet = next(s for s in template.sheets if s.name == name)
    with legacy_strings():
        try:
            return not read_template_rows(sheet).empty
        except ValueError:
            return False


def _item_column(key: str, frames: list[pd.DataFrame]) -> str:
    for name in ITEM_COLUMNS[key]:
        if any(name in f.columns and any(text_value(v) is not None for v in f[name]) for f in frames):
            return name
    raise DumpFailed(f"{key}: 값이 든 품목 열({' / '.join(ITEM_COLUMNS[key])})이 없다")


def branch_of(key: str, meta: object, record: "pd.Series[Any]") -> str | None:
    """줄 갈래: 거리 kind 면 `Distance`, 그 밖은 None. frame 의 「계산방식」 이 있으면 kind 와 대 본다."""
    kind = meta.kind if isinstance(meta, ActivityMeta) else None
    branch = DISTANCE if kind in DISTANCE_BRANCH_KINDS else None
    if branch is not None and (key, branch) not in BRANCH_FIELDS:
        raise DumpFailed(f"{key}: 칸 표에 없는 갈래 {branch!r}(kind {kind})")
    method = text_value(record.get(BRANCH_COLUMN))
    if method is not None and (method.strip() == DISTANCE) != (branch == DISTANCE):
        raise DumpFailed(f"{key}: 「계산방식」 {method!r} 와 줄 kind {kind!r} 가 어긋난다")
    return branch


def rows_of(sheets: tuple[SheetOutcome, ...], template: Workbook) -> dict[str, Any]:
    """열쇠(처리기 Category)마다 템플릿 시트 차례로 frame 을 잇고, 그 안의 차례로 row 를 센다.

    지원하지 않는 시트(`NotYetSupportedSheet`)가 견주는 열쇠에 들고 데이터 줄이 있으면 도구 실패(그 열쇠의 코랩 결과에는
    그 줄이 섞인다), 머리글만이면 지나간다. 견주지 않는 Category 의 시트는 데이터 줄이 있을 때만 `not_compared`(코랩
    결과 파일에 시트가 생기는 경우)에 이름을 적는다.
    """
    frames: dict[str, list[ProcessedSheet]] = {}
    not_compared: list[str] = []
    for outcome in sheets:
        key = compared_key(outcome)
        if key is None:
            if isinstance(outcome, NotYetSupportedSheet | ProcessedSheet) and has_data_rows(template, outcome.sheet):
                not_compared.append(outcome.sheet)
            continue
        if isinstance(outcome, NotYetSupportedSheet):
            if has_data_rows(template, outcome.sheet):
                raise DumpFailed(f"{key}: 지원하지 않는 시트 {outcome.sheet!r} 에 데이터 줄이 있다")
            continue
        if isinstance(outcome, ProcessedSheet):
            frames.setdefault(key, []).append(outcome)
        # 빈 시트·실패한 시트는 코랩 결과 파일에도 없다
    rows: list[dict[str, Any]] = []
    for key, parts in frames.items():
        item_col = _item_column(key, [part.frame for part in parts])
        n = 0
        for part in parts:
            frame = part.frame
            for position, (_, record) in enumerate(frame.iterrows()):
                n += 1
                branch = branch_of(key, part.metas[position], record)
                table = BRANCH_FIELDS[(key, branch)] if branch is not None else SHEET_FIELDS[key]
                fields = {
                    name: (number_text if numeric else text_value)(record[column] if column in frame.columns else None)
                    for name, column, numeric in table
                }
                item = text_value(record[item_col]) if item_col in frame.columns else None
                row: dict[str, Any] = {"sheet": key, "row": n, "item": item or ""}
                if branch is not None:
                    row["branch"] = branch
                row["fields"] = fields
                rows.append(row)
    return {"schema": SCHEMA, "side": "engine", "rows": rows, "not_compared": not_compared}


def write_result_file(sheets: tuple[ResultSheet, ...]) -> bytes:
    """결과 파일 `<base>_result.xlsx` 의 바이트(코랩 `ExcelWriter(…, engine="openpyxl")` + `to_excel(index=False)`)."""
    out = io.BytesIO()
    with legacy_strings(), pd.ExcelWriter(out, engine="openpyxl") as writer:
        for sheet in sheets:
            frame = pd.DataFrame(list(sheet.rows), columns=list(sheet.columns), dtype=object)
            cast(Any, frame).to_excel(writer, sheet_name=sheet.name, index=False)
    return out.getvalue()


def write_filled_template(template_bytes: bytes, writes: tuple[CellWrite, ...]) -> bytes:
    """채운 템플릿 `<base>_filled_template.xlsx` 의 바이트: 원래 템플릿을 열어(`:9367`) 칸에 넣고 저장(`:9469`)."""
    book = openpyxl.load_workbook(io.BytesIO(template_bytes))
    for write in writes:
        book[write.sheet].cell(row=write.row, column=write.column, value=write.value)
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()


def run_dump(
    template: Path, factor_book: Path, answers: Path, report_year: int, geocoder: RecordingGeocoder | None = None
) -> tuple[dict[str, Any], ColabRun]:
    """엔진 쪽 줄과 실행 결과(출력 파일 내용은 `result.outputs`)."""
    provider = OrderedAnswers(load_answers(answers))
    geocoder = geocoder if geocoder is not None else RecordingGeocoder()
    template_book = read_book(template)
    result = run(template_book, read_book(factor_book), report_year, mock_client(provider), geocoder, TAGS, ROUTE)
    if isinstance(result, ColabRejected):
        raise DumpFailed(f"실행 거절 {result.reason}: {result.detail}")
    if provider.problems:
        raise DumpFailed("; ".join(provider.problems))
    if provider.used != len(provider.answers):
        raise DumpFailed(f"짜 둔 답 {len(provider.answers)} 가운데 {provider.used} 만 쓰였다(부름 차례가 바뀌었다)")
    return rows_of(result.sheets, template_book), result


def dump(
    template: Path, factor_book: Path, answers: Path, report_year: int, geocoder: RecordingGeocoder | None = None
) -> dict[str, Any]:
    """엔진 쪽 줄. 지오코더 물음은 넘긴 `geocoder` 에 남는다(없으면 버린다)."""
    return run_dump(template, factor_book, answers, report_year, geocoder)[0]


def output_files(result: ColabRun) -> OutputFiles:
    if not isinstance(result.outputs, OutputFiles):
        raise DumpFailed(f"출력 파일 내용이 없다: {result.outputs!r}")
    return result.outputs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="scope3colab_dump", description="코랩 대조용 엔진 결과(scope3colab.rows/1)")
    parser.add_argument("--template", type=Path, required=True)
    parser.add_argument("--factor-book", type=Path, required=True)
    parser.add_argument("--answers", type=Path, required=True)
    parser.add_argument("--report-year", type=int, default=2025)
    parser.add_argument("--geocode-queries", type=Path, help="지오코더 물음 목록(JSON 배열)을 쓸 곳")
    parser.add_argument("--result-file", type=Path, help="엔진의 결과 파일 `<base>_result.xlsx` 를 쓸 곳")
    parser.add_argument("--filled-file", type=Path, help="엔진의 `<base>_filled_template.xlsx` 를 쓸 곳")
    args = parser.parse_args(argv)
    geocoder = RecordingGeocoder()
    files: list[tuple[Path, bytes]] = []
    try:
        data, result = run_dump(args.template, args.factor_book, args.answers, args.report_year, geocoder)
        if args.result_file is not None:
            files.append((args.result_file, write_result_file(output_files(result).result)))
        if args.filled_file is not None:
            writes = output_files(result).writes
            files.append((args.filled_file, write_filled_template(args.template.read_bytes(), writes)))
    except (OSError, ValueError, KeyError, TypeError, DumpFailed) as error:
        print(f"도구 실패: {error!r}", file=sys.stderr)
        return TOOL_FAILED
    for path, body in files:
        path.write_bytes(body)
    if args.geocode_queries is not None:
        args.geocode_queries.write_text(json.dumps(geocoder.queries, ensure_ascii=False) + "\n", encoding="utf-8")
    sys.stdout.write(json.dumps(data, ensure_ascii=False, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
