#!/usr/bin/env bash
# 밴드 AD4D 의 심은 파손(발주서 band-handoffs/AD4D-order.md §3, 개정 1 + MARC-TICK-231 노트의 9f 조건 (사)). 하나씩
# 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다.
# 파일을 지우는 심음은 지운 뒤 같은 바이트로 다시 쓴다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AD4D.sh [--boundary 1|2] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 —
# 경계 ① 8(P1~P6 + 9f (사)의 G1 단계 칸 UPDATE GRANT·G2 0002 지움), ② 15(+P7~P12 + 9f (사)의 G3 단계 토큰 합의
# 회사 거름 지움 — 상세 조회의 회사 거름은 P8 이 9f 의 ⓖ 몫).
# 회사 경계 심음(P8·G3)은 예외 없이 터지지 않는 꼴이다 — 업무·보안 층의 잡음은 **단언**으로 빨개진 것만 센다. 빨간 노드의
# 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다.
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: AD4D_OUT(기본: 워크트리 곁의 AD4D.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AD4D_OUT:-$(cd "$ROOT/.." && pwd)/AD4D.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
BOUNDARY = 2
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2"):
        BOUNDARY, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


DELETE = "<지움>"  # 심는 함수가 이것을 돌려주면 파일을 지운다(되돌림은 원본 바이트를 다시 씀)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def delete(text: str) -> str | None:
    return DELETE


LOG = Path("esgapi/core/llm/log.py")
SINK = Path("esgapi/core/llm/sink_db.py")
CTX = Path("esgapi/runs/context.py")
TASKS = Path("esgapi/runs/tasks.py")
MIG = Path("esgapi/core/migrations/0002_llm_call_log_step.py")
TSINKS = "esgapi/core/tests/test_llm_sinks.py"
TSINKDB = "esgapi/core/tests/test_llm_sink_db.py"
TCTX = "esgapi/runs/tests/test_context.py"
TEXEC = "esgapi/runs/tests/test_executor.py"
TMIGCHK = "esgapi/config/tests/test_migrations.py"
SLOG = "tests/security/test_llm_log.py"
SMIG = "tests/security/test_migrations.py"
STEPS_OF_ROWS = TEXEC + "::test_each_llm_row_carries_the_step_it_was_called_in"
CURSOR_SINK = TCTX + "::test_the_sink_writes_the_current_step_of_its_cursor_on_every_record"
CURSOR_EVENTS = TCTX + "::test_the_executor_events_set_the_cursor_at_the_start_and_clear_it_at_the_end"
ROUND_PURE = TSINKS + "::test_the_table_row_carries_the_step_both_ways_without_the_database"
ROUND_DB = TSINKDB + "::test_a_step_survives_the_round_trip_and_a_line_without_one_stays_null"
BAD_STEP = {
    TSINKDB + "::test_a_step_outside_one_to_a_hundred_characters_writes_nothing[empty]",
    TSINKDB + "::test_a_step_outside_one_to_a_hundred_characters_writes_nothing[101]",
}
MIG_ROUND = SMIG + "::test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip"
USAGE = Path("esgapi/core/service/selectors/llm_usage.py")
OPSEL = Path("esgapi/runs/service/selectors/operator.py")
RUNSEL = Path("esgapi/runs/service/selectors/runs.py")
ROUTE = Path("esgapi/user/service/apis/run_logs.py")
TUSAGE = "esgapi/core/tests/service/selectors/test_llm_usage.py"
TOP = "esgapi/runs/tests/service/selectors/test_operator.py"
TRUNS = "esgapi/runs/tests/service/selectors/test_runs.py"
TAPI = "esgapi/user/tests/service/apis/test_run_logs.py"
TPERM = "esgapi/core/tests/test_permissions.py"
SRUN = "tests/security/test_run_logs.py"
BEFORE = TAPI + "::test_a_run_before_ad4d_has_only_its_total"
RECORDED = TAPI + "::test_a_recorded_run_has_per_step_tokens_that_add_up_to_its_line"
SAME_404 = TAPI + "::test_a_missing_or_another_companys_run_is_the_same_404"
DETAIL_ROW = "    row = _runs(company_id).filter(id=run_id).values(*PAGE_FIELDS, \"failed_step\", \"error_code\").first()\n"
STEP_DURATION = "durationSec=None if step.started_at is None else duration_sec(step.started_at, step.finished_at),"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

MIG_TAIL = (
    '            field=models.CharField(max_length=100, null=True),\n'
    "        ),\n"
    "    ]\n"
)

# (번호, 경계, 설명, [(파일, 심는 함수)], [(경계, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "RunCallSink.record 가 step 을 버림",
     [(CTX, swap("replace(record, run_id=self._run_id, step=step)", "replace(record, run_id=self._run_id)"))],
     [(1, BUSINESS, [TEXEC], {STEPS_OF_ROWS}),
      (1, PURE, [TCTX], {CURSOR_SINK})]),
    ("P2", 1, "step_finished 가 커서를 비우지 않음",
     [(TASKS, swap("        self.cursor.current = None\n        files = _put_files(", "        files = _put_files("))],
     [(1, PURE, [TCTX], {CURSOR_EVENTS})]),
    ("P3", 1, "step_started 가 커서를 적지 않음",
     [(TASKS, swap("        self.cursor.current = step\n", ""))],
     [(1, BUSINESS, [TEXEC], {STEPS_OF_ROWS}),
      (1, PURE, [TCTX], {CURSOR_EVENTS})]),
    ("P4", 1, "row_from_record 가 step 을 안 적음",
     [(SINK, swap("        step=record.step,\n", ""))],
     [(1, PURE, [TSINKS], {ROUND_PURE}),
      (1, BUSINESS, [TSINKDB], {ROUND_DB})]),
    ("P5", 1, "BadStep 검사를 지움(101자 → DB 오류, 빈 글 → 씀)",
     [(SINK, swap("        if record.step is not None and not 1 <= len(record.step) <= STEP_MAX_LENGTH:\n"
                  "            return BadStep()\n", ""))],
     [(1, BUSINESS, [TSINKDB], BAD_STEP)]),
    ("P6", 1, "마이그레이션을 null=False, default=\"\" 로(모델과 어긋남)",
     [(MIG, swap("field=models.CharField(max_length=100, null=True)", 'field=models.CharField(max_length=100, default="")'))],
     [(1, BUSINESS, [TMIGCHK], {TMIGCHK + "::test_models_and_migrations_agree"}),
      (1, SECURITY, [SMIG], {MIG_ROUND})]),
    ("G1", 1, "9f (사): 0002 에 앱 역할의 단계 칸 UPDATE GRANT",
     [(MIG, swap(MIG_TAIL, MIG_TAIL.replace("        ),\n    ]\n",
                                             "        ),\n        grant('\"core_llm_call_logs\"', \"UPDATE (step)\"),\n    ]\n"))),
      (MIG, swap("from django.db import migrations, models\n",
                 "from django.db import migrations, models\n\nfrom esgapi.core.isolation.grants import grant\n"))],
     [(1, SECURITY, [SLOG], {SLOG + "::test_app_role_cannot_change_or_remove_a_log_line[update_step]",
                             SLOG + "::test_app_role_appends_and_reads_a_line_with_a_step"})]),
    ("G2", 1, "9f (사): 0002 파일을 지움",
     [(MIG, delete)],
     [(1, SECURITY, [SMIG], {MIG_ROUND})]),
    # ── 경계 ② 상세 ──
    ("P7", 2, "usage_by_step 의 recorded 를 늘 True",
     [(USAGE, swap("            recorded = False\n", ""))],
     [(2, BUSINESS, [TAPI], {BEFORE}),
      (2, BUSINESS, [TUSAGE], {TUSAGE + "::test_one_line_without_a_step_makes_the_run_unrecorded"})]),
    ("P8", 2, "상세가 _runs 대신 RunRow.unscoped(회사 거름 없음 — 예외 없음)",
     [(OPSEL, swap(DETAIL_ROW, DETAIL_ROW.replace("_runs(company_id).filter(id=run_id)", "RunRow.unscoped.filter(id=run_id)")))],
     [(2, SECURITY, [SRUN], {SRUN + "::test_choosing_b_gets_404_on_a_run_of_a_byte_for_byte_like_a_missing_id"}),
      (2, BUSINESS, [TAPI], {SAME_404}),
      (2, BUSINESS, [TOP], {TOP + "::test_a_missing_or_another_companys_run_is_none"})]),
    ("P9", 2, "operator_run_detail 첫 줄 권한 검사를 지움",
     [(OPSEL, swap('    if not is_allowed("user_run_log_get", kind=actor_kind):\n        return RunLogForbidden()\n', ""))],
     [(2, PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"}),
      (2, BUSINESS, [TOP], {TOP + "::test_the_detail_is_forbidden_to_a_customer_kind_before_anything_is_read"})]),
    ("P10", 2, "단계 durationSec 을 실행의 created_at 에서",
     [(ROUTE, swap(STEP_DURATION, STEP_DURATION.replace("duration_sec(step.started_at,", "duration_sec(CREATED[0],"))),
      (ROUTE, swap("    line = run_out(found.run, usage, names)\n",
                   "    line = run_out(found.run, usage, names)\n    CREATED[:] = [found.run.created_at]\n")),
      (ROUTE, swap('RUN_NOT_FOUND = "그 실행이 없다"\n', 'RUN_NOT_FOUND = "그 실행이 없다"\nCREATED: list = []\n'))],
     [(2, BUSINESS, [TAPI], {TAPI + "::test_step_times_run_from_the_first_start_to_the_end"})]),
    ("P11", 2, "step_heads 가 data 도 읽음(응답엔 안 실음)",
     [(RUNSEL, swap('.values("name", "position", "status", "started_at", "finished_at")',
                    '.values("name", "position", "status", "started_at", "finished_at", "data")'))],
     [(2, BUSINESS, [TRUNS], {TRUNS + "::test_step_heads_are_in_the_declared_order_without_data_or_partial"})]),
    ("P12", 2, "기록된 실행에서 줄 없는 단계를 null 로",
     [(ROUTE, swap("else 0 if used is None else used.tokens", "else None if used is None else used.tokens"))],
     [(2, BUSINESS, [TAPI], {RECORDED})]),
    ("G3", 2, "9f (사): 단계 토큰 합에 회사 거름 지움(LlmCallLogRow.unscoped — 예외 없음)",
     [(USAGE, swap("        LlmCallLogRow.for_company(company_id)\n        .filter(run_id=run_id)\n        .order_by()\n        .values(\"step\")",
                   "        LlmCallLogRow.unscoped.filter(run_id=run_id)\n        .order_by()\n        .values(\"step\")"))],
     [(2, SECURITY, [SRUN], {SRUN + "::test_a_b_tagged_llm_line_on_a_run_and_step_of_a_adds_nothing_to_its_detail"}),
      (2, BUSINESS, [TUSAGE], {TUSAGE + "::test_another_companys_line_on_the_same_run_and_step_is_not_counted"})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY]) for n, c, w, e, checks in PLANTS]
BOUNDARY_GUARDED = {"P8", "G3"}  # 회사 경계 심음 — 예외로 빨개지면 무효
EXCEPTION = re.compile(r"UnscopedQueryError|Internal Server Error|Traceback")


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
            if new == DELETE:
                f.unlink()
                continue
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
