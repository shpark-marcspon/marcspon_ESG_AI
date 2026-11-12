#!/usr/bin/env bash
# 밴드 OP1(MARC-TICK-222: 운영 관리자가 작업 회사로 그린워싱 업무 — 회사 동작 칸·인증 통과·회사 고르기·이름 풀기)의
# 심은 파손(발주서 band-handoffs/OP1-order.md §3-4). 틀은 planted-breaks-AS2b.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤
# 원본 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-OP1.sh --commit <1|2|3> [--with-containers] [--only 1,10a]
#   --commit 1 = 1~11·13·17(권한 표·인증·회사 고르기·실행 모듈 — 10 은 a·b·c 셋), 2 = + 14~16·18, 3 = 전부(+ 12·19).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은
# 수에 넣지 않는다. 보안 층은 직렬(test-security.sh).
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: OP1_OUT(기본: 워크트리 곁의 OP1.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${OP1_OUT:-$(cd "$ROOT/.." && pwd)/OP1.out}"
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
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2", "3"):
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")
if COMMIT == 0:
    sys.exit("--commit <1|2|3> 가 필요하다")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


E = Path("esgapi")
PERM = E / "core/permissions.py"
BEARER = E / "core/auth/bearer.py"
USERS = E / "user/service/apis/users.py"
CONFIG = E / "config/api.py"
RUNS = E / "runs/service/apis/runs.py"
TPERM = "esgapi/core/tests/test_permissions.py"
TBEAR = "esgapi/core/tests/auth/test_bearer.py"
TWORK = "esgapi/user/tests/service/apis/test_operator_work_company.py"
TRUNS = "esgapi/runs/tests/service/apis/test_runs_operator.py"
TP = "tests/security/test_tenant_paths.py"
TP_A = TP + "::test_an_operator_bearer_with_two_companies_is_400_on_the_company_work"
TP_B = TP + "::test_an_operator_bearer_is_403_on_every_customer_only_company_operation"
TABLE = [TPERM + "::test_the_table_is_these_needs", TPERM + "::test_the_cells_are_partitioned"]

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

INITIAL = "        if principal.is_initial:\n            raise password_change_required()\n        return principal\n"
# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", "CompanyScopedAuth 가 운영 관리자를 다시 401",
     [(BEARER, swap('if principal.company_id is None and principal.kind != "admin":', "if principal.company_id is None:"))],
     [(PURE, [TBEAR], {TBEAR + "::test_the_company_auth_lets_an_operator_token_through_without_a_company"}),
      (SECURITY, [TP], {TP_A, TP_B})]),
    ("2", "company_of 가 운영 관리자에게 포트 대신 회사 표의 첫 행",
     [(BEARER, swap("    return _operator_company()\n",
                    "    from esgapi.organization.models import Company\n\n    return Company.sole_candidates()[0].pk\n"))],
     [(PURE, [TBEAR], {TBEAR + "::test_an_operator_company_is_what_the_port_chooses"}),
      (SECURITY, [TP], {TP_A})]),
    ("3", "operator_work_company 의 ManyCompanies 를 첫 회사로",
     [(USERS, swap('        raise ApplicationError("invalid_input", "company_ambiguous", COMPANY_AMBIGUOUS)\n'
                   '    if isinstance(sole, NoCompany):\n        raise ApplicationError("invalid_input"',
                   "        from esgapi.organization.models import Company\n\n"
                   "        return Company.sole_candidates()[0].pk\n"
                   '    if isinstance(sole, NoCompany):\n        raise ApplicationError("invalid_input"'))],
     [(BUSINESS, [TWORK], {TWORK + "::test_two_companies_are_ambiguous"}), (SECURITY, [TP], {TP_A})]),
    ("4", "operator_work_company 의 비활성 검사 지움",
     [(USERS, swap('    if not sole.company.is_active:\n        raise ApplicationError("forbidden", "company_inactive", '
                   "COMPANY_INACTIVE)\n", ""))],
     [(BUSINESS, [TWORK], {TWORK + "::test_one_inactive_company_is_403"})]),
    ("5", "CompanyScopedAuth 의 is_initial 검사를 고객사 사용자에게만",
     [(BEARER, swap("        if principal.is_initial:\n",
                    '        if principal.is_initial and principal.kind == "service":\n'))],
     [(PURE, [TBEAR], {TBEAR + "::test_the_company_auth_refuses_an_initial_token_before_the_body"})]),
    ("6", "inventory_calc 를 COMPANY 로",
     [(PERM, swap('    "inventory_calc": CUSTOMER,\n', '    "inventory_calc": COMPANY,\n'))],
     [(PURE, [TPERM], {*TABLE, TPERM + "::test_an_operator_is_refused_every_customer_cell"}),
      (SECURITY, [TP], {TP_B})]),
    ("7", "user_me 를 COMPANY 로",
     [(PERM, swap('    "user_me": SELF,\n', '    "user_me": COMPANY,\n'))],
     [(PURE, [TPERM], {*TABLE, TPERM + "::test_the_company_work_is_not_the_self_cell"})]),
    ("8", "user_list 를 COMPANY 로",
     [(PERM, swap('    "user_list": OPERATOR,\n', '    "user_list": COMPANY,\n'))],
     [(PURE, [TPERM], {*TABLE, TPERM + "::test_the_three_user_admin_cells_are_the_same"})]),
    ("9", "runs_create 의 OPERATOR_RUN_MODULES 검사 지움",
     [(RUNS, swap('    if principal.kind == "admin" and body.module not in OPERATOR_RUN_MODULES:\n'
                  '        raise ApplicationError("forbidden", "forbidden", "운영 관리자는 그린워싱 실행만 만든다")\n', ""))],
     [(BUSINESS, [TRUNS], {TRUNS + "::test_an_operator_may_create_only_a_greenwash_run_and_is_refused_before_choosing_a_company"})]),
    ("10a", "runs_list 의 운영 관리자 거름 지움",
     [(RUNS, swap('    if principal.kind == "admin":  # 운영 관리자는 그린워싱 실행만 본다\n',
                  "    if principal.kind == \"nobody\":  # 운영 관리자는 그린워싱 실행만 본다\n"))],
     [(BUSINESS, [TRUNS], {TRUNS + "::test_the_operator_list_shows_only_greenwash_runs"})]),
    ("10b", "runs_get 의 module 검사 지움",
     [(RUNS, swap('    if run is None or not _visible(principal, run):\n        raise _not_found("그런 실행이 없다")',
                  '    if run is None:\n        raise _not_found("그런 실행이 없다")'))],
     [(BUSINESS, [TRUNS], {TRUNS + "::test_the_operator_gets_404_on_a_run_of_another_module"})]),
    ("10c", "runs_file_get 의 module 검사 지움",
     [(RUNS, swap('        if run is None or not _visible(principal, run):\n            raise _not_found("그런 파일이 없다")',
                  '        if run is None:\n            raise _not_found("그런 파일이 없다")'))],
     [(BUSINESS, [TRUNS], {TRUNS + "::test_the_operator_gets_404_on_a_file_of_another_modules_run"})]),
    ("11", "고객사 사용자의 company_of 가 포트를 부름",
     [(BEARER, swap("        return principal.company_id\n    if _operator_company is None:",
                    "        return principal.company_id if _operator_company is None else _operator_company()\n"
                    "    if _operator_company is None:"))],
     [(PURE, [TBEAR], {TBEAR + "::test_a_customer_company_is_its_own_and_never_asks_the_port"}),
      (SECURITY, [TP], {TP + "::test_numeric_neighbour_document_ids_are_not_found_for_my_session[",
                        TP + "::test_a_customer_bearer_passes_auth_and_permission_on_every_company_operation"})]),
    ("13", "회사 고르기를 인증 단계로",
     [(BEARER, swap(INITIAL, INITIAL.replace("        return principal\n",
                                             '        if principal.kind == "admin":\n            company_of(principal)\n'
                                             "        return principal\n")))],
     [(SECURITY, [TP], {TP_B})]),
    ("17", "config 의 use_operator_company 줄 지움",
     [(CONFIG, swap("use_operator_company(operator_work_company)  # 운영 관리자의 작업 회사(MARC-ENT-374)\n", ""))],
     [(BUSINESS, [TWORK], {TWORK + "::test_config_plugs_it_into_core"}), (SECURITY, [TP], {TP_A})]),
]
USEL = E / "user/service/selectors/user.py"
DOCS = E / "core/service/services/documents.py"
ORG = E / "organization/service/selectors/organization.py"
TPEOPLE = "esgapi/user/tests/service/selectors/test_user_people.py"
TLOGS = "esgapi/user/tests/service/apis/test_run_logs_operator.py"
TGW = "esgapi/greenwash/tests/service/actions/test_checks_operator.py"
TKIND = "esgapi/core/tests/service/services/test_documents_actor_kind.py"
TNAME = "esgapi/organization/tests/service/selectors/test_organization_company_name.py"
SECOND_STEP = "    for user_id in sorted(ids):\n        found = found | User.admin_by_id(user_id)\n"
SECOND = [  # ② 14~16·18
    ("14", "people_of 가 운영 관리자를 안 풂",
     [(USEL, swap(SECOND_STEP, ""))],
     [(BUSINESS, [TPEOPLE, TLOGS, TGW],
       {TPEOPLE + "::test_a_customer_of_the_company_and_an_operator_are_both_named",
        TPEOPLE + "::test_a_customer_of_another_company_is_not_named_but_the_operator_is",
        TLOGS + "::test_a_run_made_by_the_operator_carries_the_operators_name",
        TGW + "::test_the_operator_who_uploaded_and_confirmed_is_named"})]),
    ("15", "confirm_upload 의 actor_kind 를 service 로",
     [(DOCS, swap('else (actor_kind or "service"),', 'else "service",'))],
     [(BUSINESS, [TKIND], {TKIND + "::test_the_upload_line_names_the_actor_kind[admin]"})]),
    ("16", "company_name 이 늘 빈 글자",
     [(ORG, swap('    return "" if row is None else row.name\n', '    return ""\n'))],
     [(BUSINESS, [TNAME, TGW], {TNAME + "::test_the_name_of_the_company_and_empty_for_none",
                               TGW + "::test_the_operator_who_uploaded_and_confirmed_is_named"})]),
    ("18", "people_of 둘째 단계가 kind 조건 없이 id 로 풂",
     [(USEL, swap(SECOND_STEP, "    for user_id in sorted(ids):\n"
                               "        found = found | User.unscoped.filter(pk=user_id)\n"))],
     [(BUSINESS, [TPEOPLE, TGW], {TPEOPLE + "::test_a_customer_of_another_company_is_not_named_but_the_operator_is",
                                 TGW + "::test_a_customer_of_another_company_is_not_named"})]),
]
DAPI = E / "core/service/apis/documents.py"
TOC = "tests/security/test_operator_company.py"
OC = TOC + "::"
THIRD = [  # ③ 12·19·20(검증 ② R1) + ①·② 의 파손을 보안 층 새 시험으로 다시
    ("12", "질의 companyId 를 문서 목록의 회사 고르기에 넘김",
     [(DAPI, swap("    principal = permitted(request, \"core_documents_list\")\n    page = selectors.list_documents(\n"
                  "        company_id=company_of(principal),\n",
                  "    principal = permitted(request, \"core_documents_list\")\n    page = selectors.list_documents(\n"
                  "        company_id=int(request.GET.get(\"companyId\") or company_of(principal)),\n"))],
     [(SECURITY, [TOC], {OC + "test_a_query_company_id_does_not_move_the_work_company",
                         OC + "test_a_customer_query_company_id_does_not_open_another_company",
                         OC + "test_a_cookie_session_stays_a_customer_and_ignores_a_query_company_id"})]),
    ("19", "운영 관리자 감사 줄의 company_id 를 None 으로",
     [(DOCS, swap("            company_id=company_id,\n            actor_kind=\"command\" if actor_user_id is None else (actor_kind or \"service\"),\n",
                  "            company_id=None if actor_kind == \"admin\" else company_id,\n"
                  "            actor_kind=\"command\" if actor_user_id is None else (actor_kind or \"service\"),\n"))],
     [(SECURITY, [TOC], {OC + "test_the_operators_audit_lines_name_the_admin_and_the_work_company"})]),
    ("20", "문서 경로가 올림 확인에 actor_kind 를 안 넘김(검증 ② R1)",
     [(DAPI, swap("        actor_user_id=int(principal.user_id),\n        actor_kind=principal.kind,\n    )\n    if isinstance(result, selectors.DocumentNotFound):\n        raise _not_found()\n    if isinstance(result, services.NotUploaded):",
                  "        actor_user_id=int(principal.user_id),\n    )\n    if isinstance(result, selectors.DocumentNotFound):\n        raise _not_found()\n    if isinstance(result, services.NotUploaded):"))],
     [(SECURITY, [TOC], {OC + "test_the_operators_audit_lines_name_the_admin_and_the_work_company"})]),
]
# ③ 에서 ①·② 의 파손이 새 보안 시험(3-3)도 빨갛게 하는지 — 겨눔에 더한다
THIRD_EXTRA: dict[str, set[str]] = {
    "1": {OC + "test_the_operator_does_the_company_work_in_the_sole_company"},
    "2": {OC + "test_without_a_usable_sole_company_the_choosing_16_write_nothing["},
    "3": {OC + "test_without_a_usable_sole_company_the_choosing_16_write_nothing[two]"},
    "4": {OC + "test_without_a_usable_sole_company_the_choosing_16_write_nothing[inactive]"},
    "5": {OC + "test_an_initial_operator_is_403_on_the_company_work_before_the_body"},
    "6": {OC + "test_the_operator_is_403_on_the_customer_only_operations_reading_no_company"},
    "9": {OC + "test_the_operator_is_403_on_translation"},
    "13": {OC + "test_the_operator_is_403_on_the_customer_only_operations_reading_no_company"},
    "14": {OC + "test_after_a_second_company_the_operator_stops_and_each_company_sees_its_own"},
    "15": {OC + "test_the_operators_audit_lines_name_the_admin_and_the_work_company"},
    "17": {OC + "test_the_operator_does_the_company_work_in_the_sole_company"},
}
if COMMIT >= 2:
    PLANTS += SECOND
if COMMIT >= 3:
    PLANTS += THIRD
    PLANTS = [
        (n, what, edits, [*checks, (SECURITY, [TOC], THIRD_EXTRA[n])] if n in THIRD_EXTRA else checks)
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
