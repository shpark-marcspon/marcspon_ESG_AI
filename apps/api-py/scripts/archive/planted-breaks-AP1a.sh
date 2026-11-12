#!/usr/bin/env bash
# 밴드 AP1a 의 심은 파손(발주서 band-handoffs/AP1a-order.md §3-6, + 러너 몫 P15). 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트를 되쓴다(git checkout·restore·stash 를 쓰지 않는다 — planted-breaks-DV1e.sh 꼴). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AP1a.sh [--commit <n>] [--only P1,P4]
#   --commit n 은 경계 n 까지의 몫만(① P1~P11·P15, ② +P12~P14). 기본 2.
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 한 P 의 「잡음」= pytest 가 0 아닌 종료이고 기대 노드(앞머리)마다
# 그것으로 시작하는 FAILED 가 하나 이상. 전부 순수 층(not django_db) — 컨테이너를 띄우지 않는다. 끝에 심은 파일의 sha256 과
# git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=. 산출물: AP1a_OUT(기본: 워크트리 곁의
# AP1a.out)/planted/. 공급사를 부르지 않는다.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AP1a_OUT:-$(cd "$ROOT/.." && pwd)/AP1a.out}"
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
ONLY = None
COMMIT = 2
while args:
    if args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    elif args[0] == "--commit" and len(args) > 1:
        COMMIT, args = int(args[1]), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


CALC = Path("esgapi/core/calc/ai_settings.py")
SHAPES = Path("esgapi/core/contracts/ai_setting_shapes.py")
TP = "esgapi/core/tests/calc/test_ai_settings_parts.py"
TF = "esgapi/core/tests/calc/test_ai_settings_fake_module.py"
TV = "esgapi/core/tests/contracts/test_ai_setting_shapes_v3.py"
TG = "esgapi/greenwash/tests/flows/test_prompt_model_e0_v3.py"
PURE = ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"]

# (경계, 번호, 설명, [(파일, 심는 함수)], 겨눔 시험 파일들, 빨개져야 할 노드 앞머리)
PLANTS = [
    (1, "P1", "check_module 의 모르는 modelSlots 검사 지움",
     [(CALC, swap("if unknown := [slot for slot in group.model_slots if slot not in slots]:",
                  "if unknown := [slot for slot in group.model_slots if slot not in slots and not slots]:"))],
     [TP, TF], {f"{TP}::test_a_bad_module_is_a_config_error[unknown-slot]", f"{TF}::test_the_fake_module_is_declared"}),
    (1, "P2", "칸 key 겹침 검사 지움",
     [(CALC, swap("    if repeated := _repeated(slots):", "    if repeated := _repeated([]):"))],
     [TP], {f"{TP}::test_a_bad_module_is_a_config_error[slot-key-twice]"}),
    (1, "P3", "compose 의 묶음 칸 차례 대조 지움",
     [(CALC, swap('    if [entry["key"] for entry in entries] != list(group.prompt_keys):',
                  '    if not entries:'))],
     [TP], {f"{TP}::test_compose_refuses_prompts_off_the_declaration[prompt-order]",
            f"{TP}::test_compose_refuses_prompts_off_the_declaration[prompt-missing]"}),
    (1, "P4", "route_choices 가 고리를 못 지나는 경로를 choices 에 둠",
     [(CALC, swap("        if slot.tool_loop and not _loop_route(models):\n            unavailable.append(route)\n"
                  "            continue\n",
                  "        if slot.tool_loop and not _loop_route(models):\n            unavailable.append(route)\n"))],
     [TP], {f"{TP}::test_a_route_the_loop_refuses_is_named_too",
            f"{TP}::test_route_choices_split_like_unusable_routes"}),
    (1, "P5", "unavailableRoutes 늘 []",
     [(CALC, swap('"unavailableRoutes": unavailable,', '"unavailableRoutes": [],'))],
     [TP], {f"{TP}::test_a_missing_route_is_named_not_a_server_error", f"{TP}::test_a_route_the_loop_refuses_is_named_too"}),
    (1, "P6", "model_settings_sha256 앞바이트 열쇠 steps → slots",
     [(CALC, swap('    return sha256_json(\n        {\n            "steps": [\n                {\n                    "key": step.key,',
                  '    return sha256_json(\n        {\n            "slots": [\n                {\n                    "key": step.key,'))],
     [TP], {f"{TP}::test_an_old_stored_row_reads_with_the_new_names", f"{TP}::test_the_old_default_reads_with_the_new_names"}),
    (1, "P7", "prompts_sha256 차례 뒤집음",
     [(CALC, swap("[[step.key, p.key, p.text] for step", "[[p.text, p.key, step.key] for step"))],
     [TP], {f"{TP}::test_an_old_stored_row_reads_with_the_new_names"}),
    (1, "P8", "AiModelSlot.routeChoices 의 min_length 지움",
     [(SHAPES, swap('    model: AiModelSetting\n    routeChoices: Annotated[list[AiRouteChoice], Field(min_length=1)]\n'
                    '    """지금 쓸 수 있는 경로만',
                    '    model: AiModelSetting\n    routeChoices: list[AiRouteChoice]\n    """지금 쓸 수 있는 경로만'))],
     [TV], {f"{TV}::test_the_v3_schema_is_pinned_byte_for_byte", f"{TV}::test_a_broken_v3_body_is_refused[route-choices-empty]"}),
    (1, "P9", "AiRouteChoice docstring 한 글자",
     [(SHAPES, swap('"""그 단계에 고를 수 있는 경로 하나와 그 능력."""', '"""그 단계에 고를 수 있는 경로 하나와 그 능력!"""'))],
     [TV], {f"{TV}::test_the_old_shapes_are_the_base_bytes[ai.prompt-model@2]",
            f"{TV}::test_the_v3_schema_is_pinned_byte_for_byte"}),
    (1, "P10", "next_version_name 이 v01 을 셈",
     [(CALC, swap('_VERSION_NUMBER = re.compile(r"v([1-9][0-9]*)")', '_VERSION_NUMBER = re.compile(r"v([0-9]+)")'))],
     [TP], {f"{TP}::test_the_next_version_name"}),
    (1, "P11", "ai_versions 가 prompts None 에도 promptsSha256",
     [(CALC, swap('    if prompts is not None:\n        versions["promptsSha256"] = prompts_sha256(prompts)',
                  '    versions["promptsSha256"] = None if prompts is None else prompts_sha256(prompts)'))],
     [TP], {f"{TP}::test_ai_versions_carries_the_common_keys"}),
    (1, "P15", "러너 몫: compose 의 prompts 열쇠 대조를 한쪽(빠짐)만 — 더한 열쇠를 지나보냄",
     [(CALC, swap("    if set(prompts) != {group.key for group in spec.groups}:",
                  "    if not {group.key for group in spec.groups} <= set(prompts):"))],
     [TP], {f"{TP}::test_compose_refuses_prompts_off_the_declaration[extra-group]"}),
    (2, "P12", "compose 의 modelSettingsSha256 을 prompts_sha256 로",
     [(CALC, swap('"modelSettingsSha256": model_settings_sha256(model),',
                  '"modelSettingsSha256": prompts_sha256(AcceptedPrompts(steps=())),'))],
     [TG], {f"{TG}::test_the_v3_body_means_the_v2_body"}),
    (2, "P13", "묶음 modelSlots 를 [] 로",
     [(CALC, swap('"modelSlots": list(group.model_slots),', '"modelSlots": [],'))],
     [TG], {f"{TG}::test_the_v3_body_means_the_v2_body"}),
    (2, "P14", "version_status 의 past·testing 뒤바꿈",
     [(CALC, swap('return "past" if applied_at is not None else "testing"',
                  'return "testing" if applied_at is not None else "past"'))],
     [TG], {f"{TG}::test_the_version_rules_are_the_modules"}),
]
PLANTS = [p[1:] for p in PLANTS if p[0] <= COMMIT and (ONLY is None or p[1] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def run(targets: list[str], log: Path) -> tuple[int, set[str], str]:
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    done = subprocess.run([*PURE, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (.+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

zero_ok = True
for targets in sorted({tuple(p[3]) for p in PLANTS}):
    code, _failed, last = run(list(targets), LOGS / f"P0-{len(targets)}-{abs(hash(targets)) % 1000}.log")
    print(f"P0 {' '.join(targets)} 초록: EXIT={code} {last}")
    zero_ok = zero_ok and code == 0


def plant_and_check(number: str, what: str, edits, targets: list[str], expected: set[str]) -> bool:
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                return False
            f.write_text(new, encoding="utf-8")
        code, failed, _last = run(targets, LOGS / f"{number}.log")
        missing = sorted(e for e in expected if not any(node.startswith(e) for node in failed))
        hit = code != 0 and not missing
        print(f"{number} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
        for node in sorted(failed):
            print(f"    FAILED {node}")
        return hit
    finally:
        for f, data in originals.items():
            f.write_bytes(data)


caught = planted = 0
for number, what, edits, targets, expected in PLANTS:
    planted += 1
    caught += plant_and_check(number, what, edits, targets, expected)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
