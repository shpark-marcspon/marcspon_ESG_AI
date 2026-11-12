#!/usr/bin/env bash
# 밴드 GTE1 의 심은 파손(발주서 band-handoffs/GTE1-order.md §4-7). 하나씩 심고 그 단계만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash·mv 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-GTE1.sh
#
# 판정(GM1 꼴): 0번(아무것도 안 심음)은 쓰는 단계가 전부 초록. 「잡음」= section4-GTE1.sh --step 2 의 종료 코드 ≠ 0 이고
# 출력에 「[2] … EXIT=1」 줄이 있으며, 그 파손이 겨눈 시험이 FAILED 로 찍힘. 심을 때마다 파일이 실제로 바뀌었는지 먼저
# 본다. 끝에 심은 파일의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: GTE1_OUT(기본: 워크트리 곁의 GTE1.out)/planted/.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${GTE1_OUT:-$(cd "$ROOT/.." && pwd)/GTE1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
ADAPTERS = Path("esgapi/greenwash/flows/adapters.py")
A = "test_contrast_b_through_core_llm_is_the_same"
B = "test_the_default_route_is_gpt41_mini_alone_in_the_real_config"


def step(n: int) -> list[str]:
    return ["bash", "scripts/section4-GTE1.sh", "--step", str(n)]


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


# (번호, 심는 것, 파일, 심는 함수, 돌릴 단계, 빨개져야 할 시험)
PLANTS = [
    (1, "temperature 를 int 0 으로", ADAPTERS,
     swap("            temperature=checker_mod.TEMPERATURE,\n", "            temperature=0,\n"), 2, A),
    (2, "기본 경로를 light-openai 로", ADAPTERS,
     swap('CHAT_ROUTE: Final = "light-openai-41"', 'CHAT_ROUTE: Final = "light-openai"'), 2, B),
    (3, "temperature= 를 지움", ADAPTERS,
     swap("            temperature=checker_mod.TEMPERATURE,\n", ""), 2, A),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem), "GTE1_OUT": str(LOGS / "s4")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


steps = ",".join(str(n) for n in sorted({p[4] for p in PLANTS}))
code, _ = run(["bash", "scripts/section4-GTE1.sh", "--step", steps], LOGS / "00.log")
print(f"[0] 아무것도 안 심음: {'전부 초록' if code == 0 else '빨강이 있다'} (단계 {steps})")
zero_ok = code == 0

caught = 0
for num, what, path, plant, n, target in PLANTS:
    original = path.read_bytes()
    planted = plant(original.decode("utf-8"))
    if planted is None:
        print(f"[{num}] {what}: 심을 자리를 못 찾음 — 못 잡은 것으로 센다")
        continue
    (LOGS / "s4" / "section4" / "pytest-new.log").unlink(missing_ok=True)  # 앞 파손의 기록을 보지 않게
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
    s4log = LOGS / "s4" / "section4" / "pytest-new.log"
    hit = s4log.exists() and any(
        line.startswith("FAILED ") and f"::{target}" in line for line in s4log.read_text(encoding="utf-8").splitlines()
    )
    ok = code != 0 and bool(red) and hit
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (§4-{n}, 종료 {code}, "
          f"{red[0] if red else '빨간 줄 없음'}, {target} {'FAILED' if hit else '빨갛지 않음'})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
