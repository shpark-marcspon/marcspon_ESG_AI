"""흐름 extract 의 글자 층 없음 갈래(밴드 G1b, Q6): 모든 쪽의 글이 공백뿐이면 NoTextLayer, 실행기의 고정 표가 그것을
no_text_layer 로 접는다. 글 있는 쪽이 하나라도 있으면 지나간다. 순수 층 — PDF 는 tests/pdfbuild.py 로 지은 것.
"""

import pytest

from esgapi.core.flows.types import FlowStepFailed, StepContext
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.tests import pdfbuild
from esgapi.greenwash.tests.flows import support as s
from esgapi.runs.calc.errors import RUN_ERROR_MESSAGES, step_error_code


def blank_pdf(pages: int = 2) -> bytes:
    doc = pdfbuild.Doc()
    for _ in range(pages):
        doc.new_page()
    return doc.tobytes()


def text_pdf() -> bytes:
    doc = pdfbuild.Doc()
    doc.new_page()
    doc.new_page().insert_text((72, 72), "Synthetic page with text")  # pyright: ignore[reportUnknownMemberType]
    return doc.tobytes()


def inputs_of(pdf: bytes) -> colab.GreenwashInputs:
    return colab.GreenwashInputs(
        document=pdf, media_type="application/pdf", file_name="synthetic.pdf", ceo="1", company="", climate="2"
    )


def test_a_pdf_without_any_text_fails_in_extract_with_no_text_layer() -> None:
    forbidden = s.Forbidden()
    used = colab.GreenwashAdapters(pdf_text=colab.PDF_TEXT(), llm=forbidden, embedding=forbidden)
    assert colab.PDF_TEXT().page_texts(blank_pdf()) == ["", ""]  # 분모: 쪽은 둘, 글은 없다
    with pytest.raises(FlowStepFailed) as failed:
        s.run(inputs_of(blank_pdf()), used)
    assert failed.value.step == "extract"
    assert isinstance(failed.value.__cause__, colab.NoTextLayer)
    assert forbidden.calls == 0
    assert step_error_code(type(failed.value.__cause__)) == "no_text_layer"
    assert "no_text_layer" in RUN_ERROR_MESSAGES


@pytest.mark.parametrize("texts", [["", "  \n\t "], [], ["　"]])
def test_whitespace_only_pages_are_no_text(texts: list[str]) -> None:
    with pytest.raises(FlowStepFailed) as failed:
        s.run(s.inputs(), s.adapters(pdf=s.SamplePdf(texts)))
    assert isinstance(failed.value.__cause__, colab.NoTextLayer)


def test_one_page_with_text_is_enough() -> None:
    pdf = text_pdf()
    assert colab.PDF_TEXT().page_texts(pdf)[0] == ""  # 분모: 첫 쪽은 비었다
    used = colab.GreenwashAdapters(pdf_text=colab.PDF_TEXT(), llm=s.Forbidden(), embedding=s.Forbidden())
    out = colab.extract(inputs_of(pdf), used, {}, StepContext(resume=None))
    assert out.data["page_count"] == 2
