#!/usr/bin/env bash
# 밴드 S12b-2(MARC-TICK-504: Scope 1·2 일괄 올리기 POST …/uploads)의 §4 자기검증(발주서 band-handoffs/S12b-2-order.md §4).
#   사용: apps/api-py/scripts/section4-S12b-2.sh --commit <1|2|3> [--with-containers] [--step <n>]
# 단계마다 앞에서 .git/verify.lock 을 본다: 있으면 exit 3, 없으면 「lock 없음 확인 <시각>」. 단계마다 「[n] <설명> EXIT=<n> <초>s」,
#   끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(S4_BASE 로 덮어씀 — main 들이기 전). AI 공급사 호출 0.
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -euo pipefail
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
O="$E/organization"
C="$E/core"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../S12b-2.out/s4}"
WORDS="${S4_WORDS:-$ROOT/../S12b-2.out/forbidden-words.txt}"  # 저장소 밖 금지 낱말(값을 스크립트에 적지 않는다)
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
LOCK="$(cd "$(git rev-parse --git-common-dir)" && pwd)/verify.lock"
BASE="${S4_BASE:-$(git merge-base main HEAD)}"
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 S12b-2 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start code
  shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  if [ -e "$LOCK" ]; then echo "[$n] verify.lock 있음 — 멈춤"; exit 3; fi
  echo "── [$n] $what · lock 없음 확인 $(date +%H:%M:%S)"
  start=$(date +%s)
  if "$@"; then code=0; else code=$?; fi
  echo "[$n] $what EXIT=$code $(($(date +%s) - start))s"
  if [ "$code" -ne 0 ]; then FAILS=$((FAILS + 1)); fi
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# 발주서 1-1(닫힌 목록). 경계마다 누적.
ALLOWED_1="^$I/tools/(scope12_upload|xlsx_reader)\.py\$
^$I/tests/tools/test_scope12_upload\.py\$
^$I/tests/test_s3sheets_(reader_limits|is_pure)\.py\$
^$A/scripts/(section4|planted-breaks)-S12b-2\.sh\$"
ALLOWED_2="^$I/service/actions/scope12_upload\.py\$
^$I/tests/service/actions/test_scope12_upload\.py\$
^$I/tests/entries_support\.py\$
^$C/tests/test_transaction_rules\.py\$"
ALLOWED_3="^$I/service/apis/(scope12_excel|inventory)\.py\$
^$I/service/schemas/entries\.py\$
^$I/tests/service/apis/test_scope12_upload\.py\$
^$I/tests/test_route_shapes\.py\$
^$C/permissions\.py\$
^$C/tests/(test_permissions|test_permissions_wiring)\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$S/(test_tenant_paths|test_login|test_operator_company|test_entries|test_scope12_upload)\.py\$"
ALLOWED="$ALLOWED_1"
if [ "$COMMIT" -ge 2 ]; then ALLOWED="$ALLOWED
$ALLOWED_2"; fi
if [ "$COMMIT" -ge 3 ]; then ALLOWED="$ALLOWED
$ALLOWED_3"; fi

# 발주서 1-2(풀어 쓴 경로).
ZERO="$I/service/actions/entries.py $I/service/apis/entries.py $I/tools/scope12_xlsx.py $I/service/actions/scope12_excel.py
$I/models.py $I/migrations $I/service/selectors $I/service/services $I/service/utils
$I/engines $I/contracts $I/flows $I/calc $I/prompts $I/data
$O $E/user $E/reference $C/isolation $C/auth $C/exceptions.py $C/schemas.py apps/web
$A/.importlinter $A/pyproject.toml $A/uv.lock $A/gunicorn.conf.py $E/config/settings $E/config/api.py $E/config/apps_list.py
$E/dataverify"

s1() {
  local all outside pattern bad p n missing=0
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | grep . | paste -sd'|' -)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | { grep -v -E -e "$pattern" || true; } | { grep -c . || true; })"
  if [ "$outside" -ne 0 ]; then echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'; fi
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | { grep -c . || true; })"
    if [ "$n" -eq 0 ]; then echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); fi
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; git diff --name-only "$BASE" -- "$I/service/*/scope3_*.py"; } | sort -u | { grep . || true; })"
  if [ -n "$bad" ]; then echo "$bad" | sed 's/^/  ★ 0줄 자리: /'; fi
  echo "  바뀐 파일 $(echo "$all" | { grep -c . || true; }) · outside=$outside · 0줄 자리 바뀜 $(echo "$bad" | { grep -c . || true; }) · <기준> 에 없는 자리 $missing"
  [ "$outside" -eq 0 ] && [ -z "$bad" ] && [ "$missing" -eq 0 ]
}

s2() {
  local code=0 log kept broken
  log="$(cd "$A" && $NOKEY uv run --frozen lint-imports 2>&1)" || code=1
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?}"
  if [ "${kept:-0}" != "$BASE_CONTRACTS" ] || [ "${broken:-1}" != 0 ]; then code=1; fi
  (cd "$A" && uv run --frozen ruff check . > "$OUT/ruff.log" 2>&1) || code=1
  tail -1 "$OUT/ruff.log" | sed 's/^/  ruff check /'
  (cd "$A" && uv run --frozen ruff format --check . > "$OUT/format.log" 2>&1) || code=1
  tail -1 "$OUT/format.log" | sed 's/^/  ruff format /'
  (cd "$A" && uv run --frozen pyright > "$OUT/pyright.log" 2>&1) || code=1
  tail -1 "$OUT/pyright.log" | sed 's/^/  pyright /'
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$OUT/layout.log" 2>&1) || code=1
  tail -1 "$OUT/layout.log" | sed 's/^/  /'
  return "$code"
}

s3() {
  local code=0
  (cd "$A" && $NOKEY uv run --frozen pytest esgapi/inventory esgapi/core esgapi/config -m "not django_db" -q -p no:cacheprovider) \
    > "$OUT/s3-pure.log" 2>&1 || code=$?
  echo "  순수 $(tail -1 "$OUT/s3-pure.log")"
  return "$code"
}

up() {
  if [ "$(docker compose ps --status running --services 2> /dev/null | { grep -c '^postgres$' || true; })" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/up.log" 2>&1
  fi
}

s4() {
  local code=0
  up
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run) > "$OUT/s4-migrations.log" 2>&1 || code=1
  tail -1 "$OUT/s4-migrations.log" | sed 's/^/  /'
  (cd "$A" && $NOKEY scripts/test-business.sh -p no:cacheprovider esgapi/inventory esgapi/core esgapi/config) \
    > "$OUT/s4-business.log" 2>&1 || code=1
  echo "  업무(inventory·core·config) $(tail -1 "$OUT/s4-business.log")"
  if [ "$COMMIT" -ge 3 ]; then
    # 마감 판은 storage 를 띄워 skip 0(6d (사)) — 주소는 .env 에서, 값을 찍지 않는다(section4-RX1a.sh 의 s3_env 꼴).
    docker compose up -d --wait storage > "$OUT/up-storage.log" 2>&1 || code=1
    (cd "$A" && . scripts/db-env.sh \
      && export RUNBUNDLE_S3_ENDPOINT="http://127.0.0.1:$(env_value STORAGE_PORT)" \
        RUNBUNDLE_S3_BUCKET="$(env_value S3_BUCKET)" RUNBUNDLE_S3_REGION="$(env_value S3_REGION)" \
        RUNBUNDLE_S3_ACCESS_KEY="$(env_value STORAGE_ACCESS_KEY)" RUNBUNDLE_S3_SECRET_KEY="$(env_value STORAGE_SECRET_KEY)" \
      && $NOKEY scripts/test-security.sh -p no:cacheprovider) > "$OUT/s4-security.log" 2>&1 || code=1
    echo "  보안 전량 $(tail -1 "$OUT/s4-security.log")"
  fi
  return "$code"
}

# 1-5 셈 줄: numstat 과 「-」 줄 원문. 셈 파일의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
COUNTS="$C/tests/test_permissions.py $C/tests/test_permissions_wiring.py $C/tests/test_transaction_rules.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_request_schemas_reject_bool.py
$I/tests/test_s3sheets_is_pure.py $I/tests/test_route_shapes.py $I/tests/entries_support.py $I/tests/test_s3sheets_reader_limits.py
$S/test_login.py $S/test_tenant_paths.py $S/test_operator_company.py $S/test_entries.py"
s5() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS "$C/permissions.py" | sed 's/^/  numstat /'
  # 1-5 H1: 머리 주석 두 줄의 바뀜은 허락 표가 이름으로 받는다 — 원문을 찍고 셈 줄 대조에서는 뺀다.
  git diff -U0 "$BASE" -- "$C/permissions.py" | { grep -E '^-[^-]' || true; } | sed 's/^/  허락 줄(H1) /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS > "$OUT/s5.diff"
  python3 -I - "$OUT/s5.diff" <<'PYEOF'
import re, sys
def norm(line):
    if line.lstrip().startswith("#"):
        return line.rstrip()
    return re.sub(r"\d+", "N", re.sub(r"#.*$", "", line)).rstrip()
bad = 0
minus, plus = [], []
def flush():
    global bad, minus, plus
    pool = [norm(p) for p in plus]
    for m in minus:
        print(f"  - {m}")
        if norm(m) in pool:
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

# ③: generated 다시 뽑아 cmp · <기준> 과 지운 줄 0 · 더함 = 경로 하나 + EntryUploadOut.
s6() {
  local g="$OUT/s6-generated" code=0 f
  rm -rf "$g"
  mkdir -p "$g"
  (cd "$A" && $NOKEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log"
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
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
ids = sorted(op.get("operationId") for p in added for op in b["paths"][p].values())
print(f"  path 더함 {added} · 지움 {lost} · 바뀜 {moved}")
print(f"  새 동작 {ids} · schema 더함 {new} · 바뀜·지움 {changed}")
sys.exit(0 if ids == ["inventory_scope12_upload"] and new == ["EntryUploadOut"] and not lost and not moved and not changed else 1)
PYEOF
  return "$code"
}

s7() {
  local log code=0
  up
  log="$($NOKEY "$A/scripts/planted-breaks-S12b-2.sh" --commit "$COMMIT" 2>&1)" || code=$?
  echo "$log" > "$OUT/s7-planted.log"
  echo "$log" | sed 's/^/  /'
  return "$code"
}

s8() {
  local added hits keys xlsx
  [ -s "$WORDS" ] || { echo "  ★ 금지 낱말 파일이 없다: $WORDS"; return 1; }
  added="$( { git diff "$BASE" -- . ":(exclude)$A/generated"; git ls-files -o --exclude-standard | while read -r f; do sed 's/^/+/' "$f"; done; } | { grep '^+' || true; })"
  hits="$(echo "$added" | { grep -c -i -F -f "$WORDS" || true; })"
  keys="$(echo "$added" | { grep -E -c 'sk-[A-Za-z0-9_-]{16}|BEGIN [A-Z ]*PRIVATE KEY' || true; })"
  xlsx="$(changed | { grep -c -E '\.xlsx$' || true; })"
  echo "  더한 줄 $(echo "$added" | { grep -c . || true; }) · 낱말 파일 $(wc -l < "$WORDS" | tr -d ' ')줄 · 금지 낱말 $hits · 키 꼴 $keys · 새 .xlsx $xlsx"
  [ "$hits" = 0 ] && [ "$keys" = 0 ] && [ "$xlsx" = 0 ]
}

s9() {
  local log code=0
  log="$($NOKEY scripts/verify.sh --fast 2>&1)" || code=$?
  echo "$log" > "$OUT/s9-verify-fast.log"
  echo "$log" | { grep -E "VERIFY_FAST=" || true; } | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS" && [ "$code" = 0 ]
}

step 1 "바뀐 경로 ⊆ 1-1 · 1-2 diff 0" s1
step 2 "lint-imports · ruff · pyright · check_test_layout" s2
step 3 "순수(inventory·core·config)" s3
if [ "$CONTAINERS" = 1 ]; then
  step 4 "makemigrations · 업무 · (③) 보안 전량" s4
else
  not_run 4 "makemigrations · 업무 · 보안" "--with-containers 없음"
fi
step 5 "셈 줄 앞→뒤 · 표 밖 「-」 0" s5
if [ "$COMMIT" -ge 3 ]; then
  step 6 "generated 다시 뽑아 cmp · 지운 줄 0" s6
elif [ -z "$ONLY" ] || [ "$ONLY" = 6 ]; then
  if git diff --quiet "$BASE" -- "$A/generated"; then echo "[6] generated — 경계 $COMMIT 은 0바이트 EXIT=0 0s"; else echo "[6] generated ★ 바뀜 EXIT=1 0s"; FAILS=$((FAILS + 1)); fi
fi
if [ "$CONTAINERS" = 1 ]; then
  step 7 "심은 파손(경계 $COMMIT 몫)" s7
else
  not_run 7 "심은 파손" "--with-containers 없음"
fi
step 8 "위생(기업명·키 꼴·새 .xlsx)" s8
step 9 "뿌리 scripts/verify.sh --fast" s9
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
