#!/usr/bin/env bash
# 밴드 E1b 의 심은 파손(P1~P9. 발주서 §3-4 가 정본): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-E1b.sh --pure         순수 몫(컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/8
#         apps/api-py/scripts/planted-breaks-E1b.sh --containers   업무·보안 몫(compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/7
#         apps/api-py/scripts/planted-breaks-E1b.sh                전부. 마지막 줄 PLANTED=<잡은 수>/15
# 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도
# trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를
# 내지 않고 종료 1.
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (checkout·reset·stash 를 쓰지 않는다 — 커밋 안 된 다른 변경까지 쓸려 간다).
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다). 심는 글자가 지금 파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 업무·보안 층은 심은 것마다 **그 테스트만** 겨냥해 돌린다(노드 ID). 떠 있는 서버의 이미지·DB 는 건드리지 않는다.
# ★ P1 은 지운 설정(TENANT_TX_EXEMPT_PATHS)을 되살리지 않는다 — atomic()+set_rollback 만(리뷰 R9).
# ★ P3 은 발주서의 기대(순수는 못 잡음)와 다르다: on_commit 이 0 이 되어 순수 test_after_commit_work_… 의 분모(1)가 문다.
# 브로커를 쓰지 않는다. AI 공급사 호출 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1   # 심은 판의 .pyc 를 남기지 않는다

A=apps/api-py
E="$A/esgapi"
MW="$E/core/tenancy/middleware.py"
DOCS="$E/core/service/services/documents.py"
ACC="$E/accounts/service/services/accounts.py"
SINK="$E/core/llm/sink_db.py"
CMD="$E/core/management/commands/llm_call.py"
RULES="$E/core/tests/test_transaction_rules.py"
# 테스트 경로(apps/api-py 기준)
T_RULES=esgapi/core/tests/test_transaction_rules.py
T_MW=esgapi/core/tests/tenancy/test_middleware.py
T_DOCS=esgapi/core/tests/test_documents_services.py
S_BOUNDARY=tests/security/test_tenant_boundary.py
S_DOC=tests/security/test_documents.py
S_TX=tests/security/test_request_transactions.py
S_LOG=tests/security/test_llm_log.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$MW" "$DOCS" "$ACC" "$SINK" "$CMD" "$RULES")
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
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed) in |^FAILED|^ERROR' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for wanted in "$@"; do
    grep '^FAILED ' "$file" | grep -q -F "$wanted" || { missed=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$missed" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}

# 심는 글자(지금 코드에서 정확히 한 번씩 있다 — edit 가 센다).
MW_IMPORT=$'from django.http import HttpRequest, HttpResponse\n'
MW_RETURN=$'        set_session_state(request, state)\n        return self.get_response(request)\n'
MW_ATOMIC=$'        set_session_state(request, state)\n        with transaction.atomic():\n            response = self.get_response(request)\n            if response.status_code >= 400:\n                transaction.set_rollback(True)\n        return response\n'
HEAD=$'        head = storage.head(document.storage_key)  # ③ — 블록 밖\n'
HEAD_IN=$'        with transaction.atomic():\n            head = storage.head(document.storage_key)  # ③ — 블록 밖\n'
ON_COMMIT=$'                transaction.on_commit(\n                    _sending(send, tenant_id=job.tenant_id, job_id=job.id, kind=job.kind), robust=True\n                )\n'
SEND_NOW=$'                _sending(send, tenant_id=job.tenant_id, job_id=job.id, kind=job.kind)()\n'
CREATE_BLOCK=$'    with transaction.atomic():\n        row = DocumentRow.for_tenant(tenant_id).create(\n            id=document_id,\n            tenant_id=tenant_id,\n            uploaded_by=uploaded_by,\n            file_name=file_name,\n            storage_key=key.key,\n            size_bytes=size_bytes,\n            status="awaiting_upload",\n        )\n        upload = storage.presign_upload(key.key, content_length=size_bytes)\n'
CREATE_BARE=$'    row = DocumentRow.for_tenant(tenant_id).create(\n        id=document_id,\n        tenant_id=tenant_id,\n        uploaded_by=uploaded_by,\n        file_name=file_name,\n        storage_key=key.key,\n        size_bytes=size_bytes,\n        status="awaiting_upload",\n    )\n    upload = storage.presign_upload(key.key, content_length=size_bytes)\n'
SINK_IMPORT='from django.db import DatabaseError, transaction'
SINK_SHAPE=$'        if not TENANT_ID_SHAPE.match(record.tenant):\n            return NoTenant()\n'
SINK_OUTSIDE=$'        if not connection.in_atomic_block:\n            return NoTenant()\n        if not TENANT_ID_SHAPE.match(record.tenant):\n            return NoTenant()\n'
CMD_IMPORT=$'from django.core.management.base import BaseCommand, CommandError\n'
CMD_CALL=$'        result = client.call(request)\n'
CMD_BLOCK=$'        with transaction.atomic():\n            result = client.call(request)\n'
SITE_BLOCK=$'    with transaction.atomic():\n        row = SiteRow.for_tenant(tenant_id).create(name=name, external_id=external_id)\n'
SITE_BARE=$'    row = SiteRow.for_tenant(tenant_id).create(name=name, external_id=external_id)\n'
CONFIRM_BLOCK=$'    with transaction.atomic():\n        if found is not None:\n'
CONFIRM_BARE=$'    if True:  # 심은 파손 P8: 블록 문만 걷음\n        if found is not None:\n'
WORKERS='WORKER_SERVICES = frozenset({"core/service/services/jobs.py"})'

plant_p1() { edit "$MW" "$MW_IMPORT" $'from django.db import transaction\n'"$MW_IMPORT" && edit "$MW" "$MW_RETURN" "$MW_ATOMIC"; }
plant_p2() { edit "$DOCS" "$HEAD" "$HEAD_IN"; }
plant_p3() { edit "$DOCS" "$ON_COMMIT" "$SEND_NOW"; }
plant_p4() { edit "$DOCS" "$CREATE_BLOCK" "$CREATE_BARE"; }
plant_p5() { edit "$SINK" "$SINK_IMPORT" 'from django.db import DatabaseError, connection, transaction' && edit "$SINK" "$SINK_SHAPE" "$SINK_OUTSIDE"; }
plant_p6() { edit "$CMD" "$CMD_IMPORT" "$CMD_IMPORT"$'from django.db import transaction\n' && edit "$CMD" "$CMD_CALL" "$CMD_BLOCK"; }
plant_p7() { edit "$ACC" "$SITE_BLOCK" "$SITE_BARE"; }
plant_p8() { edit "$DOCS" "$CONFIRM_BLOCK" "$CONFIRM_BARE"; }
plant_p9() { edit "$RULES" "$WORKERS" 'WORKER_SERVICES = frozenset({"core/service/services/jobs.py", "core/service/services/documents.py"})'; }

pure() {
  plant_p1 || exit 3
  pure_tests "$T_RULES" "$T_MW" > "$log/P1.txt" 2>&1; code=$?
  judge "P1. 미들웨어에 atomic()+4xx 롤백을 되살림 (순수)" "$log/P1.txt" "$code" test_no_request_wide_transaction test_the_middleware_reaches_no_database

  plant_p2 || exit 3
  pure_tests "$T_RULES" > "$log/P2.txt" 2>&1; code=$?
  judge "P2. confirm_upload 의 head 를 블록 안으로 (순수)" "$log/P2.txt" "$code" test_no_outside_call_inside_a_block

  plant_p3 || exit 3
  pure_tests "$T_RULES" > "$log/P3.txt" 2>&1; code=$?
  judge "P3. confirm_upload 가 on_commit 대신 send 를 바로 부름 (순수 — 발주서는 「못 잡음」 기대)" "$log/P3.txt" "$code" test_after_commit_work_is_registered_inside_a_block

  plant_p4 || exit 3
  pure_tests "$T_RULES" > "$log/P4.txt" 2>&1; code=$?
  judge "P4. create_document 의 블록을 걷음 (순수)" "$log/P4.txt" "$code" "test_every_write_sits_inside_a_block[core/service/services/documents.py]"

  plant_p6 || exit 3
  pure_tests "$T_RULES" > "$log/P6.txt" 2>&1; code=$?
  judge "P6. llm_call 에 with transaction.atomic(): client.call 을 되살림 (순수)" "$log/P6.txt" "$code" test_no_outside_call_inside_a_block

  plant_p7 || exit 3
  pure_tests "$T_RULES" > "$log/P7.txt" 2>&1; code=$?
  judge "P7. insert_site 의 블록을 걷음 (순수)" "$log/P7.txt" "$code" "test_every_write_sits_inside_a_block[accounts/service/services/accounts.py]"

  plant_p8 || exit 3
  pure_tests "$T_RULES" > "$log/P8.txt" 2>&1; code=$?
  judge "P8. confirm_upload 의 블록 문만 걷음 (순수)" "$log/P8.txt" "$code" "test_every_write_sits_inside_a_block[core/service/services/documents.py]"

  plant_p9 || exit 3
  pure_tests "$T_RULES" > "$log/P9.txt" 2>&1; code=$?
  judge "P9. WORKER_SERVICES 에 documents.py 를 더함 (순수)" "$log/P9.txt" "$code" "test_every_write_sits_inside_a_block[core/service/services/documents.py]"
}

containers() {
  plant_p1 || exit 3
  security_tests "$S_BOUNDARY::test_the_middleware_opens_no_transaction" > "$log/P1b.txt" 2>&1; code=$?
  judge "P1b. 미들웨어에 atomic()+4xx 롤백을 되살림 (보안)" "$log/P1b.txt" "$code" test_the_middleware_opens_no_transaction

  plant_p2 || exit 3
  security_tests "$S_DOC::test_the_storage_head_runs_outside_a_transaction" > "$log/P2s.txt" 2>&1; code=$?
  judge "P2. confirm_upload 의 head 를 블록 안으로 (보안)" "$log/P2s.txt" "$code" test_the_storage_head_runs_outside_a_transaction

  plant_p3 || exit 3
  security_tests "$S_DOC::test_the_hook_runs_after_the_commit" > "$log/P3s.txt" 2>&1; code=$?
  judge "P3. confirm_upload 가 send 를 바로 부름 (보안)" "$log/P3s.txt" "$code" test_the_hook_runs_after_the_commit

  plant_p4 || exit 3
  business_tests "$T_DOCS::test_a_failed_signing_leaves_no_row" > "$log/P4b.txt" 2>&1; code=$?
  judge "P4. create_document 의 블록을 걷음 (업무)" "$log/P4b.txt" "$code" test_a_failed_signing_leaves_no_row

  plant_p5 || exit 3
  security_tests "$S_TX::test_a_log_line_survives_an_error_response" "$S_LOG::test_a_bad_tag_writes_nothing_and_outside_a_transaction_the_sink_commits" > "$log/P5.txt" 2>&1; code=$?
  judge "P5. sink_db._write 에 「밖이면 NoTenant」를 되살림 (보안)" "$log/P5.txt" "$code" test_a_log_line_survives_an_error_response test_a_bad_tag_writes_nothing_and_outside_a_transaction_the_sink_commits

  plant_p8 || exit 3
  business_tests "$T_DOCS::test_a_confirm_that_fails_midway_leaves_nothing" > "$log/P8b.txt" 2>&1; code=$?
  judge "P8. confirm_upload 의 블록 문만 걷음 (업무)" "$log/P8b.txt" "$code" test_a_confirm_that_fails_midway_leaves_nothing

  plant_p8 || exit 3
  security_tests "$S_DOC::test_the_hook_runs_after_the_commit" > "$log/P8s.txt" 2>&1; code=$?
  judge "P8. confirm_upload 의 블록 문만 걷음 (보안 — upload_as 의 올림 확인이 503)" "$log/P8s.txt" "$code" test_the_hook_runs_after_the_commit
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
echo "(되돌림 확인: 파일 ${#FILES[@]}개의 sha256 과 git status 가 처음과 같다 · 기록 $log)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
