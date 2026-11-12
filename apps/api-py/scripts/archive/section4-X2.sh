#!/usr/bin/env bash
# 밴드 X2(MARC-TICK-83: 흐름 레지스트리 — 모듈과 흐름(이름@판), 이름 붙은 단계, 엔진 둘을 흐름으로 감싸기. 순수)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-X2.sh --step <1~4>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-X2.sh --pure           --step 4 전부 + 심은 파손(planted-breaks-X2.sh)
#         apps/api-py/scripts/section4-X2.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 컨테이너 층은 없다(--containers 없음): 제품 코드가 순수이고 업무·보안·통합 층에 닿는 것은 ready() 하나다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독이 병합 뒤 main 에서). AI 공급사 호출 0. 네트워크는 uv·pnpm 의 설치뿐.
# bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 커밋마다 달라지는 기대: .importlinter 의 더한 줄(① 둘, ② 부터 셋), 새 테스트 파일(① 셋, ② 넷, ③ 다섯),
#   등록(사)과 이름(바)은 ② 부터, shapes.py 는 ③ 부터.
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 기준의 노드 ID 는 git archive 로 푼 사본(저장소 밖)에서 이 워크트리의 .venv 로 뜬다(2,031건).
set -u
cd "$(dirname "$0")/../../.."
B=8204571   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=4
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [1-4]) ;; *) echo "사용: $0 --step <1~4>" >&2; exit 2 ;; esac ;;
  --pure | --after-commit) ;;
  *) echo "사용: $0 --step <1~4> | --pure | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
ROOT="$PWD"
A=apps/api-py
E="$A/esgapi"
TEST_DS=esgapi.config.settings.test_business
PURE_BASE=1614      # 기준의 순수 층(발주서 ★10)
NODES_BASE=2031     # 기준의 노드 ID
NODES_HASH=9ef9018ffcce6c42
export A E TEST_DS

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1-2 의 닫힌 목록) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/flows/(__init__|types|registry|run)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_flows_(registry|run|core_names)\.py$' \
    -e '^apps/api-py/esgapi/inventory/flows/(__init__|scope12|scope3|registration|shapes)\.py$' \
    -e '^apps/api-py/esgapi/inventory/(apps|__init__)\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/test_flow(s|_shapes)\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/data/flow-shapes/(scope12|scope3\.llm-first)\.result@1\.schema\.json$' \
    -e '^apps/api-py/\.importlinter$' \
    -e '^apps/api-py/scripts/(section4-X2|planted-breaks-X2)\.sh$'
}
# 그 커밋까지의 새 테스트 파일(esgapi 에서).
new_tests() {
  echo esgapi/core/tests/test_flows_registry.py esgapi/core/tests/test_flows_run.py esgapi/core/tests/test_flows_core_names.py
  [ "$STEP" -ge 2 ] && echo esgapi/inventory/tests/test_flows.py
  [ "$STEP" -ge 3 ] && echo esgapi/inventory/tests/test_flow_shapes.py
  return 0
}
# .importlinter 의 더한 줄(그 커밋까지).
expected_lint_lines() {
  echo "+    esgapi.greenwash"
  echo "+    esgapi.core.flows"
  [ "$STEP" -ge 2 ] && echo "+    esgapi.inventory.flows"
  return 0
}
# 그 설정으로 django.setup() 을 부른 뒤 REGISTRY 의 기본값이 둘인가(migrate 의 DB 주소는 가짜 — 연결하지 않는다).
registered() {
  (cd "$A" && DJANGO_SETTINGS_MODULE="esgapi.config.settings.$1" DATABASE_URL_PY_OWNER=postgres://x:x@127.0.0.1:1/x \
    uv run --frozen python - <<'PY'
import django

django.setup()
from esgapi.core.flows.registry import REGISTRY

got = sorted(REGISTRY.defaults().items())
print(" ", got)
assert got == [("inventory.scope12", "scope12.engine@1"), ("inventory.scope3", "scope3.llm-first@1")]
PY
  )
}
export -f new_tests expected_lint_lines
export STEP

echo "── 밴드 X2 §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄(기준 $PURE_BASE + 새 테스트, 건너뛴 것·경고 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -8; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && total=0; for f in $(new_tests); do n="$(uv run --frozen pytest --collect-only -q -p no:cacheprovider "$f" 2>/dev/null | grep -c "::")"; echo "  새 테스트 $f: $n"; total=$((total + n)); done; want=$(('"$PURE_BASE"' + total)); uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last (기대 '"$PURE_BASE"' + $total = $want)"; case "$last" in "$want passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'

  echo; echo "── 나. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일"
  run 'git diff --quiet "$B" -- "$A/generated"'
  run 'for pair in openapi.json:62898c29b5f7d3d0 api.d.ts:5e97a088e251ae37 api.d.ts.source-sha256:756211bb0033431c; do f="${pair%%:*}"; want="${pair##*:}"; now="$(sha "$A/generated/$f" | cut -c1-16)"; echo "  $now  $f"; test "$now" = "$want" || { echo "★ 다르다: $f"; exit 1; }; done; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 다. 계약 여섯 KEPT, .importlinter 의 더한 줄이 그 커밋까지의 것뿐"
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; grep -E "^[가나다라마바]\. " "$T/lint.txt" | cut -c1-60; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'
  run 'git diff -U0 "$B" -- "$A/.importlinter" | grep -E "^[+-]" | grep -v -E "^(\+\+\+|---) " > "$T/lint-diff.txt"; cat "$T/lint-diff.txt"; expected_lint_lines | diff - "$T/lint-diff.txt"'

  echo; echo "── 라. 엔진·경로 0줄, 흐름을 부르는 경로 0"
  run 'git diff --quiet "$B" -- "$E/inventory/calc" "$E/inventory/service" "$E/inventory/api.py" "$E/inventory/data_loader.py" "$E/inventory/xlsx_reader.py" "$E/inventory/data" "$E/inventory/prompts"'
  run 'n="$(git grep -nE "inventory\.flows|core\.flows" -- "$E/*/service" "$E/*/api.py" "$E/config" "$E/reconcile" | wc -l | tr -d " ")"; git grep -nE "inventory\.flows|core\.flows" -- "$E/*/service" "$E/*/api.py" "$E/config" "$E/reconcile"; echo "  흐름을 부르는 경로·설정의 줄: $n"; [ "$n" = 0 ]'
  if [ "$STEP" -ge 2 ]; then
    run 'n="$(git diff "$B" -- "$E/inventory/apps.py" | grep -c "^-[^-]")"; echo "  inventory/apps.py 에서 지운 줄: $n"; [ "$n" = 0 ]'
  fi

  echo; echo "── 마. 경계"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- compose.yaml scripts docker infra apps/web services README.md "$A/pyproject.toml" "$A/uv.lock" "$A/tests" "$A/tests_integration" "$A/conftest.py" "$E/config" "$A/scripts/planted-breaks.sh" "$E/*/migrations"'
  run 'test ! -e "$E/greenwash" && echo "  esgapi/greenwash 없음"'
  run 'changed | grep "^$E/core/" | grep -v -E "^$E/core/(flows/[a-z_]+\.py|tests/test_flows_(registry|run|core_names)\.py)$" > "$T/core-other.txt"; cat "$T/core-other.txt"; echo "  core 에서 flows·새 테스트 밖으로 바뀐 파일: $(wc -l < "$T/core-other.txt" | tr -d " ")"; test ! -s "$T/core-other.txt"'

  if [ "$STEP" -ge 2 ]; then
    echo; echo "── 바. 이름(§2-7 의 글자)이 제품 코드에서 흐름 파일 밖에 없다(테스트·고정 파일·inventory/__init__.py 의 docstring 제외)"
    run 'bad=0; for name in inventory.scope12 inventory.scope3 scope12.engine@1 scope3.llm-first@1 scope12.result@1 scope3.llm-first.result@1; do files="$({ git grep -lF "$name" -- "$E"; git ls-files --others --exclude-standard "$E" | xargs grep -lF "$name" 2>/dev/null; } | sort -u | grep -v -E "/tests/" | grep -v -x -E "$E/inventory/flows/(scope12|scope3|registration|shapes)\.py|$E/inventory/__init__\.py")"; echo "  $name → 흐름 파일 밖: ${files:-(없음)}"; [ -z "$files" ] || bad=1; done; [ "$bad" = 0 ]'
    run 'n="$(git diff "$B" -- "$E/inventory/__init__.py" | grep -c -E "^[+-][^+-]")"; git diff "$B" -- "$E/inventory/__init__.py" | grep -E "^[+-][^+-]"; echo "  inventory/__init__.py 의 바뀐 줄: $n (docstring 한 줄)"; [ "$n" = 1 ]'

    echo; echo "── 사. 등록: 설정 셋에서 django.setup() 뒤 기본값 둘"
    for ds in test_business test_security migrate; do
      run "registered $ds"
    done
  fi

  echo; echo "── 아. 노드 ID: 기준($NODES_BASE)에서 없어진 것 0, 새로 생긴 것이 전부 이 밴드의 새 테스트 파일의 것"
  run 'mkdir -p "$T/base" && git archive "$B" "$A" | tar -x -C "$T/base" && (cd "$T/base/$A" && "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> "$T/base-collect.err" | grep "::" | LC_ALL=C sort > "$T/base-nodeids.txt"); n="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; h="$(sha "$T/base-nodeids.txt" | cut -c1-16)"; echo "  기준 ${n}건 · $h"; test "$n" = '"$NODES_BASE"' && test "$h" = '"$NODES_HASH"''
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | LC_ALL=C sort > "$T/nodeids.txt"); n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; diff "$T/base-nodeids.txt" "$T/nodeids.txt" | grep "^[<>]" > "$T/node-diff.txt"; gone="$(grep -c "^<" "$T/node-diff.txt")"; new="$(grep -c "^>" "$T/node-diff.txt")"; echo "  지금 ${n}건 · 없어진 것 $gone · 새로 생긴 것 $new"; grep "^<" "$T/node-diff.txt"; grep "^>" "$T/node-diff.txt" | sed -E "s/^> ([^:]+)::.*/\1/" | sort | uniq -c; allowed="$(new_tests | tr " " "\n" | sed "s/[.]/[.]/g" | paste -s -d "|" -)"; other="$(grep "^>" "$T/node-diff.txt" | grep -c -v -E "^> ($allowed)::")"; echo "  새 테스트 파일 밖의 새 노드: $other"; [ "$gone" = 0 ] && [ "$other" = 0 ] && [ "$n" = "$(('"$NODES_BASE"' + new))" ]'

  echo; echo "── 자. 깎지 않았다(건너뛰기·경고 예외·무시 표시를 더하지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; plus="$({ git diff "$B" -- . ":!$A/scripts/section4-X2.sh" ":!$A/scripts/planted-breaks-X2.sh"; for f in $(git ls-files --others --exclude-standard | grep -v -x -E "$A/scripts/(section4|planted-breaks)-X2\.sh"); do sed "s/^/+/" "$f"; done; } | grep -c -E "^\+.*($marks)")"; echo "  더한 줄 $plus (이 스크립트와 심은 파손 스크립트는 뺀다: 무늬를 글자로 적은 줄이 있다)"; [ "$plus" = 0 ]'

  echo; echo "── 차. 휠: tests/ 가 안 들고, 흐름 파일이 든다"
  run '"$A/scripts/check-wheel.sh" 2>&1 | tail -4; exit ${PIPESTATUS[0]}'
  run '(cd "$A" && uv build --wheel -o "$T/wheel" > /dev/null 2>&1) && unzip -Z1 "$T"/wheel/*.whl > "$T/wheel.txt" && grep -qx "esgapi/core/flows/run.py" "$T/wheel.txt" && echo "  esgapi/core/flows/run.py 있음" && { [ "$STEP" -lt 2 ] || { grep -qx "esgapi/inventory/flows/registration.py" "$T/wheel.txt" && echo "  esgapi/inventory/flows/registration.py 있음"; }; }'
}

pure_extra_part() {
  echo; echo "── 카. 심은 파손 25"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-X2.sh" > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=25/25" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
}

after_commit_part() {
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 4'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-83" "Derives-from: MARC-TICK-71"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --after-commit) step_part; pure_extra_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
