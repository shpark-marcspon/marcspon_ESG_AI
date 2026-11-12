#!/usr/bin/env bash
# 밴드 IRS1(MARC-TICK-374)의 심은 파손(발주서 band-handoffs/IRS1-order.md §3). 하나씩 심고 겨눈 순수 시험만 돌린 뒤 원본
# 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — try/finally, SIGTERM·SIGINT 도 finally 를 지난다). 사용:
#   apps/api-py/scripts/planted-breaks-IRS1.sh [--commit <n>] [--only P1,P4]
#   --commit n 은 경계 n 까지의 몫만(① P1~P6, ② +P7·P8). 기본 2.
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= pytest 가 0 아닌 종료이고 빨개져야 할 노드가 전부
# FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: IRS1_OUT(기본: 워크트리 곁의 IRS1.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${IRS1_OUT:-$(cd "$ROOT/.." && pwd)/IRS1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY \
  uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import re
import signal
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
ONLY = None
COMMIT = 2
while args:
    if args[0] == "--only" and len(args) > 1:
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


XLSX = Path("esgapi/materiality/outputs/xlsx.py")
PM = Path("esgapi/materiality/flows/prompt_model_155.py")
COLAB = Path("esgapi/materiality/flows/colab_155.py")
TX = "esgapi/materiality/tests/outputs/test_xlsx.py"
TF = "esgapi/materiality/tests/outputs/test_final_xlsx.py"
TPM = "esgapi/materiality/tests/flows/test_prompt_model_155.py"
TB = "esgapi/materiality/tests/flows/test_binding_155.py"
X_UNITS = TX + "::test_utf16_units"
X_BOUNDARY = TX + "::test_fit_cell_counts_utf16_units_at_the_boundary"
X_SPLIT = TX + "::test_fit_cell_does_not_split_a_character_on_the_boundary"
X_LONE = TX + "::test_fit_cell_takes_a_lone_surrogate"
X_CHUNKS = TX + "::test_raw_json_chunks_stay_within_utf16_units"
X_F = TX + "::test_long_f_cell_with_astral_characters_is_cut"
X_OLD_SPLIT = TX + "::test_raw_json_splits_at_32767"
F_UTF16 = TF + "::test_a_cell_over_only_in_utf16_units_is_cut"
F_OLD_FIT = TF + "::test_fit_cell"
PM_AST = TPM + "::test_no_import_inside_a_body_and_none_of_binding_155"
PM_CAP = TPM + "::test_the_fixed_values_once_in_letters"
B_CAP = TB + "::test_the_run_cost_cap_is_five_usd"
CAP_IMPORT = (
    '    """판과 무관한 읽기 전용 코드 값 둘(웹 검색 · 실행 규칙 — 처분 Q12). 부를 때 짓는다."""\n',
    '    """판과 무관한 읽기 전용 코드 값 둘(웹 검색 · 실행 규칙 — 처분 Q12). 부를 때 짓는다."""\n'
    "    from esgapi.materiality.flows import binding_155  # noqa: F401\n",
)

# (경계, 번호, 설명, [(파일, 심는 함수)], 겨눔 시험 파일들, 빨개져야 할 노드)
PLANTS = [
    (1, "P1", "fit_cell 판정을 코드포인트 len(text) 로",
     [(XLSX, swap("    if length <= CELL_LIMIT:\n", "    if len(text) <= CELL_LIMIT:\n"))],
     [TX, TF], {X_BOUNDARY, X_F, F_UTF16}),
    (1, "P2", "자를 때 keep 을 코드포인트 CELL_LIMIT - len(mark) 로",
     [(XLSX, swap("keep = utf16_cut(text, CELL_LIMIT - utf16_units(mark))", "keep = CELL_LIMIT - len(mark)"))],
     [TX, TF], {X_BOUNDARY, X_SPLIT}),
    (1, "P3", "raw_json_chunks 를 코드포인트 슬라이스로",
     [(XLSX, swap("end = utf16_cut(text, CELL_LIMIT, start)", "end = start + CELL_LIMIT"))],
     [TX, TF], {X_CHUNKS}),
    (1, "P4", "폭을 encode(utf-16-le) 로 잼",
     [(XLSX, swap("return len(text) + sum(1 for ch in text if ord(ch) > 0xFFFF)",
                  'return len(text.encode("utf-16-le")) // 2'))],
     [TX, TF], {X_UNITS, X_LONE}),
    (1, "P5", "fit_cell 둘째 값을 코드포인트 len(text) 로",
     [(XLSX, swap("    return text[:keep] + mark, length\n", "    return text[:keep] + mark, len(text)\n"))],
     [TX, TF], {X_BOUNDARY, F_UTF16}),
    (1, "P6", "utf16_cut 비교를 >= 로(한 단위 일찍 끊음)",
     [(XLSX, swap("if used + width > limit:", "if used + width >= limit:"))],
     [TX, TF], {f"{X_OLD_SPLIT}", F_OLD_FIT}),
    (2, "P7", "fixed_groups 안에 binding_155 import 를 되살림(값은 그대로)",
     [(PM, swap(*CAP_IMPORT))],
     [TPM], {PM_AST}),
    (2, "P8", "colab_155.RUN_MAX_COST_USD 를 4.0 으로",
     [(COLAB, swap("RUN_MAX_COST_USD: Final = 5.0\n", "RUN_MAX_COST_USD: Final = 4.0\n"))],
     [TPM, TB], {PM_CAP, B_CAP}),
]
PLANTS = [p for p in PLANTS if p[0] <= COMMIT and (ONLY is None or p[1] in ONLY)]
FILES = sorted({f for p in PLANTS for f, _ in p[3]})


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True, check=True).stdout


def pytest(tests: list[str], log: Path) -> tuple[int, set[str]]:
    run = subprocess.run(
        ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db", *tests],
        capture_output=True, text=True,
    )
    log.write_text(run.stdout + run.stderr, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+)", run.stdout, re.M))
    return run.returncode, failed


before = {f: sha(f) for f in FILES}
before_status = status()
originals = {f: f.read_bytes() for f in FILES}
caught = 0
try:
    targets = sorted({t for p in PLANTS for t in p[4]})
    code, failed = pytest(targets, LOGS / "P0.log")
    print(f"P0 아무것도 안 심음: pytest EXIT={code} FAILED={len(failed)}")
    if code != 0:
        sys.exit("P0 이 빨갛다 — 멈춤")
    for _, name, what, plants, tests, must in PLANTS:
        ok = True
        for f, plant in plants:
            got = plant(originals[f].decode("utf-8"))
            if got is None:
                print(f"{name} {what}: 심을 자리를 못 찾음")
                ok = False
                break
            f.write_bytes(got.encode("utf-8"))
        if ok:
            code, failed = pytest(tests, LOGS / f"{name}.log")
            missing = must - failed
            extra = failed - must
            hit = code != 0 and not missing
            caught += hit
            print(f"{name} {what}: {'잡음' if hit else '놓침'} EXIT={code} · 빨강 {sorted(must & failed)}"
                  + (f" · 안 빨개짐 {sorted(missing)}" if missing else "")
                  + (f" · 더 빨개짐 {len(extra)}" if extra else ""))
            for node in sorted(failed):
                print(f"    FAILED {node}")
        for f in FILES:
            f.write_bytes(originals[f])
finally:
    for f in FILES:
        f.write_bytes(originals[f])
same = all(sha(f) == before[f] for f in FILES) and status() == before_status
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{len(PLANTS)}")
PY
