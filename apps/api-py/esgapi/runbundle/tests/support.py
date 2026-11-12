"""실행 묶음 시험의 준비물: 시험 레지스트리(흐름 rxtest.flow@1)·시험 carrier·회사 A 의 지어낸 세계.

전역 REGISTRY·CARRIERS 에는 달지 않는다(M1) — 시험은 flows()·carriers() 가 지은 새 등록부를 export·import_ 에 인자로
넘긴다. 행은 ① 의 services 로 심는다(runbundle 시험도 .importlinter 계약 카의 source 라 남의 models 를 import 하지
않는다). ★ 회사·사람·문서·숫자는 전부 지어낸 것이다(synthetic — 「가상…」).

세계(회사 A — 묶음에 실리는 것):
    d1 ─(앞 판)─ d2        d2 의 앞 판 d1 도 실행의 문서라 묶음 안
    d0 ─(앞 판)─ d3        d0 는 어느 실행의 문서도 아니라 묶음 밖(넣은 d3 의 앞 판은 None — S8)
    r1 failed(d2)          단계 extract done(+ 단계 파일) · judge failed, LLM 기록 둘
    r2 done(d2)            r1 을 이어 간 실행(resumed_from r1), 결과 body 에 documentId, 출력 파일 out.json,
                           LLM 기록 하나
    r3 done(d3)            versions aiSettingId 7(시험 carrier 의 판 행)
    r4 done(d1)            options retryFromRunId = r3(carrier referenced_runs — 닫힘이 r3 을 끈다)
"""

import hashlib
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from typing import cast

from esgapi.core.calc.documents import BadTenantId, storage_key
from esgapi.core.flows.binding import DocumentInput, RunContext
from esgapi.core.flows.carriers import CarrierRegistry, ColumnKind, IdMap, Rewritten
from esgapi.core.flows.registry import FlowRegistry, make_flow
from esgapi.core.flows.types import Carried, FlowStep, OutputFile, StepContext, StepOutput
from esgapi.core.service.services import documents as document_services
from esgapi.core.service.services import llm_logs as llm_services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs.calc.keys import file_key
from esgapi.runs.service.services import bundle as bundle_services
from esgapi.user.service.services.user import create_customer_user
from esgapi.user.service.utils.login import UserCreated

MODULE = "rxtest"
FLOW_ID = "rxtest.flow@1"
MODULE2 = "rxtwo"  # RX1b: 판 지도가 모듈마다 따로인지 재는 둘째 시험 모듈(판 표 id 순번이 따로 — Qb6)
FLOW2_ID = "rxtwo.flow@1"
RESULT = "rxtest.result@1"
OLD = datetime(2026, 9, 1, 1, 2, 3, tzinfo=UTC)
OLDER = datetime(2026, 8, 1, 4, 5, 6, tzinfo=UTC)
PASSWORD = "Gasang-Pw-2026!"  # 지어낸 시험 비밀번호(묶음에 실리면 안 되는 값 — S14)


@dataclass(frozen=True)
class RxInputs:
    document: DocumentInput


@dataclass(frozen=True)
class RxAdapters:
    ctx: RunContext


def _step(inputs: RxInputs, adapters: RxAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    return StepOutput(
        data={"pages": 1}, files=(OutputFile(name="out.json", media_type="application/json", content=b"{}"),)
    )


FLOW = make_flow(
    module=MODULE,
    id=FLOW_ID,
    input_shape="rxtest.document@1",
    inputs=RxInputs,
    adapters=RxAdapters,
    result_shapes=(RESULT,),
    output_files=("out.json",),
    steps=(FlowStep(name="extract", run=_step), FlowStep(name="judge", run=_step)),
)


FLOW2 = make_flow(
    module=MODULE2,
    id=FLOW2_ID,
    input_shape="rxtest.document@1",
    inputs=RxInputs,
    adapters=RxAdapters,
    result_shapes=(RESULT,),
    output_files=("out.json",),
    steps=(FlowStep(name="extract", run=_step), FlowStep(name="judge", run=_step)),
)


class RxBinding:
    """S18 의 이어 돌기용 끼움(실행기는 부르지 않는다 — 만들기 단계까지)."""

    def check_options(self, options: Mapping[str, object]) -> None:
        return None

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> object:
        return RxInputs(document=document)

    def adapters(self, ctx: RunContext) -> object:
        return RxAdapters(ctx=ctx)

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {}


@dataclass
class RxCarrier:
    """메모리의 판 하나와 options retryFromRunId·결과 body documentId 를 다시 쓰는 시험 carrier."""

    imported_settings: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    imported_rows: list[dict[str, object]] = field(default_factory=list[dict[str, object]])
    next_setting: int = 900

    def export_rows(
        self, company_id: int, run_ids: Collection[int], versions: Mapping[int, Mapping[str, object]]
    ) -> dict[str, list[dict[str, object]]]:
        settings = sorted({found for v in versions.values() if isinstance(found := v.get("aiSettingId"), int)})
        return {"rxtest_settings": [{"oldId": old, "name": f"v{old}"} for old in settings]}

    def referenced_runs(self, options: Mapping[str, object]) -> tuple[int, ...]:
        found = options.get("retryFromRunId")
        return (found,) if isinstance(found, int) else ()

    def rewrite(
        self,
        *,
        options: Mapping[str, object],
        versions: Mapping[str, object],
        results: Sequence[tuple[str, object]],
        steps: Sequence[tuple[str, object]],
        partials: Sequence[tuple[str, object]],
        ids: IdMap,
    ) -> Rewritten:
        new_options = dict(options)
        if isinstance(new_options.get("retryFromRunId"), int):
            new_options["retryFromRunId"] = ids.run_id(int(str(new_options["retryFromRunId"])))
        new_results: list[tuple[str, object]] = []
        for shape, body in results:
            new_body: object = body
            if isinstance(body, dict):
                fields = cast("dict[str, object]", body)
                old = fields.get("documentId")
                if isinstance(old, int):
                    new_body = fields | {"documentId": ids.document_id(old)}
            new_results.append((shape, new_body))
        old_setting = versions.get("aiSettingId")
        new_versions = (
            {**versions, "aiSetting": ids.ai_setting_name_of(old_setting)}
            if isinstance(old_setting, int) and "aiSetting" in versions
            else versions
        )
        return Rewritten(
            options=new_options,
            versions=new_versions,
            results=tuple(new_results),
            steps=tuple(steps),
            partials=tuple(partials),
        )

    def import_settings(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]]
    ) -> Mapping[int, tuple[int, str]]:
        found: dict[int, tuple[int, str]] = {}
        for row in rows.get("rxtest_settings", []):
            self.next_setting += 1
            found[int(str(row["oldId"]))] = (self.next_setting, f"v{self.next_setting}")
            self.imported_settings.append({"company_id": company_id, "id": self.next_setting, "name": row["name"]})
        return found

    def import_rows(
        self, company_id: int, user_id: int, rows: Mapping[str, list[dict[str, object]]], ids: IdMap
    ) -> None:
        self.imported_rows.append({"company_id": company_id, "tables": sorted(rows)})

    def columns(self) -> Mapping[str, Mapping[str, ColumnKind]]:
        return {"rxtest_settings": {"oldId": "id", "name": "plain"}}

    def id_fields(self) -> Mapping[str, tuple[str, ...]]:
        return {
            "rxtest_settings": ("oldId",),
            "options": ("retryFromRunId",),
            "versions": ("aiSettingId", "aiSetting"),
            RESULT: ("documentId",),
        }


def flows() -> FlowRegistry:
    registry = FlowRegistry()
    registry.register(FLOW)
    registry.set_default(MODULE, FLOW_ID)
    registry.register(FLOW2)
    registry.set_default(MODULE2, FLOW2_ID)
    return registry


def carriers(carrier: RxCarrier | None = None) -> CarrierRegistry:
    registry = CarrierRegistry()
    registry.register(MODULE, carrier if carrier is not None else RxCarrier())
    return registry


def a_customer(company_id: int, username: str) -> int:
    made = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name=f"가상 {username}", password=PASSWORD
    )
    assert isinstance(made, UserCreated)
    return made.user_id


@dataclass(frozen=True)
class World:
    company: int
    user: int
    documents: dict[str, int]  # d0·d1·d2·d3 → id
    runs: dict[str, int]  # r1·r2·r3·r4 → id


def _document(storage: FakeStorage, company_id: int, name: str, previous: int | None, content: bytes) -> int:
    key = storage_key(company_id, f"00000000-0000-4000-8000-{hashlib.sha256(name.encode()).hexdigest()[:12]}")
    assert not isinstance(key, BadTenantId)
    document_id = document_services.import_document(
        company_id=company_id,
        uploaded_by="1",
        storage_key=key.key,
        file_name=f"가상 {name}.pdf",
        size_bytes=len(content),
        sha256=None,
        status="uploaded",
        uploaded_at=OLD,
        report_year=2025,
        previous_document_id=previous,
        page_count=1,
        has_text=True,
    )
    etag = storage.put(key.key, content)
    document_services.set_imported_etag(company_id=company_id, document_id=document_id, etag=etag)
    document_services.restore_document_times(company_id=company_id, times={document_id: (OLDER, OLD)})
    return document_id


def _run(
    storage: FakeStorage,
    company_id: int,
    user: int,
    *,
    document: int,
    status: str,
    options: dict[str, object],
    versions: dict[str, object],
    resumed_from: int | None = None,
    steps: Sequence[tuple[str, str, dict[str, object] | None]] = (
        ("extract", "done", {"pages": 1}),
        ("judge", "done", {"z": 1, "a": 2}),
    ),
    result: object = None,
    files: Sequence[tuple[str | None, str, bytes]] = (),
    launch: str | None = None,
) -> int:
    run_id = bundle_services.insert_run(
        company_id=company_id,
        fields={
            "document_id": document,
            "module": MODULE,
            "flow_id": FLOW_ID,
            "options": options,
            "versions": {"flow": FLOW_ID, **versions},
            "purpose": "service",
            "status": status,
            "attempts": 1,
            "stalled_attempts": 0,
            "progress_attempt": 1,
            "created_by_user_id": user,
            "started_at": OLDER,
            "finished_at": OLD,
            "failed_step": "judge" if status == "failed" else None,
            "error_code": "flow_failed" if status == "failed" else None,
            "error_message": "가상 실패" if status == "failed" else None,
            "resumed_from_run_id": resumed_from,
            "launch_key": launch,
        },
    )
    step_ids = bundle_services.insert_steps(
        company_id=company_id,
        run_id=run_id,
        steps=[
            {"name": name, "position": position, "status": state, "data": data, "partial": None, "done": 1, "total": 1}
            for position, (name, state, data) in enumerate(steps)
        ],
    )
    if result is not None:
        bundle_services.insert_results(
            company_id=company_id, run_id=run_id, results=[{"position": 0, "schema_version": RESULT, "body": result}]
        )
    rows: list[dict[str, object]] = []
    for step, name, content in files:
        key = file_key(company_id=company_id, run_id=run_id, step=step, name=name)
        storage.put(key, content)
        rows.append(
            {
                "step": step,
                "name": name,
                "media_type": "application/json",
                "storage_key": key,
                "size_bytes": len(content),
                "sha256": hashlib.sha256(content).hexdigest(),
            }
        )
    bundle_services.insert_files(company_id=company_id, run_id=run_id, files=rows)
    bundle_services.restore_times(company_id=company_id, table="run_runs", times={run_id: (OLDER, OLD)})
    bundle_services.restore_times(company_id=company_id, table="run_steps", times=dict.fromkeys(step_ids, (OLDER, OLD)))
    return run_id


def _log(company_id: int, run_id: int, call_id: str, step: str) -> dict[str, object]:
    return {
        "module": MODULE,
        "ts": OLD,
        "call_id": call_id,
        "attempt": 0,
        "provider": "mock",
        "model": "mock-1",
        "prompt_id": "rxtest.judge",
        "prompt_version": 1,
        "template_hash": "t" * 64,
        "request_hash": "r" * 64,
        "input_tokens": 10,
        "output_tokens": 4,
        "cost_usd": Decimal("0.00012345"),
        "duration_ms": 12.5,
        "result_kind": "success",
        "run_id": run_id,
        "step": step,
    }


def seed(storage: FakeStorage, company_id: int) -> World:
    """회사 A 의 세계(머리말 그림). 사람은 그 회사의 고객사 사용자 하나."""
    user = a_customer(company_id, "gasang-a")
    d0 = _document(storage, company_id, "보고서 0", None, b"%PDF-1.4 gasang zero")
    d1 = _document(storage, company_id, "보고서 1", None, b"%PDF-1.4 gasang one")
    d2 = _document(storage, company_id, "보고서 2", d1, b"%PDF-1.4 gasang two")
    d3 = _document(storage, company_id, "보고서 3", d0, b"%PDF-1.4 gasang three")
    r1 = _run(
        storage,
        company_id,
        user,
        document=d2,
        status="failed",
        options={"zeta": 1, "alpha": {"b": 2, "a": 1}},
        versions={},
        steps=(("extract", "done", {"pages": 1}), ("judge", "failed", None)),
        files=(("extract", "pages.json", b'{"p":1}'),),
        launch="11111111-1111-4111-8111-111111111111",
    )
    r2 = _run(
        storage,
        company_id,
        user,
        document=d2,
        status="done",
        options={"zeta": 1, "alpha": {"b": 2, "a": 1}},
        versions={},
        resumed_from=r1,
        result={"documentId": d2, "score": 0.5},
        files=(("extract", "pages.json", b'{"p":1}'), (None, "out.json", b'{"ok":true}')),
        launch="11111111-1111-4111-8111-111111111111",
    )
    r3 = _run(
        storage,
        company_id,
        user,
        document=d3,
        status="done",
        options={},
        versions={"aiSettingId": 7, "aiSetting": "v7"},
        result={"score": 1},
    )
    r4 = _run(
        storage,
        company_id,
        user,
        document=d1,
        status="done",
        options={"retryFromRunId": r3},
        versions={"aiSettingId": None},
        result={"score": 2},
    )
    llm_services.insert_rows(
        company_id=company_id,
        rows=[
            _log(company_id, r1, "c1", "extract"),
            _log(company_id, r1, "c2", "judge"),
            _log(company_id, r2, "c3", "judge"),
        ],
        run_map={r1: r1, r2: r2},
    )
    return World(
        company=company_id,
        user=user,
        documents={"d0": d0, "d1": d1, "d2": d2, "d3": d3},
        runs={"r1": r1, "r2": r2, "r3": r3, "r4": r4},
    )


# ── 왕복의 정규형(S7·S8 — section4 의 ROUNDTRIP_DIFF 도 이것) ─────────────────


def _key_shape(key: str, company: int, runs: Mapping[int, str]) -> str:
    """저장소 키를 꼴로: 회사 → C, 실행 id → 이름표, 문서 UUID → *."""
    parts = key.split("/")
    if parts[0] == "runs":
        return "/".join(
            ["runs", "C" if int(parts[1]) == company else parts[1], runs.get(int(parts[2]), parts[2]), *parts[3:]]
        )
    return "/".join(["companies", "C" if int(parts[1]) == company else parts[1], "documents", "*", *parts[4:]])


def snapshot(
    company: int, runs: Mapping[str, int], documents: Mapping[str, int], settings: Mapping[int, str]
) -> dict[str, object]:
    """그 회사의 실행·문서를 runs·core selector 로 읽어 id·회사·사람·키·넣은 때 칸을 이름표로 바꾼 꼴."""
    from dataclasses import asdict

    from esgapi.core.service.selectors.documents import Document, find_document, version_chain
    from esgapi.core.service.selectors.llm_usage import usage_by_run, usage_by_step
    from esgapi.runs.service.selectors.runs import find_run, output_file, run_files, run_page, run_results, step_rows
    from esgapi.user.service.selectors.user import people_of

    run_label = {run_id: label for label, run_id in runs.items()}
    document_label = {document_id: label for label, document_id in documents.items()}

    def document_shape(document: Document) -> dict[str, object]:
        shape = asdict(document)
        shape |= {
            "id": document_label.get(document.id, "밖"),
            "company_id": "C",
            "uploaded_by": "U",
            "storage_key": _key_shape(document.storage_key, company, run_label),
            "previous_document_id": None
            if document.previous_document_id is None
            else document_label.get(document.previous_document_id, "밖"),
        }
        return shape

    found: dict[str, object] = {}
    for label, run_id in sorted(runs.items()):
        run = find_run(company_id=company, run_id=run_id)
        assert run is not None, label
        options = dict(run.options)
        if isinstance(options.get("retryFromRunId"), int):
            options["retryFromRunId"] = run_label[int(str(options["retryFromRunId"]))]
        versions = dict(run.versions)
        if isinstance(versions.get("aiSettingId"), int):
            versions["aiSettingId"] = settings[int(str(versions["aiSettingId"]))]
            if "aiSetting" in versions:  # 판 이름도 같은 이름표(받는 쪽은 새 이름 — RX1b)
                versions["aiSetting"] = versions["aiSettingId"]
        head = asdict(run) | {
            "id": label,
            "company_id": "C",
            "document_id": None if run.document_id is None else document_label[run.document_id],
            "created_by_user_id": "U",
            "resumed_from_run_id": None if run.resumed_from_run_id is None else run_label[run.resumed_from_run_id],
            "options": options,
            "options_order": list(run.options),
            "versions": versions,
        }
        results: list[object] = []
        for result in run_results(company_id=company, run_id=run_id):
            raw: object = result.body
            body = raw
            if isinstance(raw, dict):
                fields = cast("dict[str, object]", raw)
                if isinstance(fields.get("documentId"), int):
                    body = fields | {"documentId": document_label[int(str(fields["documentId"]))]}
            results.append((result.position, result.schema_version, body))
        files = [
            asdict(file) | {"storage_key": _key_shape(file.storage_key, company, run_label), "created_at": "넣은 때"}
            for file in run_files(company_id=company, run_id=run_id)
        ]
        output = output_file(company_id=company, run_id=run_id, name="out.json")
        steps = step_rows(company_id=company, run_id=run_id)
        found[label] = {
            "run": head,
            "steps": [asdict(step) | {"data_order": None if step.data is None else list(step.data)} for step in steps],
            "results": results,
            "files": files,
            "output": None if output is None else _key_shape(output.storage_key, company, run_label),
            "usage": usage_by_run(company_id=company, run_ids=frozenset({run_id})).get(run_id),
            "usage_by_step": usage_by_step(company_id=company, run_id=run_id),
            "person": bool(people_of(company, {run.created_by_user_id})),
        }
    for label, document_id in sorted(documents.items()):
        document = find_document(company_id=company, document_id=document_id)
        assert document is not None, label
        chain = version_chain(company_id=company, document_id=document_id)
        assert isinstance(chain, tuple)
        found[label] = {
            "document": document_shape(document),
            "chain": [document_label.get(item.id, "밖") for item in chain],
        }
    page = run_page(company_id=company, module=MODULE, status=None, document_id=None, limit=50, offset=0)
    found["page"] = [run_label.get(run.id, "밖") for run, _name in page.runs]
    return found


def cut_chain(snap: dict[str, object]) -> dict[str, object]:
    """S8(m5): A 의 사슬을 묶음에 없는 첫 문서(이름표 「밖」)에서 양쪽으로 자른 꼴 — 그 문서와 그 너머를 버린다."""
    cut = dict(snap)
    for label, value in snap.items():
        if isinstance(value, dict) and "chain" in value:
            entry = cast("dict[str, object]", value)
            chain = list(cast("list[str]", entry["chain"]))
            document = dict(cast("dict[str, object]", entry["document"]))
            if "밖" in chain:
                here = chain.index(label)
                outside = [i for i, item in enumerate(chain) if item == "밖"]
                left = max([i for i in outside if i < here], default=-1)
                right = min([i for i in outside if i > here], default=len(chain))
                chain = chain[left + 1 : right]
            if document.get("previous_document_id") == "밖":
                document["previous_document_id"] = None
            cut[label] = {"document": document, "chain": chain}
    return cut
