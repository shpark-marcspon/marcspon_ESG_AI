"""흐름 greenwash.engine@G1 의 도표 라벨 읽기·근거 예산 기본값·이어 돌기 막기(밴드 GE1c ④ — T11·T12·T13·T15·M2).
순수(DB 0). 문서·도표 라벨은 지어낸 것(실제 기업·보고서 0). 문서 포트 JsonDocument 는 뷰에 chart_labels 를 싣는다.

    T11  chart_labels_of: 라벨 = used · 칸 없음 = absent · 못 지음 = unavailable(셋 다 돎) · 안 실은 뷰는 올라감
    T12  extract data 「chartLabels」·stat · 벡터 행 = 도표 포함 단락 수 · 구획마다 같은 단락
    T13  지어낸 도표 문서로 끝까지: 도표 단락이 판정 근거 글에 · result@2 꼴 그대로
    T15  근거 예산 기본값 12,000 이 구획의 근거 찾기에 간다
    M2   이어 돌기: 단락 수가 같아도 단락 글이 바뀌면 · 근거 예산이 바뀌면 · 칸 없는 옛 extract 면 G1ArtifactChanged
"""

import io
from dataclasses import replace
from typing import Any, cast

import numpy as np
import pytest

from esgapi.core.documents.view import UNAVAILABLE, ChartLabelsNotLoaded, DocArtifactView
from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import (
    Carried,
    FlowStepFailed,
    OutputFile,
    Segment,
    SegmentKey,
    StepContext,
    StepOutput,
)
from esgapi.core.tests.artifact_fakes import block, fake_chart_labels, fake_document, section, table
from esgapi.greenwash.contracts import result2_shapes as r2
from esgapi.greenwash.engines.g1 import claims as cl
from esgapi.greenwash.engines.g1 import evidence as ev
from esgapi.greenwash.engines.g1.passages import Built
from esgapi.greenwash.flows import engine_g1 as E
from esgapi.greenwash.tests.flows.test_engine_g1_flow import (
    SHA,
    Answering,
    JsonDocument,
    adapters,
    inputs,
    page_blocks,
    result_of,
)

CHART_TITLE = "가상 설비 전력 추이"


def chart_document(sha: str = SHA) -> dict[str, Any]:
    """흐름 시험의 네 쪽 + 2쪽 끝에 표 하나(t9). 도표 p2-c1 의 값 낱말이 그 표 칸에 있어 표를 먹는다 — 도표 단위가 표
    단락 자리를 갈음하므로 단락 수는 라벨이 있든 없든 5 다(M2 의 「행 수가 같아도」)."""
    blocks = [b for n in (1, 2, 3, 4) for b in page_blocks(n)]
    blocks.append(block("p2-t", page=2, order=10, kind="table", table_id="t9", section_id="s1"))
    return fake_document(
        sha,
        page_count=4,
        blocks=blocks,
        tables=[table("t9", [["구분", "2025"], ["가상 설비", "56"]], page=2)],
        sections=[section("s1", "가상 환경 경영", page_start=1, page_end=4)],
    )


def labels(sha: str = SHA) -> dict[str, Any]:
    chart = {
        "id": "p2-c1",
        "page": 2,
        "bbox": [10.0, 10.0, 200.0, 200.0],
        "form": "bar",
        "orientation": "vertical",
        "title": CHART_TITLE,
        "multi_series": False,
        "categories": ["2025"],
    }
    word = {
        "chart": "p2-c1",
        "container": "t9:r1c1",
        "start": 0,
        "end": 2,
        "text": "56",
        "bbox": [20.0, 20.0, 30.0, 30.0],
        "role": "value",
        "label": {"category": "2025", "series": None, "status": "ok"},
    }
    return fake_chart_labels(sha, charts=[chart], words=[word], page_count=4)


def charted(chart_labels: Any = None, provider: Answering | None = None) -> E.G1Adapters:
    return replace(adapters(provider), document=JsonDocument(chart_document(), chart_labels=chart_labels))


def extract_data(out: StepOutput) -> dict[str, Any]:
    return cast("dict[str, Any]", out.data)


def view_with(chart_labels: Any) -> DocArtifactView:
    fake = JsonDocument(chart_document(), chart_labels=chart_labels)
    return fake.view(fake.ensure())


# ── T11 라벨 상태 ──


@pytest.mark.parametrize(
    ("given", "state", "has"), [(None, "absent", False), (UNAVAILABLE, "unavailable", False), ("labels", "used", True)]
)
def test_t11_chart_label_states_all_run(given: Any, state: str, has: bool) -> None:
    got, named = E.chart_labels_of(view_with(labels() if given == "labels" else given))
    assert named == state
    assert (got is not None) is has
    run = run_flow(E.g1_flow(), inputs(), charted(labels() if given == "labels" else given))
    assert run.steps["extract"].data["chartLabels"] == state
    r2.check_result(result_of(run))


def test_t11_a_view_without_labels_loaded_fails_extract_by_name() -> None:
    """안 실은 뷰(charts=False 꼴 — 포트 잘못)는 absent 로 접지 않고 extract 단계 실패로 올라간다."""

    class NotLoaded(JsonDocument):
        def view(self, ref: Any) -> DocArtifactView:
            return DocArtifactView(artifact_id=ref.id, document=self.doc, char_places=None)

    with pytest.raises(FlowStepFailed) as got:
        run_flow(E.g1_flow(), inputs(), replace(adapters(), document=NotLoaded(chart_document())))
    assert got.value.step == "extract"
    assert isinstance(got.value.__cause__, ChartLabelsNotLoaded)


# ── T12 extract data · 벡터 행 · 구획마다 같은 단락 ──


def test_t12_extract_names_the_state_and_counts_the_chart_unit() -> None:
    run = run_flow(E.g1_flow(), inputs(), charted(labels()))
    data = extract_data(run.steps["extract"])
    built = E.built_of(view_with(labels()))
    assert data["chartLabels"] == "used"
    assert data["stat"]["a 도표 단위"] == 1 and data["stat"]["a 흡수한 조각"] == 1
    assert data["passages"] == len(built.passages) == 5
    assert data["passagesSha256"] == E.passages_sha256(built)
    assert data["evidenceBudget"] == ev.BUDGET_CHARS == 12000
    assert run.steps["index"].data["count"] == 5
    assert [p.kind for p in built.passages if f"도표: {CHART_TITLE}" in p.text] == ["table"]


def test_t12_without_labels_the_extract_stat_has_no_chart_keys() -> None:
    data = extract_data(run_flow(E.g1_flow(), inputs(), charted(None)).steps["extract"])
    assert data["chartLabels"] == "absent"
    assert not {k for k in data["stat"] if k.startswith("a ")}


def test_t12_every_segment_rebuilds_the_same_chart_passages(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: list[str] = []
    real = E.check_built

    def recording(built: Any, carried: Carried) -> None:
        seen.append(E.passages_sha256(built))
        real(built, carried)

    monkeypatch.setattr(E, "check_built", recording)
    run = run_flow(E.g1_flow(), inputs(), charted(labels()))
    segments = len(cast("list[object]", run.steps["judge"].data["segments"]))
    assert len(seen) == 1 + segments  # index + 구획마다
    assert set(seen) == {run.steps["extract"].data["passagesSha256"]}


# ── T13 끝까지 · T15 예산 ──


def test_t13_the_chart_passage_reaches_the_judge_and_the_result_keeps_its_shape() -> None:
    provider = Answering()
    result = result_of(run_flow(E.g1_flow(), inputs(), charted(labels(), provider)))
    judged = [repr(c) for c in provider.calls if c.json_schema is not None and c.json_schema.name == "judge"]
    assert judged and any(f"도표: {CHART_TITLE}" in t for t in judged)
    r2.check_result(result)
    assert set(result) == {"schemaVersion", "source", "failures", "budgetTrimmed", "segments"}


def test_t15_the_frozen_budget_goes_to_every_evidence_search(monkeypatch: pytest.MonkeyPatch) -> None:
    budgets: list[int] = []
    real = ev.find_evidence

    def recording(index: ev.Index, claim: ev.Claim, ports: ev.Ports, *, budget: int = -1) -> ev.Outcome:
        budgets.append(budget)
        got = real(index, claim, ports, budget=budget)
        assert not isinstance(got, ev.Found) or got.chars <= budget
        return got

    monkeypatch.setattr(ev, "find_evidence", recording)
    run_flow(E.g1_flow(), inputs(), charted(labels()))
    assert budgets and set(budgets) == {12000}


# ── M2 이어 돌기 막기 ──


def _extract(adapters_: E.G1Adapters) -> StepOutput:
    return E.extract(inputs(), adapters_, {}, StepContext(resume=None))


def test_m2_changed_passages_with_the_same_count_are_a_named_failure() -> None:
    """extract 를 라벨 없이(옛 코드 꼴) 한 실행을 라벨 읽는 코드가 이어 돈다 — 단락 수 5 = 5 라 벡터 행 수 대조는
    지나가지만 단락 글이 다르다 → index 가 G1ArtifactChanged."""
    old = _extract(charted(None))
    assert old.data["passages"] == len(E.built_of(view_with(labels())).passages)  # 수는 같다
    with pytest.raises(E.G1ArtifactChanged, match="passagesSha256"):
        E.index(inputs(), charted(labels()), {"extract": old}, StepContext(resume=None))


def test_m2_changed_passages_are_caught_by_a_judge_segment_too() -> None:
    old = _extract(charted(None))
    vectors = np.zeros((int(extract_data(old)["passages"]), 4), dtype=np.float32)
    carried: Carried = {"extract": old, "index": _vectors(vectors)}
    with pytest.raises(E.G1ArtifactChanged, match="passagesSha256"):
        E.judge_segment(inputs(), charted(labels()), carried, _segment(), StepContext(resume=None))


def test_m2_a_changed_evidence_budget_is_a_named_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    done = _extract(charted(labels()))
    monkeypatch.setattr(ev, "BUDGET_CHARS", 8000)
    with pytest.raises(E.G1ArtifactChanged, match="evidenceBudget"):
        E.index(inputs(), charted(labels()), {"extract": done}, StepContext(resume=None))


@pytest.mark.parametrize("gone", ["passagesSha256", "evidenceBudget"])
def test_m2_an_old_extract_without_the_fields_is_a_named_failure(gone: str) -> None:
    done = _extract(charted(labels()))
    old = StepOutput(data={k: v for k, v in done.data.items() if k != gone})
    with pytest.raises(E.G1ArtifactChanged):
        E.index(inputs(), charted(labels()), {"extract": old}, StepContext(resume=None))


def test_m2_the_same_code_and_document_resume_cleanly() -> None:
    done = _extract(charted(labels()))
    out = E.index(inputs(), charted(labels()), {"extract": done}, StepContext(resume=None))
    assert out.data["count"] == 5


def _vectors(vectors: np.ndarray) -> StepOutput:
    buf = io.BytesIO()
    np.save(buf, vectors, allow_pickle=False)
    return StepOutput(
        data={"count": int(vectors.shape[0]), "dim": int(vectors.shape[1])},
        files=(OutputFile(name=E.VECTORS_FILE, media_type="application/octet-stream", content=buf.getvalue()),),
    )


def _segment() -> Any:
    return Segment(
        key=SegmentKey(kind=cl.SEGMENT_KIND, span="0-0", document_sha256=SHA, parser_version="x"),
        input={"candidates": []},
    )


# ── ⑤ 해시가 무는 것: 차례 · 구성 블록(검증 4 권고 둘) ──


def _built() -> Built:
    return E.built_of(view_with(labels()))


def test_m2_only_the_order_changed_changes_the_hash() -> None:
    """같은 단락 글·구성 블록이어도 차례가 바뀌면 다르다 — 차례가 벡터 행과 맞물린다(정렬한 해시로는 못 가름)."""
    built = _built()
    flipped = replace(built, passages=tuple(reversed(built.passages)))
    assert sorted(p.text for p in flipped.passages) == sorted(p.text for p in built.passages)
    assert E.passages_sha256(flipped) != E.passages_sha256(built)


def test_m2_only_the_members_changed_is_a_named_failure(monkeypatch: pytest.MonkeyPatch) -> None:
    """글이 같고 구성 블록(result@2 blockRanges 의 원천)만 바뀌는 고침도 이어 돌기에서 G1ArtifactChanged."""
    done = _extract(charted(labels()))
    built = _built()
    first = built.passages[0]
    moved = (replace(first, members=first.members[:-1]), *built.passages[1:])
    assert [p.text for p in moved] == [p.text for p in built.passages]
    assert E.passages_sha256(replace(built, passages=moved)) != E.passages_sha256(built)

    def rebuilt(view: DocArtifactView) -> Built:
        return replace(built, passages=moved)

    monkeypatch.setattr(E, "built_of", rebuilt)
    with pytest.raises(E.G1ArtifactChanged, match="passagesSha256"):
        E.index(inputs(), charted(labels()), {"extract": done}, StepContext(resume=None))
