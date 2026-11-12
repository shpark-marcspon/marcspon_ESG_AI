#!/usr/bin/env bash
# 밴드 K1u-b(MARC-TICK-93: K1u-a 위에서 core 의 세 표 — 문서·일감·기록 — 를 숫자 id·회사 칸으로 옮기고 core 마이그레이션을
# 0001 하나로 다시 쓴다)의 §4 자기검증. 틀은 section4-K1u-a.sh·section4-E1a.sh.
#   사용: apps/api-py/scripts/section4-K1u-b.sh --step <0~3>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-K1u-b.sh --pure            --step 3 전부 + 심은 파손의 순수 몫
#         apps/api-py/scripts/section4-K1u-b.sh --containers      업무·보안·통합 층 한 번 + 정책 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-K1u-b.sh --after-commit    --step 3 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. 브로커는 compose 의 queue(sqs://queue:9324)뿐이다. 네트워크는 uv·docker·pnpm 의 설치뿐이다.
# bash 전용이다(${PIPESTATUS[0]}). git grep -E 에 \s 를 쓰지 않는다([[:space:]]).
#
# ★ 컨테이너 층에 들어가기 전 문(발주서 b-1-1, 사용자 결정 2026-10-15 밤): 자기 밖 esg-app* compose 프로젝트 둘 이하,
#   빌드 중인 것 0(실행 파일이 docker 인 줄만), 메모리 free 20% 이상, 1분 부하 24 미만. 60초 간격, 최대 30분.
#   T2 가 먼저 병합돼 scripts/with-build-lock.sh 가 있으면 build 는 그것으로 감싼다.
# ★ makemigrations --check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라 RuntimeWarning 한 줄이 난다. 기대다).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 코드의 셈은 AST 로 한다(글자 셈은 docstring 을 문다). 옛 이름의 글자 셈(사.)만은 docstring 까지 문다 — 낡은 글을 고쳤다.
set -u
cd "$(dirname "$0")/../../.."
B=7a8d21e   # 기준 커밋 = 이 가지가 갈라진 자리(감독 덧붙임 「바닥 확정」: 054812c 뒤 G1c·FW1b — 닫힌 목록 파일 diff 0)
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
export A E B T TEST_DS STEP

# 층마다의 수(기준 7a8d21e 의 수집: 순수 2,097 · 업무 419 · 보안 107). 커밋마다 정해진 이름만 늘고 준다(나.).
PURE_AT=(2097 2137 2137 2137)
BUSINESS_AT=(419 432 432 432)
SECURITY_AT=(107 107 109 109)
INTEGRATION=21   # 기준의 통합 층 수(이름 그대로 — 회사 칸 줄만 고친다)
PURE="${PURE_AT[$STEP]}"; BUSINESS="${BUSINESS_AT[$STEP]}"; SECURITY="${SECURITY_AT[$STEP]}"
export PURE BUSINESS SECURITY
PURE_PLANTED="7/7"; CONTAINER_PLANTED="6/6"   # planted-breaks-K1u-b.sh 의 순수 몫 Pb2·3·4·5·6·8(둘), 컨테이너 몫 Pb1·2·4·6·7·Rb
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
# 허용 경로(발주서 b-1-2 의 닫힌 목록) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/models\.py$' \
    -e '^apps/api-py/esgapi/core/migrations/' \
    -e '^apps/api-py/esgapi/core/tenancy/(rls|__init__|middleware)\.py$' \
    -e '^apps/api-py/esgapi/core/isolation/(__init__|managers|foreign_keys|grants)\.py$' \
    -e '^apps/api-py/esgapi/core/service/(apis|selectors|services)/(documents|jobs)\.py$' \
    -e '^apps/api-py/esgapi/core/service/schemas/documents\.py$' \
    -e '^apps/api-py/esgapi/core/service/__init__\.py$' \
    -e '^apps/api-py/esgapi/core/calc/documents\.py$' \
    -e '^apps/api-py/esgapi/core/resources/queue\.py$' \
    -e '^apps/api-py/esgapi/core/llm/sink_db\.py$' \
    -e '^apps/api-py/esgapi/core/management/commands/(llm_call|requeue_jobs)\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tasks\.py$' \
    -e '^apps/api-py/esgapi/inventory/service/(apis|services)/inventory\.py$' \
    -e '^apps/api-py/esgapi/core/tests/isolation/(test_managers|test_foreign_keys|test_static_rules)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_documents_api|test_documents_calc|test_documents_models|test_jobs_hook|test_jobs_services|test_permissions_wiring|test_selector_scope|test_selectors_tenant|test_storage_adapter|test_observability_api)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_documents_services|test_llm_sink_db|test_transaction_rules)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/service/apis/test_runs\.py$' \
    -e '^apps/api-py/esgapi/core/tests/tenancy/test_middleware\.py$' \
    -e '^apps/api-py/esgapi/core/tests/llm/test_embedding\.py$' \
    -e '^apps/api-py/esgapi/config/tests/test_api_contract\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tests/(test_tasks_parse|test_tasks_registered|test_task_note)\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/(test_api|test_scope3_api|test_scope3_services)\.py$' \
    -e '^apps/api-py/conftest\.py$' \
    -e '^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$' \
    -e '^apps/api-py/tests/security/(conftest|seed|test_documents_race|test_jobs|test_reference|test_tenant_paths|test_migrations|test_owner)\.py$' \
    -e '^apps/api-py/tests/security/(test_documents|test_llm_log|test_tenant_boundary|test_request_transactions)\.py$' \
    -e '^apps/api-py/tests/security/test_same_(tenant|company)_foreign_keys\.py$' \
    -e '^apps/api-py/tests/support/db\.py$' \
    -e '^apps/api-py/tests_integration/(conftest|test_upload_flow|test_flow|test_worker_flow)\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-K1u-b\.sh$'
}
# 컨테이너 앞의 문(발주서 b-1-1 의 규칙). 60초마다, 최대 30분.
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

echo "── 밴드 K1u-b §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음), 계약 여섯"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "$PURE passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; exit $code)'

  echo; echo "── 다. generated: 코드에서 다시 뽑은 openapi 가 커밋된 파일과 바이트 동일, 기준 대비 diff 는 처분 1 의 다섯뿐(① 뒤), apps/web 0줄"
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
    elif isinstance(a, list) and isinstance(b, list) and len(a) == len(b):
        for i, (x, y) in enumerate(zip(a, b)): walk(x, y, path + [str(i)])
    elif a != b:
        diffs.append(("바뀜", path, (a, b)))
walk(base, now, [])
for kind, path, value in diffs:
    print("  ", kind, "/".join(path), json.dumps(value, ensure_ascii=False)[:160])
def param_index(route, method):
    params = base["paths"][route][method]["parameters"]
    return str([p["name"] for p in params].index("document_id"))
want = []
if step >= 1:
    uuid_path = {"format": "uuid", "title": "Document Id", "type": "string"}
    for route, method in (("/documents/{document_id}", "get"), ("/documents/{document_id}/confirm", "post")):
        at = ["paths", route, method, "parameters", param_index(route, method), "schema"]
        want.append(("뺌", at + ["format"], "uuid"))
        want.append(("바뀜", at + ["type"], ("string", "integer")))
    for schema in ("DocumentListItemOut", "DocumentOut", "JobOut"):
        want.append(("바뀜", ["components", "schemas", schema, "properties", "id", "type"], ("string", "integer")))
got = sorted(diffs, key=lambda d: (d[1], d[0])); want = sorted(want, key=lambda d: (d[1], d[0]))
print(f"  diff {len(diffs)}개 (기대 {len(want)}: 경로 칸 둘의 format 뺌·type 바뀜, DocumentOut·DocumentListItemOut·JobOut 의 id type)")
sys.exit(0 if got == want else 1)
PY'
  run 'test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3; if [ "$STEP" -lt 1 ]; then git diff --quiet "$B" -- "$A/generated"; else test "$(cut -d" " -f1 < "$A/generated/api.d.ts.source-sha256")" = "$(sha "$A/generated/openapi.json")"; fi'

  echo; echo "── 라. 마이그레이션(makemigrations 가 낼 것 없음, core 는 0001_initial 하나, organization 에 기댐, rls 없음)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'if [ "$STEP" -lt 1 ]; then git diff --quiet "$B" -- "$E/core/migrations" "$E/core/models.py" "$E/core/tenancy/rls.py"; exit; fi; got="$(cd "$E/core/migrations" && ls *.py | tr "\n" " ")"; echo "  core/migrations: $got"; [ "$got" = "0001_initial.py __init__.py " ] || exit 1; all="$(cd "$E" && ls */migrations/0*.py | tr "\n" " ")"; echo "  마이그레이션 파일: $all"; [ "$all" = "core/migrations/0001_initial.py organization/migrations/0001_initial.py reference/migrations/0001_reference.py user/migrations/0001_initial.py " ]'
  run 'if [ "$STEP" -lt 1 ]; then exit 0; fi; (cd "$A" && uv run --frozen python - <<"PY"
import ast, pathlib, sys
tree = ast.parse(pathlib.Path("esgapi/core/migrations/0001_initial.py").read_text(encoding="utf-8"))
deps = None
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "dependencies" for t in node.targets):
        deps = ast.literal_eval(node.value)
print(f"  core 0001 의 dependencies = {deps}")
sys.exit(0 if deps == [("organization", "0001_initial")] else 1)
PY
)'
  run 'if [ "$STEP" -lt 1 ]; then exit 0; fi; n="$(git grep -n -E "esgapi\.core\.tenancy\.rls|from esgapi\.core\.tenancy import rls" -- "$A/esgapi" "$A/tests" "$A/tests_integration" "$A/conftest.py" | wc -l | tr -d " ")"; echo "  tenancy.rls 의 import: $n · rls.py $(test -e "$E/core/tenancy/rls.py" && echo 있음 || echo 없음)"; [ "$n" = 0 ] && [ ! -e "$E/core/tenancy/rls.py" ]'

  echo; echo "── 마. 경계(닫힌 목록, 0줄 파일)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'd="$(git diff --no-renames --name-only --diff-filter=D "$B" | grep -v -E "^$E/core/migrations/000[1-4]_[a-z_]+\.py$|^$E/core/tenancy/rls\.py$|^$A/tests/security/test_same_tenant_foreign_keys\.py$" | wc -l | tr -d " ")"; echo "  core 의 옛 마이그레이션·rls.py·이름 바꾼 보안 파일 밖에서 지운 파일: $d"; [ "$d" = 0 ]'
  run 'git diff --quiet "$B" -- "$E/organization" "$E/user" "$E/greenwash" "$E/config/celery.py" "$E/core/tenancy/session.py" "$E/core/tests/test_observability_worker.py" "$E/core/tests/test_observability_jsonlog.py" "$E/core/tests/test_celery_conf.py" "$E/core/llm/types.py" "$E/core/service/apis/runs.py" "$E/core/service/schemas/runs.py" "$E/core/permissions.py" "$E/config/api.py" "$A/.importlinter" "$A/pyproject.toml" "$A/uv.lock" compose.yaml scripts README.md && test -z "$(git ls-files --others --exclude-standard -- "$E/organization" "$E/user" "$E/greenwash")"'
  run 'git diff -U0 "$B" -- "$A/tests_integration/test_worker_flow.py" | grep "^@@" | tee "$T/wf-hunks.txt"; python3 -I - "$T/wf-hunks.txt" <<"PY"
import re, sys
bad = 0
for line in open(sys.argv[1]):
    m = re.match(r"@@ -(\d+)(?:,(\d+))?", line)
    start = int(m.group(1)); n = int(m.group(2) or 1); end = start + max(n, 1) - 1
    ok = (start >= 130 and end <= 145) or (start >= 316 and end <= 324)
    print("  덩어리 :%d-%d %s" % (start, end, "" if ok else "★ 허용(:137-141·:320 근처) 밖"))
    bad |= not ok
sys.exit(1 if bad else 0)
PY'

  echo; echo "── 바. system check(설정 넷, -W error) — 「(1 silenced)」 그대로"
  run '(cd "$A" && uv run --frozen python - <<"PY"
import subprocess, sys
from esgapi.config.tests.test_system_check import SETTINGS, env_for
want = "System check identified no issues (1 silenced)."
bad = 0
for name in SETTINGS:
    done = subprocess.run([sys.executable, "-W", "error", "manage.py", "check", "--fail-level", "WARNING"], env=env_for(name), capture_output=True, text=True, check=False)
    last = (done.stdout.strip().splitlines() or [done.stderr.strip()[-200:]])[-1]
    print(f"  {name}: {last}")
    bad |= done.returncode != 0 or last != want
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
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · 사라진 것 $(wc -l < "$T/gone.txt" | tr -d " ") · 새 것 $(wc -l < "$T/new.txt" | tr -d " ")"; [ "$b" = 2623 ] && diff "$T/gone-expected.txt" "$T/gone.txt"'
  run 'diff "$T/new-expected.txt" "$T/new.txt"'
  run '(cd "$A" && for m in "not django_db and not security" django_db security; do printf "  %-32s %s\n" "$m" "$(uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "$m" 2> /dev/null | grep -c "::")"; done) | tee "$T/layers.txt"; b="$(sed -n "2p" "$T/layers.txt" | awk "{print \$NF}")"; s="$(sed -n "3p" "$T/layers.txt" | awk "{print \$NF}")"; echo "  기대: 업무 $BUSINESS · 보안 $SECURITY"; [ "$b" = "$BUSINESS" ] && [ "$s" = "$SECURITY" ]'

  echo; echo "── 사. 셈: 옛 이름의 글자 0(① 뒤), 제품(esgapi 의 tests·migrations 밖, AST)의 트랜잭션 경계 10·1·3 그대로, 숨은 길 0"
  run 'if [ "$STEP" -lt 1 ]; then exit 0; fi; where="$A/esgapi $A/conftest.py"; [ "$STEP" -ge 2 ] && where="$where $A/tests $A/tests_integration"; echo "  범위: $where (보안·통합은 ② 부터)"; git grep -n -E "for_tenant\(|TENANT_FIELD|tenant_key|same_tenant_foreign_key|TenantScoped|CrossTenantWriteError|tag_tenant|TENANT_ID_SHAPE" -- $where > "$T/old-names.txt"; n="$(wc -l < "$T/old-names.txt" | tr -d " ")"; head -20 "$T/old-names.txt"; echo "  옛 이름의 글자: $n (기대 0)"; [ "$n" = 0 ]'
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
expect = {
    "esgapi/core/llm/sink_db.py": (2, 0, 0),
    "esgapi/core/management/commands/requeue_jobs.py": (1, 0, 1),
    "esgapi/core/service/services/documents.py": (2, 1, 0),
    "esgapi/organization/service/services/organization.py": (1, 0, 0),
    "esgapi/reconcile/tasks.py": (2, 0, 2),
    "esgapi/reference/admin/services/importer.py": (1, 0, 0),
    "esgapi/user/service/services/user.py": (1, 0, 0),
}
for p in sorted(set(now) | set(expect)):
    mark = "" if now.get(p) == expect.get(p) == was.get(p) else f"  ★ 기대 {expect.get(p)}"
    print(f"  {p}: 기준 {was.get(p)} → 지금 {now.get(p)}{mark}")
tot = [sum(v[i] for v in now.values()) for i in range(3)]
print(f"  합: 블록 {tot[0]} · on_commit {tot[1]} · durable=True {tot[2]} (기대 10 · 1 · 3)")
bad = now != expect or was != expect or tot != [10, 1, 3]
# 숨은 길: 제품의 .unscoped, <회사 범위 모델 여섯>.objects
names = {"Company", "User", "Site", "DocumentRow", "JobRow", "LlmCallLogRow"}
hits = []
for p in now_paths:
    tree = ast.parse(pathlib.Path(p).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute) and node.attr == "unscoped":
            hits.append(f"{p}:{node.lineno} .unscoped")
        if isinstance(node, ast.Attribute) and node.attr == "objects" and isinstance(node.value, ast.Name) and node.value.id in names:
            hits.append(f"{p}:{node.lineno} {node.value.id}.objects")
        if step >= 1 and isinstance(node, (ast.Import, ast.ImportFrom)):
            mods = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names]
            if any(m == "esgapi.organization" or m.startswith("esgapi.organization.") for m in mods) and p.startswith("esgapi/core/"):
                hits.append(f"{p}:{node.lineno} core 가 organization 을 import")
print(f"  숨은 길: {len(hits)} (기대 0)"); [print("   ", h) for h in hits]
bad |= bool(hits)
# test_transaction_rules.py 의 MODEL_ROOTS: ① 뒤 for_tenant 가 빠진다
tree = ast.parse(pathlib.Path("esgapi/core/tests/test_transaction_rules.py").read_text(encoding="utf-8"))
roots = set()
for node in ast.walk(tree):
    if isinstance(node, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "MODEL_ROOTS" for t in node.targets):
        roots = {c.value for c in ast.walk(node.value) if isinstance(c, ast.Constant) and isinstance(c.value, str)}
print(f"  MODEL_ROOTS = {sorted(roots)}")
want_roots = {"for_company", "objects", "unscoped"} | (set() if step >= 1 else {"for_tenant"})
bad |= roots != want_roots
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 사(덧). 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다 — 지운 줄과 더한 줄의 차로 센다: 옮긴 줄은 셈이 같다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$B" -- . ":!$A/scripts/section4-K1u-b.sh" ":!$A/scripts/planted-breaks-K1u-b.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-K1u-b\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+[^+].*($marks)|^\+($marks)" "$T/all.diff")"; minus="$(grep -c -E "^-[^-].*($marks)|^-($marks)" "$T/all.diff")"; echo "  더한 줄 $plus · 지운 줄 $minus (더한 쪽이 많으면 안 된다)"; grep -E "^\+[^+].*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" -le "$minus" ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫"
  if [ ! -x "$A/scripts/planted-breaks-K1u-b.sh" ]; then echo "★ planted-breaks-K1u-b.sh 가 없다(커밋 ③ 의 것)"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return; fi
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-K1u-b.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=$PURE_PLANTED" && exit $code; exit 1'
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
  echo; echo "── 자. 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh K1u-b 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test "$PROJECT" = esg-app-k1u-b'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'
  run 'n="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  이 프로젝트의 옛 볼륨 $n (볼륨은 새로 — core 마이그레이션을 다시 썼다)"; [ "$n" = 0 ]'
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  if [ -x scripts/with-build-lock.sh ]; then
    run 'scripts/with-build-lock.sh docker compose build api-py worker-py parser 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  fi
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  # K1U_LAYERS 로 다시 돌릴 층만 고를 수 있다(빨간 층만 다시 — 기본은 셋 다와 심은 파손).
  local only="${K1U_LAYERS:-업무 보안 통합 파손}"
  case " $only " in *" 업무 "*) layer "업무" "$BUSINESS" "$A/scripts/test-business.sh" -n 2 ;; esac
  case " $only " in *" 보안 "*) layer "보안" "$SECURITY" "$A/scripts/test-security.sh" ;; esac
  case " $only " in *" 통합 "*) layer "통합" "$INTEGRATION" "$A/scripts/test-integration.sh" -s ;; esac
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  # 주인 역할로(컨테이너 안의 POSTGRES_USER, Python 쪽 DB ${POSTGRES_DB}_py): 정책·RLS 0, tenant_id 칸 표 0, 마이그레이션 기록
  run 'docker compose exec -T postgres sh -c "psql -U \"\$POSTGRES_USER\" -d \"\${POSTGRES_DB}_py\" -At -F \" \" -c \"SELECT (SELECT count(*) FROM pg_policies), (SELECT count(*) FROM pg_class WHERE relrowsecurity OR relforcerowsecurity), (SELECT count(*) FROM information_schema.columns WHERE table_schema = chr(112)||chr(117)||chr(98)||chr(108)||chr(105)||chr(99) AND column_name = chr(116)||chr(101)||chr(110)||chr(97)||chr(110)||chr(116)||chr(95)||chr(105)||chr(100)), (SELECT string_agg(app || chr(58) || name, chr(44) ORDER BY app, name) FROM django_migrations WHERE app IN (chr(99)||chr(111)||chr(114)||chr(101)))\"" | tee "$T/pol.txt"; read -r pol rls tcol core < "$T/pol.txt"; echo "  정책 $pol · RLS 표 $rls · tenant_id 칸 $tcol · core 의 기록 $core"; [ "$pol$rls$tcol" = 000 ] && [ "$core" = "core:0001_initial" ]'
  if [ -x "$A/scripts/planted-breaks-K1u-b.sh" ] && case " $only " in *" 파손 "*) true ;; *) false ;; esac; then
    echo; echo "── 자(덧). 심은 파손의 컨테이너 몫"
    git status --porcelain > "$T/before-planted.txt"
    run '"$A/scripts/planted-breaks-K1u-b.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=$CONTAINER_PLANTED" && exit $code; exit 1'
    run 'git status --porcelain | diff - "$T/before-planted.txt"'
  fi
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT[-/]" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT[-/]")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 차. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD --no-merges --first-parent; n="$(git log --format=%s --first-parent "$B"..HEAD | grep -v "^merge" | wc -l | tr -d " ")"; fixes="$(git log --format=%s --first-parent "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 4'
  run 'bad=0; for c in $(git rev-list --no-merges --first-parent "$B"..HEAD); do for t in "Ticket: MARC-TICK-93" "Derives-from: MARC-ENT-137"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

# 사라지는 노드(발주서 b-§3-2·b-§3-3 — 이름 바꿈의 옛 쪽. 짝은 expected_new). 커밋마다 늘어난다.
expected_gone() {
  [ "$STEP" -ge 1 ] && cat <<'GONE'
esgapi/core/tests/isolation/test_foreign_keys.py::test_same_tenant_foreign_key_names_the_tenant_first_and_is_checked_per_statement
esgapi/core/tests/isolation/test_foreign_keys.py::test_tenant_key_is_a_unique_on_tenant_then_id_with_a_matching_drop
esgapi/core/tests/isolation/test_foreign_keys.py::test_the_tenant_column_name_is_an_argument
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_tenant_is_refused_before_the_db[DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_tenant_is_refused_before_the_db[JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_tenant_is_refused_before_the_db[LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[all-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[all-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[all-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[count-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[count-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[count-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[create-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[create-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[create-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[empty tenant-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[empty tenant-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[empty tenant-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[filter-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[filter-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_query_is_refused_before_the_db[filter-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_for_tenant_fills_the_tenant_on_create
esgapi/core/tests/isolation/test_managers.py::test_the_default_manager_is_the_refusing_one[DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_the_default_manager_is_the_refusing_one[JobRow]
esgapi/core/tests/isolation/test_managers.py::test_the_default_manager_is_the_refusing_one[LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_the_scoped_models_are_the_five_we_know
esgapi/core/tests/isolation/test_static_rules.py::test_product_code_opens_scoped_tables_only_through_for_tenant
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[-tenant]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[../tenant-a]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[\ud14c\ub10c\ud2b8]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[tenant a]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[Tenant-A]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[tenant-a\n]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[tenant/a]
esgapi/core/tests/test_documents_models.py::test_the_migration_depends_on_core_only_and_carries_the_summary_limit
esgapi/core/tests/test_jobs_hook.py::test_a_uuid_job_id_is_sent_as_text
esgapi/core/tests/test_llm_sink_db.py::test_a_wrong_tag_counts_against_the_tag_tenants_limit
esgapi/core/tests/test_llm_sink_db.py::test_the_row_is_stored_under_the_tag_tenant
GONE
  [ "$STEP" -ge 2 ] && cat <<'GONE'
tests/security/test_llm_log.py::test_the_row_is_stored_under_the_tag_tenant
tests/security/test_same_tenant_foreign_keys.py::test_every_foreign_key_between_tenant_tables_names_the_tenant
GONE
  return 0
}
# 새 노드(이름 바꿈의 새 쪽과 새 테스트).
expected_new() {
  [ "$STEP" -ge 1 ] && cat <<'NEW'
esgapi/core/tests/isolation/test_foreign_keys.py::test_company_key_is_a_unique_on_company_then_id_with_a_matching_drop
esgapi/core/tests/isolation/test_foreign_keys.py::test_same_company_foreign_key_names_the_company_first_and_is_checked_per_statement
esgapi/core/tests/isolation/test_foreign_keys.py::test_the_company_column_is_fixed_on_both_sides
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[-1-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[-1-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[-1-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[''-Company]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[''-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[''-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[''-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[''-Site]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[''-User]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db['1'-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db['1'-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db['1'-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[0-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[0-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[0-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[None-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[None-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[None-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[True-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[True-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_bad_company_id_is_refused_before_the_db[True-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_company_is_refused_before_the_db[DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_company_is_refused_before_the_db[JobRow]
esgapi/core/tests/isolation/test_managers.py::test_a_write_for_another_company_is_refused_before_the_db[LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[all-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[all-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[all-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[count-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[count-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[count-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[create-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[create-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[create-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[filter-DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[filter-JobRow]
esgapi/core/tests/isolation/test_managers.py::test_an_unscoped_company_query_is_refused_before_the_db[filter-LlmCallLogRow]
esgapi/core/tests/isolation/test_managers.py::test_for_company_fills_the_company_on_create
esgapi/core/tests/isolation/test_managers.py::test_no_model_keeps_the_tenant_column
esgapi/core/tests/isolation/test_managers.py::test_the_company_default_manager_is_the_refusing_one[DocumentRow]
esgapi/core/tests/isolation/test_managers.py::test_the_company_default_manager_is_the_refusing_one[JobRow]
esgapi/core/tests/isolation/test_managers.py::test_the_company_default_manager_is_the_refusing_one[LlmCallLogRow]
esgapi/core/tests/isolation/test_static_rules.py::test_product_code_has_no_objects_and_no_tenant_opener
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[-1]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[-7]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key['7']
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key['tenant-a']
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[0]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[7.0]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[False]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[None]
esgapi/core/tests/test_documents_calc.py::test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key[True]
esgapi/core/tests/test_documents_models.py::test_the_migration_depends_on_organization_only_and_carries_the_summary_limit
esgapi/core/tests/test_jobs_hook.py::test_the_two_ids_are_sent_as_decimal_text[1-1]
esgapi/core/tests/test_jobs_hook.py::test_the_two_ids_are_sent_as_decimal_text[9223372036854775807-9223372036854775807]
esgapi/core/tests/test_jobs_hook.py::test_the_two_ids_are_sent_as_decimal_text[9876543-42]
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing[' 1']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['-1']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['\uff11']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['+1']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['0']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['01']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['1 ']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['1.0']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['1\\n']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['11111111111111111111']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['1e3']
esgapi/core/tests/test_llm_sink_db.py::test_a_tag_outside_the_company_id_shape_writes_nothing_and_asks_nothing['tenant-a']
esgapi/core/tests/test_llm_sink_db.py::test_a_wrong_tag_counts_against_the_limit_of_the_tagged_company
esgapi/core/tests/test_llm_sink_db.py::test_the_row_is_stored_under_the_tag_company
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query[' 1'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['-1'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query[''-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['0'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['01'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1.0'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1'-'-1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1'-'']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1'-'0']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1'-'01']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1'-'0b0e7c1e-0000-4000-8000-000000000001']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1'-'1.0']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['1\\n'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['11111111111111111111'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['tenant-a'-'1']
esgapi/reconcile/tests/test_task_note.py::test_a_note_with_the_old_kwarg_name_is_a_type_error
esgapi/reconcile/tests/test_task_note.py::test_an_int_job_id_in_the_note_would_drop_the_field_silently
esgapi/reconcile/tests/test_task_note.py::test_the_note_the_hook_sends_puts_the_job_id_into_the_worker_log[1-1]
esgapi/reconcile/tests/test_task_note.py::test_the_note_the_hook_sends_puts_the_job_id_into_the_worker_log[7-42]
esgapi/reconcile/tests/test_task_note.py::test_the_note_the_hook_sends_puts_the_job_id_into_the_worker_log[9223372036854775807-9223372036854775807]
NEW
  [ "$STEP" -ge 2 ] && cat <<'NEW'
tests/security/test_llm_log.py::test_the_row_is_stored_under_the_tag_company
tests/security/test_same_company_foreign_keys.py::test_every_foreign_key_between_company_tables_names_the_company
tests/security/test_same_company_foreign_keys.py::test_the_check_catches_a_single_column_key_between_company_tables
tests/security/test_tenant_paths.py::test_numeric_neighbour_document_ids_are_not_found_for_my_session
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
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
