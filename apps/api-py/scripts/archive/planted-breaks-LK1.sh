#!/usr/bin/env bash
# 밴드 LK1 의 심은 파손(발주서 band-handoffs/LK1-order.md §3 + MARC-TICK-259 노트의 73 조건 (다)). IK1 의 꼴 그대로:
# 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지
# 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-LK1.sh [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). PLANTED 는 P 단위로 센다 — 14(§3 의
# P1~P14. 73 조건 (다): 보안 ⓚ = P4(묶음 셈의 회사 조건 빼기), 보안 ⓙ = P14(부분 색인을 유일로)). 경계는 하나다.
# 범위 심음(P3·P4 — 보안 ⓚ 와 묶음)은 예외 없이 터지지 않는 꼴이다 — 업무·보안 층의 잡음은 **단언**으로 빨개진 것만
# 센다. 빨간 노드의 로그에 예외(UnscopedQueryError·Traceback 의 500)가 있으면 「예외로 빨강」을 찍고 못 잡음으로 센다.
# 업무·보안 층(Postgres 가 필요)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 P 는 잡음으로 세지 않는다.
# 시험 DB 는 돌 때마다 마이그레이션으로 새로 짓는다(--reuse-db 없음) — P14 는 0004 를 고친다.
# 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=.
# 산출물: LK1_OUT(기본: 워크트리 곁의 LK1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${LK1_OUT:-$(cd "$ROOT/.." && pwd)/LK1.out}"
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


def chain(*plants: Callable[[str], str | None]) -> Callable[[str], str | None]:
    """한 파일에 여러 자리를 차례로 심는다(하나라도 안 맞으면 None)."""

    def plant(text: str) -> str | None:
        for one in plants:
            found = one(text)
            if found is None:
                return None
            text = found
        return text

    return plant


ACTIONS = Path("esgapi/runs/service/actions/runs.py")
API = Path("esgapi/runs/service/apis/runs.py")
CALC = Path("esgapi/runs/calc/idempotency.py")
SCHEMAS = Path("esgapi/runs/service/schemas/runs.py")
OPSEL = Path("esgapi/runs/service/selectors/operator.py")
RUN_LOGS = Path("esgapi/user/service/apis/run_logs.py")
MIGRATION = Path("esgapi/runs/migrations/0004_run_launch_key.py")
TL = "esgapi/runs/tests/service/apis/test_runs_launch.py"
TCALC = "esgapi/runs/tests/calc/test_idempotency.py"
TSEL = "esgapi/runs/tests/service/selectors/test_operator.py"
TVAL = "esgapi/runs/tests/test_models_values.py"
TRL = "esgapi/user/tests/service/apis/test_run_logs_launch.py"
TSTATIC = "esgapi/core/tests/isolation/test_static_rules.py"
SRUN = "tests/security/test_runs.py"
SLOGS = "tests/security/test_run_logs.py"

L4 = TL + "::test_a_retry_cannot_join_the_original_launch_and_a_new_key_keeps_it_apart"
L5 = TL + "::test_idempotency_counts_the_launch_key_in_the_body"
L2 = TL + "::test_a_malformed_launch_key_is_422_and_writes_nothing"
R7 = TRL + "::test_a_launch_of_three_shows_first_index_and_size"
R8 = TRL + "::test_the_launch_cells_ignore_filters_paging_and_hold_in_the_detail"
R9P = TRL + "::test_another_person_with_the_same_key_is_another_launch"
R9C = TRL + "::test_the_launch_is_counted_inside_the_chosen_company"
R10 = TRL + "::test_a_key_on_the_page_costs_one_query_and_the_export_none"
R11 = TRL + "::test_resumed_from_is_on_the_line_and_the_detail"
SEL_ORDER = TSEL + "::test_a_launch_is_counted_in_id_order_per_person_and_key"
SEL_FILTER = TSEL + "::test_launch_cells_ignore_filters_and_paging"
SEL_COMPANY = TSEL + "::test_launch_cells_stay_in_the_chosen_company"
SEL_QUERIES = TSEL + "::test_the_launch_query_is_one_when_a_key_is_on_the_page_and_zero_otherwise"
C_FIXED = TCALC + "::test_without_a_launch_key_the_bytes_are_the_ik1_ones"
C_SIXTH = TCALC + "::test_a_launch_key_is_appended_sixth_and_counts"
V_LAUNCH = TVAL + "::test_the_launch_key_column_and_index_are_the_0004_ones"
S_J = SRUN + "::test_a_launch_key_is_not_unique_and_two_companies_keep_their_own_rows"
S_K = SLOGS + "::test_a_launch_of_a_does_not_count_into_b"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

SOURCE = "        _runs(company_id)\n        .filter(launch_key__in=sorted(keys))\n"
ORDER = '        .order_by("id")\n        .values_list("created_by_user_id", "launch_key", "id")\n'
QUERY = (
    "    for person, key, run_id in (\n"
    + SOURCE
    + ORDER
    + "    ):\n"
)
GROUP = "        members.setdefault((person, key), []).append(run_id)\n"
SIZE = '            launch_size=launched[row["id"]][2] if row["id"] in launched else None,\n'
SHA = '    if launch_key is not None:\n        canonical["launchKey"] = launch_key\n'
REUSED = (
    "        if launch_key is not None and previous.launch_key == launch_key:\n"
    "            return LaunchKeyReused()  # 다시 하기가 원 묶음에 섞이지 않게(머리말 — 쓰기 0)\n"
)
ON_COMMIT = "    # robust=True: 갈고리가 던져도 커밋은 이미 끝났고 요청은 201 이다(core/resources/queue.py 의 머리말)\n"
LATE_REUSED = (
    "    if launch_key is not None and resume_from is not None and (\n"
    "        RunRow.for_company(company_id).filter(pk=resume_from, launch_key=launch_key).exists()\n"
    "    ):\n"
    "        return LaunchKeyReused()\n"
)
INDEX = 'migrations.AddIndex(\n            model_name="runrow",\n            index=models.Index(\n'
UNIQUE = 'migrations.AddConstraint(\n            model_name="runrow",\n            constraint=models.UniqueConstraint(\n'

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", "묶음 셈을 거른 줄 안에서(_filtered 위 창 함수와 같은 셈 — 쪽의 거른 QuerySet 을 원천으로)",
     [(OPSEL, chain(
         swap("def _launches(company_id: int, rows: list[dict[str, Any]]) -> dict[int, tuple[int, int, int]]:",
              "def _launches(company_id: int, rows: list[dict[str, Any]], source: Any = None) -> dict[int, tuple[int, int, int]]:"),
         swap(SOURCE, SOURCE.replace("_runs(company_id)", "(_runs(company_id) if source is None else source)")),
         swap("    company_id: int, rows: Iterable[dict[str, Any]], *, launches: bool = True\n",
              "    company_id: int, rows: Iterable[dict[str, Any]], *, launches: bool = True, source: Any = None\n"),
         swap("_launches(company_id, found) if launches", "_launches(company_id, found, source) if launches"),
         swap("runs=_operator_runs(company_id, page))", "runs=_operator_runs(company_id, page, source=rows))"),
     ))],
     [(BUSINESS, [TRL, TSEL], {R8, SEL_FILTER})]),
    ("P2", "묶음 셈을 쪽에 실린 줄만으로(따로 쿼리 0)",
     [(OPSEL, swap(QUERY, "    for person, key, run_id in sorted(\n"
                          "        ((r[\"created_by_user_id\"], r[\"launch_key\"], r[\"id\"]) for r in rows if r[\"launch_key\"]),\n"
                          "        key=lambda t: t[2],\n"
                          "    ):\n"))],
     [(BUSINESS, [TRL, TSEL], {R8, SEL_FILTER})]),
    ("P3", "묶음 가름에서 created_by_user_id 를 뺌",
     [(OPSEL, swap(GROUP, GROUP.replace("(person, key)", "(0, key)")))],
     [(BUSINESS, [TRL, TSEL], {R9P, SEL_ORDER})]),
    ("P4", "_launches 를 RunRow.unscoped 로(회사 조건 빠짐 — 73 조건 (다) ⓚ)",
     [(OPSEL, swap(SOURCE, SOURCE.replace("_runs(company_id)", "RunRow.unscoped")))],
     [(PURE, [TSTATIC], {TSTATIC + "::test_product_code_does_not_use_unscoped"}),  # test_selector_scope 는 못 잡는다
      (BUSINESS, [TRL, TSEL], {R9C, SEL_COMPANY}),
      (SECURITY, [SLOGS], {S_K})]),
    ("P5", "차례를 id 내림으로",
     [(OPSEL, swap(ORDER, ORDER.replace('.order_by("id")', '.order_by("-id")')))],
     [(BUSINESS, [TRL, TSEL], {R7, SEL_ORDER})]),
    ("P6", "열쇠 없는 줄 launchSize 를 1 로",
     [(OPSEL, swap(SIZE, SIZE.replace("else None", "else 1")))],
     [(BUSINESS, [TRL, TSEL], {R7, SEL_ORDER})]),
    ("P7", "sha 에서 launch_key 를 뺌",
     [(CALC, swap(SHA, ""))],
     [(PURE, [TCALC], {C_SIXTH}),
      (BUSINESS, [TL], {L5})]),
    ("P8", "sha 에 늘 \"launchKey\": null",
     [(CALC, swap(SHA, '    canonical["launchKey"] = launch_key\n'))],
     [(PURE, [TCALC], {C_FIXED})]),
    ("P9", "이어 돌기 같은 열쇠 검사를 지움",
     [(ACTIONS, swap(REUSED, ""))],
     [(BUSINESS, [TL], {L4})]),
    ("P10", "LaunchKeyReused 를 INSERT 뒤로(쓰기 뒤 거절)",
     [(ACTIONS, chain(swap(REUSED, ""), swap(ON_COMMIT, LATE_REUSED + ON_COMMIT)))],
     [(BUSINESS, [TL], {L4})]),
    ("P11", "RunIn.launchKey 무늬를 지움",
     [(SCHEMAS, swap("        pattern=KEY_PATTERN,\n", ""))],
     [(BUSINESS, [TL], {L2 + "[1]", L2 + "[1A2B3C4D-1111-4222-8333-444455556666]"})]),
    ("P12", "내보내기에도 묶음 셈(launches=True)",
     [(OPSEL, swap("rows.values(*PAGE_FIELDS), launches=False)", "rows.values(*PAGE_FIELDS), launches=True)"))],
     [(BUSINESS, [TRL, TSEL], {R10, SEL_QUERIES})]),
    ("P13", "run_out 의 resumedFromRunId 를 None 고정",
     [(RUN_LOGS, swap("        resumedFromRunId=run.resumed_from_run_id,\n", "        resumedFromRunId=None,\n"))],
     [(BUSINESS, [TRL], {R11})]),
    ("P14", "부분 색인을 유일로(0004 — 73 조건 (다) ⓙ)",
     [(MIGRATION, swap(INDEX, UNIQUE))],
     [(SECURITY, [SRUN], {S_J})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]
BOUNDARY_GUARDED = {"P3", "P4"}  # 범위 심음 — 예외로 빨개지면 무효
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


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 겨눈 시험이 초록
zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
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
        for layer, targets, expected in checks:
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
