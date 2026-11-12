#!/usr/bin/env bash
# 밴드 AS1(MARC-TICK-212: 모듈 공통 AI 설정 꼴 — 프롬프트·모델 설정 꼴·받기 검사·모델 설정 sha)의 심은 파손(발주서
# band-handoffs/AS1-order.md §3-4 + 감독 판단 3 의 P9·F7). 틀은 planted-breaks-G2c2.sh 그대로다: 하나씩 심고 겨눈 시험만
# 돌린 뒤 원본 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 순수 층과 lint-imports 만(컨테이너 없음).
#   사용(어디서든): apps/api-py/scripts/planted-breaks-AS1.sh [--only 1,4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험·계약이 전부 초록. 파손 하나의 「잡음」= 그 파손의 층마다 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). lint 층은 계약 하나만
# (--contract pure-modules) 돌려 0 아닌 종료를 본다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: AS1_OUT(기본: 워크트리 곁의 AS1.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AS1_OUT:-$(cd "$ROOT/.." && pwd)/AS1.out}"
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
ONLY: set[str] | None = None
while args:
    if args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


SHAPES = Path("esgapi/core/contracts/ai_setting_shapes.py")
RULE = Path("esgapi/core/calc/ai_settings.py")
PINNED = Path("esgapi/core/tests/data/ai-setting/ai.model-settings@1.schema.json")
TQ = "esgapi/core/tests/contracts/test_ai_setting_shapes.py"
TR = "esgapi/core/tests/calc/test_ai_settings.py"

# 층: (이름, 명령, 컨테이너가 필요한가 — 이 밴드는 늘 False)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
LINT = ("계약", ["uv", "run", "--frozen", "lint-imports", "--contract", "pure-modules"], False)

ROUTE_FIRST = (
    "    route = given[\"route\"]\n"
    "    if route not in spec.routes:\n"
    "        return ModelSettingRefused(\"ai_model_route_unknown\", \"고를 수 없는 모델이에요\", spec.key)\n"
    "    models = resolve_route(config, route)\n"
    "    temperature = given[\"temperature\"]\n"
    "    if temperature is not None and _temperature_out_of_range(temperature):\n"
    "        return ModelSettingRefused(\"ai_model_temperature_range\", \"temperature 는 0~2 사이 수로 넣어 주세요\", spec.key)\n"
)
TEMPERATURE_FIRST = (
    "    temperature = given[\"temperature\"]\n"
    "    if temperature is not None and _temperature_out_of_range(temperature):\n"
    "        return ModelSettingRefused(\"ai_model_temperature_range\", \"temperature 는 0~2 사이 수로 넣어 주세요\", spec.key)\n"
    "    route = given[\"route\"]\n"
    "    if route not in spec.routes:\n"
    "        return ModelSettingRefused(\"ai_model_route_unknown\", \"고를 수 없는 모델이에요\", spec.key)\n"
    "    models = resolve_route(config, route)\n"
)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", "꼴의 forbid 설정 지움",
     [(SHAPES, swap('FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True)',
                    'FORBID: Final = ConfigDict(use_attribute_docstrings=True)'))],
     [(PURE, [TQ], {TQ + "::test_a_broken_body_is_refused[response-unknown-key]",
                    TQ + "::test_a_broken_body_is_refused[input-unknown-key]"})]),
    ("2", "acceptsTemperature 를 all → any",
     [(RULE, swap("    return all(\n        model.provider not in TEMPERATURE_UNSUPPORTED_PROVIDERS",
                  "    return any(\n        model.provider not in TEMPERATURE_UNSUPPORTED_PROVIDERS"))],
     [(PURE, [TR], {TR + "::test_one_model_refusing_temperature_turns_the_mixed_route_off",
                    TR + "::test_the_temperature_rule_is_the_clients["})]),
    ("3", "TEMPERATURE_MAX import 대신 1.0 박음",
     [(RULE, swap("    TEMPERATURE_MAX,\n", "")),
      (RULE, swap("\n\n@dataclass(frozen=True, slots=True)\nclass AiStepSpec:",
                  "\nTEMPERATURE_MAX = 1.0\n\n\n@dataclass(frozen=True, slots=True)\nclass AiStepSpec:"))],
     [(PURE, [TR], {TR + "::test_the_temperature_bounds[",
                    TR + "::test_the_temperature_rule_is_the_clients[",
                    TR + "::test_the_rule_spells_no_number_and_no_model_name",
                    TR + "::test_the_judge_constants_come_from_the_client"})]),
    ("4", "web_search 판정에서 len(models) == 1 지움",
     [(RULE, swap("tool_loop and len(models) == 1 and all(", "tool_loop and all("))],
     [(PURE, [TR], {TR + "::test_two_models_turn_web_search_off",
                    TR + "::test_the_web_search_rule_is_the_clients[mixed-w]"})]),
    ("5", "받기 차례 맞바꿈(경로 ↔ temperature)",
     [(RULE, swap(ROUTE_FIRST, TEMPERATURE_FIRST))],
     [(PURE, [TR], {TR + "::test_the_route_is_checked_before_the_temperature"})]),
    ("6", "고정 스키마 파일 한 바이트",
     [(PINNED, swap('"title": "Steps"', '"title": "Stepz"'))],
     [(PURE, [TQ], {TQ + "::test_the_json_schema_is_pinned_byte_for_byte[ai.model-settings@1]"})]),
    ("7", "sha 에서 apiModelIds 를 뺌",
     [(RULE, swap('                    "apiModelIds": list(step.api_model_ids),\n', ""))],
     [(PURE, [TR], {TR + "::test_a_moved_route_has_another_sha", TR + "::test_the_sha_is_the_written_json"})]),
    ("8", "core/contracts/ai_setting_shapes.py 에 import django",
     [(SHAPES, swap("from pydantic import ConfigDict", "import django  # noqa: F401\nfrom pydantic import ConfigDict"))],
     [(LINT, [], set())]),
    ("9", "temperature 정규화 지움",
     [(RULE, swap("else float(temperature) + 0.0,", "else temperature,"))],
     [(PURE, [TR], {TR + "::test_zero_temperatures_share_a_sha[",
                    TR + "::test_the_accepted_value_resolves_the_models_and_normalizes"})]),
]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    _, cmd, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def hit(want: str, failed: set[str]) -> bool:
    return any(f.startswith(want) for f in failed) if want.endswith("[") else want in failed


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
seen: set[tuple[str, tuple[str, ...]]] = set()
for p in PLANTS:
    for layer, targets, _ in p[3]:
        key = (layer[0], tuple(targets))
        if key in seen:
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, checks in PLANTS:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, edit in edits:
            text = f.read_text(encoding="utf-8")
            new = edit(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        planted += 1
        if not ok_plant:
            print(f"[{number}] 심기 실패(파일이 바뀌지 않음) — 못 잡은 것으로 센다 — {what}")
            continue
        all_hit = True
        for layer, targets, expected in checks:
            label = f"[{number}/{layer[0]}]"
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            missing = sorted(w for w in expected if not hit(w, failed))
            ok = code != 0 and not missing
            all_hit = all_hit and ok
            print(f"{label} {'잡음' if ok else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what} · {last}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        caught += 1 if all_hit else 0
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
for f in files:
    print(f"  {f} {hashlib.sha256(f.read_bytes()).hexdigest()}")
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
