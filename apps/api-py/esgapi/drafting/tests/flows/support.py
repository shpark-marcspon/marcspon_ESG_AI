"""흐름 시험의 공용 도움: 지어낸 목차·쪽 글, 진짜 LlmClient + 대본 심은 MockProvider(실제 공급사·키·네트워크 0),
부른 요청과 지출을 적는 Spy, 쪽 글로 지은 core 문서 산출물 뷰(FakeArtifactView)를 돌려주는 가짜 ArtifactSource
(Artifacts — 부름 수와 글자 자리 여부를 센다). 쪽 글 뷰는 쪽마다 body 문단 블록 `p<n>-b1` 하나이고, 글자 자리째
열면 블록마다 한 줄 토막(글자마다 폭 5pt — places_of). 글·숫자는 전부 지어낸 것이다."""

import json
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from esgapi.core.documents.contract import (
    ArtifactInvalid,
    ArtifactRef,
    ArtifactRefused,
    ArtifactUnreadable,
    ParserInfo,
)
from esgapi.core.documents.view import DocArtifactView, utf16_length
from esgapi.core.flows.types import StepOutput
from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import DryRunReport, LlmResult, Tags
from esgapi.core.tests.artifact_fakes import FakeArtifactView, block, container, fake_document, fake_places, run
from esgapi.drafting.contracts.wire import accept_outline, outline_sha256
from esgapi.drafting.flows.draft_v2 import CODE_MODELS, DEFAULT_TEXTS, DraftAdapters, DraftInputs

OUTLINE = accept_outline(
    {
        "nodes": [
            {"key": "env", "parentKey": None, "depth": 1, "title": "환경", "requirement": ""},
            {"key": "ghg", "parentKey": "env", "depth": 2, "title": "온실가스", "requirement": "배출량"},
            {"key": "energy", "parentKey": "env", "depth": 2, "title": "에너지", "requirement": "사용량"},
            {"key": "safety", "parentKey": None, "depth": 1, "title": "안전", "requirement": "재해율"},
        ]
    }
)
PAGES = ["표지", "배출량 1,200 tCO2eq", "", "에너지 사용 300 MWh", "배출 감축 계획"]
ARTIFACT_ID = 41
SHA = "a" * 64
FILE_NAME = "가상-보고서.pdf"


def inputs(max_usd: float = 5.0, outline: dict[str, Any] | None = None) -> DraftInputs:
    chosen = outline or dict(OUTLINE)
    return DraftInputs(
        project_id=7,
        outline_id=12,
        outline_sha256=outline_sha256(chosen),
        outline=chosen,
        document_id=31,
        document_etag="e1",
        texts=DEFAULT_TEXTS,
        models=CODE_MODELS,
        tags=Tags(tenant="1", module="drafting"),
        max_usd=max_usd,
    )


@dataclass
class Spy:
    client: LlmClient
    requests: list[CallRequest[Any]] = field(default_factory=list[CallRequest[Any]])
    spent: float = 0.0
    dry: list[CallRequest[Any]] = field(default_factory=list[CallRequest[Any]])
    """dry_run 으로 잰 요청(위끝 ⓐ·ⓑ 손셈 — RP2c B5)."""

    def call[T](self, request: CallRequest[T]) -> LlmResult[T]:
        self.requests.append(request)
        result = self.client.call(request)
        self.spent += sum(a.cost_usd or 0.0 for a in result.meta.attempts)
        return result

    def dry_run[T](self, request: CallRequest[T]) -> DryRunReport:
        self.dry.append(request)
        return self.client.dry_run(request)


CHAR_WIDTH = 5.0


def document_of(texts: Sequence[str]) -> dict[str, Any]:
    """쪽 글 목록 → 쪽마다 body 문단 블록 `p<n>-b1` 하나(빈 글이면 블록 0)인 문서 모델."""
    blocks = [block(f"p{n}-b1", text, page=n) for n, text in enumerate(texts, start=1) if text]
    return fake_document(SHA, page_count=len(texts), blocks=blocks)


def places_of(document: dict[str, Any]) -> dict[str, Any]:
    """문단 블록마다 한 줄 토막(y 100~110, 글자 i 의 x = 10 + 5i ~ 15 + 5i — UTF-16 자리마다)."""
    containers: list[dict[str, Any]] = []
    for found in document["blocks"]:
        size = utf16_length(found.get("text", ""))
        if size:
            x0 = [10.0 + CHAR_WIDTH * i for i in range(size)]
            runs = [run(0, 100.0, 110.0, x0, [x + CHAR_WIDTH for x in x0])]
            containers.append(container(found["id"], runs, page=found["page"]))
    return fake_places(SHA, page_count=len(document["pages"]), containers=containers)


def view_of(texts: Sequence[str], *, artifact_id: int = ARTIFACT_ID, places: bool = False) -> FakeArtifactView:
    """쪽 글 목록의 산출물 뷰(places=True 면 글자 자리째)."""
    document = document_of(texts)
    return FakeArtifactView.from_dicts(document, places_of(document) if places else None, artifact_id=artifact_id)


def ref(artifact_id: int = ARTIFACT_ID, *, status: str = "ready", page_count: int = 5) -> ArtifactRef:
    return ArtifactRef(
        id=artifact_id,
        source_sha256=SHA,
        parser=ParserInfo(name="docparse", version="0.1.0", layout=2),
        epoch=1,
        page_count=page_count,
        body_bytes=100,
        status="ready" if status == "ready" else "too_large",
    )


def extracted(artifact_id: int = ARTIFACT_ID) -> StepOutput:
    """map·draft 를 바로 부르는 시험의 extract 단계 data(뷰를 여는 열쇠)."""
    return StepOutput(data={"rejection": None, "artifactId": artifact_id})


@dataclass
class Artifacts:
    """가짜 ArtifactSource. got 이 ensure 의 결과(예외면 던짐), 뷰는 그 쪽 글로 짓는다(document 를 주면 그 문서 모델 —
    글자 자리는 char_places, 없으면 places_of)."""

    texts: Sequence[str]
    got: ArtifactRef | ArtifactRefused | ArtifactUnreadable | ArtifactInvalid | None = None
    name: str | None = FILE_NAME
    document: dict[str, Any] | None = None
    char_places: dict[str, Any] | None = None
    ensures: list[tuple[int, str]] = field(default_factory=list[tuple[int, str]])
    views: list[tuple[int, int]] = field(default_factory=list[tuple[int, int]])
    places: list[bool] = field(default_factory=list[bool])

    def ensure(self, document_id: int, etag: str) -> ArtifactRef | ArtifactRefused | ArtifactUnreadable:
        self.ensures.append((document_id, etag))
        got = ref(page_count=len(self.texts)) if self.got is None else self.got
        if isinstance(got, ArtifactInvalid):
            raise got
        return got

    def view(self, document_id: int, artifact_id: int, *, places: bool = False) -> DocArtifactView:
        self.views.append((document_id, artifact_id))
        self.places.append(places)
        if self.document is None:
            return view_of(self.texts, artifact_id=artifact_id, places=places)
        char_places = (self.char_places or places_of(self.document)) if places else None
        return FakeArtifactView.from_dicts(self.document, char_places, artifact_id=artifact_id)

    def file_name(self, document_id: int) -> str | None:
        return self.name


def artifacts_of(adapters: DraftAdapters) -> Artifacts:
    """world 가 꽂은 가짜 ArtifactSource(부름 수·결과를 시험이 본다)."""
    assert isinstance(adapters.artifacts, Artifacts)
    return adapters.artifacts


def world(texts: Sequence[str] = PAGES, *, mock: bool = False) -> tuple[MockProvider, Spy, DraftAdapters]:
    provider = MockProvider("openai")
    client = LlmClient(
        config=load_config(default_config_sources(synthetic=mock)),
        providers={"openai": provider, "mock": provider},
        prompts=PackagePromptStore(),
        log=MemorySink(),
    )
    spy = Spy(client)
    adapters = DraftAdapters(llm=spy, mock=mock, spent_usd=lambda: spy.spent, artifacts=Artifacts(texts))
    return provider, spy, adapters


def map_reply(*pairs: tuple[int, list[str]]) -> str:
    return json.dumps({"pages": [{"page": p, "keys": k} for p, k in pairs]}, ensure_ascii=False)


Cite = int | tuple[str, int | None]


def cite(item: Cite) -> dict[str, Any]:
    """쪽 번호 n → 그 쪽 블록 `p<n>-b1` 의 첫 문장(s 0), (블록, s) → 그대로."""
    if isinstance(item, int):
        return {"block": f"p{item}-b1", "s": 0}
    return {"block": item[0], "s": item[1]}


def draft_reply(*bullets: tuple[str, Sequence[Cite]]) -> str:
    """S3 답 {bullets: [{text, sources: [{block, s}]}]}."""
    found = [{"text": t, "sources": [cite(c) for c in cites]} for t, cites in bullets]
    return json.dumps({"bullets": found}, ensure_ascii=False)


def base_result(run_id: int, outline_id: int, *, outline: dict[str, Any] | None = None) -> dict[str, Any]:
    """앞 실행의 결과(drafting.bullets@3 — 손으로 지은 최소 꼴, 잎은 전부 no_material). 끼움 시험의 BaseFacts 용."""
    from esgapi.drafting.contracts.wire import leaf_keys, title_paths

    nodes = (outline or OUTLINE)["nodes"]
    paths = title_paths(nodes)
    return {
        "schemaVersion": "drafting.bullets@3",
        "basis": None,
        "base": None,
        "projectId": 7,
        "outlineId": outline_id,
        "outlineSha256": outline_sha256(outline or OUTLINE),
        "status": {"status": "done"},
        "document": {"documentId": 31, "fileName": FILE_NAME, "pageCount": 0, "textPages": 0, "pages": []},
        "leaves": [
            {
                "key": k,
                "titlePath": list(paths[k]),
                "pages": [],
                "reusedFrom": None,
                "outcome": {"status": "no_material"},
            }
            for k in leaf_keys(nodes)
        ],
        "mapping": {"batches": 0, "failedBatches": []},
        "settings": {
            "routes": {"map": "light-openai-41", "draft": "light-openai-41"},
            "promptIds": {"map": "drafting/map@1", "draft": "drafting/draft@2"},
        },
        "warnings": [],
    }
