#!/usr/bin/env bash
# 밴드 GS1 의 심은 파손 열일곱(P1~P16 + 거꾸로 심기 R): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-GS1.sh --pure         P1·P5·P12·P14·P16 (컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/5
#         apps/api-py/scripts/planted-breaks-GS1.sh --containers   나머지 열하나 + R (compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/12
#         apps/api-py/scripts/planted-breaks-GS1.sh                전부. 마지막 줄 PLANTED=<잡은 수>/17
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다).
# ★ R 만 거꾸로다: 파이썬 쪽 tenant 조건 여덟(Selector 의 문 셋·all_sites 와 Service 의 쓰기 조건 넷)을 한꺼번에 걷고
#   보안 층 전부를 돌린다. **빨개지면 안 된다**(끝 줄 「67 passed」면 잡음). 재는 것: 보안 층 67건의 답이 전부 DB 의
#   정책만으로 나온다. 못 재는 것: 그 테스트가 넘긴 tenant_id 가 진짜 주인인가(그것은 section4-GS1.sh 의 「바」가 글자로 잰다).
# 컨테이너 몫은 업무·보안 층만 쓴다(떠 있는 서버의 이미지·DB 는 건드리지 않는다). 브로커를 쓰지 않는다. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

A=apps/api-py
SD="$A/esgapi/core/service/selectors/documents.py"
SJ="$A/esgapi/core/service/selectors/jobs.py"
VD="$A/esgapi/core/service/services/documents.py"
VJ="$A/esgapi/core/service/services/jobs.py"
AS="$A/esgapi/accounts/service/selectors/accounts.py"
RS="$A/esgapi/reference/service/selectors/reference.py"
TASKS="$A/esgapi/reconcile/tasks.py"
T_SCOPE=esgapi/core/tests/test_selector_scope.py
T_CORE=esgapi/core/tests/test_selectors_tenant.py
T_ACC=esgapi/accounts/tests/test_selectors_tenant.py
T_API=esgapi/core/tests/test_documents_api.py
T_TASK=esgapi/reconcile/tests/test_tasks_parse.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$SD" "$SJ" "$VD" "$VJ" "$AS" "$RS" "$TASKS")
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
pure_tests() { (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -m "not django_db and not security" "$@"); }
business_tests() { "$A/scripts/test-business.sh" -rf -p no:cacheprovider "$@"; }
security_tests() { "$A/scripts/test-security.sh" -rf -p no:cacheprovider "$@"; }
# <번호와 설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local name="$1" file="$2" code="$3" missed=0 wanted
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for wanted in "$@"; do
    grep '^FAILED ' "$file" | grep -q -F "$wanted" || { missed=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$missed" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}

# 심는 글자(한 파일에 한 번씩만 있다).
DOC_GATE='    return DocumentRow.objects.filter(tenant_id=tenant_id)'
JOB_GATE='    return JobRow.objects.filter(tenant_id=tenant_id)'
CLAIM_GUARD='JobRow.objects.filter(pk=job_id, tenant_id=tenant_id, status=row.status, attempts=row.attempts)'
FINISH_GUARD='JobRow.objects.filter(pk=job_id, tenant_id=tenant_id, status="processing", attempts=attempt)'
FINISH_DOC='DocumentRow.objects.filter(pk=job.document_id, tenant_id=tenant_id).update('
CONFIRM_WRITE='DocumentRow.objects.filter(pk=document_id, tenant_id=tenant_id, status="awaiting_upload").update('
SITES='SiteRow.objects.filter(tenant_id=tenant_id).order_by('
plant_doc_gate() { edit "$SD" "$DOC_GATE" '    return DocumentRow.objects.all()'; }
plant_doc_jobs_gate() { edit "$SD" "$JOB_GATE" '    return JobRow.objects.all()'; }
plant_job_gate() { edit "$SJ" "$JOB_GATE" '    return JobRow.objects.all()'; }
plant_claim_guard() { edit "$VJ" "$CLAIM_GUARD" 'JobRow.objects.filter(pk=job_id, status=row.status, attempts=row.attempts)'; }
plant_finish_guard() { edit "$VJ" "$FINISH_GUARD" 'JobRow.objects.filter(pk=job_id, status="processing", attempts=attempt)'; }
plant_finish_doc() { edit "$VJ" "$FINISH_DOC" 'DocumentRow.objects.filter(pk=job.document_id).update('; }
plant_confirm_write() { edit "$VD" "$CONFIRM_WRITE" 'DocumentRow.objects.filter(pk=document_id, status="awaiting_upload").update('; }
plant_sites() { edit "$AS" "$SITES" 'SiteRow.objects.order_by('; }

pure() {
  # P1. 문서의 문이 tenant 조건 없이 전부를 연다.
  plant_doc_gate || exit 3
  pure_tests "$T_SCOPE" > "$log/P1.txt" 2>&1; code=$?
  judge "P1. selectors/documents.py 의 _documents 가 .objects.all() (순수)" "$log/P1.txt" "$code" 'test_selectors_scope_every_read[core/service/selectors/documents.py]'

  # P5. 잡기의 울타리에서 tenant 조건을 뺀다.
  plant_claim_guard || exit 3
  pure_tests "$T_SCOPE" > "$log/P5.txt" 2>&1; code=$?
  judge "P5. claim_job 의 울타리에서 tenant_id 를 뺌 (순수)" "$log/P5.txt" "$code" test_core_services_only_write_and_name_the_tenant

  # P12. reference 의 「전역 자료」 표시 줄을 지운다.
  edit "$RS" $'# tenant-scope: global — 이 파일이 읽는 표 넷(reference_*)에는 tenant 칸이 없다(전역 자료).\n' '' || exit 3
  pure_tests "$T_SCOPE" > "$log/P12.txt" 2>&1; code=$?
  judge "P12. reference 의 표시 줄을 지움 (순수)" "$log/P12.txt" "$code" 'test_selectors_scope_every_read[reference/service/selectors/reference.py]'

  # P14. 올림 확인의 ④ 가 Service 에서 스스로 잠가 읽는다(조건은 있다).
  edit "$VD" 'locked = selectors.lock_document(tenant_id=tenant_id, document_id=document_id)  # ④' 'locked = DocumentRow.objects.select_for_update().filter(pk=document_id, tenant_id=tenant_id).first()  # ④' || exit 3
  pure_tests "$T_SCOPE" > "$log/P14.txt" 2>&1; code=$?
  judge "P14. services/documents.py 의 ④ 를 Service 의 select_for_update 로 되돌림 (순수)" "$log/P14.txt" "$code" test_row_locks_live_in_selectors_only

  # P16. 끝내기가 일감을 Service 에서 스스로 읽는다(조건은 있다).
  edit "$VJ" 'job = selectors.find_job(tenant_id=tenant_id, job_id=job_id)' 'job = JobRow.objects.filter(pk=job_id, tenant_id=tenant_id).first()' || exit 3
  pure_tests "$T_SCOPE" > "$log/P16.txt" 2>&1; code=$?
  judge "P16. finish_job 이 일감을 Service 에서 읽음(조건은 있다) (순수)" "$log/P16.txt" "$code" test_core_services_only_write_and_name_the_tenant
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in P2 P3 P4 P6 P7 P8 P9 P10 P11 P13 P15 R; do total=$((total + 1)); echo "$n. → ★ 못 잼(compose 의 postgres 가 떠 있지 않다)"; done
    return
  fi

  # P2. P1 과 같은 것을 업무 층으로.
  plant_doc_gate || exit 3
  business_tests "$T_CORE" > "$log/P2.txt" 2>&1; code=$?
  judge "P2. selectors/documents.py 의 _documents 가 .objects.all() (업무)" "$log/P2.txt" "$code" test_a_document_is_found_only_by_its_tenant test_every_statement_on_the_two_tables_names_the_tenant

  # P3. 문서 쪽 일감의 문이 전부를 연다.
  plant_doc_jobs_gate || exit 3
  business_tests "$T_CORE" > "$log/P3.txt" 2>&1; code=$?
  judge "P3. selectors/documents.py 의 _jobs 가 .objects.all()" "$log/P3.txt" "$code" test_another_tenants_job_on_my_document_is_not_listed

  # P4. 일감의 문이 전부를 연다.
  plant_job_gate || exit 3
  business_tests "$T_CORE" > "$log/P4.txt" 2>&1; code=$?
  judge "P4. selectors/jobs.py 의 _jobs 가 .objects.all()" "$log/P4.txt" "$code" test_a_job_is_claimed_only_under_its_tenant test_stale_jobs_and_requeue_see_one_tenant

  # P6. P5 와 같은 것을 업무 층으로(동작으로는 못 잡는다: 앞의 읽기가 이미 걸렀다. SQL 의 글자가 잡는다).
  plant_claim_guard || exit 3
  business_tests "$T_CORE" > "$log/P6.txt" 2>&1; code=$?
  judge "P6. claim_job 의 울타리에서 tenant_id 를 뺌 (업무)" "$log/P6.txt" "$code" test_every_statement_on_the_two_tables_names_the_tenant

  # P7. 끝내기의 울타리에서 뺀다.
  plant_finish_guard || exit 3
  business_tests "$T_CORE" > "$log/P7.txt" 2>&1; code=$?
  judge "P7. finish_job 의 울타리에서 tenant_id 를 뺌" "$log/P7.txt" "$code" test_a_job_is_finished_only_under_its_tenant

  # P8. 끝내기의 문서 갱신에서 뺀다.
  plant_finish_doc || exit 3
  business_tests "$T_CORE" > "$log/P8.txt" 2>&1; code=$?
  judge "P8. finish_job 의 문서 갱신에서 tenant_id 를 뺌" "$log/P8.txt" "$code" test_done_does_not_write_another_tenants_document

  # P9. 올림 확인의 갱신 조건에서 뺀다.
  plant_confirm_write || exit 3
  business_tests "$T_CORE" > "$log/P9.txt" 2>&1; code=$?
  judge "P9. confirm_upload 의 갱신 조건에서 tenant_id 를 뺌" "$log/P9.txt" "$code" test_every_statement_on_the_two_tables_names_the_tenant

  # P10. 사업장 조회에서 조건을 뺀다.
  plant_sites || exit 3
  business_tests "$T_ACC" > "$log/P10.txt" 2>&1; code=$?
  judge "P10. all_sites 의 .filter(tenant_id=tenant_id) 를 뺌" "$log/P10.txt" "$code" test_all_sites_gives_one_tenants_sites_without_rls test_the_sites_route_shows_only_the_sessions_tenant_without_rls

  # P11. list_sites 가 세션이 아닌 상수의 테넌트를 넘긴다.
  edit "$AS" 'all_sites(session.tenant_id)' 'all_sites("tenant-b")' || exit 3
  business_tests "$T_ACC" > "$log/P11.txt" 2>&1; code=$?
  judge "P11. list_sites 가 all_sites(\"tenant-b\") 를 부름" "$log/P11.txt" "$code" test_the_sites_route_shows_only_the_sessions_tenant_without_rls

  # P13. 문서의 잠가 읽기에서 잠금을 뺀다.
  edit "$SD" '_documents(tenant_id).select_for_update().filter(pk=document_id).first()' '_documents(tenant_id).filter(pk=document_id).first()' || exit 3
  business_tests "$T_CORE" "$T_API" > "$log/P13.txt" 2>&1; code=$?
  judge "P13. lock_document 의 .select_for_update() 를 뺌" "$log/P13.txt" "$code" test_the_lock_reads_name_the_tenant_and_lock test_confirm_reads_the_document_for_update

  # P15. 태스크가 잡기에 쪽지의 것이 아닌 테넌트를 넘긴다.
  edit "$TASKS" $'            tenant_id=tenant_id,\n            job_id=job_uuid,\n' $'            tenant_id="tenant-b",\n            job_id=job_uuid,\n' || exit 3
  business_tests "$T_TASK" > "$log/P15.txt" 2>&1; code=$?
  judge "P15. reconcile/tasks.py 의 잡기에 tenant_id=\"tenant-b\"" "$log/P15.txt" "$code" test_a_queued_job_runs_to_done

  # R. 거꾸로 심기: 파이썬 쪽 tenant 조건 여덟을 한꺼번에 걷는다. 보안 층 전부가 초록이어야 한다(67 passed).
  { plant_doc_gate && plant_doc_jobs_gate && plant_job_gate && plant_sites \
      && plant_claim_guard && plant_finish_guard && plant_finish_doc && plant_confirm_write; } || exit 3
  local left
  left="$(grep -c 'tenant_id=tenant_id' "$SD" "$SJ" "$VD" "$VJ" "$AS" | tr '\n' ' ')"
  security_tests > "$log/R.txt" 2>&1; code=$?
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED' "$log/R.txt" | sed 's/^/    /' | cut -c1-230 | head -12
  echo "    (걷은 뒤 다섯 파일에 남은 「tenant_id=tenant_id」 줄 수: $left — 남은 것은 부르는 인자다)"
  case "$(tail -1 "$log/R.txt")" in
    "67 passed"*) if [ "$code" -eq 0 ]; then ok=$((ok + 1)); echo "R. 파이썬 쪽 tenant 조건 여덟을 걷어도 보안 층 67 passed → 잡음(초록이어야 하는 것이 초록)"; else echo "R. → ★ 종료 코드 $code"; fi ;;
    *) echo "R. 파이썬 쪽 tenant 조건 여덟을 걷으니 보안 층이 67 passed 가 아니다 → ★ (그 단언은 DB 가 아니라 파이썬 조건의 답을 보고 있다)"; tail -15 "$log/R.txt" | sed 's/^/    | /' ;;
  esac
  restore_files
}

case "$MODE" in
  --pure) pure ;;
  --containers) containers ;;
  all) pure; containers ;;
esac

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
if ! diff -q "$keep/.sums-before" "$keep/.sums-after" > /dev/null || ! git status --porcelain | diff -q - "$keep/.status-before" > /dev/null; then
  echo "★ 되돌린 뒤의 지문이 처음과 다르다" >&2
  diff "$keep/.sums-before" "$keep/.sums-after" >&2
  git status --porcelain | diff - "$keep/.status-before" >&2
  exit 1
fi
echo "(되돌림 확인: 파일 ${#FILES[@]}개의 sha256 과 git status 가 처음과 같다)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
