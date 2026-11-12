#!/usr/bin/env bash
# 밴드 T1c(MARC-TICK-89: TS 통합을 compose 프로필 ts 로 전량에서 빼고, Python 통합의 쉼을 워커의 값에서 끌어내고,
# TS 의 시험 셋을 Python 으로 옮긴다)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-T1c.sh --step <1~4>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-T1c.sh --pure           --step 4 + 심은 파손(planted-breaks-T1c.sh --pure)
#         apps/api-py/scripts/section4-T1c.sh --containers     문 → 짓기·띄우기(짧은 값) → Python 통합 연속 5회 → 기본값 판 한 번
#                                                              → 심은 파손(--containers) → 내림. 판정에 든다
#         apps/api-py/scripts/section4-T1c.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서). rehearsal.sh 는 부르지 않는다. AI 공급사 호출 0.
# 네트워크는 uv·docker·pnpm 의 설치·받기뿐이다. macOS /bin/bash 3.2 에서 돈다.
#
# ★ 기준 B 는 이 워크트리의 바닥(main b83f6f1, 밴드 FK2 병합 뒤 = 발주서의 바닥).
set -u
cd "$(dirname "$0")/../../.."
B=b83f6f1   # 기준 커밋(워크트리의 바닥)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=4
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [1-4]) ;; *) echo "사용: $0 --step <1~4>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <1~4> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
A=apps/api-py
# 바뀌어도 되는 것(발주서 §1-2 의 닫힌 목록)
ALLOWED='^(compose\.yaml|\.env\.example|scripts/verify\.sh|scripts/check-gates\.sh|README\.md|apps/api-py/esgapi/config/celery\.py|apps/api-py/esgapi/config/env\.py|apps/api-py/esgapi/config/tests/test_env\.py|apps/api-py/esgapi/core/tests/test_celery_conf\.py|apps/api-py/tests_integration/(test_worker_flow|test_flow|conftest)\.py|apps/api-py/scripts/section4-T1c\.sh|apps/api-py/scripts/planted-breaks-T1c\.sh)$'
# 0줄이어야 하는 자리(발주서 §4 마)
ZERO='apps/web apps/server packages tests services infra docker generated package.json pnpm-lock.yaml pnpm-workspace.yaml scripts/git-hooks scripts/worktree-env.sh scripts/section4-PD2.sh apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/conftest.py apps/api-py/tests apps/api-py/esgapi/config/settings'
# README 에서 고쳐도 되는 기준 줄의 범위(발주서 원본 요약의 :15·:251·:262·:1975·:1996 근처. :86 은 0줄)
README_WINDOWS='13-24 249-253 260-266 1580-1590 1973-1977 1994-1998'
# 기준 B 의 Python 통합 노드 ID 열일곱(발주서 2-5 의 2. 그대로 남아야 한다)
BASE_NODES='test_flow.py::test_container_runs_as_non_root_and_has_no_owner_address
test_flow.py::test_exchange_then_me_then_sites
test_flow.py::test_migrate_py_ran_once_and_succeeded
test_flow.py::test_ready_and_alive
test_flow.py::test_readyz_is_503_while_the_db_is_down_and_recovers
test_flow.py::test_sigterm_stops_gracefully
test_observability_flow.py::test_a_well_formed_id_comes_back_and_a_malformed_one_is_replaced
test_observability_flow.py::test_every_response_carries_a_request_id
test_observability_flow.py::test_one_request_leaves_exactly_one_access_line
test_parser_flow.py::test_adapter_reaches_the_running_parser_and_yields_fact_candidates
test_upload_flow.py::test_the_adapter_works_against_the_running_storage
test_upload_flow.py::test_upload_goes_straight_to_the_storage_and_the_server_only_keeps_the_state
test_worker_flow.py::test_a_killed_workers_job_is_taken_over_after_the_lease_and_ends_once
test_worker_flow.py::test_an_object_swapped_after_the_confirm_is_not_parsed
test_worker_flow.py::test_an_uploaded_pdf_goes_through_the_queue_the_worker_and_the_parser_to_done
test_worker_flow.py::test_bytes_that_are_not_a_pdf_fail_once_with_the_parsers_code
test_worker_flow.py::test_when_the_broker_is_down_the_confirm_still_answers_and_a_second_confirm_recovers'
# 컨테이너 단계 일곱(글자·차례. 발주서 1-1 의 2)
CONTAINER_SEVEN='docker compose down -v --remove-orphans
docker compose build
docker compose up -d --wait
apps/api-py/scripts/test-business.sh -n 2
apps/api-py/scripts/test-security.sh
apps/api-py/scripts/test-integration.sh
docker compose down -v'
TS_FOUR='api migrate redis worker'

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
load1() { uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p'; }
free_pct() { memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p'; }
others() { docker ps --format '{{.Names}}' 2>/dev/null | grep -c '^esg-app'; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
steps_of() { grep '^step: ' | sed 's/^step: //'; }

echo "── 밴드 T1c §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · 1분 부하 $(load1) · free $(free_pct)% · esg-app* 컨테이너 $(others)"

fast_part() { # 가
  echo; echo "── 가. 빠른 게이트: VERIFY_FAST=PASS · EXIT= 15줄"
  local started=$SECONDS l0 c0
  l0="$(load1)"; c0="$(others)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; e="$(grep -c "^EXIT=" "$T/fast.log")"; echo "  종료 코드 $code · EXIT= ${e}줄 · 0 이 아닌 EXIT $(grep "^EXIT=" "$T/fast.log" | grep -vc "^EXIT=0$") · $(grep "^(전체" "$T/fast.log")"; tail -1 "$T/fast.log"; [ "$code" = 0 ] && [ "$(tail -1 "$T/fast.log")" = "VERIFY_FAST=PASS" ] && [ "$e" = 15 ]'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · 1분 부하 $l0 → $(load1) · esg-app* 컨테이너 $c0 → $(others))"
}

gates_part() { # 나
  echo; echo "── 나. 게이트 자기 검사(check-gates.sh)"
  run 'scripts/check-gates.sh > "$T/gates.log" 2>&1; code=$?; grep -E "^(▶|EXIT=)" "$T/gates.log" | paste - - | grep -v "EXIT=0$" | sed "s/^/  ★ /"; tail -1 "$T/gates.log"; echo "  기록: $T/gates.log"; [ "$code" = 0 ] && tail -1 "$T/gates.log" | grep -q -E "^GATES=PASS ([0-9]+)/\1$"'
}

profile_part() { # 다
  echo; echo "── 다. 프로필(컨테이너 없이): config --services 7 · --profile ts 11 · config -q 0 · TS 넷은 기본에 없다"
  run 'docker compose config --services | sort > "$T/svc.default"; docker compose --profile ts config --services | sort > "$T/svc.ts"; echo "  기본 $(wc -l < "$T/svc.default" | tr -d " "): $(tr "\n" " " < "$T/svc.default")"; echo "  --profile ts $(wc -l < "$T/svc.ts" | tr -d " ")"; [ "$(wc -l < "$T/svc.default" | tr -d " ")" = 7 ] && [ "$(wc -l < "$T/svc.ts" | tr -d " ")" = 11 ] && ! grep -q -x -E "api|worker|migrate|redis" "$T/svc.default" && [ "$(comm -13 "$T/svc.default" "$T/svc.ts" | tr "\n" " ")" = "$TS_FOUR " ]'
  run 'docker compose config -q && docker compose --profile ts config -q'
}

plan_part() { # 라
  echo; echo "── 라. 계획: step: 22 · pnpm test:integration 0줄 · 컨테이너 일곱의 글자·차례"
  run 'scripts/verify.sh --plan > "$T/plan.full"; scripts/verify.sh --fast --plan > "$T/plan.fast"; steps_of < "$T/plan.full" > "$T/steps.full"; steps_of < "$T/plan.fast" > "$T/steps.fast"; awk "NR == FNR { f[++n] = \$0; next } i < n && \$0 == f[i + 1] { i++; next } { print }" "$T/steps.fast" "$T/steps.full" > "$T/steps.rest"; echo "  전량 $(wc -l < "$T/steps.full" | tr -d " ") − 빠른 $(wc -l < "$T/steps.fast" | tr -d " ") = $(wc -l < "$T/steps.rest" | tr -d " ")"; sed "s/^/    /" "$T/steps.rest"; [ "$(wc -l < "$T/steps.full" | tr -d " ")" = 22 ] && ! grep -q "test:integration" "$T/plan.full" && [ "$(cat "$T/steps.rest")" = "$CONTAINER_SEVEN" ]'
  [ "$STEP" -ge 3 ] && run 'grep "^# .*CELERY_WAIT_TIME_SECONDS" "$T/plan.full" | sed "s/^/  /"; grep -q "^# .*CELERY_WAIT_TIME_SECONDS=[0-9]* .*JOB_RETRY_DELAY_SECONDS=[0-9]*" "$T/plan.full" && ! grep -q "CELERY_WAIT_TIME_SECONDS" "$T/plan.fast"'
}

bounds_part() { # 마·바·사
  echo; echo "── 마. 경계: 바뀐 파일 ⊆ §1-2, 0줄 구역, README 는 고쳐도 되는 줄만"
  run 'changed > "$T/changed.txt"; sed "s/^/  /" "$T/changed.txt"; ! grep -v -E "$ALLOWED" "$T/changed.txt"'
  run 'git diff --quiet "$B" -- $ZERO && test -z "$(git ls-files --others --exclude-standard -- $ZERO)"'
  run 'for f in $(git ls-tree -r --name-only "$B" -- apps/api-py/scripts); do git diff --quiet "$B" -- "$f" || { echo "★ 지난 밴드의 스크립트가 바뀌었다: $f"; exit 1; }; done'
  run 'git diff -U0 "$B" -- README.md | sed -n "s/^@@ -\([0-9]*\)\(,\([0-9]*\)\)\{0,1\} .*/\1 \3/p" > "$T/readme.hunks"; bad=0; while read -r s n; do [ -z "$n" ] && n=1; e=$((s + (n > 0 ? n - 1 : 0))); ok=0; for w in $README_WINDOWS; do lo=${w%-*}; hi=${w#*-}; [ "$s" -ge "$lo" ] && [ "$e" -le "$hi" ] && ok=1; done; echo "  README 기준 줄 $s~$e $([ $ok = 1 ] && echo 안 || echo ★밖)"; [ $ok = 1 ] || bad=1; done < "$T/readme.hunks"; [ "$bad" = 0 ]'

  echo; echo "── 바. 제품 코드: esgapi 의 테스트 밖 변경은 config/celery.py·config/env.py 둘뿐"
  run 'git diff --name-only "$B" -- apps/api-py/esgapi ":!**/tests/**" > "$T/prod.txt"; git diff --stat "$B" -- apps/api-py/esgapi ":!**/tests/**" | sed "s/^/  /"; [ "$(sort "$T/prod.txt" | tr "\n" " ")" = "apps/api-py/esgapi/config/celery.py apps/api-py/esgapi/config/env.py " ]'

  echo; echo "── 사. 운영 기본값 불변: 빈 환경의 BrokerSettings(10·120·60·75)·JobSettings(90·3·5)·폴링 간격 1"
  run '(cd "$A" && uv run --frozen python -c "
from esgapi.config import celery
from esgapi.config.env import BrokerSettings, JobSettings, load_broker_settings, load_job_settings
p = []
j = load_job_settings({}, p)
b = load_broker_settings({\"CELERY_BROKER_URL\": \"sqs://queue:9324\", \"CELERY_BROKER_REGION\": \"r\", \"CELERY_QUEUE_URL\": \"http://queue:9324/0/q\", \"CELERY_BROKER_SECURE\": \"false\"}, p, lease_s=j.lease_s)
got = (b.wait_time_seconds, b.visibility_timeout_s, b.task_soft_time_limit_s, b.task_time_limit_s, j.lease_s, j.max_attempts, j.retry_delay_s, celery.POLLING_INTERVAL_S, p)
print(\"  \", got)
assert got == (10, 120, 60, 75, 90, 3, 5, 1, []), got
")'
}

nodes_part() { # 아
  echo; echo "── 아. 통합 노드 ID ⊇ 기준의 열일곱(빠진 것 0) · 새 것"
  run 'printf "%s\n" "$BASE_NODES" | sort > "$T/nodes.base"; (cd "$A" && uv run --frozen pytest -q --collect-only -p no:cacheprovider -c tests_integration/pytest.ini tests_integration 2> "$T/collect.err" | grep "::" | sed "s|^tests_integration/||" | sort > "$T/nodes.now"); echo "  지금 $(wc -l < "$T/nodes.now" | tr -d " ") · 기준 $(wc -l < "$T/nodes.base" | tr -d " ")"; comm -13 "$T/nodes.base" "$T/nodes.now" | sed "s/^/  + /"; m="$(comm -23 "$T/nodes.base" "$T/nodes.now")"; [ -n "$m" ] && printf "%s\n" "$m" | sed "s/^/  ★ 빠짐 /"; [ -z "$m" ] && [ "$(wc -l < "$T/nodes.base" | tr -d " ")" = 17 ]'
}

sleeps_part() { # 자 (커밋 ③부터)
  echo; echo "── 자. 쉼: time.sleep( 의 줄이 기대 목록과 글자로 같다 · 숫자 글자 쉼 가운데 ≥ 3 은 0 · 쉼이 값에서 끌어내졌다"
  run 'git grep -h "time.sleep(" -- "$A/tests_integration" | sed "s/^ *//" | sort > "$T/sleeps.now"; printf "%s\n" "$SLEEPS_EXPECTED" | sort > "$T/sleeps.want"; sed "s/^/  /" "$T/sleeps.now"; diff "$T/sleeps.want" "$T/sleeps.now"'
  run '! git grep -n -E "sleep\(([3-9]|[1-9][0-9]+)(\.[0-9]+)?\)" -- "$A/tests_integration"'
  run 'f="$A/tests_integration/conftest.py"; w="$A/tests_integration/test_worker_flow.py"; grep -n -E "^POLL_SETTLE_S = WAIT_TIME_S \+ 1$" "$w" && grep -n -E "^NOT_RETRIED_S = RETRY_DELAY_S \+ 2$" "$w" && grep -n -E "^WAIT_TIME_S = worker_value\(\"CELERY_WAIT_TIME_SECONDS\", 10\)( |$)" "$f" && grep -n -E "^RETRY_DELAY_S = worker_value\(\"JOB_RETRY_DELAY_SECONDS\", 5\)( |$)" "$f"'
}

trailers_part() { # 타
  echo; echo "── 타. 커밋 트레일러: $B..HEAD 의 커밋마다 Ticket: MARC-TICK-89 와 Derives-from: MARC-TICK-71"
  run 'n=0; bad=0; for c in $(git rev-list "$B"..HEAD); do n=$((n + 1)); msg="$(git log -1 --format=%B "$c")"; printf "%s\n" "$msg" | grep -q -x "Ticket: MARC-TICK-89" && printf "%s\n" "$msg" | grep -q -x "Derives-from: MARC-TICK-71" || { echo "★ 트레일러가 없다: $c"; bad=1; }; done; echo "  커밋 $n"; [ "$bad" = 0 ]'
}

# 커밋 ③ 뒤 tests_integration 의 time.sleep( 줄(앞 공백을 뗀 글자). 바뀌면 이 목록과 보고의 쉼 표를 같이 고친다.
SLEEPS_EXPECTED='time.sleep(0.2)
time.sleep(0.5)
time.sleep(NOT_RETRIED_S)
time.sleep(2)
time.sleep(POLL_SETTLE_S)
time.sleep(POLL_SETTLE_S)'

step_part() {
  fast_part
  [ "$STEP" -ge 2 ] && gates_part
  [ "$STEP" -ge 2 ] && profile_part
  [ "$STEP" -ge 2 ] && plan_part
  bounds_part
  nodes_part
  [ "$STEP" -ge 3 ] && sleeps_part
  trailers_part
}

pure_extra_part() { # 차
  echo; echo "── 차. 심은 파손(planted-breaks-T1c.sh --pure): 다 잡힘, 지문 같음"
  run "$A/scripts/planted-breaks-T1c.sh --pure > \"\$T/planted.pure.log\" 2>&1; code=\$?; grep -E '^(#|PLANTED=|지문|★)' \"\$T/planted.pure.log\"; echo \"  기록: \$T/planted.pure.log\"; [ \"\$code\" = 0 ] && tail -1 \"\$T/planted.pure.log\" | grep -q -E '^PLANTED=([0-9]+)/\\1\$'"
}

# 컨테이너 앞의 문(발주서 2-6): 다른 esg-app* 컨테이너가 0 이 될 때까지 60초마다 최대 30분, 그 뒤 free ≥ 20% · 1분 부하 < 12.
gate() {
  local tries=0 n free load
  while :; do
    n="$(others)"; free="$(free_pct)"; load="$(load1)"
    if [ "$n" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: 떠 있는 esg-app* 컨테이너 0 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    if [ "$tries" -ge 30 ]; then
      echo "  ★ 문이 30분 안 열렸다: esg-app* 컨테이너 $n · free ${free:-?}% · 1분 부하 ${load:-?}"
      echo "  ★ 떠 있는 프로젝트: $(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | sort -u | tr '\n' ' ')"
      return 1
    fi
    tries=$((tries + 1)); sleep 60
  done
}
timed() { # <이름> <명령…>   걸린 초를 찍는다(판정은 run 이 한다)
  local name="$1" s=$SECONDS l0; shift; l0="$(load1)"
  "$@" > "$T/$name.log" 2>&1; local code=$?
  echo "  $name: $((SECONDS - s))초 · 종료 $code · 1분 부하 $l0 → $(load1) · free $(free_pct)%"
  tail -3 "$T/$name.log" | sed 's/^/    /'
  return $code
}
integ() { # <기록 이름>   Python 통합 전체 한 번(--durations=0). 걸린 초·끝 줄·부하를 찍는다
  local s=$SECONDS l0 c0 f0; l0="$(load1)"; c0="$(others)"; f0="$(free_pct)"
  PYTEST_ADDOPTS=--durations=0 "$A/scripts/test-integration.sh" > "$T/$1.log" 2>&1; local code=$?
  local secs=$((SECONDS - s))
  echo "$secs" >> "$T/$1.secs"
  echo "  $1: ${secs}초 · 종료 $code · $(grep -E '[0-9]+ (passed|failed)' "$T/$1.log" | tail -1) · 1분 부하 $l0 → $(load1) · free $f0% → $(free_pct)% · esg-app* 컨테이너 $c0 → $(others)"
  [ "$code" = 0 ] && grep -E '[0-9]+ (passed|failed)' "$T/$1.log" | tail -1 | grep -q -E '^=* *21 passed'
}
worker_ready() { local i; for i in $(seq 1 120); do docker compose logs --no-color worker-py 2> /dev/null | grep -q ' ready\.' && return 0; sleep 0.5; done; return 1; }

containers_part() { # 카
  echo; echo "── 카. 컨테이너: 문 → 짓기·띄우기(짧은 값) → Python 통합 연속 5회 → 심은 파손(짧은 값 판) → 기본값 판 한 번 → 심은 파손(기본값 판) → 내림"
  [ -f .env ] || scripts/worktree-env.sh T1c
  PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | tail -1)"
  echo "  compose 프로젝트 $PROJECT"
  [ "$PROJECT" = esg-app-t1c ] || { echo "  ★ .env 의 프로젝트가 esg-app-t1c 가 아니다 — 띄우지 않는다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return; }
  if ! gate; then echo "EXIT=1"; FAILS=$((FAILS + 1)); GATE_TIMEOUT=1; return; fi
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  # 전량 게이트(scripts/verify.sh)와 같은 짧은 값
  export CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
  echo "  짧은 값: CELERY_WAIT_TIME_SECONDS=$CELERY_WAIT_TIME_SECONDS JOB_RETRY_DELAY_SECONDS=$JOB_RETRY_DELAY_SECONDS"
  run 'timed down0 docker compose down -v --remove-orphans'
  run 'timed build docker compose build'
  run 'timed up docker compose up -d --wait && docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" " " && echo && ! docker compose ps --format "{{.Service}}" | grep -q -x -E "api|worker|migrate|redis"'

  echo; echo "  ── 3-3 Python 통합 연속 5회(짧은 값)"
  local i
  for i in 1 2 3 4 5; do run "integ short.$i"; done
  run 'sort -n "$T"/short.*.secs > "$T/short.sorted"; med="$(sed -n 3p "$T/short.sorted")"; p=0; for f in "$T"/short.*.log; do grep -E "[0-9]+ (passed|failed)" "$f" | tail -1 | grep -q -E "^=* *21 passed" && p=$((p + 1)); done; echo "  5회의 초: $(tr "\n" " " < "$T/short.sorted")· 중앙값 ${med}초 (전 90초, 실측 로그) · PASS $p/5"; [ "$p" = 5 ] && [ "$(cat "$T"/short.*.secs | wc -l | tr -d " ")" = 5 ] && [ "$med" -lt 90 ]'

  echo; echo "  ── 심은 파손(짧은 값 판)"
  run "$A/scripts/planted-breaks-T1c.sh --containers > \"\$T/planted.short.log\" 2>&1; code=\$?; grep -E '^(#|PLANTED=|지문|★)' \"\$T/planted.short.log\"; [ \"\$code\" = 0 ] && tail -1 \"\$T/planted.short.log\" | grep -q -E '^PLANTED=([0-9]+)/\\1\$'"

  echo; echo "  ── 기본값 판 한 번: 내보낸 두 값을 지운 같은 환경으로 api-py·worker-py 를 다시 만들고 통합 전체"
  unset CELERY_WAIT_TIME_SECONDS JOB_RETRY_DELAY_SECONDS
  run 'docker compose up -d --no-deps --force-recreate --wait api-py worker-py > "$T/default.up.log" 2>&1 && worker_ready && sleep 11 && echo "  worker-py 의 긴 폴링: $(docker compose exec -T worker-py python -c "from esgapi.config.celery import app; print(app.conf.broker_transport_options[\"wait_time_seconds\"])" | tail -1)"'
  run 'integ default.1'
  run "$A/scripts/planted-breaks-T1c.sh --containers > \"\$T/planted.default.log\" 2>&1; code=\$?; grep -E '^(#|PLANTED=|지문|★)' \"\$T/planted.default.log\"; [ \"\$code\" = 0 ] && tail -1 \"\$T/planted.default.log\" | grep -q -E '^PLANTED=([0-9]+)/\\1\$'"

  echo; echo "  ── 내림(전량의 글자 docker compose down -v) → 프로필 ts 까지 치움 → 남은 것 0"
  run 'timed down docker compose down -v'
  run 'docker compose --profile ts down -v --remove-orphans > "$T/down.ts.log" 2>&1; c="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $c · 볼륨 $v"; [ "$c" = 0 ] && [ "$v" = 0 ]'
  echo "  기록: $T (short.*.log · default.1.log · planted.*.log · build/up/down.log)"
}

after_commit_part() { # 파
  echo; echo "── 파. 커밋된 모습"
  run 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  git status --porcelain ${n}줄"; test "$n" = 0'
  run 'git log --format="%h %s" "$B"..HEAD | sed "s/^/  /"; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 4'
}

GATE_TIMEOUT=0
case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --containers) containers_part ;;
  --after-commit) step_part; pure_extra_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
[ "$GATE_TIMEOUT" = 1 ] && echo "컨테이너 문 30분 — 띄우지 않았다(감독에게 알린다)"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
