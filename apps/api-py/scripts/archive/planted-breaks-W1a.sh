#!/usr/bin/env bash
# 밴드 W1a 의 심은 파손 열일곱: 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-W1a.sh --pure         1~9·17 (컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/10
#         apps/api-py/scripts/planted-breaks-W1a.sh --containers   10~16 (compose 의 postgres 가 떠 있어야 한다). 마지막 줄 PLANTED=<잡은 수>/7
#         apps/api-py/scripts/planted-breaks-W1a.sh                1~17. 마지막 줄 PLANTED=<잡은 수>/17
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다).
# 10·11·16 은 마이그레이션을 고친다: 보안 층은 실행마다 테스트 DB 를 새로 만들어 마이그레이션하므로 그대로 잰다.
#   떠 있는 서버의 DB 와 이미지는 건드리지 않는다(컨테이너 안의 코드를 바꾸지 않는다).
# bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

A=apps/api-py
CALC="$A/esgapi/core/calc/documents.py"
ADAPTER="$A/esgapi/core/adapters/storage.py"
MODELS="$A/esgapi/core/models.py"
CORE_API="$A/esgapi/core/api.py"
CONFIG_API="$A/esgapi/config/api.py"
MIGRATION="$A/esgapi/core/migrations/0002_documents_jobs.py"
SERVICES="$A/esgapi/core/documents/services.py"
T_CALC=esgapi/core/tests/test_documents_calc.py
T_ADAPTER=esgapi/core/tests/test_storage_adapter.py
T_MODELS=esgapi/core/tests/test_documents_models.py
T_CONTRACT=esgapi/config/tests/test_api_contract.py
T_API=esgapi/core/tests/test_documents_api.py
T_OWNER=tests/security/test_owner.py
T_SECURITY=tests/security/test_documents.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$CALC" "$ADAPTER" "$MODELS" "$CORE_API" "$CONFIG_API" "$MIGRATION" "$SERVICES")
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

pure() {
  # 1. 문서 전이표에 uploaded → awaiting_upload 를 허용.
  edit "$CALC" '    "uploaded": (),' '    "uploaded": ("awaiting_upload",),' || exit 3
  pure_tests "$T_CALC" > "$log/1.txt" 2>&1; code=$?
  judge "1. 문서 전이표에 uploaded → awaiting_upload 를 허용" "$log/1.txt" "$code" test_document_transitions_are_exactly_the_one_written_here test_nothing_leaves_a_finished_state

  # 2. 키 짓기가 테넌트 id 의 꼴을 안 본다.
  edit "$CALC" '    if TENANT_ID_SHAPE.match(tenant_id) is None:' '    if False:' || exit 3
  pure_tests "$T_CALC" > "$log/2.txt" 2>&1; code=$?
  judge "2. 키 짓기가 테넌트 id 의 꼴을 안 본다" "$log/2.txt" "$code" 'test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key\[tenant/a\]'

  # 3. 서명을 internal 클라이언트로(안쪽 이름으로 서명한 주소가 나간다).
  edit "$ADAPTER" 'url: Any = self.external.generate_presigned_url(' 'url: Any = self.internal.generate_presigned_url(' || exit 3
  pure_tests "$T_ADAPTER" > "$log/3.txt" 2>&1; code=$?
  judge "3. 서명을 internal 클라이언트로" "$log/3.txt" "$code" test_the_upload_url_is_signed_for_the_public_name_with_the_size_as_a_condition

  # 17. 서명에서 ContentLength 를 뺌(크기가 서명 조건이 아니게 된다).
  edit "$ADAPTER" 'Params={"Bucket": self.bucket, "Key": key, "ContentLength": content_length},' 'Params={"Bucket": self.bucket, "Key": key},' || exit 3
  pure_tests "$T_ADAPTER" > "$log/17.txt" 2>&1; code=$?
  # 3 과 같은 테스트가 빨개진다. 까닭이 다른지 본다: 호스트는 그대로(바깥 이름)이고 서명한 헤더가 host 뿐이다.
  grep -q "\['host'\] == \['content-length;host'\]" "$log/17.txt" || code=0
  judge "17. 서명에서 ContentLength 를 뺌" "$log/17.txt" "$code" test_the_upload_url_is_signed_for_the_public_name_with_the_size_as_a_condition

  # 4. head 가 403 을 ObjectMissing 으로(권한 없음을 「안 올라옴」으로 읽는다).
  edit "$ADAPTER" '    if status == 404:' '    if status in (403, 404):' || exit 3
  pure_tests "$T_ADAPTER" > "$log/4.txt" 2>&1; code=$?
  judge "4. 403 을 ObjectMissing 으로" "$log/4.txt" "$code" 'test_head_and_get_sort_failures_by_http_status_only\[403-403-StorageDenied\]' 'test_head_and_get_sort_failures_by_http_status_only\[403-SignatureDoesNotMatch-StorageDenied\]'

  # 5. get 이 상한 없이 다 읽는다.
  edit "$ADAPTER" 'chunk: bytes = body.read(max_bytes + 1 - total)' 'chunk: bytes = body.read()' || exit 3
  pure_tests "$T_ADAPTER" > "$log/5.txt" 2>&1; code=$?
  judge "5. get 이 상한 없이 다 읽는다" "$log/5.txt" "$code" test_get_stops_at_the_limit_even_when_the_declared_length_lies test_get_without_a_declared_length_also_stops_at_the_limit

  # 6. Config 에서 when_required 둘을 뺌.
  edit "$ADAPTER" $'        request_checksum_calculation="when_required",\n        response_checksum_validation="when_required",\n' '' || exit 3
  pure_tests "$T_ADAPTER" > "$log/6.txt" 2>&1; code=$?
  judge "6. Config 에서 when_required 둘을 뺌" "$log/6.txt" "$code" test_two_clients_one_per_name_with_the_written_down_config

  # 7. JobRow 에 result = JSONField(null=True) 를 더함(분해 결과가 들어갈 칸).
  edit "$MODELS" $'    finished_at = models.DateTimeField(null=True)\n\n    class Meta(BaseModel.Meta):\n        db_table = "core_jobs"' $'    finished_at = models.DateTimeField(null=True)\n    result = models.JSONField(null=True)\n\n    class Meta(BaseModel.Meta):\n        db_table = "core_jobs"' || exit 3
  pure_tests "$T_MODELS" > "$log/7.txt" 2>&1; code=$?
  judge "7. JobRow 에 result = JSONField(null=True) 를 더함" "$log/7.txt" "$code" test_job_columns_are_exactly_the_written_list test_table_names_and_the_only_json_column

  # 8. core/api.py 의 operation_id 하나를 지움(ninja 가 모듈 경로로 이름을 짓는다).
  edit "$CORE_API" $'    operation_id="core_documents_get",\n' '' || exit 3
  pure_tests "$T_CONTRACT" > "$log/8.txt" 2>&1; code=$?
  judge "8. core/api.py 의 operation_id 하나를 지움" "$log/8.txt" "$code" test_operation_ids_are_the_hand_written_table

  # 9. config/api.py 의 auth=session_cookie 를 뺌. 빨개져야 하는 것(순수): 계약의 security 검사.
  #    업무 층의 401 테스트는 --containers 가 같은 파손으로 한 번 더 본다(아래 9b. PLANTED 에는 세지 않는다).
  edit "$CONFIG_API" 'api.add_router("/documents", core_router, auth=session_cookie)' 'api.add_router("/documents", core_router)' || exit 3
  pure_tests "$T_CONTRACT" > "$log/9.txt" 2>&1; code=$?
  judge "9. config/api.py 의 auth=session_cookie 를 뺌" "$log/9.txt" "$code" test_the_document_operations_require_the_session_cookie
}

extra_failed=0
containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in 10 11 12 13 14 15 16; do total=$((total + 1)); echo "$n. → ★ 못 잼(compose 의 postgres 가 떠 있지 않다)"; done
    return
  fi

  # 9b(덤. 세지 않는다). 9 와 같은 파손에서 업무 층의 401 테스트가 빨개지는가.
  edit "$CONFIG_API" 'api.add_router("/documents", core_router, auth=session_cookie)' 'api.add_router("/documents", core_router)' || exit 3
  business_tests "$T_API" > "$log/9b.txt" 2>&1; code=$?
  if [ "$code" -ne 0 ] && grep -q '^FAILED .*test_without_a_session_every_document_path_is_401' "$log/9b.txt"; then
    echo "9b(덤). auth=session_cookie 를 뺌 → 업무 층의 401 테스트가 잡음"
  else
    echo "9b(덤). auth=session_cookie 를 뺌 → ★ 업무 층의 401 테스트가 못 잡음"; tail -15 "$log/9b.txt" | sed 's/^/    | /'; extra_failed=1
  fi
  restore_files

  # 10. 마이그레이션에서 isolate("core_jobs") 를 뺌.
  edit "$MIGRATION" $'        *isolate(JOBS),\n' '' || exit 3
  security_tests "$T_OWNER" "$T_SECURITY" > "$log/10.txt" 2>&1; code=$?
  judge "10. 마이그레이션에서 isolate(core_jobs) 를 뺌" "$log/10.txt" "$code" 'test_owner.py::test_every_tenant_table_has_rls_enabled_and_forced' 'test_owner.py::test_policy_text_compares_the_transaction_setting'

  # 11. grant 에 DELETE 를 더함.
  edit "$MIGRATION" $'        grant(f\'"{DOCUMENTS}", "{JOBS}"\', "SELECT, INSERT, UPDATE"),' $'        grant(f\'"{DOCUMENTS}", "{JOBS}"\', "SELECT, INSERT, UPDATE, DELETE"),' || exit 3
  security_tests "$T_OWNER" "$T_SECURITY" > "$log/11.txt" 2>&1; code=$?
  judge "11. grant 에 DELETE 를 더함" "$log/11.txt" "$code" 'test_owner.py::test_app_role_reads_every_tenant_table_and_deletes_none' 'test_documents.py::test_app_role_cannot_delete_from_either_table' 'test_documents.py::test_app_role_may_read_insert_and_update_only'

  # 12. 올림 확인에서 select_for_update() 를 뺌.
  edit "$SERVICES" 'locked = DocumentRow.objects.select_for_update().get(pk=document_id)' 'locked = DocumentRow.objects.get(pk=document_id)' || exit 3
  business_tests "$T_API" > "$log/12.txt" 2>&1; code=$?
  judge "12. 올림 확인에서 select_for_update() 를 뺌" "$log/12.txt" "$code" test_confirm_reads_the_document_for_update

  # 13. on_commit 대신 enqueue 를 바로 부름.
  edit "$SERVICES" 'transaction.on_commit(partial(send, tenant_id=job.tenant_id, job_id=job.id, kind=job.kind), robust=True)' 'send(tenant_id=job.tenant_id, job_id=job.id, kind=job.kind)' || exit 3
  business_tests "$T_API" > "$log/13.txt" 2>&1; code=$?
  security_tests "$T_SECURITY" > "$log/13s.txt" 2>&1; scode=$?
  cat "$log/13s.txt" >> "$log/13.txt"; [ "$scode" -ne 0 ] || code=0
  judge "13. on_commit 대신 enqueue 를 바로 부름" "$log/13.txt" "$code" test_a_confirmed_upload_registers_one_callback_that_enqueues_the_job test_a_hook_that_raises_does_not_fail_the_request 'test_documents.py::test_the_hook_runs_after_the_commit'
  # 「거절에서 0」(test_a_refused_confirm_registers_nothing)이 이 파손에서 빨개지는가를 따로 적는다(세지 않는다).
  if grep -q '^FAILED .*test_a_refused_confirm_registers_nothing' "$log/13.txt"; then echo "    (13 에서 「거절에서 0」도 빨개졌다)"; else echo "    (13 에서 「거절에서 0」은 빨개지지 않았다: 거절은 큐에 넣는 줄에 닿기 전에 돌아간다)"; fi

  # 14. 올림 확인이 head 를 안 부르고 통과.
  edit "$SERVICES" 'head = storage.head(row.storage_key)  # ③' 'head = __import__("esgapi.core.ports.storage", fromlist=["ObjectFound"]).ObjectFound(size_bytes=row.size_bytes, etag="planted")' || exit 3
  business_tests "$T_API" > "$log/14.txt" 2>&1; code=$?
  judge "14. 올림 확인이 head 를 안 부르고 통과" "$log/14.txt" "$code" test_confirm_before_the_upload_is_409_and_changes_nothing test_a_size_other_than_the_declared_one_is_409_and_changes_nothing

  # 15. 만들기의 역할 가름을 뺌.
  edit "$CORE_API" $'    session = _uploader(request)\n    storage = _storage()' $'    session = _session(request)\n    storage = _storage()' || exit 3
  business_tests "$T_API" > "$log/15.txt" 2>&1; code=$?
  judge "15. 만들기의 역할 가름을 뺌" "$log/15.txt" "$code" test_viewer_cannot_create

  # 16. 마이그레이션에서 summary 의 크기 CHECK 를 뺌(RunSQL 한 덩어리를 통째로).
  python3 - "$MIGRATION" <<'PY' || exit 3
import re
import sys

path = sys.argv[1]
text = open(path, encoding="utf-8").read()
block = re.compile(r"        migrations\.RunSQL\(\n            sql=\(\n.*?core_jobs_summary_size_check.*?\n        \),\n", re.DOTALL)
if len(block.findall(text)) != 1 or "isolate(" in block.findall(text)[0]:
    sys.exit(f"심을 자리(summary 의 RunSQL 덩어리)를 하나로 집지 못했다: {path}")
open(path, "w", encoding="utf-8").write(block.sub("", text))
PY
  security_tests "$T_SECURITY" > "$log/16.txt" 2>&1; code=$?
  judge "16. 마이그레이션에서 summary 의 크기 CHECK 를 뺌" "$log/16.txt" "$code" test_summary_is_a_small_summary_enforced_by_the_db
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
[ "$ok" -eq "$total" ] && [ "$extra_failed" -eq 0 ]
