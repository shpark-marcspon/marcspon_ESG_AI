#!/usr/bin/env bash
# 밴드 RP2a(MARC-TICK-418: core 문서 산출물 core.doc-artifact@1 + 원고작성 extract 소비·474·pdftext_pypdf 걷음)의 §4
# 자기검증(발주서 band-handoffs/RP2a-order.md §4). 틀은 section4-RP1.sh.
#   사용: apps/api-py/scripts/section4-RP2a.sh --boundary <1|2> [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 9(업무·보안)를 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 경계 끝 전량은 따로). AI 공급사 호출 0(env -u 키). 파서 HTTP 0.
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 RP2a.out — 검증자는 RP2a.verify), RP2A_FORBIDDEN(실재 기업명 낱말 파일,
#   기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만), MARCSPON_ROOT(보고 파일을 찾는 뿌리).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
C="$E/core"
D="$C/documents"
P="$E/drafting"
OUT="${S4_OUT:-$ROOT/../RP2a.out}"
FORBIDDEN="${RP2A_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
MROOT="${MARCSPON_ROOT:-$HERE/../../../../..}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --boundary) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --boundary <1|2> [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--boundary <1|2> 가 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 RP2a §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# 1: 순수 층(① core/tests/documents · ② drafting — not django_db). N0 = <기준> 의 시험 파일 수 → N1.
s1() {
  local log n code n0 target="esgapi/core/tests/documents"
  [ "$COMMIT" = 2 ] && target="esgapi/core/tests/documents esgapi/drafting"
  # shellcheck disable=SC2086
  n0="$(git ls-tree -r --name-only "$BASE" -- $(echo "$target" | sed "s#esgapi#$E#g") | grep -c '/test_.*\.py$')"
  # shellcheck disable=SC2086
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q $target -m "not django_db" \
    -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s1-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  N0(기준의 시험 파일 — $target) $n0 → N1 ${n:-?} 통과 · $(echo "$log" | tail -1)"
  [ "$code" = 0 ] && [ "${n:-0}" -gt 0 ]
}

# 2: lint-imports — 계약 수 = 기준, .importlinter 0줄.
s2() {
  local log kept broken lines
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  echo "$log" | tail -2 | sed 's/^/  /'
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  lines="$(git diff "$BASE" -- "$A/.importlinter" | grep -c '^[-+][^-+]')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?} · .importlinter 바뀐 줄 $lines"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ] && [ "$lines" = 0 ]
}

s3() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s4() {
  local code=0 dirs="esgapi/core/documents esgapi/core/tests/documents esgapi/core/tests/artifact_fakes.py"
  [ "$COMMIT" = 2 ] && dirs="$dirs esgapi/drafting"
  # shellcheck disable=SC2086
  (cd "$A" && uv run --frozen pyright $dirs 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff check . 2>&1 | tail -1 | sed 's/^/  ruff check /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check . 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") \
    || code=1
  return $code
}

# 5: 경로(1-2·C-7·1-3 의 그 경계까지) · bad_minus · 0줄 목록 · services/parser(README 한 줄 밖 0) · 공유 numstat · e7 sha16
ALLOWED_1="^$C/models\.py\$
^$C/migrations/0003_document_artifacts\.py\$
^$D/(__init__|contract|selectors|services|structure|view)\.py\$
^$C/tests/documents/.*
^$C/tests/artifact_fakes\.py\$
^$C/tests/isolation/(test_managers|test_static_rules)\.py\$
^$C/tests/(test_selector_scope|test_transaction_rules)\.py\$
^$A/tests/security/(test_owner|test_migrations|test_same_company_foreign_keys)\.py\$
^services/parser/README\.md\$
^README\.md\$
^docs/development\.md\$
^$A/scripts/(section4|planted-breaks)-RP2a\.sh\$"
ALLOWED_2="^$P/tools/(blocks_text|pdftext_pypdf)\.py\$
^$P/apps\.py\$
^$P/flows/(draft_v1|binding_v1)\.py\$
^$P/engines/v1/pages\.py\$
^$P/service/actions/run_sources\.py\$
^$P/tests/.*"
# RP2d 땅(1-2 의 0줄) — ② 의 시험 허용(P/tests/**) 안에서도 막는다
ZERO="^services/parser/(docparse|schemas)/
^$E/(config|runs)/
^$C/permissions\.py\$
^$C/resources/
^$C/service/
^$P/service/selectors/projects\.py\$
^$P/service/apis/
^$P/api\.py\$
^$P/contracts/
^$P/service/schemas/
^$P/service/actions/(projects|result|download)\.py\$
^$P/outputs/
^$P/tests/service/(actions|selectors)/
^$P/tests/outputs/
^$P/tests/service/apis/conftest\.py\$
^$P/engines/v1/(texts|prompts)\.py\$
^$P/prompts/
^$A/generated/
^apps/web/
^$A/(pyproject\.toml|uv\.lock)\$
^$A/\.importlinter\$
^compose\.yaml\$"
ALLOWED="$ALLOWED_1"
[ "$COMMIT" = 2 ] && ALLOWED="$ALLOWED
$ALLOWED_2"
SHARED="$C/models.py $C/tests/isolation/test_managers.py $C/tests/isolation/test_static_rules.py
$C/tests/test_selector_scope.py $C/tests/test_transaction_rules.py
$A/tests/security/test_owner.py $A/tests/security/test_migrations.py $A/tests/security/test_same_company_foreign_keys.py
services/parser/README.md README.md docs/development.md
$E/greenwash/tests/service/actions/test_bundle_carrier.py"
# 「바꿈」 표시 줄: 앞 둘은 감독 2e·e7 허락(10-29, 418 노트), 끝 하나는 발주서 C-7 「TWO_TABLE_FUNCTIONS 에 하나 더함」
#   (frozenset 한 줄을 펼쳐 넣음 — 원래 원소 그대로)
REPLACED="FROM unnest(%s::text[]) AS t ORDER BY t\",
assert facts(scratch_db, core_records) == [(\"0001_initial\",), (\"0002_llm_call_log_step\",)]
TWO_TABLE_FUNCTIONS = frozenset({(\"core/service/services/documents.py\", \"confirm_upload\")})"

s5() {
  local all outside pattern zero code=0 parser
  all="$(changed)"
  pattern="$(echo "$ALLOWED" | paste -sd'|' -)"
  outside="$(echo "$all" | grep -v -E -e "$pattern" | grep -c .)"
  [ "$outside" -eq 0 ] || echo "$all" | grep -v -E -e "$pattern" | sed 's/^/  ★ 밖: /'
  zero="$(echo "$all" | grep -E -e "$(echo "$ZERO" | paste -sd'|' -)" | grep -c .)"
  [ "$zero" -eq 0 ] || echo "$all" | grep -E -e "$(echo "$ZERO" | paste -sd'|' -)" | sed 's/^/  ★ 0줄 목록: /'
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside · 0줄 목록 $zero"
  [ "$outside" -eq 0 ] && [ "$zero" -eq 0 ] || code=1
  parser="$(git diff --numstat "$BASE" -- services/parser | tr '\t' ' ')"
  echo "  services/parser numstat: ${parser:-없음} (허락: README.md 1 0 하나 — e7 덧붙임)"
  [ -z "$parser" ] || [ "$parser" = "1 0 services/parser/README.md" ] || code=1
  # shellcheck disable=SC2086
  git diff --numstat "$BASE" -- $SHARED | sed 's/^/  numstat /'
  echo "  e7 sha16 $(git diff "$BASE" HEAD -- $A/esgapi/core $A/esgapi/config $A/generated $A/tests/security $A/esgapi/runs \
    | shasum -a 256 | cut -c1-16) (BASE..HEAD — 커밋 뒤 값이 e7 에 가는 값)"
  # shellcheck disable=SC2086
  git diff -U0 "$BASE" -- $SHARED > "$OUT/s5-shared.diff"
  python3 -I - "$OUT/s5-shared.diff" "$REPLACED" <<'PYEOF' || code=1
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
            print("    (「바꿈」 표시 줄 — e7 허락)")
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
  if [ "$COMMIT" = 2 ]; then
    local fixed
    fixed="$(git diff --name-only "$BASE" -- "$P/tests/data/flow-shapes" "$P/engines/v1/texts.py" "$P/engines/v1/prompts.py" \
      "$P/prompts" | grep -c .)"
    echo "  계약 고정 스키마·texts·prompts 바뀜 $fixed"
    [ "$fixed" = 0 ] || code=1
  fi
  return $code
}

# 6: 금지 글 — 더한 줄(추적 diff + 새 파일)·메시지·보고. ② 는 drafting 의 pypdf 0.
s6() {
  local d="$OUT/s6.diff" n_key n_bin n_name=0 code=0 report="$MROOT/band-reports/RP2a.md" n_pypdf=0
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
  if [ "$COMMIT" = 2 ]; then
    n_pypdf="$(git grep -c -E '(^|[^_a-z])pypdf([^_a-z]|$)' -- "$P" ':!*/tests/*' 2>/dev/null | grep -c .)"
  fi
  echo "  키 꼴 $n_key · .pdf/.xlsx/.docx/.ipynb $n_bin · 실재 기업명 낱말 $n_name · drafting pypdf 파일 $n_pypdf"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ] && [ "$n_pypdf" = 0 ] || code=1
  return $code
}

s7() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

# 8: generated/ 셋을 다시 뽑아 cmp — 차이 0(경로·스키마 0 바뀜)
s8() {
  local g="$OUT/s8-generated" code=0 f
  git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ generated/ 가 바뀜"; code=1; }
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  return $code
}

s9() {
  local blog="$OUT/s9-business.log" slog="$OUT/s9-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres storage > "$OUT/s9-up.log" 2>&1 || { tail -3 "$OUT/s9-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db \
    esgapi/core esgapi/config esgapi/runs esgapi/drafting esgapi/translation esgapi/reconcile \
    esgapi/greenwash/tests/service/actions/test_bundle_carrier.py) > "$blog" 2>&1
  bcode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s10() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-RP2a.sh" --boundary "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-418" "Derives-from: MARC-ENT-514" "Derives-from: MARC-ENT-512" \
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; do
    grep -q -x -F "$t" "$MSG" || { echo "  ★ 트레일러 없음: $t"; code=1; }
  done
  if [ "$COMMIT" = 2 ]; then
    for t in "Concerns: MARC-ISSUE-474" "Concerns: MARC-ISSUE-473"; do
      grep -q -x -F "$t" "$MSG" || { echo "  ★ 트레일러 없음: $t"; code=1; }
    done
    head -1 "$MSG" | grep -q -E '^feat\(drafting\): RP2a ② ' || { echo "  ★ 제목 꼴"; code=1; }
  else
    head -1 "$MSG" | grep -q -E '^feat\(core\): RP2a ① ' || { echo "  ★ 제목 꼴"; code=1; }
  fi
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

step 1 "순수 시험 N0 → N1" s1
step 2 "lint-imports 전부 KEPT·수 = 기준 · .importlinter 0줄" s2
step 3 "check_test_layout" s3
step 4 "pyright 0 · ruff check · ruff format --check" s4
step 5 "경로 1-2·C-7 안 · 0줄 목록 · services/parser · bad_minus=0 · numstat · e7 sha16" s5
step 6 "금지 글·키 꼴·바이너리 0 (② pypdf 0)" s6
step 7 "makemigrations --check --dry-run" s7
step 8 "generated/ 다시 뽑아 cmp" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무(core·config·runs·drafting·translation·reconcile·R9 carrier) · 보안(전부)" s9
else
  not_run 9 "업무·보안(컨테이너)" "--with-containers 없음"
fi
if [ "$PLANTED" = 1 ]; then step 10 "심은 파손(경계 $COMMIT 몫)" s10; fi
if [ -n "$MSG" ]; then step 11 "커밋 메시지 트레일러(§5)" s11; fi
step 12 "뿌리 verify.sh --fast" s12
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
