#!/usr/bin/env bash
# 밴드 GX1 의 심은 파손(발주서 band-handoffs/GX1-order.md §3). 하나씩 심고 겨눈 단계만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GX1.sh
#
# 판정: 0번(아무것도 안 심음)은 쓰는 단계가 전부 초록. 「잡음」= 겨눈 단계마다 section4-GX1.sh --step <n> 의 종료 코드 ≠ 0
# 이고 출력에 「[n] … EXIT=1」 줄이 있으며, 시험을 겨눈 파손은 그 시험이 FAILED 로 찍힘. P5~P8 은 10 과 5 둘 다 빨개야
# 잡은 것으로 센다(하나만이면 놓친 쪽을 찍는다). 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이
# 시작과 같은지, 새로 만든 파일이 남지 않았는지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: GX1_OUT(기본: 워크트리 곁의 GX1.out)/planted/.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GX1_OUT:-$(cd "$ROOT/.." && pwd)/GX1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
G = Path("esgapi/greenwash")
S4 = LOGS / "s4"


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def before_imports(line: str) -> Callable[[str], str | None]:
    """첫 import 줄 앞(모듈 docstring 뒤)에 한 줄."""

    def plant(text: str) -> str | None:
        m = re.search(r"^(from |import )", text, flags=re.M)
        return None if m is None else text[: m.start()] + line + "\n" + text[m.start() :]

    return plant


T_COMPARE = "test_importing_compare_pulls_in_no_pdfium_django_or_ninja"
T_BOUNDARY = "test_flow_modules_touch_nothing_outside_their_adapters"
T_REFUSE = "test_the_bridge_refuses_what_is_not_a_notebook_call"

# (번호, 심는 것, [(파일, 심는 함수)], 새로 만드는 파일 {경로: 글}, 돌릴 단계, 빨개져야 할 시험)
PLANTS = [
    ("P1", "engines/e0/wordcount.py 의 낱말 하나", [(G / "engines/e0/wordcount.py", swap('    "녹색",\n', '    "녹샙",\n'))], {}, [6], None),
    ("P2", "outputs/compare.py 에 import …tools.pdfium_locate", [(G / "outputs/compare.py", before_imports("import esgapi.greenwash.tools.pdfium_locate"))], {}, [1], T_COMPARE),
    ("P3", "tools/llm_bridge.py 에 import os", [(G / "tools/llm_bridge.py", before_imports("import os"))], {}, [1], T_BOUNDARY),
    ("P4", "LlmChatBridge.invoke 의 프롬프트 넷 검사를 지움", [(G / "flows/colab_e0.py", swap('        if kind not in PROMPT_IDS:\n            raise ValueError("system 글이 노트북의 프롬프트 넷 가운데 하나가 아니다")\n', ""))], {}, [1], T_REFUSE),
    ("P5", "contracts/shapes.py 에 from …engines.e0 import wordcount", [(G / "contracts/shapes.py", before_imports("from esgapi.greenwash.engines.e0 import wordcount"))], {}, [10, 5], None),
    ("P6", "engines/e0/parts.py 에 from …contracts import shapes", [(G / "engines/e0/parts.py", before_imports("from esgapi.greenwash.contracts import shapes"))], {}, [10, 5], None),
    ("P7", "outputs/xlsx.py 에 from …engines.e0 import gw1", [(G / "outputs/xlsx.py", before_imports("from esgapi.greenwash.engines.e0 import gw1"))], {}, [10, 5], None),
    ("P8", "tools/textnorm.py 에 import …engines.e0.heuristics", [(G / "tools/textnorm.py", before_imports("import esgapi.greenwash.engines.e0.heuristics"))], {}, [10, 5], None),
    ("P9", "engines/e0/retrieval.py 에 import django", [(G / "engines/e0/retrieval.py", before_imports("import django"))], {}, [5], None),
    ("P10", "tools/coordinates.py 에 import django", [(G / "tools/coordinates.py", before_imports("import django"))], {}, [5], None),
    ("P11", "옛 flows/wire.py 를 다시 내보내기로 만들고 support.py 가 그것을 부름",
     [(G / "tests/flows/support.py", swap("from esgapi.greenwash.contracts import wire\n", "from esgapi.greenwash.flows import wire\n"))],
     {G / "flows/wire.py": "from esgapi.greenwash.contracts.wire import *  # noqa: F403\n"}, [3], None),
]

files = sorted({f for p in PLANTS for f, _ in p[2]})
created = sorted({c for p in PLANTS for c in p[3]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
pre_existing = [c for c in created if c.exists()]


def run(step: int, log: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache"), "GX1_OUT": str(LOGS / "out")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run(["bash", "scripts/section4-GX1.sh", "--step", str(step)], capture_output=True, text=True,
                          check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red(step: int, code: int, text: str) -> bool:
    return code != 0 and re.search(rf"^\[{step}\] .* EXIT=1$", text, flags=re.M) is not None


(LOGS / "out").mkdir(parents=True, exist_ok=True)
# section4 는 기준 collect·등록 길 파일을 GX1_OUT 에서 읽는다 — 진짜 OUT 의 것을 옮겨 쓴다
real_out = LOGS.parent
for name in ("collect-base.txt", "collect-base-nodes.txt", "registry-base.txt"):
    src = real_out / name
    if src.exists():
        (LOGS / "out" / name).write_bytes(src.read_bytes())

bad_start = bool(pre_existing)
if bad_start:
    print(f"[0] 시작 때 이미 있는 파일: {[str(c) for c in pre_existing]}")
steps0 = sorted({s for p in PLANTS for s in p[4]})
clean = True
for s in steps0:
    code, text = run(s, LOGS / f"0-step{s}.log")
    ok = code == 0
    clean = clean and ok
    print(f"[0] 안 심음 --step {s}: {'초록' if ok else '빨강'} (종료 {code})")

caught = 0
for num, what, edits, new_files, steps, test in PLANTS:
    originals = {f: f.read_bytes() for f, _ in edits}
    planted = True
    for f, plant in edits:
        new = plant(originals[f].decode("utf-8"))
        if new is None or new.encode("utf-8") == originals[f]:
            planted = False
            break
        f.write_bytes(new.encode("utf-8"))
    if planted:
        for c, body in new_files.items():
            c.write_text(body, encoding="utf-8")
    try:
        if not planted:
            print(f"[{num}] {what}: 심지 못함(자리가 없다) — 안 잡은 것으로 센다")
            continue
        verdicts = []
        for s in steps:
            code, text = run(s, LOGS / f"{num}-step{s}.log")
            hit = red(s, code, text)
            if hit and test is not None:
                log = (LOGS / "out" / "section4" / "pytest-greenwash.log").read_text(encoding="utf-8")
                hit = re.search(rf"^FAILED \S*::{test}\b", log, flags=re.M) is not None
            if s == 5:  # 어느 계약이 깨졌나(이름 줄은 접혀 찍히므로 BROKEN 앞 글을 이어 붙인다)
                lint = (LOGS / "out" / "section4" / "lint-imports.log").read_text(encoding="utf-8")
                (LOGS / f"{num}-lint-imports.log").write_text(lint, encoding="utf-8")
                head = lint.split("Contracts:")[0] if "Contracts:" in lint else lint
                rows = head.splitlines()
                broken = []
                for i, row in enumerate(rows):
                    if row.rstrip().endswith("BROKEN"):
                        prev = rows[i - 1].rstrip() if i else ""
                        joined = row if not prev or prev.endswith(("KEPT", "BROKEN", "imports)")) else prev + " " + row
                        broken.append(" ".join(joined.split()))
                print(f"    [{num}] lint-imports 깨진 계약: {broken}")
            verdicts.append((s, hit))
        ok = all(h for _, h in verdicts)
        caught += ok
        detail = " · ".join(f"--step {s} {'빨강' if h else '초록(놓침)'}" for s, h in verdicts)
        print(f"[{num}] {what}: {detail}{' · 시험 ' + test if test else ''} → {'잡음' if ok else '놓침'}")
    finally:
        for f, body in originals.items():
            f.write_bytes(body)
        for c in new_files:
            if c.exists():
                c.unlink()

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
left = [str(c) for c in created if c.exists()]
same = end == start and not left and not bad_start
print(f"[0] 안 심음 단계 전부 초록: {'예' if clean else '아니오'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if (clean and same and caught == len(PLANTS)) else 1)
PY
