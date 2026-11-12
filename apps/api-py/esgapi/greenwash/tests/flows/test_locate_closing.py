"""locate 단계의 좌표 수명(밴드 G1b-2b ① — MARC-ISSUE-98 (4)): 닫는 좌표(ClosingCoordinatesPort)면 끝에(예외에도) 닫고
data.stats 에 셈을 싣는다. dry-run 이면 닫기만 하고 data 는 그대로다. 좌표 없음·닫기 없는 가짜(BoxCoordinates) 갈래의
data 는 G1b-2b 앞과 바이트 같다. 순수 층(DB 없음). 글과 숫자는 지은 것(synthetic)이다.
"""

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, cast

import pytest

from esgapi.core.flows.types import StepContext, StepOutput
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.tests.flows import support as s
from esgapi.greenwash.tests.tools.test_pdfium_locate import sample_pdf
from esgapi.greenwash.tools.coordinates import PdfiumCoordinates
from esgapi.greenwash.tools.pdftext_pypdf import PypdfText
from esgapi.greenwash.tools.ports import ClosingCoordinatesPort, CoordinatesPort, PositionValue

SENTENCE = "가상상사는 지은 문장으로 친환경을 말한다."
RESULTS = [{"page": 1, "sentence": SENTENCE}, {"page": 2, "sentence": SENTENCE}]
CARRIED = {"judge": StepOutput(data={"results": RESULTS})}


@dataclass
class ClosingBoxes:
    """닫는 가짜 좌표: 상자 하나를 짓고, explode_at 번째 부름에서 던진다. 닫힘·셈을 기록한다."""

    explode_at: int | None = None
    calls: int = 0
    closed: int = 0
    log: list[str] = field(default_factory=lambda: [])

    def locate(self, pdf: bytes, page: int, sentence: str) -> PositionValue | None:
        self.calls += 1
        self.log.append("locate")
        if self.explode_at == self.calls:
            raise RuntimeError("지은 좌표 오류")
        return {"page": page, "boxes": [[72.0, 100.0, 520.0, 112.0]]}

    def close(self) -> None:
        self.closed += 1
        self.log.append("close")

    def stats(self) -> dict[str, int]:
        self.log.append("stats")
        return {"found_tier1": self.calls, "opened": 1}


def with_coordinates(coordinates: CoordinatesPort | None) -> colab.GreenwashAdapters:
    return dataclasses.replace(s.adapters(), coordinates=coordinates)


def locate(coordinates: CoordinatesPort | None, *, dry_run: bool = False) -> StepOutput:
    adapters = with_coordinates(coordinates)
    return colab.locate(s.inputs(dry_run=dry_run), adapters, CARRIED, StepContext(resume=None))


def as_bytes(out: StepOutput) -> bytes:
    return json.dumps(out.data, ensure_ascii=False, sort_keys=True).encode()


def test_the_closing_port_is_the_pdfium_coordinates_and_not_the_fake_boxes() -> None:
    assert isinstance(PdfiumCoordinates(), ClosingCoordinatesPort)
    assert isinstance(ClosingBoxes(), ClosingCoordinatesPort)
    assert not isinstance(s.BoxCoordinates(), ClosingCoordinatesPort)  # 분모: 닫기 없는 가짜는 이 꼴이 아니다


def test_a_closing_port_is_closed_after_the_stats_are_put_in_the_step_data() -> None:
    coordinates = ClosingBoxes()
    out = locate(coordinates)
    box = {"page": 1, "boxes": [[72.0, 100.0, 520.0, 112.0]]}
    assert out.data == {"positions": [box, {**box, "page": 2}], "stats": {"found_tier1": 2, "opened": 1}}
    assert coordinates.log == ["locate", "locate", "stats", "close"]
    assert coordinates.closed == 1


def test_a_closing_port_is_closed_when_locate_raises() -> None:
    coordinates = ClosingBoxes(explode_at=2)
    with pytest.raises(RuntimeError, match="지은 좌표 오류"):
        locate(coordinates)
    assert coordinates.closed == 1
    assert coordinates.log[-1] == "close"


def test_dry_run_closes_a_closing_port_without_calling_it_and_keeps_the_data() -> None:
    coordinates = ClosingBoxes()
    out = locate(coordinates, dry_run=True)
    assert as_bytes(out) == as_bytes(StepOutput(data={"positions": [None, None]}))
    assert (coordinates.calls, coordinates.closed, coordinates.log) == (0, 1, ["close"])


def test_no_coordinates_and_the_fake_boxes_keep_the_data_bytes() -> None:
    """G1b-2b 앞의 꼴: 좌표 없음 → positions 전부 null, 닫기 없는 가짜 → positions 만(stats 칸 없음)."""
    assert as_bytes(locate(None)) == b'{"positions": [null, null]}'
    boxes = s.BoxCoordinates()
    out = locate(boxes)
    assert sorted(out.data) == ["positions"]
    assert out.data["positions"] == [boxes.locate(b"", 1, SENTENCE), boxes.locate(b"", 2, SENTENCE)]


class WatchedPdfium(PdfiumCoordinates):
    """닫을 때 든 문서를 적어 두는 PdfiumCoordinates(닫기가 실제로 연 문서를 닫았는지 본다)."""

    def __init__(self) -> None:
        super().__init__()
        self.closed_documents: list[object] = []

    def close(self) -> None:
        self.closed_documents.append(self.document)
        super().close()


def test_pdfium_coordinates_in_the_flow_are_closed_with_stats_in_the_locate_data() -> None:
    """진짜 PdfiumCoordinates 로 지은 PDF(표본 쪽 글 넷)를 흐름에 돌면 locate data 에 stats 가 오고, 단계가 연 문서를
    단계 끝에 닫는다."""
    coordinates = WatchedPdfium()
    given = dataclasses.replace(s.inputs(), document=sample_pdf())
    ran = s.run(given, dataclasses.replace(with_coordinates(coordinates), pdf_text=PypdfText()))
    data = cast("dict[str, Any]", ran.steps["locate"].data)
    assert sorted(data) == ["positions", "stats"]
    assert data["stats"] == coordinates.stats()
    assert data["stats"]["opened"] == 1
    assert any(p is not None for p in data["positions"])  # 분모: 실제로 찾았다
    # 문서를 열 때 앞 것을 비우는 close(None) 하나 + 단계 끝의 close(연 문서) 하나
    assert [d is not None for d in coordinates.closed_documents] == [False, True]
    assert coordinates.document is None


def test_a_sample_that_is_not_a_pdf_counts_an_error_per_sentence() -> None:
    """실행기 시험의 표본 bytes(b"synthetic-sample")는 PDF 가 아니라 문장마다 pdfium 이 던진다 — 위치는 null,
    셈은 none_error·error:PdfiumError(기대 결과 — 결과·골든은 그대로)."""
    coordinates = PdfiumCoordinates()
    data = cast("dict[str, Any]", s.run(s.inputs(), with_coordinates(coordinates)).steps["locate"].data)
    total = len(data["positions"])
    assert total > 0  # 분모: 판정 문장이 있다
    assert data["positions"] == [None] * total
    assert data["stats"] == {"none_error": total, "error:PdfiumError": total}
