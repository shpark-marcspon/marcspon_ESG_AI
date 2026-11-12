#!/usr/bin/env bash
# 밴드 S12a-3(MARC-TICK-461: Scope 1·2 대시보드 서버 — GET /inventory/scope12/dashboard)의 §4 자기검증
# (발주서 band-handoffs/S12a-3-order.md §4). 틀은 앞 밴드의 section4 그대로(R1 ALLOWED 는 1-1 파일 이름 · R2 주석만 「-」
# 줄은 원문으로 견줌).
#   사용: apps/api-py/scripts/section4-S12a-3.sh --commit <1|2> [--with-containers] [--step <n>]
#   --with-containers 면 단계 7(makemigrations·DB 시험·보안 층 넷)·8(② 보안 층 전량)·10(심은 고장)을 돈다.
#   .git/verify.lock 이 있으면 [7]·[8]·[10]·[11] 앞에서 없어질 때까지 기다린다.
#   안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 S12a-3.out/s4).
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
OUT="${S4_OUT:-$ROOT/../S12a-3.out/s4}"
PURE_PATHS="esgapi/inventory esgapi/organization esgapi/core esgapi/config"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C
NOKEY="env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY -u OPENAI_API_KEY -u ANTHROPIC_API_KEY"

COMMIT=""; ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 --commit <1|2> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac
LOCK="$(git rev-parse --git-common-dir)/verify.lock"
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 S12a-3 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-1(이 트랙 땅) + 1-3 허락 표. 경계마다 누적. 시험도 1-1 의 파일 이름으로.
ALLOWED_1="^$I/service/(utils|actions)/dashboard\.py\$
^$I/service/selectors/entries\.py\$
^$I/tests/service/(utils|actions)/test_dashboard\.py\$
^$A/scripts/(section4|planted-breaks)-S12a-3\.sh\$
^$C/tests/test_transaction_rules\.py\$"
ALLOWED_2="^$I/service/(apis|schemas)/dashboard\.py\$
^$I/service/apis/inventory\.py\$
^$I/service/schemas/entries\.py\$
^$I/tests/service/apis/test_dashboard\.py\$
^$I/tests/test_route_shapes\.py\$
^$C/permissions\.py\$
^$C/tests/(test_permissions|test_permissions_wiring)\.py\$
^$E/config/tests/(test_api_contract|test_api_errors)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$S/(test_tenant_paths|test_entries|test_login|test_operator_company)\.py\$"
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"

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

# 1-2 0줄 + 1-1 의 0줄(이 트랙 안이라도). H7(test_static_rules) 0줄(처분 Q2 가). 웹 0줄.
ZERO="$E/config/api.py $E/config/apps_list.py $C/flows $C/calc $C/llm $E/runs $O $A/.importlinter
$A/pyproject.toml $A/uv.lock $A/scripts/planted-breaks.sh $E/config/tests/test_request_schemas_reject_bool.py apps/web
$I/models.py $I/migrations $I/engines $I/contracts $I/flows $I/data
$I/service/actions/entries.py $I/service/apis/entries.py $I/service/services/entries.py
$I/service/actions/ghg_pool.py $I/service/apis/ghg_pool.py $I/service/schemas/ghg_pool.py $I/service/services/ghg_pool.py
$I/service/selectors/ghg_pool.py $I/service/utils/ghg_pool.py
$I/service/actions/index_selection.py $I/service/apis/index_selection.py $I/service/schemas/index_selection.py
$I/service/services/index_selection.py $I/service/selectors/index_selection.py $I/service/utils/index_selection.py
$I/service/actions/scope3_runs.py $I/service/apis/scope3_runs.py $I/service/actions/scope3_shortlist.py
$I/service/schemas/inventory.py $I/service/utils/entries.py
$C/tests/isolation/test_static_rules.py $A/conftest.py $A/tests/support $S/conftest.py scripts/verify.sh"
[ "$COMMIT" -lt 2 ] && ZERO="$ZERO $I/service/schemas/entries.py $I/service/apis/inventory.py $C/permissions.py $A/generated"
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

# 1-3 공유 줄: numstat 과 「-」 줄 원문. 셈 파일의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
# 권한 머리 주석 두 줄(H2 — 처분 Q5)은 원문을 이름으로 허락한다(LISTED).
COUNTS="$C/permissions.py $C/tests/test_transaction_rules.py $C/tests/test_permissions.py $C/tests/test_permissions_wiring.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py
$S/test_tenant_paths.py $S/test_entries.py $S/test_login.py $S/test_operator_company.py
$I/service/apis/inventory.py $I/service/selectors/entries.py $I/tests/test_route_shapes.py"
s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS > "$OUT/s3.diff"
  python3 -I - "$OUT/s3.diff" > "$OUT/s3-minus.txt" <<'PYEOF'
import re, sys
LISTED = {
    # H2(7a — 처분 Q5): 권한 머리 주석의 회사 업무 셈
    "    # 회사 업무 64(문서 7·실행 4·그린워싱 7·영문번역 8·데이터 검증 4·중대성평가 3·원고작성 9·사업장 6·코드 목록 1",
    "    # ·인덱스 선택 2 ·Scope 1·2 입력 11 ·인벤토리 Scope 3 2): 두 kind 다 —",
    # 1-1 selectors/entries.py(처분 Q2 가): year_rows 의 values_list 한 줄이 칸 다섯 줄로(ruff format)
    '        "selection__inventory_year__year", "selection__facility_node_id", "site_facility__site_id", "emission"',
    # B1(감독 0d — critic): route_shapes 의 결과 꼴 셈이 대시보드 경로를 늘 보게
    "    for operation in with_colab_result(operations()):",
    "    assert reached == set(RENAMED.values()) | colab",
}
def norm(line):
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
            print("    (허락 표·처분의 이름 줄)")
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
  local code=$?
  cat "$OUT/s3-minus.txt"
  return $code
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

s6() {
  local log code n
  wait_lock
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
  if [ "$COMMIT" -ge 2 ]; then SEC4="tests/security/test_entries.py tests/security/test_tenant_paths.py"; SEC4_NAME="·entries·tenant_paths"; fi
  wait_lock
  up_postgres || return 1
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  wait_lock
  (cd "$A" && $NOKEY scripts/test-business.sh -p no:cacheprovider esgapi/inventory esgapi/core esgapi/config) \
    > "$blog" 2>&1 || code=1
  echo "  업무(inventory·core·config) $(tail -1 "$blog")"
  wait_lock
  # shellcheck disable=SC2086
  (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider tests/security/test_owner.py \
    tests/security/test_migrations.py tests/security/test_same_company_foreign_keys.py $SEC4) > "$OUT/s7-security.log" 2>&1 || code=1
  echo "  보안 층(owner·migrations·same_company_foreign_keys$SEC4_NAME) $(tail -1 "$OUT/s7-security.log")"
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

# ②: generated/ 를 다시 뽑아 커밋본과 cmp + <기준> 과의 차이. 지운 줄은 (가) required 끝 줄 쉼표만(감독 86 꼴) 과
#   (나) 처분 Q4 설명 셋(488-2 — 옛 글자를 이름으로) 만 뺀다. 그 밖 지운 줄 0. Scope3Colab 든 줄 바뀜 0. 더한 경로는
#   대시보드 하나, 새 꼴은 전부 Scope12Dashboard 앞머리, 있는 꼴은 Q4 설명 셋 말고 0 바뀜.
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
  git diff --patience -U0 "$BASE" -- "$A/generated/openapi.json" "$A/generated/api.d.ts" > "$g/patience.diff"
  removed="$(python3 -I - "$g/patience.diff" <<'PYEOF'
import re, sys
OLD_TEXT = ("YYYY-MM — 그 해의 열두 달", "직접입력 계수(S9 — 1차에 없음, 늘 거짓)", "value · na_on · na_off")
minus, plus, kept, comma, described, colab = [], [], 0, [], [], 0
def flush():
    global minus, plus, kept
    pool = list(plus)
    for m in minus:
        if re.fullmatch(r'\s*"[^"]*"', m) and m + "," in pool:
            pool.remove(m + ","); comma.append(m.strip())
        elif any(text in m for text in OLD_TEXT):
            described.append(m.strip())
        else:
            kept += 1; print(f"  ★ 지운 줄: {m}", file=sys.stderr)
    minus, plus = [], []
for raw in open(sys.argv[1], encoding="utf-8"):
    if raw.startswith(("@@", "diff ")):
        flush()
    elif raw.startswith("-") and not raw.startswith("---"):
        minus.append(raw[1:].rstrip("\n"))
        colab += "Scope3Colab" in raw
    elif raw.startswith("+") and not raw.startswith("+++"):
        plus.append(raw[1:].rstrip("\n"))
        colab += "Scope3Colab" in raw
flush()
print(f"  끝 줄 쉼표만(뺌) {len(comma)}: {comma}", file=sys.stderr)
print(f"  Q4 설명 줄(뺌, 원문) {len(described)}:", file=sys.stderr)
for line in described:
    print(f"    - {line}", file=sys.stderr)
print(f"  Scope3Colab 든 바뀐 줄 {colab}", file=sys.stderr)
print(kept + colab)
PYEOF
)"
  echo "  generated 지운 줄(쉼표만·Q4 설명 뺀 것) + Scope3Colab 바뀐 줄 = $removed · source-sha256 은 한 줄 바뀜(해시)"
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
print(f"  schema 더함 {len(new)}({', '.join(new)}) · 바뀜 {changed} · 그 밖 {rest}")
# 있는 꼴의 바뀜은 칸 description 글자만(처분 Q4 — EntrySlot*·EntryFactorOut.isCustom·EntryHistoryOut.kind)
def strip(schema):
    out = json.loads(json.dumps(schema))
    for prop in out.get("properties", {}).values():
        prop.pop("description", None)
        for key in ("items",):
            if isinstance(prop.get(key), dict):
                prop[key].pop("description", None)
    return out
bad = [k for k in changed if k not in sb or strip(sa[k]) != strip(sb[k]) or not k.startswith("Entry")]
print(f"  있는 꼴의 description 밖 바뀜 {bad} · description 만 바뀐 꼴 {sorted(set(changed) - set(bad))}")
names_ok = all(name.startswith("Scope12Dashboard") for name in new)
print(f"  새 꼴 전부 Scope12Dashboard 앞머리 {names_ok}")
sys.exit(0 if ids == ["inventory_scope12_dashboard"] and not lost and not moved and not bad and not rest and names_ok else 1)
PYEOF
  return $code
}
s10() {
  local log
  up_postgres || return 1
  wait_lock
  local code
  log="$($NOKEY "$A/scripts/planted-breaks-S12a-3.sh" --commit "$COMMIT" 2>&1)"
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
  if [ "$COMMIT" -ge 2 ]; then
    (cd apps/web && pnpm -s typecheck > "$OUT/s11-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
    echo "  apps/web typecheck $(tail -1 "$OUT/s11-web-typecheck.log")"
  fi
  return $code
}

step 1 "바뀐 경로가 1-1·1-3 안(outside=0)" s1
step 2 "1-2 0줄" s2
step 3 "1-3 공유 줄 numstat·「-」 줄 원문(bad_minus=0)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "ruff·pyright·check_test_layout" s5
step 6 "순수 시험(inventory·organization·core·config — not django_db and not security)" s6
if [ "$CONTAINERS" = 1 ]; then
  step 7 "makemigrations --check · 업무 층(inventory·core·config) · 보안 층 셋(② 다섯)" s7
else
  not_run 7 "makemigrations --check · 업무 층 · 보안 층" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 2 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 8 ]; then echo "[8] 보안 층 전량 — 경계 1 은 §4-8 밖(② 몫) EXIT=0 0s"; fi
elif [ "$CONTAINERS" = 1 ]; then
  step 8 "보안 층 전량(scripts/test-security.sh)" s8
else
  not_run 8 "보안 층 전량" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 2 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 9 ]; then  # ① 은 경로 0
    if git diff --quiet "$BASE" -- "$A/generated"; then
      echo "[9] generated — 경계 1 은 0바이트 EXIT=0 0s"
    else
      echo "[9] generated — ★ 경계 1 에서 바뀜 EXIT=1 0s"; FAILS=$((FAILS + 1))
    fi
  fi
else
  step 9 "generated 다시 뽑아 커밋본 cmp · <기준> 과 지운 줄 0(patience — 쉼표·Q4 설명 셋 뺌)" s9
fi
if [ "$CONTAINERS" = 1 ]; then
  step 10 "심은 고장(경계 $COMMIT 몫)" s10
else
  not_run 10 "심은 고장" "--with-containers 없음"
fi
step 11 "뿌리 verify.sh --fast(모든 경계 · ② + apps/web typecheck)" s11
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
