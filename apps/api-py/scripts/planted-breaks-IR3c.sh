#!/usr/bin/env bash
# 밴드 IR3c 의 심은 파손(발주서 band-handoffs/IR3c-order.md §3-5, + 러너 몫 P18). 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — try/finally, SIGTERM·SIGINT 도 finally 를 지난다). 사용:
#   apps/api-py/scripts/planted-breaks-IR3c.sh [--commit <n>] [--with-containers] [--only P1,P4]
#   --commit n 은 경계 n 까지의 몫만(① P1~P4·P18, ② +P5~P15, ③ +P16·P17). 기본 3.
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무·보안 층(Postgres)은 --with-containers 일 때만 —
# 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다. 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: IR3c_OUT(기본: 워크트리 곁의 IR3c.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IR3c_OUT:-$(cd "$ROOT/.." && pwd)/IR3c.out}"
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


DIGEST = Path("esgapi/materiality/outputs/digest.py")
IRO = Path("esgapi/materiality/flows/iro_155.py")
TD = "esgapi/materiality/tests/outputs/test_digest.py"
TI = "esgapi/materiality/tests/flows/test_iro_155.py"
COUNTS = TD + "::test_the_two_counts_are_the_hand_values"
ROWS = TD + "::test_the_counts_are_the_final_workbook_rows"
ONE_RUN = TI + "::test_one_run_calls_part1_then_part2_and_returns_one_v2_result"
DECLARED = TI + "::test_the_flow_declaration"
ACTION = Path("esgapi/materiality/service/actions/runs.py")
ROUTE = Path("esgapi/materiality/service/apis/materiality.py")
LIST_SHAPES = Path("esgapi/materiality/contracts/run_list_shapes.py")
PERM = Path("esgapi/core/permissions.py")
TL = "esgapi/materiality/tests/service/apis/test_materiality_runs.py"
TC = "esgapi/materiality/tests/contracts/test_run_list_shapes.py"
TO = "esgapi/materiality/tests/service/apis/test_materiality_operator.py"
TP = "esgapi/core/tests/test_permissions.py"
L_ROWS = TL + "::test_the_rows_are_my_company_materiality_runs_newest_first"
L_MARK = TL + "::test_the_rows_carry_no_topic_names_descriptions_or_other_option_fields"
L_SHAPE = TL + "::test_a_value_out_of_shape_is_null_and_the_row_stays"
L_STATUS = TL + "::test_each_status_fills_its_own_fields"
L_DONE_STEP = TL + "::test_a_failed_step_on_a_done_run_and_a_running_step_on_a_failed_run_are_not_shown"
L_FAILED_DIGEST = TL + "::test_a_digest_on_a_failed_run_is_not_shown"
L_FILTER = TL + "::test_the_status_filter_takes_several_values"
L_422 = TL + "::test_a_bad_query_is_422"
L_MINE = TL + "::test_mine_shows_only_the_runs_i_made"
O_LIST = TO + "::test_the_operator_lists_the_work_companys_materiality_runs_like_the_customer"
PATHS = Path("tests/security/test_tenant_paths.py")
SM = "tests/security/test_materiality.py"
STP = "tests/security/test_tenant_paths.py"
S_LIST = SM + "::test_another_companys_list_carries_none_of_its_runs"
UNSCOPED = (
    "    company_id = getattr(__import__('esgapi.runs.models', fromlist=['RunRow']).RunRow.unscoped"
    ".filter(module=MODULE).order_by('id').first(), 'company_id', company_id)\n"
)
PAGE_CALL = "    page = run_selectors.run_page(\n"


def swap_all(old: str, new: str, times: int) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new) if text.count(old) == times else None

    return plant


def chain(*plants: Callable[[str], str | None]) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        for one in plants:
            got = one(text)
            if got is None:
                return None
            text = got
        return text

    return plant


def AT_3(checks):  # noqa: N802 — 경계 ③ 에서 생기는 보안 시험은 그때부터 겨눈다
    return checks if COMMIT >= 3 else []


# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    (1, "P1", "pathwayRows 를 재무(financial) rows 로 셈",
     [(DIGEST, swap('_rows(result, "pathway")', '_rows(result, "financial")'))],
     [(PURE, [TD], {f"{COUNTS}[pathway-failed-two-subtopics]", f"{ROWS}[pathway-failed-two-subtopics]"})]),
    (1, "P2", "part2 not_run 이면 두 수 0",
     [(DIGEST, swap("impactRows=None, pathwayRows=None", "impactRows=0, pathwayRows=0"))],
     [(PURE, [TD], {f"{COUNTS}[part2-not-run]", f"{ROWS}[part2-not-run]"})]),
    (1, "P3", "result_shapes 에 digest 빠뜨림",
     [(IRO, swap("result_shapes=(shapes.RESULT_SHAPE_V2, DIGEST_SHAPE),", "result_shapes=(shapes.RESULT_SHAPE_V2,),"))],
     [(PURE, [TI], {DECLARED})]),
    (1, "P4", "digest 가 result@2 에 칸을 더함",
     [(IRO, swap('data={"results": [result, dict(digest(result))]}',
                 'data={"results": [{**result, "digest": dict(digest(result))}, dict(digest(result))]}'))],
     [(PURE, [TI], {ONE_RUN})]),
    (1, "P18", "러너 몫: 첫 토픽만 셈(토픽 둘 이상의 줄을 놓침)",
     [(DIGEST, swap('for topic in result["part2"]["topics"]\n', 'for topic in result["part2"]["topics"][:1]\n'))],
     [(PURE, [TD], {f"{COUNTS}[all-done]", f"{ROWS}[all-done]"})]),
    (2, "P5", "목록의 module 거름 뺌(다른 모듈 실행이 섞임)",
     [(ACTION, swap("        module=MODULE,\n", "        module=None,\n"))],
     [(BUSINESS, [TL], {L_ROWS})]),
    (2, "P6", "줄에 input.topics 째(기업명 칸에 토픽 목록 글)",
     [(ACTION, swap('"companyName": _company(given),', '"companyName": str(given.get("topics")),'))],
     [(BUSINESS, [TL], {L_ROWS, L_MARK})]),
    (2, "P7", "limit 의 le=20 뺌",
     [(ROUTE, swap("    limit: int = Field(default=20, ge=1, le=20)", "    limit: int = Field(default=20, ge=1)"))],
     [(BUSINESS, [TL], {f"{L_422}[?limit=21]"})]),
    (2, "P8", "MaterialityRunIndustry 이름을 MaterialityIndustry 로(기준 컴포넌트와 겹침)",
     [(LIST_SHAPES, chain(swap_all("MaterialityRunIndustry", "MaterialityIndustry", 2),
                          lambda t: t + "\nMaterialityRunIndustry = MaterialityIndustry\n"))],
     [(PURE, [TC], {TC + "::test_the_new_component_names_are_these_and_meet_no_other_shape_name"})]),
    (2, "P9", "권한 칸 COMPANY → CUSTOMER",
     [(PERM, swap('    "materiality_runs_list": COMPANY,', '    "materiality_runs_list": CUSTOMER,'))],
     [(PURE, [TP, TC], {TP + "::test_the_table_is_these_needs", TC + "::test_the_list_is_company_work"}),
      (BUSINESS, [TO], {O_LIST})]),
    (2, "P10", "statuses 를 run_page 에 안 넘김",
     [(ACTION, swap("        statuses=statuses,\n", "        statuses=None,\n"))],
     [(BUSINESS, [TL], {L_FILTER})]),
    (2, "P11", "mine 이 created_by_user_id 를 안 넘김",
     [(ACTION, swap("created_by_user_id=user_id if mine else None,", "created_by_user_id=None,"))],
     [(BUSINESS, [TL], {L_MINE}), (BUSINESS, [TO], {O_LIST})]),
    (2, "P12", "currentStep 을 done 에도(단계도 done 실행까지 읽음)",
     [(ACTION, chain(swap('[r.id for r in found if r.status == "processing"]', "[r.id for r in found]"),
                     swap('current.get(run.id) if run.status == "processing" else None', "current.get(run.id)")))],
     [(BUSINESS, [TL], {L_DONE_STEP})]),
    (2, "P13", "people_of 빼고 id 글자",
     [(ACTION, swap('"name": known[1] if known is not None and known[1].strip() else UNKNOWN_USER',
                    '"name": str(user)'))],
     [(BUSINESS, [TL], {L_ROWS})]),
    (2, "P14", "산업 원소 꼴 검사 뺌(꼴 밖 행이 500)",
     [(ACTION, swap("        if not isinstance(standard, str) or not isinstance(name, str):\n",
                    "        if False:\n"))],
     [(BUSINESS, [TL], {f"{L_SHAPE}[industry-standard-number]", f"{L_SHAPE}[industry-without-name]"})]),
    (2, "P15", "두 수를 failed 에도",
     [(ACTION, chain(swap('[r.id for r in found if r.status == "done"]', "[r.id for r in found]"),
                     swap('digests.get(run.id) if run.status == "done" else None', "digests.get(run.id)")))],
     [(BUSINESS, [TL], {L_FAILED_DIGEST})]),
    (3, "P16", "회사 조건 없는 읽기(가장 먼저 만든 중대성평가 실행의 회사로 갈아 읽음 — 시험 안 가짜)",
     [(ACTION, swap(PAGE_CALL, UNSCOPED + PAGE_CALL))],
     [(SECURITY, [SM], {f"{S_LIST}[session]", f"{S_LIST}[bearer]"})]),
    (3, "P17", "materiality_list 분류를 contract_only 로",
     [(PATHS, swap('    ("GET", "/materiality/runs"): "materiality_list",', '    ("GET", "/materiality/runs"): "contract_only",'))],
     [(SECURITY, [STP], {STP + "::test_a_contract_only_route_is_501_and_writes_nothing[GET /materiality/runs]"})]),
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
