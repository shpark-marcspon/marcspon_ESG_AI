#!/usr/bin/env bash
# 밴드 K1b-3(MARC-TICK-425: 사업장 상세 PUT 이 낡은 판을 409 stale 로 거절 — lost update 0)의 §4 자기검증 서버 몫
# (발주서 band-handoffs/K1b-3-order.md §4). 틀은 section4-S12a.sh. ③(웹)은 발주서 §4 의 웹 명령이 따로 잰다 —
# --commit 3 은 [1]·[2] 에 1-1 의 웹 줄을 들이고(1-2 의 웹 0줄 자리는 그대로 지킴) 나머지는 ② 와 같다(서버 다시 잼).
#   사용: apps/api-py/scripts/section4-K1b-3.sh --commit <1|2|3> [--with-containers] [--step <n>]
#   --with-containers 면 단계 7(makemigrations·DB 시험·보안 층 전량)·9(심은 고장)를 돈다. 안 주면 「안 돌림」(EXIT=1 로 센다).
#   .git/verify.lock 이 있으면 [7]·[9]·[10] 앞에서 없어질 때까지 기다린다(자기 postgres 만 쓰는 단계도).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 K1b-3.out/s4).
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
OUT="${S4_OUT:-$ROOT/../K1b-3.out/s4}"
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
    *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac
LOCK="$(git rev-parse --git-common-dir)/verify.lock"
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 K1b-3 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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
  echo "  lock 없음 확인 $(date '+%m-%d %H:%M:%S')$([ "$waited" = 0 ] || echo " (${waited}s 기다림)")"
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-1 서버 몫 + 1-6 허락 표(H1~H12 · X1 · inventory 도우미 둘). ② 는 같은 표(새 경합 시험은 이미 든다).
ALLOWED="^$O/service/(schemas|selectors|services|actions|apis)/branches\.py\$
^$O/service/utils/entities\.py\$
^$O/tests/service/(apis|actions|services)/test_branches\.py\$
^$O/tests/service/actions/test_branches_(stale|save_race)\.py\$
^$I/tests/service/actions/test_entries(_race)?\.py\$
^$C/tests/test_permissions_wiring\.py\$
^$E/config/tests/test_api_times\.py\$
^$S/(test_tenant_paths|test_branches|test_entries)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/scripts/(section4|planted-breaks)-K1b-3\.sh\$"
# ③ 웹(발주서 1-1 웹 줄 · §4 ③ paths 명령과 같은 목록).
W=apps/web
[ "$COMMIT" = 3 ] && ALLOWED="$ALLOWED
^$W/src/entities/ghg/api/(contract/index|server|server\.test|testing)\.ts\$
^$W/src/entities/ghg/model/(branch|index|model\.test)\.ts\$
^$W/src/entities/ghg/config/text\.ts\$
^$W/src/pages/ghg-branch/ui/BranchScreen(\.test)?\.tsx\$
^$W/e2e/ghg-server(\.spec)?\.ts\$
^$W/scripts/planted-breaks-K1b-3\.sh\$"

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

# 1-2 0줄: 자리 목록 + 「제품 코드 전부」 둘(inventory·core 는 tests 밖 전부). H14 두 파일도 0줄.
ZERO="$O/models.py $O/migrations $O/service/schemas/organization.py $O/service/selectors/organization.py
$O/service/services/organization.py $O/service/apis/organization.py $O/service/permissions/organization.py
$O/service/services/facility_codes.py $O/service/selectors/facility_codes.py
$C/tests/isolation $E/user $E/runs apps/web packages
$A/pyproject.toml $A/uv.lock $A/.importlinter $E/config/api.py $E/config/apps_list.py
$A/conftest.py $A/tests/support $S/conftest.py $S/seed.py
$E/config/tests/test_request_schemas_reject_bool.py $E/config/tests/test_api_contract.py"
# ③ 은 apps/web 통째 대신 1-2 의 웹 0줄 자리(shared·widgets·app·다른 ghg 화면·ghg 의 pool·selection·entries·hooks·package 둘).
[ "$COMMIT" = 3 ] && ZERO="$(echo "$ZERO" | sed 's#apps/web packages#packages#')
$W/src/shared $W/src/widgets $W/src/app $W/package.json pnpm-lock.yaml
$W/src/pages/ghg-organization $W/src/pages/ghg-inventory $W/src/pages/ghg-index-settings $W/src/pages/ghg-index-pool
$W/src/pages/ghg-facility-codes $W/src/pages/ghg-branch/ui/ConfirmDialog.tsx $W/src/pages/ghg-branch/ui/FacilityDialog.tsx
$W/src/entities/ghg/hooks $W/src/entities/ghg/api/pool.ts $W/src/entities/ghg/api/selection.ts $W/src/entities/ghg/api/entries.ts
$W/src/entities/ghg/api/index.ts $W/src/entities/ghg/model/pool.ts $W/src/entities/ghg/model/selection.ts
$W/src/entities/ghg/model/entries.ts $W/src/entities/ghg/model/facilityCode.ts $W/src/entities/ghg/model/ids.ts"
s2() {
  local missing=0 p n bad product
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u | grep .)"
  product="$( { git diff --name-only "$BASE" -- "$I" "$C"; git ls-files -o --exclude-standard --full-name -- "$I" "$C"; } \
    | sort -u | grep -v -E "^($I|$C)/tests/" | grep .)"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .)"
  echo "  inventory·core 제품 코드(tests 밖) 바뀐 것 $(echo "$product" | grep -c .)"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -n "$product" ] && echo "$product" | sed 's/^/  ★ 제품 /'
  [ -z "$bad" ] && [ -z "$product" ] && [ "$missing" -eq 0 ]
}

# 1-6 공유 줄(H7~H11): numstat 과 「-」 줄 원문. 「-」 는 숫자·같은 줄 주석만 다른 「+」 짝이 있거나, 1-6 표가 이름으로
# 허락한 줄(본문에 updatedAt 을 더하느라 고친 줄 — 지우는 단언 0)이어야 한다.
COUNTS="$C/tests/test_permissions_wiring.py $E/config/tests/test_api_times.py
$S/test_tenant_paths.py $S/test_branches.py $S/test_entries.py"
s3() {
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $COUNTS | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $COUNTS > "$OUT/s3.diff"
  python3 -I - "$OUT/s3.diff" <<'PYEOF'
import re, sys
LISTED = {
    # H7 test_permissions_wiring :223 — 본문 +updatedAt
    '        {"name": "새 사업장", "inventoryEnabled": True, "facilities": []},',
    # H9 test_tenant_paths :763 — 본문 +updatedAt(줄 나눔)
    '    "organization_branches_save": ("", {"name": "A 의 새 지점", "inventoryEnabled": True, "facilities": []}),',
    # H10 test_branches :122·:124·:129·:142·:143·:217 — save() 에 판 · 내 사업장은 진짜 판 · :217 은 companyId 하나만 422 까닭
    '    def save(row: int) -> dict[str, Any]:',
    '        return {"name": "새 이름", "inventoryEnabled": True, "facilities": rows}',
    '        ("PUT", f"/branches/{mine}", save(their_row)),  # 내 사업장에 남의 자산/시설 id',
    '    assert send(customer, "GET", f"/branches/{mine}").status_code == 200',
    '    assert send(customer, "PUT", f"/branches/{mine}", save(my_row)).status_code == 200',
    '        ("PUT", f"/branches/{mine}", {"name": "나 공장", "inventoryEnabled": True, "facilities": [], "companyId": b}),',
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
            print("    (1-6 허락 표의 줄)")
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
print(f"  공유 파일 「-」 줄 중 허용 밖 {bad} — bad_minus={bad}")
sys.exit(1 if bad else 0)
PYEOF
}

s4() {
  local log kept broken
  log="$(cd "$A" && $NOKEY uv run --frozen lint-imports 2>&1)"
  echo "$log" | tail -1 | sed 's/^/  /'
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
  bash -n "$A/scripts/section4-K1b-3.sh" && bash -n "$A/scripts/planted-breaks-K1b-3.sh" || code=1
  echo "  bash -n 스크립트 둘(shellcheck 은 이 기계에 없다)"
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
  local code=0 blog="$OUT/s7-business.log" slog="$OUT/s7-security.log"
  wait_lock
  up_postgres || return 1
  (cd "$A" && . scripts/db-env.sh && $NOKEY DATABASE_URL_PY="$OWNER_DATABASE_URL" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && $NOKEY scripts/test-business.sh -p no:cacheprovider -rs esgapi/inventory esgapi/organization esgapi/core esgapi/config) \
    > "$blog" 2>&1 || code=1
  echo "  업무(inventory·organization·core·config) $(tail -1 "$blog") · skip 줄 $(grep -c '^SKIPPED' "$blog")"
  wait_lock
  (cd "$A" && $NOKEY scripts/test-security.sh -p no:cacheprovider -rs) > "$slog" 2>&1 || code=1
  echo "  보안 층 전량 $(tail -1 "$slog") · skip 줄 $(grep -c '^SKIPPED' "$slog")"
  return $code
}

# generated/ 를 다시 뽑아 커밋본과 cmp + <기준> 과의 차이: api.d.ts 지운 줄 0, openapi.json 지운 줄은 required 배열 끝
#   이름(쉼표가 붙어 「+」 로 다시 섬)뿐(e7 조건), 더함 = BranchDetailOut·BranchSaveIn 의 updatedAt 둘뿐.
s8() {
  local g="$OUT/s8-generated" code=0 f removed
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && $NOKEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  removed="$(git diff --patience --numstat "$BASE" -- "$A/generated/api.d.ts" | awk '{s+=$2} END {print s+0}')"
  echo "  api.d.ts 지운 줄(patience) $removed · source-sha256 은 한 줄 바뀜(해시)"
  [ "$removed" = 0 ] || code=1
  git diff --patience -U0 "$BASE" -- "$A/generated/openapi.json" > "$g/openapi.diff"
  python3 -I - "$g/openapi.diff" <<'PYEOF' || code=1
import re, sys
minus, plus = [], []
for raw in open(sys.argv[1], encoding="utf-8"):
    if raw.startswith("-") and not raw.startswith("---"):
        minus.append(raw[1:].rstrip("\n"))
    elif raw.startswith("+") and not raw.startswith("+++"):
        plus.append(raw[1:].rstrip("\n"))
bad = [m for m in minus if not (re.fullmatch(r' *"[A-Za-z]+"', m) and m + "," in plus)]
for m in minus:
    print(f"  openapi.json - {m.strip()}{'  ★ required 끝 쉼표 밖' if m in bad else ''}")
print(f"  openapi.json 지운 줄 {len(minus)} · required 끝 쉼표 밖 {len(bad)}")
sys.exit(1 if bad else 0)
PYEOF
  git show "$BASE:$A/generated/openapi.json" > "$g/openapi.base.json"
  python3 -I - "$g/openapi.base.json" "$g/openapi.json" <<'PYEOF' || code=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
paths_same = a["paths"] == b["paths"]
new = sorted(set(sb) - set(sa))
changed = sorted(k for k in sa if k not in sb or sa[k] != sb[k])
added = sorted(f"{k}.{p}" for k in changed if k in sb for p in set(sb[k].get("properties", {})) - set(sa[k].get("properties", {})))
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
print(f"  paths 같음 {paths_same} · schema 새 {new} · 바뀜 {changed} · 더한 칸 {added} · 그 밖 {rest}")
want = ["BranchDetailOut.updatedAt", "BranchSaveIn.updatedAt"]
sys.exit(0 if paths_same and not new and changed == ["BranchDetailOut", "BranchSaveIn"] and added == want and not rest else 1)
PYEOF
  return $code
}

s9() {
  local log code
  up_postgres || return 1
  wait_lock
  log="$($NOKEY "$A/scripts/planted-breaks-K1b-3.sh" --commit "$([ "$COMMIT" = 3 ] && echo 2 || echo "$COMMIT")" 2>&1)"  # ③ 은 서버 ② 몫 그대로
  code=$?  # 「심은 수 ≠ 배치」·못 심음은 종료 코드로만 닿는다
  echo "$log" > "$OUT/s9-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "  planted-breaks 종료 코드 $code"
  [ "$code" = 0 ] && echo "$log" | grep -q "^FINGERPRINT=same" \
    && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s10() {
  local log code=0
  wait_lock
  log="$($NOKEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s10-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS" || code=1
  (cd apps/web && pnpm -s typecheck > "$OUT/s10-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
  echo "  apps/web typecheck(읽기만 — generated 가 웹 타입을 깨지 않음) EXIT=$code $(tail -1 "$OUT/s10-web-typecheck.log")"
  return $code
}

step 1 "바뀐 경로가 1-1·1-6 안(outside=0)" s1
step 2 "1-2 0줄" s2
step 3 "1-6 공유 줄 numstat·「-」 줄 원문(bad_minus=0)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "ruff·pyright·check_test_layout·bash -n" s5
step 6 "순수 시험(inventory·organization·core·config — not django_db and not security)" s6
if [ "$CONTAINERS" = 1 ]; then
  step 7 "makemigrations --check · 업무 층(inventory·organization·core·config) · 보안 층 전량" s7
else
  not_run 7 "makemigrations --check · 업무 층 · 보안 층 전량" "--with-containers 없음"
fi
step 8 "generated 다시 뽑아 커밋본 cmp · 지운 줄은 required 끝 쉼표만 · 더한 칸 둘" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "심은 고장(서버 — 경계 $COMMIT 몫, ③ 은 ② 와 같음)" s9
else
  not_run 9 "심은 고장" "--with-containers 없음"
fi
step 10 "뿌리 verify.sh --fast + apps/web typecheck" s10
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
