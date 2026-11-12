#!/usr/bin/env bash
# 밴드 DV1f 의 심은 파손(발주서 band-handoffs/DV1f-order.md §3-3, + 러너 몫 P8). 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-DV1f.sh [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= 그 P 가 겨눈 층마다 pytest 가 0 아닌 종료이고 빨개져야
# 할 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다). 업무 층(Postgres)은 --with-containers 일 때만 — 아니면
# 「안 돌림」으로 찍고 그 층은 건너뛴다(순수 층이 잡으면 잡음). 끝에 심은 파일의 sha256 과 git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: DV1f_OUT(기본: 워크트리 곁의 DV1f.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${DV1f_OUT:-$(cd "$ROOT/.." && pwd)/DV1f.out}"
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


SHAPE = Path("esgapi/dataverify/contracts/options_shapes.py")
BIND = Path("esgapi/dataverify/flows/binding_156.py")
TB = "esgapi/dataverify/tests/flows/test_binding_156.py"
TR = "esgapi/dataverify/tests/flows/test_runs_dataverify.py"
REF = TB + "::test_refused_sources_say_one_sentence_without_the_name"
FLOW_SAME = TB + "::test_the_source_does_not_reach_the_flow_inputs_or_versions"
NOT_REACHED = TR + "::test_the_name_reaches_no_request_result_workbook_call_record_or_log"

PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("P1", "source 를 필수로(Q1 나를 어김)",
     [(SHAPE, swap("    source: NotRequired[DataverifySource]\n", "    source: DataverifySource\n"))],
     [(PURE, [TB], {TB + "::test_synthetic_options_are_accepted",
                    TB + "::test_the_old_body_without_a_source_is_still_accepted"})]),
    ("P2", "discriminator 뺌(평평 유니온)",
     [(SHAPE, swap('Field(discriminator="kind")]', "Field()]"))],
     [(PURE, [TB], {f"{REF}[paste-with-name]", f"{REF}[file-without-name]"})]),
    ("P3", "name max_length 255 → 256",
     [(SHAPE, swap("SOURCE_NAME_MAX: Final = 255\n", "SOURCE_NAME_MAX: Final = 256\n"))],
     [(PURE, [TB], {f"{REF}[256-chars]"})]),
    ("P4", "무늬에서 `\\\\` 뺌",
     [(SHAPE, swap('r"^[^/\\\\\\u0000', 'r"^[^/\\u0000'))],
     [(PURE, [TB], {f"{REF}[backslash]"})]),
    ("P5", "_path 가 유니온 꼬리표를 다시 실음",
     [(BIND, swap("        loc = loc[:1] + loc[2:]\n", "        loc = tuple(loc)\n"))],
     [(PURE, [TB], {f"{REF}[paste-with-name]", f"{REF}[file-without-name]", f"{REF}[slash]"})]),
    ("P6", "받기 글 끝에 받은 값(e[\"input\"])을 붙임",
     [(BIND, swap("include_input=False", "include_input=True")),
      (BIND, swap('raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요") from None',
                  'raise RunOptionsRejected(f"옵션 {where}의 값이 맞지 않아요 {first.get(\'input\', \'\')}") from None'))],
     [(PURE, [TB], {f"{REF}[slash]", f"{REF}[bidi-rlo]", f"{REF}[256-chars]"})]),
    ("P7", "inputs() 가 options 째 넘김",
     [(BIND, swap('received = cast("Mapping[str, Any]", options["input"])', 'received = cast("Mapping[str, Any]", options)'))],
     [(PURE, [TB], {f"{FLOW_SAME}[file]", f"{FLOW_SAME}[paste]"}), (BUSINESS, [TR], {NOT_REACHED})]),
    ("P8", "러너 몫: 무늬에서 C1(U+0080~009F)을 뺌 — DEL 만 남음",
     [(SHAPE, swap("\\u007f-\\u009f", "\\u007f"))],
     [(PURE, [TB], {f"{REF}[c1-nel]"})]),
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
                continue
            code, failed, _last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            hit = code != 0 and expected <= failed
            hit_all = hit_all and hit
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {sorted(expected - failed)} — {what}")
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
