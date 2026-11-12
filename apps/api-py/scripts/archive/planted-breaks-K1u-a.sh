#!/usr/bin/env bash
# 밴드 K1u-a 의 심은 파손(Pa1~Pa13 + 거꾸로 심기 Ra. 발주서 a-3-5 가 정본): 하나씩 심고, 그것을 잡아야 하는 것이
# 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K1u-a.sh --pure         순수 몫(컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/8(Pa7 의 순수 몫은 관찰 — 셈 밖)
#         apps/api-py/scripts/planted-breaks-K1u-a.sh --containers   업무·보안 몫(compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/9
#         apps/api-py/scripts/planted-breaks-K1u-a.sh                전부. 마지막 줄 PLANTED=<잡은 수>/17
# 틀은 planted-breaks-E1a.sh·planted-breaks-E1b.sh 다. 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가
# 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과
# `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (checkout·reset·stash 를 쓰지 않는다 — 커밋 안 된 다른 변경까지 쓸려 간다).
# 「잡음(RED)」의 기준: 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다(다른 까닭으로 빨개진
#   것을 잡았다고 세지 않는다). makemigrations --check 는 0 이 아닌 코드 + 출력에 그 제약·칸 이름. 심는 글자가 지금
#   파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 출력: 파손마다 「Pa<n> <무엇> → 빨개진 것: <노드/명령> · RED|GREEN」. 빨개져야 할 것이 GREEN 이면 그 파손은 못 잡음.
# ★ Ra 만 거꾸로다: user/0001 의 grant 줄을 비운다(파일은 둔다). 앱 역할에 users 의 권한이 없으니 교환·/me·sites 경로가
#   permission denied 로 빨개야 정상(RED = 잡음). GREEN 이면 멈춤.
# 마이그레이션을 건드리는 심기(Pa3·Pa4·Pa10·Ra)는 볼륨을 새로 하지 않아도 된다: 보안 층의 고정물(tests/security/conftest.py
#   의 test_database)이 세션마다 테스트 DB(<POSTGRES_DB>_py_test)를 지우고 새로 만들어 지금 작업 트리의 마이그레이션으로
#   migrate 한다. 업무 층도 --reuse-db 를 쓰지 않으므로 pytest-django 가 세션마다 test_<DB> 를 새로 만든다.
#   Pa3·Pa10 의 순수 몫은 모델만 고친다(마이그레이션과 어긋나 makemigrations --check 가 변경을 낸다). 컨테이너 몫은
#   모델·마이그레이션 둘 다 고친다(DB 에서 정말 빠진다).
# ★ Pa6 은 「subdomain 대신 name 으로 찾음」을 이름 붙은 입구 by_subdomain 의 조건 칸을 바꿔 흉내 낸다
#   (CompanyRootManager.by_subdomain 의 filter(subdomain=…) → filter(name=…). by_subdomain 은 subdomain 칸으로만 찾는
#   자리라, 셀렉터에서 값만 바꾸는 것보다 「틀린 칸으로 찾기」에 가깝다).
# ★ Pa10 은 Site.company(외래 키)를 company_id = BigIntegerField() 로 바꾼다(칸 이름이 company_id 라 db 칸이 같고,
#   for_company 의 filter(company_id=…) 가 그대로 산다. company = BigIntegerField(db_column="company_id") 로 하면 company_id
#   조회가 FieldError 라 다른 까닭으로 빨개진다).
# 업무·보안 층은 심은 것마다 **그 테스트만** 겨냥해 돌린다(노드 ID). 떠 있는 서버의 이미지·DB 는 건드리지 않는다.
# 브로커를 쓰지 않는다. AI 공급사 호출 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1   # 심은 판의 .pyc 를 남기지 않는다

A=apps/api-py
E="$A/esgapi"
MANAGERS="$E/core/isolation/managers.py"
ORG_MODELS="$E/organization/models.py"
USER_MODELS="$E/user/models.py"
APPS_LIST="$E/config/apps_list.py"
ORG_SEL="$E/organization/service/selectors/organization.py"
USER_SCHEMA="$E/user/service/schemas/user.py"
SEED="$E/organization/management/commands/seed_company.py"
SESSION="$E/core/tenancy/session.py"
USER_SV="$E/user/service/services/user.py"
M_USER="$E/user/migrations/0001_initial.py"
M_ORG="$E/organization/migrations/0001_initial.py"
# 테스트 경로(순수·업무는 apps/api-py 기준, 보안은 test-security.sh 가 apps/api-py 로 들어가 돈다)
T_MGR=esgapi/core/tests/isolation/test_managers.py
T_STATIC=esgapi/core/tests/isolation/test_static_rules.py
T_SCOPE=esgapi/core/tests/test_selector_scope.py
T_CHECK=esgapi/config/tests/test_system_check.py
T_CONTRACT=esgapi/config/tests/test_api_contract.py
T_SESSION=esgapi/user/tests/service/utils/test_session_tokens.py
B_USER_MODELS=esgapi/user/tests/test_models.py
B_ORG_SEL=esgapi/organization/tests/service/selectors/test_organization.py
B_USER_API=esgapi/user/tests/service/apis/test_user.py
B_SEED=esgapi/organization/tests/management/commands/test_seed_company.py
S_PATHS=tests/security/test_tenant_paths.py
S_EXCHANGE=tests/security/test_exchange_tenant.py
S_FK=tests/security/test_same_tenant_foreign_keys.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$MANAGERS" "$ORG_MODELS" "$USER_MODELS" "$APPS_LIST" "$ORG_SEL" "$USER_SCHEMA" "$SEED" "$SESSION" "$USER_SV" "$M_USER" "$M_ORG")
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
# makemigrations --check 판정: 0 이 아닌 코드 + 출력에 그 글자(제약·칸 이름)가 있어야 RED.
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
ROOT_RAISE='        raise UnscopedQueryError(f"{self.model.__name__}.objects 는 for_company(<회사 id>)·이름 붙은 입구로만 연다")'
COMPANY_FILTER='        return queryset.filter(**{COMPANY_FIELD: checked})'
BY_SUBDOMAIN='        return self._entrance().filter(subdomain=subdomain).first()'
UNIQ_MODEL=$'            models.UniqueConstraint(\n                fields=["company", "username"], condition=models.Q(kind="service"), name="users_company_username_uniq"\n            ),\n'
UNIQ_MIG=$'                    models.UniqueConstraint(\n                        condition=models.Q(("kind", "service")),\n                        fields=("company", "username"),\n                        name="users_company_username_uniq",\n                    ),\n'
CHECK_MODEL=$'            models.CheckConstraint(\n                condition=models.Q(kind="admin", company__isnull=True)\n                | models.Q(kind="service", company__isnull=False),\n                name="users_kind_company_check",\n            ),\n'
CHECK_MIG=$'                    models.CheckConstraint(\n                        condition=models.Q(\n                            models.Q(("company__isnull", True), ("kind", "admin")),\n                            models.Q(("company__isnull", False), ("kind", "service")),\n                            _connector="OR",\n                        ),\n                        name="users_kind_company_check",\n                    ),\n'
SILENCED='SILENCED_SYSTEM_CHECKS = ["auth.W004"]'
LIST_SITES='    return SiteList(all_sites(session.company_id))'
ME_COMPANY=$'    expiresAt: datetime\n    companyId: int\n'
SEED_SAME=$'            self.stdout.write(str(found.company.id))\n            return\n'
SEED_SAME_TWICE=$'            # 심은 파손 Pa9: 같은 값의 둘째 실행에서 행을 하나 더(unique 칸 둘은 비켜서)\n            company = Company.register(name=name, business_licence_number="x" + licence[1:], subdomain="x" + subdomain[1:])\n            self.stdout.write(str(company.pk))\n            return\n'
SITE_FK=$'    company = models.ForeignKey(Company, on_delete=models.PROTECT)\n'
SITE_FK_MIG='                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),'
SESSION_SHAPE=$'    if not is_company_id(company_id):\n        return SessionRejected("malformed")\n'
UPSERT='        row, _created = User.for_company(company_id).update_or_create('
SEED_REGISTER='            company = Company.register(name=name, business_licence_number=licence, subdomain=subdomain)'
USER_GRANT=$'        grant(\'"users"\', "SELECT, INSERT, UPDATE"),\n'

plant_pa1() { edit "$MANAGERS" "$ROOT_RAISE" '        return super().get_queryset()'; }
plant_pa2() { edit "$MANAGERS" "$COMPANY_FILTER" '        return queryset'; }
plant_pa3_model() { edit "$USER_MODELS" "$UNIQ_MODEL" ''; }
plant_pa3_both() { plant_pa3_model && edit "$M_USER" "$UNIQ_MIG" ''; }
plant_pa4_both() { edit "$USER_MODELS" "$CHECK_MODEL" '' && edit "$M_USER" "$CHECK_MIG" ''; }
plant_pa5() { edit "$APPS_LIST" "$SILENCED" 'SILENCED_SYSTEM_CHECKS = ["auth.W004", "urls.W002"]'; }
plant_pa6() { edit "$MANAGERS" "$BY_SUBDOMAIN" '        return self._entrance().filter(name=subdomain).first()'; }
plant_pa7() { edit "$ORG_SEL" "$LIST_SITES" '    return SiteList(all_sites(1))'; }
plant_pa8() { edit "$USER_SCHEMA" "$ME_COMPANY" $'    expiresAt: datetime\n'; }
plant_pa9() { edit "$SEED" "$SEED_SAME" "$SEED_SAME_TWICE"; }
plant_pa10_model() { edit "$ORG_MODELS" "$SITE_FK" $'    company_id = models.BigIntegerField()  # 심은 파손 Pa10: 외래 키가 아님\n'; }
plant_pa10_both() { plant_pa10_model && edit "$M_ORG" "$SITE_FK_MIG" '                ("company_id", models.BigIntegerField()),'; }
plant_pa11() { edit "$SESSION" "$SESSION_SHAPE" ''; }
plant_pa12() { edit "$USER_SV" "$UPSERT" '        row, _created = User.unscoped.update_or_create('; }
plant_pa13() { edit "$SEED" "$SEED_REGISTER" '            company = Company.unscoped.create(name=name, business_licence_number=licence, subdomain=subdomain, is_active=True)'; }
plant_ra() { edit "$M_USER" "$USER_GRANT" ''; }

pure() {
  plant_pa1 || exit 3
  pure_tests "$T_MGR" > "$log/Pa1.txt" 2>&1; code=$?
  judge "Pa1 CompanyRootManager.get_queryset 이 거절 대신 super().get_queryset() (순수)" \
    "$T_MGR::test_an_unscoped_company_query_is_refused_before_the_db[*-Company]" "$log/Pa1.txt" "$code" \
    "test_an_unscoped_company_query_is_refused_before_the_db[all-Company]" \
    "test_an_unscoped_company_query_is_refused_before_the_db[count-Company]"

  plant_pa3_model || exit 3
  makemigrations_check > "$log/Pa3.txt" 2>&1; code=$?
  judge_mm "Pa3 users 의 (company, username) 조건부 unique 를 모델에서 뺌 (순수)" "$log/Pa3.txt" "$code" users_company_username_uniq

  plant_pa5 || exit 3
  pure_tests "$T_CHECK" > "$log/Pa5.txt" 2>&1; code=$?
  judge "Pa5 SILENCED_SYSTEM_CHECKS 에 \"urls.W002\" 를 더함 (순수)" \
    "$T_CHECK::test_the_system_check_is_clean" "$log/Pa5.txt" "$code" test_the_system_check_is_clean

  # Pa7 의 순수 몫은 관찰이다(셈 밖): 글자 검사(selector_scope·static_rules)가 상수 인자를 잡는지 본다. 발주서가 「못 잡으면
  # GREEN 으로 그대로 보고」라 했다. 이 파손의 셈은 컨테이너 몫(보안의 「B 의 것 전부」)이 한다.
  plant_pa7 || exit 3
  pure_tests "$T_SCOPE" "$T_STATIC" > "$log/Pa7.txt" 2>&1; code=$?
  grep -E '[0-9]+ (passed|failed) in |^FAILED' "$log/Pa7.txt" | sed 's/^/    /' | cut -c1-230 | head -8
  if [ "$code" -ne 0 ]; then
    echo "Pa7 list_sites 가 세션의 회사 대신 상수 1 을 all_sites 에 넘김 (순수 — 관찰, 셈 밖) → 빨개진 것: $T_SCOPE · $T_STATIC · RED"
  else
    echo "Pa7 list_sites 가 세션의 회사 대신 상수 1 을 all_sites 에 넘김 (순수 — 관찰, 셈 밖) → 빨개진 것: 없음($T_SCOPE · $T_STATIC 초록 — 글자 검사는 상수 인자를 못 잡는다. 컨테이너 몫이 잡는다) · GREEN"
  fi
  restore_files

  plant_pa8 || exit 3
  pure_tests "$T_CONTRACT" > "$log/Pa8.txt" 2>&1; code=$?
  judge "Pa8 MeOut 에서 companyId 를 뺌 (순수)" \
    "$T_CONTRACT::test_committed_openapi_matches_the_code" "$log/Pa8.txt" "$code" test_committed_openapi_matches_the_code

  plant_pa10_model || exit 3
  makemigrations_check > "$log/Pa10.txt" 2>&1; code=$?
  judge_mm "Pa10 Site.company 를 company_id = BigIntegerField() 로(모델만) (순수)" "$log/Pa10.txt" "$code" "Remove field company from site"

  plant_pa11 || exit 3
  pure_tests "$T_SESSION" > "$log/Pa11.txt" 2>&1; code=$?
  judge "Pa11 read_session 이 company_id 의 꼴(is_company_id)을 안 봄 (순수)" \
    "$T_SESSION::test_a_company_id_out_of_form_is_malformed[text·zero]" "$log/Pa11.txt" "$code" \
    "test_a_company_id_out_of_form_is_malformed[text]" "test_a_company_id_out_of_form_is_malformed[zero]"

  plant_pa12 || exit 3
  pure_tests "$T_STATIC" > "$log/Pa12.txt" 2>&1; code=$?
  judge "Pa12 upsert_user 가 User.for_company(company_id) 대신 User.unscoped 로 (kind, username) 만 봄 (순수)" \
    "$T_STATIC::test_product_code_does_not_use_unscoped" "$log/Pa12.txt" "$code" test_product_code_does_not_use_unscoped

  plant_pa13 || exit 3
  pure_tests "$T_STATIC" > "$log/Pa13.txt" 2>&1; code=$?
  judge "Pa13 seed_company 가 Company.register 대신 Company.unscoped.create (순수)" \
    "$T_STATIC::test_product_code_does_not_use_unscoped + ::test_the_company_entrances_are_called_only_from_their_place" \
    "$log/Pa13.txt" "$code" test_product_code_does_not_use_unscoped test_the_company_entrances_are_called_only_from_their_place
}

# Ra 의 앞 단: 보안 층 고정물과 같은 길(주인 역할로 빈 DB 를 만들고 settings.migrate 로 manage.py migrate)로 migrate 가
# 0 으로 끝나고 앱 역할(esg_app)에게 users 의 SELECT 가 없는 것을 찍는다. 끝나면 지운다(DB 이름은 보안 층의 것과 같다 —
# 바로 뒤의 보안 층 실행이 다시 지우고 만든다).
ra_migrate_probe() {
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
            row = conn.execute("SELECT has_table_privilege('esg_app', 'users', 'SELECT')").fetchone()
            granted = None if row is None else bool(row[0])
finally:
    drop_and(create=False)
print(f"    (Ra 앞 단: {name} 에 migrate 종료 {code} · 앱 역할의 users SELECT {granted})")
sys.exit(0 if code == 0 and granted is False else 1)
PY
  )
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in Pa2 Pa3 Pa4 Pa6 Pa7 Pa9 Pa10 Pa12 Ra; do total=$((total + 1)); echo "$n → ★ 못 잼(compose 의 postgres 가 떠 있지 않다) · GREEN"; done
    return
  fi
  local c1 c2

  # Pa2. for_company 가 범위(hints)는 싣되 조건(filter)을 빼먹는다. 보안의 목록과 업무의 SQL 회사 조건 둘 다 빨개야 잡음.
  plant_pa2 || exit 3
  security_tests "$S_PATHS::test_a_list_shows_only_my_tenant" > "$log/Pa2s.txt" 2>&1; c1=$?
  business_tests "$B_ORG_SEL::test_the_sites_query_names_the_tenant" > "$log/Pa2b.txt" 2>&1; c2=$?
  cat "$log/Pa2s.txt" "$log/Pa2b.txt" > "$log/Pa2.txt"
  echo "    (보안 종료 $c1 · 업무 종료 $c2)"
  judge "Pa2 CompanyScopedManager.for_company 가 filter 없이 범위만 실음 (보안 + 업무)" \
    "$S_PATHS::test_a_list_shows_only_my_tenant + $B_ORG_SEL::test_the_sites_query_names_the_tenant" \
    "$log/Pa2.txt" "$(both "$c1" "$c2")" test_a_list_shows_only_my_tenant test_the_sites_query_names_the_tenant

  # Pa3. 조건부 unique 를 모델·마이그레이션 둘 다에서 뺀다(업무 층이 세션마다 테스트 DB 를 새로 migrate 한다).
  plant_pa3_both || exit 3
  business_tests "$B_USER_MODELS::test_a_service_username_is_unique_within_its_company" > "$log/Pa3b.txt" 2>&1; code=$?
  judge "Pa3 users 의 (company, username) 조건부 unique 를 모델·마이그레이션에서 뺌 (업무)" \
    "$B_USER_MODELS::test_a_service_username_is_unique_within_its_company" "$log/Pa3b.txt" "$code" \
    test_a_service_username_is_unique_within_its_company

  # Pa4. kind·company CHECK 를 모델·마이그레이션 둘 다에서 뺀다.
  plant_pa4_both || exit 3
  business_tests "$B_USER_MODELS::test_kind_and_company_go_together" > "$log/Pa4.txt" 2>&1; code=$?
  judge "Pa4 users 의 kind·company CHECK 를 모델·마이그레이션에서 뺌 (업무)" \
    "$B_USER_MODELS::test_kind_and_company_go_together" "$log/Pa4.txt" "$code" test_kind_and_company_go_together

  # Pa6. by_subdomain 이 subdomain 칸 대신 name 칸으로 찾는다(머리말 ★). 보안의 교환과 업무의 교환 둘 다 빨개야 잡음.
  plant_pa6 || exit 3
  security_tests "$S_EXCHANGE::test_user_already_in_another_tenant_is_its_own_user" > "$log/Pa6s.txt" 2>&1; c1=$?
  business_tests "$B_USER_API::test_first_exchange_creates_the_user_and_sets_the_cookie" > "$log/Pa6b.txt" 2>&1; c2=$?
  cat "$log/Pa6s.txt" "$log/Pa6b.txt" > "$log/Pa6.txt"
  echo "    (보안 종료 $c1 · 업무 종료 $c2)"
  judge "Pa6 find_company 가 subdomain 대신 name 으로 찾음(by_subdomain 의 filter(subdomain=…) → filter(name=…)) (보안 + 업무)" \
    "$S_EXCHANGE::test_user_already_in_another_tenant_is_its_own_user + $B_USER_API::test_first_exchange_creates_the_user_and_sets_the_cookie" \
    "$log/Pa6.txt" "$(both "$c1" "$c2")" \
    test_user_already_in_another_tenant_is_its_own_user test_first_exchange_creates_the_user_and_sets_the_cookie

  # Pa7. list_sites 가 상수 1 을 넘긴다. 보안의 「B 의 것 전부, 그리고 B 의 것만」.
  plant_pa7 || exit 3
  security_tests "$S_PATHS::test_numeric_neighbour_ids_never_show_up_for_my_session" > "$log/Pa7s.txt" 2>&1; code=$?
  judge "Pa7 list_sites 가 세션의 회사 대신 상수 1 을 all_sites 에 넘김 (보안)" \
    "$S_PATHS::test_numeric_neighbour_ids_never_show_up_for_my_session" "$log/Pa7s.txt" "$code" \
    test_numeric_neighbour_ids_never_show_up_for_my_session

  # Pa9. 같은 값의 둘째 실행이 행을 하나 더 만든다.
  plant_pa9 || exit 3
  business_tests "$B_SEED::test_the_same_values_twice_leave_one_row" > "$log/Pa9.txt" 2>&1; code=$?
  judge "Pa9 seed_company 가 같은 값의 둘째 실행에서 행을 하나 더 (업무)" \
    "$B_SEED::test_the_same_values_twice_leave_one_row" "$log/Pa9.txt" "$code" test_the_same_values_twice_leave_one_row

  # Pa10. sites → company 의 외래 키를 모델·마이그레이션 둘 다에서 숫자 칸으로(보안 층이 세션마다 새로 migrate 한다).
  plant_pa10_both || exit 3
  security_tests "$S_FK::test_every_foreign_key_between_tenant_tables_names_the_tenant" > "$log/Pa10s.txt" 2>&1; code=$?
  judge "Pa10 Site.company 를 company_id = BigIntegerField() 로(모델·마이그레이션) (보안 — 뿌리 키의 분모)" \
    "$S_FK::test_every_foreign_key_between_tenant_tables_names_the_tenant" "$log/Pa10s.txt" "$code" \
    test_every_foreign_key_between_tenant_tables_names_the_tenant

  # Pa12. upsert_user 가 unscoped 로 (kind, username) 만 본다 → B 의 교환이 A 의 행을 덮는다.
  plant_pa12 || exit 3
  security_tests "$S_EXCHANGE::test_user_already_in_another_tenant_is_its_own_user" > "$log/Pa12s.txt" 2>&1; code=$?
  judge "Pa12 upsert_user 가 User.unscoped 로 (kind, username) 만 봄 (보안)" \
    "$S_EXCHANGE::test_user_already_in_another_tenant_is_its_own_user" "$log/Pa12s.txt" "$code" \
    test_user_already_in_another_tenant_is_its_own_user

  # Ra. 거꾸로 심기: user/0001 의 grant 줄을 비운다(파일은 둔다). 빨개져야(permission denied) 잡음.
  plant_ra || exit 3
  total=$((total + 1))
  if ! ra_migrate_probe; then
    echo "Ra → ★ 못 잼(앞 단: migrate 가 0 으로 끝나고 앱 역할의 users SELECT 가 없어야 한다) · GREEN"
    restore_files
    return
  fi
  "$A/scripts/test-security.sh" -rfE -p no:cacheprovider \
    "$S_EXCHANGE::test_user_already_in_another_tenant_is_its_own_user" \
    "$S_PATHS::test_numeric_neighbour_ids_never_show_up_for_my_session" \
    "$S_PATHS::test_a_list_shows_only_my_tenant" > "$log/Ra.txt" 2>&1; code=$?
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|errors?) in ' "$log/Ra.txt" | tail -1 | sed 's/^/    /'
  grep -E '^(FAILED|ERROR) ' "$log/Ra.txt" | sed -E 's/ - .*//; s/^/      /'
  echo "    permission denied 줄 $(grep -c -i 'permission denied' "$log/Ra.txt") · 첫 줄: $(grep -i -m1 'permission denied' "$log/Ra.txt" | cut -c1-200)"
  if [ "$code" -ne 0 ] && grep -q -E '^(FAILED|ERROR) ' "$log/Ra.txt" && grep -q -i 'permission denied' "$log/Ra.txt"; then
    ok=$((ok + 1))
    echo "Ra 거꾸로: user/0001 의 grant 줄을 비움 → 빨개진 것: $S_EXCHANGE · $S_PATHS(교환·/me·sites, permission denied) · RED (정상)"
  else
    echo "★ Ra 가 초록 — 멈춤"
    echo "Ra 거꾸로: user/0001 의 grant 줄을 비움 → 빨개진 것: 없음(종료 $code) · GREEN (★ 실패)"; tail -15 "$log/Ra.txt" | sed 's/^/    | /'
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
