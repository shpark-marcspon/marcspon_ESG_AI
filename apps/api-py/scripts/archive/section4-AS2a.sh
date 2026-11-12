#!/usr/bin/env bash
# 밴드 AS2a(MARC-TICK-215: 그린워싱 AI 설정 판의 프롬프트·모델 읽기 경로 둘 — ai.prompt-model@1)의 §4 자기검증(발주서
# band-handoffs/AS2a-order.md §4). 틀은 section4-G2c3.sh 그대로다(커밋 하나라 --commit 없음).
#   사용: apps/api-py/scripts/section4-AS2a.sh [--with-containers] [--step <n>]
#   --with-containers 면 단계 11(업무·보안)과 12 의 컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)만. 문(현황판 MARC-TICK-76 3절, MARC-ENT-241·292):
#   띄우기 전 기존 esg-app* 벌 < 3(자기 밖 ≤ 2 — 감독 f6 확인), build 중 0, free ≥ 20%, 1분 부하 < 24 — 60초 간격 최대 30분. build 는
#   scripts/with-build-lock.sh 로만. 띄운 벌은 내리지 않는다(러너가 끝에 down -v).
# 환경 변수: AS2A_OUT(로그 자리, 기본 워크트리 곁의 AS2a.out — 심은 파손에도 넘긴다), AS2A_FORBIDDEN(실재 기업명 낱말 파일,
#   기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
G="$E/greenwash"
OUT="${AS2A_OUT:-$ROOT/../AS2a.out}"
FORBIDDEN="${AS2A_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(b0a4b29)에서 잰 수 — 그 트리를 git archive 로 풀어 --collect-only. 순수 = pytest esgapi/greenwash -m "not django_db",
# 업무 = test-business.sh esgapi/{greenwash,config,core}, 보안 = test-security.sh 전부.
# 기대: 순수 +7(test_prompt_model_e0) · 업무 +8(apis/test_ai_settings_prompt_model 6 · test_permissions_wiring 매개 2) ·
# 보안 +3(test_ai_settings 함수 하나 · test_tenant_paths 401 매개 2).
BASE_PURE=759 BASE_BUSINESS=347 BASE_SECURITY=266
WANT_PURE=766 WANT_BUSINESS=355 WANT_SECURITY=269
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
echo "── 밴드 AS2a §4 · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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
ALLOWED="^$G/flows/prompt_model_e0\.py\$
^$G/service/(selectors|actions|apis)/ai_settings\.py\$
^$G/README\.md\$
^$G/tests/flows/test_prompt_model_e0\.py\$
^$G/tests/service/apis/test_ai_settings_prompt_model\.py\$
^$A/scripts/(section4|planted-breaks)-AS2a\.sh\$
^$E/core/permissions\.py\$
^$E/core/tests/test_permissions(_wiring)?\.py\$
^$E/core/tests/contracts/test_ai_setting_shapes\.py\$
^$E/config/tests/test_api_(contract|errors)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/tests/security/test_(tenant_paths|login|ai_settings)\.py\$"

# §1-3 「0줄」 + §1-4 0바이트
ZERO="$E/config/api.py $A/.importlinter $E/runs $A/tests_integration $E/config/tests/test_request_schemas_reject_bool.py
apps/web $A/uv.lock $A/scripts/test-layout-allow.txt $G/engines $G/prompts $G/tests/data/golden
$G/tests/data/gw1-ast-sha256.txt $G/migrations $G/contracts $G/flows/colab_e0.py $G/flows/criteria_e0.py
$G/flows/binding_e0.py $G/flows/rewrite_r1.py $G/models.py $G/service/services $G/tools $G/outputs"

s1() {
  local all outside pattern missing=0 p n bad
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ "$outside" -eq 0 ] && [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

SHARED="$E/core/permissions.py $E/core/tests/contracts/test_ai_setting_shapes.py $E/core/tests/test_permissions.py $E/core/tests/test_permissions_wiring.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $A/tests/security/test_tenant_paths.py
$A/tests/security/test_login.py $A/tests/security/test_ai_settings.py $A/generated/openapi.json $A/generated/api.d.ts
$A/generated/api.d.ts.source-sha256"

s2() {  # numstat · - 줄 원문 · - 줄이 「같은 줄의 숫자·주석」뿐인가(bad_minus)
  local f
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED | sed 's/^/  /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED | python3 -c '
import re, sys
bad = total = 0
GRANTED = "assert not found & set(openapi[\"components\"][\"schemas\"])"
file = None
minus, plus = [], []

def norm(line):
    code = line.split("  #", 1)[0].split(" # ", 1)[0].rstrip()
    return re.sub(r"[0-9]+", "N", code)

def flush():
    global bad, total, minus, plus
    for m in minus:
        total += 1
        print(f"    - {file}: {m}")
        stripped = m.strip()
        if file.endswith("api.d.ts.source-sha256") and re.fullmatch(r"[0-9a-f]{64}", stripped):
            continue
        if stripped.startswith("#"):
            continue  # 주석 줄
        if any(norm(m) == norm(p) for p in plus):
            continue  # 같은 줄 — 숫자·주석만 다름
        if file.endswith("contracts/test_ai_setting_shapes.py") and stripped == GRANTED:
            print("      (허락 ③ — TICK-215 노트: Ai* 겹침 단언을 「core 꼴만」으로)")
            continue
        bad += 1
        print("      ★ 숫자·주석 밖의 지움")
    minus, plus = [], []

for raw in sys.stdin:
    line = raw.rstrip("\n")
    if line.startswith("diff --git"):
        flush()
        file = line.split(" b/", 1)[1]
    elif line.startswith("@@"):
        flush()
    elif line.startswith("-") and not line.startswith("---"):
        minus.append(line[1:])
    elif line.startswith("+") and not line.startswith("+++"):
        plus.append(line[1:])
flush()
print(f"  - 줄 {total} · bad_minus={bad}")
sys.exit(1 if bad else 0)
'
}

s3() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

s4() {
  local log="$OUT/s4-pytest.log" code total perm
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash \
    -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  tail -1 "$log" | sed 's/^/  /'
  echo "  순수 기준 $BASE_PURE → 지금 ${total:-?}(기대 $WANT_PURE)"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core/tests/test_permissions.py) > "$OUT/s4-permissions.log" 2>&1
  perm=$?
  tail -1 "$OUT/s4-permissions.log" | sed 's/^/  test_permissions: /'
  [ "$code" -eq 0 ] && [ "$perm" -eq 0 ] && [ "${total:-0}" -eq "$WANT_PURE" ]
}

s5() {
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

s6() {  # 다시 뽑은 openapi 가 generated/ 와 바이트 같고, sha 파일이 맞고, <기준> 견줌 더함뿐
  local d="$OUT/s6-generated" code sha
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" || return 1
  sha="$(shasum -a 256 "$A/generated/openapi.json" | cut -d' ' -f1)"
  [ "$sha" = "$(cat "$A/generated/api.d.ts.source-sha256")" ] || { echo "  ★ api.d.ts.source-sha256 다름"; return 1; }
  git show "$BASE:$A/generated/openapi.json" > "$d/openapi.base.json"
  python3 - "$d/openapi.base.json" "$A/generated/openapi.json" <<'PY'
import json, sys
a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:3])
old_paths = [k for k in a["paths"] if a["paths"][k] != b["paths"].get(k)]
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
old_comp = [k for k in sa if sa[k] != sb.get(k)]
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
rest += [k for k in set(a["components"]) | set(b["components"]) if k != "schemas" and a["components"].get(k) != b["components"].get(k)]
new_paths = sorted(k for k in b["paths"] if k not in a["paths"])
new_comp = sorted(k for k in sb if k not in sa)
print(f"  changed_old={len(old_paths) + len(old_comp) + len(rest)} {old_paths + old_comp + rest}")
print(f"  new_paths={len(new_paths)} {new_paths}")
print(f"  new_components={len(new_comp)} {new_comp}")
ok = not (old_paths or old_comp or rest) and len(new_paths) == 2 and all(k.startswith("Ai") for k in new_comp)
sys.exit(0 if ok else 1)
PY
}

s7() {
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py makemigrations --check --dry-run 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s8() {
  local n
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || return 1
  n="$(git diff --name-only "$BASE" -- "$A/scripts/test-layout-allow.txt" | grep -c .)"
  echo "  허용 목록 diff $n"
  [ "$n" = 0 ]
}

s9() {
  local n
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core/tests/isolation/test_static_rules.py esgapi/core/tests/test_selector_scope.py \
    esgapi/core/tests/test_transaction_rules.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || return 1
  n="$(git grep -c 'opened == 60' -- "$E/core/tests/isolation/test_static_rules.py" | cut -d: -f2)"
  echo "  for_company 분모 줄 opened == 60: ${n:-0}"
  [ "${n:-0}" = 1 ]
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
  local log="$OUT/s11-business.log" code n
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s11-up-postgres.log" 2>&1 || { tail -3 "$OUT/s11-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/greenwash \
    esgapi/config esgapi/core) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 기대 $WANT_BUSINESS)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -eq "$WANT_BUSINESS" ]
}

s11_security() {
  local log="$OUT/s11-security.log" code n
  gate || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  보안 층 수 ${n:-?}(기준 $BASE_SECURITY — 늘기만 · 기대 $WANT_SECURITY)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -eq "$WANT_SECURITY" ]
}

s12() {
  local log="$OUT/s12-planted.log" flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  AS2A_OUT="$OUT" "$A/scripts/planted-breaks-AS2a.sh" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=10/10" ]; }
}

s13() {
  local all keys bin lab words body msg
  all="$(changed)"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  keys="$(printf '%s\n%s\n' "$body" "$msg" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-AS2a\.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  lab="$(echo "$body" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-AS2a\.sh:" | grep -c -E 'esg-lab|py/greenwash')"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$body" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · esg-lab 언급(더한 줄) $lab · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$lab" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2 + §1-3 안 · 0줄·0바이트 diff 0" s1
step 2 "§1-3 공유 파일 numstat·- 줄 원문(숫자·주석뿐)" s2
step 3 "lint-imports 전부 KEPT" s3
step 4 "pytest esgapi/greenwash(순수)·test_permissions 초록, 수" s4
step 5 "골든 sha256 = <기준>" s5
step 6 "generated/ 다시 뽑아 cmp · 더함뿐" s6
step 7 "makemigrations --check(모든 앱)" s7
step 8 "테스트 자리 검사·허용 목록 diff 0" s8
step 9 "격리 정적 규칙·selector 범위·트랜잭션 규칙(분모 60)" s9
step 10 "verify.sh --fast" s10
if [ "$CONTAINERS" = 1 ]; then
  step 11 "업무 층 greenwash·config·core" s11_business
  step 11 "보안 층 tests/security" s11_security
else
  not_run 11 "컨테이너 층(업무·보안)" "--with-containers 없음"
fi
step 12 "심은 파손" s12
step 13 "키 꼴·바이너리·esg-lab·실재 기업명 0" s13
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
