#!/usr/bin/env bash
# 밴드 GC4 의 심은 파손(발주서 band-handoffs/GC4-order.md §3). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GC4.sh
#
# 판정(G1c 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 빨간 줄(FAILED·ERROR, 또는 section4 의 EXIT=1 줄)에 있다. 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: GC4_OUT(기본: 워크트리 곁의 GC4.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GC4_OUT:-$(cd "$ROOT/.." && pwd)/GC4.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" "$ROOT" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
ROOT = Path(sys.argv[2])
G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests/test_contracts_gc2.py"
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"]
OPENAPI = PYTEST + [f"{T}::test_openapi_names_the_conflict_codes_in_e2_form"]
HEADER = PYTEST + [f"{T}::test_the_review_shape_header_names_the_conflict_codes_in_e2_form"]
SECTION4_4 = ["bash", "scripts/section4-GC4.sh", "--step", "4"]

# (번호, 심는 것, 파일, 옛 글, 새 글, 돌릴 명령, 빨개져야 하는 것(빨간 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "review_put docstring 의 REVIEW_LOCKED 를 옛 글자로", G / "service/apis/greenwash.py",
     "오류: 확정된 실행 409 `REVIEW_LOCKED`(legacyCode `review_locked`) ·", "오류: 확정된 실행 409 `review_locked` ·",
     OPENAPI, ["test_openapi_names_the_conflict_codes_in_e2_form"]),
    (2, "report_get docstring 의 NO_REPORT 자리를 지움", G / "service/apis/greenwash.py",
     "    `NO_REPORT`(legacyCode `no_report`) · 실행·문서가", "    실행·문서가",
     OPENAPI, ["test_openapi_names_the_conflict_codes_in_e2_form"]),
    (3, "review_shapes 머리말의 RUN_NOT_DONE 을 옛 글자로", G / "flows/review_shapes.py",
     "  `RUN_NOT_DONE`(legacyCode `run_not_done`) ·", "  `run_not_done` ·",
     HEADER, ["test_the_review_shape_header_names_the_conflict_codes_in_e2_form"]),
    (4, "GreenwashReviewUpdate docstring 을 옛 글자로", G / "service/apis/greenwash.py",
     "    - 확정된 실행에 PUT 하면 409 `REVIEW_LOCKED`(legacyCode `review_locked`).\n",
     "    - 확정된 실행에 PUT 하면 409 `review_locked`.\n",
     OPENAPI, ["test_openapi_names_the_conflict_codes_in_e2_form"]),
    (5, "README 그린워싱 단락을 되돌림", ROOT / "README.md",
     "확정 뒤 PUT 은 409 `REVIEW_LOCKED`(legacyCode `review_locked`).", "확정 뒤 PUT 은 409 `review_locked`.",
     SECTION4_4, ["[4] 옛 글자 셈 EXIT=1"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem), "GC4_OUT": str(LOGS / "s4")}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR")) or "EXIT=1" in line]


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
