#!/usr/bin/env bash
# 밴드 OP2(MARC-TICK-224: 운영 관리자도 영문번역 — 결과 칸 COMPANY·OPERATOR_RUN_MODULES 에 translation·admin 실행 목록의
# 모듈 집합, 결정 MARC-ENT-380)의 심은 파손(발주서 band-handoffs/OP2-order.md §3-4). 틀은 planted-breaks-OP1.sh 그대로다:
# 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-OP2.sh --commit <1|2> [--with-containers] [--only 1,12]
#   --commit 1 = 1~9·12(권한 표·실행 모듈·목록 거름·selector — 12 는 영문번역 경로를 잠시 고쳤다 되씀),
#   2 = 전부(+ 10·11·13, 그리고 ① 의 파손을 ② 의 새 보안 시험으로도 겨눔).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은
# 수에 넣지 않는다. 보안 층은 직렬(test-security.sh).
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: OP2_OUT(기본: 워크트리 곁의 OP2.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${OP2_OUT:-$(cd "$ROOT/.." && pwd)/OP2.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
CONTAINERS = False
ONLY: set[str] | None = None
COMMIT = 0
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2"):
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")
if COMMIT == 0:
    sys.exit("--commit <1|2> 가 필요하다")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


E = Path("esgapi")
PERM = E / "core/permissions.py"
RUNS = E / "runs/service/apis/runs.py"
SEL = E / "runs/service/selectors/runs.py"
USERS = E / "user/service/apis/users.py"
TRAPI = E / "translation/service/apis/translation.py"
TPERM = "esgapi/core/tests/test_permissions.py"
TWIRE = "esgapi/core/tests/test_permissions_wiring.py"
TRUNS = "esgapi/runs/tests/service/apis/test_runs_operator.py"
TSEL = "esgapi/runs/tests/service/selectors/test_runs.py"
TWORK = "esgapi/user/tests/service/apis/test_operator_work_company.py"
TP = "tests/security/test_tenant_paths.py"
TP_A = TP + "::test_an_operator_bearer_with_two_companies_is_400_on_the_company_work"
TP_B = TP + "::test_an_operator_bearer_is_403_on_every_customer_only_company_operation"
TT = "tests/security/test_translation.py"
TT_C = TT + "::test_an_operator_bearer_with_two_companies_is_400_ambiguous_on_the_result"
TOC = "tests/security/test_operator_company.py"
OC = TOC + "::"
OC10 = OC + "test_the_operator_reads_and_runs_translation_in_the_work_company"
OC11 = OC + "test_a_translation_run_of_the_operator_is_ambiguous_after_a_second_company_and_stays_its_companys"
OC12 = OC + "test_the_operator_lists_the_operator_modules_and_a_customer_lists_every_module"
TABLE = [TPERM + "::test_the_table_is_these_needs", TPERM + "::test_the_cells_are_partitioned",
         TPERM + "::test_both_kinds_do_the_company_work"]
WIRE_ANY = TWIRE + "::test_lowering_the_company_work_cell_makes_that_route_forbidden_for_the_operator["
WIRE_TR = WIRE_ANY + "translation_result_get]"
R = TRUNS + "::"
CREATE = R + "test_an_operator_may_create_greenwash_and_translation_runs_and_is_refused_before_choosing_a_company"
LIST = R + "test_the_operator_list_shows_greenwash_and_translation_runs"
GET = R + "test_the_operator_gets_404_on_a_run_of_another_module"
FILE = R + "test_the_operator_gets_404_on_a_file_of_another_modules_run"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가). 순수는 직렬(-n 없음 — OP1 물을 거리 1)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

ADMIN_LIST = "            modules = OPERATOR_RUN_MODULES\n"
CREATE_CHECK = (
    '    if principal.kind == "admin" and body.module not in OPERATOR_RUN_MODULES:\n'
    '        raise ApplicationError("forbidden", "forbidden", "운영 관리자는 이 모듈의 실행을 만들 수 없다")\n'
)
# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", "translation_result_get 을 CUSTOMER 로 되돌림",
     [(PERM, swap('    "translation_result_get": COMPANY,\n', '    "translation_result_get": CUSTOMER,\n'))],
     # 업무: 칸이 18 이 되면 매개(칸에서 뽑음)에서 translation_result_get 이 빠지고 나머지가 `== 19` 에서 빨강 — 묶음 하나라도.
     # 보안: 고객사 전용 시험(TP_B)은 글자 목록 9 를 돌아 초록이 맞다 — 회사 둘 400 쪽(TP_A·TT_C)이 문다.
     [(PURE, [TPERM], set(TABLE)), (BUSINESS, [TWIRE], {WIRE_ANY}),
      (SECURITY, [TP, TT, TOC], {TP_A, TT_C, OC10})]),
    ("2", "OPERATOR_RUN_MODULES 에서 translation 뺌",
     [(PERM, swap('frozenset({"greenwash", "translation"})', 'frozenset({"greenwash"})'))],
     [(PURE, [TPERM], {TPERM + "::test_the_operator_runs_greenwash_and_translation"}),
      (BUSINESS, [TRUNS], {CREATE, LIST, GET, FILE, R + "test_a_run_created_by_the_operator_runs_to_done[translation]"}),
      (SECURITY, [TOC], {OC10})]),
    ("3", "runs_list 의 admin·module 없음을 옛 식(그린워싱 하나)으로",
     [(RUNS, swap(ADMIN_LIST, '            module = "greenwash"\n'))],
     [(BUSINESS, [TRUNS], {LIST})]),
    ("4", "run_page 가 modules 를 무시",
     [(SEL, swap("    if modules is not None:\n        rows = rows.filter(module__in=modules)\n", ""))],
     [(BUSINESS, [TSEL, TRUNS], {TSEL + "::test_run_page_filters_by_a_module_set",
                                 TSEL + "::test_run_page_ands_the_module_and_the_module_set", LIST})]),
    ("5", "admin 목록이 modules 대신 거름 없음",
     [(RUNS, swap(ADMIN_LIST, "            modules = None\n"))],
     [(BUSINESS, [TRUNS], {LIST})]),
    ("6", "_visible 을 늘 True",
     [(RUNS, swap('    return principal.kind != "admin" or run.module in OPERATOR_RUN_MODULES\n', "    return True\n"))],
     [(BUSINESS, [TRUNS], {GET, FILE})]),
    ("7", "runs_file_get 의 admin find_run 검사 지움",
     [(RUNS, swap('    if principal.kind == "admin":  # 출력 파일 행에는 모듈이 없다 — 실행을 먼저 본다\n',
                  '    if principal.kind == "nobody":  # 출력 파일 행에는 모듈이 없다 — 실행을 먼저 본다\n'))],
     [(BUSINESS, [TRUNS], {FILE})]),
    ("8", "runs_create 의 admin 모듈 검사 지움",
     [(RUNS, swap(CREATE_CHECK, ""))],
     [(BUSINESS, [TRUNS], {CREATE})]),
    ("9", "translation_result_get 을 OPERATOR 로",
     [(PERM, swap('    "translation_result_get": COMPANY,\n', '    "translation_result_get": OPERATOR,\n'))],
     [(PURE, [TPERM], set(TABLE)), (SECURITY, [TOC], {OC10})]),
    ("12", "영문번역 결과 경로가 권한 표를 안 읽음(permitted → principal_of)",
     [(TRAPI, swap("from esgapi.core.auth.bearer import company_of, permitted\n",
                   "from esgapi.core.auth.bearer import company_of, permitted, principal_of\n")),
      (TRAPI, swap('    principal = permitted(request, "translation_result_get")\n',
                   "    principal = principal_of(request)\n"))],
     [(BUSINESS, [TWIRE], {WIRE_TR})]),
]
SECOND = [  # ② 10·11·13 — 회사 고르기(user 의 operator_work_company)를 영문번역 결과 경로의 새 보안 시험이 문다
    ("10", "operator_work_company 의 ManyCompanies 를 첫 회사로",
     [(USERS, swap('        raise ApplicationError("invalid_input", "company_ambiguous", COMPANY_AMBIGUOUS)\n'
                   '    if isinstance(sole, NoCompany):\n        raise ApplicationError("invalid_input"',
                   "        from esgapi.organization.models import Company\n\n"
                   "        return Company.sole_candidates()[0].pk\n"
                   '    if isinstance(sole, NoCompany):\n        raise ApplicationError("invalid_input"'))],
     [(SECURITY, [TOC, TP, TT], {OC11, TP_A, TT_C})]),
    ("11", "operator_work_company 의 비활성 검사 지움",
     [(USERS, swap('    if not sole.company.is_active:\n        raise ApplicationError("forbidden", "company_inactive", '
                   "COMPANY_INACTIVE)\n", ""))],
     [(BUSINESS, [TWORK], {TWORK + "::test_one_inactive_company_is_403"}),
      (SECURITY, [TOC], {OC + "test_without_a_usable_sole_company_the_choosing_17_write_nothing[inactive]"})]),
    ("13", "OPERATOR_RUN_MODULES 에 inventory 더함(검증 ① R1 — 보안 층이 ⑫ 로 문다)",
     [(PERM, swap('frozenset({"greenwash", "translation"})', 'frozenset({"greenwash", "translation", "inventory"})'))],
     [(PURE, [TPERM], {TPERM + "::test_the_operator_runs_greenwash_and_translation"}),
      (BUSINESS, [TRUNS], {CREATE, LIST, GET, FILE}),
      (SECURITY, [TOC], {OC12})]),
]
# ② 에서 ① 의 파손이 새 보안 시험(3-3 의 4·5)도 빨갛게 하는지 — 겨눔에 더한다
SECOND_EXTRA: dict[str, set[str]] = {
    "1": {OC11},
    "2": {OC11, OC12},
    "3": {OC12},
    "5": {OC12},
}
if COMMIT >= 2:
    PLANTS += SECOND
    PLANTS = [
        (n, what, edits, [*checks, (SECURITY, [TOC], SECOND_EXTRA[n])] if n in SECOND_EXTRA else checks)
        for n, what, edits, checks in PLANTS
    ]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def checks_of(plant):
    return plant[3]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def hit(want: str, failed: set[str]) -> bool:
    return any(f.startswith(want) for f in failed) if want.endswith("[") else want in failed


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in checks_of(p):
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, _ in PLANTS:
    plant = next(p for p in PLANTS if p[0] == number)
    originals = {f: f.read_bytes() for f, _ in edits}  # 같은 파일에 둘 심어도 원본은 처음 것
    try:
        ok_plant = True
        for f, edit in edits:
            text = f.read_text(encoding="utf-8")
            new = edit(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"[{number}] 심기 실패(파일이 바뀌지 않음) — 못 잡은 것으로 센다 — {what}")
            planted += 1
            continue
        ran = 0
        all_hit = True
        for layer, targets, expected in checks_of(plant):
            label = f"[{number}/{layer[0]}]"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            ran += 1
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            missing = sorted(w for w in expected if not hit(w, failed))
            ok = code != 0 and not missing
            all_hit = all_hit and ok
            print(f"{label} {'잡음' if ok else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        if ran:
            planted += 1
            caught += 1 if all_hit else 0
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
for f in files:
    print(f"  {f} {hashlib.sha256(f.read_bytes()).hexdigest()}")
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
