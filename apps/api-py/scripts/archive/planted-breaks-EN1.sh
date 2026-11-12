#!/usr/bin/env bash
# 밴드 EN1 의 심은 파손(발주서 band-handoffs/EN1-order.md §3). 하나씩 심고 겨눈 단계만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든): apps/api-py/scripts/planted-breaks-EN1.sh
#   --only P1,P9   일부만
#
# 판정: 0번(아무것도 안 심음)은 쓰는 단계가 전부 초록. 「잡음」= section4-EN1.sh --step <n> 의 종료 코드 ≠ 0 이고 출력에
# 「[n] … EXIT=1」 줄이 있으며 —
#   lint 를 겨눈 파손(P1~P7)은 lint-imports 가 BROKEN 으로 찍은 계약의 **id 묶음**이 기대와 꼭 같을 것
#     (planted-breaks.sh 는 머리글자만 보아 「자」 넷을 가르지 못한다. 여기서 id 로 가른다)
#   시험을 겨눈 파손(P8·P9)은 그 시험이 FAILED 로 찍힐 것
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, 새로 만든 파일이 남지 않았는지,
# git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: EN1_OUT(기본: 워크트리 곁의 EN1.out)/planted/. 컨테이너·공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${EN1_OUT:-$(cd "$ROOT/.." && pwd)/EN1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" "$OUT" "$@" <<'PY'
import configparser
import hashlib
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
REAL_OUT = Path(sys.argv[2])
ONLY = None
if len(sys.argv) > 3:
    if sys.argv[3] != "--only" or len(sys.argv) != 5:
        print(f"모르는 인자: {sys.argv[3:]} (쓸 수 있는 것은 --only P1,P9 하나)", file=sys.stderr)
        sys.exit(2)
    ONLY = set(sys.argv[4].split(","))
I = Path("esgapi/inventory")


def append(line: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text + "\n" + line + "\n"

    return plant


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


ENG_C = "inventory-engine-not-contracts"
CON_E = "inventory-contracts-not-engines"
TOOLS = "inventory-tools-know-no-axis"
APART = "inventory-engines-apart"
PURE = "pure-modules"
T_READER = "test_the_reader_is_the_only_product_file_that_imports_zipfile_or_xml"
T_VOCAB = "test_contract_literal_matches_engine[Gas]"
T_FLOW = "esgapi/inventory/tests/test_flow_shapes.py::"

# (번호, 설명, [(파일, 심는 함수)], 새로 만드는 파일 {경로: 글}, 단계, 기대 계약 id 묶음 | None, 빨개져야 할 시험들)
PLANTS = [
    ("P1", "contracts/shapes.py + from …engines.scope12.engine_1 import types",
     [(I / "contracts/shapes.py", append("from esgapi.inventory.engines.scope12.engine_1 import types"))], {}, 10, {CON_E}, []),
    ("P2", "engines/scope3/llm_first_1/memory.py + from …contracts import shapes",
     [(I / "engines/scope3/llm_first_1/memory.py", append("from esgapi.inventory.contracts import shapes"))], {}, 10, {ENG_C}, []),
    ("P3", "tools/jsrepr.py + import …engines.scope12.engine_1.units",
     [(I / "tools/jsrepr.py", append("import esgapi.inventory.engines.scope12.engine_1.units"))], {}, 10, {TOOLS, APART}, []),
    ("P4", "engines/scope3/llm_first_1/memory.py + from …engines.scope12.engine_1 import units",
     [(I / "engines/scope3/llm_first_1/memory.py", append("from esgapi.inventory.engines.scope12.engine_1 import units"))],
     {}, 10, {APART}, []),
    ("P5", "engines/scope12/engine_1/units.py + from …flows import registration",
     [(I / "engines/scope12/engine_1/units.py", append("from esgapi.inventory.flows import registration"))],
     {}, 10, {ENG_C, APART}, []),
    ("P6", "tools/scope3_sheets/grid.py + import django",
     [(I / "tools/scope3_sheets/grid.py", append("import django"))], {}, 10, {PURE}, []),
    ("P7", "engines/scope12/engine_1/units.py + import django",
     [(I / "engines/scope12/engine_1/units.py", append("import django"))], {}, 10, {PURE}, []),
    ("P8", "tests/test_s3sheets_is_pure.py 의 parents[2] 를 parents[1] 로 되돌림",
     [(I / "tests/test_s3sheets_is_pure.py", swap("Path(xlsx_reader.__file__).parents[2]", "Path(xlsx_reader.__file__).parents[1]"))],
     {}, 1, None, [T_READER]),
    ("P9", "contracts/shapes.py 의 Gas Literal 에서 N2O 를 뺌",
     [(I / "contracts/shapes.py", swap('Gas = Literal["CO2", "CH4", "N2O"]\n', 'Gas = Literal["CO2", "CH4"]\n'))],
     {}, 1, None, [T_VOCAB, T_FLOW]),
    ("P10", "옛 flows/shapes.py 를 contracts.shapes 의 다시 내보내기로 되살림",
     [], {I / "flows/shapes.py": "from esgapi.inventory.contracts.shapes import *  # noqa: F403\n"}, 4, None, []),
]
if ONLY:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]
    if not PLANTS:
        sys.exit(f"--only {sorted(ONLY)} 에 맞는 심기가 없다")


def name_to_id() -> dict[str, str]:
    cp = configparser.ConfigParser()
    cp.read(".importlinter", encoding="utf-8")
    return {cp[s]["name"].strip(): s.split(":")[-1] for s in cp.sections() if s.startswith("importlinter:contract:")}


NAMES = name_to_id()


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


files = sorted({f for p in PLANTS for f, _ in p[2]})
created = sorted({c for p in PLANTS for c in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
pre_existing = [c for c in created if c.exists()]
status_before = status()

OUTDIR = LOGS / "out"
OUTDIR.mkdir(parents=True, exist_ok=True)
# section4 는 기준 collect·bodies 를 EN1_OUT 에서 읽는다 — 진짜 OUT 의 collect-base.txt 를 옮겨 쓴다
shutil.copy(REAL_OUT / "collect-base.txt", OUTDIR / "collect-base.txt")


def run(step: int, log: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache"), "EN1_OUT": str(OUTDIR)}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run(["bash", "scripts/section4-EN1.sh", "--boundary", "2", "--step", str(step)],
                          capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red(step: int, code: int, text: str) -> bool:
    return code != 0 and re.search(rf"^\[{step}\] .* EXIT=1$", text, flags=re.M) is not None


def broken_ids() -> set[str]:
    lint = (OUTDIR / "section4/10-lint.txt").read_text(encoding="utf-8")
    got = set()
    for line in lint.splitlines():
        if line.endswith(" BROKEN"):
            got.add(NAMES.get(line[: -len(" BROKEN")].strip(), "?" + line[:40]))
    return got


steps = sorted({p[4] for p in PLANTS})
zero_ok = True
for step in steps:
    code, text = run(step, LOGS / f"P0-step{step}.txt")
    ok = code == 0
    zero_ok &= ok
    print(f"P0  심지 않음 --step {step}: {'초록' if ok else '★ 빨강'}")
caught = 0
for num, what, plants, new_files, step, want_ids, want_tests in PLANTS:
    originals = {f: f.read_bytes() for f, _ in plants}
    planted = True
    try:
        for f, fn in plants:
            new = fn(f.read_text(encoding="utf-8"))
            if new is None or new == f.read_text(encoding="utf-8"):
                planted = False
                break
            f.write_text(new, encoding="utf-8")
        for c, body in new_files.items():
            if c.exists():
                planted = False
                break
            c.write_text(body, encoding="utf-8")
        if not planted:
            print(f"{num} {what}: ★ 심지 못함(자리가 없다)")
            continue
        code, text = run(step, LOGS / f"{num}.txt")
        ok = red(step, code, text)
        detail = ""
        if want_ids is not None:
            got = broken_ids()
            ok &= got == want_ids
            detail = f" · BROKEN {sorted(got)} (기대 {sorted(want_ids)})"
        pytest_out = text
        if step == 1:  # section4 의 1 은 pytest 출력을 파일에 두고 끝 줄만 찍는다
            pytest_out += (OUTDIR / "section4/1-pure.txt").read_text(encoding="utf-8")
        for t in want_tests:
            hit = re.search(rf"^FAILED \S*{re.escape(t)}", pytest_out, flags=re.M) is not None
            ok &= hit
            detail += f" · {t} FAILED {'찍힘' if hit else '★ 없음'}"
        caught += ok
        print(f"{num} {what} --step {step}: {'잡음' if ok else '★ 놓침'}{detail}")
    finally:
        for f, b in originals.items():
            f.write_bytes(b)
        for c in new_files:
            if c.exists() and c not in pre_existing:
                c.unlink()

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
leftover = [str(c) for c in created if c.exists() and c not in pre_existing]
same = end == start and not leftover and status() == status_before
if not same:
    print("★ 작업 트리가 처음과 다르다:", [str(f) for f in files if end[f] != start[f]], leftover)
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if (zero_ok and caught == len(PLANTS) and same) else 1)
PY
