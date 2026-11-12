#!/usr/bin/env bash
# 밴드 RC1 의 심은 파손(발주서 band-handoffs/RC1-order.md §3 + MARC-TICK-246 노트의 9f 조건 (마)). RF1 의 꼴 그대로:
# 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지
# 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-RC1.sh <1|2> [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 — 경계 ① 은
# P1~P10(10), 경계 ② 는 P1~P14(14 — ① 의 것을 다시 포함. P14 는 검증 R1 을 감독 22 가 필수로 더함).
# 회사 경계 심음(P5)은 예외 없이 터지지 않는 꼴이다 — 업무 층의 잡음은 **단언**으로 빨개진 것만 센다(빨간 노드의 로그에
# UnscopedQueryError·실행기의 run_crashed(예외 → internal)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다).
# 업무 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: RC1_OUT(기본: 워크트리 곁의 RC1.out)/planted-<경계>/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${RC1_OUT:-$(cd "$ROOT/.." && pwd)/RC1.out}"
case "${1:-}" in 1|2) BOUNDARY="$1"; shift ;; *) echo "첫 인자는 경계(1|2)"; exit 2 ;; esac
mkdir -p "$OUT/planted-$BOUNDARY"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted-$BOUNDARY" "$BOUNDARY" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
BOUNDARY = int(sys.argv[2])
args = sys.argv[3:]
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


TASKS = Path("esgapi/runs/tasks.py")
RESUME = Path("esgapi/runs/service/services/resume.py")
ACTIONS = Path("esgapi/runs/service/actions/runs.py")
TEXEC = "esgapi/runs/tests/test_executor.py"
TRES = "esgapi/runs/tests/service/services/test_resume.py"
TRUNS = "esgapi/runs/tests/service/apis/test_runs.py"
E1 = TEXEC + "::test_an_empty_new_key_is_filled_from_the_previous_run_and_the_run_goes_on"
E2 = TEXEC + "::test_a_big_step_file_is_carried_by_the_executor"
E3 = TEXEC + "::test_an_unreachable_store_while_carrying_defers_and_the_next_attempt_carries"
E3P = TEXEC + "::test_an_unreachable_store_on_the_new_key_put_defers_and_the_next_attempt_carries"
E4 = TEXEC + "::test_a_refused_put_of_the_new_key_fails_storage_denied"
E6 = TEXEC + "::test_a_previous_object_larger_than_its_row_is_not_carried"
E7 = TEXEC + "::test_the_chain_is_walked_back_to_the_run_that_has_the_bytes[r1-has-bytes]"
E8 = {TEXEC + f"::test_a_chain_that_does_not_go_back_stops_at_once[{p}]" for p in ("itself", "a-later-run")}
E9 = TEXEC + "::test_a_previous_key_outside_the_company_is_never_read"
E10 = TEXEC + "::test_a_first_run_with_a_missing_step_object_reads_no_chain"
E12 = TEXEC + "::test_a_documentless_resumed_run_carries_its_step_file_too"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 경계, 설명, [(파일, 심는 함수)], [(경계, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "_plan 의 옮김 갈래를 지움(BASE 처럼 object_missing)",
     [(TASKS, swap("            elif isinstance(got, ObjectMissing) and resumed_from is not None:\n",
                   "            elif False:\n"))],
     [(1, BUSINESS, [TEXEC], {E1, E2, E3, E3P, E7, E12})]),
    ("P2", 1, "carry 의 get StorageUnavailable 을 「다음 후보」로",
     [(RESUME, swap("            return CarryUnavailable(got.detail)\n", "            continue\n"))],
     [(1, PURE, [TRES], {TRES + "::test_carry_stops_at_an_unreachable_store_without_reading_further"}),
      (1, BUSINESS, [TEXEC], {E3})]),
    ("P3", 1, "put StorageUnavailable 을 무시하고 Carried",
     [(RESUME, swap("        return CarryUnavailable(put.detail)\n", "        return Carried(data=got.data, from_run=run_id)\n"))],
     [(1, PURE, [TRES], {TRES + "::test_carry_reports_a_failed_put[unavailable]"}),
      (1, BUSINESS, [TEXEC], {E3P})]),
    ("P4", 1, "put StorageDenied 를 CarryMissing 으로",
     [(RESUME, swap("            return CarryRefused(put.detail)\n", "            return CarryMissing()\n"))],
     [(1, PURE, [TRES], {TRES + "::test_carry_reports_a_failed_put[denied]"}),
      (1, BUSINESS, [TEXEC], {E4})]),
    ("P5", 1, "회사 접두 검사를 지움",
     [(RESUME, swap("        if not key.startswith(prefix):\n            continue\n", ""))],
     [(1, PURE, [TRES], {TRES + "::test_carry_never_reads_a_key_outside_the_company"}),
      (1, BUSINESS, [TEXEC], {E9})]),
    ("P6", 1, "_ancestors 가 한 칸만(find_run 으로 거슬러 가지 않음)",
     [(TASKS, swap("        below, current = current, None if found is None else found.resumed_from_run_id\n",
                   "        below, current = current, None\n"))],
     [(1, BUSINESS, [TEXEC], {E7})]),
    ("P7", 1, "current < below 멈춤을 지움(is not None 만)",
     [(TASKS, swap("    while current is not None and current < below:\n", "    while current is not None:\n"))],
     [(1, BUSINESS, [TEXEC], E8)]),
    ("P8", 1, "resumed_from is not None 조건을 지움",
     [(TASKS, swap("            elif isinstance(got, ObjectMissing) and resumed_from is not None:\n",
                   "            elif isinstance(got, ObjectMissing):\n"))],
     [(1, BUSINESS, [TEXEC], {E10})]),
    ("P9", 1, "carry 의 get 상한을 행의 size_bytes 대신 큰 값으로(발주서의 documents.max_upload_bytes() 꼴 — resume.py 는 "
     "documents 를 import 하지 않아 상수로 심음)",
     [(RESUME, swap("        got = storage.get(key, max_bytes=size_bytes)\n", "        got = storage.get(key, max_bytes=2**40)\n"))],
     [(1, BUSINESS, [TEXEC], {E6})]),
    ("P10", 1, "옮긴 바이트를 쓰되 새 키 put 을 건너뜀",
     [(RESUME, swap("        put = storage.put(target_key, content=got.data, media_type=media_type)\n",
                    "        put = ObjectPut(etag='\"planted\"')\n"))],
     [(1, PURE, [TRES], {TRES + "::test_carry_takes_the_first_source_and_writes_the_target"}),
      (1, BUSINESS, [TEXEC], {E1, E7})]),
]
E13 = {TEXEC + f"::test_an_own_key_that_is_too_large_or_refused_is_not_overwritten_from_the_chain[{p}]"
       for p in ("too-large", "denied")}
R9 = TRUNS + "::test_resume_creation_never_calls_the_store"
R10 = TRUNS + "::test_resume_creation_is_201_with_one_message_even_when_the_store_is_down"
R11 = TRUNS + "::test_a_resume_from_the_request_to_the_executor_carries_the_bytes"
RCOPIES = TRUNS + "::test_resume_copies_the_finished_steps_and_files_and_keeps_the_previous_versions_and_options"
RCREATE = TRUNS + "::test_create_makes_a_queued_run_with_pending_steps_and_one_message"
SEND = "        send(company_id=company_id, run_id=run_id)\n"
FILE_ROW = (
    "        key = file_key(company_id=company_id, run_id=row.pk, step=file.step, name=file.name)\n"
    "        RunFileRow.for_company(company_id).create(\n"
)
PLANTS2 = [
    ("P11", 2, "요청 갈고리에 documents.default_storage() 한 번 부름을 되살림",
     [(ACTIONS, swap(SEND, "        __import__(\"esgapi.core.service.services.documents\", fromlist=[\"x\"]).default_storage()\n" + SEND))],
     [(2, BUSINESS, [TRUNS], {R9})]),
    ("P12", 2, "갈고리가 쪽지를 보내지 않음",
     [(ACTIONS, swap(SEND, "        return None\n"))],
     [(2, BUSINESS, [TRUNS], {RCOPIES, RCREATE, R9, R10})]),
    ("P13", 2, "옮긴 단계의 파일 행 쓰기를 걷음(옮김과 같이 걷는 실수)",
     [(ACTIONS, swap(FILE_ROW, "        continue\n" + FILE_ROW))],
     [(2, BUSINESS, [TRUNS], {RCOPIES, R11})]),
    ("P14", 2, "_plan 조건에서 isinstance(got, ObjectMissing) 를 지움(자기 키 큼·거절도 사슬에서 덮어씀 — 검증 R1)",
     [(TASKS, swap("            elif isinstance(got, ObjectMissing) and resumed_from is not None:\n",
                   "            elif resumed_from is not None:\n"))],
     [(2, BUSINESS, [TEXEC], E13)]),
]
PLANTS = [p for p in PLANTS + PLANTS2 if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY]) for n, c, w, e, checks in PLANTS]
BOUNDARY_GUARDED = {"P5"}  # 회사 경계 심음 — 예외로 빨개지면 무효
EXCEPTION = re.compile(r"UnscopedQueryError|run_crashed")  # 실행기 안의 예외(→ internal)는 무효


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str, str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last, text


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for _commit, layer, targets, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, last, _ = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
    """잡았으면 True, 못 잡았으면 False, 컨테이너가 없어 다 돌리지 못했으면 None."""
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all, skipped = True, False
        for _commit, layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last, text = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            raised = number in BOUNDARY_GUARDED and layer[0] != "순수" and bool(EXCEPTION.search(text))
            if raised:
                print(f"{label} 예외로 빨강(무효 — 단언으로 빨개져야 한다)")
                hit = False
            hit_all = hit_all and hit
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, _commit, what, edits, checks in PLANTS:
    planted += 1
    result = plant_and_check(number, what, edits, checks)
    caught += 1 if result is True else 0
    print(f"{number} => {'잡음' if result else '안 돌림' if result is None else '못 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
