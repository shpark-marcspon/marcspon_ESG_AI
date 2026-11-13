#!/usr/bin/env bash
# 게이트는 두 단이다.
#   scripts/verify.sh            전량: 깨끗한 상태에서 처음부터 끝까지(컨테이너를 짓고 띄우고 내린다). 끝 줄 VERIFY=PASS|FAIL
#   scripts/verify.sh --fast     빠른 게이트: 컨테이너 없이 도는 단계만(docker 를 부르지 않는다). 끝 줄 VERIFY_FAST=PASS|FAIL
#   scripts/verify.sh --plan     돌리지 않고 전량의 단계 이름만 찍는다(--fast --plan 은 빠른 게이트의 것)
# 단계마다 걸린 시간(초, 정수)과 "EXIT=<종료 코드>" 줄을 낸다. 전부 EXIT=0 이어야 통과다. 모르는 인자는 사용법을 찍고 2 로 끝난다.
#
# ── 컨테이너 없는 단계는 줄(lane) 여섯으로 나눠 동시에 돈다(동시 묶음) ──
#   앞몫(직렬): Node 판 점검 → (전량만) docker compose down → pnpm install → api-py 의 uv sync
#   묶음: L1 pnpm -r typecheck · L2 pnpm -r test · L3 파서 넷(같은 .venv 라 한 줄 안에서 직렬)
#         · L4 api-py 의 ruff check → ruff format → lint-imports → 테스트 자리 · L5 pyright · L6 순수 층(-n 4)
#   줄 안에서 앞 단계가 실패해도 뒤 단계는 돈다. 출력은 단계마다 파일(실행마다 mktemp -d)에 받아 두고, 묶음이
#   다 끝난 뒤 단계 이름의 차례(--plan 의 차례)로 한 덩어리씩 찍는다. 단계의 (N초) 는 그 단계 혼자의 벽시계라
#   더하면 전체보다 크다. 묶음 끝에 (동시 묶음 N초) 한 줄.
#   실패는 닫힌 쪽으로: 단계의 종료 코드를 못 받으면(줄이 중간에 죽음) 그 단계는 EXIT=125, 줄의 wait 가 0 이
#   아니어도 실패다. Ctrl-C·SIGTERM 이면 줄마다 그 아래 프로세스 나무 전체를 끝내고(TERM, 5초 뒤 KILL) 130·143.
#   (& 로 띄운 줄은 SIGINT 를 무시한 채 시작한다 — 터미널의 Ctrl-C 는 줄 안에 닿지 않아 이 정리가 끝낸다.)
#   컨테이너 단계 일곱과 보안 층은 직렬 그대로다(같은 서버·DB 를 쓴다). 줄 수와 -n 4 는 글자로 박는다.
#   compose.yaml 의 서비스는 Python 한 갈래(api-py·worker-py·migrate-py·parser·postgres·storage·storage-cors·queue)뿐이다.
#   macOS 의 /bin/bash 3.2 에서 돈다(wait -n·declare -A·mapfile 을 쓰지 않는다).
# 다루는 컨테이너·볼륨은 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME, 기본 esg-app)의 것뿐이다.
#
# 빠른 게이트는 완료 판정이 아니다: 업무·보안·통합 층(컨테이너)을 돌리지 않는다. 완료는 전량의 VERIFY=PASS 다.
#
# ── 전량은 한 번에 하나만 돈다(잠금) ──
# 이 저장소의 워크트리들이 같은 기계에서 이미지를 같이 지으면 메모리가 모자라 죽는다. 그래서 전량은 잠금을 잡는다.
#   자리   <git 공통 폴더>/verify.lock   (워크트리가 전부 같은 .git 을 본다. 안에 pid·worktree·started)
#   잡혀 있으면 누가 쥐었는지 찍고 VERIFY_LOCK_POLL_S(기본 30)초마다 다시 본다. VERIFY_LOCK_WAIT_S(기본 3600)초를
#   넘기면 VERIFY=LOCKED 를 찍고 75 로 끝난다. --fast·--plan 은 잠금을 잡지도 기다리지도 않는다.
#   놓는 것은 내가 쥔 잠금뿐이다(끝날 때·실패·Ctrl-C·SIGTERM). 쥔 프로세스가 죽어 있으면 다음 실행이 치우고 가져간다.
#   VERIFY_LOCK_DIR 로 자리를 바꿀 수 있다 — scripts/check-gates.sh 의 자기 검사 전용이다(손으로 쓰지 않는다).
# 이 잠금이 못 막는 것:
#   - pid 재사용: 쥐고 죽은 프로세스의 번호를 다른 프로세스가 받으면 살아 있는 잠금으로 보인다(기다리다 LOCKED).
#   - SIGKILL: 놓지 못하고 죽는다. 다음 실행이 「죽은 잠금」으로 치운다. mkdir 과 pid 적기 사이, 또는 죽은 잠금을 치우는
#     중(verify.lock.reap)에 죽으면 사람이 그 폴더를 지워야 한다.
#   - 이 저장소의 워크트리끼리만 본다. 다른 저장소의 docker 부하는 모른다.
#   - 컨테이너 층만 따로 돌리는 것(apps/api-py/scripts/section4-*.sh, test-*.sh)은 이 잠금 밖이다
#     (운행 규칙의 문 — 2026-10-15 컨테이너 새 규칙: 띄운 esg-app* 벌은 셋까지, free ≥ 20%(lock.sh 의 free_percent),
#     1분 부하 < 24. scripts/lib/lock.sh 의 container_door 가 그 문이다. 전량은 이 문을 쓰지 않는다 — 혼자 돈다).
#
# ── build 는 기계 전체에서 하나만(빌드 잠금) ──
# 같은 기계에서 이미지를 동시에 지으면 메모리가 모자라 죽는다(PY3 의 OOM 은 동시 build 였다).
#   자리   <git 공통 폴더>/build.lock   (안에 pid·worktree·started·what). 잡고 놓는 꼴은 verify.lock 과 같다(scripts/lib/lock.sh).
#   전량은 verify.lock 을 쥔 채 build 앞에서 잡고 up 뒤에 놓는다(차례: verify → build. 거꾸로 잡는 곳은 없다).
#   up 뒤에 놓는 까닭: build 가 실패해 이미지가 없으면 up 이 스스로 짓는다 — 그것도 잠금 안에서.
#   잡혀 있으면 BUILD_LOCK_POLL_S(기본 5)초마다 다시 보고, BUILD_LOCK_WAIT_S(기본 1800)초를 넘기면 VERIFY=LOCKED·75
#   (그때 verify.lock 도 놓는다). 잡은 쪽은 BUILD_LOCK_HELD_BY=<pid> 를 내보낸다 — 그 아래에서 다시 잡으면 기다리지 않는다.
#   BUILD_LOCK_DIR 로 자리를 바꿀 수 있다 — check-gates.sh 의 자기 검사 전용이다(손으로 쓰지 않는다).
#   손으로 지을 때는 scripts/with-build-lock.sh docker compose build 로 같은 잠금을 잡는다.
# 빌드 잠금이 못 막는 것:
#   - 이 저장소(그 워크트리들) 밖의 docker — 다른 저장소의 build 는 모른다.
#   - 이 잠금을 거치지 않는 build — 맨손 docker compose up --build, 지난 밴드의 section4-*.sh(그 안의 build 는 이 잠금 밖),
#     compose 가 이미지가 없을 때 스스로 짓는 것(전량 안에서는 up 뒤에 놓아 닫는다).
#   - verify.lock 과 같은 pid 재사용·SIGKILL·치우는 중의 죽음.
#
# ★ 이 파일이나 scripts/git-hooks/pre-commit 을 고친 밴드는 자기 §4 에 scripts/check-gates.sh 를 넣는다.
#   (이 스크립트는 check-gates.sh 를 부르지 않는다: 게이트의 자기 검사는 게이트를 고칠 때만 돈다.)
#   단계를 건너뛰는 환경 변수는 만들지 않는다(게이트에 구멍이 생긴다).
set -u
cd "$(dirname "$0")/.."

usage() {
  echo "사용: scripts/verify.sh [--fast] [--plan]" >&2
  echo "  (인자 없음) 전량   --fast 컨테이너 없는 단계만   --plan 돌리지 않고 단계 이름만" >&2
}
FAST=0
PLAN=0
for arg in "$@"; do
  case "$arg" in
    --fast) FAST=1 ;;
    --plan) PLAN=1 ;;
    *) usage; exit 2 ;;
  esac
done

failed=0
bundle_mode=""   # 동시 묶음 안: list(기대하는 단계를 적기만) · run(줄 안에서 돌림). 밖이면 빈 값
bundle_dir=""
lane_no=0
lane_step=0
lane_pids=""
# --plan 이면 돌리지 않고 이름만 찍는다. 실행과 같은 길이다(단계의 목록을 따로 적어 두지 않는다).
step() {
  if [ "$PLAN" -eq 1 ]; then echo "step: $*"; return 0; fi
  case "$bundle_mode" in
    list)
      lane_step=$((lane_step + 1))
      printf '%s\t%s\n' "$lane_no.$lane_step" "$*" >> "$bundle_dir/expect"
      return 0
      ;;
    run)
      lane_step=$((lane_step + 1))
      local f="$bundle_dir/$lane_no.$lane_step" started=$SECONDS code
      "$@" > "$f.out" 2>&1 < /dev/null
      code=$?
      echo "  ($((SECONDS - started))초)" >> "$f.out"
      echo "$code" > "$f.code"
      return "$code"
      ;;
  esac
  echo
  echo "▶ $*"
  local started=$SECONDS
  "$@"
  local code=$?
  echo "  ($((SECONDS - started))초)"
  echo "EXIT=$code"
  [ "$code" -eq 0 ] || failed=1
  return "$code"
}
# 컨테이너가 필요한 단계. --fast 에서는 돌지도 계획에 찍히지도 않는다.
container_step() {
  [ "$FAST" -eq 1 ] && return 0
  step "$@"
}
# step 밖에서 도는 것. 계획에는 주석 줄로 찍는다.
note() { if [ "$PLAN" -eq 1 ]; then echo "# $*"; fi; }

# ── 동시 묶음 ─────────────────────────────────────────────────────────
# 줄의 프로세스 나무(줄 자신 + 자손). pgrep -P 를 따라 내려간다.
tree_of() {
  local p c
  for p in "$@"; do
    echo "$p"
    for c in $(pgrep -P "$p" 2>/dev/null); do tree_of "$c"; done
  done
}
alive_of() {
  local p
  for p in "$@"; do
    case "$(ps -o stat= -p "$p" 2>/dev/null)" in "" | Z*) ;; *) echo "$p" ;; esac
  done
}
# 도는 줄을 나무째 끝낸다: 먼저 멈춰 세워(STOP) 나무가 더 자라지 않게 한 뒤 TERM, 5초 안에 안 끝나면 KILL.
# kill 0 은 쓰지 않는다(부른 스크립트까지 같은 프로세스 묶음이다).
stop_lanes() {
  [ -n "$lane_pids" ] || return 0
  local all="" prev="" i left
  for i in 1 2 3 4 5; do
    # shellcheck disable=SC2086
    all="$(tree_of $lane_pids | sort -u | tr '\n' ' ')"
    [ "$all" = "$prev" ] && break
    # shellcheck disable=SC2086
    kill -STOP $all 2>/dev/null
    prev="$all"
  done
  # shellcheck disable=SC2086
  kill -TERM $all 2>/dev/null
  # shellcheck disable=SC2086
  kill -CONT $all 2>/dev/null
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50; do
    # shellcheck disable=SC2086
    left="$(alive_of $all)"
    [ -z "$left" ] && break
    sleep 0.1
  done
  # shellcheck disable=SC2086
  [ -n "$left" ] && kill -KILL $left 2>/dev/null
  # shellcheck disable=SC2086
  wait $lane_pids 2>/dev/null
  lane_pids=""
}
# 밖에서 죽은 줄(wait ≠ 0)이 남긴 단계 프로세스를 거둔다. 줄이 죽으면 그 아래는 부모를 잃어 pgrep -P 로 안 보이지만,
# 단계의 출력 파일(묶음 폴더 안)을 아직 쥐고 있다 — 그 파일을 연 프로세스를 lsof 로 찾아 나무째 TERM, 5초 뒤 KILL.
reap_orphans() {
  local all i left
  # shellcheck disable=SC2046
  all="$(tree_of $(lsof -t +D "$bundle_dir" 2>/dev/null | grep -v -x "$$") | sort -u | tr '\n' ' ')"
  [ -n "${all// /}" ] || return 0
  # shellcheck disable=SC2086
  kill -TERM $all 2>/dev/null
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31 32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47 48 49 50; do
    # shellcheck disable=SC2086
    left="$(alive_of $all)"
    [ -z "$left" ] && break
    sleep 0.1
  done
  # shellcheck disable=SC2086
  [ -n "$left" ] && kill -KILL $left 2>/dev/null
  return 0
}
cleanup_bundle() {
  stop_lanes
  if [ -n "$bundle_dir" ]; then rm -rf "$bundle_dir"; bundle_dir=""; fi
}
# 줄들을 동시에 돌리고, 다 끝나면 기대한 단계의 차례로 출력·(N초)·EXIT= 를 찍는다. 인자는 줄의 함수 이름(차례대로).
run_bundle() {
  note "동시 묶음 시작: L1~L$# (서로 다른 줄은 동시에, 줄 안은 차례대로. 출력은 묶음이 끝난 뒤 이 차례로)"
  local lane i code tab id name started=$SECONDS
  if [ "$PLAN" -eq 1 ]; then
    for lane in "$@"; do "$lane"; done
    note "동시 묶음 끝"
    return 0
  fi
  bundle_dir="$(mktemp -d)"
  : > "$bundle_dir/expect"
  # 기대하는 단계: 줄을 「적기만」으로 한 번 지난다(실행과 같은 길)
  i=0
  bundle_mode=list
  for lane in "$@"; do
    i=$((i + 1)); lane_no=$i; lane_step=0
    "$lane"
  done
  bundle_mode=run
  i=0
  for lane in "$@"; do
    i=$((i + 1))
    ( lane_no=$i; lane_step=0; "$lane"; exit 0 ) > "$bundle_dir/lane.$i.log" 2>&1 < /dev/null &
    lane_pids="$lane_pids $!"
  done
  bundle_mode=""
  i=0
  local dead=0
  for lane in $lane_pids; do
    i=$((i + 1))
    # 2>/dev/null: 줄이 신호로 죽었을 때 bash 가 찍는 작업 알림(「… Killed: 9 ( lane_no=… )」)을 감춘다. 코드는 아래 파일로 남는다
    wait "$lane" 2>/dev/null
    code=$?
    echo "$code" > "$bundle_dir/lane.$i.wait"
    [ "$code" -eq 0 ] || dead=1
  done
  lane_pids=""
  [ "$dead" -eq 0 ] || reap_orphans
  tab="$(printf '\t')"
  while IFS="$tab" read -r id name; do
    echo
    echo "▶ $name"
    [ -f "$bundle_dir/$id.out" ] && cat "$bundle_dir/$id.out"
    code="$(cat "$bundle_dir/$id.code" 2>/dev/null)"
    case "$code" in
      "" | *[!0-9]*) echo "  (종료 코드를 못 받았다: 줄이 끝까지 돌지 않았다)"; code=125 ;;
    esac
    echo "EXIT=$code"
    [ "$code" -eq 0 ] || failed=1
  done < "$bundle_dir/expect"
  i=0
  for lane in "$@"; do
    i=$((i + 1))
    code="$(cat "$bundle_dir/lane.$i.wait" 2>/dev/null)"
    if [ "$code" != 0 ]; then
      failed=1
      echo
      echo "  (줄 L$i($lane) 이 끝까지 돌지 않았다: wait ${code:-?}. 그 줄의 바깥 출력:)"
      sed 's/^/    /' "$bundle_dir/lane.$i.log"
    fi
  done
  echo
  echo "(동시 묶음 $((SECONDS - started))초)"
  rm -rf "$bundle_dir"
  bundle_dir=""
}

# ── 잠금 (전량만) ─────────────────────────────────────────────────────
# 잡기·놓기·죽은 잠금 치우기는 scripts/lib/lock.sh 의 것이다(build.lock·with-build-lock.sh·weekly.sh 와 같은 한 벌).
. scripts/lib/lock.sh
LOCK="${VERIFY_LOCK_DIR:-$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock}"
release_lock() {
  # 내가 쥔 잠금만 놓는다. LOCKED 로 끝난 실행과 --fast·--plan 은 남의 잠금을 건드리지 않는다.
  lock_release "$LOCK"
}
acquire_lock() {
  lock_acquire "$LOCK" "${VERIFY_LOCK_WAIT_S:-3600}" "${VERIFY_LOCK_POLL_S:-30}" "전량 verify.sh 가 이미 돌고 있다" && return 0
  echo "VERIFY=LOCKED"
  exit 75
}
# 빌드 잠금: build 앞에서 잡고 up 뒤에 놓는다(이미지가 없으면 up 이 스스로 짓는다 — build 가 실패한 실행도 잠금 안에서).
# 자리는 잡기 직전에만 계산한다(BUILD_LOCK_DIR 가 있으면 git 을 부르지 않는다 — check-gates 의 자기 검사).
BUILD_LOCK=""
release_build_lock() {
  [ -n "$BUILD_LOCK" ] && lock_release "$BUILD_LOCK"
  return 0
}
acquire_build_lock() {
  local common
  if [ -n "${BUILD_LOCK_DIR:-}" ]; then
    BUILD_LOCK="$BUILD_LOCK_DIR"
  else
    common="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
    if [ -z "$common" ]; then
      echo "빌드 잠금 자리를 계산하지 못했다(git 공통 폴더를 모른다): $(pwd)"
      echo "VERIFY=FAIL"
      exit 1
    fi
    BUILD_LOCK="$common/build.lock"
  fi
  lock_acquire "$BUILD_LOCK" "${BUILD_LOCK_WAIT_S:-1800}" "${BUILD_LOCK_POLL_S:-5}" "빌드 잠금이 잡혀 있다" \
    "전량 scripts/verify.sh 의 build·up" "${BUILD_LOCK_HELD_BY:-}"
  case $? in
    0) ;;
    75) echo "VERIFY=LOCKED"; exit 75 ;;
    *) echo "VERIFY=FAIL"; exit 1 ;;   # 잠금 자리를 만들 수 없다
  esac
  [ "$LOCK_ACQUIRED" = new ] && export BUILD_LOCK_HELD_BY=$$
  return 0
}
# 끝날 때(정상·실패·Ctrl-C·SIGTERM) 도는 줄과 임시 폴더를 치우고, 전량이면 내가 쥔 잠금을 놓는다. 아무것도 찍지 않는다
# (다른 밴드의 §4 가 끝 줄을 tail -1 로 읽는다).
on_exit() {
  cleanup_bundle
  if [ "$FAST" -eq 0 ] && [ "$PLAN" -eq 0 ]; then release_build_lock; release_lock; fi
}
if [ "$PLAN" -eq 0 ]; then
  trap on_exit EXIT
  trap 'exit 130' INT
  trap 'exit 143' TERM
fi
if [ "$FAST" -eq 0 ] && [ "$PLAN" -eq 0 ]; then
  acquire_lock
fi

# Node 22 미만이면 pnpm 단계가 알기 어려운 꼴로 죽는다. 먼저 본다.
node_is_22_or_newer() {
  local version major
  version="$(node -v 2>/dev/null)"
  major="${version#v}"
  major="${major%%.*}"
  if [ -n "$major" ] && [ "$major" -ge 22 ] 2>/dev/null; then return 0; fi
  echo "Node 22 이상이 필요하다(지금: ${version:-없음}). 예: PATH=\"\$HOME/.nvm/versions/node/v22.23.1/bin:\$PATH\" scripts/verify.sh"
  return 1
}
if ! step node_is_22_or_newer; then
  echo
  if [ "$FAST" -eq 1 ]; then echo "VERIFY_FAST=FAIL"; else echo "VERIFY=FAIL"; fi
  exit 1
fi

# .env 가 없으면 로컬용 예시 값을 쓴다(가짜 값뿐이다).
if [ "$PLAN" -eq 0 ]; then [ -f .env ] || cp .env.example .env; fi

# 전량의 실행 조건: 시작할 때의 1분 부하·free·자기 밖의 esg-app* compose 프로젝트를 재 두고 (전체 N초) 다음 줄에 찍는다.
# 기다리지 않는다(전량은 혼자 돈다) — 흔들린 실행을 뒤에서 가릴 판정 재료다. Node 판 점검 뒤에 둔다(그 앞에서 docker 0).
run_cond=""
if [ "$FAST" -eq 0 ] && [ "$PLAN" -eq 0 ]; then
  cond_self="${COMPOSE_PROJECT_NAME:-$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env 2>/dev/null | tail -1)}"
  cond_names="$(docker compose ls -q 2>/dev/null | grep '^esg-app' | grep -v -x -F "${cond_self:-esg-app}" | tr '\n' ' ' | sed 's/ *$//')"
  if cond_free="$(free_percent)"; then cond_free="${cond_free:-?}%"; else cond_free="모름"; fi
  cond_load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
  run_cond="(조건: 시작 1분 부하 ${cond_load:-?} · free $cond_free · 다른 esg-app 벌 $(printf '%s' "$cond_names" | wc -w | tr -d ' ')(${cond_names:-없음}))"
fi

# 0. 깨끗한 상태로: 지난번에 남은 자기 컨테이너와 볼륨을 지운다.
#    compose.yaml 에서 빠진 서비스의 컨테이너가 남았으면 --remove-orphans 가 같이 지운다.
container_step docker compose down -v --remove-orphans

# 1~4. 컨테이너 없이 도는 것: 설치(앞몫, 직렬) → 타입 검사·단위 테스트·린트(동시 묶음)
in_api_py() { (cd apps/api-py && "$@"); }
step pnpm install --frozen-lockfile
# api-py 의 .venv 는 여기서 한 번 맞춘다. 묶음의 L4~L6 은 그 .venv 를 같이 쓴다(맞추는 uv run 둘이 겹치지 않게).
step in_api_py uv sync --frozen

lane_ts_typecheck() { step pnpm -r typecheck; }
lane_ts_test() { step pnpm -r test; }
# 파서: 넷이 같은 .venv 를 맞추므로 한 줄. 범위와 예외는 services/parser/pyproject.toml(docparse/ 도 같은 검사를 받는다).
lane_parser() {
  step uv run --project services/parser --frozen pytest -q services/parser
  step uv run --project services/parser --frozen ruff check services/parser
  step uv run --project services/parser --frozen ruff format --check services/parser
  step uv run --project services/parser --frozen pyright -p services/parser
}
# Python API(apps/api-py): 린트·포맷, 의존 방향의 계약, 테스트 자리 규칙 / 타입 검사 / 순수 층 테스트
lane_api_checks() {
  step in_api_py uv run --frozen ruff check .
  step in_api_py uv run --frozen ruff format --check .
  step in_api_py uv run --frozen lint-imports
  step in_api_py uv run --frozen python scripts/check_test_layout.py
}
lane_api_pyright() { step in_api_py uv run --frozen pyright; }
lane_api_pure() { step in_api_py uv run --frozen pytest -q -n 4 --durations=15 -m "not django_db and not security"; }
run_bundle lane_ts_typecheck lane_ts_test lane_parser lane_api_checks lane_api_pyright lane_api_pure

if [ "$FAST" -eq 0 ]; then
  # 통합 테스트가 EDK 인 척 토큰을 서명할 키 쌍을 만들고(apps/api-py/.dev-keys, git 밖) 공개키만 컨테이너에 준다.
  # 여기서 내보낸 환경 변수는 .env 의 같은 이름보다 앞선다(compose 의 규칙).
  note "EDK_JWT_PUBLIC_KEY 를 내보낸다: in_api_py uv run --frozen python scripts/dev_edk.py public-key"
  if [ "$PLAN" -eq 0 ]; then
    EDK_JWT_PUBLIC_KEY="$(in_api_py uv run --frozen python scripts/dev_edk.py public-key)" || failed=1
    export EDK_JWT_PUBLIC_KEY
  fi
fi

if [ "$FAST" -eq 0 ]; then
  # 전량에서만 워커의 긴 폴링과 다시 해 보기를 짧게 준다(운영 기본값 10·5 는 그대로 — 손 띄우기는 기본값이다).
  # Python 통합 시험은 같은 환경을 물려받아 쉼을 이 값에서 끌어낸다(tests_integration/conftest.py 의 worker_value).
  # 업무·보안 층도 이 환경을 물려받는다(그쪽 시험은 JobSettings 를 글자로 만들거나 바꿔 끼워 이 값에 기대지 않는다).
  note "짧은 값을 내보낸다: CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1"
  export CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
fi

# 5~6. 이미지를 만들고 띄운다. --wait: 전부 준비될(healthy) 때까지 기다린다.
# 빌드 잠금(기계 전체에서 build 는 하나)은 단계 밖에서 잡고 놓는다 — 단계의 글자는 그대로다.
if [ "$FAST" -eq 0 ]; then
  note "빌드 잠금을 잡는다: <git 공통 폴더>/build.lock (남이 쥐었으면 BUILD_LOCK_WAIT_S 기본 1800초까지 다시 본다)"
  [ "$PLAN" -eq 0 ] && acquire_build_lock
fi
container_step docker compose build
container_step docker compose up -d --wait
if [ "$FAST" -eq 0 ]; then
  note "빌드 잠금을 놓는다(up 뒤 — 이미지가 없으면 up 이 스스로 짓는다)"
  [ "$PLAN" -eq 0 ] && release_build_lock
fi

# 7-py. Python API: 업무 층(주인 역할, 워커 여럿), 보안 층(앱 역할로 붙어 RLS 를 잰다, 직렬), 떠 있는 api-py 에 요청을 보내는 테스트
# 보안 층은 compose storage 값을 RUNBUNDLE_S3_* 다섯으로 받아 실제 저장소 왕복(test_run_bundles 의 S16)을 skip 하지 않는다(MARC-ISSUE-407).
# 값은 compose 처럼 셸에 내보낸 것 > .env 의 마지막 줄. 하위 셸에서만 내보내고(뒤 단계로 새지 않음) 단계에는 함수 이름만 찍힌다(값을 찍지 않는다).
compose_value() { if [ -n "${!1+x}" ]; then printf '%s' "${!1}"; else sed -n "s/^$1=//p" .env 2>/dev/null | tail -1; fi; }
security_with_storage() {
  (
    port="$(compose_value STORAGE_PORT)"
    export RUNBUNDLE_S3_ENDPOINT="http://127.0.0.1:${port:-19000}"
    export RUNBUNDLE_S3_BUCKET="$(compose_value S3_BUCKET)" RUNBUNDLE_S3_REGION="$(compose_value S3_REGION)"
    export RUNBUNDLE_S3_ACCESS_KEY="$(compose_value STORAGE_ACCESS_KEY)" RUNBUNDLE_S3_SECRET_KEY="$(compose_value STORAGE_SECRET_KEY)"
    exec apps/api-py/scripts/test-security.sh "$@"
  )
}
container_step apps/api-py/scripts/test-business.sh -n 2
container_step security_with_storage
if ! container_step apps/api-py/scripts/test-integration.sh; then
  docker compose logs --no-color --tail 60 api-py migrate-py worker-py queue
fi
[ "$FAST" -eq 1 ] || note "위 단계가 실패하면: docker compose logs --no-color --tail 60 api-py migrate-py worker-py queue"

# 8. 자기 컨테이너와 볼륨을 남기지 않는다.
container_step docker compose down -v

[ "$PLAN" -eq 1 ] && exit 0
echo
label="VERIFY"
[ "$FAST" -eq 1 ] && label="VERIFY_FAST"
echo "(전체 ${SECONDS}초)"
[ -n "$run_cond" ] && echo "$run_cond"
if [ "$failed" -eq 0 ]; then echo "$label=PASS"; else echo "$label=FAIL"; fi
exit "$failed"
