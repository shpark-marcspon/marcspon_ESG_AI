#!/usr/bin/env bash
# 밴드 E1a 의 심은 파손 열넷(P1~P13 + 거꾸로 심기 R. 발주서 §3-4 가 정본): 하나씩 심고, 그것을 잡아야 하는 테스트가
# 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-E1a.sh --pure         P1~P6 (순수 층만, 컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/6
#         apps/api-py/scripts/planted-breaks-E1a.sh --containers   P7~P13 + R (compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/8
#         apps/api-py/scripts/planted-breaks-E1a.sh                전부. 마지막 줄 PLANTED=<잡은 수>/14
# 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도
# trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를
# 내지 않고 종료 1.
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (checkout·reset·stash 를 쓰지 않는다 — 커밋 안 된 다른 변경까지 쓸려 간다).
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다). 심는 글자가 지금 파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 업무·보안 층은 심은 것마다 **그 테스트만** 겨냥해 돌린다(업무: test-business.sh -k <이름>, 보안: test-security.sh <파일>::<이름>).
# 마이그레이션을 건드리는 심기(P12·P13·R)는 볼륨을 새로 하지 않아도 된다: 보안 층의 고정물(tests/security/conftest.py
# 의 test_database)이 세션마다 테스트 DB(<POSTGRES_DB>_py_test)를 지우고 새로 만들어 지금 작업 트리의 마이그레이션으로
# migrate 한다. 업무 층도 --reuse-db 를 쓰지 않으므로 pytest-django 가 세션마다 test_<DB> 를 새로 만든다.
# ★ R 만 거꾸로다: 두 0003_drop_rls 의 operations 를 [] 로 비운다(파일은 둔다 — 지우면 0004 의 dependencies 가 끊긴다).
#   먼저 보안 층과 같은 길(주인 역할로 빈 DB 를 만들고 settings.migrate 로 manage.py migrate)로 migrate 가 0 으로 끝나고
#   주인 역할의 pg_policies 가 6 인 것을 찍은 뒤, 보안 층 test_tenant_paths.py 전부를 돌린다. **빨개져야 잡음**
#   (정책이 남았는데 아무도 app.tenant_id 를 싣지 않으니 앱 역할의 조회가 0행이 된다). 초록이면 멈춤(§5 의 9).
# 컨테이너 몫은 업무·보안 층만 쓴다(떠 있는 서버의 이미지·DB 는 건드리지 않는다). 브로커를 쓰지 않는다. AI 공급사 호출 0.
# bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1   # 심은 판의 .pyc 를 남기지 않는다

A=apps/api-py
E="$A/esgapi"
MANAGERS="$E/core/isolation/managers.py"
MODELS="$E/core/models.py"
SD="$E/core/service/selectors/documents.py"
VJ="$E/core/service/services/jobs.py"
SINK="$E/core/llm/sink_db.py"
MW="$E/core/tenancy/middleware.py"
ACC_SV="$E/accounts/service/services/accounts.py"
ACC_SL="$E/accounts/service/selectors/accounts.py"
PATHS="$A/tests/security/test_tenant_paths.py"
M_FK="$E/core/migrations/0004_jobs_same_tenant_document.py"
M_ACC="$E/accounts/migrations/0003_drop_rls.py"
M_CORE="$E/core/migrations/0003_drop_rls.py"
# 테스트 경로(순수·업무는 apps/api-py 기준, 보안은 test-security.sh 가 apps/api-py 로 들어가 돈다)
T_MGR=esgapi/core/tests/isolation/test_managers.py
T_STATIC=esgapi/core/tests/isolation/test_static_rules.py
S_PATHS=tests/security/test_tenant_paths.py
S_FK=tests/security/test_same_tenant_foreign_keys.py
S_DOC=tests/security/test_documents.py
S_OWNER=tests/security/test_owner.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$MANAGERS" "$MODELS" "$SD" "$VJ" "$SINK" "$MW" "$ACC_SV" "$ACC_SL" "$PATHS" "$M_FK" "$M_ACC" "$M_CORE")
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
  grep -E '^[0-9]+ (passed|failed)|^FAILED|^ERROR' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for wanted in "$@"; do
    grep '^FAILED ' "$file" | grep -q -F "$wanted" || { missed=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$missed" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
# 두 층(또는 두 번)을 돌린 것을 하나로 판정한다: 둘 다 0 이 아니어야 종료 코드를 1 로 본다.
both() { [ "$1" -ne 0 ] && [ "$2" -ne 0 ] && echo 1 || echo 0; }

# 심는 글자(지금 코드에서 정확히 한 번씩 있다 — edit 가 센다).
GET_QUERYSET_RAISE='        raise UnscopedQueryError(f"{self.model.__name__}.objects 는 for_tenant(<테넌트>) 로만 연다")'
FOR_TENANT_FILTER='        return queryset.filter(**{TENANT_FIELD: tenant_id})'
JOB_MANAGERS=$'    objects = TenantScopedManager["JobRow"]()\n    unscoped = models.Manager["JobRow"]()\n'
DOC_GATE='    return DocumentRow.for_tenant(tenant_id)'
FIND_DOC='    row = _documents(tenant_id).filter(pk=document_id).first()'
CLAIM_GUARD='guard = JobRow.for_tenant(tenant_id).filter(pk=job_id, status=row.status, attempts=row.attempts)'
SINK_LOGGER=$'logger = logging.getLogger(__name__)\n'
MW_IMPORT='from django.db import DatabaseError, transaction'
MW_ATOMIC=$'            with transaction.atomic():\n                response = self.get_response(request)\n'
UPSERT='UserRow.for_tenant(claims.tenant_id).update_or_create('
SITES='SiteRow.for_tenant(tenant_id).order_by("created_at", "id")'
READYZ_ROW=$'    ("GET", "/readyz"): "public",\n'
FK_LINE=$'        same_tenant_foreign_key(table="core_jobs", column="document_id", target="core_documents"),\n'
RELEASE_SITES=$'        *release("sites"),\n'
ACC_OPS=$'    operations = [\n        *release("tenants", "id"),\n        *release("users"),\n        *release("sites"),\n    ]\n'
CORE_OPS=$'    operations = [\n        *release("core_llm_call_logs"),\n        *release("core_documents"),\n        *release("core_jobs"),\n    ]\n'

pure() {
  # P1. 기본 매니저가 던지지 않고 보통 QuerySet 을 연다.
  edit "$MANAGERS" "$GET_QUERYSET_RAISE" '        return super().get_queryset()' || exit 3
  pure_tests "$T_MGR" > "$log/P1.txt" 2>&1; code=$?
  judge "P1. TenantScopedManager.get_queryset 이 super().get_queryset() (순수)" "$log/P1.txt" "$code" test_an_unscoped_query_is_refused_before_the_db

  # P2. JobRow 의 매니저 두 줄의 차례를 바꾼다(unscoped 가 기본 매니저가 된다).
  edit "$MODELS" "$JOB_MANAGERS" $'    unscoped = models.Manager["JobRow"]()\n    objects = TenantScopedManager["JobRow"]()\n' || exit 3
  pure_tests "$T_STATIC" > "$log/P2.txt" 2>&1; code=$?
  judge "P2. JobRow 의 매니저 차례를 바꿈 (순수)" "$log/P2.txt" "$code" test_every_scoped_model_defaults_to_the_refusing_manager

  # P3. 문서의 문이 unscoped 로 연다(조건은 있다).
  edit "$SD" "$DOC_GATE" '    return DocumentRow.unscoped.filter(tenant_id=tenant_id)' || exit 3
  pure_tests "$T_STATIC" > "$log/P3.txt" 2>&1; code=$?
  judge "P3. selectors/documents.py 의 _documents 가 DocumentRow.unscoped.filter(tenant_id=…) (순수)" "$log/P3.txt" "$code" test_product_code_does_not_use_unscoped

  # P4. 잡기의 울타리가 숨은 매니저로 쓴다.
  edit "$VJ" "$CLAIM_GUARD" 'guard = JobRow._base_manager.filter(pk=job_id, status=row.status, attempts=row.attempts)' || exit 3
  pure_tests "$T_STATIC" > "$log/P4.txt" 2>&1; code=$?
  judge "P4. services/jobs.py 의 claim 울타리가 JobRow._base_manager.filter(pk=…) (순수)" "$log/P4.txt" "$code" test_product_code_does_not_reach_hidden_managers

  # P5. sink_db.py 에 connection.cursor() 한 줄(불리지 않는 함수 안 — 글자만 심는다).
  edit "$SINK" "$SINK_LOGGER" $'logger = logging.getLogger(__name__)\n\n\ndef _planted() -> None:\n    connection.cursor()\n' || exit 3
  pure_tests "$T_STATIC" > "$log/P5.txt" 2>&1; code=$?
  judge "P5. sink_db.py 에 connection.cursor() (순수)" "$log/P5.txt" "$code" test_product_code_has_no_raw_sql_outside_the_list

  # P6. 미들웨어가 트랜잭션에 테넌트를 다시 싣는다.
  { edit "$MW" "$MW_IMPORT" 'from django.db import DatabaseError, connection, transaction' \
      && edit "$MW" "$MW_ATOMIC" $'            with transaction.atomic():\n                connection.cursor().execute("SELECT set_config(\'app.tenant_id\', %s, true)", [getattr(state, "tenant_id", "")])\n                response = self.get_response(request)\n'; } || exit 3
  pure_tests "$T_STATIC" > "$log/P6.txt" 2>&1; code=$?
  judge "P6. 미들웨어에 SELECT set_config('app.tenant_id', …, true) (순수)" "$log/P6.txt" "$code" test_no_one_loads_a_tenant_into_the_connection
}

# R 의 앞 단: 보안 층 고정물과 같은 길로 빈 DB 를 만들어 migrate 하고, 주인 역할로 pg_policies 를 센다. 끝나면 지운다.
# DB 이름은 보안 층의 것(<POSTGRES_DB>_py_test)과 같다 — 바로 뒤의 보안 층 실행이 다시 지우고 만든다.
r_migrate_probe() {
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
policies = None
try:
    code = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--no-input", "-v", "0"],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.migrate", "DATABASE_URL_PY_OWNER": url},
        check=False,
    ).returncode
    if code == 0:
        with psycopg.connect(url) as conn:
            row = conn.execute("SELECT count(*) FROM pg_policies").fetchone()
            policies = None if row is None else int(row[0])
finally:
    drop_and(create=False)
print(f"    (R 앞 단: {name} 에 migrate 종료 {code} · 주인 역할의 pg_policies {policies})")
sys.exit(0 if code == 0 and policies == 6 else 1)
PY
  )
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in P7 P8 P9 P10 P11 P12 P13 R; do total=$((total + 1)); echo "$n. → ★ 못 잼(compose 의 postgres 가 떠 있지 않다)"; done
    return
  fi
  local c1 c2

  # P7. for_tenant 가 범위는 싣되 조건(filter)을 빼먹는다. 업무의 SQL 글자 단언과 보안의 경로 둘 다 빨개야 잡음.
  edit "$MANAGERS" "$FOR_TENANT_FILTER" '        return queryset' || exit 3
  business_tests "$T_MGR" -k test_the_scope_survives_filter_order_by_and_select_for_update > "$log/P7b.txt" 2>&1; c1=$?
  security_tests "$S_PATHS::test_another_tenants_document_is_not_found" > "$log/P7s.txt" 2>&1; c2=$?
  cat "$log/P7b.txt" "$log/P7s.txt" > "$log/P7.txt"
  echo "    (업무 종료 $c1 · 보안 종료 $c2)"
  judge "P7. for_tenant 가 filter 를 빼먹음 (업무 + 보안)" "$log/P7.txt" "$(both "$c1" "$c2")" \
    test_the_scope_survives_filter_order_by_and_select_for_update test_another_tenants_document_is_not_found

  # P8. upsert_user 가 조건 없이 unscoped.update_or_create. 업무 몫으로 판정하고, 순수 몫(P3 이 이미 잰다)도 같은 심기로 돌려 적는다.
  edit "$ACC_SV" "$UPSERT" 'UserRow.unscoped.update_or_create(' || exit 3
  business_tests "$T_MGR" -k test_a_user_in_another_tenant_is_not_overwritten > "$log/P8.txt" 2>&1; code=$?
  pure_tests "$T_STATIC" > "$log/P8p.txt" 2>&1; c2=$?
  if [ "$c2" -ne 0 ] && grep '^FAILED ' "$log/P8p.txt" | grep -q -F test_product_code_does_not_use_unscoped; then
    echo "    (같은 심기로 순수 test_product_code_does_not_use_unscoped 도 빨갛다 — 둘째 이름도 잡힘)"
  else
    echo "    (★ 같은 심기로 순수 test_product_code_does_not_use_unscoped 가 빨개지지 않았다: 종료 $c2)"
  fi
  judge "P8. upsert_user 가 UserRow.unscoped.update_or_create (업무)" "$log/P8.txt" "$code" test_a_user_in_another_tenant_is_not_overwritten

  # P9. find_document 가 문(_documents) 대신 unscoped 로 읽는다(조건 없음).
  edit "$SD" "$FIND_DOC" '    row = DocumentRow.unscoped.filter(pk=document_id).first()' || exit 3
  security_tests "$S_PATHS::test_another_tenants_document_is_not_found" > "$log/P9.txt" 2>&1; code=$?
  judge "P9. find_document 가 DocumentRow.unscoped (보안)" "$log/P9.txt" "$code" 'test_another_tenants_document_is_not_found[GET /documents/{document_id}]'

  # P10. all_sites 가 조건 없이 unscoped 로 연다.
  edit "$ACC_SL" "$SITES" 'SiteRow.unscoped.order_by("created_at", "id")' || exit 3
  security_tests "$S_PATHS::test_a_list_shows_only_my_tenant" > "$log/P10.txt" 2>&1; code=$?
  judge "P10. all_sites 가 SiteRow.unscoped.order_by(…) (보안)" "$log/P10.txt" "$code" test_a_list_shows_only_my_tenant

  # P11. 경로 표에서 동작 하나(GET /readyz)를 뺀다.
  edit "$PATHS" "$READYZ_ROW" '' || exit 3
  security_tests "$S_PATHS::test_every_operation_is_in_the_table" > "$log/P11.txt" 2>&1; code=$?
  judge "P11. test_tenant_paths.py 의 표에서 (GET, /readyz) 를 뺌 (보안)" "$log/P11.txt" "$code" test_every_operation_is_in_the_table

  # P12. 0004 의 same_tenant_foreign_key 줄을 뺀다(보안 층이 세션마다 테스트 DB 를 새로 migrate 한다).
  edit "$M_FK" "$FK_LINE" '' || exit 3
  security_tests "$S_FK::test_every_foreign_key_between_tenant_tables_names_the_tenant" \
    "$S_DOC::test_a_job_on_another_tenants_document_is_refused_by_the_db" > "$log/P12.txt" 2>&1; code=$?
  judge "P12. 0004 의 same_tenant_foreign_key 를 뺌 (보안)" "$log/P12.txt" "$code" \
    test_every_foreign_key_between_tenant_tables_names_the_tenant test_a_job_on_another_tenants_document_is_refused_by_the_db

  # P13. accounts 0003 에서 release("sites") 를 뺀다(sites 의 정책이 남는다).
  edit "$M_ACC" "$RELEASE_SITES" '' || exit 3
  security_tests "$S_OWNER::test_no_table_has_row_security_or_a_policy" > "$log/P13.txt" 2>&1; code=$?
  judge "P13. accounts/migrations/0003 에서 release(\"sites\") 를 뺌 (보안)" "$log/P13.txt" "$code" test_no_table_has_row_security_or_a_policy

  # R. 거꾸로 심기: 두 0003_drop_rls 의 operations 를 [] 로(파일은 둔다). 정책 여섯이 남은 채로 ③ 을 돌린다. 빨개져야 잡음.
  { edit "$M_ACC" "$ACC_OPS" $'    operations = []\n' && edit "$M_CORE" "$CORE_OPS" $'    operations = []\n'; } || exit 3
  total=$((total + 1))
  if ! r_migrate_probe; then
    echo "R. → ★ 못 잼(앞 단: migrate 가 0 으로 끝나고 pg_policies 가 6 이어야 한다)"
    restore_files
    return
  fi
  "$A/scripts/test-security.sh" -rfE -p no:cacheprovider "$S_PATHS" > "$log/R.txt" 2>&1; code=$?
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|errors?) in ' "$log/R.txt" | tail -1 | sed 's/^/    /'
  echo "    빨개진 테스트:"
  grep -E '^(FAILED|ERROR) ' "$log/R.txt" | sed -E 's/ - .*//; s/^/      /'
  echo "    첫 실패 줄: $(grep -E '^(FAILED|ERROR) ' "$log/R.txt" | head -1 | cut -c1-300)"
  echo "    첫 E 줄(까닭): $(grep -E '^E ' "$log/R.txt" | head -1 | cut -c1-300)"
  echo "    실패마다 첫 E 줄:"
  awk '/^_{3,} .* _{3,}$/ { name = $0; shown = 0 } /^E / && !shown && name != "" { print "      " name; print "        " substr($0, 1, 300); shown = 1 }' "$log/R.txt"
  if [ "$code" -ne 0 ] && grep -q -E '^(FAILED|ERROR) ' "$log/R.txt"; then
    ok=$((ok + 1)); echo "R. 두 0003_drop_rls 를 비우니(정책 여섯이 남음) 보안 층 ③ 이 빨갛다 → 잡음(① 만으로는 안 되고 RLS 가 정말 걷혔다)"
  else
    echo "★ R 이 초록 — 멈춤(§5 의 9)"; echo "R. → ★ 못 잡음 (종료 $code)"; tail -15 "$log/R.txt" | sed 's/^/    | /'
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
echo "(되돌림 확인: 파일 ${#FILES[@]}개의 sha256 과 git status 가 처음과 같다)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
