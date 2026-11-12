#!/usr/bin/env bash
# 밴드 G1b-3(MARC-TICK-225: 그린워싱 검토 고침 — review@2(굳힘)·표시 표 칸 아홉·마이그레이션 0004·PUT/GET 규칙, 확정본 엑셀
# 고친 값·목록 효력 등급, GW-05 화면)의 §4 자기검증(발주서 band-handoffs/G1b-3-order.md §4). 틀은 section4-G1b-2a.sh 그대로다.
#   사용: apps/api-py/scripts/section4-G1b-3.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit n 은 커밋 n 경계(그 커밋까지의 시험·심은 파손). --with-containers 면 단계 11(업무·보안)과 12 의 컨테이너
#   층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 병합 뒤 테스트 감독). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(MARC-ENT-241·292): 자기 밖 esg-app*
#   프로젝트 ≤ 2, build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. postgres 만 띄운다(build 없음).
#   띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G1b-3.out — 심은 파손에도 G1B3_OUT 으로 넘긴다), G1B3_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만), WEB_PORT·WEB_TEST_PORT
#   (단계 14 의 apps/web verify — 기본 .env 의 WEB_PORT 와 그다음 수).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${S4_OUT:-$ROOT/../G1b-3.out}"
FORBIDDEN="${G1B3_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
W=apps/web
# <기준>(87e9739 — OP1 병합 뒤)에서 잰 수: 그 트리를 git archive 로 풀어 --collect-only 로 잼.
#   순수 = pytest esgapi/greenwash -m "not django_db" 800 · 업무 = -m django_db esgapi/greenwash esgapi/config
#   esgapi/core/tests/test_permissions_wiring.py 231 · 보안 = tests/security 전부 299.
# 커밋마다 기대 수. ① 순수 +22(test_review_edits_shapes) · 업무 +28(test_greenwash_review_edits 21·test_migrations_0004 7) ·
#   보안 +2(ⓚ 둘). 검증 1 B2 로 업무 +1(쓰기 회사 조건)·보안 +1 → ① 업무 +29·보안 +3.
#   ② 순수 +12(test_xlsx_edits 8·test_checks_levels 4) · 업무 +6(test_greenwash_review_edits_outputs) · 보안 0.
#   ③ 파이썬 시험 0(웹만 — 순수·업무·보안 ② 그대로). 심은 파손 +5(⑯~⑳ 웹 층 vitest, 컨테이너 없음) → 21.
expect_pure() { case "$COMMIT" in 1) echo 822 ;; 2) echo 834 ;; *) echo 834 ;; esac; }
expect_business() { case "$COMMIT" in 1) echo 260 ;; 2) echo 266 ;; *) echo 266 ;; esac; }
expect_security() { case "$COMMIT" in 1) echo 302 ;; 2) echo 302 ;; *) echo 302 ;; esac; }
BASE_PURE=800 BASE_BUSINESS=231 BASE_SECURITY=299
REMOVED_PURE=0
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 G1b-3 §4 · 커밋 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
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

# §1-2(그린워싱 서버) + §1-3(그린워싱 웹) + §1-4(공통 줄 + 허락 받은 config/tests 셈 줄 — 4f, MARC-TICK-225 노트) — 닫힌 목록
ALLOWED="^$G/contracts/(review_shapes|checks_shapes|compare_shapes|__init__)\.py\$
^$G/models\.py\$
^$G/migrations/0004_review_mark_edits\.py\$
^$G/service/selectors/review\.py\$
^$G/service/services/review\.py\$
^$G/service/actions/(review|checks|report)\.py\$
^$G/service/apis/greenwash\.py\$
^$G/outputs/xlsx\.py\$
^$G/__init__\.py\$
^$G/README\.md\$
^$G/tests/.*
^$A/scripts/(section4|planted-breaks)-G1b-3\.sh\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/tests/security/test_greenwash\.py\$
^$E/config/tests/test_request_schemas_reject_bool\.py\$
^$W/src/entities/greenwash/.*
^$W/src/pages/greenwash-review/.*
^$W/src/pages/greenwash-result/.*
^$W/src/pages/greenwash-list/.*\.test\.tsx?\$
^$W/e2e/(greenwash-server\.ts|greenwash-server\.spec\.ts|greenwash\.spec\.ts)\$"

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

# §1-5 0줄(바이트 그대로). config 는 허락 받은 셈 줄 파일 밖 전부.
ZERO="$G/engines $G/prompts $G/flows $G/tools $G/outputs/compare.py $G/contracts/shapes.py $G/contracts/terms_shapes.py
$G/contracts/criteria_shapes.py $G/contracts/options_shapes.py $G/contracts/ai_setting_shapes.py $G/contracts/wire.py
$G/migrations/0001_initial.py $G/migrations/0002_ai_settings.py $G/migrations/0003_ai_settings_model_settings.py $G/apps.py
$G/service/actions/ai_settings.py $G/tests/data/golden $G/tests/data/llm $G/tests/data/contract-examples/result-normal.json
$G/tests/data/contract-examples/result-many.json $G/tests/data/contract-examples/result-no-pages.json
$G/tests/data/contract-examples/result-dry-run.json $E/user $E/core $E/runs $E/organization $E/config $A/.importlinter
$A/tests_integration $W/src/shared $W/src/widgets $W/src/app $W/src/pages/greenwash-new $W/src/pages/greenwash-status
$W/src/entities/ai-setting $W/src/entities/audit-log $W/package.json"
WIRING=":(exclude)$E/config/tests/test_request_schemas_reject_bool.py"
RULES=":(exclude)$E/config/tests/test_request_schemas_reject_bool.py"

s2() {
  local missing=0 p n bad
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO "$WIRING" "$RULES"; git ls-files -o --exclude-standard --full-name -- $ZERO "$WIRING" "$RULES"; } | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  # compare_get(501 그대로)의 함수 글이 <기준> 과 같다
  git show "$BASE:$G/service/apis/greenwash.py" > "$OUT/s2-greenwash-base.py"
  (cd "$A" && uv run --frozen python - "$OUT/s2-greenwash-base.py" "esgapi/greenwash/service/apis/greenwash.py" <<'PY'
import ast
import sys


def source(path: str) -> str:
    text = open(path, encoding="utf-8").read()
    node = next(n for n in ast.parse(text).body if isinstance(n, ast.FunctionDef) and n.name == "compare_get")
    lines = text.splitlines()
    return "\n".join(lines[node.decorator_list[0].lineno - 1 : node.end_lineno])


same = source(sys.argv[1]) == source(sys.argv[2])
print(f"  compare_get 글 <기준> 과 {'같음' if same else '★ 다름'}")
sys.exit(0 if same else 1)
PY
  )
  local cmp=$?
  [ -z "$bad" ] && [ "$missing" -eq 0 ] && [ "$cmp" -eq 0 ]
}

numstat() {  # <파일> → "더함 지움"(바뀌지 않았으면 0 0)
  local got
  got="$(git diff --numstat "$BASE" -- "$1" | awk '{print $1, $2}')"
  echo "${got:-0 0}"
}

s3() {
  local bad=0 add del want
  # 파일 · 지움 한도: test_greenwash 0(더하기만) · reject_bool 2(셈 줄 둘 — 4f 허락). generated 는 [8] 이 잰다.
  for want in "$A/tests/security/test_greenwash.py 0" "$E/config/tests/test_request_schemas_reject_bool.py 2" \
    "$A/generated/openapi.json -" "$A/generated/api.d.ts -" "$A/generated/api.d.ts.source-sha256 -"; do
    set -- $want
    read -r add del <<< "$(numstat "$1")"
    echo "  $1 더함 $add 지움 $del(지움 한도 $2)"
    [ "$2" = "-" ] && continue
    [ "$del" -le "$2" ] || bad=$((bad + 1))
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
  echo "  기준 $BASE_PURE → 지금 ${total:-?}(커밋 $COMMIT 기대 $want = 기준 + 새 − 걷은 $REMOVED_PURE)"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq "$want" ]
}

s6() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/greenwash/tests/test_copy_ast.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s7() {
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

s8() {  # generated: 다시 뽑아 cmp + <기준> 과의 차이가 §1-4 허용 안
  local d="$OUT/s8-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  echo "  openapi 다시 뽑음 cmp 같음"
  [ "$(shasum -a 256 "$A/generated/openapi.json" | cut -d' ' -f1)" = "$(cat "$A/generated/api.d.ts.source-sha256")" ] \
    || { echo "  ★ api.d.ts.source-sha256 ≠ openapi.json"; return 1; }
  git show "$BASE:$A/generated/openapi.json" > "$d/openapi-base.json"
  git diff -U0 "$BASE" -- "$A/generated/api.d.ts" > "$d/api.d.ts.diff"
  (cd "$A" && uv run --frozen python - "$d/openapi-base.json" generated/openapi.json "$COMMIT" <<'PY'
import json
import sys

base, head = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
commit = int(sys.argv[3])
NEW = {"GreenwashReviewEdit", "GreenwashReviewEditIn", "GreenwashReviewEditedLevel", "GreenwashReviewEditedReasons",
       "GreenwashReviewEditedFix"}
# levelCounts 칸은 GreenwashCheckRun 에 있다(발주서 §1-4 「GreenwashChecks.levelCounts」 — 코드가 이김, 러너 2 보고)
CHANGED = {"GreenwashReviewState", "GreenwashReviewUpdate"} | ({"GreenwashCheckRun"} if commit >= 2 else set())
PATHS = {("/greenwash/runs/{run_id}/review", "get"), ("/greenwash/runs/{run_id}/review", "put")}
if commit >= 2:
    PATHS |= {("/greenwash/checks", "get")}
bc, hc = base["components"]["schemas"], head["components"]["schemas"]
bad = []
if set(hc) - set(bc) != NEW or set(bc) - set(hc):
    bad.append(f"구성요소 더함·뺌: {sorted(set(hc) - set(bc))} / {sorted(set(bc) - set(hc))}")
changed = {k for k in bc if k in hc and bc[k] != hc[k]}
if not changed <= CHANGED:
    bad.append(f"허용 밖 구성요소 바뀜: {sorted(changed - CHANGED)}")
if "GreenwashCheckRun" in changed:  # levelCounts 칸의 설명 글만
    b, h = json.loads(json.dumps(bc["GreenwashCheckRun"])), json.loads(json.dumps(hc["GreenwashCheckRun"]))
    b["properties"]["levelCounts"].pop("description", None)
    h["properties"]["levelCounts"].pop("description", None)
    if b != h:
        bad.append("GreenwashCheckRun 이 levelCounts 설명 밖으로 바뀜")
ops = {(p, m) for p in set(base["paths"]) | set(head["paths"]) for m in set(base["paths"].get(p, {})) | set(head["paths"].get(p, {}))
       if base["paths"].get(p, {}).get(m) != head["paths"].get(p, {}).get(m)}
if not ops <= PATHS:
    bad.append(f"허용 밖 경로 바뀜: {sorted(ops - PATHS)}")
for p, m in ops:  # 경로는 description 만
    b = dict(base["paths"][p][m]); h = dict(head["paths"][p][m])
    b.pop("description", None); h.pop("description", None)
    if b != h:
        bad.append(f"{m} {p} 가 description 밖으로 바뀜")
for k in ("GreenwashChecks", "GreenwashReviewMark", "GreenwashReviewer", "GreenwashResult", "ScanResult", "DryRunResult", "Item"):
    if k in bc and bc.get(k) != hc.get(k):
        bad.append(f"{k} 가 바뀜(0바이트여야)")
print(f"  openapi: 새 구성요소 {sorted(set(hc) - set(bc))} · 바뀐 구성요소 {sorted(changed)} · 바뀐 경로 {sorted(ops)}")
for line in bad:
    print(f"  ★ {line}")
sys.exit(0 if not bad else 1)
PY
  )
}

s9() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s9b() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s10() {
  local log="$OUT/s10-verify-fast.log"
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

s11_business() {
  local log="$OUT/s11-business.log" code n want
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s11-up-postgres.log" 2>&1 || { tail -3 "$OUT/s11-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/greenwash \
    esgapi/config esgapi/core/tests/test_permissions_wiring.py) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  want="$(expect_business)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -gt "$BASE_BUSINESS" ] && [ "${n:-0}" -eq "$want" ]
}

s11_security() {
  local log="$OUT/s11-security.log" code n want
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s11-up-postgres.log" 2>&1 || { tail -3 "$OUT/s11-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  want="$(expect_security)"
  echo "  보안 층 수 ${n:-?}(기준 $BASE_SECURITY — 줄지 않음 · 커밋 $COMMIT 기대 $want)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -ge "$BASE_SECURITY" ] && [ "${n:-0}" -eq "$want" ]
}

s12() {
  local log="$OUT/s12-planted.log" flag="" want=10  # ①~⑨ + ⑦b
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  [ "$COMMIT" = 2 ] && want=16
  [ "$COMMIT" = 3 ] && want=21
  # shellcheck disable=SC2086
  G1B3_OUT="$OUT" "$A/scripts/planted-breaks-G1b-3.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=$want/$want" ]; }
}

s14() {
  local log="$OUT/s14-web-verify.log" port
  port="${WEB_PORT:-$(env_value WEB_PORT)}"
  (cd "$W" && WEB_PORT="$port" WEB_TEST_PORT="${WEB_TEST_PORT:-$((port + 1))}" scripts/verify.sh) > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY=PASS" ]
}

s13() {  # bash 3.2: $( ) 안의 case 패턴은 여는 괄호를 붙인다(안 붙이면 ) 를 치환의 닫힘으로 읽어 몸이 빈다 — 검증 1 B1)
  local all keys bin words body msg lines
  all="$(changed)"
  body="$(for f in $all; do
    case "$f" in ("$A"/generated/*) continue ;; esac
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G1b-3\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  lines="$(printf '%s\n' "$body" | grep -c .)"
  echo "  더한 줄 $lines · 키 꼴 $keys · pdf/xlsx/ipynb 파일 더함 $bin · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$lines" -gt 0 ] || echo "  ★ 더한 줄이 0 — 몸을 못 읽음(빈 초록 막기)"
  [ "$lines" -gt 0 ] && [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2·§1-3·§1-4 안" s1
step 2 "0줄 목록 diff 0(§1-5)·compare_get 글 그대로" s2
step 3 "§1-4 공유 파일 numstat·- 줄 원문" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash(순수) 초록, 수 = 기준 + 새 − 걷은" s5
step 6 "test_copy_ast(엔진 AST 그대로)" s6
step 7 "골든 sha256 = <기준>" s7
step 8 "generated/ 다시 뽑아 cmp + 차이가 §1-4 허용 안" s8
step 9 "makemigrations --check(모든 앱)" s9
step 9 "테스트 자리 검사" s9b
step 10 "verify.sh --fast" s10
if [ "$CONTAINERS" = 1 ]; then
  step 11 "업무 층 greenwash·config·core/tests/test_permissions_wiring.py" s11_business
  step 11 "보안 층 tests/security" s11_security
else
  not_run 11 "컨테이너 층(업무·보안)" "--with-containers 없음"
fi
step 12 "심은 파손" s12
step 13 "키 꼴·xlsx/pdf 파일·실재 기업명 0" s13
step 14 "apps/web verify" s14
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
