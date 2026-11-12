"""흐름 translation.colab@158(밴드 TR2 §3-1-2·6~9, 순수): prepare 의 거절·설정 오류, 문서 판정, 끝까지 돈 결과·Word.
실호출 0 — 모의 공급사뿐. 문서·회사·숫자는 전부 지어낸 것이다."""

import hashlib
import json
import re
from typing import Any, Literal, cast

import pytest

from esgapi.core.flows.types import FlowStepFailed
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError, PromptError
from esgapi.core.llm.prompts import PackagePromptStore, PromptRef, PromptTemplate, format_prompt_id
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import Completed, ProviderRequest, Usage
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES
from esgapi.translation.contracts.shapes import RESULT_SHAPE, RESULT_SHAPES
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.flows import binding_158
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows.colab_158 import (
    DocxDocument,
    RetryFound,
    RetryNotDone,
    TextDocument,
    UnsupportedDocument,
    read_document,
)
from esgapi.translation.tests import docx_support
from esgapi.translation.tests.engines.colab_158.run_digest import _docx_sha  # pyright: ignore[reportPrivateUsage]
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.support import (
    SIMPLE,
    SIMPLE_EN,
    FakeStore,
    Ran,
    default_versions,
    digest_of,
    options,
    result_of,
    run_options,
)
from esgapi.translation.tools.llm_bridge import TRANSLATE_ROUTE, CallModel, TranslationModels
from esgapi.translation.tools.page_tags import PageTags, page_count

NO_ISSUES = ok("[]")
RUN_RESULT_BODY_MAX_OCTETS = 8 * 1024 * 1024
"""runs 의 결과 본문 상한(runs/models.py — 계약 나로 들이지 않는다).
값은 runs/tests/test_models_values.py 가 못 박는다."""


def rejection_of(given: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    ran = run_options(given, **kwargs)
    result = result_of(ran)
    assert result["status"] == "rejected"
    assert ran.openai.calls == []
    assert ran.run.output.files == ()
    return result["rejection"]


# ── 끝까지 ──


def test_a_small_text_document_runs_to_a_strict_result_and_word_files() -> None:
    ran = run_options(options(), [ok(SIMPLE_EN), NO_ISSUES])
    result = result_of(ran)
    RESULT_SHAPES[RESULT_SHAPE].validate_python(result, strict=True)
    assert result["status"] == "done"
    assert result["document"]["sourceSha256"] == hashlib.sha256(SIMPLE.encode()).hexdigest()
    assert result["settings"]["retry"] is None
    assert [f["remainingKorean"] for f in result["variants"][0]["fragments"]] == [[]]
    names = [f.name for f in ran.run.output.files]
    assert "translation-bilingual-single.docx" in names and set(names) <= set(colab.OUTPUT_FILES)
    prepared = ran.run.steps["prepare"].data
    assert prepared["rejection"] is None and prepared["pageCount"] == 1
    assert isinstance(prepared["totalEstimateUsd"], float) and prepared["totalEstimateUsd"] > 0
    assert list(ran.run.steps) == ["prepare", "translate", "report"]


def test_the_report_keeps_the_result_bytes_and_adds_the_digest_second() -> None:
    """밴드 TR3a §3-1-3: 결과는 [result@1, digest@1](주 꼴 먼저 — 흐름의 result_shapes 차례). 주 결과는 translate 가
    지은 것과 바이트까지 같고 Word 도 결과로만 짓는다(시각을 가린 내용이 같음). 요약의 files 는 실제 출력 파일
    이름이다."""
    assert colab.FLOW.result_shapes == ("translation.result@1", "translation.digest@1")
    ran = run_options(options(), [ok(SIMPLE_EN), NO_ISSUES])
    built = cast("dict[str, Any]", ran.run.steps["translate"].data["result"])
    result = result_of(ran)
    summary = digest_of(ran)
    assert json.dumps(result, ensure_ascii=False) == json.dumps(built, ensure_ascii=False)
    # Word 바이트는 지은 시각을 싣는다(zip 항목·core.xml) — 다시 지은 것과는 시각을 가린 내용으로 견준다
    assert [(f.name, _docx_sha(f.content)) for f in ran.run.output.files] == [
        (f.name, _docx_sha(f.content)) for f in colab.word_files(built)
    ]
    DIGEST_SHAPES[DIGEST_SHAPE].validate_python(summary, strict=True)
    names = {f.name for f in ran.run.output.files}
    (variant,) = summary["variants"]
    assert {n for n in variant["files"].values() if n is not None} == names
    assert (summary["outcome"], summary["pageCount"], summary["failedPages"]) == ("done", 1, [])


def test_a_rejected_run_has_a_rejected_digest_and_no_files() -> None:
    ran = run_options(options(), content=b"%PDF-1.7 virtual")
    summary = digest_of(ran)
    assert (summary["status"], summary["rejectionKind"], summary["outcome"]) == (
        "rejected",
        "unsupported_input",
        "rejected",
    )
    assert summary["variants"] == [] and ran.run.output.files == ()


# ── Q5: 설정 오류는 prepare 의 dry-run 에서 — 공급사 0, translate 안 돎 ──


def failed_at_prepare(llm: LlmClient) -> BaseException:
    with pytest.raises(FlowStepFailed) as caught:
        run_options(options(), llm=llm)
    assert caught.value.step == "prepare"
    assert list(caught.value.completed) == []
    cause = caught.value.__cause__
    assert cause is not None
    return cause


def real_client(providers: dict[str, MockProvider], store: object = None) -> LlmClient:
    return LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers=providers,
        prompts=store or PackagePromptStore(),  # type: ignore[arg-type]
        log=MemorySink(),
        provider_retry={},
    )


def test_a_missing_provider_is_a_config_error_in_prepare() -> None:
    anthropic = MockProvider("anthropic")
    assert isinstance(failed_at_prepare(real_client({"anthropic": anthropic})), LlmConfigError)
    assert anthropic.calls == []


def test_an_output_cap_over_the_model_limit_is_a_config_error_in_prepare(monkeypatch: pytest.MonkeyPatch) -> None:
    """출력 상한은 min(자리 값, 칸 위끝)(TR4 R4) — 자리 값과 칸 위끝이 둘 다 모델 상한을 넘어야 넘는다."""
    openai = MockProvider("openai")
    monkeypatch.setitem(prompts.MAX_TOKENS, "section", 10**7)
    huge = CallModel(TRANSLATE_ROUTE, 10**7)
    monkeypatch.setattr(binding_158, "DEFAULT_MODELS", TranslationModels(huge, huge, huge))
    assert isinstance(
        failed_at_prepare(real_client({"anthropic": MockProvider("a"), "openai": openai})), LlmConfigError
    )
    assert openai.calls == []


class _Without:
    """실제 패키지 봉투에서 하나만 뺀 저장소."""

    def __init__(self, missing: str) -> None:
        self.inner = PackagePromptStore()
        self.missing = missing

    def get(self, ref: PromptRef) -> PromptTemplate:
        if format_prompt_id(ref) == self.missing:
            return PackagePromptStore().get(PromptRef(module=ref.module, name=ref.name, version=99))
        return self.inner.get(ref)


def test_a_missing_envelope_is_a_prompt_error_in_prepare() -> None:
    openai = MockProvider("openai")
    llm = real_client({"anthropic": MockProvider("anthropic"), "openai": openai}, _Without("translation/section@2"))
    assert isinstance(failed_at_prepare(llm), PromptError)
    assert openai.calls == []


# ── Q6: 너무 큼·예산 넘음 — 공급사 0 ──


def test_three_hundred_and_one_page_chunks_are_too_large() -> None:
    text = "\n".join(f"[PAGE {n}]\n[BLOCK 1]\n가상 {n}" for n in range(1, 302))
    refused = rejection_of(options(), text=text)
    assert (refused["kind"], refused["pageCount"], refused["limit"]) == ("too_large", 301, 300)


def test_one_char_over_the_source_limit_is_too_large() -> None:
    text = "[PAGE 1]\n[BLOCK 1]\n" + "가" * (colab.MAX_SOURCE_CHARS - len("[PAGE 1]\n[BLOCK 1]\n") + 1)
    assert len(text) == colab.MAX_SOURCE_CHARS + 1
    refused = rejection_of(options(), text=text)
    assert (refused["kind"], refused["limit"]) == ("too_large", colab.MAX_SOURCE_CHARS)


def _sized_page(number: int, chars: int) -> str:
    """조각 글자가 꼭 chars 인 쪽(`[PAGE n]` 줄 포함)."""
    head = f"[PAGE {number}]\n[BLOCK 1]\n"
    return head + "가" * (chars - len(head))


def _ranged(text: str, start: int | None, end: int | None) -> Ran:
    """금액 상한을 아주 낮춰 공급사 없이 prepare 의 판단까지만 본다(over_budget = 글자 상한을 지나 계획까지 감)."""
    return run_options(options(pages={"start": start, "end": end}), text=text, max_usd=0.0001)


def _rejected(ran: Ran) -> dict[str, Any]:
    return cast("dict[str, Any]", ran.run.steps["prepare"].data["rejection"])


@pytest.mark.parametrize(
    ("sizes", "start", "end", "kind"),
    [
        ((colab.MAX_SOURCE_CHARS, 1000), 1, 1, "over_budget"),  # 전체는 넘고 범위 안은 상한 그대로
        ((colab.MAX_SOURCE_CHARS + 1, 1000), 1, 1, "too_large"),
        ((1000, colab.MAX_SOURCE_CHARS), None, 1, "over_budget"),  # 끝만
        ((1000, colab.MAX_SOURCE_CHARS + 1), 2, None, "too_large"),  # 시작만
        ((colab.MAX_SOURCE_CHARS // 2, colab.MAX_SOURCE_CHARS // 2), 1, 2, "over_budget"),  # 조각을 더해 잰다
        ((colab.MAX_SOURCE_CHARS // 2 + 1, colab.MAX_SOURCE_CHARS // 2), 1, 2, "too_large"),
    ],
)
def test_the_char_limit_counts_only_the_chosen_pages(
    sizes: tuple[int, int], start: int | None, end: int | None, kind: str
) -> None:
    text = "\n".join(_sized_page(n, size) for n, size in enumerate(sizes, 1))
    ran = _ranged(text, start, end)
    assert _rejected(ran)["kind"] == kind
    if kind == "too_large":
        assert _rejected(ran)["limit"] == colab.MAX_SOURCE_CHARS


def test_text_outside_the_range_does_not_change_the_answer_and_the_sha_is_of_the_whole_document() -> None:
    small = _sized_page(1, 1000) + "\n" + _sized_page(2, 1000)
    large = _sized_page(1, 1000) + "\n" + _sized_page(2, 3 * colab.MAX_SOURCE_CHARS)
    one, other = (_ranged(text, 1, 1).run.steps["prepare"].data for text in (small, large))
    assert one["rejection"] == other["rejection"]
    assert (one["pageCount"], one["calls"]) == (other["pageCount"], other["calls"])
    assert one["sourceSha256"] == hashlib.sha256(small.encode()).hexdigest()
    assert other["sourceSha256"] == hashlib.sha256(large.encode()).hexdigest()
    too_large = _ranged(large, 2, 2)
    assert _rejected(too_large)["kind"] == "too_large"
    assert too_large.run.steps["prepare"].data["sourceSha256"] == other["sourceSha256"]


def test_without_a_range_the_whole_document_counts_including_text_before_the_first_page() -> None:
    head = "가상 머리 글\n"
    chunk = _sized_page(1, colab.MAX_SOURCE_CHARS)
    assert _rejected(_ranged(chunk, None, None))["kind"] == "over_budget"
    assert _rejected(_ranged(head + chunk, None, None))["kind"] == "too_large"


def test_table_text_counts_for_the_chosen_page_and_the_grid_still_shows() -> None:
    """표가 많은 docx: 몸 문단 글만으로는 상한 아래지만 엔진이 받는 글(표 pipe 줄 포함)은 넘는다. 격자는 쪽 수만 세므로
    뜨고, 상한은 prepare 의 셈 하나로 잰다(TRW9 C0 ⑥)."""
    cell = docx_support.tc("가" * 1000)
    rows = docx_support.tr(cell, cell)
    body_only = docx_support.p("[PAGE 1]") + docx_support.p("가상 몸 글")
    table = docx_support.tbl(rows * (colab.MAX_SOURCE_CHARS // 2000 + 1))
    data = docx_support.with_body(body_only + table + docx_support.p("[PAGE 2]") + docx_support.p("가상 둘째"))
    assert page_count(data) == PageTags(2, None)
    read = read_document(data)
    assert isinstance(read, DocxDocument) and len(read.text) > colab.MAX_SOURCE_CHARS
    bare = read_document(docx_support.with_body(body_only + docx_support.p("[PAGE 2]") + docx_support.p("가상 둘째")))
    assert isinstance(bare, DocxDocument) and len(bare.text) < colab.MAX_SOURCE_CHARS  # 분모: 몸 문단만이면 상한 아래
    assert rejection_of(options(pages={"start": 1, "end": 1}), content=data)["kind"] == "too_large"
    assert rejection_of(options(pages={"start": 2, "end": 2}), content=data, max_usd=0.0001)["kind"] == "over_budget"


def test_one_call_over_the_planned_call_limit_is_too_large(monkeypatch: pytest.MonkeyPatch) -> None:
    """SIMPLE 의 계획 호출 수(자동수정 몫 포함)보다 상한을 하나 작게 두면 거절, 같으면 돈다."""
    planned = colab.plan.plan(colab.engine_input(run_inputs(), SIMPLE))
    calls = sum(c.count for c in planned.calls)
    monkeypatch.setattr(colab, "MAX_PLANNED_CALLS", calls - 1)
    refused = rejection_of(options())
    assert (refused["kind"], refused["limit"]) == ("too_large", calls - 1)
    monkeypatch.setattr(colab, "MAX_PLANNED_CALLS", calls)
    assert result_of(run_options(options(), [ok(SIMPLE_EN), NO_ISSUES]))["status"] == "done"


def run_inputs() -> colab.TranslationRunInputs:
    from esgapi.translation.tests.flows.support import binding, document

    return binding().inputs_with(document(), options(), company_id=1, versions={})


def test_an_upper_bound_over_the_budget_is_over_budget() -> None:
    refused = rejection_of(options(), max_usd=0.0001)
    assert refused["kind"] == "over_budget"


def test_the_budget_compares_with_the_measured_upper_bound() -> None:
    """위끝 T 를 재서: 상한 T − ε 면 over_budget, 상한 T 면 거절 없음(같으면 넘지 않은 것)."""
    measured = run_options(options(), max_usd=0.0001).run.steps["prepare"].data["totalEstimateUsd"]
    assert isinstance(measured, float) and measured > 0
    assert rejection_of(options(), max_usd=measured - 1e-9)["kind"] == "over_budget"
    assert result_of(run_options(options(), [ok(SIMPLE_EN), NO_ISSUES], max_usd=measured))["status"] == "done"


def test_the_bounds_stay_in_the_prepare_output_only() -> None:
    ran = run_options(options(), max_usd=0.0001)
    prepared = ran.run.steps["prepare"].data
    assert prepared["totalEstimateUsd"] is not None and prepared["calls"] is not None
    assert "totalEstimateUsd" not in json.dumps(result_of(ran))


# ── 9: 문서 판정 ──


def test_documents_are_told_apart_by_their_bytes() -> None:
    def body(doc: Any) -> None:
        doc.add_paragraph("[PAGE 1]")
        doc.add_paragraph("가상 본문")

    assert isinstance(read_document(docx_support.built(body)), DocxDocument)
    assert read_document(SIMPLE.encode()) == TextDocument(SIMPLE)
    pdf = read_document(b"%PDF-1.7\nsynthetic")
    assert isinstance(pdf, UnsupportedDocument) and pdf.kind == "pdf"
    assert isinstance(read_document("가".encode("cp949")), UnsupportedDocument)
    rejected = read_document(b"PK\x03\x04not a real zip")
    assert isinstance(rejected, UnsupportedDocument) and rejected.kind == "docx_rejected"


@pytest.mark.parametrize(
    "content",
    [b"%PDF-1.7\nsynthetic", "가상".encode("cp949"), b"PK\x03\x04not a real zip"],
    ids=["pdf", "cp949", "zip"],
)
def test_an_unsupported_document_is_rejected_before_any_call(content: bytes) -> None:
    refused = rejection_of(options(), content=content)
    assert refused["kind"] == "unsupported_input"


def test_a_docx_document_is_read_as_text() -> None:
    def body(doc: Any) -> None:
        doc.add_paragraph("[PAGE 1]")
        doc.add_paragraph("[BLOCK 1]")
        doc.add_paragraph("가상 제목")

    ran = run_options(options(), [ok(SIMPLE_EN), NO_ISSUES], content=docx_support.built(body))
    assert result_of(ran)["status"] == "done"


# ── retry 의 대조(prepare) ──


def retry_options(pages: list[int]) -> dict[str, Any]:
    return options(retry={"fromRunId": 7, "pages": pages})


def found(
    text: str = SIMPLE, labels: tuple[str, ...] = ("single",), key: colab.AiKey | Literal["same"] | None = "same"
) -> RetryFound:
    """key "same" = 이번 실행(기본 판)과 같은 판 열쇠."""
    return RetryFound(
        base={"single": "[PAGE 1]\n[BLOCK 1]\nOld"},
        source_sha256=hashlib.sha256(text.encode()).hexdigest(),
        labels=labels,
        ai_key=colab.ai_key(default_versions()) if key == "same" else key,
    )


V2_KEY: colab.AiKey = (2, "0" * 64, None)
"""지어낸 저장 판 v2 의 열쇠(이번 실행은 기본 판)."""
DEFAULT_MODEL_SHA = default_versions()["modelSettingsSha256"]
OTHER_MODEL_SHA_KEY: colab.AiKey = (None, "f" * 64, None)
"""같은 기본 판(id None)인데 모델 설정 sha 만 다름(그사이 명세 기본값이 바뀐 꼴 — 검증 권고 R1)."""
OTHER_PROMPTS_SHA_KEY: colab.AiKey = (None, DEFAULT_MODEL_SHA, "e" * 64)
"""같은 판 id·같은 모델 sha 인데 프롬프트 글 sha 만 다름(검증 권고 R1)."""


@pytest.mark.parametrize("source", [None, RetryNotDone("processing")], ids=["missing", "not_done"])
def test_a_missing_or_unfinished_source_is_not_found(source: Any) -> None:
    store = FakeStore({} if source is None else {(1, 7): source})
    assert rejection_of(retry_options([1]), store=store)["kind"] == "retry_source_not_found"
    assert store.asked == [(1, 7)]


@pytest.mark.parametrize(
    "source",
    [
        found("[PAGE 1]\n다른 원문"),
        found(labels=("A", "B")),
        found(key=V2_KEY),
        found(key=OTHER_MODEL_SHA_KEY),
        found(key=OTHER_PROMPTS_SHA_KEY),
        found(key=None),
    ],
    ids=[
        "other_text",
        "other_styles",
        "other_setting",
        "same_id_other_model_sha",
        "same_id_other_prompts_sha",
        "old_run_without_key",
    ],
)
def test_another_source_text_style_set_or_setting_is_a_mismatch(source: RetryFound) -> None:
    store = FakeStore({(1, 7): source})
    refused = rejection_of(retry_options([1]), store=store, versions=default_versions())
    assert refused["kind"] == "retry_source_mismatch"
    assert refused["message"] == "앞 번역 실행과 원문이나 문체 묶음, AI 설정 판이 달라요"


def test_a_run_without_its_own_setting_key_cannot_retry() -> None:
    """이번 실행에 판 열쇠가 없으면(회사 없는 inputs·옛 꼴) 앞 실행과 같은 판인지 알 수 없어 거절."""
    store = FakeStore({(1, 7): found()})
    assert rejection_of(retry_options([1]), store=store)["kind"] == "retry_source_mismatch"


def test_the_setting_key_reads_the_three_version_keys() -> None:
    versions = {"engine": "e", "aiSettingId": 3, "modelSettingsSha256": "m", "promptsSha256": "p"}
    assert colab.ai_key(versions) == (3, "m", "p")
    assert colab.ai_key({"aiSettingId": None, "modelSettingsSha256": "m"}) == (None, "m", None)
    assert colab.ai_key({"engine": "e"}) is None


def test_a_matching_source_retries_the_chosen_page_and_records_the_skipped_ones() -> None:
    store = FakeStore({(1, 7): found()})
    ran = run_options(retry_options([1, 9]), [ok(SIMPLE_EN), NO_ISSUES], store=store, versions=default_versions())
    result = result_of(ran)
    assert result["settings"]["retry"] == {"fromRunId": 7, "pages": [1, 9], "skippedPages": [9]}
    assert "Virtual Title" in result["variants"][0]["translatedText"]
    assert [w["code"] for w in result["warnings"]] == ["retry_page_missing"]


# ── 8: 상한 글자 문서의 결과는 8MiB 안 ──


U = Usage(input_tokens=1, output_tokens=1, cache_read_tokens=0, cache_write_tokens=0)
EN = "The virtual company reviews its risks and opportunities. "


def _answer(request: ProviderRequest) -> Completed:
    """검수면 이슈 하나(자동수정이 돌게), 그 밖이면 국문 글자 × 2.5 의 영문(★D 의 가정)."""
    system = "".join(s.text for s in request.system)
    if system == prompts.QA_SYSTEM_PROMPT:
        issue = {"issue_type": "GRAMMAR", "severity": "LOW", "original_span": "", "suggestion": "x", "reason": "y"}
        return Completed(text=json.dumps([issue]), usage=U)
    user = "".join(getattr(p, "text", "") for p in request.user)
    korean = len(re.findall(r"[가-힣]", user))
    return Completed(text="[BLOCK 1]\n" + (EN * 1000)[: max(40, int(korean * 2.5))], usage=U)


def test_a_document_at_the_char_limit_keeps_its_result_under_the_body_limit() -> None:
    para = "가상기업은 지속가능한 경영을 위해 위험과 기회를 점검하고 이해관계자와 소통합니다. "
    pages: list[str] = []
    n = 0
    while sum(len(p) + 1 for p in pages) < colab.MAX_SOURCE_CHARS - 2000:
        n += 1
        pages.append(f"[PAGE {n}]\n[BLOCK 1]\n" + (para * 40)[:1300])
    text = "\n".join(pages)
    assert colab.MAX_SOURCE_CHARS - 2000 <= len(text) <= colab.MAX_SOURCE_CHARS
    openai = MockProvider("openai")
    for _ in range(10_000):
        openai.enqueue(_answer)
    llm = real_client({"anthropic": MockProvider("anthropic"), "openai": openai})
    given = options(style={"compareAb": True, "single": "B"}, ceoPageLimit=None)
    from esgapi.core.flows.run import run_flow
    from esgapi.translation.tests.flows.support import binding, document

    inputs = binding(max_usd=10_000.0).inputs_with(document(text), given, company_id=1, versions={})
    run = run_flow(
        colab.FLOW, inputs, colab.TranslationAdapters(llm=llm, tenant="1", mock=False, spent_usd=lambda: 0.0)
    )
    result, summary = run.output.results
    assert result["status"] == "done"
    size = len(json.dumps(result, ensure_ascii=False).encode())
    assert size < RUN_RESULT_BODY_MAX_OCTETS, size
    # 요약은 쪽 수와 무관하게 작다(목록이 결과 본문을 읽지 않으려는 것 — 밴드 TR3a)
    assert len(json.dumps(summary, ensure_ascii=False).encode()) < 4096
