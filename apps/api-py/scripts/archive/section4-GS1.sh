#!/usr/bin/env bash
# 밴드 GS1(MARC-TICK-68: 조회마다 tenant 조건을 Selector 에, 잠금 조회 둘을 Selector 로. RLS 는 그대로)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-GS1.sh --step <0~4>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-GS1.sh --pure            --step 4 전부 + 심은 파손의 순수 몫 + 휠
#         apps/api-py/scripts/section4-GS1.sh --containers      업무·보안·통합 층 한 번 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-GS1.sh --after-commit    --step 4 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. AWS 로 나가는 호출 0: 브로커는 compose 의 queue(SQS 흉내, sqs://queue:9324)뿐이다.
# 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 컨테이너 층은 기계 전체에서 한 번에 하나다: 다른 esg-app* 컨테이너가 0 이 될 때까지 기다린다(60초 간격, 최대 30분).
# ★ makemigrations --check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라 RuntimeWarning 한 줄이 난다. 기대다).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 「바」가 보안 층의 바뀐 줄을 글자로 못 박는다. 기대 줄은 아래 here-doc 이다(발주서 §1-3 의 ★★: 실은 테넌트를 넘겨
#   초록을 만드는 약해짐은 테스트를 돌려서는 안 보인다. 이 검사가 그것을 막는 기계 쪽의 문이다).
set -u
cd "$(dirname "$0")/../../.."
B=aae8afa   # 기준 커밋(발주서 §1-1)
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
TEST_DS=esgapi.config.settings.test_business
NEW_PURE=9        # 새 순수 테스트(core/tests/test_selector_scope.py). 커밋 ④ 부터
NEW_BUSINESS=11   # 새 업무 테스트(core 8 + accounts 3)
PURE=1508; [ "$STEP" -ge 4 ] && PURE=$((1508 + NEW_PURE))

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
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1-2 의 닫힌 목록) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/service/__init__\.py$' \
    -e '^apps/api-py/esgapi/core/service/selectors/(documents|jobs)\.py$' \
    -e '^apps/api-py/esgapi/core/service/services/(documents|jobs)\.py$' \
    -e '^apps/api-py/esgapi/accounts/service/selectors/accounts\.py$' \
    -e '^apps/api-py/esgapi/reference/service/selectors/reference\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tasks\.py$' \
    -e '^apps/api-py/esgapi/core/management/commands/requeue_jobs\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_jobs_services|test_documents_services)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_selector_scope|test_selectors_tenant)\.py$' \
    -e '^apps/api-py/esgapi/accounts/tests/test_services\.py$' \
    -e '^apps/api-py/esgapi/accounts/tests/test_selectors_tenant\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tests/test_tasks_parse\.py$' \
    -e '^apps/api-py/tests/security/(test_jobs|test_rls|test_documents)\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-GS1\.sh$'
}
# 보안 층에서 바뀌는 코드 줄의 전부(band-handoffs/GS1-probe/security-code-diff.expected.txt 를 글자 그대로. 뺀 줄 7 · 더한 줄 9).
# 커밋 ② 가 tests/security/test_jobs.py 의 14줄을, 커밋 ③ 이 test_rls.py 의 2줄(all_sites)을 만든다.
expected_security_diff() {
  [ "$STEP" -ge 2 ] || return 0
  cat <<'EXPECTED' | { if [ "$STEP" -ge 3 ]; then cat; else grep -v 'all_sites'; fi; }
+from esgapi.core.service.selectors import jobs as job_selectors
-from esgapi.core.service.services import jobs as job_services
-def claim(job_id: str) -> Any:
-    return claim_job(job_id=uuid.UUID(job_id), now=NOW, lease_s=90, max_attempts=3)
+def claim(job_id: str, tenant_id: str = "tenant-a") -> Any:
+    return claim_job(tenant_id=tenant_id, job_id=uuid.UUID(job_id), now=NOW, lease_s=90, max_attempts=3)
-        finish_job(job_id=uuid.UUID(job_id), attempt=1, now=NOW, outcome=Done({}, "a" * 64))
+        finish_job(tenant_id="tenant-a", job_id=uuid.UUID(job_id), attempt=1, now=NOW, outcome=Done({}, "a" * 64))
-        job_services.stale_jobs(now=NOW, queued_older_than_s=1)
+        job_selectors.stale_jobs(tenant_id="tenant-a", now=NOW, queued_older_than_s=1)
-        finish_job(job_id=uuid.UUID(b_job), attempt=1, now=NOW, outcome=Done({"pages": 1}, "a" * 64))
+        finish_job(
+            tenant_id="tenant-b", job_id=uuid.UUID(b_job), attempt=1, now=NOW, outcome=Done({"pages": 1}, "a" * 64)
+        )
-    assert selectors.all_sites() == []
+    assert selectors.all_sites("tenant-a") == []
EXPECTED
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

echo "── 밴드 GS1 §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "'"$PURE"' passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'

  echo; echo "── 나. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일"
  run 'git diff --quiet "$B" -- "$A/generated"'
  run 'for f in openapi.json api.d.ts api.d.ts.source-sha256; do test "$(sha "$A/generated/$f")" = "$(git show "$B:$A/generated/$f" | shasum -a 256 | cut -d" " -f1)" || { echo "★ 다르다: $f"; exit 1; }; done; wc -c < "$A/generated/openapi.json" | tr -d " "; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 다. RLS 와 transaction 이 그대로(마이그레이션·tenancy·models 0줄, makemigrations 가 낼 것 없음, transaction 줄의 diff 0)"
  run 'n="$(git diff --stat "$B" -- "*/migrations/*" "$A/esgapi/core/tenancy" "$A/esgapi/core/models.py" "$A/esgapi/accounts/models" "$A/esgapi/reference/models" | wc -l | tr -d " ")"; echo "  diff --stat 줄: $n"; [ "$n" = 0 ] && test "$(changed | grep -c -E "/migrations/|/core/tenancy/|/models")" = 0'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  # 제품 코드의 바뀐 줄. 아직 추적되지 않은 새 파일(커밋 전의 selectors/jobs.py)은 git diff 에 안 나오므로 줄마다 + 를 붙여 더한다.
  { git diff -U0 "$B" -- "$A/esgapi" ":!$A/esgapi/**/tests/**" | grep -E '^[+-][^+-]'
    git ls-files --others --exclude-standard -- "$A/esgapi" | grep -v '/tests/' | while IFS= read -r f; do sed 's/^/+/' "$f"; done
  } > "$T/product-diff.txt"
  run 'n="$(grep -c -E "transaction\.atomic\(|with tenant_transaction\(|transaction\.on_commit\(|set_rollback\(" "$T/product-diff.txt")"; echo "  제품 코드의 바뀐 줄 $(wc -l < "$T/product-diff.txt" | tr -d " ") 가운데 transaction 을 열고 닫는 줄: $n"; [ "$n" = 0 ]'
  if [ "$STEP" -ge 2 ]; then
    run 'grep -E "_require_transaction\(|in_atomic_block" "$T/product-diff.txt" | sort > "$T/tx-check.txt"; cat "$T/tx-check.txt"; printf "%s\n" "-    _require_transaction(\"stale_jobs\")" "+    if not connection.in_atomic_block:" | sort | diff - "$T/tx-check.txt"'
  else
    run 'n="$(grep -c -E "_require_transaction\(|in_atomic_block" "$T/product-diff.txt")"; echo "  「트랜잭션 안인가」를 확인하는 줄의 diff: $n"; [ "$n" = 0 ]'
  fi

  echo; echo "── 라. 표시와 자리(§0 의 1·2·3. 커밋 $STEP 까지)"
  local unscoped='esgapi/reference/service/selectors/reference.py'
  [ "$STEP" -lt 3 ] && unscoped="esgapi/accounts/service/selectors/accounts.py
$unscoped"
  [ "$STEP" -lt 1 ] && unscoped="$(printf '%s\n' esgapi/accounts/service/selectors/accounts.py esgapi/core/service/selectors/documents.py esgapi/reference/service/selectors/reference.py)"
  export unscoped
  run '(cd "$A" && grep -rnE "\.objects\b" esgapi/*/service/selectors/*.py | grep -vE "\.objects\.filter\((tenant_id|pk)=tenant_id[,)]" | cut -d: -f1 | sort -u > "$T/unscoped.txt"; cat "$T/unscoped.txt" | sed "s/^/  조건 없는 .objects 가 있는 파일: /"; echo "$unscoped" | diff - "$T/unscoped.txt")'
  local outside_locks=2 selector_locks=0
  [ "$STEP" -ge 1 ] && outside_locks=1 && selector_locks=1
  [ "$STEP" -ge 2 ] && outside_locks=0 && selector_locks=2
  run '(cd "$A" && o="$(grep -rn "select_for_update" esgapi --include="*.py" | grep -v /tests/ | grep -vc "/service/selectors/")"; s="$(grep -rn "select_for_update" esgapi --include="*.py" | grep -v /tests/ | grep -c "/service/selectors/")"; echo "  select_for_update: selectors 밖 $o · selectors 아래 $s"; [ "$o" = '"$outside_locks"' ] && [ "$s" = '"$selector_locks"' ])'
  if [ "$STEP" -ge 2 ]; then
    run '(cd "$A" && n="$(grep -nE "\.objects\b" esgapi/core/service/services/*.py | grep -vcE "\.objects\.create\(|\.objects\.filter\(pk=[a-z_.]+, tenant_id=tenant_id[,)]")"; echo "  core services 의 .objects $(grep -cE "\.objects\b" esgapi/core/service/services/documents.py esgapi/core/service/services/jobs.py | tr "\n" " ") 가운데 create 도 「pk, tenant_id」 조건도 아닌 줄: $n"; [ "$n" = 0 ])'
    run '(cd "$A" && n="$(grep -rnw owned_by esgapi tests --include="*.py" | grep -vc "core/tests/test_documents_api.py")"; echo "  owned_by 라는 낱말(GP1 의 test_documents_api.py 밖): $n"; [ "$n" = 0 ])'
  fi
  if [ "$STEP" -ge 4 ]; then
    run '(cd "$A" && grep -rlE "^# tenant-scope: global" esgapi --include="*.py" | grep -v /tests/ > "$T/global.txt"; cat "$T/global.txt"; echo esgapi/reference/service/selectors/reference.py | diff - "$T/global.txt" && n="$(grep -c tenant_id esgapi/reference/service/selectors/reference.py)"; echo "  그 파일의 tenant_id 라는 글자: $n"; [ "$n" = 0 ])'
    run '(cd "$A" && grep -rnE "tenant_id 조건이 없|WHERE 가 없" esgapi/*/service/selectors esgapi/*/service/services; n="$(grep -rnE "tenant_id 조건이 없|WHERE 가 없" esgapi/*/service/selectors esgapi/*/service/services | wc -l | tr -d " ")"; echo "  selectors·services 에 남은 낡은 글: $n"; [ "$n" = 0 ])'
  fi

  echo; echo "── 마. 테스트가 사라지지 않았다(기준의 노드 ID 는 git archive 사본에서 뜬다)"
  mkdir -p "$T/base"
  git archive "$B" "$A" compose.yaml | tar -x -C "$T/base"
  ln -s "$ROOT/.env" "$T/base/.env"   # 통합 층의 conftest 가 뿌리의 .env 를 읽는다(모으기만 한다. 베끼지 않고 가리킨다)
  run '(cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt"); (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt"); b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; gone="$(comm -23 "$T/base-nodeids.txt" "$T/nodeids.txt" | wc -l | tr -d " ")"; comm -13 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/new-nodeids.txt"; new="$(wc -l < "$T/new-nodeids.txt" | tr -d " ")"; stray="$(grep -vcE "^esgapi/(core/tests/(test_selector_scope|test_selectors_tenant)|accounts/tests/test_selectors_tenant)\.py::" "$T/new-nodeids.txt")"; echo "  기준 $b · 지금 $n · 사라진 것 $gone · 새 것 $new (새 파일 셋 밖의 것 $stray)"; cut -d: -f1 "$T/new-nodeids.txt" | uniq -c; [ "$b" = 1891 ] && [ "$gone" = 0 ] && [ "$stray" = 0 ] && { [ "'"$STEP"'" -lt 4 ] || [ "$n" = '"$((1891 + NEW_PURE + NEW_BUSINESS))"' ]; }'
  run '(cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider -m security 2> /dev/null | grep "::" | sort > "$T/base-sec.txt"); (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider -m security 2> /dev/null | grep "::" | sort > "$T/sec.txt"); echo "  보안 층의 노드 ID: 기준 $(wc -l < "$T/base-sec.txt" | tr -d " ") · 지금 $(wc -l < "$T/sec.txt" | tr -d " ")"; test "$(wc -l < "$T/sec.txt" | tr -d " ")" = 67 && cmp "$T/base-sec.txt" "$T/sec.txt"'
  run '(cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider -c tests_integration/pytest.ini tests_integration 2> /dev/null | grep "::" | sort > "$T/base-int.txt"); (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider -c tests_integration/pytest.ini tests_integration 2> /dev/null | grep "::" | sort > "$T/int.txt"); echo "  통합 층의 노드 ID: 기준 $(wc -l < "$T/base-int.txt" | tr -d " ") · 지금 $(wc -l < "$T/int.txt" | tr -d " ")"; test "$(wc -l < "$T/int.txt" | tr -d " ")" = 14 && cmp "$T/base-int.txt" "$T/int.txt"'

  echo; echo "── 바. 보안 층에서 바뀐 것이 부르는 꼴뿐 — 글자로 못 박는다(커밋 $STEP 까지)"
  git diff -U0 "$B" -- "$A/tests/security" | grep -E '^[+-][^+-]' > "$T/sec-diff-all.txt"
  grep -v 'tenant_id 조건이 없다' "$T/sec-diff-all.txt" | sort > "$T/sec-diff.txt"
  expected_security_diff | sort > "$T/sec-expected.txt"
  local words=0; [ "$STEP" -ge 3 ] && words=2; [ "$STEP" -ge 4 ] && words=4
  local claims=0 tenant_b=0; [ "$STEP" -ge 2 ] && claims=1 && tenant_b=1
  run 'echo "  보안 층의 바뀐 줄 전부:"; sed "s/^/    /" "$T/sec-diff-all.txt"; diff "$T/sec-expected.txt" "$T/sec-diff.txt" && echo "  기대 $(wc -l < "$T/sec-expected.txt" | tr -d " ")줄과 글자까지 같다"'
  run 'w="$(grep -c "tenant_id 조건이 없다" "$T/sec-diff-all.txt")"; b="$(grep "^+" "$T/sec-diff.txt" | grep -c "\"tenant-b\"")"; c="$(grep -c -F "+def claim(job_id: str, tenant_id: str = \"tenant-a\") -> Any:" "$T/sec-diff.txt")"; am="$(grep "^-" "$T/sec-diff.txt" | grep -c -w assert)"; ap="$(grep "^+" "$T/sec-diff.txt" | grep -c -w assert)"; echo "  머리말의 글 줄 $w · 더한 줄의 \"tenant-b\" $b · claim 의 기본값 tenant-a $c · assert 뺀 줄 $am 더한 줄 $ap"; [ "$w" = '"$words"' ] && [ "$b" = '"$tenant_b"' ] && [ "$c" = '"$claims"' ] && [ "$am" = "$ap" ]'

  echo; echo "── 사. 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$B" -- . ":!$A/scripts/section4-GS1.sh" ":!$A/scripts/planted-breaks-GS1.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-GS1\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+.*($marks)" "$T/all.diff")"; minus="$(grep -c -E "^-.*($marks)" "$T/all.diff")"; echo "  더한 줄 $plus · 뺀 줄 $minus (이 밴드의 스크립트 둘은 뺀다: 무늬를 글자로 적은 줄이 있다)"; grep -E "^\+.*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" = 0 ]'

  echo; echo "── 아. 경계"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- compose.yaml scripts docker infra apps/web README.md "$A/uv.lock" "$A/pyproject.toml" "$A/.importlinter"'
  run 'git diff --quiet "$B" -- "$A/esgapi/*/service/apis" "$A/esgapi/*/service/permissions" "$A/esgapi/accounts/service/services" "$A/esgapi/inventory" "$A/esgapi/config" "$A/esgapi/core/calc" "$A/esgapi/core/resources" "$A/esgapi/core/llm"'
  run '(cd "$A" && git show "$B:$A/esgapi/reference/service/selectors/reference.py" > "$T/reference-base.py" && uv run --frozen python - "$T/reference-base.py" esgapi/reference/service/selectors/reference.py <<"PY"
import ast, sys
def code(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    assert isinstance(tree.body[0], ast.Expr)  # 머리 docstring
    return ast.dump(ast.Module(body=tree.body[1:], type_ignores=[]))
same = code(sys.argv[1]) == code(sys.argv[2])
print("  reference selectors 의 코드(머리 docstring·주석을 뺀 AST):", "같다" if same else "★ 다르다")
sys.exit(0 if same else 1)
PY
)'
  if [ "$STEP" -ge 2 ]; then
    run 'git diff -U0 "$B" -- "$A/esgapi/reconcile/tasks.py" | grep -E "^(@@|[+-][^+-])"; h="$(git diff -U0 "$B" -- "$A/esgapi/reconcile/tasks.py" | grep -c "^@@")"; s="$(git diff --numstat "$B" -- "$A/esgapi/reconcile/tasks.py" | cut -f1,2 | tr "\t" " ")"; echo "  reconcile/tasks.py: 덩어리 $h · 더한 줄과 뺀 줄 $s"; [ "$h" = 2 ] && [ "$s" = "10 2" ]'
  else
    run 'git diff --quiet "$B" -- "$A/esgapi/reconcile/tasks.py"'
  fi
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 5 kept, 0 broken." && exit $code; exit 1)'
}

pure_extra_part() {
  echo; echo "── 자. 심은 파손의 순수 몫(P1·P5·P12·P14·P16)"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-GS1.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=5/5" && exit $code; exit 1'
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

containers_part() {
  echo; echo "── 차. 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. scripts/worktree-env.sh GS1 으로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
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
  layer "업무 층" "$((316 + NEW_BUSINESS))" "$A/scripts/test-business.sh" -n 2
  layer "보안 층" 67 "$A/scripts/test-security.sh"
  layer "통합 층" 14 "$A/scripts/test-integration.sh" -s
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  echo; echo "── 자. 심은 파손의 컨테이너 몫(업무 열하나 + 거꾸로 심기 R)"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-GS1.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=12/12" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 7'   # ⓪~⑤ 여섯 + 검증자의 권고를 닫은 test: 커밋 하나
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-68" "Concerns: MARC-ISSUE-62" "Concerns: MARC-ISSUE-66"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

export -f sha changed outside expected_security_diff gate env_value 2> /dev/null
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
