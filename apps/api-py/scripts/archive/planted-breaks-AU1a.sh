#!/usr/bin/env bash
# 밴드 AU1a 의 심은 파손(발주서 band-handoffs/AU1a-order.md §3-2). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AU1a.sh [--boundary 1|2|3] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 그 층의 pytest 가 0 아닌 종료이고, 빨개져야 할
# 시험 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# 경계 n 에는 커밋 n 까지의 P 만 심는다. 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」
# 으로 찍고 잡은 수·심은 수에 넣지 않는다(조용한 초록 0).
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지
# 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 보안 층은 부를 때마다 테스트 DB 를 새로 만들어 마이그레이션한다(심은 마이그레이션이 그대로 들어간다).
# 산출물: AU1A_OUT(기본: 워크트리 곁의 AU1a.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AU1A_OUT:-$(cd "$ROOT/.." && pwd)/AU1a.out}"
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


def cut(pattern: str) -> Callable[[str], str | None]:
    """정규식(DOTALL)에 정확히 한 번 맞는 자리를 지운다."""

    def plant(text: str) -> str | None:
        found = list(re.finditer(pattern, text, flags=re.S))
        return text[: found[0].start()] + text[found[0].end() :] if len(found) == 1 else None

    return plant


MODELS = Path("esgapi/core/models.py")
MIGRATION = Path("esgapi/core/migrations/0001_initial.py")
SVC_AUDIT = Path("esgapi/core/service/services/audit.py")
SEL_AUDIT = Path("esgapi/core/service/selectors/audit.py")
SVC_DOCS = Path("esgapi/core/service/services/documents.py")
SVC_LOGIN = Path("esgapi/user/service/services/login.py")
ACT_PASSWORD = Path("esgapi/user/service/actions/password.py")
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
TSEL = "esgapi/core/tests/service/selectors/test_audit.py"
SAUDIT = "tests/security/test_audit.py"
SOWNER = "tests/security/test_owner.py"
TLOGIN = "esgapi/user/tests/service/services/test_login.py"
TACCOUNT = "esgapi/user/tests/service/actions/test_account.py"
TPASSWORD = "esgapi/user/tests/service/actions/test_password.py"
TDOCS = "esgapi/core/tests/test_documents_services.py"
NOTE_TAIL = "    audit_company_id: int | None = None,\n) -> None:"
LABEL = "target_label=None if user is None else user.username,"
SECRET_SESSION = SAUDIT + "::test_no_secret_reaches_an_audit_line"
API_AUDIT = Path("esgapi/user/service/apis/audit.py")
SEL_USER = Path("esgapi/user/service/selectors/user.py")
PERMS = Path("esgapi/core/permissions.py")
TPERM = "esgapi/core/tests/test_permissions.py"
TAUDITAPI = "esgapi/user/tests/service/apis/test_audit.py"
# 커밋 ③ 뒤에만 있는 시험(경계 1·2 에서는 겨누지 않는다)
AFTER3 = BOUNDARY >= 3

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "마이그레이션의 감사 표 grant 를 SELECT, INSERT, UPDATE 로",
     [(MIGRATION, swap("grant(f'\"{AUDIT}\"', \"SELECT, INSERT\")", "grant(f'\"{AUDIT}\"', \"SELECT, INSERT, UPDATE\")"))],
     [(SECURITY, [SAUDIT, SOWNER], {SAUDIT + "::test_app_role_cannot_change_or_remove_an_audit_line[update]",
                                    SOWNER + "::test_app_role_reads_every_tenant_table_and_deletes_none"})]),
    ("P2", 1, "마이그레이션의 감사 표 grant 를 SELECT, INSERT, DELETE 로",
     [(MIGRATION, swap("grant(f'\"{AUDIT}\"', \"SELECT, INSERT\")", "grant(f'\"{AUDIT}\"', \"SELECT, INSERT, DELETE\")"))],
     [(SECURITY, [SAUDIT, SOWNER], {SAUDIT + "::test_app_role_cannot_change_or_remove_an_audit_line[delete]",
                                    SOWNER + "::test_app_role_reads_every_tenant_table_and_deletes_none"})]),
    ("P3", 1, "operator_rows() 의 company_id__isnull=True 를 지움(모든 행)",
     [(MODELS, swap('(model=cls).filter(company_id__isnull=True)', "(model=cls).filter()"))],
     [(PURE, [TSTATIC], {TSTATIC + "::test_the_audit_entrance_carries_the_no_company_condition"}),
      (BUSINESS, [TSEL], {TSEL + "::test_the_chosen_company_and_the_lines_without_a_company_are_seen_but_not_another_company"}),
      *([(SECURITY, [SAUDIT], {SAUDIT + "::test_an_operator_choosing_b_sees_no_line_of_a"})] if AFTER3 else [])]),
    ("P4", 1, "services/documents.py 에서 AuditEventRow.operator_rows() 를 부름(허용 자리 밖)",
     [(SVC_DOCS, swap("from esgapi.core.models import DocumentRow\n", "from esgapi.core.models import AuditEventRow, DocumentRow\n")),
      (SVC_DOCS, swap("# 큐에 넣는 함수의 꼴", "def _planted() -> object:\n    return AuditEventRow.operator_rows()\n\n\n# 큐에 넣는 함수의 꼴"))],
     [(PURE, [TSTATIC], {TSTATIC + "::test_the_audit_entrance_is_called_only_from_its_places"})]),
    ("P5", 1, "모델·마이그레이션의 action CHECK 를 지움",
     [(MODELS, cut(r"            models\.CheckConstraint\(\n                condition=models\.Q\(action__in=AUDIT_EVENT_ACTIONS\), name=\"core_audit_events_action_check\"\n            \),\n")),
      (MIGRATION, cut(r"                    models\.CheckConstraint\(\n                        condition=models\.Q\(\n                            \(\n                                \"action__in\",.*?name=\"core_audit_events_action_check\",\n                    \),\n"))],
     [(SECURITY, [SAUDIT], {SAUDIT + "::test_the_checks_refuse_what_the_app_would_not_write[unknown-action]"})]),
    ("P6", 1, "list_audit_events 첫 문장 권한 검사를 지움",
     [(SEL_AUDIT, swap('    if not is_allowed("user_audit_list", kind=actor_kind):\n        return AuditForbidden()\n', ""))],
     [(BUSINESS, [TSEL], {TSEL + "::test_a_customer_kind_is_forbidden_before_anything_is_read"}),
      *([(PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"})] if AFTER3 else [])]),
    ("P16", 1, "모델·마이그레이션의 NOT (actor_kind='service' AND company_id IS NULL) CHECK 를 지움",
     [(MODELS, cut(r"            # 고객사 사람의 줄은 회사가 있다:[^\n]*\n            models\.CheckConstraint\(\n                condition=~models\.Q\(actor_kind=\"service\", company_id__isnull=True\),\n                name=\"core_audit_events_service_company_check\",\n            \),\n")),
      (MIGRATION, cut(r"                    models\.CheckConstraint\(\n                        condition=models\.Q\(\(\"actor_kind\", \"service\"\), \(\"company_id__isnull\", True\), _negated=True\),\n                        name=\"core_audit_events_service_company_check\",\n                    \),\n"))],
     [(SECURITY, [SAUDIT], {SAUDIT + "::test_the_checks_refuse_what_the_app_would_not_write[customer-line-without-a-company]"})]),
    # ── 커밋 ② 기록 지점 ──
    ("P7", 2, "login() 의 모르는 아이디 갈래가 넣은 username 을 target_label 로 넘김(note 에 typed 인자를 심음)",
     [(SVC_LOGIN, swap(NOTE_TAIL, "    audit_company_id: int | None = None,\n    typed: str | None = None,\n) -> None:")),
      (SVC_LOGIN, swap(LABEL, "target_label=typed if user is None else user.username,")),
      (SVC_LOGIN, swap("reason=reason, audit_company_id=company_id)", "reason=reason, audit_company_id=company_id, typed=username)"))],
     [(BUSINESS, [TLOGIN], {TLOGIN + "::test_every_miss_writes_one_failure_line_and_still_hashes_once[unknown-username]",
                            TLOGIN + "::test_every_miss_writes_one_failure_line_and_still_hashes_once[operator-unknown]",
                            TLOGIN + "::test_an_unknown_username_without_a_subdomain_is_set_on_the_sole_company"}),
      (SECURITY, [SAUDIT], {SECRET_SESSION})]),
    ("P8", 2, "바꾸기 갈래의 note 가 새 비밀번호를 감사 줄의 칸(target_label)에 실음(note 에 secret 인자를 심음)",
     [(SVC_LOGIN, swap(NOTE_TAIL, "    audit_company_id: int | None = None,\n    secret: str | None = None,\n) -> None:")),
      (SVC_LOGIN, swap(LABEL, "target_label=secret or (None if user is None else user.username),")),
      (ACT_PASSWORD, swap('services.note("password_changed", fresh, now=now)', 'services.note("password_changed", fresh, now=now, secret=new)'))],
     [(SECURITY, [SAUDIT], {SECRET_SESSION})]),
    ("P9", 2, "confirm_upload 의 감사 줄을 멱등 호출에서도 씀",
     [(SVC_DOCS, swap("    if moved:\n        record_event(", "    if True:\n        record_event("))],
     [(BUSINESS, [TDOCS], {TDOCS + "::test_the_move_writes_one_upload_line_and_a_second_confirm_writes_none"})]),
    ("P10", 2, "note() 의 record_event 호출을 지움",
     [(SVC_LOGIN, cut(r"    record_event\(\n        at=now,\n.*?\n    \)\n"))],
     [(BUSINESS, [TLOGIN], {TLOGIN + "::test_a_success_writes_one_line_of_the_person_on_their_company[service]",
                            TLOGIN + "::test_every_miss_writes_one_failure_line_and_still_hashes_once[wrong-password]"}),
      (SECURITY, [SAUDIT], {SAUDIT + "::test_a_failed_login_line_is_committed"})]),
    ("P11", 2, "revoke() 의 note(\"logout\") 을 지움",
     [(SVC_LOGIN, cut(r"    note\(\n        \"logout\",\n.*?\n    \)\n"))],
     [(BUSINESS, [TLOGIN], {TLOGIN + "::test_a_logout_writes_one_line_of_the_refresh_person[service]",
                            TLOGIN + "::test_a_logout_writes_one_line_of_the_refresh_person[admin]",
                            TLOGIN + "::test_every_note_name_has_an_action_and_every_action_is_one_of_nine"})]),
    ("P12", 2, "EVENT_ACTIONS 에서 user_updated 를 지움",
     [(SVC_LOGIN, swap('    "user_updated": "setting_change",\n', ""))],
     [(BUSINESS, [TLOGIN, TACCOUNT], {TLOGIN + "::test_every_note_name_has_an_action_and_every_action_is_one_of_nine",
                                      TACCOUNT + "::test_an_update_over_http_names_the_changed_fields_and_by_command_is_a_command_line"})]),
    ("P17", 2, "reset_password 의 감사 행위자를 늘 (command, None) 으로(HTTP 갈래도)",
     [(ACT_PASSWORD, swap("audit_actor_kind=kind, audit_actor_user_id=who", 'audit_actor_kind="command", audit_actor_user_id=None'))],
     [(BUSINESS, [TPASSWORD], {TPASSWORD + "::test_a_reset_over_http_is_the_operators_line_and_by_command_a_command_line[service]",
                               TPASSWORD + "::test_a_reset_over_http_is_the_operators_line_and_by_command_a_command_line[admin]"})]),
    # ── 커밋 ③ 조회 경로 ──
    ("P13", 3, "경로의 permitted(request, \"user_audit_list\") 를 지움",
     [(API_AUDIT, swap('    principal = permitted(request, "user_audit_list")\n', "    principal = request.auth\n"))],
     [(PURE, [TPERM], {TPERM + "::test_each_route_checks_its_own_operation_id_first",
                       TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"})]),
    ("P14", 3, "권한 표의 user_audit_list 를 CUSTOMER 로",
     [(PERMS, swap('    "user_audit_list": OPERATOR,\n', '    "user_audit_list": CUSTOMER,\n'))],
     [(PURE, [TPERM], {TPERM + "::test_the_table_is_these_needs"}),
      (SECURITY, [SAUDIT], {SAUDIT + "::test_a_customer_cannot_read_the_audit_lines"})]),
    ("P15", 3, "names_of 가 for_company 대신 고른 회사 조건 없이 고객사 사용자를 읽음(pk__in 만 — _base_manager)",
     [(SEL_USER, swap('User.for_company(company_id).filter(pk__in=customer_ids, kind="service")',
                      'User._base_manager.filter(pk__in=customer_ids, kind="service")'))],
     [(BUSINESS, [TAUDITAPI], {TAUDITAPI + "::test_names_are_the_current_ones_and_other_companies_people_stay_null"}),
      (PURE, [TSTATIC], {TSTATIC + "::test_product_code_does_not_reach_hidden_managers"})]),
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
