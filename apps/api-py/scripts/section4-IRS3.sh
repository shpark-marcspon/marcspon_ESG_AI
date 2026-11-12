#!/usr/bin/env bash
# 밴드 IRS3(MARC-TICK-477: 중대성평가 IRO 결과 글 칸 고치기 서버 반쪽 — 고친 값 저장·결과 GET 이 고친 판·결과 엑셀이
# 고친 판)의 §4 자기검증(발주서 band-handoffs/IRS3-order.md §4 — section4-IR3c.sh 꼴).
#   사용: apps/api-py/scripts/section4-IRS3.sh --commit <n> [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --commit n(1·2·3)은 그 경계까지의 허락 목록·0바이트 목록·수·심은 파손 몫으로 잰다.
#   --with-containers 면 단계 6(업무·보안 — 이 워크트리 compose 의 postgres)을 돈다. 안 주면 「안 돌림」(EXIT=1 로 센다).
#   --planted 면 단계 8, --msg 면 단계 9.
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만 — 단계 11). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 IRS3.out), IRS3_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
M="$E/materiality"
OUT="${S4_OUT:-$ROOT/../IRS3.out}"
FORBIDDEN="${IRS3_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(4b767d19)에서 잰 수: 순수 = pytest esgapi/materiality -m "not django_db and not security" 756 · 업무(django_db)
#   224 · lint-imports 계약 19.
# 기대(늘기만): ① 순수 +68(tests/outputs/test_edits.py) · 업무 +12(tests/service/services/test_edits.py)
#   · ② 업무 +17(tests/service/apis/test_materiality_edits.py) · ③ 업무 +5(tests/service/apis/test_materiality_report.py).
BASE_PURE=756 BASE_BUSINESS=224 BASE_CONTRACTS=19
unset OPENAI_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY ANTHROPIC_API_KEY
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""; COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit <n> [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in
  1) EXPECT_PURE=824 EXPECT_PLANTED=8 EXPECT_BUSINESS=236 ;;
  2) EXPECT_PURE=824 EXPECT_PLANTED=12 EXPECT_BUSINESS=253 ;;
  3) EXPECT_PURE=824 EXPECT_PLANTED=16 EXPECT_BUSINESS=259 ;;
  *) echo "--commit 은 1·2·3" >&2; exit 2 ;;
esac
BASE="$(git merge-base main HEAD)"
# 경계 ④(main 들이기): 병합 진행 중(MERGE_HEAD)이면 기준 = main — 커밋 뒤 merge-base 도 main 이다
if git rev-parse -q --verify MERGE_HEAD > /dev/null; then BASE="$(git rev-parse main)"; fi
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 IRS3 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0
# 잠금(runner-common §5): main 저장소의 .git/verify.lock 이 있으면 전량뿐 아니라 부분 실행도 하지 않는다 — 없어질 때까지
# 기다린다(디렉터리라 -e 로 본다).
LOCK="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
while [ -e "$LOCK" ]; do
  echo "  .git/verify.lock 있음($(cat "$LOCK/pid" 2> /dev/null)) — 30초 뒤 다시 본다"
  sleep 30
done

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

changed() {  # <기준> 뒤 바뀐 경로(추적 diff + 추적 안 된 새 파일)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-1 materiality 땅 + §1-2 71 표(경계 ①: test_selector_scope·test_managers·test_static_rules·test_transaction_rules
# (7a 조건 1 의 「+n 꼴」)·test_owner)
ALLOWED_1='apps/api-py/esgapi/materiality/(models\.py|migrations/0002_result_edits\.py|contracts/edit_shapes\.py|outputs/edits\.py|service/selectors/edits\.py|service/services/edits\.py|tests/outputs/test_edits\.py|tests/service/services/test_(edits|ai_settings)\.py)|apps/api-py/scripts/(section4|planted-breaks)-IRS3\.sh|apps/api-py/esgapi/core/tests/(test_selector_scope|test_transaction_rules|isolation/test_managers|isolation/test_static_rules)\.py|apps/api-py/tests/security/test_owner\.py'
# 경계 ②: 경로 셋·결과 GET 덮기 + 71 표(권한·계약·generated·보안 둘)
ALLOWED_2='apps/api-py/esgapi/materiality/(service/actions/(result|edits)\.py|service/apis/materiality\.py|tests/service/apis/test_materiality(_edits)?\.py)|apps/api-py/esgapi/core/permissions\.py|apps/api-py/esgapi/core/tests/test_permissions(_wiring)?\.py|apps/api-py/esgapi/config/tests/test_(api_contract|api_errors|api_times|request_schemas_reject_bool)\.py|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|apps/api-py/tests/security/test_(tenant_paths|materiality|login|operator_company)\.py'
# 경계 ③: 내려받기
ALLOWED_3='apps/api-py/esgapi/materiality/(service/actions/report\.py|tests/service/apis/test_materiality_report\.py)'
case "$COMMIT" in
  1) ALLOWED="^($ALLOWED_1)$" ;;
  2) ALLOWED="^($ALLOWED_1|$ALLOWED_2)$" ;;
  *) ALLOWED="^($ALLOWED_1|$ALLOWED_2|$ALLOWED_3)$" ;;
esac

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · OUTSIDE=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-2 끝 「0바이트」
ZERO=("$E/runs" "$E/runbundle" "$E/user" "$E/organization" "$E/greenwash" "$E/translation" "$E/dataverify"
  "$E/drafting" "$E/inventory" "$E/reference" "$E/reconcile" "$E/config/api.py" "$E/config/settings" "$E/config/apps_list.py"
  "$M/flows" "$M/engines" "$M/prompts" "$M/outputs/final_xlsx.py" "$M/outputs/xlsx.py" "$M/outputs/digest.py"
  "$M/contracts/shapes.py" "$M/contracts/options_shapes.py" "$M/contracts/digest_shapes.py" "$M/contracts/run_list_shapes.py"
  "$M/contracts/value_chain_shapes.py" "$M/contracts/ai_setting_shapes.py" "$M/contracts/wire.py" "$M/tests/data"
  "$M/apps.py" "$M/api.py" "$E/core/flows" "$E/core/calc" "$E/core/models.py" "$E/core/migrations"
  "$A/.importlinter" "$A/pyproject.toml" "$A/uv.lock" "$A/conftest.py" "$A/tests/support" "$A/tests/security/conftest.py"
  "$A/tests_integration" "$A/scripts/planted-breaks.sh" apps/web docs README.md)
if [ "$COMMIT" = 1 ]; then
  ZERO+=("$E/core/permissions.py" "$E/config" "$A/generated" "$M/service/actions" "$M/service/apis")
elif [ "$COMMIT" = 2 ]; then
  ZERO+=("$M/service/actions/report.py")
fi

s2() {
  local n
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  ZERO_CHANGED=$n"
  { git diff --name-only "$BASE" -- "${ZERO[@]}"; git ls-files -o --exclude-standard -- "${ZERO[@]}"; } | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

minus_lines() {  # 기존 시험·71 파일의 「-」 줄을 <파일>:<기준 줄>\t<글> 로
  git diff -U0 "$BASE" -- "$@" | python3 -I -c '
import re, sys
f = None
for line in sys.stdin:
    if line.startswith("--- "):
        continue
    if line.startswith("+++ "):
        f = line[6:].strip().replace("apps/api-py/", "", 1)
        continue
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+", line)
    if m:
        n = int(m.group(1))
        continue
    if line.startswith("-"):
        print(f"{f}:{n}\t{line[1:].rstrip()}")
        n += 1
'
}

s3() {
  local code=0 mat other
  mat="$(minus_lines "$M/tests")"
  other="$(minus_lines "$E/core" "$E/config" "$A/tests/security")"
  { echo "$mat"; echo "$other"; } > "$OUT/s3-minus.txt"
  # 감독 허락(27 · 11-03): test_ai_settings.py :436·:442 의 표 집합 두 줄만
  mat="$(echo "$mat" | grep -v -E '^esgapi/materiality/tests/service/services/test_ai_settings\.py:(436|442)'$'\t''    assert _tables\(\) == \{"materiality_ai_settings"\}$')"
  echo "  materiality 시험 「-」 줄(허락 둘 밖) $(echo "$mat" | grep -c .)(0 이어야)"
  [ -z "$mat" ] || { echo "$mat" | sed 's/^/  ★ /'; code=1; }
  echo "  71 표 파일 「-」 줄 $(echo "$other" | grep -c .) — 원문(보고에 옮김):"
  echo "$other" | grep . | sed 's/^/    - /'
  git diff --numstat "$BASE" -- "$E/core" "$E/config" "$A/tests/security" "$A/generated" | sed 's/^/  numstat /'
  git diff -U0 "$BASE" -- "$E/core" "$E/config" "$A/tests/security" "$A/generated" | shasum -a 256 | cut -c1-16 \
    | sed 's/^/  71 땅 diff sha256 16자 /'
  return $code
}

s4() {
  local code=0 log kept broken files
  log="$(cd "$A" && uv run --frozen lint-imports 2>&1)"
  echo "$log" > "$OUT/s4-lint-imports.log"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\2/p')"
  echo "  lint-imports kept=$kept broken=$broken (기준 $BASE_CONTRACTS)"
  [ "$kept" = "$BASE_CONTRACTS" ] && [ "$broken" = 0 ] || code=1
  files="$(changed | grep '^apps/api-py/.*\.py$' | sed 's|^apps/api-py/||' | tr '\n' ' ')"
  # shellcheck disable=SC2086
  (cd "$A" && uv run --frozen ruff check $files && uv run --frozen ruff format --check $files) > "$OUT/s4-ruff.log" 2>&1 \
    || code=1
  tail -1 "$OUT/s4-ruff.log" | sed 's/^/  ruff /'
  # shellcheck disable=SC2086
  (cd "$A" && uv run --frozen pyright $files) > "$OUT/s4-pyright.log" 2>&1 || code=1
  tail -1 "$OUT/s4-pyright.log" | sed 's/^/  pyright(바뀐 파일) /'
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s4-layout.log" 2>&1 || code=1
  tail -1 "$OUT/s4-layout.log" | sed 's/^/  layout /'
  return $code
}

s5() {
  local log n code
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/materiality -m "not django_db and not security" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  materiality 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] || return 1
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/core/tests/test_selector_scope.py \
    esgapi/core/tests/isolation esgapi/core/tests/test_transaction_rules.py -m "not django_db and not security" 2>&1)"
  code=$?
  echo "  71 정적 규칙(selector_scope·isolation·transaction_rules 순수 몫) $(echo "$log" | tail -1)"
  [ "$code" = 0 ]
}

s6() {
  local code=0 mlog="$OUT/s6-materiality.log" slog="$OUT/s6-security.log" n names
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s6-up.log" 2>&1 || { tail -3 "$OUT/s6-up.log"; return 1; }
  fi
  (cd "$A" && scripts/test-business.sh -p no:cacheprovider --create-db esgapi/materiality) > "$mlog" 2>&1 || code=1
  n="$(tail -1 "$mlog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  materiality 업무 $(tail -1 "$mlog") (기준 $BASE_BUSINESS → 기대 $EXPECT_BUSINESS)"
  [ "$n" = "$EXPECT_BUSINESS" ] || code=1
  # 보안 층 전부(③ 전량 verify 에서 test_login·test_operator_company 셈 줄을 놓친 뒤 넓힘 — 셋만 돌리면 안 된다)
  (cd "$A" && scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1 || code=1
  echo "  보안 층 전부 $(tail -1 "$slog")"
  if [ "$COMMIT" -ge 2 ]; then
    names="$(grep -c -E '^def test_.*(stored_results|run_results|stored_rows).*' "$M/tests/service/apis/test_materiality_edits.py")"
    echo "  RESULT_ROWS_SAME 시험 $names 개(0 아니어야)"
    [ "$names" -ge 1 ] && echo "  RESULT_ROWS_SAME=0" || { echo "  RESULT_ROWS_SAME=1"; code=1; }
  else
    echo "  RESULT_ROWS_SAME — 경계 ① 은 경로가 없어 run_results 를 건드릴 길 0(② 부터 잼)"
  fi
  return $code
}

s7() {
  local code=0 log
  if [ "$COMMIT" = 1 ]; then
    git diff --quiet "$BASE" -- "$A/generated" && echo "  경계 ① — generated 0줄" && return 0
    echo "  ★ 경계 ① 인데 generated/ 가 기준과 다름"; return 1
  fi
  # 순수 몫은 여기, django_db 몫(wiring 의 권한 내림 등)은 업무 층으로(이 워크트리 postgres — --with-containers 일 때만)
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py \
    esgapi/core/tests/test_permissions.py esgapi/core/tests/test_permissions_wiring.py \
    esgapi/config/tests/test_api_errors.py esgapi/config/tests/test_request_schemas_reject_bool.py \
    -m "not django_db" 2>&1)" || code=1
  if [ "$CONTAINERS" = 1 ]; then
    log="$log
$(cd "$A" && scripts/test-business.sh -p no:cacheprovider esgapi/config/tests/test_api_contract.py \
      esgapi/core/tests/test_permissions.py esgapi/core/tests/test_permissions_wiring.py \
      esgapi/config/tests/test_api_errors.py 2>&1)" || code=1
  fi
  echo "$log" > "$OUT/s7-contract.log"
  echo "$log" | grep -E "(passed|failed|error)" | grep -E "^[0-9]" | sed 's/^/  계약·권한·오류 /'
  local before after
  before="$(shasum -a 256 "$A"/generated/* | shasum -a 256)"
  (cd "$A" && scripts/gen-ts-types.sh) > "$OUT/s7-gen.log" 2>&1 || { echo "  ★ gen-ts-types 실패"; return 1; }
  after="$(shasum -a 256 "$A"/generated/* | shasum -a 256)"
  [ "$before" = "$after" ] && echo "  gen-ts-types 다시 돌림 → 작업본 diff 0" \
    || { echo "  ★ gen-ts-types 뒤 generated 가 바뀜(손편집·낡은 생성물)"; code=1; }
  git diff --numstat "$BASE" -- "$A/generated" | sed 's/^/  numstat /'
  git diff -U0 "$BASE" -- "$A/generated/openapi.json" | grep -E '^[-+] ' > "$OUT/s7-openapi-lines.txt"
  echo "  openapi '-' 줄 $(grep -c '^-' "$OUT/s7-openapi-lines.txt") · '+' 줄 $(grep -c '^+' "$OUT/s7-openapi-lines.txt")"
  python3 -I - "$A/generated/openapi.json" "$OUT/s7-base-openapi.json" "$BASE" <<'PYEOF' || code=1
import json, subprocess, sys
head = json.load(open(sys.argv[1], encoding="utf-8"))
base = json.loads(subprocess.run(["git", "show", f"{sys.argv[3]}:apps/api-py/generated/openapi.json"], capture_output=True,
                                 text=True, check=True).stdout)
bs, hs = base["components"]["schemas"], head["components"]["schemas"]
changed = [k for k in bs if hs.get(k) != bs[k]]
added = [k for k in hs if k not in bs]
paths = [p for p in head["paths"] if p not in base["paths"]]
gone = [p for p in base["paths"] if p not in head["paths"]]
moved = [f"{p} {m}" for p, ops in base["paths"].items() for m, op in ops.items() if head["paths"].get(p, {}).get(m) != op]
print(f"  COMPONENTS_CHANGED={len(changed)} {changed} · 늘어남 {added}")
print(f"  PATHS_ADDED={paths} · 없어진 path {gone} · 바뀐 동작 {moved}")
ok = not changed and not gone and not moved and all(k.startswith("Materiality") for k in added)
ok = ok and all(p.startswith("/materiality/runs/{run_id}/") for p in paths)
sys.exit(0 if ok else 1)
PYEOF
  return $code
}

s8() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(IRS3_OUT="$OUT" "$A/scripts/planted-breaks-IRS3.sh" --commit "$COMMIT" $flag 2>&1)"
  echo "$log" > "$OUT/s8-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s9() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-477" "Derives-from: MARC-ENT-561" "Concerns: MARC-TICK-272" \
    "Constraint: run_results·run_files 는 한 번 쓰고 끝" "Rejected: 저장 때 엑셀 새 판" "Rejected: 1-1 항목 한 자리만 고침" \
    "Directive: 맥락 항목 묶음은 원본 url 로" "Co-Authored-By:"; do
    grep -q "^$t" "$MSG" && echo "  있음 $t" || { echo "  ★ 없음 $t"; code=1; }
  done
  return $code
}

s10() {
  local d="$OUT/s10.diff" n_key n_bin n_name=0
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-IRS3.sh"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-IRS3.sh" \
      | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴·키 자리 $n_key · .xlsx/.csv/.ipynb $n_bin · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ]
}

s11() {
  local log start
  start=$(date +%s)
  log="$(scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s11-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

step 1 "바뀐 경로가 §1-1·§1-2 안(OUTSIDE=0)" s1
step 2 "0바이트 목록(ZERO_CHANGED=0)" s2
step 3 "시험 「-」 줄: materiality 0 · 71 표 파일 원문" s3
step 4 "lint-imports·ruff·format·pyright(바뀐 파일)·test layout" s4
step 5 "순수 시험 초록·수 · 71 정적 규칙" s5
if [ "$CONTAINERS" = 1 ]; then
  step 6 "업무·보안(이 워크트리 postgres) · RESULT_ROWS_SAME" s6
else
  not_run 6 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 7 "계약·권한 시험 · gen-ts-types 다시 돌려 diff 0 · generated 는 materiality 경로·꼴만" s7
if [ "$PLANTED" = 1 ]; then
  step 8 "심은 파손(경계 $COMMIT 까지의 몫 $EXPECT_PLANTED)" s8
else
  not_run 8 "심은 파손" "--planted 없음"
fi
if [ -n "$MSG" ]; then
  step 9 "커밋 메시지 트레일러" s9
fi
step 10 "추가 줄의 키 꼴·.xlsx/.csv/.ipynb·실재 기업명 0" s10
step 11 "뿌리 verify.sh --fast" s11

s12() {  # ★B: 고침 0 이면 새 경로 엑셀 = 저장본(시트 셋 칸 값, RAW_JSON json.loads — 경고 차이만)
  local log code
  log="$(cd "$A" && scripts/test-business.sh -p no:cacheprovider \
    "esgapi/materiality/tests/service/apis/test_materiality_report.py::test_without_edits_the_report_matches_the_stored_file" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s12-noedit.log"
  echo "  $(echo "$log" | tail -1)"
  [ "$code" = 0 ] && echo "  NOEDIT_SHEETS_SAME=0" || echo "  NOEDIT_SHEETS_SAME=1"
  return $code
}
if [ "$COMMIT" = 3 ]; then
  if [ "$CONTAINERS" = 1 ]; then
    step 12 "★B 고침 0 엑셀 = 저장본(NOEDIT_SHEETS_SAME=0)" s12
  else
    not_run 12 "★B 고침 0 엑셀" "--with-containers 없음"
  fi
fi
echo "SECTION4_FAIL=$FAILS"
