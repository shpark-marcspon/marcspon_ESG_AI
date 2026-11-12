#!/usr/bin/env bash
# 밴드 S3K1(MARC-TICK-427: Scope 3 코랩 흐름을 실행기에 잇기 — 끼움·기본 흐름·결과 읽기·양식 내려받기·운영 관리자 실행)의
# §3 자기검증(발주서 band-handoffs/S3K1-order.md §3). 틀은 section4-K1b-2b.sh.
#   사용: apps/api-py/scripts/section4-S3K1.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --with-containers 면 단계 7(makemigrations·업무 층)·8(③ 보안 층 전량)·10(심은 고장)을 돈다.
#   .git/verify.lock 이 있으면 [7]·[8]·[10]·[11] 앞에서 없어질 때까지 기다린다.
#   안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 S3K1.out/s4).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
C="$E/core"
R="$E/runs"
S="$A/tests/security"
OUT="${S4_OUT:-$ROOT/../S3K1.out/s4}"
PURE_PATHS="esgapi/inventory esgapi/greenwash esgapi/runbundle esgapi/runs esgapi/core esgapi/config"
BIZ_PATHS="esgapi/inventory esgapi/greenwash/tests/service/actions/test_bundle_carrier.py esgapi/runbundle esgapi/runs
esgapi/core esgapi/config"
FORBIDDEN="$ROOT/../G1a.out/forbidden-words.txt"
RECEIVED="$ROOT/../../received/2026-10-13"
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
LOCK="$(git rev-parse --git-common-dir)/verify.lock"
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 S3K1 §3 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-1 + 1-5 표 + 그린워싱 T7(80 허락 — ★E). 경계마다 누적.
ALLOWED_1="^README\.md\$
^$I/flows/(binding_157|registration)\.py\$
^$I/(apps|__init__)\.py\$
^$I/README\.md\$
^$I/data/README\.md\$
^$I/data/scope3/scope3-(template-v2\.1|factor-book)\.xlsx\$
^$I/service/utils/scope3_files\.py\$
^$I/tests/flows/test_binding_157\.py\$
^$I/tests/test_flows\.py\$
^$A/scripts/(section4|planted-breaks)-S3K1\.sh\$
^$E/greenwash/tests/service/actions/test_bundle_carrier\.py\$
^$C/tests/flows/test_carriers\.py\$"
ALLOWED_2="^$C/permissions\.py\$
^$C/tests/test_permissions\.py\$
^$I/tests/flows/test_binding_157_end_to_end\.py\$"
ALLOWED_3="^$I/service/(actions|schemas|apis)/scope3_runs\.py\$
^$I/service/apis/inventory\.py\$
^$I/tests/service/apis/test_scope3_runs\.py\$
^$I/tests/test_route_shapes\.py\$
^$C/tests/test_permissions_wiring\.py\$
^$C/tests/test_transaction_rules\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool|test_env)\.py\$
^$E/config/env\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$S/(test_tenant_paths|test_login|test_operator_company)\.py\$"
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

# 1-2 0줄(S3L1 땅 — 엔진·흐름 파일 포함).
ZERO="$I/engines $I/flows/scope3_colab_157.py $I/flows/scope3_llm_first_1.py $I/flows/scope12_engine_1.py
$I/contracts $I/prompts $I/tools $I/migrations $I/data_loader.py
$I/data/factors.kr-ets-sample.json $I/data/gwp-sets.json $I/data/unit-conversions.json $I/data/ghg-pool-seed.json
$C/flows $C/service/services/documents.py $R apps/web
$A/pyproject.toml $A/uv.lock $A/.importlinter $E/config/api.py $E/config/apps_list.py
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

# 1-5 공유 줄: numstat 과 「-」 줄 원문. 셈 파일의 「-」 줄은 숫자·같은 줄 주석만 다른 「+」 줄이 있어야 한다.
COUNTS="$C/tests/test_permissions.py $C/tests/test_permissions_wiring.py
$E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py $E/config/tests/test_request_schemas_reject_bool.py
$S/test_login.py $S/test_tenant_paths.py $S/test_operator_company.py
$E/greenwash/tests/service/actions/test_bundle_carrier.py $C/tests/flows/test_carriers.py
$C/tests/test_transaction_rules.py"
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
# 셈 줄 꼴이 아닌데 허락이 이름으로 허락한 「-」 줄
LISTED = {
    # 그린워싱 T7(80 허락 — ★E): 끼움 있는 모듈 집합에 inventory.scope3 · docstring 셈 다섯·넷 → 여섯·다섯
    '    """T7: 끼움 있는 모듈 다섯(drafting 은 RPA1 까지 carrier 없음)의 넷이 CARRIERS 에. 끼움 없는 모듈은 거절."""',
    '    assert bound == {"dataverify", "drafting", "greenwash", "materiality", "translation"}',
    # core carriers 분모(7a 허락 — 427 노트): carrier 단 모듈 목록에 inventory.scope3 · 주석 「모듈 넷」→「다섯」
    '    # 분모: 모듈 넷의 carrier 는 RX1b 가 단다(각 모듈 AppConfig.ready() — 이 층도 앱을 적재한다). 끼움 없는 모듈 0.',
    '    assert sorted(CARRIERS.modules()) == ["dataverify", "greenwash", "materiality", "translation"]',
    # ② H2 test_permissions.py:493(e7 — 1-5 H2 「집합 +1」): 운영 관리자 모듈 집합에 inventory.scope3 · docstring 한 마디
    '    경로가 이것을 읽는다. 419 — 중대성평가."""',
    '    assert frozenset({"greenwash", "translation", "dataverify", "materiality", "drafting"}) == OPERATOR_RUN_MODULES',
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
            print("    (허락 표의 목록 줄)")
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

s6() {
  local log code n
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
  local code=0 blog="$OUT/s7-business.log"
  up_postgres || return 1
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  wait_lock
  # shellcheck disable=SC2086
  (cd "$A" && $NOKEY scripts/test-business.sh -n 4 -p no:cacheprovider $BIZ_PATHS) > "$blog" 2>&1 || code=1
  echo "  업무($(echo $BIZ_PATHS | wc -w | tr -d ' ') 자리) $(tail -1 "$blog")"
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

# ③: generated/ 를 다시 뽑아 커밋본과 cmp + <기준> 과의 차이 — 지운 줄 0(patience), 더함 = 경로 둘뿐.
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
  removed="$(git diff --patience --numstat "$BASE" -- "$A/generated/openapi.json" "$A/generated/api.d.ts" | awk '{s+=$2} END {print s+0}')"
  echo "  generated 지운 줄(patience, openapi.json·api.d.ts) $removed · source-sha256 은 한 줄 바뀜(해시)"
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
want = sorted(["inventory_scope3_template", "inventory_scope3_result_get"])
sys.exit(0 if ids == want and not lost and not moved and not changed and not rest else 1)
PYEOF
  return $code
}

s10() {
  local log code
  up_postgres || return 1
  wait_lock
  log="$($NOKEY "$A/scripts/planted-breaks-S3K1.sh" --commit "$COMMIT" 2>&1)"
  code=$?  # 「심은 수 ≠ 배치」·못 심음은 종료 코드로만 닿는다
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

# §3-4·§3-6: 두 xlsx(받은 원본 sha → 저장소 sha, 부품마다 대조 — lastModifiedBy·absPath url 두 칸 말고 차이 0) · 새 xlsx 는 둘뿐 ·
#   받은 원본은 바뀌지 않음(sha) · diff 「+」 줄에 금지어·키 꼴 0(낱말은 찍지 않는다)
s12() {
  python3 -I - "$RECEIVED" "$I" "$FORBIDDEN" "$BASE" <<'PYEOF'
import hashlib, re, subprocess, sys, zipfile
from pathlib import Path
received, inv, forbidden, base = Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]), sys.argv[4]
PAIRS = {  # 저장소 이름: (받은 원본 자리, 원본 sha256, 저장소 sha256 — data/README.md 의 표)
    "scope3-template-v2.1.xlsx": ("요청 하신 파일 목록/파일/Scope3_템플릿_수정본_v2.1 (1).xlsx",
        "73c4bded2bd3d68a57350c7f7351f6c8484c7e817289c166cdc2309cef7a59a2",
        "664d1c3b5b14b0adb3dc7db842e13974902ac5b828df77cdd2b534909628bc36"),
    "scope3-factor-book.xlsx": ("Scope 3 상세 기획 첨부/배출계수_Scope3_DB.xlsx",
        "6ab4b0b2c0fd40980ace91a4b79f804b5a6328f538dc8f16d30f546f1c535dec",
        "f658e1a258e7b9292107230434c66e51491e3339d7e81f19133ed83676cec42f"),
}
LMB = re.compile(rb"(<cp:lastModifiedBy>)[^<]*(</cp:lastModifiedBy>)")
ABS = re.compile(rb'(<x15ac:absPath\b[^>]*\burl=")[^"]*(")')
bad = 0
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest()
for name, (src, want_src, want_dst) in PAIRS.items():
    s, d = received / src, inv / "data" / "scope3" / name
    ok_src, ok_dst = sha(s) == want_src, sha(d) == want_dst
    with zipfile.ZipFile(s) as a, zipfile.ZipFile(d) as b:
        same_names = a.namelist() == b.namelist()
        differ = [p for p in a.namelist() if a.read(p) != b.read(p)]
        meta = [p for p in a.namelist() if (a.getinfo(p).compress_type, a.getinfo(p).date_time) != (b.getinfo(p).compress_type, b.getinfo(p).date_time)]
        core = b"docProps/core.xml"
        blank = LMB.sub(rb"\1\2", a.read("docProps/core.xml")) == b.read("docProps/core.xml")
        blank = blank and ABS.subn(rb"\1\2", a.read("xl/workbook.xml")) == (b.read("xl/workbook.xml"), 1)
        empty = b"<cp:lastModifiedBy></cp:lastModifiedBy>" in b.read("docProps/core.xml") and len(ABS.findall(b.read("xl/workbook.xml"))) == 1 and b'url=""' in b.read("xl/workbook.xml")
    ok = ok_src and ok_dst and same_names and sorted(differ) == ["docProps/core.xml", "xl/workbook.xml"] and not meta and blank and empty
    print(f"  {name}: 원본 sha {want_src[:16]} {'=' if ok_src else '★≠'} · 저장소 sha {want_dst[:16]} {'=' if ok_dst else '★≠'}"
          f" · 부품 {len(differ)}개 다름({differ}) · 그 칸 말고 같음 {blank} · 빈 칸 {empty} · 압축·날짜 다름 {meta}")
    bad += not ok
new_xlsx = subprocess.run(["git", "ls-files", "-o", "--exclude-standard", "--full-name", "*.xlsx"], capture_output=True, text=True).stdout.split()
new_xlsx += subprocess.run(["git", "diff", "--name-only", "--diff-filter=A", base, "--", "*.xlsx"], capture_output=True, text=True).stdout.split()
new_xlsx = sorted(set(new_xlsx))
print(f"  새 xlsx {len(new_xlsx)}: {new_xlsx}")
bad += len(new_xlsx) != 2 or not all(p.endswith(tuple(PAIRS)) for p in new_xlsx)
diff = subprocess.run(["git", "diff", base, "--", ".", ":(exclude)*.xlsx"], capture_output=True, text=True).stdout
untracked = subprocess.run(["git", "ls-files", "-o", "--exclude-standard", "--full-name"], capture_output=True, text=True).stdout.split()
added = [l[1:] for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
for p in untracked:
    if not p.endswith(".xlsx"):
        added += Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip(), p).read_text(encoding="utf-8").splitlines()
words = [w.strip() for w in forbidden.read_text(encoding="utf-8").splitlines() if w.strip() and not w.startswith("#")] if forbidden.exists() else []
hits = sum(1 for l in added for w in words if w in l)
keys = sum(1 for l in added if re.search(r"sk-[A-Za-z0-9_-]{20,}|sk-ant-[A-Za-z0-9_-]{20,}|AKIA[0-9A-Z]{16}", l))
print(f"  더한 줄 {len(added)} · 금지어 {len(words)}개 대조 걸림 {hits} · 키 꼴 {keys}" + ("" if words else " · ★ 금지어 목록 없음"))
bad += hits + keys + (not words)
sys.exit(1 if bad else 0)
PYEOF
}

step 1 "바뀐 경로가 1-1·1-5 안(outside=0)" s1
step 2 "1-2 0줄(S3L1 땅·runs·core/flows)" s2
step 3 "1-5 공유 줄 numstat·「-」 줄 원문(bad_minus=0)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "ruff·pyright·check_test_layout" s5
step 6 "순수 시험(inventory·greenwash·runbundle·runs·core·config)" s6
if [ "$CONTAINERS" = 1 ]; then
  step 7 "makemigrations --check · 업무 층(inventory·T7·runbundle·runs·core·config)" s7
else
  not_run 7 "makemigrations --check · 업무 층" "--with-containers 없음"
fi
if [ "$COMMIT" -lt 3 ]; then
  if [ -z "$ONLY" ] || [ "$ONLY" = 8 ]; then echo "[8] 보안 층 전량 — 경계 $COMMIT 은 §3 밖(③ 몫) EXIT=0 0s"; fi
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
step 11 "뿌리 verify.sh --fast(③ + apps/web typecheck)" s11
step 12 "두 xlsx sha·부품 대조 · 새 xlsx 둘뿐 · 금지어·키 꼴 0" s12
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
