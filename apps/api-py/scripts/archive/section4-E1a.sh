#!/usr/bin/env bash
# 밴드 E1a(MARC-TICK-82: RLS 를 걷고 격리를 ① 조건 ② 거절하는 기본 매니저 ③ 경로 표 ④ 순수 AST 검사 ⑤ 같은 테넌트
# 외래 키로 다시 세운다)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-E1a.sh --step <0~5>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-E1a.sh --pure            --step 5 전부 + 심은 파손의 순수 몫 + 휠
#         apps/api-py/scripts/section4-E1a.sh --containers      업무·보안·통합 층 한 번 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-E1a.sh --after-commit    --step 5 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. 브로커는 compose 의 queue(sqs://queue:9324)뿐이다. 네트워크는 uv·docker·pnpm 의 설치뿐이다.
# bash 전용이다(${PIPESTATUS[0]}). git grep -E 에 \s 를 쓰지 않는다([[:space:]]).
#
# ★ 컨테이너 층은 기계 전체에서 한 번에 하나다: 다른 esg-app* 컨테이너가 0 이 될 때까지 기다린다(60초 간격, 최대 30분).
# ★ makemigrations --check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라 RuntimeWarning 한 줄이 난다. 기대다).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
B=8204571   # 기준 커밋(발주서 §1-1)
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
SCOPED='(DocumentRow|JobRow|LlmCallLogRow|SiteRow|UserRow)'
NEW_PURE_1=37        # core/tests/isolation/test_managers.py 의 순수 몫(커밋 ①)
NEW_BUSINESS_1=3     # 같은 파일의 업무 몫(커밋 ①)
NEW_PURE_5=4         # core/tests/isolation/test_foreign_keys.py(커밋 ⑤)
NEW_PURE_4=7         # core/tests/isolation/test_static_rules.py(커밋 ④)
PURE=1614; [ "$STEP" -ge 1 ] && PURE=$((PURE + NEW_PURE_1)); [ "$STEP" -ge 4 ] && PURE=$((PURE + NEW_PURE_4)); [ "$STEP" -ge 5 ] && PURE=$((PURE + NEW_PURE_5))
C1_SUBJECT='feat(core): 회사 범위 표의 기본 매니저가 테넌트를 정하지 않은 조회를 거절한다'

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
# 허용 경로(발주서 §1-2 의 닫힌 목록 + 감독 덧붙임 5 의 tests/security/seed.py) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/isolation/(__init__|managers|foreign_keys)\.py$' \
    -e '^apps/api-py/esgapi/core/models\.py$' \
    -e '^apps/api-py/esgapi/accounts/models/__init__\.py$' \
    -e '^apps/api-py/esgapi/accounts/migrations/0003_drop_rls\.py$' \
    -e '^apps/api-py/esgapi/core/migrations/0003_drop_rls\.py$' \
    -e '^apps/api-py/esgapi/core/migrations/0004_jobs_same_tenant_document\.py$' \
    -e '^apps/api-py/esgapi/core/tenancy/(__init__|middleware|rls)\.py$' \
    -e '^apps/api-py/esgapi/core/tenancy/(db|tasks)\.py$' \
    -e '^apps/api-py/esgapi/core/__init__\.py$' \
    -e '^apps/api-py/esgapi/accounts/__init__\.py$' \
    -e '^apps/api-py/esgapi/accounts/service/services/accounts\.py$' \
    -e '^apps/api-py/esgapi/accounts/service/selectors/accounts\.py$' \
    -e '^apps/api-py/esgapi/core/service/selectors/(documents|jobs)\.py$' \
    -e '^apps/api-py/esgapi/core/service/services/(documents|jobs)\.py$' \
    -e '^apps/api-py/esgapi/core/llm/sink_db\.py$' \
    -e '^apps/api-py/esgapi/core/management/commands/(llm_call|requeue_jobs)\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tasks\.py$' \
    -e '^apps/api-py/esgapi/config/settings/base\.py$' \
    -e '^apps/api-py/esgapi/config/settings/(test_security|test_business)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/isolation/(__init__|test_managers|test_foreign_keys|test_static_rules)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_selector_scope|test_selectors_tenant|test_jobs_services|test_documents_services|test_llm_sink_db|test_documents_api|test_observability_api)\.py$' \
    -e '^apps/api-py/esgapi/accounts/tests/(test_services|test_api|test_selectors_tenant)\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tests/test_tasks_parse\.py$' \
    -e '^apps/api-py/tests/security/(conftest|test_owner|test_documents|test_documents_race|test_jobs|test_llm_log|test_reference|test_migrations)\.py$' \
    -e '^apps/api-py/tests/security/(test_rls|test_exchange_rls)\.py$' \
    -e '^apps/api-py/tests/security/(test_tenant_boundary|test_exchange_tenant|test_tenant_paths|test_same_tenant_foreign_keys|seed)\.py$' \
    -e '^apps/api-py/conftest\.py$' \
    -e '^apps/api-py/tests/__init__\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-E1a\.sh$'
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다: 다른 esg-app* 컨테이너 0, verify.lock 없음, 메모리 free 20% 이상, 1분 부하 12 미만.
# 60초마다, 최대 30분.
gate() {
  local tries=0 free load lock others
  lock="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
  while :; do
    others="$(docker ps --format '{{.Names}}' | grep -c '^esg-app')"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" = 0 ] && [ ! -e "$lock" ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: esg-app* 컨테이너 0 · verify.lock 없음 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: esg-app* 컨테이너 $others · verify.lock $([ -e "$lock" ] && echo 있음 || echo 없음) · free ${free:-?}% · 1분 부하 ${load:-?} · 30분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

echo "── 밴드 E1a §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "'"$PURE"' passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'

  echo; echo "── 다. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일, apps/web 0줄"
  run 'git diff --quiet "$B" -- "$A/generated" apps/web'
  run 'for f in openapi.json api.d.ts api.d.ts.source-sha256; do test "$(sha "$A/generated/$f")" = "$(git show "$B:$A/generated/$f" | shasum -a 256 | cut -d" " -f1)" || { echo "★ 다르다: $f"; exit 1; }; done; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 라. 마이그레이션(makemigrations 가 낼 것 없음, 새 마이그레이션 파일의 수)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  local migs=0; [ "$STEP" -ge 2 ] && migs=2; [ "$STEP" -ge 5 ] && migs=3
  run 'changed | grep "/migrations/" | sed "s/^/  /"; n="$(changed | grep -c "/migrations/")"; echo "  바뀐·새 마이그레이션 파일: $n (기대 '"$migs"')"; [ "$n" = '"$migs"' ] && git diff --quiet "$B" -- "$E/accounts/migrations/0001_initial.py" "$E/accounts/migrations/0002_rls.py" "$E/core/migrations/0001_llm_call_log.py" "$E/core/migrations/0002_documents_jobs.py" "$E/reference/migrations"'

  echo; echo "── 마. 경계(닫힌 목록, 지운 파일)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  local deleted=""
  [ "$STEP" -ge 2 ] && deleted="$E/core/tenancy/db.py
$E/core/tenancy/tasks.py"
  [ "$STEP" -ge 3 ] && deleted="$deleted
$A/tests/security/test_exchange_rls.py
$A/tests/security/test_rls.py"
  export deleted
  run 'git diff --no-renames --name-only --diff-filter=D "$B" | sort > "$T/deleted.txt"; sed "s/^/  지운 파일: /" "$T/deleted.txt"; printf "%s\n" "$deleted" | sed "/^$/d" | sort | diff - "$T/deleted.txt"'
  run 'git diff --quiet "$B" -- compose.yaml scripts docker infra README.md "$A/uv.lock" "$A/pyproject.toml" "$A/.importlinter" "$A/tests/support" "$A/tests_integration" "$E/config/api.py" "$E/core/exceptions.py" "$E/core/schemas.py" "$E/core/permissions.py" "$E/core/observability" "$E/core/tenancy/session.py" "$E/core/tenancy/context.py" "$E/inventory" "$E/reference" "$E/accounts/migrations/0001_initial.py" "$E/accounts/migrations/0002_rls.py" || exit 1; n="$(changed | grep -c -E "/service/(apis|schemas|permissions)/")"; echo "  */service/(apis|schemas|permissions) 의 바뀐 파일: $n" && [ "$n" = 0 ]'
  run '(cd "$A" && git show "$B:$E/core/tenancy/rls.py" > "$T/rls-base.py" && uv run --frozen python - "$T/rls-base.py" esgapi/core/tenancy/rls.py <<"PY"
import ast, sys
def body(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    assert isinstance(tree.body[0], ast.Expr)  # 머리 docstring
    return tree.body[1:]
base, now = body(sys.argv[1]), body(sys.argv[2])
same = [ast.dump(n) for n in base] == [ast.dump(n) for n in now[: len(base)]]
extra = [n.name for n in now[len(base) :] if isinstance(n, ast.FunctionDef)]
others = [n for n in now[len(base) :] if not isinstance(n, ast.FunctionDef)]
print("  rls.py: 기준의 문(머리 docstring 밖)", "그대로" if same else "★ 다르다", "· 더한 함수", extra)
sys.exit(0 if same and not others and extra in ([], ["release"]) else 1)
PY
)'

  echo; echo "── 나. 수집: 사라진 노드는 이름 바꿈 목록과 글자로 같고, 새 노드는 정해진 파일에만(기준의 노드 ID 는 git archive 사본에서)"
  mkdir -p "$T/base"
  git archive "$B" "$A" compose.yaml | tar -x -C "$T/base"
  ln -s "$ROOT/.env" "$T/base/.env"   # 통합 층의 conftest 가 뿌리의 .env 를 읽는다(모으기만 한다)
  (cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt")
  (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt")
  grep -v "^tests/security/" "$T/base-nodeids.txt" > "$T/base-ns.txt"; grep -v "^tests/security/" "$T/nodeids.txt" > "$T/ns.txt"
  comm -23 "$T/base-ns.txt" "$T/ns.txt" > "$T/gone.txt"; comm -13 "$T/base-ns.txt" "$T/ns.txt" > "$T/new.txt"
  expected_gone | sort > "$T/gone-expected.txt"
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · (보안 층 밖) 사라진 것 $(wc -l < "$T/gone.txt" | tr -d " ") · 새 것 $(wc -l < "$T/new.txt" | tr -d " ")"; sed "s/^/  사라짐: /" "$T/gone.txt"; [ "$b" = 2031 ] && diff "$T/gone-expected.txt" "$T/gone.txt"'
  run 'cut -d: -f1 "$T/new.txt" | uniq -c | sed "s/^/  새 노드: /"; bad=0; for f in $(cut -d: -f1 "$T/gone.txt" | sort -u); do g="$(grep -c "^$f::" "$T/gone.txt")"; a="$(grep -c "^$f::" "$T/new.txt")"; echo "  $f: 사라짐 $g · 새로 듦 $a"; [ "$g" = "$a" ] || bad=1; done; stray="$(grep -v -E "^esgapi/core/tests/isolation/" "$T/new.txt" | grep -v -x -F -f <(expected_extra_new; echo "-") | cut -d: -f1 | sort -u | while read -r f; do grep -q "^$f::" "$T/gone.txt" || echo "$f"; done)"; [ -n "$stray" ] && { echo "★ 새 노드가 정해진 파일 밖에: $stray"; bad=1; }; n="$(grep -c "^esgapi/core/tests/isolation/" "$T/new.txt")"; echo "  core/tests/isolation 의 새 노드 $n (기대 '"$NEW_ISOLATION"')"; [ "$n" = '"$NEW_ISOLATION"' ] && [ "$bad" = 0 ]'
  grep "^tests/security/" "$T/base-nodeids.txt" > "$T/base-sec.txt"; grep "^tests/security/" "$T/nodeids.txt" > "$T/sec.txt"
  comm -23 "$T/base-sec.txt" "$T/sec.txt" > "$T/sec-gone.txt"; comm -13 "$T/base-sec.txt" "$T/sec.txt" > "$T/sec-new.txt"
  expected_security_gone | sort > "$T/sec-gone-expected.txt"; expected_security_new | sort > "$T/sec-new-expected.txt"
  run 'echo "  보안 층의 노드: 기준 $(wc -l < "$T/base-sec.txt" | tr -d " ") · 지금 $(wc -l < "$T/sec.txt" | tr -d " ") · 사라짐 $(wc -l < "$T/sec-gone.txt" | tr -d " ") · 새로 $(wc -l < "$T/sec-new.txt" | tr -d " ")"; diff "$T/sec-gone-expected.txt" "$T/sec-gone.txt" && diff "$T/sec-new-expected.txt" "$T/sec-new.txt"'

  if [ "$STEP" -ge 1 ]; then
    echo; echo "── 바. 기계 치환(커밋 ① 하나의 diff): 파일 13 의 커밋 ① 판 = ruff format(기준 판에 .objects. → .unscoped.)"
    local c1; c1="$(git log --format=%H --grep "^$C1_SUBJECT" "$B"..HEAD | tail -1)"
    export c1
    run 'echo "  커밋 ①: ${c1:-<아직 없음 — 작업 트리로 잰다>}"; bad=0; reflowed=0; for f in $(subst_files); do if [ -n "$c1" ]; then git show "$c1:$f" > "$T/after.py"; else cp "$f" "$T/after.py"; fi; git show "$B:$f" | sed -E "s/$SCOPED\.objects\./\1.unscoped./g" > "$T/sed.py"; (cd "$A" && uv run --frozen ruff format --stdin-filename x.py - < "$T/sed.py") > "$T/formatted.py" 2> /dev/null; cmp -s "$T/formatted.py" "$T/after.py" || { echo "★ 치환 밖의 글자가 있다: $f"; diff "$T/formatted.py" "$T/after.py" | head -6; bad=1; }; r="$(diff "$T/sed.py" "$T/formatted.py" | grep -c "^<")"; reflowed=$((reflowed + r)); done; echo "  파일 $(subst_files | wc -l | tr -d " ") · 포매터가 다시 접은 줄 $reflowed (치환으로 120자를 넘긴 줄)"; [ "$bad" = 0 ] && [ "$(subst_files | wc -l | tr -d " ")" = 13 ]'
    run 'n="$(for f in $(subst_files); do git show "$B:$f" | grep -c -E "$SCOPED\.objects\."; done | paste -sd+ - | bc)"; echo "  기준에서 치환한 줄 $n (기대 140)"; [ "$n" = 140 ]'
  fi

  echo; echo "── 사. 글자 셈(제품 = esgapi 의 tests·migrations 밖)"
  if [ "$STEP" -ge 1 ]; then
    run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, pathlib, sys
SCOPED = {"DocumentRow", "JobRow", "LlmCallLogRow", "SiteRow", "UserRow"}
objects = for_tenant = unscoped = 0
for path in pathlib.Path("esgapi").rglob("*.py"):
    if "tests" in path.parts or "migrations" in path.parts:
        continue
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id in SCOPED:
            objects += node.attr == "objects"
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "for_tenant":
            for_tenant += isinstance(node.func.value, ast.Name) and node.func.value.id in SCOPED
        if isinstance(node, ast.Attribute) and node.attr == "unscoped":
            unscoped += 1
print(f"  (코드, AST) <범위 모델>.objects {objects} · <범위 모델>.for_tenant( {for_tenant} · .unscoped {unscoped}")
sys.exit(0 if (objects, for_tenant, unscoped) == (0, 13, 0) else 1)
PY
)'
  fi

  if [ "$STEP" -ge 2 ]; then
    run 'n="$(git grep -n -w -E "enter_tenant|tenant_transaction" -- "$E" ":!$E/**/tests/**" | wc -l | tr -d " ")"; m="$(git grep -n -E "set_config|current_setting|app\\.tenant_id" -- "$E" ":!$E/**/tests/**" ":!$E/**/migrations/**" ":!$E/core/tenancy/rls.py" | wc -l | tr -d " ")"; echo "  제품의 enter_tenant·tenant_transaction $n · set_config·current_setting·app.tenant_id(rls.py 밖) $m"; [ "$n" = 0 ] && [ "$m" = 0 ]'
    run 'for f in "$E/reconcile/tasks.py:2" "$E/core/management/commands/requeue_jobs.py:1" "$E/core/management/commands/llm_call.py:0"; do p="${f%:*}"; want="${f##*:}"; got="$(git diff -U0 "$B" -- "$p" | grep -c -E "^\\+[[:space:]]*with transaction\\.atomic\\(")"; echo "  $p: transaction.atomic( 를 더한 줄 $got (기대 $want)"; [ "$got" = "$want" ] || exit 1; done; others="$(git diff -U0 "$B" -- "$E" ":!$E/**/tests/**" ":!$E/reconcile/tasks.py" ":!$E/core/management/commands/requeue_jobs.py" ":!$E/core/tenancy/tasks.py" | grep -c -E "^[+-][[:space:]]*with transaction\\.atomic\\(")"; echo "  그 셋 밖의 제품에서 transaction.atomic( 줄의 diff: $others (지운 core/tenancy/tasks.py 의 한 줄은 뺀다 — 그 블록이 위의 셋으로 옮겼다)"; [ "$others" = 0 ] && git diff -U0 "$B" -- "$E/reconcile/tasks.py" "$E/core/management/commands/requeue_jobs.py" | grep -E "^\\+[[:space:]]*with transaction\\.atomic\\(" | grep -v -c "durable=True" | grep -q "^0$"'
  fi
  if [ "$STEP" -ge 3 ]; then
    run 'n="$(git grep -n -w -E "enter_tenant|tenant_transaction" -- "$A/esgapi" "$A/tests" "$A/conftest.py" | wc -l | tr -d " ")"; echo "  테스트까지 enter_tenant·tenant_transaction $n"; [ "$n" = 0 ]'
  fi

  echo; echo "── 사(덧). 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$B" -- . ":!$A/scripts/section4-E1a.sh" ":!$A/scripts/planted-breaks-E1a.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-E1a\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+.*($marks)" "$T/all.diff")"; echo "  더한 줄 $plus (이 밴드의 스크립트 둘은 뺀다: 무늬를 글자로 적은 줄이 있다)"; grep -E "^\+.*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" = 0 ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫(P1~P6)"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-E1a.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=6/6" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
  echo; echo "── 아(덧). 휠"
  run '"$A/scripts/check-wheel.sh" 2>&1 | tail -4; exit ${PIPESTATUS[0]}'
}

# 한 층을 돌리고 EXIT 를 찍는다. 끝 줄이 「<건수> passed」로 시작해야 한다. 다시 돌리지 않는다.
layer() { # <이름> <건수> <명령…>
  local name="$1" want="$2" code started=$SECONDS last
  shift 2
  echo; echo "▶ $*"
  "$@" > "$T/layer.txt" 2>&1; code=$?
  tail -3 "$T/layer.txt"
  last="$(tail -1 "$T/layer.txt")"
  case "$last" in "$want passed"*) ;; *) echo "★ 끝 줄이 「$want passed」로 시작하지 않는다"; code=1 ;; esac
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  if [ "$code" -ne 0 ]; then
    grep -E "^(FAILED|ERROR)" "$T/layer.txt" | head -30
    memory_pressure | grep percentage
    [ "$name" = "통합 층" ] && docker compose logs --no-color --tail 80 api-py migrate-py worker-py queue parser
  fi
}

# 층마다 기대하는 「<n> passed」(수집으로 센 값. HEAD cbea7b9 에서 pytest --collect-only 로 셌다).
#   업무: 기준 350 + 새 업무 3(core/tests/isolation/test_managers.py 의 django_db 셋. -m django_db 의 수 353 − 350)
#   보안: 82(커밋 ③ 뒤: 67 − 지움·옮김 24 + 새 39) + ⑤ 의 수 −1(새 2 − 사라짐 3) = 81(-m security 의 수)
#   통합: 17(tests_integration 의 수집. 이 밴드는 그 폴더를 안 고친다 — 기준 8204571 에서도 17. GO1 이후의 값)
NEW_BUSINESS=4   # test_managers 의 django_db 셋 + B1 의 test_tasks_parse 하나
BUSINESS=$((350 + NEW_BUSINESS))
SECURITY=81
INTEGRATION=17

# 주인 역할로 센 pg_policies 와 RLS 를 켠 표가 0 인가(떠 있는 서버의 DB, 주소는 scripts/db-env.sh 의 OWNER_DATABASE_URL).
owner_policies_are_zero() {
  (
    cd "$A" || exit 1
    # shellcheck source=db-env.sh
    . scripts/db-env.sh
    PROBE_OWNER_URL="$OWNER_DATABASE_URL" uv run --frozen python - <<'PY'
import os

import psycopg

with psycopg.connect(os.environ["PROBE_OWNER_URL"]) as conn:
    policies = conn.execute("SELECT count(*) FROM pg_policies").fetchone()
    secured = conn.execute(
        "SELECT count(*) FROM pg_class WHERE relnamespace = 'public'::regnamespace "
        "AND (relrowsecurity OR relforcerowsecurity)"
    ).fetchone()
got = (policies[0] if policies else None, secured[0] if secured else None)
print(f"  주인 역할({os.environ['PROBE_OWNER_URL'].rsplit('/', 1)[1]}): pg_policies {got[0]} · RLS 를 켠 표 {got[1]}")
raise SystemExit(0 if got == (0, 0) else 1)
PY
  )
}

containers_part() {
  echo; echo "── 자. 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh E1a 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  local PROJECT; PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test -n "$PROJECT" && test "$PROJECT" != esg-app'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'                                                                # 포트 넷이 비어 있다
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  # api-py·worker-py 가 postgres·migrate-py·storage·queue 를 끌고 뜬다. TS 의 api·worker·redis 는 띄우지 않는다.
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  run 'docker compose exec -T worker-py python -c "from urllib.parse import urlsplit; from esgapi.config.celery import app; print(app.conf.broker_url.split(\":\")[0]); assert urlsplit(app.conf.broker_url).hostname == \"queue\""'   # 브로커는 로컬 흉내
  run 'docker compose logs --no-color worker-py | grep -E "jobs\.parse|ready\." | head -3 ; docker compose logs --no-color worker-py | grep -q "jobs.parse"'   # 태스크가 등록됐다
  layer "업무 층" "$BUSINESS" "$A/scripts/test-business.sh" -n 2
  layer "보안 층" "$SECURITY" "$A/scripts/test-security.sh"
  layer "통합 층" "$INTEGRATION" "$A/scripts/test-integration.sh" -s
  # 주인 역할로 pg_policies 를 한 번 더 센다. 보안 층의 테스트 DB(<POSTGRES_DB>_py_test)는 그 세션이 끝나며 지워지므로,
  # 같은 마이그레이션이 새 볼륨에 돈 떠 있는 서버의 DB(<POSTGRES_DB>_py, migrate-py 가 migrate 한 것)를 db-env.sh 의
  # 주인 주소로 센다.
  run 'owner_policies_are_zero'
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  echo; echo "── 자(덧). 심은 파손의 컨테이너 몫(P7~P13 + 거꾸로 심기 R)"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-E1a.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=8/8" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 차. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 7'   # ⓪~⑥ 일곱 + fix: 몇 개든
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-82" "Derives-from: MARC-ENT-137"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
  local c1; c1="$(git log --format=%H --grep "^$C1_SUBJECT" "$B"..HEAD | tail -1)"
  export c1
  run 'echo "  커밋 ①: ${c1:-<없다>}"; test -n "$c1" && git log -1 --format=%B "$c1" | grep -q -x "Concerns: MARC-ISSUE-74"'
}

# 커밋 ① 의 기계 치환 파일(발주서 2-2: 14 − test_selector_scope.py).
subst_files() {
  git grep -l -E "$SCOPED\.objects\." "$B" -- "$A/esgapi" "$A/tests" | sed "s/^$B://" | grep "/tests/" | grep -v "test_selector_scope\.py$" | sort
}
# 보안 층 밖에서 사라지는 노드(이름 바꿈. 발주서 3-2·§4 나). 커밋마다 늘어난다.
expected_gone() {
  [ "$STEP" -ge 2 ] || return 0
  cat <<'GONE'
esgapi/accounts/tests/test_services.py::test_ok_verifies_then_enters_tenant_then_looks_up_then_upserts
esgapi/core/tests/test_llm_sink_db.py::test_a_wrong_tag_is_written_under_the_session_tenant_and_reported
esgapi/core/tests/test_llm_sink_db.py::test_a_wrong_tag_slips_past_both_limits_this_records_the_hole
esgapi/core/tests/test_llm_sink_db.py::test_without_a_session_tenant_the_table_is_not_asked
GONE
  [ "$STEP" -ge 5 ] || return 0
  cat <<'GONE'
esgapi/core/tests/test_jobs_services.py::test_a_job_on_another_tenants_document_is_finished_as_document_missing
esgapi/core/tests/test_selectors_tenant.py::test_another_tenants_job_on_my_document_is_not_listed
GONE
}
# 보안 층에서 사라지는 노드와 새 노드(발주서 §3-1). 커밋 ② 는 pyright 가 강제한 셋만(보고의 「발주서와 다르게」).
expected_security_gone() {
  [ "$STEP" -ge 2 ] || return 0
  if [ "$STEP" -ge 3 ]; then expected_security_gone_3; return 0; fi
  cat <<'GONE'
tests/security/test_llm_log.py::test_a_wrong_tag_is_stored_under_the_session_tenant
tests/security/test_rls.py::test_enter_tenant_outside_a_transaction_is_an_error
GONE
}
expected_security_new() {
  [ "$STEP" -ge 2 ] || return 0
  if [ "$STEP" -ge 3 ]; then expected_security_new_3; return 0; fi
  cat <<'NEW'
tests/security/test_llm_log.py::test_the_row_is_stored_under_the_tag_tenant
NEW
}
# 커밋 ③ 뒤의 보안 층(발주서 §3-1 의 처분 — 대조표는 band-reports/E1a-isolation.md).
expected_security_gone_3() {
  [ "$STEP" -ge 5 ] && printf '%s\n' \
    "tests/security/test_documents.py::test_the_foreign_key_does_not_stop_a_job_on_another_tenants_document" \
    "tests/security/test_jobs.py::test_a_done_that_cannot_write_the_document_is_an_error_and_rolls_back" \
    "tests/security/test_jobs.py::test_a_job_on_another_tenants_document_ends_as_document_missing"
  cat <<'GONE'
tests/security/test_documents.py::test_a_connection_without_a_tenant_sees_zero_rows
tests/security/test_documents.py::test_a_document_for_another_tenant_is_refused_by_the_db
tests/security/test_documents.py::test_a_job_for_another_tenant_is_refused_by_the_db
tests/security/test_exchange_rls.py::test_user_already_in_another_tenant_is_409
tests/security/test_jobs.py::test_tenant_transaction_refuses_to_open_inside_another_transaction
tests/security/test_jobs.py::test_the_tenant_does_not_outlive_the_block
tests/security/test_jobs.py::test_without_a_tenant_the_claim_sees_no_job
tests/security/test_llm_log.py::test_a_wrong_tag_is_stored_under_the_session_tenant
tests/security/test_llm_log.py::test_policy_rejects_a_raw_insert_for_another_tenant_and_a_savepoint_keeps_the_outer_alive
tests/security/test_owner.py::test_a_non_superuser_owner_is_also_held_by_the_policy
tests/security/test_owner.py::test_every_tenant_table_has_rls_enabled_and_forced
tests/security/test_owner.py::test_policy_text_compares_the_transaction_setting
tests/security/test_rls.py::test_app_role_cannot_create_tenants_or_delete
tests/security/test_rls.py::test_enter_tenant_outside_a_transaction_is_an_error
tests/security/test_rls.py::test_error_response_rolls_back_the_request_transaction
tests/security/test_rls.py::test_exchanging_again_for_another_tenant_switches_the_whole_session
tests/security/test_rls.py::test_insert_for_another_tenant_is_refused_by_the_db
tests/security/test_rls.py::test_insert_without_tenant_is_refused_by_the_db
tests/security/test_rls.py::test_query_without_where_is_still_scoped
tests/security/test_rls.py::test_session_a_sees_only_a
tests/security/test_rls.py::test_tenant_does_not_leak_from_a_to_b_on_the_same_connection
tests/security/test_rls.py::test_tenant_does_not_leak_to_the_next_request_on_the_same_connection
tests/security/test_rls.py::test_tests_run_as_the_app_role_which_cannot_bypass_rls
tests/security/test_rls.py::test_without_session_http_is_401_and_orm_sees_zero_rows
GONE
}
expected_security_new_3() {
  [ "$STEP" -ge 5 ] && printf '%s\n' \
    "tests/security/test_documents.py::test_a_job_on_another_tenants_document_is_refused_by_the_db" \
    "tests/security/test_same_tenant_foreign_keys.py::test_every_foreign_key_between_tenant_tables_names_the_tenant"
  cat <<'NEW'
tests/security/test_documents.py::test_a_document_for_another_tenant_is_refused_by_the_manager
tests/security/test_documents.py::test_a_job_for_another_tenant_is_refused_by_the_manager
tests/security/test_documents.py::test_an_unscoped_query_on_either_table_is_refused
tests/security/test_exchange_tenant.py::test_user_already_in_another_tenant_is_409
tests/security/test_jobs.py::test_task_blocks_are_durable
tests/security/test_jobs.py::test_with_another_tenant_the_claim_sees_no_job
tests/security/test_llm_log.py::test_a_rejected_insert_in_a_savepoint_keeps_the_outer_alive
tests/security/test_llm_log.py::test_the_row_is_stored_under_the_tag_tenant
tests/security/test_owner.py::test_no_table_has_row_security_or_a_policy
tests/security/test_tenant_boundary.py::test_app_role_cannot_create_tenants_or_delete
tests/security/test_tenant_boundary.py::test_error_response_rolls_back_the_request_transaction
tests/security/test_tenant_boundary.py::test_exchanging_again_for_another_tenant_switches_the_whole_session
tests/security/test_tenant_boundary.py::test_insert_for_another_tenant_is_refused_by_the_manager
tests/security/test_tenant_boundary.py::test_query_without_where_is_still_scoped
tests/security/test_tenant_boundary.py::test_session_a_sees_only_a
tests/security/test_tenant_boundary.py::test_tenant_does_not_leak_from_a_to_b_on_the_same_connection
tests/security/test_tenant_boundary.py::test_tenant_does_not_leak_to_the_next_request_on_the_same_connection
tests/security/test_tenant_boundary.py::test_tests_run_as_the_app_role_which_is_not_a_superuser
tests/security/test_tenant_boundary.py::test_without_session_http_is_401_and_an_unscoped_orm_query_is_refused
tests/security/test_tenant_paths.py::test_a_create_lands_in_my_tenant[POST /documents]
tests/security/test_tenant_paths.py::test_a_create_lands_in_my_tenant[POST /sites]
tests/security/test_tenant_paths.py::test_a_list_shows_only_my_tenant
tests/security/test_tenant_paths.py::test_another_tenants_document_is_not_found[GET /documents/{document_id}]
tests/security/test_tenant_paths.py::test_another_tenants_document_is_not_found[POST /documents/{document_id}/confirm]
tests/security/test_tenant_paths.py::test_every_id_field_in_a_request_body_is_classified
tests/security/test_tenant_paths.py::test_every_operation_is_in_the_table
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /documents/{document_id}]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /me]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /reference/factors]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /reference/sources]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /sites]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /documents]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /documents/{document_id}/confirm]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /inventory/calc]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /inventory/scope3/classify]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /inventory/scope3/shortlist]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /reference/assemble-electricity]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /reference/assemble]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /sites]
NEW
}
# 감독 처분(검증 B1, fix 커밋)으로 더한 업무 노드. 이름 바꿈이 아닌 새 노드는 이것뿐이다.
expected_extra_new() {
  cat <<'NEW'
esgapi/reconcile/tests/test_tasks_parse.py::test_a_note_with_an_empty_tenant_is_skipped_and_touches_no_row
NEW
}
NEW_ISOLATION=0; [ "$STEP" -ge 1 ] && NEW_ISOLATION=$((NEW_PURE_1 + NEW_BUSINESS_1)); [ "$STEP" -ge 4 ] && NEW_ISOLATION=$((NEW_ISOLATION + NEW_PURE_4)); [ "$STEP" -ge 5 ] && NEW_ISOLATION=$((NEW_ISOLATION + NEW_PURE_5))
export -f sha changed outside gate env_value subst_files expected_gone expected_security_gone expected_security_new expected_security_gone_3 expected_security_new_3 expected_extra_new 2> /dev/null
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
