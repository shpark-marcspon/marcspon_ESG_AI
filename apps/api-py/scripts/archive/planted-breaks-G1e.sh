#!/usr/bin/env bash
# 밴드 G1e(MARC-TICK-199: 목록 줄 greenwash.checks@1 의 errorCode)의 심은 파손(발주서 band-handoffs/G1e-order.md §3-6).
# 꼴은 planted-breaks-G1b.sh 그대로(그 파일은 G1b 의 기록 — 고치지 않는다): 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로
# 되쓴다(git checkout·restore·stash 0). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-G1e.sh [--with-containers] [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 돌린 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED. 업무·보안 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」, 돌린 층이 없는 파손은
# 셈 밖. 통합 층은 심지 않는다(워커·api 이미지는 소스를 마운트하지 않는다 — 심은 파손을 재려면 매번 build 다).
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: G1E_OUT(기본: 워크트리 곁의 G1e.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${G1E_OUT:-$(cd "$ROOT/.." && pwd)/G1e.out}"
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


G = Path("esgapi/greenwash")
CHECKS = G / "service/actions/checks.py"
SHAPES = G / "contracts/checks_shapes.py"
T = "esgapi/greenwash/tests"
TC = f"{T}/service/apis/test_greenwash_checks.py"
TS = f"{T}/contracts/test_checks_shapes.py"
TR = f"{T}/flows/test_binding_e0_runs.py"
SEC = "tests/security/test_greenwash.py"
LINE = '                "errorCode": run.error_code if run.status == "failed" else None,\n'
GUARD = TC + "::test_the_error_code_is_the_run_records_code_only_when_failed"
ROWS = TC + "::test_the_rows_carry_the_greenwash_runs_and_their_documents"
SEC_NEW = SEC + "::test_the_checks_list_shows_my_failed_runs_error_code_only_to_my_company"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", "상태 가드 지움(run.error_code 그대로)",
     [(CHECKS, swap(LINE, '                "errorCode": run.error_code,\n'))],
     [(BUSINESS, [TC], {GUARD}), (SECURITY, [SEC], {SEC_NEW})]),
    ("2", "늘 None",
     [(CHECKS, swap(LINE, '                "errorCode": None,\n'))],
     [(BUSINESS, [TC, TR], {GUARD, ROWS, TR + "::test_a_pdf_without_a_text_layer_fails_in_extract"}),
      (SECURITY, [SEC], {SEC_NEW})]),
    ("3", "run.failed_step 을 냄",
     [(CHECKS, swap(LINE, '                "errorCode": run.failed_step if run.status == "failed" else None,\n'))],
     [(BUSINESS, [TC], {GUARD, ROWS})]),
    ("4", "꼴에서 칸 지움(예시·스키마 그대로)",
     [(SHAPES, swap("    errorCode: str | None\n", ""))],
     [(PURE, [TS], {TS + "::test_the_json_schema_is_pinned_byte_for_byte",
                    TS + "::test_an_example_fits_the_shape[checks-normal.json]"})]),
    ("5", "실행마다 run_selectors.find_run 한 번 더(쿼리 +1/실행)",
     [(CHECKS, swap("        result = _result_of(company_id, run)\n",
                    "        run_selectors.find_run(company_id=company_id, run_id=run.id)\n"
                    "        result = _result_of(company_id, run)\n"))],
     [(BUSINESS, [TC], {TC + "::test_the_query_count_grows_at_most_three_per_run"})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
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
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, checks in PLANTS:
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
        for layer, targets, expected in checks:
            label = f"[{number}/{layer[0]}]"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            ran += 1
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            missing = sorted(w for w in expected if w not in failed)
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
