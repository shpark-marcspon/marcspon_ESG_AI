"""S6 흐름 scope3.colab@157: `run_flow` 의 결과 = 엔진 `run` + serializer, 거절 갈래 둘(읽개 거절·옛 템플릿).

순수 층: DB 0, 소켓 문지기 아래(모의 공급사 — 막힌 시도 0). 템플릿은 지어낸 xlsx 바이트(시험 짓개 `xlsx_bytes`).
"""

from esgapi.core.flows.run import run_flow
from esgapi.inventory.engines.scope3.colab_157.pipeline import run
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.tests.engines.scope3.colab_157.support import (
    ColabReplies,
    FakeGeocoder,
    activity_book,
    commute_sheet,
    sheet,
    transport_distance_sheet,
    transport_ef_sheet,
    transport_spend_sheet,
    travel_distance_sheet,
    travel_ef_sheet,
    travel_spend_sheet,
    waste_sheet,
    workbook,
    xlsx_bytes,
)
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import (
    BOOK_ROWS,
    C1_ROWS,
    C2_ROWS,
    TAGS,
    book,
    replies,
)
from esgapi.inventory.tests.s3sheets_support import MiB, padded
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tools import xlsx_reader
from esgapi.inventory.tools.scope3_sheets.grid import Workbook
from esgapi.inventory.tools.xlsx_reader import read_workbook

TEMPLATE = workbook(sheet("C1_구매품서비스", C1_ROWS), sheet("C2_자본재", C2_ROWS), sheet("표지", {1: ["가상"]}))
ACTIVITY_TEMPLATE = workbook(
    sheet("C1_구매품서비스", {n: C1_ROWS[n] for n in (4, 5, 6)}),
    transport_distance_sheet("c4-1_운송거리"),
    transport_spend_sheet("c4-2_운송금액"),
    waste_sheet("c5_사업장폐기물"),
    travel_distance_sheet("c6-1_출장거리"),
    travel_spend_sheet("c6-2_출장비"),
    commute_sheet("c7_임직원통근"),
    transport_distance_sheet("c9-1_운송거리"),
    transport_spend_sheet("c9-2_운송금액"),
)


def flow_run(template: bytes, mock: ColabReplies, factor_book: Workbook | None = None) -> dict[str, object]:
    inputs = colab.ColabInputs(template=template, report_year=2025, route=ROUTE, tags=TAGS)
    factors = book() if factor_book is None else factor_book
    adapters = colab.ColabAdapters(llm=mock_client(mock), factor_book=factors, geocoder=FakeGeocoder())
    result = run_flow(colab.FLOW, inputs, adapters)
    assert list(result.steps) == [*colab.CATEGORY_STEPS, "assemble"]
    assert result.output.files == ()
    (only,) = result.output.results
    return only


def test_the_flow_equals_the_engine_and_serializer(blocked_network: list[object]) -> None:
    data = xlsx_bytes(TEMPLATE)
    flowed = flow_run(data, replies())
    read = read_workbook(data)
    assert isinstance(read, Workbook)
    direct = run(read, book(), 2025, mock_client(replies()), FakeGeocoder(), TAGS, ROUTE)
    assert flowed == result_to_dict(direct, colab.RESULT_SHAPE)
    assert next(iter(flowed)) == "schemaVersion"
    assert flowed["status"] == "done"
    assert blocked_network == []


def test_an_unreadable_template_is_rejected() -> None:
    flowed = flow_run(b"PK\x03\x04 not a zip", ColabReplies())
    assert flowed["status"] == "rejected"
    assert repr(flowed["rejected"]).startswith("{'reason': 'reader_problem', 'detail': ")


def test_an_uploaded_template_between_ten_and_twenty_mib_is_read() -> None:
    """올린 템플릿은 온실가스 올리기 상한(20MB — MARC-ENT-593)까지 읽는다: 15MiB 판이 작은 판과 같은 결과다."""
    small = xlsx_bytes(TEMPLATE)
    large = padded(small, 15 * MiB)
    assert xlsx_reader.MAX_BYTES < len(large) < xlsx_reader.GHG_UPLOAD_MAX_BYTES
    assert flow_run(large, replies()) == flow_run(small, replies())


def test_the_category_steps_read_a_large_upload_too() -> None:
    """카테고리 단계도 같은 상한으로 읽는다: 15MiB 판의 단계 일지(c1)가 작은 판과 같고 비어 있지 않다."""

    def journals(template: bytes) -> dict[str, object]:
        inputs = colab.ColabInputs(template=template, report_year=2025, route=ROUTE, tags=TAGS)
        adapters = colab.ColabAdapters(llm=mock_client(replies()), factor_book=book(), geocoder=FakeGeocoder())
        steps = run_flow(colab.FLOW, inputs, adapters).steps
        return {name: steps[name].data["journal"] for name in colab.CATEGORY_STEPS}

    small = xlsx_bytes(TEMPLATE)
    found = journals(padded(small, 15 * MiB))
    assert found["c1"]
    assert found == journals(small)


def test_an_uploaded_template_over_twenty_mib_is_a_reader_problem() -> None:
    flowed = flow_run(padded(xlsx_bytes(TEMPLATE), xlsx_reader.GHG_UPLOAD_MAX_BYTES + 1), ColabReplies())
    assert flowed["status"] == "rejected"
    assert repr(flowed["rejected"]).startswith("{'reason': 'reader_problem', 'detail': 'too_many_bytes")


def colab_flow_result(case: str) -> dict[str, object]:
    """test_flow_shapes 의 경우 셋: colab:done(S1 의 C1·C2 + 대상 아닌 시트) · colab:rejected(옛 템플릿) ·
    colab:activity(S3C-b1 — C1 한 줄 + C4-2·C9-2·C6-2·C5 한 줄씩, 계수 책은 구매_USEPA + 지출·폐기물 셋. S3C-b2a 가
    C4-1·C9-1 한 줄씩(거리 입력 — AI·지오코더 0)과 계수 시트 `운송` 을, S3C-b2b 가 C6-1·C7 한 줄씩(거리 입력)과
    계수 시트 `출장_통근` 을 더함)."""
    if case == "colab:done":
        return flow_run(xlsx_bytes(TEMPLATE), replies())
    if case == "colab:activity":
        book = activity_book(sheet("구매_USEPA", BOOK_ROWS))
        return flow_run(
            xlsx_bytes(ACTIVITY_TEMPLATE),
            replies(),
            Workbook((*book.sheets, transport_ef_sheet(), travel_ef_sheet()), ()),
        )
    assert case == "colab:rejected"
    return flow_run(xlsx_bytes(workbook(sheet("01_구매_Template", {1: ["가상"]}))), ColabReplies())


def test_a_legacy_template_is_rejected() -> None:
    mock = ColabReplies()
    flowed = flow_run(xlsx_bytes(workbook(sheet("01_구매_Template", {1: ["가상"]}))), mock)
    assert flowed == {
        "schemaVersion": "scope3.colab.result@1",
        "status": "rejected",
        "rejected": {"reason": "legacy_template", "detail": "「c + 숫자」 로 시작하는 시트가 없다: 01_구매_Template"},
    }
    assert mock.calls == []
