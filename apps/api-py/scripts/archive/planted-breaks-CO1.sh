#!/usr/bin/env bash
# 밴드 CO1(MARC-TICK-227: core 검사 빈틈 — AI 설정 받기 MARC-ISSUE-248 · core 업무 이름 목록 MARC-ISSUE-247)의 심은
# 파손(발주서 band-handoffs/CO1-order.md §3-4). 틀은 planted-breaks-AS1.sh·planted-breaks-OP2.sh 그대로다: 하나씩 심고 겨눈
# 시험만 돌린 뒤 원본 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-CO1.sh --commit <1|2> [--with-containers] [--only 1,12]
#   --commit 1 = 1~12(받기 규칙 — 7 은 컨테이너가 있으면 그린워싱 업무 층으로도), 2 = 전부(+ 13~15 이름 검사).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 업무 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍는다(순수 층이 있는 파손은 그대로 센다).
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: CO1_OUT(기본: 워크트리 곁의 CO1.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${CO1_OUT:-$(cd "$ROOT/.." && pwd)/CO1.out}"
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
ONLY: set[str] | None = None
COMMIT = 0
while args:
    if args[0] == "--commit" and len(args) > 1 and args[1] in ("1", "2"):
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")
if COMMIT == 0:
    sys.exit("--commit <1|2> 가 필요하다")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def append(tail: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text + tail

    return plant


RULE = Path("esgapi/core/calc/ai_settings.py")
FLOWS = Path("esgapi/core/flows/__init__.py")
CORE_NAMES = Path("esgapi/core/tests/test_flows_core_names.py")
RUNS_NAMES = Path("esgapi/runs/tests/test_names.py")
TR = "esgapi/core/tests/calc/test_ai_settings.py"
TPM = "esgapi/greenwash/tests/flows/test_prompt_model_e0.py"
TGM = "esgapi/greenwash/tests/service/apis/test_ai_settings_model.py"
TCN = str(CORE_NAMES)
TRN = str(RUNS_NAMES)

# 층: (이름, 명령, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

UNSUPPORTED = (
    "    if given[\"webSearch\"] and not _web_search_available(models, tool_loop=spec.tool_loop):\n"
    "        return ModelSettingRefused(\"ai_model_web_search_unsupported\", \"이 모델은 웹 검색을 쓸 수 없어요\", spec.key)\n"
)
FIXED = (
    "    if given[\"webSearch\"] != spec.default[\"webSearch\"]:\n"
    "        return ModelSettingRefused(\"ai_model_web_search_fixed\", \"웹 검색 여부는 바꿀 수 없어요\", spec.key)\n"
)
UNAVAILABLE = (
    "    try:\n"
    "        models = resolve_route(config, route)\n"
    "    except LlmConfigError:\n"
    "        return ModelSettingRefused(\"ai_model_route_unavailable\", \"지금 쓸 수 없는 모델이에요\", spec.key)\n"
)
TOOL_LOOP = (
    "    if spec.tool_loop and not _loop_route(models):\n"
    "        return ModelSettingRefused(\"ai_model_tool_loop_unsupported\", \"이 단계에서는 쓸 수 없는 모델이에요\", spec.key)\n"
)
VIEW = (
    "    if tuple(model.api_model_id for model in models) != accepted.api_model_ids:\n"
    "        raise LlmConfigError(f\"경로 {accepted.route} 가 받을 때와 다른 모델로 풀린다: {accepted.api_model_ids}\")\n"
)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)], 경계)
PLANTS = [
    ("1", "_check_step 의 tool_loop 갈래 지움", [(RULE, swap(TOOL_LOOP, ""))],
     [(PURE, [TR], {TR + "::test_a_loop_step_refuses_a_route_the_loop_refuses[",
                    TR + "::test_the_tool_loop_rule_is_the_clients["})], 1),
    ("2", "_loop_route 의 len(models) == 1 지움",
     [(RULE, swap("    return len(models) == 1 and all(_passes_tool_loop(model) for model in models)\n",
                  "    return all(_passes_tool_loop(model) for model in models)\n"))],
     [(PURE, [TR], {TR + "::test_the_tool_loop_rule_is_the_clients[mixed-w]",
                    TR + "::test_two_models_turn_web_search_off",
                    TR + "::test_the_web_search_rule_is_the_clients[mixed-w]"})], 1),
    ("3", "_passes_tool_loop 의 TOOL_MODELS 검사 지움",
     [(RULE, swap(" and (model.provider != \"openai\" or model.api_model_id in TOOL_MODELS)\n", "\n"))],
     [(PURE, [TR], {TR + "::test_the_tool_loop_rule_is_the_clients[light-openai]",
                    TR + "::test_the_tool_loop_rule_is_the_clients[light-openai-41]",
                    TR + "::test_a_loop_step_refuses_a_route_the_loop_refuses[light-openai]"})], 1),
    ("4", "출력 상한 > → >=",
     [(RULE, swap("max_output_tokens > _max_output(models):", "max_output_tokens >= _max_output(models):"))],
     [(PURE, [TR], {TR + "::test_the_output_bound_is_the_clients[",
                    TR + "::test_a_rule_refuses_its_case[max-output-at-the-bound]"})], 1),
    ("5", "출력 상한 > _max_output → > _max_output + 1",
     [(RULE, swap("max_output_tokens > _max_output(models):", "max_output_tokens > _max_output(models) + 1:"))],
     [(PURE, [TR], {TR + "::test_the_output_bound_is_the_clients[",
                    TR + "::test_a_rule_refuses_its_case[max-output-above]"})], 1),
    ("6", "_max_output 의 min → max",
     [(RULE, swap("    return min(model.max_output_tokens for model in models)",
                  "    return max(model.max_output_tokens for model in models)"))],
     [(PURE, [TR], {TR + "::test_the_output_bound_is_the_clients[",
                    TR + "::test_one_model_refusing_temperature_turns_the_mixed_route_off"})], 1),
    ("7", "route_unavailable 갈래 지움(LlmConfigError 가 샘)",
     [(RULE, swap(UNAVAILABLE, "    models = resolve_route(config, route)\n"))],
     [(PURE, [TR], {TR + "::test_a_step_route_missing_from_the_config_is_refused",
                    TR + "::test_the_new_rules_keep_their_place"}),
      (BUSINESS, [TGM], {TGM + "::test_a_route_missing_from_the_models_file_is_refused_not_500"})], 1),
    ("8", "web_search_fixed 갈래 지움", [(RULE, swap(FIXED, ""))],
     [(PURE, [TR], {TR + "::test_web_search_is_fixed_to_the_default[loop-turned-off]",
                    TR + "::test_web_search_is_accepted_on_a_loop_step_at_its_default",
                    TR + "::test_the_new_rules_keep_their_place"})], 1),
    ("9", "web_search_fixed 를 unsupported 앞으로", [(RULE, swap(UNSUPPORTED + FIXED, FIXED + UNSUPPORTED))],
     [(PURE, [TR, TPM], {TR + "::test_web_search_is_fixed_to_the_default[plain-turned-on]",
                         TPM + "::test_accept_model_passes_the_as1_codes[web-search]"})], 1),
    ("10", "key 중복 검사 지움(check_model_settings)",
     [(RULE, swap("    명세의 단계 key 가 겹치면 LlmConfigError(도메인 잘못).\"\"\"\n    _check_unique_keys(steps)\n",
                  "    명세의 단계 key 가 겹치면 LlmConfigError(도메인 잘못).\"\"\"\n"))],
     [(PURE, [TR], {TR + "::test_a_repeated_step_key_is_a_config_error"})], 1),
    ("11", "model_setting_view 같음 검사 지움", [(RULE, swap(VIEW, ""))],
     [(PURE, [TR], {TR + "::test_the_view_refuses_a_route_that_moved"})], 1),
    ("12", "unusable_routes 가 tool_loop 를 안 봄",
     [(RULE, swap("            if spec.tool_loop and not _loop_route(models):\n                found.append",
                  "            if False and not _loop_route(models):\n                found.append"))],
     [(PURE, [TR], {TR + "::test_unusable_routes_names_what_the_check_always_refuses"})], 1),
    ("13", "core 제품 파일(core/flows/__init__.py 끝)에 \"esgapi.dataverify\" 글자", [(FLOWS, append('_X = "esgapi.dataverify"\n'))],
     [(PURE, [TCN], {TCN + "::test_core_spells_no_business_module"})], 2),
    ("14", "core 시험의 읽기에서 dataverify 를 뺌",
     [(CORE_NAMES, swap('BUSINESS = forbidden("core-knows-no-module")',
                        'BUSINESS = tuple(n for n in forbidden("core-knows-no-module") if n != "dataverify")'))],
     [(PURE, [TCN], {TCN + "::test_the_list_is_the_import_contracts"})], 2),
    ("15", "runs 시험의 읽기가 계약 가(runs 포함)를 읽음",
     [(RUNS_NAMES, swap('BUSINESS = forbidden("runs-knows-no-module")', 'BUSINESS = forbidden("core-knows-no-module")'))],
     [(PURE, [TRN], {TRN + "::test_the_list_is_the_import_contracts"})], 2),
]
PLANTS = [p for p in PLANTS if p[4] <= COMMIT]
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


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
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, checks, _ in PLANTS:
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
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
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
