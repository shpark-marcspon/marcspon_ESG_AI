"""`ColabRun` → 결과 dict. 꼴 `contracts/shapes.py` 의 Scope3ColabDone·Scope3ColabRejected 와 키 차례까지 같게 손으로
적는다.

결과 꼴 id 의 글자는 흐름이 준다(흐름 id·결과 꼴 id 의 글자는 흐름·registration.py·contracts/shapes.py 에만 —
`flows/__init__.py`). 엔진은 계약을 import 하지 않는다(.importlinter inventory-engine-not-contracts).

수의 꼴(처분 ⑦): 셈은 코랩과 같은 float 이고, 칸은 `repr(float)`(가장 짧은 왕복 표기 — `1e-05` 같은 지수 표기도
낸다). 십진 정확값이 아니다. NaN·inf·없음은 null 이고 그 줄의 `missing` 에 어느 칸이 왜 비었는지 남긴다.
rowId = `시트!엑셀 줄`(같은 줄이 둘 이상이면 `#n` — llm-first 꼴).
입력 칸은 줄 끝의 `input` 으로만 싣는다(MARC-ISSUE-524, S3R2): 키 열여섯(`INPUT_KEYS` — S3R3 에 useMonths)이 늘 있고
값은 처리기 key 별 원천 표(`INPUT_SOURCES`)의 frame 열 — 그 밖 칸에서 다시 꺼내지 않는다. 글은 글자 그대로, 수는
`decimal_text`, 빈 글·NaN·없음은 null. 이름 후보가 둘인 C4·C9·C5 는 카테고리(처리기 category) 단위로 값이 든 첫 열을
한 번 고른다(esg-lab 대조 `scope3colab_dump._item_column` 과 같은 규칙).
`co2e`·`formula`·추천의 `expectedCo2e` 는 코랩 후처리(`_fix_result_c1_c2` `:8799`) 뒤의 값이다 — 「구매금액」
열(통화 환산 전)이 기준이다. `spendKrw` 는 셈 때의 원화 환산 금액(EF적용금액(KRW))이다.
줄은 판별 칸 `kind` 로 가른다(S3C-b1): C1·C2 = `"purchase"`(RowMeta), C4-2·C9-2·C6-2·C5 = 활동 줄(ActivityMeta —
`transport_spend`·`travel_spend`·`waste`). 활동 줄의 `co2e`·`formula` 는 코랩 결과 행의 「배출량(tCO2e)」·「계산식」
(C6 은 후처리 뒤, C5 는 화석기원)이고 활동량·계수·생물기원·이동수단·산정 출처는 줄 메타에서 온다.
거리 줄(C4-1·C9-1 — S3C-b2a, kind `transport_distance`)은 칸 `distance`(셈에 쓴 거리와 그 길)를 싣고, `missing` 의
`amount` 는 셈에 쓴 거리나 무게(kg)가 없을 때, `factor` 는 운송 계수 맵에 그 코드가 없을 때다. 지출·폐기물 줄의
`distance` 는 null 이다. 출장·통근 거리 줄(C6-1·C7 — S3C-b2b, kind `travel_distance`·`commute`)은 같은 칸에 왕복계수·
인원·이동횟수(C6)·근무일수(C7)를 더 싣고, `co2e`·`formula` 는 후처리(`_fix_result_c6`·`_fix_result_c7`) 뒤 값이다.
에너지 줄(C3·C8·C13 — S3C-c1a, kind `fuel_energy`·`leased_asset`·`leased_out_asset`, EnergyMeta)은 사용량·환산·계수를
같은 칸에 싣고, C8·C13 은 `match`(계수 사슬의 match_type·score)와 `allocation`(산정방식·건물전체사용량·비율)을 더한다.
판매제품 폐기·투자 줄(C12·C15 — S3C-c1b-1, kind `product_eol`·`investment`, ProductMeta)은 같은 줄 꼴에 C12 는
`biogenic`(화석·생물기원 나눔 — C5 꼴)과 `treatments`(처리방법별 비중·계수 — S3Q1, 셈에 안 닿는 보기 칸,
`input` 앞), C15 는 `investment`(지분율·Scope1·Scope2)를 싣고 C15 의 factor 는 null 이다.
판매제품 사용·프랜차이즈 줄(C11·C14 — S3C-c1b-2, kind `product_use`·`franchise`, ProductMeta)은 사용량·환산·계수를
에너지 줄과 같은 칸에 싣고 `match`(처리 때 EF매핑방식·EF매핑점수)를, C11 은 `product`(사용기간·총사용량)를 더한다.
값은 결과 후처리(`:8720`·`:8862`) 뒤다.
`factorSheets` 는 실행 머리에서 읽은 계수 시트 여덟(지출·폐기물 셋 + `운송` + `출장_통근` + `에너지`·`에너지_C3` +
`폐기물_C12`, `ColabRun.factor_sheets`)이다.
"""

import numbers
from collections import Counter
from collections.abc import Mapping
from typing import Any, Final

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157.activity import ActivityBiogenic, ActivityDistance, ActivityMeta
from esgapi.inventory.engines.scope3.colab_157.energy import EnergyMatch, EnergyMeta
from esgapi.inventory.engines.scope3.colab_157.factor_book import USEPA_SHEET, FactorSheetRead, SpendDbKeptInitial
from esgapi.inventory.engines.scope3.colab_157.pipeline import (
    ColabRejected,
    ColabRun,
    EmptySheet,
    FailedSheet,
    NotTargetSheet,
    NotYetSupportedSheet,
    ProcessedSheet,
    SheetOutcome,
)
from esgapi.inventory.engines.scope3.colab_157.product import C12Treatments, ProductMeta
from esgapi.inventory.engines.scope3.colab_157.purchase import ColabMissing, PurchaseGroup, RowMeta, finite
from esgapi.inventory.engines.scope3.colab_157.waste import BiogenicSplit


def decimal_text(value: object) -> str | None:
    """float 셈의 값 → `repr(float)`. 유한한 수가 아니면 None."""
    number = finite(value)
    return None if number is None else repr(number)


def _text(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _group(group: PurchaseGroup) -> dict[str, object]:
    llm = (
        None
        if group.llm is None
        else {"outcome": group.llm.outcome, "answer": group.llm.answer, "reason": group.llm.reason}
    )
    return {
        "key": group.key,
        "name": group.name,
        "reason": group.reason,
        "family": group.family,
        "category": group.category,
        "llm": llm,
    }


def _row(row_id: str, meta: RowMeta, values: "pd.Series[Any]", factor_column: str | None) -> dict[str, object]:
    amount = decimal_text(pd.to_numeric(pd.Series([values.get("구매금액")]), errors="coerce").iloc[0])
    title = _text(values.get("EF_DB"))
    value = decimal_text(values.get("배출계수"))
    missing: list[ColabMissing] = []
    if amount is None:
        missing.append("amount")
    if title is None:
        missing.append("factor")
    elif value is None:
        missing.append("factorValue")
    recommendations: list[dict[str, object]] = []
    for i in range(1, 5):
        rec_title = _text(values.get(f"추천EF{i}"))
        if rec_title is None:
            continue
        recommendations.append(
            {
                "title": rec_title,
                "value": decimal_text(values.get(f"추천EF{i}_배출계수")),
                "expectedCo2e": decimal_text(values.get(f"추천EF{i}_예상배출량(tCO2e)")),
            }
        )
    source = meta.candidates[0].source if meta.candidates else "none"
    return {
        "rowId": row_id,
        "kind": "purchase",
        "month": meta.month,
        "amount": amount,
        "spendKrw": decimal_text(meta.spend.amount_krw),
        "spendNote": meta.spend.unit_note,
        "factor": {
            "title": title,
            "value": value,
            "unit": "kgCO2e/KRW",
            "column": factor_column,
            "source": source,
        },
        "co2e": decimal_text(values.get("배출량(tCO2e)")),
        "unit": "tCO2eq",
        "formula": str(values.get("계산식") or ""),
        "recommendations": recommendations,
        "group": _group(meta.group),
        "origin": meta.origin,
        "originSteps": [{"step": s.step, "origin": s.origin, "via": s.via} for s in meta.origin_steps],
        "missing": missing,
    }


def _distance(distance: ActivityDistance | None) -> dict[str, object] | None:
    if distance is None:
        return None
    return {
        "km": decimal_text(distance.km),
        "via": distance.via,
        "geoMode": distance.geo_mode,
        "departure": distance.departure,
        "arrival": distance.arrival,
        "roundTrip": decimal_text(distance.round_trip),
        "people": decimal_text(distance.people),
        "trips": decimal_text(distance.trips),
        "workdays": decimal_text(distance.workdays),
    }


def _activity_row(row_id: str, meta: ActivityMeta, values: "pd.Series[Any]") -> dict[str, object]:
    activity, factor = meta.activity, meta.factor
    amount = decimal_text(activity.value)
    factor_value = decimal_text(factor.value)
    has_factor = any(s.step == "factor" for s in meta.steps)
    missing: list[ColabMissing] = []
    distance = meta.distance
    if distance is not None:  # 거리 줄: 셈에 쓴 거리·무게(kg)
        if decimal_text(distance.km) is None or decimal_text(activity.base_value) is None:
            missing.append("amount")
    elif amount is None:
        missing.append("amount")
    if not has_factor:
        missing.append("factor")
    elif factor_value is None:
        missing.append("factorValue")
    biogenic_json = _biogenic(meta.biogenic)
    mode = meta.mode
    formula = values.get("계산식")
    return {
        "rowId": row_id,
        "kind": meta.kind,
        "month": meta.month,
        "activity": {
            "value": amount,
            "unit": activity.unit,
            "baseValue": decimal_text(activity.base_value),
            "baseUnit": activity.base_unit,
            "note": activity.note,
        },
        "factor": {
            "sheet": factor.sheet,
            "title": factor.title,
            "value": factor_value,
            "unit": factor.unit,
            "column": factor.column,
            "code": factor.code,
        },
        "co2e": decimal_text(values.get("배출량(tCO2e)")),
        "unit": "tCO2eq",
        "formula": formula if isinstance(formula, str) else "",
        "treatment": meta.treatment,
        "biogenic": biogenic_json,
        "mode": None if mode is None else {"value": mode.value, "origin": mode.origin},
        "distance": _distance(distance),
        "origin": meta.origin,
        "originSteps": [{"step": s.step, "origin": s.origin, "via": s.via} for s in meta.steps],
        "missing": missing,
    }


def _biogenic(biogenic: ActivityBiogenic | BiogenicSplit | None) -> dict[str, object] | None:
    if biogenic is None:
        return None
    return {
        "fossilCo2e": decimal_text(biogenic.fossil),
        "biogenicCo2e": decimal_text(biogenic.biogenic),
        "fcf": decimal_text(biogenic.fcf),
        "note": biogenic.note,
    }


def _match(match: EnergyMatch | None) -> dict[str, object] | None:
    return None if match is None else {"type": match.match_type, "score": decimal_text(match.score)}


def _product_row(row_id: str, meta: ProductMeta, values: "pd.Series[Any]") -> dict[str, object]:
    """C11·C12·C14·C15 줄 — 키 차례는 `_energy_row` 그대로(allocation 은 null, match 는 C11·C14, product 는 C11)."""
    activity, factor = meta.activity, meta.factor
    amount = decimal_text(activity.value)
    factor_value = None if factor is None else decimal_text(factor.value)
    missing: list[ColabMissing] = []
    if amount is None:
        missing.append("amount")
    if not any(s.step == "factor" for s in meta.steps):
        missing.append("factor")
    elif factor_value is None:
        missing.append("factorValue")
    investment, use = meta.investment, meta.product
    co2e_column = "배출량" if meta.kind == "investment" else "배출량(tCO2e)"  # C15 는 단위 없는 이름(`:5630`)
    formula = values.get("계산식")
    row: dict[str, object] = {
        "rowId": row_id,
        "kind": meta.kind,
        "month": meta.month,
        "activity": {
            "value": amount,
            "unit": activity.unit,
            "baseValue": decimal_text(activity.base_value),
            "baseUnit": activity.base_unit,
            "note": activity.note,
        },
        "factor": None
        if factor is None
        else {
            "sheet": factor.sheet,
            "title": factor.title,
            "value": factor_value,
            "unit": factor.unit,
            "column": factor.column,
            "code": factor.code,
        },
        "co2e": decimal_text(values.get(co2e_column)),
        "unit": "tCO2eq",
        "formula": formula if isinstance(formula, str) else "",
        "match": _match(meta.match),
        "allocation": None,
        "biogenic": _biogenic(meta.biogenic),
        "product": None
        if use is None
        else {"years": decimal_text(use.years), "totalUsage": decimal_text(use.total_usage)},
        "investment": None
        if investment is None
        else {
            "share": decimal_text(investment.share),
            "scope1": decimal_text(investment.scope1),
            "scope2": decimal_text(investment.scope2),
        },
        "origin": meta.origin,
        "originSteps": [{"step": s.step, "origin": s.origin, "via": s.via} for s in meta.steps],
        "missing": missing,
    }
    if meta.kind == "product_eol" and meta.treatments is not None:
        row["treatments"] = _treatments(meta.treatments)  # S3Q1 — C12 만, input 앞(계약 차례)
    return row


def _treatments(treatments: C12Treatments) -> dict[str, object]:
    """C12 처리방법별 값(S3Q1 Q6·Q7): 비중은 0~1 수(`_pct` 뒤), 계수는 kgCO2eq/kg — 둘 다 repr(float), NaN 은 null."""
    return {
        "branch": treatments.branch,
        "shareTotal": decimal_text(treatments.share_total),
        "parts": [
            {
                "treatment": part.treatment,
                "share": decimal_text(part.share),
                "factor": decimal_text(part.factor),
                "used": part.used,
            }
            for part in treatments.parts
        ],
    }


def _energy_row(row_id: str, meta: EnergyMeta, values: "pd.Series[Any]") -> dict[str, object]:
    activity, factor = meta.activity, meta.factor
    amount = decimal_text(activity.value)
    factor_value = None if factor is None else decimal_text(factor.value)
    missing: list[ColabMissing] = []
    if amount is None:
        missing.append("amount")
    if not any(s.step == "factor" for s in meta.steps):
        missing.append("factor")
    elif factor_value is None:
        missing.append("factorValue")
    match, allocation = meta.match, meta.allocation
    formula = values.get("계산식")
    return {
        "rowId": row_id,
        "kind": meta.kind,
        "month": meta.month,
        "activity": {
            "value": amount,
            "unit": activity.unit,
            "baseValue": decimal_text(activity.base_value),
            "baseUnit": activity.base_unit,
            "note": activity.note,
        },
        "factor": None
        if factor is None
        else {
            "sheet": factor.sheet,
            "title": factor.title,
            "value": factor_value,
            "unit": factor.unit,
            "column": factor.column,
            "code": factor.code,
        },
        "co2e": decimal_text(values.get("배출량(tCO2e)")),
        "unit": "tCO2eq",
        "formula": formula if isinstance(formula, str) else "",
        "match": None if match is None else {"type": match.match_type, "score": decimal_text(match.score)},
        "allocation": None
        if allocation is None
        else {
            "method": allocation.method,
            "buildingTotal": decimal_text(allocation.building_total),
            "areaRatio": decimal_text(allocation.area_ratio),
            "personRatio": decimal_text(allocation.person_ratio),
        },
        "biogenic": None,
        "product": None,
        "investment": None,
        "origin": meta.origin,
        "originSteps": [{"step": s.step, "origin": s.origin, "via": s.via} for s in meta.steps],
        "missing": missing,
    }


def _meta_row(
    row_id: str,
    meta: RowMeta | ActivityMeta | EnergyMeta | ProductMeta,
    values: "pd.Series[Any]",
    factor_column: str | None,
) -> dict[str, object]:
    if isinstance(meta, ProductMeta):
        return _product_row(row_id, meta, values)
    if isinstance(meta, EnergyMeta):
        return _energy_row(row_id, meta, values)
    if isinstance(meta, ActivityMeta):
        return _activity_row(row_id, meta, values)
    return _row(row_id, meta, values, factor_column)


def _row_ids(
    sheet: str,
    metas: tuple[RowMeta, ...] | tuple[ActivityMeta, ...] | tuple[EnergyMeta, ...] | tuple[ProductMeta, ...],
) -> list[str]:
    bases = [f"{sheet}!{meta.excel_row}" if meta.excel_row is not None else f"{sheet}!?" for meta in metas]
    counts = Counter(bases)
    seen: Counter[str] = Counter()
    ids: list[str] = []
    for base in bases:
        seen[base] += 1
        ids.append(base if counts[base] == 1 else f"{base}#{seen[base]}")
    return ids


# ── 입력 칸(S3R2) ──
INPUT_KEYS: Final = (
    "country", "site", "name", "vehicle", "energy", "people", "buildingArea", "usedArea", "buildingPeople", "ownPeople",
    "productCount", "sales", "weight", "weightUnit", "stores", "useMonths",
)  # fmt: skip
"""`input` 의 키 차례(contracts/shapes.py 의 ColabRowInputJson 과 같은 글자·차례)."""

_LEASED: Final = {"country": ("국가",), "name": ("자산명",), "energy": ("에너지원",)}
_LEASED_AREA: Final = {**_LEASED, "buildingArea": ("건물전체면적",), "usedArea": ("사용면적",)}
_LEASED_PERSON: Final = {**_LEASED, "buildingPeople": ("건물전체인원수",), "ownPeople": ("자사인원수",)}
INPUT_SOURCES: Final[Mapping[str, Mapping[str, tuple[str, ...]]]] = {
    # 처리기 key → 키 → frame 열(코랩 결과 시트의 열 이름 — 표준화 이름 바꿈 뒤).
    # 열이 둘이면 이름 후보(카테고리 단위로 고름).
    # 양식 머리 글과 frame 열의 같음은 S3R2 C0-2 실측(band-reports/S3R2.md §1-2 고친 판).
    "c1": {"country": ("국가",), "site": ("사업장",), "name": ("품목명",)},  # ← 상세 품목명/서비스명(그룹 덮기 전)
    "c2": {"country": ("국가",), "site": ("사업장",), "name": ("자산명",)},  # ← 상세 자산명(`품목/자산명` 은 그룹)
    "c3": {"country": ("국가",), "site": ("사업장",), "energy": ("에너지원",)},  # ← 연료/에너지명
    "c4_dist": {"country": ("국가",), "site": ("사업장",), "name": ("자재명", "제품명")},
    "c4_spend": {"country": ("국가",), "site": ("사업장",), "name": ("자재명", "제품명"), "vehicle": ("운송수단",)},
    "c5": {"country": ("국가",), "site": ("사업장",), "name": ("폐기물 종류", "상세폐기물명")},
    "c6_dist": {"country": ("국가",), "site": ("사업장",), "people": ("인원수",)},  # 사업장 ← 출장주체
    # 사업장 ← 출장주체, 이동수단 ← 출장항목(지출 kind 의 mode 는 null)
    "c6_spend": {"country": ("국가",), "site": ("사업장",), "vehicle": ("이동수단",), "people": ("인원수",)},
    "c7": {"country": ("국가",), "site": ("사업장",), "people": ("인원수",)},
    "c8_energy": _LEASED,  # 자산명 ← 임차자산명, 에너지원 ← 에너지종류
    "c8_area": _LEASED_AREA,
    "c8_person": _LEASED_PERSON,
    "c9_dist": {"country": ("국가",), "site": ("사업장",), "name": ("제품명", "자재명")},
    "c9_spend": {"country": ("국가",), "site": ("사업장",), "name": ("제품명", "자재명"), "vehicle": ("운송수단",)},
    "c11": {  # useMonths ← 수명(개월) 혹은 평균 사용기간(개월)(바꿈 `product.py` `_C11_RENAMES` — S3R3)
        "country": ("국가",),
        "name": ("제품명",),
        "energy": ("에너지명",),
        "productCount": ("제품수량",),
        "useMonths": ("수명(개월)",),
    },
    "c12": {
        "country": ("국가",),
        "name": ("제품명",),
        "sales": ("판매량",),
        "weight": ("제품중량",),
        "weightUnit": ("제품중량 단위",),
    },
    "c13_energy": _LEASED,  # 자산명 ← 임대자산명
    "c13_area": _LEASED_AREA,
    "c13_person": _LEASED_PERSON,
    "c14": {"country": ("국가",), "name": ("프랜차이즈명",), "energy": ("에너지원",), "stores": ("가맹점수",)},
    "c15": {"name": ("피투자기업명",)},
}


def input_text(value: object) -> str | None:
    """입력 칸 값 → 글. 글은 그대로(빈 글은 None), 수는 `decimal_text`, None·NaN 은 None, 그 밖 꼴은 `str`."""
    if value is None or value is pd.NA or value is pd.NaT:
        return None
    if isinstance(value, str):
        return value if value != "" else None
    if isinstance(value, bool):
        return str(value)
    if isinstance(value, numbers.Real):
        return decimal_text(value)  # NaN·inf → None
    return str(value)


def _has_text(value: object) -> bool:
    """고르는 판정에서만 쓰는 「값이 든」: 공백만인 글은 빈 것(esg-lab `text_value` 의 strip 과 같다). 싣는 값은
    `input_text` 그대로 — 공백 글도 글자 그대로 실린다."""
    text = input_text(value)
    return text is not None and text.strip() != ""


def name_columns(sheets: "list[ProcessedSheet]") -> dict[str, str]:
    """카테고리(처리기 category)마다 이름 열 하나: 후보 가운데 그 카테고리의 frame 들에 값이 하나라도 든 첫 열."""
    chosen: dict[str, str] = {}
    by_category: dict[str, list[ProcessedSheet]] = {}
    for outcome in sheets:
        by_category.setdefault(outcome.processor.category, []).append(outcome)
    for category, parts in by_category.items():
        candidates = INPUT_SOURCES.get(parts[0].processor.key, {}).get("name", ())
        if len(candidates) < 2:
            continue
        chosen[category] = next(
            (
                column
                for column in candidates
                if any(column in part.frame.columns and any(_has_text(v) for v in part.frame[column]) for part in parts)
            ),
            candidates[0],
        )
    return chosen


def _input(key: str, values: "pd.Series[Any]", name_column: str | None) -> dict[str, str | None]:
    sources = INPUT_SOURCES.get(key, {})
    out: dict[str, str | None] = {}
    for field in INPUT_KEYS:
        columns = sources.get(field, ())
        column = name_column if field == "name" and len(columns) > 1 and name_column is not None else None
        column = column if column is not None else (columns[0] if columns else None)
        out[field] = None if column is None or column not in values.index else input_text(values[column])
    return out


def sheet_to_dict(
    outcome: SheetOutcome, factor_column: str | None, names: Mapping[str, str] | None = None
) -> dict[str, object]:
    """시트 하나의 결과. `names` 는 카테고리 → 이름 열(`run_to_dict` 가 실행의 시트 전부로 고름 — 없으면 이 시트로)."""
    match outcome:
        case ProcessedSheet(sheet=sheet, processor=processor, frame=frame, metas=metas):
            ids = _row_ids(sheet, metas)
            name_column = (name_columns([outcome]) if names is None else names).get(processor.category)
            rows: list[dict[str, object]] = []
            for i, meta in enumerate(metas):
                values = frame.iloc[i]
                row = _meta_row(ids[i], meta, values, factor_column)
                row["input"] = _input(processor.key, values, name_column)
                rows.append(row)
            return {"sheet": sheet, "category": processor.category, "status": "processed", "rows": rows}
        case NotTargetSheet(sheet=sheet):
            return {"sheet": sheet, "status": "not_target"}
        case NotYetSupportedSheet(sheet=sheet, processor=processor):
            return {
                "sheet": sheet,
                "category": processor.category,
                "status": "not_yet_supported",
                "band": processor.band,
            }
        case EmptySheet(sheet=sheet, processor=processor):
            return {"sheet": sheet, "category": processor.category, "status": "empty"}
        case FailedSheet(sheet=sheet, processor=processor, error=error):
            return {"sheet": sheet, "category": processor.category, "status": "failed", "error": error}


def _factor_sheet(read: FactorSheetRead) -> dict[str, object]:
    return {"sheet": read.sheet, "read": read.how, "header": read.header, "rows": len(read.frame)}


def run_to_dict(result: ColabRun, schema_version: str) -> dict[str, object]:
    choice = result.spend_db
    kept = isinstance(choice, SpendDbKeptInitial)
    factor_column = choice.db.ef_col
    names = name_columns([outcome for outcome in result.sheets if isinstance(outcome, ProcessedSheet)])
    return {
        "schemaVersion": schema_version,
        "status": "done",
        "reportYear": result.report_year,
        "factorBook": {
            "sheet": USEPA_SHEET,
            "column": factor_column,
            "year": choice.db.year,
            "reload": choice.kind,
            "reloadProblem": choice.reason if kept else None,
        },
        "factorSheets": [_factor_sheet(read) for read in result.factor_sheets],
        "sheets": [sheet_to_dict(outcome, factor_column, names) for outcome in result.sheets],
        "llmCalls": {prompt: dict(counts) for prompt, counts in result.llm_calls.by_prompt.items()},
    }


def rejected_to_dict(schema_version: str, reason: str, detail: str) -> dict[str, object]:
    return {"schemaVersion": schema_version, "status": "rejected", "rejected": {"reason": reason, "detail": detail}}


def result_to_dict(result: ColabRun | ColabRejected, schema_version: str) -> dict[str, object]:
    if isinstance(result, ColabRejected):
        return rejected_to_dict(schema_version, result.reason, result.detail)
    return run_to_dict(result, schema_version)
