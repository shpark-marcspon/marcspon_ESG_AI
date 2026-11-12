#!/usr/bin/env bash
# 밴드 OP2(MARC-TICK-224: 운영 관리자도 영문번역 — 결과 칸 COMPANY·OPERATOR_RUN_MODULES 에 translation·admin 실행 목록의
# 모듈 집합, 결정 MARC-ENT-380·방식 374)의 §4 자기검증(발주서 band-handoffs/OP2-order.md §4). 틀은 section4-OP1.sh 그대로다.
#   사용: apps/api-py/scripts/section4-OP2.sh --commit <1|2> [--with-containers] [--step <n>]
#   --commit 1 = 동작 + 기존 단언 따라잡기(PLANTED 10 — 1~9·12), 2 = + 새 보안 짝 둘(PLANTED 13 — + 10·11·13).
#   --with-containers 면 단계 9(업무·보안)와 10 의 컨테이너 층을 돈다 — 아니면 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 postgres 만(MARC-ENT-241 문 — 아래 gate).
# 환경 변수: OP2_OUT(로그 자리, 기본 워크트리 곁의 OP2.out — 심은 파손에도 넘긴다), OP2_FORBIDDEN(실재 기업명 낱말 파일,
#   기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
OUT="${OP2_OUT:-$ROOT/../OP2.out}"
FORBIDDEN="${OP2_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(87e9739)에서 잰 수 — 그 트리를 git archive 로 풀어 --collect-only.
#   순수 = pytest esgapi/{core,runs} -m "not django_db"(직렬 — OP1 물을 거리 1)
#   업무 = test-business.sh esgapi/{core,runs,user,translation} · 보안 = test-security.sh 전부(늘기만 — 9f 조건 (마))
# ① 기대: 순수 0(이름 바꿈 하나는 셈 0) · 업무 +5(test_runs selectors 셋 · test_runs_operator 끝까지 매개 +1 ·
# test_permissions_wiring 회사 업무 19 매개 +1) · 보안 0(이름 바꿈·뒤집기뿐).
BASE_PURE=1406 BASE_BUSINESS=767 BASE_SECURITY=299
WANT1_PURE=1406 WANT1_BUSINESS=772 WANT1_SECURITY=299
# ② 기대(① 뒤): 순수·업무 0 · 보안 +2(test_operator_company ⑪ 남의 회사 · ⑫ 목록 짝).
WANT2_PURE=1406 WANT2_BUSINESS=772 WANT2_SECURITY=301
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in
  1) WANT_PURE=$WANT1_PURE WANT_BUSINESS=$WANT1_BUSINESS WANT_SECURITY=$WANT1_SECURITY WANT_PLANTED=10 ;;
  2) WANT_PURE=$WANT2_PURE WANT_BUSINESS=$WANT2_BUSINESS WANT_SECURITY=$WANT2_SECURITY WANT_PLANTED=13 ;;
  *) echo "사용: $0 --commit <1|2> [--with-containers] [--step <n>]" >&2; exit 2 ;;
esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 OP2 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-2(줄기) + §1-4(9f 허락) + §1-5 (가)(21 허락) — 닫힌 목록(개정 1: translation/** 는 0줄)
ALLOWED="^$E/core/permissions\.py\$
^$E/runs/service/apis/runs\.py\$
^$E/runs/service/selectors/runs\.py\$
^$E/(core|runs)/tests/.*\$
^$A/scripts/(section4|planted-breaks)-OP2\.sh\$
^$A/tests/security/(test_tenant_paths|test_operator_company|test_translation)\.py\$"

# §4-2 0줄 목록(글롭은 git 경로 마법)
ZERO="apps/web $A/generated :(glob)**/migrations/** :(glob)**/models.py $E/translation $E/greenwash $E/core/auth $E/user
$E/organization $E/config $E/runs/service/actions $E/runs/tasks.py $E/core/flows $A/.importlinter $A/tests_integration
:(glob)**/conftest.py $A/tests/support $A/scripts/planted-breaks.sh"

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
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
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

SHARED="$A/tests/security"

s3() {  # 9f·21 줄의 numstat · - 줄 원문 · 허락 밖의 지움(bad_minus)
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED | sed 's/^/  /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED | python3 -c '
import re, sys
bad = total = 0
# 허락한 - 줄(앞뒤 빈칸 뺀 원문): 발주서 §1-4(9f — 머리말 셈·⑩ 뒤집기·:422 줄) + §1-5 (가)(21 — :12·:237·:253).
# 숫자·주석만 다른 줄은 아래 norm 이 따로 넘긴다.
GRANTED = {
    # 9f test_operator_company 머리말 :1-2·:6·:21 과 ⑩ :424-440(뒤집기 — 거절 단언을 지우는 자리)
    "\"\"\"운영 관리자(kind admin, 회사 없음)가 작업 회사(하나뿐인 회사)로 하는 회사 업무를 앱 역할로 잰다(결정 MARC-ENT-374,",
    "밴드 OP1 §3-3). 보안 층.",
    "② 고객사 전용 10(사업장·인벤토리·기준 자료·영문번역 결과): 운영 관리자 403 forbidden, 회사 표·업무 표 읽기 0, 행 0.",
    "⑩ TR2: 영문번역 결과 운영 관리자 403 · 실행 만들기 module translation 운영 관리자 403(행 0).",
    "def test_the_operator_is_403_on_translation(owner: Owner, solo: int, fake: FakeStorage) -> None:",
    "from tests.security.test_translation import owner_done_translation, result_url",
    "operator, _ = operator_client(owner)",
    "run_id = owner_done_translation(owner, fake, solo)",
    "assert code(operator.get(result_url(run_id))) == (403, \"FORBIDDEN\")",
    "document_id = upload(operator, fake, owner)",
    "before = count(owner, \"run_runs\")",
    "\"/api/runs\", data={\"module\": \"translation\", \"documentId\": document_id}, content_type=\"application/json\"",
    "assert code(made) == (403, \"FORBIDDEN\")",
    "assert count(owner, \"run_runs\") == before",
    "assert customer_client(solo).get(result_url(run_id)).status_code == 200  # 짝: 고객사 사용자는 연다",
    "\"\"\"(K2b·MARC-ENT-374) 운영 관리자의 Bearer 로 회사 업무 18: 회사가 둘이라 작업 회사를 못 고른다 — 회사를 고르는 16",
    "은 400 company_ambiguous, 고르지 않는 둘(비교 501·기본 단어 200)은 회사와 상관없다. 회사 행을 읽지도 쓰지도",
    "\"\"\"(K2b·MARC-ENT-374) 운영 관리자의 Bearer 로 고객사 전용 10(사업장·인벤토리·기준 자료·영문번역 결과): 인증은 지나고",
    "\"translation_result_get\",  # TR2 — 영문번역 권한은 범위 밖(OP1 Q9)",
    "ⓒ 세션 없이 401, 운영 관리자 Bearer 403 `FORBIDDEN`(영문번역 결과는 고객사 전용 — OP1 Q9, MARC-ENT-374).",
    "def test_an_operator_bearer_is_403_forbidden_on_the_result(",
    "assert (response.status_code, response.json()[\"error\"][\"code\"]) == (403, \"FORBIDDEN\")",
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
  local all body ids names words msg
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
  names="$(for f in $all; do [ "$f" = "$E/core/permissions.py" ] && continue
    git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ '; done | grep -c -E '"(translation|greenwash)"')"
  echo "  회사 id 숫자 박기(더한 제품 줄) $ids · 모듈 이름 글자(permissions.py 밖 더한 제품 줄) $names · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$ids" -eq 0 ] && [ "$names" -eq 0 ] && [ "$words" = 0 ]
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
    esgapi/core esgapi/runs -m "not django_db") > "$log" 2>&1
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
    esgapi/runs esgapi/user esgapi/translation) > "$log" 2>&1
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
  [ "$code" -eq 0 ] && [ "${n:-0}" -eq "$WANT_SECURITY" ] && [ "${n:-0}" -ge "$BASE_SECURITY" ]
}

s10() {
  local log="$OUT/s10-planted.log" flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  OP2_OUT="$OUT" "$A/scripts/planted-breaks-OP2.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$CONTAINERS" = 1 ] || echo "  (컨테이너 층 없이 — 업무·보안 층만 걸린 파손은 셈 밖)"
  [ "$code" -eq 0 ] && { [ "$CONTAINERS" = 0 ] || [ "$(tail -1 "$log")" = "PLANTED=$WANT_PLANTED/$WANT_PLANTED" ]; }
}

step 1 "바뀐 경로가 §1-2·§1-4·§1-5 안(outside=0)" s1
step 2 "0줄 목록 diff 0 · test_each_route_checks_its_own_operation_id_first 몸 그대로" s2
step 3 "9f·21 줄 numstat·- 줄 원문(허락한 꼴뿐)" s3
step 4 "더한 제품 줄에 회사 id 숫자 박기 0 · 모듈 이름 글자 0(permissions.py 밖) · 실재 기업명 0" s4
step 5 "lint-imports 전부 KEPT(17)" s5
step 6 "순수 층 core·runs 초록, 수(직렬)" s6
step 7 "generated/ 다시 뽑아 cmp 0바이트" s7
step 8 "verify.sh --fast" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무 층 core·runs·user·translation" s9_business
  step 9 "보안 층 tests/security" s9_security
else
  not_run 9 "컨테이너 층(업무·보안)" "--with-containers 없음"
fi
step 10 "심은 파손" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
