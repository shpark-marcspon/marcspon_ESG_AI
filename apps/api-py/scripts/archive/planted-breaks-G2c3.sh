#!/usr/bin/env bash
# 밴드 G2c3(MARC-TICK-202: 그린워싱 AI 설정 판 뒷손질 — 목록·잠금이 기준표를 안 읽음, 못 받는 저장 판 409, 시험 보강)의
# 심은 파손(발주서 band-handoffs/G2c3-order.md §3-5). 틀은 planted-breaks-G2c2.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로
# 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G2c3.sh [--commit 1|2] [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 커밋 n 에는 커밋 n 까지의 파손만 심는다. 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로
# 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G2C3_OUT(기본: 워크트리 곁의 G2c3.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G2C3_OUT:-$(cd "$ROOT/.." && pwd)/G2c3.out}"
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
COMMIT = 2
CONTAINERS = False
ONLY: set[str] | None = None
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2"):
        COMMIT, args = int(args[1]), args[2:]
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


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
SEL = G / "service/selectors/ai_settings.py"
FLOWF = G / "flows/colab_e0.py"
TSEL = f"{T}/service/selectors/test_ai_settings.py"
TA = f"{T}/service/apis/test_ai_settings.py"
TBR = f"{T}/flows/test_binding_e0_settings_runs.py"
TD = f"{T}/flows/test_colab_e0_dryrun_settings.py"
TB = f"{T}/flows/test_binding_e0_settings.py"
BIND = G / "flows/binding_e0.py"
SVC = G / "service/services/ai_settings.py"
RUNS_ACT = Path("esgapi/runs/service/actions/runs.py")
RUNS_API = Path("esgapi/runs/service/apis/runs.py")
ERRORS = Path("esgapi/runs/calc/errors.py")
TRV = "esgapi/runs/tests/service/apis/test_runs_versions.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

RUN_409 = TBR + "::test_a_run_on_an_applied_version_the_rules_no_longer_take_is_409"
RUN_409_ANY = TRV + "::test_a_binding_that_cannot_build_the_versions_is_409_and_writes_nothing"
WORKER = TBR + "::test_a_run_whose_version_the_rules_no_longer_take_fails_as_versions_mismatch"
# P12: 거절을 실행 행 쓰기 뒤에서 돌려준다(블록은 정상 끝 — 행이 커밋된다)
ROW_THEN_REFUSE = (
    "            RunRow.for_company(company_id).create(company_id=company_id, document_id=document.id,"
    " module=flow.module, flow_id=flow.id, options=dict(options), versions={}, status=\"queued\", attempts=0,"
    " created_by_user_id=actor_user_id, resumed_from_run_id=resume_from)\n"
    "            return VersionsRejected(refused.message)\n"
)

NO_CRITERIA = {TSEL + "::test_the_list_and_the_lock_never_read_the_criteria",
               TA + "::test_the_apply_path_never_reads_the_criteria"}
# P3 의 셈 둘(BASE 의 꼴 — 쪽 읽기 뒤 셈 한 문·적용 판 한 문)
BASE_COUNTS = ('type("Counted", (), {"total": rows.count(), '
               '"applied_id": next((r["id"] for r in applied), None)})')

# (번호, 커밋, 설명, [(파일, 심는 함수)], [(검사 커밋, 층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", 1, "목록 문에서 .only(...) 지움",
     [(SEL, swap("        rows.only(*HEAD_FIELDS)\n", "        rows\n"))],
     [(1, BUSINESS, [TSEL, TA], NO_CRITERIA)]),
    ("2", 1, "잠금 문에서 .only(...) 지움",
     [(SEL, swap('.only("id", "name", "applied").select_for_update()', ".select_for_update()"))],
     [(1, BUSINESS, [TSEL, TA], NO_CRITERIA)]),
    ("3", 1, "목록을 BASE 의 문 셋으로(쪽 읽기·셈·적용 판 따로)",
     [(SEL, swap(
         "    page = list(\n"
         "        rows.only(*HEAD_FIELDS)\n"
         '        .annotate(total=Window(Count("id")), applied_id=Subquery(applied))\n'
         '        .order_by("-id")[offset : offset + limit]\n'
         "    )\n"
         "    if page:\n"
         "        first = page[0]\n",
         '    page = list(rows.only(*HEAD_FIELDS).order_by("-id")[offset : offset + limit])\n'
         "    if page:\n"
         f"        first = {BASE_COUNTS}\n"))],
     [(1, BUSINESS, [TSEL], {TSEL + "::test_a_non_empty_page_is_one_statement"})]),
    ("4", 1, "빈 쪽 갈래 지움(total 을 쪽 행에서만)",
     [(SEL, swap('    counted = rows.aggregate(total=Count("id"), applied_id=Max("id", filter=Q(applied=True)))\n',
                 '    counted = {"total": 0, "applied_id": None}\n'))],
     [(1, BUSINESS, [TSEL], {TSEL + "::test_an_empty_page_still_counts["})]),
    ("5", 1, "RunSettingStore.get 의 회사 조건 지움",
     [(SEL, swap("        row = GreenwashAiSettingRow.for_company(company_id).filter(id=setting_id).first()\n",
                 '        row = GreenwashAiSettingRow._meta.managers_map["unscoped"].filter(id=setting_id).first()\n'))],
     [(1, BUSINESS, [TBR], {TBR + "::test_a_run_whose_version_cannot_be_rebuilt_fails[foreign]"})]),
    ("6", 1, "dry-run 보정의 글자·토큰 맞바꿈(토큰을 못 세는 갈래는 그대로)",
     [(FLOWF, swap('            tally["input_chars"] += requests * chars\n',
                   '            tally["input_chars"] += requests * (chars if tokens is None else tokens)\n')),
      (FLOWF, swap('                counted["value"] += requests * tokens\n',
                   '                counted["value"] += requests * chars\n'))],
     [(1, PURE, [TD], {TD + "::test_chars_and_tokens_are_adjusted_each_by_its_own_difference",
                       TD + "::test_the_flow_adjusts_bytes_as_tokens_and_chars_as_chars"})]),
    ("7", 1, "토큰 차이 = 글자 차이(tokens = chars)",
     [(FLOWF, swap("    tokens = None if edited_tokens is None or default_tokens is None else edited_tokens - default_tokens\n",
                   "    tokens = None if edited_tokens is None or default_tokens is None else chars\n"))],
     [(1, PURE, [TD], {TD + "::test_chars_and_tokens_are_adjusted_each_by_its_own_difference",
                       TD + "::test_the_flow_adjusts_bytes_as_tokens_and_chars_as_chars"})]),
    ("8", 2, "versions_with 의 except CriteriaRejected 지움",
     [(BIND, swap("        except CriteriaRejected as refused:\n            raise RunVersionsRejected(",
                  "        except ZeroDivisionError as refused:\n            raise RunVersionsRejected("))],
     [(2, PURE, [TB], {TB + "::test_versions_with_a_version_the_rules_no_longer_take_is_rejected"}),
      (2, BUSINESS, [TBR], {RUN_409})]),
    ("9", 2, "runs actions 의 except RunVersionsRejected 지움",
     [(RUNS_ACT, swap("        except flow_ports.RunVersionsRejected as refused:\n",
                      "        except ZeroDivisionError as refused:\n"))],
     [(2, BUSINESS, [TRV, TBR], {RUN_409_ANY, RUN_409})]),
    ("10", 2, "runs apis 가 invalid_input 으로 접음",
     [(RUNS_API, swap('        raise ApplicationError("conflict", "ai_setting_unusable", result.message)\n',
                      '        raise ApplicationError("invalid_input", "invalid_options", result.message)\n'))],
     [(2, BUSINESS, [TRV, TBR], {RUN_409_ANY, RUN_409})]),
    ("11", 2, "적용 막기 지움",
     [(SVC, swap("        try:\n            accept_criteria(found.criteria)\n        except CriteriaRejected as refused:\n"
                 "            return SettingUnusable(refused.code, found.name)\n", ""))],
     [(2, BUSINESS, [TA], {TA + "::test_a_version_the_rules_no_longer_take_cannot_be_applied"})]),
    ("12", 2, "거절을 실행 행 쓰기 뒤에서 돌려줌",
     [(RUNS_ACT, swap("            return VersionsRejected(refused.message)\n", ROW_THEN_REFUSE))],
     [(2, BUSINESS, [TRV, TBR], {RUN_409_ANY, RUN_409})]),
    ("13", 2, "errors.py 의 새 줄 지움(versions_mismatch)",
     [(ERRORS, swap('    "RunVersionsMismatch": "versions_mismatch",\n', "")),
      (ERRORS, swap('    "versions_mismatch": "실행을 만들 때의 판정 기준을 지금 다시 지을 수 없다(새 실행으로 다시 돌려야 한다)",\n', ""))],
     [(2, BUSINESS, [TBR], {TBR + "::test_a_run_whose_version_cannot_be_rebuilt_fails[", WORKER})]),
    ("14", 2, "inputs_with 의 except CriteriaRejected 지움(critic B1)",
     [(BIND, swap("        except CriteriaRejected as refused:\n            raise AiSettingMismatch(",
                  "        except ZeroDivisionError as refused:\n            raise AiSettingMismatch("))],
     [(2, PURE, [TB], {TB + "::test_inputs_with_a_version_the_rules_no_longer_take_fails"}),
      (2, BUSINESS, [TBR], {WORKER})]),
]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]
PLANTS = [p for p in PLANTS if p[1] <= COMMIT]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def checks_of(plant):
    return [c for c in plant[4] if c[0] <= COMMIT]


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


files = sorted({f for p in PLANTS for f, _ in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for _, layer, targets, _ in checks_of(p):
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, _commit, what, edits, _ in PLANTS:
    plant = next(p for p in PLANTS if p[0] == number)
    originals = {f: f.read_bytes() for f, _ in edits}
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
        for _, layer, targets, expected in checks_of(plant):
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
