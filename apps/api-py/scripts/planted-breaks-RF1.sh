#!/usr/bin/env bash
# 밴드 RF1 의 심은 파손(발주서 band-handoffs/RF1-order.md §3 + MARC-TICK-241 노트의 9f 조건 (바)). AD4D 의 꼴 그대로:
# 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지
# 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-RF1.sh [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 — 13(P1~P12,
# P7 은 a·b 둘). 경계는 하나다(--boundary 는 받지 않는다).
# 회사 경계 심음(P2·P12 — 9f 의 ⓘ 와 묶음)은 예외 없이 터지지 않는 꼴이다 — 업무·보안 층의 잡음은 **단언**으로 빨개진
# 것만 센다. 빨간 노드의 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다.
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: RF1_OUT(기본: 워크트리 곁의 RF1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${RF1_OUT:-$(cd "$ROOT/.." && pwd)/RF1.out}"
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
BOUNDARY = 1
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


OPSEL = Path("esgapi/runs/service/selectors/operator.py")
ROUTE = Path("esgapi/user/service/apis/run_logs.py")
FILES = Path("esgapi/runs/service/services/files.py")
RUNS_API = Path("esgapi/runs/service/apis/runs.py")
TPERM = "esgapi/core/tests/test_permissions.py"
TOP = "esgapi/runs/tests/service/selectors/test_operator.py"
TFILES = "esgapi/runs/tests/service/services/test_files.py"
TRUNS = "esgapi/runs/tests/service/apis/test_runs.py"
TRUNSOP = "esgapi/runs/tests/service/apis/test_runs_operator.py"
TAPI = "esgapi/user/tests/service/apis/test_run_logs.py"
SRUN = "tests/security/test_run_logs.py"
T1 = TAPI + "::test_the_operator_gets_the_output_file_bytes_and_one_audit_line"
T2 = {TAPI + f"::test_a_run_of_any_module_gives_its_file_unlike_the_customer_path[{m}]" for m in ("dataverify", "inventory")}
T4 = TAPI + "::test_a_missing_or_another_companys_run_is_the_same_404_on_a_file"
T5 = TAPI + "::test_an_unknown_name_a_step_file_or_a_missing_object_is_run_file_not_found"
T6 = TAPI + "::test_the_store_refusals_are_the_three_503s_without_an_audit_line"
S_I = SRUN + "::test_choosing_b_gets_404_on_a_file_of_a_run_of_a_like_a_missing_id"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

EXISTS = "    if not _runs(company_id).filter(id=run_id).exists():\n"
OUTPUT = "    found = run_selectors.output_file(company_id=company_id, run_id=run_id, name=name)\n"
AUDIT = (
    "    record_event(\n"
    "        at=now(),\n"
    "        company_id=company_id,\n"
    "        actor_kind=principal.kind,\n"
    "        actor_user_id=int(principal.user_id),\n"
    "        action=\"download\",\n"
    "        event=\"run_file_downloaded\",\n"
    "        result=\"success\",\n"
    "        target_kind=\"run\",\n"
    "        target_id=run_id,\n"
    "        target_label=found.name,\n"
    "    )\n"
)
READ = "    data = file_services.output_bytes(found)  # 저장소 없음·거절·닿지 못함은 503 셋으로 던진다\n"
CHOSEN = '    principal = permitted(request, "user_run_log_file_get")\n    company_id = chosen_company(companyId, company_ports())\n'
IMPORT = "from esgapi.core.auth.bearer import access_token_auth, permitted\n"
IMPORT_OF = "from esgapi.core.auth.bearer import access_token_auth, company_of, permitted\n"
DISPOSITION = "    response[\"Content-Disposition\"] = f'attachment; filename=\"{found.name}\"'  # 이름은 [A-Za-z0-9._-] 뿐(표의 CHECK)\n"

# (번호, 경계, 설명, [(파일, 심는 함수)], [(경계, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", 1, "operator_run_file 첫 줄 권한 검사를 지움",
     [(OPSEL, swap('    if not is_allowed("user_run_log_file_get", kind=actor_kind):\n        return RunLogForbidden()\n', ""))],
     [(1, PURE, [TPERM], {TPERM + "::test_the_user_admin_routes_also_reach_the_table_inside"}),
      (1, BUSINESS, [TOP], {TOP + "::test_the_file_is_forbidden_to_a_customer_kind_before_anything_is_read"})]),
    ("P2", 1, "실행 있음 검사를 _runs 대신 RunRow.unscoped 로(회사 거름 없음 — 예외 없음)",
     [(OPSEL, swap(EXISTS, EXISTS.replace("_runs(company_id).filter(id=run_id)", "RunRow.unscoped.filter(id=run_id)")))],
     [(1, BUSINESS, [TAPI], {T4}),
      (1, BUSINESS, [TOP], {TOP + "::test_a_missing_or_another_companys_run_has_no_file"}),
      (1, SECURITY, [SRUN], {S_I})]),
    ("P3", 1, "output_file 대신 run_files 에서 이름으로 찾음(단계 산출 파일도 냄)",
     [(OPSEL, swap(OUTPUT, "    found = next((f for f in run_selectors.run_files(company_id=company_id, run_id=run_id)"
                           " if f.name == name), None)\n"))],
     [(1, BUSINESS, [TAPI], {T5}),
      (1, BUSINESS, [TOP], {TOP + "::test_a_step_files_name_or_an_unknown_name_is_missing"})]),
    ("P4", 1, "경로가 record_event 를 부르지 않음",
     [(ROUTE, swap(AUDIT, ""))],
     [(1, BUSINESS, [TAPI], {T1}),
      (1, SECURITY, [SRUN], {S_I})]),
    ("P5", 1, "record_event 를 output_bytes 앞으로(실패에도 감사)",
     [(ROUTE, swap(AUDIT, "")), (ROUTE, swap(READ, AUDIT + READ))],
     [(1, BUSINESS, [TAPI], {T5, T6})]),
    ("P6", 1, "selector 가 module 을 읽어 OPERATOR_RUN_MODULES 로 거름",
     [(OPSEL, swap(EXISTS, EXISTS.replace("filter(id=run_id)", 'filter(id=run_id, module__in=("greenwash", "translation"))')))],
     [(1, BUSINESS, [TAPI], T2)]),
    ("P7a", 1, "nosniff 줄을 지움",
     [(ROUTE, swap(DISPOSITION + '    response["X-Content-Type-Options"] = "nosniff"\n', DISPOSITION))],
     [(1, BUSINESS, [TAPI], {T1})]),
    ("P7b", 1, "no-store 줄을 지움",
     [(ROUTE, swap('    response["Cache-Control"] = "no-store"  # 회사 자료(내보내기와 같다)\n', ""))],
     [(1, BUSINESS, [TAPI], {T1})]),
    ("P8", 1, "output_bytes 의 StorageDenied 를 storage_unavailable 로",
     [(FILES, swap('"storage_denied", "저장소가 요청을 거절했다"', '"storage_unavailable", "저장소가 요청을 거절했다"'))],
     [(1, PURE, [TFILES], {TFILES + "::test_a_denial_is_storage_denied"}),
      (1, BUSINESS, [TAPI], {T6}),
      (1, BUSINESS, [TRUNS], {TRUNS + "::test_download_when_the_store_refuses_or_is_missing_is_its_503_without_an_audit_line"})]),
    ("P9", 1, "runs_file_get 의 _visible 검사를 지움",
     [(RUNS_API, swap('        if run is None or not _visible(principal, run):\n            raise _not_found("그런 파일이 없다")\n',
                      '        if run is None:\n            raise _not_found("그런 파일이 없다")\n'))],
     [(1, BUSINESS, [TRUNSOP], {TRUNSOP + "::test_the_operator_gets_404_on_a_file_of_another_modules_run"}),
      (1, BUSINESS, [TAPI], T2)]),
    ("P10", 1, "RunFileMissing 을 run_not_found 로",
     [(ROUTE, swap('    if isinstance(found, operator_selectors.RunFileMissing):\n'
                   '        raise ApplicationError("not_found", "run_file_not_found", RUN_FILE_NOT_FOUND)\n',
                   '    if isinstance(found, operator_selectors.RunFileMissing):\n'
                   '        raise ApplicationError("not_found", "run_not_found", RUN_NOT_FOUND)\n'))],
     [(1, BUSINESS, [TAPI], {T5})]),
    ("P11", 1, "감사 company_id 를 company_of(principal)(작업 회사)로",
     [(ROUTE, swap(AUDIT, AUDIT.replace("        company_id=company_id,\n", "        company_id=company_of(principal),\n"))),
      (ROUTE, swap(IMPORT, IMPORT_OF))],
     [(1, BUSINESS, [TAPI], {T1})]),
    ("P12", 1, "chosen_company 대신 경로가 company_of(작업 회사)",
     [(ROUTE, swap(CHOSEN, CHOSEN.replace("chosen_company(companyId, company_ports())", "company_of(principal)"))),
      (ROUTE, swap(IMPORT, IMPORT_OF))],
     [(1, BUSINESS, [TAPI], {T1}),
      (1, SECURITY, [SRUN], {S_I})]),
]
PLANTS = [p for p in PLANTS if p[1] <= BOUNDARY and (ONLY is None or p[0] in ONLY)]
PLANTS = [(n, c, w, e, [k for k in checks if k[0] <= BOUNDARY]) for n, c, w, e, checks in PLANTS]
BOUNDARY_GUARDED = {"P2", "P12"}  # 회사 경계 심음 — 예외로 빨개지면 무효
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
