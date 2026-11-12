"""영문번역 묶음 목록·하나 보기(GET /translation/batches · GET /translation/documents/{document_id}/batches/{batch_key}
의 몸 — 밴드 TR3b, MARC-ENT-392·393). runs(실행 열쇠·실행·단계·결과)·core(문서)·user(이름)·organization(회사 이름
— 목록만, TRC1)을 엮어 조립하므로
Action 이다(greenwash service/actions/checks.py 꼴). 꼴은 contracts/batch_shapes.py.

    batches(company_id, user_id, document_id, state, mine, limit, offset)   한 쪽(TranslationBatchPage)
    batch(company_id, document_id, batch_key)                               하나(TranslationBatchDetail) | NotFound
    find(company_id, document_id, batch_key)                                그 묶음(Found) | NotFound([모두 받기]도)

규칙(발주서 TR3b §2):
  - 묶음 열쇠 = (문서, batchKey). batchKey = 옵션 batchId ?? `run-<실행 id>`(batchId 없는 실행만 — batchId 있는 실행의
    `run-N` 은 없는 묶음). 묶음 차례 = 묶음 안 가장 새 실행(created_at·id 내림).
  - 파트마다 가장 새 실행이 latest(393), 그 앞이 earlier(새 것 먼저), round = earlier 수 + 1. part 가 셋 밖인 실행은
    뺀다.
  - state 는 파트 최신 실행만 본다(contracts/batch_shapes.py TranslationBatch.state). 거름(state·mine)은 묶은 뒤·자르기
    전, count·isNext 는 거른 뒤 묶음 수. mine = 그 묶음 문서의 uploaded_by 가 나(운영 관리자도 같은 규칙).
  - steps 는 파트 최신 실행마다 step_lines_of(끝난 실행도 — ★D: failed 실행은 멈춘 단계 뒤가 pending 으로 남고,
    실행기의 실패(attempts_exhausted·result_too_large)는 failed_step 이 null 이라 Run 칸으로 GET /runs/{id} 의 steps 를
    지을 수 없다). 앞 회차는 RunKey 칸과 digest 의 outcome 만.
★ 목록은 옵션 본문·결과 본문을 읽지 않는다: 실행은 run_keys(옵션의 batchId·part 투영)로 묶고, 결과는 digest 꼴만
  (results_of 의 schema_versions), 옵션은 그 쪽 묶음의 파트 최신 실행만 runs_of 로(pages·style·용어집 짝 수).
★ 쿼리 수(★I): 회사 이름 1 · 실행 열쇠 1 · 요약 1 · 문서 1 · 실행 ⌈그 쪽 파트 최신 실행 수/RUNS_OF_CHUNK⌉ · 단계 1 ·
  이름 1 = 6 + ⌈n/15⌉ — 쪽 20묶음·파트 셋(n ≤ 60)이면 많아야 10. 끝난 실행이 없으면 요약이, 쪽이 비면 실행·단계·이름이
  쿼리를 내지 않는다(입력이 비면 0 — checks.py 선례). 쪽이 비어도 회사 이름 1 은 낸다.
★ 실행은 RUNS_MAX 까지(새 것 먼저). 넘으면 오래된 것이 빠지고 truncated 가 true 다.
"""

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Final, cast

from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.selectors.documents import Document
from esgapi.organization.service.selectors.organization import company_name
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.runs.service.selectors.runs import Run, RunKey, RunStepLine
from esgapi.translation.contracts.batch_shapes import (
    BATCH_KEY_PATTERN,
    BatchState,
    RunStatus,
    StepStatus,
    TranslationBatch,
    TranslationBatchDetail,
    TranslationBatchEarlier,
    TranslationBatchGlossaryCounts,
    TranslationBatchPage,
    TranslationBatchPages,
    TranslationBatchPart,
    TranslationBatchPerson,
    TranslationBatchRun,
    TranslationBatchStyle,
)
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE, TranslationDigest
from esgapi.translation.contracts.shapes import Part
from esgapi.user.service.selectors.user import people_of

MODULE: Final = "translation"
RUNS_MAX: Final = 1000
"""한 번에 읽는 실행 수의 상한(새 것 먼저 — 묶음 읽기 입력의 상한도 이것. greenwash checks.py 와 같은 어림)."""
PARTS: Final[tuple[Part, ...]] = ("ceo_message", "story", "general")
UNKNOWN_USER: Final = "알 수 없는 사용자"
RUNS_OF_CHUNK: Final = 15
"""runs_of 한 번에 넘기는 실행 수(옵션 통째 — 쪽 20묶음·파트 셋 = 60 이면 쿼리 넷, 3-2-7 처분 (가))."""
ACTIVE: Final = frozenset({"queued", "processing"})
PDF_FLOW_PREFIX: Final = "translation.pdf@"
"""이 앞머리의 흐름 id 로 돈 실행은 PDF 입력이다(묶음 칸 inputKind — 밴드 TRS3)."""


@dataclass(frozen=True, slots=True)
class NotFound:
    """그런 묶음이 없다(꼴 밖 열쇠·남의 회사 문서·batchId 있는 실행의 run-N 도 이 갈래)."""


@dataclass(slots=True)
class _Group:
    document_id: int
    key: str
    newest: RunKey
    runs: dict[str, list[RunKey]] = field(default_factory=dict[str, list[RunKey]])  # 파트 → 새 것 먼저

    def latest(self) -> list[RunKey]:
        return [self.runs[p][0] for p in PARTS if p in self.runs]


def _group(keys: Sequence[RunKey]) -> list[_Group]:
    """실행 열쇠(새 것 먼저) → 묶음(처음 본 차례 = 가장 새 실행 차례)."""
    groups: dict[tuple[int, str], _Group] = {}
    for key in keys:
        if key.document_id is None or key.part not in PARTS:
            continue
        batch_key = key.batch_id if key.batch_id is not None else f"run-{key.id}"
        found = groups.setdefault((key.document_id, batch_key), _Group(key.document_id, batch_key, key))
        found.runs.setdefault(cast("str", key.part), []).append(key)
    return list(groups.values())


def _digests(company_id: int, keys: Sequence[RunKey]) -> dict[int, TranslationDigest]:
    """끝난 실행의 요약(실행 id → digest). 요약을 남기기 전의 옛 실행은 열쇠가 없다."""
    done = [k.id for k in keys if k.status == "done"]
    results = run_selectors.results_of(company_id=company_id, run_ids=done, schema_versions={DIGEST_SHAPE})
    found: dict[int, TranslationDigest] = {}
    for run_id, rows in results.items():
        body = next((r.body for r in rows if r.schema_version == DIGEST_SHAPE), None)
        if isinstance(body, dict):
            found[run_id] = cast("TranslationDigest", body)
    return found


def _state(latest: Sequence[RunKey], digests: Mapping[int, TranslationDigest]) -> BatchState:
    if any(k.status in ACTIVE for k in latest):
        return "active"
    for k in latest:
        digest = digests.get(k.id)
        if k.status == "failed" or (digest is not None and digest["outcome"] in ("rejected", "partial")):
            return "failed"
    return "done"


def _uploader(document: Document) -> int | None:
    """문서 uploaded_by 는 세션 주체 id 의 십진 글자다(core 의 문서 경로). 아니면 None."""
    return int(document.uploaded_by) if document.uploaded_by.isdecimal() else None


def _time(value: datetime | None) -> str | None:
    return to_seoul_iso(value) if value is not None else None


def _int(value: object) -> int | None:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _counts(options: Mapping[str, object]) -> TranslationBatchGlossaryCounts:
    glossary = options.get("glossary")
    found = cast("dict[str, object]", glossary) if isinstance(glossary, dict) else {}
    base, final = found.get("base"), found.get("final")
    return {
        "base": len(cast("list[object]", base)) if isinstance(base, list) else 0,
        "final": len(cast("list[object]", final)) if isinstance(final, list) else 0,
    }


def _pages(options: Mapping[str, object]) -> TranslationBatchPages | None:
    pages = options.get("pages")
    if not isinstance(pages, dict):
        return None
    found = cast("dict[str, object]", pages)
    return {"start": _int(found.get("start")), "end": _int(found.get("end"))}


def _style(options: Mapping[str, object]) -> TranslationBatchStyle | None:
    style = options.get("style")
    if not isinstance(style, dict):
        return None
    found = cast("dict[str, object]", style)
    compare, single = found.get("compareAb"), found.get("single")
    if not isinstance(compare, bool):
        return None
    if single == "A":
        return {"compareAb": compare, "single": "A"}
    if single == "B":
        return {"compareAb": compare, "single": "B"}
    return None


def _run_line(run: Run) -> TranslationBatchRun:
    """실행 → 줄(옵션에서 pages·style·짝 수만 남긴다). steps·digest 는 부르는 쪽이 채운다."""
    failed = run.status == "failed"
    return {
        "runId": run.id,
        "flowId": run.flow_id,
        "status": cast("RunStatus", run.status),
        "pages": _pages(run.options),
        "style": _style(run.options),
        "glossaryCounts": _counts(run.options),
        "createdAt": to_seoul_iso(run.created_at),
        "startedAt": _time(run.started_at),
        "finishedAt": _time(run.finished_at),
        "failedStep": run.failed_step if failed else None,
        "errorCode": run.error_code if failed else None,
        "steps": [],
        "digest": None,
    }


def _latest_lines(company_id: int, run_ids: Sequence[int]) -> dict[int, TranslationBatchRun]:
    """파트 최신 실행의 줄. runs_of 를 RUNS_OF_CHUNK 개씩 끊어 부르고 끊을 때마다 줄만 남긴다 — 옵션 통째(용어집
    500+500짝이면 실행 하나에 파이썬 객체 약 720KB, ★H)를 한 쪽 전부 한꺼번에 올리지 않는다(3-2-7 처분 (가))."""
    lines: dict[int, TranslationBatchRun] = {}
    for start in range(0, len(run_ids), RUNS_OF_CHUNK):
        chunk = run_selectors.runs_of(company_id=company_id, run_ids=run_ids[start : start + RUNS_OF_CHUNK])
        lines |= {run_id: _run_line(run) for run_id, run in chunk.items()}
    return lines


def _with(
    line: TranslationBatchRun, steps: Sequence[RunStepLine], digest: TranslationDigest | None
) -> TranslationBatchRun:
    return {
        **line,
        "steps": [
            {"step": s.name, "status": cast("StepStatus", s.status), "done": s.done, "total": s.total} for s in steps
        ],
        "digest": digest if line["status"] == "done" else None,
    }


def _earlier(key: RunKey, digests: Mapping[int, TranslationDigest]) -> TranslationBatchEarlier:
    digest = digests.get(key.id)
    return {
        "runId": key.id,
        "status": cast("RunStatus", key.status),
        "createdAt": to_seoul_iso(key.created_at),
        "finishedAt": _time(key.finished_at),
        "outcome": digest["outcome"] if digest is not None and key.status == "done" else None,
    }


def _assemble(
    company_id: int,
    groups: Sequence[_Group],
    documents: Mapping[int, Document],
    digests: Mapping[int, TranslationDigest],
) -> list[TranslationBatch]:
    """그 쪽의 묶음 → 꼴. 파트 최신 실행만 runs_of(⌈n/RUNS_OF_CHUNK⌉ 쿼리)·step_lines_of(쿼리 1)로 읽는다 — 쪽이
    비면 0."""
    latest_ids = [k.id for g in groups for k in g.latest()]
    lines = _latest_lines(company_id, latest_ids)
    steps = run_selectors.step_lines_of(company_id=company_id, run_ids=latest_ids)
    wanted = {g.newest.created_by_user_id for g in groups}
    wanted |= {u for g in groups if (u := _uploader(documents[g.document_id])) is not None}
    names = people_of(company_id, wanted) if wanted else {}

    def person(user: int | None) -> TranslationBatchPerson:
        found = names.get(user) if user is not None else None
        return {"userId": user or 0, "name": found[1] if found is not None and found[1].strip() else UNKNOWN_USER}

    out: list[TranslationBatch] = []
    for g in groups:
        document = documents[g.document_id]
        parts: list[TranslationBatchPart] = []
        for part in PARTS:
            if part not in g.runs:
                continue
            latest, *earlier = g.runs[part]
            parts.append(
                {
                    "part": part,
                    "latest": _with(lines[latest.id], steps.get(latest.id, ()), digests.get(latest.id)),
                    "earlier": [_earlier(k, digests) for k in earlier],
                    "round": len(earlier) + 1,
                }
            )
        latest_keys = g.latest()
        out.append(
            {
                "batchKey": g.key,
                # 묶음 차례를 정한 가장 새 실행은 늘 그 파트의 최신 실행이다 — 줄이 이미 있다(쿼리 0)
                "inputKind": "pdf" if lines[g.newest.id]["flowId"].startswith(PDF_FLOW_PREFIX) else "word",
                "document": {
                    "id": document.id,
                    "fileName": document.file_name,
                    "uploadedAt": _time(document.uploaded_at),
                    "uploadedBy": person(_uploader(document)),
                },
                "createdBy": person(g.newest.created_by_user_id),
                "parts": parts,
                "state": _state(latest_keys, digests),
                "doneParts": sum(k.status == "done" for k in latest_keys),
                "partCount": len(parts),
            }
        )
    return out


def _read(company_id: int, document_id: int | None) -> tuple[list[_Group], bool, dict[int, TranslationDigest]]:
    keys = run_selectors.run_keys(company_id=company_id, module=MODULE, document_id=document_id, limit=RUNS_MAX + 1)
    truncated = len(keys) > RUNS_MAX
    keys = keys[:RUNS_MAX]
    return _group(keys), truncated, _digests(company_id, keys)


def batches(
    *,
    company_id: int,
    user_id: int,
    document_id: int | None,
    state: BatchState | None,
    mine: bool,
    limit: int,
    offset: int,
) -> TranslationBatchPage:
    groups, truncated, digests = _read(company_id, document_id)
    documents = document_selectors.documents_of(
        company_id=company_id, document_ids=list(dict.fromkeys(g.document_id for g in groups))
    )
    kept = [
        g
        for g in groups
        if g.document_id in documents
        and (state is None or _state(g.latest(), digests) == state)
        and (not mine or documents[g.document_id].uploaded_by == str(user_id))
    ]
    page = kept[offset : offset + limit]
    return {
        "companyName": company_name(company_id),
        "count": len(kept),
        "isNext": offset + len(page) < len(kept),
        "truncated": truncated,
        "results": _assemble(company_id, page, documents, digests),
    }


@dataclass(frozen=True, slots=True)
class Found:
    """하나 보기·[모두 받기]가 찾은 묶음 — 묶음, 그 문서의 실행이 읽기 상한을 넘었나, 끝난 실행의 요약."""

    group: _Group
    truncated: bool
    digests: Mapping[int, TranslationDigest]


def find(*, company_id: int, document_id: int, batch_key: str) -> Found | NotFound:
    """그 문서의 그 묶음(꼴 밖 열쇠·없음·남의 회사 문서·batchId 있는 실행의 run-N 은 NotFound). 옵션 본문 0."""
    if re.fullmatch(BATCH_KEY_PATTERN, batch_key) is None:
        return NotFound()
    groups, truncated, digests = _read(company_id, document_id)
    found = next((g for g in groups if g.key == batch_key), None)
    if found is None:
        return NotFound()
    return Found(found, truncated, digests)


def batch(*, company_id: int, document_id: int, batch_key: str) -> TranslationBatchDetail | NotFound:
    found = find(company_id=company_id, document_id=document_id, batch_key=batch_key)
    if isinstance(found, NotFound):
        return found
    documents = document_selectors.documents_of(company_id=company_id, document_ids=[document_id])
    if document_id not in documents:
        return NotFound()
    (one,) = _assemble(company_id, [found.group], documents, found.digests)
    return cast("TranslationBatchDetail", {**one, "truncated": found.truncated})
