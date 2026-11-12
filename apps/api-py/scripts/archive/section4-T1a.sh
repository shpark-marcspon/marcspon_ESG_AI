#!/usr/bin/env bash
# 밴드 T1a(MARC-TICK-84: 빠른 게이트의 단계를 줄로 나눠 동시에 돌리고, 테스트 자리 규칙을 검사로 둔다)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-T1a.sh --step <1~4>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-T1a.sh --pure           --step 4 + 심은 파손(planted-breaks-T1a.sh) + --fast 열 번
#         apps/api-py/scripts/section4-T1a.sh --containers     업무 층 워커 수를 재기만(postgres 하나). 판정에 안 든다
#         apps/api-py/scripts/section4-T1a.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서). AI 공급사 호출 0.
# 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 기준 B 는 이 워크트리의 바닥(main b78a477 = 발주서의 8204571 + 밴드 X2 의 병합. 감독 덧붙임 9 「바닥은 워크트리를
#   만들 때의 main」). 순수 층 노드 ID 는 1,709 = 8204571 의 1,614(사라진 것 0) + X2 의 새 테스트 파일 다섯의 95.
#   노드 목록은 저장소에 두지 않고(닫힌 목록 밖) 줄 수와 sha256 앞 16자로 견준다.
set -u
cd "$(dirname "$0")/../../.."
B=b78a477   # 기준 커밋(워크트리의 바닥)
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
NODES_N=1709
NODES_SHA=4ab4b9dd2e36d18c   # sort 한 순수 층 노드 ID 목록의 sha256 앞 16자(기준 B 에서 잼)
LAYOUT_LINE='테스트 파일 115 · 비춘 것 12 · 자유 27 · 허용 76 · 허용인데 없음 0 · 어김 0'
BEFORE_MEDIAN=30   # 기준의 --fast 다섯 번의 (전체 N초) 중앙값(보고 band-reports/T1a-test-speed.md 의 「전」 표)
# 바뀌어도 되는 일곱(발주서 §1-2)
ALLOWED='^(scripts/verify\.sh|scripts/check-gates\.sh|scripts/git-hooks/pre-commit|apps/api-py/scripts/check_test_layout\.py|apps/api-py/scripts/test-layout-allow\.txt|apps/api-py/scripts/section4-T1a\.sh|apps/api-py/scripts/planted-breaks-T1a\.sh)$'
# verify.sh·pre-commit 의 더한 줄이 읽어도 되는 이름: 있던 환경 변수 셋 + 늘 있는 것 + verify.sh 가 맨 위에서 스스로
# 0 으로 두는 FAST·PLAN(환경에서 들어오지 않는다). 새로 읽는 환경 변수 0.
READ_VARS='EDK_JWT_PUBLIC_KEY FAST HOME PATH PLAN SECONDS VERIFY_LOCK_DIR VERIFY_LOCK_POLL_S VERIFY_LOCK_WAIT_S'

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
load1() { uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p'; }
others() { docker ps --format '{{.Names}}' 2>/dev/null | grep -c '^esg-app'; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
steps_of() { grep '^step: ' | sed 's/^step: //'; }
# 순수 층 단계의 출력 덩어리에서 끝 요약 줄
pure_summary() { awk '/^▶ in_api_py uv run --frozen pytest -q/ { on = 1; next } on && /^EXIT=/ { on = 0 } on' "$1" | grep -E '[0-9]+ (passed|failed)' | tail -1; }

echo "── 밴드 T1a §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · 1분 부하 $(load1) · esg-app* 컨테이너 $(others)"

fast_part() { # 가·나
  echo; echo "── 가. 빠른 게이트: VERIFY_FAST=PASS · EXIT= 줄 수 = --fast --plan 의 step 수 · ▶ 차례 = 계획 차례"
  local started=$SECONDS l0 c0
  l0="$(load1)"; c0="$(others)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; scripts/verify.sh --fast --plan | steps_of > "$T/plan.fast"; grep "^▶ " "$T/fast.log" | sed "s/^▶ //" > "$T/ran.fast"; e="$(grep -c "^EXIT=" "$T/fast.log")"; p="$(wc -l < "$T/plan.fast" | tr -d " ")"; echo "  종료 코드 $code · EXIT= ${e}줄 · 계획 ${p}단계 · 0 이 아닌 EXIT $(grep "^EXIT=" "$T/fast.log" | grep -vc "^EXIT=0$") · $(grep "^(전체" "$T/fast.log") $(grep "^(동시 묶음" "$T/fast.log")"; tail -1 "$T/fast.log"; [ "$code" = 0 ] && [ "$(tail -1 "$T/fast.log")" = "VERIFY_FAST=PASS" ] && [ "$e" = "$p" ] && diff "$T/plan.fast" "$T/ran.fast"'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · 1분 부하 $l0 → $(load1) · esg-app* 컨테이너 $c0 → $(others))"
  [ "$STEP" -ge 2 ] && run 'test "$(wc -l < "$T/plan.fast" | tr -d " ")" = 15'

  echo; echo "── 나. 순수 층 노드 ID 가 기준과 글자로 같다($NODES_N) · 빠른 게이트의 순수 층 끝 줄이 $NODES_N passed, 건너뛴 것·경고 없음"
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "not django_db and not security" 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt"); n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; h="$(sha "$T/nodeids.txt" | cut -c1-16)"; echo "  지금 $n · sha256 $h (기준 $NODES_N · $NODES_SHA) · 사본 $T/nodeids.txt"; [ "$n" = "$NODES_N" ] && [ "$h" = "$NODES_SHA" ]'
  run 'last="$(pure_summary "$T/fast.log")"; echo "  $last"; echo "$last" | grep -q -E "^$NODES_N passed" || exit 1; echo "$last" | grep -q -E "failed|skipped|xfailed|xpassed|warning|error" && exit 1; exit 0'
}

layout_part() { # 라
  echo; echo "── 라. 자리 검사 단독: 종료 0, 셈 줄 그대로"
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1); code=$?; cat "$T/layout.txt"; [ "$code" = 0 ] && [ "$(head -1 "$T/layout.txt")" = "$LAYOUT_LINE" ] && [ "$(wc -l < "$T/layout.txt" | tr -d " ")" = 1 ]'
  run 'GD="$(git rev-parse --absolute-git-dir)"; (cd "$A" && GIT_DIR="$GD" uv run --frozen python scripts/check_test_layout.py > "$T/layout.gd.txt" 2>&1); code=$?; echo "  GIT_DIR 판: $(head -1 "$T/layout.gd.txt")"; [ "$code" = 0 ] && cmp -s "$T/layout.txt" "$T/layout.gd.txt"'
}

bounds_part() { # 마·바·사·아
  echo; echo "── 마. 경계: 바뀐 파일 ⊆ §1-2 의 일곱, 0줄 구역, pre-commit 의 모드 100755"
  run 'changed > "$T/changed.txt"; cat "$T/changed.txt" | sed "s/^/  /"; ! grep -v -E "$ALLOWED" "$T/changed.txt"'
  run 'git diff --quiet "$B" -- apps/web generated apps/api-py/esgapi apps/api-py/tests apps/api-py/tests_integration apps/api-py/pyproject.toml apps/api-py/uv.lock apps/api-py/conftest.py apps/api-py/generated pnpm-lock.yaml package.json compose.yaml docker infra services README.md scripts/worktree-env.sh scripts/section4-PD2.sh && test -z "$(git ls-files --others --exclude-standard -- apps/web generated apps/api-py/esgapi apps/api-py/tests apps/api-py/tests_integration services docker infra)"'
  run 'for f in $(git ls-tree -r --name-only "$B" -- apps/api-py/scripts); do git diff --quiet "$B" -- "$f" || { echo "★ 지난 밴드의 스크립트가 바뀌었다: $f"; exit 1; }; done'
  run 'm="$(git ls-files -s scripts/git-hooks/pre-commit | cut -c1-6)"; echo "  색인의 모드 $m · 실행 비트 $([ -x scripts/git-hooks/pre-commit ] && echo 있음 || echo 없음)"; [ "$m" = 100755 ] && [ -x scripts/git-hooks/pre-commit ]'

  echo; echo "── 바. 컨테이너 단계 여덟의 글자·차례가 기준과 같다(--plan − --fast --plan)"
  run 'mkdir -p "$T/base/scripts"; git show "$B:scripts/verify.sh" > "$T/base/scripts/verify.sh"; rest() { awk "NR == FNR { f[++n] = \$0; next } i < n && \$0 == f[i + 1] { i++; next } { print }" "$2" "$1"; }; (bash "$T/base/scripts/verify.sh" --plan 2>/dev/null | steps_of) > "$T/bp.full"; (bash "$T/base/scripts/verify.sh" --fast --plan 2>/dev/null | steps_of) > "$T/bp.fast"; scripts/verify.sh --plan | steps_of > "$T/np.full"; scripts/verify.sh --fast --plan | steps_of > "$T/np.fast"; rest "$T/bp.full" "$T/bp.fast" > "$T/b.rest"; rest "$T/np.full" "$T/np.fast" > "$T/n.rest"; echo "  기준 전량 $(wc -l < "$T/bp.full" | tr -d " ") − 빠른 $(wc -l < "$T/bp.fast" | tr -d " ") = $(wc -l < "$T/b.rest" | tr -d " ") · 지금 $(wc -l < "$T/np.full" | tr -d " ") − $(wc -l < "$T/np.fast" | tr -d " ") = $(wc -l < "$T/n.rest" | tr -d " ")"; sed "s/^/    /" "$T/n.rest"; [ "$(wc -l < "$T/b.rest" | tr -d " ")" = 8 ] && diff "$T/b.rest" "$T/n.rest"'

  echo; echo "── 사. 건너뛰기·재실행 0: 더한 줄이 읽는 환경 변수 ⊆ {$READ_VARS} · rerun|retry|--lf 0줄"
  run 'git diff "$B" -- scripts/verify.sh scripts/git-hooks/pre-commit | grep "^+" | grep -v "^+++" > "$T/added.txt"; names="$(grep -o -E "\\\$\{?[A-Z][A-Z0-9_]*" "$T/added.txt" | sed -E "s/^\\\$\{?//" | sort -u | tr "\n" " ")"; echo "  더한 줄 $(wc -l < "$T/added.txt" | tr -d " ") · 읽는 이름: ${names:-없음}"; for v in $names; do case " $READ_VARS " in *" $v "*) ;; *) echo "★ 새로 읽는 환경 변수: $v"; exit 1 ;; esac; done; ! grep -n -i -E "rerun|reruns|--lf|--last-failed|retry" "$T/added.txt"'

  echo; echo "── 아. 보안 층 직렬: test-security.sh 0줄(마), verify.sh 의 보안 단계 글자에 -n 없음"
  run 's="$(scripts/verify.sh --plan | steps_of | grep test-security)"; echo "  $s"; [ "$s" = "apps/api-py/scripts/test-security.sh" ]'
}

gates_part() { # 다
  echo; echo "── 다. 게이트 자기 검사(check-gates.sh)"
  run 'scripts/check-gates.sh > "$T/gates.log" 2>&1; code=$?; grep -E "^(▶|EXIT=)" "$T/gates.log" | paste - - | grep -v "EXIT=0$" | sed "s/^/  ★ /"; tail -1 "$T/gates.log"; echo "  기록: $T/gates.log"; [ "$code" = 0 ] && tail -1 "$T/gates.log" | grep -q -E "^GATES=PASS ([0-9]+)/\1$"'
}

trailers_part() { # 차
  echo; echo "── 차. 커밋 트레일러: $B..HEAD 의 커밋마다 Ticket: MARC-TICK-84 와 Derives-from: MARC-TICK-71"
  run 'n=0; bad=0; for c in $(git rev-list "$B"..HEAD); do n=$((n + 1)); msg="$(git log -1 --format=%B "$c")"; printf "%s\n" "$msg" | grep -q -x "Ticket: MARC-TICK-84" && printf "%s\n" "$msg" | grep -q -x "Derives-from: MARC-TICK-71" || { echo "★ 트레일러가 없다: $c"; bad=1; }; done; echo "  커밋 $n"; [ "$bad" = 0 ]'
}

step_part() {
  fast_part
  layout_part
  bounds_part
  [ "$STEP" -ge 2 ] && gates_part
  trailers_part
}

pure_extra_part() { # 자
  echo; echo "── 자. 심은 파손(planted-breaks-T1a.sh)"
  run "$A/scripts/planted-breaks-T1a.sh > \"\$T/planted.log\" 2>&1; code=\$?; grep -E '^(#|PLANTED=|지문)' \"\$T/planted.log\"; echo \"  기록: \$T/planted.log\"; [ \"\$code\" = 0 ] && tail -1 \"\$T/planted.log\" | grep -q -E '^PLANTED=([0-9]+)/\\1\$'"

  echo; echo "── 자. --fast 열 번 연속(전부 VERIFY_FAST=PASS · 중앙값이 기준의 ${BEFORE_MEDIAN}초보다 작다)"
  run 'printf "  %-4s %-6s %-8s %-10s %-12s %s\n" 회 끝줄 "전체(초)" "묶음(초)" "1분 부하" "esg-app* 컨테이너"; : > "$T/ten.txt"; bad=0; for i in 1 2 3 4 5 6 7 8 9 10; do l0="$(load1)"; c0="$(others)"; scripts/verify.sh --fast > "$T/ten.$i.log" 2>&1; last="$(tail -1 "$T/ten.$i.log")"; all="$(sed -n "s/^(전체 \([0-9]*\)초)$/\1/p" "$T/ten.$i.log")"; lane="$(sed -n "s/^(동시 묶음 \([0-9]*\)초)$/\1/p" "$T/ten.$i.log")"; printf "  %-4s %-6s %-8s %-10s %-12s %s\n" "$i" "${last#VERIFY_FAST=}" "${all:-?}" "${lane:-?}" "${l0}→$(load1)" "${c0}→$(others)"; echo "$all" >> "$T/ten.txt"; [ "$last" = "VERIFY_FAST=PASS" ] || { bad=1; echo "  ★ ${i}회가 빨갛다: $T/ten.$i.log"; grep "^EXIT=" "$T/ten.$i.log" | grep -v "EXIT=0$"; }; done; med="$(sort -n "$T/ten.txt" | sed -n 5,6p | paste -s -d" " - | awk "{ print (\$1 + \$2) / 2 }")"; echo "  중앙값 ${med}초 (전 ${BEFORE_MEDIAN}초) · 기록 $T/ten.*.log"; [ "$bad" = 0 ] && awk -v m="$med" -v b="$BEFORE_MEDIAN" "BEGIN { exit !(m < b) }"'
  run 'for i in 1 2 3 4 5 6 7 8 9 10; do last="$(pure_summary "$T/ten.$i.log")"; echo "$last" | grep -q -E "^$NODES_N passed" || { echo "★ ${i}회 순수 층: $last"; exit 1; }; done; echo "  열 번 모두 순수 층 $NODES_N passed"'
}

# 컨테이너 앞의 문: 다른 esg-app* 컨테이너가 0 이 될 때까지 60초마다 최대 30분, 그 뒤 free ≥ 20% · 1분 부하 < 12.
gate() {
  local tries=0 n free load
  while :; do
    n="$(others)"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(load1)"
    if [ "$n" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: 떠 있는 esg-app* 컨테이너 0 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: esg-app* 컨테이너 $n · free ${free:-?}% · 1분 부하 ${load:-?} · 30분 기다림 — 못 잼)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

containers_part() { # 2-5: 재기만. 판정에 안 든다(늘 EXIT=0)
  echo; echo "── 업무 층 워커 수 재기(postgres 하나, -n 2 / -n 4 를 두 번씩) + 「173 errors」 재현 한 번 — 판정 밖"
  [ -f .env ] || scripts/worktree-env.sh T1a
  PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env | tail -1)"
  echo "  compose 프로젝트 $PROJECT"
  [ "$PROJECT" = esg-app-t1a ] || { echo "  ★ .env 의 프로젝트가 esg-app-t1a 가 아니다 — 띄우지 않는다"; echo "EXIT=0"; return 0; }
  if ! gate; then echo "EXIT=0"; return 0; fi
  docker compose up -d --wait postgres 2>&1 | tail -2
  local kind i s code last mem
  printf '  %-6s %-3s %-8s %-14s %-10s %s\n' 워커 회 "걸린 초" "postgres 메모리" "1분 부하" 끝줄
  for kind in 2 4; do
    for i in 1 2; do
      s=$SECONDS
      $A/scripts/test-business.sh -n "$kind" --durations=15 > "$T/biz.n$kind.$i.log" 2>&1
      code=$?
      last="$(tail -1 "$T/biz.n$kind.$i.log")"
      mem="$(docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | grep "^$PROJECT-postgres" | cut -d' ' -f2-)"
      printf '  -n %-3s %-3s %-8s %-14s %-10s %s (종료 %s)\n' "$kind" "$i" "$((SECONDS - s))" "${mem:-?}" "$(load1)" "$last" "$code"
    done
  done
  echo "  느린 업무 테스트(-n 2 첫 회의 --durations=15):"
  sed -n '/slowest 15 durations/,/^$/p' "$T/biz.n2.1.log" | head -18 | sed 's/^/    /'
  echo "  「173 errors」 재현: 한 파일 xdist 없이 → 바로 -n 2 두 번"
  $A/scripts/test-business.sh esgapi/accounts/tests/test_api.py > "$T/repro.0.log" 2>&1
  echo "    한 파일: $(tail -1 "$T/repro.0.log")"
  for i in 1 2; do
    $A/scripts/test-business.sh -n 2 > "$T/repro.$i.log" 2>&1
    echo "    -n 2 ($i): $(tail -1 "$T/repro.$i.log")"
    if grep -q -E '[0-9]+ errors?' "$T/repro.$i.log"; then
      echo "    ★ 재현됐다 — 첫 오류 40줄:"; grep -n -m1 -A40 -E '^(_+ ERROR|E )' "$T/repro.$i.log" | head -40 | sed 's/^/      /'
    fi
  done
  echo "  기록: $T/biz.*.log · $T/repro.*.log"
  docker compose down -v --remove-orphans 2>&1 | tail -2
  echo "  남은 컨테이너 $(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d ' ') · 볼륨 $(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d ' ')"
  echo "EXIT=0"
}

after_commit_part() { # 카
  echo; echo "── 카. 커밋된 모습"
  run 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  git status --porcelain ${n}줄"; test "$n" = 0'
  run 'git log --format="%h %s" "$B"..HEAD | sed "s/^/  /"; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 4'
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
