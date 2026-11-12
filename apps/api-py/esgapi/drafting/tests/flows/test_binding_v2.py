"""끼움 DraftingBinding(flows/binding_v2.py — RP1 §3 S12, RP2a §3 S6·S8, RP2b B12 — v1 을 옮김, RP2c B2·B7 — 앞 실행
이어 받기). 순수 층(가짜 ProjectSource·BaseSource). 목차·글은 지어낸 것이다."""

from dataclasses import dataclass, field
from typing import Any

import pytest

from esgapi.core.calc.ai_settings import defaults, model_settings_sha256
from esgapi.core.documents.contract import EPOCH
from esgapi.core.flows.binding import RunOptionsRejected, RunVersionsMismatch, RunVersionsRejected
from esgapi.drafting.contracts.wire import outline_sha256
from esgapi.drafting.flows import binding_v2
from esgapi.drafting.flows.binding_v2 import BaseFacts, DocumentFacts, DraftingBinding, OutlineFacts, ProjectFacts
from esgapi.drafting.flows.prompt_model_v2 import MODELS as SLOTS
from esgapi.drafting.tests.flows.settings_store import DefaultOnlyStore, FileModels, file_config
from esgapi.drafting.tests.flows.support import OUTLINE, base_result

A, B = 1, 2
SHA = outline_sha256(OUTLINE)
DEFAULT_MODEL_SHA = model_settings_sha256(defaults(file_config(), SLOTS))
"""기본 판의 모델 설정 sha(RPA1 ② — 명세 기본값, 저장소 정본 models.json)."""


@dataclass
class Source:
    projects: dict[tuple[int, int], ProjectFacts] = field(default_factory=dict[tuple[int, int], ProjectFacts])
    outlines: dict[tuple[int, int], OutlineFacts] = field(default_factory=dict[tuple[int, int], OutlineFacts])
    documents: dict[tuple[int, int], DocumentFacts] = field(default_factory=dict[tuple[int, int], DocumentFacts])
    bases: dict[tuple[int, int], BaseFacts] = field(default_factory=dict[tuple[int, int], BaseFacts])

    def base(self, company_id: int, run_id: int) -> BaseFacts | None:
        return self.bases.get((company_id, run_id))

    def project(self, company_id: int, project_id: int) -> ProjectFacts | None:
        return self.projects.get((company_id, project_id))

    def outline(self, company_id: int, outline_id: int) -> OutlineFacts | None:
        return self.outlines.get((company_id, outline_id))

    def document(self, company_id: int, document_id: int) -> DocumentFacts | None:
        return self.documents.get((company_id, document_id))


def source() -> Source:
    found = Source()
    found.projects[(A, 7)] = ProjectFacts(project_id=7, outline_id=12, outline_sha256=SHA, document_id=31)
    found.outlines[(A, 12)] = OutlineFacts(project_id=7, sha256=SHA, outline=OUTLINE)
    found.documents[(A, 31)] = DocumentFacts(uploaded=True, etag="e1")
    found.outlines[(A, 11)] = OutlineFacts(project_id=7, sha256="b" * 64, outline=OUTLINE)
    found.bases[(A, 50)] = BaseFacts(run_id=50, project_id=7, status="done", versions={}, result=base_result(50, 11))
    return found


class NoArtifacts:
    def ensure(self, company_id: int, document_id: int, etag: str) -> Any:
        raise AssertionError("끼움 시험은 산출물을 짓지 않는다")

    def view(self, company_id: int, document_id: int, artifact_id: int, *, places: bool = False) -> Any:
        raise AssertionError("끼움 시험은 산출물을 읽지 않는다")

    def file_name(self, company_id: int, document_id: int) -> Any:
        raise AssertionError("끼움 시험은 문서를 읽지 않는다")


def binding(found: Source) -> DraftingBinding:
    return DraftingBinding(
        projects=found,
        max_usd=lambda: 2.5,
        mock=lambda: False,
        spent_usd=lambda c, r: 0.0,
        artifacts=NoArtifacts(),
        bases=found,
        settings=DefaultOnlyStore(),  # RPA1 ②: 적용 판 없음(기본 판)
        models=FileModels(),
    )


def test_versions_with_carries_the_current_outline_and_document() -> None:
    assert binding(source()).versions_with({"projectId": 7}, company_id=A) == {
        "engine": "v2",
        "flow": "drafting.draft@v2",
        "promptIds": {"map": "drafting/map@1", "draft": "drafting/draft@2"},
        "adapter": "drafting-blocks@1",
        "parserLayout": 2,
        "epoch": EPOCH,
        "segmenter": "drafting-sentences@1",
        "reuse": "drafting-reuse@1",
        "texts": "drafting-texts@3",
        "outlineId": 12,
        "outlineSha256": SHA,
        "documentId": 31,
        "documentEtag": "e1",
        "aiSetting": "기본 설정",  # RPA1 ②: 기본 판의 AI 열쇠(promptsSha256 은 코드 글이라 없음)
        "aiSettingId": None,
        "modelSettingsSha256": DEFAULT_MODEL_SHA,
    }


def test_missing_things_are_rejected_and_another_company_is_the_same_as_missing() -> None:
    found = source()
    with pytest.raises(RunVersionsRejected) as other:
        binding(found).versions_with({"projectId": 7}, company_id=B)
    with pytest.raises(RunVersionsRejected) as missing:
        binding(found).versions_with({"projectId": 8}, company_id=A)
    assert str(other.value) == str(missing.value) == binding_v2.NO_PROJECT
    for change, message in (
        (ProjectFacts(project_id=7, outline_id=None, outline_sha256=None, document_id=31), binding_v2.NO_OUTLINE),
        (ProjectFacts(project_id=7, outline_id=12, outline_sha256=SHA, document_id=None), binding_v2.NO_DOCUMENT),
    ):
        found.projects[(A, 7)] = change
        with pytest.raises(RunVersionsRejected, match=message):
            binding(found).versions_with({"projectId": 7}, company_id=A)
    found = source()
    found.documents[(A, 31)] = DocumentFacts(uploaded=False, etag=None)
    with pytest.raises(RunVersionsRejected, match=binding_v2.NOT_UPLOADED):
        binding(found).versions_with({"projectId": 7}, company_id=A)


def test_inputs_with_reads_the_pinned_version_even_after_a_new_outline() -> None:
    found = source()
    pinned = binding(found).versions_with({"projectId": 7}, company_id=A)
    found.projects[(A, 7)] = ProjectFacts(project_id=7, outline_id=13, outline_sha256="b" * 64, document_id=31)
    made = binding(found).inputs_with({"projectId": 7}, company_id=A, versions=pinned)
    assert (made.outline_id, made.outline, made.max_usd, made.tags.tenant) == (12, OUTLINE, 2.5, "1")


def test_inputs_with_refuses_tampered_or_foreign_versions() -> None:
    found = source()
    pinned = binding(found).versions_with({"projectId": 7}, company_id=A)
    with pytest.raises(RunVersionsMismatch):
        binding(found).inputs_with({"projectId": 7}, company_id=A, versions={**pinned, "outlineSha256": "c" * 64})
    with pytest.raises(RunVersionsMismatch):
        binding(found).inputs_with(
            {"projectId": 7}, company_id=A, versions={k: v for k, v in pinned.items() if k != "documentId"}
        )
    with pytest.raises(RunVersionsMismatch):
        binding(found).inputs_with({"projectId": 7}, company_id=B, versions=pinned)
    with pytest.raises(RunVersionsMismatch):
        binding(found).inputs_with({"projectId": 8}, company_id=A, versions=pinned)
    found.outlines[(A, 12)] = OutlineFacts(project_id=7, sha256=SHA, outline={"nodes": []})  # 판 글이 바뀜
    with pytest.raises(RunVersionsMismatch):
        binding(found).inputs_with({"projectId": 7}, company_id=A, versions=pinned)


@pytest.mark.parametrize("options", [{}, {"projectId": "7"}, {"projectId": 7, "x": 1}, {"projectId": 0}])
def test_options_are_refused_in_one_sentence(options: dict[str, object]) -> None:
    with pytest.raises(RunOptionsRejected):
        binding(source()).check_options(options)


def test_s6_an_uploaded_document_without_an_etag_is_refused_at_create() -> None:
    """474: etag 없는 문서(올림 확인이 etag 를 못 받음)는 만들 때 막는다 — 산출물 열쇠가 etag 라서."""
    found = source()
    found.documents[(A, 31)] = DocumentFacts(uploaded=True, etag=None)
    with pytest.raises(RunVersionsRejected, match=binding_v2.NOT_UPLOADED):
        binding(found).versions_with({"projectId": 7}, company_id=A)


@pytest.mark.parametrize("etag", [None, 7, ["e1"]])
def test_s6_inputs_with_refuses_an_etag_that_is_not_text(etag: object) -> None:
    found = source()
    pinned = binding(found).versions_with({"projectId": 7}, company_id=A)
    with pytest.raises(RunVersionsMismatch, match="etag"):
        binding(found).inputs_with({"projectId": 7}, company_id=A, versions={**pinned, "documentEtag": etag})


def test_s8_the_ports_have_no_defaults_and_the_mock_keeps_the_versions() -> None:
    with pytest.raises(TypeError):
        DraftingBinding(  # type: ignore[call-arg]
            projects=source(), max_usd=lambda: 2.5, mock=lambda: False, spent_usd=lambda c, r: 0.0
        )
    with pytest.raises(TypeError):  # RP2c: bases 도 기본값 없음
        DraftingBinding(  # type: ignore[call-arg]
            projects=source(),
            max_usd=lambda: 2.5,
            mock=lambda: False,
            spent_usd=lambda c, r: 0.0,
            artifacts=NoArtifacts(),
        )
    live = binding(source())
    found = source()
    mocked = DraftingBinding(
        projects=found,
        max_usd=lambda: 2.5,
        mock=lambda: True,
        spent_usd=lambda c, r: 0.0,
        artifacts=NoArtifacts(),
        bases=found,
        settings=DefaultOnlyStore(),  # RPA1 ②
        models=FileModels(),
    )
    assert live.versions({"projectId": 7}) == mocked.versions({"projectId": 7})
    assert binding_v2.PARSER_LAYOUT == 2


class PlacesArtifacts:
    """회사·places 를 그대로 넘기는지 보는 가짜 CompanyArtifacts."""

    def __init__(self) -> None:
        self.views: list[tuple[int, int, int, bool]] = []

    def ensure(self, company_id: int, document_id: int, etag: str) -> Any:
        raise AssertionError("부르지 않는다")

    def view(self, company_id: int, document_id: int, artifact_id: int, *, places: bool = False) -> Any:
        self.views.append((company_id, document_id, artifact_id, places))
        return None

    def file_name(self, company_id: int, document_id: int) -> str | None:
        return None


def test_b12_the_scoped_view_passes_places_through() -> None:
    """RP2b §2-4: 흐름의 view(…, places) 가 회사를 묶은 채 그대로 간다(기본 False)."""
    artifacts = PlacesArtifacts()
    scoped = binding_v2._Scoped(artifacts, A)  # pyright: ignore[reportPrivateUsage]
    scoped.view(31, 41)
    scoped.view(31, 41, places=True)
    assert artifacts.views == [(A, 31, 41, False), (A, 31, 41, True)]


# ── RP2c B2·B7: 옵션 @2 와 앞 실행 이어 받기 ──

WITH_BASE: dict[str, object] = {"projectId": 7, "base": {"runId": 50, "rebuild": []}}


@pytest.mark.parametrize(
    ("options", "said"),
    [
        ({"projectId": 7, "base": {"runId": 50}}, "옵션 base의 값이 맞지 않아요"),
        ({"projectId": 7, "base": {"runId": True, "rebuild": []}}, "옵션 base의 값이 맞지 않아요"),
        (
            {"projectId": 7, "base": {"runId": 50, "rebuild": [f"k{n}" for n in range(151)]}},
            "옵션 base의 값이 맞지 않아요",
        ),
        ({"projectId": 7, "base": {"runId": 50, "rebuild": ["ghg", "ghg"]}}, "다시 만들 목차가 겹쳐요"),
        ({"projectId": 7, "base": {"runId": 50, "rebuild": [], "x": 1}}, "알 수 없는 옵션이에요"),
    ],
)
def test_b2_base_options_are_refused_in_one_sentence(options: dict[str, object], said: str) -> None:
    with pytest.raises(RunOptionsRejected) as caught:
        binding(source()).check_options(options)
    assert str(caught.value) == said


def test_b2_project_id_alone_still_passes() -> None:
    binding(source()).check_options({"projectId": 7})
    binding(source()).check_options({"projectId": 7, "base": {"runId": 50, "rebuild": ["ghg"]}})


def _broken(kind: str) -> Source:
    found = source()
    good = found.bases[(A, 50)]
    match kind:
        case "missing":
            del found.bases[(A, 50)]
        case "foreign":  # 남의 회사의 실행 — 포트가 회사 조건으로 None
            found.bases[(B, 50)] = found.bases.pop((A, 50))
        case "not_done":
            found.bases[(A, 50)] = BaseFacts(50, 7, "failed", {}, good.result)
        case "other_project":
            found.bases[(A, 50)] = BaseFacts(50, 8, "done", {}, good.result)
        case _:  # 결과 @3 없음(@2 만 있는 실행)
            found.bases[(A, 50)] = BaseFacts(50, 7, "done", {}, None)
    return found


@pytest.mark.parametrize("kind", ["missing", "foreign", "not_done", "other_project", "no_result"])
def test_b7_an_unusable_base_is_one_sentence_at_create(kind: str) -> None:
    with pytest.raises(RunVersionsRejected) as caught:
        binding(_broken(kind)).versions_with(WITH_BASE, company_id=A)
    assert str(caught.value) == binding_v2.BASE_MISSING == "이어 받을 앞 실행을 찾을 수 없어요"


def test_b7_rebuild_outside_the_current_leaves_is_refused() -> None:
    options = {"projectId": 7, "base": {"runId": 50, "rebuild": ["env"]}}  # env 는 가지
    with pytest.raises(RunVersionsRejected) as caught:
        binding(source()).versions_with(options, company_id=A)
    assert str(caught.value) == "다시 만들 목차가 지금 목차에 없어요"


def test_b7_versions_carry_the_reuse_rule_but_not_the_base() -> None:
    found = binding(source()).versions_with(WITH_BASE, company_id=A)
    assert found["reuse"] == "drafting-reuse@1" and "base" not in found and 50 not in found.values()
    assert found == binding(source()).versions_with({"projectId": 7}, company_id=A)


def test_b7_inputs_with_reads_the_base_and_compares_versions_without_fact_keys() -> None:
    found = source()
    pinned = binding(found).versions_with(WITH_BASE, company_id=A)
    facts = {"outlineId": 11, "outlineSha256": "b" * 64, "documentId": 30, "documentEtag": "e0"}
    found.bases[(A, 50)] = BaseFacts(50, 7, "done", {**pinned, **facts}, base_result(50, 11))
    options = {"projectId": 7, "base": {"runId": 50, "rebuild": ["ghg"]}}
    inputs = binding(found).inputs_with(options, company_id=A, versions=pinned)
    assert inputs.base is not None and inputs.rebuild == frozenset({"ghg"})
    assert (inputs.base.run_id, inputs.base.outline_id, inputs.base.versions_same) == (50, 11, True)
    assert list(inputs.base.nodes) == list(OUTLINE["nodes"])
    found.bases[(A, 50)] = BaseFacts(50, 7, "done", {**pinned, **facts, "segmenter": "x@9"}, base_result(50, 11))
    assert binding(found).inputs_with(options, company_id=A, versions=pinned).base.versions_same is False  # type: ignore[union-attr]
    assert binding(found).inputs_with({"projectId": 7}, company_id=A, versions=pinned).base is None


def test_b7_a_base_gone_before_the_run_is_a_mismatch() -> None:
    found = source()
    pinned = binding(found).versions_with(WITH_BASE, company_id=A)
    del found.bases[(A, 50)]
    with pytest.raises(RunVersionsMismatch):
        binding(found).inputs_with(WITH_BASE, company_id=A, versions=pinned)
