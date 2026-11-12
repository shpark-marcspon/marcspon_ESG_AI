#!/usr/bin/env bash
# 밴드 X2(MARC-TICK-83)의 심은 파손 스물다섯(0~24): 하나씩 심고, 그것을 잡아야 하는 계약·테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-X2.sh        마지막 줄 PLANTED=<잡은 수>/25
# 0번은 심지 않고 돌린다: 계약 여섯 KEPT, 새 테스트 다섯이 전부 초록이어야 한다(처음부터 빨간 것을 「잡았다」고 세지 않게).
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준:
#   계약  lint-imports 가 0 이 아닌 코드로 끝나고 그 계약의 머리글자 줄(「가. … BROKEN」)이 있다.
#         「계약 없음」은 0 으로 끝나고 끝 줄이 `Contracts: 6 kept, 0 broken.` 이다.
#   테스트  pytest 가 0 이 아닌 코드로 끝나고 **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다.
#         「초록」으로 적은 것은 PASSED 줄에 있어야 한다.
#   10번은 pytest 가 시작에서 죽으므로 django.setup() 명령의 종료 코드와 출력으로 잰다.
# 컨테이너 0, 네트워크 0. 순수 층만 돈다. bash 전용이다.
set -u
export PYTHONDONTWRITEBYTECODE=1   # 심은 파일의 바이트코드를 남기지 않는다(되돌린 뒤 낡은 .pyc 를 읽지 않게)
cd "$(dirname "$0")/../../.."

A=apps/api-py
E="$A/esgapi"
REGISTRY="$E/core/flows/registry.py"
RUN="$E/core/flows/run.py"
SCOPE12="$E/inventory/flows/scope12.py"
SCOPE3="$E/inventory/flows/scope3.py"
REGISTRATION="$E/inventory/flows/registration.py"
APPS="$E/inventory/apps.py"
SHAPES="$E/inventory/flows/shapes.py"
LINTER="$A/.importlinter"
GREENWASH="$E/greenwash"
T_REG=esgapi/core/tests/test_flows_registry.py
T_RUN=esgapi/core/tests/test_flows_run.py
T_NAMES=esgapi/core/tests/test_flows_core_names.py
T_FLOWS=esgapi/inventory/tests/test_flows.py
T_SHAPES=esgapi/inventory/tests/test_flow_shapes.py
ALL_TESTS="$T_REG $T_RUN $T_NAMES $T_FLOWS $T_SHAPES"

[ -e "$GREENWASH" ] && { echo "$GREENWASH 가 이미 있다(8번이 잠깐 만들고 지운다) — 멈춘다" >&2; exit 2; }
keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$E/core/flows/__init__.py" "$REGISTRY" "$RUN" "$SCOPE12" "$SCOPE3" "$REGISTRATION" "$APPS" "$SHAPES" "$LINTER")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() {
  for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done
  rm -rf "$GREENWASH"
}
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자>   글자가 정확히 한 번 있어야 한다(없으면 심지 못한 것이다: 종료 3)
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
tests() { (cd "$A" && PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run --frozen pytest -q -rfp -p no:cacheprovider -m "not django_db and not security" $1); }
lint() { (cd "$A" && PYTHONPYCACHEPREFIX="$(mktemp -d)" COLUMNS=400 uv run --frozen lint-imports --no-cache); }

# 판정. <이름> 뒤에 기대를 적는다:
#   contract:<가|다|none>   계약의 기대 (lint 로그 $log/<n>.lint)
#   red:<테스트 이름>        FAILED 줄에 있어야 한다 (테스트 로그 $log/<n>.test)
#   green:<테스트 이름>      PASSED 줄에 있어야 한다
judge() {
  local number="$1" name="$2" caught=0 want kind
  shift 2
  total=$((total + 1))
  for want in "$@"; do
    kind="${want%%:*}"; want="${want#*:}"
    case "$kind" in
      contract)
        local code; code="$(cat "$log/$number.lint.code")"
        grep -E "^[가나다라마바]\. .*(KEPT|BROKEN)|^Contracts:" "$log/$number.lint" | cut -c1-90 | sed 's/^/    /'
        if [ "$want" = none ]; then
          { [ "$code" = 0 ] && [ "$(tail -1 "$log/$number.lint")" = "Contracts: 6 kept, 0 broken." ]; } || { caught=1; echo "    (계약 없음이 아니다)"; }
        else
          { [ "$code" != 0 ] && grep -q -E "^$want\. .* BROKEN" "$log/$number.lint"; } || { caught=1; echo "    (계약 $want 이 BROKEN 이 아니다)"; }
        fi ;;
      red)
        grep -q "^FAILED .*$want" "$log/$number.test" && [ "$(cat "$log/$number.test.code")" != 0 ] || { caught=1; echo "    (FAILED 줄에 없다: $want)"; } ;;
      green)
        grep -q "^PASSED .*$want" "$log/$number.test" || { caught=1; echo "    (PASSED 줄에 없다: $want)"; } ;;
    esac
  done
  [ -f "$log/$number.test" ] && grep -E '^[0-9]+ (passed|failed)|^FAILED|^ERROR' "$log/$number.test" | sed 's/^/    /' | cut -c1-160 | head -8
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$number. $name → 잡음"; else
    echo "$number. $name → ★ 못 잡음"; [ -f "$log/$number.test" ] && tail -15 "$log/$number.test" | sed 's/^/    | /'; fi
  restore_files
}
# 심은 뒤 잰다: <번호> <계약을 잴까 0|1> <테스트 파일들|"">
measure() {
  local number="$1" with_lint="$2" files="$3"
  if [ "$with_lint" = 1 ]; then lint > "$log/$number.lint" 2>&1; echo $? > "$log/$number.lint.code"; fi
  if [ -n "$files" ]; then tests "$files" > "$log/$number.test" 2>&1; echo $? > "$log/$number.test.code"; fi
}

# ── 0. 심지 않고: 계약 여섯 KEPT, 새 테스트 다섯 초록 ──
measure 0 1 "$ALL_TESTS"
if [ "$(cat "$log/0.test.code")" != 0 ] || tail -1 "$log/0.test" | grep -q -E 'failed|error'; then
  echo "0. 심지 않았는데 빨갛다 → ★ 멈춘다" >&2; tail -20 "$log/0.test" >&2; exit 1
fi
judge 0 "심지 않음" contract:none

# ── 계약과 AST ──
edit "$REGISTRY" $'import re\n' $'import re\n\nimport esgapi.inventory.flows.scope12\n' || exit 3
measure 1 1 ""
judge 1 "core/flows/registry.py 가 esgapi.inventory.flows.scope12 를 import" contract:가

edit "$REGISTRY" $'import re\n' $'import re\nfrom importlib import import_module\n' || exit 3
printf '\n\ndef _planted() -> object:\n    return import_module("esgapi.inventory.flows.registration")\n' >> "$REGISTRY"
measure 2 1 "$T_NAMES"
judge 2 "registry.py 의 함수 안에서 import_module(\"esgapi.inventory.flows.registration\")" contract:none \
  red:test_core_spells_no_business_module red:test_core_imports_dynamically_only_inside_core

edit "$REGISTRY" $'import re\n' $'import importlib\nimport re\n' || exit 3
printf '\n\ndef _planted() -> object:\n    return importlib.import_module(".".join(["esgapi", "inventory", "flows"]))\n' >> "$REGISTRY"
measure 3 1 "$T_NAMES"
judge 3 "registry.py 의 함수 안에서 importlib.import_module(\".\".join([...]))" contract:none \
  red:test_core_imports_dynamically_only_inside_core green:test_core_spells_no_business_module

edit "$REGISTRY" $'import re\n' $'import re\n\nimport django\n' || exit 3
measure 4 1 ""
judge 4 "registry.py 에 import django" contract:다

edit "$SCOPE12" $'from typing import Final\n' $'from typing import Final\n\nimport django\n' || exit 3
measure 5 1 ""
judge 5 "inventory/flows/scope12.py 에 import django" contract:다

edit "$SCOPE3" $'from typing import Final\n' $'from typing import Final\n\nfrom esgapi.inventory.service.services import inventory as _planted\n' || exit 3
measure 6 1 "$T_FLOWS"
judge 6 "inventory/flows/scope3.py 가 inventory.service.services 를 import" contract:다 red:test_flows_call_no_service

# 7번은 짝 하나로 잰다(감독 처분 2026-10-15 밤). 발주서 §3-3 은 registry.py 에 심으라 했으나, 그 자리는
# 「다」의 esgapi.inventory.flows 줄이 inventory.flows.registration → core.flows.registry → django 로 간접으로 문다.
# inventory.flows 가 들이지 않는 core/flows/__init__.py 에 심어야 esgapi.core.flows 줄이 하는 일을 잰다:
#   (가) 줄이 있으면 「다」 BROKEN   (나) 그 줄을 뺀 채 같은 것을 심으면 계약 없음(그 줄 없이는 못 잡음)
FLOWS_INIT="$E/core/flows/__init__.py"
cp "$FLOWS_INIT" "$keep/flows_init"
printf '\nimport django\n' >> "$FLOWS_INIT"
measure 7a 1 ""
edit "$LINTER" $'    esgapi.core.flows\n' '' || exit 3
measure 7b 1 ""
cp "$keep/flows_init" "$FLOWS_INIT"
cp "$log/7a.lint" "$log/7.lint"; cp "$log/7a.lint.code" "$log/7.lint.code"
seven_a="$(cat "$log/7a.lint.code")"
judge 7 "core/flows/__init__.py 에 import django — (가) 「다」 BROKEN" contract:다
if [ "$seven_a" != 0 ] && grep -q -E "^다\. .* BROKEN" "$log/7a.lint" && [ "$(cat "$log/7b.lint.code")" = 0 ] \
  && [ "$(tail -1 "$log/7b.lint")" = "Contracts: 6 kept, 0 broken." ]; then
  echo "   (나) 「다」에서 esgapi.core.flows 를 뺀 채 같은 것 → 계약 없음: $(tail -1 "$log/7b.lint") — 짝 맞음"
else
  echo "   (나) 짝이 안 맞음: $(tail -1 "$log/7b.lint") → 7번을 못 잡음으로 센다"; ok=$((ok - 1))
fi

mkdir "$GREENWASH" && : > "$GREENWASH/__init__.py"
edit "$RUN" $'import json\n' $'import json\n\nimport esgapi.greenwash\n' || exit 3
measure 8 1 ""
judge 8 "새 esgapi/greenwash/__init__.py + core/flows/run.py 가 esgapi.greenwash 를 import" contract:가

# ── 레지스트리와 등록 ──
edit "$REGISTRY" $'        if flow.id in self._flows:\n            raise FlowRegistryError(f"흐름 {flow.id} 이 이미 있다")\n' '' || exit 3
measure 9 0 "$T_REG $T_FLOWS"
judge 9 "register 의 같은 id 검사를 끈다" red:test_the_same_flow_id_twice_is_an_error red:test_registration_into_a_fresh_registry

edit "$REGISTRATION" '(scope12.FLOW, scope3.FLOW)' '(scope12.FLOW, scope3.FLOW, scope12.FLOW)' || exit 3
total=$((total + 1))
out="$(cd "$A" && PYTHONPYCACHEPREFIX="$(mktemp -d)" DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python -c "import django; django.setup()" 2>&1)"; code=$?
echo "$out" | tail -2 | sed 's/^/    /' | cut -c1-160
if [ "$code" != 0 ] && echo "$out" | grep -q FlowRegistryError && echo "$out" | grep -q 'scope12.engine@1'; then
  ok=$((ok + 1)); echo "10. registration.py 의 FLOWS 에 scope12.FLOW 를 한 번 더 → 잡음 (django.setup() 종료 $code)"
else
  echo "10. registration.py 의 FLOWS 에 scope12.FLOW 를 한 번 더 → ★ 못 잡음 (종료 $code)"
fi
restore_files

edit "$APPS" $'    def ready(self) -> None:\n' $'    def ready(self) -> None:\n        return\n' || exit 3
measure 11 0 "$T_FLOWS"
judge 11 "inventory/apps.py 의 ready 몸 첫 줄에 return" red:test_ready_registered_both_flows

edit "$REGISTRATION" ', "inventory.scope3": "scope3.llm-first@1"}' '}' || exit 3
measure 12 0 "$T_FLOWS"
judge 12 "registration.py 의 DEFAULTS 에서 inventory.scope3 를 뺌" red:test_ready_registered_both_flows

# ── 결과 꼴 ──
edit "$SCOPE12" '{"schemaVersion": RESULT_SHAPE, **out}' '{"schemaVersion": RESULT_SHAPE, **{k: v for k, v in out.items() if k != "aggregation"}}' || exit 3
measure 13 0 "$T_FLOWS $T_SHAPES"
judge 13 "scope12.py 의 단계가 결과에서 aggregation 을 뺌" red:test_scope12_flow_equals_the_calc_path red:test_flow_results_fit_their_shape

edit "$SCOPE3" $'        "usage": usage_to_dict(result.usage),\n' '' || exit 3
measure 14 0 "$T_FLOWS $T_SHAPES"
judge 14 "scope3.py 의 단계가 usage 칸을 안 냄" red:test_scope3_flow_equals_the_pipeline red:test_flow_results_fit_their_shape

edit "$SHAPES" $'    schemaVersion: Literal["scope12.result@1"]\n    gwpSetId: str\n' $'    schemaVersion: Literal["scope12.result@1"]\n' || exit 3
measure 15 0 "$T_SHAPES"
judge 15 "shapes.py 의 Scope 1·2 꼴에서 gwpSetId 칸을 지움" red:test_the_json_schema_is_pinned red:test_flow_results_fit_their_shape

edit "$SCOPE12" '{"schemaVersion": RESULT_SHAPE, **out}' '{**out}' || exit 3
measure 16 0 "$T_FLOWS"
judge 16 "scope12.py 의 단계가 schemaVersion 을 안 붙임" red:test_scope12_flow_equals_the_calc_path

# ── 실행 ──
edit "$RUN" $'        first = flow.steps.index(start_at)\n' $'        first = 0\n' || exit 3
measure 17 0 "$T_RUN"
judge 17 "run_flow 가 start_at 을 무시하고 늘 첫 단계부터" red:test_resume_from_a_step

edit "$RUN" $'            events.step_failed(flow.id, name, f"{type(err).__name__}: {err}")\n' '' || exit 3
measure 18 0 "$T_RUN"
judge 18 "run_flow 가 실패 때 step_failed 를 안 부름" red:test_a_failing_step

edit "$REGISTRY" '    if id.split("@", 1)[0].split(".", 1)[0] != module.rsplit(".", 1)[-1]:' '    if False:' || exit 3
measure 19 0 "$T_REG"
judge 19 "make_flow 의 「첫 마디 = 모듈 끝 마디」 검사를 끈다" red:test_flow_id_starts_with_the_module_tail

edit "$APPS" $'        if self.apps is not global_apps:\n            return\n' '' || exit 3
measure 20 0 "$T_FLOWS"
judge 20 "inventory/apps.py 의 지킴 두 줄을 지움" red:test_another_app_registry_does_not_register_again

edit "$RUN" '            kept = StepOutput(data=_round_trip(f"단계 {name} 의 data", out.data), files=out.files)' \
  '            _round_trip(f"단계 {name} 의 data", out.data); kept = StepOutput(data=out.data, files=out.files)' || exit 3
measure 21 0 "$T_RUN"
judge 21 "run_flow 가 왕복한 값 대신 단계가 낸 data 를 그대로 넘김" red:test_step_data_is_what_a_checkpoint_gives_back

edit "$RUN" '        events.step_finished(flow.id, name, _snapshot(kept))' \
  '        events.step_finished(flow.id, name, StepOutput(data={}))' || exit 3
measure 22 0 "$T_RUN"
judge 22 "run_flow 가 step_finished 에 빈 StepOutput 을 실음" red:test_resume_from_a_step

edit "$RUN" 'StepContext(resume=resumed if name == start_at else None,' 'StepContext(resume=None,' || exit 3
measure 23 0 "$T_RUN"
judge 23 "run_flow 가 resume 을 받아도 ctx.resume 을 늘 None 으로" red:test_resume_inside_a_step

edit "$RUN" 'partial=progress.partial) from err' 'partial=None) from err' || exit 3
measure 24 0 "$T_RUN"
judge 24 "FlowStepFailed.partial 을 늘 None 으로" red:test_resume_inside_a_step

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "★ 되돌린 뒤의 파일이 처음과 다르다(sha256 이나 git status)" >&2
  diff "$keep/.sums-before" "$keep/.sums-after" >&2
  exit 1
fi
echo "되돌림 확인: sha256 $(wc -l < "$keep/.sums-after" | tr -d ' ')개 같음 · git status 같음 · esgapi/greenwash 없음"
echo "PLANTED=$ok/$total"
[ "$ok" -eq 25 ] && [ "$total" -eq 25 ]
