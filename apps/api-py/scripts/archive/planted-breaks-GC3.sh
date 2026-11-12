#!/usr/bin/env bash
# 밴드 GC3 의 심은 파손(발주서 band-handoffs/GC3-order.md §3 의 다섯). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GC3.sh
#
# 판정(GR1·GL1 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이 전부
# 빨간 줄(pytest 의 FAILED·ERROR 줄, section4 의 `[n] … EXIT=<0 아님>` 줄)에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 파손 5 는 section4-G1a.sh --step 12(대조 A)로 잰다 — 그 스크립트가 스스로 부르는 gw1(esg-lab, 모의 공급사)만 돈다.
# 환경 변수: GC3_OUT(기본: 워크트리 곁의 GC3.out) — 산출물은 $GC3_OUT/planted/. GC3_BASE(기준 커밋, G1A_BASE 로 넘긴다).
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GC3_OUT:-$(cd "$ROOT/.." && pwd)/GC3.out}"
BASE="${GC3_BASE:-b10dc74f35c80a96779543c42095897c33ebf7fc}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" "$BASE" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from pathlib import Path

LOGS, BASE = Path(sys.argv[1]), sys.argv[2]
G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"]
WIRE_COLAB = PYTEST + [f"{T}/flows/test_wire.py", f"{T}/flows/test_colab.py"]
G1A_12 = ["env", f"G1A_OUT={LOGS / 'g1a'}", f"G1A_BASE={BASE}", "scripts/section4-G1a.sh", "--step", "12"]

# (번호, 심는 것, 파일, [(옛 글, 새 글), …], 돌릴 명령, 빨개져야 하는 것(빨간 줄에 들어야 하는 글 — 전부))
PLANTS = [
    (1, "result_to_wire 에서 by_level·by_part 예외를 뺌", G / "flows/wire.py",
     [('VALUE_KEYED: Final = {"byLevel": 1, "byPart": 2}', "VALUE_KEYED: Final[dict[str, int]] = {}")],
     WIRE_COLAB, ["test_value_keyed_places_keep_their_keys", "test_contrast_a_matches_gw1"]),
    (2, "assemble 이 result_to_wire 를 거치지 않음", G / "flows/colab.py",
     [("    return wire.result_to_wire(snake)\n", "    return snake\n")],
     WIRE_COLAB, ["test_contrast_a_matches_gw1", "test_the_flows_snake_result_becomes_result_at_1"]),
    (3, "support.gw1_view 가 GW1 쪽을 사상하지 않음", G / "tests/flows/support.py",
     [("    mapped = _gw1_wire(gw1)\n", "    mapped = dict(gw1)\n")],
     WIRE_COLAB, ["test_contrast_a_matches_gw1"]),
    (4, "Item 의 riskTags 를 risk_tags 로 되돌림", G / "flows/shapes.py",
     [("    riskTags: list[str]\n", "    risk_tags: list[str]\n")],
     PYTEST + [f"{T}/flows/test_wire.py"],
     ["test_every_shape_key_is_camel_case_except_the_value_keyed_two", "test_the_69_renamed_keys_are_all_new_and_none_old"]),
    (5, "g1a_compare.py 가 GW1 쪽을 사상하지 않음", Path("scripts/g1a_compare.py"),
     [("    return result_to_wire({k: v for k, v in gw1.items() if k not in UNMAPPED})",
       "    return {k: v for k, v in gw1.items() if k not in UNMAPPED}")],
     G1A_12, ["[12] 대조 A"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다.
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    return [
        line
        for line in text.splitlines()
        if line.startswith(("FAILED", "ERROR")) or re.match(r"^\[\d+\] .* EXIT=[1-9]", line)
    ]


zero_ok = True
for name, cmd in (("00-pytest", PYTEST + [f"{T}/flows/test_wire.py", f"{T}/flows/test_colab.py"]), ("00-g1a", G1A_12)):
    code, _ = run(cmd, LOGS / f"{name}.log")
    zero_ok = zero_ok and code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'}")

caught = 0
for num, what, path, edits, cmd, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    counts = [text.count(old) for old, _ in edits]
    if counts != [1] * len(edits):
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {counts} 번) — 못 잡은 것으로 센다")
        continue
    for old, new in edits:
        text = text.replace(old, new, 1)
    try:
        path.write_text(text, encoding="utf-8")
        code, out = run(cmd, LOGS / f"{num:02d}.log")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    reds = red_lines(out)
    hit = [w for w in want if any(w in line for line in reds)]
    ok = code != 0 and len(hit) == len(want)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대한 것 {hit}/{want})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
