#!/usr/bin/env bash
# 밴드 K2a 의 심은 파손(발주서 a-3-4 가 정본): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K2a.sh --pure         순수 몫(컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/8
#         apps/api-py/scripts/planted-breaks-K2a.sh --containers   업무·보안 몫(compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/15
#         apps/api-py/scripts/planted-breaks-K2a.sh                전부. 마지막 줄 PLANTED=<잡은 수>/23
# 틀은 planted-breaks-K1u-a.sh·planted-breaks-E1b.sh 다. 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가
# 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 그 파일들의
# `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# ★ git status 는 심는 파일들로 좁혀 잰다: 이 스크립트가 도는 동안 다른 손이 테스트 파일을 쓸 수 있다(K2a ⑤ 의 보안
#   테스트) — 남의 새 파일을 「되돌림 실패」로 세지 않는다.
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (checkout·reset·stash 를 쓰지 않는다 — 커밋 안 된 다른 변경까지 쓸려 간다).
# 「잡음(RED)」의 기준: 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다(다른 까닭으로 빨개진
#   것을 잡았다고 세지 않는다). 심는 글자가 지금 파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 출력: 파손마다 「P<n> <무엇> : RED|GREEN(★ not caught)」.
# 컨테이너 몫이 심은 것을 보는 길: 업무·보안 층은 호스트에서 `uv run pytest` 로 돈다(test-business.sh·test-security.sh —
#   compose 에서는 postgres 만 쓴다). 그래서 작업 트리의 파일을 고치면 그대로 보인다(이미지 다시 짓기·bind mount 0).
#   떠 있는 서버(api-py 컨테이너)의 이미지·DB 는 건드리지 않는다.
# ★ R(거꾸로 심기)은 user/0002 의 grant 줄을 비운다(파일은 둔다 — K1u-a 의 Ra 와 같은 길). 보안 층의 고정물이 세션마다
#   테스트 DB(<POSTGRES_DB>_py_test)를 지우고 지금 작업 트리의 마이그레이션으로 다시 migrate 하므로 볼륨을 새로 하지
#   않아도 된다. 앞 단에서 같은 길로 migrate 가 0 으로 끝나고 앱 역할에게 user_refresh_tokens 의 INSERT 가 없는 것을 찍는다.
#   앱 역할로 붙는 보안 층의 로그인·refresh 가 permission denied 로 빨개야 정상(RED = 잡음).
# ★ P3 은 read_access 의 aud 만 끈다(_decode 의 options 에 "verify_aud": audience != ACCESS_AUDIENCE — refresh 의 칸막이는 둔다).
# ★ P6b 는 재사용 갈래에서 블록 안에서 던진다(ApplicationError token_not_valid). 블록이 되돌아가 계보 끊기가 사라져야 잡힌다.
# ★ P15 는 순수(정적 규칙)와 업무(명령의 출력) 두 몫이다: 순수는 P15, 업무는 P15b 로 따로 센다.
# 브로커를 쓰지 않는다. AI 공급사 호출 0. 비밀번호·토큰 글자를 찍지 않는다. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1   # 심은 판의 .pyc 를 남기지 않는다

A=apps/api-py
E="$A/esgapi"
TOKENS="$E/core/auth/tokens.py"
BEARER="$E/core/auth/bearer.py"
PERMS="$E/core/permissions.py"
SEL="$E/user/service/selectors/user.py"
USER_MODELS="$E/user/models.py"
CREATE_CMD="$E/user/management/commands/create_user.py"
LOGIN_SV="$E/user/service/services/login.py"
PASSWORD_ACT="$E/user/service/actions/password.py"
M_REFRESH="$E/user/migrations/0002_refresh_tokens.py"
# 테스트 경로(순수·업무는 apps/api-py 기준, 보안은 test-security.sh 가 apps/api-py 로 들어가 돈다)
T_TOKENS=esgapi/core/tests/auth/test_tokens.py
T_BEARER=esgapi/core/tests/auth/test_bearer.py
T_PERMS=esgapi/core/tests/test_permissions.py
T_STATIC=esgapi/core/tests/isolation/test_static_rules.py
B_LOGIN=esgapi/user/tests/service/services/test_login.py
B_LOGIN_API=esgapi/user/tests/service/apis/test_login.py
B_PASSWORD=esgapi/user/tests/service/actions/test_password.py
B_CREATE=esgapi/user/tests/management/commands/test_create_user.py
B_RESET=esgapi/user/tests/management/commands/test_reset_password.py
S_LOGIN=tests/security/test_login.py
S_REFRESH=tests/security/test_refresh.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$TOKENS" "$BEARER" "$PERMS" "$SEL" "$USER_MODELS" "$CREATE_CMD" "$LOGIN_SV" "$PASSWORD_ACT" "$M_REFRESH")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
status_of_files() { git status --porcelain -- "${FILES[@]}"; }
sums > "$keep/.sums-before"
status_of_files > "$keep/.status-before"
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
# 두 층(또는 두 번)을 돌린 것을 하나로 판정한다: 둘 다 0 이 아니어야 종료 코드를 1 로 본다.
both() { [ "$1" -ne 0 ] && [ "$2" -ne 0 ] && echo 1 || echo 0; }

# <번호> <설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local num="$1" what="$2" file="$3" code="$4" missed=0 wanted
  shift 4
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|errors?) in |^FAILED|^ERROR' "$file" | sed 's/^/    /' | cut -c1-230 | head -8
  [ "$code" -ne 0 ] || missed=1
  for wanted in "$@"; do
    grep '^FAILED ' "$file" | grep -q -F "$wanted" || { missed=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$missed" -eq 0 ]; then
    ok=$((ok + 1)); echo "$num $what : RED"
  else
    echo "$num $what : GREEN(★ not caught)"; tail -15 "$file" | sed 's/^/    | /'
  fi
  restore_files
}

# 심는 글자(지금 코드에서 정확히 한 번씩 있다 — edit 가 센다).
AUD_OPTIONS='            options={"require": ["aud", "sub", "iat", "exp", "jti"], "verify_exp": False},'
AUD_OFF='            options={"require": ["aud", "sub", "iat", "exp", "jti"], "verify_exp": False, "verify_aud": audience != ACCESS_AUDIENCE},'
ACCESS_EXPIRY='    if now >= claims.expires_at:'
PAIR_CHECK=$'    if kind == "service" and is_company_id(company_id) and isinstance(company_is_active, bool):\n        company: tuple[int | None, bool | None] = (company_id, company_is_active)\n    elif kind == "admin" and company_id is None and company_is_active is None:\n        company = (None, None)\n    else:\n        return TokenRejected("malformed")\n'
PAIR_GONE=$'    company: tuple[int | None, bool | None] = (company_id, company_is_active)  # 심은 파손 P8: 짝 검사 없음\n'
CUSTOMER_CELL='        return kind == "service"'
INITIAL_CHECK=$'    if principal.is_initial and operation_id not in permissions.INITIAL_ALLOWED:\n        raise ApplicationError("forbidden", "password_change_required", "먼저 비밀번호를 바꾼다(첫 로그인·초기화 뒤)")\n'
FIND_CUSTOMER='    return User.for_company(company_id).filter(kind="service", username=username).first()'
ADMIN_BY_USERNAME='        return self._admins().filter(username=username)'
CREATE_PRINT='        self.stdout.write(f"{result.user_id} {kind} {subdomain or '"'"'-'"'"'}")'
CREATE_PRINT_SECRET='        self.stdout.write(f"{result.user_id} {kind} {subdomain or '"'"'-'"'"'} {secret}")'
MAX_FAILURES='MAX_LOGIN_FAILURES: Final = 5'
EARLY_LOCK=$'    if user is not None and user.is_active and is_locked(user.login_expiry_at, now):\n        note("login_locked", user)\n        return LoginRejected("account_locked")\n'
INBLOCK_RECHECK=$'        if is_locked(row.login_expiry_at, now):\n            return AttemptLocked()\n'
HASH_THEN_CUT=$'    ok = check_password(password, encoded)\n    if user is None or not user.is_active:\n'
FAKE_HASH=$'    encoded = user.password if user is not None else make_password(None)\n'
NO_FAKE_HASH=$'    if user is None:  # 심은 파손 P14: 가짜 해시 없이 끊음\n        return LoginRejected("invalid_credentials")\n    encoded = user.password\n'
ME_AUTH='access_token_auth = AccessTokenAuth(required=True)'
USED_AT=$'                row.used_at = now\n                row.save(update_fields=["used_at"])\n'
REUSE_BRANCH=$'            _revoke_family(row.family, now)\n            outcome = RefreshRejected("reused")\n'
REUSED_OUTCOME='            outcome = RefreshRejected("reused")'
CONF_IMPORT=$'from esgapi.core.conf import app_config\n'
CHANGE_REVOKE=$'    RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)\n    return True\n'
RESET_REVOKE=$'    RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)\n    services.note("password_reset", row)\n'
CHANGE_COUNT='    attempt = services.record_password_attempt(company_id=company_id, user_id=user_id, ok=ok, now=now)'
OPERATOR_LEVEL='kind="admin", company=None, username=username, name=name, level=99, is_initial=True'
REFRESH_GRANT=$'        grant(\'"user_refresh_tokens"\', "SELECT, INSERT, UPDATE"),\n'

plant_p3() { edit "$TOKENS" "$AUD_OPTIONS" "$AUD_OFF"; }
plant_p4() { edit "$TOKENS" "$ACCESS_EXPIRY" '    if False:  # 심은 파손 P4: 만료를 안 봄'; }
plant_p8() { edit "$TOKENS" "$PAIR_CHECK" "$PAIR_GONE"; }
plant_p9() { edit "$PERMS" "$CUSTOMER_CELL" '        return True'; }
plant_p12() { edit "$BEARER" "$INITIAL_CHECK" ''; }
plant_p7() { edit "$SEL" "$FIND_CUSTOMER" '    return User.unscoped.filter(kind="service", username=username).first()'; }
plant_p20() { edit "$USER_MODELS" "$ADMIN_BY_USERNAME" '        return models.QuerySet["User"](model=self.model, using=self._db).filter(username=username)'; }
plant_p15() { edit "$CREATE_CMD" "$CREATE_PRINT" "$CREATE_PRINT_SECRET"; }
plant_p1() { edit "$TOKENS" "$MAX_FAILURES" 'MAX_LOGIN_FAILURES: Final = 6'; }
plant_p2() { edit "$LOGIN_SV" "$EARLY_LOCK" ''; }
plant_p17() { edit "$LOGIN_SV" "$INBLOCK_RECHECK" ''; }
plant_p18() { edit "$LOGIN_SV" "$HASH_THEN_CUT" $'    if user is not None and not user.is_active:  # 심은 파손 P18: 해시 전에 끊음\n        return LoginRejected("invalid_credentials")\n'"$HASH_THEN_CUT"; }
plant_p14() { edit "$LOGIN_SV" "$FAKE_HASH" "$NO_FAKE_HASH"; }
plant_p19() { edit "$BEARER" "$ME_AUTH" 'access_token_auth = AccessTokenAuth(required=False)'; }
plant_p5() { edit "$LOGIN_SV" "$USED_AT" ''; }
plant_p6() { edit "$LOGIN_SV" "$REUSE_BRANCH" $'            outcome = RefreshRejected("reused")\n'; }
plant_p6b() {
  edit "$LOGIN_SV" "$CONF_IMPORT" "$CONF_IMPORT"$'from esgapi.core.exceptions import ApplicationError\n' &&
    edit "$LOGIN_SV" "$REUSED_OUTCOME" '            raise ApplicationError("token_not_valid", "token_not_valid", "x")  # 심은 파손 P6b'
}
plant_p13() { edit "$PASSWORD_ACT" "$CHANGE_REVOKE" $'    return True\n'; }
plant_p23() { edit "$PASSWORD_ACT" "$RESET_REVOKE" $'    services.note("password_reset", row)\n'; }
plant_p24() { edit "$PASSWORD_ACT" "$CHANGE_COUNT" '    attempt = services.record_password_attempt(company_id=company_id, user_id=user_id, ok=True, now=now)'; }
plant_p28() { edit "$USER_MODELS" "$OPERATOR_LEVEL" 'kind="admin", company=None, username=username, name=name, level=79, is_initial=True'; }
plant_r() { edit "$M_REFRESH" "$REFRESH_GRANT" ''; }

pure() {
  plant_p3 || exit 3
  pure_tests "$T_TOKENS" > "$log/P3.txt" 2>&1; code=$?
  judge P3 "read_access 가 aud 를 안 봄 → $T_TOKENS aud 칸막이" "$log/P3.txt" "$code" \
    test_a_refresh_token_is_not_an_access test_a_session_cookie_is_not_an_access

  plant_p4 || exit 3
  pure_tests "$T_TOKENS" > "$log/P4.txt" 2>&1; code=$?
  judge P4 "read_access 가 만료를 안 봄 → $T_TOKENS" "$log/P4.txt" "$code" \
    test_an_access_token_is_active_one_second_before_exp_and_expired_at_exp

  plant_p8 || exit 3
  pure_tests "$T_TOKENS" > "$log/P8.txt" 2>&1; code=$?
  judge P8 "read_access 의 kind·company 짝 검사를 뺌 → $T_TOKENS" "$log/P8.txt" "$code" \
    "test_kind_and_company_must_pair[service-without-company]" "test_kind_and_company_must_pair[admin-with-company]"

  plant_p9 || exit 3
  pure_tests "$T_PERMS" > "$log/P9.txt" 2>&1; code=$?
  judge P9 "is_allowed 의 customer 칸이 kind 를 안 봄 → $T_PERMS" "$log/P9.txt" "$code" \
    test_an_operator_is_refused_every_customer_cell

  plant_p12 || exit 3
  pure_tests "$T_BEARER" > "$log/P12.txt" 2>&1; code=$?
  judge P12 "permitted 의 is_initial 검사를 뺌 → $T_BEARER" "$log/P12.txt" "$code" \
    test_an_initial_principal_on_a_company_operation_must_change_the_password_first

  plant_p7 || exit 3
  pure_tests "$T_STATIC" > "$log/P7.txt" 2>&1; code=$?
  judge P7 "find_customer 가 User.unscoped 로 (kind, username) 만 봄 → $T_STATIC" "$log/P7.txt" "$code" \
    test_product_code_does_not_use_unscoped

  plant_p20 || exit 3
  pure_tests "$T_STATIC" > "$log/P20.txt" 2>&1; code=$?
  judge P20 "admin_by_username 이 운영 관리자 조건 없이 찾음 → $T_STATIC" "$log/P20.txt" "$code" \
    test_the_operator_entrances_carry_the_admin_condition

  plant_p15 || exit 3
  pure_tests "$T_STATIC" > "$log/P15.txt" 2>&1; code=$?
  judge P15 "create_user 가 비밀번호를 찍음 → $T_STATIC" "$log/P15.txt" "$code" \
    test_no_password_or_token_reaches_a_log
}

# R 의 앞 단: 보안 층 고정물과 같은 길(주인 역할로 빈 DB 를 만들고 settings.migrate 로 manage.py migrate)로 migrate 가
# 0 으로 끝나고 앱 역할(esg_app)에게 user_refresh_tokens 의 INSERT 가 없는 것을 찍는다. 끝나면 지운다(DB 이름은 보안
# 층의 것과 같다 — 바로 뒤의 보안 층 실행이 다시 지우고 만든다).
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
granted = None
try:
    code = subprocess.run(
        [sys.executable, "manage.py", "migrate", "--no-input", "-v", "0"],
        env={**os.environ, "DJANGO_SETTINGS_MODULE": "esgapi.config.settings.migrate", "DATABASE_URL_PY_OWNER": url},
        check=False,
    ).returncode
    if code == 0:
        with psycopg.connect(url) as conn:
            row = conn.execute("SELECT has_table_privilege('esg_app', 'user_refresh_tokens', 'INSERT')").fetchone()
            granted = None if row is None else bool(row[0])
finally:
    drop_and(create=False)
print(f"    (R 앞 단: {name} 에 migrate 종료 {code} · 앱 역할의 user_refresh_tokens INSERT {granted})")
sys.exit(0 if code == 0 and granted is False else 1)
PY
  )
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in P1 P2 P17 P18 P14 P19 P5 P6 P6b P13 P23 P24 P28 P15b R; do
      total=$((total + 1)); echo "$n ★ 못 잼(compose 의 postgres 가 떠 있지 않다) : GREEN(★ not caught)"
    done
    return
  fi
  local c1 c2

  plant_p1 || exit 3
  business_tests "$B_LOGIN::test_the_fifth_failure_locks_for_ten_minutes" > "$log/P1b.txt" 2>&1; c1=$?
  security_tests "$S_LOGIN::test_the_lock_holds_at_five_and_six" > "$log/P1s.txt" 2>&1; c2=$?
  cat "$log/P1b.txt" "$log/P1s.txt" > "$log/P1.txt"
  echo "    (업무 종료 $c1 · 보안 종료 $c2)"
  judge P1 "잠금 문턱 5 → 6 (업무 + 보안)" "$log/P1.txt" "$(both "$c1" "$c2")" \
    test_the_fifth_failure_locks_for_ten_minutes test_the_lock_holds_at_five_and_six

  plant_p2 || exit 3
  business_tests "$B_LOGIN::test_a_locked_account_refuses_the_right_password_without_hashing" > "$log/P2.txt" 2>&1; code=$?
  judge P2 "login 의 앞선 잠김 검사를 뺌(비밀번호 확인 뒤에야 잠김) (업무 — 잠김 중 해시 0)" "$log/P2.txt" "$code" \
    test_a_locked_account_refuses_the_right_password_without_hashing

  plant_p17 || exit 3
  business_tests "$B_LOGIN::test_a_lock_committed_while_the_password_was_checked_wins" > "$log/P17.txt" 2>&1; code=$?
  judge P17 "record_password_attempt 의 블록 안 잠김 재확인을 뺌 (업무)" "$log/P17.txt" "$code" \
    test_a_lock_committed_while_the_password_was_checked_wins

  plant_p18 || exit 3
  business_tests "$B_LOGIN::test_every_miss_is_invalid_credentials_after_exactly_one_hash" > "$log/P18.txt" 2>&1; code=$?
  judge P18 "꺼진 사용자를 해시 전에 끊음 (업무 — 해시 한 번)" "$log/P18.txt" "$code" \
    "test_every_miss_is_invalid_credentials_after_exactly_one_hash[inactive-user]" \
    "test_every_miss_is_invalid_credentials_after_exactly_one_hash[operator-inactive]"

  plant_p14 || exit 3
  business_tests "$B_LOGIN::test_every_miss_is_invalid_credentials_after_exactly_one_hash" > "$log/P14.txt" 2>&1; code=$?
  judge P14 "없는 사용자에 가짜 해시를 안 돎 (업무 — 해시 한 번)" "$log/P14.txt" "$code" \
    "test_every_miss_is_invalid_credentials_after_exactly_one_hash[unknown-username]" \
    "test_every_miss_is_invalid_credentials_after_exactly_one_hash[unknown-company]" \
    "test_every_miss_is_invalid_credentials_after_exactly_one_hash[operator-unknown]"

  plant_p19 || exit 3
  business_tests "$B_LOGIN_API::test_me_without_a_bearer_is_401_no_token" > "$log/P19.txt" 2>&1; code=$?
  judge P19 "access_token_auth 가 required=False(/users/me 머리 없음이 no_token 아님) (업무)" "$log/P19.txt" "$code" \
    test_me_without_a_bearer_is_401_no_token

  plant_p5 || exit 3
  security_tests "$S_REFRESH::test_rotate_then_the_old_refresh_is_rejected" > "$log/P5.txt" 2>&1; code=$?
  judge P5 "refresh 가 옛 행에 used_at 을 안 적음 (보안)" "$log/P5.txt" "$code" \
    test_rotate_then_the_old_refresh_is_rejected

  plant_p6 || exit 3
  security_tests "$S_REFRESH::test_reusing_a_refresh_revokes_the_whole_family" > "$log/P6.txt" 2>&1; code=$?
  judge P6 "재사용이 계보를 안 끊음 (보안)" "$log/P6.txt" "$code" \
    test_reusing_a_refresh_revokes_the_whole_family

  plant_p6b || exit 3
  security_tests "$S_REFRESH::test_reusing_a_refresh_revokes_the_whole_family" > "$log/P6b.txt" 2>&1; code=$?
  judge P6b "재사용 갈래가 블록 안에서 던짐(계보 끊기가 되돌아감) (보안)" "$log/P6b.txt" "$code" \
    test_reusing_a_refresh_revokes_the_whole_family

  plant_p13 || exit 3
  security_tests "$S_REFRESH::test_a_password_change_revokes_other_families" > "$log/P13.txt" 2>&1; code=$?
  judge P13 "비밀번호 바꾸기가 다른 계보를 안 끊음 (보안)" "$log/P13.txt" "$code" \
    test_a_password_change_revokes_other_families

  plant_p23 || exit 3
  business_tests "$B_RESET::test_a_locked_customer_is_reset_and_every_refresh_is_revoked" > "$log/P23b.txt" 2>&1; c1=$?
  security_tests "$S_REFRESH::test_a_reset_by_the_command_revokes_the_users_families_and_is_committed" > "$log/P23s.txt" 2>&1; c2=$?
  cat "$log/P23b.txt" "$log/P23s.txt" > "$log/P23.txt"
  echo "    (업무 종료 $c1 · 보안 종료 $c2)"
  judge P23 "초기화가 refresh 를 안 끊음 (업무 + 보안)" "$log/P23.txt" "$(both "$c1" "$c2")" \
    test_a_locked_customer_is_reset_and_every_refresh_is_revoked \
    test_a_reset_by_the_command_revokes_the_users_families_and_is_committed

  plant_p24 || exit 3
  business_tests "$B_PASSWORD::test_a_wrong_current_password_counts_like_a_login" > "$log/P24.txt" 2>&1; code=$?
  judge P24 "바꾸기의 틀린 현재 비밀번호를 안 셈 (업무)" "$log/P24.txt" "$code" \
    test_a_wrong_current_password_counts_like_a_login

  plant_p28 || exit 3
  business_tests "$B_CREATE::test_an_operator_is_made_with_level_99_and_must_change_the_password" > "$log/P28.txt" 2>&1; code=$?
  judge P28 "register_admin 이 level 79 (업무)" "$log/P28.txt" "$code" \
    test_an_operator_is_made_with_level_99_and_must_change_the_password

  plant_p15 || exit 3
  business_tests "$B_CREATE::test_an_operator_is_made_with_level_99_and_must_change_the_password" > "$log/P15b.txt" 2>&1; code=$?
  judge P15b "create_user 가 비밀번호를 찍음 (업무 — 명령의 출력)" "$log/P15b.txt" "$code" \
    test_an_operator_is_made_with_level_99_and_must_change_the_password

  # R. 거꾸로 심기: user/0002 의 grant 줄을 비운다(파일은 둔다). 빨개져야(permission denied) 잡음.
  plant_r || exit 3
  total=$((total + 1))
  if ! r_migrate_probe; then
    echo "R ★ 못 잼(앞 단: migrate 가 0 으로 끝나고 앱 역할의 user_refresh_tokens INSERT 가 없어야 한다) : GREEN(★ not caught)"
    restore_files
    return
  fi
  "$A/scripts/test-security.sh" -rfE -p no:cacheprovider "$S_LOGIN" "$S_REFRESH" > "$log/R.txt" 2>&1; code=$?
  grep -E '^[0-9]+ (passed|failed)|[0-9]+ (passed|failed|errors?) in ' "$log/R.txt" | tail -1 | sed 's/^/    /'
  grep -E '^(FAILED|ERROR) ' "$log/R.txt" | sed -E 's/ - .*//; s/^/      /' | head -20
  echo "    permission denied 줄 $(grep -c -i 'permission denied' "$log/R.txt") · 첫 줄: $(grep -i -m1 'permission denied' "$log/R.txt" | cut -c1-200)"
  if [ "$code" -ne 0 ] && grep -q -E '^(FAILED|ERROR) ' "$log/R.txt" && grep -q -i 'permission denied' "$log/R.txt"; then
    ok=$((ok + 1))
    echo "R 거꾸로: user/0002 의 grant 줄을 비움 → $S_LOGIN · $S_REFRESH (permission denied) : RED"
  else
    echo "★ R 이 초록 — 멈춤"
    echo "R 거꾸로: user/0002 의 grant 줄을 비움 (종료 $code) : GREEN(★ not caught)"; tail -15 "$log/R.txt" | sed 's/^/    | /'
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
if ! diff -q "$keep/.sums-before" "$keep/.sums-after" > /dev/null || ! status_of_files | diff -q - "$keep/.status-before" > /dev/null; then
  echo "★ 되돌린 뒤의 지문이 처음과 다르다" >&2
  diff "$keep/.sums-before" "$keep/.sums-after" >&2
  status_of_files | diff - "$keep/.status-before" >&2
  exit 1
fi
echo "(되돌림 확인: 파일 ${#FILES[@]}개의 sha256 과 그 파일들의 git status 가 처음과 같다 · 기록 $log)"
echo "PLANTED=$ok/$total"
[ "$ok" = "$total" ]
