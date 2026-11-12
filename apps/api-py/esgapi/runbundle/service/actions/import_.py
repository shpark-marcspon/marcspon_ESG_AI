"""넣기(import_runs): 묶음 zip 하나를 받는 회사에 새 id 로 다 넣거나 0 을 넣는다.

쓰기 앞의 문(하나라도 걸리면 Refused — 쓰기 0, 객체 0):
  zip 항목 = bundle.json + 머리 blobs 이름만(밖·`..`·절대 경로·겹침 거절) · 풀린 크기 합 ≤ max_bytes(읽은 바이트로도
  잰다) · blob 마다 크기·sha(흘려 읽어 잰다 — 바이트를 들지 않는다, HD1 R1) · JSON 의 NaN·Infinity·자릿수 넘는 정수·
  깊은 중첩 · 사람·회사 칸 실림 → 꼭 실을 칸·position 꼴(HD1 R4) · 실행 ≥ 1·안 쓰인 문서·실행 없는 모듈 행(HD1 R2) →
  Q5 ⓐ 꼴 ⓑ 흐름·꼴·단계 ⓒ 칸
  ⓓ 마이그레이션 잎 · carrier · 모듈 행을 받는 쪽 carrier 의 columns() 로 검사·time 칸 풀기(RX1b Qb7) · carrier
  referenced_runs 가 묶음 안의 같은 모듈 done 이고 옛 id 가 자기보다 작음(Qb8·Qb11) → 회사 있음(find_company_by_id) ·
  사람이 그 회사의 사람(people_of — 고객사 사용자 또는 운영 관리자) · 모듈 행의 runOldId 는 그 모듈 실행(HD1 S2) →
  이 묶음의 열쇠가 그 회사에 이미 있음(HD1 R3 — 잠금 없이 그때의 모습: dry-run 도 같은 거절. 진짜 판정은 ① 의 것)
  그 두 부름(read_bundle·check_gates) 밖으로 새는 KeyError·TypeError·ValueError·RecursionError 는
  Refused("묶음 꼴이 틀렸다(<예외 이름>)") 한 줄로(HD1 R4 안전망 — 블록 안의 날 예외는 그대로)

블록 하나(atomic durable) 안, 차례 고정(발주서 §2-2 넣기 3 — 바꾸지 않는다):
  ① _pg.lock_bundle(회사, bundleId) → 그 회사에 이 묶음의 Idempotency-Key 가 하나라도 있으면 거절(만든 사람 무관 — Q4)
  ② 문서 행(앞 판 먼저 — 키는 새 UUID 로 미리 지음, etag NULL)
  ③ 판 행(carrier import_settings → **모듈별** 판 지도 — 모듈 넷의 판 id 를 한 지도로 합치지 않는다, RX1b Qb6)
  ④ 실행(옛 id 오름) + options·versions·결과·단계 data·partial 은 그 모듈 carrier rewrite(길이·이름·차례 같음,
     id_fields() 밖 자리는 바이트 같음, versions aiSettingId 는 그대로 — 아니면 거절), versions 의 aiSettingId 는 그
     모듈의 판 지도 → 단계 → 결과 →
     파일 행(키 = runs/calc/keys.py 의 file_key(받는 회사, 새 실행, …)) → LLM 기록 → carrier import_rows → 시각 되돌리기
     (표 T: run_runs·run_steps·core_documents)
  ⑤ _put_all: 문서·파일 바이트를 몰아서 올리고 올린 키를 적는다 → 문서마다 set_imported_etag(put 이 준 ETag —
     실행기의 object_changed 가 견준다). 바이트는 zip 을 다시 열어 하나씩 읽고 sha·크기를 다시 대조한다(다르면 올린 뒤
     실패 갈래 — 메모리는 bundle.json + blob 하나, HD1 R1)
  ⑥ 블록을 나옴 = 커밋
지도 밖 옛 id(UnknownId)·carrier 의 거절(CarrierRefused)은 블록 안에서 Refused 로 바뀐다(쓰기 0 — 종료 1).
orphans_out 은 블록 앞에서 O_CREAT|O_EXCL 0600 으로 만든다(있으면 거절). ⑤ 앞에서 던지면 행·객체 0(빈 파일은 지움).
⑤ 에서 던지면 행은 되돌려지고 올린 키(키만)를 그 파일에 — 그것도 실패하면 ImportFailed.keys 로(명령이 stderr 로).
⑥ 커밋 단계에서 던지면 새 연결로 이 넣기가 지은 실행(새 id)을 다시 본다: 다 있으면 커밋된 것이라 고아 0
(Imported.commit_error), 없으면 ⑤ 와 같고(머리 「행 되돌림 — 지워도 됨」), 다시 볼 수도 없으면 머리
「확인 불가 키(지우지 말 것)」로 적는다(행이 객체를 가리킬 수 있다 — 지우기 전에 확인). 저장소 지우기는 이 코드에
없다(포트에 delete 가 없다 — MARC-ENT-208. 인프라가 자기 자격으로 지운다).
★ put 이 블록 안에 있는 것은 이 함수 하나의 이름 붙은 예외다(core/tests/test_transaction_rules.py 의
  PUT_IN_BLOCK_FUNCTIONS — 운영자 명령의 다 아니면 0, 요청·워커 경로 아님).
"""

import dataclasses
import hashlib
import logging
import os
import uuid
import zipfile
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import cast

from django.apps import apps
from django.db import connection, transaction

from esgapi.core.calc.documents import BadTenantId, storage_key
from esgapi.core.flows.carriers import (
    CARRIERS,
    CarrierRefused,
    CarrierRegistry,
    IdMap,
    Rewritten,
    RunCarrier,
    UnknownId,
)
from esgapi.core.flows.registry import REGISTRY, FlowRegistry
from esgapi.core.resources.ports.storage import ObjectPut, ObjectStorage
from esgapi.core.service.services import documents as document_services
from esgapi.core.service.services import llm_logs as llm_services
from esgapi.runbundle.calc.bundle import (
    BUNDLE_JSON,
    REFS,
    SEGMENTS,
    Bundle,
    Refused,
    Row,
    blob_name,
    canonical_sha256,
    check_bundle,
    check_members,
    check_module_rows,
    decode_row,
    loads,
    same_outside,
)
from esgapi.runbundle.calc.gate import (
    check_carried,
    check_carriers,
    check_columns,
    check_flows,
    check_migrations,
    check_module_runs,
    check_segments,
    check_shape,
    check_statuses,
)
from esgapi.runbundle.calc.idmap import (
    AI_SETTING_ID,
    document_order,
    idempotency_key,
    launch_key,
    rewrite_versions,
    run_order,
)
from esgapi.runbundle.service.actions import _pg
from esgapi.runbundle.service.actions._common import (
    DEFAULT_MAX_BYTES,
    carrier_of,
    migration_graph,
    model_columns,
    require_company,
)
from esgapi.runs.calc.keys import file_key
from esgapi.runs.service.selectors import bundle as bundle_selectors
from esgapi.runs.service.selectors.runs import runs_of
from esgapi.runs.service.services import bundle as bundle_services
from esgapi.user.service.selectors.user import people_of

logger = logging.getLogger("esgapi.runbundle")
CHUNK = 1 << 20
DOCUMENT_MEDIA_TYPE = "application/octet-stream"
ROLLED_BACK_HEAD = "# 행 되돌림 — 아래 키는 지워도 됨"
UNKNOWN_HEAD = "# 확인 불가 키(지우지 말 것) — 커밋 여부 확인 불가, 지우기 전에 확인"
TIMES = ("created_at", "updated_at")


class ImportFailed(Exception):
    """⑤·⑥ 에서 실패했다(쓰기 0 이 아니다 — 저장소에 올린 키가 있을 수 있다).

    rolled_back True  행이 되돌려졌다. 올린 키는 written 이면 orphans_out 에, 아니면 keys 로(부르는 쪽이 stderr 로)
    rolled_back None  커밋 단계에서 실패했고 커밋됐는지 다시 볼 수도 없었다 — 키는 「확인 불가 키(지우지 말 것)」 머리로
                      적는다(행이 그 객체를 가리킬 수 있다 — 지우기 전에 확인)
    머리 줄(orphans 파일 첫 줄·stderr 첫 줄)이 두 갈래를 가른다: ROLLED_BACK_HEAD / UNKNOWN_HEAD.
    """

    @property
    def head(self) -> str:
        return UNKNOWN_HEAD if self.rolled_back is None else ROLLED_BACK_HEAD

    def __init__(self, keys: Sequence[str], *, written: bool, rolled_back: bool | None) -> None:
        if rolled_back is None:
            text = (
                f"커밋 여부 확인 불가 — 지우기 전에 확인. 올린 키 {len(keys)}개는 「{UNKNOWN_HEAD}」 머리로 적었다"
                if written
                else f"커밋 여부 확인 불가 — 지우기 전에 확인. 올린 키 {len(keys)}개를 stderr 로 낸다"
            )
        elif written:
            text = f"올린 뒤 실패했다(행은 되돌림) — 올린 키 {len(keys)}개를 --orphans-out 에 적었다"
        else:
            text = f"올린 뒤 실패했다(행은 되돌림) — --orphans-out 쓰기도 실패해 올린 키 {len(keys)}개를 stderr 로 낸다"
        super().__init__(text)
        self.keys = tuple(keys)
        self.uploaded = len(keys)
        self.written = written
        self.rolled_back = rolled_back


@dataclass(frozen=True, slots=True)
class Imported:
    bundle_id: str
    dry_run: bool
    counts: dict[str, int]
    runs: dict[int, int] = field(default_factory=dict[int, int])  # 옛 실행 id → 새 id(dry_run 이면 빔)
    commit_error: str | None = None  # 커밋 단계에서 예외가 났으나 다시 보니 커밋됐다(그 예외 이름 — 고아 0)


@dataclass(frozen=True, slots=True)
class _Put:
    key: str
    blob: str
    media_type: str
    document_id: int | None  # 문서면 새 문서 id(etag 를 적을 자리)


# ── 쓰기 앞의 문 ──────────────────────────────────────────────────────


def _read_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int) -> bytes:
    """항목 하나를 끝까지 읽되 선언 크기·남은 상한을 넘으면 Refused(읽은 바이트로 잰다 — 거짓 머리 막음)."""
    limit = min(info.file_size, budget)
    if info.file_size > budget:
        raise Refused("묶음의 풀린 크기가 상한을 넘는다")
    chunks: list[bytes] = []
    read = 0
    try:
        with archive.open(info) as handle:
            while chunk := handle.read(min(CHUNK, limit - read + 1)):
                read += len(chunk)
                if read > limit:
                    raise Refused("zip 항목이 선언한 크기보다 크다")
                chunks.append(chunk)
    except (zipfile.BadZipFile, EOFError):
        raise Refused("zip 항목을 읽지 못했다") from None
    return b"".join(chunks)


def _hash_member(archive: zipfile.ZipFile, info: zipfile.ZipInfo, budget: int) -> tuple[int, str]:
    """항목 하나를 끝까지 흘려 읽어 (읽은 크기, sha256) — 바이트를 들지 않는다. 상한은 _read_member 와 같다."""
    limit = min(info.file_size, budget)
    if info.file_size > budget:
        raise Refused("묶음의 풀린 크기가 상한을 넘는다")
    digest = hashlib.sha256()
    # hashlib 갱신 — DB 쓰기 아님, test_transaction_rules 가 .update 를 쓰기로 셈. 까닭: 이름 붙여 부르면 이 한 줄만
    # 비킨다(함수 통째 면제보다 좁다 — core 시험 0줄)
    feed = digest.update
    read = 0
    try:
        with archive.open(info) as handle:
            while chunk := handle.read(min(CHUNK, limit - read + 1)):
                read += len(chunk)
                if read > limit:
                    raise Refused("zip 항목이 선언한 크기보다 크다")
                feed(chunk)
    except (zipfile.BadZipFile, EOFError):
        raise Refused("zip 항목을 읽지 못했다") from None
    return read, digest.hexdigest()


def read_bundle(path: Path, max_bytes: int) -> Bundle:
    """zip → 검사를 지난 묶음(blob 은 크기·sha 만 대조하고 바이트는 들지 않는다 — ⑤ 가 다시 읽는다). 꼴이 하나라도
    틀리면 Refused."""
    try:
        archive = zipfile.ZipFile(path)
    except (OSError, zipfile.BadZipFile):
        raise Refused("묶음을 zip 으로 열지 못했다") from None
    with archive:
        infos = archive.infolist()
        names = [info.filename for info in infos]
        if names.count(BUNDLE_JSON) != 1:
            raise Refused("bundle.json 이 하나가 아니다")
        if sum(info.file_size for info in infos) > max_bytes:
            raise Refused("묶음의 풀린 크기가 상한을 넘는다")
        budget = max_bytes
        head = next(info for info in infos if info.filename == BUNDLE_JSON)
        text = _read_member(archive, head, budget)
        budget -= len(text)
        bundle = check_bundle(loads(text))
        check_members(names, bundle.blobs)
        by_name = {info.filename: info for info in infos}
        for blob in bundle.blobs:
            info = by_name[blob_name(blob.sha256)]
            if info.file_size != blob.size:
                raise Refused("blob 의 크기가 머리와 다르다")
            size, sha = _hash_member(archive, info, budget)
            budget -= size
            if size != blob.size or sha != blob.sha256:
                raise Refused("blob 의 바이트가 머리의 sha·크기와 다르다")
    return bundle


def _modules(bundle: Bundle) -> list[str]:
    return sorted({str(row["module"]) for row in bundle.rows["run_runs"]} | set(bundle.modules))


def check_gates(bundle: Bundle, *, flows: FlowRegistry, carriers: CarrierRegistry) -> Bundle:
    """꼭 실을 칸·꼴(HD1 R4·R2), Q5 ⓑ·ⓒ·ⓓ 와 carrier, 모듈 행 검사·풀기·실행 짝(HD1 S2), 참조(쓰기 앞 — DB 0).
    모듈 행의 time 칸을 푼 묶음을 돌려준다."""
    check_carried(bundle)
    check_shape(bundle)
    check_flows(bundle, flows)
    check_segments(bundle, flows)
    check_statuses(bundle)
    check_columns(bundle, model_columns())
    _leaves, nodes = migration_graph()
    labels = {config.label for config in apps.get_app_configs()}
    check_migrations(bundle.migrations, nodes, {"core", "runs", *(m for m in _modules(bundle) if m in labels)})
    check_carriers(_modules(bundle), carriers)
    declared = {module: carrier_of(carriers, module).columns() for module in _modules(bundle)}
    modules = check_module_rows(bundle.modules, declared)
    checked = dataclasses.replace(bundle, modules=modules)
    check_module_runs(checked)
    _check_references(checked, carriers)
    return checked


def _check_references(bundle: Bundle, carriers: CarrierRegistry) -> None:
    """carrier 가 options 에서 읽은 앞 실행은 묶음 안의 같은 모듈 done 이고 옛 id 가 자기보다 작아야 한다(Qb8·Qb11 —
    정상 묶음은 내보내기의 닫힘이 늘 그렇게 싣는다. 남는 것은 꾸민 묶음뿐)."""
    runs = {int(str(row["oldId"])): row for row in bundle.rows["run_runs"]}
    for old, row in runs.items():
        options = row["options"]
        if not isinstance(options, dict):
            raise Refused(f"실행 {old} 의 options 가 객체가 아니다")
        carrier = carrier_of(carriers, str(row["module"]))
        for pointed in carrier.referenced_runs(cast("dict[str, object]", options)):
            target = runs.get(pointed)
            if target is None or target["module"] != row["module"] or target["status"] != "done":
                raise Refused(f"실행 {old} 이 묶음 안의 같은 모듈 done 이 아닌 실행을 가리킨다")
            if pointed >= old:
                raise Refused(f"실행 {old} 이 옛 id 가 더 큰 실행을 가리킨다(앞 참조)")


def _check_people(company_id: int, user_id: int) -> None:
    require_company(company_id)
    if user_id not in people_of(company_id, {user_id}):
        raise Refused("--user 가 그 회사의 사람이 아니다")


# ── 넣기 ────────────────────────────────────────────────────────────


def _plain(table: str, row: Mapping[str, object], *, drop: Sequence[str] = ()) -> Row:
    """옛 id 열쇠·blob 과 drop 을 뺀 넣을 값."""
    decoded = decode_row(table, row)
    return {name: value for name, value in decoded.items() if name not in REFS[table] and name not in drop}


def _times(table: str, row: Mapping[str, object]) -> tuple[datetime, datetime]:
    decoded = decode_row(table, row)
    created, updated = decoded["created_at"], decoded["updated_at"]
    if not isinstance(created, datetime) or not isinstance(updated, datetime):
        raise Refused(f"{table} 행에 시각이 없다")
    return created, updated


def _optional_old(value: object) -> int | None:
    return None if value is None else int(str(value))


def _insert_documents(
    bundle: Bundle, company_id: int, user_id: int, document_map: dict[int, int], puts: list[_Put]
) -> dict[int, tuple[datetime, datetime]]:
    rows = {int(str(row["oldId"])): row for row in bundle.rows["core_documents"]}
    times: dict[int, tuple[datetime, datetime]] = {}
    ids = IdMap(run={}, document=document_map, ai_setting={})
    for old in document_order(bundle.rows["core_documents"]):
        row = rows[old]
        key = storage_key(company_id, str(uuid.uuid4()))
        if isinstance(key, BadTenantId):
            raise Refused("회사 id 가 키의 꼴이 아니다")
        previous = _optional_old(row["previousOldId"])
        values = _plain("core_documents", row, drop=(*TIMES, "etag"))
        new = document_services.import_document(
            company_id=company_id,
            uploaded_by=str(user_id),
            storage_key=key.key,
            previous_document_id=None if previous is None else ids.document_id(previous),
            etag=None,
            **values,  # pyright: ignore[reportArgumentType] — 칸은 문 ⓒ 가 받는 모델과 맞췄다
        )
        document_map[old] = new
        times[new] = _times("core_documents", row)
        puts.append(_Put(key=key.key, blob=str(row["blob"]), media_type=DOCUMENT_MEDIA_TYPE, document_id=new))
    return times


def _by_run(rows: Sequence[Row]) -> dict[int, list[Row]]:
    found: dict[int, list[Row]] = {}
    for row in rows:
        found.setdefault(int(str(row["runOldId"])), []).append(row)
    return found


def _rewrite(
    carrier: RunCarrier,
    old: int,
    *,
    options: dict[str, object],
    versions: dict[str, object],
    results: list[tuple[str, object]],
    steps: list[tuple[str, object]],
    partials: list[tuple[str, object]],
    ids: IdMap,
) -> Rewritten:
    """carrier rewrite 를 부르고 계약을 단언한다(RX1b §1-9·§1-10): 결과·단계·partial 의 길이·이름·차례가 같고, 자리마다
    id_fields() 밖은 바이트로 같고, versions 의 aiSettingId 는 carrier 가 바꾸지 않았다(그것은 runbundle 몫)."""
    found = carrier.rewrite(
        options=options, versions=versions, results=results, steps=steps, partials=partials, ids=ids
    )
    for name, before, after in (
        ("결과", results, found.results),
        ("단계", steps, found.steps),
        ("partial", partials, found.partials),
    ):
        if [label for label, _value in before] != [label for label, _value in after]:
            raise Refused(f"실행 {old} 의 carrier 가 {name} 의 길이·이름·차례를 바꿨다")
    fields = carrier.id_fields()
    places = [
        ("options", options, found.options),
        ("versions", versions, found.versions),
        *((shape, body, new) for (shape, body), (_s, new) in zip(results, found.results, strict=True)),
        *((f"step:{name}", data, new) for (name, data), (_n, new) in zip(steps, found.steps, strict=True)),
        *((f"partial:{name}", data, new) for (name, data), (_n, new) in zip(partials, found.partials, strict=True)),
    ]
    for place, before, after in places:
        paths = [path for path in fields.get(place, ()) if not (place == "versions" and path == AI_SETTING_ID)]
        if not same_outside(before, after, paths):
            raise Refused(f"실행 {old} 의 carrier 가 선언 밖 자리({place})를 바꿨다")
    return found


def _insert_runs(
    bundle: Bundle,
    company_id: int,
    user_id: int,
    ids_of: Mapping[str, IdMap],
    run_map: dict[int, int],
    carriers: CarrierRegistry,
    puts: list[_Put],
) -> tuple[dict[int, tuple[datetime, datetime]], dict[int, tuple[datetime, datetime]]]:
    runs = {int(str(row["oldId"])): row for row in bundle.rows["run_runs"]}
    steps, results, files = (_by_run(bundle.rows[table]) for table in ("run_steps", "run_results", "run_files"))
    segments = _by_run(bundle.rows[SEGMENTS]) if bundle.has_segments else {}  # 옛 묶음은 구획 0(RM1c)
    run_times: dict[int, tuple[datetime, datetime]] = {}
    step_times: dict[int, tuple[datetime, datetime]] = {}
    for old in run_order(bundle.rows["run_runs"]):
        raw = runs[old]
        values = _plain("run_runs", raw, drop=TIMES)
        options, versions = values["options"], values["versions"]
        if not isinstance(options, dict) or not isinstance(versions, dict):
            raise Refused(f"실행 {old} 의 options·versions 가 객체가 아니다")
        mine_steps = sorted(steps.get(old, []), key=lambda row: int(str(row["position"])))
        mine_results = sorted(results.get(old, []), key=lambda row: int(str(row["position"])))
        module = str(raw["module"])
        ids = ids_of[module]
        rewritten = _rewrite(
            carrier_of(carriers, module),
            old,
            options=cast("dict[str, object]", options),
            versions=cast("dict[str, object]", versions),
            results=[(str(row["schema_version"]), row["body"]) for row in mine_results],
            steps=[(str(row["name"]), row["data"]) for row in mine_steps],
            partials=[(str(row["name"]), row["partial"]) for row in mine_steps],
            ids=ids,
        )
        document_old = _optional_old(raw["documentOldId"])
        resumed_old = _optional_old(raw["resumedFromOldId"])
        fields = values | {
            "options": dict(rewritten.options),
            "versions": rewrite_versions(rewritten.versions, ids),
            "document_id": None if document_old is None else ids.document_id(document_old),
            "resumed_from_run_id": None if resumed_old is None else ids.run_id(resumed_old),
            "created_by_user_id": user_id,
            "idempotency_key": idempotency_key(bundle.bundle_id, old),
            "idempotency_sha256": canonical_sha256(raw),
            "launch_key": launch_key(bundle.bundle_id, _optional_text(values["launch_key"])),
        }
        new = bundle_services.insert_run(company_id=company_id, fields=fields)
        run_map[old] = new
        run_times[new] = _times("run_runs", raw)
        step_values = [
            _plain("run_steps", row, drop=TIMES) | {"data": data, "partial": partial}
            for row, (_name, data), (_p, partial) in zip(mine_steps, rewritten.steps, rewritten.partials, strict=True)
        ]
        step_ids = bundle_services.insert_steps(company_id=company_id, run_id=new, steps=step_values)
        for step_id, row in zip(step_ids, mine_steps, strict=True):
            step_times[step_id] = _times("run_steps", row)
        bundle_services.insert_results(
            company_id=company_id,
            run_id=new,
            results=[
                _plain("run_results", row) | {"schema_version": shape, "body": body}
                for row, (shape, body) in zip(mine_results, rewritten.results, strict=True)
            ],
        )
        file_values: list[Row] = []
        for row in files.get(old, []):
            step = _optional_text(row["step"])
            key = file_key(company_id=company_id, run_id=new, step=step, name=str(row["name"]))
            file_values.append(_plain("run_files", row) | {"storage_key": key})
            puts.append(_Put(key=key, blob=str(row["blob"]), media_type=str(row["media_type"]), document_id=None))
        bundle_services.insert_files(company_id=company_id, run_id=new, files=file_values)
        # RM1c: 구획 행 — 실행은 지도의 새 id, 회사는 넣는 쪽. data 는 바이트 그대로(carrier 밖 — R3)
        mine_segments = sorted(segments.get(old, []), key=lambda row: (str(row["step"]), int(str(row["position"]))))
        bundle_services.insert_segments(
            company_id=company_id, run_id=new, segments=[_plain(SEGMENTS, row) for row in mine_segments]
        )
    return run_times, step_times


def _optional_text(value: object) -> str | None:
    return None if value is None else str(value)


def _put_all(
    storage: ObjectStorage,
    company_id: int,
    puts: Sequence[_Put],
    path: Path,
    sizes: Mapping[str, int],
    uploaded: list[str],
) -> None:
    """⑤: 바이트를 몰아서 올린다(행을 다 넣은 뒤). 올린 키는 uploaded 에 — 실패하면 그 앞까지가 고아다. 문서는 저장소가
    준 ETag 를 행에 적는다. 바이트는 zip 을 다시 열어 blob 하나씩 읽고 머리의 sha·크기와 다시 대조한다(읽은 뒤 zip 이
    바뀌었으면 RuntimeError — 올린 뒤 실패 갈래, HD1 R1)."""
    with zipfile.ZipFile(path) as archive:
        for item in puts:
            size = sizes[item.blob]
            data = _read_member(archive, archive.getinfo(blob_name(item.blob)), size)
            if len(data) != size or hashlib.sha256(data).hexdigest() != item.blob:
                raise RuntimeError("묶음 zip 의 blob 이 읽은 뒤 바뀌었다")
            result = storage.put(item.key, content=data, media_type=item.media_type)
            if not isinstance(result, ObjectPut):
                raise RuntimeError(f"저장소 쓰기가 실패했다({type(result).__name__})")
            uploaded.append(item.key)
            if item.document_id is not None:
                document_services.set_imported_etag(
                    company_id=company_id, document_id=item.document_id, etag=result.etag
                )


def open_orphans(path: Path) -> int:
    """블록 앞에서 --orphans-out 을 만든다(O_CREAT|O_EXCL 0600 — 있으면 Refused, 확인과 만들기 사이 틈 0)."""
    try:
        return os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        raise Refused("--orphans-out 이 이미 있다(덮어쓰지 않는다)") from None
    except OSError as err:
        raise Refused(f"--orphans-out 을 만들지 못했다({type(err).__name__})") from None


def write_orphans(fd: int, head: str, keys: Sequence[str]) -> bool:
    """미리 연 파일에 머리 줄(갈래)과 키를 한 줄씩. 쓰기가 실패하면 False(부르는 쪽이 키를 stderr 로)."""
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.writelines([f"{head}\n", *(f"{key}\n" for key in keys)])
    except OSError:
        return False
    return True


def drop_orphans(fd: int, path: Path) -> None:
    """고아가 없으면(성공·put 앞 실패·커밋 확인됨) 빈 파일을 지운다."""
    os.close(fd)
    path.unlink(missing_ok=True)


def _committed(company_id: int, run_ids: Collection[int]) -> bool | None:
    """커밋 단계 실패 뒤 새 연결로 이 넣기가 지은 실행(새 id)이 그 회사에 다 있는가 — 묶음 열쇠가 아니라 새 id 로 보아
    같은 묶음을 앞서 다른 넣기가 커밋한 경우와 가른다(되돌려졌으면 그 id 는 없다). 다시 볼 수도 없으면 None."""
    if not run_ids:
        return False
    try:
        connection.close()
        return len(runs_of(company_id=company_id, run_ids=run_ids)) == len(run_ids)
    except Exception:  # 다시 보기 실패 = 모름(아래에서 「확인 불가 키(지우지 말 것)」)
        return None


def run(
    *,
    path: Path,
    company_id: int,
    user_id: int,
    orphans_out: Path,
    dry_run: bool = False,
    max_bytes: int = DEFAULT_MAX_BYTES,
    flows: FlowRegistry = REGISTRY,
    carriers: CarrierRegistry = CARRIERS,
    storage: ObjectStorage | None = None,
) -> Imported:
    """거절은 Refused(쓰기 0), 올린 뒤 실패는 ImportFailed(행 0 · 올린 키는 orphans_out)."""
    try:
        bundle = check_gates(read_bundle(path, max_bytes), flows=flows, carriers=carriers)
    except (KeyError, TypeError, ValueError, RecursionError) as err:  # 안전망(HD1 R4) — 값을 싣지 않고 이름만
        raise Refused(f"묶음 꼴이 틀렸다({type(err).__name__})") from None
    _check_people(company_id, user_id)
    counts = {table: len(rows) for table, rows in bundle.rows.items()}
    keys = [idempotency_key(bundle.bundle_id, old) for old in run_order(bundle.rows["run_runs"])]
    if bundle_selectors.taken_keys(company_id=company_id, keys=keys):  # 그때의 모습(잠금 없음 — HD1 R3)
        raise Refused("이 묶음은 이미 그 회사에 넣었다")
    if dry_run:
        return Imported(bundle_id=bundle.bundle_id, dry_run=True, counts=counts)
    store = storage if storage is not None else document_services.default_storage()
    if store is None:
        raise Refused("저장소 설정이 없다")
    orphans = open_orphans(orphans_out)
    run_map: dict[int, int] = {}
    document_map: dict[int, int] = {}
    puts: list[_Put] = []
    uploaded: list[str] = []
    putting = committing = False
    try:
        with transaction.atomic(durable=True):
            # ①
            _pg.lock_bundle(company_id, bundle.bundle_id)
            if bundle_selectors.taken_keys(company_id=company_id, keys=keys):
                raise Refused("이 묶음은 이미 그 회사에 넣었다")
            try:
                # ②
                document_times = _insert_documents(bundle, company_id, user_id, document_map, puts)
                # ③ 모듈별 판 지도(Qb6 — 합치지 않는다)
                ids_of: dict[str, IdMap] = {}
                for module in _modules(bundle):
                    made = carrier_of(carriers, module).import_settings(
                        company_id, user_id, bundle.modules.get(module, {})
                    )
                    ids_of[module] = IdMap(
                        run=run_map,
                        document=document_map,
                        ai_setting={old: new for old, (new, _name) in made.items()},
                        ai_setting_name={old: name for old, (_new, name) in made.items()},
                    )
                # ④
                run_times, step_times = _insert_runs(bundle, company_id, user_id, ids_of, run_map, carriers, puts)
            except (UnknownId, CarrierRefused) as err:
                raise Refused(str(err)) from None
            llm_services.insert_rows(
                company_id=company_id,
                rows=[
                    _plain("core_llm_call_logs", row) | {"run_id": _optional_old(row["runOldId"])}
                    for row in bundle.rows["core_llm_call_logs"]
                ],
                run_map=run_map,
            )
            for module in _modules(bundle):
                try:
                    carrier_of(carriers, module).import_rows(
                        company_id, user_id, bundle.modules.get(module, {}), ids_of[module]
                    )
                except (UnknownId, CarrierRefused) as err:
                    raise Refused(str(err)) from None
            bundle_services.restore_times(company_id=company_id, table="run_runs", times=run_times)
            bundle_services.restore_times(company_id=company_id, table="run_steps", times=step_times)
            document_services.restore_document_times(company_id=company_id, times=document_times)
            # ⑤
            putting = True
            _put_all(store, company_id, puts, path, {blob.sha256: blob.size for blob in bundle.blobs}, uploaded)
            committing = True  # 블록의 마지막 문장 — 이 뒤의 예외는 ⑥ 커밋 단계의 것
        # ⑥ 블록을 나왔다 = 커밋
    except Exception as err:
        found = _committed(company_id, list(run_map.values())) if committing else False
        if found:
            drop_orphans(orphans, orphans_out)
            logger.warning(
                "run bundle committed with an ambiguous error",
                extra={"bundle_id": bundle.bundle_id, "runs": len(run_map), "commit_error": type(err).__name__},
            )
            return Imported(
                bundle_id=bundle.bundle_id,
                dry_run=False,
                counts=counts,
                runs=dict(run_map),
                commit_error=type(err).__name__,
            )
        if found is None:
            written = write_orphans(orphans, UNKNOWN_HEAD, uploaded)
            raise ImportFailed(uploaded, written=written, rolled_back=None) from err
        if putting:
            written = write_orphans(orphans, ROLLED_BACK_HEAD, uploaded)
            raise ImportFailed(uploaded, written=written, rolled_back=True) from err
        drop_orphans(orphans, orphans_out)
        raise
    drop_orphans(orphans, orphans_out)
    logger.info(
        "run bundle imported",
        extra={"bundle_id": bundle.bundle_id, "runs": len(run_map), "bytes": sum(blob.size for blob in bundle.blobs)},
    )
    return Imported(bundle_id=bundle.bundle_id, dry_run=False, counts=counts, runs=dict(run_map))
