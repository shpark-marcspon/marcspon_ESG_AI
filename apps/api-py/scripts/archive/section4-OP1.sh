#!/usr/bin/env bash
# 밴드 OP1(MARC-TICK-222: 운영 관리자가 작업 회사 chosen_company 로 그린워싱 업무 — 회사 동작 칸·인증 통과·회사 고르기·
# 이름 풀기, 결정 MARC-ENT-374)의 §4 자기검증(발주서 band-handoffs/OP1-order.md §4). 틀은 section4-AS2b.sh 그대로다.
#   사용: apps/api-py/scripts/section4-OP1.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --commit 1 = 권한 표·인증·회사 고르기·실행 모듈(PLANTED 15), 2 = + 기록·이름(+4), 3 = + 보안 시험 test_operator_company
#   (+3 — 22: 12·19·20). 수 기대도 경계마다.
#   --with-containers 면 단계 9(업무·보안)와 10 의 컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 postgres 만(MARC-ENT-241 문 — 아래 gate).
# 환경 변수: OP1_OUT(로그 자리, 기본 워크트리 곁의 OP1.out — 심은 파손에도 넘긴다), OP1_FORBIDDEN(실재 기업명 낱말 파일,
#   기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
OUT="${OP1_OUT:-$ROOT/../OP1.out}"
FORBIDDEN="${OP1_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(bfc4e25)에서 잰 수 — 그 트리를 git archive 로 풀어 --collect-only.
#   순수 = pytest esgapi/{core,user,runs,organization,config} -m "not django_db"
#   업무 = test-business.sh esgapi/{core,user,runs,organization,config,greenwash} · 보안 = test-security.sh 전부
# ① 기대: 순수 +8(test_permissions 함수 셋 · test_bearer 함수 다섯 — 이름 바꾼 하나는 셈 0) · 업무 +28(test_permissions_wiring
# 회사 업무 18 · test_runs_operator 다섯 · test_operator_work_company 다섯) · 보안 +1(test_tenant_paths 운영 관리자 시험을 둘로).
BASE1_PURE=1681 BASE1_BUSINESS=903 BASE1_SECURITY=276  # ①·② 의 <기준> bfc4e25. 순수는 passed 수(수집 − skipped 1)
WANT1_PURE=1689 WANT1_BUSINESS=931 WANT1_SECURITY=277
# ② 기대(① 뒤): 순수 0 · 업무 +11(people_of 셋 · company_name 하나 · 올림 확인 actor_kind 매개 넷 · 실행 기록 이름 하나 ·
# 그린워싱 actions 둘) · 보안 0.
WANT2_PURE=1689 WANT2_BUSINESS=942 WANT2_SECURITY=277
# ③ 의 <기준>은 감독의 따라잡기 병합(d64e83b — main 47b8a52, MARC-TICK-222 노트) 뒤 merge-base = 47b8a52. 그 트리로 다시 잰
# 수(TR2 몫 포함): 순수 1692 · 업무 904 · 보안 285. ③ 기대: 순수·업무는 ①② 몫(+8·+39) 그대로, 보안 +14(test_tenant_paths
# 둘로 나눔 +1 · test_operator_company 13 — ④ 매개 셋).
BASE3_PURE=1692 BASE3_BUSINESS=904 BASE3_SECURITY=285
WANT3_PURE=1700 WANT3_BUSINESS=943 WANT3_SECURITY=299
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in
  1) WANT_PURE=$WANT1_PURE WANT_BUSINESS=$WANT1_BUSINESS WANT_SECURITY=$WANT1_SECURITY WANT_PLANTED=15 ;;
  2) WANT_PURE=$WANT2_PURE WANT_BUSINESS=$WANT2_BUSINESS WANT_SECURITY=$WANT2_SECURITY WANT_PLANTED=19 ;;
  3) WANT_PURE=$WANT3_PURE WANT_BUSINESS=$WANT3_BUSINESS WANT_SECURITY=$WANT3_SECURITY WANT_PLANTED=22 ;;
  *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
esac
if [ "$COMMIT" = 3 ]; then
  BASE_PURE=$BASE3_PURE BASE_BUSINESS=$BASE3_BUSINESS BASE_SECURITY=$BASE3_SECURITY
else
  BASE_PURE=$BASE1_PURE BASE_BUSINESS=$BASE1_BUSINESS BASE_SECURITY=$BASE1_SECURITY
fi
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 OP1 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

tr2_merged() { git cat-file -e "$BASE:$A/tests/security/test_translation.py" 2> /dev/null; }  # <기준>에 TR2 가 들었나

# §1-2(줄기) + §1-4(9f·37 허락) + 감독 판단으로 더한 것(37: 그린워싱 계약 시험 :235·:237) — 닫힌 목록
ALLOWED="^$E/core/permissions\.py\$
^$E/core/auth/bearer\.py\$
^$E/user/service/apis/users\.py\$
^$E/config/api\.py\$
^$E/runs/service/apis/runs\.py\$
^$E/core/service/services/documents\.py\$
^$E/core/service/apis/documents\.py\$
^$E/user/service/selectors/user\.py\$
^$E/user/service/apis/run_logs\.py\$
^$E/organization/service/selectors/organization\.py\$
^$E/(core|user|runs|organization|config)/tests/.*\$
^$A/scripts/(section4|planted-breaks)-OP1\.sh\$
^$A/tests/security/(test_tenant_paths|test_login|test_greenwash|test_operator_company)\.py\$
^$E/greenwash/service/actions/(checks|review)\.py\$
^$E/greenwash/tests/service/actions/.*\$
^$E/greenwash/tests/contracts/test_contracts_review_report_terms\.py\$"
tr2_merged && ALLOWED="$ALLOWED
^$A/tests/security/test_translation\.py\$"

# §4-2 0줄 목록(글롭은 git 경로 마법)
ZERO="apps/web $A/generated :(glob)**/migrations/** :(glob)**/models.py $E/core/auth/tokens.py $E/core/auth/principal.py
$E/core/flows $E/runs/tasks.py $E/runs/service/actions $E/runs/service/selectors $E/greenwash/service/apis $E/greenwash/flows
$E/greenwash/tests/flows $E/greenwash/outputs $A/.importlinter $A/tests_integration :(glob)**/conftest.py $A/tests/support
$A/scripts/planted-breaks.sh $E/core/tests/isolation/test_static_rules.py"
# ① 에서는 ② 의 자리도 0줄(기록·이름 — documents·selectors·run_logs·organization selectors·37 줄)
[ "$COMMIT" = 1 ] && ZERO="$ZERO $E/core/service/services/documents.py $E/core/service/apis/documents.py
$E/user/service/selectors/user.py $E/user/service/apis/run_logs.py $E/organization/service/selectors/organization.py
$E/greenwash/service/actions $E/greenwash/tests/service/actions"
[ "$COMMIT" = 3 ] || ZERO="$ZERO $A/tests/security/test_operator_company.py"

route_sha() {  # <git 대상(기준 해시 또는 빈 값 = 작업 트리)> — test_each_route_checks_its_own_operation_id_first 몸의 ast sha
  local f="$E/core/tests/test_permissions.py"
  { if [ -n "$1" ]; then git show "$1:$f"; else cat "$f"; fi; } | python3 -c '
import ast, hashlib, sys
tree = ast.parse(sys.stdin.read())
(fn,) = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "test_each_route_checks_its_own_operation_id_first"]
print(hashlib.sha256(ast.dump(fn).encode()).hexdigest())'
}

s1() {
  local all outside pattern bad
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside · TR2 병합 $(tr2_merged && echo 됨 || echo 안 됨)"
  [ "$outside" -eq 0 ]
}

s2() {
  local bad a b
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  a="$(route_sha "$BASE")"; b="$(route_sha "")"
  echo "  test_each_route_checks_its_own_operation_id_first 몸 ast sha <기준> ${a:0:12} · 지금 ${b:0:12}"
  [ -z "$bad" ] && [ -n "$a" ] && [ "$a" = "$b" ]
}

SHARED="$A/tests/security $E/greenwash"

s3() {  # 9f·37 줄의 numstat · - 줄 원문 · 허락 밖의 지움(bad_minus)
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED | sed 's/^/  /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED | python3 -c '
import re, sys
bad = total = 0
# 허락한 - 줄(앞뒤 빈칸 뺀 원문): 발주서 §1-4(9f·37) + 감독 판단(37 계약 시험 :235·:237, 9f test_login + 한 줄)
GRANTED = {
    # 9f test_tenant_paths :361-384 — 둘로 나누고 PASSING_REQUESTS 로 보냄(발주서 §1-4)
    "def test_an_operator_bearer_is_401_company_required_on_every_company_operation(",
    "\"\"\"(K2b) 운영 관리자의 Bearer 로 회사 동작 27 전부 401 company_required — 회사 행을 읽지도 쓰지도 않는다.\"\"\"",
    "assert len(company_operations()) == 27  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다",
    "for method, path in company_operations():",
    "response = (",
    "operator.get(concrete(path)) if method == \"GET\" else getattr(operator, method.lower())(concrete(path))",
    ")",
    "assert (response.status_code, response.json()[\"error\"][\"code\"]) == (401, \"COMPANY_REQUIRED\"), (method, path)",
    # 9f test_login :392-407 · :10
    "\"\"\"(K2b) 운영 관리자의 Bearer 로 회사 경로: 401 company_required — 회사 행을 읽지도 쓰지도 않는다(행 0).",
    "assert answer(client.get(\"/api/sites\", **bearer(access))) == (401, \"COMPANY_REQUIRED\")",
    "assert answer(created) == (401, \"COMPANY_REQUIRED\")",
    "assert answer(client.get(\"/api/documents\", **bearer(access))) == (401, \"COMPANY_REQUIRED\")",
    # 9f test_greenwash :12 · :335 · :356
    "ⓔ 운영 관리자 Bearer(§3-4-4) → 그린워싱 경로 넷(결과·검토 GET·PUT·목록 줄) 401 company_required, 행 0.",
    "def test_an_operator_bearer_is_401_company_required_on_the_greenwash_routes(",
    "assert (response.status_code, response.json()[\"error\"][\"code\"]) == (401, \"COMPANY_REQUIRED\"), path",
    # 37 checks.py :44·:51-55·:182·:208 · review.py :56·:130(발주서 §1-4 — 회사 이름 도우미를 걷고 company_name·people_of 로)
    "from esgapi.user.service.selectors.user import account, names_of",
    "def _company_name(company_id: int, user_id: int) -> str:",
    "\"\"\"세션 사용자의 회사 이름(user 의 account 가 회사를 같이 읽는다 — 쿼리 하나). 못 찾으면 빈 글자.\"\"\"",
    "user = account(company_id, user_id)",
    "company = user.company if user is not None else None",
    "return company.name if company is not None else \"\"",
    "",
    "names = names_of(company_id, wanted, set()) if wanted else {}",
    "\"companyName\": _company_name(company_id, user_id),",
    "from esgapi.user.service.selectors.user import names_of",
    "found = names_of(company_id, {user_id}, set()).get(user_id)",
    # 37 계약 시험 :235·:237(감독 판단 — 222 노트)
    "from esgapi.core.permissions import CUSTOMER, OPERATION_POLICY, OPERATOR",
    "assert OPERATION_POLICY[operation_id] == CUSTOMER",
    # 같은 옛 줄의 TR2 판(③ 의 <기준> 47b8a52 — 회사 동작 28) · 고객사 Bearer 시험 docstring 의 「401 의 짝」
    "\"\"\"(K2b) 운영 관리자의 Bearer 로 회사 동작 28 전부 401 company_required — 회사 행을 읽지도 쓰지도 않는다.\"\"\"",
    "assert len(company_operations()) == 28  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다 · TR2 +1",
    "\"\"\"(AUTHZ1) 고객사 사용자의 Bearer(쿠키 0)로 회사 동작 28 전부가 인증과 권한을 지난다 — 위 운영 관리자 401 의 짝.",
    # 9f test_translation(TR2 병합 뒤만 — §1-5): :12 머리말 ⓒ · :237 이름 · :253 단언
    "ⓒ 세션 없이 401, 운영 관리자 Bearer 401 `COMPANY_REQUIRED`(그린워싱 결과 경로와 같다).",
    "def test_an_operator_bearer_is_401_company_required(",
    "assert (response.status_code, response.json()[\"error\"][\"code\"]) == (401, \"COMPANY_REQUIRED\")",
}
DISABLERS = re.compile(r"\bor True\b|\bif False\b|pytest\.skip|xfail")
disabled = 0
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
        if stripped.startswith("#"):
            continue  # 주석 줄
        if any(norm(m) == norm(p) for p in plus):
            continue  # 같은 줄 — 숫자·주석만 다름(또는 옮김)
        if stripped in GRANTED:
            continue
        bad += 1
        print("      ★ 허락 밖의 지움")
    minus, plus = [], []

for raw in sys.stdin:
    line = raw.rstrip("\n")
    if line.startswith("diff --git"):
        flush()
        file = line.split(" b/", 1)[1]
    elif line.startswith("@@"):
        continue  # 덩이를 넘어 견준다(나눈 함수의 옮긴 줄)
    elif line.startswith("-") and not line.startswith("---"):
        minus.append(line[1:])
    elif line.startswith("+") and not line.startswith("+++"):
        plus.append(line[1:])
        if DISABLERS.search(line[1:]) and not line[1:].lstrip().startswith("#"):
            disabled += 1
            print(f"    ★ 끄는 꼴: {file}: {line[1:]}")
flush()
print(f"  - 줄 {total} · bad_minus={bad} · 끄는 꼴(or True·if False·pytest.skip·xfail) {disabled}")
sys.exit(1 if bad or disabled else 0)
'
}

s4() {  # 더한 제품 줄에 회사 id 숫자 박기 0 · 실재 기업명 0(더한 줄·커밋 메시지)
  local all body ids words msg
  all="$(changed | grep -v -E '/tests/|/scripts/')"
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2> /dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed 's/^/+/' "$f"; fi; done)"
  ids="$(echo "$body" | grep -c -E 'company_id[[:space:]]*=[[:space:]]*[0-9]|for_company\([0-9]')"
  msg="$(git log --format=%B "$BASE..HEAD")"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$(changed | while read -r f; do [ -f "$f" ] && git diff "$BASE" -- "$f" | grep -E '^\+'; done; git ls-files -o --exclude-standard --full-name | while read -r f; do cat "$f"; done)" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  회사 id 숫자 박기(더한 제품 줄) $ids · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$ids" -eq 0 ] && [ "$words" = 0 ]
}

s5() {
  local log="$OUT/s5-lint-imports.log" kept
  (cd "$A" && uv run --frozen lint-imports) > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  kept="$(sed -n -E 's/^Contracts: ([0-9]+) kept, 0 broken\.$/\1/p' "$log")"
  echo "  KEPT ${kept:-?}(기준 17)"
  [ "$code" -eq 0 ] && [ "${kept:-0}" = 17 ]
}

s6() {
  local log="$OUT/s6-pure.log" code total
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core esgapi/user esgapi/runs esgapi/organization esgapi/config -m "not django_db") > "$log" 2>&1
  code=$?
  total="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  tail -1 "$log" | sed 's/^/  /'
  echo "  순수 기준 $BASE_PURE → 지금 ${total:-?}(기대 $WANT_PURE)"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq "$WANT_PURE" ]
}

s7() {  # generated/ 다시 뽑아 cmp — 0바이트
  local d="$OUT/s7-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" && echo "  openapi.json 같음 · generated/ diff $(git diff --name-only "$BASE" -- "$A/generated" | grep -c .)"
}

s8() {
  local log="$OUT/s8-verify-fast.log"
  scripts/verify.sh --fast > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ]
}

gate() {  # 기계 문(MARC-ENT-241): 자기 밖 esg-app* ≤ 2 · build 중 0 · free ≥ 20% · 1분 부하 < 24 — 60초 간격 최대 30분
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

s9_business() {
  local log="$OUT/s9-business.log" code n
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s9-up-postgres.log" 2>&1 || { tail -3 "$OUT/s9-up-postgres.log"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider -n 4 esgapi/core \
    esgapi/user esgapi/runs esgapi/organization esgapi/config esgapi/greenwash) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  업무 층 수 ${n:-?}(기준 $BASE_BUSINESS — 늘기만 · 기대 $WANT_BUSINESS)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -eq "$WANT_BUSINESS" ]
}

s9_security() {
  local log="$OUT/s9-security.log" code n
  gate || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  보안 층 수 ${n:-?}(기준 $BASE_SECURITY — 늘기만 · 기대 $WANT_SECURITY)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -eq "$WANT_SECURITY" ]
}

s10() {
  local log="$OUT/s10-planted.log" flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  OP1_OUT="$OUT" "$A/scripts/planted-breaks-OP1.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무·보안 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=$WANT_PLANTED/$WANT_PLANTED" ]; }
}

step 1 "바뀐 경로가 §1-2·§1-4 안(outside=0)" s1
step 2 "0줄 목록 diff 0 · test_each_route_checks_its_own_operation_id_first 몸 그대로" s2
step 3 "9f·37 줄 numstat·- 줄 원문(허락한 꼴뿐)" s3
step 4 "더한 제품 줄에 회사 id 숫자 박기 0 · 실재 기업명 0" s4
step 5 "lint-imports 전부 KEPT(17)" s5
step 6 "순수 층 core·user·runs·organization·config 초록, 수" s6
step 7 "generated/ 다시 뽑아 cmp 0바이트" s7
step 8 "verify.sh --fast" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무 층 core·user·runs·organization·config·greenwash" s9_business
  step 9 "보안 층 tests/security" s9_security
else
  not_run 9 "컨테이너 층(업무·보안)" "--with-containers 없음"
fi
step 10 "심은 파손" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
