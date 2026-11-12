#!/usr/bin/env bash
# 밴드 G1b-1(MARC-TICK-191: 그린워싱 끼움·결과·검토·목록 줄)의 §4 자기검증(발주서 band-handoffs/G1b-order.md §4, 개정 1
# + 감독 처분: run_id BigInt(MARC-ENT-210), colab_e0 의 파트 차례 한 갈래).
#   사용: apps/api-py/scripts/section4-G1b.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit n 은 커밋 n 경계(그 커밋까지의 시험·심은 파손). --with-containers 면 단계 11(업무·보안·통합)과 12 의
#   컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(MARC-ENT-241·292): 자기 밖 esg-app*
#   프로젝트 ≤ 2, build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. build 는 scripts/with-build-lock.sh 로만.
#   띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G1b.out — 심은 파손에도 G1B_OUT 으로 넘긴다), G1B_FORBIDDEN(실재
#   기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${S4_OUT:-$ROOT/../G1b.out}"
FORBIDDEN="${G1B_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
BASE_TESTS=601   # <기준>(181a483)에서 잰 pytest -q esgapi/greenwash -m "not django_db" 의 수
DROPPED_TESTS=0  # 커밋 ② 부터 3: test_contracts_shapes_paths 의 「몸은 501」 매개변수 넷 → 비교 하나(몸 생긴 셋은 업무 층)
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
echo "── 밴드 G1b-1 §4 · 커밋 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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
ALLOWED="^$G/apps\.py\$
^$G/flows/binding_e0\.py\$
^$G/flows/colab_e0\.py\$
^$G/contracts/options_shapes\.py\$
^$G/contracts/checks_shapes\.py\$
^$G/contracts/__init__\.py\$
^$G/models\.py\$
^$G/migrations/__init__\.py\$
^$G/migrations/0001_initial\.py\$
^$G/service/selectors/(__init__|review|checks)\.py\$
^$G/service/services/(__init__|review)\.py\$
^$G/service/actions/(__init__|review|checks)\.py\$
^$G/service/apis/greenwash\.py\$
^$G/README\.md\$
^$G/tests/.*
^$A/scripts/section4-G1b\.sh\$
^$A/scripts/planted-breaks-G1b\.sh\$
^$E/core/permissions\.py\$
^$E/config/tests/test_api_contract\.py\$
^$E/config/tests/test_api_errors\.py\$
^$E/core/tests/test_permissions\.py\$
^$E/core/tests/test_permissions_wiring\.py\$
^$E/core/tests/isolation/test_managers\.py\$
^$E/core/tests/isolation/test_static_rules\.py\$
^$E/core/tests/test_selector_scope\.py\$
^$E/core/tests/test_transaction_rules\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$E/runs/calc/errors\.py\$
^$E/runs/models\.py\$
^$A/tests/security/test_tenant_paths\.py\$
^$A/tests/security/test_owner\.py\$
^$A/tests/security/test_same_company_foreign_keys\.py\$
^$A/tests/security/test_migrations\.py\$
^$A/tests/security/test_greenwash\.py\$
^$A/tests/security/test_login\.py\$
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

# §1-4 0줄. 기존 그린워싱 시험 파일은 support.py·test_contracts_shapes_paths.py 밖이 0줄이다(새 파일만).
ZERO="$G/engines $G/prompts $G/tests/data/golden $G/tests/data/flow-shapes/greenwash.result@1.schema.json
$G/tests/data/flow-shapes/review $G/tests/data/flow-shapes/compare $G/tests/data/flow-shapes/criteria
$G/tests/data/flow-shapes/terms $G/tests/data/contract-examples/result-normal.json
$G/tests/data/contract-examples/result-dry-run.json $G/tests/data/contract-examples/result-no-pages.json
$G/tests/data/contract-examples/result-many.json $G/tests/data/contract-examples/review
$G/tests/data/contract-examples/compare $G/tests/data/contract-examples/criteria $G/contracts/shapes.py
$G/contracts/review_shapes.py $G/contracts/compare_shapes.py $G/contracts/criteria_shapes.py $G/contracts/terms_shapes.py
$G/contracts/wire.py $G/flows/criteria_e0.py $G/flows/registration.py $G/flows/rewrite_r1.py $G/outputs $G/tools
$G/api.py $G/tests/test_copy_ast.py $G/tests/data/gw1-ast-sha256.txt $G/tests/test_apps.py $G/tests/flows/test_colab_e0.py
$G/tests/flows/test_criteria_flow.py $G/tests/flows/test_extra_terms.py $G/tests/flows/test_registration.py
$G/tests/flows/test_boundary.py $E/user $A/.importlinter $E/config/api.py $E/config/apps_list.py $A/pyproject.toml
$A/uv.lock README.md scripts $A/scripts/planted-breaks.sh apps/web compose.yaml docker infra
$E/runs/tasks.py $E/runs/context.py $E/runs/service $E/runs/migrations $E/core/models.py $E/core/flows $E/core/service
$E/core/migrations $E/core/auth"

s2() {
  local missing=0 p n bad mig
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  # core/·runs/ 는 허용 파일 밖 전부 0줄
  bad="$(printf '%s\n%s\n' "$bad" "$(changed | grep -E "^$E/(core|runs)/" | grep -v -E "^$E/(core/permissions\.py|core/tests/test_permissions(_wiring)?\.py|core/tests/isolation/test_(managers|static_rules)\.py|core/tests/test_(selector_scope|transaction_rules)\.py|runs/calc/errors\.py|runs/models\.py)$")" | grep . | sort -u)"
  mig="$(changed | grep '/migrations/' | grep -v -c "^$G/migrations/")"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .) · 남의 migrations $mig"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ] && [ "$mig" -eq 0 ]
}

numstat() {  # <파일> → "더함 지움"(바뀌지 않았으면 0 0)
  local got
  got="$(git diff --numstat "$BASE" -- "$1" | awk '{print $1, $2}')"
  echo "${got:-0 0}"
}

s3() {
  local bad=0 f add del want
  # 파일 · 커밋 ③ 의 (더함, 지움) 정확 값(③ 앞에는 그 이하)
  for want in "$E/core/permissions.py 1 0" "$E/runs/calc/errors.py 2 0" "$E/runs/models.py 1 1" \
    "$E/core/tests/test_permissions_wiring.py 1 0"; do
    set -- $want
    read -r add del <<< "$(numstat "$1")"
    echo "  $1 더함 $add 지움 $del(기대 ③ $2/$3)"
    if [ "$COMMIT" = 3 ] && { [ "$add" != "$2" ] || [ "$del" != "$3" ]; }; then bad=$((bad + 1)); fi
    if [ "$add" -gt "$2" ] || [ "$del" -gt "$3" ]; then bad=$((bad + 1)); fi
  done
  read -r add del <<< "$(numstat "$E/core/tests/test_permissions.py")"
  # 한도 5/4: 발주서 4/3 + 막힌 수 분모 :213 한 줄(커밋 ③ — 백엔드 4d 의 core/tests 분모 허락)
  echo "  $E/core/tests/test_permissions.py 더함 $add 지움 $del(한도 5/4)"
  { [ "$add" -le 5 ] && [ "$del" -le 4 ]; } || bad=$((bad + 1))
  # config/tests/test_api_errors.py: 분모 둘(:67·:83)과 그 주석 줄만(X1b-2a 와 겹침 — 감독 처분 5)
  read -r add del <<< "$(numstat "$E/config/tests/test_api_errors.py")"
  echo "  $E/config/tests/test_api_errors.py 더함 $add 지움 $del(한도 4/4 — 분모 줄)"
  { [ "$add" -le 4 ] && [ "$del" -le 4 ]; } || bad=$((bad + 1))
  # core/tests 의 분모·목록(백엔드 4d 허락 2026-10-19 — 더하는 줄, - 줄은 숫자·합 줄뿐): 지움 한도
  for want in "$E/core/tests/isolation/test_managers.py 2" "$E/core/tests/isolation/test_static_rules.py 2" \
    "$E/core/tests/test_selector_scope.py 3" "$E/core/tests/test_transaction_rules.py 2"; do
    set -- $want
    read -r add del <<< "$(numstat "$1")"
    echo "  $1 더함 $add 지움 $del(지움 한도 $2 — 분모 줄)"
    [ "$del" -le "$2" ] || bad=$((bad + 1))
  done
  # test_login.py: 분모 둘(:281 인증 수·:303 막힌 수)의 숫자 줄만 −(테스트 감독 39 묶음 허락 2026-10-19)
  read -r add del <<< "$(numstat "$A/tests/security/test_login.py")"
  echo "  $A/tests/security/test_login.py 더함 $add 지움 $del(지움 한도 2 — 분모 숫자 줄)"
  [ "$del" -le 2 ] || bad=$((bad + 1))
  for f in "$A/tests/security/test_owner.py" "$A/tests/security/test_same_company_foreign_keys.py" "$A/tests/security/test_migrations.py"; do
    read -r add del <<< "$(numstat "$f")"
    echo "  $f 더함 $add 지움 $del(지움 0)"
    [ "$del" = 0 ] || bad=$((bad + 1))
  done
  # tenant_paths: - 줄 가운데 ID_FIELDS 블록 안 줄 0
  f="$A/tests/security/test_tenant_paths.py"
  read -r add del <<< "$(numstat "$f")"
  local idf
  idf="$(python3 - "$BASE" "$f" <<'PY'
import re, subprocess, sys
base, f = sys.argv[1], sys.argv[2]
old = subprocess.run(["git", "show", f"{base}:{f}"], capture_output=True, text=True, check=True).stdout.splitlines()
start = next((i for i, l in enumerate(old) if l.startswith("ID_FIELDS")), None)
end = start
if start is not None:
    depth = 0
    for j in range(start, len(old)):
        depth += old[j].count("(") + old[j].count("[") + old[j].count("{") - old[j].count(")") - old[j].count("]") - old[j].count("}")
        if depth <= 0 and j > start or (j == start and depth == 0):
            end = j
            break
diff = subprocess.run(["git", "diff", "-U0", base, "--", f], capture_output=True, text=True, check=True).stdout
hit = 0
for m in re.finditer(r"^@@ -(\d+)(?:,(\d+))? ", diff, flags=re.M):
    a, n = int(m.group(1)), int(m.group(2) or 1)
    for line in range(a, a + n):
        if start is not None and start + 1 <= line <= end + 1:
            hit += 1
print(hit)
PY
)"
  echo "  $f 더함 $add 지움 $del · ID_FIELDS 안 - 줄 $idf"
  [ "$idf" = 0 ] || bad=$((bad + 1))
  for f in "$A/.importlinter" "$A/scripts/planted-breaks.sh" "$E/config/api.py"; do
    read -r add del <<< "$(numstat "$f")"
    echo "  $f 더함 $add 지움 $del(0줄)"
    { [ "$add" = 0 ] && [ "$del" = 0 ]; } || bad=$((bad + 1))
  done
  read -r add del <<< "$(numstat "$G/flows/colab_e0.py")"
  echo "  $G/flows/colab_e0.py 더함 $add 지움 $del(한도 22/3 — no_text_layer 갈래·머리말 한 단락·파트 차례)"
  { [ "$add" -le 22 ] && [ "$del" -le 3 ]; } || bad=$((bad + 1))
  [ "$bad" = 0 ]
}

s4() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

NEW_PURE="esgapi/greenwash/tests/flows/test_binding_e0.py esgapi/greenwash/tests/flows/test_colab_e0_no_text_layer.py
esgapi/greenwash/tests/flows/test_colab_e0_part_order.py esgapi/greenwash/tests/contracts/test_options_shapes.py
esgapi/greenwash/tests/test_apps_binding.py esgapi/greenwash/tests/contracts/test_checks_shapes.py
esgapi/greenwash/tests/service/test_review_rules.py"

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
  [ "$COMMIT" = 1 ] || DROPPED_TESTS=3
  echo "  기준 $BASE_TESTS + 새 $new − 501 셋 $DROPPED_TESTS = $((BASE_TESTS + new - DROPPED_TESTS)) · 지금 ${total:-?}"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq $((BASE_TESTS + new - DROPPED_TESTS)) ]
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
  local d="$OUT/s8-generated" code
  mkdir -p "$d"
  if [ "$COMMIT" = 1 ]; then
    local n
    n="$( { git diff --name-only "$BASE" -- "$A/generated"; git ls-files -o --exclude-standard --full-name -- "$A/generated"; } | grep -c .)"
    echo "  커밋 $COMMIT: generated/ 바뀐 것 $n(② 에서 다시 뽑는다 — 501 빠짐 몫은 ②, /greenwash/checks 몫은 ③)"
    [ "$n" = 0 ]
    return
  fi
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  python3 - "$BASE" "$A/generated/openapi.json" "$COMMIT" <<'PY'
import json, subprocess, sys
base, path, commit = sys.argv[1], sys.argv[2], sys.argv[3]
old = json.loads(subprocess.run(["git", "show", f"{base}:{path}"], capture_output=True, text=True, check=True).stdout)
new = json.loads(open(path, encoding="utf-8").read())
bad = []
paths_added = sorted(set(new["paths"]) - set(old["paths"]))
paths_gone = sorted(set(old["paths"]) - set(new["paths"]))
schemas_added = sorted(set(new["components"]["schemas"]) - set(old["components"]["schemas"]))
schemas_gone = sorted(set(old["components"]["schemas"]) - set(new["components"]["schemas"]))
changed = sorted(p for p in set(old["paths"]) & set(new["paths"]) if old["paths"][p] != new["paths"][p])
changed_schemas = sorted(s for s in set(old["components"]["schemas"]) & set(new["components"]["schemas"])
                         if old["components"]["schemas"][s] != new["components"]["schemas"][s])
print(f"  경로 더함 {paths_added} · 빠짐 {paths_gone} · 바뀜 {changed}")
print(f"  구성요소 더함 {schemas_added} · 빠짐 {schemas_gone} · 바뀜 {changed_schemas}")
ok_paths = {"/greenwash/checks"} if commit == "3" else set()
ok_changed = {"/greenwash/runs/{run_id}/result", "/greenwash/runs/{run_id}/review"}
if set(paths_added) - ok_paths or paths_gone:
    bad.append("경로")
if set(changed) - ok_changed:
    bad.append("바뀐 경로")
if any(not s.startswith("GreenwashCheck") for s in schemas_added) or schemas_gone or changed_schemas:
    bad.append("구성요소")
if any("GreenwashOption" in s for s in new["components"]["schemas"]):
    bad.append("GreenwashOptions 가 openapi 에 오름")
for p in ok_changed:
    for method, op in new["paths"].get(p, {}).items():
        if "501" in op.get("responses", {}):
            bad.append(f"{method} {p} 501")
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
  local log="$OUT/s11-security.log" code
  gate || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  echo "  보안 층 수집(= 고른 수) $(sed -n -E 's/^([0-9]+) passed.*/\1/p; s/^.* ([0-9]+) passed.*/\1/p' "$log" | tail -1)(기준 181a483: 204)"
  return "$code"
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
  G1B_OUT="$OUT" "$A/scripts/planted-breaks-G1b.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  local want=6
  [ "$COMMIT" = 2 ] && want=16
  [ "$COMMIT" = 3 ] && want=17
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
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G1b\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  lab="$(echo "$body" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G1b\.sh:" | grep -c -E 'esg-lab|py/greenwash')"
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
step 3 "§1-3 줄 범위(numstat)" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash(순수) 초록, 수 = 기준 + 새" s5
step 6 "test_copy_ast(엔진 AST 그대로)" s6
step 7 "골든 sha256 = <기준>" s7
step 8 "generated/ 다시 뽑아 cmp + 차이가 §2-6 셋 안" s8
step 9 "makemigrations --check(모든 앱)" s9
step 10 "verify.sh --fast" s10
if [ "$CONTAINERS" = 1 ]; then
  step 11 "업무 층 greenwash·runs·config" s11_business
  step 11 "보안 층 tests/security" s11_security
  step 11 "통합 tests_integration/test_run_flow.py" s11_integration
else
  not_run 11 "컨테이너 층(업무·보안·통합)" "--with-containers 없음"
fi
step 12 "심은 파손" s12
step 13 "키 꼴·바이너리·esg-lab·실재 기업명 0" s13
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
