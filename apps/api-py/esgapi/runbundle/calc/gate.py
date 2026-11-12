"""받는 쪽의 문(Q5 ⓑ~ⓓ — 순수, DB 0). 쓰기 앞에서 하나라도 걸리면 Refused(통째 거절).

    check_flows(bundle, flows)              ⓑ 실행의 흐름이 받는 레지스트리에 있고 그 모듈의 것이며, 결과 꼴이 그 흐름의
                                            result_shapes 안, 단계 이름이 선언 안
    check_columns(bundle, receiving)        ⓒ 표마다 실은 칸 ⊆ 받는 모델의 칸, 받는 모델의 필수 칸
                                            (NOT NULL·기본값 없음)은 실렸거나 넣기가 채우는 칸(NOT_CARRIED)
    check_migrations(sent, nodes)           ⓓ 묶음의 앱별 잎(보낸 쪽 디스크 그래프)이 받는 쪽 디스크 그래프의
                                            마디에 있음. 받는 쪽이 앞선 것은 통과(ⓒ 가 칸을 본다)
    check_statuses(bundle)                  묶음의 실행은 끝난 것(done·failed)만 — queued·processing 이면 거절(실행기가
                                            넣은 실행을 집어 들 길 0)
    check_carriers(modules, carriers)       모듈마다 carrier 가 달려 있음(닫힌 기본 — 없으면 그 모듈 실행은 거절)
    check_carried(bundle)                   (HD1 R4) 꼭 실을 칸(REQUIRED_COLUMNS)이 표마다 실렸고 position 은 bool 아닌
                                            정수 — 문이 이름으로 읽는 자리(KeyError·ValueError)보다 앞
    check_shape(bundle)                     (HD1 R2) 실행 ≥ 1 · 문서는 모두 실행의 documentOldId 이거나 그 앞 판 사슬
                                            위 · 모듈 행의 모듈 ⊆ 실행의 모듈 — 내보내기가 짓지 못하는 꼴(실행 0 묶음은
                                            두 번 넣힌다: 넣은 표시가 실행마다의 열쇠다)
    check_module_runs(bundle)               (HD1 S2) 모듈 행의 runOldId 는 묶음 안 **그 모듈** 실행만
    check_segments(bundle, flows)           (RM1c) 구획 행: 묶음 안 실행 · 그 흐름의 펼침 단계 · 열쇠 꼴과 sha
                                            다시 셈 · kind · (실행, 단계) position 0..n−1·sha 겹침 0·행 수 ≤
                                            max_segments · 상태↔칸 짝 · data 객체·크기 상한·data_octets 다시 셈 ·
                                            error_code ≤ 64. 옛 묶음(has_segments False)은 구획 검사를 다 건너뛴다
                                            (check_columns·check_carried 도)

받는 모델의 칸 목록은 부르는 쪽(actions)이 Django 의 앱 등록부에서 읽어 넘긴다(여기는 표 이름 → 칸 → 필수 여부만 안다).
"""

from collections.abc import Collection, Mapping
from typing import cast

from esgapi.core.calc.jobs import MAX_ERROR_CODE_CHARS
from esgapi.core.flows.carriers import CarrierRegistry
from esgapi.core.flows.registry import FlowRegistry
from esgapi.core.flows.types import (
    SEGMENT_DATA_MAX_OCTETS,
    FlowRegistryError,
    segment_key_of,
    segment_key_problem,
    segment_key_sha256,
)
from esgapi.runbundle.calc.bundle import (
    LEGACY_TABLES,
    NOT_CARRIED,
    REQUIRED_COLUMNS,
    SEGMENTS,
    TABLES,
    Bundle,
    Refused,
    Row,
)
from esgapi.runs.calc.segments import data_octets


def tables_of(bundle: Bundle) -> tuple[str, ...]:
    """그 묶음이 싣는 표(옛 묶음은 표 여섯 — RM1c)."""
    return TABLES if bundle.has_segments else LEGACY_TABLES


def check_flows(bundle: Bundle, flows: FlowRegistry) -> None:
    runs = {int(str(row["oldId"])): row for row in bundle.rows["run_runs"]}
    for old, row in runs.items():
        try:
            flow = flows.get(str(row["flow_id"]))
        except FlowRegistryError:
            raise Refused(f"실행 {old} 의 흐름을 받는 쪽이 모른다") from None
        if flow.module != row["module"]:
            raise Refused(f"실행 {old} 의 흐름이 그 모듈의 것이 아니다")
    for row in bundle.rows["run_files"]:
        run = runs.get(int(str(row["runOldId"])))
        if run is None:
            raise Refused("run_files 행이 묶음에 없는 실행을 가리킨다")
        step = row["step"]
        if step is not None and step not in flows.get(str(run["flow_id"])).steps:
            raise Refused(f"파일의 단계가 흐름 {run['flow_id']} 의 선언 밖이다")
    for table, column, what in (("run_results", "schema_version", "결과 꼴"), ("run_steps", "name", "단계")):
        for row in bundle.rows[table]:
            run = runs.get(int(str(row["runOldId"])))
            if run is None:
                raise Refused(f"{table} 행이 묶음에 없는 실행을 가리킨다")
            flow = flows.get(str(run["flow_id"]))
            allowed = flow.result_shapes if table == "run_results" else flow.steps
            if row[column] not in allowed:
                raise Refused(f"{what} 이 흐름 {flow.id} 의 선언 밖이다")


FINISHED = frozenset({"done", "failed"})


def check_statuses(bundle: Bundle) -> None:
    """끝난 실행만, 그리고 failed 실행은 묶음 안에서 resumedFromOldId 사슬로 done 후손이 있어야 한다 — 외톨이 failed
    (꾸민 묶음)를 넣으면 받는 회사에서 그것을 이어 돌려 옮겨 온 체크포인트로 새 호출이 나갈 길이 생긴다(S18 의 짝).
    carrier 참조로 끌린 앞 실행은 done 만이다(RX1b Qb8 — import_ 의 참조 검사). 사슬 가운데 failed(f1→f2→done 의 f1)는
    A 처럼 B 에서도 이어 갈 수 있다(runs 의 바로 아래 자식 규칙 그대로 — Qb9)."""
    runs = {int(str(row["oldId"])): row for row in bundle.rows["run_runs"]}
    children: dict[int, list[int]] = {}
    for old, row in runs.items():
        if row.get("status") not in FINISHED:
            raise Refused(f"실행 {old} 이 끝난 실행이 아니다 — 묶음에는 done·failed 만 실린다")
        parent = row["resumedFromOldId"]
        if parent is not None:
            children.setdefault(int(str(parent)), []).append(old)
    for old, row in runs.items():
        if row["status"] == "failed" and not _has_done_descendant(old, runs, children):
            raise Refused(f"실행 {old} 은 묶음 안에 이어 간 done 실행이 없는 failed 다")


def _has_done_descendant(start: int, runs: dict[int, Row], children: dict[int, list[int]]) -> bool:
    stack, seen = list(children.get(start, [])), {start}
    while stack:
        old = stack.pop()
        if old in seen:
            continue
        seen.add(old)
        if runs[old]["status"] == "done":
            return True
        stack.extend(children.get(old, []))
    return False


def check_columns(bundle: Bundle, receiving: Mapping[str, Mapping[str, bool]]) -> None:
    """receiving: 표 → 칸 이름(attname) → 필수인가(NOT NULL·기본값 없음·자동 시각 아님·pk 아님)."""
    for table in tables_of(bundle):
        columns = receiving.get(table)
        if columns is None:
            raise Refused(f"받는 쪽에 {table} 표가 없다")
        carried = set(bundle.tables[table])
        if not carried <= set(columns):
            raise Refused(f"{table} 에 받는 쪽이 모르는 칸이 실렸다")
        missing = {name for name, required in columns.items() if required} - carried - NOT_CARRIED[table]
        if missing:
            raise Refused(f"{table} 의 받는 쪽 필수 칸이 묶음에 없다")


def check_migrations(
    sent: Mapping[str, Collection[str]], nodes: Collection[tuple[str, str]], required: Collection[str]
) -> None:
    """required: 묶음 머리에 잎이 반드시 있어야 하는 앱(core·runs 와 묶음 모듈 가운데 앱인 것 — 빈 {} 통과 막음)."""
    missing = sorted(set(required) - {app for app, leaves in sent.items() if leaves})
    if missing:
        raise Refused(f"묶음 머리의 마이그레이션에 {missing} 이 없다")
    known = set(nodes)
    for app, leaves in sent.items():
        for leaf in leaves:
            if (app, leaf) not in known:
                raise Refused(f"보낸 쪽 마이그레이션 {app}.{leaf} 을 받는 쪽이 모른다")


def check_carriers(modules: Collection[str], carriers: CarrierRegistry) -> None:
    for module in sorted(set(modules)):
        if carriers.get(module) is None:
            raise Refused(f"모듈 {module} 에 carrier 가 없다(그 모듈의 실행은 묶음에 싣지도 넣지도 못한다)")


POSITIONED = ("run_steps", "run_results")


def check_carried(bundle: Bundle) -> None:
    for table in tables_of(bundle):
        if not REQUIRED_COLUMNS[table] <= set(bundle.tables[table]):
            raise Refused(f"{table} 에 꼭 실을 칸이 없다")
    for table in POSITIONED:
        for row in bundle.rows[table]:
            position = row["position"]
            if not isinstance(position, int) or isinstance(position, bool):
                raise Refused(f"{table} 의 position 은 정수여야 한다")


def check_shape(bundle: Bundle) -> None:
    runs = bundle.rows["run_runs"]
    if not runs:
        raise Refused("묶음에 실행이 없다")
    documents = {row["oldId"]: row for row in bundle.rows["core_documents"]}
    reached: set[object] = set()
    for run in runs:
        current = run["documentOldId"]
        while current is not None and current in documents and current not in reached:
            reached.add(current)
            current = documents[current]["previousOldId"]
    if set(documents) - reached:
        raise Refused("어느 실행도 쓰지 않는 문서가 있다")
    if set(bundle.modules) - {str(run["module"]) for run in runs}:
        raise Refused("실행이 없는 모듈의 행이 실렸다")


def check_module_runs(bundle: Bundle) -> None:
    """모듈 행의 runOldId 칸은 묶음 안 그 모듈의 실행이어야 한다(꼴은 check_module_rows 가 먼저 본다)."""
    modules = {row["oldId"]: str(row["module"]) for row in bundle.rows["run_runs"]}
    for module, tables in bundle.modules.items():
        for table, rows in tables.items():
            for row in rows:
                if "runOldId" not in row:
                    continue
                pointed = row["runOldId"]
                if not isinstance(pointed, int) or isinstance(pointed, bool) or modules.get(pointed) != module:
                    raise Refused(f"모듈 {module} 의 표 {table} 행이 묶음 안 그 모듈 실행이 아닌 실행을 가리킨다")


SEGMENT_STATUSES = frozenset({"pending", "running", "done", "failed"})


def _integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _segment_row(row: Row, where: str, max_octets: int) -> None:
    """구획 행 하나의 꼴(열쇠·상태↔칸·크기). 실행·단계는 부르는 쪽이 본다."""
    key = row["key"]
    if not isinstance(key, dict):
        raise Refused(f"{where} 의 key 가 객체가 아니다")
    try:
        parsed = segment_key_of(cast("dict[str, object]", key))
    except ValueError:
        raise Refused(f"{where} 의 key 꼴이 틀렸다") from None
    if segment_key_problem(parsed) is not None:
        raise Refused(f"{where} 의 key 꼴이 틀렸다")
    if row["key_sha256"] != segment_key_sha256(parsed):
        raise Refused(f"{where} 의 key_sha256 이 key 에서 다시 센 값과 다르다")
    if row["kind"] != parsed.kind:
        raise Refused(f"{where} 의 kind 가 key 의 kind 와 다르다")
    status, attempts = row["status"], row["attempts"]
    if status not in SEGMENT_STATUSES or not _integer(attempts) or cast("int", attempts) < 0:
        raise Refused(f"{where} 의 status·attempts 꼴이 틀렸다")
    data, code = row.get("data"), row.get("error_code")
    octets = row.get("data_octets")
    if status == "done":
        if not isinstance(data, dict) or code is not None:
            raise Refused(f"{where} 의 done 에 data 가 없거나 error_code 가 있다")
        size = data_octets(cast("dict[str, object]", data))
        if size > max_octets:
            raise Refused(f"{where} 의 data 가 구획 상한을 넘는다")
        if octets is not None and octets != size:
            raise Refused(f"{where} 의 data_octets 가 다시 센 값과 다르다")
        return
    if data is not None or octets is not None:
        raise Refused(f"{where} 의 {status} 에 data 가 있다")
    if status == "failed":
        if not isinstance(code, str) or not 1 <= len(code) <= MAX_ERROR_CODE_CHARS:
            raise Refused(f"{where} 의 failed 에 error_code 가 없거나 {MAX_ERROR_CODE_CHARS}자를 넘는다")
    elif code is not None:
        raise Refused(f"{where} 의 {status} 에 error_code 가 있다")


def check_segments(bundle: Bundle, flows: FlowRegistry) -> None:
    """구획 행(RM1c — 머리말). 옛 묶음은 건너뛴다. check_flows 뒤에 부른다(실행의 흐름은 받는 쪽에 있다)."""
    if not bundle.has_segments:
        return
    runs = {int(str(row["oldId"])): row for row in bundle.rows["run_runs"]}
    groups: dict[tuple[int, str], list[Row]] = {}
    for row in bundle.rows[SEGMENTS]:
        old = int(str(row["runOldId"]))
        run = runs.get(old)
        if run is None:
            raise Refused("run_segments 행이 묶음에 없는 실행을 가리킨다")
        step = row["step"]
        if not isinstance(step, str) or step not in flows.get(str(run["flow_id"])).fanouts:
            raise Refused(f"구획의 단계가 흐름 {run['flow_id']} 의 펼침 단계가 아니다")
        position = row["position"]
        if not _integer(position):
            raise Refused("run_segments 의 position 은 정수여야 한다")
        _segment_row(row, f"실행 {old} 의 구획", SEGMENT_DATA_MAX_OCTETS)
        groups.setdefault((old, step), []).append(row)
    for (old, step), rows in groups.items():
        fanout = flows.get(str(runs[old]["flow_id"])).fanouts[step]
        if len(rows) > fanout.max_segments:
            raise Refused(f"실행 {old} 의 단계 {step} 구획이 max_segments 를 넘는다")
        if sorted(cast("int", row["position"]) for row in rows) != list(range(len(rows))):
            raise Refused(f"실행 {old} 의 단계 {step} 구획 position 이 0..n−1 이 아니다")
        if len({row["key_sha256"] for row in rows}) != len(rows):
            raise Refused(f"실행 {old} 의 단계 {step} 구획 열쇠가 겹친다")
