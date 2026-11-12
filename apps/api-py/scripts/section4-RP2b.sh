#!/usr/bin/env bash
# 밴드 RP2b(MARC-TICK-430: 원고작성 결과 꼴 drafting.bullets@2 — 블록 id·문장 번호 근거·상자·basis, 흐름
# drafting.draft@v2·engines/v2)의 §4 자기검증(발주서 band-handoffs/RP2b-order.md §4). 틀은 section4-RP2a.sh.
#   사용: apps/api-py/scripts/section4-RP2b.sh [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 9(업무·보안)를 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 경계 끝 전량은 따로). AI 공급사 호출 0(env -u 키). 파서 HTTP 0.
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 RP2b.out — 검증자는 RP2b.verify), RP2B_FORBIDDEN(실재 기업명 낱말 파일,
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
OUT="${S4_OUT:-$ROOT/../RP2b.out}"
FORBIDDEN="${RP2B_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
MROOT="${MARCSPON_ROOT:-$HERE/../../../../..}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 RP2b §4 · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# 1: 순수 층(drafting — not django_db). N0 = <기준> 의 시험 파일 수 → N1.
s1() {
  local log n code n0 target="esgapi/drafting"
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
  local code=0 dirs="esgapi/drafting"
  # shellcheck disable=SC2086
  (cd "$A" && uv run --frozen pyright $dirs 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff check . 2>&1 | tail -1 | sed 's/^/  ruff check /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check . 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") \
    || code=1
  return $code
}

# 5: 경로(1-2·1-3) · bad_minus · 0줄 목록 · 공유 numstat · e7 sha16
ALLOWED="^$P/engines/v2/(__init__|sentences|material|answers|checks|places|texts)\.py\$
^$P/engines/v1/(pages|bullets|checks)\.py\$
^$P/contracts/shapes\.py\$
^$P/flows/(draft_v1|draft_v2|binding_v1|binding_v2|registration)\.py\$
^$P/apps\.py\$
^$P/service/actions/(run_sources|result|download)\.py\$
^$P/service/apis/drafting\.py\$
^$P/outputs/docx\.py\$
^$P/prompts/draft/2\.md\$
^$P/prompts/README\.md\$
^$P/tests/.*
^$A/scripts/(section4|planted-breaks)-RP2b\.sh\$
^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)\$
^$A/tests/security/.*
^$C/tests/(isolation/.*|test_transaction_rules\.py|test_selector_scope\.py)\$
^$E/config/tests/.*
^README\.md\$"
ZERO="^services/parser/
^$E/runs/
^$C/(documents|resources|service|flows|llm|auth|migrations)/
^$C/(models|permissions|conf)\.py\$
^$E/config/(settings|env|api)
^$P/(models|api)\.py\$
^$P/migrations/
^$P/contracts/(wire|options_shapes|api_shapes)\.py\$
^$P/tools/
^$P/engines/v1/(texts|prompts|mapping)\.py\$
^$P/prompts/(map|draft)/1\.md\$
^apps/web/
^$A/(pyproject\.toml|uv\.lock)\$
^$A/\.importlinter\$
^compose\.yaml\$"
SHARED="$A/tests/security README.md $C/tests/isolation $C/tests/test_transaction_rules.py $C/tests/test_selector_scope.py
$E/config/tests $E/greenwash/tests/service/actions/test_bundle_carrier.py"
# 「바꿈」 표시 줄: 발주서 1-3 의 README:36 한 줄(@1 → @2 + 「출처 = 블록·문장」). test_drafting 세 줄은 @1→@2·@v1→@v2
#   라 숫자 정규화로 같은 줄이 된다(단언 뜻 0 바뀜)
REPLACED="잎마다 개조식 bullet(출처 쪽은 서버 코드가 대 봄)을 짓고"

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
            print("    (「바꿈」 표시 줄 — 1-3 허락)")
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
  return $code
}

# 6: 금지 글 — 더한 줄(추적 diff + 새 파일)·메시지·보고. ② 는 drafting 의 pypdf 0.
s6() {
  local d="$OUT/s6.diff" n_key n_bin n_name=0 code=0 report="$MROOT/band-reports/RP2b.md" n_pypdf=0
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
  n_pypdf="$(git grep -c -E '(^|[^_a-z])pypdf([^_a-z]|$)' -- "$P" ':!*/tests/*' 2>/dev/null | grep -c .)"
  echo "  키 꼴 $n_key · .pdf/.xlsx/.docx/.ipynb $n_bin · 실재 기업명 낱말 $n_name · drafting pypdf 파일 $n_pypdf"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ] && [ "$n_pypdf" = 0 ] || code=1
  return $code
}

s7() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

# 8: generated/ 셋을 다시 뽑아 cmp(손 0) + 바뀐 컴포넌트 목록 $OUT/generated-diff.txt(기준 openapi 와 견줌)
s8() {
  local g="$OUT/s8-generated" code=0 f
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 작업본"; else echo "  ★ cmp $f ≠ 작업본"; code=1; fi
  done
  git show "$BASE:$A/generated/openapi.json" > "$g/openapi.base.json"
  python3 -I - "$g/openapi.base.json" "$g/openapi.json" > "$OUT/generated-diff.txt" <<'PYEOF' || code=1
import json, sys
a = json.load(open(sys.argv[1]))["components"]["schemas"]
b = json.load(open(sys.argv[2]))["components"]["schemas"]
print("새 컴포넌트:", sorted(set(b) - set(a)))
print("빠진 컴포넌트(-):", sorted(set(a) - set(b)))
for k in sorted(set(a) & set(b)):
    if a[k] != b[k]:
        pa, pb = a[k].get("properties", {}), b[k].get("properties", {})
        ra, rb = set(a[k].get("required", [])), set(b[k].get("required", []))
        print(f"바뀐 {k}: 칸 더함 {sorted(set(pb) - set(pa))} 칸 뺌 {sorted(set(pa) - set(pb))} "
              f"필수 더함 {sorted(rb - ra)} 필수 뺌 {sorted(ra - rb)}")
        for f in sorted(set(pa) & set(pb)):
            if pa[f] != pb[f]:
                print(f"   칸 바뀜 {k}.{f}: {json.dumps(pa[f], ensure_ascii=False)} → {json.dumps(pb[f], ensure_ascii=False)}")
outside = [k for k in set(a) | set(b) if a.get(k) != b.get(k) and not k.startswith("Drafting")]
print("Drafting 밖 바뀐 컴포넌트:", sorted(outside))
sys.exit(1 if outside else 0)
PYEOF
  sed -n '1,2p' "$OUT/generated-diff.txt" | sed 's/^/  /'
  grep '^Drafting 밖' "$OUT/generated-diff.txt" | sed 's/^/  /'
  return $code
}

s9() {
  local blog="$OUT/s9-business.log" slog="$OUT/s9-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres storage > "$OUT/s9-up.log" 2>&1 || { tail -3 "$OUT/s9-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db \
    esgapi/drafting esgapi/config esgapi/core esgapi/runs esgapi/translation \
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
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-RP2b.sh" 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | sed 's/^/  /'
  [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s11() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-430" "Derives-from: MARC-ENT-514" "Derives-from: MARC-ENT-512" "Concerns: MARC-ISSUE-472" \
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; do
    grep -q -x -F "$t" "$MSG" || { echo "  ★ 트레일러 없음: $t"; code=1; }
  done
  head -1 "$MSG" | grep -q -E '^feat\(drafting\): RP2b ' || { echo "  ★ 제목 꼴"; code=1; }
  echo "  제목 $(head -1 "$MSG") · 트레일러 $(grep -c -E '^[A-Z][A-Za-z-]+: ' "$MSG") 줄"
  return $code
}

# 10: 시험 약화 검사. HEAD 가 기준이면(커밋 전) --warn 으로 미리(작업 트리는 못 본다 — 짝 표는 보고에)
s10w() {
  local log code
  if [ "$(git rev-parse HEAD)" = "$BASE" ]; then
    log="$(python3 -I scripts/check_test_weakening.py --warn main HEAD 2>&1)"
  else
    log="$(python3 -I scripts/check_test_weakening.py main HEAD 2>&1)"
  fi
  code=$?
  echo "$log" > "$OUT/s10-weaken.log"
  echo "$log" | tail -3 | sed 's/^/  /'
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
step 5 "경로 1-2·1-3 안 · 0줄 목록 · bad_minus=0 · numstat · e7 sha16" s5
step 6 "금지 글·키 꼴·바이너리 0 · drafting pypdf 0" s6
step 7 "makemigrations --check --dry-run" s7
step 8 "generated/ 다시 뽑아 cmp · 바뀐 컴포넌트 목록(Drafting 밖 0)" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무(drafting·config·core·runs·translation·R9 carrier) · 보안(전부)" s9
else
  not_run 9 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 10 "WEAKEN(check_test_weakening — 커밋 전엔 --warn)" s10w
if [ "$PLANTED" = 1 ]; then step 11 "심은 파손 R1~R12" s10; fi
if [ -n "$MSG" ]; then step 12 "커밋 메시지 트레일러(§5)" s11; fi
step 13 "뿌리 verify.sh --fast" s12
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
