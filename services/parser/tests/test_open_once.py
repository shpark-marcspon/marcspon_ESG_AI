"""PDF 는 자식 안에서 한 번만 연다(밴드 PX2 ⑦, 결함 D4 의 「두 번 엶」).

자식이 부르는 `decompose_to_json` 은 암호·쪽 수를 보려고 연 문서를 그대로 분해에 넘긴다. 여기서는 그 함수를 이
프로세스에서 직접 부르고, 엔진이 문서를 여는 횟수를 센다. 열린 문서를 받는 입구(`parse_opened_places`)의 산출은
경로 입구(`parse_pdf_places`)와 같아야 하고, PB1 의 고정 해시와도 같아야 한다.
"""

import json

import pytest

import app as parser
from docparse.document import ParseError, parse_opened_places, parse_pdf_places
from docparse.engine import open_pdf, pdfium_engine

from . import baseline_doc, pdfbuild
from .test_baseline import FIXED, VARIANTS, pb


def two_page_pdf():
    doc = pdfbuild.Doc()
    doc.new_page().insert_text((40, 60), "First page 12.5")
    doc.new_page().insert_text((40, 60), "Second page")
    return doc.tobytes()


@pytest.fixture
def opened_count(monkeypatch):
    seen = []
    real = pdfium_engine.open_document

    def counting(path):
        seen.append(path)
        return real(path)

    monkeypatch.setattr(pdfium_engine, "open_document", counting)
    return seen


def test_the_child_opens_the_pdf_once(opened_count):
    body = json.loads(parser.decompose_to_json(two_page_pdf(), "x.pdf", 10))
    assert set(body) == {"document", "charPlaces"}
    assert len(opened_count) == 1, opened_count


def test_rejections_before_decomposing_open_it_once_too(opened_count):
    with pytest.raises(parser.Rejected) as caught:
        parser.decompose_to_json(two_page_pdf(), "x.pdf", 1)
    assert caught.value.code == "too_many_pages"
    assert len(opened_count) == 1


def test_the_opened_entrance_leaves_closing_to_the_caller(tmp_path):
    pdf = tmp_path / "a.pdf"
    pdf.write_bytes(two_page_pdf())
    with open_pdf(pdf) as doc:
        parse_opened_places(doc, pdf)
        assert len(doc) == 2  # 아직 열려 있다


def test_the_opened_entrance_refuses_a_locked_document(tmp_path):
    pdf = tmp_path / "locked.pdf"
    doc = pdfbuild.Doc()
    doc.new_page().insert_text((40, 60), "Secret")
    pdf.write_bytes(doc.tobytes(user_pw="user", owner_pw="owner"))
    with open_pdf(pdf) as opened, pytest.raises(ParseError):
        parse_opened_places(opened, pdf)


@pytest.mark.parametrize("variant", VARIANTS)
def test_the_opened_entrance_matches_the_frozen_baseline(variant, tmp_path):
    """새 입구도 PB1 고정값과 같다(검증 감독 알림 ①). 경로 입구와도 바이트로 같다."""
    pdf = tmp_path / f"{variant}.pdf"
    pdf.write_bytes(baseline_doc.build(**baseline_doc.VARIANTS[variant]))
    with open_pdf(pdf) as doc:
        document, places = parse_opened_places(doc, pdf)
    assert places is not None
    diff = pb.differing(pb.hashes(document, places), FIXED["variants"][variant])
    assert not diff, f"{variant}: 기준선과 다른 부분 = {', '.join(diff)}"
    assert (document, places) == parse_pdf_places(pdf)
