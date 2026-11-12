#!/usr/bin/env bash
# 밴드 G1e(MARC-TICK-199: 목록 줄 greenwash.checks@1 의 errorCode)의 §4 자기검증(발주서 band-handoffs/G1e-order.md §4).
# 꼴은 section4-G1b.sh(G1b 의 기록 — 고치지 않는다)를 따르고 단계를 줄였다.
#   사용: apps/api-py/scripts/section4-G1e.sh [--with-containers] [--step <n>]
#   --with-containers 면 단계 11(업무·보안·통합)과 12 의 컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(MARC-ENT-241·292): 자기 밖 esg-app*
#   프로젝트 ≤ 2, build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. build 는 scripts/with-build-lock.sh 로만.
#   띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G1e.out — 심은 파손에도 G1E_OUT 으로 넘긴다), G1E_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${S4_OUT:-$ROOT/../G1e.out}"
FORBIDDEN="${G1E_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
BASE_TESTS=683   # <기준>(2d2e8e0·1969cc6 같음)에서 잰 pytest -q esgapi/greenwash -m "not django_db" 의 수
NEW_TESTS=3      # test_checks_shapes 의 거절 갈래 셋(error-code-missing·number·bool)
BASE_SECURITY=241  # <기준>(1969cc6 — X1b-2a 병합 뒤. 2d2e8e0 은 231)에서 잰 tests/security 수집 수(+1 = 새 시험 하나)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 G1e §4 · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2"; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code"
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

# §1-2 — 닫힌 목록
ALLOWED="^$G/contracts/checks_shapes\.py\$
^$G/service/actions/checks\.py\$
^$G/tests/data/flow-shapes/checks/greenwash\.checks@1\.schema\.json\$
^$G/tests/data/contract-examples/checks/checks-normal\.json\$
^$G/tests/contracts/test_checks_shapes\.py\$
^$G/tests/service/apis/test_greenwash_checks\.py\$
^$G/tests/service/seed\.py\$
^$G/tests/flows/test_binding_e0_runs\.py\$
^$G/README\.md\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/tests_integration/test_run_flow\.py\$
^$A/tests/security/test_greenwash\.py\$
^$A/scripts/section4-G1e\.sh\$
^$A/scripts/planted-breaks-G1e\.sh\$"

s1() {
  local all outside re
  all="$(changed)"
  re="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$re" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$re" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# §1-3 0줄
ZERO="$A/scripts/section4-G1b.sh $A/scripts/planted-breaks-G1b.sh $G/tests/data/contract-examples/checks/checks-empty.json
$G/contracts/shapes.py $G/contracts/review_shapes.py $G/contracts/compare_shapes.py $G/contracts/criteria_shapes.py
$G/contracts/terms_shapes.py $G/contracts/options_shapes.py $G/tests/data/flow-shapes/greenwash.result@1.schema.json
$G/tests/data/flow-shapes/review $G/tests/data/flow-shapes/compare $G/tests/data/flow-shapes/criteria
$G/tests/data/flow-shapes/terms $G/tests/data/golden $G/engines $G/prompts $G/flows
$E/core $E/config $E/runs $E/user $A/.importlinter $A/pyproject.toml $A/uv.lock apps/web compose.yaml docker infra"

s2() {
  local missing=0 p n bad sec
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  sec="$(changed | grep "^$A/tests/security/" | grep -v -c -x "$A/tests/security/test_greenwash.py")"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .) · 남의 보안 파일 $sec"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ] && [ "$sec" -eq 0 ]
}

numstat() {  # <파일> → "더함 지움"(바뀌지 않았으면 0 0)
  local got
  got="$(git diff --numstat "$BASE" -- "$1" | awk '{print $1, $2}')"
  echo "${got:-0 0}"
}

s3() {
  local bad=0 f add del
  for f in "$G/contracts/checks_shapes.py" "$G/service/actions/checks.py"; do
    read -r add del <<< "$(numstat "$f")"
    echo "  $f 더함 $add 지움 $del(한도 6/1)"
    { [ "$add" -le 6 ] && [ "$del" -le 1 ]; } || bad=$((bad + 1))
  done
  for f in "$G/tests/service/seed.py" "$G/tests/flows/test_binding_e0_runs.py" "$A/tests/security/test_greenwash.py" \
    "$A/tests_integration/test_run_flow.py"; do
    read -r add del <<< "$(numstat "$f")"
    echo "  $f 더함 $add 지움 $del(지움 0)"
    [ "$del" = 0 ] || bad=$((bad + 1))
  done
  [ "$bad" = 0 ]
}

s4() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

s5() {
  local log="$OUT/s5-pytest.log" code total
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash \
    -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  tail -1 "$log" | sed 's/^/  /'
  echo "  기준 $BASE_TESTS + 새 $NEW_TESTS = $((BASE_TESTS + NEW_TESTS)) · 지금 ${total:-?}"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq $((BASE_TESTS + NEW_TESTS)) ]
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

s7() {
  local d="$OUT/s7-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  [ "$(shasum -a 256 "$A/generated/openapi.json" | cut -d' ' -f1)" = "$(cat "$A/generated/api.d.ts.source-sha256")" ] \
    || { echo "  ★ api.d.ts.source-sha256 이 openapi.json 과 다름"; return 1; }
  python3 - "$BASE" "$A/generated/openapi.json" "$A/generated/api.d.ts" <<'PY'
import json, subprocess, sys
base, path, dts = sys.argv[1], sys.argv[2], sys.argv[3]
def show(p):
    return subprocess.run(["git", "show", f"{base}:{p}"], capture_output=True, text=True, check=True).stdout
old, new = json.loads(show(path)), json.loads(open(path, encoding="utf-8").read())
bad = []
paths = sorted(p for p in set(old["paths"]) | set(new["paths"]) if old["paths"].get(p) != new["paths"].get(p))
os_, ns = old["components"]["schemas"], new["components"]["schemas"]
schemas = sorted(s for s in set(os_) | set(ns) if os_.get(s) != ns.get(s))
print(f"  바뀐 경로 {paths} · 바뀐 구성요소 {schemas}")
if paths or schemas != ["GreenwashCheckRun"]:
    bad.append("경로·구성요소")
else:
    o, n = os_["GreenwashCheckRun"], ns["GreenwashCheckRun"]
    if set(n["properties"]) - set(o["properties"]) != {"errorCode"} or set(o["properties"]) - set(n["properties"]):
        bad.append("칸")
    if {k: v for k, v in n["properties"].items() if k != "errorCode"} != o["properties"]:
        bad.append("다른 칸")
    if [r for r in n["required"] if r != "errorCode"] != o["required"]:
        bad.append("required")
    if {k: v for k, v in n.items() if k not in ("properties", "required")} != {
        k: v for k, v in o.items() if k not in ("properties", "required")}:
        bad.append("그 밖 열쇠")
    if {k: v for k, v in new.items() if k not in ("paths", "components")} != {
        k: v for k, v in old.items() if k not in ("paths", "components")} or {
        k: v for k, v in new["components"].items() if k != "schemas"} != {
        k: v for k, v in old["components"].items() if k != "schemas"}:
        bad.append("문서 머리")
diff = subprocess.run(["git", "diff", "-U0", base, "--", dts], capture_output=True, text=True, check=True).stdout
plus = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
minus = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
fields = [l for l in plus if l.strip().startswith("+") and ":" in l and not l.lstrip("+ ").startswith("*")]
print(f"  api.d.ts +{len(plus)} -{len(minus)} · 더한 칸 {[l.strip(' +') for l in fields]}")
if minus or [l.strip(" +") for l in fields] != ["errorCode: string | null;"]:
    bad.append("api.d.ts")
print(f"  §2-3 밖: {bad}")
sys.exit(1 if bad else 0)
PY
}

s8() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s9() {
  local log="$OUT/s9-verify-fast.log" start
  start=$(date +%s)
  scripts/verify.sh --fast > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  echo "  verify --fast EXIT=$code $(( $(date +%s) - start ))초"
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ]
}

s10() {
  local all keys bin words body msg
  all="$(changed)"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G1e\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$words" = 0 ]
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
  local log="$OUT/s11-business.log" code
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s11-up-postgres.log" 2>&1 || { tail -3 "$OUT/s11-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/greenwash \
    esgapi/runs esgapi/config) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  return "$code"
}

s11_security() {
  local log="$OUT/s11-security.log" code got
  gate || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  got="$(sed -n -E 's/^([0-9]+) passed.*/\1/p; s/^.* ([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  보안 층 통과 ${got:-?}(기준 $BASE_SECURITY + 새 1 = $((BASE_SECURITY + 1)))"
  [ "$code" -eq 0 ] && [ "${got:-0}" -eq $((BASE_SECURITY + 1)) ]
}

s11_integration() {
  local log="$OUT/s11-integration.log" code start key
  gate || return 1
  key="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || return 1
  export EDK_JWT_PUBLIC_KEY="$key" CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
  scripts/with-build-lock.sh docker compose build > "$OUT/s11-build.log" 2>&1 || { tail -3 "$OUT/s11-build.log"; return 1; }
  docker compose up -d --wait > "$OUT/s11-up.log" 2>&1 || { tail -3 "$OUT/s11-up.log"; return 1; }
  start=$(date +%s)
  (cd "$A" && scripts/test-integration.sh -p no:cacheprovider -rA tests_integration/test_run_flow.py) > "$log" 2>&1
  code=$?
  grep -E "^(PASSED|FAILED)" "$log" | sed 's/^/  /'
  tail -1 "$log" | sed 's/^/  /'
  echo "  통합 test_run_flow $(( $(date +%s) - start ))초"
  return "$code"
}

s12() {
  local log="$OUT/s12-planted.log" flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  G1E_OUT="$OUT" "$A/scripts/planted-breaks-G1e.sh" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무·보안 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=5/5" ]; }
}

step 1 "바뀐 파일이 §1-2 안" s1
step 2 "0줄 목록 diff 0(§1-3)" s2
step 3 "줄 범위(numstat)" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash(순수) 초록, 수 = 기준 + 새" s5
step 6 "골든 sha256 = <기준>" s6
step 7 "generated/ 다시 뽑아 cmp + 차이가 §2-3 안(GreenwashCheckRun.errorCode 하나)" s7
step 8 "makemigrations --check(모든 앱)" s8
step 9 "verify.sh --fast" s9
step 10 "키 꼴·바이너리·실재 기업명 0" s10
if [ "$CONTAINERS" = 1 ]; then
  step 11 "업무 층 greenwash·runs·config" s11_business
  step 11 "보안 층 tests/security" s11_security
  step 11 "통합 tests_integration/test_run_flow.py" s11_integration
else
  not_run 11 "컨테이너 층(업무·보안·통합)" "--with-containers 없음"
fi
step 12 "심은 파손" s12
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
