#!/usr/bin/env bash
# 밴드 GM(MARC-TICK-67: 파이썬 코드를 가이드의 자리로 옮긴다. 동작 변화 0)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-GM.sh --step <0~8>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-GM.sh --pure           --step 8 전부 + 자리·옛 경로 글자 전부 + 심은 파손 + README 대조 + 휠
#         apps/api-py/scripts/section4-GM.sh --containers     컨테이너 층 한 번(띄우기 → 업무 → 보안 → 통합 → 내리기 → 이미지 치우기)
#         apps/api-py/scripts/section4-GM.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. AWS 로 나가는 호출 0: 브로커는 compose 의 queue(SQS 흉내, sqs://queue:9324)뿐이다.
# 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ --step <n> 에서 「옛 경로 글자 0」은 그 커밋이 끝낸 묶음의 무늬만 보고, 커밋 ⑧ 이 고치는 두 파일
#   (scripts/planted-breaks.sh·scripts/readme_audit.py)은 n < 8 에서 보지 않는다. README 대조와 심은 파손도 --pure 에서만.
# ★ makemigrations --check 와 manage.py check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라
#   「consistent migration history」 RuntimeWarning 한 줄이 난다. 기대다).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
B=3a0fa3a   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=8
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-8]) ;; *) echo "사용: $0 --step <0~8>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~8> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
TEST_DS=esgapi.config.settings.test_business

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
# 허용 경로(발주서 §1-6) 밖에서 바뀐 파일. 줄마다 저장소 뿌리에서 시작하는 꼴이다.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/(core|accounts|inventory|reference|reconcile|drafting|greenwashing|materiality|translation)/' \
    -e '^apps/api-py/esgapi/config/(api\.py|apps_list\.py|tests/(test_settings|test_api_contract)\.py)$' \
    -e '^apps/api-py/esgapi/__init__\.py$' \
    -e '^apps/api-py/(tests/security|tests/support|tests_integration)/' \
    -e '^apps/api-py/conftest\.py$' \
    -e '^apps/api-py/\.importlinter$' \
    -e '^apps/api-py/pyproject\.toml$' \
    -e '^apps/api-py/scripts/(planted-breaks\.sh|readme_audit\.py|section4-GM\.sh|gm_check\.py|gm-nodeids-3a0fa3a\.txt)$' \
    -e '^README\.md$'
}
# 허용 경로 안의 0줄 구역(발주서 §1-6)에서 바뀐 파일.
frozen() {
  changed | grep -E \
    -e '/migrations/' \
    -e '^apps/api-py/esgapi/[a-z]+/calc/' \
    -e '^apps/api-py/esgapi/core/tenancy/' \
    -e '^apps/api-py/esgapi/core/(exceptions|schemas|conf)\.py$' \
    -e '^apps/api-py/esgapi/[a-z]+/(data|prompts)/' \
    -e '^apps/api-py/(uv\.lock|generated/)' \
    -e '^apps/api-py/esgapi/config/(settings/|celery\.py|env\.py|urls\.py|wsgi\.py)'
}
# 지난 밴드의 기록 스크립트 23파일과 rehearsal.sh (0줄이어야 한다).
records() {
  git ls-files "$A/scripts/section4*.sh" "$A/scripts/planted-breaks-*.sh" "$A/esgapi/*/tests/planted-breaks-*.sh" \
    | grep -v -x "$A/scripts/section4-GM.sh"
  echo "$A/scripts/rehearsal.sh"
}
# 노드 ID 의 기대 차이(발주서 §3-1 의 네 쌍 가운데 그 커밋까지의 것). diff 의 < 줄(기준에만) 과 > 줄(지금에만).
P=esgapi/core/tests/test_parser_port.py::test_the_port_the_adapter_and_the_service_import_only_the_allowed_modules
S=esgapi/config/tests/test_settings.py::test_the_app_list_is_core_and_the
expected_node_diff() {
  if [ "$STEP" -ge 1 ]; then
    echo "< $P[esgapi/core/adapters/parser.py]"; echo "< $P[esgapi/core/ports/parser.py]"
    echo "> $P[esgapi/core/resources/parser.py]"; echo "> $P[esgapi/core/resources/ports/parser.py]"
  fi
  if [ "$STEP" -ge 3 ]; then echo "< ${S}_eight_modules"; echo "> ${S}_four_modules"; fi
  if [ "$STEP" -ge 7 ]; then
    echo "< $P[esgapi/reconcile/services/parse.py]"; echo "> $P[esgapi/reconcile/service/services/parse.py]"
  fi
}
# 「옛 경로 글자 0」(발주서 §4 사)의 무늬 가운데 그 커밋까지 끝난 것. 한 줄에 하나.
LEAVES='auth|entities|exchange|permissions|schemas|selectors|services|tokens|importer'
stale_patterns() {
  [ "$STEP" -ge 1 ] && echo 'esgapi[./]core[./](adapters|ports)([^a-z_]|$)'
  [ "$STEP" -ge 2 ] && echo 'esgapi[./]core[./]documents([^a-z_]|$)' && echo 'esgapi[./]core[./]api([^a-z_]|$)'
  [ "$STEP" -ge 3 ] && echo 'esgapi[./](drafting|greenwashing|materiality|translation)([^a-z_]|$)' && echo 'esgapi[./]reconcile[./]api([^a-z_]|$)'
  [ "$STEP" -ge 4 ] && echo "esgapi[./]accounts[./]($LEAVES)([^a-z_]|\$)"
  [ "$STEP" -ge 5 ] && echo "esgapi[./]reference[./]($LEAVES)([^a-z_]|\$)"
  [ "$STEP" -ge 6 ] && echo "esgapi[./]inventory[./]($LEAVES)([^a-z_]|\$)"
  [ "$STEP" -ge 7 ] && echo 'esgapi[./]reconcile[./]services([^a-z_]|$)'
  return 0
}
# 자리 검사(발주서 §4 바)의 무늬 가운데 그 커밋까지 끝난 것: 옛 자리에 남은 추적 파일.
stale_places() {
  (
    cd "$A" || exit 1
    [ "$STEP" -ge 1 ] && git ls-files esgapi/core | grep -E '^esgapi/core/(adapters/|ports/)'
    [ "$STEP" -ge 2 ] && git ls-files esgapi/core | grep -E '^esgapi/core/(api\.py|documents/)'
    [ "$STEP" -ge 3 ] && git ls-files esgapi/drafting esgapi/greenwashing esgapi/materiality esgapi/translation esgapi/reconcile/api.py
    [ "$STEP" -ge 4 ] && git ls-files esgapi/accounts | grep -E "^esgapi/accounts/(($LEAVES)\.py|services/)"
    [ "$STEP" -ge 5 ] && git ls-files esgapi/reference | grep -E "^esgapi/reference/(($LEAVES)\.py|services/)"
    [ "$STEP" -ge 6 ] && git ls-files esgapi/inventory | grep -E "^esgapi/inventory/(($LEAVES)\.py|services/)"
    [ "$STEP" -ge 7 ] && git ls-files esgapi/reconcile | grep -E "^esgapi/reconcile/(($LEAVES)\.py|services/)"
    git ls-files | grep '/actions/'
    exit 0
  )
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다: 메모리 free 20% 이상, 1분 부하 12 미만, verify.lock 없음. 30초마다, 최대 10분.
gate() {
  local tries=0 free load lock
  lock="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
  while :; do
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ ! -e "$lock" ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: verify.lock 없음 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 30초)"
      return 0
    fi
    [ "$tries" -ge 20 ] && { echo "  (문이 안 열렸다: verify.lock $([ -e "$lock" ] && echo 있음 || echo 없음) · free ${free:-?}% · 1분 부하 ${load:-?} · 10분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 30
  done
}

echo "── 밴드 GM §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local kept=4; [ "$STEP" -ge 5 ] && kept=5
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄(1508 passed, 건너뛴 것 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "1508 passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'

  echo; echo "── 나. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일"
  run 'git diff --quiet "$B" -- "$A/generated"'
  run 'for f in openapi.json api.d.ts api.d.ts.source-sha256; do test "$(sha "$A/generated/$f")" = "$(git show "$B:$A/generated/$f" | shasum -a 256 | cut -d" " -f1)" || { echo "★ 다르다: $f"; exit 1; }; done; wc -c < "$A/generated/openapi.json" | tr -d " "; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 다. 마이그레이션 0, makemigrations 가 낼 것 없음, system check"
  run 'test "$(git diff --stat "$B" -- "*/migrations/*" | wc -l | tr -d " ")" = 0 && test "$(changed | grep -c "/migrations/")" = 0'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python -W error manage.py check 2>&1 | tail -2; exit ${PIPESTATUS[0]})'

  echo; echo "── 라. 노드 ID: 기준과의 차이가 발주서 §3-1 의 쌍과 글자까지 같다(커밋 $STEP 까지), 건수 1,891, 통합 14"
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt"); n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  모은 건수 $n"; diff "$A/scripts/gm-nodeids-3a0fa3a.txt" "$T/nodeids.txt" | grep "^[<>]" | sort > "$T/node-diff.txt"; expected_node_diff | sort > "$T/node-diff-expected.txt"; cat "$T/node-diff.txt"; diff "$T/node-diff-expected.txt" "$T/node-diff.txt" && test "$n" = 1891 && test "$(wc -l < "$A/scripts/gm-nodeids-3a0fa3a.txt" | tr -d " ")" = 1891 && test "$(sha "$A/scripts/gm-nodeids-3a0fa3a.txt" | cut -c1-16)" = e6ce9543c6759525'
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider -c tests_integration/pytest.ini tests_integration 2>/dev/null | grep "::" | sort > "$T/nodeids-int.txt"); n="$(wc -l < "$T/nodeids-int.txt" | tr -d " ")"; h="$(sha "$T/nodeids-int.txt" | cut -c1-16)"; echo "  통합 ${n}건 · $h"; test "$n" = 14 && test "$h" = 2b622935f489eea7'

  echo; echo "── 마. gm_check.py 여섯 (--upto $STEP)"
  local check
  for check in moves others imports strings new places; do
    run '(cd "$A" && uv run --frozen python scripts/gm_check.py '"$check"' --upto '"$STEP"')'
  done

  echo; echo "── 바·사. 옛 자리에 남은 파일 0, 옛 경로 글자 0 (커밋 $STEP 까지 끝난 묶음)"
  run 'n="$(stale_places | wc -l | tr -d " ")"; stale_places; echo "  옛 자리에 남은 추적 파일(과 actions/): $n"; [ "$n" = 0 ]'
  run 'bad=0; while IFS= read -r pattern; do [ -n "$pattern" ] || continue; n="$(cd "$A" && git grep -IE "$pattern" -- . "${EX[@]}" | wc -l | tr -d " ")"; echo "  ${n}줄  $pattern"; [ "$n" = 0 ] || { bad=1; (cd "$A" && git grep -nIE "$pattern" -- . "${EX[@]}" | cut -c1-200 | head -20); }; done < <(stale_patterns); [ "$bad" = 0 ]'

  echo; echo "── 아. 계약 $kept KEPT, core/llm 의 순수 계약 1 KEPT"
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; grep -E "^[가나다라마]\. " "$T/lint.txt"; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: '"$kept"' kept, 0 broken." && test "$(grep -c -E "^[가나다라마]\. .* KEPT" "$T/lint.txt")" = '"$kept"' && exit $code; exit 1)'
  run '(cd "$A" && uv run --frozen lint-imports --no-cache --config esgapi/core/llm/purity.importlinter 2>&1 | tail -1 | grep -x "Contracts: 1 kept, 0 broken.")'

  echo; echo "── 카. 경계"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'n="$(frozen | wc -l | tr -d " ")"; frozen; echo "  0줄 구역에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- compose.yaml scripts docker infra apps/web apps/server packages services "$A/uv.lock"'
  run 'git diff --quiet "$B" -- "$A/esgapi/*/calc" "$A/esgapi/core/tenancy" "$A/esgapi/config/settings"'
  run 'git diff -U0 "$B" -- "$A/pyproject.toml" | grep "^[+-][^+-]"; test "$(git diff -U0 "$B" -- "$A/pyproject.toml" | grep "^[+-][^+-]" | grep -v -c -E "^[+-] *#")" = 0'
  run 'n="$(records | wc -l | tr -d " ")"; echo "  기록 스크립트와 rehearsal.sh: ${n}파일"; [ "$n" = 24 ] && git diff --quiet "$B" -- $(records)'
  run 'first="$(git diff -U0 "$B" -- README.md | sed -n "s/^@@ -\([0-9]*\).*/\1/p" | sort -n | head -1)"; echo "  README.md 의 첫 덩어리가 시작하는 줄: ${first:-없음(0줄)}"; [ -z "$first" ] || [ "$first" -ge 1169 ]'

  echo; echo "── 파. 깎지 않았다(건너뛰기·경고 예외·무시 표시가 늘지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; plus="$(git diff "$B" -- . ":!$A/scripts/section4-GM.sh" | grep -c -E "^\+.*($marks)")"; minus="$(git diff "$B" -- . ":!$A/scripts/section4-GM.sh" | grep -c -E "^-.*($marks)")"; echo "  더한 줄 $plus · 뺀 줄 $minus (이 스크립트는 뺀다: 무늬를 글자로 적은 줄이 있다)"; [ "$plus" -le "$minus" ]'
}

pure_extra_part() {
  echo; echo "── 사(덧). 0줄 구역에 남는 낡은 글이 기준 그대로 있다(고치지 않았다)"
  run 'git diff --quiet "$B" -- "$A/esgapi/core/calc/documents.py" "$A/esgapi/core/calc/jobs.py" "$A/esgapi/reconcile/calc/job_summary.py" "$A/esgapi/config/celery.py" "$A/esgapi/inventory/prompts/README.md" compose.yaml "$A/esgapi/core/migrations/0002_documents_jobs.py"'
  # 짧은 꼴(esgapi 없이 적은 옛 경로)은 0줄 구역의 일곱 줄만 남는다(발주서 §4 사가 줄 번호로 든 것. 뿌리 compose.yaml:133 은 위 줄이 본다).
  run 'short="(^|[^a-z_./])(core/(adapters|ports|documents)|(accounts|inventory|reference)/(auth|entities|exchange|permissions|schemas|selectors|services|tokens|importer)\.py|reconcile/services|core/api\.py)"; (cd "$A" && git grep -nIE "$short" -- . "${EX[@]}" | cut -d: -f1,2 | sort > "$T/short.txt"); cat "$T/short.txt" | tr "\n" " "; echo; printf "%s\n" esgapi/config/celery.py:26 esgapi/config/celery.py:39 esgapi/core/calc/documents.py:121 esgapi/core/calc/jobs.py:4 esgapi/core/calc/jobs.py:78 esgapi/inventory/prompts/README.md:16 esgapi/reconcile/calc/job_summary.py:16 | sort | diff - "$T/short.txt"'
  echo; echo "── 자. 심은 파손 19"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks.sh" > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=19/19" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
  echo; echo "── 차. README 대조(README 는 작업 트리, 코드는 HEAD)"
  run '(cd "$A" && uv run --frozen python scripts/readme_audit.py paths --rev HEAD > "$T/paths.txt" 2>&1; code=$?; tail -1 "$T/paths.txt"; grep -q "못 찾음 0$" "$T/paths.txt" && exit $code; grep "못 찾음\|없다" "$T/paths.txt" | head -20; exit 1)'
  run '(cd "$A" && uv run --frozen python scripts/readme_audit.py forward --rev HEAD > "$T/forward.txt" 2>&1; code=$?; tail -6 "$T/forward.txt"; grep -q "^표 10/10$" "$T/forward.txt" && grep -q "^모듈 6/6$" "$T/forward.txt" && grep -q "^계약 5/5$" "$T/forward.txt" && grep -q "^FORWARD=OK$" "$T/forward.txt" && exit $code; exit 1)'
  run '(cd "$A" && uv run --frozen python scripts/readme_audit.py facts HEAD > "$T/facts.txt" 2>&1; code=$?; grep -n "모듈별 동작" "$T/facts.txt"; sum="$(grep "모듈별 동작" "$T/facts.txt" | sed "s/config [0-9]*//" | grep -o -E " [0-9]+ " | paste -sd+ - | bc)"; echo "  모듈별 동작의 합(config 의 상태 확인 둘을 뺀 것): $sum (15 = 동작 17 − 상태 확인 2)"; test "$sum" = 15 && exit $code; exit 1)'
  echo; echo "── 타. 휠"
  run '"$A/scripts/check-wheel.sh" 2>&1 | tail -4; exit ${PIPESTATUS[0]}'
}

# 한 층을 돌리고 EXIT 를 찍는다. 끝 줄이 「<건수> passed」로 시작해야 한다. 다시 돌리지 않는다.
layer() { # <이름> <건수> <명령…>
  local name="$1" want="$2" code started=$SECONDS last
  shift 2
  echo; echo "▶ $*"
  "$@" > "$T/layer.txt" 2>&1; code=$?
  tail -3 "$T/layer.txt"
  last="$(tail -1 "$T/layer.txt")"
  case "$last" in "$want passed"*) ;; *) echo "★ 끝 줄이 「$want passed」로 시작하지 않는다"; code=1 ;; esac
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  if [ "$code" -ne 0 ]; then
    grep -E "^(FAILED|ERROR)" "$T/layer.txt" | head -30
    memory_pressure | grep percentage
    [ "$name" = "통합 층" ] && docker compose logs --no-color --tail 80 api-py migrate-py worker-py queue parser
  fi
}

containers_part() {
  echo; echo "── 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. scripts/worktree-env.sh GM 으로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  local PROJECT; PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test -n "$PROJECT" && test "$PROJECT" != esg-app'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'                                                                # 포트 넷이 비어 있다
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  # api-py·worker-py 가 postgres·migrate-py·storage·queue 를 끌고 뜬다. TS 의 api·worker·redis 는 띄우지 않는다.
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  run 'docker compose exec -T worker-py python -c "from urllib.parse import urlsplit; from esgapi.config.celery import app; print(app.conf.broker_url.split(\":\")[0]); assert urlsplit(app.conf.broker_url).hostname == \"queue\""'   # 브로커는 로컬 흉내
  run 'docker compose logs --no-color worker-py | grep -E "jobs\.parse|ready\." | head -3 ; docker compose logs --no-color worker-py | grep -q "jobs.parse"'   # 태스크가 등록됐다
  layer "업무 층" 316 "$A/scripts/test-business.sh" -n 2
  layer "보안 층" 67 "$A/scripts/test-security.sh"
  layer "통합 층" 14 "$A/scripts/test-integration.sh" -s
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 9'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do git log -1 --format=%B "$c" | grep -q -x "Ticket: MARC-TICK-67" || { echo "★ 트레일러가 없다: $c"; bad=1; }; done; [ "$bad" = 0 ]'
}

# 옛 경로 글자 검사에서 보지 않는 것(apps/api-py 에서 본 pathspec): 기록 스크립트, 마이그레이션, 이 밴드의 검사 둘과
# 기준의 노드 ID 목록(옛 경로가 파라미터 이름으로 든 자료다).
EX=(':!scripts/section4*.sh' ':!scripts/planted-breaks-*.sh' ':!esgapi/*/tests/planted-breaks-*.sh' ':!scripts/rehearsal.sh' ':!*/migrations/*' ':!scripts/gm_check.py' ':!scripts/section4-GM.sh' ':!scripts/gm-nodeids-3a0fa3a.txt')
if [ "$MODE" = --step ] && [ "$STEP" -lt 8 ]; then EX+=(':!scripts/planted-breaks.sh' ':!scripts/readme_audit.py'); fi

case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --containers) containers_part ;;
  --after-commit) step_part; pure_extra_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
