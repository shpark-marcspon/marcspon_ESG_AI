#!/usr/bin/env bash
# 밴드 K2a(MARC-TICK-97: username·비밀번호 → JWT(access 30분·refresh 7일 rotate), 5회 실패 10분 잠금, 첫 로그인 비밀번호
# 바꾸기, 역할 둘(운영 관리자·고객사 사용자)과 「동작 → 필요한 것」 권한 표, 부트스트랩 명령 둘)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-K2a.sh --step <0~5>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-K2a.sh --pure            --step 5 전부 + 심은 파손의 순수 몫
#         apps/api-py/scripts/section4-K2a.sh --containers      업무·보안·통합 층 한 번 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-K2a.sh --after-commit    --step 5 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. 네트워크는 uv·docker·pnpm 의 설치뿐이다. 비밀번호·토큰 글자를 찍지 않는다.
# bash 전용이다(${PIPESTATUS[0]}). git grep -E 에 \s 를 쓰지 않는다([[:space:]]).
#
# ★ 기준 둘: B = 발주서의 바닥(054812c, K1u-a 병합 — 수의 출처), W = 이 가지가 갈라진 자리(7a8d21e = 054812c + G1c·FW1b.
#   닫힌 목록 파일의 diff 0 — 감독 덧붙임 「바닥 확정」). 파일·노드·openapi 의 diff 는 W 로 잰다(G1c 의 노드 38·openapi 더함이
#   B 대비로 섞이지 않게). 순수 층의 수는 W 의 수(2,097 = 2,059 + G1c 38)에서 센다.
# ★ 컨테이너 층에 들어가기 전 문(발주서 a-1-1, 사용자 결정 2026-10-15 밤): 자기 밖 esg-app* compose 프로젝트 둘 이하,
#   빌드 중인 것 0, 메모리 free 20% 이상, 1분 부하 24 미만. 60초 간격, 최대 30분.
# ★ 코드의 셈은 AST 로 한다(글자 셈은 docstring 을 문다).
set -u
cd "$(dirname "$0")/../../.."
B=054812c   # 발주서의 바닥(개정 4): 수의 출처
W=7a8d21e   # 이 가지가 갈라진 자리: 파일·노드·openapi diff 의 기준
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
export LC_ALL=C   # sort 와 diff 가 같은 차례를 쓴다
MODE="${1:-}"
STEP=5
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-5]) ;; *) echo "사용: $0 --step <0~5>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~5> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
ROOT="$(pwd)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
E="$A/esgapi"
TEST_DS=esgapi.config.settings.test_business
export A E B W T TEST_DS STEP ROOT

# 층마다의 수(W 의 수집: 순수 2,097 · 업무 419 · 보안 107). 커밋마다 정해진 이름만 늘고 준다(나.).
PURE_AT=(2097 2103 2180 2195 2196 2196)   # ① +6: 표 칸 단언 넷 −옛 둘, 교환 권한 매개변수 3 → 6 · ② +77: 토큰·주체·잠금 규칙·격리 검사·만들기 검사 · ③ +15: Bearer 13·자기 칸 1·444 계약 1 · ④ +1: create_operator 의 자리
BUSINESS_AT=(419 419 487 513 527 527)   # ② +68: 로그인·잠금·refresh·바꾸기·초기화·만들기·입구 · ③ +26: 경로 24·자기 칸 배선 2 · ④ +14: 명령 둘
SECURITY_AT=(107 107 107 109 109 127)   # ③ +2: test_without_a_session_it_is_401 의 bearer 둘 · ⑤ +18: test_login 10·test_refresh 7·test_owner 1
INTEGRATION=21   # 통합 층 수(test_flow.py 는 :91-93 두 줄만 고친다 — 노드 그대로)
PURE="${PURE_AT[$STEP]}"; BUSINESS="${BUSINESS_AT[$STEP]}"; SECURITY="${SECURITY_AT[$STEP]}"
export PURE BUSINESS SECURITY
PURE_PLANTED="8/8"; CONTAINER_PLANTED="15/15"   # planted-breaks-K2a.sh 의 순수 몫·컨테이너 몫(⑤ 에서 정한다)
export PURE_PLANTED CONTAINER_PLANTED

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일 + 지운 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --no-renames --name-only "$W"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 a-1-2 의 닫힌 목록, 개정 4) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/auth/(__init__|tokens|principal|bearer)\.py$' \
    -e '^apps/api-py/esgapi/core/(permissions|exceptions|schemas)\.py$' \
    -e '^apps/api-py/esgapi/config/api\.py$' \
    -e '^apps/api-py/esgapi/core/service/apis/(documents|runs)\.py$' \
    -e '^apps/api-py/esgapi/user/models\.py$' \
    -e '^apps/api-py/esgapi/user/migrations/0002_refresh_tokens\.py$' \
    -e '^apps/api-py/esgapi/user/api\.py$' \
    -e '^apps/api-py/esgapi/user/service/apis/(auth|user|login)\.py$' \
    -e '^apps/api-py/esgapi/user/service/schemas/' \
    -e '^apps/api-py/esgapi/user/service/selectors/' \
    -e '^apps/api-py/esgapi/user/service/services/' \
    -e '^apps/api-py/esgapi/user/service/actions/(__init__|password)\.py$' \
    -e '^apps/api-py/esgapi/user/service/utils/' \
    -e '^apps/api-py/esgapi/user/management/(__init__|commands/(__init__|create_user|reset_password))\.py$' \
    -e '^apps/api-py/esgapi/user/tests/' \
    -e '^apps/api-py/esgapi/organization/service/(permissions|selectors|services)/organization\.py$' \
    -e '^apps/api-py/esgapi/organization/service/apis/organization\.py$' \
    -e '^apps/api-py/esgapi/organization/tests/' \
    -e '^apps/api-py/esgapi/config/tests/(test_api_contract|test_request_schemas_reject_bool)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_transaction_rules|test_selector_scope|test_permissions|test_permissions_wiring|test_documents_api)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/service/apis/test_runs\.py$' \
    -e '^apps/api-py/esgapi/core/tests/auth/(__init__|test_tokens|test_principal|test_bearer)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/isolation/test_static_rules\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/test_scope3_api\.py$' \
    -e '^apps/api-py/esgapi/greenwash/tests/test_contracts_gc1\.py$' \
    -e '^apps/api-py/tests/security/(test_login|test_refresh)\.py$' \
    -e '^apps/api-py/tests/security/(conftest|seed|test_tenant_paths|test_owner|test_migrations)\.py$' \
    -e '^apps/api-py/tests/support/(http|tokens)\.py$' \
    -e '^apps/api-py/tests_integration/test_flow\.py$' \
    -e '^apps/api-py/\.importlinter$' \
    -e '^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-K2a\.sh$'
}
# 컨테이너 앞의 문(발주서 a-1-1 의 규칙). 60초마다, 최대 30분.
gate() {
  local tries=0 free load others builds lock
  lock="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
  while :; do
    others="$(docker ps --format '{{.Labels}}' | grep -o 'com.docker.compose.project=esg-app[^,]*' | sort -u | grep -v -c -x "com.docker.compose.project=$PROJECT")"
    # 발주서의 pgrep 무늬는 다른 세션의 프롬프트 글자도 문다 — 실행 파일이 docker 인 줄만 센다.
    builds="$(pgrep -fl 'compose.*build|buildx|docker build' | awk '$2 ~ /docker/' | grep -c .)"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" -le 2 ] && [ "$builds" = 0 ] && [ ! -e "$lock" ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 다른 esg-app* 프로젝트 $others · 빌드 $builds · verify.lock 없음 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: 다른 프로젝트 $others · 빌드 $builds · free ${free:-?}% · 1분 부하 ${load:-?} · 30분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

echo "── 밴드 K2a §4 · $MODE${2:+ $2} · 바닥 $B · 갈라진 자리 $W · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음), 계약 여섯"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "$PURE passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'
  run '(cd "$A" && uv run --frozen python - <<"PY"
import configparser, os, sys
step = int(os.environ["STEP"])
c = configparser.ConfigParser(); c.read(".importlinter")
def lines(section, key):
    return {x.strip() for x in c[f"importlinter:contract:{section}"][key].splitlines() if x.strip() and not x.strip().startswith(";")}
pure = lines("pure-modules", "source_modules")
want = set()
if step >= 1: want.add("esgapi.core.auth.principal")
if step >= 2: want.add("esgapi.core.auth.tokens")
miss = want - pure
print(f"  계약 다 에 든 core.auth: {sorted(want - miss)} · 빠짐 {sorted(miss)}")
BEARER = "esgapi.core.auth.bearer"
print(f"  계약 다 에 bearer(ninja 를 앎)가 없다: {BEARER not in pure}")
sys.exit(1 if miss or "esgapi.core.auth.bearer" in pure else 0)
PY
)'
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; exit $code)'

  echo; echo "── 다. generated: 코드에서 다시 뽑은 openapi 가 커밋된 파일과 바이트 동일, W 대비 diff 는 「generated 에 더해지는 것 — K2a」뿐(③ 뒤), apps/web 0줄"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'
  run 'git diff --quiet "$W" -- apps/web && test -z "$(git ls-files --others --exclude-standard -- apps/web)"'
  run 'git show "$W:$A/generated/openapi.json" > "$T/openapi-base.json"; python3 -I - "$T/openapi-base.json" "$A/generated/openapi.json" <<"PY"
import json, os, sys
step = int(os.environ["STEP"])
base = json.load(open(sys.argv[1])); now = json.load(open(sys.argv[2]))
diffs = []
def walk(a, b, path):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b)):
            if k not in a: diffs.append(("더함", path + [k], b[k]))
            elif k not in b: diffs.append(("뺌", path + [k], a[k]))
            else: walk(a[k], b[k], path + [k])
    elif a != b:
        diffs.append(("바뀜", path, (a, b)))
walk(base, now, [])
NEW_PATHS = {"/auth/login": ("post", "user_auth_login"), "/auth/refresh": ("post", "user_auth_refresh"),
             "/auth/revoke": ("post", "user_auth_revoke"), "/users/me": ("get", "user_me"),
             "/users/me/password": ("post", "user_password_change")}
NEW_SCHEMAS = {"LoginIn", "RefreshIn", "TokenPairOut", "UserMeOut", "PasswordChangeIn"}
TOKEN_TAKERS = {"user_auth_refresh", "user_auth_revoke", "user_me", "user_password_change"}
OID = "operationId"
want = set()
if step >= 3:
    want = {("paths", p) for p in NEW_PATHS} | {("components", "schemas", s) for s in NEW_SCHEMAS} | {("components", "securitySchemes", "AccessTokenAuth")}
got = set()
bad = 0
for kind, path, value in diffs:
    key = tuple(path)
    print("  ", kind, "/".join(path), json.dumps(value, ensure_ascii=False)[:120])
    if kind != "더함": bad = 1; continue
    got.add(key)
SLASH = "/"
print(f"  diff {len(diffs)}개 · 더함 자리 {sorted(SLASH.join(k) for k in got)}")
bad |= got != want
if step >= 3:
    ops = {(m, op["operationId"]): (p, op) for p, item in now["paths"].items() for m, op in item.items()}
    with444 = {op["operationId"] for p, item in now["paths"].items() for m, op in item.items() if "444" in op.get("responses", {})}
    print(f"  444 를 선언한 동작: {sorted(with444)} (기대 {sorted(TOKEN_TAKERS)})")
    bad |= with444 != TOKEN_TAKERS
    for p, (m, oid) in NEW_PATHS.items():
        op = now["paths"].get(p, {}).get(m, {})
        sec = op.get("security")
        want_sec = [{"AccessTokenAuth": []}] if oid in {"user_me", "user_password_change"} else None
        ok = op.get("operationId") == oid and sec == want_sec
        mark = "" if ok else "★"
        print(f"  {m.upper()} {p}: operationId {op.get(OID)} · security {sec} {mark}")
        bad |= not ok
    scheme = now["components"]["securitySchemes"].get("AccessTokenAuth")
    print(f"  AccessTokenAuth = {scheme}")
    bad |= now["components"]["securitySchemes"].get("AccessTokenAuth") != {"type": "http", "scheme": "bearer"}
sys.exit(1 if bad else 0)
PY'
  run 'test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3; if [ "$STEP" -lt 3 ]; then git diff --quiet "$W" -- "$A/generated"; else test "$(cat "$A/generated/api.d.ts.source-sha256" | cut -d" " -f1)" = "$(sha "$A/generated/openapi.json")"; fi'

  echo; echo "── 라. 마이그레이션(makemigrations 가 낼 것 없음, user 에 0002_refresh_tokens 하나 더함, 나머지 0줄)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'git diff --quiet "$W" -- "$E/user/migrations/0001_initial.py" "$E/core/migrations" "$E/organization/migrations" "$E/reference/migrations" && got="$(cd "$E/user/migrations" && ls *.py | tr "\n" " ")"; echo "  user/migrations: $got"; if [ "$STEP" -ge 2 ]; then [ "$got" = "0001_initial.py 0002_refresh_tokens.py __init__.py " ]; else [ "$got" = "0001_initial.py __init__.py " ]; fi'

  echo; echo "── 마. 경계(닫힌 목록, 지운 파일 0, 다른 감독의 파일은 정해진 줄만)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'd="$(git diff --no-renames --name-only --diff-filter=D "$W" | wc -l | tr -d " ")"; echo "  지운 파일: $d"; [ "$d" = 0 ]'
  run 'git diff --quiet "$W" -- "$E/core/tenancy" "$E/core/isolation" "$E/core/observability" "$E/core/models.py" "$E/config/settings" "$E/config/env.py" "$E/core/conf.py" "$E/reconcile" "$E/user/service/utils/tokens.py" "$A/pyproject.toml" "$A/uv.lock" compose.yaml .env.example scripts README.md'
  # 기대(뺀 줄:더한 줄): exceptions.py 는 ErrorKind 한 줄을 갈음(ruff format 이 한 줄을 여러 줄로 편다 — 뺀 줄 1 만 본다),
  # api.py 는 HTTP_STATUS 에 444 한 줄, schemas.py 는 TOKEN_… 두 줄.
  run 'for f in "$E/core/exceptions.py:1:" "$E/config/api.py:0:1" "$E/core/schemas.py:0:2"; do p="${f%%:*}"; rest="${f#*:}"; wm="${rest%%:*}"; wp="${rest#*:}"; [ "$STEP" -lt 3 ] && { wm=0; wp=0; }; m="$(git diff -U0 "$W" -- "$p" | grep -c -E "^-[^-]")"; a="$(git diff -U0 "$W" -- "$p" | grep -c -E "^\+[^+]")"; echo "  $p: 뺀 줄 $m · 더한 줄 $a (기대 $wm · ${wp:-여럿})"; [ "$m" = "$wm" ] || exit 1; [ -z "$wp" ] || [ "$a" = "$wp" ] || exit 1; done'
  run 'g="$(git diff --no-renames --name-only "$W" -- "$E/greenwash"; git ls-files --others --exclude-standard -- "$E/greenwash")"; echo "  greenwash 의 바뀐 파일: ${g:-없음}"; [ -z "$g" ] || [ "$g" = "$E/greenwash/tests/test_contracts_gc1.py" ]'
  run 'h="$(git diff -U0 "$W" -- "$E/organization/service/apis/organization.py" | grep -c "^@@")"; echo "  organization apis 의 덩어리: $h (기대 0 또는 1 — _forbidden)"; [ "$h" -le 1 ]; f="$(git diff --name-only "$W" -- "$A/tests_integration")"; out="$(git diff -U0 "$W" -- "$A/tests_integration" | sed -n "s/^@@ -\([0-9]*\).*/\1/p" | awk "\$1 < 91 || \$1 > 93")"; echo "  tests_integration 의 파일 ${f:-없음} · :91-93 밖에서 시작한 덩어리 ${out:-없음}"; [ -z "$out" ] && { [ -z "$f" ] || [ "$f" = "$A/tests_integration/test_flow.py" ]; }'

  echo; echo "── 바. 셈(제품 = esgapi 의 tests·migrations 밖, AST)"
  run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, os, pathlib, subprocess, sys
step = int(os.environ["STEP"])
base = os.environ["W"]
def is_atomic(node):
    f = node.func if isinstance(node, ast.Call) else node
    return isinstance(f, ast.Attribute) and f.attr == "atomic" and isinstance(f.value, ast.Name) and f.value.id == "transaction"
def counts(tree):
    blocks = durable = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            blocks += sum(is_atomic(item.context_expr) for item in node.items)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            blocks += sum(is_atomic(d) for d in node.decorator_list)
        if isinstance(node, ast.keyword) and node.arg == "durable" and isinstance(node.value, ast.Constant) and node.value.value is True:
            durable += 1
    return blocks, durable
def product(paths):
    return [p for p in paths if p.startswith("esgapi/") and p.endswith(".py") and "/tests/" not in p and "/migrations/" not in p]
now_paths = product([str(p) for p in pathlib.Path("esgapi").rglob("*.py")])
base_paths = product(subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "--", "."], capture_output=True, text=True, check=True).stdout.split())
def tally(paths, read):
    return {p: c for p in paths if any(c := counts(ast.parse(read(p))))}
now = tally(now_paths, lambda p: pathlib.Path(p).read_text(encoding="utf-8"))
was = tally(base_paths, lambda p: subprocess.run(["git", "show", f"{base}:apps/api-py/{p}"], capture_output=True, text=True, check=True).stdout)
bad = 0
for p in sorted(set(now) | set(was)):
    if now.get(p) != was.get(p):
        # 블록이 늘어도 되는 자리는 user 뿐이다(새 services·actions, services/user.py 의 만들기 둘 — 발주서 a-2-1 마)
        mark = "" if p.startswith("esgapi/user/") else "  ★ user 밖의 블록 수가 바뀜"
        print(f"  {p}: 기준 {was.get(p)} → 지금 {now.get(p)}{mark}")
        bad |= bool(mark)
dur = sum(v[1] for v in now.values()); print(f"  durable=True 합 {dur} (기대 3)"); bad |= dur != 3
trees = {p: ast.parse(pathlib.Path(p).read_text(encoding="utf-8")) for p in now_paths}
# 권한 표(①부터): 회사 23 = CUSTOMER, 자기 둘 = SELF(③부터), OPERATOR 0, proposed=True 는 inventory_scope3_classify 하나
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ["TEST_DS"])
if step >= 1:
    from esgapi.core import permissions as P
    cells = {}
    for op, pol in P.OPERATION_POLICY.items():
        cells.setdefault(pol.needs, set()).add(op)
    want_self = {"user_me", "user_password_change"} if step >= 3 else set()
    n_c, n_o, s_s = len(cells.get("customer", ())), len(cells.get("operator", ())), sorted(cells.get("self", ()))
    print(f"  표: customer {n_c} · operator {n_o} · self {s_s}")
    bad |= len(cells.get("customer", ())) != 23 or cells.get("operator", set()) != set() or cells.get("self", set()) != want_self
    proposed = sorted(op for op, pol in P.OPERATION_POLICY.items() if pol.proposed)
    print(f"  proposed=True: {proposed}"); bad |= proposed != ["inventory_scope3_classify"]
    level_hits = []
    for p in ("esgapi/core/permissions.py", "esgapi/organization/service/permissions/organization.py", "esgapi/core/auth/bearer.py"):
        if pathlib.Path(p).exists():
            for node in ast.walk(trees[p]):
                if isinstance(node, ast.Name) and node.id == "level" or isinstance(node, ast.Attribute) and node.attr == "level" or isinstance(node, ast.Constant) and node.value == "level":
                    level_hits.append(f"{p}:{node.lineno}")
    print(f"  권한 모듈의 level 글자: {level_hits} (기대 없음)"); bad |= bool(level_hits)
# User·Company 의 숨은 길 0, by_subdomain( 호출 자리 하나, 입구 호출 자리
calls = {}
hits = []
for p, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "unscoped":
            hits.append(f"{p}:{node.lineno} .unscoped")
        if isinstance(node, ast.Attribute) and node.attr == "objects" and isinstance(node.value, ast.Name) and node.value.id in {"User", "Company", "Site", "RefreshToken"}:
            hits.append(f"{p}:{node.lineno} {node.value.id}.objects")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"by_subdomain", "admin_by_username", "admin_by_id", "create_operator"}:
            if p not in {"esgapi/core/isolation/managers.py", "esgapi/organization/models.py", "esgapi/user/models.py"}:
                calls.setdefault(node.func.attr, set()).add(p)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "create_operator":
            calls.setdefault("create_operator", set()).add(p)
print(f"  숨은 길: {hits} (기대 없음)"); bad |= bool(hits)
for k in sorted(calls): print(f"  {k}( 의 자리: {sorted(calls[k])}")
bad |= calls.get("by_subdomain") != {"esgapi/organization/service/selectors/organization.py"}
if step >= 4:
    bad |= calls.get("create_operator") != {"esgapi/user/management/commands/create_user.py"}
# 설정 파일에 PASSWORD_HASHERS·AUTH_PASSWORD_VALIDATORS 글자 0
settings_hits = [str(p) for p in pathlib.Path("esgapi/config/settings").glob("*.py") if "PASSWORD_HASHERS" in p.read_text() or "AUTH_PASSWORD_VALIDATORS" in p.read_text()]
print(f"  설정의 PASSWORD_HASHERS·AUTH_PASSWORD_VALIDATORS: {settings_hits} (기대 없음)"); bad |= bool(settings_hits)
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 바(덧). 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$W" -- . ":!$A/scripts/section4-K2a.sh" ":!$A/scripts/planted-breaks-K2a.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-K2a\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+[^+].*($marks)|^\+($marks)" "$T/all.diff")"; minus="$(grep -c -E "^-[^-].*($marks)|^-($marks)" "$T/all.diff")"; echo "  더한 줄 $plus · 지운 줄 $minus (더한 쪽이 많으면 안 된다)"; grep -E "^\+[^+].*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" -le "$minus" ]'

  echo; echo "── 자. 비밀: diff·커밋 메시지에 JWT 꼴 글자·PBKDF2 해시 0(테스트 파일 안의 지어낸 것 밖)"
  run 'git diff "$W" -- . ":!$A/esgapi/*/tests/*" ":!$A/tests/*" ":!$A/tests_integration/*" ":!$A/scripts/section4-K2a.sh" > "$T/prod.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "/tests/|tests_integration/|section4-K2a\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/prod.diff"; j="$(grep -c -E "eyJ[A-Za-z0-9_-]{10,}\." "$T/prod.diff")"; h="$(grep -c -E "pbkdf2_sha256\\\$[0-9]+\\\$" "$T/prod.diff")"; m="$(git log --format=%B "$W"..HEAD | grep -c -E "eyJ[A-Za-z0-9_-]{10,}\.|pbkdf2_sha256\\\$[0-9]")"; echo "  제품 diff 의 JWT $j · 해시 $h · 커밋 메시지 $m"; [ "$j$h$m" = 000 ]'

  echo; echo "── 나. 수집: 사라진 노드가 발주서 a-3-1 의 이름과 글자로 같다(W 의 노드 ID 는 git archive 사본에서)"
  mkdir -p "$T/base"
  git archive "$W" "$A" | tar -x -C "$T/base"
  (cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt")
  (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt")
  comm -23 "$T/base-nodeids.txt" "$T/nodeids.txt" | sed 's/\[.*//' | sort -u > "$T/gone.txt"; comm -13 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/new.txt"
  expected_gone | sort > "$T/gone-expected.txt"
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · 사라진 이름 $(wc -l < "$T/gone.txt" | tr -d " ") · 새 노드 $(wc -l < "$T/new.txt" | tr -d " ")"; [ "$b" = 2623 ] && diff "$T/gone-expected.txt" "$T/gone.txt"'
  run '(cd "$A" && for m in "not django_db and not security" django_db security; do printf "  %-32s %s\n" "$m" "$(uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "$m" 2> /dev/null | grep -c "::")"; done) | tee "$T/layers.txt"; b="$(sed -n "2p" "$T/layers.txt" | awk "{print \$NF}")"; s="$(sed -n "3p" "$T/layers.txt" | awk "{print \$NF}")"; echo "  기대: 업무 $BUSINESS · 보안 $SECURITY"; [ "$b" = "$BUSINESS" ] && [ "$s" = "$SECURITY" ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫"
  if [ ! -x "$A/scripts/planted-breaks-K2a.sh" ]; then echo "★ planted-breaks-K2a.sh 가 없다(커밋 ⑤ 의 것)"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return; fi
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-K2a.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=$PURE_PLANTED" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
}

# 한 층을 돌리고 EXIT 를 찍는다. 끝 줄이 「<건수> passed」로 시작해야 한다. 다시 돌리지 않는다.
layer() { # <이름> <건수> <명령…>
  local name="$1" want="$2" code started=$SECONDS last
  shift 2
  echo; echo "▶ $*"
  "$@" > "$T/layer.txt" 2>&1; code=$?
  cp "$T/layer.txt" "$T/layer-$name.txt"
  tail -3 "$T/layer.txt"
  last="$(tail -1 "$T/layer.txt")"
  case "$last" in *"$want passed"*) ;; *) echo "★ 끝 줄에 「$want passed」가 없다"; code=1 ;; esac
  echo "$last" | grep -q -E "failed|error|skipped|xfail" && code=1
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/') · 기록 $T/layer-$name.txt)"
  if [ "$code" -ne 0 ]; then
    grep -E "^(FAILED|ERROR)" "$T/layer.txt" | head -30
    memory_pressure | grep percentage
    [ "$name" = "통합" ] && docker compose logs --no-color --tail 80 api-py migrate-py worker-py queue parser
  fi
}

containers_part() {
  echo; echo "── 아. 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh K2a 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test "$PROJECT" = esg-app-k2a'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'
  run 'n="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  이 프로젝트의 옛 볼륨 $n (볼륨은 새로)"; [ "$n" = 0 ]'
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  # K2A_LAYERS 로 다시 돌릴 층만 고를 수 있다(빨간 층만 다시 — 기본은 셋 다와 심은 파손).
  local only="${K2A_LAYERS:-업무 보안 통합 파손}"
  case " $only " in *" 업무 "*) layer "업무" "$BUSINESS" "$A/scripts/test-business.sh" -n 2 ;; esac
  case " $only " in *" 보안 "*) layer "보안" "$SECURITY" "$A/scripts/test-security.sh" ;; esac
  case " $only " in *" 통합 "*) layer "통합" "$INTEGRATION" "$A/scripts/test-integration.sh" -s ;; esac
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  run 'n="$(docker compose logs --no-color api-py worker-py | grep -c -E "eyJ[A-Za-z0-9_-]{10,}\.|pbkdf2_sha256")"; echo "  기록의 토큰·해시 꼴 줄: $n"; [ "$n" = 0 ]'
  if [ -x "$A/scripts/planted-breaks-K2a.sh" ] && case " $only " in *" 파손 "*) true ;; *) false ;; esac; then
    echo; echo "── 아(덧). 심은 파손의 컨테이너 몫"
    git status --porcelain > "$T/before-planted.txt"
    run '"$A/scripts/planted-breaks-K2a.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=$CONTAINER_PLANTED" && exit $code; exit 1'
    run 'git status --porcelain | diff - "$T/before-planted.txt"'
  fi
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT[-/]" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT[-/]")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 차. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$W"..HEAD --no-merges --first-parent; n="$(git log --format=%s --first-parent "$W"..HEAD | grep -v "^merge" | wc -l | tr -d " ")"; fixes="$(git log --format=%s --first-parent "$W"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 6'
  run 'bad=0; for c in $(git rev-list --no-merges --first-parent "$W"..HEAD); do for t in "Ticket: MARC-TICK-97" "Derives-from: MARC-ENT-137"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

# 사라지는 노드 이름(발주서 a-3-1 의 열 — 매개변수 꼬리는 떼고 견준다). 커밋마다 늘어난다.
expected_gone() {
  [ "$STEP" -ge 1 ] && cat <<'GONE'
esgapi/core/tests/service/apis/test_runs.py::test_a_viewer_cannot_create_a_run
esgapi/core/tests/test_documents_api.py::test_viewer_cannot_confirm
esgapi/core/tests/test_documents_api.py::test_viewer_cannot_create
esgapi/core/tests/test_permissions.py::test_the_message_names_the_needed_role
esgapi/core/tests/test_permissions.py::test_the_table_is_these_thirty_nine_cells
esgapi/greenwash/tests/test_contracts_gc1.py::test_a_viewer_reads_but_does_not_write
esgapi/inventory/tests/test_scope3_api.py::test_a_viewer_cannot_classify_and_nothing_is_called
esgapi/organization/tests/service/apis/test_organization.py::test_viewer_cannot_create_a_site
esgapi/organization/tests/service/services/test_organization.py::test_viewer_lists_but_cannot_create
esgapi/user/tests/service/utils/test_exchange.py::test_only_editor_and_above_create_sites
GONE
  return 0
}
export -f sha changed outside env_value expected_gone 2> /dev/null
case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --containers) containers_part ;;
  --after-commit) step_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (갈라진 자리 $W 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
