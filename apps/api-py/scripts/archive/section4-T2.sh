#!/usr/bin/env bash
# 밴드 T2(MARC-TICK-98: 빌드 잠금 + 주 1회 정기 실행 scripts/weekly.sh + MARC-ISSUE-90 의 1·2)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-T2.sh --step <1~3>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-T2.sh --pure           --step 3 + 심은 파손(planted-breaks-T2.sh --pure, PLANTED=6/6)
#         apps/api-py/scripts/section4-T2.sh --containers <자리>   컨테이너 한 덩어리(한 번): 문 → weekly 작은 실행 두 회
#                  (decimal.py 하나, 결과는 <자리>/w1, 알려진 생존 씨앗은 <자리>/known-survivors.txt) → 이 워크트리의
#                  프로젝트에서 짧은 값 통합 한 번 · 심은 파손 P7 · README 의 이미지 고르기 → 내림 · 남은 것 0
#         … --containers <자리> --self-only   weekly 두 회를 빼고 이 워크트리의 프로젝트 부분만(감독 처분 — 첫 덩어리 뒤)
#         apps/api-py/scripts/section4-T2.sh --after-commit   ④ 커밋 뒤: 가·나·다·아 + 작업 트리 0줄
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독이 병합 뒤). rehearsal.sh 는 부르지 않는다. AI 공급사 호출 0.
# 컨테이너 0(--step·--pure·--after-commit). macOS /bin/bash 3.2 에서 돈다.
#
# ★ 기준 B 는 이 워크트리의 바닥(main 24ab83c, XC·GC1·FW1 병합 뒤 = 발주서의 바닥).
set -u
cd "$(dirname "$0")/../../.."
B=24ab83c   # 기준 커밋(워크트리의 바닥)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=3
SPOT=""
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [1-3]) ;; *) echo "사용: $0 --step <1~3>" >&2; exit 2 ;; esac ;;
  --pure | --after-commit) ;;
  --containers) SPOT="${2:-}"; SELF_ONLY=0; [ "${3:-}" = --self-only ] && SELF_ONLY=1; [ -n "$SPOT" ] && [ -s "$SPOT/known-survivors.txt" ] || { echo "사용: $0 --containers <자리(known-survivors.txt 가 있는 곳)>" >&2; exit 2; } ;;
  *) echo "사용: $0 --step <1~3> | --pure | --containers <자리> | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
# 바뀌어도 되는 것(발주서 §1-2 의 닫힌 목록)
ALLOWED='^(scripts/lib/lock\.sh|scripts/with-build-lock\.sh|scripts/weekly\.sh|scripts/weekly_compare\.py|scripts/weekly_mutmut_diffs\.py|scripts/verify\.sh|scripts/check-gates\.sh|README\.md|apps/api-py/tests_integration/test_worker_flow\.py|apps/api-py/scripts/section4-T2\.sh|apps/api-py/scripts/planted-breaks-T2\.sh)$'
# 0줄이어야 하는 자리(발주서 §1-2 의 「0줄」)
ZERO='apps/api-py/esgapi apps/api-py/tests apps/api-py/conftest.py apps/api-py/tests_integration/conftest.py apps/api-py/pyproject.toml apps/api-py/uv.lock package.json pnpm-lock.yaml compose.yaml docker apps/web scripts/git-hooks scripts/worktree-env.sh scripts/section4-PD2.sh .gitignore .env.example'
# 컨테이너 단계 일곱(글자·차례. 발주서 1-1 의 1)
CONTAINER_SEVEN='docker compose down -v --remove-orphans
docker compose build
docker compose up -d --wait
apps/api-py/scripts/test-business.sh -n 2
apps/api-py/scripts/test-security.sh
apps/api-py/scripts/test-integration.sh
docker compose down -v'

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
projects() { docker compose ls -q 2>/dev/null | tr '\n' ' '; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
steps_of() { grep '^step: ' | sed 's/^step: //'; }
now_ms() { perl -MTime::HiRes=time -e 'printf "%.3f\n", time'; }

echo "── 밴드 T2 §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · 1분 부하 $(load1) · free $(free_pct)% · compose ls -q: $(projects)"

# 가. 전량 계획 22단계(컨테이너 일곱의 글자 그대로), 빠른 계획 15·docker 0, 빌드 잠금 주석 둘은 build 앞·up 뒤(전량만)
plan_part() {
  scripts/verify.sh --plan > "$T/plan.full" 2>&1 || return 1
  scripts/verify.sh --fast --plan > "$T/plan.fast" 2>&1 || return 1
  local full fast dock seven before after
  full="$(steps_of < "$T/plan.full" | wc -l | tr -d ' ')"
  fast="$(steps_of < "$T/plan.fast" | wc -l | tr -d ' ')"
  dock="$(grep -c docker "$T/plan.fast")"
  seven="$(steps_of < "$T/plan.full" | grep -v -x -F -f <(steps_of < "$T/plan.fast"))"
  before="$(grep -B1 -x 'step: docker compose build' "$T/plan.full" | head -1)"
  after="$(grep -A1 -x 'step: docker compose up -d --wait' "$T/plan.full" | tail -1)"
  echo "  전량 step: $full · 빠른 step: $fast · 빠른 계획의 docker 줄 $dock · 잠금 주석: 전량 $(grep -c '^# 빌드 잠금' "$T/plan.full") · 빠른 $(grep -c '빌드 잠금' "$T/plan.fast")"
  echo "  build 바로 앞: $before"
  echo "  up 바로 뒤:   $after"
  [ "$full" -eq 22 ] && [ "$fast" -eq 15 ] && [ "$dock" -eq 0 ] && [ "$seven" = "$CONTAINER_SEVEN" ] &&
    [ "$(grep -c '^# 빌드 잠금' "$T/plan.full")" -eq 2 ] && [ "$(grep -c '빌드 잠금' "$T/plan.fast")" -eq 0 ] &&
    case "$before" in "# 빌드 잠금을 잡는다:"*) true ;; *) false ;; esac &&
    case "$after" in "# 빌드 잠금을 놓는다"*) true ;; *) false ;; esac
}
# 나. 게이트의 자기 검사(기존 37 + 새 16)
gates_part() {
  scripts/check-gates.sh > "$T/gates.log" 2>&1
  local code=$?
  grep '^GATES=' "$T/gates.log"
  grep -B2 '^EXIT=[^0]' "$T/gates.log" | sed 's/^/    /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/gates.log")" = "GATES=PASS 53/53" ]
}
# 다. 빠른 게이트
fast_part() {
  scripts/verify.sh --fast > "$T/fast.log" 2>&1
  local code=$?
  grep -v '^EXIT=0$' "$T/fast.log" | grep '^EXIT=' | sed 's/^/    /'
  tail -2 "$T/fast.log"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/fast.log")" = "VERIFY_FAST=PASS" ]
}
# 바. 진짜 with-build-lock.sh 둘을 임시 자리로 동시에(sleep 2 를 감쌈) → 겹침 0, 둘 다 0. 감싼 안에서 한 번 더 → 기다림 0
wrap_part() {
  local dir="$T/wrap/build.lock" a b ca cb s1 e1 s2 e2 started
  mkdir -p "$T/wrap"
  BUILD_LOCK_DIR="$dir" BUILD_LOCK_HELD_BY= BUILD_LOCK_POLL_S=1 scripts/with-build-lock.sh sh -c 'echo "a $(perl -MTime::HiRes=time -e "printf q(%.3f), time")" >> "$0"; sleep 2; echo "a $(perl -MTime::HiRes=time -e "printf q(%.3f), time")" >> "$0"' "$T/wrap/times" > "$T/wrap/a.out" 2>&1 &
  a=$!
  BUILD_LOCK_DIR="$dir" BUILD_LOCK_HELD_BY= BUILD_LOCK_POLL_S=1 scripts/with-build-lock.sh sh -c 'echo "b $(perl -MTime::HiRes=time -e "printf q(%.3f), time")" >> "$0"; sleep 2; echo "b $(perl -MTime::HiRes=time -e "printf q(%.3f), time")" >> "$0"' "$T/wrap/times" > "$T/wrap/b.out" 2>&1 &
  b=$!
  wait "$a"; ca=$?
  wait "$b"; cb=$?
  s1="$(awk '$1 == "a" { print $2; exit }' "$T/wrap/times")"; e1="$(awk '$1 == "a" { v = $2 } END { print v }' "$T/wrap/times")"
  s2="$(awk '$1 == "b" { print $2; exit }' "$T/wrap/times")"; e2="$(awk '$1 == "b" { v = $2 } END { print v }' "$T/wrap/times")"
  echo "  a: $s1 → $e1 (종료 $ca) · b: $s2 → $e2 (종료 $cb) · 기다린 쪽의 글: $(grep -h -c '기다린다' "$T/wrap/a.out" "$T/wrap/b.out" | tr '\n' ' ')"
  # 겹침 0: 한쪽의 끝이 다른 쪽의 시작보다 앞이다
  awk -v s1="$s1" -v e1="$e1" -v s2="$s2" -v e2="$e2" 'BEGIN { exit !((e1 <= s2) || (e2 <= s1)) }' || { echo "  ★ 겹쳤다"; return 1; }
  started=$SECONDS
  BUILD_LOCK_DIR="$dir" BUILD_LOCK_HELD_BY= BUILD_LOCK_WAIT_S=30 scripts/with-build-lock.sh scripts/with-build-lock.sh true > "$T/wrap/c.out" 2>&1
  local cc=$?
  echo "  감싼 안에서 한 번 더 → 종료 $cc · $((SECONDS - started))초 · $(grep -c '이미 조상' "$T/wrap/c.out")줄 「이미 조상」 · 끝난 뒤 잠금 폴더 $([ -e "$dir" ] && echo 있음 || echo 없음)"
  [ "$ca" -eq 0 ] && [ "$cb" -eq 0 ] && [ "$cc" -eq 0 ] && [ $((SECONDS - started)) -lt 5 ] && [ ! -e "$dir" ]
}
# 2. SIGTERM 시험(MARC-ISSUE-90 의 1)이 모이고 린트·타입을 지나며, 바뀐 자리가 그 시험 안(기준 :396-429)뿐이다.
#    README 의 바뀐 자리는 「워크트리에서 띄우기」 절(기준 :255-266) 안이다(③ 의 정기 실행 단락은 그 밖의 새 절 하나)
issue90_part() {
  local collected hunks bad=0 h start len
  collected="$(cd apps/api-py && uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration --collect-only 2>&1 | tail -1)"
  echo "  모으기: $collected"
  case "$collected" in "21 tests collected"*) ;; *) bad=1 ;; esac
  (cd apps/api-py && uv run --frozen ruff check tests_integration/test_worker_flow.py && uv run --frozen ruff format --check tests_integration/test_worker_flow.py &&
    uv run --frozen pyright tests_integration/test_worker_flow.py) > "$T/issue90.lint" 2>&1 || { tail -5 "$T/issue90.lint"; bad=1; }
  echo "  ruff·pyright: $(tail -1 "$T/issue90.lint")"
  # 기준 쪽 hunk 머리(-시작,길이)가 396~429 안
  hunks="$(git diff -U0 "$B" -- apps/api-py/tests_integration/test_worker_flow.py | sed -n 's/^@@ -\([0-9,]*\) .*/\1/p' | tr '\n' ' ')"
  echo "  test_worker_flow.py 의 기준 쪽 hunk: ${hunks:-없음}"
  for h in $hunks; do
    start="${h%%,*}"; len=1; case "$h" in *,*) len="${h#*,}" ;; esac
    [ "$start" -ge 396 ] && [ $((start + len)) -le 430 ] || { echo "  ★ SIGTERM 시험 밖: $h"; bad=1; }
  done
  [ -n "$hunks" ] || bad=1
  # 단언: 신호 기록은 kill 앞의 셈보다 늘기를(기록 전체), 옛 「worker_logs(200) 안에 있음」 은 그 시험에서 사라짐
  sed -n '396,440p' apps/api-py/tests_integration/test_worker_flow.py > "$T/sigterm.py"
  grep -q 'seen = compose("logs", "--no-color", "worker-py").count(WARM_SHUTDOWN)' "$T/sigterm.py" &&
    grep -q '.count(WARM_SHUTDOWN) > seen' "$T/sigterm.py" && ! grep -q 'WARM_SHUTDOWN in worker_logs' "$T/sigterm.py" || { echo "  ★ 신호 기다림의 글자가 다르다"; bad=1; }
  hunks="$(git diff -U0 "$B" -- README.md | sed -n 's/^@@ -\([0-9,]*\) .*/\1/p' | tr '\n' ' ')"
  echo "  README.md 의 기준 쪽 hunk: ${hunks:-없음}"
  grep -q "docker image ls -q --filter 'reference=esg-app-<이름>/\*' | xargs docker image rm" README.md || { echo "  ★ README 의 새 지우기 명령이 없다"; bad=1; }
  ! grep -q 'docker image rm esg-app-<이름>/server:local' README.md || { echo "  ★ README 의 옛 지우기 명령이 남았다"; bad=1; }
  [ "$bad" -eq 0 ]
}
# 라. 견주기 도우미의 자기 시험
selftest_part() { python3 -I scripts/weekly_compare.py --self-test | tee "$T/selftest.log"; [ "$(tail -1 "$T/selftest.log" | cut -d' ' -f1)" = "SELF_TEST=PASS" ]; }
# 마. weekly.sh 를 가짜 도구로: --plan 은 docker·uv·git archive 호출 0. 남의 프로젝트 이름·포트를 내보낸 셸에서 돈 판
#     (--integration-only)이 부른 compose 호출은 전부 esg-app-weekly 환경이고, config 가 남의 이름을 돌려주면 띄우지도
#     내리지도 않고 FAIL. 일터·결과는 임시 자리(HOME·--out), 잠금도 임시 자리
fake_tools() {
  local fb="$T/fakebin" real_git
  real_git="$(command -v git)"
  mkdir -p "$fb"
  cat > "$fb/docker" <<'STUB'
#!/usr/bin/env bash
echo "docker $* · project=${COMPOSE_PROJECT_NAME-<unset>} api=${API_PY_PORT-<unset>} pg=${POSTGRES_PORT-<unset>} celery=${CELERY_WAIT_TIME_SECONDS-<unset>} retry=${JOB_RETRY_DELAY_SECONDS-<unset>}" >> "$FAKE_LOG"
case "$*" in
  "compose config --format json") echo "{\"name\": \"${FAKE_COMPOSE_NAME:-esg-app-weekly}\"}" ;;
esac
exit 0
STUB
  cat > "$fb/uv" <<'STUB'
#!/usr/bin/env bash
echo "uv $* · celery=${CELERY_WAIT_TIME_SECONDS-<unset>} retry=${JOB_RETRY_DELAY_SECONDS-<unset>}" >> "$FAKE_LOG"
case "$*" in
  *"dev_edk.py public-key"*) echo "fake-public-key" ;;
  *"pytest"*) echo "21 passed in 0.01s" ;;
esac
exit 0
STUB
  cat > "$fb/perl" <<'STUB'
#!/usr/bin/env bash
# perl -e '<alarm 의 글>' <초> <명령…> 의 흉내: 상한 없이 명령을 돌린다
echo "perl alarm $3 · ${*:4}" >> "$FAKE_LOG"
shift 3
exec "$@"
STUB
  printf '#!/usr/bin/env bash\necho "System-wide memory free percentage: 50%%"\n' > "$fb/memory_pressure"
  printf '#!/usr/bin/env bash\necho "12:00  up 1 day, 2 users, load averages: 1.00 1.00 1.00"\n' > "$fb/uptime"
  printf '#!/usr/bin/env bash\necho "git $*" >> "$FAKE_LOG"\nexec %s "$@"\n' "$real_git" > "$fb/git"
  chmod +x "$fb"/*
}
weekly_plan_part() {
  fake_tools
  : > "$T/fake.plan.log"
  env PATH="$T/fakebin:$PATH" FAKE_LOG="$T/fake.plan.log" HOME="$T/home.plan" scripts/weekly.sh --plan > "$T/weekly.plan" 2>&1
  local code=$?
  sed 's/^/    /' "$T/weekly.plan"
  echo "  종료 코드 $code · 가짜 도구 호출: docker $(grep -c '^docker ' "$T/fake.plan.log") · uv $(grep -c '^uv ' "$T/fake.plan.log") · git archive $(grep -c '^git archive' "$T/fake.plan.log") · git 전부: $(grep '^git ' "$T/fake.plan.log" | tr '\n' ';')"
  [ "$code" -eq 0 ] && ! grep -q '^docker \|^uv \|^git archive\|^perl ' "$T/fake.plan.log" && [ ! -e "$T/home.plan" ] &&
    grep -q '① 기본값 판' "$T/weekly.plan" && grep -q '② calc 변이' "$T/weekly.plan" && grep -q '③ ' "$T/weekly.plan"
}
weekly_fake_part() {
  fake_tools
  local code bad=0 compose_lines
  mkdir -p "$T/fake-locks"
  : > "$T/fake.run.log"
  env PATH="$T/fakebin:$PATH" FAKE_LOG="$T/fake.run.log" HOME="$T/home.run" BUILD_LOCK_DIR="$T/fake-locks/build.lock" \
    VERIFY_LOCK_DIR="$T/fake-locks/verify.lock" BUILD_LOCK_HELD_BY= \
    COMPOSE_PROJECT_NAME=esg-app-남의것 API_PY_PORT=1 POSTGRES_PORT=1 CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1 \
    scripts/weekly.sh --commit HEAD --integration-only --out "$T/fake-out" > "$T/weekly.fake" 2>&1
  code=$?
  tail -4 "$T/weekly.fake" | sed 's/^/    /'
  compose_lines="$(grep -E '^docker compose (config|build|up|down|logs)' "$T/fake.run.log")"
  echo "  남의 이름·포트를 내보낸 셸 → 종료 코드 $code · compose 호출 $(printf '%s\n' "$compose_lines" | grep -c .) · 그 가운데 esg-app-weekly·포트 없음·빈 짧은 값이 아닌 것 $(printf '%s\n' "$compose_lines" | grep -v -c ' project=esg-app-weekly api=<unset> pg=<unset> celery= retry=$')"
  echo "  pytest 의 환경: $(grep 'pytest' "$T/fake.run.log" | sed 's/.* · //')"
  echo "  summary 첫 줄: $(head -1 "$T"/fake-out/*/summary.md 2>/dev/null)"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/weekly.fake")" = "WEEKLY=OK" ] || bad=1
  printf '%s\n' "$compose_lines" | grep -q '^docker compose build ' || bad=1
  printf '%s\n' "$compose_lines" | grep -q '^docker compose up -d --wait ' || bad=1
  printf '%s\n' "$compose_lines" | grep -q '^docker compose down -v --remove-orphans ' || bad=1
  [ "$(printf '%s\n' "$compose_lines" | grep -v -c ' project=esg-app-weekly api=<unset> pg=<unset> celery= retry=$')" -eq 0 ] || bad=1
  # compose ls -q(문·기록 — 프로젝트에 묶이지 않는다)는 환경을 닫기 전에도 부른다. 그 밖의 호출에 남의 이름 0
  ! grep -v '^docker compose ls -q ' "$T/fake.run.log" | grep -q '남의것' || bad=1
  grep 'pytest' "$T/fake.run.log" | grep -q 'celery= retry=$' || bad=1
  grep -q -x '기본값 판 통합: PASS (21 passed / 0 failed, [0-9]*초)' "$T"/fake-out/*/summary.md || bad=1
  [ ! -e "$T/fake-locks/build.lock" ] || bad=1
  # config 가 남의 이름을 돌려주면: build·up·down 0, FAIL
  : > "$T/fake.run2.log"
  env PATH="$T/fakebin:$PATH" FAKE_LOG="$T/fake.run2.log" HOME="$T/home.run" FAKE_COMPOSE_NAME=esg-app-남의것 BUILD_LOCK_DIR="$T/fake-locks/build.lock" \
    VERIFY_LOCK_DIR="$T/fake-locks/verify.lock" BUILD_LOCK_HELD_BY= \
    scripts/weekly.sh --commit HEAD --integration-only --out "$T/fake-out" > "$T/weekly.fake2" 2>&1
  local code2=$?
  echo "  config 가 남의 이름 → 종료 코드 $code2 · 끝 줄 $(tail -1 "$T/weekly.fake2") · build·up·down 호출 $(grep -c -E '^docker compose (build|up|down)' "$T/fake.run2.log") · $(grep -m1 '★' "$T/weekly.fake2")"
  [ "$code2" -eq 1 ] && [ "$(tail -1 "$T/weekly.fake2")" = "WEEKLY=FAIL" ] && ! grep -q -E '^docker compose (build|up|down)' "$T/fake.run2.log" || bad=1
  [ "$bad" -eq 0 ]
}
# 아. 닫힌 목록 대조(기준에서 바뀐 파일 ⊂ §1-2)
allowed_part() {
  local bad
  changed > "$T/changed"
  sed 's/^/    /' "$T/changed"
  bad="$(grep -v -E "$ALLOWED" "$T/changed")"
  [ -z "$bad" ] || { echo "  ★ 닫힌 목록 밖: $bad"; return 1; }
}
# 자. 제품 코드·lock·compose·지난 밴드 스크립트 0줄
zero_part() {
  local n prev
  # shellcheck disable=SC2086
  n="$(git diff --name-only "$B" -- $ZERO | wc -l | tr -d ' ')"
  # 지난 밴드 스크립트(이 밴드의 둘 말고)
  prev="$(changed | grep -E '^apps/api-py/scripts/(section4|planted-breaks)-' | grep -v -E 'section4-T2\.sh|planted-breaks-T2\.sh')"
  echo "  0줄 자리의 바뀐 파일: $n · 지난 밴드 스크립트의 바뀐 파일: ${prev:-없음}"
  [ "$n" -eq 0 ] && [ -z "$prev" ]
}

# ── 컨테이너 한 덩어리 ───────────────────────────────────────────────
WEEKLY_PROJECT=esg-app-weekly
SELF_PROJECT="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env)"
door_part() {
  . scripts/lib/lock.sh
  container_door "$SELF_PROJECT"
}
# <n> 회째 weekly 작은 실행. 끝 줄·summary 맨 위 다섯 줄·meta 를 찍는다
weekly_small() { # <회> [더 줄 인자…]
  local n="$1" code res
  shift
  echo "  시작 · 1분 부하 $(load1) · free $(free_pct)% · compose ls -q: $(projects)"
  scripts/weekly.sh --commit HEAD --only esgapi/core/calc/decimal.py --known "$SPOT/known-survivors.txt" --out "$SPOT/w1" "$@" > "$SPOT/weekly$n.log" 2>&1
  code=$?
  res="$(sed -n 's/^결과: \(.*\)\/summary.md$/\1/p' "$SPOT/weekly$n.log" | tail -1)"
  echo "  끝 줄 $(tail -1 "$SPOT/weekly$n.log") · 종료 $code · 결과 ${res:-?}"
  [ -n "$res" ] && head -5 "$res/summary.md" | sed 's/^/    | /'
  [ -n "$res" ] && sed 's/^/    meta: /' "$res/meta.txt"
  grep -E '빌드 잠금:|docker compose (build|up|down)|mutmut run|diff 뽑기|문 열림|문 닫힘|일터' "$SPOT/weekly$n.log" | sed 's/^/    · /'
  echo "  끝 · 1분 부하 $(load1) · free $(free_pct)% · compose ls -q: $(projects)"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$SPOT/weekly$n.log")" = "WEEKLY=OK" ]
}
weekly1_part() { weekly_small 1; }
weekly2_part() {
  weekly_small 2 --mutmut-only || return 1
  local res
  res="$(sed -n 's/^결과: \(.*\)\/summary.md$/\1/p' "$SPOT/weekly2.log" | tail -1)"
  sed -n 2,3p "$res/summary.md" | grep -q '^새 생존: 0 (지난 회 ' && sed -n 3p "$res/summary.md" | grep -q '^사라진 생존: 0 (지난 회 '
}
# 이 워크트리의 프로젝트: 빌드 잠금으로 짓고, 짧은 값으로 띄우고, 통합 한 번(빨간 시험은 그것만 둘 더까지) · P7 · 고르기 · 내림
# 짧은 값과 공개키는 containers_mode 가 run 밖(이 셸)에서 내보낸다 — run 은 부분마다 서브셸이라 안에서 내보내면
# 다음 부분(통합·P7)에 안 넘어간다(첫 덩어리에서 겪음: compose 는 2, pytest 는 10 으로 읽어 세션 시작 단언이 막았다).
self_up_part() {
  echo "  환경: CELERY_WAIT_TIME_SECONDS=${CELERY_WAIT_TIME_SECONDS:-<없음>} JOB_RETRY_DELAY_SECONDS=${JOB_RETRY_DELAY_SECONDS:-<없음>} EDK_JWT_PUBLIC_KEY $([ -n "${EDK_JWT_PUBLIC_KEY:-}" ] && echo 있음 || echo ★없음)"
  [ "${CELERY_WAIT_TIME_SECONDS:-}" = 2 ] && [ -n "${EDK_JWT_PUBLIC_KEY:-}" ] || return 1
  local started=$SECONDS
  scripts/with-build-lock.sh docker compose build > "$T/self-build.log" 2>&1 || { tail -20 "$T/self-build.log"; return 1; }
  echo "  with-build-lock … build → 0 ($((SECONDS - started))초) · $(grep '빌드 잠금' "$T/self-build.log" | head -1)"
  started=$SECONDS
  docker compose up -d --wait > "$T/self-up.log" 2>&1 || { tail -20 "$T/self-up.log"; return 1; }
  echo "  up -d --wait → 0 ($((SECONDS - started))초) · 1분 부하 $(load1) · free $(free_pct)%"
}
self_integration_part() {
  local f="$T/self-integ.log" code failed n
  apps/api-py/scripts/test-integration.sh > "$f" 2>&1
  code=$?
  echo "  1회: $(grep -E '[0-9]+ (passed|failed)' "$f" | tail -1) · 종료 $code"
  [ "$code" -eq 0 ] && return 0
  failed="$(grep -E '^(FAILED|ERROR) ' "$f" | sed -e 's/^[A-Z]* //' -e 's/ - .*//' | sort -u | tr '\n' ' ')"
  [ -n "${failed// /}" ] || { echo "  ★ 다시 돌릴 시험 이름을 뽑지 못했다 — 다시 돌리지 않는다"; return 1; }
  for n in 2 3; do
    # shellcheck disable=SC2086
    (cd apps/api-py && uv run --frozen pytest -q -p no:cacheprovider -c tests_integration/pytest.ini $failed) > "$T/self-integ.$n.log" 2>&1
    code=$?
    echo "  ${n}회(빨간 것만: $failed): $(grep -E '[0-9]+ (passed|failed)' "$T/self-integ.$n.log" | tail -1) · 종료 $code"
    [ "$code" -eq 0 ] || { echo "  ★ 같은 빨강이 두 번 — 멈춤(고치지 않는다)"; return 1; }
  done
  echo "  ★ 1회의 빨강은 흔들림으로 보임(다시 돌린 둘은 초록) — 보고"
  return 1
}
planted_containers_part() { apps/api-py/scripts/planted-breaks-T2.sh --containers; }
image_pick_part() {
  # README :265 의 새 지우기의 앞 절반(고르기)만. 지우지 않는다(처분 ⑥)
  local picked
  picked="$(docker image ls --filter "reference=$SELF_PROJECT/*" --format '{{.Repository}}:{{.Tag}}' | sort | tr '\n' ' ')"
  echo "  docker image ls -q --filter 'reference=$SELF_PROJECT/*' → $(docker image ls -q --filter "reference=$SELF_PROJECT/*" | wc -l | tr -d ' ')개: $picked"
  echo "  (견줌) reference=esg-app/* → $(docker image ls --filter 'reference=esg-app/*' --format '{{.Repository}}' | sort -u | tr '\n' ' ')"
  case " $picked" in *" $SELF_PROJECT/api-py:local "*) ;; *) return 1 ;; esac
  case " $picked" in *" $SELF_PROJECT/parser:local "*) ;; *) return 1 ;; esac
  ! printf '%s' "$picked" | tr ' ' '\n' | grep -v '^$' | grep -v "^$SELF_PROJECT/" | grep -q .
}
down_part() {
  docker compose down -v --remove-orphans > "$T/self-down.log" 2>&1
  local code=$? p c v
  echo "  down -v --remove-orphans → $code"
  for p in "$SELF_PROJECT" "$WEEKLY_PROJECT"; do
    c="$(docker ps -a -q --filter "label=com.docker.compose.project=$p" | wc -l | tr -d ' ')"
    v="$(docker volume ls -q --filter "label=com.docker.compose.project=$p" | wc -l | tr -d ' ')"
    echo "  $p: 컨테이너 $c · 볼륨 $v"
    [ "$c" -eq 0 ] && [ "$v" -eq 0 ] || code=1
  done
  echo "  weekly 일터(~/.cache/esg-weekly): $(ls -1 "$HOME/.cache/esg-weekly" 2>/dev/null | tr '\n' ' ')"
  [ "$code" -eq 0 ]
}
containers_mode() {
  run door_part
  [ "$FAILS" -eq 0 ] || { echo "문이 안 열렸다 — 띄우지 않는다"; return; }
  export CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1   # verify.sh 의 짧은 값과 같다(weekly 는 제 안에서 지운다)
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  if [ "${SELF_ONLY:-0}" -eq 0 ]; then
    run weekly1_part
    run weekly2_part
  fi
  run self_up_part
  if [ "$FAILS" -eq 0 ] || docker compose ps -q api-py 2>/dev/null | grep -q .; then
    run self_integration_part
    run planted_containers_part
    run image_pick_part
  fi
  run down_part
}

planted_pure_part() {
  apps/api-py/scripts/planted-breaks-T2.sh --pure > "$T/planted.log" 2>&1
  local code=$?
  grep '^#\|^PLANTED=\|★' "$T/planted.log"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$T/planted.log")" = "PLANTED=6/6" ]
}
status_zero_part() { echo "  git status --porcelain: $(git status --porcelain | wc -l | tr -d ' ')줄"; [ -z "$(git status --porcelain)" ]; }

case "$MODE" in
  --containers)
    containers_mode
    run zero_part
    ;;
  --after-commit)
    run plan_part
    run gates_part
    run fast_part
    run allowed_part
    run status_zero_part
    ;;
  *)
    run plan_part
    run gates_part
    run fast_part
    run wrap_part
    [ "$STEP" -ge 2 ] && run issue90_part
    if [ "$STEP" -ge 3 ]; then
      run selftest_part
      run weekly_plan_part
      run weekly_fake_part
    fi
    [ "$MODE" = --pure ] && run planted_pure_part
    run allowed_part
    run zero_part
    ;;
esac

echo
echo "── 끝 · 1분 부하 $(load1) · free $(free_pct)% · compose ls -q: $(projects)"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" -eq 0 ]
