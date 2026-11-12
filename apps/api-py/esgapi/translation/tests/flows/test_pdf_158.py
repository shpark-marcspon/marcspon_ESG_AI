"""흐름 translation.pdf@158(flows/pdf_158.py — 밴드 TRD2 F1·F2·F4 의 순수 층). 가짜 파서(core FakeParser — 지어낸
분해 판 2 문서)와 모의 공급사로 끝까지 돈다. 실호출 0 · 파서 HTTP 0.

F1 PDF → done · 결과 셋(result@1·digest@1·layout@1 strict) · 파서가 받은 layout 2 · result@1·Word 이름이 태그 글을 글
   문서로 넣은 워드 흐름과 같음 · versions 의 input·adapter·parserLayout.
F2 거절·실패(G5): PDF 아님·파서 rejected → unsupported_input(쪽 번호 0) · 파서 뒤 거절(too_large·over_budget)은
   태그 글의 쪽 번호 · unavailable → RunRetryLater · invalid_response·옛 파서·ParserSetupError → 단계 예외 · 전 쪽
   이미지 → NoTextLayer · layout@1 꼴이 틀리면 FlowOutputError · 쪽 범위가 어댑터·엔진에 같이 감.
F4 워드 흐름 그대로: 기본 흐름 colab · 워드 흐름은 여전히 PDF 를 거절.
"""

from typing import Any

import pytest

from esgapi.core.flows.binding import RunRetryLater
from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import FlowOutputError, FlowStepFailed, NoTextLayer
from esgapi.core.resources import parser as parsers
from esgapi.core.resources.parser import ParserSetupError
from esgapi.core.tests.resource_fakes import FakeParser
from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE, LAYOUT_SHAPES
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows import pdf_158 as pdf
from esgapi.translation.flows import registration
from esgapi.translation.tests import docx_support
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.pdf_support import (
    ONE_PAGE_EN,
    PDF,
    block,
    document,
    failed,
    parsed,
    pdf_binding,
    results_of,
    run_pdf,
)
from esgapi.translation.tests.flows.support import options, result_of, run_options
from esgapi.translation.tools import pdf_tags
from esgapi.translation.tools.pdf_tags import ADAPTER_VERSION

NO_ISSUES = ok("[]")


def done() -> Any:
    return run_pdf(options(), [ok(ONE_PAGE_EN), NO_ISSUES])


def failure(*args: Any, **kwargs: Any) -> BaseException | None:
    with pytest.raises(FlowStepFailed) as caught:
        run_pdf(*args, **kwargs)
    assert caught.value.step == "prepare"
    return caught.value.__cause__


# ── F1 ──


def test_a_pdf_runs_to_three_strict_results() -> None:
    ran = done()
    result, summary, layout = results_of(ran)
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(layout, strict=True)
    assert (result["status"], summary["status"], layout["status"]) == ("done", "done", "done")
    assert ran.parser.layouts == [2] and [name for _, name in ran.parser.calls] == [pdf.PARSER_FILE_NAME]
    assert layout["sourceSha256"] == result["document"]["sourceSha256"]
    assert layout["source"]["parser"] == {"name": "docparse", "version": "0.0-virtual", "layout": 2}
    (variant,) = layout["variants"]
    assert (result["variants"][0]["autofix"]["status"], variant["stage"]) == ("done", "autofix")
    assert [(u["tag"], u["level"]) for u in variant["units"]] == [("BLOCK 1", "block"), (None, "source_only")]
    assert variant["units"][0]["translations"] == [
        "Water stewardship",
        "The virtual site cut its water use by 12 percent.",
    ]
    assert variant["unplaced"] == [] and layout["warnings"] == []


def test_the_engine_sees_the_tagged_text_like_a_text_document() -> None:
    """같은 태그 글을 글 문서로 넣은 워드 흐름과 result@1 이 같고 Word 이름도 같다(엔진·사슬 그대로)."""
    ran = done()
    tagged = ran.run.steps["prepare"].data["pdf"]["tagged"]
    assert tagged == "[PAGE 1]\n\n[BLOCK 1]\n물 관리\n\n가상 사업장은 물 사용량을 12% 줄였다.\n"
    word = run_options(options(), [ok(ONE_PAGE_EN), NO_ISSUES], text=tagged)
    assert results_of(ran)[0] == result_of(word)
    assert [f.name for f in ran.run.output.files] == [f.name for f in word.run.output.files]


def test_the_prepare_output_carries_the_pdf_map_and_the_versions_name_the_input() -> None:
    data = done().run.steps["prepare"].data
    assert set(data["pdf"]) == {
        "pdfSha256",
        "pageCount",
        "parser",
        "adapter",
        "pages",
        "tagged",
        "units",
        "skipped",
        "warnings",
    }
    assert data["rejection"] is None and data["pdf"]["adapter"] == ADAPTER_VERSION
    versions = pdf_binding(FakeParser()).versions(options())
    assert {k: versions[k] for k in ("flow", "input", "adapter", "parserLayout")} == {
        "flow": pdf.FLOW_ID,
        "input": "pdf",
        "adapter": ADAPTER_VERSION,
        "parserLayout": 2,
    }


def pdf_data(doc: dict[str, Any]) -> dict[str, Any]:
    """prepare 의 pdf 칸(파서 0 — 지어낸 문서를 어댑터에 바로)."""
    tagged = pdf_tags.build(doc, None, page_start=None, page_end=None)
    return {
        "pdfSha256": "1" * 64,
        "pageCount": len(doc["pages"]),
        "parser": {"name": "docparse", "version": "0.0-virtual", "layout": 2},
        "adapter": ADAPTER_VERSION,
        "pages": tagged.pages,
        "tagged": tagged.text,
        "units": tagged.units,
        "skipped": tagged.skipped,
        "warnings": tagged.warnings,
    }


def a_variant(label: str, translated: str, autofixed: str | None) -> dict[str, Any]:
    autofix = (
        {"status": "done", "translatedText": autofixed}
        if autofixed is not None
        else {
            "status": "not_run",
            "translatedText": None,
        }
    )
    return {"label": label, "translatedText": translated, "autofix": autofix}


def test_the_layout_takes_the_autofix_text_when_done_and_the_translation_otherwise() -> None:
    data = pdf_data(document())
    text = f"[PAGE 1]\n{ONE_PAGE_EN}"  # 엔진 번역 글은 쪽 머리 태그를 품는다
    fixed = text.replace("12 percent", "twelve percent")
    result = {
        "status": "done",
        "document": {"sourceSha256": "0" * 64},
        "variants": [a_variant("A", text, fixed), a_variant("B", text, None)],
    }
    made = pdf.layout(result, data)
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(made, strict=True)
    a, b = made["variants"]
    assert (a["label"], a["stage"], b["label"], b["stage"]) == ("A", "autofix", "B", "translated")
    assert a["units"][0]["translations"][1] == "The virtual site cut its water use by twelve percent."
    assert b["units"][0]["translations"][1] == "The virtual site cut its water use by 12 percent."


def test_the_layout_carries_placing_warnings_with_their_variant_and_build_warnings_without() -> None:
    doc = document(pages=2)
    doc["pages"][1]["text_layer"] = "none"  # 2쪽 글자 층 없음 — 어댑터 경고 image_only_page
    data = pdf_data(doc)
    result = {
        "status": "done",
        "document": {"sourceSha256": "0" * 64},
        "variants": [  # B 는 태그만 남고 글이 빠짐
            a_variant("A", f"[PAGE 1]\n{ONE_PAGE_EN}", None),
            a_variant("B", "[PAGE 1]\n[BLOCK 1]\n", None),
        ],
    }
    made = pdf.layout(result, data)
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(made, strict=True)
    assert made["warnings"] == [
        {"code": "image_only_page", "page": 2, "tag": None, "variant": None},
        {"code": "tag_missing", "page": 1, "tag": "BLOCK 1", "variant": "B"},
    ]
    assert made["variants"][1]["units"][0]["level"] == "missing"


def line_document() -> dict[str, Any]:
    """1쪽 한 단: 파서가 줄 하나씩 준 가상 문단 둘(줄 높이 8.8 · 줄 틈 5.1 · 문단 끝 줄은 짧음 — 밴드 TRS5 L7)."""
    texts = [
        [
            "가상 사업장의 올해 물 사용량은 지난해보다",
            "12% 줄었고 재이용 설비가 그 몫을 맡았으며",
            "다음 해에도 이어진다.",
        ],
        ["가상 사업장의 에너지 사용량은 원단위로 보아", "조금 줄었다."],
    ]
    blocks: list[dict[str, Any]] = []
    top, order = 100.0, 0
    for para in texts:
        for n, text in enumerate(para):
            order += 1
            right = 280.0 if n < len(para) - 1 else 200.0
            blocks.append(block(1, order, text, [40, top, right, top + 8.8]) | {"font_size": 7.7})
            top += 13.9
        top += 5.7
    doc = document()
    doc["blocks"] = blocks
    return doc


def test_lines_of_a_paragraph_become_one_member_and_the_layout_stays_strict() -> None:
    doc = line_document()
    data = pdf_data(doc)
    (unit,) = data["units"]
    assert [m["id"] for m in unit["members"]] == ["p1-b1", "p1-b4"]  # 줄 다섯 → 멤버 둘
    body = "\n\n".join(m["source"] for m in unit["members"])
    text = f"[PAGE 1]\n[BLOCK 1]\n{body}"
    result = {"status": "done", "document": {"sourceSha256": "0" * 64}, "variants": [a_variant("A", text, None)]}
    made = pdf.layout(result, data)
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(made, strict=True)
    (variant,) = made["variants"]
    assert [(u["tag"], u["level"]) for u in variant["units"]] == [("BLOCK 1", "block")]
    assert made["warnings"] == [] and variant["unplaced"] == []


def test_a_unit_re_paragraphed_before_a_dropped_last_tag_is_grouped_with_a_shift() -> None:
    """밴드 TRS5 S5: 모의 번역이 끝 BLOCK 2(오른 단 서명) 태그 줄을 빠뜨려 그 글이 BLOCK 1 끝에 붙음 → TRS6 부터는
    BLOCK 1 몸 문단 수(3) = 멤버 2 + 1 이라 꼬리 문단을 BLOCK 2 로 되살린다(둘 다 block · 둘 다 tag_shift)."""
    doc = document()
    doc["blocks"].append(block(1, 4, "가상 서명", [400, 700, 480, 712]))
    data = pdf_data(doc)
    assert [u["tag"] for u in data["units"] if u["tag"]] == ["BLOCK 1", "BLOCK 2"]
    text = f"[PAGE 1]\n{ONE_PAGE_EN}\n\nVirtual signature"
    result = {"status": "done", "document": {"sourceSha256": "0" * 64}, "variants": [a_variant("A", text, None)]}
    made = pdf.layout(result, data)
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(made, strict=True)
    (variant,) = made["variants"]
    levels = [(u["tag"], u["level"]) for u in variant["units"]]
    assert levels == [("BLOCK 1", "block"), ("BLOCK 2", "block"), (None, "source_only")]
    assert variant["unplaced"] == []
    assert {"code": "tag_shift", "page": 1, "tag": "BLOCK 1", "variant": "A"} in made["warnings"]
    assert {"code": "tag_shift", "page": 1, "tag": "BLOCK 2", "variant": "A"} in made["warnings"]


def test_a_dropped_last_tag_merged_into_the_paragraph_before_is_still_grouped_with_a_shift() -> None:
    """S5 의 옛 길(TRS6): 모의 번역이 끝 BLOCK 2 태그 줄을 빠뜨리고 서명까지 BLOCK 1 과 한 문단으로 냄 → 문단 수가
    안 맞아 되살리지 않고 지금처럼 BLOCK 1 group · tag_shift, BLOCK 2 missing."""
    doc = document()
    doc["blocks"].append(block(1, 4, "가상 서명", [400, 700, 480, 712]))
    data = pdf_data(doc)
    merged = " ".join(ONE_PAGE_EN.removeprefix("[BLOCK 1]\n").split("\n\n"))
    text = f"[PAGE 1]\n[BLOCK 1]\n{merged} Virtual signature"
    result = {"status": "done", "document": {"sourceSha256": "0" * 64}, "variants": [a_variant("A", text, None)]}
    made = pdf.layout(result, data)
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(made, strict=True)
    (variant,) = made["variants"]
    levels = [(u["tag"], u["level"]) for u in variant["units"]]
    assert levels == [("BLOCK 1", "group"), ("BLOCK 2", "missing"), (None, "source_only")]
    assert variant["unplaced"] == []
    assert {"code": "tag_shift", "page": 1, "tag": "BLOCK 1", "variant": "A"} in made["warnings"]


# ── F2 ──


def rejected(ran: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    result, _, layout = results_of(ran)
    assert (result["status"], layout["status"], layout["variants"]) == ("rejected", "rejected", [])
    LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(layout, strict=True)
    return result, layout


@pytest.mark.parametrize(
    "content",
    [docx_support.built(lambda d: d.add_paragraph("가상 문단")), "가상 글".encode(), b""],
    ids=["docx", "txt", "empty"],
)
def test_a_document_that_is_not_a_pdf_is_unsupported_before_the_parser(content: bytes) -> None:
    ran = run_pdf(options(), content=content)
    result, layout = rejected(ran)
    assert result["rejection"]["kind"] == "unsupported_input"
    assert result["document"]["pageNumbers"] == [] and ran.parser.calls == []
    assert layout["source"]["parser"] is None and layout["units"] == []


def test_a_parser_rejection_is_unsupported_with_its_code_only() -> None:
    ran = run_pdf(options(), result=failed("rejected", "password_protected", 422))
    result, layout = rejected(ran)
    assert result["rejection"]["kind"] == "unsupported_input"
    assert "password_protected" in result["rejection"]["message"] and "가짜 파서" not in result["rejection"]["message"]
    assert result["document"]["pageNumbers"] == [] and ran.parser.layouts == [2]
    assert layout["source"]["pageCount"] is None


def test_a_rejection_after_the_parser_keeps_the_page_numbers_of_the_tagged_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(colab, "MAX_SOURCE_CHARS", 10)
    result, layout = rejected(run_pdf(options()))
    assert (result["rejection"]["kind"], result["document"]["pageNumbers"]) == ("too_large", [1])
    assert [u["tag"] for u in layout["units"]] == ["BLOCK 1", None] and layout["source"]["pageCount"] == 1


def test_an_estimate_over_the_budget_is_over_budget_with_no_call() -> None:
    ran = run_pdf(options(), max_usd=0.0001)
    result, _ = rejected(ran)
    assert result["rejection"]["kind"] == "over_budget" and ran.openai.calls == []


@pytest.mark.parametrize("code", ["busy", None])
def test_an_unavailable_parser_asks_for_a_later_attempt(code: str | None) -> None:
    cause = failure(options(), result=failed("unavailable", code, 503 if code else None))
    assert isinstance(cause, RunRetryLater)


def test_an_invalid_response_or_an_old_parser_is_a_step_error() -> None:
    assert isinstance(failure(options(), result=failed("invalid_response", None, 200)), pdf.PdfFlowError)
    assert isinstance(failure(options(), result=parsed(document(layout=1))), pdf.PdfFlowError)


def test_a_parser_without_its_address_is_a_step_error() -> None:
    def unset() -> Any:
        return parsers.make("http", base_url=None, timeout_s=210.0)

    with pytest.raises(FlowStepFailed) as caught:
        run_pdf(options(), parser_factory=unset)
    assert isinstance(caught.value.__cause__, ParserSetupError)


def test_a_range_of_image_only_pages_has_no_text_layer() -> None:
    assert isinstance(failure(options(), result=parsed(document(layer="none"))), NoTextLayer)


def test_a_layout_out_of_its_shape_is_a_flow_output_error(monkeypatch: pytest.MonkeyPatch) -> None:
    real = pdf.layout

    def extra(result: Any, data: Any) -> dict[str, Any]:
        return {**real(result, data), "extra": 1}

    monkeypatch.setattr(pdf, "layout", extra)
    with pytest.raises(FlowStepFailed) as caught:
        done()
    assert caught.value.step == "report" and isinstance(caught.value.__cause__, FlowOutputError)


def test_the_page_range_reaches_the_adapter_and_the_engine() -> None:
    reply = "[BLOCK 1]\nWater stewardship\n\nThe virtual site cut its water use by 2 percent."
    ran = run_pdf(options(pages={"start": 2, "end": 2}), [ok(reply), NO_ISSUES], result=parsed(document(pages=3)))
    result, _, layout = results_of(ran)
    assert result["document"]["pageNumbers"] == [2]
    assert {u["page"] for u in layout["units"]} == {2} and [p["page"] for p in layout["pages"]] == [2]
    assert layout["variants"][0]["units"][0]["level"] == "block"


# ── F4 ──


def test_the_word_flow_stays_the_default_and_still_refuses_a_pdf() -> None:
    registry = FlowRegistry()
    registration.register(registry)
    assert registry.default_of("translation").id == colab.FLOW_ID
    assert {f.id for f in registry.flows_of("translation")} == {colab.FLOW_ID, pdf.FLOW_ID}
    word = result_of(run_options(options(), content=PDF))
    assert (word["status"], word["rejection"]["kind"]) == ("rejected", "unsupported_input")
