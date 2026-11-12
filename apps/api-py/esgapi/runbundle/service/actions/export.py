"""내보내기(export_runs): 한 회사의 고른 실행과 그 닫힘을 묶음 zip 하나로 쓴다. 쓰기 0(DB·저장소).

차례(발주서 §2-2):
  1. 회사 있음(find_company_by_id) — 없으면 Refused
  2. 블록 하나(atomic durable) 첫 문장 _pg.read_only_snapshot() 뒤 읽기 전부: 고름(Q9·RX1b Qb10) → 닫힘(Q8·Qb8,
     고정점) → 판정 → runs bundle_rows · 문서(실행의 문서) · LLM 기록 · carrier export_rows → 모듈 행을 carrier 의
     columns() 로 검사(Qb7)
       - --runs 는 done 만(아니면 거절). 창(--module --from --to)은 done 만 고르고 나머지는 상태별로 센다(건너뜀) —
         --max-runs 는 창 안의 모든 상태를 센다
       - 이어 가기 사슬(resumed_from_run_id)이 끈 앞 실행은 done·failed 를 기록으로 싣고, queued·processing·회사 밖이면
         거절
       - carrier referenced_runs 가 끈 앞 실행은 **같은 회사·같은 모듈·done** 만(Qb8). 아니면 --runs 는 거절, 창은 그
         실행을 건너뛰고 「참조 밖」으로 센다 — 지도 밖 id 를 그대로 싣는 길 0
       - carrier 없는 모듈의 실행이면 거절(닫힌 기본)
  3. 블록 밖: 임시 파일(같은 폴더, 0600·O_EXCL)을 열고 저장소 get 을 읽는 대로 zip 에 쓴다(메모리는 객체 하나 — HD1 R1).
     문서는 크기·etag, 파일은 크기·sha 가 행과 다르면 거절. 문서 blob 이름은 잰 sha. 같은 바이트가 문서·실행 파일
     둘이면 blob 하나에 role shared(HD1 R6). 풀린 합(blob + bundle.json)이 넣기 기본 상한(_common.DEFAULT_MAX_BYTES)을
     넘으면 거절. bundle.json 은 마지막 항목
  4. link 로 --out(있으면 거절 — 덮어쓰지 않는다). 임시 파일을 연 뒤의 어느 거절·예외에도 임시 파일은 지운다

회사의 범위는 인자 company_id 하나다(모든 selector 가 for_company). 사람 칸·키·회사 칸은 싣지 않는다(calc/bundle.py).
흐름·carrier 등록부는 인자로 받는다(기본값이 전역 — 시험은 자기 레지스트리를 넘긴다).
"""

import hashlib
import logging
import os
import uuid
import zipfile
from collections.abc import Collection, Mapping
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from django.db import transaction

from esgapi.core.conf import now as clock
from esgapi.core.flows.carriers import CARRIERS, CarrierRegistry
from esgapi.core.flows.registry import REGISTRY, FlowRegistry
from esgapi.core.resources.ports.storage import ObjectBytes, ObjectStorage
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.selectors import llm_logs as llm_selectors
from esgapi.core.service.services import documents as document_services
from esgapi.runbundle.calc.bundle import (
    BUNDLE_JSON,
    FORMAT,
    NOT_CARRIED,
    SEGMENTS,
    SHARED,
    TABLES,
    Refused,
    Row,
    blob_name,
    check_module_rows,
    dumps,
    encode_value,
)
from esgapi.runbundle.service.actions import _pg
from esgapi.runbundle.service.actions._common import (
    DEFAULT_MAX_BYTES,
    carrier_of,
    migration_graph,
    model_columns,
    require_company,
)
from esgapi.runs.service.selectors import bundle as bundle_selectors
from esgapi.runs.service.selectors.runs import Run, runs_of

logger = logging.getLogger("esgapi.runbundle")
SEOUL = ZoneInfo("Asia/Seoul")
DEFAULT_MAX_RUNS = 200
CLOSURE_STATUSES = frozenset({"done", "failed"})


class _OutOfReference(Exception):
    """carrier 가 가리킨 앞 실행이 같은 회사·같은 모듈·done 이 아니다(Qb8)."""


@dataclass(frozen=True, slots=True)
class RunIds:
    """--runs 1,2 — 직접 고른 실행."""

    ids: tuple[int, ...]


@dataclass(frozen=True, slots=True)
class Window:
    """--module m --from YYYY-MM-DD --to YYYY-MM-DD — 그 모듈의 실행 가운데 created_at 이 서울 날짜 양끝 안."""

    module: str
    first: date
    last: date


@dataclass(frozen=True, slots=True)
class Exported:
    bundle_id: str
    runs: int  # 실은 실행 수(닫힘 몫 포함)
    closure: int  # 그 가운데 닫힘이 더한 실행 수
    counts: dict[str, int]
    json_bytes: int
    blob_bytes: int
    zip_bytes: int
    zip_sha256: str
    skipped: dict[str, int]  # 창에서 건너뛴 done 아닌 실행 — 상태 → 수(--runs 면 빔)
    out_of_reference: int  # 창에서 참조 밖이라 건너뛴 done 실행 수(Qb8)


# ── 고름·닫힘 ─────────────────────────────────────────────────────────


def _picked(company_id: int, selection: RunIds | Window, max_runs: int) -> tuple[list[int], dict[str, int]]:
    """직접 고른 실행 id 와 창에서 건너뛴 수(상태 → 수). --runs 의 done 아님은 _closure 가 거절한다."""
    if isinstance(selection, RunIds):
        ids = sorted(set(selection.ids))
        if len(ids) > max_runs:
            raise Refused(f"고른 실행이 --max-runs({max_runs})를 넘는다")
        return ids, {}
    since = datetime.combine(selection.first, time(0), tzinfo=SEOUL)
    until = datetime.combine(selection.last + timedelta(days=1), time(0), tzinfo=SEOUL)
    if until <= since:
        raise Refused("--from 이 --to 보다 뒤다")
    picked = bundle_selectors.pick_runs(
        company_id=company_id, module=selection.module, since=since, until=until, limit=max_runs
    )
    if len(picked) > max_runs:  # 모든 상태를 센다(pick_runs 그대로 — Qb10)
        raise Refused(f"창 안 실행이 --max-runs({max_runs})를 넘는다")
    skipped: dict[str, int] = {}
    for _run_id, status in picked:
        if status != "done":
            skipped[status] = skipped.get(status, 0) + 1
    done = [run_id for run_id, status in picked if status == "done"]
    if not done:
        raise Refused("창 안에 done 실행이 없다")
    return done, skipped


def _reach(company_id: int, root: Run, carriers: CarrierRegistry, known: dict[int, Run]) -> set[int]:
    """root 와 그것이 가리키는 앞 실행의 고정점(id). 참조가 같은 회사·같은 모듈·done 이 아니면 _OutOfReference, 이어
    가기 사슬이 회사 밖·끝나지 않은 실행을 가리키면 Refused. known 은 읽은 실행의 곳간(같은 실행을 두 번 읽지 않음)."""
    members = {root.id}
    frontier: list[Run] = [root]
    while frontier:
        links: list[tuple[Run, int, bool]] = []  # (가리킨 실행, 앞 실행 id, carrier 참조인가)
        for run in frontier:
            links += [(run, pointed, True) for pointed in carrier_of(carriers, run.module).referenced_runs(run.options)]
            if run.resumed_from_run_id is not None:
                links.append((run, run.resumed_from_run_id, False))
        unknown = {pointed for _run, pointed, _ref in links} - set(known)
        if unknown:
            known |= runs_of(company_id=company_id, run_ids=unknown)
        frontier = []
        for run, pointed, by_carrier in links:
            target = known.get(pointed)
            if by_carrier and (target is None or target.module != run.module or target.status != "done"):
                raise _OutOfReference(
                    f"실행 {run.id} 이 가리킨 앞 실행 {pointed} 이 같은 회사·같은 모듈 done 이 아니다"
                )
            if target is None:
                raise Refused(f"묶음 밖·그 회사 밖 실행을 가리킨다: [{pointed}]")
            if target.status not in CLOSURE_STATUSES:
                raise Refused(f"닫힘이 끈 앞 실행 {target.id} 이 끝나지 않았다({target.status})")
            if pointed not in members:
                members.add(pointed)
                frontier.append(target)
    return members


def _closure(
    company_id: int, direct: list[int], carriers: CarrierRegistry, max_runs: int, *, window: bool
) -> tuple[dict[int, Run], set[int], int]:
    """직접 고른 실행과 그것이 가리키는 같은 회사 실행의 고정점. (실행 id → Run, 닫힘이 더한 id, 참조 밖으로 건너뛴 수).
    참조 밖(Qb8)은 --runs 면 거절, 창이면 그 실행을 건너뛴다."""
    known = runs_of(company_id=company_id, run_ids=direct)
    missing = set(direct) - set(known)
    if missing:
        raise Refused(f"그 회사에 없는 실행이다: {sorted(missing)}")
    for run_id in direct:
        if known[run_id].status != "done":
            raise Refused(f"직접 고른 실행 {run_id} 이 done 이 아니다({known[run_id].status})")
    chosen: set[int] = set()
    roots: set[int] = set()
    out = 0
    for run_id in direct:
        try:
            reached = _reach(company_id, known[run_id], carriers, known)
        except _OutOfReference as err:
            if not window:
                raise Refused(str(err)) from None
            out += 1
            continue
        roots.add(run_id)
        chosen |= reached
        if len(chosen) > max_runs:
            raise Refused(f"닫힘까지 실행이 --max-runs({max_runs})를 넘는다")
    if not chosen:
        raise Refused("고른 실행이 모두 참조 밖이다")
    return {run_id: known[run_id] for run_id in chosen}, chosen - roots, out


# ── 행 꼴 ────────────────────────────────────────────────────────────


def _carried(table: str, row: Mapping[str, object], columns: Collection[str]) -> Row:
    return {name: encode_value(row[name]) for name in columns if name not in NOT_CARRIED[table]}


def _tables(columns: Mapping[str, Mapping[str, bool]]) -> dict[str, list[str]]:
    return {table: [name for name in columns[table] if name not in NOT_CARRIED[table]] for table in TABLES}


def _read_bytes(storage: ObjectStorage, key: str, max_bytes: int) -> ObjectBytes:
    got = storage.get(key, max_bytes=max_bytes)
    if not isinstance(got, ObjectBytes):
        raise Refused(f"저장소에서 바이트를 읽지 못했다({type(got).__name__})")
    return got


def run(
    *,
    company_id: int,
    selection: RunIds | Window,
    out: Path,
    app_commit: str,
    max_runs: int = DEFAULT_MAX_RUNS,
    flows: FlowRegistry = REGISTRY,
    carriers: CarrierRegistry = CARRIERS,
    storage: ObjectStorage | None = None,
) -> Exported:
    """묶음을 out 에 쓴다. 거절은 Refused(파일 0)."""
    if out.exists():
        raise Refused("--out 이 이미 있다(덮어쓰지 않는다)")
    require_company(company_id)
    store = storage if storage is not None else document_services.default_storage()
    if store is None:
        raise Refused("저장소 설정이 없다")
    columns = model_columns()
    with transaction.atomic(durable=True):
        _pg.read_only_snapshot()
        direct, skipped = _picked(company_id, selection, max_runs)
        runs, added, out_of_reference = _closure(
            company_id, direct, carriers, max_runs, window=isinstance(selection, Window)
        )
        run_ids = sorted(runs)
        rows = bundle_selectors.bundle_rows(company_id=company_id, run_ids=run_ids)
        document_ids = sorted({run.document_id for run in runs.values() if run.document_id is not None})
        documents = document_selectors.raw_documents(company_id=company_id, document_ids=document_ids)
        logs = llm_selectors.rows_of_runs(company_id=company_id, run_ids=run_ids)
        modules: dict[str, dict[str, list[Row]]] = {}
        for module in sorted({run.module for run in runs.values()}):
            mine = [run.id for run in runs.values() if run.module == module]
            exported = carrier_of(carriers, module).export_rows(
                company_id, mine, {run_id: runs[run_id].versions for run_id in mine}
            )
            modules[module] = {
                name: [{key: encode_value(value) for key, value in row.items()} for row in table]
                for name, table in exported.items()
            }
        check_module_rows(modules, {module: carrier_of(carriers, module).columns() for module in modules})
    if len(rows.runs) != len(runs) or len(documents) != len(document_ids):
        raise Refused("읽는 사이에 행이 사라졌다")

    # ── 블록 밖: 바이트 — 읽는 대로 임시 zip 에 쓴다(메모리는 객체 하나, HD1 R1) ──
    leaves, _nodes = migration_graph()
    bundle_id = str(uuid.uuid4())
    fd, temp = _temp_file(out)
    try:  # 임시 파일을 연 뒤부터 link 까지 한 곳 — 어느 거절·예외에도 지운다(거절은 파일 0)
        with os.fdopen(fd, "wb") as handle, zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as bundle:
            blobs: dict[str, tuple[int, str]] = {}  # sha → (크기, role)
            total = 0

            def keep(data: bytes, sha: str, role: str) -> str:
                """같은 sha 는 한 번 쓴다. 같은 바이트가 문서·실행 파일 둘이면 role 은 shared(HD1 R6)."""
                nonlocal total
                if sha in blobs:
                    size, was = blobs[sha]
                    blobs[sha] = (size, was if was == role else SHARED)
                    return sha
                total += len(data)
                if total > DEFAULT_MAX_BYTES:
                    raise Refused("묶음의 풀린 크기가 넣기 기본 상한을 넘는다")
                blobs[sha] = (len(data), role)
                bundle.writestr(blob_name(sha), data)
                return sha

            limit = document_services.max_upload_bytes()
            document_rows: list[Row] = []
            in_bundle = set(document_ids)
            for document in documents:
                got = _read_bytes(store, str(document["storage_key"]), limit)
                if len(got.data) != document["size_bytes"] or (
                    document["etag"] is not None and got.etag != document["etag"]
                ):
                    raise Refused(f"문서 {document['id']} 의 바이트가 행과 다르다")
                previous = document["previous_document_id"]
                document_rows.append(
                    {
                        "oldId": document["id"],
                        "previousOldId": previous if previous in in_bundle else None,
                        "blob": keep(got.data, hashlib.sha256(got.data).hexdigest(), "document"),
                        **_carried("core_documents", document, columns["core_documents"]),
                    }
                )
            file_rows: list[Row] = []
            for file in rows.files:
                got = _read_bytes(store, str(file["storage_key"]), int(str(file["size_bytes"])))
                sha = hashlib.sha256(got.data).hexdigest()
                if len(got.data) != file["size_bytes"] or sha != file["sha256"]:
                    raise Refused(f"실행 {file['run_id']} 의 파일 {file['name']} 바이트가 행과 다르다")
                file_rows.append(
                    {
                        "runOldId": file["run_id"],
                        "blob": keep(got.data, sha, "run_file"),
                        **_carried("run_files", file, columns["run_files"]),
                    }
                )

            run_rows = [
                {
                    "oldId": row["id"],
                    "documentOldId": row["document_id"],
                    "resumedFromOldId": row["resumed_from_run_id"],
                    **_carried("run_runs", row, columns["run_runs"]),
                }
                for row in rows.runs
            ]
            tables: dict[str, list[Row]] = {
                "core_documents": document_rows,
                "run_runs": run_rows,
                "run_steps": [
                    {"runOldId": row["run_id"], **_carried("run_steps", row, columns["run_steps"])}
                    for row in rows.steps
                ],
                "run_results": [
                    {"runOldId": row["run_id"], **_carried("run_results", row, columns["run_results"])}
                    for row in rows.results
                ],
                "run_files": file_rows,
                "core_llm_call_logs": [
                    {"runOldId": row["run_id"], **_carried("core_llm_call_logs", row, columns["core_llm_call_logs"])}
                    for row in logs
                ],
                # RM1c: 구획 행((실행, 단계, 차례) — 임대·id·회사·시각 둘은 싣지 않는다. data 는 바이트 그대로 — R3)
                SEGMENTS: [
                    {"runOldId": row["run_id"], **_carried(SEGMENTS, row, columns[SEGMENTS])} for row in rows.segments
                ],
            }
            counts = {table: len(tables[table]) for table in TABLES}
            header = {
                "format": FORMAT,
                "bundleId": bundle_id,
                "createdAt": clock().isoformat(),
                "appCommit": app_commit,
                "sourceCompanyId": company_id,
                "migrations": leaves,
                "flows": sorted({str(row["flow_id"]) for row in rows.runs}),
                "shapes": sorted({str(row["schema_version"]) for row in rows.results}),
                "tables": _tables(columns),
                "counts": counts,
                "blobs": [{"sha256": sha, "size": size, "role": role} for sha, (size, role) in sorted(blobs.items())],
                "rows": {**tables, "modules": modules},
            }
            text = dumps(header)
            if total + len(text) > DEFAULT_MAX_BYTES:
                raise Refused("묶음의 풀린 크기가 넣기 기본 상한을 넘는다")
            bundle.writestr(BUNDLE_JSON, text)  # 마지막 항목(읽는 쪽은 이름으로 찾는다 — 차례를 보지 않는다)
        try:
            os.link(temp, out)
        except FileExistsError:
            raise Refused("--out 이 이미 있다(덮어쓰지 않는다)") from None
    finally:
        Path(temp).unlink(missing_ok=True)
    with out.open("rb") as handle:
        zip_sha = hashlib.file_digest(handle, "sha256").hexdigest()
    zip_bytes = out.stat().st_size
    done = Exported(
        bundle_id=bundle_id,
        runs=len(run_rows),
        closure=len(added),
        counts=counts,
        json_bytes=len(text),
        blob_bytes=total,
        zip_bytes=zip_bytes,
        zip_sha256=zip_sha,
        skipped=skipped,
        out_of_reference=out_of_reference,
    )
    logger.info(
        "run bundle exported",
        extra={"bundle_id": bundle_id, "runs": done.runs, "zip_bytes": zip_bytes},
    )
    return done


def _temp_file(out: Path) -> tuple[int, str]:
    temp = str(out.parent / f".{out.name}.{uuid.uuid4().hex}.part")
    return os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), temp
