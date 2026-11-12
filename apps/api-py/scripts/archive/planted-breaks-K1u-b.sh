#!/usr/bin/env bash
# 밴드 K1u-b 의 심은 파손(Pb1~Pb8 + 거꾸로 심기 Rb. 발주서 b-3-5 가 정본): 하나씩 심고, 그것을 잡아야 하는 것이
# 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K1u-b.sh --pure         순수 몫(컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/7
#         apps/api-py/scripts/planted-breaks-K1u-b.sh --containers   업무·보안 몫(compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/6
#         apps/api-py/scripts/planted-breaks-K1u-b.sh                전부. 마지막 줄 PLANTED=<잡은 수>/13
#   순수 몫: Pb2(받침 ④) · Pb3 · Pb4(입구의 순수 테스트) · Pb5 · Pb6(makemigrations) · Pb8(id 칸 타입 루프) · Pb8(커밋된 openapi)
#   컨테이너 몫: Pb1 · Pb2(보안) · Pb4(업무 test_tasks_parse) · Pb6(보안 제약 표) · Pb7 · Rb
# 틀은 planted-breaks-K1u-a.sh 다. 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가 되돌린다(되돌리는 데
# git 을 쓰지 않는다. 죽어도 trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과
# 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (checkout·reset·stash 를 쓰지 않는다 — 커밋 안 된 다른 변경까지 쓸려 간다).
# 「잡음(RED)」의 기준: 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다(다른 까닭으로 빨개진
#   것을 잡았다고 세지 않는다). makemigrations --check 는 0 이 아닌 코드 + 출력에 그 칸 이름. 심는 글자가 지금
#   파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 출력: 파손마다 「Pb<n> <무엇> → 빨개진 것: <노드/명령> · RED|GREEN」. 빨개져야 할 것이 GREEN 이면 그 파손은 못 잡음.
#
# 파손마다(무엇을 심고 무엇이 빨개져야 하나):
#   Pb1 core/0001 에서 same_company_foreign_key(core_jobs.document_id → core_documents) 줄을 뺌. RunSQL 이라 모델은
#       그대로다(makemigrations 는 모른다). 보안의 카탈로그 검사(짝이 없는 키) + 남의 문서에 일감을 거는 23503 테스트.
#   Pb2 find_document 가 _documents(company_id)(= for_company) 대신 DocumentRow.unscoped.filter(pk=…) 로 찾음(발주서의
#       글자 그대로 — 회사 조건이 빠진다. _documents 안에서 unscoped.filter(company_id=…) 로 바꾸면 회사 조건이 살아
#       보안 테스트가 초록이라 「pk 로만」을 심는다). 순수 ④(unscoped 금지) + 보안의 남의 문서 404.
#   Pb3 core/resources/queue.py 의 쪽지 job_id 를 str(job_id) 대신 정수로. 순수 test_task_note(로그의 job_id 칸).
#   Pb4 워커 입구(reconcile/tasks.py)가 company_id 의 꼴(COMPANY_ID_TEXT)을 안 봄 → "01" 이 int 1 로 통과한다.
#       발주서의 test_tasks_parse 는 django_db 라 컨테이너 몫(업무)이다. 순수 test_task_note 의 꼴 테스트도 같은 입구를
#       재므로(잡기를 부르면 pytest.fail) 순수 몫으로 따로 센다.
#   Pb5 저장소 키에 회사 id 대신 서브도메인 꼴 글자(companies/tenant-a/). 순수 test_documents_calc.
#   Pb6 LlmCallLogRow.company_id(숫자 칸)를 company = ForeignKey("organization.Company") 로. 이름을 company 로 둬야
#       db 칸·attname 이 company_id 로 같아 filter(company_id=…)·create(company_id=…) 가 그대로 산다(칸 이름을
#       company_id 로 둔 ForeignKey 면 attname 이 company_id_id 가 되어 다른 까닭으로 빨개진다 — K1u-a Pa10 의 거울).
#       순수 몫은 모델만 고친다(makemigrations --check 가 변경을 낸다). 컨테이너 몫은 모델·마이그레이션 둘 다 고친다
#       (보안 test_migrations 의 「core_llm_call_logs 에 외래 키 0」).
#   Pb7 (J1) 같은 회사 FK 검사의 셈(missing_same_company_pairs)이 회사 표를 옛 칸 tenant_id 로 찾음. 셈에 회사 표가
#       하나도 안 들어 자기 시험(company_id 표 둘의 한 칸 FK)과 본 검사의 짝 분모(core_jobs.document_id)가 빨개야 한다.
#       ★ 모듈 상수 COMPANY 를 통째로 되돌리면 자기 시험의 임시 표도 tenant_id 칸으로 서서 자기 시험이 초록이다 —
#       그래서 셈 함수 안의 칸 인자만 되돌린다.
#   Pb8 JobOut.id 를 int 대신 str 로(generated 는 그대로). 순수 test_api_contract 의 id 칸 타입 루프(JobOut 을 더한 것,
#       test_the_run_and_version_operations_are_the_contract_sheet 안) + test_committed_openapi_matches_the_code.
#   ★ Rb 만 거꾸로다: core/0001 의 grant 줄 둘을 비운다(파일은 둔다). 앱 역할에 core_documents·core_jobs·
#       core_llm_call_logs 의 권한이 없으니 documents 경로가 permission denied 로 빨개야 정상(RED = 잡음). GREEN 이면 멈춤.
# 마이그레이션을 건드리는 심기(Pb1·Pb6·Rb)는 볼륨을 새로 하지 않아도 된다: 보안 층의 고정물(tests/security/conftest.py
#   의 test_database)이 세션마다 테스트 DB(<POSTGRES_DB>_py_test)를 지우고 새로 만들어 지금 작업 트리의 마이그레이션으로
#   migrate 한다. 업무 층도 --reuse-db 를 쓰지 않으므로 pytest-django 가 세션마다 test_<DB> 를 새로 만든다.
# 업무·보안 층은 심은 것마다 **그 테스트만** 겨냥해 돌린다(노드 ID). 떠 있는 서버의 이미지·DB 는 건드리지 않는다.
# 브로커를 쓰지 않는다. AI 공급사 호출 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1   # 심은 판의 .pyc 를 남기지 않는다

A=apps/api-py
E="$A/esgapi"
M_CORE="$E/core/migrations/0001_initial.py"
CORE_MODELS="$E/core/models.py"
DOC_SEL="$E/core/service/selectors/documents.py"
QUEUE="$E/core/resources/queue.py"
TASKS="$E/reconcile/tasks.py"
DOC_CALC="$E/core/calc/documents.py"
DOC_SCHEMA="$E/core/service/schemas/documents.py"
FK_CHECK="$A/tests/security/test_same_company_foreign_keys.py"
# 테스트 경로(순수·업무는 apps/api-py 기준, 보안은 test-security.sh 가 apps/api-py 로 들어가 돈다)
T_STATIC=esgapi/core/tests/isolation/test_static_rules.py
T_NOTE=esgapi/reconcile/tests/test_task_note.py
T_CALC=esgapi/core/tests/test_documents_calc.py
T_CONTRACT=esgapi/config/tests/test_api_contract.py
B_PARSE=esgapi/reconcile/tests/test_tasks_parse.py
S_FK=tests/security/test_same_company_foreign_keys.py
S_DOCS=tests/security/test_documents.py
S_PATHS=tests/security/test_tenant_paths.py
S_MIG=tests/security/test_migrations.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$M_CORE" "$CORE_MODELS" "$DOC_SEL" "$QUEUE" "$TASKS" "$DOC_CALC" "$DOC_SCHEMA" "$FK_CHECK")
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
# 호스트에서 test_business 설정으로(DB 없이. 닿지 않는 주소라 RuntimeWarning 한 줄이 난다 — section4 와 같은 길).
makemigrations_check() {
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py makemigrations --check --dry-run)
}
# 두 층(또는 두 번)을 돌린 것을 하나로 판정한다: 둘 다 0 이 아니어야 종료 코드를 1 로 본다.
both() { [ "$1" -ne 0 ] && [ "$2" -ne 0 ] && echo 1 || echo 0; }

# <번호와 설명> <「빨개진 것」 칸에 적을 글> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local name="$1" what="$2" file="$3" code="$4" missed=0 wanted
  shift 4
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|errors?) in |^FAILED|^ERROR' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for wanted in "$@"; do
    grep '^FAILED ' "$file" | grep -q -F "$wanted" || { missed=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$missed" -eq 0 ]; then
    ok=$((ok + 1)); echo "$name → 빨개진 것: $what · RED"
  else
    echo "$name → 빨개진 것: $what · GREEN (★ 못 잡음)"; tail -15 "$file" | sed 's/^/    | /'
  fi
  restore_files
}
# makemigrations --check 판정: 0 이 아닌 코드 + 출력에 그 글자(칸 이름)가 있어야 RED.
judge_mm() {
  local name="$1" file="$2" code="$3" wanted="$4"
  total=$((total + 1))
  grep -v -E 'RuntimeWarning|warnings.warn' "$file" | sed 's/^/    /' | cut -c1-230 | head -6
  if [ "$code" -ne 0 ] && grep -q -F "$wanted" "$file"; then
    ok=$((ok + 1)); echo "$name → 빨개진 것: makemigrations --check --dry-run (종료 $code, 「${wanted}」) · RED"
  else
    echo "$name → 빨개진 것: makemigrations --check --dry-run (종료 $code) · GREEN (★ 못 잡음)"; tail -8 "$file" | sed 's/^/    | /'
  fi
  restore_files
}

# 심는 글자(지금 코드에서 정확히 한 번씩 있다 — edit 가 센다).
PAIR_LINE=$'        same_company_foreign_key(table=JOBS, column="document_id", target=DOCUMENTS),\n'
FIND_DOC='    row = _documents(company_id).filter(pk=document_id).first()'
NOTE_KWARGS='kwargs={"company_id": str(company_id), "job_id": str(job_id)},'
ENTRANCE_SHAPE='    if COMPANY_ID_TEXT.match(company_id) is None or COMPANY_ID_TEXT.match(job_id) is None:'
KEY_FSTRING='    return StorageKey(f"companies/{company_id}/documents/{key_id}/original")'
LOG_COMPANY=$'    company_id = models.BigIntegerField()\n    module = models.CharField(max_length=100)\n'
LOG_COMPANY_MIG='                ("company_id", models.BigIntegerField()),'
COUNT_COLUMN=$'    셈: 「company_id 칸이 있는 표 → company_id 칸이 있는 표」의 한 칸 외래 키. 자기 참조도 센다.\n    """\n    with_company = {name for (name,) in owner.execute(TABLES_WITH_COMPANY_SQL, [COMPANY])}\n'
JOB_ID=$'class JobOut(Schema):\n    id: int\n'
CORE_GRANTS=$'        grant(f\'"{LOGS}"\', "SELECT, INSERT"),\n        grant(f\'"{DOCUMENTS}", "{JOBS}"\', "SELECT, INSERT, UPDATE"),\n'

plant_pb1() { edit "$M_CORE" "$PAIR_LINE" ''; }
plant_pb2() { edit "$DOC_SEL" "$FIND_DOC" '    row = DocumentRow.unscoped.filter(pk=document_id).first()  # 심은 파손 Pb2: 회사 조건 없이 pk 로만'; }
plant_pb3() { edit "$QUEUE" "$NOTE_KWARGS" 'kwargs={"company_id": str(company_id), "job_id": job_id},'; }
plant_pb4() { edit "$TASKS" "$ENTRANCE_SHAPE" '    if COMPANY_ID_TEXT.match(job_id) is None:  # 심은 파손 Pb4: 회사 id 의 꼴을 안 봄'; }
plant_pb5() { edit "$DOC_CALC" "$KEY_FSTRING" '    return StorageKey(f"companies/tenant-a/documents/{key_id}/original")  # 심은 파손 Pb5'; }
plant_pb6_model() {
  edit "$CORE_MODELS" "$LOG_COMPANY" \
    $'    company = models.ForeignKey("organization.Company", on_delete=models.PROTECT)  # 심은 파손 Pb6: 외래 키\n    module = models.CharField(max_length=100)\n'
}
plant_pb6_both() {
  plant_pb6_model && edit "$M_CORE" "$LOG_COMPANY_MIG" \
    '                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),'
}
plant_pb7() {
  edit "$FK_CHECK" "$COUNT_COLUMN" \
    $'    셈: 「company_id 칸이 있는 표 → company_id 칸이 있는 표」의 한 칸 외래 키. 자기 참조도 센다.\n    """\n    with_company = {name for (name,) in owner.execute(TABLES_WITH_COMPANY_SQL, ["tenant_id"])}  # 심은 파손 Pb7\n'
}
plant_pb8() { edit "$DOC_SCHEMA" "$JOB_ID" $'class JobOut(Schema):\n    id: str\n'; }
plant_rb() { edit "$M_CORE" "$CORE_GRANTS" ''; }

pure() {
  plant_pb2 || exit 3
  pure_tests "$T_STATIC" > "$log/Pb2p.txt" 2>&1; code=$?
  judge "Pb2 find_document 가 for_company 대신 DocumentRow.unscoped.filter(pk=…) (순수 — 받침 ④)" \
    "$T_STATIC::test_product_code_does_not_use_unscoped" "$log/Pb2p.txt" "$code" test_product_code_does_not_use_unscoped

  plant_pb3 || exit 3
  pure_tests "$T_NOTE" > "$log/Pb3.txt" 2>&1; code=$?
  judge "Pb3 queue.py 의 쪽지 job_id 를 글자 대신 정수로 (순수)" \
    "$T_NOTE::test_the_note_the_hook_sends_puts_the_job_id_into_the_worker_log" "$log/Pb3.txt" "$code" \
    test_the_note_the_hook_sends_puts_the_job_id_into_the_worker_log

  plant_pb4 || exit 3
  pure_tests "$T_NOTE" > "$log/Pb4p.txt" 2>&1; code=$?
  judge "Pb4 워커 입구가 company_id 의 꼴을 안 봄 (순수 — 입구의 꼴 테스트)" \
    "$T_NOTE::test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['01'·'0'·…]" "$log/Pb4p.txt" "$code" \
    "test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['01'-'1']" \
    "test_a_note_out_of_shape_is_skipped_at_the_entrance_without_a_query['0'-'1']"

  plant_pb5 || exit 3
  pure_tests "$T_CALC" > "$log/Pb5.txt" 2>&1; code=$?
  judge "Pb5 저장소 키에 회사 id 대신 서브도메인 글자 (순수)" \
    "$T_CALC::test_the_key_is_tenant_then_document_and_takes_no_file_name + ::test_tenant_id_length_boundary" \
    "$log/Pb5.txt" "$code" test_the_key_is_tenant_then_document_and_takes_no_file_name test_tenant_id_length_boundary

  plant_pb6_model || exit 3
  makemigrations_check > "$log/Pb6.txt" 2>&1; code=$?
  judge_mm "Pb6 LlmCallLogRow.company_id 를 company = ForeignKey 로(모델만) (순수)" "$log/Pb6.txt" "$code" \
    "Remove field company_id from llmcalllogrow"

  plant_pb8 || exit 3
  pure_tests "$T_CONTRACT" > "$log/Pb8.txt" 2>&1; code=$?
  # judge 하나가 하나를 센다 — Pb8 은 두 노드를 각각 센다(id 칸 타입 루프, 커밋된 openapi).
  cp "$log/Pb8.txt" "$log/Pb8b.txt"
  judge "Pb8 JobOut.id 를 str 로(generated 그대로) (순수 — id 칸 타입 루프)" \
    "$T_CONTRACT::test_the_run_and_version_operations_are_the_contract_sheet" "$log/Pb8.txt" "$code" \
    test_the_run_and_version_operations_are_the_contract_sheet
  judge "Pb8 JobOut.id 를 str 로(generated 그대로) (순수 — 커밋된 openapi)" \
    "$T_CONTRACT::test_committed_openapi_matches_the_code" "$log/Pb8b.txt" "$code" test_committed_openapi_matches_the_code
}

# Rb 의 앞 단: 보안 층 고정물과 같은 길(주인 역할로 빈 DB 를 만들고 settings.migrate 로 manage.py migrate)로 migrate 가
# 0 으로 끝나고 앱 역할(esg_app)에게 core_documents 의 SELECT 가 없는 것을 찍는다. 끝나면 지운다(DB 이름은 보안 층의
# 것과 같다 — 바로 뒤의 보안 층 실행이 다시 지우고 만든다).
rb_migrate_probe() {
  (
    cd "$A" || exit 1
    # shellcheck source=db-env.sh
    . scripts/db-env.sh
    PROBE_OWNER_URL="$OWNER_DATABASE_URL" uv run --frozen python - <<'PY'
import os
import subprocess
import sys

import psycopg
from psycopg import sql

from tests.support.db import TEST_DB_SUFFIX

owner_url = os.environ["PROBE_OWNER_URL"]
name = owner_url.rsplit("/", 1)[1] + TEST_DB_SUFFIX
url = owner_url + TEST_DB_SUFFIX


def drop_and(create: bool) -> None:
    with psycopg.connect(owner_url, autocommit=True) as admin:
        admin.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
        if create:
            admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))


drop_and(create=True)
granted = None
try:
    code = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--no-input", "-v", "0"],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.migrate", "DATABASE_URL_PY_OWNER": url},
        check=False,
    ).returncode
    if code == 0:
        with psycopg.connect(url) as conn:
            row = conn.execute("SELECT has_table_privilege('esg_app', 'core_documents', 'SELECT')").fetchone()
            granted = None if row is None else bool(row[0])
finally:
    drop_and(create=False)
print(f"    (Rb 앞 단: {name} 에 migrate 종료 {code} · 앱 역할의 core_documents SELECT {granted})")
sys.exit(0 if code == 0 and granted is False else 1)
PY
  )
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in Pb1 Pb2 Pb4 Pb6 Pb7 Rb; do total=$((total + 1)); echo "$n → ★ 못 잼(compose 의 postgres 가 떠 있지 않다) · GREEN"; done
    return
  fi
  local c1 c2

  # Pb1. 같은 회사 외래 키 짝을 core/0001 에서 뺀다(보안 층이 세션마다 새로 migrate 한다). 카탈로그 검사 + 23503.
  plant_pb1 || exit 3
  security_tests "$S_FK::test_every_foreign_key_between_company_tables_names_the_company" \
    "$S_DOCS::test_a_job_on_another_tenants_document_is_refused_by_the_db" > "$log/Pb1.txt" 2>&1; code=$?
  judge "Pb1 core/0001 에서 same_company_foreign_key 줄을 뺌 (보안 — 카탈로그 검사 + 23503)" \
    "$S_FK::test_every_foreign_key_between_company_tables_names_the_company + $S_DOCS::test_a_job_on_another_tenants_document_is_refused_by_the_db" \
    "$log/Pb1.txt" "$code" \
    test_every_foreign_key_between_company_tables_names_the_company test_a_job_on_another_tenants_document_is_refused_by_the_db

  # Pb2. find_document 가 회사 조건 없이 pk 로만 → B 의 세션이 A 의 문서를 본다(404 가 아니다).
  plant_pb2 || exit 3
  security_tests "$S_PATHS::test_another_tenants_document_is_not_found" > "$log/Pb2s.txt" 2>&1; code=$?
  judge "Pb2 find_document 가 DocumentRow.unscoped.filter(pk=…) (보안)" \
    "$S_PATHS::test_another_tenants_document_is_not_found" "$log/Pb2s.txt" "$code" test_another_tenants_document_is_not_found

  # Pb4. 워커 입구가 company_id 의 꼴을 안 봄 → "0{a}"·"" 등이 조회까지 간다(업무 층, django_db).
  plant_pb4 || exit 3
  business_tests "$B_PARSE::test_a_note_with_an_empty_tenant_is_skipped_and_touches_no_row" > "$log/Pb4b.txt" 2>&1; code=$?
  judge "Pb4 워커 입구가 company_id 의 꼴을 안 봄 (업무)" \
    "$B_PARSE::test_a_note_with_an_empty_tenant_is_skipped_and_touches_no_row" "$log/Pb4b.txt" "$code" \
    test_a_note_with_an_empty_tenant_is_skipped_and_touches_no_row

  # Pb6. 기록의 company_id 를 모델·마이그레이션 둘 다에서 company 를 가리키는 외래 키로(보안의 제약 표: 외래 키 0).
  plant_pb6_both || exit 3
  security_tests "$S_MIG::test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip" > "$log/Pb6s.txt" 2>&1; code=$?
  judge "Pb6 LlmCallLogRow.company_id 를 company = ForeignKey 로(모델·마이그레이션) (보안 — 제약 표)" \
    "$S_MIG::test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip" "$log/Pb6s.txt" "$code" \
    test_migrate_runs_on_an_empty_db_and_the_company_user_migrations_round_trip

  # Pb7. (J1) 셈이 회사 표를 옛 칸 tenant_id 로 찾는다 → 자기 시험과 본 검사의 짝 분모가 빨개야 한다.
  plant_pb7 || exit 3
  security_tests "$S_FK" > "$log/Pb7.txt" 2>&1; code=$?
  judge "Pb7 같은 회사 FK 검사의 셈이 옛 칸 tenant_id 로 회사 표를 찾음 (보안 — J1 자기 시험 + 짝 분모)" \
    "$S_FK::test_the_check_catches_a_single_column_key_between_company_tables + ::test_every_foreign_key_between_company_tables_names_the_company" \
    "$log/Pb7.txt" "$code" \
    test_the_check_catches_a_single_column_key_between_company_tables test_every_foreign_key_between_company_tables_names_the_company

  # Rb. 거꾸로 심기: core/0001 의 grant 줄 둘을 비운다(파일은 둔다). 빨개져야(permission denied) 잡음.
  plant_rb || exit 3
  total=$((total + 1))
  if ! rb_migrate_probe; then
    echo "Rb → ★ 못 잼(앞 단: migrate 가 0 으로 끝나고 앱 역할의 core_documents SELECT 가 없어야 한다) · GREEN"
    restore_files
    return
  fi
  "$A/scripts/test-security.sh" -rfE -p no:cacheprovider \
    "$S_PATHS::test_another_tenants_document_is_not_found" \
    "$S_PATHS::test_numeric_neighbour_document_ids_are_not_found_for_my_session" > "$log/Rb.txt" 2>&1; code=$?
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|errors?) in ' "$log/Rb.txt" | tail -1 | sed 's/^/    /'
  grep -E '^(FAILED|ERROR) ' "$log/Rb.txt" | sed -E 's/ - .*//; s/^/      /'
  echo "    permission denied 줄 $(grep -c -i 'permission denied' "$log/Rb.txt") · 첫 줄: $(grep -i -m1 'permission denied' "$log/Rb.txt" | cut -c1-200)"
  if [ "$code" -ne 0 ] && grep -q -E '^(FAILED|ERROR) ' "$log/Rb.txt" && grep -q -i 'permission denied' "$log/Rb.txt"; then
    ok=$((ok + 1))
    echo "Rb 거꾸로: core/0001 의 grant 줄을 비움 → 빨개진 것: $S_PATHS(documents 경로, permission denied) · RED (정상)"
  else
    echo "★ Rb 가 초록 — 멈춤"
    echo "Rb 거꾸로: core/0001 의 grant 줄을 비움 → 빨개진 것: 없음(종료 $code) · GREEN (★ 실패 — 못 잡음으로 센다)"; tail -15 "$log/Rb.txt" | sed 's/^/    | /'
  fi
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
echo "(되돌림 확인: 파일 ${#FILES[@]}개의 sha256 과 git status 가 처음과 같다 · 기록 $log)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
