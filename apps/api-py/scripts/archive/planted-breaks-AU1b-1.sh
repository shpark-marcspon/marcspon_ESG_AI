#!/usr/bin/env bash
# 밴드 AU1b-1 의 심은 파손(발주서 band-handoffs/AU1b-order.md §3-2). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AU1b-1.sh [--boundary 1|2] [--with-containers] [--only P1,P4] [--optional]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다(층 단위 아님 —
# 경계 ① 8 = P1~P7·P12, 경계 ② 13 = P1~P13).
# 「참고」 층(P6 의 정적 규칙)은 무는지 적기만 하고 셈에 넣지 않는다.
# 경계 n 에는 커밋 n 까지의 P 만 심는다. 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」
# 으로 찍고 그 P 는 잡음으로 세지 않는다(조용한 초록 0 — section4 의 8 이 「안 돌림」 줄 0 과 정확한 n/n 을 함께 잰다).
# --optional: 경계 ② 에서 선택 P14(개정 2 n4)를 따로 심고 OPTIONAL_P14=<잡음|안 잡음> 한 줄(PLANTED 에 넣지 않는다).
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: AU1B1_OUT(기본: 워크트리 곁의 AU1b-1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AU1B1_OUT:-$(cd "$ROOT/.." && pwd)/AU1b-1.out}"
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
OPTIONAL = False
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2"):
        BOUNDARY, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--optional":
        OPTIONAL, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


SEL = Path("esgapi/core/service/selectors/audit.py")
API = Path("esgapi/user/service/apis/audit.py")
PERMS = Path("esgapi/core/permissions.py")
TAPI = "esgapi/user/tests/service/apis/test_audit.py"
TSEL = "esgapi/core/tests/service/selectors/test_audit.py"
TPERM = "esgapi/core/tests/test_permissions.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
TSCOPE = "esgapi/core/tests/test_selector_scope.py"
SAUDIT = "tests/security/test_audit.py"
FINDS = TAPI + "::test_q_finds_people_by_current_name_and_username_and_lines_by_target_label"
AFTER2 = BOUNDARY >= 2

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)
INFO = "참고"  # 빨개지기를 기대하지 않는다 — 무는지 적기만

Q_BOTH = (
    "        matched = Q(target_label__icontains=q)\n"
    "        if q_actor_ids:\n"
    "            matched |= Q(actor_user_id__in=q_actor_ids)\n"
)
ROUTE_Q_ARGS = "        q=q,\n        q_actor_ids=q_actor_ids,\n    )\n"
SEARCH_ADMINS = '            {actor.actor_user_id for actor in actors if actor.actor_kind == "admin"},\n'
SEARCH_MATCH = "        q_actor_ids = matching_ids(searched, q)\n"
P6_EVERYWHERE = (
    "        from esgapi.organization.models import Company  # 심은 파손: 시험 고정물의 두 회사를 다 연다\n\n"
    "        for other in (Company.by_subdomain(\"tenant-a\"), Company.by_subdomain(\"tenant-b\")):\n"
    "            if other is not None:\n"
    "                searched = {**selectors.names_of(\n"
    "                    other.pk,\n"
    "                    {actor.actor_user_id for actor in actors if actor.actor_kind == \"service\"},\n"
    "                    set(),\n"
    "                ), **searched}\n"
    + SEARCH_MATCH
)
P3_AFTER_PAGE = (
    "        q=None,\n    )\n"
    "    if q is not None and not isinstance(page, audit_selectors.AuditForbidden):  # 심은 파손: 쪽을 자른 뒤 거름\n"
    "        needle = q.casefold()\n"
    "        page = audit_selectors.AuditPage(\n"
    "            count=page.count,\n"
    "            rows=tuple(\n"
    "                row for row in page.rows\n"
    "                if row.actor_user_id in q_actor_ids or needle in (row.target_label or \"\").casefold()\n"
    "            ),\n"
    "        )\n"
)
DATE_TO = '            le=DATE_CEILING,  # pyright: ignore[reportArgumentType]\n            description="KST 그날 끝까지(포함).'
VISIBLE = "    return AuditEventRow.for_company(company_id) | AuditEventRow.operator_rows()\n"
ACTORS_CHECK = '    if not is_allowed("user_audit_actors", kind=actor_kind):\n        return AuditForbidden()\n    return _actors(company_id)\n'
SEARCH_CHECK = (
    '    """GET /audit-logs 의 q 길이 이름을 풀 사람들. 그 동작(user_audit_list)의 칸을 읽는다 — 운영 관리자만(첫 줄)."""\n'
    '    if not is_allowed("user_audit_list", kind=actor_kind):\n'
)

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음, 참고인가)])
PLANTS = [
    ("P1", 1, "q 갈래에서 Q(target_label__icontains=q) 를 지움(사람만)",
     [(SEL, swap(Q_BOTH, "        matched = Q(actor_user_id__in=q_actor_ids)\n"))],
     [(BUSINESS, [TAPI], {FINDS, TAPI + "::test_q_keeps_target_label_matches_when_no_person_matches"}, False)]),
    ("P2", 1, "q 갈래에서 actor_user_id__in 을 지움(대상 글자만)",
     [(SEL, swap(Q_BOTH, "        matched = Q(target_label__icontains=q)\n"))],
     [(BUSINESS, [TAPI], {FINDS}, False)]),
    ("P3", 1, "경로가 q 를 쪽을 자른 뒤 파이썬으로 거름(처분 ① (다) — count 는 거르기 전)",
     [(API, swap(ROUTE_Q_ARGS, P3_AFTER_PAGE))],
     [(BUSINESS, [TAPI], {FINDS}, False)]),
    ("P4", 1, "경로의 q 길에서 names_of 에 운영 관리자 id 집합을 비워 넘김",
     [(API, swap(SEARCH_ADMINS, "            set(),\n"))],
     [(BUSINESS, [TAPI], {FINDS}, False)]),
    ("P5", 1, "dateTo 의 le= 를 지움",
     [(API, swap(DATE_TO, '            description="KST 그날 끝까지(포함).'))],
     [(BUSINESS, [TAPI], {TAPI + "::test_a_query_out_of_shape_is_422[dateTo=9999-12-31]",
                          TAPI + "::test_dates_are_bounded_2000_to_2999_and_outside_is_a_validation_error"}, False)]),
    ("P6", 1, "경로의 q 길이 고객사 이름을 모든 회사에서 풂(고정물의 두 회사 — 터지지 않는 꼴)",
     [(API, swap(SEARCH_MATCH, P6_EVERYWHERE))],
     [(BUSINESS, [TAPI], {TAPI + "::test_q_never_resolves_a_person_of_another_company"}, False),
      (SECURITY, [SAUDIT], {SAUDIT + "::test_q_does_not_cross_the_company_line"}, False),
      (PURE, [TSTATIC, TSCOPE], set(), True)]),
    ("P7", 1, "icontains 를 iregex 로",
     [(SEL, swap("Q(target_label__icontains=q)", "Q(target_label__iregex=q)"))],
     [(BUSINESS, [TAPI], {TAPI + "::test_q_takes_wildcard_letters_as_letters[.]"}, False)]),
    ("P12", 1, "_visible 의 | AuditEventRow.operator_rows() 를 지움(회사 없는 줄 안 봄)",
     [(SEL, swap(VISIBLE, "    return AuditEventRow.for_company(company_id)\n"))],
     [(BUSINESS, [TAPI, TSEL], {
         TAPI + "::test_an_operator_reads_the_chosen_company_and_the_companyless_lines_newest_first",
         TSEL + "::test_the_chosen_company_and_the_lines_without_a_company_are_seen_but_not_another_company",
         *([TAPI + "::test_actors_list_the_people_of_the_visible_lines_including_operators"] if AFTER2 else []),
     }, False)]),
    # ── 커밋 ② 행위자 목록 ──
    ("P8", 2, "권한 표의 user_audit_actors 를 CUSTOMER 로",
     [(PERMS, swap('    "user_audit_actors": OPERATOR,\n', '    "user_audit_actors": CUSTOMER,\n'))],
     [(PURE, [TPERM], {TPERM + "::test_the_table_is_these_needs"}, False),
      (SECURITY, [SAUDIT], {SAUDIT + "::test_a_customer_cannot_read_the_actor_list"}, False)]),
    ("P9", 2, "list_audit_actors 첫 줄 권한 검사를 지움",
     [(SEL, swap(ACTORS_CHECK, "    return _actors(company_id)\n"))],
     [(BUSINESS, [TSEL], {TSEL + "::test_list_audit_actors_reads_the_cell_of_user_audit_actors"}, False),
      (PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"}, False)]),
    ("P10", 2, "경로의 permitted(request, \"user_audit_actors\") 를 지움",
     [(API, swap('    principal = permitted(request, "user_audit_actors")\n', "    principal = request.auth\n"))],
     [(PURE, [TPERM], {TPERM + "::test_each_route_checks_its_own_operation_id_first"}, False)]),
    ("P11", 2, "행위자 함수에서 actor_user_id__isnull=False 를 지움",
     [(SEL, swap("        .filter(actor_user_id__isnull=False)\n", ""))],
     [(BUSINESS, [TAPI, TSEL], {TAPI + "::test_actors_list_the_people_of_the_visible_lines_including_operators",
                                TSEL + "::test_actors_are_the_distinct_people_of_the_visible_lines"}, False)]),
    ("P13", 2, "list_audit_actors 의 첫 줄이 user_audit_list 칸을 읽음",
     [(SEL, swap(ACTORS_CHECK, ACTORS_CHECK.replace('"user_audit_actors"', '"user_audit_list"')))],
     [(BUSINESS, [TSEL], {TSEL + "::test_list_audit_actors_reads_the_cell_of_user_audit_actors"}, False)]),
]
OPTIONAL_PLANTS = [
    ("P14", 2, "audit_actors_for_search 가 user_audit_actors 칸을 읽음(선택 — 개정 2 n4)",
     [(SEL, swap(SEARCH_CHECK, SEARCH_CHECK.replace('is_allowed("user_audit_list"', 'is_allowed("user_audit_actors"')))],
     [(BUSINESS, [TSEL], {TSEL + "::test_actors_for_search_read_the_cell_of_user_audit_list"}, False)]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
OPTIONAL_PLANTS = [p for p in OPTIONAL_PLANTS if OPTIONAL and p[1] <= BOUNDARY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _name, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


ALL = PLANTS + OPTIONAL_PLANTS
files = sorted({f for p in ALL for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in ALL:
    for layer, targets, _, _info in p[4]:
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
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
        for layer, targets, expected, info in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                skipped = True
                continue
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            if info:
                print(f"{label} {INFO}: EXIT={code} 빨강 {len(failed)} — {' '.join(targets)}")
                for node in sorted(failed):
                    print(f"    FAILED {node}")
                continue
            hit = code != 0 and expected <= failed
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

for number, _commit, what, edits, checks in OPTIONAL_PLANTS:
    result = plant_and_check(number, what, edits, checks)
    print(f"OPTIONAL_{number}={'잡음' if result else '안 돌림' if result is None else '안 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
