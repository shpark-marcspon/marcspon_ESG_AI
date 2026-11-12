#!/usr/bin/env bash
# 밴드 IRW2(MARC-TICK-349: 중대성평가 IRO 입력 — 가치사슬 엑셀 읽기 POST /materiality/value-chain/read)의 §4 자기검증 —
# 서버 몫(발주서 band-handoffs/IRW2-order.md §4 — section4-IR3c.sh 꼴). 웹 몫은 apps/web/scripts/section4-IRW2.sh.
#   사용: apps/api-py/scripts/section4-IRW2.sh [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 10(업무·보안)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다). --planted 면 단계 11.
#   --msg 면 단계 13(커밋 메시지 초안의 트레일러).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 IRW2.out), IRW2_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
M="$E/materiality"
OUT="${S4_OUT:-$ROOT/../IRW2.out}"
FORBIDDEN="${IRW2_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(54a38aaa)에서 잰 수: 순수 = pytest esgapi/materiality -m "not django_db" 442 · lint-imports 계약 17 ·
#   openapi 컴포넌트 359. 기대(늘기만): 순수 +144(tools 133 · contracts/test_value_chain_shapes 11) · 업무 +11
#   (service/apis/test_value_chain). 심은 파손 서버 몫 13(P1~P5·P2b~P2g·PR1·PR2).
BASE_PURE=442 BASE_CONTRACTS=18 BASE_COMPONENTS=359
EXPECT_PURE=586 EXPECT_PLANTED=13
unset OPENAI_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY ANTHROPIC_API_KEY
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
mkdir -p "$OUT"
echo "── 밴드 IRW2 §4(서버) · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

changed() {  # <기준> 뒤 바뀐 경로(추적 diff + 추적 안 된 새 파일) — 서버 몫만(apps/web 은 웹 스크립트)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u | grep -v '^apps/web/'
}

# §1-2 서버 ① + A0 의 H1·H2·H3 줄의 파일
ALLOWED='apps/api-py/esgapi/materiality/tools/(__init__|value_chain_xlsx)\.py|apps/api-py/esgapi/materiality/contracts/value_chain_shapes\.py|apps/api-py/esgapi/materiality/service/actions/value_chain\.py|apps/api-py/esgapi/materiality/service/apis/materiality\.py|apps/api-py/esgapi/materiality/tests/.*|apps/api-py/scripts/(section4|planted-breaks)-IRW2\.sh|docs/development\.md|apps/api-py/esgapi/core/permissions\.py|apps/api-py/esgapi/core/tests/test_(permissions|permissions_wiring|transaction_rules)\.py|apps/api-py/esgapi/config/tests/test_api_(contract|errors)\.py|apps/api-py/\.importlinter|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|apps/api-py/tests/security/test_(tenant_paths|login|operator_company|materiality)\.py|apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure\.py'

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "^($ALLOWED)$" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · OUTSIDE=$outside"
  echo "$all" | grep -v -E "^($ALLOWED)$" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-2 끝(0바이트)·§H 의 0줄
ZERO=("$M/contracts/shapes.py" "$M/contracts/wire.py" "$M/contracts/options_shapes.py" "$M/contracts/run_list_shapes.py"
  "$M/contracts/digest_shapes.py" "$M/engines" "$M/prompts" "$M/flows" "$M/outputs" "$M/service/actions/result.py"
  "$M/service/actions/runs.py" "$M/tests/data" "$M/api.py" "$M/apps.py" "$E/translation" "$E/config/api.py" "$E/runs"
  "$E/dataverify" "$E/greenwash" "$E/reference" "$E/organization" "$E/reconcile" "$E/user"
  "$A/pyproject.toml" "$A/uv.lock" package.json pnpm-lock.yaml "$A/tests/support" "$A/tests/security/conftest.py"
  "$A/conftest.py" "$A/tests_integration")
CORE_TABLE='esgapi/core/permissions\.py|esgapi/core/tests/test_(permissions|permissions_wiring|transaction_rules)\.py'

s2() {
  local n core_out inv_out
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  core_out="$(git diff --name-only "$BASE" -- "$E/core" | sed "s|^$A/||" | grep -v -E "^($CORE_TABLE)$" | grep -c .)"
  inv_out="$(git diff --name-only "$BASE" -- "$E/inventory" | grep -v -x "$E/inventory/tests/test_s3sheets_is_pure.py" | grep -c .)"
  echo "  0바이트·0줄 목록 바뀐 파일 $n · core 표 밖 $core_out · inventory 한 줄 밖 $inv_out"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ] && [ "$core_out" = 0 ] && [ "$inv_out" = 0 ]
}

# A0 허락 「-」 줄(기준의 파일:줄 — C0 표, 감독 「C0 통과」 10-28 · ※1 :346 · 444 셈 :340).
# 기준을 main 1b7484bc(RX1a 병합 — 감독 10-28 가지 병합 0f83be19)로 옮김: test_transaction_rules 분모 줄 :306 → :326 · 계약 수 17 → 18(runbundle).
MINUS_ALLOWED='esgapi/core/permissions.py:7 esgapi/core/permissions.py:46
esgapi/core/tests/test_permissions.py:227 esgapi/core/tests/test_permissions.py:242 esgapi/core/tests/test_permissions.py:276
esgapi/core/tests/test_permissions.py:277 esgapi/core/tests/test_permissions.py:346
esgapi/core/tests/test_permissions_wiring.py:335 esgapi/core/tests/test_permissions_wiring.py:336
esgapi/core/tests/test_transaction_rules.py:326
esgapi/config/tests/test_api_contract.py:257 esgapi/config/tests/test_api_contract.py:261 esgapi/config/tests/test_api_contract.py:279
esgapi/config/tests/test_api_contract.py:327 esgapi/config/tests/test_api_contract.py:340 esgapi/config/tests/test_api_contract.py:460
esgapi/config/tests/test_api_contract.py:461 esgapi/config/tests/test_api_contract.py:661
esgapi/config/tests/test_api_errors.py:67 esgapi/config/tests/test_api_errors.py:99
tests/security/test_login.py:284 tests/security/test_login.py:322 tests/security/test_operator_company.py:155
tests/security/test_tenant_paths.py:383 tests/security/test_tenant_paths.py:428 tests/security/test_tenant_paths.py:459
tests/security/test_tenant_paths.py:485 tests/security/test_tenant_paths.py:600
generated/api.d.ts:* generated/api.d.ts.source-sha256:* generated/openapi.json:*'

minus_lines() {  # 공유 경로의 「-」 줄을 <파일>:<기준 줄>\t<원문> 으로
  git diff -U0 "$BASE" -- "$E/core" "$E/config" "$E/inventory" "$A/tests/security" "$A/generated" "$A/.importlinter" \
    | python3 -I -c '
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

# 허락 청 묶음(A0 H1·H2·H3)마다 diff 파일과 numstat·sha256 16자
HUNKS='h1-permissions:esgapi/core/permissions.py
h1-core-tests:esgapi/core/tests/test_permissions.py esgapi/core/tests/test_permissions_wiring.py esgapi/core/tests/test_transaction_rules.py
h1-config-tests:esgapi/config/tests/test_api_contract.py esgapi/config/tests/test_api_errors.py
h1-importlinter:.importlinter
h1-generated:generated/openapi.json generated/api.d.ts generated/api.d.ts.source-sha256
h2-security:tests/security/test_tenant_paths.py tests/security/test_login.py tests/security/test_operator_company.py tests/security/test_materiality.py
h3-s3sheets:esgapi/inventory/tests/test_s3sheets_is_pure.py'

s3() {
  local code=0 got bad name paths p
  got="$(minus_lines)"
  echo "$got" > "$OUT/s3-minus.txt"
  bad="$(MINUS_ALLOWED="$MINUS_ALLOWED" python3 -I -c '
import os, sys
allowed = set(os.environ["MINUS_ALLOWED"].split())
for line in sys.stdin:
    where = line.split("\t", 1)[0].strip()
    if where and where not in allowed and where.rsplit(":", 1)[0] + ":*" not in allowed:
        print(where)
' < "$OUT/s3-minus.txt")"
  echo "  「-」 줄 $(grep -c -v -E '^generated/' "$OUT/s3-minus.txt") (generated 밖) · 허락 밖 $(echo "$bad" | grep -c .)"
  echo "$bad" | grep . | sed 's/^/  ★ /'
  [ -z "$bad" ] || code=1
  echo "$HUNKS" | while IFS=: read -r name paths; do
    set --
    for p in $paths; do set -- "$@" "$A/$p"; done
    git diff "$BASE" -- "$@" > "$OUT/$name.diff"
    for p in "$@"; do
      git diff --numstat "$BASE" -- "$p" | awk -v p="$p" '{printf "  %s +%s/-%s", p, $1, $2}'
      printf ' sha256 %s\n' "$(git diff "$BASE" -- "$p" | shasum -a 256 | cut -c1-16)"
    done
    printf '  └ %s.diff sha256 %s\n' "$name" "$(shasum -a 256 < "$OUT/$name.diff" | cut -c1-16)"
  done
  got="$(git diff --numstat "$BASE" -- docs/development.md | awk '{print $1" "$2}')"
  echo "  docs/development.md numstat +${got% *}/-${got#* } (허락 +1/-1)"
  [ "$got" = "1 1" ] || code=1
  return $code
}

s4() {
  local log kept broken
  log="$(cd "$A" && uv run --frozen lint-imports 2>&1)"
  echo "$log" > "$OUT/s4-lint-imports.log"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\2/p')"
  echo "  kept=$kept broken=$broken (기준 $BASE_CONTRACTS)"
  grep -q "^    esgapi.materiality.tools$" "$A/.importlinter" || { echo "  ★ .importlinter 에 esgapi.materiality.tools 없음"; return 1; }
  [ "$kept" = "$BASE_CONTRACTS" ] && [ "$broken" = 0 ]
}

s5() {
  local log n code
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/materiality -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  materiality 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] || return 1
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/core esgapi/config esgapi/translation/tests/tools \
    esgapi/inventory/tests/test_s3sheets_is_pure.py -m "not django_db" 2>&1)"
  code=$?
  echo "  core·config·translation tools·s3sheets(순수 몫) $(echo "$log" | tail -1)"
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/materiality/tests/tools/test_value_chain_xlsx_twin.py 2>&1)"
  echo "  쌍둥이 $(echo "$log" | tail -1)"
  [ "$code" = 0 ] && echo "$log" | tail -1 | grep -q "passed" && ! echo "$log" | tail -1 | grep -q "failed"
}

s6() {  # 상한 여섯(50·200·20·50·200·100)이 읽개에 있다 — 웹 valueChain.ts 와의 대조는 웹 스크립트(② 뒤)
  local got
  got="$(grep -E '^MAX_CHARS: Final = |^MAX_DATA_ROWS: Final = ' "$M/tools/value_chain_xlsx.py" | tr '\n' ' ')"
  echo "  읽개: $got"
  echo "$got" | grep -q "MAX_DATA_ROWS: Final = 100" && echo "$got" | grep -q "MAX_CHARS: Final = (50, 200, 20, 50, 200)"
}

s7() {
  local g="$OUT/s7-generated" code=0
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi) \
    > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 커밋본"; else echo "  ★ cmp $f ≠ 커밋본"; code=1; fi
  done
  git show "$BASE:$A/generated/openapi.json" > "$g/base-openapi.json"
  jq -n --slurpfile b "$g/base-openapi.json" --slurpfile h "$A/generated/openapi.json" '
    ($b[0].components.schemas) as $bs | ($h[0].components.schemas) as $hs |
    {base: ($bs | length),
     changed: [$bs | keys[] | select($hs[.] != $bs[.])],
     added: [$hs | keys[] | select($bs[.] == null)],
     paths: [$h[0].paths | keys[] | select($b[0].paths[.] == null)],
     pathsGone: [$b[0].paths | keys[] | select($h[0].paths[.] == null)],
     pathsChanged: [$b[0].paths | to_entries[] | .key as $p | .value | to_entries[]
       | select($h[0].paths[$p][.key] != null and $h[0].paths[$p][.key] != .value) | .value.operationId]}' > "$g/components.json" || return 1
  echo "  기준 컴포넌트 $(jq .base "$g/components.json") · COMPONENTS_CHANGED=$(jq '.changed | length' "$g/components.json") · 늘어남 $(jq '.added | length' "$g/components.json") $(jq -c .added "$g/components.json") · PATHS_ADDED=$(jq '.paths | length' "$g/components.json") $(jq -c .paths "$g/components.json") · 없어진 path $(jq -c .pathsGone "$g/components.json") · 바뀐 동작 $(jq -c .pathsChanged "$g/components.json")"
  git diff --numstat "$BASE" -- "$A/generated" | sed 's/^/  numstat /'
  [ "$(jq .base "$g/components.json")" = "$BASE_COMPONENTS" ] || code=1
  [ "$(jq '.changed | length' "$g/components.json")" = 0 ] || code=1
  [ "$(jq '.pathsGone | length' "$g/components.json")" = 0 ] || code=1
  [ "$(jq '.pathsChanged | length' "$g/components.json")" = 0 ] || { echo "  ★ 바뀐 동작 0 이어야 한다"; code=1; }
  [ "$(jq '[.added[] | select(startswith("Materiality") | not)] | length' "$g/components.json")" = 0 ] \
    || { echo "  ★ 늘어난 컴포넌트는 전부 Materiality 머리"; code=1; }
  [ "$(jq -c .paths "$g/components.json")" = '["/materiality/value-chain/read"]' ] || { echo "  ★ PATHS_ADDED=1 이어야 한다"; code=1; }
  [ "$(git diff --numstat "$BASE" -- "$A/generated" | awk '{s += $2} END {print s + 0}')" = 1 ] \
    || { echo "  ★ generated 의 「-」 는 source-sha256 한 줄뿐"; code=1; }
  return $code
}

s8() {
  local code=0
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s8-layout.log" 2>&1 || code=1
  tail -1 "$OUT/s8-layout.log" | sed 's/^/  layout /'
  (cd "$A" && uv run --frozen pyright esgapi/materiality esgapi/core esgapi/config tests/security) > "$OUT/s8-pyright.log" 2>&1 || code=1
  tail -1 "$OUT/s8-pyright.log" | sed 's/^/  pyright /'
  (cd "$A" && uv run --frozen ruff check . && uv run --frozen ruff format --check .) > "$OUT/s8-ruff.log" 2>&1 || code=1
  tail -1 "$OUT/s8-ruff.log" | sed 's/^/  ruff /'
  return $code
}

s9() {
  local log start
  start=$(date +%s)
  log="$(scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s9-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "  $(( $(date +%s) - start ))s · $(uptime | sed 's/.*load/load/')"
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && scripts/test-business.sh -n 4 -p no:cacheprovider esgapi/materiality esgapi/runs esgapi/config esgapi/core \
    esgapi/translation esgapi/inventory esgapi/user) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  업무(materiality·runs·config·core·translation·inventory·user) $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s11() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(IRW2_OUT="$OUT" "$A/scripts/planted-breaks-IRW2.sh" $flag 2>&1)"
  echo "$log" > "$OUT/s11-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s12() {
  local d="$OUT/s12.diff" n_key n_bin n_bytes n_name=0
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-IRW2.sh" ":(exclude)apps/web"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-IRW2.sh" | grep -v '^apps/web/' \
      | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb|json)$' | awk '{print $1}')"
  n_bin=$((n_bin - $(changed | grep -c -x "$A/generated/openapi.json")))
  n_bytes="$(git diff --numstat "$BASE" | grep -c '^-')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴·키 자리 $n_key · 새 .xlsx/.csv/.ipynb/.json(generated 밖) $n_bin · 바이너리 $n_bytes · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_bytes" = 0 ] && [ "$n_name" = 0 ]
}

s13() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-349" "Derives-from: MARC-ENT-464" "Derives-from: MARC-ENT-421" \
    "Constraint: 계약 materiality.input@1 0바이트" "Directive: xlsx 방어는 translation/tools/glossary_xlsx.py 를 옮겨 적은 것" \
    "Co-Authored-By:"; do
    grep -q "^$t" "$MSG" && echo "  있음 $t" || { echo "  ★ 없음 $t"; code=1; }
  done
  return $code
}

s14() {  # 남의 모듈 import 0 — 새 파일(읽개·계약·actions·시험)이 materiality·core 밖 esgapi 를 들이지 않는다
  local files bad
  files="$(git ls-files -o --exclude-standard -- "$M"; git diff --name-only --diff-filter=A "$BASE" -- "$M")"
  bad="$(echo "$files" | grep '\.py$' | sort -u | while read -r f; do
    grep -n -E '^(from|import) esgapi\.' "$f" | grep -v -E 'esgapi\.(materiality|core)\b' | sed "s|^|$f:|"
  done)"
  echo "  새 파일 $(echo "$files" | grep -c '\.py$') · 남의 모듈 import $(echo "$bad" | grep -c .)"
  echo "$bad" | grep . | sed 's/^/  ★ /'
  [ -z "$bad" ]
}

step 1 "바뀐 경로가 §1-2·A0 안(OUTSIDE=0)" s1
step 2 "0바이트·0줄 목록 diff 0" s2
step 3 "허락 줄 「-」 ⊆ C0 표 · 묶음별 numstat·sha256 · docs 한 줄" s3
step 4 "lint-imports 전부 KEPT·수 = 기준 · tools 계약 줄" s4
step 5 "순수 시험 초록·수 · 쌍둥이" s5
step 6 "상한 여섯 = 50·200·20·50·200·100" s6
step 7 "generated/ 다시 뽑아 cmp · COMPONENTS_CHANGED=0 · PATHS_ADDED=1" s7
step 8 "check_test_layout·pyright·ruff" s8
step 9 "뿌리 verify.sh --fast" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무·보안(컨테이너 postgres)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
if [ "$PLANTED" = 1 ]; then
  step 11 "심은 파손(서버 몫 $EXPECT_PLANTED)" s11
else
  not_run 11 "심은 파손" "--planted 없음"
fi
step 12 "추가 줄의 키 꼴·새 .xlsx/.json·바이너리·실재 기업명 0" s12
if [ -n "$MSG" ]; then
  step 13 "커밋 메시지 트레일러" s13
fi
step 14 "남의 모듈 import 0" s14
echo "SECTION4_FAIL=$FAILS"
