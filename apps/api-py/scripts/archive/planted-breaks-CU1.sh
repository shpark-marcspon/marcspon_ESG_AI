#!/usr/bin/env bash
# 밴드 CU1 의 심은 파손(발주서 band-handoffs/CU1-order.md §3). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-CU1.sh
#
# 판정(GC4 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 빨간 줄(FAILED·ERROR)에 있다. 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: CU1_OUT(기본: 워크트리 곁의 CU1.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${CU1_OUT:-$(cd "$ROOT/.." && pwd)/CU1.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
E = Path("esgapi")
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "-p", "no:randomly"]
IDS = PYTEST + ["esgapi/core/tests/calc/test_ids.py"]
PERMISSIONS = PYTEST + ["esgapi/core/tests/test_permissions.py"]
PIPELINE = PYTEST + ["esgapi/inventory/tests/calc/scope3/test_pipeline.py"]
SHAPES = PYTEST + ["esgapi/inventory/tests/flows/test_shapes.py"]
TRANSACTION = PYTEST + ["esgapi/core/tests/test_transaction_rules.py"]

# (번호, 심는 것, 파일, 옛 글, 새 글, 돌릴 명령, 빨개져야 하는 것(빨간 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "ids.is_company_id 가 True 를 받음", E / "core/calc/ids.py",
     "isinstance(value, int) and not isinstance(value, bool) and value > 0", "isinstance(value, int) and value > 0",
     IDS, ["test_the_shape_of_a_company_id[True-False]"]),
    (2, "runs_list 가 첫 문장에서 permitted 를 부르지 않음", E / "core/service/apis/runs.py",
     '    permitted(request, "runs_list")\n    return error_response(501',
     '    _ = NOT_IMPLEMENTED\n    permitted(request, "runs_list")\n    return error_response(501',
     PERMISSIONS, ["test_each_route_checks_its_own_operation_id_first"]),
    (3, "후보 고르기의 단위 환산 거르기를 뺌", E / "inventory/calc/scope3/pipeline.py",
     "    physical = [factor for factor in physical_all if conversion_factor(dim, factor.denominator_dim) is not None]",
     "    physical = [factor for factor in physical_all if dim is not None]",
     PIPELINE, ["test_the_two_paths_pick_the_same_candidates"]),
    (4, "shapes.py 의 LlmFailureJson 에 키 하나를 더함", E / "inventory/flows/shapes.py",
     "class LlmFailureJson(TypedDict):\n    kind: FailureKind\n    detail: str\n",
     "class LlmFailureJson(TypedDict):\n    kind: FailureKind\n    detail: str\n    hint: NotRequired[str]\n",
     SHAPES, ["test_the_typed_dict_and_the_route_schema_have_the_same_skeleton[LlmFailureJson"]),
    (5, "업무 층 Scope 3 분류를 atomic 블록 안에서 부름(검증 F1)", E / "inventory/service/services/inventory.py",
     "        classification = classify_group(client, group, SCOPE3_ROUTE, tags, usage)\n",
     "        with transaction.atomic():\n"
     "            classification = classify_group(client, group, SCOPE3_ROUTE, tags, usage)\n",
     TRANSACTION, ["test_no_outside_call_inside_a_block"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]


cmds = {tuple(p[5]) for p in PLANTS}
zero_ok = True
for i, cmd in enumerate(sorted(cmds)):
    code, _ = run(list(cmd), LOGS / f"00-{i}.log")
    zero_ok = zero_ok and code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'} ({len(cmds)} 명령)")

caught = 0
for num, what, path, old, new, cmd, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    if text.count(old) != 1:
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {text.count(old)} 번) — 못 잡은 것으로 센다")
        continue
    try:
        path.write_text(text.replace(old, new, 1), encoding="utf-8")
        changed = path.read_bytes() != original
        code, out = run(cmd, LOGS / f"{num:02d}.log") if changed else (0, "")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    if not changed:
        print(f"[{num}] {what}: 파일이 바뀌지 않음 — 못 잡은 것으로 센다")
        continue
    reds = red_lines(out)
    hit = [w for w in want if any(w in line for line in reds)]
    ok = code != 0 and bool(hit)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대한 것 {hit or want})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
