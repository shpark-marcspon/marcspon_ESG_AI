"""S3 시트 갈래: 21키 각각이 processed(`SUPPORTED_KEYS` 스물하나 — C1·C2·C4-1·C4-2·C9-1·C9-2·C6-2·C5,
C4-1·C9-1 은 S3C-b2a, C6-1·C7 은 S3C-b2b, C3·C8 셋·C13 셋은 S3C-c1a, C12·C15 는 S3C-c1b-1, C11·C14 는
S3C-c1b-2)로 가고 not_yet_supported 는 남지 않는다. 대상 아닌 시트는 not_target, 빈 시트는 empty 로 간다(분모 21 + 2).
「아직 지원 안 함」 을 조용히 건너뛰지 않는다(§1-7). 그리고 실행을 멈추는 둘과 시트 실패.
"""

import pytest

from esgapi.inventory.engines.scope3.colab_157 import pipeline
from esgapi.inventory.engines.scope3.colab_157.pipeline import (
    SUPPORTED_KEYS,
    ColabRejected,
    ColabRun,
    NotYetSupportedSheet,
    run,
)
from esgapi.inventory.engines.scope3.colab_157.template import SHEET_PROCESSOR_MAP
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    ColabReplies,
    FakeGeocoder,
    activity_book,
    c3_sheet,
    c11_sheet,
    c12_sheet,
    c14_sheet,
    c15_sheet,
    commute_sheet,
    leased_sheet,
    sheet,
    transport_distance_sheet,
    transport_spend_sheet,
    travel_distance_sheet,
    travel_spend_sheet,
    waste_sheet,
    workbook,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, C1_HEAD, C1_SUB, C2_ROWS, TAGS
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools.scope3_sheets.grid import Sheet, Workbook

C1_ONE_ROW = {4: C1_HEAD, 5: C1_SUB, 6: ["가상국", "가상사업장", "컨설팅", "가상 경영자문", None, 9100000]}
EMPTY_BY_PREFIX = "c2_자본가상"  # 21키 어디에도 없고 「c2_자」 앞 4글자로만 C2 에 닿는다(P7 이 문다)


def all_sheets() -> list[Sheet]:
    sheets: list[Sheet] = []
    for key in SHEET_PROCESSOR_MAP:
        if key == "c1_구매품서비스":
            sheets.append(sheet(key, C1_ONE_ROW))
        elif key == "c2_자본재":
            sheets.append(sheet(key, C2_ROWS))
        elif key in ("c4-1_운송거리", "c9-1_운송거리"):
            sheets.append(transport_distance_sheet(key))
        elif key in ("c4-2_운송금액", "c9-2_운송금액"):
            sheets.append(transport_spend_sheet(key))
        elif key == "c6-1_출장거리":
            sheets.append(travel_distance_sheet(key))
        elif key == "c7_임직원통근":
            sheets.append(commute_sheet(key))
        elif key == "c6-2_출장비":
            sheets.append(travel_spend_sheet(key))
        elif key == "c5_사업장폐기물":
            sheets.append(waste_sheet(key))
        elif key == "c3_연료에너지":
            sheets.append(c3_sheet(key))
        elif key.startswith(("c8-", "c13-")):
            sheets.append(leased_sheet(key))
        elif key == "c11_판매제품사용":
            sheets.append(c11_sheet(key))
        elif key == "c14_프랜차이즈":
            sheets.append(c14_sheet(key))
        elif key == "c12_판매제품폐기":
            sheets.append(c12_sheet(key))
        elif key == "c15_투자":
            sheets.append(c15_sheet(key))
        else:
            sheets.append(sheet(key, {1: ["가상 안내"]}))
    return [*sheets, sheet("표지", {1: ["가상 표지"]}), Sheet(EMPTY_BY_PREFIX, {}, (), ())]


def run_on(template: Workbook) -> ColabRun | ColabRejected:
    return run(
        template,
        activity_book(sheet("구매_USEPA", BOOK_ROWS)),
        2025,
        mock_client(ColabReplies()),
        FakeGeocoder(),
        TAGS,
        ROUTE,
    )


def test_every_sheet_gets_a_branch() -> None:
    result = run_on(workbook(*all_sheets()))
    assert isinstance(result, ColabRun)
    statuses = [(outcome.sheet, outcome.status) for outcome in result.sheets]
    assert len(statuses) == 21 + 2
    expected = [
        (key, "processed" if processor.key in SUPPORTED_KEYS else "not_yet_supported")
        for key, processor in SHEET_PROCESSOR_MAP.items()
    ]
    assert statuses == [*expected, ("표지", "not_target"), (EMPTY_BY_PREFIX, "empty")]
    processed = [key for key, status in statuses if status == "processed"]
    assert processed == [
        "c1_구매품서비스",
        "c2_자본재",
        "c3_연료에너지",
        "c4-1_운송거리",
        "c4-2_운송금액",
        "c5_사업장폐기물",
        "c6-1_출장거리",
        "c6-2_출장비",
        "c7_임직원통근",
        "c8-1_에너지사용량 아는 경우",
        "c8-2_면적",
        "c8-3_인원",
        "c9-1_운송거리",
        "c9-2_운송금액",
        "c11_판매제품사용",
        "c12_판매제품폐기",
        "c13-1_에너지사용량 아는경우",
        "c13-2_면적",
        "c13-3_인원",
        "c14_프랜차이즈",
        "c15_투자",
    ]
    assert [status for _, status in statuses].count("not_yet_supported") == 0
    bands = {o.processor.band for o in result.sheets if isinstance(o, NotYetSupportedSheet)}
    assert bands == set()  # S3C-b·c 몫을 다 처리(S3C-c1b-2)


def test_a_failing_sheet_is_a_branch_not_a_stop(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_: object) -> object:
        raise ValueError("가상 실패")

    monkeypatch.setattr(pipeline, "process_purchase_sheet", boom)
    result = run_on(workbook(sheet("C1_구매품서비스", C1_ONE_ROW), sheet("C2_자본재", C2_ROWS)))
    assert isinstance(result, ColabRun)
    assert [(o.status, getattr(o, "error", None)) for o in result.sheets] == [
        ("failed", "ValueError: 가상 실패"),
        ("failed", "ValueError: 가상 실패"),
    ]


def test_the_two_stops() -> None:
    no_usepa = run(
        workbook(sheet("C1_구매품서비스", C1_ONE_ROW)),
        workbook(sheet("가상 시트", {1: ["가상"]})),
        2025,
        mock_client(ColabReplies()),
        FakeGeocoder(),
        TAGS,
        ROUTE,
    )
    assert isinstance(no_usepa, ColabRejected)
    assert (no_usepa.reason, no_usepa.detail) == ("factor_book", "ValueError: Worksheet named '구매_USEPA' not found")
    legacy = run_on(workbook(sheet("01_구매_Template", {1: ["가상"]})))
    assert isinstance(legacy, ColabRejected)
    assert legacy.reason == "legacy_template"


def test_a_failed_reload_keeps_the_initial_spend_db() -> None:
    """보고연도 열이 없으면(2022 → 2025 열) 다시 짓기는 된다 — 원화 열이 아예 없을 때만 셀 9 의 것(USD 열)을 쓴다."""
    usd_only = workbook(
        sheet(
            "구매_USEPA",
            {
                3: ["품목군", "상세 카테고리", "한국어 매핑 키워드", "NAICS 코드", "NAICS Title", "EF (kgCO2e/USD)"],
                4: ["외주서비스", "가상세부", None, 9001, "Management Consulting Services", 0.95],
            },
        )
    )
    result = run(
        workbook(sheet("C1_구매품서비스", C1_ONE_ROW)),
        usd_only,
        2025,
        mock_client(ColabReplies()),
        FakeGeocoder(),
        TAGS,
        ROUTE,
    )
    assert isinstance(result, ColabRun)
    assert (result.spend_db.kind, result.spend_db.db.ef_col) == ("kept_initial", "EF (kgCO2e/USD)")
