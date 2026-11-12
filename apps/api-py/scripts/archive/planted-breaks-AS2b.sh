#!/usr/bin/env bash
# 밴드 AS2b(MARC-TICK-216: 그린워싱 AI 설정 판마다 모델 설정 저장·조회·적용)의 심은 파손(발주서
# band-handoffs/AS2b-order.md §3-5). 틀은 planted-breaks-AS2a.sh 그대로다: 하나씩 심고 겨눈 시험만 돌린 뒤 원본 바이트로
# 되쓴다(git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AS2b.sh --commit <1|2> [--with-containers] [--only 1,4]
#   --commit 1 = P1~P8(저장·조회), --commit 2 = P1~P17(+ 적용, P17 = 검증 2 B1).
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 파손 하나의 「잡음」= 그 파손의 돌린 층마다 pytest 가 0 아닌 종료이고,
# 빨개져야 할 노드가 전부 FAILED 로 찍힘(노드 이름 끝이 `[` 면 그 매개변수 묶음 하나라도). 파손 하나 = 하나로 센다.
# 업무 층(컨테이너)은 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고, 돌린 층이 하나도 없는 파손은 잡은 수·심은
# 수에 넣지 않는다.
# 끝에 심은 파일의 sha256·git status 가 시작과 같은지 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은>/<심은>.
# 산출물: AS2B_OUT(기본: 워크트리 곁의 AS2b.out)/planted/. 공급사를 부르지 않는다(env -u 키). macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AS2B_OUT:-$(cd "$ROOT/.." && pwd)/AS2b.out}"
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


G = Path("esgapi/greenwash")
T = "esgapi/greenwash/tests"
PM = G / "flows/prompt_model_e0.py"
MIG = G / "migrations/0003_ai_settings_model_settings.py"
ACT = G / "service/actions/ai_settings.py"
SEL = G / "service/selectors/ai_settings.py"
SVC = G / "service/services/ai_settings.py"
SHAPES = Path("esgapi/core/contracts/ai_setting_shapes.py")
TP = f"{T}/flows/test_prompt_model_e0.py"
TAM = f"{T}/service/apis/test_ai_settings_model.py"
TSEL = f"{T}/service/selectors/test_ai_settings.py"
TCORE = "esgapi/core/tests/contracts/test_ai_setting_shapes.py"

# 층: (이름, 명령 앞부분, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db"], False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], True)

# (번호, 설명, [(파일, 심는 함수)], [(층, 겨눔 시험 파일들, 빨개져야 할 노드 묶음)])
PLANTS = [
    ("1", "create 가 받은 값 대신 코드 값을 저장(입력 무시)",
     [(SVC, swap("    stored = to_input(model)\n", "    stored = to_input(defaults(config, models.steps()))\n"))],
     [(BUSINESS, [TAM], {TAM + "::test_a_model_only_change_is_a_new_version"})]),
    ("2", "create 가 모델 거절을 무시하고 저장",
     [(SVC, swap("        if isinstance(found, ModelSettingRefused):\n            return ModelRefused(found.code, found.message)\n",
                 "        if isinstance(found, ModelSettingRefused):\n            found = defaults(config, models.steps())\n"))],
     [(BUSINESS, [TAM], {TAM + "::test_a_refused_model_is_400_and_writes_nothing[",
                         TAM + "::test_a_non_finite_temperature_is_400["})]),
    ("3", "이행 상수의 1300 → 1301",
     [(MIG, swap('"maxOutputTokens": 1300}', '"maxOutputTokens": 1301}'))],
     [(PURE, [TP], {TP + "::test_the_migration_constant_is_the_code_value"})]),
    ("4", "apply 의 모델 다시 받기 지움",
     [(SVC, swap("        if isinstance(model, ModelSettingRefused):\n            return SettingUnusable(model.code, found.name)\n", ""))],
     [(BUSINESS, [TAM], {TAM + "::test_a_board_whose_model_is_no_longer_taken_cannot_be_applied"})]),
    ("5", "prompt-model 이 저장 값 대신 defaults",
     [(ACT, swap("            model=model,\n", "            model=defaults(config, source.steps()),\n"))],
     [(BUSINESS, [TAM], {TAM + "::test_prompt_model_shows_the_stored_model"})]),
    ("6", "HEAD_FIELDS 에 model_settings 더함",
     [(SEL, swap('    "applied_at",\n)\n', '    "applied_at",\n    "model_settings",\n)\n'))],
     [(BUSINESS, [TSEL], {TSEL + "::test_the_list_and_the_lock_never_read_the_model_settings"})]),
    ("7", "EDITABLE_MODEL = False",
     [(PM, swap("EDITABLE_MODEL: Final = True\n", "EDITABLE_MODEL: Final = False\n"))],
     [(PURE, [TP], {TP + "::test_the_default_board_passes_the_as1_shape_strictly"}),
      (BUSINESS, [TAM], {TAM + "::test_prompt_model_shows_the_stored_model"})]),
    ("8", "core 입력 꼴을 FORBID 로 되돌림(strict 지움)",
     [(SHAPES, swap("@with_config(STRICT_FORBID)\nclass AiModelStepIn", "@with_config(FORBID)\nclass AiModelStepIn")),
      (SHAPES, swap("@with_config(STRICT_FORBID)\nclass AiModelSettingsIn", "@with_config(FORBID)\nclass AiModelSettingsIn"))],
     [(PURE, [TCORE], {TCORE + "::test_a_strict_body_keeps_the_input_shapes_strict"}),
      (BUSINESS, [TAM], {TAM + "::test_a_bad_model_shape_is_422[max-output-bool]",
                         TAM + "::test_a_bad_model_shape_is_422[max-output-text]",
                         TAM + "::test_a_bad_model_shape_is_422[temperature-bool]",
                         TAM + "::test_a_bad_model_shape_is_422[web-search-int]"})]),
]
BIND = G / "flows/binding_e0.py"
COLAB = G / "flows/colab_e0.py"
TBT = f"{T}/flows/test_bridge_temperature.py"
TBS = f"{T}/flows/test_binding_e0_settings.py"
TSR = f"{T}/flows/test_binding_e0_settings_runs.py"
RUN_MODEL = TSR + "::test_a_run_on_a_model_setting_calls_that_model"
MOVED = TSR + "::test_a_run_whose_model_moved_after_it_was_made_fails"
PURE_MOVED = TBS + "::test_inputs_with_a_model_that_moved_fails"
SAVED_SHA = '        return {**built, "aiSettingId": applied.id, "modelSettingsSha256": model_settings_sha256(model)}\n'
SAVED_CHECK = (
    '        if model_settings_sha256(model) != versions["modelSettingsSha256"]:\n'
    '            raise AiSettingMismatch(f"AI 설정 판 {setting_id} 의 모델 설정이 실행을 만들 때와 다르다")\n'
)
DEFAULT_CHECK = (
    '            if checks_model and model_settings_sha256(self._defaults()) != versions["modelSettingsSha256"]:\n'
    '                raise AiSettingMismatch("기본 판의 모델 설정이 실행을 만들 때와 다르다")\n'
)
REFUSED = (
    "            raise AiSettingMismatch(\n"
    '                f"AI 설정 판 {setting_id} 의 모델 설정을 지금 받기로 다시 받을 수 없다: {model.code}"\n'
    "            )\n"
)
SECOND = [
    ("9", "with_model 이 temperature 를 버림(상수)",
     [(COLAB, swap("            temperature=temperature,\n", "            temperature=TEMPERATURE,\n"))],
     [(PURE, [TBT], {TBT + "::test_with_model_sends_the_route_temperature_and_cap"}),
      (BUSINESS, [TSR], {RUN_MODEL})]),
    ("10", "_scan_pages 의 with_model 끼움 지움",
     [(COLAB, swap("        llm = llm.with_model(inputs.model.route, inputs.model.temperature, inputs.model.max_output_tokens)\n",
                   "        pass\n"))],
     [(BUSINESS, [TSR], {RUN_MODEL})]),
    ("11", "versions_with 의 modelSettingsSha256 지움(저장 판)",
     [(BIND, swap(SAVED_SHA, '        return {**built, "aiSettingId": applied.id}\n'))],
     [(PURE, [TBS], {TBS + "::test_versions_with_carry_the_model_settings_sha"}),
      (BUSINESS, [TSR], {MOVED + "[pair]", RUN_MODEL})]),
    ("12", "inputs_with 의 sha 대조 지움(저장 판·기본 판)",
     [(BIND, swap(SAVED_CHECK, "")), (BIND, swap(DEFAULT_CHECK, ""))],
     [(PURE, [TBS], {PURE_MOVED + "[pair]", PURE_MOVED + "[default-temperature]"}),
      (BUSINESS, [TSR], {MOVED + "[pair]", TSR + "::test_a_default_run_whose_default_model_moved_fails"})]),
    ("13", "sha 를 받은 값 대신 저장 원문으로 셈",
     [(BIND, swap(SAVED_SHA, '        return {**built, "aiSettingId": applied.id, "modelSettingsSha256": sha256_json(applied.model_settings)}\n')),
      (BIND, swap('        if model_settings_sha256(model) != versions["modelSettingsSha256"]:\n',
                  '        if sha256_json(found.model_settings) != versions["modelSettingsSha256"]:\n')),
      (BIND, swap("from esgapi.core.llm.embedding import ClientEmbeddingPort\n",
                  "from esgapi.core.llm.embedding import ClientEmbeddingPort\nfrom esgapi.core.llm.log import sha256_json\n"))],
     [(PURE, [TBS], {PURE_MOVED + "[pair]", TBS + "::test_versions_with_carry_the_model_settings_sha"}),
      (BUSINESS, [TSR], {MOVED + "[pair]"})]),
    ("14", "versions_with 의 모델 거절을 무시",
     [(BIND, swap("        if isinstance(model, ModelSettingRefused):\n            raise unusable\n",
                  "        if isinstance(model, ModelSettingRefused):\n            model = self._defaults()\n"))],
     [(BUSINESS, [TSR], {TSR + "::test_a_board_whose_model_is_no_longer_taken_is_409_everywhere"})]),
    ("15", "inputs_with 가 다시 받기 거절을 버리고 저장 원문으로 돎",
     [(BIND, swap(REFUSED, "            return replace(base, criteria=found.criteria)\n"))],
     [(PURE, [TBS], {PURE_MOVED + "[cap]", PURE_MOVED + "[route]"}),
      (BUSINESS, [TSR], {MOVED + "[cap]", MOVED + "[route]"})]),
    ("16", "inputs_with 의 「기본값과 같으면 None」 갈래 지움",
     [(BIND, swap("        return None if judge == default else judge\n", "        return judge\n"))],
     [(PURE, [TBS], {TBS + "::test_inputs_with_carry_the_judge_step_unless_it_is_the_default"}),
      (BUSINESS, [TSR], {TSR + "::test_a_run_keeps_the_version_applied_when_it_was_made"})]),
    ("17", "_judge_model 이 경로만 견줌(검증 2 B1)",
     [(BIND, swap("        return None if judge == default else judge\n",
                  "        return None if judge.route == default.route else judge\n"))],
     [(BUSINESS, [TSR], {TSR + "::test_the_default_route_with_another_temperature_calls_with_that_temperature"})]),
]
if COMMIT == 2:
    PLANTS += SECOND
if ONLY is not None:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[2]


def checks_of(plant):
    return plant[3]


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
    for layer, targets, _ in checks_of(p):
        key = (layer[0], tuple(targets))
        if key in seen or not runnable(layer):
            continue
        seen.add(key)
        code, _, last = run(layer, targets, LOGS / f"P0-{layer[0]}-{len(seen)}.log")
        print(f"[0] {layer[0]} {' '.join(targets)} 초록: EXIT={code} {last}")
        zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, _ in PLANTS:
    plant = next(p for p in PLANTS if p[0] == number)
    originals = {f: f.read_bytes() for f, _ in edits}  # 같은 파일에 둘 심어도 원본은 처음 것
    try:
        ok_plant = True
        for f, edit in edits:
            text = f.read_text(encoding="utf-8")
            new = edit(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"[{number}] 심기 실패(파일이 바뀌지 않음) — 못 잡은 것으로 센다 — {what}")
            planted += 1
            continue
        ran = 0
        all_hit = True
        for layer, targets, expected in checks_of(plant):
            label = f"[{number}/{layer[0]}]"
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            ran += 1
            code, failed, last = run(layer, targets, LOGS / f"{number}-{layer[0]}.log")
            missing = sorted(w for w in expected if not hit(w, failed))
            ok = code != 0 and not missing
            all_hit = all_hit and ok
            print(f"{label} {'잡음' if ok else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
        if ran:
            planted += 1
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
