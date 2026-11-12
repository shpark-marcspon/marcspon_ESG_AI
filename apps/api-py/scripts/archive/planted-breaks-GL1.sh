#!/usr/bin/env bash
# 밴드 GL1 의 심은 파손(발주서 band-handoffs/GL1-order.md §3). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GL1.sh
#
# 판정(G1c 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 FAILED·ERROR 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 끝에 심은 파일들의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: GL1_OUT(기본: 워크트리 곁의 GL1.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GL1_OUT:-$(cd "$ROOT/.." && pwd)/GL1.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
PYTEST = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider"]
RESUME = PYTEST + [f"{T}/calc/test_checker_resume.py", f"{T}/flows/test_colab.py"]

# (번호, 심는 것, 파일, 옛 글, 새 글, 돌릴 명령, 빨개져야 하는 것(FAILED/ERROR 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "checker 루프가 done_pages 를 건너뛰지 않음", G / "calc/checker.py",
     "        if page_no in done_pages:\n            continue", "        if page_no in done_pages:\n            pass",
     RESUME, ["test_resume_after_the_second_page_is_the_whole_run", "test_contrast_d_resume_after_the_second_page"]),
    (2, "checker 가 실패한 쪽에서는 checkpoint 를 부르지 않음", G / "calc/checker.py",
     "        if checkpoint is not None:\n",
     '        if checkpoint is not None and all(f["page"] != page_no for f in failed_pages):\n',
     PYTEST + [f"{T}/calc/test_checker_resume.py"], ["test_checkpoint_once_per_page_including_a_failed_one"]),
    (3, "colab 겉이 resume 을 넘기지 않음", G / "flows/colab.py",
     '        resume=cast("dict[str, Any] | None", ctx.resume),\n', "",
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_contrast_d_resume_after_the_second_page"]),
    (4, "colab 겉이 checkpoint 를 넘기지 않음", G / "flows/colab.py",
     "        checkpoint=checkpoint,\n", "",
     PYTEST + [f"{T}/flows/test_colab.py"], ["test_the_judge_reports_progress_page_by_page"]),
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
        code, out = run(cmd, LOGS / f"{num:02d}.log")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
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
