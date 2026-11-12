#!/usr/bin/env bash
# 밴드 DV1i 의 심은 파손(발주서 band-handoffs/DV1i-order.md §3 D1~D3, + 러너 몫 D4). 틀은 planted-breaks-DV1h.sh 그대로다:
# 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-DV1i.sh [--with-containers] [--only D1,D3]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 D 의 「잡음」= 그 D 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘. 빨개져야 할 묶음이 None 인 층은 거꾸로 초록이어야 잡음이다(D3 — 거짓 빨강 없음).
# 업무 층(Postgres)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 그 D 는 못 잡음으로 센다. 끝에 심은 파일의
# sha256 과 git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: DV1i_OUT(기본: 워크트리 곁의
# DV1i.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${DV1i_OUT:-$(cd "$ROOT/.." && pwd)/DV1i.out}"
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
ONLY = None
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


TR = "esgapi/dataverify/tests/flows/test_runs_dataverify.py"
TR_FILE = Path(TR)
TAIL_HEX = TR + "::test_the_name_tail_is_not_hex"
TC = "esgapi/config/tests/test_api_component_names.py"
TC_FILE = Path(TC)
NAMES = TC + "::test_no_component_name_has_two_definitions"
DV_SETTINGS = Path("esgapi/dataverify/service/apis/ai_settings.py")


def rename(old: str, new: str) -> Callable[[str], str | None]:
    """old 를 전부 new 로(하나도 없으면 심기 실패)."""

    def plant(text: str) -> str | None:
        return text.replace(old, new) if old in text else None

    return plant


PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음 | None = 초록이어야 함)])
PLANTS = [
    ("D1", "꼬리에 「-」 를 품은 16진 글자(a-b1)",
     [(TR_FILE, swap('TAIL = "zq7x"\n', 'TAIL = "a-b1"\n'))],
     [(BUSINESS, [TR], {TAIL_HEX})]),
    ("D2", "데이터 검증의 적용 본문 이름을 그린워싱 것과 같게(정의는 다름 — docstring)",
     [(DV_SETTINGS, rename("DataverifyAiSettingApply", "GreenwashAiSettingApply"))],
     [(PURE, [TC], {NAMES})]),
    ("D3", "D2 + docstring 까지 그린워싱 것과 같게(같은 이름·같은 정의)",
     [(DV_SETTINGS, rename("DataverifyAiSettingApply", "GreenwashAiSettingApply")),
      (DV_SETTINGS, swap("기본 판(엔진 코드 값)으로", "기본 판(코랩 원본)으로"))],
     [(PURE, [TC], None)]),
    ("D4", "러너 몫: 감싸기가 한 번에 온 정의 가운데 첫 것만 모음(분모가 문다)",
     [(TC_FILE, swap("        for name, definition in definitions.items():\n",
                     "        for name, definition in list(definitions.items())[:1]:\n"))],
     [(PURE, [TC], {NAMES})]),
]
PLANTS = [p for p in PLANTS if ONLY is None or p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    done = subprocess.run([*layer[1], *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (.+?)(?: - .*)?$", text, flags=re.M))
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
        code, _failed, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"P0 {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, checks) -> bool:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        hit_all = True
        for layer, targets, expected in checks:
            label = f"{number}/{layer[0]}"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                hit_all = False
                continue
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            if expected is None:
                hit = code == 0 and not failed
                print(f"{label} {'잡음(초록)' if hit else '못 잡음(거짓 빨강)'} EXIT={code} 빨강 {len(failed)} {last} — {what}")
            else:
                hit = code != 0 and expected <= failed
                print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
            hit_all = hit_all and hit
            for node in sorted(failed):
                print(f"    FAILED {node}")
        return hit_all
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, what, edits, checks in PLANTS:
    planted += 1
    result = plant_and_check(number, what, edits, checks)
    caught += 1 if result else 0
    print(f"{number} => {'잡음' if result else '못 잡음'}")

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
