"""도표 라벨(밴드 CHL1 T1~T4·T8 의 파서 몫). 지어낸 쪽(`pdfbuild`)만 — 원본 PDF 를 읽지 않는다.

규칙(`docparse/charts.py`·`places.py`)은 esg-lab `py/docparse/` 의 것을 그대로 옮겼다. 여기의 쪽은 랩
`py/docparse/tests/test_charts.py` 의 지어낸 쪽을 이 저장소의 PDF 도구로 다시 그린 것이다.
「틀린 라벨은 없는 라벨보다 나쁘다」: 애매하면 붙이지 않고 까닭(`status`)을 남기는지를 본다.
"""

import json

import pytest
from jsonschema import Draft202012Validator

from docparse import charts
from docparse import document as document_module
from docparse.charts import _nearest_category, label_page
from docparse.cli import main as cli_main
from docparse.config import CHARTS_SCHEMA_PATH
from docparse.document import ParseError, label_charts, parse_opened_places, parse_pdf_charts, parse_pdf_places
from docparse.engine import open_pdf

from . import pdfbuild
from .conftest import seam

YELLOW, GREY = (0.97, 0.71, 0.0), (0.49, 0.45, 0.4)
SMALL = 6.5


def _page():
    doc = pdfbuild.Doc()
    return doc, doc.new_page(width=400, height=300)


def _bar(page, x, h, color, width=12):
    page.draw_rect((x, 200 - h, x + width, 200), fill=color, color=None)


def _chart_page(legend=True, same_color=False):
    """묶은 막대 도표 하나: 범주 Alpha·Beta 에 막대 둘씩, 막대 위에 값, (선택) 범례 Plan·Actual."""
    doc, page = _page()
    heights = {100: 60, 114: 50, 200: 70, 214: 55}
    for x, color in ((100, YELLOW), (114, GREY), (200, YELLOW), (214, YELLOW if same_color else GREY)):
        _bar(page, x, heights[x], color)
    page.draw_line((80, 200), (260, 200), color=(0.7, 0.7, 0.7), width=0.3)
    for text, x in (("16.2", 100), ("15.9", 114), ("16.4", 200), ("16.0", 214)):
        page.insert_text((x - 3, 200 - heights[x] - 3), text, fontsize=SMALL)
    page.insert_text((104, 212), "Alpha", fontsize=SMALL)
    page.insert_text((204, 212), "Beta", fontsize=SMALL)
    page.insert_text((80, 110), "Sample ratio", fontsize=9.5)
    if legend:
        for y, name, color in ((105, "Plan", YELLOW), (117, "Actual", GREY)):
            page.draw_rect((300, y - 5, 305, y), fill=color, color=None)
            page.insert_text((308, y), name, fontsize=SMALL)
    return doc, page


def _places(page):
    return [
        {"container": "p1-b1", "start": i, "end": i + 1, "text": w[4], "bbox": [round(v, 1) for v in w[:4]]}
        for i, w in enumerate(page.get_words())
    ]


def _label(page, **options):
    page = seam(page)
    return label_page(page, _places(page), **options)


def _values(page):
    found, words = _label(page)
    return found, {w["text"]: w for w in words if w["role"] == "value"}


# ── T1 묶은 막대: 값마다 범주·범례 계열, 눈금은 값 아님 ─────────────────────


def test_grouped_bars_get_category_from_the_axis_and_series_from_the_legend():
    found, values = _values(_chart_page()[1])
    assert len(found) == 1
    assert found[0]["title"] == "Sample ratio" and found[0]["categories"] == ["Alpha", "Beta"]
    assert values["16.2"]["label"] == {
        "title": "Sample ratio",
        "category": "Alpha",
        "status": "ok",
        "series": "Plan",
        "series_status": "ok",
    }
    assert (values["15.9"]["label"]["category"], values["15.9"]["label"]["series"]) == ("Alpha", "Actual")
    assert (values["16.0"]["label"]["category"], values["16.0"]["label"]["series"]) == ("Beta", "Actual")


def test_axis_ticks_and_numeric_categories_are_not_values():
    _doc, page = _page()
    for x, h in ((100, 60), (160, 40)):
        _bar(page, x, h, YELLOW)
    page.insert_text((99, 137), "61.5", fontsize=SMALL)
    page.insert_text((159, 157), "40.2", fontsize=SMALL)
    page.insert_text((99, 212), "2023", fontsize=SMALL)
    page.insert_text((159, 212), "2024", fontsize=SMALL)
    for text, y in (("0", 202), ("30", 172), ("60", 142)):
        page.insert_text((82 - pdfbuild.text_length(text, fontsize=SMALL), y), text, fontsize=SMALL)
    _found, words = _label(page)
    assert {w["text"]: w["role"] for w in words} == {
        "61.5": "value",
        "40.2": "value",
        "0": "tick",
        "30": "tick",
        "60": "tick",
        "2023": "category",
        "2024": "category",
    }
    assert next(w for w in words if w["text"] == "61.5")["label"]["category"] == "2023"


def test_a_value_much_nearer_one_category_is_labelled_but_a_closer_call_is_not():
    cats = [{"text": "Aa", "pos": 100.0}, {"text": "Bb", "pos": 116.0}]
    assert _nearest_category(101.0, cats) == ("Aa", "ok")
    assert _nearest_category(105.0, cats) == ("Aa", "ok")  # 5 대 11
    assert _nearest_category(107.0, cats) == (None, "between_categories")  # 7 대 9 — 붙이지 않는다
    assert _nearest_category(200.0, cats)[0] is None  # 축 밖
    assert _nearest_category(50.0, []) == (None, "no_category_axis")


# ── T2 애매하면 안 붙임 ─────────────────────────────────────────────


def test_value_halfway_between_two_categories_is_left_unlabelled():
    cats = [{"text": "Aa", "pos": 100.0}, {"text": "Bb", "pos": 116.0}]
    assert _nearest_category(108.5, cats) == (None, "between_categories")


def test_when_the_two_methods_disagree_no_category_is_given():
    # 값 글자가 옆 범주 쪽으로 밀려 있으면 좌표는 옆 범주를, 그림 요소는 제 막대의 범주를 낸다 → 합친 것은 붙이지 않는다
    _doc, page = _page()
    for x, h in ((100, 60), (130, 30)):
        _bar(page, x, h, YELLOW)
    page.insert_text((128, 137), "77.0", fontsize=SMALL)
    page.insert_text((128, 215), "9.0", fontsize=SMALL)
    page.insert_text((101, 212), "Aa", fontsize=SMALL)
    page.insert_text((131, 212), "Bb", fontsize=SMALL)
    _found, values = _values(page)
    word = values["77.0"]
    assert word["elem"]["category"] == "Aa" and word["coord"]["category"] == "Bb"
    assert word["label"]["category"] is None and word["label"]["status"] == "methods_disagree"


# ── T3 범례 색이 같은 두 계열 → 계열 안 붙임 ───────────────────────────


def test_legend_color_shared_by_two_names_gives_no_series():
    _doc, page = _page()
    for x, h in ((100, 60), (200, 70)):
        _bar(page, x, h, YELLOW)
    page.insert_text((97, 137), "16.2", fontsize=SMALL)
    page.insert_text((197, 127), "16.4", fontsize=SMALL)
    page.insert_text((104, 212), "Alpha", fontsize=SMALL)
    page.insert_text((204, 212), "Beta", fontsize=SMALL)
    for y, name in ((105, "Plan"), (117, "Actual")):
        page.draw_rect((300, y - 5, 305, y), fill=YELLOW, color=None)
        page.insert_text((308, y), name, fontsize=SMALL)
    _found, values = _values(page)
    assert values["16.2"]["label"]["series"] is None
    assert values["16.2"]["label"]["series_status"] == "legend_color_shared"
    assert values["16.2"]["label"]["category"] == "Alpha"


def test_no_legend_means_no_series_name():
    _found, values = _values(_chart_page(legend=False)[1])
    assert values["16.2"]["label"]["series"] is None
    assert values["16.2"]["label"]["series_status"] == "no_legend_for_color"
    assert values["16.2"]["label"]["category"] == "Alpha"


# ── T4 글 상자·괘선 표 칸 배경은 막대 아님 ─────────────────────────────


def test_text_boxes_are_not_bars():
    _doc, page = _page()
    for x, h in ((100, 20), (160, 30)):  # 표의 칸 배경처럼 글이 든 사각형
        page.draw_rect((x, 200 - h, x + 50, 200), fill=YELLOW, color=None)
        page.insert_text((x + 4, 195), "Header", fontsize=SMALL)
    page.insert_text((104, 212), "12", fontsize=SMALL)
    page.insert_text((164, 212), "34", fontsize=SMALL)
    assert _label(page)[0] == []


def _grid_page():
    """괘선 표의 숫자 칸 배경: 한 줄의 칸들은 밑변이 같고, 합친 칸은 높이가 달라 「밑선이 같고 높이가 다른 사각형」."""
    doc, page = _page()
    for x, top in ((100, 160), (160, 180), (220, 180)):
        page.draw_rect((x, top, x + 60, 200), fill=(1.0, 0.96, 0.88), color=None)
        page.insert_text((x + 20, 195), "7.5", fontsize=SMALL)
    for y in (160, 180, 200):
        page.draw_line((40, y), (300, y), color=(0.6, 0.6, 0.6), width=0.3)
    for i, name in enumerate(("Aa", "Bb", "Cc")):
        page.insert_text((120 + 60 * i, 212), name, fontsize=SMALL)
    return doc, page


def test_cell_backgrounds_between_table_rules_are_not_bars():
    assert _label(_grid_page()[1])[0] == []
    assert len(_label(_grid_page()[1], grid_rule=False)[0]) == 1  # 규칙을 끄면 칸 배경이 막대로 읽힌다
    assert len(_label(_chart_page()[1])[0]) == 1  # 막대는 밑변만 축선에 닿는다 → 그대로 도표다


# ── 문서 입구: 판 2 만, 같은 열린 PDF, 스키마 ─────────────────────────


def _chart_pdf(tmp_path):
    pdf = tmp_path / "chart.pdf"
    pdf.write_bytes(_chart_page()[0].tobytes())
    return pdf


def _schema_errors(labels):
    schema = json.loads(CHARTS_SCHEMA_PATH.read_text(encoding="utf-8"))
    return [e.message for e in Draft202012Validator(schema).iter_errors(labels)]


def test_document_labels_pass_the_schema_and_carry_a_copy_of_the_source(tmp_path):
    pdf = _chart_pdf(tmp_path)
    with open_pdf(pdf) as doc:
        document, _places = parse_opened_places(doc, pdf, layout=2)
        labels = label_charts(doc, document)
    assert _schema_errors(labels) == []
    assert labels["source"] == document["source"] and labels["source"] is not document["source"]
    assert labels["llm_used"] is False and labels["ocr_used"] is False
    values = [w for w in labels["words"] if w["role"] == "value"]
    assert {w["label"]["category"] for w in values} == {"Alpha", "Beta"}
    assert all(w["container"] for w in values)  # 낱말은 문서 모델의 그릇에 걸린다
    assert "places" not in labels  # 낱말 자리(수 MB)는 싣지 않는다


def test_labels_are_only_for_the_layout_2_model(tmp_path):
    pdf = _chart_pdf(tmp_path)
    with open_pdf(pdf) as doc:
        document, _places = parse_opened_places(doc, pdf)
        with pytest.raises(ParseError):
            label_charts(doc, document)


def test_the_path_entrance_gives_the_same_model_as_without_charts(tmp_path):
    """도표 라벨을 켜도 문서 모델·글자 자리는 판 2 의 것과 같다(라벨은 곁 산출)."""
    pdf = _chart_pdf(tmp_path)
    document, places, labels = parse_pdf_charts(pdf)
    assert (document, places) == parse_pdf_places(pdf, layout=2)
    with open_pdf(pdf) as doc:
        assert labels == label_charts(doc, document)


def test_the_rules_are_the_lab_thresholds():
    """문턱은 랩 그대로다(바꾸면 KB W 채점·G1 두 권을 다시 재고 EPOCH 를 올린다 — 발주서 CHL1 Directive)."""
    assert (charts.SWATCH_MAX, charts.MARKER_MAX, charts.DATA_LINE_MIN_WIDTH, charts.LEADER_MAX) == (
        8.5,
        9.0,
        0.9,
        45.0,
    )
    assert (charts.EDGE, charts.VALUE_MARK_MAX, charts.SAME_PLACE, charts.NEAR_RATIO) == (0.8, 30.0, 1.5, 0.6)
    assert (charts.FRAME_MIN, charts.TITLE_MAX) == ((100.0, 50.0), 40)


# ── 명령줄 `parse --charts`(판 2 에만, 스키마 검사) ─────────────────────────


def test_the_cli_writes_chart_labels_beside_the_unchanged_model(tmp_path, capsys):
    pdf = _chart_pdf(tmp_path)
    plain, charted = tmp_path / "plain", tmp_path / "charted"
    assert cli_main(["parse", str(pdf), "--out", str(plain), "--layout", "2", "--places"]) == 0
    capsys.readouterr()
    assert cli_main(["parse", str(pdf), "--out", str(charted), "--layout", "2", "--places", "--charts"]) == 0
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_valid"] is True and summary["chart_labels"]["charts"] == 1
    labels = json.loads((charted / "chart-labels.json").read_text(encoding="utf-8"))
    assert _schema_errors(labels) == []
    assert {w["label"]["category"] for w in labels["words"] if w["role"] == "value"} == {"Alpha", "Beta"}
    for name in ("document.json", "char-places.json"):  # 곁 파일 둘은 --charts 와 무관하게 같은 글자
        assert (charted / name).read_bytes() == (plain / name).read_bytes()
    assert not (plain / "chart-labels.json").exists()


def test_the_cli_refuses_charts_off_layout_2_and_flags_a_schema_miss(tmp_path, capsys, monkeypatch):
    pdf = _chart_pdf(tmp_path)
    assert cli_main(["parse", str(pdf), "--out", str(tmp_path / "one"), "--charts"]) == 2
    assert not (tmp_path / "one").exists()
    real = document_module.label_charts

    def without_place_count(doc, model):
        labels = real(doc, model)
        del labels["place_count"]  # 스키마의 필수 칸
        return labels

    monkeypatch.setattr(document_module, "label_charts", without_place_count)
    assert cli_main(["parse", str(pdf), "--out", str(tmp_path / "bad"), "--layout", "2", "--charts"]) == 1
    summary = json.loads(capsys.readouterr().out)
    assert summary["schema_valid"] is False
    assert any(e.startswith("chart-labels: ") for e in summary["schema_errors"])
