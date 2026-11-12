#!/usr/bin/env bash
# 밴드 K1b-1(MARC-TICK-358: 사업장 넓힘 · 자산/시설 코드 목록(공통) · 사업장별 자산/시설 · /branches · 코드 목록 경로)의
# §4 자기검증(발주서 band-handoffs/K1b-1-order.md §4). 틀은 section4-IR4.sh.
#   사용: apps/api-py/scripts/section4-K1b-1.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --with-containers 면 단계 7(makemigrations·organization DB 시험)·8(③ 보안 층 전량)·10(심은 고장 — DB 시험)을 돈다.
#   안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 K1b-1.out/s4).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
O="$E/organization"
C="$E/core"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../K1b-1.out/s4}"
PURE_PATHS="esgapi/organization esgapi/core esgapi/config"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C
NOKEY="env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY"

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 K1b-1 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-1(organization 몫) + 1-6 허락 표. 경계마다 누적.
ALLOWED_1="^$O/models\.py\$
^$O/migrations/000[23]_[a-z_]+\.py\$
^$O/service/(selectors|services)/branches\.py\$
^$O/management/commands/seed_company\.py\$
^$O/tests/.*
^$A/scripts/(section4|planted-breaks)-K1b-1\.sh\$
^$C/tests/isolation/(test_managers|test_static_rules)\.py\$
^$C/tests/(test_selector_scope|test_transaction_rules)\.py\$
^$S/(test_owner|test_migrations|test_same_company_foreign_keys)\.py\$"
ALLOWED_2="^$O/service/(apis|schemas|selectors|services|permissions|utils|actions)/[a-z_]+\.py\$
^$C/permissions\.py\$
^$C/schemas\.py\$
^$C/tests/(test_permissions|test_permissions_wiring)\.py\$
^$E/config/tests/test_api_times\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool)\.py\$"
# ③→② 옮김(감독 10-28 (가) — pre-commit 훅이 순수 층 전부를 돌려 ② 의 generated 어긋남 빨강으로는 커밋이 안 된다):
#   generated 다시 뽑음과 config/tests 셋은 ② 몫이 됐다. ③ 은 tests/security·config/api.py(0줄 목표).
ALLOWED_3="^$E/config/api\.py\$
^$S/(test_tenant_paths|test_operator_company|test_login|test_request_transactions|test_branches)\.py\$"
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"
[ "$COMMIT" -ge 3 ] && ALLOWED="$ALLOWED
$ALLOWED_3"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# 1-2 0줄 + d9 (바) 0줄. core/schemas.py 는 ② 에서 :82 주석 한 줄만(아래 s2 가 따로 센다).
ZERO="$C/isolation $C/auth $C/exceptions.py $O/migrations/0001_initial.py $E/user $E/inventory $E/reference $E/runs
apps/web $A/pyproject.toml $A/uv.lock $A/.importlinter $A/conftest.py $A/tests/support $S/conftest.py $S/seed.py
$A/tests_integration scripts/verify.sh"
s2() {
  local missing=0 p n bad schema_lines
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u | grep .)"
  if [ "$COMMIT" -lt 2 ]; then
    git diff --quiet "$BASE" -- "$C/schemas.py" || bad="$bad
$C/schemas.py(경계 ② 전)"
  else
    schema_lines="$(git diff --numstat "$BASE" -- "$C/schemas.py" | awk '{print $1+$2}')"
    [ -z "$schema_lines" ] || [ "$schema_lines" -le 2 ] || bad="$bad
$C/schemas.py(바뀐 줄 $schema_lines — :82 주석 한 줄만)"
  fi
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

# 1-6 공유 줄: numstat 과 「-」 줄 원문. 셈 파일의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
COUNTS="$C/tests/test_permissions.py $C/tests/test_permissions_wiring.py $C/tests/test_transaction_rules.py
$C/tests/test_selector_scope.py $C/tests/isolation/test_static_rules.py $C/tests/isolation/test_managers.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_request_schemas_reject_bool.py
$E/config/tests/test_api_times.py $S/test_login.py $S/test_tenant_paths.py $S/test_owner.py $S/test_operator_company.py $S/test_migrations.py
$S/test_same_company_foreign_keys.py $S/test_request_transactions.py"
PERMITTED="$C/permissions.py $C/schemas.py $E/config/api.py"
s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS $PERMITTED | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $PERMITTED > "$OUT/s3-permitted.diff"
  grep -E '^(\+\+\+ |-[^-])' "$OUT/s3-permitted.diff" | sed 's/^/  허락 줄 /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS > "$OUT/s3.diff"
  python3 -I - "$OUT/s3.diff" <<'PYEOF'
import re, sys
# 셈 줄 꼴이 아닌데 1-6 허락 표가 이름으로 허락한 「-」 줄(그 자리를 목록으로 넓힘)
LISTED = {
    '    assert marked == ["reference/service/selectors/reference.py"]',  # test_selector_scope :268 marked(ce 가 B2)
    # test_api_contract: Bearer 동작 집합에 코드 목록 넷(ce 다 — config/tests, ③→② 옮김)
    '        bearer == {("get", "/users/me"), ("post", "/users/me/password")} | USER_ADMIN_OPERATIONS | AI_SETTING_OPERATIONS',
    # test_login url_of: replace 한 줄(d9 다 — {branch_id}·{code_id} 를 더함)
    '    return url.replace("{user_id}", "1")  # 사용자 관리의 초기화(K2c — 경로 변환기가 int 라 숫자로)',
}
def norm(line):
    line = re.sub(r"#.*$", "", line)
    return re.sub(r"\d+", "N", line).rstrip()
bad = 0
minus, plus = [], []
def flush():
    global bad, minus, plus
    pool = [norm(p) for p in plus]
    for m in minus:
        print(f"  - {m}")
        if m in LISTED:
            print("    (1-6 허락 표의 목록 줄)")
        elif norm(m) in pool:
            pool.remove(norm(m))
        else:
            print("    ★ 숫자·같은 줄 주석 밖이 바뀐 「-」 줄")
            bad += 1
    minus, plus = [], []
for raw in open(sys.argv[1], encoding="utf-8"):
    if raw.startswith("@@") or raw.startswith("diff "):
        flush()
    elif raw.startswith("-") and not raw.startswith("---"):
        minus.append(raw[1:].rstrip("\n"))
    elif raw.startswith("+") and not raw.startswith("+++"):
        plus.append(raw[1:].rstrip("\n"))
flush()
print(f"  셈 파일 「-」 줄 중 허용 밖 {bad} — bad_minus={bad}")
sys.exit(1 if bad else 0)
PYEOF
}

s4() {
  local log kept broken
  log="$(cd "$A" && $NOKEY uv run --frozen lint-imports 2>&1)"
  echo "$log" | tail -3 | sed 's/^/  /'
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?}"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ]
}

s5() {
  local code=0
  (cd "$A" && uv run --frozen ruff check . 2>&1 | tail -1 | sed 's/^/  ruff check /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check . 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen pyright 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  return $code
}

# ② 에서 generated(커밋본)와 어긋나 빨개지던 계약 시험 열넷 — ③→② 옮김(감독 10-28 (가)) 뒤로는 ② 도 0 이어야 한다.
#   아래 목록은 기록으로만 남기고 판정에는 쓰지 않는다(GENERATED_RED_ALLOWED 가 빈 값).
GENERATED_RED_ALLOWED=""
GENERATED_RED_WAS="esgapi/config/tests/test_api_contract.py::test_openapi_and_docs_are_served
esgapi/config/tests/test_api_contract.py::test_the_served_openapi_is_the_committed_one
esgapi/config/tests/test_api_contract.py::test_committed_openapi_matches_the_code
esgapi/config/tests/test_api_contract.py::test_operation_ids_are_the_hand_written_table
esgapi/config/tests/test_api_contract.py::test_an_operation_declares_413_exactly_when_it_takes_a_body
esgapi/config/tests/test_api_contract.py::test_444_is_declared_by_the_token_takers
esgapi/config/tests/test_api_contract.py::test_every_operation_declares_exactly_these_response_codes
esgapi/config/tests/test_api_errors.py::test_every_operation_that_declares_errors_declares_422_and_500
esgapi/config/tests/test_api_errors.py::test_444_is_declared_exactly_by_the_operations_that_take_a_token
esgapi/config/tests/test_request_schemas_reject_bool.py::test_every_integer_field_of_every_request_body_rejects_true
esgapi/core/tests/test_permissions.py::test_every_authenticated_operation_is_in_the_table
esgapi/core/tests/test_permissions.py::test_the_public_operations_are_these_seven
esgapi/core/tests/test_permissions.py::test_the_cells_are_partitioned
esgapi/core/tests/test_permissions.py::test_initial_users_reach_only_these_operations"
s6() {
  local log code n red outside
  # shellcheck disable=SC2086
  log="$(cd "$A" && $NOKEY uv run --frozen pytest $PURE_PATHS -m "not django_db" -q -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s6-pure.log"
  n="$(echo "$log" | tail -1)"
  red="$(echo "$log" | sed -n 's/^FAILED \([^ ]*\).*/\1/p' | sort -u)"
  echo "  순수($PURE_PATHS) $n EXIT=$code · 빨강 $(echo "$red" | grep -c .)"
  if [ "$COMMIT" = 2 ]; then
    outside="$(echo "$red" | grep . | grep -v -x -F -f <(printf "%s\n" "$GENERATED_RED_ALLOWED" | grep . || echo "-"))"
    [ -z "$outside" ] || echo "$outside" | sed 's/^/  ★ 허용 밖 빨강: /'
    echo "  ② 빨강 허용 0(③→② 옮김 뒤) — 빨강 $(echo "$red" | grep -c .)"
    [ -z "$outside" ] && [ "$(echo "$log" | grep -c '^ERROR ')" = 0 ]
  else
    [ "$code" = 0 ]
  fi
}

up_postgres() {
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/up.log" 2>&1 || { tail -3 "$OUT/up.log"; return 1; }
  fi
}

s7() {
  local code=0 blog="$OUT/s7-business.log"
  up_postgres || return 1
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && $NOKEY scripts/test-business.sh -p no:cacheprovider esgapi/organization esgapi/core esgapi/user esgapi/config) \
    > "$blog" 2>&1 || code=1
  echo "  업무(organization·core·user·config) $(tail -1 "$blog")"
  if [ "$COMMIT" -ge 2 ]; then  # 검증자 R1(경계 ①): ② 부터 ① 의 보안 층 셋을 붙인다(③ 은 [8] 전량)
    (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider tests/security/test_owner.py \
      tests/security/test_migrations.py tests/security/test_same_company_foreign_keys.py) > "$OUT/s7-security3.log" 2>&1 || code=1
    echo "  보안 층 셋(owner·migrations·same_company_foreign_keys) $(tail -1 "$OUT/s7-security3.log")"
  fi
  return $code
}

s8() {
  local slog="$OUT/s8-security.log" code
  up_postgres || return 1
  (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  code=$?
  echo "  보안 층 전량 $(tail -1 "$slog") EXIT=$code"
  return $code
}

# ②③: generated/ 를 다시 뽑아 cmp + <기준> 과의 차이 — 지운 줄 0, 더함 = 새 경로 열하나·새 컴포넌트·옛 /sites 둘의
#   deprecated: true 뿐.
s9() {
  local g="$OUT/s9-generated" code=0 f
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && $NOKEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  if [ "$COMMIT" -ge 2 ]; then  # ③→② 옮김: ② 부터 커밋본과 cmp
    for f in openapi.json api.d.ts api.d.ts.source-sha256; do
      if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
    done
  else  # ②: generated 는 ③ 이 다시 뽑는다 — 커밋본 0바이트, 새로 뽑은 것을 <기준> 과 견준다
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 $COMMIT 에서 generated/ 가 바뀜"; code=1; }
    echo "  generated/ 커밋본 0바이트(경계 $COMMIT) · 새로 뽑은 것을 <기준> 과 견줌"
  fi
  git show "$BASE:$A/generated/openapi.json" > "$g/openapi.base.json"
  python3 -I - "$g/openapi.base.json" "$g/openapi.json" <<'PYEOF' || code=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
added = sorted(set(b["paths"]) - set(a["paths"]))
lost = sorted(set(a["paths"]) - set(b["paths"]))
moved = []
for p in a["paths"]:
    if p not in b["paths"] or a["paths"][p] == b["paths"][p]:
        continue
    for method, op in a["paths"][p].items():
        other = dict(b["paths"][p].get(method, {}))
        if p == "/sites" and other.pop("deprecated", None) is True:
            pass
        if op != other:
            moved.append(f"{method.upper()} {p}")
    moved += [f"{m.upper()} {p}(더한 메서드)" for m in set(b["paths"][p]) - set(a["paths"][p])]
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
new = sorted(set(sb) - set(sa))
changed = [k for k in sa if k not in sb or sa[k] != sb[k]]
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
rest += [k for k in set(a["components"]) | set(b["components"]) if k != "schemas" and a["components"].get(k) != b["components"].get(k)]
ids = sorted(op.get("operationId") for p in b["paths"] for op in b["paths"][p].values()
             if op.get("operationId", "").startswith("organization_"))
print(f"  path 더함 {added} · 지움 {lost} · 바뀜 {moved}")
print(f"  organization 동작 {len(ids)} {ids}")
print(f"  schema 더함 {len(new)}({', '.join(new)}) · 바뀜·지움 {changed} · 그 밖 {rest}")
want = sorted(["organization_branches_" + n for n in ("list", "get", "create", "save", "inventory", "delete")]
              + ["organization_facility_codes_list"]
              + ["organization_admin_facility_codes_" + n for n in ("list", "create", "update", "delete")])
ok = ids == want and not lost and not moved and not changed and not rest
sys.exit(0 if ok else 1)
PYEOF
  return $code
}

s10() {
  local log
  up_postgres || return 1
  log="$($NOKEY "$A/scripts/planted-breaks-K1b-1.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local log code=0
  log="$($NOKEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s11-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS" || code=1  # R7: ② 갈래도 PASS 를 요구(③→② 옮김 뒤 빨강 허용 0)
  if [ "$COMMIT" = 2 ]; then  # ②: 실패가 generated 어긋남 목록 안이면 통과로 센다(발주서 §2)
    local red outside nonzero
    red="$(echo "$log" | sed -n 's/^FAILED \([^ ]*\).*/\1/p' | sort -u)"
    outside="$(echo "$red" | grep . | grep -v -x -F -f <(printf "%s\n" "$GENERATED_RED_ALLOWED" | grep . || echo "-"))"
    [ -z "$outside" ] || echo "$outside" | sed 's/^/  ★ 허용 밖 실패: /'
    echo "  ② verify --fast 실패 $(echo "$red" | grep -c .) — 모두 generated 어긋남 목록 안이어야 함"
    # R2: pytest 밖 단계는 EXIT 전부 0 — 0 아닌 단계 줄은 순수 층 pytest 하나뿐이어야 한다
    nonzero="$(echo "$log" | grep -c '^EXIT=[1-9]')"
    echo "  단계 EXIT 0 아님 $nonzero(순수 층 pytest 하나만 허용)"
    [ -z "$outside" ] && [ "$(echo "$log" | grep -c '^ERROR ')" = 0 ] && [ "$nonzero" -le 1 ] || code=1
  else
    echo "$log" | grep -q "VERIFY_FAST=PASS" || code=1
  fi
  if [ "$COMMIT" -ge 3 ]; then
    (cd apps/web && pnpm -s typecheck > "$OUT/s11-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
    echo "  apps/web typecheck $(tail -1 "$OUT/s11-web-typecheck.log")"
  fi
  return $code
}

step 1 "바뀐 경로가 1-1·1-6 안(outside=0)" s1
step 2 "1-2·d9 (바) 0줄" s2
step 3 "1-6 공유 줄 numstat·「-」 줄 원문(bad_minus=0)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "ruff·pyright·check_test_layout" s5
step 6 "순수 시험(organization·core·config — not django_db)" s6
if [ "$CONTAINERS" = 1 ]; then
  step 7 "makemigrations --check · 업무 층(organization·core·user·config)" s7
else
  not_run 7 "makemigrations --check · 업무 층" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 3 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 8 ]; then echo "[8] 보안 층 전량 — 경계 $COMMIT 은 §4-8 밖(③ 몫) EXIT=0 0s"; fi
elif [ "$CONTAINERS" = 1 ]; then
  step 8 "보안 층 전량(scripts/test-security.sh)" s8
else
  not_run 8 "보안 층 전량" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 2 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 9 ]; then  # ① 은 경로 0
    if git diff --quiet "$BASE" -- "$A/generated"; then
      echo "[9] generated — 경계 ① 은 0바이트 EXIT=0 0s"
    else
      echo "[9] generated — ★ 경계 ① 에서 바뀜 EXIT=1 0s"; FAILS=$((FAILS + 1))
    fi
  fi
else
  step 9 "generated 다시 뽑아 <기준> 과 diff · 지운 줄 0(③ 은 커밋본 cmp)" s9
fi
if [ "$CONTAINERS" = 1 ]; then
  step 10 "심은 고장(경계 $COMMIT 몫)" s10
else
  not_run 10 "심은 고장" "--with-containers 없음"
fi
step 11 "뿌리 verify.sh --fast(③ + apps/web typecheck)" s11
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
