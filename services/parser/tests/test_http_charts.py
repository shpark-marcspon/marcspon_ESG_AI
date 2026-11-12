"""`POST /parse?layout=2&charts=1` — 도표 라벨 셋째 키 `chartLabels`(밴드 CHL1 T5~T7).

쿼리가 없으면 봉투·바이트·안쪽 부르는 꼴이 그대로임도 본다(7a 허락 H1 조건). PDF 는 `pdfbuild` 로 짓는다.
"""

import json
from functools import partial
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from jsonschema import Draft202012Validator

import app as parser
from docparse.config import CHARTS_SCHEMA_PATH
from docparse.engine import pdfium_engine

from .test_charts import _chart_page
from .test_http import PDF, detail, in_child

client = TestClient(parser.app)


def chart_pdf():
    return _chart_page()[0].tobytes()


def _schema_errors(labels):
    schema = json.loads(CHARTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    return [e.message for e in Draft202012Validator(schema).iter_errors(labels)]


# ── 200 ──────────────────────────────────────────────────────────────


def test_layout_2_with_charts_adds_chart_labels_that_pass_the_schema():
    response = client.post("/parse?layout=2&charts=1&file_name=mine.pdf", content=chart_pdf(), headers=PDF)
    assert response.status_code == 200
    body = response.json()
    assert list(body) == ["document", "charPlaces", "chartLabels"]
    labels = body["chartLabels"]
    assert _schema_errors(labels) == []
    assert labels["source"] == body["document"]["source"] == body["charPlaces"]["source"]
    assert labels["source"]["file_name"] == "mine.pdf"  # 부르는 쪽이 준 이름을 셋 다에 적는다
    assert {w["label"]["category"] for w in labels["words"] if w["role"] == "value"} == {"Alpha", "Beta"}


def test_charts_leave_the_document_and_char_places_as_without_them():
    data = chart_pdf()
    plain = client.post("/parse?layout=2&file_name=mine.pdf", content=data, headers=PDF)
    with_charts = client.post("/parse?layout=2&charts=1&file_name=mine.pdf", content=data, headers=PDF)
    assert plain.status_code == with_charts.status_code == 200
    plain_body, charts_body = plain.json(), with_charts.json()
    assert list(plain_body) == ["document", "charPlaces"]  # 쿼리 없으면 키 둘
    assert charts_body["document"] == plain_body["document"] and charts_body["charPlaces"] == plain_body["charPlaces"]
    # 쿼리 없는 판 2 봉투의 바이트는 라벨을 뺀 봉투와 같다(같은 꼴로 적는다)
    del charts_body["chartLabels"]
    assert plain.content == json.dumps(charts_body, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


# ── 422 bad_charts ───────────────────────────────────────────────────


@pytest.mark.parametrize(
    "query",
    [
        "layout=2&charts=2",
        "layout=2&charts=true",
        "layout=2&charts=",
        "layout=2&charts=1&charts=1",
        "layout=1&charts=1",
        "charts=1",  # layout 쿼리가 없으면 판 1
    ],
)
def test_bad_charts_query_is_422(query):
    response = client.post(f"/parse?{query}", content=chart_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "bad_charts"


# ── 422 output_schema_invalid ────────────────────────────────────────


REAL_LABEL_CHARTS = parser.label_charts


def labels_without_words(doc, document):
    labels = REAL_LABEL_CHARTS(doc, document)
    del labels["words"]  # 스키마의 필수 칸
    return labels


def patched_in_child_with(patches, data, file_name, max_pages, *extra):
    """`test_http.patched_in_child` 와 같되 판·도표 라벨 인자를 그대로 넘긴다."""
    for dotted, value in patches:
        setattr(parser, dotted, value)
    return parser.decompose_to_json(data, file_name, max_pages, *extra)


def test_chart_labels_that_fail_their_schema_are_422_and_not_sent(monkeypatch):
    monkeypatch.setattr(
        parser, "CHILD_TARGET", partial(patched_in_child_with, (("label_charts", labels_without_words),))
    )
    response = client.post("/parse?layout=2&charts=1", content=chart_pdf(), headers=PDF)
    assert response.status_code == 422 and detail(response) == "output_schema_invalid"
    assert "Alpha" not in response.text


# ── 기본 길의 부르는 꼴 그대로 ───────────────────────────────────────


def record_target(log, data, file_name, max_pages, *extra):
    with open(log, "a", encoding="utf-8") as out:
        out.write(json.dumps(list(extra)) + "\n")
    return parser.decompose_to_json(data, file_name, max_pages, *extra)


def test_the_child_target_gets_charts_only_when_asked(monkeypatch, tmp_path):
    log = tmp_path / "target.log"
    monkeypatch.setattr(parser, "CHILD_TARGET", partial(record_target, str(log)))
    for query in ("", "?layout=2", "?layout=2&charts=1"):
        assert client.post(f"/parse{query}", content=chart_pdf(), headers=PDF).status_code == 200
    assert [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()] == [[], [2], [2, True]]


def record_decompose(log, *args, **kwargs):
    with open(log, "a", encoding="utf-8") as out:
        out.write(json.dumps([len(args), sorted(kwargs)]) + "\n")
    return REAL_DECOMPOSE(*args, **kwargs)


REAL_DECOMPOSE = parser.decompose


def test_decompose_is_called_as_before_even_with_charts(monkeypatch, tmp_path):
    """도표 라벨은 분해 함수의 인자로 들어가지 않는다(분해 뒤 같은 열린 문서로 따로 낸다)."""
    log = tmp_path / "decompose.log"
    monkeypatch.setattr(parser, "CHILD_TARGET", in_child({"decompose": partial(record_decompose, str(log))}))
    assert client.post("/parse", content=chart_pdf(), headers=PDF).status_code == 200
    monkeypatch.setattr(
        parser,
        "CHILD_TARGET",
        partial(patched_in_child_with, (("decompose", partial(record_decompose, str(log))),)),
    )
    assert client.post("/parse?layout=2&charts=1", content=chart_pdf(), headers=PDF).status_code == 200
    assert [json.loads(line) for line in Path(log).read_text(encoding="utf-8").splitlines()] == [
        [2, []],  # (path, opened)
        [3, []],  # (path, opened, layout)
    ]


# ── PDF 한 번 ─────────────────────────────────────────────────────────


def test_charts_do_not_open_the_pdf_again(monkeypatch):
    seen = []
    real = pdfium_engine.open_document

    def counting(path):
        seen.append(path)
        return real(path)

    monkeypatch.setattr(pdfium_engine, "open_document", counting)
    body = json.loads(parser.decompose_to_json(chart_pdf(), "x.pdf", 10, 2, True))
    assert list(body) == ["document", "charPlaces", "chartLabels"]
    assert len(seen) == 1, seen
