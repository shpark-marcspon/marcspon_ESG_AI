#!/usr/bin/env bash
# 밴드 W1b 의 심은 파손 열아홉: 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-W1b.sh --pure         1~9 (컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/9
#         apps/api-py/scripts/planted-breaks-W1b.sh --containers   10~19 (compose 의 postgres 가 떠 있어야 한다). 마지막 줄 PLANTED=<잡은 수>/10
#         apps/api-py/scripts/planted-breaks-W1b.sh                1~19. 마지막 줄 PLANTED=<잡은 수>/19
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다). 8 만 다르다: 테스트가 아니라 lint-imports 의 계약 (라)가 깨져야 한다.
# 15·16 은 이 밴드가 0줄로 둔 core/documents/services.py 에 심는다(되돌린 뒤 sha256 을 본다).
# 10~19 는 업무·보안 층만 쓴다(떠 있는 서버의 이미지·DB 는 건드리지 않는다). 브로커를 쓰지 않는다.
# bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

A=apps/api-py
RULES="$A/esgapi/core/calc/jobs.py"
CELERY="$A/esgapi/config/celery.py"
HOOKS="$A/esgapi/core/documents/hooks.py"
SUMMARY="$A/esgapi/reconcile/calc/job_summary.py"
TASKS="$A/esgapi/reconcile/tasks.py"
JOBS="$A/esgapi/core/documents/jobs.py"
SERVICES="$A/esgapi/core/documents/services.py"
REQUEUE="$A/esgapi/core/management/commands/requeue_jobs.py"
COMPOSE=compose.yaml
T_RULES=esgapi/core/tests/test_jobs_calc.py
T_CELERY=esgapi/core/tests/test_celery_conf.py
T_HOOK=esgapi/core/tests/test_jobs_hook.py
T_SUMMARY=esgapi/reconcile/tests/test_job_summary.py
T_ENV=esgapi/config/tests/test_env.py
T_JOBS=esgapi/core/tests/test_jobs_services.py
T_TASK=esgapi/reconcile/tests/test_tasks_parse.py
T_SEC=tests/security/test_jobs.py
T_RACE=tests/security/test_documents_race.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$RULES" "$CELERY" "$HOOKS" "$SUMMARY" "$TASKS" "$JOBS" "$SERVICES" "$REQUEUE" "$COMPOSE")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자>   글자가 정확히 한 번 있어야 한다(없으면 심지 못한 것이다: 종료 3)
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
pure_tests() { (cd "$A" && uv run --frozen pytest -q -rf -m "not django_db and not security" "$@"); }
business_tests() { "$A/scripts/test-business.sh" -rf "$@"; }
security_tests() { "$A/scripts/test-security.sh" -rf "$@"; }
# <번호와 설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local name="$1" file="$2" code="$3" caught=0 wanted
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED' "$file" | sed 's/^/    /' | cut -c1-220 | head -8
  [ "$code" -ne 0 ] || caught=1
  for wanted in "$@"; do
    grep -q "^FAILED .*$wanted" "$file" || { caught=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
# 트랜잭션은 열되 테넌트를 싣지 않는 가짜(10·18 이 tenant_transaction 의 자리에 심는다).
SHIM=$'from django.db import transaction\n\n\ndef tenant_transaction(tenant_id: str):\n    return transaction.atomic()\n'

pure() {
  # 1. 판정이 임대가 안 지난 processing 을 잡는다.
  edit "$RULES" '    if status == "processing" and lease_expires_at is not None and lease_expires_at > now:' '    if False:' || exit 3
  pure_tests "$T_RULES" > "$log/1.txt" 2>&1; code=$?
  judge "1. claim_decision 이 임대가 안 지난 processing 을 잡는다" "$log/1.txt" "$code" test_the_claim_decision_is_exactly_the_written_table

  # 2. 판정이 done 을 잡는다.
  edit "$RULES" '    if status == "done" or status == "failed":' '    if status == "failed":' || exit 3
  pure_tests "$T_RULES" > "$log/2.txt" 2>&1; code=$?
  judge "2. claim_decision 이 done 을 잡는다" "$log/2.txt" "$code" test_the_claim_decision_is_exactly_the_written_table test_a_finished_job_is_never_taken_whatever_the_lease_or_attempts

  # 3. celery_conf 에서 task_acks_late 를 뺌.
  edit "$CELERY" $'        "task_acks_late": True,\n' '' || exit 3
  pure_tests "$T_CELERY" > "$log/3.txt" 2>&1; code=$?
  judge "3. celery_conf 에서 task_acks_late 를 뺌" "$log/3.txt" "$code" test_the_conf_is_exactly_these_names_and_values

  # 4. celery_conf 에 result_backend 를 더함.
  edit "$CELERY" $'        "task_ignore_result": True,\n' $'        "task_ignore_result": True,\n        "result_backend": "rpc://",\n' || exit 3
  pure_tests "$T_CELERY" > "$log/4.txt" 2>&1; code=$?
  judge "4. celery_conf 에 result_backend 를 더함" "$log/4.txt" "$code" test_there_is_no_result_backend_and_the_queue_is_always_predefined

  # 5. 갈고리가 쪽지에 storage_key 를 싣는다.
  edit "$HOOKS" 'kwargs={"tenant_id": tenant_id, "job_id": str(job_id)},' 'kwargs={"tenant_id": tenant_id, "job_id": str(job_id), "storage_key": "tenants/x"},' || exit 3
  pure_tests "$T_HOOK" > "$log/5.txt" 2>&1; code=$?
  judge "5. 갈고리가 kwargs 에 storage_key 를 싣는다" "$log/5.txt" "$code" test_the_note_carries_the_task_name_two_ids_the_queue_and_no_retry

  # 6. 갈고리가 retry=False 를 뺌.
  edit "$HOOKS" $'        retry=False,\n' '' || exit 3
  pure_tests "$T_HOOK" > "$log/6.txt" 2>&1; code=$?
  judge "6. 갈고리가 retry=False 를 뺌" "$log/6.txt" "$code" test_the_note_carries_the_task_name_two_ids_the_queue_and_no_retry

  # 7. 요약이 첫 블록의 글을 싣는다.
  edit "$SUMMARY" '"warnings": len(parsed.warnings),' '"warnings": len(parsed.warnings), "first_text": str(parsed.document.blocks[0].text),' || exit 3
  pure_tests "$T_SUMMARY" > "$log/7.txt" 2>&1; code=$?
  judge "7. parse_summary 가 첫 블록의 글을 싣는다" "$log/7.txt" "$code" test_the_summary_has_exactly_the_fixed_keys_and_only_numbers_and_booleans

  # 8. 태스크 파일이 esgapi.core.models 를 직접 들인다. 테스트가 아니라 lint-imports 의 계약 (라)가 깨져야 한다.
  edit "$TASKS" $'from esgapi.core.ports.parser import DocumentParser\n' $'from esgapi.core.models import JobRow as _PlantedJobRow  # noqa: F401\nfrom esgapi.core.ports.parser import DocumentParser\n' || exit 3
  (cd "$A" && uv run --frozen lint-imports) > "$log/8.txt" 2>&1; code=$?
  total=$((total + 1))
  grep -E 'BROKEN|Contracts:' "$log/8.txt" | sed 's/^/    /' | cut -c1-220
  if [ "$code" -ne 0 ] && grep -A1 '^라\. ' "$log/8.txt" | grep -q 'BROKEN' && grep -q 'Contracts: 3 kept, 1 broken' "$log/8.txt"; then
    ok=$((ok + 1)); echo "8. reconcile/tasks.py 가 esgapi.core.models 를 직접 들인다 → 잡음(lint-imports 계약 라)"
  else
    echo "8. reconcile/tasks.py 가 esgapi.core.models 를 직접 들인다 → ★ 못 잡음"; tail -15 "$log/8.txt" | sed 's/^/    | /'
  fi
  restore_files

  # 9. compose 의 worker-py 에 주인 역할의 주소를 더함.
  edit "$COMPOSE" $'      <<: *api-py-env\n' $'      <<: *api-py-env\n      DATABASE_URL_PY_OWNER: postgres://owner:pw@postgres:5432/esg_py\n' || exit 3
  pure_tests "$T_ENV" > "$log/9.txt" 2>&1; code=$?
  judge "9. compose 의 worker-py 에 DATABASE_URL_PY_OWNER 를 더함" "$log/9.txt" "$code" test_compose_worker_py_takes_the_api_py_environment_and_no_owner_address
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in 10 11 12 13 14 15 16 17 18 19; do total=$((total + 1)); echo "$n. → ★ 못 잼(compose 의 postgres 가 떠 있지 않다)"; done
    return
  fi

  # 10. 태스크가 tenant_transaction 대신 transaction.atomic() (테넌트를 싣지 않는다).
  #     업무 층은 초록이어야 한다(그 층에는 RLS 가 없다). 빨개지는 것은 보안 층의 「끝까지」다(0행 → JobNotFound).
  edit "$TASKS" $'from esgapi.core.tenancy.tasks import tenant_transaction\n' "$SHIM" || exit 3
  business_tests "$T_TASK" > "$log/10b.txt" 2>&1; bcode=$?
  security_tests "$T_SEC" > "$log/10.txt" 2>&1; code=$?
  if [ "$bcode" -eq 0 ]; then echo "    (10 에서 업무 층은 초록이다: $(grep -E '^[0-9]+ passed' "$log/10b.txt"))"; else echo "    (★ 10 에서 업무 층도 빨갛다 — 보고에 적는다)"; grep -E '^FAILED' "$log/10b.txt" | head -5 | sed 's/^/    | /'; fi
  judge "10. 태스크가 tenant_transaction 대신 transaction.atomic()" "$log/10.txt" "$code" test_the_task_runs_to_done_in_two_transactions_with_the_work_outside

  # 11. 잡기에서 select_for_update() 를 뺌.
  edit "$JOBS" 'row = JobRow.objects.select_for_update().filter(pk=job_id).first()' 'row = JobRow.objects.filter(pk=job_id).first()' || exit 3
  business_tests "$T_JOBS" > "$log/11.txt" 2>&1; code=$?
  security_tests "$T_SEC" > "$log/11s.txt" 2>&1; scode=$?
  cat "$log/11s.txt" >> "$log/11.txt"; [ "$scode" -ne 0 ] || code=0
  judge "11. 잡기에서 select_for_update() 를 뺌" "$log/11.txt" "$code" test_the_claim_locks_the_row_before_it_writes test_two_connections_reading_the_same_queued_job_end_it_once

  # 12. 끝내기의 조건에서 attempts= 를 뺌.
  edit "$JOBS" 'guard = JobRow.objects.filter(pk=job_id, status="processing", attempts=attempt)' 'guard = JobRow.objects.filter(pk=job_id, status="processing")' || exit 3
  business_tests "$T_TASK" "$T_JOBS" > "$log/12.txt" 2>&1; code=$?
  judge "12. finish_job 의 조건에서 attempts= 를 뺌" "$log/12.txt" "$code" test_a_worker_that_was_taken_over_answers_late_and_writes_nothing test_a_worker_that_was_taken_over_cannot_write

  # 13. ETag 견주기를 뺌.
  edit "$TASKS" '    if got.etag != document.etag:' '    if False:' || exit 3
  business_tests "$T_TASK" > "$log/13.txt" 2>&1; code=$?
  judge "13. ETag 견주기를 뺌" "$log/13.txt" "$code" test_an_object_swapped_after_the_confirm_is_not_parsed

  # 14. 저장소·파서를 트랜잭션 안에서 부른다.
  edit "$TASKS" $'        outcome = parse_document(claimed.document)  # 트랜잭션 밖\n' $'        with tenant_transaction(tenant_id):\n            outcome = parse_document(claimed.document)\n' || exit 3
  security_tests "$T_SEC" > "$log/14.txt" 2>&1; code=$?
  judge "14. 저장소·파서를 트랜잭션 안에서 부른다" "$log/14.txt" "$code" test_the_task_runs_to_done_in_two_transactions_with_the_work_outside

  # 15. 올림 확인에서 select_for_update() 를 뺌(0줄로 둔 services.py 에 심는다). 한쪽이 던진다.
  edit "$SERVICES" 'locked = DocumentRow.objects.select_for_update().get(pk=document_id)' 'locked = DocumentRow.objects.get(pk=document_id)' || exit 3
  security_tests "$T_RACE" > "$log/15.txt" 2>&1; code=$?
  grep -q '갱신이 0행이다' "$log/15.txt" || { code=0; echo "    (까닭이 다르다: 「갱신이 0행」으로 던진 것이 아니다)"; }
  judge "15. confirm_upload 에서 select_for_update() 를 뺌" "$log/15.txt" "$code" test_two_confirms_of_the_same_document_make_one_job

  # 16. 15 + `if updated != 1` 과 status= 조건을 뺌. 일감이 둘이 된다.
  edit "$SERVICES" 'locked = DocumentRow.objects.select_for_update().get(pk=document_id)' 'locked = DocumentRow.objects.get(pk=document_id)' || exit 3
  edit "$SERVICES" 'DocumentRow.objects.filter(pk=document_id, status="awaiting_upload").update(' 'DocumentRow.objects.filter(pk=document_id).update(' || exit 3
  edit "$SERVICES" '            if updated != 1:' '            if False:' || exit 3
  security_tests "$T_RACE" > "$log/16.txt" 2>&1; code=$?
  grep -q 'assert 2 == 1' "$log/16.txt" || { code=0; echo "    (까닭이 다르다: 일감이 2 가 된 것이 아니다)"; }
  judge "16. 15 + 「갱신 1행」 검사와 status 조건을 뺌" "$log/16.txt" "$code" test_two_confirms_of_the_same_document_make_one_job

  # 17. Deferred 가 임대를 안 당긴다.
  edit "$JOBS" 'updated = guard.update(lease_expires_at=now, updated_at=now)' 'updated = guard.update(updated_at=now)' || exit 3
  business_tests "$T_TASK" "$T_JOBS" > "$log/17.txt" 2>&1; code=$?
  judge "17. Deferred 가 임대를 안 당긴다" "$log/17.txt" "$code" test_a_passing_failure_keeps_processing_pulls_the_lease_and_asks_for_a_retry test_deferred_keeps_processing_and_pulls_the_lease_to_now

  # 18. 다시 넣기 명령이 테넌트를 싣지 않고 읽는다. 고른 수가 0 이 된다.
  edit "$REQUEUE" $'from esgapi.core.tenancy.tasks import tenant_transaction\n' "$SHIM" || exit 3
  security_tests "$T_SEC" > "$log/18.txt" 2>&1; code=$?
  judge "18. requeue_jobs 가 tenant_transaction 없이 읽는다" "$log/18.txt" "$code" test_requeue_sends_only_that_tenants_jobs_and_outside_the_transaction

  # 19. 끝내기가 문서 갱신의 행 수를 안 본다.
  edit "$JOBS" '        if documents != 1:' '        if False:' || exit 3
  security_tests "$T_SEC" > "$log/19.txt" 2>&1; code=$?
  judge "19. finish_job 이 문서 갱신의 행 수를 안 본다" "$log/19.txt" "$code" test_a_done_that_cannot_write_the_document_is_an_error_and_rolls_back
}

case "$MODE" in
  --pure) pure ;;
  --containers) containers ;;
  all) pure; containers ;;
esac

# ── 끝 검사: 베껴 둔 파일과 작업 트리가 처음과 같은가 ──
restore_files
if ! sums | diff "$keep/.sums-before" - || ! git status --porcelain | diff "$keep/.status-before" -; then
  echo "★ 작업 트리가 처음과 다르다(< 처음, > 지금). PLANTED 를 내지 않는다"
  exit 1
fi
echo "PLANTED=$ok/$total"
[ "$ok" -eq "$total" ]
