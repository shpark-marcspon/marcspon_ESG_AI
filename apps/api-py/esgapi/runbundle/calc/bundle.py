"""묶음 꼴 esg.run-bundle@1(순수 — django 0). zip 하나 = `bundle.json` + `blobs/<sha256>`(같은 sha 는 하나).

    머리   format·bundleId·createdAt·appCommit·sourceCompanyId·migrations·flows·shapes·tables·counts·blobs
    rows   표마다 행. 옛 id 는 지도 열쇠로만 싣는다(oldId·documentOldId·resumedFromOldId·previousOldId·runOldId)
    blob   문서 원본·실행 파일의 바이트(행의 `blob` 칸이 sha 로 가리킨다)

싣지 않는 칸(NOT_CARRIED): id·company_id·사람 칸(uploaded_by·created_by_user_id)·storage_key·lease_expires_at·
idempotency_*. 회사·사람은 넣을 때의 인자, 키·id 는 받는 쪽이 새로 짓는다. 묶음에 그 칸이 실려 있으면 통째 거절이다
(묶음 안 id 를 믿지 않는다 — MARC-ENT-440). sourceCompanyId 는 머리의 기록일 뿐 넣기에 쓰지 않는다.
시각은 UTC ISO 글자, cost_usd 는 글자(Decimal). JSON 은 NaN·Infinity 를 쓰지도 읽지도 않는다.

구획 표 run_segments(RM1c — 일곱째 표, 635-3): 펼침 단계의 구획 행을 runOldId 로 싣는다(임대·id·회사·시각 둘 빼고).
  FORMAT 은 그대로 @1 이다(shared 의 선례). 옛 묶음(표 여섯 — tables·rows·counts 셋 다 run_segments 없음)은 그대로
  받는다(Bundle.has_segments False — 받는 쪽 문은 구획 검사를 건너뛴다). 셋 가운데 일부에만 있으면 거절.
  ★ 무효 조건: 앞 호환은 없다 — 새 꼴(표 일곱) 묶음을 RM1c 앞 코드가 받으면 「tables 의 표가 다르다」로 거절한다
  (묶음 받기는 운영자 명령이고 같은 판끼리다).
  ★ run_segments.data 는 carrier 다시 쓰기 밖이다 — 바이트 그대로 실린다. 펼침 흐름을 등록하는 밴드는 구획 data 에
  id 를 두지 않거나 carrier 에 그 자리를 선언한다.
  ★ core_llm_call_logs.segment 는 열쇠 sha 라 이미 실리고 지도가 필요 없다.
"""

import hashlib
import json
import re
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
from typing import Final, cast

FORMAT: Final = "esg.run-bundle@1"
BUNDLE_JSON: Final = "bundle.json"
BLOB_PREFIX: Final = "blobs/"
SEGMENTS: Final = "run_segments"
TABLES: Final = (
    "core_documents",
    "run_runs",
    "run_steps",
    "run_results",
    "run_files",
    "core_llm_call_logs",
    SEGMENTS,
)
LEGACY_TABLES: Final = TABLES[:-1]
"""옛 묶음(RM1c 앞 — 표 여섯)의 표. 받기만 한다."""
HEADER_KEYS: Final = frozenset(
    {
        "format",
        "bundleId",
        "createdAt",
        "appCommit",
        "sourceCompanyId",
        "migrations",
        "flows",
        "shapes",
        "tables",
        "counts",
        "blobs",
        "rows",
    }
)
# blob 의 role. "shared" = 같은 바이트가 문서와 실행 파일 둘에 쓰임(HD1 R6 — 그때만 쓴다, 두 쪽 검사를 다 지난다).
# 정상 묶음의 머리는 그대로이고 FORMAT 도 그대로다(옛 읽는 쪽은 shared 가 있는 묶음만 거절한다).
ROLES: Final = frozenset({"document", "run_file", "shared"})
SHARED: Final = "shared"
SHA256: Final = re.compile(r"[0-9a-f]{64}")
# 표마다 싣지 않는 칸(모델 칸 이름). 옛 id 칸은 아래 REFS 의 이름으로 바꿔 싣는다.
NOT_CARRIED: Final[Mapping[str, frozenset[str]]] = {
    "core_documents": frozenset({"id", "company_id", "uploaded_by", "storage_key", "previous_document_id"}),
    "run_runs": frozenset(
        {
            "id",
            "company_id",
            "created_by_user_id",
            "lease_expires_at",
            "idempotency_key",
            "idempotency_sha256",
            "document_id",
            "resumed_from_run_id",
        }
    ),
    "run_steps": frozenset({"id", "company_id", "run_id"}),
    "run_results": frozenset({"id", "company_id", "run_id", "created_at"}),
    "run_files": frozenset({"id", "company_id", "run_id", "storage_key", "created_at"}),
    "core_llm_call_logs": frozenset({"id", "company_id", "run_id", "created_at"}),
    SEGMENTS: frozenset({"id", "company_id", "run_id", "lease_expires_at", "created_at", "updated_at"}),
}
# 표마다 옛 id 열쇠(와 blob)의 이름 — 행의 칸 = 머리 tables[표] ∪ 이것
REFS: Final[Mapping[str, frozenset[str]]] = {
    "core_documents": frozenset({"oldId", "previousOldId", "blob"}),
    "run_runs": frozenset({"oldId", "documentOldId", "resumedFromOldId"}),
    "run_steps": frozenset({"runOldId"}),
    "run_results": frozenset({"runOldId"}),
    "run_files": frozenset({"runOldId", "blob"}),
    "core_llm_call_logs": frozenset({"runOldId"}),
    SEGMENTS: frozenset({"runOldId"}),
}
# 어느 표에 실려도 거절하는 사람·회사 칸(P2 꼴 — 칸 목록이 맞아도 이 이름이면 먼저 거절)
PERSON_OR_COMPANY: Final = frozenset({"company_id", "created_by_user_id", "uploaded_by", "companyId", "userId"})
DATETIME_COLUMNS: Final[Mapping[str, frozenset[str]]] = {
    "core_documents": frozenset({"uploaded_at", "created_at", "updated_at"}),
    "run_runs": frozenset({"started_at", "finished_at", "created_at", "updated_at"}),
    "run_steps": frozenset({"started_at", "finished_at", "created_at", "updated_at"}),
    "run_results": frozenset(),
    "run_files": frozenset(),
    "core_llm_call_logs": frozenset({"ts"}),
    SEGMENTS: frozenset({"started_at", "finished_at"}),
}
DECIMAL_COLUMNS: Final[Mapping[str, frozenset[str]]] = {"core_llm_call_logs": frozenset({"cost_usd"})}
# 꼭 실을 칸(HD1 R4): 넣기·문(import_·gate·idmap)이 행에서 이름으로 읽는 모델 칸. 정상 내보내기는 NOT_CARRIED 밖 모델 칸
# 전부를 실으므로 늘 있다 — 꾸민 묶음이 빼면 날 KeyError 대신 받는 쪽 문(gate.check_carried)이 Refused 로 막는다.
# 옛 id 열쇠(REFS)는 _check_row 가 이미 칸 집합으로 본다.
REQUIRED_COLUMNS: Final[Mapping[str, frozenset[str]]] = {
    "core_documents": frozenset({"size_bytes", "sha256", "created_at", "updated_at"}),
    "run_runs": frozenset(
        {"module", "flow_id", "status", "options", "versions", "launch_key", "created_at", "updated_at"}
    ),
    "run_steps": frozenset({"name", "position", "data", "partial", "created_at", "updated_at"}),
    "run_results": frozenset({"position", "schema_version", "body"}),
    "run_files": frozenset({"step", "name", "media_type", "size_bytes", "sha256"}),
    "core_llm_call_logs": frozenset(),
    SEGMENTS: frozenset({"step", "position", "kind", "key", "key_sha256", "status", "attempts"}),
}

type Row = dict[str, object]


class Refused(Exception):
    """묶음을 통째 거절한다(쓰기 0). 문장은 사람에게 보일 한 줄(값·비밀을 싣지 않는다)."""


@dataclass(frozen=True, slots=True)
class Blob:
    sha256: str
    size: int
    role: str


@dataclass(frozen=True, slots=True)
class Bundle:
    """검사를 지난 머리와 행(값은 아직 JSON 꼴 — 시각·Decimal 은 decode_row 로 푼다)."""

    bundle_id: str
    created_at: str
    app_commit: str
    source_company_id: int
    migrations: dict[str, list[str]]
    flows: list[str]
    shapes: list[str]
    tables: dict[str, list[str]]
    blobs: tuple[Blob, ...]
    rows: dict[str, list[Row]]
    modules: dict[str, dict[str, list[Row]]]
    has_segments: bool = True  # False = 옛 묶음(표 여섯 — tables·rows 에 run_segments 열쇠 없음)


# ── JSON 값 ──────────────────────────────────────────────────────────


def encode_value(value: object) -> object:
    """행의 값 → JSON 값. 시각은 UTC ISO, Decimal 은 글자. 그 밖은 그대로(dict·list·글자·수·None·bool)."""
    if isinstance(value, datetime):
        if value.tzinfo is None:
            raise ValueError("시각에 시간대가 없다")
        return value.astimezone(UTC).isoformat()
    if isinstance(value, Decimal):
        return str(value)
    return value


def decode_row(table: str, row: Mapping[str, object]) -> Row:
    """JSON 행 → 넣을 값(그 표의 시각 칸은 datetime, Decimal 칸은 Decimal). 꼴이 틀리면 Refused."""
    times = DATETIME_COLUMNS[table]
    decimals = DECIMAL_COLUMNS.get(table, frozenset())
    decoded: Row = {}
    for name, value in row.items():
        if value is not None and name in times:
            if not isinstance(value, str):
                raise Refused(f"{table}.{name} 의 시각 꼴이 틀렸다")
            try:
                moment = datetime.fromisoformat(value)
            except ValueError:
                raise Refused(f"{table}.{name} 의 시각 꼴이 틀렸다") from None
            if moment.tzinfo is None:
                raise Refused(f"{table}.{name} 의 시각에 시간대가 없다")
            decoded[name] = moment
        elif value is not None and name in decimals:
            if not isinstance(value, str):
                raise Refused(f"{table}.{name} 은 글자여야 한다")
            try:
                number = Decimal(value)
            except ArithmeticError:
                raise Refused(f"{table}.{name} 의 수 꼴이 틀렸다") from None
            if not number.is_finite():
                raise Refused(f"{table}.{name} 이 유한한 수가 아니다")
            decoded[name] = number
        else:
            decoded[name] = value
    return decoded


def dumps(value: object) -> bytes:
    """묶음의 JSON(열쇠 차례 그대로 — options 는 쓴 차례가 뜻이다). NaN·Infinity 는 ValueError."""
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


def _refuse_constant(name: str) -> object:
    raise Refused(f"JSON 에 {name} 가 있다")


def loads(data: bytes) -> object:
    """묶음의 JSON 읽기. NaN·Infinity·-Infinity · 자릿수 상한(sys.get_int_max_str_digits)을 넘는 정수 · 재귀 상한을
    넘는 중첩은 Refused(HD1 R4 — 날 예외 대신 한 줄)."""
    try:
        return json.loads(data.decode(), parse_constant=_refuse_constant)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise Refused("bundle.json 을 JSON 으로 읽지 못했다") from None
    except ValueError:
        raise Refused("bundle.json 에 자릿수 상한을 넘는 정수가 있다") from None
    except RecursionError:
        raise Refused("bundle.json 의 중첩이 너무 깊다") from None


def canonical_sha256(value: object) -> str:
    """정규형(열쇠 정렬·빈칸 없음)의 sha256 — 넣은 실행의 idempotency_sha256."""
    text = json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":"), sort_keys=True)
    return hashlib.sha256(text.encode()).hexdigest()


# ── zip 항목 ─────────────────────────────────────────────────────────


def blob_name(sha256: str) -> str:
    return f"{BLOB_PREFIX}{sha256}"


def check_members(names: Sequence[str], blobs: Sequence[Blob]) -> None:
    """zip 항목 = bundle.json + 머리 blobs 이름만(겹침·밖·`..`·절대 경로·빠짐 → Refused)."""
    if len(set(names)) != len(names):
        raise Refused("zip 항목 이름이 겹친다")
    for name in names:
        if name.startswith("/") or "\\" in name or ".." in name.split("/"):
            raise Refused("zip 항목 이름에 밖을 가리키는 길이 있다")
    expected = {BUNDLE_JSON} | {blob_name(blob.sha256) for blob in blobs}
    if set(names) != expected:
        raise Refused("zip 항목이 머리의 목록과 다르다")


# ── 머리·행 검사 ──────────────────────────────────────────────────────


def _list(value: object, what: str) -> list[object]:
    if not isinstance(value, list):
        raise Refused(f"{what} 은 목록이어야 한다")
    return cast("list[object]", value)


def _strings(value: object, what: str) -> list[str]:
    items = _list(value, what)
    if not all(isinstance(item, str) for item in items):
        raise Refused(f"{what} 은 글자의 목록이어야 한다")
    return cast("list[str]", items)


def _dict(value: object, what: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise Refused(f"{what} 은 객체여야 한다")
    items = cast("dict[object, object]", value)
    if not all(isinstance(key, str) for key in items):
        raise Refused(f"{what} 의 열쇠는 글자여야 한다")
    return dict(cast("dict[str, object]", items))


def _rows(value: object, what: str) -> list[Row]:
    return [_dict(row, what) for row in _list(value, what)]


def _blobs(value: object) -> tuple[Blob, ...]:
    found: list[Blob] = []
    for item in _list(value, "blobs"):
        entry = _dict(item, "blobs 의 항목")
        sha, size, role = entry.get("sha256"), entry.get("size"), entry.get("role")
        if set(entry) != {"sha256", "size", "role"} or not isinstance(sha, str) or SHA256.fullmatch(sha) is None:
            raise Refused("blobs 의 항목 꼴이 틀렸다")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0 or role not in ROLES:
            raise Refused("blobs 의 항목 꼴이 틀렸다")
        found.append(Blob(sha256=sha, size=size, role=str(role)))
    if len({blob.sha256 for blob in found}) != len(found):
        raise Refused("blobs 에 같은 sha 가 둘이다")
    return tuple(found)


def _check_row(table: str, row: Row, columns: frozenset[str]) -> None:
    person = PERSON_OR_COMPANY & set(row)
    if person:
        raise Refused(f"{table} 행에 사람·회사 칸이 실렸다")
    if frozenset(row) != columns | REFS[table]:
        raise Refused(f"{table} 행의 칸이 머리 tables 와 다르다")


def _old_id(value: object, what: str, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise Refused(f"{what} 은 양의 정수여야 한다")


def check_bundle(header: object) -> Bundle:
    """bundle.json 의 값 → Bundle. 꼴이 하나라도 틀리면 Refused(쓰기 앞의 문 — S1)."""
    head = _dict(header, "bundle.json")
    if head.get("format") != FORMAT:
        raise Refused("모르는 묶음 꼴이다")
    if frozenset(head) != HEADER_KEYS:
        raise Refused("머리의 열쇠가 다르다")
    bundle_id = head["bundleId"]
    try:
        if not isinstance(bundle_id, str) or str(uuid.UUID(bundle_id)) != bundle_id:
            raise ValueError
    except ValueError:
        raise Refused("bundleId 가 소문자 UUID 가 아니다") from None
    created_at, app_commit, source = head["createdAt"], head["appCommit"], head["sourceCompanyId"]
    if not isinstance(created_at, str) or not isinstance(app_commit, str):
        raise Refused("createdAt·appCommit 은 글자여야 한다")
    if not isinstance(source, int) or isinstance(source, bool):
        raise Refused("sourceCompanyId 는 정수여야 한다")
    migrations_raw = _dict(head["migrations"], "migrations")
    migrations = {app: _strings(leaves, "migrations") for app, leaves in migrations_raw.items()}
    tables_raw = _dict(head["tables"], "tables")
    rows_raw = _dict(head["rows"], "rows")
    counts = _dict(head["counts"], "counts")
    present = [SEGMENTS in tables_raw, SEGMENTS in rows_raw, SEGMENTS in counts]
    if any(present) and not all(present):
        raise Refused("run_segments 가 tables·rows·counts 가운데 일부에만 있다")
    has_segments = all(present)
    names = TABLES if has_segments else LEGACY_TABLES
    if frozenset(tables_raw) != frozenset(names):
        raise Refused("tables 의 표가 다르다")
    tables = {table: _strings(columns, "tables") for table, columns in tables_raw.items()}
    for table, columns in tables.items():
        if len(set(columns)) != len(columns) or set(columns) & (NOT_CARRIED[table] | PERSON_OR_COMPANY):
            raise Refused(f"{table} 에 싣지 않는 칸이 실렸다")
    blobs = _blobs(head["blobs"])
    by_sha = {blob.sha256: blob for blob in blobs}
    if set(rows_raw) != {*names, "modules"}:
        raise Refused("rows 의 표가 다르다")
    rows = {table: _rows(rows_raw[table], table) for table in names}
    for table in names:
        for row in rows[table]:
            _check_row(table, row, frozenset(tables[table]))
    if counts != {table: len(rows[table]) for table in names}:
        raise Refused("counts 가 행 수와 다르다")
    modules_raw = _dict(rows_raw["modules"], "modules")
    modules = {
        module: {name: _rows(table, f"{module}.{name}") for name, table in _dict(tables_of, module).items()}
        for module, tables_of in modules_raw.items()
    }
    for table in ("core_documents", "run_files"):
        if not {"size_bytes", "sha256"} <= set(tables[table]):
            raise Refused(f"{table} 에 size_bytes·sha256 칸이 없다")
    for row in rows["core_documents"]:
        _old_id(row["oldId"], "문서 oldId")
        _old_id(row["previousOldId"], "previousOldId", optional=True)
        blob = by_sha.get(str(row["blob"]))
        if blob is None or blob.role not in ("document", SHARED):
            raise Refused("문서 행의 blob 이 목록에 없다")
        if row["size_bytes"] != blob.size or row["sha256"] not in (None, blob.sha256):
            raise Refused("문서 행의 크기·sha 가 blob 과 다르다")
    for row in rows["run_runs"]:
        _old_id(row["oldId"], "실행 oldId")
        _old_id(row["documentOldId"], "documentOldId", optional=True)
        _old_id(row["resumedFromOldId"], "resumedFromOldId", optional=True)
    for table in ("run_steps", "run_results", "run_files", *((SEGMENTS,) if has_segments else ())):
        for row in rows[table]:
            _old_id(row["runOldId"], f"{table} runOldId")
    for row in rows["core_llm_call_logs"]:
        _old_id(row["runOldId"], "LLM 기록 runOldId")  # 실행 없는 줄은 싣지 않는다(내보내기는 실행의 줄만 읽는다)
    for row in rows["run_files"]:
        blob = by_sha.get(str(row["blob"]))
        if blob is None or blob.role not in ("run_file", SHARED):
            raise Refused("파일 행의 blob 이 목록에 없다")
        if row["size_bytes"] != blob.size or row["sha256"] != blob.sha256:
            raise Refused("파일 행의 크기·sha 가 blob 과 다르다")
    used = {str(row["blob"]) for table in ("core_documents", "run_files") for row in rows[table]}
    if used != set(by_sha):
        raise Refused("어느 행도 가리키지 않는 blob 이 있다")
    for table, key in (("core_documents", "oldId"), ("run_runs", "oldId")):
        olds = [row[key] for row in rows[table]]
        if len(set(olds)) != len(olds):
            raise Refused(f"{table} 의 oldId 가 겹친다")
    return Bundle(
        bundle_id=bundle_id,
        created_at=created_at,
        app_commit=app_commit,
        source_company_id=source,
        migrations=migrations,
        flows=_strings(head["flows"], "flows"),
        shapes=_strings(head["shapes"], "shapes"),
        tables=tables,
        blobs=blobs,
        rows=rows,
        modules=modules,
        has_segments=has_segments,
    )


# ── 모듈 행(RX1b Qb7) ──────────────────────────────────────────────────


def _person_or_company(name: str) -> bool:
    return name in PERSON_OR_COMPANY or name == "id" or name.endswith(("_user_id", "UserId", "_by"))


def check_module_rows(
    modules: Mapping[str, Mapping[str, Sequence[Mapping[str, object]]]],
    declared: Mapping[str, Mapping[str, Mapping[str, str]]],
) -> dict[str, dict[str, list[Row]]]:
    """모듈 행을 받는 쪽 carrier 의 선언(columns())으로 검사하고 time 칸을 datetime 으로 푼 값. 틀리면 Refused.

    표 이름 ⊆ 그 모듈의 선언 표 · 행의 칸 집합 = 선언 칸 · 사람·회사·id 칸(선언에 있어도) 거절 · "id" 꼴은 양의 정수 ·
    "time" 꼴은 시간대 있는 ISO 글자(또는 null). 내보낼 때도 같은 검사를 지난다(풀린 값은 버림)."""
    decoded: dict[str, dict[str, list[Row]]] = {}
    for module, tables in modules.items():
        kinds_of = declared.get(module)
        if kinds_of is None:
            raise Refused(f"모듈 {module} 의 행을 받을 carrier 선언이 없다")
        decoded[module] = {}
        for table, rows in tables.items():
            kinds = kinds_of.get(table)
            if kinds is None:
                raise Refused(f"모듈 {module} 의 표 {table} 는 carrier 가 선언하지 않았다")
            if any(_person_or_company(name) for name in kinds) or set(kinds.values()) - {"id", "time", "plain"}:
                raise Refused(f"모듈 {module} 의 표 {table} 선언에 사람·회사·id 칸이나 모르는 꼴이 있다")
            decoded[module][table] = [_module_row(module, table, row, kinds) for row in rows]
    return decoded


def _module_row(module: str, table: str, row: Mapping[str, object], kinds: Mapping[str, str]) -> Row:
    where = f"{module}.{table}"
    if any(_person_or_company(name) for name in row):
        raise Refused(f"{where} 행에 사람·회사·id 칸이 실렸다")
    if set(row) != set(kinds):
        raise Refused(f"{where} 행의 칸이 carrier 선언과 다르다")
    found: Row = {}
    for name, value in row.items():
        kind = kinds[name]
        if kind == "id":
            _old_id(value, f"{where}.{name}")
            found[name] = value
        elif kind == "time" and value is not None:
            if not isinstance(value, str):
                raise Refused(f"{where}.{name} 의 시각 꼴이 틀렸다")
            try:
                moment = datetime.fromisoformat(value)
            except ValueError:
                raise Refused(f"{where}.{name} 의 시각 꼴이 틀렸다") from None
            if moment.tzinfo is None:
                raise Refused(f"{where}.{name} 의 시각에 시간대가 없다")
            found[name] = moment
        else:
            found[name] = value
    return found


# ── 선언한 자리만 다시 쓰기(RX1b §1-9) ─────────────────────────────────────

MASK: Final = "\u0000id"


def masked(value: object, paths: Sequence[str]) -> object:
    """값에서 경로(점으로 잇고 목록은 `[]` — "retry.fromRunId"·"results[].settings.retry.fromRunId")의 자리를 MASK 로
    바꾼 사본. 없는 자리는 그대로(더해진 열쇠는 견줌에서 드러난다)."""
    result = value
    for path in paths:
        result = _mask(result, path.split("."))
    return result


def _mask(value: object, parts: list[str]) -> object:
    if not parts or not isinstance(value, dict):
        return value
    fields = cast("dict[str, object]", value)
    head, rest = parts[0], parts[1:]
    listed = head.endswith("[]")
    key = head.removesuffix("[]")
    if key not in fields:
        return fields
    inner = fields[key]
    if listed:
        if not isinstance(inner, list):
            return fields
        items = cast("list[object]", inner)
        replaced: object = [MASK if not rest else _mask(item, rest) for item in items]
    else:
        replaced = MASK if not rest else _mask(inner, rest)
    return {**fields, key: replaced}


def same_outside(before: object, after: object, paths: Sequence[str]) -> bool:
    """선언한 자리(paths) 밖이 바이트로 같은가(열쇠 차례까지 — dumps 로 견줌)."""
    return dumps(masked(before, paths)) == dumps(masked(after, paths))
