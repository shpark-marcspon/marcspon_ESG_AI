# pyright: reportPrivateUsage=false, reportUnknownVariableType=false, reportIndexIssue=false
# pyright: reportArgumentType=false, reportGeneralTypeIssues=false, reportUnknownMemberType=false
"""흐름 drafting.draft@v2(flows/draft_v2.py — RP1 §3 S7~S11·S13b, RP2b B7 — v1 시험을 옮겨 @2 로): 진짜 LlmClient +
대본 심은 MockProvider(키·네트워크 0). 순수 층. 쪽 글·답은 지어낸 것이다(답의 쪽 번호 n = 그 쪽 블록
p<n>-b1 의 문장 0 — support.cite)."""

import dataclasses
import json
from typing import Any, cast

import pytest

from esgapi.core.documents.contract import ArtifactInvalid, ArtifactRefused, ArtifactUnreadable
from esgapi.core.flows.binding import RunRetryLater
from esgapi.core.flows.run import FlowStepFailed, run_flow
from esgapi.core.flows.types import NoTextLayer, StepContext, StepOutput
from esgapi.core.llm.config import default_config_sources, load_config, resolve_route
from esgapi.core.tests.artifact_fakes import fake_places
from esgapi.drafting.contracts import shapes
from esgapi.drafting.engines.v1 import pages, prompts
from esgapi.drafting.engines.v1 import texts as v1_texts
from esgapi.drafting.engines.v2 import material
from esgapi.drafting.engines.v2 import prompts as v2_prompts
from esgapi.drafting.engines.v2 import texts as v2_texts
from esgapi.drafting.engines.v2.texts import DEFAULT_TEXTS, MARKER_RULES, WRITING_RULES
from esgapi.drafting.flows import draft_v2, reuse
from esgapi.drafting.tests.flows.support import (
    ARTIFACT_ID,
    OUTLINE,
    PAGES,
    SHA,
    Artifacts,
    artifacts_of,
    document_of,
    draft_reply,
    extracted,
    inputs,
    map_reply,
    ref,
    view_of,
    world,
)
from esgapi.drafting.tools import blocks_text


def result_of(run: Any) -> dict[str, Any]:
    found = cast("dict[str, Any]", run.output.results[0])
    shapes.check_result(found)
    return found


def by_key(result: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {leaf["key"]: leaf for leaf in result["leaves"]}


def test_s7_end_to_end_one_map_two_drafts_and_a_leaf_without_material() -> None:
    provider, spy, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"]), (5, ["ghg"]), (1, [])))
    provider.enqueue_text(draft_reply(("배출량 1,200 tCO2eq", [2]), ("감축 계획 수립", [5])))
    provider.enqueue_text(draft_reply(("에너지 300 MWh 사용", [4])))
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert [r.prompt for r in spy.requests] == ["drafting/map@1", "drafting/draft@2", "drafting/draft@2"]
    assert {(r.route, r.temperature, r.max_output_tokens, r.max_schema_retries) for r in spy.requests} == {
        ("light-openai-41", 0.0, 4000, 1)
    }
    found = pages.pages_of(PAGES)
    outline = prompts.outline_lines(
        [
            ("ghg", ("환경", "온실가스"), "배출량"),
            ("energy", ("환경", "에너지"), "사용량"),
            ("safety", ("안전",), "재해율"),
        ]
    )
    assert spy.requests[0].vars == dict(
        zip(
            ("system", "user"),
            v2_prompts.map_texts(
                draft_v2.DEFAULT_TEXTS, outline, pages.batch_text([found[0], found[1], found[3], found[4]])
            ),
            strict=True,
        )
    )
    assert (
        spy.requests[1]
        .vars["user"]
        .endswith("[PAGE 2]\n[B p2-b1] ⟨0⟩배출량 1,200 tCO2eq\n\n[PAGE 5]\n[B p5-b1] ⟨0⟩배출 감축 계획")
    )
    leaves = by_key(result)
    assert [leaf["key"] for leaf in result["leaves"]] == ["ghg", "energy", "safety"]
    assert leaves["ghg"]["pages"] == [2, 5] and leaves["ghg"]["titlePath"] == ["환경", "온실가스"]
    assert [b["unsupported"] for b in leaves["ghg"]["outcome"]["bullets"]] == [False, False]
    assert leaves["safety"]["outcome"] == {"status": "no_material"}
    assert result["mapping"] == {"batches": 1, "failedBatches": []}
    assert result["settings"]["promptIds"] == {"map": "drafting/map@1", "draft": "drafting/draft@2"}
    assert [w["code"] for w in result["warnings"]] == ["mapping_incomplete"]
    sizes = [{"page": n, "width": 595.0, "height": 842.0} for n in range(1, 6)]
    assert result["document"] == {
        "documentId": 31,
        "fileName": "가상-보고서.pdf",
        "pageCount": 5,
        "textPages": 4,
        "pages": sizes,
    }


def test_s8_unsupported_sources_are_marked_not_dropped() -> None:
    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(
        draft_reply(("감축 실적", [4]), ("빈 쪽 근거", [3]), ("배출량 9,999 톤", [2]), ("배출량 1200", [2]))
    )
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    bullets = by_key(result)["ghg"]["outcome"]["bullets"]
    assert [b["unsupported"] for b in bullets] == [True, True, True, False]
    assert all(1 <= len(b["text"]) <= 200 for b in bullets) and len(bullets) <= 15
    codes = [w["code"] for w in result["warnings"] if w["key"] == "ghg"]
    assert codes.count("unsupported_bullet") == 2 and "number_not_in_source" in codes
    assert all(w["page"] is None or w["page"] >= 1 for w in result["warnings"])  # R4


@pytest.mark.parametrize(
    ("reply", "kind"),
    [("not json", "schema_mismatch"), ("refuse", "refusal"), ("cut", "truncated"), ("error", "provider_error")],
)
def test_s9_a_failed_draft_fails_only_that_leaf(reply: str, kind: str) -> None:
    from esgapi.core.llm.types import ProviderError, Refusal, Truncated

    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    match reply:
        case "not json":
            provider.enqueue_text("모르는 글").enqueue_text("또 모르는 글")
        case "refuse":
            provider.enqueue(Refusal(text="no", category=None, usage=None))
        case "cut":
            provider.enqueue(Truncated(text="{", usage=None))
        case _:
            provider.enqueue(ProviderError(status=400, retryable=False, message="bad"))
    provider.enqueue_text(draft_reply(("에너지 300 MWh", [4])))
    leaves = by_key(result_of(run_flow(draft_v2.FLOW, inputs(), adapters)))
    assert leaves["ghg"]["outcome"]["status"] == "failed" and leaves["ghg"]["outcome"]["failure"]["kind"] == kind
    assert "bad" not in leaves["ghg"]["outcome"]["failure"]["message"]
    assert leaves["energy"]["outcome"]["status"] == "done"


def test_s9_a_failed_map_batch_leaves_pages_unmapped() -> None:
    provider, _, adapters = world()
    provider.enqueue_text("JSON 아님").enqueue_text("JSON 아님")
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert result["mapping"]["failedBatches"] == [
        {
            "firstPage": 1,
            "lastPage": 5,
            "failure": {"kind": "schema_mismatch", "message": draft_v2.FAILURE_MESSAGES["schema_mismatch"]},
        }
    ]
    assert {leaf["outcome"]["status"] for leaf in result["leaves"]} == {"no_material"}
    assert [w["code"] for w in result["warnings"]].count("mapping_incomplete") == 3


def test_s9_no_text_layer_fails_the_run() -> None:
    _, _, adapters = world(["", "  "])
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(draft_v2.FLOW, inputs(), adapters)
    assert isinstance(caught.value.__cause__, NoTextLayer)


def test_s9_too_many_pages_is_rejected_without_calls() -> None:
    _, spy, adapters = world(["글"] * 301)
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert result["status"]["code"] == "too_large" and spy.requests == []


def test_s10_a_over_budget_before_map_calls_nothing() -> None:
    _, spy, adapters = world()
    result = result_of(run_flow(draft_v2.FLOW, inputs(max_usd=0.001), adapters))
    assert (result["status"]["code"], result["status"]["stage"]) == ("over_budget", "before_map")
    assert spy.requests == [] and {leaf["outcome"]["status"] for leaf in result["leaves"]} == {"not_run"}


def test_s10_b_over_budget_before_draft_keeps_the_mapping() -> None:
    texts = ["가" * 7900] * 3  # 묶음 하나·잎 셋이 그 셋을 다 받음 — ⓑ(실제 재료 셋) > ⓐ(S2 하나 + 바닥 셋)
    provider, spy, adapters = world(texts)
    groups = pages.batches(pages.pages_of(texts))
    for batch in groups:
        provider.enqueue_text(map_reply(*((p.number, ["ghg", "energy", "safety"]) for p in batch)))
    leaves = draft_v2._leaves(inputs())
    floor = sum(
        adapters.llm.dry_run(draft_v2.draft_request(inputs(), adapters, path, req, "")).estimate.worst_case_usd
        for _, path, req in leaves
    )
    maps = sum(
        adapters.llm.dry_run(draft_v2.map_request(inputs(), adapters, b)).estimate.worst_case_usd for b in groups
    )
    result = result_of(run_flow(draft_v2.FLOW, inputs(max_usd=maps + floor + 0.0001), adapters))
    assert (result["status"]["code"], result["status"]["stage"]) == ("over_budget", "before_draft")
    assert {r.prompt for r in spy.requests} == {"drafting/map@1"} and result["mapping"]["batches"] == len(groups)
    assert by_key(result)["ghg"]["pages"] and {leaf["outcome"]["status"] for leaf in result["leaves"]} == {"not_run"}


def test_s10_a_150_page_report_with_60_leaves_passes_both_bounds_at_the_real_price() -> None:
    nodes = [
        {"key": f"k{i}", "parentKey": None, "depth": 1, "title": f"잎 {i}", "requirement": "요구 " * 50}
        for i in range(60)
    ]
    big = {"nodes": nodes}
    texts = [("가상 보고서 문장 " * 200)[:1470] for _ in range(150)]  # ≈ 22만 자
    _, _, adapters = world(texts)
    data = draft_v2._map(inputs(5.0, big), adapters, {"extract": extracted()}, StepContext(resume=None))
    assert data.data["rejection"] is None
    material = "가" * 32000  # 재료 32,000자 — 셈기는 한글 1자 ≈ 1토큰이라 8k 토큰 어림보다 엄하게 잰다
    ceiling = sum(
        adapters.llm.dry_run(
            draft_v2.draft_request(inputs(5.0, big), adapters, ("잎",), "요구", material)
        ).estimate.worst_case_usd
        for _ in range(60)
    )
    assert ceiling < 5.0


def test_s10_the_guard_stops_after_the_cap() -> None:
    provider, spy, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    adapters_capped = draft_v2.DraftAdapters(
        llm=spy,
        mock=False,
        spent_usd=lambda: 0.0 if len(spy.requests) < 2 else 99.0,
        artifacts=adapters.artifacts,
    )
    leaves = by_key(result_of(run_flow(draft_v2.FLOW, inputs(), adapters_capped)))
    assert leaves["ghg"]["outcome"]["status"] == "done"
    assert leaves["energy"]["outcome"]["failure"]["kind"] == "budget_exceeded" and len(spy.requests) == 2


def test_s11_mock_routes_are_mock_and_inputs_stay() -> None:
    provider, spy, adapters = world(mock=True)
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert {r.route for r in spy.requests} == {"mock"}
    assert result["settings"]["routes"] == {"map": "mock", "draft": "mock"} and result["outlineId"] == 12


def test_s13b_resume_skips_finished_places_without_calls() -> None:
    provider, spy, adapters = world()
    saved: list[dict[str, Any]] = []
    ctx = StepContext(resume=None, on_checkpoint=lambda partial, done, total: saved.append(dict(partial)))
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    mapped = draft_v2._map(inputs(), adapters, {"extract": extracted()}, ctx)
    assert len(spy.requests) == 1 and saved[-1]["answers"] == mapped.data["answers"]
    again = draft_v2._map(inputs(), adapters, {"extract": extracted()}, StepContext(resume=saved[-1]))
    assert len(spy.requests) == 1 and again.data["answers"] == mapped.data["answers"]
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    saved.clear()
    carried = {"extract": extracted(), "map": mapped}
    draft_v2._draft(
        inputs(), adapters, carried, StepContext(resume=None, on_checkpoint=lambda p, d, t: saved.append(dict(p)))
    )
    first = saved[0]  # ghg 하나 끝난 자리
    provider.enqueue_text(draft_reply(("에너지 300", [4])))
    calls = len(spy.requests)
    resumed = draft_v2._draft(inputs(), adapters, carried, StepContext(resume=first))
    assert len(spy.requests) == calls + 1  # 남은 energy 만
    assert [a["at"] for a in resumed.data["answers"]] == ["ghg", "energy", "safety"]
    with pytest.raises(ValueError, match="차례"):
        draft_v2._draft(inputs(), adapters, carried, StepContext(resume={"answers": [{"at": "energy"}]}))
    assert OUTLINE["nodes"][0]["key"] == "env"


# ── 위끝 ⓑ·draft 가드(검증 ② B1) — _draft 를 바로 부른다. 잎 ghg(쪽 2)·energy(쪽 4)·safety(쪽 0) ──


def mapped_world() -> tuple[Any, Any, Any, StepOutput]:
    provider, spy, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    mapped = draft_v2._map(inputs(), adapters, {"extract": extracted()}, StepContext(resume=None))
    return provider, spy, adapters, mapped


def draft_worst(adapters: Any, path: tuple[str, ...], requirement: str, page: int) -> float:
    """그 잎에 그 쪽 하나를 재료로 단 S3 요청의 dry_run 위끝(_draft 가 짓는 것과 같은 요청)."""
    text = material.material([page], view_of(PAGES)).text
    request = draft_v2.draft_request(inputs(), adapters, path, requirement, text)
    return float(adapters.llm.dry_run(request).estimate.worst_case_usd)


def with_spent(adapters: Any, spy: Any, spent: Any) -> Any:
    return draft_v2.DraftAdapters(llm=spy, mock=False, spent_usd=spent, artifacts=adapters.artifacts)


def test_b1_i_the_draft_bound_on_resume_counts_only_the_leaves_left() -> None:
    """ghg 가 끝난 자리에서 이어 돌 때 ⓑ = 앞 지출 + energy 하나의 위끝. 상한을 「energy 하나」와 「ghg + energy」
    사이에 두면 돈다(잎 전부로 세면 before_draft)."""
    provider, spy, adapters, mapped = mapped_world()
    ghg = draft_worst(adapters, ("환경", "온실가스"), "배출량", 2)
    energy = draft_worst(adapters, ("환경", "에너지"), "사용량", 4)
    resume: dict[str, Any] = {
        "answers": [{"at": "ghg", "outcome": {"status": "no_material"}, "warnings": []}],
        "spentUsd": 0.0,
    }
    provider.enqueue_text(draft_reply(("에너지 300", [4])))
    capped = with_spent(adapters, spy, lambda: 0.0)
    out = draft_v2._draft(
        inputs(max_usd=energy + ghg / 2), capped, {"extract": extracted(), "map": mapped}, StepContext(resume=resume)
    )
    assert out.data["rejection"] is None
    assert out.data["answers"][1]["outcome"]["status"] == "done" and provider.pending == 0


def test_b1_ii_the_draft_bound_adds_what_was_already_spent() -> None:
    """ⓑ = 지금까지 지출 + 남은 잎 위끝. 재료 위끝만으로는 상한 밑이어도 앞 지출을 더하면 넘는다 → before_draft·S3 0."""
    _, spy, adapters, mapped = mapped_world()
    worst = draft_worst(adapters, ("환경", "온실가스"), "배출량", 2) + draft_worst(
        adapters, ("환경", "에너지"), "사용량", 4
    )
    spent = 0.01
    calls = len(spy.requests)
    capped = with_spent(adapters, spy, lambda: spent)
    out = draft_v2._draft(
        inputs(max_usd=worst + spent / 2), capped, {"extract": extracted(), "map": mapped}, StepContext(resume=None)
    )
    assert (out.data["rejection"]["code"], out.data["rejection"]["stage"]) == ("over_budget", "before_draft")
    assert len(spy.requests) == calls


def test_b1_iii_the_draft_guard_caps_at_the_bound_not_at_max_usd() -> None:
    """가드 상한 = min(max_usd, ⓑ). ⓑ 를 잰 뒤 지출이 ⓑ 에 닿으면(max_usd 보다는 아래) 첫 잎부터
    budget_exceeded·S3 0."""
    _, spy, adapters, mapped = mapped_world()
    worst = draft_worst(adapters, ("환경", "온실가스"), "배출량", 2) + draft_worst(
        adapters, ("환경", "에너지"), "사용량", 4
    )
    asked: list[int] = []

    def spent() -> float:
        asked.append(1)
        return 0.0 if len(asked) == 1 else worst  # 첫 물음 = ⓑ 셈, 그 뒤 = ⓑ 와 같은 지출

    calls = len(spy.requests)
    out = draft_v2._draft(
        inputs(max_usd=10.0),
        with_spent(adapters, spy, spent),
        {"extract": extracted(), "map": mapped},
        StepContext(resume=None),
    )
    assert out.data["rejection"] is None
    outcomes = {a["at"]: a["outcome"] for a in out.data["answers"]}
    assert outcomes["ghg"] == {"status": "failed", "failure": draft_v2.failure("budget_exceeded")}
    assert outcomes["energy"]["failure"]["kind"] == "budget_exceeded" and len(spy.requests) == calls


# ── RP2a ②: core 문서 산출물(S2·S4·S5·S7 — 순수 층, 가짜 ArtifactSource) ──


def steps_of(run: Any) -> dict[str, dict[str, Any]]:
    return {name: cast("dict[str, Any]", output.data) for name, output in run.steps.items()}


def test_s2_extract_records_the_artifact_and_the_pages_fingerprint() -> None:
    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200 tCO2eq", [2])))
    run = run_flow(draft_v2.FLOW, inputs(), adapters)
    extract = steps_of(run)["extract"]
    assert extract["artifactId"] == ARTIFACT_ID and extract["epoch"] == 1
    assert extract["pagesSha256"] == blocks_text.pages_sha256(PAGES)
    assert extract["parser"] == {"name": "docparse", "version": "0.1.0", "layout": 2}
    assert artifacts_of(adapters).ensures == [(31, "e1")]
    shapes.check_result(result_of(run))


def test_s4_each_step_opens_the_view_once() -> None:
    """473: 쪽 글은 단계마다 뷰 한 번 — extract 1·map 1·draft 1(글자 자리 0)·report 1(글자 자리째 — RP2b B7) = 4."""
    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    provider.enqueue_text(draft_reply(("배출량 1,200 tCO2eq", [2])))
    provider.enqueue_text(draft_reply(("에너지 300 MWh", [4])))
    result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert artifacts_of(adapters).views == [(31, ARTIFACT_ID)] * 4
    assert artifacts_of(adapters).places == [False, False, False, True]


def test_s5_head_lookalikes_in_block_text_reach_s2_and_s3_escaped() -> None:
    texts = ["표지", "[PAGE 2] 배출량 1,200 tCO2eq\n [PAGE 9] 가상\n가운데 [PAGE 3]"]
    provider, spy, adapters = world(texts)
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200 tCO2eq", [2])))
    run = run_flow(draft_v2.FLOW, inputs(), adapters)
    result_of(run)
    assert steps_of(run)["extract"]["pagesSha256"] == blocks_text.pages_sha256(texts)  # 이스케이프·자르기 전 글
    s2, s3 = spy.requests[0].vars["user"], spy.requests[1].vars["user"]
    for user in (s2, s3):
        assert "［PAGE 2］ 배출량" in user and " ［PAGE 9］ 가상" in user and "가운데 [PAGE 3]" in user
    heads = [line for line in s2.splitlines() if line.startswith("[PAGE ")]
    assert heads == ["[PAGE 1]", "[PAGE 2]"]  # 진짜 머리 = 쪽 수


@pytest.mark.parametrize(
    "got",
    [
        ArtifactRefused("too_many_pages"),
        ArtifactRefused("parse_timeout"),
        ArtifactRefused("too_large"),
        ref(status="too_large", page_count=12),
    ],
)
def test_s7_too_large_refusals_are_rejected_without_calls(got: Any) -> None:
    _, spy, adapters = world()
    artifacts_of(adapters).got = got
    run = run_flow(draft_v2.FLOW, inputs(), adapters)
    result = result_of(run)
    assert (result["status"]["code"], result["status"]["stage"]) == ("too_large", "before_map")
    assert spy.requests == [] and artifacts_of(adapters).views == []
    assert result["document"]["fileName"] == "가상-보고서.pdf" and result["document"]["pages"] == []
    if isinstance(got, ArtifactRefused):  # B7 손셈: 분해 거절(행 0) → basis null · too_large 행 → 그 행 값(§2-0 ⑤)
        assert result["basis"] is None
    else:
        parser = {"name": "docparse", "version": "0.1.0", "layout": 2}
        assert result["basis"] == {"artifactId": ARTIFACT_ID, "parser": parser, "epoch": 1, "pagesSha256": None}
    assert result["document"]["pageCount"] == (12 if not isinstance(got, ArtifactRefused) else 0)


@pytest.mark.parametrize(
    ("got", "code"),
    [
        (ArtifactRefused("password_protected"), "password_protected"),
        (ArtifactUnreadable("object_changed"), "object_changed"),
        (ArtifactInvalid("가짜 꼴 어김"), "artifact_invalid"),
    ],
)
def test_s7_other_refusals_fail_the_run_with_the_code_only(got: Any, code: str) -> None:
    _, spy, adapters = world()
    artifacts_of(adapters).got = got
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(draft_v2.FLOW, inputs(), adapters)
    assert isinstance(caught.value.__cause__, draft_v2.ArtifactFailed)
    assert str(caught.value.__cause__) == code and spy.requests == []


def test_s7_a_passing_outage_is_raised_as_is() -> None:
    _, spy, adapters = world()

    def outage(document_id: int, etag: str) -> Any:
        raise RunRetryLater("가짜 파서 잠깐 장애")

    artifacts_of(adapters).ensure = outage  # type: ignore[method-assign]
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(draft_v2.FLOW, inputs(), adapters)
    assert isinstance(caught.value.__cause__, RunRetryLater) and spy.requests == []


# ── RP2b B7: 블록·문장 근거 — 재료 표지 · 답 꼴 · basis · 상자 · 뷰 부름 수 ──


def test_b7_the_result_is_bullets_at_3_with_blocks_sentences_boxes_and_basis() -> None:
    provider, spy, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    provider.enqueue_text(draft_reply(("배출량 1,200 tCO2eq", [2, ("p2-b1", None), ("p2-b1", 7)])))
    provider.enqueue_text(draft_reply(("에너지 300 MWh", [("p9-b1", 0)])))
    run = run_flow(draft_v2.FLOW, inputs(), adapters)
    result = result_of(run)
    assert result["schemaVersion"] == "drafting.bullets@3" and list(result)[:3] == ["schemaVersion", "basis", "base"]
    extract = steps_of(run)["extract"]
    assert result["basis"] == {k: extract[k] for k in ("artifactId", "parser", "epoch", "pagesSha256")}
    assert result["base"] is None and {leaf["reusedFrom"] for leaf in result["leaves"]} == {None}
    assert result["basis"]["artifactId"] == ARTIFACT_ID
    (ghg,) = by_key(result)["ghg"]["outcome"]["bullets"]
    # 「배출량 1,200 tCO2eq」 = UTF-16 16 자리(3+1+5+1+6) · 문장 0 = [0, 16) → x 10 ~ 10 + 5·16
    sentence = {"index": 0, "boxes": [[10.0, 100.0, 90.0, 110.0]]}
    box = [10.0, 10.0, 100.0, 20.0]
    assert ghg["sources"] == [
        {"documentId": 31, "blockId": "p2-b1", "page": 2, "blockBox": box, "sentence": None},
        {"documentId": 31, "blockId": "p2-b1", "page": 2, "blockBox": box, "sentence": sentence},
    ]  # (p2-b1, 7) 은 범위 밖 → None 이 되어 (p2-b1, None) 과 하나로 · 차례 None 먼저
    assert ghg["unsupported"] is False
    (energy,) = by_key(result)["energy"]["outcome"]["bullets"]
    assert energy == {"text": "에너지 300 MWh", "sources": [], "unsupported": True}
    codes = [w["code"] for w in result["warnings"]]
    assert codes.count("sentence_out_of_range") == 1 and "source_not_given" in codes
    s3 = spy.requests[1]
    assert s3.schema_name == "bullets" and s3.schema is draft_v2.DraftAnswer
    assert s3.vars["system"].endswith("\n\n" + draft_v2.v2_texts.MARKER_RULES + "\n\n" + WRITING_RULES)
    assert "[B p2-b1] ⟨0⟩배출량 1,200 tCO2eq" in s3.vars["user"]


def test_b7_the_answer_schema_names_block_and_sentence() -> None:
    schema = draft_v2.ANSWER_SHAPES["draft"].json_schema()
    source = schema["$defs"]["DraftSource"]
    assert source["required"] == ["block", "s"] and source["additionalProperties"] is False
    assert schema["$defs"]["DraftLine"]["required"] == ["text", "sources"]


@pytest.mark.parametrize("case", ["over_budget_before_map", "too_large", "all_maps_failed"])
def test_b7_without_map_answers_the_report_opens_no_view(case: str) -> None:
    """뷰 부름 3 갈래(★): rejected·S2 전부 실패면 report 는 뷰를 열지 않는다(extract·map·draft 중 연 것만 —
    글자 자리 0)."""
    provider, _, adapters = world()
    max_usd = 5.0
    match case:
        case "over_budget_before_map":
            max_usd = 0.001
        case "too_large":
            artifacts_of(adapters).got = ref(status="too_large", page_count=12)
        case _:
            provider.enqueue_text("JSON 아님").enqueue_text("JSON 아님")
    result_of(run_flow(draft_v2.FLOW, inputs(max_usd=max_usd), adapters))
    expected = {"over_budget_before_map": 2, "too_large": 0, "all_maps_failed": 2}[case]
    assert artifacts_of(adapters).places == [False] * expected


def test_b7_three_views_and_no_places_when_no_bullet_has_a_source() -> None:
    """S3 답에 출처가 하나도 없으면 상자 지을 것이 없어 report 는 뷰를 열지 않는다 — [False×3]."""
    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [])))
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert artifacts_of(adapters).places == [False, False, False]
    assert by_key(result)["ghg"]["outcome"]["bullets"][0]["unsupported"] is True


def test_b7_draft_data_carries_block_ids_indexes_and_the_block_box_only() -> None:
    """RP2c §2-4 ①: 블록 상자(blockBox)는 draft data 에 싣는다 — report 가 블록을 못 찾을 때 쓴다. 글자 상자는 0."""
    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    run = run_flow(draft_v2.FLOW, inputs(), adapters)
    (ghg,) = [a for a in steps_of(run)["draft"]["answers"] if a["at"] == "ghg"]
    box = [10.0, 10.0, 100.0, 20.0]
    assert ghg["outcome"]["bullets"][0]["sources"] == [
        {"documentId": 31, "blockId": "p2-b1", "page": 2, "index": 0, "blockBox": box}
    ]
    assert steps_of(run)["map"]["groups"] == [[1, 2, 4, 5]]


def test_b7_runs_without_places_give_a_null_sentence() -> None:
    """글자 자리에 그 블록의 토막이 없으면(runs 0) sentence null — 블록 상자만."""
    provider, _, adapters = world()
    artifacts_of(adapters).document = support_document()
    artifacts_of(adapters).char_places = fake_places(SHA, page_count=5)
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    (source,) = by_key(result)["ghg"]["outcome"]["bullets"][0]["sources"]
    assert source["sentence"] is None and source["blockBox"] == [10.0, 10.0, 100.0, 20.0]


def support_document() -> dict[str, Any]:
    return document_of(PAGES)


# ── RP2c B5: 앞 실행 이어 받기 — 대본 모의로 돈 앞 결과를 base 로 ──

CHANGED = {
    "nodes": [
        {**node, "requirement": "사용량과 절감"} if node["key"] == "energy" else dict(node) for node in OUTLINE["nodes"]
    ]
}


def first_run() -> dict[str, Any]:
    """앞 실행: ghg(쪽 2·5, done) · energy(쪽 4, done) · safety(쪽 0, no_material)."""
    provider, _, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"]), (5, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200 tCO2eq", [2]), ("감축 계획 수립", [5])))
    provider.enqueue_text(draft_reply(("에너지 300 MWh 사용", [4])))
    return result_of(run_flow(draft_v2.FLOW, inputs(), adapters))


def with_base(
    found: dict[str, Any], *, outline: dict[str, Any] | None = None, rebuild: frozenset[str] = frozenset()
) -> draft_v2.DraftInputs:
    base = reuse.Base(run_id=50, outline_id=11, nodes=list(OUTLINE["nodes"]), versions_same=True, result=found)
    chosen = inputs(outline=outline or dict(OUTLINE))
    return dataclasses.replace(chosen, document_id=32, base=base, rebuild=rebuild)


def no_docs(leaf: dict[str, Any]) -> dict[str, Any]:
    """출처 documentId 를 뺀 잎 outcome(옮김은 documentId 만 바꾼다 — 처분 ⑧)."""
    found = cast("dict[str, Any]", json.loads(json.dumps(leaf["outcome"])))
    for bullet in found.get("bullets", []):
        for source in bullet["sources"]:
            assert source.pop("documentId") in (31, 32)
    return found


def test_b5_one_changed_leaf_reruns_only_that_leaf() -> None:
    before = first_run()
    provider, spy, adapters = world()
    provider.enqueue_text(map_reply((4, ["energy"])))
    provider.enqueue_text(draft_reply(("에너지 300 MWh 사용·절감", [4])))
    result = result_of(run_flow(draft_v2.FLOW, with_base(before, outline=CHANGED), adapters))
    assert [r.prompt for r in spy.requests] == ["drafting/map@1", "drafting/draft@2"]
    s2_lines = prompts.outline_lines([("energy", ("환경", "에너지"), "사용량과 절감")])
    assert s2_lines in spy.requests[0].vars["user"] and "온실가스" not in spy.requests[0].vars["user"]
    leaves, old = by_key(result), by_key(before)
    assert leaves["ghg"]["reusedFrom"] == {"runId": 50, "outlineId": 11}
    assert no_docs(leaves["ghg"]) == no_docs(old["ghg"]) and leaves["ghg"]["pages"] == old["ghg"]["pages"]
    assert {s["documentId"] for b in leaves["ghg"]["outcome"]["bullets"] for s in b["sources"]} == {32}
    assert leaves["energy"]["reusedFrom"] is None and leaves["energy"]["pages"] == [4]
    assert leaves["safety"]["reusedFrom"] is None and leaves["safety"]["outcome"] == {"status": "no_material"}
    assert result["base"] == {"runId": 50, "outlineId": 11, "matched": True, "reason": None}
    assert result["mapping"]["batches"] == 1
    assert "base_not_reused" not in [w["code"] for w in result["warnings"]]
    # 위끝 ⓐ·ⓑ: 옮긴 잎(ghg — 제목 「온실가스」)의 S3 는 하나도 재지 않는다
    drafts = [r for r in spy.dry if r.prompt == "drafting/draft@2"]
    assert len(drafts) == 3 and not any("온실가스" in r.vars["user"] for r in drafts)  # ⓐ energy·safety + ⓑ energy


def test_b5_nothing_changed_calls_nothing_and_opens_only_the_extract_view() -> None:
    before = first_run()
    _, spy, adapters = world()
    result = result_of(run_flow(draft_v2.FLOW, with_base(before), adapters))
    assert spy.requests == [] and result["mapping"] == {"batches": 0, "failedBatches": []}
    assert artifacts_of(adapters).places == [False]  # ★ extract 하나 — map·draft·report 0
    assert [leaf["reusedFrom"] for leaf in result["leaves"]] == [{"runId": 50, "outlineId": 11}] * 2 + [None]
    assert [w for w in result["warnings"] if w["code"] != "mapping_incomplete"] == [
        w for w in before["warnings"] if w["code"] != "mapping_incomplete"
    ]


def test_b5_the_origin_chain_goes_back_to_the_run_that_built_the_leaf() -> None:
    before = first_run()
    _, _, adapters = world()
    second = result_of(run_flow(draft_v2.FLOW, with_base(before), adapters))
    _, _, adapters = world()
    third = result_of(
        run_flow(
            draft_v2.FLOW,
            dataclasses.replace(
                with_base(second),
                base=dataclasses.replace(cast("reuse.Base", with_base(second).base), run_id=60, outline_id=12),
            ),
            adapters,
        )
    )
    assert by_key(third)["ghg"]["reusedFrom"] == {"runId": 50, "outlineId": 11}


@pytest.mark.parametrize("case", ["document", "settings", "versions"])
def test_b5_a_mismatch_reruns_everything_with_a_warning(case: str) -> None:
    before = first_run()
    provider, spy, adapters = world(
        PAGES if case != "document" else [*PAGES[:4], "배출 감축 계획 변경"], mock=case == "settings"
    )
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    provider.enqueue_text(draft_reply(("에너지 300", [4])))
    chosen = with_base(before)
    if case == "versions":
        chosen = dataclasses.replace(
            chosen, base=dataclasses.replace(cast("reuse.Base", chosen.base), versions_same=False)
        )
    result = result_of(run_flow(draft_v2.FLOW, chosen, adapters))
    assert len(spy.requests) == 3 and {leaf["reusedFrom"] for leaf in result["leaves"]} == {None}
    assert result["base"] == {"runId": 50, "outlineId": 11, "matched": False, "reason": case}
    assert [w["code"] for w in result["warnings"]].count("base_not_reused") == 1
    for leaf in ("ghg", "energy", "safety"):
        assert f"\n{leaf} | " in spy.requests[0].vars["user"]


def test_b5_rebuild_reruns_that_leaf_through_s2_and_s3() -> None:
    before = first_run()
    provider, spy, adapters = world()
    provider.enqueue_text(map_reply((2, ["ghg"]), (5, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200 다시", [2])))
    result = result_of(run_flow(draft_v2.FLOW, with_base(before, rebuild=frozenset({"ghg"})), adapters))
    assert [r.prompt for r in spy.requests] == ["drafting/map@1", "drafting/draft@2"]
    assert "\nghg | " in spy.requests[0].vars["user"] and "\nenergy | " not in spy.requests[0].vars["user"]
    assert by_key(result)["ghg"]["reusedFrom"] is None and by_key(result)["energy"]["reusedFrom"] is not None


def test_b5_resume_of_a_reused_draft_calls_nothing() -> None:
    before = first_run()
    _, spy, adapters = world()
    chosen = with_base(before, outline=CHANGED)
    carried = {
        "extract": StepOutput(
            data={"rejection": None, "artifactId": ARTIFACT_ID, "pagesSha256": before["basis"]["pagesSha256"]}
        )
    }
    plan = draft_v2._plan(chosen, adapters, carried)
    assert plan["s2Keys"] == ["energy"] and plan["keptPages"] == {"ghg": [2, 5], "safety": []}
    mapped = StepOutput(
        data={
            "rejection": None,
            "batches": 0,
            "groups": [],
            "answers": [],
            "reuse": {**plan, "s2Keys": [], "keptPages": {**plan["keptPages"], "energy": []}},
        }
    )
    first = draft_v2._draft(chosen, adapters, {**carried, "map": mapped}, StepContext(resume=None))
    answers = cast("list[dict[str, Any]]", first.data["answers"])
    again = draft_v2._draft(chosen, adapters, {**carried, "map": mapped}, StepContext(resume={"answers": answers[:1]}))
    assert spy.requests == [] and again.data["answers"] == first.data["answers"]


# ── RP2c B6: 이슈 482 ──


@dataclasses.dataclass
class GoneInPlaces(Artifacts):
    """글자 자리째 연 뷰에서만 쪽 2 의 블록이 사라진 가짜(산출물이 바뀐 것처럼)."""

    def view(self, document_id: int, artifact_id: int, *, places: bool = False) -> Any:
        if places:
            self.views.append((document_id, artifact_id))
            self.places.append(places)
            return view_of([*PAGES[:1], "", *PAGES[2:]], artifact_id=artifact_id, places=True)
        return super().view(document_id, artifact_id)


def test_b6_1_a_block_gone_from_the_places_view_keeps_the_run_done() -> None:
    provider, spy, adapters = world()
    adapters = dataclasses.replace(adapters, artifacts=GoneInPlaces(PAGES))
    provider.enqueue_text(map_reply((2, ["ghg"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert result["status"] == {"status": "done"} and len(spy.requests) == 2
    (source,) = by_key(result)["ghg"]["outcome"]["bullets"][0]["sources"]
    box = [10.0, 10.0, 100.0, 20.0]
    assert source == {"documentId": 31, "blockId": "p2-b1", "page": 2, "blockBox": box, "sentence": None}
    missing = [w for w in result["warnings"] if w["code"] == "source_block_missing"]
    assert [(w["key"], w["page"]) for w in missing] == [("ghg", 2)]


def test_b6_2_a_block_id_equal_to_a_table_id_fails_the_step_before_any_call() -> None:
    from esgapi.core.tests.artifact_fakes import block, fake_document, table

    provider, spy, adapters = world()
    artifacts_of(adapters).document = fake_document(
        SHA,
        page_count=5,
        blocks=[
            block("p2-t1", "배출량 1,200", page=2),
            block("p2-tb", "", page=2, kind="table", table_id="p2-t1"),
        ],
        tables=[table("p2-t1", [["배출량", "1,200"]], page=2)],
    )
    provider.enqueue_text(map_reply((2, ["ghg"])))
    with pytest.raises(FlowStepFailed) as caught:
        run_flow(draft_v2.FLOW, inputs(), adapters)
    assert "p2-t1" in str(caught.value.__cause__ or caught.value)
    assert [r.prompt for r in spy.requests] == ["drafting/map@1"]  # S3 0


def test_b6_3_a_page_whose_first_block_is_all_over_8000_is_no_material_and_truncated() -> None:
    long = "가" * 8_100 + "."
    provider, spy, adapters = world(["표지", f"{long} {long}", "", "", ""])
    provider.enqueue_text(map_reply((2, ["ghg"])))
    result = result_of(run_flow(draft_v2.FLOW, inputs(), adapters))
    assert by_key(result)["ghg"]["outcome"] == {"status": "no_material"}
    assert [r.prompt for r in spy.requests] == ["drafting/map@1"]
    cut = [w for w in result["warnings"] if w["code"] == "material_truncated"]
    assert [(w["key"], w["message"]) for w in cut] == [("ghg", draft_v2.CUT_ALL)]


# ── RPA1 B7: 흐름 입력 칸 models(AI 설정 판의 모델 칸 둘) ──

SLOT_MODELS = draft_v2.StageModels(
    map=draft_v2.StageModel(route="standard-openai-41", temperature=0.3, max_output_tokens=3000),
    draft=draft_v2.StageModel(route="light-openai-41", temperature=0.9, max_output_tokens=6500),
)


def run_with(chosen: Any, *, mock: bool = False) -> tuple[Any, dict[str, Any]]:
    provider, spy, adapters = world(mock=mock)
    provider.enqueue_text(map_reply((2, ["ghg"]), (4, ["energy"])))
    provider.enqueue_text(draft_reply(("배출량 1,200", [2])))
    provider.enqueue_text(draft_reply(("에너지 300", [4])))
    return spy, result_of(run_flow(draft_v2.FLOW, chosen, adapters))


def test_rpa1_b7_the_slot_values_reach_s2_and_s3() -> None:
    spy, result = run_with(dataclasses.replace(inputs(), models=SLOT_MODELS))
    assert [(r.prompt, r.route, r.temperature, r.max_output_tokens) for r in spy.requests] == [
        ("drafting/map@1", "standard-openai-41", 0.3, 3000),
        ("drafting/draft@2", "light-openai-41", 0.9, 6500),
        ("drafting/draft@2", "light-openai-41", 0.9, 6500),
    ]
    assert {r.timeout_ms for r in spy.requests} == {draft_v2.TIMEOUT_MS}  # 시간 상한은 칸 밖
    assert result["settings"] == {
        "routes": {"map": "standard-openai-41", "draft": "light-openai-41"},
        "promptIds": {"map": "drafting/map@1", "draft": "drafting/draft@2"},
    }


def test_rpa1_b7_the_bounds_are_measured_with_the_slot_caps() -> None:
    """위끝 ⓐ·ⓑ(dry_run)도 칸의 경로·위끝으로 잰다 — 코드 상수로 재면 위끝 가드가 판과 다른 요청을 잰다."""
    spy, _ = run_with(dataclasses.replace(inputs(), models=SLOT_MODELS))
    assert spy.dry
    assert {(r.prompt, r.route, r.max_output_tokens) for r in spy.dry} == {
        ("drafting/map@1", "standard-openai-41", 3000),
        ("drafting/draft@2", "light-openai-41", 6500),
    }


def test_rpa1_b7_mock_changes_only_the_routes() -> None:
    """mock 은 경로를 바꾸고 위끝은 min(칸 값, 4000)이다(temperature 는 칸 값). 칸 값이 모의 모델의 출력 상한(4000)
    안이면 칸 값 그대로다 — 상한을 넘는 칸은 RPA4 B8(MARC-ISSUE-490)."""
    within = draft_v2.StageModels(
        map=SLOT_MODELS.map, draft=dataclasses.replace(SLOT_MODELS.draft, max_output_tokens=3500)
    )
    spy, result = run_with(dataclasses.replace(inputs(), models=within), mock=True)
    assert [(r.route, r.temperature, r.max_output_tokens) for r in spy.requests] == [
        ("mock", 0.3, 3000),
        ("mock", 0.9, 3500),
        ("mock", 0.9, 3500),
    ]
    assert result["settings"]["routes"] == {"map": "mock", "draft": "mock"}


def test_rpa1_b7_a_saved_draft_system_still_gets_the_marker_rules() -> None:
    saved = dataclasses.replace(inputs().texts, draft_system="⟦RPA1-draft_system⟧ 지어낸 초안 지시 글")
    spy, _ = run_with(dataclasses.replace(inputs(), texts=saved))
    drafts = [r.vars["system"] for r in spy.requests if r.prompt == "drafting/draft@2"]
    assert drafts and all(
        text == f"⟦RPA1-draft_system⟧ 지어낸 초안 지시 글\n\n{MARKER_RULES}\n\n{WRITING_RULES}" for text in drafts
    )


def test_rpq1_b3_the_tail_and_the_map_text_reach_the_provider() -> None:
    """기본 판: S3 system = 칸 글 + 꼬리 둘 · S2 system = v2 map 글. 경로·온도·위끝은 그대로(코드 모델)."""
    spy, _ = run_with(inputs())
    maps = [r for r in spy.requests if r.prompt == "drafting/map@1"]
    drafts = [r for r in spy.requests if r.prompt == "drafting/draft@2"]
    assert maps and all(r.vars["system"] == DEFAULT_TEXTS.map_system for r in maps)
    assert drafts and all(
        r.vars["system"] == f"{DEFAULT_TEXTS.draft_system}\n\n{MARKER_RULES}\n\n{WRITING_RULES}" for r in drafts
    )
    assert {(r.route, r.temperature, r.max_output_tokens) for r in spy.requests} == {("light-openai-41", 0.0, 4000)}


def test_rpa1_b7_the_code_models_are_the_old_requests() -> None:
    """기본 값(CODE_MODELS)은 RPA1 앞 상수 그대로 — s7 의 단언과 같은 값."""
    spy, result = run_with(inputs())
    assert {(r.route, r.temperature, r.max_output_tokens) for r in spy.requests} == {("light-openai-41", 0.0, 4000)}
    assert result["settings"]["routes"] == {"map": "light-openai-41", "draft": "light-openai-41"}


# ── RPA4 B4 · B8 — v2 자리 끼움(재료가 실제로 실림) · 모의 위끝 min(칸, 4000)(MARC-ISSUE-490) ──


def _users(spy: Any, prompt: str) -> list[str]:
    return [cast("str", r.vars["user"]) for r in spy.requests if r.prompt == prompt]


def test_rpa4_b4_no_slot_glyph_reaches_the_provider_and_the_material_is_in() -> None:
    spy, _ = run_with(inputs())
    maps, drafts = _users(spy, "drafting/map@1"), _users(spy, "drafting/draft@2")
    assert maps and drafts
    for user in maps + drafts:
        assert v2_texts.PAGES_SLOT not in user and v1_texts.PAGES_SLOT not in user
    assert all("[PAGE 2]" in user and "[PAGE 4]" in user for user in maps)
    assert "\n[페이지 글]\n[PAGE 1]\n" in maps[0]
    assert maps[0].startswith("[목차 잎 — key | 제목 경로 | 요구 내용]\nghg | 환경 > 온실가스 | ")
    assert (
        drafts[0].startswith("[목차 잎] 환경 > 온실가스\n[요구 내용] ")
        and "\n\n[자료]\n[PAGE 2]\n[B p2-b1] ⟨0⟩" in drafts[0]
    )
    assert "\n\n[자료]\n[PAGE 4]\n[B p4-b1] ⟨0⟩" in drafts[1]


def test_rpa4_b4_a_saved_text_with_moved_slots_still_gets_the_material() -> None:
    saved = dataclasses.replace(
        inputs().texts,
        map_user="⟦RPA4-map_user⟧ 지어낸 붙이기 글 {페이지 글} 다음에 {목차}",
        draft_user="⟦RPA4-draft_user⟧ {페이지 글} · {요구 내용} · {제목 경로}",
    )
    spy, _ = run_with(dataclasses.replace(inputs(), texts=saved))
    maps, drafts = _users(spy, "drafting/map@1"), _users(spy, "drafting/draft@2")
    assert maps and drafts
    for user in maps + drafts:
        assert v2_texts.PAGES_SLOT not in user and v1_texts.PAGES_SLOT not in user and "{목차}" not in user
    assert (
        maps[0].startswith("⟦RPA4-map_user⟧ 지어낸 붙이기 글 [PAGE 1]\n")
        and "다음에 ghg | 환경 > 온실가스 | " in maps[0]
    )
    assert drafts[0].startswith("⟦RPA4-draft_user⟧ [PAGE 2]\n[B p2-b1] ⟨0⟩") and drafts[0].endswith(
        " · 환경 > 온실가스"
    )


def _synthetic_cap() -> int:
    """가상 모델 상한을 core 설정(models.synthetic.json — 모의 실행기가 읽는 길)에서 읽는다."""
    return min(m.max_output_tokens for m in resolve_route(load_config(default_config_sources(synthetic=True)), "mock"))


def test_rpa4_b8_the_mock_cap_is_the_synthetic_models_cap() -> None:
    assert draft_v2.MOCK_MAX_OUTPUT_TOKENS == _synthetic_cap() == 4000


def test_rpa4_b8_mock_cuts_a_slot_over_the_synthetic_cap_and_the_run_ends() -> None:
    spy, result = run_with(dataclasses.replace(inputs(), models=SLOT_MODELS), mock=True)
    assert [(r.route, r.temperature, r.max_output_tokens) for r in spy.requests] == [
        ("mock", 0.3, 3000),
        ("mock", 0.9, 4000),
        ("mock", 0.9, 4000),
    ]
    assert spy.dry and {(r.route, r.max_output_tokens) for r in spy.dry} == {("mock", 3000), ("mock", 4000)}
    assert [leaf["outcome"]["status"] for leaf in result["leaves"]] == ["done", "done", "no_material"]
    assert all(len(leaf["outcome"]["bullets"]) == 1 for leaf in result["leaves"][:2])
    assert result["mapping"] == {"batches": 1, "failedBatches": []}


@pytest.mark.parametrize(("given", "sent"), [(4001, 4000), (4000, 4000), (3999, 3999)])
def test_rpa4_b8_the_mock_cap_is_the_smaller_of_the_slot_and_4000(given: int, sent: int) -> None:
    chosen = draft_v2.StageModels(
        map=dataclasses.replace(SLOT_MODELS.map, max_output_tokens=given),
        draft=dataclasses.replace(SLOT_MODELS.draft, max_output_tokens=given),
    )
    spy, _ = run_with(dataclasses.replace(inputs(), models=chosen), mock=True)
    assert {r.max_output_tokens for r in spy.requests} == {sent}


def test_rpa4_b8_live_keeps_the_slot_cap_over_4000() -> None:
    spy, _ = run_with(dataclasses.replace(inputs(), models=SLOT_MODELS), mock=False)
    assert [r.max_output_tokens for r in spy.requests if r.prompt == "drafting/draft@2"] == [6500, 6500]
    assert {r.max_output_tokens for r in spy.dry if r.prompt == "drafting/draft@2"} == {6500}
