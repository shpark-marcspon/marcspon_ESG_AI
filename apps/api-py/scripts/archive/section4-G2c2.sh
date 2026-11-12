#!/usr/bin/env bash
# 밴드 G2c2(MARC-TICK-198: 그린워싱 AI 설정 판 — 회사별 저장·조회·적용, 실행 판 고정, dry-run 판 보정)의 §4 자기검증
# (발주서 band-handoffs/G2c2-order.md §4, 개정 1). 틀은 section4-G1b.sh 그대로다.
#   사용: apps/api-py/scripts/section4-G2c2.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit n 은 커밋 n 경계(그 커밋까지의 시험·심은 파손). --with-containers 면 단계 10(업무·보안·통합)과 11 의
#   컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(MARC-ENT-241·292): 자기 밖 esg-app*
#   프로젝트 ≤ 2, build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. build 는 scripts/with-build-lock.sh 로만.
#   띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G2c2.out — 심은 파손에도 G2C2_OUT 으로 넘긴다), G2C2_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${S4_OUT:-$ROOT/../G2c2.out}"
FORBIDDEN="${G2C2_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(1969cc6)에서 잰 수. 순수 = pytest -q esgapi/greenwash -m "not django_db",
# 업무 = test-business.sh esgapi/{greenwash,runs,config,core}, 보안 = test-security.sh 전부.
# main ef3aa14 를 병합한 뒤(병합 커밋 d7114b6)의 <기준>은 ef3aa14 — 그 트리에서 잰 수(수집). 앞 기준 1969cc6 은 683·386·241.
BASE_PURE=686
BASE_BUSINESS=387
BASE_SECURITY=242
# 커밋마다 기대 수(검증 1 권고 r3 — 「늘기만」에 더해 정확히). ① 업무 +22(services/test_ai_settings)·보안 +1(test_owner 칸 권한),
# ② 업무 +24(apis/test_ai_settings 19 · test_permissions_wiring 매개 5)·보안 +21(test_ai_settings 16 · test_tenant_paths 401 매개 5)
# ③ 업무 +11(settings_runs 7 · test_executor 한 쌍 넷)·보안 +0(ProbeBinding 0줄 그대로)
# ④ 업무 +2(이름 경합 409 경로 시험 · 기본 판 sha 다름 실행 매개)
# 기대 수는 그 커밋을 1969cc6 위에서 잰 값(①~③), ④ 는 ef3aa14 병합 뒤: 업무 387 + 59 · 보안 242 + 22.
expect_business() { case "$COMMIT" in 1) echo 408 ;; 2) echo 432 ;; 3) echo 443 ;; *) echo 446 ;; esac; }
expect_security() { case "$COMMIT" in 1) echo 242 ;; 2) echo 263 ;; 3) echo 263 ;; *) echo 264 ;; esac; }
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3|4> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3 | 4) ;; *) echo "--commit <1|2|3|4> 이 필요하다" >&2; exit 2 ;; esac
# 4 = 가지 리뷰 뒤 고침 커밋 ④(③ 과 같은 단계·심은 파손, 기대 수만 다름)
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 G2c2 §4 · 커밋 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-2(그린워싱) + §1-3(공유 파일) — 닫힌 목록
ALLOWED="^$G/models\.py\$
^$G/migrations/0002_[a-z_]+\.py\$
^$G/contracts/(ai_setting_shapes|criteria_shapes|__init__)\.py\$
^$G/flows/(binding_e0|colab_e0|criteria_e0)\.py\$
^$G/apps\.py\$
^$G/service/(selectors|services|actions|apis)/ai_settings\.py\$
^$G/api\.py\$
^$G/README\.md\$
^$G/tests/.*
^$A/scripts/(section4|planted-breaks)-G2c2\.sh\$
^$E/core/flows/binding\.py\$
^$E/runs/service/actions/runs\.py\$
^$E/runs/tasks\.py\$
^$E/runs/models\.py\$
^$E/runs/tests/(test_binding|test_executor)\.py\$
^$E/runs/tests/service/apis/test_runs\.py\$
^$E/config/api\.py\$
^$E/core/permissions\.py\$
^$E/core/tests/test_permissions(_wiring)?\.py\$
^$E/core/tests/isolation/test_(managers|static_rules)\.py\$
^$E/core/tests/test_(selector_scope|transaction_rules)\.py\$
^$E/config/tests/test_(api_contract|api_errors|request_schemas_reject_bool)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/tests/security/test_(login|tenant_paths|runs|owner|same_company_foreign_keys|migrations|ai_settings)\.py\$
^$A/tests_integration/test_run_flow\.py\$"

s1() {
  local all outside
  all="$(changed)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$(echo "$ALLOWED" | paste -sd'|' -)" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$(echo "$ALLOWED" | paste -sd'|' -)" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# §1-4 0줄(+ §1-3 끝의 0줄 목록)
ZERO="$G/engines $G/prompts $G/tests/data/golden $G/tests/data/gw1-ast-sha256.txt $G/tests/test_copy_ast.py
$G/migrations/0001_initial.py $G/service/selectors/review.py $G/service/services/review.py $G/service/actions/review.py
$G/service/actions/checks.py $G/service/apis/greenwash.py $G/contracts/shapes.py $G/contracts/wire.py
$A/uv.lock $A/.importlinter $E/config/apps_list.py $E/core/calc/audit.py $E/core/models.py $E/runs/calc/errors.py
$A/scripts/planted-breaks.sh $A/tests_integration/test_flow.py apps/web"

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

minus_lines() {  # <파일> → 그 파일의 - 줄 원문
  git diff -U0 "$BASE" -- "$1" | grep -E '^-' | grep -v -E '^--- ' | sed 's/^/      /'
}

s3() {
  local bad=0 f add del want
  # 파일 · 지움 한도(발주서 §4-3·§1-3: 숫자 줄·같은 줄 주석만)
  for want in "$E/core/flows/binding.py 4" "$E/runs/service/actions/runs.py 1" "$E/runs/tasks.py 1" \
    "$E/runs/models.py 1" "$E/config/api.py 0" "$E/core/permissions.py 0" \
    "$E/core/tests/test_permissions.py 4" "$E/core/tests/test_permissions_wiring.py 0" \
    "$E/core/tests/isolation/test_managers.py 1" "$E/core/tests/isolation/test_static_rules.py 2" \
    "$E/core/tests/test_selector_scope.py 2" "$E/core/tests/test_transaction_rules.py 1" \
    "$E/config/tests/test_api_contract.py 6" "$E/config/tests/test_api_errors.py 2" \
    "$E/config/tests/test_request_schemas_reject_bool.py 3" \
    "$E/runs/tests/test_binding.py 0" "$E/runs/tests/test_executor.py 0" "$E/runs/tests/service/apis/test_runs.py 0" \
    "$A/tests/security/test_login.py 3" "$A/tests/security/test_tenant_paths.py 1" "$A/tests/security/test_runs.py 0" \
    "$A/tests/security/test_owner.py 0" "$A/tests/security/test_same_company_foreign_keys.py 0" \
    "$A/tests/security/test_migrations.py 0" "$A/tests_integration/test_run_flow.py 1"; do
    set -- $want
    read -r add del <<< "$(numstat "$1")"
    echo "  $1 더함 $add 지움 $del(지움 한도 $2)"
    [ "$del" -le "$2" ] || bad=$((bad + 1))
    [ "$del" = 0 ] || minus_lines "$1"
  done
  for f in "$E/runs/service/actions/runs.py" "$E/runs/tasks.py"; do
    read -r add del <<< "$(numstat "$f")"
    [ "$add" -le 10 ] || { echo "  ★ $f 더함 $add(한도 10 — import 한 줄 + 부르는 문 하나, ruff 가 나눔)"; bad=$((bad + 1)); }
    [ "$add" = 0 ] || git diff -U0 "$BASE" -- "$f" | grep -E '^[-+]' | grep -v -E '^(---|\+\+\+) ' | sed 's/^/      /'
  done
  # 다른 끼움(등록된 것 전부)은 0줄: greenwash 밖의 flows/binding 파일
  local others
  others="$(changed | grep -E "^$E/[a-z]+/flows/binding" | grep -v "^$E/core/flows/binding\.py$" | grep -v -c "^$G/")"
  echo "  greenwash 밖 끼움 파일 바뀐 수 $others(0)"
  [ "$others" = 0 ] || bad=$((bad + 1))
  [ "$bad" = 0 ]
}

s4() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

NEW_PURE="esgapi/greenwash/tests/contracts/test_ai_setting_shapes.py esgapi/greenwash/tests/service/services/test_ai_settings_rules.py
esgapi/greenwash/tests/flows/test_binding_e0_settings.py esgapi/greenwash/tests/flows/test_colab_e0_dryrun_settings.py"

s5() {
  local log="$OUT/s5-pytest.log" code total new files
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash \
    -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  # shellcheck disable=SC2086
  files="$(cd "$A" && for f in $NEW_PURE; do [ -f "$f" ] && echo "$f"; done)"
  # shellcheck disable=SC2086
  new="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider --collect-only \
    -m "not django_db" $files | grep -c '::')"
  tail -1 "$log" | sed 's/^/  /'
  echo "  기준 $BASE_PURE + 새 파일 $new = $((BASE_PURE + new)) · 지금 ${total:-?}"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq $((BASE_PURE + new)) ]
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

s8() {
  local d="$OUT/s8-generated" code n
  mkdir -p "$d"
  if [ "$COMMIT" = 1 ]; then
    n="$( { git diff --name-only "$BASE" -- "$A/generated"; git ls-files -o --exclude-standard --full-name -- "$A/generated"; } | grep -c .)"
    echo "  커밋 1: generated/ 바뀐 것 $n(② 에서 다시 뽑는다)"
    [ "$n" = 0 ]
    return
  fi
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  python3 - "$BASE" "$A/generated/openapi.json" <<'PY'
import json, subprocess, sys
base, path = sys.argv[1], sys.argv[2]
old = json.loads(subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout)
new = json.loads(open(path, encoding="utf-8").read())
paths_added = sorted(set(new["paths"]) - set(old["paths"]))
paths_gone = sorted(set(old["paths"]) - set(new["paths"]))
changed = sorted(p for p in set(old["paths"]) & set(new["paths"]) if old["paths"][p] != new["paths"][p])
os_, ns = old["components"]["schemas"], new["components"]["schemas"]
schemas_added = sorted(set(ns) - set(os_))
schemas_gone = sorted(set(os_) - set(ns))
changed_schemas = sorted(s for s in set(os_) & set(ns) if os_[s] != ns[s])
ops = sorted(op["operationId"] for p in paths_added for op in new["paths"][p].values())
print(f"  경로 더함 {paths_added} · 빠짐 {paths_gone} · 바뀜 {changed}")
print(f"  동작 더함 {ops}")
print(f"  구성요소 더함 {schemas_added} · 빠짐 {schemas_gone} · 바뀜 {changed_schemas}")
want_paths = {"/ai-settings/greenwash", "/ai-settings/greenwash/default", "/ai-settings/greenwash/{setting_id}",
              "/ai-settings/greenwash/applied"}
want_ops = ["greenwash_ai_setting_apply", "greenwash_ai_setting_create", "greenwash_ai_setting_default",
            "greenwash_ai_setting_get", "greenwash_ai_setting_list"]
bad = []
if set(paths_added) != want_paths or paths_gone or changed:
    bad.append("경로")
if ops != want_ops:
    bad.append("동작")
if schemas_gone or changed_schemas or any(not s.startswith(("GreenwashAiSetting", "GreenwashCriteri")) for s in schemas_added):
    bad.append("구성요소")
print(f"  §2-6 밖: {bad}")
sys.exit(1 if bad else 0)
PY
}

s9() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
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

s9b() {  # 0002 는 0001 만 딛는다
  local deps
  deps="$(python3 - "$G/migrations" <<'PY'
import ast, sys
from pathlib import Path
found = sorted(Path(sys.argv[1]).glob("0002_*.py"))
tree = ast.parse(found[0].read_text(encoding="utf-8"))
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(getattr(t, "id", "") == "dependencies" for t in node.targets):
        print(ast.literal_eval(node.value))
PY
)"
  echo "  0002 dependencies $deps"
  [ "$deps" = "[('greenwash', '0001_initial')]" ]
}

s10_business() {
  local log="$OUT/s10-business.log" code n
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s10-up-postgres.log" 2>&1 || { tail -3 "$OUT/s10-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/greenwash \
    esgapi/runs esgapi/config esgapi/core) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 커밋 $COMMIT 기대 $(expect_business))"
  [ "$code" -eq 0 ] && [ "${n:-0}" -gt "$BASE_BUSINESS" ] && { [ "$(expect_business)" = 0 ] || [ "${n:-0}" -eq "$(expect_business)" ]; }
}

s10_security() {
  local log="$OUT/s10-security.log" code n
  gate || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  보안 층 수 ${n:-?}(기준 $BASE_SECURITY — 늘기만 · 커밋 $COMMIT 기대 $(expect_security))"
  [ "$code" -eq 0 ] && [ "${n:-0}" -gt "$BASE_SECURITY" ] && { [ "$(expect_security)" = 0 ] || [ "${n:-0}" -eq "$(expect_security)" ]; }
}

s10_integration() {
  local log="$OUT/s10-integration.log" code start key
  gate || return 1
  key="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || return 1
  export EDK_JWT_PUBLIC_KEY="$key" CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
  scripts/with-build-lock.sh docker compose build > "$OUT/s10-build.log" 2>&1 || { tail -3 "$OUT/s10-build.log"; return 1; }
  docker compose up -d --wait > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  start=$(date +%s)
  (cd "$A" && scripts/test-integration.sh -p no:cacheprovider -rA tests_integration/test_run_flow.py) > "$log" 2>&1
  code=$?
  grep -E "^(PASSED|FAILED)" "$log" | sed 's/^/  /'
  tail -1 "$log" | sed 's/^/  /'
  echo "  통합 test_run_flow $(( $(date +%s) - start ))초"
  return "$code"
}

s11() {
  local log="$OUT/s11-planted.log" flag="" want
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  G2C2_OUT="$OUT" "$A/scripts/planted-breaks-G2c2.sh" --commit "$([ "$COMMIT" -ge 3 ] && echo 3 || echo "$COMMIT")" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  want=8
  [ "$COMMIT" = 2 ] && want=11
  [ "$COMMIT" -ge 3 ] && want=16
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무·보안 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=$want/$want" ]; }
}

s13() {
  local all keys bin lab words body msg
  all="$(changed)"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2c2\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  lab="$(echo "$body" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2c2\.sh:" | grep -c -E 'esg-lab|py/greenwash')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · esg-lab 언급(더한 줄) $lab · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$lab" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2 + §1-3 안" s1
step 2 "0줄 목록 diff 0(§1-4)" s2
step 3 "§1-3 줄 범위(numstat·- 줄 원문)" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash(순수) 초록, 수 = 기준 + 새" s5
step 5 "test_copy_ast(엔진 AST 그대로)" s6
step 6 "골든 sha256 = <기준>" s7
step 7 "generated/ 다시 뽑아 cmp + 차이가 §2-6 안" s8
step 8 "makemigrations --check(모든 앱)" s9
step 8 "0002 는 0001 만 딛음" s9b
step 9 "verify.sh --fast" s10
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무 층 greenwash·runs·config·core" s10_business
  step 10 "보안 층 tests/security" s10_security
  if [ "$COMMIT" -ge 3 ]; then
    step 10 "통합 tests_integration/test_run_flow.py" s10_integration
  fi
else
  not_run 10 "컨테이너 층(업무·보안·통합)" "--with-containers 없음"
fi
step 11 "심은 파손" s11
step 12 "키 꼴·바이너리·esg-lab·실재 기업명 0" s13
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
