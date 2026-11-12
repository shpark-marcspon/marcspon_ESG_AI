#!/usr/bin/env bash
# 밴드 K2c 의 심은 파손(발주서가 정본): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K2c.sh --pure         순수 몫(컨테이너 없이). 마지막 줄 PLANTED=<잡은 수>/3
#         apps/api-py/scripts/planted-breaks-K2c.sh --containers   업무·보안 몫(compose 의 postgres 가 떠 있어야 한다). PLANTED=<잡은 수>/8
#         apps/api-py/scripts/planted-breaks-K2c.sh                전부. 마지막 줄 PLANTED=<잡은 수>/11
# 틀은 planted-breaks-K2a.sh 다. 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가 되돌린다(되돌리는 데
# git 을 쓰지 않는다. 죽어도 trap 이 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 그 파일들의 `git status --porcelain` 이
# 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# ★ git status 는 심는 파일들로 좁혀 잰다(이 스크립트가 도는 동안 다른 손이 테스트 파일을 쓸 수 있다).
# ★ 그래도 파일을 잃었으면(kill -9 등으로 trap 이 못 돌았으면) 그 파일만 `git show HEAD:<경로> > <경로>` 로 되찾는다
#   (checkout·reset·stash 를 쓰지 않는다 — 커밋 안 된 다른 변경까지 쓸려 간다).
# 「잡음(RED)」의 기준: 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다(다른 까닭으로 빨개진
#   것을 잡았다고 세지 않는다). 업무·보안의 이름이 같은 테스트(P25)가 있어 이름은 파일 이름까지 적는다
#   (test_users.py::… · test_user_admin.py::…). 심는 글자가 지금 파일에 정확히 한 번 있지 않으면 심지 못한 것이다(종료 3).
# 출력: 파손마다 「P<n> <무엇> : RED|GREEN(★ not caught)」.
# 컨테이너 몫이 심은 것을 보는 길: 업무·보안 층은 호스트에서 `uv run pytest` 로 돈다(test-business.sh·test-security.sh —
#   compose 에서는 postgres 만 쓴다). 그래서 작업 트리의 파일을 고치면 그대로 보인다(이미지 다시 짓기·bind mount 0).
#   떠 있는 서버(api-py 컨테이너)의 이미지·DB 는 건드리지 않는다.
# ★ 두 몫에 걸친 파손(P10·P21·P22)은 순수 몫과 컨테이너 몫을 따로 센다(K2a 의 P15·P15b 꼴): 순수는 P10·P21·P22,
#   컨테이너는 P10c(업무 + 보안 — 둘 다 빨개야 잡음)·P21s·P22s.
# ★ P27(목록에 운영 관리자 행이 섞임)은 「kind 조건을 뺌」으로 심지 않는다: for_company(<회사>)는 company_id = <회사> 라
#   운영 관리자 행(회사 NULL — users_kind_company_check)이 애초에 안 걸린다(같은 답을 내는 변이 — 잡을 테스트가 없다).
#   대신 운영 관리자 행 전부를 OR 로 섞는다(User._manager()._admins()).
# ★ P23h 는 HTTP 초기화만 refresh 를 안 끊게 심는다(actor_user_id 가 실린 부름 = HTTP. 명령은 None 이라 그대로 끊는다).
# 브로커를 쓰지 않는다. AI 공급사 호출 0. 비밀번호·토큰 글자를 찍지 않는다. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac
export PYTHONDONTWRITEBYTECODE=1   # 심은 판의 .pyc 를 남기지 않는다

A=apps/api-py
E="$A/esgapi"
PERMS="$E/core/permissions.py"
SEL="$E/user/service/selectors/user.py"
PASSWORD_ACT="$E/user/service/actions/password.py"
ORG_SEL="$E/organization/service/selectors/organization.py"
USERS_API="$E/user/service/apis/users.py"
# 테스트 경로(순수·업무는 apps/api-py 기준, 보안은 test-security.sh 가 apps/api-py 로 들어가 돈다)
T_PERMS=esgapi/core/tests/test_permissions.py
T_STATIC=esgapi/core/tests/isolation/test_static_rules.py
B_USERS=esgapi/user/tests/service/apis/test_users.py
S_ADMIN=tests/security/test_user_admin.py

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$PERMS" "$SEL" "$PASSWORD_ACT" "$ORG_SEL" "$USERS_API")
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
# 두 층을 돌린 것을 하나로 판정한다: 둘 다 0 이 아니어야 종료 코드를 1 로 본다.
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
OPERATOR_CELL='        return kind == "admin"'
KIND_IMPORT=$'from esgapi.core.auth.principal import Kind\n'
LIST_ROWS='    rows = User.for_company(company_id).filter(kind="service").order_by("id")'
ACCOUNT_ROW='    return User.for_company(company_id).select_related("company").filter(pk=user_id, kind="service").first()'
LOCK_ROW='    return User.for_company(company_id).select_for_update().filter(pk=user_id, kind="service").first()'
RESET_REVOKE=$'    RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)\n    services.note("password_reset", row, actor_user_id=actor_user_id)\n'
MANY_COMPANIES=$'    if len(rows) > 1:\n        return ManyCompanies()\n'
IS_LOCKED='        isLocked=is_locked(row.login_expiry_at, moment),'
LIST_ORDER=$'    principal = permitted(request, "user_list")\n    company_id = chosen_company(companyId, company_ports())\n'

plant_p10() { edit "$PERMS" "$OPERATOR_CELL" '        return True  # 심은 파손 P10: operator 칸이 kind 를 안 봄'; }
plant_p21() {
  edit "$SEL" "$KIND_IMPORT" $'from django.db.models import QuerySet\n\n'"$KIND_IMPORT" &&
    edit "$SEL" "$LIST_ROWS" '    rows = QuerySet(model=User).filter(kind="service").order_by("id")  # 심은 파손 P21'
}
plant_p22() {
  edit "$SEL" "$ACCOUNT_ROW" '    return User.unscoped.select_related("company").filter(pk=user_id, kind="service").first()  # 심은 파손 P22' &&
    edit "$SEL" "$LOCK_ROW" '    return User.unscoped.select_for_update().filter(pk=user_id, kind="service").first()  # 심은 파손 P22'
}
plant_p23h() {
  edit "$PASSWORD_ACT" "$RESET_REVOKE" \
    $'    if actor_user_id is None:  # 심은 파손 P23h: HTTP 초기화(actor 있음)는 refresh 를 안 끊음\n        RefreshToken.of_user(row.pk).filter(revoked_at__isnull=True).update(revoked_at=now)\n    services.note("password_reset", row, actor_user_id=actor_user_id)\n'
}
plant_p25() { edit "$ORG_SEL" "$MANY_COMPANIES" ''; }
plant_p26() { edit "$USERS_API" "$IS_LOCKED" '        isLocked=row.login_expiry_at is not None and moment < row.login_expiry_at,  # 심은 파손 P26'; }
plant_p27() { edit "$SEL" "$LIST_ROWS" '    rows = (User.for_company(company_id) | User._manager()._admins()).order_by("id")  # 심은 파손 P27'; }
plant_p29() {
  edit "$USERS_API" "$LIST_ORDER" \
    $'    company_id = chosen_company(companyId, company_ports())  # 심은 파손 P29: 권한 앞에 회사 고르기\n    principal = permitted(request, "user_list")\n'
}

pure() {
  plant_p10 || exit 3
  pure_tests "$T_PERMS" > "$log/P10.txt" 2>&1; code=$?
  judge P10 "is_allowed 의 operator 칸이 kind 를 안 봄(고객사 사용자가 셋을 지남) → $T_PERMS" "$log/P10.txt" "$code" \
    test_a_customer_is_refused_every_operator_cell

  plant_p21 || exit 3
  pure_tests "$T_STATIC" > "$log/P21.txt" 2>&1; code=$?
  judge P21 "목록이 for_company 없이 QuerySet(model=User) 의 kind 조건만 → $T_STATIC" "$log/P21.txt" "$code" \
    test_querysets_are_built_only_in_the_entrances

  plant_p22 || exit 3
  pure_tests "$T_STATIC" > "$log/P22.txt" 2>&1; code=$?
  judge P22 "초기화 대상을 회사 없이 id 로만 찾음(account·lock_account 가 User.unscoped) → $T_STATIC" "$log/P22.txt" "$code" \
    test_product_code_does_not_use_unscoped
}

containers() {
  if ! docker compose ps --status running --format '{{.Service}}' 2> /dev/null | grep -qx postgres; then
    local n; for n in P10c P21s P22s P23h P25 P26 P27 P29; do
      total=$((total + 1)); echo "$n ★ 못 잼(compose 의 postgres 가 떠 있지 않다) : GREEN(★ not caught)"
    done
    return
  fi
  local c1 c2

  plant_p10 || exit 3
  business_tests "$B_USERS::test_a_customer_gets_403_on_all_three_and_nothing_is_read_or_written" > "$log/P10b.txt" 2>&1; c1=$?
  security_tests "$S_ADMIN::test_a_customer_gets_403_on_every_user_admin_operation_and_nothing_is_written" > "$log/P10s.txt" 2>&1; c2=$?
  cat "$log/P10b.txt" "$log/P10s.txt" > "$log/P10c.txt"
  echo "    (업무 종료 $c1 · 보안 종료 $c2)"
  judge P10c "is_allowed 의 operator 칸이 kind 를 안 봄 (업무 + 보안)" "$log/P10c.txt" "$(both "$c1" "$c2")" \
    "test_users.py::test_a_customer_gets_403_on_all_three_and_nothing_is_read_or_written" \
    "test_user_admin.py::test_a_customer_gets_403_on_every_user_admin_operation_and_nothing_is_written"

  plant_p21 || exit 3
  security_tests "$S_ADMIN::test_the_user_list_shows_only_the_named_company" > "$log/P21s.txt" 2>&1; code=$?
  judge P21s "목록이 for_company 없이 kind 조건만 (보안 — 남의 회사 행이 보임)" "$log/P21s.txt" "$code" \
    "test_user_admin.py::test_the_user_list_shows_only_the_named_company"

  plant_p22 || exit 3
  security_tests "$S_ADMIN::test_a_reset_with_another_company_is_404_and_changes_nothing" > "$log/P22s.txt" 2>&1; code=$?
  judge P22s "초기화 대상을 회사 없이 id 로만 찾음 (보안 — 남의 회사 사용자가 초기화됨)" "$log/P22s.txt" "$code" \
    "test_user_admin.py::test_a_reset_with_another_company_is_404_and_changes_nothing"

  plant_p23h || exit 3
  security_tests "$S_ADMIN::test_a_reset_revokes_the_users_families_and_is_committed" > "$log/P23h.txt" 2>&1; code=$?
  judge P23h "HTTP 초기화가 refresh 를 안 끊음 (보안)" "$log/P23h.txt" "$code" \
    "test_user_admin.py::test_a_reset_revokes_the_users_families_and_is_committed"

  plant_p25 || exit 3
  business_tests "$B_USERS::test_without_company_id_two_companies_are_400_and_nothing_is_written" > "$log/P25b.txt" 2>&1; c1=$?
  security_tests "$S_ADMIN::test_without_company_id_two_companies_are_400_and_nothing_is_written" > "$log/P25s.txt" 2>&1; c2=$?
  cat "$log/P25b.txt" "$log/P25s.txt" > "$log/P25.txt"
  echo "    (업무 종료 $c1 · 보안 종료 $c2)"
  judge P25 "회사가 둘 이상이어도 첫 행을 하나뿐인 회사로 고름 (업무 + 보안)" "$log/P25.txt" "$(both "$c1" "$c2")" \
    "test_users.py::test_without_company_id_two_companies_are_400_and_nothing_is_written" \
    "test_user_admin.py::test_without_company_id_two_companies_are_400_and_nothing_is_written"

  plant_p26 || exit 3
  business_tests "$B_USERS::test_is_locked_is_the_logins_judgement_to_the_second" > "$log/P26.txt" 2>&1; code=$?
  judge P26 "isLocked 를 now < login_expiry_at 로 따로 셈(같은 초가 풀림) (업무)" "$log/P26.txt" "$code" \
    "test_users.py::test_is_locked_is_the_logins_judgement_to_the_second"

  plant_p27 || exit 3
  business_tests "$B_USERS::test_the_list_shows_only_the_named_companys_customers" > "$log/P27.txt" 2>&1; code=$?
  judge P27 "목록에 운영 관리자 행이 섞임 (업무)" "$log/P27.txt" "$code" \
    "test_users.py::test_the_list_shows_only_the_named_companys_customers"

  plant_p29 || exit 3
  business_tests "$B_USERS::test_a_customer_gets_403_on_all_three_and_nothing_is_read_or_written" > "$log/P29.txt" 2>&1; code=$?
  judge P29 "목록 경로가 permitted 앞에서 회사를 고름 (업무 — 403 앞의 회사 고르기 0)" "$log/P29.txt" "$code" \
    "test_users.py::test_a_customer_gets_403_on_all_three_and_nothing_is_read_or_written"
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
