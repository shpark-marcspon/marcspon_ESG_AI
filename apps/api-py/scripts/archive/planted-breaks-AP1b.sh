#!/usr/bin/env bash
# 밴드 AP1b(MARC-TICK-262: 그린워싱 prompt-model 을 ai.prompt-model@3 로 · versions 공통 열쇠·판 규칙을 core 에서)의 심은
# 파손(발주서 band-handoffs/AP1b-order.md §3-5). 틀은 planted-breaks-G2d.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본
# 바이트로 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 경계 ① = P1~P6·P15, ② = 그것 다시 + P7~P14·P16. 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AP1b.sh --commit <1|2> [--with-containers] [--only P1,P4]
#
# 층(갈래마다 박음): [순] pytest -m "not django_db" · [업] scripts/test-business.sh(컨테이너 — --with-containers 일 때만,
# §4 [10] 과 같은 창) · [웹] apps/web 에서 pnpm exec vitest run src/entities/ai-setting/api/server.test.ts.
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 0 아닌 종료이고 빨개져야 할
# 노드가 전부 FAILED(노드 끝이 `[` 면 그 매개변수 묶음 하나라도 — 웹 층은 vitest 의 빨간 시험 이름에 그 글이 듦). 돌린 층이
# 하나도 없는 파손은 잡은 수·심은 수에 넣지 않는다. 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다
# (FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>. 산출물: AP1B_OUT(기본: 워크트리 곁의 AP1b.out)/planted/.
# 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AP1B_OUT:-$(cd "$ROOT/.." && pwd)/AP1b.out}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
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
CONTAINERS = False
while args:
    if args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    elif args[0] == "--commit" and len(args) > 1:
        COMMIT, args = int(args[1]), args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
BIND = G / "flows/binding_e0.py"
PM = G / "flows/prompt_model_e0.py"
SVC = G / "service/services/ai_settings.py"
SEL = G / "service/selectors/ai_settings.py"
TV = f"{T}/flows/test_binding_e0_versions_ap1b.py"
TP = f"{T}/flows/test_prompt_model_e0.py"
T3 = f"{T}/flows/test_prompt_model_e0_v3.py"
TR = f"{T}/service/services/test_ai_settings_rules.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가, 도는 자리)
PURE = ("순", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False, ".")
BUSINESS = ("업", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True, ".")
WEB = ("웹", ["pnpm", "exec", "vitest", "run"], False, "../web")

DEFAULT_COMMON = "**ai_versions(setting_id=None, model=self._defaults(), prompts=None)}"
SAVED_COMMON = "versions = {**built, **ai_versions(setting_id=applied.id, model=model, prompts=texts)}"

# (경계, 번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS_1 = [
    (1, "P1", "기본 판 갈래에 v3 의 저장 글(accepted_saved())을 넘김 — 열쇠 promptsSha256 이 붙음",
     [(BIND, swap(DEFAULT_COMMON,
                  "**ai_versions(setting_id=None, model=self._defaults(), prompts=__import__("
                  "'esgapi.greenwash.tests.flows.ap1b_baseline', fromlist=['_']).accepted_saved())}"))],
     [(PURE, [TV], {TV + "::test_the_versions_are_the_baseline_to_the_byte[v1-default]",
                    TV + "::test_a_new_run_builds_the_same_inputs[v1-default]"})]),
    (1, "P2", "저장 글 갈래의 evalPromptSha256 덮기 지움",
     [(BIND, swap('            versions["evalPromptSha256"] = sha256_text(colab.pack_from(texts).eval_system_prompt)\n',
                  "            pass\n"))],
     [(PURE, [TV], {TV + "::test_the_versions_are_the_baseline_to_the_byte[v3-saved-text]",
                    TV + "::test_a_new_run_builds_the_same_inputs[v3-saved-text]"})]),
    (1, "P3", "termsSha256 줄 지움",
     [(BIND, swap('        return {**versions, "termsSha256": terms_sha256(used_terms(accepted))}\n',
                  "        return versions\n"))],
     [(PURE, [TV], {TV + "::test_the_versions_are_the_baseline_to_the_byte[v4-saved-terms]",
                    TV + "::test_a_new_run_builds_the_same_inputs[v4-saved-terms]"})]),
    (1, "P4", "저장 판 versions 의 열쇠 차례를 {**ai_versions(…), **built} 로",
     [(BIND, swap(SAVED_COMMON, "versions = {**ai_versions(setting_id=applied.id, model=model, prompts=texts), **built}"))],
     [(PURE, [TV], {TV + "::test_the_versions_are_the_baseline_to_the_byte[v2-saved-code-text]"})]),
    (1, "P5", "next_name 별칭을 lambda n: \"v1\" 로",
     [(SVC, swap("from esgapi.core.calc.ai_settings import next_version_name as next_name\n",
                 'next_name = lambda names: "v1"  # noqa: E731\n'))],
     [(PURE, [TR], {TR + "::test_the_next_name_is_the_largest_plus_one[second]"})]),
    (1, "P6", "MODULE_SPEC 묶음 model_slots=()",
     [(PM, swap("prompt_keys=tuple(colab.PROMPT_IDS), model_slots=(JUDGE.key,)",
                "prompt_keys=tuple(colab.PROMPT_IDS), model_slots=()"))],
     [(PURE, [TP], {TP + "::test_the_declarations_layout_is_the_workers"})]),
    (1, "P15", "러너 몫: status_of 별칭이 applied_at 을 버림(past → testing)",
     [(SEL, swap("status_of: Final = version_status\n",
                 "status_of: Final = lambda applied, applied_at: version_status(applied, None)  # noqa: E731\n"))],
     [(PURE, [TR, T3], {TR + "::test_the_status_is_counted_from_the_two_cells[",
                        T3 + "::test_the_module_version_rules_are_core_aliases"})]),
]
ACT = G / "service/actions/ai_settings.py"
SRV = Path("../web/src/entities/ai-setting/api/server.ts")
TA = f"{T}/service/apis/test_ai_settings_prompt_model.py"
TW = "src/entities/ai-setting/api/server.test.ts"
COMPOSE_AT = "    return compose(\n        config,\n        MODULE_SPEC,\n"
PLANTS_2 = [
    (2, "P7", "prompt_model 이 칸(entries)을 뒤집어 넘김 — compose 의 칸 차례 대조가 LlmConfigError",
     [(PM, swap("prompts={JUDGE.key: entries},", "prompts={JUDGE.key: entries[::-1]},"))],
     [(PURE, [T3, TP], {T3 + "::test_the_v3_body_means_the_v2_body[",
                        TP + "::test_the_default_board_passes_the_as1_shape_strictly"})]),
    (2, "P8", "compose 앞에 BASE 꼴 route_choice 를 명세 routes 전부에(빠진 경로 → LlmConfigError)",
     [(PM, swap(COMPOSE_AT, "    [__import__('esgapi.core.calc.ai_settings', fromlist=['_']).route_choice(config, r, "
                            "tool_loop=False) for r in JUDGE.routes]\n" + COMPOSE_AT))],
     [(PURE, [TP], {TP + "::test_a_route_missing_from_the_config_is_unavailable_not_an_error"})]),
    (2, "P9", "fixed=[]",
     [(PM, swap("        fixed=fixed_groups(),\n", "        fixed=[],\n"))],
     [(PURE, [T3], {T3 + "::test_the_v3_body_means_the_v2_body["})]),
    (2, "P10", "editable.prompts 에 EDITABLE_PROMPTS 대신 editable_model",
     [(PM, swap('editable={"prompts": EDITABLE_PROMPTS, "model": editable_model},',
                'editable={"prompts": editable_model, "model": editable_model},'))],
     [(PURE, [TP], {TP + "::test_editable_is_the_module_prompts_and_the_given_model"})]),
    (2, "P11", "fromV3 가 칸 둘도 받음",
     [(SRV, swap("if (models.length !== 1 || promptGroups.length !== 1) return null;",
                 "if (promptGroups.length !== 1) return null;"))],
     [(WEB, [TW], {"칸 둘·묶음 둘"})]),
    (2, "P12", "isPromptModel3 의 unavailableRoutes 검사 지움",
     [(SRV, swap("all((value as Shape).unavailableRoutes, isString)", "true"))],
     [(WEB, [TW], {"칸 둘·묶음 둘"})]),
    (2, "P13", "reader 분기에서 @3 → null",
     [(SRV, swap(": isPromptModel3(data) ? fromV3(data)", ": isPromptModel3(data) ? null"))],
     [(WEB, [TW], {"reader: @3 답"})]),
    (2, "P14", "actions 저장 판이 모델 거절을 무시하고 기본값으로",
     [(ACT, swap("    if isinstance(model, ModelSettingRefused):\n        return services.SettingUnusable(model.code, found.name)\n",
                 "    if isinstance(model, ModelSettingRefused):\n        model = defaults(config, source.steps())\n"))],
     [(BUSINESS, [TA], {TA + "::test_a_saved_board_names_it_too_but_one_that_chose_it_is_409"})]),
    (2, "P16", "러너 몫: editable.model 이 넘긴 값을 버리고 늘 True",
     [(PM, swap('editable={"prompts": EDITABLE_PROMPTS, "model": editable_model},',
                'editable={"prompts": EDITABLE_PROMPTS, "model": True},'))],
     [(PURE, [TP], {TP + "::test_editable_is_the_module_prompts_and_the_given_model"})]),
]
PLANTS = [p[1:] for p in (*PLANTS_1, *PLANTS_2) if p[0] <= COMMIT and (ONLY is None or p[1] in ONLY)]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def run(layer, targets: list[str], log: Path) -> tuple[int, set[str], str]:
    name, cmd, _, cwd = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env, cwd=cwd)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    if name == "웹":  # vitest 의 빨간 줄(× …) — 기대는 그 줄에 든 글
        failed = set(re.findall(r"^ *(?:×|✗|FAIL) (.+)$", text, flags=re.M))
    else:
        failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


def hit(want: str, failed: set[str]) -> bool:
    if "::" not in want:  # 웹 층 — 빨간 시험 이름에 든 글
        return any(want in f for f in failed)
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
        print(f"P0 [{layer[0]}] {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, checks in PLANTS:
    layers = [c for c in checks if runnable(c[0])]
    if not layers:
        print(f"{number} 안 돌림(컨테이너 층뿐 — --with-containers 없음) — {what}")
        continue
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, edit in edits:
            text = f.read_text(encoding="utf-8")
            new = edit(text)
            if new is None or new == text:
                print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        planted += 1
        if not ok_plant:
            continue
        all_hit = True
        for i, (layer, targets, expected) in enumerate(layers):
            code, failed, _ = run(layer, targets, LOGS / f"{number}-{layer[0]}-{i}.log")
            missing = sorted(e for e in expected if not hit(e, failed))
            layer_hit = code != 0 and not missing
            all_hit = all_hit and layer_hit
            print(f"{number} [{layer[0]}] {'잡음' if layer_hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} "
                  f"빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        caught += all_hit
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
