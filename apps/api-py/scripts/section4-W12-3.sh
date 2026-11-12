#!/usr/bin/env bash
# 밴드 W12-3(MARC-TICK-488: Scope 1·2 계수 바꿈 S9·S11 · 직접입력 단위 검사 sid:MARC-ISSUE-548)의 서버 몫 §4 자기검증
# (발주서 band-handoffs/W12-3-order.md §1-1·§4 + 감독 처분 B2). 틀은 section4-S12a-2.sh — 이 밴드는 서버 경계가 ① 하나라
#   새 경로·스키마·권한·generated 0 을 재는 단계만 남겼다.
#   사용: apps/api-py/scripts/section4-W12-3.sh --commit 1 [--step <n>]
#   DB 단계(7·9)는 이 워크트리의 compose postgres(esg-app-w12-3)를 쓴다. .git/verify.lock 이 있으면 시험 단계 앞에서
#   없어질 때까지 기다린다(runner-common §5 — 순수 시험·심은 고장 포함).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 W12-3.out/s4).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다.
set -euo pipefail
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
C="$E/core"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../W12-3.out/s4}"
PURE_PATHS="esgapi/inventory esgapi/organization esgapi/core esgapi/config"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C
NOKEY="env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY"

COMMIT=""; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit 1 [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1) ;; *) echo "--commit 1 이 필요하다(서버 경계는 ① 하나)" >&2; exit 2 ;; esac
LOCK="$(git rev-parse --git-common-dir)/verify.lock"
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 W12-3 §4(서버) · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start code; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  code=0
  "$@" || code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

wait_lock() {  # .git/verify.lock 이 있는 동안 기다린다(전량 verify 와 겹치지 않게)
  local waited=0
  while [ -e "$LOCK" ]; do
    [ "$waited" = 0 ] && echo "  verify.lock 있음 — 기다림"
    sleep 20
    waited=$((waited + 20))
  done
  echo "  lock 없음 확인 $(date '+%H:%M:%S')${waited:+ (기다림 ${waited}s)}"
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u | grep . || true
}

# §1-2 ① 의 닫힌 목록(웹 경계 ②③ 은 apps/web 의 몫 — 이 스크립트는 서버만 본다).
ALLOWED="^$I/service/(actions|utils)/entries\.py\$
^$I/tests/service/(actions|apis)/test_entries\.py\$
^$A/scripts/(section4|planted-breaks)-W12-3\.sh\$
^apps/web/(src/entities/ghg/(api|model|config)/|src/pages/ghg-inventory/ui/|src/app/ghg/GhgRoutes\.tsx\$|e2e/ghg-server(\.spec)?\.ts\$)"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c . || true)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c . || true) · 목록 밖 $outside"
  [ "$outside" -eq 0 ]
}

# §1-3 0줄(서버 몫).
ZERO="$A/generated $I/service/schemas $I/service/apis $C $I/calc $I/models.py $I/migrations $I/README.md
$C/tests $E/config/tests $S $I/tests/test_route_shapes.py
$I/service/actions/ghg_pool.py $I/service/actions/dashboard.py $I/service/utils/ghg_pool.py
$A/pyproject.toml $A/uv.lock $A/.importlinter"
s2() {
  local bad missing=0 p n
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c . || true)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u | grep . || true)"
  # scope3_* 는 이름 꼴로
  bad="$bad$( { git diff --name-only "$BASE" -- "$I/service"; } | grep -E '/scope3_' || true)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c . || true)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

# 감독 처분 B2: 공통 셈 줄 = core·config·tests/security·test_route_shapes 의 「== n」·셈 꼴 줄 0.
s3() {
  local n
  n="$(git diff "$BASE" -- "$C" "$E/config" "$S" "$I/tests/test_route_shapes.py" \
    | grep -cE '^[-+].*==? *\(?[0-9]+|^[-+] +[0-9]+ +#' || true)"
  echo "  공통 셈 줄 $n"
  [ "$n" = 0 ]
}

s4() {
  local log kept broken
  log="$(cd "$A" && $NOKEY uv run --frozen lint-imports 2>&1 || true)"
  echo "$log" | tail -2 | sed 's/^/  /'
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?}"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ]
}

s5() {
  local code=0
  (cd "$A" && uv run --frozen ruff check . 2>&1 | tail -1 | sed 's/^/  ruff check /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check . 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen pyright 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  return $code
}

s6() {
  local log code
  wait_lock
  code=0
  # shellcheck disable=SC2086
  log="$(cd "$A" && $NOKEY uv run --frozen pytest $PURE_PATHS -m "not django_db and not security" -q -p no:cacheprovider 2>&1)" || code=$?
  echo "$log" > "$OUT/s6-pure.log"
  echo "  순수($PURE_PATHS) $(echo "$log" | tail -1) EXIT=$code"
  [ "$code" = 0 ]
}

up_postgres() {
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$' || true)" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/up.log" 2>&1 || { tail -3 "$OUT/up.log"; return 1; }
  fi
}

s7() {
  local code=0 blog="$OUT/s7-business.log"
  up_postgres || return 1
  wait_lock
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && $NOKEY scripts/test-business.sh -p no:cacheprovider esgapi/inventory) > "$blog" 2>&1 || code=1
  echo "  업무 층 inventory $(tail -1 "$blog")"
  return $code
}

# generated 를 다시 뽑아 커밋본(=<기준>)과 cmp — 바뀜 0 증명.
s8() {
  local g="$OUT/s8-generated" code=0 f
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && $NOKEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ generated 가 <기준> 과 다름"; code=1; }
  return $code
}

s9() {
  local log code
  up_postgres || return 1
  wait_lock
  code=0
  log="$($NOKEY "$A/scripts/planted-breaks-W12-3.sh" --commit "$COMMIT" 2>&1)" || code=$?
  echo "$log" > "$OUT/s9-planted.log"
  echo "$log" | sed 's/^/  /'
  [ "$code" = 0 ] && echo "$log" | grep -q "^FINGERPRINT=same" \
    && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\).*$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s10() {
  local log code=0
  wait_lock
  log="$($NOKEY scripts/verify.sh --fast 2>&1 || true)"
  echo "$log" > "$OUT/s10-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS" || code=1
  return $code
}

step 1 "바뀐 경로가 §1-2 안(outside=0)" s1
step 2 "§1-3 0줄(generated·schemas·apis·core·calc·models·migrations·공통 시험)" s2
step 3 "공통 셈 줄 0(감독 처분 B2)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "ruff·pyright·check_test_layout" s5
step 6 "순수 시험(inventory·organization·core·config)" s6
step 7 "makemigrations --check · 업무 층 inventory(DB)" s7
step 8 "generated 다시 뽑아 cmp(바뀜 0)" s8
step 9 "심은 고장(①)" s9
step 10 "뿌리 verify.sh --fast" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
