#!/usr/bin/env bash
# 밴드 GT1 의 심은 파손(발주서 band-handoffs/GT1-order.md §3). 하나씩 심고 그 단계만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash·mv 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GT1.sh
#
# 판정(GC4 꼴): 0번(아무것도 안 심음)은 쓰는 단계가 전부 초록. 「잡음」= section4-GT1.sh --step <n> 의 종료 코드 ≠ 0 이고
# 출력에 「[n] … EXIT=1」 줄이 있다. 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일들의 sha256 이 시작과
# 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: GT1_OUT(기본: 워크트리 곁의 GT1.out)/planted/. 기준 노드 id 목록은 GT1_NODEIDS_BEFORE(기본 $GT1_OUT/nodeids-before.txt).
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GT1_OUT:-$(cd "$ROOT/.." && pwd)/GT1.out}"
export GT1_NODEIDS_BEFORE="${GT1_NODEIDS_BEFORE:-$OUT/nodeids-before.txt}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import ast
import hashlib
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
T = Path("esgapi/greenwash/tests")
CONTRACT = Path("esgapi/config/tests/test_api_contract.py")
SHAPES = T / "test_contracts_shapes_paths.py"
TERMS = T / "test_contracts_review_report_terms.py"


def step(n: int) -> list[str]:
    return ["bash", "scripts/section4-GT1.sh", "--step", str(n)]


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def drop_function(name: str) -> Callable[[str], str | None]:
    """최상위 함수 하나를 데코레이터째 지운다."""

    def plant(text: str) -> str | None:
        found = [n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == name]
        if len(found) != 1:
            return None
        node = found[0]
        first = min([node.lineno, *(d.lineno for d in node.decorator_list)])
        lines = text.splitlines(keepends=True)
        return "".join(lines[: first - 1] + lines[node.end_lineno :])

    return plant


# (번호, 심는 것, 파일, 심는 함수, 돌릴 단계)
PLANTS = [
    (1, "test_api_contract.py:414 주석을 옛 이름으로", CONTRACT,
     swap("test_contracts_shapes_paths.py 가 못 박는다", "test_contracts_gc1.py 가 못 박는다"), 4),
    (2, "review_report_terms 에서 시험 함수 하나(test_the_report_body_is_501)를 몸째 지움", TERMS,
     drop_function("test_the_report_body_is_501"), 5),
    (3, "shapes_paths 의 import 에서 compare_shapes 를 뺌", SHAPES,
     swap("from esgapi.greenwash.flows import compare_shapes, review_shapes, shapes\n",
          "from esgapi.greenwash.flows import review_shapes, shapes\n"), 3),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem), "GT1_OUT": str(LOGS / "s4")}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


steps = ",".join(str(n) for n in sorted({p[4] for p in PLANTS}))
code, _ = run(["bash", "scripts/section4-GT1.sh", "--step", steps], LOGS / "00.log")
print(f"[0] 아무것도 안 심음: {'전부 초록' if code == 0 else '빨강이 있다'} (단계 {steps})")
zero_ok = code == 0

caught = 0
for num, what, path, plant, n in PLANTS:
    original = path.read_bytes()
    planted = plant(original.decode("utf-8"))
    if planted is None:
        print(f"[{num}] {what}: 심을 자리를 못 찾음 — 못 잡은 것으로 센다")
        continue
    try:
        path.write_text(planted, encoding="utf-8")
        changed = path.read_bytes() != original
        code, out = run(step(n), LOGS / f"{num:02d}.log") if changed else (0, "")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    if not changed:
        print(f"[{num}] {what}: 파일이 바뀌지 않음 — 못 잡은 것으로 센다")
        continue
    red = [line for line in out.splitlines() if line.startswith(f"[{n}] ") and line.endswith("EXIT=1")]
    ok = code != 0 and bool(red)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (§4-{n}, 종료 {code}, {red[0] if red else '빨간 줄 없음'})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
