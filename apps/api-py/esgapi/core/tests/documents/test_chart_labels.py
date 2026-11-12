"""CHL1 ② — 도표 라벨(셋째 JSON)의 순수 층: 어댑터(T9) · 꼴·NUL·크기(T11·T12) · 뷰(T14). DB 0.

DB 층(T10·T12 DB 단·T13·T15·T16)은 test_chart_labels_db.py. 도표·낱말은 지어낸 것이다(「Alpha」 꼴).
"""

import json
import urllib.request
from dataclasses import FrozenInstanceError
from typing import Any

import pytest

from esgapi.core.documents.contract import body_bytes, scrub_nul, shape_problem
from esgapi.core.documents.view import ChartLabels, ChartLabelsNotLoaded, DocArtifactView
from esgapi.core.resources.parser import decode_response
from esgapi.core.resources.ports.parser import Parsed, ParseFailed
from esgapi.core.tests.artifact_fakes import FakeArtifactView, fake_chart_labels, fake_document, fake_places
from esgapi.core.tests.test_parser_port import DOCUMENT, PDF, PLACES, Opener, http

SHA = "b" * 64

CHART = {
    "id": "p1-c1",
    "page": 1,
    "bbox": [80.0, 100.0, 260.0, 215.0],
    "plot": [100.0, 130.0, 226.0, 200.0],
    "form": "bar",
    "orientation": "vertical",
    "title": "Sample ratio",
    "multi_series": True,
    "legend": [["Actual", "#7d7366"], ["Plan", "#f7b500"]],
    "categories": ["Alpha", "Beta"],
}
LATER = {**CHART, "id": "p2-c1", "page": 2, "title": None, "multi_series": False, "categories": ["Gamma"]}


def word(text: str, *, chart: str = "p1-c1", role: str = "value", category: str | None = "Alpha", **label: Any):
    item: dict[str, Any] = {
        "container": "p1-b3",
        "start": 0,
        "end": len(text),
        "text": text,
        "bbox": [97.0, 131.0, 109.0, 137.0],
        "chart": chart,
        "role": role,
    }
    if role == "value":
        item["coord"] = {"category": category, "status": "ok"}
        item["elem"] = {"category": category, "status": "ok", "series": None, "series_status": "x"}
        item["label"] = {
            "title": "Sample ratio",
            "category": category,
            "status": label.get("status", "ok" if category else "between_categories"),
            "series": label.get("series"),
            "series_status": "ok" if label.get("series") else "no_legend_for_color",
        }
    return item


def labels(*words: dict[str, Any], charts: tuple[dict[str, Any], ...] = (CHART,)) -> dict[str, Any]:
    return fake_chart_labels(SHA, charts=charts, words=words)


# ── T9 어댑터 ────────────────────────────────────────────────────────────────


def envelope(**extra: Any) -> bytes:
    return json.dumps({"document": DOCUMENT, "charPlaces": PLACES, **extra}).encode()


def test_charts_asks_with_the_query_and_reads_the_third_key() -> None:
    opener = Opener(body=envelope(chartLabels=labels()))
    result = http(opener).parse(PDF, file_name="a.pdf", layout=2, charts=True)
    assert isinstance(result, Parsed) and result.chart_labels == labels()
    assert opener.requests[0].full_url == "http://parser.invalid:8000/parse?file_name=a.pdf&layout=2&charts=1"


@pytest.mark.parametrize("missing", [{}, {"chartLabels": None}, {"chartLabels": []}])
def test_charts_without_chart_labels_in_the_answer_is_an_invalid_response(missing: dict[str, Any]) -> None:
    """모르는 쿼리를 무시하는 옛 파서는 키 둘만 낸다 — None 으로 넘기지 않고 invalid_response(1-3 ⑥)."""
    result = http(Opener(body=envelope(**missing))).parse(PDF, file_name="a.pdf", layout=2, charts=True)
    assert isinstance(result, ParseFailed) and result.kind == "invalid_response"


def test_without_charts_the_answer_is_read_as_before() -> None:
    assert decode_response(envelope()) == Parsed(document=DOCUMENT, char_places=PLACES)
    # 묻지 않았는데 온 셋째 키는 싣지 않는다(기본 길의 Parsed 그대로)
    assert decode_response(envelope(chartLabels=labels())) == Parsed(document=DOCUMENT, char_places=PLACES)


def test_the_translation_and_reconcile_requests_are_the_bytes_of_before() -> None:
    """번역(pdf_158 — layout 2, charts 없음)·데이터 검증(reconcile parse — 인자 없음)의 요청 바이트 그대로
    (CHL1 permits 4)."""
    translation, reconcile = Opener(), Opener()
    http(translation).parse(PDF, file_name="document.pdf", layout=2)
    http(reconcile).parse(PDF, file_name="a.pdf")
    header = [("Content-type", "application/pdf")]
    assert _sent(translation.requests[0]) == (
        "POST",
        "http://parser.invalid:8000/parse?file_name=document.pdf&layout=2",
        header,
        PDF,
    )
    assert _sent(reconcile.requests[0]) == ("POST", "http://parser.invalid:8000/parse?file_name=a.pdf", header, PDF)


def _sent(request: urllib.request.Request) -> tuple[str, str, list[tuple[str, str]], object]:
    return (request.get_method(), request.full_url, sorted(request.header_items()), request.data)


# ── T11·T12 꼴·NUL·크기 ─────────────────────────────────────────────────────


def shape(chart_labels: object) -> str | None:
    return shape_problem(fake_document(SHA), fake_places(SHA), layout=2, sha256=SHA, chart_labels=chart_labels)


def test_the_shape_of_chart_labels_is_checked_only_when_present() -> None:
    assert shape(None) is None
    assert shape(labels(word("16.2"))) is None
    assert shape([]) == "chartLabels 가 객체가 아니다"
    assert shape({**labels(), "source": {"sha256": "c" * 64}}) == "chartLabels 의 source.sha256 이 원본과 다르다"
    for key in ("charts", "words", "unlinked"):
        assert shape({**labels(), key: {}}) == f"chartLabels 의 {key} 가 배열이 아니다"


def test_nul_in_chart_labels_is_scrubbed_like_the_other_two() -> None:
    clean, count = scrub_nul(labels(word("1\x006")))
    assert count == 1 and clean["words"][0]["text"] == "1�6"


def test_body_bytes_adds_the_third_part() -> None:
    document, places, third = fake_document(SHA), fake_places(SHA), labels(word("16.2"))
    one = len(json.dumps(third, ensure_ascii=False, separators=(",", ":")).encode())
    assert body_bytes(document, places, third) == body_bytes(document, places) + one
    assert body_bytes(document, places, None) == body_bytes(document, places)


# ── T14 뷰 ───────────────────────────────────────────────────────────────────


def view(chart_labels: dict[str, Any] | None) -> FakeArtifactView:
    return FakeArtifactView.from_dicts(fake_document(SHA), chart_labels=chart_labels)


def test_no_column_is_none_but_found_nothing_is_empty() -> None:
    assert view(None).chart_labels() is None
    empty = view(labels(charts=()))
    assert empty.chart_labels() == ChartLabels(charts=(), words=())


def test_a_view_that_did_not_load_labels_says_so() -> None:
    plain = DocArtifactView(artifact_id=1, document=fake_document(SHA), char_places=None)
    with pytest.raises(ChartLabelsNotLoaded):
        plain.chart_labels()


def test_the_view_gives_the_combined_label_only_in_page_chart_order() -> None:
    raw = labels(
        word("9", chart="p2-c1", category="Gamma"),
        word("16.2", series="Plan"),
        word("40", role="tick"),
        word("16.9", category=None),
        charts=(LATER, CHART),  # 파서가 낸 도표 차례와 쪽 차례가 다르다
    )
    got = view(raw).chart_labels()
    assert got is not None
    assert [c.id for c in got.charts] == ["p2-c1", "p1-c1"]
    assert [w.text for w in got.words] == ["16.2", "40", "16.9", "9"]  # 쪽 → 도표 → 원래 차례
    first = got.words[0]
    assert (first.category, first.series, first.status, first.role) == ("Alpha", "Plan", "ok", "value")
    assert not hasattr(first, "coord") and not hasattr(first, "elem")
    tick = got.words[1]
    assert (tick.role, tick.category, tick.series, tick.status) == ("tick", None, None, None)
    assert [w.text for w in got.values()] == ["16.2", "9"]  # 범주 없는 값·눈금은 빠진다
    assert [w.text for w in got.values("p2-c1")] == ["9"]
    assert view(raw).chart_labels() == got  # 결정적


FIELD, TITLE = "category", "title"  # 이름을 변수로 — 고칠 수 없음을 setattr 로 잰다


def test_the_labels_are_frozen() -> None:
    got = view(labels(word("16.2"))).chart_labels()
    assert got is not None
    with pytest.raises(FrozenInstanceError):
        setattr(got.words[0], FIELD, "Beta")
    with pytest.raises(FrozenInstanceError):
        setattr(got.charts[0], TITLE, "x")
