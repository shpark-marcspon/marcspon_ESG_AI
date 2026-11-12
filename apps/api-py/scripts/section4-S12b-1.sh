#!/usr/bin/env bash
# 밴드 S12b-1(MARC-TICK-462: Scope 1·2 엑셀 — 양식 GET …/template · 데이터 GET …/export)의 §4 자기검증
# (발주서 band-handoffs/S12b-1-order.md §4). 틀은 section4-S12a-2.sh(ALLOWED_n 을 1-1 파일 이름으로).
#   사용: apps/api-py/scripts/section4-S12b-1.sh --commit <1|2|3|4> [--with-containers] [--step <n>]
#   --with-containers 면 단계 7(makemigrations·DB 시험·보안 층)·8(③·④ 보안 층 전량)·10(심은 고장)을 돈다.
#   .git/verify.lock 이 있으면 [7]·[8]·[10]·[11] 앞에서 없어질 때까지 기다린다. [6] 순수도 기다린다(runner-common §5).
#   안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 S12b-1.out/s4) · S4_BASE(<기준> 덮어쓰기 — ④ merge 커밋 전).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
O="$E/organization"
C="$E/core"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../S12b-1.out/s4}"
PURE_PATHS="esgapi/inventory esgapi/organization esgapi/core esgapi/config"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C
NOKEY="env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY"

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3|4> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3 | 4) ;; *) echo "--commit <1|2|3|4> 이 필요하다" >&2; exit 2 ;; esac
LOCK="$(git rev-parse --git-common-dir)/verify.lock"
BASE="${S4_BASE:-$(git merge-base main HEAD)}"  # ④: merge 를 커밋하기 전에는 S4_BASE=<들인 main> 으로 준다
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 S12b-1 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

wait_lock() {  # .git/verify.lock 이 있는 동안 기다린다(전량 verify 와 겹치지 않게)
  local waited=0
  while [ -e "$LOCK" ]; do
    [ "$waited" = 0 ] && echo "  verify.lock 있음 — 기다림($(cat "$LOCK/pid" 2> /dev/null))"
    sleep 20
    waited=$((waited + 20))
  done
  [ "$waited" = 0 ] || echo "  verify.lock 풀림(${waited}s 기다림)"
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-1 + 1-6 허락 표. 경계마다 누적. 시험도 1-1 의 파일 이름으로(`$I/tests/.*` 0).
ALLOWED_1="^$I/tools/scope12_xlsx\.py\$
^$I/tests/tools/(__init__|test_scope12_xlsx)\.py\$
^$I/tests/test_s3sheets_is_pure\.py\$
^$A/scripts/(section4|planted-breaks)-S12b-1\.sh\$"
ALLOWED_2="^$I/service/actions/scope12_excel\.py\$
^$I/tests/service/actions/test_scope12_excel\.py\$
^$I/tests/entries_support\.py\$
^$C/tests/test_transaction_rules\.py\$"
ALLOWED_3="^$I/service/apis/(scope12_excel|inventory)\.py\$
^$I/tests/service/apis/test_scope12_excel\.py\$
^$C/permissions\.py\$
^$C/tests/(test_permissions|test_permissions_wiring)\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$S/(test_tenant_paths|test_login|test_operator_company|test_entries|test_scope12_excel)\.py\$"
# ④(main 들이기)는 더하는 자리 0 — <기준> 이 들인 main 으로 옮겨 가 main 쪽 바뀜은 차이에 없다.
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"
[ "$COMMIT" -ge 3 ] && ALLOWED="$ALLOWED
$ALLOWED_3"

s1() {
  local all outside pattern
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | grep . | paste -sd'|' -)"  # 빈 줄이 「|」 끝 빈 갈래(전부 맞음)가 되지 않게
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# 1-2 0줄 + 0줄 목표(conftest·tests/support·S/seed.py).
ZERO="$I/models.py $I/migrations $I/service/selectors $I/service/services $I/service/utils $I/service/schemas
$I/service/actions/entries.py $I/service/apis/entries.py $I/tests/test_route_shapes.py
$I/engines $I/contracts $I/flows $I/calc $I/prompts $I/data $E/reference $O $E/user
$C/isolation $C/auth $C/exceptions.py $C/schemas.py $E/runs apps/web
$A/pyproject.toml $A/uv.lock $A/.importlinter $E/config/api.py $E/config/apps_list.py
$C/tests/isolation/test_static_rules.py $C/tests/test_selector_scope.py
$A/conftest.py $A/tests/support $S/conftest.py $S/seed.py $A/tests_integration scripts/verify.sh"
s2() {
  local missing=0 p n bad
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u | grep .)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

# 1-6 공유 줄: numstat 과 「-」 줄 원문. 셈 파일의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
COUNTS="$C/tests/test_permissions.py $C/tests/test_permissions_wiring.py $C/tests/test_transaction_rules.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_request_schemas_reject_bool.py
$I/tests/test_s3sheets_is_pure.py
$S/test_login.py $S/test_tenant_paths.py $S/test_operator_company.py $S/test_entries.py $I/tests/entries_support.py"
PERMITTED="$C/permissions.py $I/service/apis/inventory.py"
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
# 셈 줄 꼴이 아닌데 1-6 허락 표가 이름으로 허락한 「-」 줄(그 자리를 목록으로 넓힘 — C0-lines.md)
LISTED: set[str] = set()  # 셈 줄 꼴이 아닌데 1-6 허락 표가 이름으로 허락한 「-」 줄(없음 — 생기면 C0-lines.md 와 함께)
def norm(line):
    # 469 R2: 주석만인 줄은 원문으로 견준다(주석을 지우면 아무 주석 「+」 줄과 짝이 된다). 코드 줄은 같은 줄 주석을 지우고
    # 숫자를 N 으로.
    if line.lstrip().startswith("#"):
        return line.rstrip()
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

# 빨강 허용 경계 없음(발주서 1-6 — pre-commit 훅이 순수 층 전부를 돈다).
s6() {
  local log code n
  wait_lock  # runner-common §5: 부분 실행도 lock 동안 0
  # shellcheck disable=SC2086
  log="$(cd "$A" && $NOKEY uv run --frozen pytest $PURE_PATHS -m "not django_db and not security" -q -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s6-pure.log"
  n="$(echo "$log" | tail -1)"
  echo "  순수($PURE_PATHS) $n EXIT=$code · 빨강 $(echo "$log" | grep -c '^FAILED ')"
  [ "$code" = 0 ]
}

up_postgres() {
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/up.log" 2>&1 || { tail -3 "$OUT/up.log"; return 1; }
  fi
}

s7() {
  local code=0 blog="$OUT/s7-business.log" SEC4="" SEC4_NAME=""
  if [ "$COMMIT" -ge 3 ]; then SEC4="tests/security/test_entries.py tests/security/test_scope12_excel.py"; SEC4_NAME="·entries·scope12_excel"; fi
  wait_lock  # 자기 postgres 만 쓰는 단계도 전량 verify 와 겹치지 않게(발주서 §4)
  up_postgres || return 1
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && $NOKEY scripts/test-business.sh -p no:cacheprovider esgapi/inventory esgapi/organization esgapi/core esgapi/config) \
    > "$blog" 2>&1 || code=1
  echo "  업무(inventory·organization·core·config) $(tail -1 "$blog")"
  wait_lock
  (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider tests/security/test_owner.py \
    tests/security/test_migrations.py $SEC4) > "$OUT/s7-security3.log" 2>&1 || code=1
  echo "  보안 층(owner·migrations$SEC4_NAME) $(tail -1 "$OUT/s7-security3.log")"
  return $code
}

s8() {
  local slog="$OUT/s8-security.log" code
  up_postgres || return 1
  wait_lock
  (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  code=$?
  echo "  보안 층 전량 $(tail -1 "$slog") EXIT=$code"
  return $code
}

# ③·④: generated/ 를 다시 뽑아 커밋본과 cmp + <기준> 과의 차이 — 지운 줄 0(git diff --patience, api.d.ts.source-sha256
#   한 줄 제외), 더함 = 경로 둘(바이너리 응답)뿐.
s9() {
  local g="$OUT/s9-generated" code=0 f removed
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && $NOKEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  # 감독 86(10-30, (가)): required 배열 끝 줄에 쉼표만 붙은 것(`"<글자>"` → `"<글자>",`)만 지운 줄에서 뺀다 — 그 밖은 셈.
  git diff --patience -U0 "$BASE" -- "$A/generated/openapi.json" "$A/generated/api.d.ts" > "$g/patience.diff"
  removed="$(python3 -I - "$g/patience.diff" <<'PYEOF'
import re, sys
minus, plus, kept, comma = [], [], 0, []
def flush():
    global minus, plus, kept
    pool = list(plus)
    for m in minus:
        if re.fullmatch(r'\s*"[^"]*"', m) and m + "," in pool:
            pool.remove(m + ","); comma.append(m.strip())
        else:
            kept += 1; print(f"  ★ 지운 줄: {m}", file=sys.stderr)
    minus, plus = [], []
for raw in open(sys.argv[1], encoding="utf-8"):
    if raw.startswith(("@@", "diff ")):
        flush()
    elif raw.startswith("-") and not raw.startswith("---"):
        minus.append(raw[1:].rstrip("\n"))
    elif raw.startswith("+") and not raw.startswith("+++"):
        plus.append(raw[1:].rstrip("\n"))
flush()
print(f"  required 끝 줄 쉼표만(뺌) {len(comma)}: {comma}", file=sys.stderr)
print(kept)
PYEOF
)"
  echo "  generated 지운 줄(patience, openapi.json·api.d.ts — 쉼표만 줄 뺀 것) $removed · source-sha256 은 한 줄 바뀜(해시)"
  [ "$removed" = 0 ] || code=1
  git show "$BASE:$A/generated/openapi.json" > "$g/openapi.base.json"
  python3 -I - "$g/openapi.base.json" "$g/openapi.json" <<'PYEOF' || code=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
added = sorted(set(b["paths"]) - set(a["paths"]))
lost = sorted(set(a["paths"]) - set(b["paths"]))
moved = [p for p in a["paths"] if p in b["paths"] and a["paths"][p] != b["paths"][p]]
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
new = sorted(set(sb) - set(sa))
changed = [k for k in sa if k not in sb or sa[k] != sb[k]]
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
rest += [k for k in set(a["components"]) | set(b["components"]) if k != "schemas" and a["components"].get(k) != b["components"].get(k)]
ids = sorted(op.get("operationId") for p in added for op in b["paths"][p].values())
print(f"  path 더함 {added} · 지움 {lost} · 바뀜 {moved}")
print(f"  새 동작 {len(ids)} {ids}")
print(f"  schema 더함 {len(new)}({', '.join(new)}) · 바뀜·지움 {changed} · 그 밖 {rest}")
want = sorted(f"inventory_scope12_{name}" for name in ("export", "template"))
# 있는 schema 는 칸을 더하기만(2-8 — 지운 칸·바뀐 칸 0). 응답 꼴의 required 는 늘어도 된다.
bad = []
for k in changed:
    if k not in sb:
        bad.append(f"{k}: 지움"); continue
    pa, pb = sa[k].get("properties", {}), sb[k].get("properties", {})
    bad += [f"{k}.{p}" for p in pa if p not in pb or pa[p] != pb[p]]
    rest_a = {x: y for x, y in sa[k].items() if x not in ("properties", "required")}
    rest_b = {x: y for x, y in sb[k].items() if x not in ("properties", "required")}
    if rest_a != rest_b or not set(sa[k].get("required", [])) <= set(sb[k].get("required", [])):
        bad.append(f"{k}: 칸 밖이 바뀜")
print(f"  있는 schema 의 지운·바뀐 칸 {bad}")
sys.exit(0 if ids == want and not lost and not moved and not bad and not rest else 1)
PYEOF
  return $code
}

s10() {
  local log
  up_postgres || return 1
  wait_lock
  local code
  log="$($NOKEY "$A/scripts/planted-breaks-S12b-1.sh" --commit "$COMMIT" 2>&1)"
  code=$?  # 검증 R4: 「심은 수 ≠ 배치」·못 심음은 종료 코드로만 닿는다
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "  planted-breaks 종료 코드 $code"
  [ "$code" = 0 ] && echo "$log" | grep -q "^FINGERPRINT=same" \
    && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local log code=0
  wait_lock
  log="$($NOKEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s11-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS" || code=1
  if [ "$COMMIT" -ge 3 ]; then
    (cd apps/web && pnpm -s typecheck > "$OUT/s11-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
    echo "  apps/web typecheck $(tail -1 "$OUT/s11-web-typecheck.log")"
  fi
  return $code
}

step 1 "바뀐 경로가 1-1·1-6 안(outside=0)" s1
step 2 "1-2 0줄" s2
step 3 "1-6 공유 줄 numstat·「-」 줄 원문(bad_minus=0)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "ruff·pyright·check_test_layout" s5
step 6 "순수 시험(inventory·organization·core·config — not django_db and not security)" s6
if [ "$CONTAINERS" = 1 ]; then
  step 7 "makemigrations --check · 업무 층(inventory·organization·core·config) · 보안 층(③~ entries·scope12_excel)" s7
else
  not_run 7 "makemigrations --check · 업무 층 · 보안 층" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 3 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 8 ]; then echo "[8] 보안 층 전량 — 경계 $COMMIT 은 §4-8 밖(③·④ 몫) EXIT=0 0s"; fi
elif [ "$CONTAINERS" = 1 ]; then
  step 8 "보안 층 전량(scripts/test-security.sh)" s8
else
  not_run 8 "보안 층 전량" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 3 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 9 ]; then  # ①② 는 경로 0
    if git diff --quiet "$BASE" -- "$A/generated"; then
      echo "[9] generated — 경계 $COMMIT 은 0바이트 EXIT=0 0s"
    else
      echo "[9] generated — ★ 경계 $COMMIT 에서 바뀜 EXIT=1 0s"; FAILS=$((FAILS + 1))
    fi
  fi
else
  step 9 "generated 다시 뽑아 커밋본 cmp · <기준> 과 지운 줄 0(patience)" s9
fi
if [ "$CONTAINERS" = 1 ]; then
  step 10 "심은 고장(경계 $COMMIT 몫)" s10
else
  not_run 10 "심은 고장" "--with-containers 없음"
fi
step 11 "뿌리 verify.sh --fast(모든 경계 · ③~ + apps/web typecheck)" s11
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
