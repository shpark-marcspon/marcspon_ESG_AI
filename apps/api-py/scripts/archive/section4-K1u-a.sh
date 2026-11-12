#!/usr/bin/env bash
# 밴드 K1u-a(MARC-TICK-91: 회사 하나(시드)와 EDK 꼴의 계정 표(Company·User)를 세우고 accounts 를 organization·user 로
# 옮겨 지운다. core 의 표는 0줄)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-K1u-a.sh --step <0~4>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-K1u-a.sh --pure            --step 4 전부 + 심은 파손의 순수 몫
#         apps/api-py/scripts/section4-K1u-a.sh --containers      업무·보안·통합 층 한 번 + 왕복·정책 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-K1u-a.sh --after-commit    --step 4 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. 브로커는 compose 의 queue(sqs://queue:9324)뿐이다. 네트워크는 uv·docker·pnpm 의 설치뿐이다.
# bash 전용이다(${PIPESTATUS[0]}). git grep -E 에 \s 를 쓰지 않는다([[:space:]]).
#
# ★ 컨테이너 층에 들어가기 전 문(발주서 a-1-1, 사용자 결정 2026-10-15 밤): 자기 밖 esg-app* compose 프로젝트 둘 이하,
#   빌드 중인 것 0, 메모리 free 20% 이상, 1분 부하 24 미만. 60초 간격, 최대 30분.
# ★ makemigrations --check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라 RuntimeWarning 한 줄이 난다. 기대다).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 코드의 셈은 AST 로 한다(글자 셈은 docstring 을 문다).
set -u
cd "$(dirname "$0")/../../.."
B=76aca77   # 기준 커밋(발주서 a-1-1, 개정 4): 수·노드·openapi·트랜잭션 셈의 기준
W=24ab83c   # 이 가지가 갈라진 자리(= 76aca77 + 프론트 FW1, apps/web 만 — 감독 덧붙임 「바닥 확정」): 파일 diff 의 기준
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
export LC_ALL=C   # sort 와 diff 가 같은 차례를 쓴다
MODE="${1:-}"
STEP=4
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-4]) ;; *) echo "사용: $0 --step <0~4>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~4> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
ROOT="$(pwd)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
E="$A/esgapi"
TEST_DS=esgapi.config.settings.test_business
export A E B W T TEST_DS STEP

# 층마다의 수(기준 76aca77 의 수집: 순수 1,898 · 업무 388 · 보안 105). 커밋마다 정해진 이름만 늘고 준다(나.).
PURE_AT=(1898 1913 1931 1932 1932)   # ③ 뒤 +1: 검증 F1 의 fix(받침 ④ 의 root_manager 자리)
BUSINESS_AT=(388 406 419 419 419)
SECURITY_AT=(105 105 107 107 107)   # 보안 층은 ② 에 같이 든다(seed 의 타입이 부르는 자리 전부를 묶는다)
INTEGRATION=21   # 기준 76aca77 의 통합 층 수(이름 그대로 — 두 파일은 회사 칸 줄만 고친다)
PURE="${PURE_AT[$STEP]}"; BUSINESS="${BUSINESS_AT[$STEP]}"; SECURITY="${SECURITY_AT[$STEP]}"
export PURE BUSINESS SECURITY
PURE_PLANTED="8/8"; CONTAINER_PLANTED="9/9"   # planted-breaks-K1u-a.sh 의 순수 몫 Pa1·3·5·8·10·11·12·13, 컨테이너 몫 Pa2·3·4·6·7·9·10·12·Ra
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
# 허용 경로(발주서 a-1-2 의 닫힌 목록 + 감독 처분: organization 의 permissions) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/organization/' \
    -e '^apps/api-py/esgapi/user/' \
    -e '^apps/api-py/esgapi/accounts/' \
    -e '^apps/api-py/esgapi/config/apps_list\.py$' \
    -e '^apps/api-py/esgapi/config/settings/(base|migrate)\.py$' \
    -e '^apps/api-py/esgapi/config/api\.py$' \
    -e '^apps/api-py/esgapi/config/tests/(test_system_check|test_api_contract|test_settings)\.py$' \
    -e '^apps/api-py/esgapi/core/tenancy/session\.py$' \
    -e '^apps/api-py/esgapi/core/isolation/(__init__|managers|grants)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/isolation/(test_managers|test_static_rules|test_grants)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_selector_scope|test_documents_models|test_permissions)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_flows_core_names\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_documents_api\.py$' \
    -e '^apps/api-py/esgapi/core/tests/tenancy/test_middleware\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_transaction_rules\.py$' \
    -e '^apps/api-py/esgapi/inventory/service/apis/inventory\.py$' \
    -e '^apps/api-py/esgapi/greenwash/service/apis/greenwash\.py$' \
    -e '^apps/api-py/esgapi/greenwash/tests/test_contracts_gc1\.py$' \
    -e '^apps/api-py/esgapi/reference/service/apis/reference\.py$' \
    -e '^apps/api-py/esgapi/reference/migrations/0001_reference\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/(test_flows|test_scope3_is_pure)\.py$' \
    -e '^apps/api-py/\.importlinter$' \
    -e '^apps/api-py/conftest\.py$' \
    -e '^apps/api-py/scripts/test-layout-allow\.txt$' \
    -e '^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$' \
    -e '^apps/api-py/tests/security/(conftest|seed|test_owner|test_exchange_tenant|test_tenant_paths|test_migrations|test_same_tenant_foreign_keys)\.py$' \
    -e '^apps/api-py/tests/security/(test_tenant_boundary|test_llm_log)\.py$' \
    -e '^apps/api-py/tests/security/test_request_transactions\.py$' \
    -e '^apps/api-py/tests/security/(test_documents|test_documents_race|test_jobs|test_reference)\.py$' \
    -e '^apps/api-py/tests/support/(db|http|tokens)\.py$' \
    -e '^apps/api-py/tests_integration/(conftest|test_flow)\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-K1u-a\.sh$' \
    -e '^README\.md$'
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

echo "── 밴드 K1u-a §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

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
want_gone = {"esgapi.accounts"} if step >= 2 else set()
bad = 0
for section, key in (("core-knows-no-module", "forbidden_modules"), ("no-foreign-models", "source_modules"), ("services-stay-home", "forbidden_modules")):
    got = lines(section, key)
    need = {"esgapi.organization", "esgapi.user"} if step >= 2 else set()
    miss = need - got; left = want_gone & got
    print(f"  {section}.{key}: organization·user {sorted(need - miss)} · 빠짐 {sorted(miss)} · 남은 accounts {sorted(left)}")
    bad |= bool(miss or left)
pure = lines("pure-modules", "source_modules")
if step >= 2:
    ok = "esgapi.organization.service.permissions" in pure and "esgapi.accounts.service.permissions" not in pure
    print(f"  pure-modules 에 esgapi.organization.service.permissions(감독 처분 ㉠): {ok}")
    bad |= not ok
sys.exit(1 if bad else 0)
PY
)'
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; exit $code)'

  echo; echo "── 다. generated: 코드에서 다시 뽑은 openapi 가 커밋된 파일과 바이트 동일, 기준 대비 diff 는 MeOut.companyId 더함뿐(② 뒤), apps/web 0줄"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'
  run 'git diff --quiet "$W" -- apps/web && test -z "$(git ls-files --others --exclude-standard -- apps/web)"'
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
for kind, path, value in diffs:
    print("  ", kind, "/".join(path), json.dumps(value, ensure_ascii=False)[:160])
want = []
if step >= 2:
    want = [
        ("더함", ["components", "schemas", "MeOut", "properties", "companyId"], {"title": "Companyid", "type": "integer"}),
        ("바뀜", ["components", "schemas", "MeOut", "required"], (base["components"]["schemas"]["MeOut"]["required"], base["components"]["schemas"]["MeOut"]["required"] + ["companyId"])),
    ]
got = [(k, p, v) for k, p, v in diffs]
print(f"  diff {len(diffs)}개 (기대 {len(want)}: MeOut.companyId 더함과 required 에 companyId)")
sys.exit(0 if got == want else 1)
PY'
  run 'for f in api.d.ts api.d.ts.source-sha256; do :; done; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3; if [ "$STEP" -lt 2 ]; then git diff --quiet "$B" -- "$A/generated"; else test "$(cat "$A/generated/api.d.ts.source-sha256" | cut -d" " -f1)" = "$(sha "$A/generated/openapi.json")"; fi'

  echo; echo "── 라. 마이그레이션(makemigrations 가 낼 것 없음, 폴더마다 0001 하나, core 0줄)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'git diff --quiet "$B" -- "$E/core/migrations" "$E/core/models.py" "$E/core/isolation/foreign_keys.py" "$E/core/tenancy/rls.py" && test -z "$(git ls-files --others --exclude-standard -- "$E/core/migrations")"'
  run 'for app in organization user; do [ "$app" = user ] && [ "$STEP" -lt 2 ] && continue; [ "$STEP" -lt 1 ] && continue; got="$(cd "$E/$app/migrations" && ls *.py | tr "\n" " ")"; echo "  $app/migrations: $got"; [ "$got" = "0001_initial.py __init__.py " ] || exit 1; done; n="$(git ls-files "$E/accounts" | wc -l | tr -d " ")"; m="$(find "$E/accounts" -name "*.py" 2>/dev/null | wc -l | tr -d " ")"; echo "  E/accounts 의 추적 파일 $n · 작업 트리 .py $m"; if [ "$STEP" -ge 2 ]; then [ "$n$m" = 00 ]; fi'

  echo; echo "── 마. 경계(닫힌 목록, 지운 파일은 accounts 뿐)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'd="$(git diff --no-renames --name-only --diff-filter=D "$W" | grep -v "^$E/accounts/" | grep -v "^$A/esgapi/accounts/" | wc -l | tr -d " ")"; a="$(git diff --no-renames --name-only --diff-filter=D "$W" -- "$E/accounts" | wc -l | tr -d " ")"; echo "  지운 파일: accounts $a · 그 밖 $d"; [ "$d" = 0 ]'
  run 'git diff --quiet "$B" -- "$E/reconcile" "$E/config/celery.py" "$E/config/env.py" "$E/core/exceptions.py" "$E/core/schemas.py" "$E/core/observability" "$E/core/permissions.py" "$E/core/tenancy/middleware.py" "$E/core/tenancy/context.py" "$E/config/tests/test_request_schemas_reject_bool.py" "$A/pyproject.toml" "$A/uv.lock" compose.yaml .env.example scripts docker infra || exit 1; g="$(git diff --no-renames --name-only "$B" -- "$E/greenwash"; git ls-files --others --exclude-standard -- "$E/greenwash")"; echo "  greenwash 의 바뀐 파일: ${g:-없음}"; [ -z "$g" ] || [ "$g" = "$(printf "%s\n%s" "$E/greenwash/service/apis/greenwash.py" "$E/greenwash/tests/test_contracts_gc1.py")" ] || [ "$g" = "$E/greenwash/service/apis/greenwash.py" ]'

  echo; echo "── 바. system check(설정 넷, -W error) — ① 까지 「(0 silenced)」, ② 뒤 「(1 silenced)」 와 끈 것 auth.W004 하나"
  run '(cd "$A" && uv run --frozen python - <<"PY"
import os, subprocess, sys
from esgapi.config.tests.test_system_check import SETTINGS, env_for
step = int(os.environ["STEP"])
want = "System check identified no issues (1 silenced)." if step >= 2 else "System check identified no issues (0 silenced)."
bad = 0
for name in SETTINGS:
    done = subprocess.run([sys.executable, "-W", "error", "manage.py", "check", "--fail-level", "WARNING"], env=env_for(name), capture_output=True, text=True, check=False)
    last = (done.stdout.strip().splitlines() or [done.stderr.strip()[-200:]])[-1]
    print(f"  {name}: {last}")
    bad |= done.returncode != 0 or last != want
env = env_for("test_business")
code = "import django; django.setup(); from django.conf import settings; print(list(settings.SILENCED_SYSTEM_CHECKS))"
silenced = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False).stdout.strip()
print(f"  SILENCED_SYSTEM_CHECKS = {silenced}")
if step >= 2:
    bad |= silenced != str(["auth.W004"])
    code = "import django; django.setup(); from django.core import checks; from django.conf import settings; settings.SILENCED_SYSTEM_CHECKS = []; print(sorted(m.id for m in checks.run_checks()))"
    unsilenced = subprocess.run([sys.executable, "-c", code], env=env, capture_output=True, text=True, check=False).stdout.strip()
    print(f"  끄지 않으면: {unsilenced}")
    bad |= unsilenced != str(["auth.W004"])
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 나. 수집: 사라진 노드·새 노드가 정해진 이름과 글자로 같다(기준의 노드 ID 는 git archive 사본에서)"
  mkdir -p "$T/base"
  git archive "$B" "$A" | tar -x -C "$T/base"
  (cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt")
  (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt")
  comm -23 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/gone.txt"; comm -13 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/new.txt"
  expected_gone | sort > "$T/gone-expected.txt"; expected_new | sort > "$T/new-expected.txt"
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · 사라진 것 $(wc -l < "$T/gone.txt" | tr -d " ") · 새 것 $(wc -l < "$T/new.txt" | tr -d " ")"; [ "$b" = 2391 ] && diff "$T/gone-expected.txt" "$T/gone.txt"'
  run 'diff "$T/new-expected.txt" "$T/new.txt"'
  run '(cd "$A" && for m in "not django_db and not security" django_db security; do printf "  %-32s %s\n" "$m" "$(uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "$m" 2> /dev/null | grep -c "::")"; done) | tee "$T/layers.txt"; b="$(sed -n "2p" "$T/layers.txt" | awk "{print \$NF}")"; s="$(sed -n "3p" "$T/layers.txt" | awk "{print \$NF}")"; echo "  기대: 업무 $BUSINESS · 보안 $SECURITY"; [ "$b" = "$BUSINESS" ] && [ "$s" = "$SECURITY" ]'

  echo; echo "── 사. 셈(제품 = esgapi 의 tests·migrations 밖, AST): 트랜잭션 경계 10·1·3 그대로, 옛 이름 0"
  run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, os, pathlib, subprocess, sys
step = int(os.environ["STEP"])
base = os.environ["B"]
def is_atomic(node):
    f = node.func if isinstance(node, ast.Call) else node
    return isinstance(f, ast.Attribute) and f.attr == "atomic" and isinstance(f.value, ast.Name) and f.value.id == "transaction"
def counts(tree):
    blocks = on_commit = durable = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            blocks += sum(is_atomic(item.context_expr) for item in node.items)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            blocks += sum(is_atomic(d) for d in node.decorator_list)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "on_commit":
            on_commit += 1
        if isinstance(node, ast.keyword) and node.arg == "durable" and isinstance(node.value, ast.Constant) and node.value.value is True:
            durable += 1
    return blocks, on_commit, durable
def product(paths):
    return [p for p in paths if p.startswith("esgapi/") and p.endswith(".py") and "/tests/" not in p and "/migrations/" not in p]
now_paths = product([str(p) for p in pathlib.Path("esgapi").rglob("*.py")])
base_paths = product(subprocess.run(["git", "ls-tree", "-r", "--name-only", base, "--", "."], capture_output=True, text=True, check=True).stdout.split())
def tally(paths, read):
    out = {}
    for p in paths:
        c = counts(ast.parse(read(p)))
        if any(c): out[p] = c
    return out
now = tally(now_paths, lambda p: pathlib.Path(p).read_text(encoding="utf-8"))
was = tally(base_paths, lambda p: subprocess.run(["git", "show", f"{base}:apps/api-py/{p}"], capture_output=True, text=True, check=True).stdout)
moved = {"esgapi/accounts/service/services/accounts.py": None}
if step >= 2:
    expect = {k: v for k, v in was.items() if k not in moved}
    expect["esgapi/user/service/services/user.py"] = (1, 0, 0)          # upsert_user 의 블록 하나
    expect["esgapi/organization/service/services/organization.py"] = (1, 0, 0)   # insert_site 의 블록 하나
else:
    expect = dict(was)
for p in sorted(set(now) | set(expect)):
    mark = "" if now.get(p) == expect.get(p) else f"  ★ 기대 {expect.get(p)}"
    print(f"  {p}: 기준 {was.get(p)} → 지금 {now.get(p)}{mark}")
tot = [sum(v[i] for v in now.values()) for i in range(3)]
print(f"  합: 블록 {tot[0]} · on_commit {tot[1]} · durable=True {tot[2]} (기대 10 · 1 · 3)")
bad = now != expect or tot != [10, 1, 3]
# 옛 이름(② 뒤): esgapi.accounts 의 import, user_in_other_tenant·UserInOtherTenant 이름과 글자, .unscoped, <회사 모델>.objects
names = {"Company", "User", "Site"}
hits = []
for p in now_paths:
    tree = ast.parse(pathlib.Path(p).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "unscoped":
            hits.append(f"{p}:{node.lineno} .unscoped")
        if isinstance(node, ast.Attribute) and node.attr == "objects" and isinstance(node.value, ast.Name) and node.value.id in names:
            hits.append(f"{p}:{node.lineno} {node.value.id}.objects")
        if step >= 2:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                mods = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
                if any(m == "esgapi.accounts" or m.startswith("esgapi.accounts.") for m in mods):
                    hits.append(f"{p}:{node.lineno} import esgapi.accounts")
            if isinstance(node, ast.Name) and node.id == "UserInOtherTenant":
                hits.append(f"{p}:{node.lineno} UserInOtherTenant")
            if isinstance(node, ast.Constant) and node.value == "user_in_other_tenant":
                hits.append(f"{p}:{node.lineno} \"user_in_other_tenant\"")
print(f"  옛 이름·숨은 길: {len(hits)} (기대 0)"); [print("   ", h) for h in hits]
bad |= bool(hits)
# 개정 4 ★다: test_transaction_rules.py 의 MODEL_ROOTS 에 for_company 가 들었는가(② 뒤)
tree = ast.parse(pathlib.Path("esgapi/core/tests/test_transaction_rules.py").read_text(encoding="utf-8"))
roots = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL_ROOTS" for t in node.targets):
        roots = {c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
print(f"  MODEL_ROOTS = {sorted(roots)}")
if step >= 2:
    bad |= "for_company" not in roots
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 사(덧). 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다 — 지운 줄과 더한 줄의 차로 센다: 옮긴 줄은 셈이 같다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$W" -- . ":!$A/scripts/section4-K1u-a.sh" ":!$A/scripts/planted-breaks-K1u-a.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-K1u-a\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+[^+].*($marks)|^\+($marks)" "$T/all.diff")"; minus="$(grep -c -E "^-[^-].*($marks)|^-($marks)" "$T/all.diff")"; echo "  더한 줄 $plus · 지운 줄 $minus (더한 쪽이 많으면 안 된다)"; grep -E "^\+[^+].*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" -le "$minus" ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫"
  if [ ! -x "$A/scripts/planted-breaks-K1u-a.sh" ]; then echo "★ planted-breaks-K1u-a.sh 가 없다(커밋 ④ 의 것)"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return; fi
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-K1u-a.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=$PURE_PLANTED" && exit $code; exit 1'
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
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh K1u-a 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test "$PROJECT" = esg-app-k1u-a'
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
  # K1U_LAYERS 로 다시 돌릴 층만 고를 수 있다(빨간 층만 다시 — 기본은 셋 다와 심은 파손).
  local only="${K1U_LAYERS:-업무 보안 통합 파손}"
  case " $only " in *" 업무 "*) layer "업무" "$BUSINESS" "$A/scripts/test-business.sh" -n 2 ;; esac
  case " $only " in *" 보안 "*) layer "보안" "$SECURITY" "$A/scripts/test-security.sh" ;; esac
  case " $only " in *" 통합 "*) layer "통합" "$INTEGRATION" "$A/scripts/test-integration.sh" -s ;; esac
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  # 주인 역할로(컨테이너 안의 POSTGRES_USER, Python 쪽 DB ${POSTGRES_DB}_py): 정책·RLS 0, 마이그레이션 기록의 앱
  run 'docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\${POSTGRES_DB}_py\" -At -c \"SELECT (SELECT count(*) FROM pg_policies) || chr(32) || (SELECT count(*) FROM pg_class WHERE relrowsecurity OR relforcerowsecurity) || chr(32) || (SELECT string_agg(DISTINCT app, chr(44) ORDER BY app) FROM django_migrations)\"" | tee "$T/pol.txt"; read -r pol rls apps < "$T/pol.txt"; echo "  정책 $pol · RLS 표 $rls · 기록의 앱 $apps"; [ "$pol$rls" = 00 ] && [ "$apps" = "auth,contenttypes,core,organization,reference,user" ]'
  if [ -x "$A/scripts/planted-breaks-K1u-a.sh" ] && case " $only " in *" 파손 "*) true ;; *) false ;; esac; then
    echo; echo "── 아(덧). 심은 파손의 컨테이너 몫"
    git status --porcelain > "$T/before-planted.txt"
    run '"$A/scripts/planted-breaks-K1u-a.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=$CONTAINER_PLANTED" && exit $code; exit 1'
    run 'git status --porcelain | diff - "$T/before-planted.txt"'
  fi
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT[-/]" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT[-/]")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 차. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$W"..HEAD --no-merges --first-parent; n="$(git log --format=%s --first-parent "$W"..HEAD | grep -v "^merge" | wc -l | tr -d " ")"; fixes="$(git log --format=%s --first-parent "$W"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 5'
  run 'bad=0; for c in $(git rev-list --no-merges --first-parent "$W"..HEAD); do for t in "Ticket: MARC-TICK-91" "Derives-from: MARC-ENT-137"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

# 사라지는 노드(발주서 a-§3-2·a-§3-3. 커밋마다 늘어난다).
expected_gone() {
  [ "$STEP" -ge 2 ] && cat <<'GONE'
esgapi/accounts/tests/test_api.py::test_an_oversized_exchange_body_is_413_and_nothing_is_echoed
esgapi/accounts/tests/test_api.py::test_body_cannot_carry_tenant_or_user
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_algorithm0]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_algorithm1]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_claims]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_signature]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-expired]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-malformed]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-wrong_audience]
esgapi/accounts/tests/test_api.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-wrong_issuer]
esgapi/accounts/tests/test_api.py::test_editor_and_admin_create_a_site_in_their_own_tenant[admin]
esgapi/accounts/tests/test_api.py::test_editor_and_admin_create_a_site_in_their_own_tenant[editor]
esgapi/accounts/tests/test_api.py::test_first_exchange_creates_the_user_and_sets_the_cookie
esgapi/accounts/tests/test_api.py::test_me_and_logout
esgapi/accounts/tests/test_api.py::test_same_external_id_from_another_issuer_would_be_another_user
esgapi/accounts/tests/test_api.py::test_second_exchange_upserts_name_and_role
esgapi/accounts/tests/test_api.py::test_site_body_cannot_carry_a_tenant
esgapi/accounts/tests/test_api.py::test_tampered_or_expired_cookie_is_401_with_its_own_code
esgapi/accounts/tests/test_api.py::test_tenant_header_is_not_a_way_in
esgapi/accounts/tests/test_api.py::test_unknown_path_is_404_in_the_one_error_shape
esgapi/accounts/tests/test_api.py::test_unknown_tenant_is_403_and_nothing_is_created
esgapi/accounts/tests/test_api.py::test_viewer_cannot_create_a_site
esgapi/accounts/tests/test_exchange.py::test_claims_are_read_from_a_verified_payload
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[name-None]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[role-None]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[role-bad10]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[role-superadmin]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[sub-123]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[sub-None]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[sub-]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-../x]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-None]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-Tenant-A]
esgapi/accounts/tests/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
esgapi/accounts/tests/test_exchange.py::test_only_editor_and_above_create_sites[admin-True]
esgapi/accounts/tests/test_exchange.py::test_only_editor_and_above_create_sites[editor-True]
esgapi/accounts/tests/test_exchange.py::test_only_editor_and_above_create_sites[viewer-False]
esgapi/accounts/tests/test_exchange.py::test_registered_tenant_is_admitted
esgapi/accounts/tests/test_exchange.py::test_roles_are_exactly_the_three_in_the_plan
esgapi/accounts/tests/test_exchange.py::test_session_freezes_tenant_and_role_and_expires_after_ttl
esgapi/accounts/tests/test_exchange.py::test_tenant_id_shape_matches_the_ts_skeleton
esgapi/accounts/tests/test_exchange.py::test_unknown_tenant_is_rejected_by_name
esgapi/accounts/tests/test_permissions.py::test_both_read_the_table
esgapi/accounts/tests/test_permissions.py::test_permitted_session_returns_the_session_or_raises_forbidden
esgapi/accounts/tests/test_permissions.py::test_the_values_are_what_they_were
esgapi/accounts/tests/test_selectors_tenant.py::test_all_sites_gives_one_tenants_sites_without_rls
esgapi/accounts/tests/test_selectors_tenant.py::test_the_sites_query_names_the_tenant
esgapi/accounts/tests/test_selectors_tenant.py::test_the_sites_route_shows_only_the_sessions_tenant_without_rls
esgapi/accounts/tests/test_services.py::test_editor_creates_in_the_session_tenant
esgapi/accounts/tests/test_services.py::test_ok_verifies_then_looks_up_then_upserts
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[bad_algorithm]
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[bad_claims]
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[bad_signature]
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[expired]
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[malformed]
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[wrong_audience]
esgapi/accounts/tests/test_services.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[wrong_issuer]
esgapi/accounts/tests/test_services.py::test_unknown_tenant_is_rejected_and_no_user_is_written
esgapi/accounts/tests/test_services.py::test_user_in_other_tenant_is_its_own_branch
esgapi/accounts/tests/test_services.py::test_viewer_lists_but_cannot_create
esgapi/accounts/tests/test_session_tokens.py::test_edk_token_is_not_a_session
esgapi/accounts/tests/test_session_tokens.py::test_expired_session_is_rejected_with_its_reason
esgapi/accounts/tests/test_session_tokens.py::test_garbage_cookie_is_malformed
esgapi/accounts/tests/test_session_tokens.py::test_no_cookie_is_absent_not_rejected
esgapi/accounts/tests/test_session_tokens.py::test_our_session_is_not_an_edk_token
esgapi/accounts/tests/test_session_tokens.py::test_round_trip
esgapi/accounts/tests/test_session_tokens.py::test_session_signed_with_another_secret_is_rejected
esgapi/accounts/tests/test_tokens.py::test_alg_none_is_rejected
esgapi/accounts/tests/test_tokens.py::test_attacker_key_in_jwk_header_is_ignored
esgapi/accounts/tests/test_tokens.py::test_expired_token_is_rejected
esgapi/accounts/tests/test_tokens.py::test_garbage_is_malformed
esgapi/accounts/tests/test_tokens.py::test_missing_required_claims_are_rejected
esgapi/accounts/tests/test_tokens.py::test_only_rs256_is_allowed
esgapi/accounts/tests/test_tokens.py::test_swap_public_key_as_hs256_secret_is_rejected
esgapi/accounts/tests/test_tokens.py::test_token_signed_with_another_key_is_rejected
esgapi/accounts/tests/test_tokens.py::test_valid_token_is_ok
esgapi/accounts/tests/test_tokens.py::test_wrong_audience_is_rejected
esgapi/accounts/tests/test_tokens.py::test_wrong_issuer_is_rejected
esgapi/core/tests/isolation/test_managers.py::test_a_user_in_another_tenant_is_not_overwritten
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_tenant_is_refused_before_the_db[SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_tenant_is_refused_before_the_db[UserRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[all-SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[all-UserRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[count-SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[count-UserRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[create-SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[create-UserRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[empty tenant-SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[empty tenant-UserRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[filter-SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[filter-UserRow]
esgapi/core/tests/isolation/test_managers.py::test_the_default_manager_is_the_refusing_one[SiteRow]
esgapi/core/tests/isolation/test_managers.py::test_the_default_manager_is_the_refusing_one[UserRow]
esgapi/core/tests/test_selector_scope.py::test_selectors_scope_every_read[accounts/service/selectors/accounts.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[accounts/service/services/accounts.py]
tests/security/test_exchange_tenant.py::test_user_already_in_another_tenant_is_409
tests/security/test_migrations.py::test_migrate_runs_on_an_empty_db_and_on_a_db_migrated_by_py1
GONE
  return 0
}
# 새 노드.
expected_new() {
  [ "$STEP" -ge 1 ] && cat <<'NEW'
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[-1-Company]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db['1'-Company]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[0-Company]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[None-Company]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[True-Company]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[all-Company]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[count-Company]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[create-Company]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[filter-Company]
esgapi/core/tests/isolation/test_managers.py::test_the_company_default_manager_is_the_refusing_one[Company]
esgapi/core/tests/isolation/test_managers.py::test_the_company_models_are_the_ones_we_know
esgapi/core/tests/isolation/test_static_rules.py::test_every_company_model_defaults_to_the_refusing_manager
esgapi/core/tests/isolation/test_static_rules.py::test_product_code_opens_company_tables_only_through_for_company
esgapi/core/tests/isolation/test_static_rules.py::test_the_company_entrances_are_called_only_from_their_place
esgapi/core/tests/test_selector_scope.py::test_selectors_scope_every_read[organization/service/selectors/organization.py]
esgapi/organization/tests/management/commands/test_seed_company.py::test_a_licence_number_taken_by_another_company_is_refused
esgapi/organization/tests/management/commands/test_seed_company.py::test_a_new_company_is_made_active_and_its_id_printed
esgapi/organization/tests/management/commands/test_seed_company.py::test_a_second_company_can_be_made
esgapi/organization/tests/management/commands/test_seed_company.py::test_the_same_subdomain_with_other_values_is_refused
esgapi/organization/tests/management/commands/test_seed_company.py::test_the_same_values_twice_leave_one_row
esgapi/organization/tests/service/selectors/test_organization.py::test_an_active_company_is_found_with_its_id
esgapi/organization/tests/service/selectors/test_organization.py::test_an_inactive_company_is_its_own_branch
esgapi/organization/tests/service/selectors/test_organization.py::test_an_unknown_subdomain_is_unknown
esgapi/organization/tests/test_models.py::test_a_licence_number_or_subdomain_is_unique
esgapi/organization/tests/test_models.py::test_a_new_row_is_inactive_by_default
esgapi/organization/tests/test_models.py::test_a_subdomain_out_of_form_is_refused_by_the_db[-tenant]
esgapi/organization/tests/test_models.py::test_a_subdomain_out_of_form_is_refused_by_the_db[]
esgapi/organization/tests/test_models.py::test_a_subdomain_out_of_form_is_refused_by_the_db[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
esgapi/organization/tests/test_models.py::test_a_subdomain_out_of_form_is_refused_by_the_db[tenant_a]
esgapi/organization/tests/test_models.py::test_a_subdomain_out_of_form_is_refused_by_the_db[Tenant-A]
esgapi/organization/tests/test_models.py::test_by_subdomain_finds_one_row_active_or_not
esgapi/organization/tests/test_models.py::test_for_company_opens_only_that_row
esgapi/organization/tests/test_models.py::test_register_makes_an_active_company
NEW
  [ "$STEP" -ge 2 ] && cat <<'NEW'
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db['1'-Site]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db['1'-User]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[-1-Site]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[-1-User]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[0-Site]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[0-User]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[None-Site]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[None-User]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[True-Site]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[True-User]
esgapi/core/tests/isolation/test_managers.py::test_a_user_in_another_company_is_not_overwritten
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_company_is_refused_before_the_db[Site]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_company_is_refused_before_the_db[User]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[all-Site]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[all-User]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[count-Site]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[count-User]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[create-Site]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[create-User]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[filter-Site]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[filter-User]
esgapi/core/tests/isolation/test_managers.py::test_the_company_default_manager_is_the_refusing_one[Site]
esgapi/core/tests/isolation/test_managers.py::test_the_company_default_manager_is_the_refusing_one[User]
esgapi/core/tests/test_selector_scope.py::test_company_services_only_write_and_name_the_company
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[organization/service/services/organization.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[user/service/services/user.py]
esgapi/organization/tests/service/apis/test_organization.py::test_editor_and_admin_create_a_site_in_their_own_tenant[admin]
esgapi/organization/tests/service/apis/test_organization.py::test_editor_and_admin_create_a_site_in_their_own_tenant[editor]
esgapi/organization/tests/service/apis/test_organization.py::test_site_body_cannot_carry_a_tenant
esgapi/organization/tests/service/apis/test_organization.py::test_tenant_header_is_not_a_way_in
esgapi/organization/tests/service/apis/test_organization.py::test_viewer_cannot_create_a_site
esgapi/organization/tests/service/permissions/test_organization.py::test_both_read_the_table
esgapi/organization/tests/service/permissions/test_organization.py::test_the_values_are_what_they_were
esgapi/organization/tests/service/selectors/test_organization.py::test_all_sites_gives_one_tenants_sites_without_rls
esgapi/organization/tests/service/selectors/test_organization.py::test_the_sites_query_names_the_tenant
esgapi/organization/tests/service/selectors/test_organization.py::test_the_sites_route_shows_only_the_sessions_tenant_without_rls
esgapi/organization/tests/service/services/test_organization.py::test_editor_creates_in_the_session_tenant
esgapi/organization/tests/service/services/test_organization.py::test_viewer_lists_but_cannot_create
esgapi/user/tests/service/apis/test_auth.py::test_permitted_session_returns_the_session_or_raises_forbidden
esgapi/user/tests/service/apis/test_user.py::test_an_inactive_company_is_403_unknown_tenant
esgapi/user/tests/service/apis/test_user.py::test_an_oversized_exchange_body_is_413_and_nothing_is_echoed
esgapi/user/tests/service/apis/test_user.py::test_body_cannot_carry_tenant_or_user
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_algorithm0]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_algorithm1]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_claims]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-bad_signature]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-expired]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-malformed]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-wrong_audience]
esgapi/user/tests/service/apis/test_user.py::test_each_rejection_has_its_own_code_and_no_session[<lambda>-wrong_issuer]
esgapi/user/tests/service/apis/test_user.py::test_first_exchange_creates_the_user_and_sets_the_cookie
esgapi/user/tests/service/apis/test_user.py::test_me_and_logout
esgapi/user/tests/service/apis/test_user.py::test_same_external_id_from_another_issuer_would_be_another_user
esgapi/user/tests/service/apis/test_user.py::test_second_exchange_upserts_name_and_role
esgapi/user/tests/service/apis/test_user.py::test_tampered_or_expired_cookie_is_401_with_its_own_code
esgapi/user/tests/service/apis/test_user.py::test_unknown_path_is_404_in_the_one_error_shape
esgapi/user/tests/service/apis/test_user.py::test_unknown_tenant_is_403_and_nothing_is_created
esgapi/user/tests/service/services/test_user.py::test_a_sub_in_another_company_is_this_companys_own_user
esgapi/user/tests/service/services/test_user.py::test_ok_verifies_then_looks_up_then_upserts
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[bad_algorithm]
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[bad_claims]
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[bad_signature]
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[expired]
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[malformed]
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[wrong_audience]
esgapi/user/tests/service/services/test_user.py::test_rejected_token_keeps_its_reason_and_never_touches_the_db[wrong_issuer]
esgapi/user/tests/service/services/test_user.py::test_the_user_scope_opens_only_its_company_not_the_neighbours
esgapi/user/tests/service/services/test_user.py::test_unknown_tenant_is_rejected_and_no_user_is_written
esgapi/user/tests/service/services/test_user.py::test_upsert_user_neither_sees_nor_touches_another_companys_row
esgapi/user/tests/service/utils/test_exchange.py::test_claims_are_read_from_a_verified_payload
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[name-None]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[role-None]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[role-bad10]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[role-superadmin]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[sub-123]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[sub-None]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[sub-]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-../x]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-None]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-Tenant-A]
esgapi/user/tests/service/utils/test_exchange.py::test_missing_or_misshapen_claims_are_bad_claims[tenant_id-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
esgapi/user/tests/service/utils/test_exchange.py::test_only_editor_and_above_create_sites[admin-True]
esgapi/user/tests/service/utils/test_exchange.py::test_only_editor_and_above_create_sites[editor-True]
esgapi/user/tests/service/utils/test_exchange.py::test_only_editor_and_above_create_sites[viewer-False]
esgapi/user/tests/service/utils/test_exchange.py::test_registered_tenant_is_admitted
esgapi/user/tests/service/utils/test_exchange.py::test_roles_are_exactly_the_three_in_the_plan
esgapi/user/tests/service/utils/test_exchange.py::test_session_freezes_tenant_and_role_and_expires_after_ttl
esgapi/user/tests/service/utils/test_exchange.py::test_tenant_id_shape_matches_the_ts_skeleton
esgapi/user/tests/service/utils/test_exchange.py::test_unknown_tenant_is_rejected_by_name
esgapi/user/tests/service/utils/test_session_tokens.py::test_a_company_id_out_of_form_is_malformed[bool]
esgapi/user/tests/service/utils/test_session_tokens.py::test_a_company_id_out_of_form_is_malformed[missing]
esgapi/user/tests/service/utils/test_session_tokens.py::test_a_company_id_out_of_form_is_malformed[negative]
esgapi/user/tests/service/utils/test_session_tokens.py::test_a_company_id_out_of_form_is_malformed[text]
esgapi/user/tests/service/utils/test_session_tokens.py::test_a_company_id_out_of_form_is_malformed[zero]
esgapi/user/tests/service/utils/test_session_tokens.py::test_edk_token_is_not_a_session
esgapi/user/tests/service/utils/test_session_tokens.py::test_expired_session_is_rejected_with_its_reason
esgapi/user/tests/service/utils/test_session_tokens.py::test_garbage_cookie_is_malformed
esgapi/user/tests/service/utils/test_session_tokens.py::test_no_cookie_is_absent_not_rejected
esgapi/user/tests/service/utils/test_session_tokens.py::test_our_session_is_not_an_edk_token
esgapi/user/tests/service/utils/test_session_tokens.py::test_round_trip
esgapi/user/tests/service/utils/test_session_tokens.py::test_session_signed_with_another_secret_is_rejected
esgapi/user/tests/service/utils/test_session_tokens.py::test_the_read_session_carries_the_company_that_was_signed
esgapi/user/tests/service/utils/test_tokens.py::test_alg_none_is_rejected
esgapi/user/tests/service/utils/test_tokens.py::test_attacker_key_in_jwk_header_is_ignored
esgapi/user/tests/service/utils/test_tokens.py::test_claim_lengths_stop_at_the_table_columns[iss]
esgapi/user/tests/service/utils/test_tokens.py::test_claim_lengths_stop_at_the_table_columns[name]
esgapi/user/tests/service/utils/test_tokens.py::test_claim_lengths_stop_at_the_table_columns[sub]
esgapi/user/tests/service/utils/test_tokens.py::test_expired_token_is_rejected
esgapi/user/tests/service/utils/test_tokens.py::test_garbage_is_malformed
esgapi/user/tests/service/utils/test_tokens.py::test_missing_required_claims_are_rejected
esgapi/user/tests/service/utils/test_tokens.py::test_only_rs256_is_allowed
esgapi/user/tests/service/utils/test_tokens.py::test_swap_public_key_as_hs256_secret_is_rejected
esgapi/user/tests/service/utils/test_tokens.py::test_token_signed_with_another_key_is_rejected
esgapi/user/tests/service/utils/test_tokens.py::test_valid_token_is_ok
esgapi/user/tests/service/utils/test_tokens.py::test_wrong_audience_is_rejected
esgapi/user/tests/service/utils/test_tokens.py::test_wrong_issuer_is_rejected
esgapi/user/tests/test_models.py::test_a_service_username_is_unique_within_its_company
esgapi/user/tests/test_models.py::test_an_admin_username_is_unique_across_the_whole_table
esgapi/user/tests/test_models.py::test_for_company_opens_only_that_companys_rows
esgapi/user/tests/test_models.py::test_kind_and_company_go_together
esgapi/user/tests/test_models.py::test_level_is_one_of_the_three[0]
esgapi/user/tests/test_models.py::test_level_is_one_of_the_three[100]
esgapi/user/tests/test_models.py::test_level_is_one_of_the_three[50]
esgapi/user/tests/test_models.py::test_level_is_one_of_the_three[80]
esgapi/user/tests/test_models.py::test_the_same_service_username_lives_in_two_companies
esgapi/user/tests/test_models.py::test_the_three_levels_are_accepted
tests/security/test_exchange_tenant.py::test_exchange_for_an_inactive_company_is_403
tests/security/test_exchange_tenant.py::test_user_already_in_another_tenant_is_its_own_user
tests/security/test_migrations.py::test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip
tests/security/test_tenant_paths.py::test_numeric_neighbour_ids_never_show_up_for_my_session
NEW
  [ "$STEP" -ge 3 ] && cat <<'NEW'
esgapi/core/tests/isolation/test_static_rules.py::test_the_root_manager_is_taken_out_only_in_its_place
NEW
  return 0
}
export -f sha changed outside env_value expected_gone expected_new 2> /dev/null
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
