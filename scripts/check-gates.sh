#!/usr/bin/env bash
# 게이트 자체의 자기 검사: scripts/verify.sh(--fast·--plan·잠금·빌드 잠금·Node 판 점검·전량의 실행 조건 줄),
# scripts/with-build-lock.sh, scripts/git-hooks/pre-commit, scripts/lib/lock.sh 의 free_percent 를 잰다.
#   사용: scripts/check-gates.sh        검사마다 EXIT=<종료 코드>, 마지막 줄 GATES=PASS|FAIL <통과>/<전체>
# 진짜 docker 를 부르지 않는다. 전량 모드는 PATH 앞에 둔 가짜 docker·pnpm·uv·node(임시 폴더, 부른 것을 적는다)로
# 끝까지 돌리고, 잠금은 임시 폴더의 자리(VERIFY_LOCK_DIR·BUILD_LOCK_DIR)에서만 잡는다 — 진짜 잠금 자리는 계산하지도 않는다.
# pre-commit 은 자기 워크트리에서 잰다: 임시 색인(GIT_INDEX_FILE)에 추적 안 되는 새 파일 하나를 올리고 훅을 부른 뒤 지운다.
# 진짜 uv 와 apps/api-py/.venv 가 있어야 한다(없으면 그 검사가 빨갛다). 끝나면 git status 가 처음과 같다.
#
# verify.sh 나 pre-commit 을 고친 밴드가 자기 §4 에서 부른다. verify.sh 는 이것을 부르지 않는다.
# 이 검사가 못 보는 것: 진짜 docker·pnpm 이 도는 전량(그것은 전량 한 번이 잰다), 사람의 Ctrl-C(프로세스 묶음 전체에
# 가는 신호. 여기서는 verify.sh 한 프로세스에만 보낸다), 30초 간격의 기다림(1초로 줄여 잰다),
# 진짜 도구가 동시에 돌 때의 CPU 경쟁과 흔들림(그것은 진짜 --fast 를 여러 번 돌려 잰다).
set -u
cd "$(dirname "$0")/.."
ROOT="$PWD"
V="$ROOT/scripts/verify.sh"
HOOK="$ROOT/scripts/git-hooks/pre-commit"
REAL_PATH="$PATH"

T="$(mktemp -d)"
BIN="$T/bin"
LOG="$T/calls.log"
LOCKDIR="$T/lock/verify.lock"
BLOCKDIR="$T/lock/build.lock"   # 빌드 잠금도 임시 자리다(진짜 <git 공통 폴더>/build.lock 은 계산하지 않는다)
SEEN="$T/build-lock.seen"       # 가짜 도구가 불릴 때 빌드 잠금을 쥔 pid(없으면 「없음」). STUB_LOG 와 따로 둔다
W="$ROOT/scripts/with-build-lock.sh"
mkdir -p "$BIN" "$T/lock"
probes=()   # 훅 검사가 심는 파일(끝에서 지운다)
cleanup() {
  for f in "${probes[@]:-}"; do [ -n "$f" ] && rm -f "$f"; done
  if [ -n "${SLEEPER:-}" ]; then kill "$SLEEPER" 2>/dev/null; wait "$SLEEPER" 2>/dev/null; fi
  rm -rf "$T"
}
trap cleanup EXIT

status_before="$(git status --porcelain)"

# ── 가짜 도구: 부른 것을 한 줄로 적고(표준 출력에도 stub-out 한 줄), 고른 것만 실패하거나 잠깐 자거나 줄을 죽인다 ──
# STUB_SLEEP_ON 은 「|」 로 여럿을 받는다. STUB_DIE_ON 에 맞으면 자기를 부른 verify.sh 의 서브셸들(줄과 in_api_py)을
# kill -9 로 죽인다(맨 위의 verify.sh 는 남긴다) — 줄이 단계의 종료 코드를 못 남기고 죽는 꼴.
for tool in docker pnpm uv node git; do
  cat > "$BIN/$tool" <<'STUB'
#!/usr/bin/env bash
me="$(basename "$0")"
echo "$me $*" >> "$STUB_LOG"
if [ "$me" = git ]; then PATH="$STUB_REAL_PATH" exec git "$@"; fi
[ -n "${STUB_LOCK_SEEN:-}" ] && echo "$me $* · $(cat "${BUILD_LOCK_DIR:-/nonexistent}/pid" 2>/dev/null || echo 없음)" >> "$STUB_LOCK_SEEN"
[ "$me $*" = "node -v" ] && echo "${STUB_NODE_VERSION:-v22.0.0}"
[ "$me $*" = "node -v" ] || echo "stub-out $me $*"
[ "$me $*" = "docker compose ls -q" ] && [ -n "${STUB_COMPOSE_LS:-}" ] && printf '%s\n' $STUB_COMPOSE_LS
if [ -n "${STUB_DIE_ON:-}" ] && [ "$me $*" = "$STUB_DIE_ON" ]; then
  chain="" p=$PPID
  while ps -o args= -p "$p" 2>/dev/null | grep -q 'scripts/verify\.sh'; do chain="$chain $p"; p="$(ps -o ppid= -p "$p" | tr -d ' ')"; done
  sleep 7 &   # 죽는 줄이 남기는 단계 프로세스의 흉내(이 단계의 출력 파일을 쥔 채 남는다)
  set -- $chain
  while [ "$#" -gt 1 ]; do kill -9 "$1"; shift; done
  exit 1
fi
case "|${STUB_SLEEP_ON:-}|" in *"|$me $*|"*) sleep "${STUB_SLEEP_S:-2}" ;; esac
if [ -n "${STUB_FAIL_ON:-}" ] && [ "$me $*" = "$STUB_FAIL_ON" ]; then exit 1; fi
exit 0
STUB
  chmod +x "$BIN/$tool"
done
# 가짜 도구로 verify.sh 를 돌린다. 잠금은 늘 임시 자리다(빌드 잠금도). 물려받은 되들어감 표지(BUILD_LOCK_HELD_BY)는 비운다.
stubbed() { PATH="$BIN:$REAL_PATH" STUB_REAL_PATH="$REAL_PATH" STUB_LOG="$LOG" VERIFY_LOCK_DIR="$LOCKDIR" BUILD_LOCK_DIR="$BLOCKDIR" BUILD_LOCK_HELD_BY= STUB_LOCK_SEEN="$SEEN" "$@"; }
reset() { : > "$LOG"; rm -rf "$LOCKDIR" "$LOCKDIR".reap "$LOCKDIR".stale.* "$BLOCKDIR" "$BLOCKDIR".reap "$BLOCKDIR".stale.*; : > "$SEEN"; }

total=0
passed=0
check() { # <이름> <함수>
  echo
  echo "▶ $1"
  reset
  "$2"
  local code=$?
  echo "EXIT=$code"
  total=$((total + 1))
  [ "$code" -eq 0 ] && passed=$((passed + 1))
  return 0
}
say() { echo "  $*"; }
# <기대 줄들의 파일> 이 <실제 줄들의 파일> 안에 그 순서로 있는가(사이에 다른 줄이 끼어도 된다)
in_order() { awk 'NR == FNR { want[++n] = $0; next } i < n && $0 == want[i + 1] { i++ } END { exit !(i == n) }' "$1" "$2"; }
steps_of() { grep '^step: ' | sed 's/^step: //'; }

# 컨테이너 없이 도는 단계 열다섯(앞몫 셋 + 동시 묶음 열둘)과 컨테이너 단계 일곱(TS 통합은 전량에 없다 — 프로필 ts).
# 이 목록은 verify.sh 와 따로 적은 기대다(verify.sh 는 이것을 읽지 않는다).
PURE_STEPS='node_is_22_or_newer
pnpm install --frozen-lockfile
in_api_py uv sync --frozen
pnpm -r typecheck
pnpm -r test
uv run --project services/parser --frozen pytest -q services/parser
uv run --project services/parser --frozen ruff check services/parser
uv run --project services/parser --frozen ruff format --check services/parser
uv run --project services/parser --frozen pyright -p services/parser
in_api_py uv run --frozen ruff check .
in_api_py uv run --frozen ruff format --check .
in_api_py uv run --frozen lint-imports
in_api_py uv run --frozen python scripts/check_test_layout.py
in_api_py uv run --frozen pyright
in_api_py uv run --frozen pytest -q -n 4 --durations=15 -m not django_db and not security'
# 그 가운데 동시 묶음의 열둘(--plan 의 「# 동시 묶음 시작」·「# 동시 묶음 끝」 사이)
BUNDLE_STEPS="$(printf '%s\n' "$PURE_STEPS" | tail -n 12)"
CONTAINER_STEPS='docker compose down -v --remove-orphans
docker compose build
docker compose up -d --wait
apps/api-py/scripts/test-business.sh -n 2
security_with_storage
apps/api-py/scripts/test-integration.sh
docker compose down -v'

stubbed "$V" --plan > "$T/plan.full" 2>&1
stubbed "$V" --fast --plan > "$T/plan.fast" 2>&1
steps_of < "$T/plan.full" > "$T/steps.full"
steps_of < "$T/plan.fast" > "$T/steps.fast"
# 계획에서 동시 묶음 안의 단계(주석 두 줄 사이)
bundle_of() { awk '/^# 동시 묶음 시작/ { on = 1; next } /^# 동시 묶음 끝/ { on = 0 } on' | steps_of; }
bundle_of < "$T/plan.full" > "$T/bundle.full"

# ── 계획 ──────────────────────────────────────────────────────────────
fast_plan_has_no_docker() {
  local n; n="$(grep -c docker "$T/plan.fast")"
  say "--fast --plan 의 docker 줄: $n (단계 $(wc -l < "$T/steps.fast" | tr -d ' ')개)"
  [ "$n" -eq 0 ] && [ "$(cat "$T/steps.fast")" = "$PURE_STEPS" ]
}
fast_plan_is_inside_full_plan() { in_order "$T/steps.fast" "$T/steps.full"; }
full_minus_fast_is_the_seven() {
  # 전량의 단계에서 빠른 게이트의 단계를 (순서대로) 뺀 나머지
  awk 'NR == FNR { fast[++n] = $0; next } i < n && $0 == fast[i + 1] { i++; next } { print }' "$T/steps.fast" "$T/steps.full" > "$T/steps.rest"
  say "전량 $(wc -l < "$T/steps.full" | tr -d ' ') − 빠른 $(wc -l < "$T/steps.fast" | tr -d ' ') = $(wc -l < "$T/steps.rest" | tr -d ' ')"
  [ "$(cat "$T/steps.rest")" = "$CONTAINER_STEPS" ] || { diff <(echo "$CONTAINER_STEPS") "$T/steps.rest" | sed 's/^/    /'; return 1; }
}
# compose.yaml 에 TS 뼈대(프로필 ts, 서비스 api·worker·migrate·redis)가 없고 docker/server.Dockerfile 도 없다(글자로 본다. docker 를 부르지 않는다).
# 이것이 깨지면 기본 build·up(전량의 컨테이너 단계)이 걷어낸 TS 를 다시 짓거나 없는 Dockerfile 을 찾는다.
compose_has_no_ts() {
  awk '/^services:/ { on = 1; next }
    on && /^[a-z]/ { on = 0 }
    on && /^  [a-z][a-z0-9-]*:/ { svc = $1; sub(/:$/, "", svc); print svc }' "$ROOT/compose.yaml" | sort > "$T/compose.services"
  local bad=0 s
  say "서비스: $(tr '\n' ' ' < "$T/compose.services")"
  for s in api worker migrate redis; do
    grep -qx "$s" "$T/compose.services" && { say "★ 서비스 $s 가 있다"; bad=1; }
  done
  grep -nE 'profiles:.*"ts"|server\.Dockerfile' "$ROOT/compose.yaml" | sed 's/^/    ★ /' | grep . && bad=1
  [ -e "$ROOT/docker/server.Dockerfile" ] && { say "★ docker/server.Dockerfile 이 있다"; bad=1; }
  [ "$bad" -eq 0 ]
}
unknown_argument_exits_2() {
  stubbed "$V" --nope > "$T/out" 2>&1
  local code=$?
  say "종료 코드 $code"
  [ "$code" -eq 2 ] && grep -q '사용:' "$T/out" && [ ! -s "$LOG" ]
}
plan_takes_no_lock_and_calls_nothing() { [ ! -s "$LOG" ] && [ ! -e "$LOCKDIR" ]; }

# ── 가짜 도구로 돌린 전량 ─────────────────────────────────────────────
# 계획의 단계 하나가 가짜 도구를 어떻게 부르는가(스크립트 셋은 안에서 uv 를 부른다)
calls_of_plan() {
  sed -e 's/^node_is_22_or_newer$/node -v/' -e 's/^in_api_py //' \
    -e 's|^apps/api-py/scripts/test-business.sh -n 2$|uv run --frozen pytest -q -m django_db -n 2|' \
    -e 's|^security_with_storage$|uv run --frozen pytest -q --ds=esgapi.config.settings.test_security -m security|' \
    -e 's|^apps/api-py/scripts/test-integration.sh$|uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration|'
}
full_run_calls_every_planned_step_in_order() {
  stubbed "$V" > "$T/out" 2>&1
  local code=$?
  grep '^▶ ' "$T/out" | sed 's/^▶ //' > "$T/ran"
  # 앞몫과 컨테이너 단계는 차례대로, 동시 묶음 안은 차례가 없으니 같은 집합인지만 본다
  grep -v -x -F -f "$T/bundle.full" "$T/steps.full" | calls_of_plan > "$T/want.calls"
  calls_of_plan < "$T/bundle.full" | sort > "$T/want.bundle"
  grep -x -F -f "$T/want.bundle" "$LOG" | sort > "$T/got.bundle"
  grep -v -x -F -f "$T/want.bundle" "$LOG" > "$T/got.serial"
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · ▶ $(wc -l < "$T/ran" | tr -d ' ')줄 · 가짜 도구 호출 $(wc -l < "$LOG" | tr -d ' ')줄(묶음 $(wc -l < "$T/got.bundle" | tr -d ' '))"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/out")" = "VERIFY=PASS" ] && diff "$T/steps.full" "$T/ran" > /dev/null &&
    [ "$(wc -l < "$T/steps.full" | tr -d ' ')" -eq 22 ] && [ "$(wc -l < "$T/bundle.full" | tr -d ' ')" -eq 12 ] &&
    [ "$(cat "$T/bundle.full")" = "$BUNDLE_STEPS" ] && diff "$T/want.bundle" "$T/got.bundle" > /dev/null &&
    in_order "$T/want.calls" "$T/got.serial" && [ ! -e "$LOCKDIR" ] && ! grep -q 'git-common-dir' "$LOG"
}
fast_run_calls_no_docker() {
  stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  grep '^▶ ' "$T/out" | sed 's/^▶ //' > "$T/ran"
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · docker 호출 $(grep -c '^docker ' "$LOG")"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/out")" = "VERIFY_FAST=PASS" ] && ! grep -q 'VERIFY=' "$T/out" &&
    diff "$T/steps.fast" "$T/ran" > /dev/null && ! grep -q '^docker ' "$LOG" && ! grep -q 'test:integration\|django_db -n\|test_security\|tests_integration' "$LOG"
}
failing_step_fails_and_releases_the_lock() {
  STUB_FAIL_ON="docker compose build" stubbed "$V" > "$T/out" 2>&1
  local code=$?
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out")"
  [ "$code" -eq 1 ] && [ "$(tail -1 "$T/out")" = "VERIFY=FAIL" ] && [ ! -e "$LOCKDIR" ]
}
# 신호: 뒤에서 띄운 프로세스는 SIGINT 를 무시한 채 시작하므로 perl 로 기본 동작을 되돌려 띄운다.
signal_releases_the_lock() { # <신호> <기대 종료 코드>
  # env 로 띄운다(셸 함수로 띄우면 $! 가 verify.sh 가 아니라 감싼 셸의 번호다).
  env PATH="$BIN:$REAL_PATH" STUB_REAL_PATH="$REAL_PATH" STUB_LOG="$LOG" VERIFY_LOCK_DIR="$LOCKDIR" \
    BUILD_LOCK_DIR="$BLOCKDIR" BUILD_LOCK_HELD_BY= STUB_LOCK_SEEN="$SEEN" \
    STUB_SLEEP_ON="docker compose build" STUB_SLEEP_S=2 perl -e '$SIG{INT} = "DEFAULT"; exec @ARGV' "$V" > "$T/out" 2>&1 &
  local pid=$! tries=0
  while [ ! -e "$LOCKDIR/pid" ] && [ "$tries" -lt 50 ]; do sleep 0.1; tries=$((tries + 1)); done
  local held; held="$(cat "$LOCKDIR/pid" 2>/dev/null)"
  while ! grep -q '^docker compose build$' "$LOG" && [ "$tries" -lt 100 ]; do sleep 0.1; tries=$((tries + 1)); done
  kill "-$1" "$pid"
  wait "$pid"
  local code=$?
  say "SIG$1: 잠금을 쥐었던 pid ${held:-없음} · 종료 코드 $code · 그 뒤 잠금 폴더 $([ -e "$LOCKDIR" ] && echo 있음 || echo 없음)"
  [ "$held" = "$pid" ] && [ "$code" -eq "$2" ] && [ ! -e "$LOCKDIR" ] && ! grep -q '^docker compose up' "$LOG"
}
sigint_releases_the_lock() { signal_releases_the_lock INT 130; }
sigterm_releases_the_lock() { signal_releases_the_lock TERM 143; }

# ── 잠금 ──────────────────────────────────────────────────────────────
sleep 300 &
SLEEPER=$!   # 살아 있는 남의 pid
foreign_lock() { # <pid>
  mkdir -p "$LOCKDIR"
  echo "$1" > "$LOCKDIR/pid"
  echo "/다른/워크트리" > "$LOCKDIR/worktree"
  echo "2026-01-01 00:00:00" > "$LOCKDIR/started"
}
dead_pid() { (exit 0) & local pid=$!; wait "$pid"; echo "$pid"; }
live_lock_makes_full_wait_then_locked() {
  foreign_lock "$SLEEPER"
  VERIFY_LOCK_WAIT_S=1 VERIFY_LOCK_POLL_S=1 stubbed "$V" > "$T/out" 2>&1
  local code=$?
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · 그 뒤 잠금의 pid $(cat "$LOCKDIR/pid" 2>/dev/null)(남의 것 $SLEEPER)"
  [ "$code" -eq 75 ] && [ "$(tail -1 "$T/out")" = "VERIFY=LOCKED" ] && grep -q '기다린다' "$T/out" &&
    [ "$(cat "$LOCKDIR/pid" 2>/dev/null)" = "$SLEEPER" ] && [ ! -s "$LOG" ]
}
fast_and_plan_ignore_a_held_lock() {
  foreign_lock "$SLEEPER"
  stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  stubbed "$V" --plan > "$T/out.plan" 2>&1
  local plan_code=$?
  say "--fast 종료 코드 $code · --plan 종료 코드 $plan_code · 그 뒤 잠금의 pid $(cat "$LOCKDIR/pid" 2>/dev/null)(남의 것 $SLEEPER)"
  [ "$code" -eq 0 ] && [ "$plan_code" -eq 0 ] && ! grep -q '기다린다\|LOCKED' "$T/out" "$T/out.plan" &&
    [ "$(cat "$LOCKDIR/pid" 2>/dev/null)" = "$SLEEPER" ] && [ "$(cat "$LOCKDIR/worktree")" = "/다른/워크트리" ]
}
dead_lock_is_taken_over() {
  local dead; dead="$(dead_pid)"
  foreign_lock "$dead"
  VERIFY_LOCK_WAIT_S=0 stubbed "$V" > "$T/out" 2>&1
  local code=$?
  say "죽은 pid $dead · 종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · 「죽은 잠금」 줄 $(grep -c '죽은 잠금을 치운다' "$T/out")"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/out")" = "VERIFY=PASS" ] && grep -q '죽은 잠금을 치운다' "$T/out" &&
    [ ! -e "$LOCKDIR" ] && [ -z "$(ls -d "$LOCKDIR".* 2>/dev/null)" ]
}
two_runs_on_one_dead_lock_only_one_holds() {
  local round codes builds ok=0
  for round in 1 2 3 4 5; do
    reset
    foreign_lock "$(dead_pid)"
    STUB_SLEEP_ON="docker compose build" STUB_SLEEP_S=1 VERIFY_LOCK_WAIT_S=0 stubbed "$V" > "$T/out.a" 2>&1 &
    local a=$!
    STUB_SLEEP_ON="docker compose build" STUB_SLEEP_S=1 VERIFY_LOCK_WAIT_S=0 stubbed "$V" > "$T/out.b" 2>&1 &
    local b=$!
    wait "$a"; local ca=$?
    wait "$b"; local cb=$?
    codes="$(printf '%s\n%s\n' "$ca" "$cb" | sort -n | tr '\n' ' ')"
    builds="$(grep -c '^docker compose build$' "$LOG")"
    say "${round}회: 종료 코드 ${codes}· docker compose build 를 부른 실행 ${builds}"
    [ "$codes" = "0 75 " ] && [ "$builds" -eq 1 ] && [ ! -e "$LOCKDIR" ] && ok=$((ok + 1))
  done
  [ "$ok" -eq 5 ]
}
node_20_fails_at_the_first_step() {
  STUB_NODE_VERSION=v20.11.1 stubbed "$V" > "$T/out" 2>&1
  local code=$?
  say "종료 코드 $code · 첫 단계 「$(grep -m1 '^▶ ' "$T/out")」 $(grep -m1 '^EXIT=' "$T/out") · 가짜 도구 호출: $(tr '\n' ';' < "$LOG")"
  [ "$code" -eq 1 ] && [ "$(grep -m1 '^▶ ' "$T/out")" = "▶ node_is_22_or_newer" ] && [ "$(grep -m1 '^EXIT=' "$T/out")" = "EXIT=1" ] &&
    [ "$(tail -1 "$T/out")" = "VERIFY=FAIL" ] && grep -q 'Node 22 이상' "$T/out" && [ "$(cat "$LOG")" = "node -v" ] && [ ! -e "$LOCKDIR" ]
}

# ── 빌드 잠금(전량) ───────────────────────────────────────────────────
foreign_build_lock() { # <pid>
  mkdir -p "$BLOCKDIR"
  echo "$1" > "$BLOCKDIR/pid"
  echo "/다른/워크트리" > "$BLOCKDIR/worktree"
  echo "2026-01-01 00:00:00" > "$BLOCKDIR/started"
}
# 가짜 도구로 전량을 뒤에서 띄운다($! 가 verify.sh 다 — perl 이 exec 한다). 인자는 더 줄 환경(NAME=값 …)
bg_full() {
  env PATH="$BIN:$REAL_PATH" STUB_REAL_PATH="$REAL_PATH" STUB_LOG="$LOG" VERIFY_LOCK_DIR="$LOCKDIR" \
    BUILD_LOCK_DIR="$BLOCKDIR" BUILD_LOCK_HELD_BY= STUB_LOCK_SEEN="$SEEN" "$@" \
    perl -e '$SIG{INT} = "DEFAULT"; exec @ARGV' "$V" > "$T/out" 2>&1 &
}
# 가짜 도구가 <호출> 로 불렸을 때 빌드 잠금을 쥔 pid(처음 한 번)
seen_holder() { awk -v want="$1 · " 'index($0, want) == 1 { print substr($0, length(want) + 1); exit }' "$SEEN"; }
b1_build_runs_inside_the_build_lock() {
  bg_full
  local pid=$! code
  wait "$pid"; code=$?
  say "종료 코드 $code · verify.sh pid $pid · build 때 잠금의 pid $(seen_holder 'docker compose build') · 첫 down 때 $(seen_holder 'docker compose down -v --remove-orphans')"
  [ "$code" -eq 0 ] && [ "$(seen_holder 'docker compose build')" = "$pid" ] &&
    [ "$(seen_holder 'docker compose down -v --remove-orphans')" = 없음 ] && ! grep -q 'git-common-dir' "$LOG"
}
b2_released_after_up_before_the_business_layer() {
  bg_full
  local pid=$! code
  wait "$pid"; code=$?
  say "종료 코드 $code · up 때 잠금의 pid $(seen_holder 'docker compose up -d --wait')(verify.sh $pid) · 업무 층 때 $(seen_holder 'uv run --frozen pytest -q -m django_db -n 2') · 끝난 뒤 잠금 폴더 $([ -e "$BLOCKDIR" ] && echo 있음 || echo 없음)"
  [ "$code" -eq 0 ] && [ "$(seen_holder 'docker compose up -d --wait')" = "$pid" ] &&
    [ "$(seen_holder 'uv run --frozen pytest -q -m django_db -n 2')" = 없음 ] && [ ! -e "$BLOCKDIR" ]
}
b3_pass_and_fail_leave_no_build_lock() {
  stubbed "$V" > "$T/out" 2>&1
  local pass=$?
  local after_pass; after_pass="$([ -e "$BLOCKDIR" ] && echo 있음 || echo 없음)"
  STUB_FAIL_ON="docker compose build" stubbed "$V" > "$T/out.fail" 2>&1
  local fail=$?
  say "PASS 판 종료 코드 $pass · 뒤 잠금 폴더 $after_pass · build 가 실패한 판 종료 코드 $fail($(tail -1 "$T/out.fail")) · 뒤 잠금 폴더 $([ -e "$BLOCKDIR" ] && echo 있음 || echo 없음)"
  [ "$pass" -eq 0 ] && [ "$after_pass" = 없음 ] && [ "$fail" -eq 1 ] && [ "$(tail -1 "$T/out.fail")" = "VERIFY=FAIL" ] && [ ! -e "$BLOCKDIR" ]
}
build_lock_released_on_signal() { # <신호> <기대 종료 코드>
  bg_full STUB_SLEEP_ON="docker compose build" STUB_SLEEP_S=2
  local pid=$! tries=0 code held
  while ! grep -q '^docker compose build$' "$LOG" && [ "$tries" -lt 100 ]; do sleep 0.1; tries=$((tries + 1)); done
  held="$(cat "$BLOCKDIR/pid" 2>/dev/null)"
  kill "-$1" "$pid"
  wait "$pid"; code=$?
  say "build 중 SIG$1: 빌드 잠금을 쥐었던 pid ${held:-없음}(verify.sh $pid) · 종료 코드 $code · 그 뒤 빌드 잠금 폴더 $([ -e "$BLOCKDIR" ] && echo 있음 || echo 없음)"
  [ "$held" = "$pid" ] && [ "$code" -eq "$2" ] && [ ! -e "$BLOCKDIR" ] && [ ! -e "$LOCKDIR" ]
}
b3_sigint_releases_the_build_lock() { build_lock_released_on_signal INT 130; }
b3_sigterm_releases_the_build_lock() { build_lock_released_on_signal TERM 143; }
b4_live_build_lock_makes_full_wait_then_locked() {
  foreign_build_lock "$SLEEPER"
  BUILD_LOCK_WAIT_S=1 BUILD_LOCK_POLL_S=1 stubbed "$V" > "$T/out" 2>&1
  local code=$?
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · build 호출 $(grep -c '^docker compose build$' "$LOG") · verify.lock $([ -e "$LOCKDIR" ] && echo 있음 || echo 없음) · 그 뒤 빌드 잠금의 pid $(cat "$BLOCKDIR/pid" 2>/dev/null)(남의 것 $SLEEPER)"
  [ "$code" -eq 75 ] && [ "$(tail -1 "$T/out")" = "VERIFY=LOCKED" ] && grep -q '빌드 잠금이 잡혀 있다: pid' "$T/out" &&
    grep -q "빌드 잠금이 잡혀 있다(1초 기다림): pid $SLEEPER · /다른/워크트리 · 2026-01-01 00:00:00 시작" "$T/out" &&
    ! grep -q '^docker compose build$' "$LOG" && [ ! -e "$LOCKDIR" ] &&
    [ "$(cat "$BLOCKDIR/pid" 2>/dev/null)" = "$SLEEPER" ] && [ "$(cat "$BLOCKDIR/worktree")" = "/다른/워크트리" ]
}
b5_dead_build_lock_is_taken_over() {
  local dead; dead="$(dead_pid)"
  foreign_build_lock "$dead"
  BUILD_LOCK_WAIT_S=0 stubbed "$V" > "$T/out" 2>&1
  local code=$?
  say "죽은 pid $dead · 종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · 「죽은 잠금」 줄 $(grep -c "죽은 잠금을 치운다(pid $dead 는 살아 있지 않다): $BLOCKDIR" "$T/out")"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/out")" = "VERIFY=PASS" ] && grep -q "죽은 잠금을 치운다(pid $dead 는 살아 있지 않다): $BLOCKDIR" "$T/out" &&
    [ ! -e "$BLOCKDIR" ] && [ -z "$(ls -d "$BLOCKDIR".* 2>/dev/null)" ]
}
b6_fast_and_plan_ignore_a_held_build_lock() {
  foreign_build_lock "$SLEEPER"
  stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  stubbed "$V" --plan > "$T/out.plan" 2>&1
  local plan_code=$?
  say "--fast 종료 코드 $code · --plan 종료 코드 $plan_code · 그 뒤 빌드 잠금의 pid $(cat "$BLOCKDIR/pid" 2>/dev/null)(남의 것 $SLEEPER)"
  [ "$code" -eq 0 ] && [ "$plan_code" -eq 0 ] && ! grep -q '기다린다\|LOCKED' "$T/out" "$T/out.plan" &&
    [ "$(cat "$BLOCKDIR/pid" 2>/dev/null)" = "$SLEEPER" ] && [ "$(cat "$BLOCKDIR/worktree")" = "/다른/워크트리" ]
}

# ── scripts/with-build-lock.sh ────────────────────────────────────────
wrapped() { BUILD_LOCK_DIR="$BLOCKDIR" BUILD_LOCK_HELD_BY= "$@"; }
w1_no_argument_exits_2() {
  wrapped "$W" > "$T/out" 2>&1
  local code=$?
  say "인자 없음 → 종료 코드 $code"
  [ "$code" -eq 2 ] && grep -q '사용:' "$T/out" && [ ! -e "$BLOCKDIR" ]
}
w2_passes_the_exit_code_and_holds_while_running() {
  wrapped "$W" true > "$T/out" 2>&1
  local c0=$?
  wrapped "$W" sh -c 'exit 3' > "$T/out" 2>&1
  local c3=$?
  # 감싼 명령 안에서 본 잠금의 pid 와 물려받은 BUILD_LOCK_HELD_BY 가 같다(잠금은 명령이 도는 동안 쥐어져 있다)
  wrapped "$W" sh -c 'echo "$(cat "$BUILD_LOCK_DIR/pid") $BUILD_LOCK_HELD_BY" > "$0"' "$T/held" > "$T/out" 2>&1
  local pair; pair="$(cat "$T/held" 2>/dev/null)"
  say "true → $c0 · exit 3 → $c3 · 안에서 본 「잠금 pid · 표지」 = ${pair:-없음} · 끝난 뒤 잠금 폴더 $([ -e "$BLOCKDIR" ] && echo 있음 || echo 없음)"
  [ "$c0" -eq 0 ] && [ "$c3" -eq 3 ] && [ -n "${pair%% *}" ] && [ "${pair%% *}" = "${pair#* }" ] && [ ! -e "$BLOCKDIR" ]
}
w3_live_foreign_lock_waits_then_75() {
  foreign_build_lock "$SLEEPER"
  BUILD_LOCK_WAIT_S=1 BUILD_LOCK_POLL_S=1 wrapped "$W" touch "$T/w3.ran" > "$T/out" 2>&1
  local code=$?
  say "종료 코드 $code · 명령이 돌았나 $([ -e "$T/w3.ran" ] && echo ★돌았다 || echo 안 돌았다) · 그 뒤 잠금의 pid $(cat "$BLOCKDIR/pid" 2>/dev/null)(남의 것 $SLEEPER)"
  [ "$code" -eq 75 ] && [ ! -e "$T/w3.ran" ] && grep -q '빌드 잠금이 잡혀 있다(1초 기다림)' "$T/out" &&
    [ "$(cat "$BLOCKDIR/pid" 2>/dev/null)" = "$SLEEPER" ] && [ "$(cat "$BLOCKDIR/worktree")" = "/다른/워크트리" ]
}
w4_sigterm_releases_only_after_the_command_is_gone() {
  # 감싼 명령의 표지: 이 검사만의 sleep 3.21(SLEEPER 의 sleep 300, G5 의 sleep 7 과 안 섞인다)
  env BUILD_LOCK_DIR="$BLOCKDIR" BUILD_LOCK_HELD_BY= "$W" sleep 3.21 > "$T/out" 2>&1 &
  local pid=$! tries=0 held left code
  while [ "$(pgrep -f '^sleep 3.21$' | wc -l | tr -d ' ')" -lt 1 ] && [ "$tries" -lt 50 ]; do sleep 0.1; tries=$((tries + 1)); done
  held="$(cat "$BLOCKDIR/pid" 2>/dev/null)"
  kill -TERM "$pid"
  tries=0
  while [ -e "$BLOCKDIR" ] && [ "$tries" -lt 200 ]; do sleep 0.02; tries=$((tries + 1)); done
  left="$(pgrep -f '^sleep 3.21$' | wc -l | tr -d ' ')"   # 잠금이 사라진 것을 본 바로 그때 센다
  wait "$pid"; code=$?
  say "잠금을 쥐었던 pid ${held:-없음}(with-build-lock $pid) · SIGTERM → 종료 코드 $code · 잠금이 사라졌을 때 감싼 명령 ${left}개"
  [ "$held" = "$pid" ] && [ "$code" -eq 143 ] && [ ! -e "$BLOCKDIR" ] && [ "$left" -eq 0 ]
}
w5_two_on_one_dead_lock_only_one_holds() {
  local round ca cb ran ok=0
  for round in 1 2 3 4 5; do
    reset
    rm -f "$T/ran.n"
    foreign_build_lock "$(dead_pid)"
    BUILD_LOCK_WAIT_S=0 wrapped "$W" sh -c 'echo x >> "$0"; sleep 1' "$T/ran.n" > "$T/out.a" 2>&1 &
    local a=$!
    BUILD_LOCK_WAIT_S=0 wrapped "$W" sh -c 'echo x >> "$0"; sleep 1' "$T/ran.n" > "$T/out.b" 2>&1 &
    local b=$!
    wait "$a"; ca=$?
    wait "$b"; cb=$?
    ran="$(grep -c x "$T/ran.n" 2>/dev/null || echo 0)"
    say "${round}회: 종료 코드 $(printf '%s\n%s\n' "$ca" "$cb" | sort -n | tr '\n' ' ')· 명령이 돈 수 $ran"
    [ "$(printf '%s\n%s\n' "$ca" "$cb" | sort -n | tr '\n' ' ')" = "0 75 " ] && [ "$ran" -eq 1 ] && [ ! -e "$BLOCKDIR" ] && ok=$((ok + 1))
  done
  [ "$ok" -eq 5 ]
}
w6_a_wrap_inside_a_wrap_does_not_wait() {
  local started=$SECONDS code
  # 안쪽 with-build-lock 이 끝난 뒤에도 잠금은 바깥이 쥐고 있어야 한다(안쪽은 놓지 않는다)
  BUILD_LOCK_WAIT_S=30 wrapped "$W" sh -c '"$0" true && [ "$(cat "$BUILD_LOCK_DIR/pid")" = "$BUILD_LOCK_HELD_BY" ] && echo 바깥이-그대로-쥠' "$W" > "$T/out" 2>&1
  code=$?
  say "감싼 안에서 한 번 더 → 종료 코드 $code · $((SECONDS - started))초 · 「이미 조상」 줄 $(grep -c '이미 조상' "$T/out") · 안쪽 뒤 $(grep -c '바깥이-그대로-쥠' "$T/out")"
  [ "$code" -eq 0 ] && [ $((SECONDS - started)) -lt 5 ] && grep -q '이미 조상' "$T/out" && grep -q '바깥이-그대로-쥠' "$T/out" && [ ! -e "$BLOCKDIR" ]
}
w7_outside_git_exits_2() {
  # git 저장소 밖에 둔 사본(사본의 것을 부르는 꼴): 자리를 계산하지 못하면 기다리지 않고 2
  mkdir -p "$T/notgit/scripts/lib"
  cp "$W" "$T/notgit/scripts/with-build-lock.sh"
  cp "$ROOT/scripts/lib/lock.sh" "$T/notgit/scripts/lib/lock.sh"
  env -u BUILD_LOCK_DIR -u GIT_DIR -u GIT_WORK_TREE BUILD_LOCK_WAIT_S=30 "$T/notgit/scripts/with-build-lock.sh" touch "$T/w7.ran" > "$T/out" 2>&1
  local code=$?
  say "git 밖의 사본 → 종료 코드 $code · 명령이 돌았나 $([ -e "$T/w7.ran" ] && echo ★돌았다 || echo 안 돌았다) · $(head -1 "$T/out" | cut -c1-80)"
  [ "$code" -eq 2 ] && [ ! -e "$T/w7.ran" ] && grep -q '계산하지 못했다' "$T/out"
}
w8_unmakeable_lock_place_exits_2() {
  # 잠금 자리의 부모 폴더가 없다: 빈 pid 를 「남이 쥠」으로 읽어 상한까지 기다리지 않고 바로 2
  local started=$SECONDS code
  BUILD_LOCK_DIR="$T/없는-폴더/build.lock" BUILD_LOCK_HELD_BY= BUILD_LOCK_WAIT_S=30 "$W" touch "$T/w8.ran" > "$T/out" 2>&1
  code=$?
  say "부모 없는 잠금 자리 → 종료 코드 $code · $((SECONDS - started))초 · 명령이 돌았나 $([ -e "$T/w8.ran" ] && echo ★돌았다 || echo 안 돌았다)"
  [ "$code" -eq 2 ] && [ $((SECONDS - started)) -lt 5 ] && [ ! -e "$T/w8.ran" ] && grep -q '잠금 자리를 만들 수 없다' "$T/out"
}

# ── 동시 묶음(가짜 도구로 돌린 --fast) ────────────────────────────────
# EXIT= 줄을 「단계 이름 · 코드」 꼴로
exits_of() { awk '/^▶ / { n = substr($0, 5) } /^EXIT=/ { print n " · " substr($0, 6) }' "$1"; }
ran_in_plan_order() { grep '^▶ ' "$1" | sed 's/^▶ //' | diff "$T/steps.fast" - > /dev/null; }
g1_one_failing_step_in_a_lane() {
  STUB_FAIL_ON="uv run --frozen ruff check ." stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  exits_of "$T/out" > "$T/exits"
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · 0 이 아닌 EXIT: $(grep -v ' · 0$' "$T/exits" | tr '\n' ';')"
  [ "$code" -eq 1 ] && [ "$(tail -1 "$T/out")" = "VERIFY_FAST=FAIL" ] && ran_in_plan_order "$T/out" &&
    [ "$(grep -c ' · 0$' "$T/exits")" -eq 14 ] && [ "$(grep -v ' · 0$' "$T/exits")" = "in_api_py uv run --frozen ruff check . · 1" ] &&
    grep -q -x 'uv run --frozen ruff format --check .' "$LOG" && grep -q -x 'uv run --frozen lint-imports' "$LOG" &&
    grep -q -x 'uv run --frozen python scripts/check_test_layout.py' "$LOG"
}
g2_lanes_really_run_at_once() {
  local started=$SECONDS
  STUB_SLEEP_ON="pnpm -r typecheck|uv run --frozen pyright|uv run --frozen pytest -q -n 4 --durations=15 -m not django_db and not security" STUB_SLEEP_S=2 \
    stubbed "$V" --fast > "$T/out" 2>&1
  local code=$? took=$((SECONDS - started))
  say "서로 다른 줄의 셋(L1·L5·L6)이 2초씩 잔다 → ${took}초(직렬이면 6초 이상) · $(grep '^(동시 묶음' "$T/out") · 끝 줄 $(tail -1 "$T/out")"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/out")" = "VERIFY_FAST=PASS" ] && [ "$took" -lt 5 ]
}
g3_outputs_do_not_mix() {
  STUB_SLEEP_ON="pnpm -r test|uv run --frozen lint-imports" STUB_SLEEP_S=1 stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  # 각 ▶ X 덩어리 안의 stub-out 줄이 전부 X 가 부른 도구의 것인가
  awk '/^▶ / { n = substr($0, 5); next } /^stub-out / { print n "\t" substr($0, 10) }' "$T/out" > "$T/blocks"
  local bad=0 name call want
  while IFS="$(printf '\t')" read -r name call; do
    want="$(printf '%s\n' "$name" | calls_of_plan)"
    [ "$call" = "$want" ] || { say "★ 섞임: 「$name」 덩어리에 「$call」"; bad=1; }
  done < "$T/blocks"
  say "stub-out 줄 $(wc -l < "$T/blocks" | tr -d ' ') · 덩어리 밖의 것 $(awk '/^▶ / { on = 1 } /^stub-out / && !on' "$T/out" | wc -l | tr -d ' ') · 끝 줄 $(tail -1 "$T/out")"
  [ "$code" -eq 0 ] && [ "$bad" -eq 0 ] && [ "$(wc -l < "$T/blocks" | tr -d ' ')" -eq 14 ]
}
g4_slow_first_lane_keeps_the_order() {
  STUB_SLEEP_ON="pnpm -r typecheck" STUB_SLEEP_S=2 stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  say "L1(차례상 첫째)이 2초 잔다 → 종료 코드 $code · ▶ 차례 $(ran_in_plan_order "$T/out" && echo 계획과 같음 || echo ★ 다름)"
  [ "$code" -eq 0 ] && ran_in_plan_order "$T/out" && [ "$(grep -c '^EXIT=0$' "$T/out")" -eq 15 ]
}
# 묶음이 도는 중에 신호: 줄과 그 아래(가짜 도구의 sleep 7)가 남지 않는다. 뒤에서 띄운 셸은 SIGINT 를 무시한 채
# 시작하므로 perl 로 기본 동작을 되돌려 띄운다. 남은 것은 이 검사만의 표지(sleep 7)로 센다(SLEEPER 의 sleep 300 과 안 섞인다).
g5_signal_during_the_bundle() { # <신호> <기대 종료 코드> [full]
  local before after pid tries=0 code
  before="$(pgrep -f '^sleep 7$' | wc -l | tr -d ' ')"
  # shellcheck disable=SC2046
  env PATH="$BIN:$REAL_PATH" STUB_REAL_PATH="$REAL_PATH" STUB_LOG="$LOG" VERIFY_LOCK_DIR="$LOCKDIR" \
    BUILD_LOCK_DIR="$BLOCKDIR" BUILD_LOCK_HELD_BY= STUB_LOCK_SEEN="$SEEN" \
    STUB_SLEEP_ON="pnpm -r typecheck|pnpm -r test|uv run --project services/parser --frozen pytest -q services/parser|uv run --frozen ruff check .|uv run --frozen pyright|uv run --frozen pytest -q -n 4 --durations=15 -m not django_db and not security" \
    STUB_SLEEP_S=7 perl -e '$SIG{INT} = "DEFAULT"; exec @ARGV' "$V" $([ "${3:-}" = full ] || echo --fast) > "$T/out" 2>&1 &
  pid=$!
  while [ "$(pgrep -f '^sleep 7$' | wc -l | tr -d ' ')" -lt $((before + 6)) ] && [ "$tries" -lt 100 ]; do sleep 0.1; tries=$((tries + 1)); done
  local during; during="$(pgrep -f '^sleep 7$' | wc -l | tr -d ' ')"
  kill "-$1" "$pid"
  wait "$pid"
  code=$?
  sleep 0.3
  after="$(pgrep -f '^sleep 7$' | wc -l | tr -d ' ')"
  say "SIG$1${3:+ (전량)}: 도는 sleep 7 $before → $during → 신호 뒤 $after · 종료 코드 $code · 잠금 폴더 $([ -e "$LOCKDIR" ] && echo 있음 || echo 없음) · 끝 줄 「$(tail -1 "$T/out")」"
  [ "$during" -eq $((before + 6)) ] && [ "$code" -eq "$2" ] && [ "$after" -eq "$before" ] && [ ! -e "$LOCKDIR" ] &&
    ! grep -q '^VERIFY' "$T/out"
}
g5_sigint_fast() { g5_signal_during_the_bundle INT 130; }
g5_sigterm_fast() { g5_signal_during_the_bundle TERM 143; }
g5_sigint_full() { g5_signal_during_the_bundle INT 130 full; }
g6_failing_front_step_still_runs_the_bundle() {
  STUB_FAIL_ON="pnpm install --frozen-lockfile" stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  exits_of "$T/out" > "$T/exits"
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · 0 이 아닌 EXIT: $(grep -v ' · 0$' "$T/exits" | tr '\n' ';') · 묶음 단계 호출 $(grep -c -x -F -f <(printf '%s\n' "$BUNDLE_STEPS" | calls_of_plan) "$LOG")"
  [ "$code" -eq 1 ] && [ "$(tail -1 "$T/out")" = "VERIFY_FAST=FAIL" ] && ran_in_plan_order "$T/out" &&
    [ "$(grep -v ' · 0$' "$T/exits")" = "pnpm install --frozen-lockfile · 1" ] && [ "$(grep -c ' · 0$' "$T/exits")" -eq 14 ] &&
    [ "$(grep -c -x -F -f <(printf '%s\n' "$BUNDLE_STEPS" | calls_of_plan) "$LOG")" -eq 12 ]
}
g7_a_lane_that_dies_fails_closed() {
  STUB_DIE_ON="uv run --frozen ruff check ." stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  exits_of "$T/out" > "$T/exits"
  say "종료 코드 $code · 끝 줄 $(tail -1 "$T/out") · EXIT= $(grep -c '^EXIT=' "$T/out")줄 · 0 이 아닌 EXIT: $(grep -v ' · 0$' "$T/exits" | tr '\n' ';')"
  [ "$code" -eq 1 ] && [ "$(tail -1 "$T/out")" = "VERIFY_FAST=FAIL" ] && [ "$(grep -c '^EXIT=' "$T/out")" -eq 15 ] &&
    grep -q -x 'in_api_py uv run --frozen ruff check . · 125' "$T/exits" && grep -q '종료 코드를 못 받았다' "$T/out" &&
    ran_in_plan_order "$T/out"
}
g8_a_dead_lane_leaves_no_process() {
  local before after
  before="$(pgrep -f '^sleep 7$' | wc -l | tr -d ' ')"
  STUB_DIE_ON="uv run --frozen ruff check ." stubbed "$V" --fast > "$T/out" 2>&1
  local code=$?
  after="$(pgrep -f '^sleep 7$' | wc -l | tr -d ' ')"
  say "종료 코드 $code · 남은 sleep 7 $before → $after · 작업 알림(Killed) 줄 $(grep -c 'Killed' "$T/out")"
  [ "$code" -eq 1 ] && [ "$after" -eq "$before" ] && ! grep -q 'Killed' "$T/out" && [ "$(tail -1 "$T/out")" = "VERIFY_FAST=FAIL" ]
}

# ── pre-commit ────────────────────────────────────────────────────────
# 임시 색인에 HEAD 를 읽어 들이고 파일 하나를 더 올린 뒤 훅을 부른다. 진짜 색인은 건드리지 않는다.
hook_with() { # <경로> <내용> [stub: 가짜 도구를 쓴다 | gitdir: 워크트리 커밋처럼 GIT_DIR 을 내보낸다]
  local path="$1" index="$T/index.$RANDOM"
  [ -e "$path" ] && { say "★ 심을 자리에 이미 파일이 있다: $path"; return 99; }
  probes+=("$ROOT/$path")
  printf '%s' "$2" > "$path"
  GIT_INDEX_FILE="$index" git read-tree HEAD
  GIT_INDEX_FILE="$index" git update-index --add "$path"
  local code
  if [ "${3:-}" = stub ]; then
    PATH="$BIN:$REAL_PATH" STUB_REAL_PATH="$REAL_PATH" STUB_LOG="$LOG" GIT_INDEX_FILE="$index" "$HOOK" > "$T/out" 2>&1
  elif [ "${3:-}" = gitdir ]; then
    GIT_DIR="$(git rev-parse --absolute-git-dir)" GIT_INDEX_FILE="$index" "$HOOK" > "$T/out" 2>&1
  else
    GIT_INDEX_FILE="$index" "$HOOK" > "$T/out" 2>&1
  fi
  code=$?
  rm -f "$path" "$index"
  sed 's/^/    /' "$T/out" | grep 'pre-commit:' | cut -c1-150
  return "$code"
}
hook_mode_is_executable() {
  local index="$T/index.mode" mode
  GIT_INDEX_FILE="$index" git read-tree HEAD
  GIT_INDEX_FILE="$index" git update-index --add scripts/git-hooks/pre-commit
  mode="$(GIT_INDEX_FILE="$index" git ls-files -s scripts/git-hooks/pre-commit | cut -c1-6)"
  say "커밋될 모드 $mode"
  [ -x "$HOOK" ] && [ "$mode" = 100755 ]
}
hook_a_no_python_runs_nothing() {
  hook_with "apps/web/zz-check-gates-probe.txt" "probe" stub
  local code=$?
  say "(a) 종료 코드 $code · 가짜 uv·docker·pnpm·node 호출 $(grep -c -v '^git ' "$LOG")"
  [ "$code" -eq 0 ] && [ "$(grep -c -v '^git ' "$LOG")" -eq 0 ] && [ ! -s "$T/out" ]
}
hook_clean_python_passes() {
  hook_with "apps/api-py/esgapi/user/zz_check_gates_probe.py" '"""check-gates 가 심은 파일."""

PROBE = 1
'
  local code=$?
  say "(대조) 흠 없는 파이썬 파일 → 종료 코드 $code"
  [ "$code" -eq 0 ] && grep -q 'ruff check (1 파일) … 통과' "$T/out" && grep -q 'lint-imports … 통과' "$T/out" && grep -q '순수 층 esgapi/user … 통과' "$T/out"
}
hook_b_lint_violation_blocks() {
  hook_with "apps/api-py/esgapi/user/zz_check_gates_probe.py" '"""check-gates 가 심은 파일."""

import os

PROBE = 1
'
  local code=$?
  say "(b) 안 쓰는 import → 종료 코드 $code"
  [ "$code" -eq 1 ] && grep -q 'ruff check (1 파일) … ★ 실패' "$T/out"
}
hook_c_contract_violation_blocks() {
  hook_with "apps/api-py/esgapi/reconcile/calc/zz_check_gates_probe.py" '"""check-gates 가 심은 파일."""

import django  # noqa: F401
'
  local code=$?
  say "(c) calc 가 django 를 import → 종료 코드 $code"
  [ "$code" -eq 1 ] && grep -q 'ruff check (1 파일) … 통과' "$T/out" && grep -q 'lint-imports … ★ 실패' "$T/out"
}
hook_d_failing_pure_test_blocks() {
  hook_with "apps/api-py/esgapi/user/tests/test_zz_check_gates_probe.py" '"""check-gates 가 심은 파일."""


def test_probe() -> None:
    assert sum([1]) == 2
'
  local code=$?
  say "(d) 깨지는 순수 테스트 → 종료 코드 $code"
  [ "$code" -eq 1 ] && grep -q 'ruff check (1 파일) … 통과' "$T/out" && grep -q '순수 층 esgapi/user … ★ 실패' "$T/out"
}
hook_parser_lint_violation_blocks() {
  hook_with "services/parser/scripts/zz_check_gates_probe.py" 'import os
'
  local code=$?
  say "(파서) 안 쓰는 import → 종료 코드 $code"
  [ "$code" -eq 1 ] && grep -q 'parser ruff check (1 파일) … ★ 실패' "$T/out" && ! grep -q 'api-py' "$T/out"
}
# 흠 없는 테스트 하나를 소스가 있는 접두사(scope3 → inventory/calc/scope3)로 평평하게 둔다 → 자리 검사가 막는다
H1_PATH="apps/api-py/esgapi/inventory/tests/test_scope3_zz_check_gates_probe.py"
h1_flat_test_is_blocked() { # [gitdir]
  hook_with "$H1_PATH" '"""check-gates 가 심은 파일."""


def test_probe() -> None:
    assert sum([1]) == 1
' "${1:-}"
  local code=$?
  say "(H1${1:+ GIT_DIR 판}) 평평한 새 테스트 → 종료 코드 $code"
  [ "$code" -eq 1 ] && grep -q 'api-py 테스트 자리 … ★ 실패' "$T/out" && grep -q "${H1_PATH#apps/api-py/}" "$T/out" &&
    grep -q 'ruff check (1 파일) … 통과' "$T/out" && grep -q '순수 층 esgapi/inventory … 통과' "$T/out"
}
h1_plain() { h1_flat_test_is_blocked; }
h1_gitdir() { h1_flat_test_is_blocked gitdir; }
h3_all_pure_uses_four_workers() {
  hook_with "apps/api-py/esgapi/core/zz_check_gates_probe.py" '"""check-gates 가 심은 파일."""

PROBE = 1
' stub
  local code=$?
  say "(H3) core/ 의 파일 → 종료 코드 $code · 가짜 uv 의 pytest 호출: $(grep '^uv run --frozen pytest' "$LOG" | tr '\n' ';')"
  [ "$code" -eq 0 ] && [ "$(grep -c '^uv run --frozen pytest' "$LOG")" -eq 1 ] &&
    grep -q -x 'uv run --frozen pytest -q -m not django_db and not security -n 4' "$LOG" && ! grep -q 'check_test_layout' "$LOG"
}
# ── 전량의 실행 조건 줄 ───────────────────────────────────────────────
# (전체 N초) 바로 다음 줄이 조건 줄이고 끝 줄은 그대로 VERIFY=PASS. 자기 프로젝트는 빼고 esg-app* 만 센다.
# --fast 에는 조건 줄이 없다.
c1_full_prints_the_run_conditions() {
  COMPOSE_PROJECT_NAME=esg-app-self STUB_COMPOSE_LS="esg-app-self esg-app-other1 nope esg-app-other2" stubbed "$V" > "$T/out" 2>&1
  local code=$? after
  after="$(awk 'prev ~ /^\(전체 [0-9]+초\)$/ { print; exit } { prev = $0 }' "$T/out")"
  stubbed "$V" --fast > "$T/out.fast" 2>&1
  say "종료 코드 $code · (전체) 다음 줄 「${after}」 · 끝 줄 $(tail -1 "$T/out") · --fast 의 조건 줄 $(grep -c '^(조건:' "$T/out.fast")"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/out")" = "VERIFY=PASS" ] &&
    printf '%s\n' "$after" | grep -q -E '^\(조건: 시작 1분 부하 [0-9.]+ · free ([0-9]+%|모름) · 다른 esg-app 벌 2\(esg-app-other1 esg-app-other2\)\)$' &&
    [ "$(tail -2 "$T/out" | head -1)" = "$after" ] && ! grep -q '^(조건:' "$T/out.fast"
}
# ── free_percent(scripts/lib/lock.sh) ─────────────────────────────────
# 필요한 도구만 심링크한 bin 을 PATH 로 쓴다(macOS 의 memory_pressure 는 /usr/bin 이라 PATH 를 통째로 막으면 sed 도 막힌다).
# uptime 은 가짜(1분 부하 1.50 — 문이 기다리지 않게). meminfo 는 가짜 파일(FREE_MEMINFO).
f1_free_without_memory_pressure() {
  local fb="$T/fbin" mi="$T/meminfo" t out1 out2 out3 out4
  mkdir -p "$fb"
  for t in sed awk tr wc cat; do ln -sf "$(PATH="$REAL_PATH" command -v "$t")" "$fb/$t"; done
  printf '#!/bin/sh\necho "12:00  up 1 day, 2 users, load averages: 1.50 1.40 1.30"\n' > "$fb/uptime"
  printf 'MemTotal:        1000 kB\nMemFree:          100 kB\nMemAvailable:     370 kB\n' > "$mi"
  chmod +x "$fb/uptime"
  fp() { env -i PATH="$1" FREE_MEMINFO="$2" VERIFY_LOCK_DIR="$LOCKDIR" BUILD_LOCK_DIR="$BLOCKDIR" /bin/bash -c '. "$0"; '"$3" "$ROOT/scripts/lib/lock.sh" 2>&1; }
  out1="$(fp "$fb" "$mi" 'free_percent; echo "code=$?"' | tr '\n' ' ')"
  out2="$(fp "$fb" "$T/no-meminfo" 'free_percent; echo "code=$?"' | tr '\n' ' ')"
  out3="$(fp "$fb" "$T/no-meminfo" 'host_door; echo "code=$?"' | tr '\n' ' ')"
  # 대조: memory_pressure 가 있으면 meminfo 를 보지 않고 그 값 그대로
  mkdir -p "$T/fbin-mp"
  for t in sed awk tr wc cat uptime; do ln -sf "$fb/$t" "$T/fbin-mp/$t"; done
  printf '#!/bin/sh\necho "System-wide memory free percentage: 50%%"\n' > "$T/fbin-mp/memory_pressure"
  chmod +x "$T/fbin-mp/memory_pressure"
  out4="$(fp "$T/fbin-mp" "$mi" 'free_percent; echo "code=$?"' | tr '\n' ' ')"
  say "meminfo 370/1000 → 「${out1}」 · 둘 다 없음 → 「${out2}」 · host_door → 「${out3}」 · 가짜 memory_pressure 50% → 「${out4}」"
  [ "$out1" = "37 code=0 " ] && [ "$out2" = "code=1 " ] && [ "$out4" = "50 code=0 " ] &&
    case "$out3" in *"문 열림"*"free 모름"*"code=0 ") true ;; *) false ;; esac
}
tree_is_as_before() {
  local now; now="$(git status --porcelain)"
  say "git status --porcelain: 처음 $(printf '%s' "$status_before" | grep -c .)줄, 지금 $(printf '%s' "$now" | grep -c .)줄"
  [ "$now" = "$status_before" ]
}

check "--fast --plan 에 docker 0줄, 컨테이너 없는 단계 열다섯이 전부 그 차례로 있다" fast_plan_has_no_docker
check "--fast 의 계획 ⊂ 전량의 계획, 순서 같음" fast_plan_is_inside_full_plan
check "전량 − 빠른 = 컨테이너 단계 일곱" full_minus_fast_is_the_seven
check "--plan 은 아무것도 부르지 않고 잠금을 잡지 않는다" plan_takes_no_lock_and_calls_nothing
check "compose.yaml: 프로필 ts·서비스 api·worker·migrate·redis·server.Dockerfile 없음" compose_has_no_ts
check "모르는 인자 → 2" unknown_argument_exits_2
check "가짜 도구로 돌린 전량: 계획의 단계 스물둘이 불렸다(앞몫·컨테이너는 그 순서로, 묶음 열둘은 같은 집합), 끝난 뒤 잠금 없음" full_run_calls_every_planned_step_in_order
check "가짜 도구로 돌린 --fast: docker 호출 0, VERIFY_FAST=PASS" fast_run_calls_no_docker
check "단계가 실패한 전량: VERIFY=FAIL, 끝난 뒤 잠금 없음" failing_step_fails_and_releases_the_lock
check "SIGINT 뒤 자기 잠금 없음" sigint_releases_the_lock
check "SIGTERM 뒤 자기 잠금 없음" sigterm_releases_the_lock
check "살아 있는 pid 의 잠금 → 기다리다 VERIFY=LOCKED·75, 남의 잠금은 그대로" live_lock_makes_full_wait_then_locked
check "잠금이 잡혀 있어도 --fast·--plan 은 기다리지 않고, 남의 잠금은 그대로" fast_and_plan_ignore_a_held_lock
check "죽은 pid 의 잠금 → 치우고 가져감" dead_lock_is_taken_over
check "죽은 잠금 하나에 둘이 덤비면 쥐는 것은 하나(다섯 번)" two_runs_on_one_dead_lock_only_one_holds
check "Node 20 → 첫 단계에서 실패" node_20_fails_at_the_first_step
check "B1 전량의 build 는 빌드 잠금 안에서(쥔 pid = 그 verify.sh), 앞의 down 은 밖에서, git 공통 폴더 계산 0" b1_build_runs_inside_the_build_lock
check "B2 빌드 잠금은 up 뒤·업무 층 앞에서 놓인다" b2_released_after_up_before_the_business_layer
check "B3 PASS 판과 build 가 실패한 판 뒤 빌드 잠금 없음" b3_pass_and_fail_leave_no_build_lock
check "B3 build 중 SIGINT → 130, 빌드 잠금 없음" b3_sigint_releases_the_build_lock
check "B3 build 중 SIGTERM → 143, 빌드 잠금 없음" b3_sigterm_releases_the_build_lock
check "B4 산 남의 빌드 잠금 → 기다리다 VERIFY=LOCKED·75, build 0, verify.lock 없음, 남의 잠금 그대로" b4_live_build_lock_makes_full_wait_then_locked
check "B5 죽은 빌드 잠금 → 치우고 가져감" b5_dead_build_lock_is_taken_over
check "B6 빌드 잠금이 잡혀 있어도 --fast·--plan 은 기다리지 않고, 남의 잠금은 그대로" b6_fast_and_plan_ignore_a_held_build_lock
check "W1 with-build-lock 인자 없음 → 2" w1_no_argument_exits_2
check "W2 with-build-lock 은 명령의 종료 코드를 그대로(0·3), 도는 동안 잠금을 쥔다" w2_passes_the_exit_code_and_holds_while_running
check "W3 with-build-lock 산 남의 잠금 → 기다리다 75, 명령 0, 남의 잠금 그대로" w3_live_foreign_lock_waits_then_75
check "W4 with-build-lock SIGTERM → 143, 잠금이 사라질 때 감싼 명령 0" w4_sigterm_releases_only_after_the_command_is_gone
check "W5 with-build-lock 죽은 잠금 하나에 둘 → 쥐는 것 하나(다섯 번)" w5_two_on_one_dead_lock_only_one_holds
check "W6 with-build-lock 을 감싼 안에서 한 번 더 → 기다림 0, 안쪽은 놓지 않음" w6_a_wrap_inside_a_wrap_does_not_wait
check "W7 with-build-lock 이 git 밖에 있으면 → 2, 명령 0" w7_outside_git_exits_2
check "W8 with-build-lock 잠금 자리를 만들 수 없으면(부모 없음) → 기다리지 않고 2" w8_unmakeable_lock_place_exits_2
check "G1 묶음 안 단계 하나 실패 → 그 단계만 EXIT=1, 같은 줄의 뒤 단계도 돈다, ▶ 차례 = 계획" g1_one_failing_step_in_a_lane
check "G2 서로 다른 줄은 정말 동시에 돈다" g2_lanes_really_run_at_once
check "G3 단계의 출력이 섞이지 않는다" g3_outputs_do_not_mix
check "G4 차례상 첫 줄이 느려도 출력 차례는 계획 그대로" g4_slow_first_lane_keeps_the_order
check "G5 묶음 중 SIGINT(--fast) → 130, 줄의 프로세스가 남지 않는다" g5_sigint_fast
check "G5 묶음 중 SIGTERM(--fast) → 143, 줄의 프로세스가 남지 않는다" g5_sigterm_fast
check "G5 묶음 중 SIGINT(전량) → 130, 남는 프로세스·잠금 없음" g5_sigint_full
check "G6 앞몫(pnpm install) 실패 → FAIL, 묶음은 그대로 돌고 찍힌다" g6_failing_front_step_still_runs_the_bundle
check "G7 줄 하나가 단계 코드를 못 남기고 죽는다 → 그 단계 EXIT=125, FAIL, EXIT= 15줄" g7_a_lane_that_dies_fails_closed
check "G8 밖에서 죽은 줄이 남긴 단계 프로세스를 거둔다, 작업 알림 줄 없음" g8_a_dead_lane_leaves_no_process
check "pre-commit 의 모드 100755" hook_mode_is_executable
check "pre-commit (a) 파이썬 없는 스테이징 → 0, 도구 호출 0" hook_a_no_python_runs_nothing
check "pre-commit (대조) 흠 없는 파이썬 파일 → 0" hook_clean_python_passes
check "pre-commit (b) 린트 위반 → 1" hook_b_lint_violation_blocks
check "pre-commit (c) 계약 위반 import → 1" hook_c_contract_violation_blocks
check "pre-commit (d) 순수 테스트를 깨는 변경 → 1" hook_d_failing_pure_test_blocks
check "pre-commit (파서) 린트 위반 → 1" hook_parser_lint_violation_blocks
check "pre-commit H1 소스를 접두사로 둔 평평한 새 테스트 → 테스트 자리가 막는다(1)" h1_plain
check "pre-commit H1 같은 것을 GIT_DIR 을 내보낸 채(워크트리 커밋의 꼴) → 1" h1_gitdir
check "pre-commit H3 core/ 를 건드리면 순수 층 전부를 -n 4 로, 테스트 밖이면 자리 검사 0" h3_all_pure_uses_four_workers
check "C1 전량은 (전체 N초) 다음 줄에 실행 조건(1분 부하·free·자기 밖 esg-app* 벌), 끝 줄 그대로, --fast 에는 없음" c1_full_prints_the_run_conditions
check "F1 free_percent: memory_pressure 없음 → /proc/meminfo 꼴(37%), 둘 다 없음 → 「free 모름」(문은 그 조건만 건너뜀), 있으면 그 값" f1_free_without_memory_pressure
check "끝난 뒤 작업 트리가 처음과 같다" tree_is_as_before

echo
if [ "$passed" -eq "$total" ]; then echo "GATES=PASS $passed/$total"; else echo "GATES=FAIL $passed/$total"; fi
[ "$passed" -eq "$total" ]
