#!/usr/bin/env bash
# 밴드 DV1e(MARC-TICK-242: 데이터 검증 결과 경로·결과 꼴 @2·운영 관리자 실행)의 §4 자기검증(발주서 band-handoffs/DV1e-order.md §4).
#   사용: apps/api-py/scripts/section4-DV1e.sh [--commit <n>] [--with-containers] [--step <n>]
#   --commit n(1·2·3, 기본 3)은 그 경계까지의 허락 목록·0줄 목록·수·심은 파손 몫으로 잰다.
#   --with-containers 면 단계 10(업무·보안)과 단계 11 의 업무·보안 층을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 DV1e.out), DV1e_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
DV="$E/dataverify"
FS="$DV/tests/data/flow-shapes"
OUT="${S4_OUT:-$ROOT/../DV1e.out}"
FORBIDDEN="${DV1e_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>에서 잰 수(① 은 1a45b1b, ② 부터 감독이 RF1 을 병합해 49a1e0d — 데이터 검증 몫은 둘이 같다): 그 트리를
#   git archive 로 풀어 --collect-only. 순수 = pytest esgapi/dataverify -m "not django_db" 392 · 업무 16 ·
#   lint-imports 계약 17 · openapi 컴포넌트 239.
# 기대(늘기만): ① 순수 +24(test_colab_156_failures 20 · test_shapes 3 · test_xlsx 1) · ② 업무 +7(경로 4 · 운영 관리자 3).
BASE_PURE=392 BASE_CONTRACTS=17 BASE_COMPONENTS=239
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; COMMIT=3
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 [--commit <n>] [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in
  1) EXPECT_PURE=416 EXPECT_PLANTED=7 EXPECT_BUSINESS=16 ;;
  2) EXPECT_PURE=416 EXPECT_PLANTED=14 EXPECT_BUSINESS=23 ;;
  3) EXPECT_PURE=416 EXPECT_PLANTED=16 EXPECT_BUSINESS=23 ;;
  *) echo "--commit 은 1·2·3" >&2; exit 2 ;;
esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 DV1e §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 뒤 바뀐 경로(추적 diff + 추적 안 된 새 파일)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2 데이터 검증(이 트랙) — 경계 ① 몫
ALLOWED_1='apps/api-py/esgapi/dataverify/contracts/shapes\.py|apps/api-py/esgapi/dataverify/flows/colab_156\.py|apps/api-py/esgapi/dataverify/outputs/xlsx\.py|apps/api-py/esgapi/dataverify/tests/data/flow-shapes/dataverify\.result@(1|2)\.schema\.json|apps/api-py/esgapi/dataverify/tests/data/examples/result-sample\.json|apps/api-py/esgapi/dataverify/tests/.*|apps/api-py/scripts/(section4|planted-breaks)-DV1e\.sh'
# §1-2 경계 ② 몫(경로 새 파일) + §1-3 허락 줄의 파일(core·config·generated·runs.py — Q8 나 · S/** 셈 줄 셋 — 감독 78
# (나), ③ 에서 당겨 옴 · user 시험 test_run_logs.py 한 자리 — 22 허락, RF1 시험과 390 충돌)
ALLOWED_2='apps/api-py/esgapi/dataverify/api\.py|apps/api-py/esgapi/dataverify/service/(__init__|apis/__init__|apis/dataverify|actions/__init__|actions/result)\.py|apps/api-py/esgapi/core/permissions\.py|apps/api-py/esgapi/core/tests/test_(permissions|permissions_wiring|transaction_rules)\.py|apps/api-py/esgapi/config/api\.py|apps/api-py/esgapi/config/tests/test_api_(contract|errors)\.py|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|apps/api-py/esgapi/runs/service/apis/runs\.py|apps/api-py/tests/security/test_(login|operator_company|tenant_paths)\.py|apps/api-py/esgapi/user/tests/service/apis/test_run_logs\.py'
# §1-2·§1-3 경계 ③ 몫(보안 시험 새 파일 · README·development 각 한 줄)
ALLOWED_3='apps/api-py/tests/security/test_dataverify\.py|README\.md|docs/development\.md'
case "$COMMIT" in
  1) ALLOWED="^($ALLOWED_1)$" ;;
  2) ALLOWED="^($ALLOWED_1|$ALLOWED_2)$" ;;
  *) ALLOWED="^($ALLOWED_1|$ALLOWED_2|$ALLOWED_3)$" ;;
esac

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · outside=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-2 끝·§1-3 끝·§1-4 의 0줄 목록(경계 ① 은 공유 줄 전부도 0)
ZERO=("$DV/engines" "$DV/prompts" "$DV/flows/binding_156.py" "$DV/contracts/wire.py" "$DV/contracts/options_shapes.py"
  "$FS/dataverify.input@1.schema.json" "$FS/options/dataverify.options@1.schema.json"
  "$A/.importlinter" "$E/core/tests/test_flows_core_names.py" "$E/greenwash" "$E/translation" apps/web
  "$A/tests_integration" "$A/conftest.py" "$A/tests/support" "$A/tests/security/conftest.py" "$A/tests/security/seed.py"
  "$A/scripts/planted-breaks.sh" "$E/runs/tests")
if [ "$COMMIT" = 1 ]; then
  ZERO+=("$E/core" "$E/runs" "$E/config" "$A/generated" "$A/tests/security" README.md docs/development.md)
elif [ "$COMMIT" = 2 ]; then
  ZERO+=("$A/tests/security/test_dataverify.py" "$A/tests/security/test_translation.py" README.md docs/development.md)
else
  ZERO+=("$A/tests/security/test_translation.py" "$A/tests/security/test_greenwash.py" "$A/tests/security/test_runs.py")
fi

s2() {
  local n
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

# §1-3 허락 줄 numstat 과 「-」 줄 원문
s3() {
  if [ "$COMMIT" = 1 ]; then
    echo "  경계 ① — 허락 줄 0(공유 파일 diff 는 단계 2 가 0 으로 본다)"
    return 0
  fi
  local code=0 f want got oc=4 tp=5 op=4
  # 경계 ③ 은 S/** 두 파일에 새 시험(3-4-1·3-4-3·3-4-4 — 더하기만)이 붙는다: 「-」 수는 ② 그대로
  if [ "$COMMIT" = 3 ]; then oc=103 tp=47; fi
  # 허락 줄 표(§1-3, 「RF1 값 + DV1e 몫」 — 기준 49a1e0d 에서 잰 numstat +/−)
  for pair in "$E/core/permissions.py 6 5" "$E/core/tests/test_permissions.py 15 13" \
    "$E/core/tests/test_permissions_wiring.py 3 2" "$E/core/tests/test_transaction_rules.py 2 1" \
    "$E/config/api.py 5 3" "$E/config/tests/test_api_contract.py 15 6" "$E/config/tests/test_api_errors.py 4 2" \
    "$E/runs/service/apis/runs.py 2 2" "$A/tests/security/test_login.py 4 2" \
    "$A/tests/security/test_operator_company.py $oc $op" "$A/tests/security/test_tenant_paths.py $tp 5" \
    "$E/user/tests/service/apis/test_run_logs.py 3 1"; do
    set -- $pair
    f="$1"; want="$2 $3"
    got="$(git diff --numstat "$BASE" -- "$f" | awk '{print $1" "$2}')"
    echo "  $f numstat +${got% *}/-${got#* } (허락 +$2/-$3)"
    [ "$got" = "$want" ] || code=1
  done
  echo "  「-」 줄 원문(숫자 줄·같은 줄 주석·머리말·Q8 줄·함수 이름 줄):"
  git diff "$BASE" -- "$E/core" "$E/config" "$E/runs" "$E/user" "$A/tests/security" | grep -E '^-[^-]' | sed 's/^/    /'
  [ "$(git diff --name-only "$BASE" -- "$E/runs")" = "$E/runs/service/apis/runs.py" ] || { echo "  ★ runs 는 runs.py 두 줄뿐(Q8 나)"; code=1; }
  if [ "$COMMIT" = 3 ]; then
    for f in README.md docs/development.md; do
      got="$(git diff --numstat "$BASE" -- "$f" | awk '{print $1" "$2}')"
      echo "  $f numstat +${got% *}/-${got#* } (허락 +1/-1)"
      [ "$got" = "1 1" ] || code=1
    done
    git diff "$BASE" -- README.md docs/development.md | grep -E '^-[^-]' | sed 's/^/    /'
  fi
  return $code
}

s4() {
  local log kept broken
  log="$(cd "$A" && uv run --frozen lint-imports 2>&1)"
  echo "$log" > "$OUT/s4-lint-imports.log"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\2/p')"
  echo "  kept=$kept broken=$broken (기준 $BASE_CONTRACTS)"
  [ "$kept" = "$BASE_CONTRACTS" ] && [ "$broken" = 0 ]
}

# 순수 시험 + BASE 흐름과 견줌(3-1-2 message 바이트 · 3-1-6 끝남·부분 갈래 결과와 호출 차례)
s5() {
  local log n code
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify \
    -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] || return 1
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core/tests/test_permissions.py esgapi/config/tests/test_api_contract.py -m "not django_db" 2>&1)"
  code=$?
  echo "  test_permissions·test_api_contract(순수 몫) $(echo "$log" | tail -1)"
  [ "$code" = 0 ] || return 1
  git show "$BASE:$DV/flows/colab_156.py" > "$OUT/s5-base-colab_156.py"
  git show "$BASE:$DV/contracts/shapes.py" > "$OUT/s5-base-shapes.py"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python - "$OUT/s5-base-colab_156.py" "$OUT/s5-base-shapes.py" <<'PYEOF')
import dataclasses
import importlib.util
import sys

from esgapi.core.flows.run import run_flow
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ProviderError, Truncated, Usage
from esgapi.dataverify.flows import colab_156 as new
from esgapi.dataverify.flows.colab_156 import StageCosts
from esgapi.dataverify.tests.flows import support, test_colab_156, test_colab_156_failures as cases
from esgapi.core.llm.types import ToolLoopFailed

import esgapi.dataverify.contracts as contracts


def load(name, path):
    """파일 자리째 싣는다(pydantic 의 use_attribute_docstrings 가 inspect 로 원문을 읽는다)."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


# BASE 흐름은 BASE 결과 꼴(@1)로 돈다: 그 흐름이 import 하는 shapes 자리에 BASE shapes 를 잠시 끼운다.
base_shapes = load("base_shapes", sys.argv[2])
current = contracts.shapes
sys.modules["esgapi.dataverify.contracts.shapes"], contracts.shapes = base_shapes, base_shapes
try:
    base = load("base_colab_156", sys.argv[1])
finally:
    sys.modules["esgapi.dataverify.contracts.shapes"], contracts.shapes = current, current
assert base.shapes.RESULT_SHAPE == "dataverify.result@1" and new.shapes.RESULT_SHAPE == "dataverify.result@2"
bad = 0
for failure, source, *_ in cases.LOOP_CASES:
    loop = ToolLoopFailed(failure=failure, steps=(), meta=cases.META, budget_source=source)
    same = base.ended(loop).message == new.ended(loop).message
    bad += not same
    print(f"  message 고리 {failure.kind:22} {'같음' if same else '★ 다름'}")
for failure, *_ in cases.CALL_CASES:
    same = base.ended_call(failure).message == new.ended_call(failure).message
    bad += not same
    print(f"  message 호출 {failure.kind:22} {'같음' if same else '★ 다름'}")

USAGE = Usage(input_tokens=100, output_tokens=20, cache_read_tokens=0, cache_write_tokens=0)


def scenario(name):
    mock = MockProvider("openai")
    given = support.inputs()
    if name == "happy":
        test_colab_156.happy(mock)
    elif name == "web_search_off":
        test_colab_156.happy(mock)
        given = support.inputs(web_search=False)
    elif name == "review_partial":
        mock.enqueue_text("[]")
        mock.enqueue_tool_calls([("value_of_by_name", test_colab_156.S1_2022)])
        mock.enqueue_text(test_colab_156.INSIGHT, hosted_calls=1)
    elif name == "review_provider_error":
        mock.enqueue_text("['가상 산식']")
        mock.enqueue(ProviderError(status=500, retryable=False, message="가상 공급사 오류 글"))
        mock.enqueue_text(test_colab_156.INSIGHT, hosted_calls=1)
    elif name == "insight_truncated":
        mock.enqueue_text("['가상 산식']")
        mock.enqueue_text("가상 검토")
        mock.enqueue(Truncated(text="가상 부분", usage=USAGE))
    elif name == "insight_budget":
        mock.enqueue_text("['가상 산식']")
        mock.enqueue_text("가상 검토")
        mock.enqueue_tool_calls([("web_search", "{}")], hosted_calls=1)
        given = support.inputs(max_cost_usd=StageCosts(plan=1.0, review=1.0, insight=0.0103))
    return mock, given


def strip(value):
    """결과에서 @2 의 새 칸(failure.kind·budgetSource·partialText)과 schemaVersion 을 뺀 것 — 나머지는 BASE 와 같아야
    한다."""
    if isinstance(value, dict):
        value = {k: v for k, v in value.items() if k != "schemaVersion"}
        out = {k: strip(v) for k, v in value.items() if k not in ("partialText", "budgetSource")}
        if "kind" in out and "message" in out and set(out) == {"kind", "message"}:
            out.pop("kind")
        return out
    if isinstance(value, list):
        return [strip(v) for v in value]
    return value


for name in ("happy", "web_search_off", "review_partial", "review_provider_error", "insight_truncated", "insight_budget"):
    runs = []
    for module in (base, new):
        mock, given = scenario(name)
        llm = support.spy(mock)
        fields = {f.name: getattr(given, f.name) for f in dataclasses.fields(given)}
        fields["max_cost_usd"] = module.StageCosts(**dataclasses.asdict(given.max_cost_usd))
        done = run_flow(module.FLOW, module.DataverifyInputs(**fields), module.DataverifyAdapters(llm=llm))
        (only,) = done.output.results
        calls = [(r.prompt, r.max_steps, r.max_cost_usd, r.tools) for r in llm.tool_requests]
        calls += [(r.prompt,) for r in llm.call_requests]
        runs.append((strip(dict(only)), calls, len(mock.calls)))
    same = runs[0] == runs[1]
    bad += not same
    print(f"  흐름 {name:22} {'결과·호출 차례 같음' if same else '★ 다름'}")
sys.exit(1 if bad else 0)
PYEOF
}

s6() {
  local code=0 g="$OUT/s6-shapes"
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && uv run --frozen python - "$g" <<'PYEOF') || return 1
import json, sys
from pathlib import Path
from esgapi.dataverify.contracts import options_shapes, shapes
out = Path(sys.argv[1])
for name, adapter in {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES, **options_shapes.OPTIONS_SHAPES}.items():
    (out / f"{name}.schema.json").write_text(json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
  for pair in "dataverify.options@1 options/" "dataverify.input@1 " "dataverify.result@2 "; do
    set -- $pair
    if cmp -s "$g/$1.schema.json" "$FS/${2:-}$1.schema.json"; then echo "  cmp $1 = 고정 파일"; else echo "  ★ cmp $1 ≠ 고정 파일"; code=1; fi
  done
  [ ! -e "$FS/dataverify.result@1.schema.json" ] && echo "  result@1 고정 파일 지움" || { echo "  ★ result@1 고정 파일이 남음"; code=1; }
  git diff --quiet "$BASE" -- "$FS/dataverify.input@1.schema.json" "$FS/options/dataverify.options@1.schema.json" \
    || { echo "  ★ input@1·options@1 이 기준과 다름"; code=1; }
  return $code
}

s7() {
  local g="$OUT/s7-generated" code=0
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi) \
    > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  git show "$BASE:$A/generated/openapi.json" > "$g/base-openapi.json"
  # 기준의 컴포넌트마다 값이 같음(바뀜 0·지움 0) · 늘어난 열쇠 · 늘어난 path
  jq -n --slurpfile b "$g/base-openapi.json" --slurpfile h "$A/generated/openapi.json" '
    ($b[0].components.schemas) as $bs | ($h[0].components.schemas) as $hs |
    {base: ($bs | length),
     changed: [$bs | keys[] | select($hs[.] != $bs[.])],
     added: [$hs | keys[] | select($bs[.] == null)],
     paths: [$h[0].paths | keys[] | select($b[0].paths[.] == null)],
     pathsGone: [$b[0].paths | keys[] | select($h[0].paths[.] == null)]}' > "$g/components.json" || return 1
  echo "  기준 컴포넌트 $(jq .base "$g/components.json") · 바뀜/지움 $(jq -c .changed "$g/components.json") · 늘어남 $(jq '.added | length' "$g/components.json") · 새 path $(jq -c .paths "$g/components.json") · 없어진 path $(jq -c .pathsGone "$g/components.json")"
  [ "$(jq .base "$g/components.json")" = "$BASE_COMPONENTS" ] || code=1
  [ "$(jq '.changed | length' "$g/components.json")" = 0 ] || code=1
  [ "$(jq '.pathsGone | length' "$g/components.json")" = 0 ] || code=1
  if [ "$COMMIT" = 1 ]; then
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 ① 인데 generated/ 가 기준과 다름"; code=1; }
  else
    [ "$(jq -c .paths "$g/components.json")" = '["/dataverify/runs/{run_id}/result"]' ] || { echo "  ★ 새 path 는 하나여야 한다"; code=1; }
  fi
  return $code
}

s8() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s8-layout.log" 2>&1
  local code=$?
  tail -1 "$OUT/s8-layout.log" | sed 's/^/  /'
  return $code
}

s9() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s9-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" dlog="$OUT/s10-dataverify.log" bcode scode dcode n
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/dataverify) > "$dlog" 2>&1
  dcode=$?
  n="$(tail -1 "$dlog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 업무 $(tail -1 "$dlog") EXIT=$dcode (기대 $EXPECT_BUSINESS)"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -n 4 -p no:cacheprovider esgapi/dataverify \
    esgapi/runs esgapi/config esgapi/core esgapi/greenwash esgapi/translation esgapi/user) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  업무(dataverify·runs·config·core·greenwash·translation·user) $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$dcode" = 0 ] && [ "$n" = "$EXPECT_BUSINESS" ] && [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s11() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-DV1e.sh" --commit "$COMMIT" $flag 2>&1)"
  echo "$log" > "$OUT/s11-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s12() {
  local d="$OUT/s12.diff" n_key n_bin n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .xlsx/.csv/.ipynb $n_bin · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2·§1-3 안(outside=0)" s1
step 2 "0줄 목록 diff 0" s2
step 3 "허락 줄 numstat·「-」 줄 원문" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험 초록·수 · BASE 흐름과 message·결과·호출 차례 같음" s5
step 6 "고정 스키마 다시 뽑아 cmp · result@1 지움 · input@1·options@1 = 기준" s6
step 7 "generated/ 다시 뽑아 cmp · 기준 컴포넌트 값 같음 · 새 path" s7
step 8 "check_test_layout" s8
step 9 "뿌리 verify.sh --fast" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무·보안(컨테이너 postgres)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 11 "심은 파손(경계 $COMMIT 까지의 몫 $EXPECT_PLANTED)" s11
step 12 "추적 diff 의 키 꼴·.xlsx/.csv/.ipynb·실재 기업명 0" s12
echo "SECTION4_FAIL=$FAILS"
