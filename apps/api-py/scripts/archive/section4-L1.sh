#!/usr/bin/env bash
# 밴드 L1(MARC-TICK-85: core/llm 에 임베딩 호출 길 — 가짜 공급사로만 잼, 실호출 0)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-L1.sh --step <1~3>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-L1.sh --pure           --step 3 전부 + 심은 파손(planted-breaks-L1.sh) + 휠
#         apps/api-py/scripts/section4-L1.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 컨테이너 층은 없다: 바뀌는 파일이 전부 DB 를 모르는 쪽이고 DB 싱크(sink_db.py)는 0줄이다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독이 병합 뒤 main 에서). AI 공급사 호출 0. 네트워크는 uv·pnpm 의 설치뿐.
# bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 기준: 발주서는 8204571 이라 적었지만 워크트리는 X2 가 병합된 main(b78a477)에서 지었다(감독 덧붙임 7 「바닥은
#   워크트리를 만들 때의 main」). X2 의 변경은 core/llm·core/resources 에 0줄이고 순수 층 테스트 95건을 더했다
#   (1,614 → 1,709). 그래서 B 와 순수 층의 기준 수는 b78a477 의 것이다.
# ★ 커밋마다 달라지는 기대: 새 테스트 파일(① 하나, ② 둘, ③ 셋), CallRecord 의 칸·순환 import 는 ② 부터.
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
B=b78a477   # 기준 커밋(워크트리를 만들 때의 main. 위의 ★)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=3
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [1-3]) ;; *) echo "사용: $0 --step <1~3>" >&2; exit 2 ;; esac ;;
  --pure | --after-commit) ;;
  *) echo "사용: $0 --step <1~3> | --pure | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
A=apps/api-py
E="$A/esgapi"
L="$E/core/llm"
TEST_DS=esgapi.config.settings.test_business
PURE_BASE=1709      # 기준(b78a477)의 순수 층
export A E L TEST_DS B

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1-2 의 닫힌 목록) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/llm/embedding\.py$' \
    -e '^apps/api-py/esgapi/core/llm/embedding_types\.py$' \
    -e '^apps/api-py/esgapi/core/llm/config\.py$' \
    -e '^apps/api-py/esgapi/core/llm/log\.py$' \
    -e '^apps/api-py/esgapi/core/llm/providers/mock\.py$' \
    -e '^apps/api-py/esgapi/core/llm/providers/openai\.py$' \
    -e '^apps/api-py/esgapi/core/llm/setup\.py$' \
    -e '^apps/api-py/esgapi/core/llm/__init__\.py$' \
    -e '^apps/api-py/esgapi/core/llm/purity\.importlinter$' \
    -e '^apps/api-py/esgapi/core/llm/data/models\.embedding\.synthetic\.json$' \
    -e '^apps/api-py/esgapi/core/llm/data/README\.md$' \
    -e '^apps/api-py/esgapi/core/resources/ports/llm\.py$' \
    -e '^apps/api-py/esgapi/core/resources/llm\.py$' \
    -e '^apps/api-py/esgapi/core/tests/llm/__init__\.py$' \
    -e '^apps/api-py/esgapi/core/tests/llm/test_config_embedding\.py$' \
    -e '^apps/api-py/esgapi/core/tests/llm/test_embedding\.py$' \
    -e '^apps/api-py/esgapi/core/tests/llm/providers/__init__\.py$' \
    -e '^apps/api-py/esgapi/core/tests/llm/providers/test_openai_embedding\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-L1\.sh$'
}
# 그 커밋까지의 새 테스트 파일(apps/api-py 에서).
new_tests() {
  echo esgapi/core/tests/llm/test_config_embedding.py
  [ "$STEP" -ge 2 ] && echo esgapi/core/tests/llm/test_embedding.py
  [ "$STEP" -ge 3 ] && echo esgapi/core/tests/llm/providers/test_openai_embedding.py
  return 0
}
export -f new_tests
export STEP

echo "── 밴드 L1 §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -8; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"

  echo; echo "── 나. 새 테스트 파일만"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider $(new_tests) > "$T/new.txt" 2>&1; code=$?; tail -1 "$T/new.txt"; for f in $(new_tests); do echo "  $f: $(uv run --frozen pytest --collect-only -q -p no:cacheprovider "$f" 2>/dev/null | grep -c "::")"; done; exit $code)'

  echo; echo "── 다. 순수 층 전량(기준 $PURE_BASE + 새 테스트, 건너뛴 것·경고 없음)"
  run '(cd "$A" && total=0; for f in $(new_tests); do n="$(uv run --frozen pytest --collect-only -q -p no:cacheprovider "$f" 2>/dev/null | grep -c "::")"; total=$((total + n)); done; want=$(('"$PURE_BASE"' + total)); uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last (기대 '"$PURE_BASE"' + $total = $want)"; case "$last" in "$want passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'

  echo; echo "── 라. 계약: 저장소 여섯 KEPT, core/llm 순수 하나 KEPT"
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache --config esgapi/core/llm/purity.importlinter > "$T/purity.txt" 2>&1; code=$?; tail -1 "$T/purity.txt"; test "$(tail -1 "$T/purity.txt")" = "Contracts: 1 kept, 0 broken." && exit $code; exit 1)'

  echo; echo "── 마. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일"
  run 'git diff --quiet "$B" -- "$A/generated" && test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3 && test -z "$(git ls-files --others --exclude-standard "$A/generated")"'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 바. 경계"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- "$A/pyproject.toml" "$A/uv.lock" "$A/.importlinter" "$L/sink_db.py" "$E/core/models.py" "$E"/*/migrations "$A/conftest.py" "$A/tests" "$A/tests_integration" "$E/config" "$E/core/management" "$E/core/flows" "$E/inventory" "$L/sinks" compose.yaml scripts docker infra apps/web README.md'
  run 'for f in client types budget cost retry throttle prompts schema errors; do git diff --quiet "$B" -- "$L/$f.py" || { echo "★ 바뀌었다: $L/$f.py"; exit 1; }; done; git diff --quiet "$B" -- "$L/providers/anthropic.py" "$L/providers/gemini.py" "$L/providers/redact.py"'
  run 'changed | grep "^$E/core/tests/" | grep -v -E "^$E/core/tests/llm/((providers/)?__init__|test_config_embedding|test_embedding|providers/test_openai_embedding)\.py$" > "$T/old-tests.txt"; cat "$T/old-tests.txt"; echo "  있는 테스트 파일의 변경: $(wc -l < "$T/old-tests.txt" | tr -d " ")"; test ! -s "$T/old-tests.txt"'

  echo; echo "── 사. 글자: core 의 업무 모듈 이름·import_module, 새 의존성 이름, 키 파일"
  run 'grep -rnE --include="*.py" "esgapi\.(accounts|inventory|reference|reconcile|greenwash)|import_module" "$L" "$E/core/resources" > "$T/names.txt"; cat "$T/names.txt"; echo "  줄: $(wc -l < "$T/names.txt" | tr -d " ")"; test ! -s "$T/names.txt"'
  run 'grep -rnE --include="*.py" "numpy|tiktoken" "$E/core" > "$T/deps.txt"; cat "$T/deps.txt"; echo "  줄: $(wc -l < "$T/deps.txt" | tr -d " ")"; test ! -s "$T/deps.txt"'
  run 'changed | grep -v -E "^$A/scripts/(section4|planted-breaks)-L1\.sh$" | while read -r f; do [ -f "$f" ] && grep -nH -E "spike/\.env|OPENAI_API_KEY=" "$f"; done > "$T/keys.txt"; cat "$T/keys.txt"; echo "  줄: $(wc -l < "$T/keys.txt" | tr -d " ")"; test ! -s "$T/keys.txt"'

  if [ "$STEP" -ge 2 ]; then
    echo; echo "── 아. CallRecord 의 있는 28칸이 이름·차례 그대로, 뒤에 embedding_inputs 하나만"
    run 'git show "$B:$L/log.py" > "$T/log-base.py"; "$A/.venv/bin/python" - "$T/log-base.py" "$L/log.py" <<'"'"'PY'"'"'
import ast, sys

def fields(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    (cls,) = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "CallRecord"]
    return [n.target.id for n in cls.body if isinstance(n, ast.AnnAssign) and isinstance(n.target, ast.Name)]

base, now = fields(sys.argv[1]), fields(sys.argv[2])
print(f"  기준 {len(base)}칸 · 지금 {len(now)}칸 · 더한 것 {now[len(base):]}")
assert len(base) == 28 and now == [*base, "embedding_inputs"]
PY'
    echo; echo "── 아-2. 순환 import 없음: 모듈마다 새 프로세스에서 맨 먼저 import"
    for m in esgapi.core.llm.client esgapi.core.llm.embedding esgapi.core.llm.embedding_types esgapi.core.resources.ports.llm esgapi.core.resources.llm esgapi.core.llm.providers.mock esgapi.core.llm.providers.openai esgapi.core.llm.setup; do
      run "(cd \"\$A\" && DJANGO_SETTINGS_MODULE=\$TEST_DS uv run --frozen python -c 'import $m')"
    done
  fi

  echo; echo "── 자. esg-lab 의 사본 둘이 바이트 동일"
  run 'git diff --quiet "$B" -- "$L/data/models.json" "$L/data/models.synthetic.json"'

  echo; echo "── 파. 깎지 않았다(건너뛰기·경고 예외·무시 표시를 더하지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; plus="$({ git diff "$B" -- . ":!$A/scripts/section4-L1.sh" ":!$A/scripts/planted-breaks-L1.sh"; for f in $(git ls-files --others --exclude-standard | grep -v -x -E "$A/scripts/(section4|planted-breaks)-L1\.sh"); do sed "s/^/+/" "$f"; done; } | grep -E "^\+.*($marks)")"; echo "$plus"; n="$(printf "%s" "$plus" | grep -c .)"; echo "  더한 줄 $n (이 스크립트와 심은 파손 스크립트는 뺀다: 무늬를 글자로 적은 줄이 있다)"; [ "$n" = 0 ]'
}

pure_extra_part() {
  echo; echo "── 카. 심은 파손 열셋"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-L1.sh" > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=13/13" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'

  echo; echo "── 타. 휠: tests/ 가 안 들고, 가상 임베딩 파일과 새 모듈이 든다"
  run '"$A/scripts/check-wheel.sh" 2>&1 | tail -4; exit ${PIPESTATUS[0]}'
  run '(cd "$A" && uv build --wheel -o "$T/wheel" > /dev/null 2>&1) && unzip -Z1 "$T"/wheel/*.whl > "$T/wheel.txt" && for f in esgapi/core/llm/data/models.embedding.synthetic.json esgapi/core/llm/embedding.py esgapi/core/llm/embedding_types.py; do grep -qx "$f" "$T/wheel.txt" || { echo "★ 없다: $f"; exit 1; }; echo "  $f 있음"; done; ! grep -q "/tests/" "$T/wheel.txt"'
}

after_commit_part() {
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 4'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-85" "Derives-from: MARC-TICK-71"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
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
