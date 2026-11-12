#!/usr/bin/env bash
# 밴드 RP1(MARC-TICK-412: 원고작성 모듈 뼈 esgapi/drafting — 앱·표 넷·계약 셋·엔진 v1·문서 없는 흐름·경로 다섯)의 §4
# 자기검증(발주서 band-handoffs/RP1-order.md §4). 틀은 section4-IR4.sh.
#   사용: apps/api-py/scripts/section4-RP1.sh --commit <1|2|3> [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 9(업무 · ③ 보안)를 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — ③ 끝 전량은 따로). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 RP1.out — 검증자는 RP1.verify), RP1_FORBIDDEN(실재 기업명 낱말 파일,
#   기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만), MARCSPON_ROOT(PRD 읽기판을 찾는 뿌리,
#   기본 = 이 스크립트 자리 ../../../../.. — 파일이 없으면 단계 6 EXIT≠0, 글은 찍지 않는다).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
P="$E/drafting"
OUT="${S4_OUT:-$ROOT/../RP1.out}"
FORBIDDEN="${RP1_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
MROOT="${MARCSPON_ROOT:-$HERE/../../../../..}"
PRD="$MROOT/received-derived/2026-10-29/PRD_AI보고서작성_v2.md"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit <1|2|3> [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 RP1 §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# 1: 순수 층(drafting — not django_db). N0 = <기준> 의 수(drafting 이 없으면 0) → N1.
s1() {
  local log n code n0
  n0="$(git ls-tree -r --name-only "$BASE" -- "$P" | grep -c '/test_.*\.py$')"
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q esgapi/drafting -m "not django_db" \
    -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s1-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  N0(기준의 drafting 시험 파일) $n0 → N1 ${n:-?} 통과 · $(echo "$log" | tail -1)"
  [ "$code" = 0 ] && [ "${n:-0}" -gt 0 ]
}

# 2: lint-imports — 계약 수 = 기준, drafting 줄 수 = 1-3 의 그 경계까지(① 9 · ② 12 · ③ 12).
s2() {
  local log kept broken lines want
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  echo "$log" | tail -2 | sed 's/^/  /'
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  lines="$(git diff -U0 "$BASE" -- "$A/.importlinter" | grep -c '^+ *esgapi\.drafting')"
  want=9; [ "$COMMIT" -ge 2 ] && want=12
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?} · drafting 더한 줄 $lines (경계 몫 $want)"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ] && [ "$lines" = "$want" ]
}

s3() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s4() {
  local code=0
  (cd "$A" && uv run --frozen pyright esgapi/drafting 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff check esgapi/drafting 2>&1 | tail -1 | sed 's/^/  ruff check /'
    exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check esgapi/drafting 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") \
    || code=1
  return $code
}

# 5: 경로(1-2·1-3 의 그 경계까지) · bad_minus · 공유 numstat·sha16 · 복사 몸 == 원본(② 부터)
ALLOWED_1="^$P/(__init__|apps|models)\.py\$
^$P/migrations/(__init__|0001_initial)\.py\$
^$P/contracts/(__init__|shapes|options_shapes|wire)\.py\$
^$P/service/__init__\.py\$
^$P/service/(selectors|services)/(__init__|projects)\.py\$
^$P/tests/.*
^$A/scripts/(section4|planted-breaks)-RP1\.sh\$
^$A/\.importlinter\$
^$E/config/apps_list\.py\$
^$E/config/tests/test_settings\.py\$
^$E/core/tests/isolation/(test_managers|test_static_rules)\.py\$
^$E/core/tests/(test_selector_scope|test_transaction_rules)\.py\$
^$A/tests/security/(test_owner|test_migrations|test_same_company_foreign_keys|test_request_transactions)\.py\$"
ALLOWED_2="^$P/engines/(__init__|v1/(__init__|pages|mapping|bullets|checks|texts|prompts))\.py\$
^$P/tools/(__init__|pdftext_pypdf)\.py\$
^$P/flows/(__init__|draft_v1|binding_v1|registration)\.py\$
^$P/prompts/(map|draft)/1\.md\$
^$P/prompts/README\.md\$
^$P/service/actions/(__init__|run_sources)\.py\$
^$E/config/env\.py\$
^$E/config/tests/test_env\.py\$
^compose\.yaml\$"
ALLOWED_3="^$P/api\.py\$
^$P/service/apis/(__init__|drafting)\.py\$
^$P/service/actions/(projects|result)\.py\$
^$P/contracts/api_shapes\.py\$
^$E/core/permissions\.py\$
^$E/runs/service/apis/runs\.py\$
^$E/core/tests/(test_permissions|test_permissions_wiring)\.py\$
^$E/config/api\.py\$
^$E/config/tests/(test_api_contract|test_api_errors|test_request_schemas_reject_bool)\.py\$
^$A/tests/security/(test_drafting|test_tenant_paths|test_login|test_operator_company)\.py\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^README\.md\$
^docs/development\.md\$
^$E/user/service/utils/run_log_xlsx\.py\$
^$E/greenwash/tests/service/actions/test_bundle_carrier\.py\$"  # 그린워싱 80 허락(MARC-TICK-74 노트)
ALLOWED="$ALLOWED_1"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"
[ "$COMMIT" -ge 3 ] && ALLOWED="$ALLOWED
$ALLOWED_3"
# 공유 줄(1-3) — drafting 밖의 바뀐 파일 전부
SHARED="$A/.importlinter $E/config/apps_list.py $E/config/tests/test_settings.py
$E/core/tests/isolation/test_managers.py $E/core/tests/isolation/test_static_rules.py
$E/core/tests/test_selector_scope.py $E/core/tests/test_transaction_rules.py
$A/tests/security/test_owner.py $A/tests/security/test_migrations.py $A/tests/security/test_same_company_foreign_keys.py
$A/tests/security/test_request_transactions.py
$E/config/env.py $E/config/tests/test_env.py compose.yaml
$E/core/permissions.py $E/runs/service/apis/runs.py $E/core/tests/test_permissions.py $E/core/tests/test_permissions_wiring.py
$E/config/api.py $E/config/tests/test_api_contract.py $E/config/tests/test_api_errors.py
$E/config/tests/test_request_schemas_reject_bool.py $A/tests/security/test_tenant_paths.py $A/tests/security/test_login.py
$A/tests/security/test_operator_company.py README.md docs/development.md $E/user/service/utils/run_log_xlsx.py
$E/greenwash/tests/service/actions/test_bundle_carrier.py"
# 「바꿈」 표시 줄(1-3 — 원문이 바뀌는 줄. ③ 만): 그 「-」 줄의 고정 글자 조각
REPLACED_3="회사 업무 40
OPERATOR_RUN_MODULES
보고서 작성 | 코드 없음
중대성평가 모듈만).
끼움 있는 모듈 넷(F12)
assert bound == {\"dataverify\", \"greenwash\"
assert set(CARRIERS.modules()) == bound"  # 끝 줄: runs_create docstring 의 모듈 이름 줄(커밋 25e917ba Directive)
COPY_SRC="$E/greenwash/tools/pdftext_pypdf.py"
COPY_DST="$P/tools/pdftext_pypdf.py"

s5() {
  local all outside pattern code=0
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ] || code=1
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED | sed 's/^/  numstat /'
  # shellcheck disable=SC2086
  echo "  공유 sha16 $(git diff "$BASE" HEAD -- $SHARED | shasum -a 256 | cut -c1-16) (BASE..HEAD) · 작업 트리 $(git diff "$BASE" -- $SHARED | shasum -a 256 | cut -c1-16)"
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED > "$OUT/s5-shared.diff"
  local replaced=""; [ "$COMMIT" -ge 3 ] && replaced="$REPLACED_3"
  python3 -I - "$OUT/s5-shared.diff" "$replaced" <<'PYEOF' || code=1
import re, sys
replaced = [r for r in sys.argv[2].split("\n") if r]
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
        if norm(m) in pool:
            pool.remove(norm(m))
        elif any(r in m for r in replaced):
            print("    (「바꿈」 표시 줄 — 1-3)")
        else:
            print("    ★ 셈·같은 줄 주석·「바꿈」 밖이 바뀐 「-」 줄")
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
print(f"  bad_minus={bad}")
sys.exit(1 if bad else 0)
PYEOF
  if [ "$COMMIT" -ge 2 ]; then
    python3 -I - "$COPY_SRC" "$COPY_DST" <<'PYEOF' || code=1
import sys
def body(path):
    text = open(path, encoding="utf-8").read()
    # 머리말(첫 docstring)을 뺀 몸
    end = text.index('"""', 3) + 3
    return text[end:]
same = body(sys.argv[1]) == body(sys.argv[2])
print(f"  복사 몸 == 원본({sys.argv[1].split('esgapi/')[1]}): {same}")
sys.exit(0 if same else 1)
PYEOF
  fi
  return $code
}

# 6: 금지 글 — 더한 줄(추적 diff + 새 파일)·메시지·보고. PRD 읽기판과 더한 줄 겹침(공백 정규화 20자+) 0.
s6() {
  local d="$OUT/s6.diff" n_key n_bin n_name=0 code=0 report="$MROOT/band-reports/RP1.md"
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } \
    > "$d" 2>/dev/null
  [ -n "$MSG" ] && [ -f "$MSG" ] && sed 's/^/+/' "$MSG" >> "$d"
  [ -f "$report" ] && sed 's/^/+/' "$report" >> "$d"
  n_key="$(grep -E '^\+' "$d" | grep -v -F 'sk-[A-Za-z0-9' | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  n_bin="$(changed | grep -c -E '\.(pdf|xlsx|docx|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .pdf/.xlsx/.docx/.ipynb $n_bin · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ] || code=1
  if [ ! -f "$PRD" ]; then
    echo "  ★ PRD 읽기판이 없다(MARCSPON_ROOT 를 본다)"; return 1
  fi
  python3 -I - "$PRD" "$d" <<'PYEOF' || code=1
import re, sys
W = 20
def squash(text):
    return re.sub(r"\s+", " ", text).strip()
prd = squash(open(sys.argv[1], encoding="utf-8").read())
grams = {prd[i:i + W] for i in range(len(prd) - W + 1)}
hits = 0
for raw in open(sys.argv[2], encoding="utf-8", errors="replace"):
    if not raw.startswith("+") or raw.startswith("+++"):
        continue
    line = squash(raw[1:])
    if any(line[i:i + W] in grams for i in range(len(line) - W + 1)):
        hits += 1
print(f"  PRD 읽기판 겹침(공백 정규화 {W}자+) 줄 {hits}")
sys.exit(1 if hits else 0)
PYEOF
  return $code
}

s7() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

# 8(③): generated/ 셋을 다시 뽑아 cmp + <기준> 과의 차이가 /drafting 경로 다섯과 Drafting* 뿐(기존 값 0)
s8() {
  local g="$OUT/s8-generated" code=0 f
  if [ "$COMMIT" -lt 3 ]; then
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 $COMMIT 에서 generated/ 가 바뀜"; return 1; }
    echo "  generated/ 0바이트(경계 $COMMIT)"; return 0
  fi
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  git show "$BASE:$A/generated/openapi.json" > "$g/openapi.base.json"
  python3 -I - "$g/openapi.base.json" "$A/generated/openapi.json" <<'PYEOF' || code=1
import json, sys
a, b = (json.load(open(p)) for p in sys.argv[1:3])
added = sorted(set(b["paths"]) - set(a["paths"]))
lost = sorted(set(a["paths"]) - set(b["paths"]))
moved = [p for p in a["paths"] if p in b["paths"] and a["paths"][p] != b["paths"][p]]
# 허용: /runs POST 의 description 한 칸(1-3 runs_create docstring 모듈 이름 — 커밋 25e917ba Directive). 그 밖 칸 0
runs_a, runs_b = a["paths"].get("/runs", {}), b["paths"].get("/runs", {})
runs_moved = sorted(f"{m}.{k}" for m in set(runs_a) | set(runs_b) for k in set(runs_a.get(m, {})) | set(runs_b.get(m, {}))
                    if runs_a.get(m, {}).get(k) != runs_b.get(m, {}).get(k))
if runs_moved == ["post.description"]:
    moved.remove("/runs")
    print("  /runs 바뀜 = post.description 한 칸(허용 — runs_create docstring 「원고작성」)")
sa, sb = a["components"]["schemas"], b["components"]["schemas"]
new = sorted(set(sb) - set(sa))
changed = [k for k in sa if k not in sb or sa[k] != sb[k]]
rest = [k for k in set(a) | set(b) if k not in ("paths", "components") and a.get(k) != b.get(k)]
rest += [k for k in set(a["components"]) | set(b["components"]) if k != "schemas" and a["components"].get(k) != b["components"].get(k)]
ids = sorted(op.get("operationId") for p in added for op in b["paths"][p].values())
print(f"  path 더함 {added} {ids} · 지움 {lost} · 바뀜 {moved}")
print(f"  schema 더함 {len(new)}({', '.join(new)}) · 바뀜·지움 {changed} · 그 밖 {rest}")
ok = all(p.startswith("/drafting/") for p in added)
ok = ok and ids == sorted(["drafting_projects_create", "drafting_project_get", "drafting_project_document_put",
                           "drafting_outline_put", "drafting_result_get"])
ok = ok and not lost and not moved and not changed and not rest
ok = ok and all(k.startswith("Drafting") for k in new)
sys.exit(0 if ok else 1)
PYEOF
  return $code
}

s9() {
  local blog="$OUT/s9-business.log" slog="$OUT/s9-security.log" bcode scode=0
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres storage > "$OUT/s9-up.log" 2>&1 || { tail -3 "$OUT/s9-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db \
    esgapi/drafting esgapi/core esgapi/config esgapi/runs) > "$blog" 2>&1
  bcode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode"
  if [ "$COMMIT" -ge 3 ]; then
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
    scode=$?
    echo "  보안 $(tail -1 "$slog") EXIT=$scode"
  else
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider \
      tests/security/test_owner.py tests/security/test_migrations.py tests/security/test_same_company_foreign_keys.py) \
      > "$slog" 2>&1
    scode=$?
    echo "  보안(이 경계가 건드린 셋) $(tail -1 "$slog") EXIT=$scode"
  fi
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s10() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-RP1.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-412" "Derives-from: MARC-ENT-501" "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; do
    grep -q -x -F "$t" "$MSG" || { echo "  ★ 트레일러 없음: $t"; code=1; }
  done
  head -1 "$MSG" | grep -q -E '^feat\(drafting\): RP1 (①|②|③) ' || { echo "  ★ 제목 꼴"; code=1; }
  echo "  제목 $(head -1 "$MSG") · 트레일러 $(grep -c -E '^[A-Z][A-Za-z-]+: ' "$MSG") 줄"
  return $code
}

s12() {
  local log code start
  start=$(date +%s)
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  code=$?
  echo "$log" > "$OUT/s12-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  [ $(( $(date +%s) - start )) -gt 30 ] && echo "  30초 넘음 · $(uptime | sed 's/.*load/load/')"
  [ "$code" = 0 ] && echo "$log" | grep -q "VERIFY_FAST=PASS"
}

step 1 "순수 시험(drafting — not django_db) N0 → N1" s1
step 2 "lint-imports 전부 KEPT·수 = 기준 · drafting 줄 = 1-3" s2
step 3 "check_test_layout" s3
step 4 "pyright esgapi/drafting 0 · ruff check · ruff format --check" s4
step 5 "경로 1-2·1-3 안 · bad_minus=0 · 공유 numstat·sha16 · 복사 몸(②③)" s5
step 6 "금지 글·키 꼴·바이너리 0 · PRD 읽기판 겹침 0" s6
step 7 "makemigrations --check --dry-run" s7
step 8 "generated/(③ 다시 뽑아 cmp·허용 차이)" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무(drafting·core·config·runs) · 보안" s9
else
  not_run 9 "업무·보안(컨테이너)" "--with-containers 없음"
fi
if [ "$PLANTED" = 1 ]; then step 10 "심은 파손(경계 $COMMIT 몫)" s10; fi
if [ -n "$MSG" ]; then step 11 "커밋 메시지 트레일러(§5)" s11; fi
step 12 "뿌리 verify.sh --fast" s12
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
