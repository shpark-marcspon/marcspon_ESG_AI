#!/usr/bin/env bash
# 밴드 G2c3(MARC-TICK-202: 그린워싱 AI 설정 판 뒷손질 — 목록·잠금이 기준표를 안 읽음·목록 한 문, 못 받는 저장 판의 실행
# 만들기·적용 409, 시험 보강)의 §4 자기검증(발주서 band-handoffs/G2c3-order.md §4). 틀은 section4-G2c2.sh 그대로다.
#   사용: apps/api-py/scripts/section4-G2c3.sh --commit <1|2> [--with-containers] [--step <n>]
#   --commit n 은 커밋 n 경계(그 커밋까지의 시험·심은 파손). --with-containers 면 단계 12(업무·보안·통합)와 13 의
#   컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(MARC-ENT-241·292): 자기 밖 esg-app*
#   프로젝트 ≤ 2, build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. build 는 scripts/with-build-lock.sh 로만.
#   띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G2c3.out — 심은 파손에도 G2C3_OUT 으로 넘긴다), G2C3_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${S4_OUT:-$ROOT/../G2c3.out}"
FORBIDDEN="${G2C3_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>에서 잰 수. 순수 = pytest -q esgapi/greenwash -m "not django_db", 업무 = test-business.sh
# esgapi/{greenwash,runs,config,core}, 보안 = test-security.sh 전부.
# ① 의 <기준> 6409695(① 의 트리에서 잰 수 − ① 이 더한 시험): 755·446·264.
# ② 의 <기준> 78d779e(main 따라잡기 병합 46e8112 — X1b-2b·S3C-b0 위): 그 트리를 git archive 로 풀어 --collect-only 로 잼
#   755·483·266.
# 커밋마다 기대 수. ① 순수 +2(dry-run 토큰 ≠ 글자 둘) · 업무 +9(selectors/test_ai_settings 7 · apis 적용 경로 SQL 1 ·
# settings_runs [foreign] 1) · 보안 +0.
# ② = ① + 순수 +2(binding_e0_settings 의 versions_with·inputs_with 좁힘) · 업무 +4(settings_runs 409·워커 versions_mismatch
# 둘 · apis 적용 409 하나 · runs test_runs_versions 하나) · 보안 +0.
expect_pure() { case "$COMMIT" in 1) echo 757 ;; *) echo 759 ;; esac; }
expect_business() { case "$COMMIT" in 1) echo 455 ;; *) echo 496 ;; esac; }
expect_security() { case "$COMMIT" in 1) echo 264 ;; *) echo 266 ;; esac; }
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac
case "$COMMIT" in 1) BASE_PURE=755 BASE_BUSINESS=446 BASE_SECURITY=264 ;; *) BASE_PURE=755 BASE_BUSINESS=483 BASE_SECURITY=266 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 G2c3 §4 · 커밋 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…> — EXIT 줄에 걸린 초(검증 1 권고 R1)
  local n="$1" what="$2" start; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

env_value() { sed -n "s/^$1=//p" .env | tail -1; }

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2(그린워싱) + §1-3(공유 파일) — 닫힌 목록
ALLOWED="^$G/service/(selectors|services|actions|apis)/ai_settings\.py\$
^$G/flows/binding_e0\.py\$
^$G/README\.md\$
^$G/tests/.*
^$A/scripts/(section4|planted-breaks)-G2c3\.sh\$
^$E/core/flows/binding\.py\$
^$E/runs/service/actions/runs\.py\$
^$E/runs/service/apis/runs\.py\$
^$E/runs/tests/service/apis/test_runs_versions\.py\$
^$E/runs/calc/errors\.py\$"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# §1-3 「0줄」 + §1-4 0바이트
ZERO="$A/generated apps/web $E/config $E/core/tests $A/tests $E/runs/tasks.py $E/runs/tests/test_executor.py
$E/runs/tests/test_binding.py $E/runs/tests/service/apis/test_runs.py $E/runs/models.py $A/.importlinter
$A/scripts/test-layout-allow.txt $A/uv.lock $G/engines $G/prompts $G/tests/data/golden $G/tests/data/gw1-ast-sha256.txt
$G/migrations $G/contracts $G/flows/colab_e0.py $G/flows/criteria_e0.py $G/service/selectors/review.py
$G/service/services/review.py $G/service/actions/review.py $G/service/actions/checks.py $G/service/apis/greenwash.py"

s2() {
  local missing=0 p n bad
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

numstat() {  # <파일> → "더함 지움"(바뀌지 않았으면 0 0)
  local got
  got="$(git diff --numstat "$BASE" -- "$1" | awk '{print $1, $2}')"
  echo "${got:-0 0}"
}

s3() {
  local bad=0 add del want
  # 파일 · 지움 한도(§1-3: binding.py 0 · errors.py 0 · runs 둘은 머리말 줄 + 원래 문 하나 — 커밋 ① 은 전부 0).
  # actions/runs.py 13 = 머리말 한 줄 + versions 짓기 문 12줄(따라잡기 뒤 꼴 — 이어 돌기 갈래를 if 로 갈라 except 를 새
  # 갈래에만 건다). apis/runs.py 1 = 머리말 한 줄.
  for want in "$E/core/flows/binding.py 0 0" "$E/runs/calc/errors.py 0 0" \
    "$E/runs/service/actions/runs.py 0 13" "$E/runs/service/apis/runs.py 0 1" \
    "$E/runs/tests/service/apis/test_runs_versions.py 0 0"; do
    set -- $want
    read -r add del <<< "$(numstat "$1")"
    local limit="$2"
    [ "$COMMIT" = 2 ] && limit="$3"
    echo "  $1 더함 $add 지움 $del(지움 한도 $limit)"
    [ "$del" -le "$limit" ] || bad=$((bad + 1))
    [ "$COMMIT" = 1 ] && [ "$add" != 0 ] && { echo "  ★ 커밋 1 은 공유 파일 0줄"; bad=$((bad + 1)); }
    [ "$del" = 0 ] || git diff -U0 "$BASE" -- "$1" | grep -E '^-' | grep -v -E '^--- ' | sed 's/^/      /'
  done
  [ "$bad" = 0 ]
}

s4() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

s5() {
  local log="$OUT/s5-pytest.log" code total want
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash \
    -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  want="$(expect_pure)"
  tail -1 "$log" | sed 's/^/  /'
  echo "  기준 $BASE_PURE → 지금 ${total:-?}(커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${total:-0}" -ge "$BASE_PURE" ] && { [ "$want" = 0 ] || [ "${total:-0}" -eq "$want" ]; }
}

s5b() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/greenwash/tests/test_copy_ast.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s6() {
  local p bad=0 n=0 a b
  for p in $(git ls-tree -r --name-only "$BASE" -- "$G/tests/data/golden"); do
    a="$(git show "$BASE:$p" | shasum -a 256 | cut -d' ' -f1)"
    b="$(shasum -a 256 "$p" | cut -d' ' -f1)"
    n=$((n + 1))
    [ "$a" = "$b" ] || { echo "  ★ $p"; bad=$((bad + 1)); }
  done
  echo "  골든 $n 파일 · 다름 $bad"
  [ "$n" -gt 0 ] && [ "$bad" = 0 ]
}

s7() {  # 계약 0: 다시 뽑은 openapi 가 generated/ 와 바이트 같다
  local d="$OUT/s7-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json"
  code=$?
  echo "  openapi 다시 뽑음 cmp EXIT=$code · generated/ 바뀐 것 $(git diff --name-only "$BASE" -- "$A/generated" | grep -c .)"
  return "$code"
}

s8() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s9() {
  local n
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || return 1
  n="$(git diff --name-only "$BASE" -- "$A/scripts/test-layout-allow.txt" | grep -c .)"
  echo "  허용 목록 diff $n"
  [ "$n" = 0 ]
}

s10() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core/tests/isolation/test_static_rules.py esgapi/core/tests/test_selector_scope.py \
    esgapi/core/tests/test_transaction_rules.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s11() {
  local log="$OUT/s11-verify-fast.log"
  scripts/verify.sh --fast > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ]
}

gate() {  # 기계 문(머리말)
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d ' ')"
    building="$(ps -axo command | grep -E "^[^ ]*/?(docker|docker-compose)( .*)? (build|buildx)( |$)" | grep -v -c grep)"
    free="$(memory_pressure 2> /dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(sysctl -n vm.loadavg | awk '{print $2}')"
    if [ "$others" -le 2 ] && [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 자기 밖 esg-app* $others · build 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다림 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열림: 자기 밖 $others · build 중 $building · free ${free:-?}% · 부하 ${load:-?})"; return 1; }
    tries=$((tries + 1))
    sleep 60
  done
}

s12_business() {
  local log="$OUT/s12-business.log" code n want
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s12-up-postgres.log" 2>&1 || { tail -3 "$OUT/s12-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/greenwash \
    esgapi/runs esgapi/config esgapi/core) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  want="$(expect_business)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -gt "$BASE_BUSINESS" ] && { [ "$want" = 0 ] || [ "${n:-0}" -eq "$want" ]; }
}

s12_security() {
  local log="$OUT/s12-security.log" code n want
  gate || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  want="$(expect_security)"
  echo "  보안 층 수 ${n:-?}(기준 $BASE_SECURITY — 줄지 않음 · 커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -ge "$BASE_SECURITY" ] && { [ "$want" = 0 ] || [ "${n:-0}" -eq "$want" ]; }
}

s12_integration() {
  local log="$OUT/s12-integration.log" code start key
  gate || return 1
  key="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || return 1
  export EDK_JWT_PUBLIC_KEY="$key" CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
  scripts/with-build-lock.sh docker compose build > "$OUT/s12-build.log" 2>&1 || { tail -3 "$OUT/s12-build.log"; return 1; }
  docker compose up -d --wait > "$OUT/s12-up.log" 2>&1 || { tail -3 "$OUT/s12-up.log"; return 1; }
  start=$(date +%s)
  (cd "$A" && scripts/test-integration.sh -p no:cacheprovider -rA tests_integration/test_run_flow.py) > "$log" 2>&1
  code=$?
  grep -E "^(PASSED|FAILED)" "$log" | sed 's/^/  /'
  tail -1 "$log" | sed 's/^/  /'
  echo "  통합 test_run_flow $(( $(date +%s) - start ))초"
  return "$code"
}

s13() {
  local log="$OUT/s13-planted.log" flag="" want=7
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  [ "$COMMIT" = 2 ] && want=14
  # shellcheck disable=SC2086
  G2C3_OUT="$OUT" "$A/scripts/planted-breaks-G2c3.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=$want/$want" ]; }
}

s14() {
  local all keys bin lab words body msg
  all="$(changed)"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2c3\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  lab="$(echo "$body" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2c3\.sh:" | grep -c -E 'esg-lab|py/greenwash')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · esg-lab 언급(더한 줄) $lab · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$lab" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2 + §1-3 안" s1
step 2 "0줄·0바이트 목록 diff 0(§1-3·§1-4)" s2
step 3 "§1-3 공유 파일 numstat·- 줄 원문" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash(순수) 초록, 수" s5
step 5 "test_copy_ast(엔진 AST 그대로)" s5b
step 6 "골든 sha256 = <기준>" s6
step 7 "generated/ 다시 뽑아 cmp 차이 0" s7
step 8 "makemigrations --check(모든 앱)" s8
step 9 "테스트 자리 검사·허용 목록 diff 0" s9
step 10 "격리 정적 규칙·selector 범위·트랜잭션 규칙" s10
step 11 "verify.sh --fast" s11
if [ "$CONTAINERS" = 1 ]; then
  step 12 "업무 층 greenwash·runs·config·core" s12_business
  step 12 "보안 층 tests/security" s12_security
  step 12 "통합 tests_integration/test_run_flow.py" s12_integration
else
  not_run 12 "컨테이너 층(업무·보안·통합)" "--with-containers 없음"
fi
step 13 "심은 파손" s13
step 14 "키 꼴·바이너리·esg-lab·실재 기업명 0" s14
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
