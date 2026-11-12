"""흐름 translation.pdf@158(밴드 TRD2, 결정 MARC-ENT-471): PDF 문서 → 파서(분해 판 2) → 태그 글(tools/pdf_tags) →
1차 흐름 translation.colab@158 의 단계 셋 그대로 → translation.result@1·digest@1 + 셋째 결과 translation.layout@1.

엔진·워드 흐름은 0줄이다(MARC-ENT-442) — 이 흐름은 입력 경로를 더할 뿐(새 엔진 아님, MARC-ENT-465).
단계마다 `dataclasses.replace(inputs, document=<태그 글 UTF-8>)` 로 colab 의 단계 함수를 그대로 부른다(그 함수들은
inputs.document 를 글로 다시 읽는다).

    prepare    `%PDF-` 아니면 unsupported_input(파서 0) → 파서 parse(layout=2):
                 rejected(4xx — not_a_pdf·password_protected·too_many_pages·too_large·parse_timeout·bad_layout …)
                     → unsupported_input(문장에 code 만)
                 unavailable(503 busy·연결 실패·시간 초과) → core RunRetryLater(실행기가 같은 실행을 다시 넣는다)
                 invalid_response·응답 parser.layout != 2(옛 파서)·ParserSetupError → 단계 예외(step_error)
               → 범위 안 쪽이 모두 글자 층 없음 → core NoTextLayer → pdf_tags.build(PdfTagsError 는 단계 예외)
               → colab.prepare 그대로. 산출에 `pdf` 칸 {pdfSha256, pageCount, parser, adapter, pages, tagged, units,
               skipped, warnings}. 거절 길(파서 앞·파서)은 tagged "" 를 싣는다(translate 의 쪽 번호 0).
               파서는 늘 전 쪽을 분해한다(HTTP 에 쪽 범위 없음) — 실패 쪽만 다시도 매번 다시 분해한다.
    translate  colab.translate 그대로(document = pdf.tagged). sourceSha256 = 태그 글 sha 라 실패 쪽만 다시는 같은
               PDF·쪽 범위·어댑터 판일 때만 지난다.
    report     colab.report 그대로(result@1 strict·Word·digest@1) + layout@1(strict — 못 지나면 FlowOutputError).
               문체마다 글 = 자동수정 done 이면 autofix.translatedText, 아니면 translatedText → 쪽 조각
               → pdf_tags.place.
"""

import dataclasses
import hashlib
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from pydantic import ValidationError

from esgapi.core.flows.binding import RunRetryLater
from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, FlowOutputError, FlowStep, NoTextLayer, StepContext, StepOutput
from esgapi.core.resources.ports.parser import DocumentParser, ParseFailed
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.translation.contracts.layout_shapes import LAYOUT_SHAPE, LAYOUT_SHAPES
from esgapi.translation.contracts.shapes import RESULT_SHAPE
from esgapi.translation.engines.colab_158.pages import pages_to_map_merge, parse_pages
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows.colab_158 import TranslationAdapters, TranslationRunInputs
from esgapi.translation.tools import pdf_tags

FLOW_ID: Final = "translation.pdf@158"
INPUT_SHAPE: Final = "translation.pdf-run@1"
"""흐름 입력의 이름표(translation.run@1 과 같은 칸 — 문서가 PDF 바이트)."""
PARSER_LAYOUT: Final = 2
PARSER_FILE_NAME: Final = "document.pdf"
"""파서에 넘기는 파일 이름(파서 산출의 source.file_name 에만 실린다 — 실행 문서의 이름은 싣지 않는다)."""


class PdfFlowError(Exception):
    """파서 산출을 쓸 수 없다(invalid_response·옛 파서 판). 단계 예외(step_error)로 둔다."""


@dataclass(frozen=True, slots=True, kw_only=True)
class PdfAdapters(TranslationAdapters):
    """워드 흐름의 어댑터 + 파서를 만드는 함수(끼움이 싣는다 — apps.py 가 설정으로 꽂은 것). 부를 때 지으므로 설정
    오류(ParserSetupError)는 prepare 의 단계 예외다."""

    parser: Callable[[], DocumentParser]


# ── prepare ──


def _pdf_data(pdf_sha256: str, **given: object) -> dict[str, object]:
    return {
        "pdfSha256": pdf_sha256,
        "pageCount": given.get("pageCount"),
        "parser": given.get("parser"),
        "adapter": pdf_tags.ADAPTER_VERSION,
        "pages": given.get("pages", []),
        "tagged": given.get("tagged", ""),
        "units": given.get("units", []),
        "skipped": given.get("skipped", {"emptyTables": [], "imageOnlyPages": []}),
        "warnings": given.get("warnings", []),
    }


def _refused(pdf_sha256: str, message: str) -> StepOutput:
    """파서 앞·파서의 거절 — 태그 글 없음(sourceSha256 = 빈 글, 워드 흐름의 unsupported_input 과 같은 꼴)."""
    out = colab.prepared(colab.rejection("unsupported_input", message), colab.sha256_of(""))
    return StepOutput(data={**out.data, "pdf": _pdf_data(pdf_sha256)})


def _parser_info(document: Mapping[str, Any]) -> dict[str, object]:
    parser = cast("Mapping[str, Any]", document.get("parser", {}))
    if parser.get("layout") != PARSER_LAYOUT:
        raise PdfFlowError(f"파서 산출의 분해 판이 {PARSER_LAYOUT} 이 아니다(옛 파서 이미지일 수 있다)")
    return {"name": parser["name"], "version": parser["version"], "layout": PARSER_LAYOUT}


def prepare(inputs: TranslationRunInputs, adapters: PdfAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    """머리말 prepare. 공급사 호출 0(파서 한 번 + 다리의 dry_run)."""
    pdf = inputs.document
    pdf_sha256 = hashlib.sha256(pdf).hexdigest()
    if not pdf.startswith(b"%PDF-"):
        return _refused(pdf_sha256, "PDF 흐름은 PDF 만 받아요 — Word(docx)·글은 기본 번역으로 올려 주세요")
    parsed = adapters.parser().parse(pdf, file_name=PARSER_FILE_NAME, layout=PARSER_LAYOUT)
    if isinstance(parsed, ParseFailed):
        if parsed.kind == "rejected":
            return _refused(pdf_sha256, f"PDF 를 읽지 못했어요({parsed.detail.code or '파서 거절'})")
        if parsed.kind == "unavailable":
            raise RunRetryLater(f"파서를 지금 쓸 수 없다(상태 {parsed.detail.status}, code {parsed.detail.code})")
        raise PdfFlowError(f"파서 응답이 약속한 꼴이 아니다: {parsed.detail.message}")
    document = parsed.document
    parser = _parser_info(document)
    tagged = pdf_tags.build(document, parsed.char_places, page_start=inputs.page_start, page_end=inputs.page_end)
    if tagged.pages and all(p["textLayer"] != "present" for p in tagged.pages):
        raise NoTextLayer("쪽 범위 안의 모든 쪽에 글자 층이 없다")
    out = colab.prepare(dataclasses.replace(inputs, document=tagged.text.encode("utf-8")), adapters, carried, ctx)
    pdf_data = _pdf_data(
        pdf_sha256,
        pageCount=document["source"]["page_count"],
        parser=parser,
        pages=tagged.pages,
        tagged=tagged.text,
        units=tagged.units,
        skipped=tagged.skipped,
        warnings=tagged.warnings,
    )
    return StepOutput(data={**out.data, "pdf": pdf_data})


def _pdf(carried: Carried) -> Mapping[str, Any]:
    return cast("Mapping[str, Any]", carried["prepare"].data["pdf"])


# ── translate ──


def translate(inputs: TranslationRunInputs, adapters: PdfAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    tagged = cast("str", _pdf(carried)["tagged"])
    return colab.translate(dataclasses.replace(inputs, document=tagged.encode("utf-8")), adapters, carried, ctx)


# ── report ──


def _variant_text(variant: Mapping[str, Any]) -> tuple[str, str]:
    """(stage, 글): 자동수정이 done 이면 그 글, 아니면 번역 글."""
    autofix = cast("Mapping[str, Any]", variant["autofix"])
    if autofix["status"] == "done":
        return "autofix", cast("str", autofix["translatedText"])
    return "translated", cast("str", variant["translatedText"])


def layout(result: Mapping[str, Any], pdf: Mapping[str, Any]) -> dict[str, Any]:
    """result@1 + prepare 의 pdf 칸 → translation.layout@1(꼴 검사 전)."""
    units = cast("Sequence[Mapping[str, Any]]", pdf["units"])
    warnings: list[dict[str, Any]] = [{**w, "variant": None} for w in pdf["warnings"]]
    variants: list[dict[str, Any]] = []
    for variant in cast("Sequence[Mapping[str, Any]]", result["variants"]):
        stage, text = _variant_text(variant)
        placed = pdf_tags.place(units, pages_to_map_merge(parse_pages(text))[0])
        variants.append({"label": variant["label"], "stage": stage, "units": placed.units, "unplaced": placed.unplaced})
        warnings.extend({**w, "variant": variant["label"]} for w in placed.warnings)
    return {
        "schemaVersion": LAYOUT_SHAPE,
        "status": result["status"],
        "sourceSha256": result["document"]["sourceSha256"],
        "source": {
            "pdfSha256": pdf["pdfSha256"],
            "pageCount": pdf["pageCount"],
            "parser": pdf["parser"],
            "adapter": pdf["adapter"],
        },
        "pages": pdf["pages"],
        "units": units,
        "variants": variants,
        "skipped": pdf["skipped"],
        "warnings": warnings,
    }


def report(inputs: TranslationRunInputs, adapters: PdfAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    out = colab.report(inputs, adapters, carried, ctx)
    results = cast("list[Mapping[str, Any]]", out.data["results"])
    made = layout(results[0], _pdf(carried))
    try:
        LAYOUT_SHAPES[LAYOUT_SHAPE].validate_python(made, strict=True)
    except ValidationError as error:
        raise FlowOutputError(f"결과가 {LAYOUT_SHAPE} 꼴이 아니다: 오류 {error.error_count()}개") from None
    return dataclasses.replace(out, data={**out.data, "results": [*results, made]})


STEPS: Final[Sequence[FlowStep[TranslationRunInputs, PdfAdapters]]] = (
    FlowStep(name="prepare", run=prepare),
    FlowStep(name="translate", run=translate),
    FlowStep(name="report", run=report),
)

FLOW: Final = make_flow(
    module="translation",
    id=FLOW_ID,
    input_shape=INPUT_SHAPE,
    inputs=TranslationRunInputs,
    adapters=PdfAdapters,
    result_shapes=(RESULT_SHAPE, DIGEST_SHAPE, LAYOUT_SHAPE),
    output_files=colab.OUTPUT_FILES,
    steps=tuple(STEPS),
)
