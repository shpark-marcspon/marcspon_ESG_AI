#!/usr/bin/env bash
# 주 1회 정기 실행 — 감독이 손으로 돌린다(예약 작업으로 걸지 않는다. 사용자 결정 2026-10-15).
#   사용: scripts/weekly.sh [--commit <rev>(기본 main)] [--only <변이 대상 파일>]... [--integration-only | --mutmut-only]
#                           [--out <결과들의 뿌리>] [--known <알려진 생존 파일>] [--allow-fewer-targets] [--plan]
#   ⓪ import 계약의 두 검사(기본 실행에서만): apps/api-py/scripts/planted-breaks.sh(심은 파손 — 계약 열다섯 전부를 계약 id 로.
#      게이트가 부르지 않으면 낡는다. MARC-ISSUE-116)와 apps/api-py/scripts/check-wheel.sh(wheel 에 tests 가 없다). 일터 사본에서 돈다.
#   ① 기본값 판 Python 통합: 워커의 긴 폴링 10·재시도 5(운영 기본값)로 띄우고 통합 시험을 돌린다 — 전량은 짧은 값이라
#      POLL_SETTLE 쉼의 회귀는 이 실행만 잡는다.
#   ② 변이 테스트(mutmut 3.8.0 — lock 에 넣지 않고 uv run --frozen --with mutmut==3.8.0 으로 잠깐 얹는다). 대상은 아래
#      TARGET_GLOBS 한 자리(calc 전체·inventory engines·inventory tools)를 펼친 것 — default_targets·is_target·--plan 이 같이 쓴다.
#      --only 도 같은 검사를 지난다. 기본 대상이 지난 회(targets_source=default·mutmut_done=1 의 가장 최근)보다 10% 넘게
#      줄면 mutmut 을 띄우지 않고 FAIL — 일부러 줄였으면 --allow-fewer-targets. 사본에서 뜻이 없는 시험(소스·코드 객체를
#      읽거나 한 프로세스의 거듭 실행에서 깨지는 것)은 표식 not_under_mutmut 로 뺀다(apps/api-py/pyproject.toml 의 markers). 깨끗한 실행이 빨개지면 FAILED·ERROR
#      줄을 mutmut-clean-fail.txt 에 — 표식이 빠진 새 순수성 시험이면 거기 이름이 나온다.
#   ③ 지난 회와 diff 글자로 견줘(scripts/weekly_compare.py) 「기본값 판 실패」「새 생존 변이」만 summary.md 맨 위로 올린다.
#      병합 게이트가 아니다 — 새 생존은 판정 재료다(개수 래칫은 하지 않는다). 시간초과는 견주기에서 빼고 따로 센다
#      (「시간초과: n (지난 회 m)」 — 무한 반복 변이는 같은 코드에서도 회마다 killed·timeout 이 갈린다).
# 끝 줄과 종료 코드: WEEKLY=OK(0 — 돈 국면이 다 끝까지, ⓪ 의 두 검사 종료 0, 통합 PASS. 새 생존이 있어도 0) · WEEKLY=FAIL(1)
#   · WEEKLY=WAITED(75 — 문이나 빌드 잠금이 30분 안에 안 열림. 문이 열린 뒤 그 국면만 다시: --integration-only·--mutmut-only)
#   · 2 사용법. --plan 은 국면과 명령, 펼친 대상의 수를 찍고 아무것도 부르지 않는다(docker·uv·git archive 0 — 대상은
#   git ls-tree 로 센다). 대상이 줄어 ② 가 FAIL 할 자리면 --plan 도 1.
# 시간 상한(① WEEKLY_INTEG_CAP_S 기본 1200 · ② WEEKLY_MUTMUT_CAP_S 기본 21600): run_capped 가 명령을 새 프로세스 그룹으로
#   띄우고 상한을 넘기면 그룹째 TERM → 10초 → KILL(종료 142). uv 아래의 mutmut·pytest 자식·손자까지 끊긴다.
#
# 자리:
#   일은 저장소 밖 사본에서 한다: git archive <rev> → ~/.cache/esg-weekly/<YYYY-MM-DD-HHMMSS>/src (일터 — 지워도 되는 것).
#     일터의 뿌리는 WEEKLY_WORK_ROOT 로 덮는다(시험 실행이 정기 실행의 남은 일터를 지우지 않게).
#     작업 트리·색인·가지는 건드리지 않는다(끝에 git status --porcelain 이 처음과 같은지 본다). 일터는 WEEKLY=OK 면 지우고
#     아니면 남긴다(살펴볼 것). 남은 일터는 가장 최근 하나만 두고 그 앞의 것은 다음 회 시작에 지운다.
#   결과(작은 글)는 <marcspon>/weekly/<YYYY-MM-DD-HHMMSS>/ (<marcspon> = git 공통 폴더의 위의 위. git 밖). 자리가 이미 있으면 FAIL.
#     meta.txt · planted-breaks.txt · check-wheel.txt · integration.log · mutmut-results.txt · survivors.txt · summary.md
#     (실패 때 compose-logs.txt)
#   알려진 생존(감독이 손으로 고치는 판정 재료): 기본 <marcspon>/weekly/known-survivors.txt. 없으면 「알려진 생존 없음」.
#   잠금·문은 부른 저장소에서 계산하고 그 저장소의 scripts/lib/lock.sh 를 쓴다(사본의 것을 부르지 않는다).
# 환경을 닫는다: 사본 .env 의 키 전부와 COMPOSE_FILE·COMPOSE_PROFILES·COMPOSE_PROJECT_NAME 을 지우고 프로젝트 이름을
#   esg-app-weekly 로 글자로 박는다. up 앞과 down 앞에서 docker compose config 의 name 이 esg-app-weekly 인지 보고, 아니면
#   아무것도 띄우거나 내리지 않고 FAIL — 부른 셸에 남은 값이 남의 프로젝트를 내리지 않게.
# 혼자 도는 실행이 아니다(시간을 재지 않는다). 다만 ① 은 container_door(자기 밖 esg-app* 둘 이하·verify.lock 없음·
#   build.lock 없음·free ≥ 20%·1분 부하 < 24), ② 는 host_door(verify.lock 없음·free·부하)를 지나야 시작한다. build 와 up 은
#   빌드 잠금 안에서(전량과 같이 up 뒤에 놓는다). 문은 아무 잠금도 쥐지 않고 기다린다.
# macOS 의 /bin/bash 3.2 에서 돈다. AI 공급사 호출 0. 네트워크는 uv·docker 의 받기뿐.
set -u
cd "$(dirname "$0")/.."
REPO="$PWD"

usage() {
  echo "사용: scripts/weekly.sh [--commit <rev>] [--only <변이 대상 파일>]... [--integration-only | --mutmut-only] [--out <자리>] [--known <파일>] [--allow-fewer-targets] [--plan]" >&2
}
REV=main
ONLY=""
DO_INTEG=1
DO_MUT=1
OUT=""
KNOWN=""
PLAN=0
ALLOW_FEWER=0
while [ "$#" -gt 0 ]; do
  case "$1" in
    --commit) [ "$#" -ge 2 ] || { usage; exit 2; }; REV="$2"; shift 2 ;;
    --only) [ "$#" -ge 2 ] || { usage; exit 2; }; ONLY="$ONLY$2
"; shift 2 ;;
    --integration-only) DO_MUT=0; shift ;;
    --mutmut-only) DO_INTEG=0; shift ;;
    --out) [ "$#" -ge 2 ] || { usage; exit 2; }; OUT="$2"; shift 2 ;;
    --known) [ "$#" -ge 2 ] || { usage; exit 2; }; KNOWN="$2"; shift 2 ;;
    --plan) PLAN=1; shift ;;
    --allow-fewer-targets) ALLOW_FEWER=1; shift ;;
    *) usage; exit 2 ;;
  esac
done
[ "$DO_INTEG" -eq 1 ] || [ "$DO_MUT" -eq 1 ] || { echo "--integration-only 와 --mutmut-only 는 같이 쓰지 않는다" >&2; usage; exit 2; }

. scripts/lib/lock.sh

COMMON="$(git rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
[ -n "$COMMON" ] || { echo "git 공통 폴더를 계산하지 못했다: $REPO" >&2; exit 2; }
MARCSPON="$(dirname "$(dirname "$COMMON")")"
OUTROOT="${OUT:-$MARCSPON/weekly}"
KNOWN="${KNOWN:-$MARCSPON/weekly/known-survivors.txt}"
STAMP="$(date '+%Y-%m-%d-%H%M%S')"
RES="$OUTROOT/$STAMP"
WROOT="${WEEKLY_WORK_ROOT:-$HOME/.cache/esg-weekly}"
WORK="$WROOT/$STAMP"
SRC="$WORK/src"
API="$SRC/apps/api-py"
PROJECT=esg-app-weekly
BLOCK="${BUILD_LOCK_DIR:-$COMMON/build.lock}"
MUTMUT="uv run --frozen --with mutmut==3.8.0"
TEST_SELECTION='esgapi/core
esgapi/inventory
esgapi/reconcile
esgapi/reference'
# 변이 대상의 한 자리(MARC-ISSUE-153 — find·case·plan 이 셋으로 갈려 EN1 의 이동 뒤 대상이 소리 없이 줄었다).
# apps/api-py 에서 본 경로의 case 패턴(* 는 / 도 넘는다). 이 가운데 .py 이고 tests/ 밖이고 비지 않은 것.
# greenwash/engines 는 TEST_SELECTION 에 greenwash 가 없어 넣지 않는다(넣으면 TEST_SELECTION 에도).
TARGET_GLOBS='esgapi/*/calc/*
esgapi/inventory/engines/*
esgapi/inventory/tools/*'
MUT_CAP="${WEEKLY_MUTMUT_CAP_S:-21600}"   # 2026-10-17 손 실행: calc 27 파일 6068 변이가 약 9200초 — 대상 약 2배 + 여유
INTEG_CAP="${WEEKLY_INTEG_CAP_S:-1200}"
for v in "$MUT_CAP" "$INTEG_CAP"; do
  case "$v" in "" | *[!0-9]*) echo "WEEKLY_MUTMUT_CAP_S·WEEKLY_INTEG_CAP_S 는 초(자연수)다: $v" >&2; exit 2 ;; esac
done

# <apps/api-py 에서 본 경로>: 변이 대상의 꼴인가(비었는지는 따로 본다)
is_target() {
  local g
  case "$1" in */tests/* | tests/*) return 1 ;; *.py) ;; *) return 1 ;; esac
  set -f
  for g in $TARGET_GLOBS; do
    # shellcheck disable=SC2254
    case "$1" in $g) set +f; return 0 ;; esac
  done
  set +f
  return 1
}
# <rev>: 기본 대상(apps/api-py 에서 본 경로, 차례대로). 사본은 git archive <rev> 라 같은 트리다 — plan 과 실행이 같은 목록.
default_targets() {
  local f
  git ls-tree -r -l "$1" -- apps/api-py/esgapi | awk -F'\t' '{ split($1, a, " "); if (a[2] == "blob" && a[4] + 0 > 0) print $2 }' |
    sed 's#^apps/api-py/##' | while IFS= read -r f; do is_target "$f" && printf '%s\n' "$f"; done | LC_ALL=C sort
}
# <$OUTROOT> <지금 결과 자리 이름(없으면 빈 글)>: targets_source=default·mutmut_done=1 인 가장 최근 회의 「이름 수」. 없으면 빈 글
last_default_count() {
  local d m best=""
  [ -d "$1" ] || return 0
  for d in $(ls -1 "$1" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}$' | sort); do
    [ "$d" = "$2" ] && continue
    m="$1/$d/meta.txt"
    [ -f "$m" ] || continue
    grep -qx 'targets_source=default' "$m" && grep -qx 'mutmut_done=1' "$m" || continue
    best="$d $(sed -n 's/^targets_count=//p' "$m" | tail -1)"
  done
  echo "$best"
}
# <지금 수> <지금 결과 자리 이름>: TARGETS_LINE 을 채우고, 10% 넘게 줄었고 --allow-fewer-targets 가 없으면 1
TARGETS_LINE=""
check_fewer() {
  local n="$1" last prev m
  last="$(last_default_count "$OUTROOT" "$2")"
  if [ -z "$last" ]; then TARGETS_LINE="대상 수: $n (지난 회 없음)"; return 0; fi
  prev="${last%% *}"
  m="${last#* }"
  case "$m" in "" | *[!0-9]*) TARGETS_LINE="대상 수: $n (지난 회 $prev 의 targets_count 를 못 읽음)"; return 0 ;; esac
  if [ $((n * 10)) -lt $((m * 9)) ]; then
    if [ "$ALLOW_FEWER" -eq 1 ]; then
      TARGETS_LINE="대상 수: $n (지난 회 $prev 의 $m — 10% 넘게 줄었으나 --allow-fewer-targets)"
      return 0
    fi
    TARGETS_LINE="대상 수: $n (지난 회 $prev 의 $m — 10% 넘게 줄어 mutmut 을 띄우지 않음)"
    echo "  ★ 대상이 지난 회 $m → 지금 $n 으로 줄었다($prev). 일부러 줄였으면 --allow-fewer-targets"
    return 1
  fi
  TARGETS_LINE="대상 수: $n (지난 회 $prev 의 $m)"
  return 0
}

if [ "$PLAN" -eq 1 ]; then
  echo "# 계획만 — 아무것도 부르지 않는다(docker·uv·git archive 0)"
  echo "자리: 결과 $OUTROOT/<YYYY-MM-DD-HHMMSS>/ · 일터 $WROOT/<같은 이름>/ · 알려진 생존 $KNOWN · 빌드 잠금 $BLOCK"
  echo "준비: 지난 일터는 가장 최근 하나만 남기고 지운다 → git archive <$REV> | tar -x -C <일터>/src"
  if [ "$DO_INTEG" -eq 1 ] && [ "$DO_MUT" -eq 1 ]; then
    echo "⓪ import 계약 검사 (일터 사본 apps/api-py 에서 — 부른 트리에 심지 않는다. 기본 실행에서만)"
    echo "  (apps/api-py) uv sync --frozen"
    echo "  (apps/api-py) scripts/planted-breaks.sh(계약 열다섯 전부를 계약 id 로) → 끝 줄 PLANTED= 와 종료 코드 (meta planted_breaks·planted_breaks_exit, 0 아니면 FAIL)"
    echo "  (apps/api-py) scripts/check-wheel.sh → 종료 코드 (meta check_wheel_exit, 0 아니면 FAIL)"
  fi
  if [ "$DO_INTEG" -eq 1 ]; then
    echo "① 기본값 판 Python 통합 (compose 프로젝트 $PROJECT)"
    echo "  문: container_door $PROJECT (자기 밖 esg-app* ≤ 2 · verify.lock 없음 · build.lock 없음 · free ≥ 20% · 1분 부하 < 24, 60초 간격 30분)"
    echo "  (사본에서) GIT_DIR=$COMMON scripts/worktree-env.sh weekly"
    echo "  환경 닫기: 사본 .env 의 키·COMPOSE_FILE·COMPOSE_PROFILES·COMPOSE_PROJECT_NAME 지움 → COMPOSE_PROJECT_NAME=$PROJECT CELERY_WAIT_TIME_SECONDS= JOB_RETRY_DELAY_SECONDS="
    echo "  (apps/api-py) uv sync --frozen · EDK_JWT_PUBLIC_KEY=\$(uv run --frozen python scripts/dev_edk.py public-key)"
    echo "  docker compose config --format json 의 name = $PROJECT 확인"
    echo "  빌드 잠금 잡기 → docker compose build → docker compose up -d --wait → 빌드 잠금 놓기"
    echo "  상한 ${INTEG_CAP}초(그룹째 끊음): apps/api-py/scripts/test-integration.sh --durations=0"
    echo "  (실패면) docker compose logs --no-color --tail 200 api-py migrate-py worker-py queue parser"
    echo "  name 확인 → docker compose down -v --remove-orphans (실패·신호에도)"
  fi
  PLAN_CODE=0
  if [ "$DO_MUT" -eq 1 ]; then
    echo "② 변이 테스트"
    echo "  문: host_door (verify.lock 없음 · free ≥ 20% · 1분 부하 < 24, 60초 간격 30분)"
    echo "  대상 패턴: $(printf '%s' "$TARGET_GLOBS" | tr '\n' ' ')(.py · tests/ 밖 · 비지 않음)"
    if [ -n "$ONLY" ]; then
      echo "  대상(--only): $(printf '%s' "$ONLY" | tr '\n' ' ')"
      for f in $ONLY; do is_target "$f" || { echo "  ★ 변이 대상 밖이다: $f (대상: $(printf '%s' "$TARGET_GLOBS" | tr '\n' ' '))"; PLAN_CODE=1; }; done
    else
      REVHASH="$(git rev-parse --verify --quiet "$REV^{commit}")"
      [ -n "$REVHASH" ] || { echo "rev 를 모른다: $REV"; exit 1; }
      targets="$(default_targets "$REVHASH")"
      n="$(printf '%s' "$targets" | grep -c .)"
      echo "  대상(기본, $REV 의 트리를 펼침): $n 파일 — 디렉터리별"
      printf '%s\n' "$targets" | grep . | sed 's#/[^/]*$##' | LC_ALL=C sort | uniq -c | sed 's/^/   /'
      check_fewer "$n" "" || PLAN_CODE=1
      echo "  $TARGETS_LINE"
    fi
    echo "  (apps/api-py) setup.cfg 를 쓴다: 테스트 선택 $(printf '%s' "$TEST_SELECTION" | tr '\n' ' ')· -m not django_db and not security and not not_under_mutmut"
    echo "  상한 ${MUT_CAP}초(그룹째 끊음): $MUTMUT mutmut run --max-children 4"
    echo "  $MUTMUT mutmut results --all true → 살아남음·시간초과·의심의 이름"
    echo "  $MUTMUT python -I $REPO/scripts/weekly_mutmut_diffs.py <이름 목록>"
  fi
  echo "③ python3 -I $REPO/scripts/weekly_compare.py --run <결과> --history $OUTROOT … → summary.md · survivors.txt"
  echo "끝: git status --porcelain 이 처음과 같은지 · WEEKLY=OK 면 일터를 지운다"
  exit "$PLAN_CODE"
fi

# ── 실행 ──────────────────────────────────────────────────────────────
meta() { printf '%s=%s\n' "$1" "$2" >> "$RES/meta.txt"; }
load1() { uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p'; }
free_pct() { free_percent; }   # scripts/lib/lock.sh 의 것(문과 같은 셈). 「free 모름」이면 빈 값
free_txt() { local f; f="$(free_pct)"; if [ -n "$f" ]; then echo "$f%"; else echo "모름"; fi; }   # 빈 값을 「%」로 찍지 않는다
host_now() { echo "1분 부하 $(load1) · free $(free_txt) · compose ls -q: $(docker compose ls -q 2>/dev/null | tr '\n' ' ')"; }

mkdir -p "$OUTROOT" || exit 1
if ! mkdir "$RES" 2>/dev/null; then echo "결과 자리가 이미 있거나 만들 수 없다(덮어쓰지 않는다): $RES"; echo "WEEKLY=FAIL"; exit 1; fi
STATUS_BEFORE="$(git status --porcelain)"
REVHASH="$(git rev-parse --verify --quiet "$REV^{commit}")"
meta rev "$REV"
meta rev_hash "${REVHASH:-?}"
meta started "$(date '+%Y-%m-%d %H:%M:%S')"
meta caller "$REPO"
meta work "$WORK"
meta uptime_start "$(uptime)"
meta free_start "$(free_txt)"
meta compose_ls_start "$(docker compose ls -q 2>/dev/null | tr '\n' ' ')"
meta phases "import_checks=$([ "$DO_INTEG" -eq 1 ] && [ "$DO_MUT" -eq 1 ] && echo 1 || echo 0) integration=$DO_INTEG mutmut=$DO_MUT"
echo "── weekly · rev $REV (${REVHASH:-?}) · 결과 $RES · 일터 $WORK · $(host_now)"
[ -n "$REVHASH" ] || { echo "rev 를 모른다: $REV"; meta finished "$(date '+%Y-%m-%d %H:%M:%S')"; echo "WEEKLY=FAIL"; exit 1; }

# 프로세스 나무(verify.sh 의 꼴). 시간 상한을 넘겨 죽은 uv 아래의 pytest 는 부모를 잃으므로 돌던 동안의 나무를 적어 둔다.
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
    [ "$p" = "$$" ] && continue
    case "$(ps -o stat= -p "$p" 2>/dev/null)" in "" | Z*) ;; *) echo "$p" ;; esac
  done
}
CAPPED_TREE=""
reap_capped() {
  local left i
  # shellcheck disable=SC2086
  left="$(alive_of $CAPPED_TREE | tr '\n' ' ')"
  CAPPED_TREE=""
  [ -n "${left// /}" ] || return 0
  echo "  (남은 프로세스를 거둔다: $left)"
  # shellcheck disable=SC2086
  kill -TERM $left 2>/dev/null
  for i in 1 2 3 4 5 6 7 8 9 10; do
    # shellcheck disable=SC2086
    [ -z "$(alive_of $left)" ] && return 0
    sleep 0.5
  done
  # shellcheck disable=SC2086
  kill -KILL $(alive_of $left) 2>/dev/null
  return 0
}
# 그룹 <pgid> 에 좀비 아닌 것이 남았나
group_alive() {
  ps -A -o pgid= -o stat= 2>/dev/null | awk -v g="$1" '$1 == g && $2 !~ /^Z/ { found = 1 } END { exit !found }'
}
# 그룹 <pgid> 를 TERM → 10초 → KILL. 그룹 밖으로 샌 것(스스로 setsid 한 자식)은 reap_capped 가 나무로 거둔다.
CAPPED_PGID=""
kill_group() {
  local i
  [ -n "$1" ] || return 0
  group_alive "$1" || return 0
  kill -TERM -- "-$1" 2>/dev/null
  for i in 1 2 3 4 5 6 7 8 9 10 11 12 13 14 15 16 17 18 19 20; do
    group_alive "$1" || return 0
    sleep 0.5
  done
  echo "  (그룹 $1 이 TERM 10초 뒤에도 남아 KILL)"
  kill -KILL -- "-$1" 2>/dev/null
  return 0
}
# <상한 초> <로그> <자리> <명령…>: 명령을 새 프로세스 그룹으로 뒤에서 돌리고(perl setpgrp — macOS 에 setsid·timeout 이
# 없다) 끝을 기다린다. 상한을 넘기면 그룹째 끊는다(perl alarm 은 exec 한 것만 죽이고, 2초마다 뜬 나무로 거두는 것은
# 그 사이 이중 fork 로 나무를 벗어난 손자를 놓친다 — WK1 함수 단위 실측). 끝나면(상한·실패 포함) 나무에 남은 것을
# 거둔다. 종료 코드를 돌려준다(상한이면 142).
run_capped() {
  local cap="$1" log="$2" dir="$3" pid code start over=0
  shift 3
  ( cd "$dir" && exec perl -e 'setpgrp(0, 0) or die "setpgrp: $!"; exec @ARGV or die "exec: $!"' "$@" ) > "$log" 2>&1 < /dev/null &
  pid=$!
  CAPPED_PGID="$pid"   # exec 한 subshell 이 perl 이고 setpgrp(0,0) 이라 그룹 번호 = pid
  start=$SECONDS
  while kill -0 "$pid" 2>/dev/null; do
    CAPPED_TREE="$(tree_of "$pid" | tr '\n' ' ')"
    if [ $((SECONDS - start)) -ge "$cap" ]; then
      over=1
      kill_group "$pid"
      break
    fi
    sleep 2
  done
  wait "$pid"
  code=$?
  [ "$over" -eq 1 ] && code=142
  kill_group "$pid"   # 우두머리가 먼저 끝나도 그룹에 남은 것
  CAPPED_PGID=""
  reap_capped
  return "$code"
}

compose_name() {
  (cd "$SRC" && docker compose config --format json 2>/dev/null) | python3 -I -c 'import json, sys; print(json.load(sys.stdin).get("name", ""))' 2>/dev/null
}
name_is_ours() {
  local n
  n="$(compose_name)"
  [ "$n" = "$PROJECT" ] && return 0
  echo "  ★ compose 프로젝트 이름이 $PROJECT 가 아니다(${n:-못 읽음}) — 아무것도 띄우거나 내리지 않는다"
  return 1
}
UP=0
HELD_BUILD=0
compose_down() {
  [ "$UP" -eq 1 ] || return 0
  UP=0
  name_is_ours || return 1
  (cd "$SRC" && docker compose down -v --remove-orphans) > "$WORK/down.log" 2>&1
  local code=$?
  echo "  docker compose down -v --remove-orphans → $code"
  return "$code"
}
FINISHED=0
cleanup() {
  kill_group "$CAPPED_PGID"   # 신호로 끝날 때 돌던 그룹(새 그룹이라 터미널의 ^C 를 받지 않는다)
  CAPPED_PGID=""
  reap_capped
  if [ "$HELD_BUILD" -eq 1 ]; then lock_release "$BLOCK"; HELD_BUILD=0; fi
  compose_down
  if [ "$FINISHED" -eq 0 ] && [ -d "$RES" ]; then meta finished "$(date '+%Y-%m-%d %H:%M:%S') (중간에 끝남)"; fi
}
trap cleanup EXIT
trap 'echo "WEEKLY=FAIL (SIGINT)"; exit 130' INT
trap 'echo "WEEKLY=FAIL (SIGTERM)"; exit 143' TERM

# 지난 일터: 가장 최근 하나만 남긴다(이번 것을 만들기 전에). 이름이 시각 꼴인 것만 지운다.
if [ -d "$WROOT" ]; then
  for d in $(ls -1 "$WROOT" | grep -E '^[0-9]{4}-[0-9]{2}-[0-9]{2}-[0-9]{6}$' | sort | sed '$d'); do
    echo "  지난 일터를 지운다: $WROOT/$d"
    rm -rf "${WROOT:?}/$d"
  done
fi
mkdir -p "$SRC" || { echo "WEEKLY=FAIL"; exit 1; }
git archive "$REVHASH" | tar -x -C "$SRC"
codes="${PIPESTATUS[0]} ${PIPESTATUS[1]}"
[ "$codes" = "0 0" ] || { echo "git archive | tar 실패: $codes"; echo "WEEKLY=FAIL"; exit 1; }

RESULT=OK       # OK · FAIL · WAITED
note_result() { # <국면의 코드>: 75 → WAITED(FAIL 이 이미 있으면 FAIL), 0 아닌 것 → FAIL
  case "$1" in
    0) ;;
    75) [ "$RESULT" = FAIL ] || RESULT=WAITED ;;
    *) RESULT=FAIL ;;
  esac
}

# ── ⓪ import 계약의 두 검사 ──────────────────────────────────────────
# 일터 사본($API)에서 돈다 — $REPO(부른 트리, 보통 main)에서 돌리면 다른 세션이 쓰는 트리에 파손을 심었다 되돌린다.
# 사본은 git 저장소가 아니라 planted-breaks.sh 의 끝 검사(작업 트리 지문)는 늘 같다고 나온다. 여기서 보는 것은
# 끝 줄 PLANTED= 와 종료 코드다(종료 0 = 심은 파손이 다 기대대로). 둘 다 가볍고 컨테이너를 띄우지 않아 문을 지나지 않는다.
phase_import_checks() {
  local pcode wcode planted
  echo
  echo "── ⓪ import 계약 검사 (심은 파손·wheel) · $(host_now)"
  (cd "$API" && uv sync --frozen) > "$WORK/uv-sync-import.log" 2>&1 || { meta planted_breaks "uv sync 실패"; tail -5 "$WORK/uv-sync-import.log"; return 1; }
  (cd "$API" && scripts/planted-breaks.sh) > "$RES/planted-breaks.txt" 2>&1 < /dev/null
  pcode=$?
  planted="$(grep -E '^PLANTED=' "$RES/planted-breaks.txt" | tail -1)"
  meta planted_breaks "${planted:-PLANTED 줄 없음}"
  meta planted_breaks_exit "$pcode"
  echo "  apps/api-py/scripts/planted-breaks.sh → ${planted:-PLANTED 줄 없음} · 종료 $pcode"
  grep '★' "$RES/planted-breaks.txt" | head -5 | sed 's/^/    /'
  (cd "$API" && scripts/check-wheel.sh) > "$RES/check-wheel.txt" 2>&1 < /dev/null
  wcode=$?
  meta check_wheel_exit "$wcode"
  echo "  apps/api-py/scripts/check-wheel.sh → 종료 $wcode"
  [ "$wcode" -eq 0 ] || tail -3 "$RES/check-wheel.txt" | sed 's/^/    /'
  [ "$pcode" -eq 0 ] && [ "$wcode" -eq 0 ]   # 0 아니면 1(FAIL) — 75(WAITED)로 새지 않는다
}

# ── ① 기본값 판 Python 통합 ──────────────────────────────────────────
INTEG_LINE="기본값 판 통합: 안 돌림"
close_env() {
  local k
  for k in $(sed -n 's/^\([A-Za-z_][A-Za-z0-9_]*\)=.*/\1/p' "$SRC/.env") COMPOSE_FILE COMPOSE_PROFILES COMPOSE_PROJECT_NAME COMPOSE_ENV_FILES; do
    unset "$k"
  done
  export COMPOSE_PROJECT_NAME=esg-app-weekly
  # 기본값 판: 빈 셸 값은 .env 를 이기고, compose 의 ${…:-} 가 빈 값을 넘기면 설정이 기본값(10·5)을 쓴다.
  # 통합 시험(conftest.worker_value)도 빈 글자를 「없음」으로 읽는다 — up 과 pytest 가 같은 환경을 본다.
  export CELERY_WAIT_TIME_SECONDS= JOB_RETRY_DELAY_SECONDS=
}
phase_integration() {
  local code started passed failed errors secs
  echo
  echo "── ① 기본값 판 Python 통합 (프로젝트 $PROJECT) · $(host_now)"
  container_door "$PROJECT"
  code=$?
  [ "$code" -eq 0 ] || return "$code"
  (cd "$SRC" && GIT_DIR="$COMMON" scripts/worktree-env.sh weekly) > "$WORK/env.log" 2>&1 || { cat "$WORK/env.log"; return 1; }
  close_env
  (cd "$API" && uv sync --frozen) > "$WORK/uv-sync.log" 2>&1 || { tail -5 "$WORK/uv-sync.log"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$API" && uv run --frozen python scripts/dev_edk.py public-key)" || return 1
  export EDK_JWT_PUBLIC_KEY
  name_is_ours || return 1
  lock_acquire "$BLOCK" "${BUILD_LOCK_WAIT_S:-1800}" "${BUILD_LOCK_POLL_S:-5}" "빌드 잠금이 잡혀 있다" \
    "scripts/weekly.sh 의 build·up ($PROJECT)" "${BUILD_LOCK_HELD_BY:-}"
  code=$?
  [ "$code" -eq 0 ] || return "$code"   # 75 상한(WAITED) · 2 잠금 자리를 만들 수 없음(FAIL)
  if [ "$LOCK_ACQUIRED" = new ]; then HELD_BUILD=1; export BUILD_LOCK_HELD_BY=$$; fi
  echo "  빌드 잠금: $LOCK_ACQUIRED (${LOCK_WAITED}초 기다림) · $BLOCK"
  started=$SECONDS
  (cd "$SRC" && docker compose build) > "$WORK/build.log" 2>&1
  code=$?
  echo "  docker compose build → $code ($((SECONDS - started))초)"
  UP=1
  if [ "$code" -eq 0 ]; then
    started=$SECONDS
    (cd "$SRC" && docker compose up -d --wait) > "$WORK/up.log" 2>&1
    code=$?
    echo "  docker compose up -d --wait → $code ($((SECONDS - started))초)"
  fi
  if [ "$HELD_BUILD" -eq 1 ]; then lock_release "$BLOCK"; HELD_BUILD=0; fi
  if [ "$code" -ne 0 ]; then
    tail -20 "$WORK/build.log" "$WORK/up.log" 2>/dev/null
    (cd "$SRC" && docker compose logs --no-color --tail 200 api-py migrate-py worker-py queue parser) > "$RES/compose-logs.txt" 2>&1
    INTEG_LINE="기본값 판 통합: FAIL (build·up 실패 — 시험 안 돎)"
    compose_down
    return 1
  fi
  started=$SECONDS
  run_capped "$INTEG_CAP" "$WORK/integration.full.log" "$SRC" apps/api-py/scripts/test-integration.sh --durations=0
  code=$?
  secs=$((SECONDS - started))
  passed="$(grep -Eo '[0-9]+ passed' "$WORK/integration.full.log" | tail -1 | cut -d' ' -f1)"
  failed="$(grep -Eo '[0-9]+ failed' "$WORK/integration.full.log" | tail -1 | cut -d' ' -f1)"
  errors="$(grep -Eo '[0-9]+ errors?' "$WORK/integration.full.log" | tail -1 | cut -d' ' -f1)"
  { echo "# --durations 표"; awk '/slowest durations/,/short test summary|passed|failed/' "$WORK/integration.full.log"
    echo; echo "# 꼬리 300줄"; tail -300 "$WORK/integration.full.log"; } > "$RES/integration.log"
  meta integration_exit "$code"
  meta integration_secs "$secs"
  if [ "$code" -eq 0 ]; then
    INTEG_LINE="기본값 판 통합: PASS (${passed:-0} passed / ${failed:-0} failed, ${secs}초)"
  else
    [ "$code" -eq 142 ] && echo "  ★ 시간 상한 ${INTEG_CAP}초를 넘겼다"
    INTEG_LINE="기본값 판 통합: FAIL (${passed:-0} passed / ${failed:-0} failed${errors:+ / $errors error}, ${secs}초, 종료 $code)"
    (cd "$SRC" && docker compose logs --no-color --tail 200 api-py migrate-py worker-py queue parser) > "$RES/compose-logs.txt" 2>&1
  fi
  echo "  $INTEG_LINE"
  tail -3 "$WORK/integration.full.log" | sed 's/^/    /'
  compose_down || return 1
  [ "$code" -eq 0 ]
}

# ── ② 변이 테스트 ────────────────────────────────────────────────────
MUT_ARGS=""
phase_mutmut() {
  local code started f targets hash wall dwall n
  echo
  echo "── ② 변이 테스트 · $(host_now)"
  if [ -n "$ONLY" ]; then
    targets="$(printf '%s' "$ONLY" | sed '/^$/d' | LC_ALL=C sort -u)"
    meta targets_source only
  else
    targets="$(default_targets "$REVHASH")"
    meta targets_source default
  fi
  for f in $targets; do
    is_target "$f" || { echo "  ★ 변이 대상 밖이다: $f (대상: $(printf '%s' "$TARGET_GLOBS" | tr '\n' ' '))"; return 1; }
  done
  [ -n "$targets" ] || { echo "  ★ 대상이 없다"; return 1; }
  n="$(printf '%s\n' "$targets" | wc -l | tr -d ' ')"
  if [ -n "$ONLY" ]; then
    TARGETS_LINE="대상 수: $n (--only — 지난 회와 견주지 않음)"
  else
    check_fewer "$n" "$STAMP" || return 1
  fi
  echo "  $TARGETS_LINE"
  host_door
  code=$?
  [ "$code" -eq 0 ] || return "$code"
  # ① 의 기본값 판 환경은 변이 테스트에 넘기지 않는다
  unset CELERY_WAIT_TIME_SECONDS JOB_RETRY_DELAY_SECONDS
  (cd "$API" && uv sync --frozen) > "$WORK/uv-sync-mut.log" 2>&1 || { tail -5 "$WORK/uv-sync-mut.log"; return 1; }
  for f in $targets; do
    [ -s "$API/$f" ] || { echo "  ★ 사본에 없거나 비었다: $f"; return 1; }
  done
  printf '%s\n' "$targets" > "$RES/targets.txt"
  hash="$(printf '%s\n' "$targets" | shasum -a 256 | cut -c1-16)"
  meta targets_count "$n"
  meta targets_hash "$hash"
  [ -e "$API/setup.cfg" ] && { echo "  ★ 사본에 setup.cfg 가 이미 있다(덮어쓰지 않는다): $API/setup.cfg"; return 1; }
  # MUT0 §2 의 둘째 판(사본 설정의 걸림 1~3 을 푼 것)에 대상·테스트 선택을 바꾸고 also_copy 에 .importlinter 를 더함
  {
    echo "[mutmut]"
    echo "source_paths=esgapi"
    echo "only_mutate="
    printf '    %s\n' $targets
    # .importlinter: reconcile 의 시험(test_tasks_registered)이 apps/api-py 뿌리에서 읽는다 — MUT0 의 선택(core·inventory)에는 없던 걸림
    printf '%s\n' "also_copy=" "    conftest.py" "    generated" "    manage.py" "    gunicorn.conf.py" "    .importlinter"
    # not_under_mutmut: 사본에서 뜻이 없는 시험(트램펄린을 심은 소스·코드 객체를 읽거나, 한 프로세스에서 pytest 를 거듭 부르면 깨지는 것). 이름 박은 --deselect 를 두지 않는다
    printf '%s\n' "pytest_add_cli_args=" "    -p" "    no:cacheprovider" "    -m" "    not django_db and not security and not not_under_mutmut"
    echo "pytest_add_cli_args_test_selection="
    printf '    %s\n' $TEST_SELECTION
  } > "$API/setup.cfg"
  cp "$API/setup.cfg" "$RES/setup.cfg"
  started=$SECONDS
  # shellcheck disable=SC2086
  run_capped "$MUT_CAP" "$WORK/mutmut-run.log" "$API" $MUTMUT mutmut run --max-children 4
  code=$?
  wall=$((SECONDS - started))
  meta mutmut_exit "$code"
  meta mutmut_wall "$wall"
  echo "  mutmut run → $code (${wall}초) · $(host_now)"
  tail -5 "$WORK/mutmut-run.log" | tr '\r' '\n' | tail -3 | sed 's/^/    /'
  if [ "$code" -eq 142 ]; then echo "  ★ 시간 상한 ${MUT_CAP}초를 넘겼다(그룹째 끊음)"; return 1; fi
  if [ "$code" -ne 0 ]; then
    # 깨끗한 실행(clean tests)·stats 의 빨강: 표식(not_under_mutmut)이 빠진 새 순수성 시험이면 여기 이름이 나온다
    tr '\r' '\n' < "$WORK/mutmut-run.log" | grep -E '^(FAILED|ERROR) ' | head -20 > "$RES/mutmut-clean-fail.txt"
    if [ -s "$RES/mutmut-clean-fail.txt" ]; then
      echo "  ★ mutmut 안의 pytest 가 빨갛다($RES/mutmut-clean-fail.txt):"
      sed 's/^/    /' "$RES/mutmut-clean-fail.txt"
    else
      rm -f "$RES/mutmut-clean-fail.txt"
    fi
    return 1
  fi
  # shellcheck disable=SC2086
  (cd "$API" && $MUTMUT mutmut results --all true) > "$RES/mutmut-results.txt" 2> "$WORK/results.err" || { tail -5 "$WORK/results.err"; return 1; }
  awk -F': ' '$2 == "survived" || $2 == "timeout" || $2 == "suspicious" { gsub(/^ +/, "", $1); print $1 }' "$RES/mutmut-results.txt" > "$WORK/names.txt"
  started=$SECONDS
  # shellcheck disable=SC2086
  (cd "$API" && $MUTMUT python -I "$REPO/scripts/weekly_mutmut_diffs.py" "$WORK/names.txt") > "$WORK/diffs.txt" 2> "$WORK/diffs.err"
  code=$?
  dwall=$((SECONDS - started))
  meta diffs_exit "$code"
  meta diffs_wall "$dwall"
  echo "  diff 뽑기(한 프로세스) → $code · $(tail -1 "$WORK/diffs.err") · ${dwall}초"
  [ "$code" -eq 0 ] || return 1
  MUT_ARGS="ok"
  MUT_HASH="$hash"
  MUT_WALL="$wall"
  return 0
}

if [ "$DO_INTEG" -eq 1 ] && [ "$DO_MUT" -eq 1 ]; then
  phase_import_checks
  c=$?
  meta import_checks_phase "$c"
  note_result "$c"
fi
if [ "$DO_INTEG" -eq 1 ]; then
  phase_integration
  c=$?
  meta integration_phase "$c"
  [ "$c" -eq 75 ] && INTEG_LINE="기본값 판 통합: 안 돌림 (문·잠금이 30분 안에 안 열림 — WAITED)"
  [ "$c" -ne 0 ] && [ "$c" -ne 75 ] && case "$INTEG_LINE" in *PASS* | *"안 돌림") INTEG_LINE="기본값 판 통합: FAIL (국면이 끝까지 못 돎, 종료 $c)" ;; esac
  note_result "$c"
fi
if [ "$DO_MUT" -eq 1 ]; then
  phase_mutmut
  c=$?
  meta mutmut_phase "$c"
  note_result "$c"
fi

# ── ③ 견주기와 summary.md ────────────────────────────────────────────
echo
if [ "$MUT_ARGS" = ok ]; then
  python3 -I "$REPO/scripts/weekly_compare.py" --run "$RES" --history "$OUTROOT" --integration "$INTEG_LINE" \
    --results "$RES/mutmut-results.txt" --diffs "$WORK/diffs.txt" --known "$KNOWN" --targets-hash "$MUT_HASH" --wall "$MUT_WALL" \
    --targets "$TARGETS_LINE"
  c=$?
  if [ "$c" -eq 0 ]; then meta mutmut_done 1; else note_result 1; fi
else
  [ "$DO_MUT" -eq 1 ] && MUT_NOTE="(mutmut 국면이 끝까지 못 돎)" || MUT_NOTE=""
  if [ -n "$TARGETS_LINE" ]; then
    python3 -I "$REPO/scripts/weekly_compare.py" --run "$RES" --history "$OUTROOT" --integration "$INTEG_LINE" --targets "$TARGETS_LINE"
  else
    python3 -I "$REPO/scripts/weekly_compare.py" --run "$RES" --history "$OUTROOT" --integration "$INTEG_LINE"
  fi
  c=$?
  [ -n "$MUT_NOTE" ] && echo "$MUT_NOTE"
  [ "$c" -eq 0 ] || note_result 1
fi

STATUS_AFTER="$(git status --porcelain)"
if [ "$STATUS_AFTER" != "$STATUS_BEFORE" ]; then
  echo "★ 저장소의 git status 가 처음과 다르다"
  RESULT=FAIL
fi
meta git_status_same "$([ "$STATUS_AFTER" = "$STATUS_BEFORE" ] && echo 1 || echo 0)"
meta uptime_end "$(uptime)"
meta free_end "$(free_txt)"
meta compose_ls_end "$(docker compose ls -q 2>/dev/null | tr '\n' ' ')"
meta result "$RESULT"
trap - EXIT
FINISHED=1
cleanup
meta finished "$(date '+%Y-%m-%d %H:%M:%S')"
if [ "$RESULT" = OK ]; then
  rm -rf "${WORK:?}"
  meta work_removed 1
  echo "일터를 지웠다: $WORK"
else
  meta work_removed 0
  echo "일터를 남겼다(살펴볼 것): $WORK"
fi
echo "결과: $RES/summary.md"
case "$RESULT" in
  OK) echo "WEEKLY=OK"; exit 0 ;;
  WAITED) echo "WEEKLY=WAITED"; exit 75 ;;
  *) echo "WEEKLY=FAIL"; exit 1 ;;
esac
