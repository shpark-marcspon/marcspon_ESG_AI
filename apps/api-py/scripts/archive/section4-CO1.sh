#!/usr/bin/env bash
# 밴드 CO1(MARC-TICK-227: core 검사 빈틈 — AI 설정 받기의 도구 고리·경로 없음·웹 검색 고정·출력 상한 client 대조
# MARC-ISSUE-248·결정 MARC-ENT-372 · core 업무 이름 목록을 계약에서 MARC-ISSUE-247)의 §4 자기검증(발주서
# band-handoffs/CO1-order.md §4). 틀은 section4-AS1.sh(순수 받기 규칙)·section4-OP2.sh(--commit·--with-containers)다.
#   사용: apps/api-py/scripts/section4-CO1.sh --commit <1|2> [--with-containers] [--step <n>]
#   --commit 1 = 248(받기 갈래 셋·key 중복·view 같음·unusable_routes + 그린워싱 dd 시험 둘, PLANTED 12 — 1~12)
#   --commit 2 = + 247(이름 검사의 목록을 .importlinter 계약 가·차에서, PLANTED 15 — + 13~15)
#   --with-containers 면 단계 9(그린워싱 감시 업무 층 — ① 만)를 돈다. ① 에서 없으면 「안 돌림」(EXIT=1 로 센다),
#   ② 는 컨테이너 0(단계 9 는 셈 밖).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 전량은 감독 몫). AI 공급사 호출 0(env -u 키).
# 컨테이너: 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 postgres 만(MARC-ENT-241 문 — 아래 gate).
# 환경 변수: CO1_OUT(로그 자리, 기본 워크트리 곁의 CO1.out — 심은 파손에도 넘긴다), CO1_FORBIDDEN(실재 기업명 낱말 파일,
#   기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
OUT="${CO1_OUT:-$ROOT/../CO1.out}"
FORBIDDEN="${CO1_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(71ba531)에서 잰 수 — 그 트리를 git archive 로 풀어 --collect-only.
#   순수 = pytest esgapi/{core,runs} -m "not django_db"(직렬) 1406
#   감시 = 그린워싱 AI 설정 시험 여섯(아래 WATCH): 업무 66 · 순수 38
# ① 기대: 순수 +61(core/tests/calc/test_ai_settings.py 133 → 194 — 옮긴 매개 둘은 새 시험 둘, 셈 0) · 감시 업무 +1
#   (test_a_route_missing_from_the_models_file_is_refused_not_500) · 감시 순수 +1(test_the_steps_have_no_unusable_route).
BASE_PURE=1406 BASE_WATCH_BUSINESS=66 BASE_WATCH_PURE=38
WANT1_PURE=1467 WANT_WATCH_BUSINESS=67 WANT_WATCH_PURE=39
# ② 기대(① 뒤): 순수 +4(core·runs 이름 검사에 각 둘 — 목록이 계약 가·차인지 · 목록 이름마다 양성 대조) · 컨테이너 0.
WANT2_PURE=1471
WATCH="esgapi/greenwash/tests/service/apis/test_ai_settings.py esgapi/greenwash/tests/service/apis/test_ai_settings_model.py
esgapi/greenwash/tests/service/apis/test_ai_settings_prompt_model.py esgapi/greenwash/tests/flows/test_binding_e0_settings.py
esgapi/greenwash/tests/flows/test_binding_e0_settings_runs.py esgapi/greenwash/tests/flows/test_prompt_model_e0.py"
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
  1) WANT_PURE=$WANT1_PURE WANT_PLANTED=12 ;;
  2) WANT_PURE=$WANT2_PURE WANT_PLANTED=15 ;;
  *) echo "사용: $0 --commit <1|2> [--with-containers] [--step <n>]" >&2; exit 2 ;;
esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 CO1 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-2(줄기) + 개정 1(critic B1 — 꼴 시험 고정물) + §1-4(그린워싱 dd 허락, 더하기만) — 닫힌 목록
ALLOWED="^$E/core/calc/ai_settings\.py\$
^$E/core/tests/calc/test_ai_settings\.py\$
^$E/core/tests/contracts/test_ai_setting_shapes\.py\$
^$E/core/tests/test_flows_core_names\.py\$
^$E/runs/tests/test_names\.py\$
^$A/scripts/(section4|planted-breaks)-CO1\.sh\$
^$E/greenwash/tests/service/apis/test_ai_settings_model\.py\$
^$E/greenwash/tests/flows/test_prompt_model_e0\.py\$"

# §4-2 0줄 목록(글롭은 git 경로 마법). esgapi/greenwash 는 dd 시험 둘 밖, runs 는 tests/test_names.py 밖.
ZERO="apps/web $A/generated :(glob)**/migrations/** :(glob)**/models.py $E/core/contracts $E/core/llm $E/translation
$E/dataverify $A/.importlinter $A/tests :(glob)**/conftest.py $A/scripts/planted-breaks.sh
:(exclude)$E/greenwash/tests/service/apis/test_ai_settings_model.py :(exclude)$E/greenwash/tests/flows/test_prompt_model_e0.py
$E/greenwash :(exclude)$E/runs/tests/test_names.py $E/runs"

fn_sha() {  # <git 대상(기준 해시 또는 빈 값 = 작업 트리)> — ai_settings.py 의 0줄 함수 넷 몸의 ast sha
  local f="$E/core/calc/ai_settings.py"
  { if [ -n "$1" ]; then git show "$1:$f"; else cat "$f"; fi; } | python3 -c '
import ast, hashlib, sys
tree = ast.parse(sys.stdin.read())
names = ("model_settings_sha256", "to_input", "route_choice", "prompt_entry")
found = {n.name: n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name in names}
print(hashlib.sha256("".join(ast.dump(found[n]) for n in names).encode()).hexdigest())'
}

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

s2() {
  local bad a b
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  echo "  0줄 자리 · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  a="$(fn_sha "$BASE")"; b="$(fn_sha "")"
  echo "  model_settings_sha256·to_input·route_choice·prompt_entry 몸 ast sha <기준> ${a:0:12} · 지금 ${b:0:12}"
  [ -z "$bad" ] && [ -n "$a" ] && [ "$a" = "$b" ]
}

TESTS="$E/core/tests $E/runs/tests $E/greenwash/tests"

s3() {  # 시험 파일의 numstat · - 줄 원문 · 허락 밖의 지움(bad_minus) · 끄는 꼴
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $TESTS | sed 's/^/  /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $TESTS | python3 -c '
import re, sys
bad = total = 0
# 허락한 - 줄(앞뒤 빈칸 뺀 원문): 발주서 §1-3(머리말·고정물 spec()·옮긴 매개 둘·round trip 의 specs) · 개정 1(꼴 시험
# 고정물 — 차례 바꿈과 default) · §1-4(dd — import 줄만: isort 가 같은 모듈 import 를 한 줄로 묶는다) · §1-5(BUSINESS 두 줄).
GRANTED = {
    "실제 설정(synthetic=False)의 경로 여덟 능력, 시험이 지은 섞인 경로, 받기 차례 여섯과 그 순서, 호출 층",
    "(`_check_temperature`·`_check_tool_models`)과 같은 판정, 받은 값의 sha, 판정 상수를 import 하는지(AST).",
    "from esgapi.core.llm.types import WebSearchTool",
    "def spec(key: str = \"judge\", routes: tuple[str, ...] = tuple(CAPABILITIES), *, tool_loop: bool = True) -> AiStepSpec:",
    "return AiStepSpec(key=key, label=key, routes=routes, tool_loop=tool_loop, default=step(key))",
    "pytest.param(step(route=\"standard-openai-41\", webSearch=True), \"accepted\", id=\"web-search-accepted\"),",
    "specs = (spec(\"detect\"), spec(\"judge\"))",
    "pytest.param(step(route=\"standard-openai-41\", webSearch=True), id=\"web-search\"),",
    "default=cast(\"Any\", None),",
    "model = step[\"model\"]",
    "given: Any = {\"steps\": [{\"key\": step[\"key\"], **{k: model[k] for k in model if k != \"models\"}}]}",
    "from esgapi.core.llm.config import default_config_sources, load_config",
    "from esgapi.core.models import AuditEventRow",
    "from esgapi.greenwash.flows import prompt_model_e0",
    "from tests.support.http import bearer, bearer_pair",
    "BUSINESS = (\"organization\", \"user\", \"inventory\", \"reference\", \"reconcile\", \"greenwash\", \"translation\", \"runs\")",
    "BUSINESS = (\"organization\", \"user\", \"inventory\", \"reference\", \"reconcile\", \"greenwash\", \"dataverify\", \"translation\")",
}
DISABLERS = re.compile(r"\bor True\b|\bif False\b|pytest\.skip|xfail|# noqa|type: ignore")
disabled = 0
file = None
minus, plus = [], []

def flush():
    global bad, total, minus, plus
    for m in minus:
        total += 1
        print(f"    - {file}: {m}")
        stripped = m.strip()
        if stripped in GRANTED or any(stripped == p.strip() for p in plus):
            continue  # 허락한 줄, 또는 그대로 옮긴 줄
        bad += 1
        print("      ★ 허락 밖의 지움")
    minus, plus = [], []

for raw in sys.stdin:
    line = raw.rstrip("\n")
    if line.startswith("diff --git"):
        flush()
        file = line.split(" b/", 1)[1]
    elif line.startswith("@@"):
        continue  # 덩이를 넘어 견준다(옮긴 줄)
    elif line.startswith("-") and not line.startswith("---"):
        minus.append(line[1:])
    elif line.startswith("+") and not line.startswith("+++"):
        plus.append(line[1:])
        if DISABLERS.search(line[1:]) and not line[1:].lstrip().startswith("#"):
            disabled += 1
            print(f"    ★ 끄는 꼴: {file}: {line[1:]}")
flush()
print(f"  - 줄 {total} · bad_minus={bad} · 끄는 꼴(or True·if False·skip·xfail·noqa·type: ignore) {disabled}")
sys.exit(1 if bad or disabled else 0)
'
}

s4() {  # ai_settings.py 의 "openai" 글자 하나 · 실재 기업명 0(더한 줄·새 파일·커밋 메시지)
  local openai words msg
  openai="$(grep -o '"openai"' "$E/core/calc/ai_settings.py" | grep -c .)"
  msg="$(git log --format=%B "$BASE..HEAD")"
  if [ -f "$FORBIDDEN" ]; then
    words="$(printf '%s\n%s\n' "$(git diff "$BASE" | grep -E '^\+' | grep -v -E '^\+\+\+ '; git ls-files -o --exclude-standard --full-name | while read -r f; do cat "$f"; done)" "$msg" | grep -c -i -F -f "$FORBIDDEN")"
  else
    words="파일 없음"
  fi
  echo "  ai_settings.py \"openai\" 글자 $openai(1 이어야) · 실재 기업명(더한 줄·커밋 메시지) $words"
  [ "$openai" = 1 ] && [ "$words" = 0 ]
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
  local log="$OUT/s6-pure.log" wlog="$OUT/s6-watch-pure.log" code wcode total wtotal
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core esgapi/runs -m "not django_db") > "$log" 2>&1
  code=$?
  # shellcheck disable=SC2086
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    -m "not django_db" $WATCH) > "$wlog" 2>&1
  wcode=$?
  total="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  wtotal="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$wlog" | tail -1)"
  tail -1 "$log" | sed 's/^/  /'
  tail -1 "$wlog" | sed 's/^/  /'
  echo "  순수 core·runs 기준 $BASE_PURE → 지금 ${total:-?}(기대 $WANT_PURE) · 감시 순수 $BASE_WATCH_PURE → ${wtotal:-?}(기대 $WANT_WATCH_PURE)"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq "$WANT_PURE" ] && [ "$wcode" -eq 0 ] && [ "${wtotal:-0}" -eq "$WANT_WATCH_PURE" ]
}

s7() {  # generated/ 다시 뽑아 cmp — 0바이트
  local d="$OUT/s7-generated" code
  mkdir -p "$d"
  (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python \
    manage.py export_openapi > "$d/openapi.json" 2> "$d/export.err")
  code=$?
  [ "$code" = 0 ] || { tail -3 "$d/export.err"; return "$code"; }
  cmp "$d/openapi.json" "$A/generated/openapi.json" && echo "  openapi.json 같음 · generated/ diff $(git diff --name-only "$BASE" -- "$A/generated" | grep -c .)" \
    "· apps/web·generated 의 AI_MODEL_ 글자 $(git grep -n 'AI_MODEL_' -- apps/web "$A/generated" | grep -c .)"
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

s9_watch() {
  local log="$OUT/s9-watch-business.log" code n
  gate || return 1
  docker compose up -d --wait postgres > "$OUT/s9-up-postgres.log" 2>&1 || { tail -3 "$OUT/s9-up-postgres.log"; return 1; }
  # shellcheck disable=SC2086
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider -n 4 $WATCH) > "$log" 2>&1
  code=$?
  tail -1 "$log" | sed 's/^/  /'
  n="$(sed -n -E 's/^([0-9]+) passed.*/\1/p' "$log" | tail -1)"
  echo "  감시 업무 층 수 ${n:-?}(기준 $BASE_WATCH_BUSINESS · 기대 $WANT_WATCH_BUSINESS)"
  [ "$code" -eq 0 ] && [ "${n:-0}" -eq "$WANT_WATCH_BUSINESS" ]
}

s10() {
  local log="$OUT/s10-planted.log" flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  # shellcheck disable=SC2086
  CO1_OUT="$OUT" "$A/scripts/planted-breaks-CO1.sh" --commit "$COMMIT" $flag > "$log" 2>&1
  local code=$?
  grep -E '^\[|^    FAILED|^P0|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "PLANTED=$WANT_PLANTED/$WANT_PLANTED" ]
}

step 1 "바뀐 경로가 §1-2·개정 1·§1-4 안(outside=0)" s1
step 2 "0줄 목록 diff 0 · sha·to_input·route_choice·prompt_entry 몸 그대로" s2
step 3 "시험 파일 numstat·- 줄 원문(허락한 꼴뿐)·끄는 꼴 0" s3
step 4 "ai_settings.py \"openai\" 글자 하나 · 실재 기업명 0" s4
step 5 "lint-imports 전부 KEPT(17)" s5
step 6 "순수 층 core·runs 초록, 수(직렬) · 감시 순수" s6
step 7 "generated/ 다시 뽑아 cmp 0바이트" s7
step 8 "verify.sh --fast" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "그린워싱 감시 업무 층" s9_watch
elif [ "$COMMIT" = 1 ]; then
  not_run 9 "그린워싱 감시 업무 층" "--with-containers 없음"
else
  echo "[9] 그린워싱 감시 업무 층 — ② 는 컨테이너 0(셈 밖)"
fi
step 10 "심은 파손 PLANTED=$WANT_PLANTED/$WANT_PLANTED" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
