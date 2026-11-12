#!/usr/bin/env bash
# 밴드 K2c(MARC-TICK-97 의 c 부분: 운영 관리자 전용 GET /users·POST /users·POST /users/{user_id}/password-reset — 대상은
# 고른 회사(생략 = 하나뿐인 시드 회사)의 고객사 사용자, CustomerUserOut.isLocked)의 §4 자기검증. 틀은 section4-K2a.sh.
#   사용: apps/api-py/scripts/section4-K2c.sh --step <0~3>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-K2c.sh --pure            --step 3 전부 + 심은 파손의 순수 몫
#         apps/api-py/scripts/section4-K2c.sh --containers      업무·보안·통합 층 한 번 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-K2c.sh --after-commit    --step 3 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. 네트워크는 uv·docker·pnpm 의 설치뿐이다. 비밀번호·토큰 글자를 찍지 않는다.
# bash 전용이다(${PIPESTATUS[0]}). git grep -E 에 \s 를 쓰지 않는다([[:space:]]).
#
# ★ 커밋(발주서 c-2-0 에서 바꿈 — 표의 OPERATOR 칸은 계약(generated)의 동작과 한 커밋에 서야 test_permissions 가 초록):
#   ⓪ 이 스크립트 · ① K2a 검증 권고 1·2·4·5 · ② 권한·서명·경로 셋(발주서의 c①+c②) · ③ 보안 층·심은 파손
# ★ 기준 하나: B = 감독 덧붙임의 바닥(ee18aaa — K2a 병합 7b16ec5 위에 K1u-b 병합). 이 가지는 B 에서 갈라졌다(수·diff 모두 B).
# ★ 감독 처분(2026-10-16, marcspon-ad): 회사가 둘 이상인데 companyId 생략은 400 + code company_ambiguous(발주서 끝 처분 ②) —
#   core/exceptions.py·config/api.py 는 0줄. 발주서의 UserOut = CustomerUserOut(기존 UserOut 구성요소 0줄).
# ★ K2a 검증 권고 1~5(덧붙임 — 닫힌 목록에 더함): core/auth/tokens.py 의 _decode 한 자리(verify_iat), 그 테스트,
#   test_static_rules(QuerySet 생성자), test_documents_api(성공 코드), test_transaction_rules(블록 둘로 쪼갬).
# ★ 컨테이너 층에 들어가기 전 문(감독 덧붙임의 갈음 줄): 자기 밖 esg-app* compose 프로젝트 둘 이하,
#   빌드 중인 것 0, 메모리 free 20% 이상, 1분 부하 24 미만. 60초 간격, 최대 30분.
# ★ 코드의 셈은 AST 로 한다(글자 셈은 docstring 을 문다). 층의 끝 줄은 「<수> passed」로 줄 끝까지 견준다(권고 3).
set -u
cd "$(dirname "$0")/../../.."
B=ee18aaa   # 감독 덧붙임의 바닥: 수와 diff 의 기준
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
export LC_ALL=C   # sort 와 diff 가 같은 차례를 쓴다
MODE="${1:-}"
STEP=3
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-3]) ;; *) echo "사용: $0 --step <0~3>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~3> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
ROOT="$(pwd)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
E="$A/esgapi"
TEST_DS=esgapi.config.settings.test_business
export A E B T TEST_DS STEP ROOT

# 층마다의 수(B 의 수집: 순수 2,236 · 업무 540 · 보안 129 · 전체 2,905). 커밋마다 정해진 이름만 는다(나.).
PURE_AT=(2236 2239 2250 2250)   # ① +3: 권고 1(미래 시계의 토큰)·2(QuerySet 생성자)·5(블록 둘로 쪼갬) · ② +11: 표 넷(운영 관리자 칸·셋 같은 칸·안에서도·회사 고르기 자리)·user 권한 7
BUSINESS_AT=(540 540 559 560)   # ② +19: 배선 3(운영 관리자 칸)·경로 셋 16(test_users) · ③ +1: 회사 하나 + 없는 companyId(검증 권고 2)
SECURITY_AT=(129 129 132 139)   # ② +3: test_without_a_session_it_is_401 의 bearer 셋(사용자 관리) · ③ +7: test_user_admin
INTEGRATION=21   # 통합 층 수(K2c 는 tests_integration 0줄)
PURE="${PURE_AT[$STEP]}"; BUSINESS="${BUSINESS_AT[$STEP]}"; SECURITY="${SECURITY_AT[$STEP]}"
export PURE BUSINESS SECURITY
PURE_PLANTED="3/3"; CONTAINER_PLANTED="8/8"   # planted-breaks-K2c.sh 의 순수 몫(P10·P21·P22)·컨테이너 몫(P10c·P21s·P22s·P23h·P25·P26·P27·P29)
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
changed() { { git diff --no-renames --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 c-1-2 의 닫힌 목록 + 덧붙임의 K2a 검증 권고 몫) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/permissions\.py$' \
    -e '^apps/api-py/esgapi/core/auth/tokens\.py$' \
    -e '^apps/api-py/esgapi/user/service/permissions/' \
    -e '^apps/api-py/esgapi/user/service/(apis|schemas|selectors|services|actions)/' \
    -e '^apps/api-py/esgapi/user/management/commands/(create_user|reset_password)\.py$' \
    -e '^apps/api-py/esgapi/organization/models\.py$' \
    -e '^apps/api-py/esgapi/organization/service/selectors/' \
    -e '^apps/api-py/esgapi/user/tests/' \
    -e '^apps/api-py/esgapi/organization/tests/' \
    -e '^apps/api-py/esgapi/config/tests/(test_api_contract|test_request_schemas_reject_bool)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_transaction_rules|test_permissions|test_permissions_wiring|test_documents_api)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/auth/test_tokens\.py$' \
    -e '^apps/api-py/esgapi/core/tests/isolation/test_static_rules\.py$' \
    -e '^apps/api-py/tests/security/(test_user_admin|seed|test_tenant_paths)\.py$' \
    -e '^apps/api-py/tests/security/test_login\.py$' \
    -e '^apps/api-py/tests/support/http\.py$' \
    -e '^apps/api-py/\.importlinter$' \
    -e '^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-K2c\.sh$'
}
# 컨테이너 앞의 문(덧붙임의 갈음 줄). 60초마다, 최대 30분.
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

echo "── 밴드 K2c §4 · $MODE${2:+ $2} · 바닥 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음), 계약 여섯"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; echo "$last" | grep -q -E "^=* ?$PURE passed, [0-9]+ deselected in [0-9.]+s( \([0-9:]+\))? ?=*$" || exit 1; exit $code)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'
  run '(cd "$A" && uv run --frozen python - <<"PY"
import configparser, os, sys
step = int(os.environ["STEP"])
c = configparser.ConfigParser(); c.read(".importlinter")
def lines(section, key):
    return {x.strip() for x in c[f"importlinter:contract:{section}"][key].splitlines() if x.strip() and not x.strip().startswith(";")}
pure = lines("pure-modules", "source_modules")
want = "esgapi.user.service.permissions"
has = want in pure
print(f"  계약 다 에 {want}: {has} (기대 {step >= 2})")
sys.exit(0 if has == (step >= 2) else 1)
PY
)'
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; exit $code)'

  echo; echo "── 다. generated: 코드에서 다시 뽑은 openapi 가 커밋된 파일과 바이트 동일, B 대비 diff 는 「generated 에 더해지는 것 — K2c」뿐(② 뒤), apps/web 0줄"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'
  run 'git diff --quiet "$B" -- apps/web && test -z "$(git ls-files --others --exclude-standard -- apps/web)"'
  run 'git show "$B:$A/generated/openapi.json" > "$T/openapi-base.json"; python3 -I - "$T/openapi-base.json" "$A/generated/openapi.json" <<"PY"
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
NEW_OPS = {("/users", "get"): "user_list", ("/users", "post"): "user_create",
           ("/users/{user_id}/password-reset", "post"): "user_password_reset"}
OID = "operationId"; SEC = "security"; MARK = {True: "", False: " ★"}
NEW_SCHEMAS = {"CustomerUserOut", "UserPageOut", "UserCreateIn", "PasswordResetIn"}
TOKEN_TAKERS = {"user_auth_refresh", "user_auth_revoke", "user_me", "user_password_change", *NEW_OPS.values()}
want = set()
if step >= 2:
    want = {("paths", "/users"), ("paths", "/users/{user_id}/password-reset")} | {("components", "schemas", s) for s in NEW_SCHEMAS}
got = set()
bad = 0
for kind, path, value in diffs:
    print("  ", kind, "/".join(path), json.dumps(value, ensure_ascii=False)[:120])
    if kind != "더함": bad = 1; continue
    got.add(tuple(path))
SLASH = "/"
print(f"  diff {len(diffs)}개 · 더함 자리 {sorted(SLASH.join(k) for k in got)}")
bad |= got != want
if step >= 2:
    with444 = {op["operationId"] for p, item in now["paths"].items() for m, op in item.items() if "444" in op.get("responses", {})}
    print(f"  444 를 선언한 동작 {len(with444)}: {sorted(with444)}")
    bad |= with444 != TOKEN_TAKERS
    with422 = sorted(op["operationId"] for p, item in now["paths"].items() for m, op in item.items() if "422" in op.get("responses", {}))
    print(f"  422 를 선언한 동작: {with422} (기대 없음 — 감독 처분: 400 company_ambiguous)")
    bad |= bool(with422)
    for (p, m), oid in NEW_OPS.items():
        op = now["paths"].get(p, {}).get(m, {})
        codes = sorted(op.get("responses", {}))
        ok = op.get("operationId") == oid and op.get("security") == [{"AccessTokenAuth": []}]
        print(f"  {m.upper()} {p}: operationId {op.get(OID)} · security {op.get(SEC)} · 응답 {codes}{MARK[ok]}")
        bad |= not ok
    params = {x["name"]: x.get("required", False) for x in now["paths"]["/users"]["get"].get("parameters", [])}
    print(f"  GET /users 의 쿼리: {params}")
    bad |= params != {"companyId": False, "limit": False, "offset": False}
    out = now["components"]["schemas"]["CustomerUserOut"]["properties"]
    print(f"  CustomerUserOut 칸: {sorted(out)}")
    bad |= set(out) != {"id", "companyId", "username", "name", "isActive", "isInitial", "isLocked", "branchId", "lastLoginAt"}
    bad |= now["components"]["schemas"]["UserOut"] != base["components"]["schemas"]["UserOut"]
sys.exit(1 if bad else 0)
PY'
  run 'test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3; if [ "$STEP" -lt 2 ]; then git diff --quiet "$B" -- "$A/generated"; else test "$(cat "$A/generated/api.d.ts.source-sha256" | cut -d" " -f1)" = "$(sha "$A/generated/openapi.json")"; fi'

  echo; echo "── 라. 마이그레이션 0(makemigrations 가 낼 것 없음, migrations 폴더 diff 0)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'git diff --quiet "$B" -- $(cd "$ROOT" && ls -d "$E"/*/migrations) && test -z "$(git ls-files --others --exclude-standard -- "$E" | grep /migrations/)"'

  echo; echo "── 마. 경계(닫힌 목록, 지운 파일 0, core/auth 는 tokens.py 의 _decode 한 자리, exceptions·api·schemas 0줄)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'd="$(git diff --no-renames --name-only --diff-filter=D "$B" | wc -l | tr -d " ")"; echo "  지운 파일: $d"; [ "$d" = 0 ]'
  run 'git diff --quiet "$B" -- "$E/core/exceptions.py" "$E/config/api.py" "$E/core/schemas.py" "$E/core/auth/principal.py" "$E/core/auth/bearer.py" "$E/core/auth/__init__.py" "$E/user/models.py" "$E/core/tenancy" "$E/core/isolation" "$E/organization/service/apis" "$E/organization/service/permissions" "$E/config/settings" "$E/config/env.py" "$E/core/conf.py" "$A/pyproject.toml" "$A/uv.lock" compose.yaml .env.example scripts README.md'
  # core/auth/tokens.py: 바뀌어도 되는 것은 _decode 의 몸 하나(권고 1 — 덧붙임의 어긋남 풀이). 덩어리가 그 함수 안에서만.
  run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, os, subprocess, sys
p = "esgapi/core/auth/tokens.py"
old = subprocess.run(["git", "show", f"{os.environ["B"]}:apps/api-py/{p}"], capture_output=True, text=True, check=True).stdout
new = open(p, encoding="utf-8").read()
def bodies(src):
    tree = ast.parse(src)
    return {n.name: ast.dump(n) for n in tree.body if isinstance(n, ast.FunctionDef | ast.ClassDef)}, [ast.dump(n) for n in tree.body if not isinstance(n, ast.FunctionDef | ast.ClassDef)]
(o, orest), (n, nrest) = bodies(old), bodies(new)
changed = sorted(k for k in set(o) | set(n) if o.get(k) != n.get(k))
print(f"  tokens.py 에서 바뀐 정의: {changed} · 그 밖의 문장 바뀜: {orest != nrest}")
sys.exit(0 if set(changed) <= {"_decode"} and orest == nrest else 1)
PY
)'

  # 감독 허락(2026-10-16): K2a 의 시드 도우미 두 줄은 create_customer_user 호출에 actor_kind="admin" 한 키워드만(ruff 가 줄을 편 것 밖 0),
  # test_login 은 그 밖에 url_of 와 test_an_initial_user_reaches_only_the_allowed_operations(수 25→28·23→26, 사용자 관리 셋 403)만.
  run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, os, subprocess, sys
bad = 0
base = os.environ["B"]
for p in ("tests/security/test_login.py", "tests/support/http.py"):
    old = subprocess.run(["git", "show", f"{base}:apps/api-py/{p}"], capture_output=True, text=True, check=True).stdout
    new = open(p, encoding="utf-8").read()
    old = old.replace("create_customer_user(company_id=", "create_customer_user(actor_kind=\"admin\", company_id=")
    # test_login 은 감독 허락(2026-10-16)으로 두 정의(url_of·test_an_initial_user_reaches_only_the_allowed_operations)도 고친다
    allowed = {"url_of", "test_an_initial_user_reaches_only_the_allowed_operations"} if p.endswith("test_login.py") else set()
    def defs(src):
        return {n.name if isinstance(n, ast.FunctionDef | ast.ClassDef) else f"#{i}": ast.dump(n) for i, n in enumerate(ast.parse(src).body)}
    o, n = defs(old), defs(new)
    changed = sorted(k for k in set(o) | set(n) if o.get(k) != n.get(k))
    ok = set(changed) <= allowed
    print(f"  {p}: 바뀐 정의 {changed} (허락 {sorted(allowed)})")
    print(f"  {p}: actor_kind 한 키워드 밖의 바뀜 0 = {ok}")
    bad |= not ok
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 바. 셈(제품 = esgapi 의 tests·migrations 밖, AST)"
  run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, os, pathlib, subprocess, sys
step = int(os.environ["STEP"])
base = os.environ["B"]
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
# 블록 수는 파일마다 정확히 그대로다(권고 3 — K2c 는 새 블록 0: 만들기는 K2a 의 한 표 service, 초기화는 K2a 의 action)
for p in sorted(set(now) | set(was)):
    if now.get(p) != was.get(p):
        print(f"  ★ {p}: 기준 {was.get(p)} → 지금 {now.get(p)}"); bad = 1
svc = now.get("esgapi/user/service/services/user.py")
print(f"  블록을 품은 파일 {len(now)} (기준 {len(was)}) · services/user.py {svc}")
dur = sum(v[1] for v in now.values()); print(f"  durable=True 합 {dur} (기대 3)"); bad |= dur != 3
trees = {p: ast.parse(pathlib.Path(p).read_text(encoding="utf-8")) for p in now_paths}
sys.path.insert(0, ".")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", os.environ["TEST_DS"])
from esgapi.core import permissions as P
cells = {}
for op, pol in P.OPERATION_POLICY.items():
    cells.setdefault(pol.needs, set()).add(op)
want_operator = {"user_list", "user_create", "user_password_reset"} if step >= 2 else set()
n_c, s_o, s_s = len(cells.get("customer", ())), sorted(cells.get("operator", ())), sorted(cells.get("self", ()))
print(f"  표: customer {n_c} · operator {s_o} · self {s_s}")
bad |= len(cells.get("customer", ())) != 23 or cells.get("operator", set()) != want_operator or cells.get("self", set()) != {"user_me", "user_password_change"}
print(f"  INITIAL_ALLOWED: {sorted(P.INITIAL_ALLOWED)}"); bad |= P.INITIAL_ALLOWED != {"user_me", "user_password_change"}
proposed = sorted(op for op, pol in P.OPERATION_POLICY.items() if pol.proposed)
print(f"  proposed=True: {proposed}"); bad |= proposed != ["inventory_scope3_classify"]
calls, hits, opened = {}, [], 0
SEL = "esgapi/organization/service/selectors/organization.py"
WATCH = {"by_subdomain", "admin_by_username", "admin_by_id", "register_admin", "create_operator", "sole_candidates", "find_company_by_id", "find_sole_company"}
for p, tree in trees.items():
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "unscoped":
            hits.append(f"{p}:{node.lineno} .unscoped")
        if isinstance(node, ast.Attribute) and node.attr == "objects" and isinstance(node.value, ast.Name) and node.value.id in {"User", "Company", "Site", "RefreshToken"}:
            hits.append(f"{p}:{node.lineno} {node.value.id}.objects")
        if isinstance(node, ast.Name) and node.id in {"find_company_by_id", "find_sole_company"} and p != SEL:
            calls.setdefault(node.id, set()).add(p)   # 포트로 꽂는 자리는 부름이 아니라 가리킴이다
        if isinstance(node, ast.Call):
            name = node.func.attr if isinstance(node.func, ast.Attribute) else node.func.id if isinstance(node.func, ast.Name) else None
            if name in WATCH and p not in {"esgapi/core/isolation/managers.py", "esgapi/organization/models.py", "esgapi/user/models.py"}:
                calls.setdefault(name, set()).add(p)
            if isinstance(node.func, ast.Attribute) and node.func.attr == "for_company" and isinstance(node.func.value, ast.Name) and node.func.value.id in {"Company", "User", "Site", "DocumentRow", "JobRow", "LlmCallLogRow"}:
                opened += 1
print(f"  숨은 길: {hits} (기대 없음)"); bad |= bool(hits)
for k in sorted(calls): print(f"  {k}( 의 자리: {sorted(calls[k])}")
want_calls = {
    "by_subdomain": {SEL},
    "admin_by_username": {"esgapi/user/service/selectors/user.py"},
    "admin_by_id": {"esgapi/user/service/selectors/user.py"},
    "register_admin": {"esgapi/user/service/services/user.py"},
    "create_operator": {"esgapi/user/management/commands/create_user.py"},
}
if step >= 2:
    want_calls |= {"sole_candidates": {SEL}, "find_company_by_id": {"esgapi/user/service/apis/users.py"}, "find_sole_company": {"esgapi/user/service/apis/users.py"}}
bad |= calls != want_calls
want_opened = 17 + (2 if step >= 2 else 0)   # ② +2: find_company_by_id(Company)·list_customer_users(User). 초기화의 대상 읽기는 K2a 의 account() 를 쓴다
print(f"  <회사 모델>.for_company( 의 수: {opened} (기대 {want_opened})"); bad |= opened != want_opened
settings_hits = [str(p) for p in pathlib.Path("esgapi/config/settings").glob("*.py") if "PASSWORD_HASHERS" in p.read_text() or "AUTH_PASSWORD_VALIDATORS" in p.read_text()]
print(f"  설정의 PASSWORD_HASHERS·AUTH_PASSWORD_VALIDATORS: {settings_hits} (기대 없음)"); bad |= bool(settings_hits)
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 바(덧). 깎은 것 0(건너뛰기·경고 예외·무시 표시를 더한 줄 0 — 지운 줄과 맞바꾸지 않는다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$B" -- . ":!$A/scripts/section4-K2c.sh" ":!$A/scripts/planted-breaks-K2c.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-K2c\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+[^+].*($marks)|^\+($marks)" "$T/all.diff")"; minus="$(grep -c -E "^-[^-].*($marks)|^-($marks)" "$T/all.diff")"; echo "  더한 줄 $plus · 지운 줄 $minus"; grep -E "^\+[^+].*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" = 0 ]'

  echo; echo "── 자. 비밀: diff·커밋 메시지에 JWT 꼴 글자·PBKDF2 해시 0(테스트 파일 안의 지어낸 것 밖)"
  run 'git diff "$B" -- . ":!$A/esgapi/*/tests/*" ":!$A/tests/*" ":!$A/tests_integration/*" ":!$A/scripts/section4-K2c.sh" > "$T/prod.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "/tests/|tests_integration/|section4-K2c\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/prod.diff"; j="$(grep -c -E "eyJ[A-Za-z0-9_-]{10,}\." "$T/prod.diff")"; h="$(grep -c -E "pbkdf2_sha256\\\$[0-9]+\\\$" "$T/prod.diff")"; m="$(git log --format=%B "$B"..HEAD | grep -c -E "eyJ[A-Za-z0-9_-]{10,}\.|pbkdf2_sha256\\\$[0-9]")"; echo "  제품 diff 의 JWT $j · 해시 $h · 커밋 메시지 $m"; [ "$j$h$m" = 000 ]'

  echo; echo "── 나. 수집: 사라진 노드 0(B 의 노드 ID 는 git archive 사본에서), 층마다의 수"
  mkdir -p "$T/base"
  git archive "$B" "$A" | tar -x -C "$T/base"
  (cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt")
  (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt")
  comm -23 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/gone.txt"; comm -13 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/new.txt"
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; g="$(wc -l < "$T/gone.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · 사라진 노드 $g · 새 노드 $(wc -l < "$T/new.txt" | tr -d " ")"; cat "$T/gone.txt"; [ "$b" = 2905 ] && [ "$g" = 0 ]'
  run '(cd "$A" && for m in "not django_db and not security" django_db security; do printf "  %-32s %s\n" "$m" "$(uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "$m" 2> /dev/null | grep -c "::")"; done) | tee "$T/layers.txt"; p="$(sed -n "1p" "$T/layers.txt" | awk "{print \$NF}")"; b="$(sed -n "2p" "$T/layers.txt" | awk "{print \$NF}")"; s="$(sed -n "3p" "$T/layers.txt" | awk "{print \$NF}")"; echo "  기대: 순수 $PURE · 업무 $BUSINESS · 보안 $SECURITY"; [ "$p" = "$PURE" ] && [ "$b" = "$BUSINESS" ] && [ "$s" = "$SECURITY" ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫"
  if [ ! -x "$A/scripts/planted-breaks-K2c.sh" ]; then echo "★ planted-breaks-K2c.sh 가 없다(커밋 ③ 의 것)"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return; fi
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-K2c.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=$PURE_PLANTED" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
}

# 한 층을 돌리고 EXIT 를 찍는다. 끝 줄이 「<건수> passed in …」 하나여야 한다(줄 끝까지 — 권고 3). 다시 돌리지 않는다.
layer() { # <이름> <건수> <명령…>
  local name="$1" want="$2" code started=$SECONDS last
  shift 2
  echo; echo "▶ $*"
  "$@" > "$T/layer.txt" 2>&1; code=$?
  cp "$T/layer.txt" "$T/layer-$name.txt"
  tail -3 "$T/layer.txt"
  last="$(tail -1 "$T/layer.txt")"
  echo "$last" | grep -q -E "^=* ?$want passed(, [0-9]+ deselected)? in [0-9.]+s( \([0-9:]+\))? ?=*$" || { echo "★ 끝 줄이 「$want passed in …」가 아니다"; code=1; }
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
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh K2c 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test "$PROJECT" = esg-app-k2c'
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
  # K2C_LAYERS 로 다시 돌릴 층만 고를 수 있다(빨간 층만 다시 — 기본은 셋 다와 심은 파손).
  local only="${K2C_LAYERS:-업무 보안 통합 파손}"
  case " $only " in *" 업무 "*) layer "업무" "$BUSINESS" "$A/scripts/test-business.sh" -n 2 ;; esac
  case " $only " in *" 보안 "*) layer "보안" "$SECURITY" "$A/scripts/test-security.sh" ;; esac
  case " $only " in *" 통합 "*) layer "통합" "$INTEGRATION" "$A/scripts/test-integration.sh" -s ;; esac
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  run 'n="$(docker compose logs --no-color api-py worker-py | grep -c -E "eyJ[A-Za-z0-9_-]{10,}\.|pbkdf2_sha256")"; echo "  기록의 토큰·해시 꼴 줄: $n"; [ "$n" = 0 ]'
  if [ -x "$A/scripts/planted-breaks-K2c.sh" ] && case " $only " in *" 파손 "*) true ;; *) false ;; esac; then
    echo; echo "── 아(덧). 심은 파손의 컨테이너 몫"
    git status --porcelain > "$T/before-planted.txt"
    run '"$A/scripts/planted-breaks-K2c.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=$CONTAINER_PLANTED" && exit $code; exit 1'
    run 'git status --porcelain | diff - "$T/before-planted.txt"'
  fi
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT[-/]" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT[-/]")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 차. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  # 커밋 넷(⓪~③). ① 은 K2a 검증 권고를 고치는 계획된 fix(k2c): ① 이라 「앞 커밋의 흠을 고친 fix」의 셈에서 뺀다.
  run 'git log --format="%h %s" "$B"..HEAD --no-merges --first-parent; n="$(git log --format=%s --first-parent "$B"..HEAD | grep -v "^merge" | wc -l | tr -d " ")"; fixes="$(git log --format=%s --first-parent "$B"..HEAD | grep "^fix" | grep -c -v "^fix(k2c): ① ")"; echo "  커밋 $n (앞 커밋을 고친 fix: $fixes)"; test "$((n - fixes))" = 4'
  run 'bad=0; for c in $(git rev-list --no-merges --first-parent "$B"..HEAD); do for t in "Ticket: MARC-TICK-97" "Derives-from: MARC-ENT-137"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

export -f sha changed outside env_value 2> /dev/null
case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --containers) containers_part ;;
  --after-commit) step_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (바닥 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
