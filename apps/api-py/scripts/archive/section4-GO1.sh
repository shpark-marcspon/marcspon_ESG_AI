#!/usr/bin/env bash
# 밴드 GO1(MARC-TICK-70: request ID 와 한 줄 JSON 로그, system check 를 게이트에, 개인 경로 걷기)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-GO1.sh --step <0~6>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-GO1.sh --pure           --step 6 전부 + 심은 파손 + 휠
#         apps/api-py/scripts/section4-GO1.sh --containers     컨테이너 층 한 번(띄우기 → 업무 → 보안 → 통합 → 로그 재기 → 내리기 → 이미지 치우기)
#         apps/api-py/scripts/section4-GO1.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. AWS 로 나가는 호출 0: 브로커는 compose 의 queue(SQS 흉내, sqs://queue:9324)뿐이다.
# 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ makemigrations --check 와 manage.py check 는 호스트에서 test_business 설정으로 돈다(DB 없이).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 「깎지 않았다」(파)는 이 스크립트와 planted-breaks-GO1.sh 를 뺀다(무늬를 글자로 적은 줄이 있다).
set -u
cd "$(dirname "$0")/../../.."
B=aae8afa   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=6
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-6]) ;; *) echo "사용: $0 --step <0~6>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~6> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
TEST_DS=esgapi.config.settings.test_business
NODES="$A/scripts/go1-nodeids-aae8afa.txt"
OWN=(":!$A/scripts/section4-GO1.sh" ":!$A/scripts/planted-breaks-GO1.sh" ":!$NODES")

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
# 추적 안 된 새 파일 가운데 이 스크립트 둘과 노드 목록이 아닌 것(「깎지 않았다」가 그 글도 본다).
untracked() { git ls-files --others --exclude-standard | grep -v -E '/scripts/(section4-GO1\.sh|planted-breaks-GO1\.sh|go1-nodeids-aae8afa\.txt)$'; }
# 허용 경로(발주서 §1-2) 밖에서 바뀐 파일. 줄마다 저장소 뿌리에서 시작하는 꼴이다.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/observability/(__init__|context|jsonlog|middleware)\.py$' \
    -e '^apps/api-py/esgapi/config/settings/base\.py$' \
    -e '^apps/api-py/esgapi/config/celery\.py$' \
    -e '^apps/api-py/gunicorn\.conf\.py$' \
    -e '^apps/api-py/esgapi/core/resources/queue\.py$' \
    -e '^apps/api-py/esgapi/config/tests/test_system_check\.py$' \
    -e '^apps/api-py/esgapi/config/tests/test_settings\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_jobs_hook\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_observability_(context|jsonlog|layers|middleware|worker|api)\.py$' \
    -e '^apps/api-py/tests_integration/test_observability_flow\.py$' \
    -e '^apps/api-py/scripts/(section4-GO1\.sh|planted-breaks-GO1\.sh|go1-nodeids-aae8afa\.txt)$' \
    -e '^apps/api-py/scripts/section4-(PY5|PY6|PY7|PY8b|PY8c)\.sh$' \
    -e '^apps/api-py/esgapi/inventory/tests/data/scope3/make-golden\.sh$' \
    -e '^apps/api-py/esgapi/reconcile/tests/golden/(check_lab\.py|dump\.mts|make-golden\.sh)$' \
    -e '^services/parser/scripts/planted\.py$'
}
# 더해져도 되는 노드 ID(발주서 §3-1: 새 테스트 파일 일곱과 「더하기만」 두 파일의 새 함수).
NEW_NODES='^esgapi/config/tests/test_system_check\.py::|^esgapi/core/tests/test_observability_(context|jsonlog|layers|middleware|worker|api)\.py::|^esgapi/config/tests/test_settings\.py::test_the_request_id_middleware_is_first\[|^esgapi/core/tests/test_jobs_hook\.py::(test_a_failed_send_is_logged_with_the_job_id_and_still_raised|test_a_sent_note_logs_nothing|test_an_unknown_kind_is_raised_without_a_record)$'
# 그 커밋까지 선 새 순수 테스트 파일(api 는 업무 층이라 컨테이너에서 돈다).
new_pure_tests() {
  [ "$STEP" -ge 3 ] && echo esgapi/core/tests/test_observability_context.py esgapi/core/tests/test_observability_jsonlog.py esgapi/core/tests/test_observability_layers.py
  [ "$STEP" -ge 4 ] && echo esgapi/core/tests/test_observability_middleware.py esgapi/config/tests/test_settings.py
  [ "$STEP" -ge 5 ] && echo esgapi/core/tests/test_observability_worker.py esgapi/core/tests/test_jobs_hook.py
  return 0
}
# 컨테이너 앞의 문: 다른 esg-app* 컨테이너가 0 이 될 때까지 60초마다 최대 30분, 그 뒤 verify.lock 없음 · free ≥ 20% · 1분 부하 < 12.
gate() {
  local tries=0 others free load lock
  lock="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
  while :; do
    others="$(docker ps --format '{{.Names}}' | grep -c '^esg-app')"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" = 0 ] && [ ! -e "$lock" ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: 떠 있는 esg-app* 컨테이너 0 · verify.lock 없음 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: esg-app* 컨테이너 $others · verify.lock $([ -e "$lock" ] && echo 있음 || echo 없음) · free ${free:-?}% · 1분 부하 ${load:-?} · 30분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

echo "── 밴드 GO1 §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄(1,508 이상 passed, 건너뛴 것·경고 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; n="$(echo "$last" | sed -n "s/^\([0-9]*\) passed.*/\1/p")"; [ "${n:-0}" -ge 1508 ] || exit 1; echo "$last" | grep -q -E "failed|skipped|xfailed|xpassed|warning|error" && exit 1; exit $code)'

  echo; echo "── 나. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일"
  run 'git diff --quiet "$B" -- "$A/generated"'
  run 'for f in openapi.json api.d.ts api.d.ts.source-sha256; do test "$(sha "$A/generated/$f")" = "$(git show "$B:$A/generated/$f" | shasum -a 256 | cut -d" " -f1)" || { echo "★ 다르다: $f"; exit 1; }; done; echo "  openapi.json $(wc -c < "$A/generated/openapi.json" | tr -d " ") B · sha256 $(sha "$A/generated/openapi.json" | cut -c1-16)"; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; echo "  표준 오류 $(wc -l < "$T/export.err" | tr -d " ")줄"; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 다. 마이그레이션 0, makemigrations 가 낼 것 없음, pyproject.toml·uv.lock 0줄"
  run 'test "$(git diff --stat "$B" -- "*/migrations/*" | wc -l | tr -d " ")" = 0 && test "$(changed | grep -c "/migrations/")" = 0'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'git diff --quiet "$B" -- "$A/pyproject.toml" "$A/uv.lock"'

  echo; echo "── 라. 노드 ID: 기준의 것이 하나도 사라지지 않았다, 더해진 것은 새 테스트뿐"
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt"); test "$(wc -l < "$NODES" | tr -d " ")" = 1891 && test "$(sha "$NODES" | cut -c1-16)" = b5b24a95a60cedc8 || { echo "★ 기준의 목록이 바뀌었다"; exit 1; }; gone="$(comm -23 "$NODES" "$T/nodeids.txt" | wc -l | tr -d " ")"; comm -13 "$NODES" "$T/nodeids.txt" > "$T/added.txt"; other="$(grep -v -c -E "$NEW_NODES" "$T/added.txt")"; echo "  지금 $(wc -l < "$T/nodeids.txt" | tr -d " ") · 사라진 것 $gone · 더해진 것 $(wc -l < "$T/added.txt" | tr -d " ") (새 테스트가 아닌 것 $other)"; cut -d: -f1 "$T/added.txt" | sort | uniq -c; comm -23 "$NODES" "$T/nodeids.txt" | head -10; grep -v -E "$NEW_NODES" "$T/added.txt" | head -10; [ "$gone" = 0 ] && [ "$other" = 0 ]'
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider -c tests_integration/pytest.ini tests_integration 2>/dev/null | grep "::" | sort > "$T/nodeids-int.txt"); grep -v "^test_observability_flow\.py::" "$T/nodeids-int.txt" > "$T/nodeids-int-old.txt"; n="$(wc -l < "$T/nodeids-int.txt" | tr -d " ")"; old="$(wc -l < "$T/nodeids-int-old.txt" | tr -d " ")"; h="$(sha "$T/nodeids-int-old.txt" | cut -c1-16)"; echo "  통합 ${n}건 (있던 것 $old · $h · 새 것 $((n - old)))"; test "$old" = 14 && test "$h" = 2b622935f489eea7 && { [ "$((n - old))" = 0 ] || [ "$((n - old))" = 3 ]; }'

  if [ "$STEP" -ge 1 ]; then
    echo; echo "── 사. 개인 경로: apps/api-py·services 에 0, 뿌리 scripts 에는 남는 한 파일 2줄, 옛 section4 다섯은 적힌 줄만"
    run 'git grep -cE "/Users/[a-z]+" -- apps/api-py services; test "$(git grep -cE "/Users/[a-z]+" -- apps/api-py services | wc -l | tr -d " ")" = 0'
    run 'git grep -cE "/Users/[a-z]+" -- scripts; test "$(git grep -cE "/Users/[a-z]+" -- scripts)" = "scripts/section4-PD2.sh:2"'
    run 'git diff --numstat "$B" -- "$A/scripts/section4-PY5.sh" "$A/scripts/section4-PY6.sh" "$A/scripts/section4-PY7.sh" "$A/scripts/section4-PY8b.sh" "$A/scripts/section4-PY8c.sh" | tee "$T/numstat.txt"; test "$(cut -f1,2 "$T/numstat.txt" | tr "\t\n" " ;")" = "1 1;1 1;1 1;1 1;2 2;"'
  fi

  if [ "$STEP" -ge 2 ]; then
    echo; echo "── 마. system check: 테스트 일곱이 순수 층에서 초록, 명령으로도 「no issues (0 silenced)」"
    run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_system_check.py 2>&1 | tail -1 | tee "$T/check-test.txt"; grep -q "^7 passed" "$T/check-test.txt")'
    run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python -W error manage.py check --fail-level WARNING > "$T/check.txt" 2>&1; code=$?; tail -1 "$T/check.txt"; test "$(tail -1 "$T/check.txt")" = "System check identified no issues (0 silenced)." && exit $code; exit 1)'
    run '(cd "$A" && n="$(uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "not django_db and not security" 2>/dev/null | grep -c "test_system_check\.py::")"; echo "  순수 층에 든 test_system_check 노드 $n"; [ "$n" -ge 7 ])'
  fi

  if [ "$STEP" -ge 3 ]; then
    echo; echo "── 바. request ID 가 제품 코드에 있다(기준 0)"
    run '(cd "$A" && n="$(git grep --untracked -ciE "request.?id" -- esgapi gunicorn.conf.py ":!esgapi/**/tests/**" | awk -F: "{n+=\$2} END {print n+0}")"; base="$(git grep -ciE "request.?id" "$B" -- esgapi gunicorn.conf.py ":!esgapi/**/tests/**" | awk -F: "{n+=\$NF} END {print n+0}")"; echo "  지금 ${n}줄 · 기준 ${base}줄"; [ "$n" -gt 0 ] && [ "$base" = 0 ])'
    echo; echo "── 새 순수 테스트 파일(커밋 $STEP 까지 선 것)"
    run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" $(new_pure_tests) 2>&1 | tail -1 | tee "$T/new-tests.txt"; code=${PIPESTATUS[0]}; grep -q -E "failed|skipped|xfailed|warning|error" "$T/new-tests.txt" && exit 1; exit $code)'
  fi

  echo; echo "── 아. 계약 5 KEPT, .importlinter 0줄"
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; grep -E "^[가나다라마]\. " "$T/lint.txt"; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 5 kept, 0 broken." && exit $code; exit 1)'
  run 'git diff --quiet "$B" -- "$A/.importlinter"'

  echo; echo "── 차. 경계"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n (바뀐 파일 전부 $(changed | wc -l | tr -d " "))"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- compose.yaml scripts docker infra apps/web apps/server packages README.md'
  run 'git diff --quiet "$B" -- "$A/esgapi/core/tenancy" "$A/esgapi/reconcile/tasks.py" "$A/esgapi/config/api.py" "$A/esgapi/core/__init__.py" "$A/esgapi/core/tests/test_celery_conf.py" "$A/esgapi/config/settings/migrate.py" "$A/esgapi/config/settings/test_business.py" "$A/esgapi/config/settings/test_security.py" "$A/conftest.py" "$A/tests" "$A/esgapi/core/service"'
  run 'n="$(git diff "$B" -- "$A/esgapi/config/tests/test_settings.py" "$A/esgapi/core/tests/test_jobs_hook.py" | grep -c "^-[^-]")"; echo "  「더하기만」 두 파일의 - 줄: $n"; [ "$n" = 0 ]'
  run 'changed | grep "^services/" | tr "\n" " "; echo; if [ "$STEP" -ge 1 ]; then test "$(changed | grep "^services/")" = services/parser/scripts/planted.py; else test -z "$(changed | grep "^services/")"; fi'

  if [ "$STEP" -ge 5 ]; then
    echo; echo "── 카. celery_conf 의 dict 와 갈고리·태스크 등록이 그대로"
    run 'git diff --quiet "$B" -- "$A/esgapi/core/tests/test_celery_conf.py" && (cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/core/tests/test_celery_conf.py esgapi/core/tests/test_jobs_hook.py esgapi/reconcile/tests/test_tasks_registered.py 2>&1 | tail -1 | tee "$T/celery-tests.txt"; code=${PIPESTATUS[0]}; grep -q -E "failed|skipped|warning|error" "$T/celery-tests.txt" && exit 1; exit $code)'
  fi

  echo; echo "── 파. 깎지 않았다(건너뛰기·경고 예외·무시 표시·끈 system check 가 늘지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|type: ignore|pyright: ignore|SILENCED_SYSTEM_CHECKS"; { git diff "$B" -- . "${OWN[@]}" | grep -E "^\+" | grep -v "^+++"; untracked | while IFS= read -r f; do sed "s/^/+/" "$f"; done; } > "$T/plus.txt"; n="$(grep -c -E "$marks" "$T/plus.txt")"; q="$(grep -c "noqa" "$T/plus.txt")"; bad="$(grep "noqa" "$T/plus.txt" | grep -v -c "# noqa: B010")"; grep -n -E "$marks|noqa" "$T/plus.txt" | cut -c1-200; echo "  더한 줄 $(wc -l < "$T/plus.txt" | tr -d " ") 가운데 무늬에 걸린 것 $n · noqa $q (B010 이 아닌 것 $bad)"; [ "$n" = 0 ] && [ "$q" -le 1 ] && [ "$bad" = 0 ]'
}

pure_extra_part() {
  echo; echo "── 자. 심은 파손 15"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-GO1.sh" > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=15/15" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
  echo; echo "── 타. 휠(이미지에 core/observability/ 가 실린다)"
  run '"$A/scripts/check-wheel.sh" > "$T/wheel.txt" 2>&1; code=$?; tail -4 "$T/wheel.txt"; exit $code'
  run '(cd "$A" && w="$(mktemp -d)" && uv build --wheel --out-dir "$w" > /dev/null 2>&1 && n="$(unzip -Z1 "$w"/*.whl | grep -c -E "^esgapi/core/observability/(__init__|context|jsonlog|middleware)\.py$")"; echo "  휠에 실린 core/observability 파일 $n"; [ "$n" = 4 ])'
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

# 컨테이너의 로그를 잰다. <api|worker> <로그 파일> 또는 leak <로그 파일…>. 표본 몇 줄을 찍고(보고에 옮긴다), 어긋나면 그 줄을 찍고 1 로 끝난다.
check_logs() {
  python3 - "$@" <<'PY'
import json
import re
import sys

FIELDS = {
    "ts", "level", "logger", "pid", "message", "request_id", "task_id", "task_name", "job_id",
    "method", "path", "status", "duration_ms", "exc",
}
kind, path = sys.argv[1:3]
if kind == "leak":
    # 두 로그에 넣지 말 것이 없는가. (1) 글자: JSON 줄은 exc 칸을 뺀 나머지에서, JSON 이 아닌 줄(배너)은 글자 그대로
    # tenant_id·esg_session·「Bearer 」 0. exc(스택)에는 소스 코드의 줄이 실린다(값이 아니라 글자다. 예:
    # `send(tenant_id=tenant_id, …)`). (2) 값: 두 로그 전체(message·exc 포함)에 테넌트 id 의 값 0 —
    # 통합 층이 쓰는 꼴 it-<8자 16진>-a|b 와 저장소 키의 tenants/. 예외의 글에 값이 실리는 길을 여기서 잡는다.
    words = re.compile(r"tenant_id|esg_session|Bearer ")
    values = re.compile(r"it-[0-9a-f]{8}-[ab]\b|tenants/")
    found: list[str] = []
    total = in_exc = 0
    for name in sys.argv[2:]:
        for line in open(name, encoding="utf-8").read().split("\n"):
            if not line.strip():
                continue
            total += 1
            outside = line
            if line.startswith("{"):
                try:
                    record = json.loads(line)
                    in_exc += 1 if words.search(str(record.get("exc", ""))) else 0
                    outside = json.dumps({k: v for k, v in record.items() if k != "exc"}, ensure_ascii=False)
                except ValueError:
                    pass
            if words.search(outside):
                found.append("exc 밖에 그 글자가 있다: " + line[:300])
            if values.search(line):
                found.append("테넌트 id 의 값이 있다: " + line[:300])
    for item in found[:20]:
        print("★ " + item)
    print(f"  두 로그 {total}줄 · exc 밖의 tenant_id·esg_session·Bearer 와 테넌트 id 의 값: {len(found)}"
          f" · (참고) exc 안의 소스 줄에 그 글자가 든 줄 {in_exc}")
    sys.exit(1 if found else 0)
lines = [line for line in open(path, encoding="utf-8").read().split("\n") if line.strip()]
bad: list[str] = []
records: list[dict[str, object]] = []
plain: list[str] = []
for line in lines:
    if kind == "worker" and not line.startswith("{"):
        plain.append(line)
        continue
    try:
        record = json.loads(line)
    except ValueError:
        bad.append("JSON 이 아니다: " + line[:300])
        continue
    if not isinstance(record, dict) or not set(record) <= FIELDS:
        bad.append("칸이 닫힌 목록 밖이다: " + line[:300])
        continue
    records.append(record)


def sample(label: str, found: list[dict[str, object]]) -> None:
    if found:
        print(f"  표본({label}): " + json.dumps(found[0], ensure_ascii=False, separators=(",", ":"))[:400])


if kind == "api":
    access = [r for r in records if r.get("logger") == "esgapi.access"]
    if not access:
        bad.append("esgapi.access 의 줄이 없다")
    bad += [f"접근 줄에 request_id 가 없다: {r}" for r in access if not isinstance(r.get("request_id"), str)]
    bad += ["gunicorn 꼴의 접근 줄: " + line[:200] for line in lines if '"GET /' in line or '"POST /' in line]
    sample("접근 줄", access)
    late = [r for r in records if r.get("logger") == "django.request"]
    sample("4xx·5xx 의 django.request 줄", late)
    if late:
        sample("같은 요청의 접근 줄", [r for r in access if r.get("request_id") == late[0].get("request_id")])
    sample("gunicorn 의 뜨는 줄", [r for r in records if r.get("logger") == "gunicorn.error"])
    # 커밋 뒤 갈고리가 브로커에 못 닿은 줄(통합 층이 브로커를 내려 본다). 요청 안에서 난 줄이라 request_id 가 실려야 한다.
    unsent = [r for r in records if str(r.get("message", "")).startswith("queue_send_failed job_id=")]
    bad += [f"queue_send_failed 줄에 request_id 가 없다: {r}" for r in unsent if not isinstance(r.get("request_id"), str)]
    sample("queue_send_failed 줄", unsent)
    if not unsent:
        bad.append("queue_send_failed 줄이 없다(통합 층이 브로커를 내린 채 올림 확인을 부른다. 1 이상이어야 한다)")
    print(f"  queue_send_failed 줄 {len(unsent)} (전부 request_id 있음: {all('request_id' in r for r in unsent)})")
    print(f"  api-py: 줄 {len(lines)} · JSON {len(records)} · 접근 줄 {len(access)} · django.request {len(late)}"
          f" · django.request 가운데 request_id 있는 것 {sum(1 for r in late if 'request_id' in r)}")
else:
    finished = [r for r in records if str(r.get("message", "")).startswith("job_finished ")]
    if not finished:
        bad.append("job_finished 줄이 없다")
    for r in finished:
        named = re.search(r"job_id=(\S+)", str(r["message"]))
        if named is None or r.get("job_id") != named.group(1) or r.get("task_name") != "jobs.parse" or "task_id" not in r:
            bad.append(f"job_finished 줄의 칸이 글과 어긋난다: {r}")
    bad += ["Traceback 이 든 맨 글 줄: " + line[:200] for line in plain if "Traceback" in line]
    # 자식 프로세스가 죽은 줄(통합 층이 워커를 죽인다)은 multiprocessing 로거의 JSON 이어야 한다. 맨 글이면 처리기가 없다.
    bad += ["맨 글로 나온 자식 프로세스의 줄: " + line[:200] for line in plain if " exited with " in line]
    sample("multiprocessing 로거의 줄", [r for r in records if r.get("logger") == "multiprocessing"])
    sample("job_finished 줄", finished)
    sample("부모의 received 줄", [r for r in records if " received" in str(r.get("message", ""))])
    print(f"  worker-py: 줄 {len(lines)} · JSON {len(records)} · job_finished {len(finished)} · JSON 이 아닌 줄(배너) {len(plain)}")
    for line in plain[:3]:
        print("    | " + line[:120])
for item in bad[:20]:
    print("★ " + item)
print(f"  어긋난 것 {len(bad)}")
sys.exit(1 if bad else 0)
PY
}

containers_part() {
  echo; echo "── 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. scripts/worktree-env.sh GO1 으로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  local PROJECT; PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test -n "$PROJECT" && test "$PROJECT" != esg-app'
  run 'gate'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'                                                                # 포트 넷이 비어 있다
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  # api-py·worker-py 가 postgres·migrate-py·storage·queue 를 끌고 뜬다. TS 의 api·worker·redis 는 띄우지 않는다.
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  run 'docker compose exec -T worker-py python -c "from urllib.parse import urlsplit; from esgapi.config.celery import app; print(app.conf.broker_url.split(\":\")[0]); assert urlsplit(app.conf.broker_url).hostname == \"queue\""'   # 브로커는 로컬 흉내
  run 'docker compose logs --no-color worker-py | grep -q "jobs.parse"'   # 태스크가 등록됐다(배너)
  layer "업무 층" 319 "$A/scripts/test-business.sh" -n 2
  layer "보안 층" 67 "$A/scripts/test-security.sh"
  layer "통합 층" 17 "$A/scripts/test-integration.sh" -s
  echo; echo "── 컨테이너의 로그(통합 층이 지난 뒤)"
  docker compose logs --no-color --no-log-prefix api-py > "$T/api.log" 2>&1
  docker compose logs --no-color --no-log-prefix worker-py > "$T/worker.log" 2>&1
  echo "  로그 사본: $T/api.log · $T/worker.log"
  run 'check_logs api "$T/api.log"'
  run 'check_logs worker "$T/worker.log"'
  run 'check_logs leak "$T/api.log" "$T/worker.log"'
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 7'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do git log -1 --format=%B "$c" | grep -q -x "Ticket: MARC-TICK-70" || { echo "★ 트레일러가 없다: $c"; bad=1; }; done; [ "$bad" = 0 ]'
}

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
