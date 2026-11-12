#!/usr/bin/env bash
# 밴드 AU1b-2 의 심은 파손(발주서 band-handoffs/AU1b-2-order.md §3-2, 개정 2). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로
# 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AU1b-2.sh [--boundary 1|2] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다(층 단위 아님 —
# 경계 ① 9 = P1·P2·P3·P4·P6·P7·P10·P12·P13, 경계 ② 13 = P1~P13). 한 P 의 겨눔도 커밋마다 다르다(P2·P6·P7 은 경계 ②
# 에서 겨눔이 는다).
# 회사 경계 심음(P1·P6)은 예외 없이 터지지 않는 꼴이다 — 잡음은 업무·보안 시험이 **단언**으로 빨개진 것으로만 센다
# (개정 2 n3). 빨간 노드의 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로
# 센다. 정적 unscoped 검사(test_static_rules)도 겨눔에 넣는다(그것만 빨가면 업무 겨눔이 못 잡음이라 셈에 들지 않는다).
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: AU1B2_OUT(기본: 워크트리 곁의 AU1b-2.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AU1B2_OUT:-$(cd "$ROOT/.." && pwd)/AU1b-2.out}"
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


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


OPSEL = Path("esgapi/runs/service/selectors/operator.py")
USAGE = Path("esgapi/core/service/selectors/llm_usage.py")
CALC = Path("esgapi/core/calc/run_metrics.py")
API = Path("esgapi/user/service/apis/run_logs.py")
PERMS = Path("esgapi/core/permissions.py")
TOP = "esgapi/runs/tests/service/selectors/test_operator.py"
TUSAGE = "esgapi/core/tests/service/selectors/test_llm_usage.py"
TCALC = "esgapi/core/tests/calc/test_run_metrics.py"
TAPI = "esgapi/user/tests/service/apis/test_run_logs.py"
TPERM = "esgapi/core/tests/test_permissions.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
SRUN = "tests/security/test_run_logs.py"
UNSCOPED = TSTATIC + "::test_product_code_does_not_use_unscoped"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

PAGE_CHECK = '    if not is_allowed("user_run_log_list", kind=actor_kind):\n        return RunLogForbidden()\n    rows = _runs(company_id)\n'
COHORT_CHECK = '    if not is_allowed("user_run_log_metrics", kind=actor_kind):\n'
USAGE_OPEN = "        LlmCallLogRow.for_company(company_id)\n        .filter(run_id__in=run_ids)\n"
RATE = "failure_rate=None if done + failed == 0 else failed / (done + failed),"
USED = "    used = [usage[run.id] for run in service if run.id in usage]\n"
ROUTE_DURATION = "durationSec=duration_sec(run.created_at, run.finished_at),"
ROUTE_METRIC = "created_at=run.created_at,"

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "usage_by_run 이 LlmCallLogRow.unscoped.filter(run_id__in=…) 로 연다(예외 없음)",
     [(USAGE, swap(USAGE_OPEN, "        LlmCallLogRow.unscoped.filter(run_id__in=run_ids)\n"))],
     [(1, BUSINESS, [TUSAGE], {TUSAGE + "::test_another_companys_line_with_the_same_run_id_is_not_counted"}),
      (1, PURE, [TSTATIC], {UNSCOPED})]),
    ("P2", 1, "operator_run_page 첫 줄 권한 검사를 지움",
     [(OPSEL, swap(PAGE_CHECK, "    rows = _runs(company_id)\n"))],
     [(1, BUSINESS, [TOP], {TOP + "::test_a_customer_kind_is_forbidden_before_anything_is_read",
                            TOP + "::test_each_function_reads_its_own_cell"}),
      (2, PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"})]),
    ("P3", 1, "operator_run_cohort 가 user_run_log_list 칸을 읽음",
     [(OPSEL, swap(COHORT_CHECK, COHORT_CHECK.replace("user_run_log_metrics", "user_run_log_list")))],
     [(1, BUSINESS, [TOP], {TOP + "::test_each_function_reads_its_own_cell"})]),
    ("P4", 1, "usage_by_run 의 output 합에 thinking_tokens 를 더함",
     [(USAGE, swap('output=Sum("output_tokens"),', 'output=Sum("output_tokens") + Sum("thinking_tokens"),'))],
     [(1, BUSINESS, [TUSAGE], {TUSAGE + "::test_thinking_tokens_are_not_added_to_output"})]),
    ("P6", 1, "operator.py 의 문 _runs 몸을 RunRow.unscoped.all() 로(예외 없음)",
     [(OPSEL, swap("    return RunRow.for_company(company_id)\n", "    return RunRow.unscoped.all()\n"))],
     [(1, BUSINESS, [TOP], {TOP + "::test_only_the_chosen_companys_runs_are_seen"}),
      (2, SECURITY, [SRUN], {SRUN + "::test_choosing_b_shows_no_run_or_llm_line_of_a",
                             SRUN + "::test_metrics_for_b_do_not_count_the_runs_of_a"}),
      (1, PURE, [TSTATIC], {UNSCOPED})]),
    ("P7", 1, "실패율 분모에서 failed 를 뺌(failed / done)",
     [(CALC, swap(RATE, "failure_rate=None if done + failed == 0 else failed / done,"))],
     [(1, PURE, [TCALC], {TCALC + "::test_the_failure_rate_is_failed_over_finished_and_none_without_a_finished_run"}),
      (2, BUSINESS, [TAPI], {TAPI + "::test_metrics_follow_the_rules_of_disposition_5"})]),
    ("P10", 1, "목록 q 를 icontains 대신 iregex 로",
     [(OPSEL, swap("document__file_name__icontains=q", "document__file_name__iregex=q"))],
     [(1, BUSINESS, [TOP], {TOP + "::test_q_takes_percent_underscore_and_dot_as_letters"})]),
    ("P12", 1, "month_bounds 가 now 를 UTC 로 달을 고름",
     [(CALC, swap("    local = now.astimezone(KST)\n", "    local = now.astimezone(timezone.utc)\n"))],
     [(1, PURE, [TCALC], {TCALC + "::test_the_month_turns_at_kst_midnight_not_utc"})]),
    ("P13", 1, "metrics 가 usage 값 전부를 더함(purpose 무관)",
     [(CALC, swap(USED, "    used = list(usage.values())\n"))],
     [(1, PURE, [TCALC], {TCALC + "::test_test_runs_are_left_out_of_every_metric_including_their_llm_usage"})]),
    # ── 커밋 ② 경로·권한 표 ──
    ("P5", 2, "권한 표의 user_run_log_list 를 CUSTOMER 로",
     [(PERMS, swap('    "user_run_log_list": OPERATOR,\n', '    "user_run_log_list": CUSTOMER,\n'))],
     [(2, PURE, [TPERM], {TPERM + "::test_the_table_is_these_needs"}),
      (2, SECURITY, [SRUN], {SRUN + "::test_a_customer_bearer_is_refused_on_both_paths"})]),
    ("P8", 2, "경로가 durationSec 을 started_at 부터, 지표의 MetricRun 을 created_at=started_at 으로 지음",
     [(API, swap(ROUTE_DURATION, "durationSec=duration_sec(run.started_at or run.created_at, run.finished_at),")),
      (API, swap(ROUTE_METRIC, "created_at=run.started_at or run.created_at,"))],
     [(2, BUSINESS, [TAPI], {TAPI + "::test_the_duration_includes_the_wait_from_created_at"})]),
    ("P9", 2, "경로의 permitted(request, \"user_run_log_metrics\") 를 지움",
     [(API, swap('    principal = permitted(request, "user_run_log_metrics")\n', "    principal = request.auth\n"))],
     [(2, PURE, [TPERM], {TPERM + "::test_each_route_checks_its_own_operation_id_first"})]),
    ("P11", 2, "경로가 chosen_company 대신 쿼리 companyId 를 그대로 selector 에 넘김(목록)",
     [(API, swap("    company_id = chosen_company(companyId, company_ports())\n    page =",
                 "    company_id = companyId or 0\n    page ="))],
     [(2, BUSINESS, [TAPI], {TAPI + "::test_an_unknown_company_is_404"})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY]) for n, c, w, e, checks in PLANTS]
BOUNDARY_GUARDED = {"P1", "P6"}  # 회사 경계 심음 — 예외로 빨개지면 무효
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
