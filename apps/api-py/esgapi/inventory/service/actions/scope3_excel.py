"""Scope 3 데이터 엑셀 내려받기의 몸(밴드 S3D1 ① — 결정 MARC-ENT-592, 발주서 Q1·Q8·Q9). HTTP 를 모른다. 읽기만 한다.

    export(company_id, year)  그 해의 「지금 결과」(잠금 핀 · 제외 · 계수 고침 — Q1 ①)를 요약 + 카테고리 시트 열넷으로

재료는 연도 상태(actions/scope3_state.year_state)와 같은 함수를 공개 이름으로 가져다 쓴다(판단이 두 곳에 갈리지 않게):
`base_of`(R) → `selectors.locks_of` → `pinned_bodies`(핀 본문 — R 은 다시 읽지 않음)
→ `events_of`(지금 결과 실행들의 편집
사건, 쿼리 하나) → 카테고리마다 `run_of`(핀 아니면 R) · `category_value`(요약 합 — 화면 카드와 같은 Decimal 합).
★ R 이 없으면(그 해 done 실행 0) NotFound(Q8). R 은 있고 줄이 0 이면 머리만 있는 파일(Q9). year 범위 밖은 Invalid.
★ 읽기를 atomic 으로 묶지 않는다(Scope 1·2 export 꼴 — 동시 편집 중이면 카테고리끼리 다른 때의 값이 섞일 수 있다).
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Final, cast

from esgapi.inventory.engines.scope3.colab_157.output_files import OUT_SHEET_NAME_MAP
from esgapi.inventory.service.actions import scope3_state as state
from esgapi.inventory.service.selectors import scope3_edits as edit_selectors
from esgapi.inventory.service.selectors import scope3_state as selectors
from esgapi.inventory.service.utils.ghg_pool import Invalid, NotFound
from esgapi.inventory.service.utils.scope3_edits import Now, co2e_of, excluded_of, fold
from esgapi.inventory.service.utils.scope3_state import (
    CATEGORIES,
    CATEGORY_NAMES,
    category_value,
    engine_category,
)
from esgapi.inventory.tools import scope3_xlsx as xlsx
from esgapi.organization.service.selectors.organization import company_name

MEDIA_TYPE: Final = xlsx.MEDIA_TYPE


@dataclass(frozen=True)
class Download:
    """내려받을 파일 하나(이름·바이트)."""

    file_name: str
    content: bytes


def _fixed(now: Now, run_id: int, category: str) -> dict[str, xlsx.FixedFactor]:
    """그 실행 그 카테고리에서 계수가 AI 원안과 다른 줄(co2e_of 와 같은 거름 — applied 는 안 듦)의 사건 값."""
    found: dict[str, xlsx.FixedFactor] = {}
    for (event_run, row_id, _), event in now.items():
        factor = event.factor
        if event_run != run_id or event.category != category or factor is None or factor.choice == "applied":
            continue
        found[row_id] = xlsx.FixedFactor(
            value=factor.value,
            unit=factor.unit,
            source=factor.source,
            co2e=factor.co2e,
            biogenic_co2e=factor.biogenic_co2e,
        )
    return found


def _engine_sheets(body: Mapping[str, object] | None, category: str) -> tuple[xlsx.EngineSheet, ...]:
    """본문에서 그 카테고리의 processed 시트(서버 차례 그대로 — category_value 와 같은 거름)."""
    if body is None:
        return ()
    name = engine_category(category)
    sheets = body.get("sheets")
    found: list[xlsx.EngineSheet] = []
    for item in cast("list[object]", sheets) if isinstance(sheets, list) else []:
        if not isinstance(item, Mapping):
            continue
        sheet = cast("Mapping[str, object]", item)
        rows = sheet.get("rows")
        if sheet.get("category") != name or sheet.get("status") != "processed":
            continue
        title = sheet.get("sheet")
        found.append(
            xlsx.EngineSheet(
                name=title if isinstance(title, str) else "",
                rows=cast("list[object]", rows) if isinstance(rows, list) else [],
            )
        )
    return tuple(found)


def export(company_id: int, year: int) -> Download | NotFound | Invalid:
    """Scope 3 데이터 엑셀. year 범위 밖 Invalid · 그 해 R 없음 NotFound."""
    problem = state.year_problem(year)
    if problem is not None:
        return problem
    base = state.base_of(company_id, year)
    if base.run_id is None:
        return NotFound()
    locks = selectors.locks_of(company_id, year)
    pinned = state.pinned_bodies(company_id, base, locks)
    run_ids = {state.run_of(base, locks.get(category)) for category in CATEGORIES} - {None}
    now = fold(edit_selectors.events_of(company_id, cast("set[int]", run_ids)))
    books: list[xlsx.CategoryBook] = []
    for category in CATEGORIES:
        lock = locks.get(category)
        run_id = cast("int", state.run_of(base, lock))  # R 이 있으니 None 이 아니다
        body = base.body if lock is None else pinned.get(run_id)
        excluded = excluded_of(now, run_id, category)
        value = category_value(body, category, excluded, co2e_of(now, run_id, category))
        books.append(
            xlsx.CategoryBook(
                category=category,
                name=CATEGORY_NAMES[category],
                sheet_name=OUT_SHEET_NAME_MAP[engine_category(category)],
                total=value.total,
                sheets=value.sheets,
                failed_sheets=value.failed_sheets,
                engine_sheets=_engine_sheets(body, category),
                excluded=excluded,
                fixed=_fixed(now, run_id, category),
            )
        )
    content = xlsx.build_export(xlsx.ExportBook(year=year, categories=books))
    return Download(xlsx.export_file_name(year, company_name(company_id)), content)
