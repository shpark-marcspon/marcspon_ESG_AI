#!/usr/bin/env bash
# 밴드 IR3b 의 심은 파손(발주서 band-handoffs/IR3b-order.md §3-5, + 러너 몫 P14). 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — try/finally, SIGTERM·SIGINT 도 finally 를 지난다). 사용:
#   apps/api-py/scripts/planted-breaks-IR3b.sh [--commit <n>] [--with-containers] [--only P1,P4]
#   --commit n 은 경계 n 까지의 몫만(① P1~P3·P14, ② +P4~P11, ③ P4·P5·P8 의 보안 몫·P12·P13). 기본 3.
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무·보안 층(Postgres)은 --with-containers 일 때만 —
# 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다. 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: IR3b_OUT(기본: 워크트리 곁의 IR3b.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IR3b_OUT:-$(cd "$ROOT/.." && pwd)/IR3b.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
CONTAINERS = False
ONLY = None
COMMIT = 3
while args:
    if args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    elif args[0] == "--commit" and len(args) > 1:
        COMMIT, args = int(args[1]), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def _stop(signum, _frame):  # SIGTERM·SIGINT 도 되쓰기(finally)를 지나게
    raise SystemExit(128 + signum)


signal.signal(signal.SIGTERM, _stop)
signal.signal(signal.SIGINT, _stop)


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


BINDING = Path("esgapi/materiality/flows/binding_155.py")
TB = "esgapi/materiality/tests/flows/test_binding_155.py"
MASKED = TB + "::test_a_topic_name_key_is_masked_in_the_sentence"
NOT_TEXT = TB + "::test_a_key_that_is_not_text_is_masked_without_the_key_mark"
PATH_ONLY = TB + "::test_the_path_masks_only_the_part_under_a_dict_key_field"
ONCE = TB + "::test_inputs_read_the_clock_once_across_the_seoul_midnight"
CASES = ("unknown-key", "wrong-shape", "missing", "not-a-list")
ACTION = Path("esgapi/materiality/service/actions/result.py")
ROUTE = Path("esgapi/materiality/service/apis/materiality.py")
PERM = Path("esgapi/core/permissions.py")
API = Path("esgapi/config/api.py")
PATHS = Path("tests/security/test_tenant_paths.py")
TR = "esgapi/materiality/tests/service/apis/test_materiality.py"
TO = "esgapi/materiality/tests/service/apis/test_materiality_operator.py"
TP = "esgapi/core/tests/test_permissions.py"
TW = "esgapi/core/tests/test_permissions_wiring.py"
SM = "tests/security/test_materiality.py"
STP = "tests/security/test_tenant_paths.py"
SOC = "tests/security/test_operator_company.py"
R_404 = TR + "::test_no_run_another_company_and_another_module_are_the_same_404"
R_OTHER_DONE = TR + "::test_a_done_run_of_another_module_is_404"
R_AT1 = TR + "::test_a_done_run_without_an_at_2_result_is_404"
R_409 = TR + "::test_queued_processing_and_failed_runs_are_409"
O_MADE = TO + "::test_an_operator_creates_a_documentless_materiality_run_in_the_work_company"
O_READ = TO + "::test_the_operator_reads_the_same_result_and_both_workbooks_as_the_customer"
O_LIST = TO + "::test_the_operator_list_has_the_materiality_run_without_and_with_the_module"
O_RESUME = TO + "::test_the_operator_resumes_a_customers_failed_run_of_the_work_company"
P_MODULES = TP + "::test_the_operator_runs_greenwash_translation_dataverify_and_materiality"
P_NEEDS = TP + "::test_the_table_is_these_needs"
W_RAISE = TW + "::test_raising_the_cell_makes_that_route_forbidden[materiality_result_get]"
# P9 는 칸이 COMPANY 밖으로 나가 그 매개가 사라진다 — 회사 업무 수 27 단언이 남은 매개마다 빨개진다(하나를 겨눈다)
W_LOWER = TW + "::test_lowering_the_company_work_cell_makes_that_route_forbidden_for_the_operator[runs_get]"
FIND = "    run = run_selectors.find_run(company_id=company_id, run_id=run_id)\n"
UNSCOPED = (
    "    company_id = getattr(__import__('esgapi.runs.models', fromlist=['RunRow']).RunRow.unscoped"
    ".filter(pk=run_id).first(), 'company_id', company_id)\n"
)


def AT_3(checks):  # noqa: N802 — 경계 ③ 에서 생기는 보안 시험은 그때부터 겨눈다
    return checks if COMMIT >= 3 else []


# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

S_PATHS = STP + "::test_a_materiality_run_path_hides_another_companys_run_and_other_modules"
S_OTHER = SM + "::test_another_companys_result_is_not_found_like_a_missing_id"
S_AMBIG = SM + "::test_an_operator_bearer_with_two_companies_is_400_ambiguous_without_reading_runs"
S_RESULT_PATH = "GET /materiality/runs/{run_id}/result"
SECURITY_P4 = [(SECURITY, [STP], {f"{S_PATHS}[{via}-{S_RESULT_PATH}]" for via in ("session", "bearer")})]
SECURITY_P5 = [(SECURITY, [SM], {f"{S_OTHER}[session]", f"{S_OTHER}[bearer]"})]
SECURITY_P8 = [(SECURITY, [SOC], {
    f"{SOC}::test_the_operator_reads_and_runs_materiality_and_stops_after_a_second_company",
    f"{SOC}::test_the_operator_downloads_both_materiality_workbooks_of_the_work_company_only",
})]

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    (1, "P1", "_path 가리기 지움(토픽 이름이 문장에 실림)",
     [(BINDING, swap("            masked = part in _DICT_KEY_FIELDS\n", "            masked = False\n"))],
     [(PURE, [TB], {*(f"{MASKED}[{c}]" for c in CASES), NOT_TEXT, PATH_ONLY})]),
    (1, "P2", "[key] 마디를 남김",
     [(BINDING, swap(' and part != "[key]":', ":"))],
     [(PURE, [TB], {NOT_TEXT, PATH_ONLY})]),
    (1, "P3", "inputs 가 today() 를 두 번 읽음(검사·입력 따로)",
     [(BINDING, swap("        _accept(options, day)\n", "        _accept(options, today())\n"))],
     [(PURE, [TB], {ONCE})]),
    (1, "P14", "러너 몫: dict 칸 이름 자체도 * 로 가림(위치가 사라짐)",
     [(BINDING, swap("            parts.append(part)\n            masked",
                     '            parts.append("*" if part in _DICT_KEY_FIELDS else part)\n            masked'))],
     [(PURE, [TB], {*(f"{MASKED}[{c}]" for c in CASES), NOT_TEXT, PATH_ONLY})]),
    (2, "P4", "결과 action 의 module 검사 지움",
     [(ACTION, swap("    if run is None or run.module != MODULE:", "    if run is None:"))],
     [(BUSINESS, [TR], {R_404, R_OTHER_DONE}), *AT_3(SECURITY_P4)]),
    (2, "P5", "find_run 대신 회사 조건 없는 읽기(실행의 회사로 갈아 읽음)",
     [(ACTION, swap(FIND, UNSCOPED + FIND))],
     [(BUSINESS, [TR], {R_404}), *AT_3(SECURITY_P5)]),
    (2, "P6", "failed 를 done 처럼",
     [(ACTION, swap('    if run.status != "done":', '    if run.status not in ("done", "failed"):'))],
     [(BUSINESS, [TR], {R_409})]),
    (2, "P7", "RUN_NOT_DONE 을 404 로",
     [(ROUTE, swap('return ApplicationError("conflict", "run_not_done", "실행이 아직 끝나지 않았다")',
                   'return ApplicationError("not_found", "not_found", "그런 실행이 없다")'))],
     [(BUSINESS, [TR], {R_409})]),
    (2, "P8", "OPERATOR_RUN_MODULES 에서 materiality 뺌",
     [(PERM, swap('frozenset({"greenwash", "translation", "dataverify", "materiality"})',
                  'frozenset({"greenwash", "translation", "dataverify"})'))],
     [(PURE, [TP], {P_MODULES}), (BUSINESS, [TO], {O_MADE, O_READ, O_LIST, O_RESUME}), *AT_3(SECURITY_P8)]),
    (2, "P9", "권한 칸 COMPANY → CUSTOMER",
     [(PERM, swap('    "materiality_result_get": COMPANY,', '    "materiality_result_get": CUSTOMER,'))],
     [(PURE, [TP], {P_NEEDS}), (BUSINESS, [TO, TW], {O_READ, W_LOWER})]),
    (2, "P10", "경로가 @2 아닌 첫 결과 행을 읽음",
     [(ACTION, swap("next((r.body for r in results if r.schema_version == RESULT_SHAPE_V2), None)",
                    "next((r.body for r in results), None)"))],
     [(BUSINESS, [TR], {R_AT1})]),
    (2, "P11", "permitted 에 dataverify_result_get 를 넘김",
     [(ROUTE, swap('permitted(request, "materiality_result_get")', 'permitted(request, "dataverify_result_get")'))],
     [(BUSINESS, [TW], {W_RAISE})]),
    (3, "P12", "config/api.py 의 auth 를 뺌",
     [(API, swap('api.add_router("/materiality", materiality_router, auth=[company_scoped_auth_or_next, session_cookie])',
                 'api.add_router("/materiality", materiality_router)'))],
     # 세션 없이는 여전히 401(경로의 permitted 가 주체 없음을 막는다) — 세션·Bearer 를 실은 요청이 인증을 못 받아 빨개진다
     [(SECURITY, [SM], {f"{S_OTHER}[session]", f"{S_OTHER}[bearer]", S_AMBIG})]),
    (3, "P13", "materiality_run_paths 분류를 contract_only 로",
     [(PATHS, swap('    ("GET", "/materiality/runs/{run_id}/result"): "materiality_run_paths",',
                   '    ("GET", "/materiality/runs/{run_id}/result"): "contract_only",'))],
     [(SECURITY, [STP], {STP + f"::test_a_contract_only_route_is_501_and_writes_nothing[{S_RESULT_PATH}]"})]),
]
PLANTS = [p[1:] for p in PLANTS if p[0] <= COMMIT and (ONLY is None or p[1] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    done = subprocess.run([*layer[1], *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (.+?)(?: - .*)?$", text, flags=re.M))  # 매개 id 에 빈칸이 있다(GET /…)
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool | None:
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
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, _last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return None if skipped and hit_all else hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, what, edits, checks in PLANTS:
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
