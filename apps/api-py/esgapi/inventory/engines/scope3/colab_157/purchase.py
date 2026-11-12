"""C1(구매품·서비스)·C2(자본재)의 셈 — 코랩 셀 22·23·26·27 의 마지막 판(늦은 묶임 포함).

길(코랩 `process_new_template` `:5898` 의 Category1·2 갈래와 후처리 `:8916`):
    시트 읽기(template.py) → `standardize_c1_sheet`(`:4918`)·`standardize_c2_sheet`(`:5015`) → 월 합(`:5947`)
    → 줄마다 `calc_category1_2_detail`(`:8464`) → 결과 파일을 다시 읽어 `_fix_result_c1_c2`(`:8799`)
`calc_category1_2_detail` 안:
    `normalize_purchase_spend_for_usepa`(`:7994` — `:4099` 판이 아니다) → `normalize_purchase_unit`(`:4043`)
    `classify_purchase_group`(`:4618`): 사용자 그룹 → 규칙 `PURCHASE_GROUP_RULES` → LLM `_infer_group_name_llm`(`:4592`)
    `_fix_rank_spend_candidates`(`:8341`): 수작업 규칙 → 구매_USEPA 한국어 키워드 점수 → 옛 추천(`:3161` 판 —
    `_ORIGINAL_get_spend_recommendations_FULL_FIX` 가 붙잡은 것) → 끝 대안(제목 둘)
옛 추천 `:3161` 안의 `translate_product_for_search_info`(`:2743`)가 C1·C2 길의 두 번째 LLM 이다(NAICS 고르기).

코랩과 다르게 짠 자리(밴드 보고 「코랩과 다른 자리」 표):
- 전역 `spend_db`·`SPEND_DB_NAMES`·`SPEND_DB_NAME_SET`·`CURATED_SPEND_CANDIDATES`·`FX_REFERENCE_YEAR` → `PurchaseBook`.
- `lru_cache`(`translate_product_for_search_info`) → 실행 하나의 `PurchaseRun.translations`. 코랩처럼 성공만
  기억한다(예외는 lru_cache 가 기억하지 않는다). `_infer_group_name_llm` 은 코랩도 기억하지 않는다 — 줄마다 부른다.
- `translate_product_for_search_info` 는 C1·C2 길이 쓰는 `generic_english` 만 짓는다(`selected_titles`·
  `candidate_pool`·`confidence` 는 옛 추천 `:3161` 이 읽지 않는다).
- 결과 파일 왕복(`to_excel` → `read_excel`) 없이 frame 에서 후처리한다. 왕복이 지우는 「전부 빈 열」은 흉내 낸다.
- 행마다 산정 출처(`origin`·`originSteps` — 처분 ⑧)와 그룹 LLM 의 갈래를 남긴다(코랩에는 없다 — 값은 바꾸지 않는다).
  키워드 점수 후보가 키워드 몫 0 · LLM 그룹 이름 몫만으로 섰으면 `ai`(`rank_spend_candidates` — 점수 합은 코랩 그대로).
"""

import contextlib
import math
import numbers
import re
from dataclasses import dataclass, field
from typing import Any, Final, Literal, cast

import pandas as pd
from rapidfuzz import fuzz, process

from esgapi.inventory.engines.scope3.colab_157.constants import (
    BOK_USD_KRW_MONTHLY_AVG_2025,
    BROAD_DEFAULT_TITLES,
    CURATED_SPEND_CANDIDATES,
    CURRENCY_ALIAS,
    ERP_TO_NAICS_HINTS,
    GENERIC_NOISE_WORDS,
    MANUAL_PURCHASE_TITLE_RULES,
    NOISE_PATTERNS,
    PURCHASE_GROUP_RULES,
    SPEND_FAMILY_TITLES,
    NaicsHint,
)
from esgapi.inventory.engines.scope3.colab_157.factor_book import SpendDb
from esgapi.inventory.engines.scope3.colab_157.llm import (
    LlmContext,
    LlmFailed,
    LlmOutcome,
    call_text,
    reraises,
    safe_json_loads,
)
from esgapi.inventory.engines.scope3.colab_157.pdcompat import colab_str
from esgapi.inventory.engines.scope3.colab_157.template import (
    MONTH_NAME_TO_NUM,
    PURCHASE_WIDE_MONTH_COLS,
    TEMPLATE_ROW,
    normalize_template_columns,
    read_template_rows,
    sum_monthly_spend,
)
from esgapi.inventory.tools.scope3_sheets.grid import Sheet

ColabOrigin = Literal["rule", "ai", "estimate"]
ColabStep = Literal["group", "factor", "spend"]
ColabMissing = Literal["amount", "factor", "factorValue"]

GROUP_PROMPT: Final = "inventory/scope3-colab-group-name@1"
NAICS_PROMPT: Final = "inventory/scope3-colab-naics-pick@1"
FX_REFERENCE_YEAR: Final = 2025  # 코랩 :3457 — 함수 기본 인자로 묶인 값(get_bok_usd_krw_annual_avg 의 year)


# ── 값 하나 다루기(코랩 셀 7·22·27) ──


def _is_na(x: object) -> bool:
    """코랩의 `if pd.isna(x):` 자리(값 하나): None·NaN(numpy 실수 포함)·NaT·NA. 배열은 코랩도 그 자리에서 ValueError 를
    받아 넘기므로 아니다(False). frame 의 칸 값은 글·수·None·NaN 뿐이다(frames.py)."""
    if x is None or x is pd.NA or x is pd.NaT:
        return True
    if isinstance(x, numbers.Real) and not isinstance(x, numbers.Integral):
        return math.isnan(float(x))
    return False


def fix_text(x: object) -> str:
    """코랩 `_fix_text`(`:8149`) — `_safe_text`(`:2906`)와 글자까지 같다."""
    if x is None:
        return ""
    if _is_na(x):
        return ""
    return str(x).strip()


def to_float(x: object) -> float | None:
    """코랩 `to_float`(`:1098`). 코랩의 맨 `except:` 는 Exception 으로 받는다(KeyboardInterrupt 는 올려 보냄)."""
    if x is None:
        return None
    try:
        s = str(x).replace(",", "").strip()
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def fix_num(x: object) -> float | None:
    """코랩 `_fix_num`(`:8160`)."""
    if _is_na(x):
        return None
    f = to_float(x)
    if f is not None:
        return f
    try:
        s = fix_text(x).replace(",", "")
        if not s:
            return None
        return float(s)
    except Exception:
        return None


def fix_norm(x: object) -> str:
    """코랩 `_fix_norm`(`:8181`)."""
    return re.sub(r"[^0-9a-zA-Z가-힣]+", "", fix_text(x).lower())


def norm_title_key(x: object) -> str:
    """코랩 `_norm_title_key`(`:3036`)."""
    return fix_text(x).strip().lower()


def coerce_month_value(value: object) -> int | None:
    """코랩 `_coerce_month_value`(`:3547` — `:4514` 의 것은 `not in dir()` 로 걸러져 쓰이지 않는다)."""
    if _is_na(value):
        return None
    if isinstance(value, (int, float)):
        mm = int(value)
        return mm if 1 <= mm <= 12 else None
    s = str(value).strip()
    if not s:
        return None
    if s in MONTH_NAME_TO_NUM:
        return MONTH_NAME_TO_NUM[s]
    m = re.search(r"([1-9]|1[0-2])\s*월", s)
    if m:
        return int(m.group(1))
    m = re.search(r"^\s*([1-9]|1[0-2])\s*$", s)
    if m:
        return int(m.group(1))
    if "구매일자" in s or "date" in s.lower():
        return None
    m = re.search(r"20\d{2}[./-](\d{1,2})[./-]\d{1,2}", s)
    if m:
        mm = int(m.group(1))
        return mm if 1 <= mm <= 12 else None
    return None


def normalize_currency_unit(value: object) -> str:
    """코랩 `_normalize_currency_unit`(`:3538`)."""
    s = fix_text(value).strip().upper()
    mapping = {
        "원": "KRW", "KRW": "KRW", "WON": "KRW", "₩": "KRW",
        "USD": "USD", "US$": "USD", "$": "USD", "달러": "USD", "미국달러": "USD",
        "U$": "USD", "USDOLLAR": "USD", "US DOLLAR": "USD",
    }  # fmt: skip
    return mapping.get(s, s)


def normalize_unit(unit_raw: object) -> str:
    """코랩 `normalize_unit`(`:3992`)."""
    return str(unit_raw).strip().lower().replace(" ", "").replace("-", "").replace("_", "")


def get_purchase_month(row: "pd.Series[Any]") -> int | None:
    """코랩 `_get_purchase_month`(`:3616`)."""
    for key in ["구매 월", "구매월", "발생월"]:
        mm = coerce_month_value(row.get(key))
        if mm is not None:
            return mm
    date_val = row.get("구매일자")
    if not _is_na(date_val):
        m = re.search(r"20\d{2}[./-](\d{1,2})[./-]\d{1,2}", str(date_val))
        if m:
            mm = int(m.group(1))
            if 1 <= mm <= 12:
                return mm
    return None


def get_bok_usd_krw_annual_avg(year: int = FX_REFERENCE_YEAR) -> float:
    """코랩 `get_bok_usd_krw_annual_avg`(`:3655`) → `get_bok_usd_krw_monthly_avg(None, year)`(`:3632`)의 연평균 갈래."""
    fx_map = {FX_REFERENCE_YEAR: BOK_USD_KRW_MONTHLY_AVG_2025}.get(int(year), {})
    if fx_map:
        return round(sum(fx_map.values()) / len(fx_map), 2)
    return 1400.0


# ── 금액 단위(코랩 :4043 · :7994) ──


@dataclass(frozen=True)
class SpendMeta:
    """`normalize_purchase_spend_for_usepa`(`:7994`)가 낸 것 가운데 C1·C2 가 읽는 셋."""

    input_currency: str  # 적용단위
    unit_note: str  # 단위환산비고
    amount_krw: float | None  # EF적용금액(KRW)


def normalize_purchase_unit(row: "pd.Series[Any]") -> SpendMeta:
    """코랩 `normalize_purchase_unit`(`:4043`). 외화 근사 환율(EUR 1.09 등)은 코랩 셀의 글자 그대로다."""
    amount = to_float(row.get("구매금액"))
    unit_raw = str(row.get("단위") or row.get("통화") or "").strip()
    u = normalize_unit(unit_raw)
    std_currency = CURRENCY_ALIAS.get(u, u.upper() if u else "KRW")
    if amount is None:
        return SpendMeta(std_currency, "금액 없음", None)
    if std_currency == "KRW":
        return SpendMeta(std_currency, "KRW 그대로", amount)
    if std_currency == "USD":
        fx = get_bok_usd_krw_annual_avg()
        return SpendMeta(std_currency, f"USD → KRW ({fx:,.0f} 환율 적용)", amount * fx)
    if std_currency == "EUR":
        eur_usd = 1.09
        fx = get_bok_usd_krw_annual_avg()
        return SpendMeta(std_currency, f"EUR → USD ({eur_usd}) → KRW ({fx:,.0f})", amount * eur_usd * fx)
    if std_currency == "JPY":
        jpy_krw = 8.90
        return SpendMeta(std_currency, f"JPY → KRW ({jpy_krw}/100 적용)", amount * jpy_krw)
    if std_currency == "CNY":
        cny_krw = 200.0
        return SpendMeta(std_currency, f"CNY → KRW ({cny_krw} 적용)", amount * cny_krw)
    if std_currency == "VND":
        vnd_krw = 0.057
        return SpendMeta(std_currency, f"VND → KRW ({vnd_krw} 적용)", amount * vnd_krw)
    return SpendMeta("KRW(추정)", f"미지원 통화({unit_raw}) → KRW 간주", amount)


# ── 실행 하나의 상태(코랩 전역의 자리) ──


@dataclass(frozen=True)
class PurchaseBook:
    """코랩 전역 `spend_db`·`SPEND_DB_NAMES`·`SPEND_DB_NAME_SET`·`CURATED_SPEND_CANDIDATES`·`FX_REFERENCE_YEAR`."""

    db: pd.DataFrame
    names: tuple[str, ...]
    curated: tuple[str, ...]
    year: int

    @property
    def name_set(self) -> frozenset[str]:
        return frozenset(self.names)


def purchase_book(used: SpendDb, initial: SpendDb, report_year: int) -> PurchaseBook:
    """큐레이션 후보는 두 번 걸러진다: 셀 9 의 이름 집합(`:2384`)과 보고연도로 다시 지은 이름 집합(`:7954`).

    다시 짓기가 실패하면(`used is initial`) 두 번째 거르기는 없다.
    """
    curated = [x for x in CURATED_SPEND_CANDIDATES if x in set(initial.names)]
    if used is not initial:
        curated = [x for x in curated if x in set(used.names)]
    return PurchaseBook(used.frame, used.names, tuple(curated), report_year)


@dataclass(frozen=True)
class TranslateInfo:
    """`translate_product_for_search_info`(`:2743`)의 `generic_english` 와 그 출처(LLM 의 답인가, 규칙의 것인가)."""

    generic_english: str
    from_llm: bool


class TranslateFailed(Exception):
    """코랩에서 `translate_product_for_search_info` 가 예외를 낼 자리(LLM 실패·JSON 못 읽음·dict 아님)."""


@dataclass
class PurchaseRun:
    book: PurchaseBook
    llm: LlmContext
    translations: dict[str, TranslateInfo | None] = field(default_factory=dict[str, TranslateInfo | None])


# ── 그룹(코랩 :4552-4703) ──


def normalize_purchase_classification(value: object) -> str | None:
    """코랩 `_normalize_purchase_classification`(`:3580` — `:4530` 의 것은 `not in dir()` 로 걸러진다)."""
    s = fix_text(value).strip().lower()
    if not s:
        return None
    cat1_keys = ["category1", "cat1", "카테고리1", "구매", "상품", "원재료", "소모품", "일반구매", "구입"]
    cat2_keys = ["category2", "cat2", "카테고리2", "자산", "자본재", "설비", "비품", "장비"]
    if any(k in s for k in cat2_keys):
        return "Category2"
    if any(k in s for k in cat1_keys):
        return "Category1"
    return None


def purchase_text(row: "pd.Series[Any]") -> str:
    """코랩 `_purchase_text`(`:4552`). NaN 은 참이라 `str(nan)` = 'nan' 이 글에 들어간다(코랩 그대로)."""
    parts = [
        str(row.get("상세 품목명/서비스명", "") or ""),
        str(row.get("상세 자산명", "") or ""),
        str(row.get("품목명", "") or ""),
        str(row.get("자산명", "") or ""),
        str(row.get("품목/자산명", "") or ""),
        str(row.get("설명/적요", "") or ""),
        str(row.get("거래처명(선택)", "") or ""),
        str(row.get("거래처명", "") or ""),
    ]
    return " ".join(parts).lower()


_FAMILY_FROM_USER_GROUP: Final[list[tuple[list[str], str]]] = [
    (["원재료", "원자재", "부자재", "철강", "알루미늄", "수지", "화학"], "raw_material"),
    (["포장재", "포장지", "박스", "골판지", "비닐"], "packaging"),
    (["a4", "복사지", "용지", "복사용지"], "paper"),
    (["토너", "잉크", "카트리지", "드럼"], "printer_supplies"),
    (["사무용품", "문구", "소모품"], "office_supplies"),
    (["커피", "원두", "차", "음료", "생수", "물", "탕비", "다과"], "pantry_supplies"),
    (["의자", "책상", "파티션", "캐비닛", "옷장", "가구", "비품"], "office_furniture"),
    (["노트북", "데스크탑", "컴퓨터", "모니터", "서버", "pc", "it"], "computer_equipment"),
    (["프린터", "복합기", "스캐너"], "printer_device"),
    (["소프트웨어", "라이선스", "software"], "software_it"),
    (["외주", "용역", "서비스", "컨설팅", "청소", "경비"], "service_outsourcing"),
    (["생산설비", "기계장치", "설비"], "manufacturing_equipment"),
    (["차량", "트럭", "승용차"], "vehicle"),
    (["건물", "구축물", "창고"], "building"),
]


def infer_family_from_user_group(group_text: str) -> str:
    """코랩 `_infer_family_from_user_group`(`:4567`)."""
    t = str(group_text).strip().lower()
    for keywords, family in _FAMILY_FROM_USER_GROUP:
        if any(k in t for k in keywords):
            return family
    return "misc_purchase"


@dataclass(frozen=True)
class GroupLlm:
    """그룹 이름 LLM 한 번의 갈래. `answer` 는 코랩이 쓴 글자다(실패면 코랩의 `"Unknown"`)."""

    outcome: Literal["success", "truncated", "refusal", "failed"]
    answer: str
    reason: str | None  # failed 면 core.llm 결과의 kind


@dataclass(frozen=True)
class PurchaseGroup:
    """`classify_purchase_group` 의 dict(group_key·품목/자산명·그룹판단근거·추천Family·자동카테고리)와 산정 출처."""

    key: str
    name: str
    reason: str
    family: str
    category: str
    origin: ColabOrigin
    via: str
    llm: GroupLlm | None


def infer_group_name_llm(run: PurchaseRun, product_text: str) -> tuple[str, LlmOutcome]:
    """코랩 `_infer_group_name_llm`(`:4592`): max_tokens 20, system 없음. 실패는 `"Unknown"`."""
    outcome = call_text(run.llm, GROUP_PROMPT, {"product_text": product_text}, 20)
    if isinstance(outcome, LlmFailed):
        return "Unknown", outcome  # 코랩 `except Exception: return "Unknown"`
    return outcome.text.strip(), outcome


def _group_llm(answer: str, outcome: LlmOutcome) -> GroupLlm:
    if isinstance(outcome, LlmFailed):
        return GroupLlm("failed", answer, outcome.reason)
    return GroupLlm(outcome.via, answer, None)


def classify_purchase_group(run: PurchaseRun, row: "pd.Series[Any]") -> PurchaseGroup:
    """코랩 `classify_purchase_group`(`:4618`): 사용자 그룹 → 키워드 규칙 → LLM → 기타."""
    user_group = fix_text(row.get("품목군")) or fix_text(row.get("자산분류")) or fix_text(row.get("분류"))
    manual_category = normalize_purchase_classification(row.get("자동카테고리") or row.get("분류"))

    if user_group:
        category = manual_category if manual_category else "Category1"
        family = infer_family_from_user_group(user_group)
        key = f"user_{user_group[:20].replace(' ', '_')}"
        return PurchaseGroup(key, user_group, f"사용자입력: {user_group}", family, category, "rule", "group_user", None)

    text = purchase_text(row)
    for rule in PURCHASE_GROUP_RULES:
        matched = [kw for kw in rule["keywords"] if kw.lower() in text]
        if matched:
            category = manual_category if manual_category else rule["category"]
            reason = "키워드매칭: " + ", ".join(matched[:3])
            return PurchaseGroup(
                rule["group_key"], rule["group_ko"], reason, rule["family"], category, "rule", "group_rule", None
            )

    product_text = (
        fix_text(row.get("상세 품목명/서비스명"))
        or fix_text(row.get("상세 자산명"))
        or fix_text(row.get("품목/자산명"))
        or fix_text(row.get("품목명"))
        or fix_text(row.get("자산명"))
    )
    llm: GroupLlm | None = None
    if product_text:
        llm_group, outcome = infer_group_name_llm(run, product_text)
        llm = _group_llm(llm_group, outcome)
        if llm_group and llm_group != "Unknown":
            category = manual_category if manual_category else "Category1"
            family = infer_family_from_user_group(llm_group)
            key = f"llm_{llm_group[:20].replace(' ', '_')}"
            reason = f"AI그룹핑: {product_text[:30]}"
            return PurchaseGroup(key, llm_group, reason, family, category, "ai", "group_llm", llm)

    category = manual_category if manual_category else "Category1"
    fallback_name = product_text or "기타구매"
    return PurchaseGroup(
        "misc_purchase", fallback_name, "rule_unmatched", "misc_purchase", category, "estimate", "group_fallback", llm
    )


# ── NAICS 고르기 LLM(코랩 :2629-2805) — 옛 추천 `:3161` 이 부른다 ──


def clean_product_text(product: object) -> str:
    """코랩 `clean_product_text`(`:2629`)."""
    if _is_na(product):
        return ""
    s = str(product).strip()
    if not s:
        return ""
    for p in NOISE_PATTERNS:
        s = re.sub(p, " ", s, flags=re.IGNORECASE)
    for w in GENERIC_NOISE_WORDS:
        s = s.replace(w, " ")
    return re.sub(r"\s+", " ", s).strip()


def detect_hint_rules(product: object) -> list[NaicsHint]:
    """코랩 `detect_hint_rules`(`:2646`)."""
    text = str(product or "")
    return [
        rule for rule in ERP_TO_NAICS_HINTS if any(re.search(p, text, flags=re.IGNORECASE) for p in rule["patterns"])
    ]


def build_allowed_titles(book: PurchaseBook, product: object) -> list[str]:
    """코랩 `build_allowed_titles`(`:2654`)."""
    matched = detect_hint_rules(product)
    titles: list[str] = []
    if matched:
        for rule in matched:
            titles.extend(rule["titles"])
    else:
        titles.extend(book.curated)
    name_set = book.name_set
    titles.extend([x for x in BROAD_DEFAULT_TITLES if x in name_set])
    deduped: list[str] = []
    seen: set[str] = set()
    for t in titles:
        if t in name_set and t not in seen:
            deduped.append(t)
            seen.add(t)
    return deduped[:12]


def allowed_text(allowed_titles: list[str]) -> str:
    """코랩 `build_prompt_for_curated_naics`(`:2702`)의 `allowed_text`."""
    return "\n".join([f"- {x}" for x in allowed_titles]) if allowed_titles else "- (no candidates)"


def translate_product_for_search_info(run: PurchaseRun, product: object) -> TranslateInfo | None:
    """코랩 `translate_product_for_search_info`(`:2743`) 의 `generic_english` 길. 실패는 `TranslateFailed`."""
    if _is_na(product):
        return None
    product = str(product).strip()
    if not product:
        return None
    if product in run.translations:
        return run.translations[product]

    cleaned_product = clean_product_text(product)
    allowed_titles = build_allowed_titles(run.book, product)
    matched = detect_hint_rules(product)
    rule_generic_en = matched[0]["generic_en"] if matched else None  # guess_generic_from_rules(:2683) 의 첫 규칙

    variables = {"product": product, "cleaned_product": cleaned_product, "allowed_text": allowed_text(allowed_titles)}
    outcome = call_text(run.llm, NAICS_PROMPT, variables, 1024)
    if isinstance(outcome, LlmFailed):
        raise TranslateFailed(outcome.reason)
    try:
        parsed = safe_json_loads(outcome.text)
    except ValueError as error:  # json.JSONDecodeError
        raise TranslateFailed("json") from error
    if not isinstance(parsed, dict):
        raise TranslateFailed("not_a_dict")  # 코랩 `parsed.get(...)` 의 AttributeError
    answer = cast("dict[str, object]", parsed)  # core/llm/providers/gemini.py 꼴(JSON 객체의 칸)
    generic_english = str(answer.get("generic_english", "")).strip()
    from_llm = bool(generic_english)
    if rule_generic_en is not None and not generic_english:
        generic_english = rule_generic_en
    info = TranslateInfo(generic_english, from_llm)
    run.translations[product] = info
    return info


# ── 옛 추천(코랩 :3040-3200, `:3161` 판) ──


@dataclass(frozen=True)
class LegacyRec:
    title: str
    ef: float | None
    origin: ColabOrigin  # 계열 제목 = rule, LLM 의 generic_english 로 fuzzy = ai(규칙의 generic_english 면 rule)


def _names_stripped(db: pd.DataFrame) -> "pd.Series[str]":
    return colab_str(db["name"]).str.strip()


def existing_spend_titles(book: PurchaseBook, titles: list[str]) -> list[LegacyRec]:
    """코랩 `_existing_spend_titles`(`:3062`)."""
    out: list[LegacyRec] = []
    db = book.db
    db_names = colab_str(db["name"].dropna()).str.strip()
    for t in titles:
        match = db[db_names == str(t).strip()]
        if len(match) > 0:
            out.append(LegacyRec(t, to_float(match.iloc[0]["ef"]), "rule"))
    return out


def detect_spend_family(product: object = "", desc: object = "", vendor: object = "") -> str:
    """코랩 `detect_spend_family`(`:3072`)."""
    text = " ".join([fix_text(product), fix_text(desc), fix_text(vendor)]).lower()
    if any(k in text for k in ["폐기물", "오니", "waste", "sludge", "처리비", "처리"]):
        return "waste"
    if any(k in text for k in ["토너", "ink", "잉크", "cartridge", "카트리지", "드럼", "printer", "프린터"]):
        return "printer_supplies"
    if any(k in text for k in ["a4", "복사지", "복사용지", "copy paper", "용지", "paper"]):
        return "paper"
    furniture = ["의자", "chair", "책상", "desk", "파티션", "partition", "캐비닛", "cabinet", "옷장", "locker", "비품"]
    if any(k in text for k in furniture):
        return "office_furniture"
    if any(k in text for k in ["모니터", "monitor", "display"]):
        return "monitor"
    if any(k in text for k in ["노트북", "laptop", "데스크탑", "desktop", "pc computer", "computer", "pc"]):
        return "computer"
    if any(k in text for k in ["커피", "원두", "coffee", "tea", "캡슐"]):
        return "coffee"
    if any(k in text for k in ["생수", "식수", "정수기", "water", "식수대"]):
        return "water"
    if any(k in text for k in ["주방음료", "탕비", "간식", "음료", "beverage", "snack"]):
        return "beverage"
    if any(k in text for k in ["종이컵", "휴지", "티슈", "paper cup", "tissue"]):
        return "sanitary_paper"
    return "office_supplies"


def unique_recommendations(recs: list[LegacyRec], limit: int = 4) -> list[LegacyRec]:
    """코랩 `_unique_recommendations`(`:3040`, exclude_title=None)."""
    out: list[LegacyRec] = []
    seen: set[str] = set()
    for rec in recs:
        title = fix_text(rec.title)
        if not title:
            continue
        key = norm_title_key(title)
        if key in seen:
            continue
        seen.add(key)
        out.append(LegacyRec(title, to_float(rec.ef), rec.origin))
        if len(out) >= limit:
            break
    return out


def get_spend_recommendations_3161(run: PurchaseRun, product: str, top_k: int) -> list[LegacyRec]:
    """코랩 `get_spend_recommendations`(`:3161` 판, desc·vendor = "")."""
    family = detect_spend_family(product, "", "")
    family_titles = SPEND_FAMILY_TITLES.get(family, SPEND_FAMILY_TITLES["office_supplies"])
    recs = existing_spend_titles(run.book, family_titles)

    if len(recs) < top_k:
        base_query = fix_text(product)
        generic_english = ""
        from_llm = False
        try:
            info = translate_product_for_search_info(run, base_query)
            if info:
                generic_english = fix_text(info.generic_english)
                from_llm = info.from_llm
        except Exception as error:  # 코랩 `except Exception: generic_english = ""` — TranslateFailed 가 여기로 온다
            if reraises(run.llm, error):
                raise
            generic_english = ""

        if generic_english:
            with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
                db = run.book.db
                choices = [str(c) for c in colab_str(db["name"].dropna()).unique().tolist()]
                fuzzy_hits = process.extract(generic_english, choices, scorer=fuzz.WRatio, limit=10)
                for title, score, _ in fuzzy_hits:
                    if score >= 78 and title not in [r.title for r in recs]:
                        match = db[_names_stripped(db) == str(title).strip()]
                        if len(match) > 0:
                            origin: ColabOrigin = "ai" if from_llm else "rule"
                            recs.append(LegacyRec(title, to_float(match.iloc[0]["ef"]), origin))
                    if len(recs) >= top_k:
                        break

    return unique_recommendations(recs, limit=top_k)[:top_k]


# ── 후보 순위(코랩 :8341, 마지막 판) ──


@dataclass(frozen=True)
class Candidate:
    """후보 하나(코랩 dict 의 title·ef·source·score)와 산정 출처."""

    title: str
    ef: float | None
    source: str  # 코랩의 source 글자: manual_keyword · db_keyword · legacy_fallback · manual_title
    score: int
    origin: ColabOrigin


def fix_spend_row_by_title(book: PurchaseBook, title: str) -> Candidate | None:
    """코랩 `_fix_spend_row_by_title`(`:8308`)."""
    db = book.db
    if db.empty or "name" not in db.columns:
        return None
    subset = db[_names_stripped(db) == fix_text(title)]
    if subset.empty:
        return None
    r = subset.iloc[0]
    return Candidate(fix_text(r.get("name")), fix_num(r.get("ef")), "manual_title", 999, "estimate")


def fix_split_keywords(s: object) -> list[str]:
    """코랩 `_fix_split_keywords`(`:8325`)."""
    raw = fix_text(s)
    if not raw:
        return []
    return [x.strip() for x in re.split(r"[,;/|]+", raw) if x.strip()]


_QUERY_FIELDS: Final = [
    "상세 품목명/서비스명", "상세 자산명", "품목명", "자산명", "품목/자산명",
    "분류", "품목군", "자산분류", "계정과목", "계정과목(선택)", "거래처명", "거래처명(선택)", "설명/적요", "비고",
]  # fmt: skip


def fix_purchase_query_from_row(row: "pd.Series[Any]") -> str:
    """코랩 `_fix_purchase_query_from_row`(`:8332`)."""
    return " ".join(fix_text(row.get(c)) for c in _QUERY_FIELDS if fix_text(row.get(c)))


GROUP_ALIAS: Final[dict[str, str]] = {
    "전문서비스": "외주서비스", "서비스": "외주서비스", "원재료": "원재료부자재",
    "플라스틱": "원재료부자재", "기계장치": "생산설비", "차량": "차량운송장비",
    "건물구축물": "건설자재", "it장비": "it장비", "종이인쇄물": "사무용품포장재",
}  # fmt: skip  # 코랩 :8386-8390(함수 안의 group_alias)
FALLBACK_TITLES: Final = [
    "Other Miscellaneous Durable Goods Merchant Wholesalers",
    "Office Supplies and Stationery Stores",
]


def rank_spend_candidates(
    run: PurchaseRun,
    query_text: str,
    group_hint: str = "",
    top_n: int = 5,
    group_hint_origin: ColabOrigin = "rule",
) -> list[Candidate]:
    """코랩 `_fix_rank_spend_candidates`(`:8341`) 네 단계.

    2단계 점수는 키워드 몫(`한국어매핑키워드`)과 그룹 몫(`group_hint`)을 따로 센다 — 합(정렬·`score`)은 코랩 그대로.
    키워드 몫이 0 이고 그룹 몫만으로 선 후보는 `group_hint_origin` 이 `"ai"`(LLM 그룹 이름)면 산정 출처도 `"ai"`.
    """
    db = run.book.db
    if db.empty or "name" not in db.columns:
        return []
    text_norm = fix_norm(fix_text(query_text))
    group_norm = fix_norm(group_hint)
    picked: list[Candidate] = []
    seen: set[str] = set()

    # 1) 수작업 규칙
    for keys, titles in MANUAL_PURCHASE_TITLE_RULES:
        if any(fix_norm(k) and fix_norm(k) in text_norm for k in keys):
            for title in titles:
                rec = fix_spend_row_by_title(run.book, title)
                if rec and rec.title not in seen:
                    picked.append(Candidate(rec.title, rec.ef, "manual_keyword", rec.score, "rule"))
                    seen.add(rec.title)

    # 2) 구매_USEPA 의 한국어 매핑 키워드·품목군·상세카테고리 점수
    rows: list[Candidate] = []
    for _, r in db.iterrows():
        title = fix_text(r.get("name"))
        if not title or title in seen:
            continue
        keyword_score = 0
        group_score = 0
        cat = fix_text(r.get("품목군"))
        sub = fix_text(r.get("상세카테고리"))
        for kw in fix_split_keywords(r.get("한국어매핑키워드")):
            kn = fix_norm(kw)
            if not kn:
                continue
            if kn in text_norm:
                keyword_score += 80 + min(len(kn), 20)
            elif len(kn) >= 3 and any(part and part in text_norm for part in re.split(r"[·\-_/ ]+", kw)):
                keyword_score += 15
        if group_norm:
            if group_norm and group_norm in fix_norm(cat + sub):
                group_score += 35
            aliased = GROUP_ALIAS.get(group_norm)
            if aliased and aliased in fix_norm(cat + sub):
                group_score += 30
        score = keyword_score + group_score
        if score > 0:
            origin: ColabOrigin = "ai" if keyword_score == 0 and group_hint_origin == "ai" else "rule"
            rows.append(Candidate(title, fix_num(r.get("ef")), "db_keyword", score, origin))
    rows = sorted(rows, key=lambda x: x.score, reverse=True)
    for rec in rows:
        if rec.title not in seen:
            picked.append(rec)
            seen.add(rec.title)
        if len(picked) >= top_n:
            break

    # 3) 옛 추천(:3161)으로 채운다
    if len(picked) < top_n:
        try:
            old_recs = get_spend_recommendations_3161(run, query_text, top_k=top_n * 2)
        except Exception as error:  # 코랩 `except Exception: old_recs = []`
            if reraises(run.llm, error):
                raise
            old_recs = []
        for old in old_recs:
            title = fix_text(old.title)
            if title and title not in seen:
                picked.append(Candidate(title, fix_num(old.ef), "legacy_fallback", 0, old.origin))
                seen.add(title)
            if len(picked) >= top_n:
                break

    # 4) 아무것도 없을 때만 끝 대안
    if not picked:
        for title in FALLBACK_TITLES:
            rec = fix_spend_row_by_title(run.book, title)
            if rec:
                picked.append(rec)
                break
    return picked[:top_n]


# ── 줄 하나의 셈(코랩 :8464) ──


@dataclass(frozen=True)
class OriginStep:
    step: ColabStep
    origin: ColabOrigin
    via: str


@dataclass(frozen=True)
class RowMeta:
    """코랩 결과 행에는 없는 것: 입력 줄(엑셀 줄 번호), 고른 후보 다섯, 그룹, 금액 단위, 산정 출처."""

    excel_row: int | None
    month: int | None
    spend: SpendMeta
    group: PurchaseGroup
    candidates: tuple[Candidate, ...]

    @property
    def origin(self) -> ColabOrigin | None:
        return self.candidates[0].origin if self.candidates else None

    @property
    def origin_steps(self) -> tuple[OriginStep, ...]:
        factor = OriginStep("factor", self.candidates[0].origin, self.candidates[0].source) if self.candidates else None
        steps = [OriginStep("group", self.group.origin, self.group.via)]
        if factor is not None:
            steps.append(factor)
        steps.append(OriginStep("spend", "rule", self.spend.input_currency))
        return tuple(steps)


def spend_formula_krw_t(spend_krw: float | None, ef: float | None, emission_t: float | None) -> str:
    """코랩 `_fix_spend_formula_krw_t`(`:8457`)."""
    if spend_krw is None or ef is None or emission_t is None:
        return ""
    return f"배출량(tCO2e) = 구매금액(KRW) × EF(kgCO2e/KRW) / 1000 = {spend_krw:g} × {ef:g} / 1000 = {emission_t:g}"


def calc_category1_2_detail(
    run: PurchaseRun, row: "pd.Series[Any]", category: str
) -> tuple[dict[str, object], RowMeta]:
    """코랩 `calc_category1_2_detail`(`:8464`) — 결과(코랩 열 이름, 코랩은 `pd.Series(result)`)와 RowMeta."""
    row = row.copy()
    if "품목/자산명" in row.index:
        if _is_na(row.get("품목명")):
            row["품목명"] = row.get("품목/자산명")
        if _is_na(row.get("자산명")):
            row["자산명"] = row.get("품목/자산명")

    spend_meta = normalize_purchase_unit(row)  # normalize_purchase_spend_for_usepa(:7994) 가 읽는 셋
    spend_krw = fix_num(spend_meta.amount_krw)
    group = classify_purchase_group(run, row)
    user_hint = row.get("품목군") or row.get("자산분류") or row.get("분류")  # 코랩 `or` 사슬 그대로(NaN 은 참)
    group_hint = fix_text(user_hint or group.name)
    hint_origin = group.origin if not user_hint else "rule"  # 그룹 이름에서 왔을 때만 그 출처
    query = fix_purchase_query_from_row(row)

    candidates = rank_spend_candidates(run, query, group_hint=group_hint, top_n=5, group_hint_origin=hint_origin)
    primary = candidates[0] if candidates else None
    alt_candidates = candidates[1:5]
    rep_name = primary.title if primary else None
    rep_ef = fix_num(primary.ef) if primary else None
    emission_kg = (spend_krw * rep_ef) if (spend_krw is not None and rep_ef is not None) else None
    emission_t = (emission_kg / 1000.0) if emission_kg is not None else None
    year = run.book.year
    product_display = fix_text(
        row.get("상세 품목명/서비스명")
        or row.get("상세 자산명")
        or row.get("품목명")
        or row.get("자산명")
        or row.get("품목/자산명")
    )
    month = get_purchase_month(row)
    source = primary.source if primary else "none"  # 코랩 primary.get('source') — 후보가 없으면 {"source": "none"}

    result: dict[str, object] = {
        "구매 월": month,
        "단위환산비고": spend_meta.unit_note or "KRW 그대로",
        "배출계수기준연도": year,
        "배출계수기준컬럼": f"기계산 KRW EF 직접 적용 ({year}년, kgCO2e/KRW)",
        "배출계수단위": "kgCO2e/KRW",
        "EF적용금액(KRW)": spend_krw,
        "group_key": group.key,
        "품목/자산명": group.name or product_display,
        "그룹판단근거": group.reason,
        "추천Family": group.family,
        "자동카테고리": group.category,
        "매개변수": rep_name,
        "EF_DB": rep_name,
        "배출계수": rep_ef,
        "배출량(kgCO2e)": emission_kg,
        "배출량": emission_t,
        "배출량(tCO2e)": emission_t,
        "EF_DB_추천사유": f"템플릿 입력값/한국어 매핑 키워드 기반 후보 랭킹 적용({source}).",
        "계산방식": "Spend",
        "계산식": spend_formula_krw_t(spend_krw, rep_ef, emission_t),
    }
    for i in range(1, 5):
        cand = alt_candidates[i - 1] if i - 1 < len(alt_candidates) else None
        ef_i = fix_num(cand.ef) if cand else None
        result[f"추천EF{i}"] = cand.title if cand else None
        result[f"추천EF{i}_배출계수"] = ef_i
        result[f"추천EF{i}_예상배출량(tCO2e)"] = (
            (spend_krw * ef_i / 1000.0) if (spend_krw is not None and ef_i is not None) else None
        )
    excel_row = row.get(TEMPLATE_ROW)
    row_number = int(excel_row) if isinstance(excel_row, numbers.Integral) else None
    return result, RowMeta(row_number, month, spend_meta, group, tuple(candidates))


# ── 시트 표준화(코랩 셀 23 :4918 · :5015) ──


def standardize_c1_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c1_sheet`(`:4918`) 그대로.

    v1 템플릿은 「연간지출금액(원)」 이 「구매금액」 으로 바뀐 뒤 월별 행을 녹이므로 `melt(value_name="구매금액")` 이
    ValueError 를 내 녹이지 않는다(코랩도 `except: pass`) — 월별 금액은 뒤의 월 합(`:5947`)이 채운다.
    """
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    if "*상세 품목명/서비스명" in df.columns:
        rename["*상세 품목명/서비스명"] = "상세 품목명/서비스명"
    if "*품목군" in df.columns:
        rename["*품목군"] = "품목군"
    if "*국가" in df.columns:
        rename["*국가"] = "국가"
    if "*사업장" in df.columns:
        rename["*사업장"] = "사업장"
    if rename:
        df = df.rename(columns=rename)
        rename = {}

    if "상세 품목명/서비스명" in df.columns and "품목/자산명" not in df.columns:
        rename["상세 품목명/서비스명"] = "품목/자산명"
    if "품목군" in df.columns and "분류" not in df.columns:
        rename["품목군"] = "분류"
    if "연간지출금액(원)" in df.columns and "구매금액" not in df.columns:
        rename["연간지출금액(원)"] = "구매금액"
    if "계정과목(선택)" in df.columns:
        rename["계정과목(선택)"] = "계정과목"
    if "거래처명(선택)" in df.columns:
        rename["거래처명(선택)"] = "거래처명"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)

    month_cols = [str(c) for c in df.columns if str(c).strip() in PURCHASE_WIDE_MONTH_COLS]
    annual_col = next((c for c in ["구매금액", "연간금액", "연간지출금액(원)"] if c in df.columns), None)

    if month_cols and "입력방식" in df.columns:
        df_m = df[df["입력방식"] == "월별"].copy()
        df_a = df[df["입력방식"] != "월별"].copy()
        if not df_m.empty:
            id_cols = [str(c) for c in df_m.columns if c not in month_cols]
            with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
                long_m = df_m.melt(id_vars=id_cols, value_vars=month_cols, var_name="구매 월", value_name="구매금액")
                long_m = long_m.dropna(subset=["구매금액"]).reset_index(drop=True)
                long_m["구매 월"] = long_m["구매 월"].apply(coerce_month_value)
                df_m = long_m
        if not df_a.empty and annual_col and annual_col != "구매금액":
            df_a = df_a.rename(columns={annual_col: "구매금액"})
        df = pd.concat([df_a, df_m], ignore_index=True)
    elif month_cols:
        id_cols = [str(c) for c in df.columns if c not in month_cols and c != annual_col]
        with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
            long_df = df.melt(
                id_vars=id_cols + ([annual_col] if annual_col else []),
                value_vars=month_cols,
                var_name="구매 월",
                value_name="구매금액",
            )
            long_df = long_df.dropna(subset=["구매금액"]).reset_index(drop=True)
            long_df["구매 월"] = long_df["구매 월"].apply(coerce_month_value)
            df = long_df
    elif annual_col and annual_col != "구매금액":
        df = df.rename(columns={annual_col: "구매금액"})

    if "품목/자산명" in df.columns and "품목명" not in df.columns:
        df["품목명"] = df["품목/자산명"]
    return _finish_standardize(df)


def standardize_c2_sheet(df: pd.DataFrame) -> pd.DataFrame:
    """코랩 `standardize_c2_sheet`(`:5015`) 그대로(월별 녹이기도 C1 과 같은 까닭으로 ValueError → 그대로)."""
    df = normalize_template_columns(df)
    rename: dict[str, str] = {}
    for col in ["*상세 자산명", "*자산분류", "*국가", "*사업장"]:
        clean = col.lstrip("*")
        if col in df.columns:
            rename[col] = clean
    if rename:
        df = df.rename(columns=rename)
        rename = {}

    if "상세 자산명" in df.columns and "품목/자산명" not in df.columns:
        rename["상세 자산명"] = "품목/자산명"
    if "자산분류" in df.columns and "분류" not in df.columns:
        rename["자산분류"] = "분류"
    if "연간취득금액(원)" in df.columns and "구매금액" not in df.columns:
        rename["연간취득금액(원)"] = "구매금액"
    if "자산번호(선택)" in df.columns:
        rename["자산번호(선택)"] = "자산번호"
    if "계정과목(선택)" in df.columns:
        rename["계정과목(선택)"] = "계정과목"
    if "거래처명(선택)" in df.columns:
        rename["거래처명(선택)"] = "거래처명"
    if "비고(선택)" in df.columns:
        rename["비고(선택)"] = "비고"
    if rename:
        df = df.rename(columns=rename)

    month_cols = [str(c) for c in df.columns if str(c).strip() in PURCHASE_WIDE_MONTH_COLS]
    if month_cols:
        annual_col = next((c for c in ["구매금액", "연간취득금액(원)"] if c in df.columns), None)
        id_cols = [str(c) for c in df.columns if c not in month_cols and c != annual_col]
        with contextlib.suppress(Exception):  # 코랩 `except Exception: pass`
            long_df = df.melt(
                id_vars=id_cols + ([annual_col] if annual_col else []),
                value_vars=month_cols,
                var_name="구매 월",
                value_name="구매금액",
            )
            long_df = long_df.dropna(subset=["구매금액"]).reset_index(drop=True)
            long_df["구매 월"] = long_df["구매 월"].apply(coerce_month_value)
            df = long_df

    if "품목/자산명" in df.columns and "자산명" not in df.columns:
        df["자산명"] = df["품목/자산명"]
    return _finish_standardize(df)


def _finish_standardize(df: pd.DataFrame) -> pd.DataFrame:
    """두 표준화의 끝(구매 월·단위·통화) — 글자가 같아 하나로 뒀다."""
    if "구매 월" in df.columns:
        df["구매 월"] = df["구매 월"].apply(coerce_month_value)
    if "단위" not in df.columns:
        df["단위"] = "KRW"
    df["단위"] = df["단위"].apply(normalize_currency_unit)
    if "통화" not in df.columns:
        df["통화"] = df["단위"]
    return df


# ── 후처리(코랩 :8799) — 결과 파일 왕복 대신 frame 에서 ──


def fix_result_c1_c2(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """코랩 `_fix_result_c1_c2`(`:8799`). 결과 파일에는 전부 빈 열이 지워져 있다(`:6240`) — 그 열은 없는 것으로 본다."""
    out = df.copy()
    kept = {str(c) for c in out.columns if bool(out[c].notna().any())}
    if "구매금액" in kept and "배출계수" in kept:
        spend = pd.to_numeric(out["구매금액"], errors="coerce")
        ef = pd.to_numeric(out["배출계수"], errors="coerce")
        out["배출량(kgCO2e)"] = spend * ef
        out["배출량(tCO2e)"] = out["배출량(kgCO2e)"] / 1000.0
        out["배출량"] = out["배출량(tCO2e)"]
        out["배출계수기준컬럼"] = f"기계산 KRW EF 직접 적용 ({year}년, kgCO2e/KRW)"
        out["배출계수단위"] = "kgCO2e/KRW"
        out["계산식"] = [
            f"배출량(tCO2e) = 구매금액(KRW) × EF(kgCO2e/KRW) / 1000 = {s:g} × {e:g} / 1000 = {v:g}"
            if pd.notna(s) and pd.notna(e) and pd.notna(v)
            else ""
            for s, e, v in zip(spend, ef, out["배출량(tCO2e)"], strict=True)
        ]
        for i in range(1, 5):
            c = f"추천EF{i}_배출계수"
            if c in kept:
                out[f"추천EF{i}_예상배출량(tCO2e)"] = spend * pd.to_numeric(out[c], errors="coerce") / 1000.0
    return out


# ── 시트 하나 ──


@dataclass(frozen=True)
class PurchaseSheet:
    """C1·C2 시트 하나의 셈: 코랩 결과 frame(후처리 뒤, 코랩 열 이름)과 같은 차례의 RowMeta."""

    frame: pd.DataFrame
    metas: tuple[RowMeta, ...]


@dataclass(frozen=True)
class EmptyPurchaseSheet:
    """`read_template_sheet` 가 빈 frame 을 냈다(코랩 `[empty]` — `:5970`)."""


def process_purchase_sheet(run: PurchaseRun, sheet: Sheet, category: str) -> PurchaseSheet | EmptyPurchaseSheet:
    """코랩 `process_new_template` 의 시트 하나(`:5966-6007` 의 Category1·2 갈래)와 후처리(`:8799`)."""
    df = read_template_rows(sheet)
    if df.empty:
        return EmptyPurchaseSheet()
    df = standardize_c1_sheet(df) if category == "Category1" else standardize_c2_sheet(df)
    df["자동카테고리"] = category
    df["출처시트"] = sheet.name
    df = sum_monthly_spend(df, "구매금액")
    rows_out: list[dict[str, object]] = []
    metas: list[RowMeta] = []
    for _, row in df.iterrows():
        detail, meta = calc_category1_2_detail(run, row, category)
        merged_row: dict[str, object] = {str(k): v for k, v in row.to_dict().items()}
        merged_row.update(detail)  # 코랩 `_theme_merge_row`(:6254)
        rows_out.append(merged_row)
        metas.append(meta)
    merged = pd.DataFrame(rows_out)
    return PurchaseSheet(fix_result_c1_c2(merged, run.book.year), tuple(metas))


def finite(value: object) -> float | None:
    """frame 의 칸 값 → 유한한 float(NaN·inf·None·글은 None)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, numbers.Real):
        f = float(value)
        return f if math.isfinite(f) else None
    return None
