#!/usr/bin/env bash
# 밴드 UA1 의 심은 파손(발주서 band-handoffs/UA1-order.md §3). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-UA1.sh [--boundary 1|2|3] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 그 층의 pytest 가 0 아닌 종료이고, 빨개져야 할
# 시험 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# 경계 n 에는 커밋 n 까지의 P 만 심는다. 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」
# 으로 찍고 잡은 수·심은 수에 넣지 않는다(조용한 초록 0).
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지
# 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: UA1_OUT(기본: 워크트리 곁의 UA1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${UA1_OUT:-$(cd "$ROOT/.." && pwd)/UA1.out}"
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
BOUNDARY = 3
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2", "3"):
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


SVC_USER = Path("esgapi/user/service/services/user.py")
APIS_USERS = Path("esgapi/user/service/apis/users.py")
ACT_ACCOUNT = Path("esgapi/user/service/actions/account.py")
SEL_USER = Path("esgapi/user/service/selectors/user.py")
SCH_USERS = Path("esgapi/user/service/schemas/users.py")
TU = "esgapi/user/tests/service/services/test_user.py"
TPERM = "esgapi/core/tests/test_permissions.py"
TACC = "esgapi/user/tests/service/actions/test_account.py"
TUSERS = "esgapi/user/tests/service/apis/test_users.py"
TSEL = "esgapi/user/tests/service/selectors/test_user.py"
TCONTRACT = "esgapi/config/tests/test_api_contract.py"
SADMIN = "tests/security/test_user_admin.py"
SVC_LOGIN = Path("esgapi/user/service/services/login.py")
APIS_USER = Path("esgapi/user/service/apis/user.py")
TLOGIN = "esgapi/user/tests/service/services/test_login.py"
TAPILOGIN = "esgapi/user/tests/service/apis/test_login.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
SLOGIN = "tests/security/test_login.py"
SREFRESH = "tests/security/test_refresh.py"
STENANT = "tests/security/test_tenant_paths.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "검사기 목록에 CommonPasswordValidator 를 되살림",
     [(SVC_USER, swap('    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},\n',
                      '    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},\n'
                      '    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},\n'))],
     [(PURE, [TU], {TU + "::test_password_problems_now_pass_what_the_removed_validators_refused[common]"})]),
    ("P2", 1, "MinimumLengthValidator 의 min_length 를 7 로",
     [(SVC_USER, swap('"OPTIONS": {"min_length": 8}}', '"OPTIONS": {"min_length": 7}}'))],
     [(PURE, [TU], {TU + "::test_password_problems_draw_the_line_between_seven_and_eight_characters"})]),
    ("P3", 2, "PATCH 경로의 permitted(request, \"user_update\") 를 request.auth 로 바꿈(첫 문장 권한 검사를 끔)",
     [(APIS_USERS, swap('    principal = permitted(request, "user_update")\n', "    principal = request.auth\n"))],
     [(PURE, [TPERM], {TPERM + "::test_each_route_checks_its_own_operation_id_first",
                       TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"})]),
    ("P4", 2, "actions/account.py 첫 줄 can_manage_customer_users 검사를 지움",
     [(ACT_ACCOUNT, swap('    if not can_manage_customer_users(actor_kind):\n        return Forbidden("user_update")\n', ""))],
     [(PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"}),
      (BUSINESS, [TACC], {TACC + "::test_a_non_operator_is_forbidden_before_anything_is_read"})]),
    ("P5", 2, "actions/account.py 의 refresh 끊기 줄을 지움",
     [(ACT_ACCOUNT, swap("        RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)\n", "        pass\n"))],
     [(BUSINESS, [TACC], {TACC + "::test_deactivating_cuts_only_that_users_refresh_at_that_moment",
                          TACC + "::test_reactivating_cuts_a_refresh_left_uncut_but_the_same_value_does_not"}),
      (SECURITY, [SADMIN], {SADMIN + "::test_deactivating_revokes_every_family_and_is_committed_and_reactivating_does_not_revive",
                            SADMIN + "::test_a_refresh_left_uncut_while_inactive_is_cut_on_reactivation"})]),
    ("P6", 2, "actions/account.py 의 lock_account(company_id, …) 를 lock_account(None, …) 로",
     [(ACT_ACCOUNT, swap("    row = selectors.lock_account(company_id, user_id)\n", "    row = selectors.lock_account(None, user_id)\n"))],
     [(BUSINESS, [TUSERS], {TUSERS + "::test_a_rename_changes_only_the_name_and_answers_the_full_shape",
                            TUSERS + "::test_name_and_active_change_together"})]),
    ("P7", 2, "셀렉터의 교환 행 거르기(exclude)를 지움",
     [(SEL_USER, swap("        .exclude(password__startswith=UNUSABLE_PASSWORD_PREFIX)\n", ""))],
     [(BUSINESS, [TUSERS, TSEL], {TUSERS + "::test_the_list_leaves_out_exchange_rows",
                                  TSEL + "::test_the_list_leaves_out_rows_whose_password_cannot_be_used"})]),
    ("P8", 2, "status=locked 의 경계를 __gt 로",
     [(SEL_USER, swap("login_expiry_at__gte=now", "login_expiry_at__gt=now"))],
     [(BUSINESS, [TUSERS, TSEL], {TUSERS + "::test_status_filters_by_the_four_states_to_the_second",
                                  TSEL + "::test_status_and_q_filter_and_count_after_filtering"})]),
    ("P9", 2, "UserCreateIn.username pattern 을 \\w 로 되돌림",
     [(SCH_USERS, swap('pattern=r"^[A-Za-z0-9_.@+-]+$"', 'pattern=r"^[\\w.@+-]+$"'))],
     [(PURE, [TCONTRACT], {TCONTRACT + "::test_committed_openapi_matches_the_code"}),
      (BUSINESS, [TUSERS], {TUSERS + "::test_a_username_outside_ascii_is_422_and_makes_nothing[hangul]",
                            TUSERS + "::test_a_username_outside_ascii_is_422_and_makes_nothing[fullwidth]"})]),
    ("P15", 2, "인증 끔 — PATCH 경로의 auth=access_token_auth 를 지움(test_tenant_paths 의 표가 문다)",
     [(APIS_USERS, swap('    operation_id="user_update",\n    response={200: CustomerUserOut, **USER_ADMIN_BODY_ERROR_RESPONSES},\n    auth=access_token_auth,\n',
                        '    operation_id="user_update",\n    response={200: CustomerUserOut, **USER_ADMIN_BODY_ERROR_RESPONSES},\n'))],
     [(SECURITY, [STENANT], {STENANT + "::test_every_operation_is_in_the_table"})]),
    ("P16", 2, "회사 검사 끔 — action 의 lock_account(company_id, …) 를 회사 없는 조회로(개정 3 — 테스트 감독 조건 ②, 검증 B1)",
     [(ACT_ACCOUNT, swap("    row = selectors.lock_account(company_id, user_id)\n",
                         '    row = selectors.User.unscoped.select_for_update().filter(pk=user_id, kind="service").first()\n'))],
     [(SECURITY, [SADMIN], {SADMIN + "::test_a_patch_with_another_company_is_404_and_changes_nothing"}),
      (BUSINESS, [TACC], {TACC + "::test_rows_outside_the_company_or_not_customers_are_not_found_and_unchanged"})]),
    ("P10", 3, "login() 의 서브도메인 없는 길에서 운영 관리자보다 고객사를 먼저 찾음",
     [(SVC_LOGIN, swap(
         "        user = selectors.find_admin(username)\n"
         "        if user is None:  # 운영 관리자 먼저(처분 ⑩ ㄱ) — 찾기는 둘이어도 해시는 아래 한 번이다\n"
         "            company_id = ports.sole_company_id()\n"
         "            user = selectors.find_customer(company_id, username) if company_id is not None else None\n",
         "        company_id = ports.sole_company_id()\n"
         "        user = selectors.find_customer(company_id, username) if company_id is not None else None\n"
         "        if user is None:\n"
         "            company_id = None\n"
         "            user = selectors.find_admin(username)\n"))],
     [(SECURITY, [SLOGIN], {SLOGIN + "::test_with_one_company_the_operator_of_the_same_username_comes_first"}),
      (BUSINESS, [TLOGIN], {TLOGIN + "::test_without_a_subdomain_the_operator_comes_first"})]),
    ("P11", 3, "sole_company_id() 가 is_active 를 보지 않음",
     [(APIS_USER, swap("    if isinstance(sole, SoleCompany) and sole.company.is_active:\n", "    if isinstance(sole, SoleCompany):\n"))],
     [(SECURITY, [SLOGIN], {SLOGIN + "::test_with_one_inactive_company_a_customer_without_a_subdomain_is_401"}),
      (BUSINESS, [TAPILOGIN], {TAPILOGIN + "::test_with_one_inactive_company_the_customer_path_is_closed"})]),
    ("P12", 3, "서브도메인 없는 길에서 사용자가 없으면 check_password 를 건너뜀",
     [(SVC_LOGIN, swap("    ok = check_password(password, encoded)\n",
                       "    ok = check_password(password, encoded) if (user is not None or subdomain is not None) else False\n"))],
     [(BUSINESS, [TLOGIN], {
         TLOGIN + "::test_every_miss_without_a_subdomain_is_invalid_credentials_after_exactly_one_hash[sole-unknown-username]",
         TLOGIN + "::test_every_miss_without_a_subdomain_is_invalid_credentials_after_exactly_one_hash[no-sole-company-customer]"})]),
    ("P13", 3, "create_customer_user 의 운영 관리자 아이디 검사를 지움",
     [(SVC_USER, swap("    if selectors.find_admin(username) is not None:\n        return UsernameTaken()\n", ""))],
     [(BUSINESS, [TU, TUSERS], {TU + "::test_a_customer_with_an_operators_username_is_taken_and_nothing_is_made",
                                TUSERS + "::test_a_customer_with_an_operators_username_is_409_and_makes_nothing"})]),
    ("P14", 3, "test_static_rules 를 그대로 두고 services/login.py 에서 find_sole_company 를 직접 import·가리킴",
     [(SVC_LOGIN, swap("from django.contrib.auth.hashers import check_password, make_password\n",
                       "from django.contrib.auth.hashers import check_password, make_password\n\n"
                       "from esgapi.organization.service.selectors.organization import find_sole_company\n")),
      (SVC_LOGIN, swap("            company_id = ports.sole_company_id()\n",
                       "            company_id = ports.sole_company_id() if find_sole_company else None\n"))],
     [(PURE, [TSTATIC], {TSTATIC + "::test_the_company_choosers_are_wired_only_in_the_user_admin_routes"})]),
    ("P17", 3, "(:356 준비 차례의 짝) 서브도메인 있는 길이 고객사 대신 같은 username 의 운영 관리자 행을 읽음",
     [(SVC_LOGIN, swap("        company_id = ports.company_id_of(subdomain)\n"
                       "        user = selectors.find_customer(company_id, username) if company_id is not None else None\n",
                       "        company_id = ports.company_id_of(subdomain)\n"
                       "        user = selectors.find_admin(username) if company_id is not None else None\n"))],
     [(SECURITY, [SLOGIN], {SLOGIN + "::test_an_operator_and_a_customer_with_the_same_username_do_not_cross"})]),
    ("P18", 3, "(test_refresh 준비 차례의 짝) 운영 관리자의 refresh 가 같은 username 의 고객사 행을 읽음",
     [(SVC_LOGIN, swap("            user = selectors.account(claims.company_id, user_id)\n",
                       "            user = selectors.account(claims.company_id, user_id)\n"
                       "            if user is not None and user.kind == \"admin\":\n"
                       "                user = selectors.User.unscoped.filter(kind=\"service\", username=user.username).first()\n"))],
     [(SECURITY, [SREFRESH], {SREFRESH + "::test_an_operator_refresh_reads_the_operator"})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, checks in PLANTS:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
            planted += 1
            continue
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            planted += 1
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            caught += 1 if hit else 0
            missing = sorted(expected - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
