#!/usr/bin/env bash
# 밴드 TRP6(MARC-TICK-331: 영문번역 문서 쪽 수 GET /translation/documents/{document_id}/pages — 결정 MARC-ENT-452)의 §4
# 자기검증(발주서 band-handoffs/TRP6-order.md §4 — section4-IR3c.sh 꼴).
#   사용: apps/api-py/scripts/section4-TRP6.sh [--commit <n>] [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --commit n(1 서버 · 2 웹 · 3 가지 리뷰 상한, 기본 2)은 그 경계까지의 허락 목록·0줄 목록·수·심은 파손 몫으로 잰다.
#   --with-containers 면 단계 10(업무·보안 — 이 워크트리의 compose postgres 하나)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로
#   센다). --planted 면 단계 11. --msg 면 단계 13(커밋 메시지 초안의 트레일러). 웹 단계(14)는 ② 에서 더한다.
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 TRP6.out), TRP6_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
T="$E/translation"
S="$A/tests/security"
W=apps/web/src
OUT="${S4_OUT:-$ROOT/../TRP6.out}"
FORBIDDEN="${TRP6_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(3d7dd5c9)에서 잰 수: 순수 = pytest esgapi/translation -m "not django_db" 788 · 업무(translation·core·config) 456 ·
#   보안 437 · lint-imports 계약 17 · openapi 컴포넌트 358.
# 기대(늘기만): ① 순수 +45(test_page_tags) · 업무 +12(test_pages) · 보안 +6(ⓕ 다섯 + test_tenant_paths 의 401 매개 하나).
BASE_PURE=788 BASE_CONTRACTS=17 BASE_COMPONENTS=358 BASE_WEB=314
unset OPENAI_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY ANTHROPIC_API_KEY
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""; COMMIT=2
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--commit <n>] [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in
  1) EXPECT_PURE=833 EXPECT_PLANTED=13 EXPECT_BUSINESS=468 EXPECT_SECURITY=443 ;;
  2) EXPECT_PURE=833 EXPECT_PLANTED=15 EXPECT_BUSINESS=468 EXPECT_SECURITY=443 EXPECT_WEB=331 ;;
  # ③ 순수 +14(test_page_tags 가지 리뷰 상한) · 업무 +1(test_pages 쪽 상한 로그) · 심은 파손 +3(P16~P18) · 웹 그대로
  3) EXPECT_PURE=847 EXPECT_PLANTED=18 EXPECT_BUSINESS=469 EXPECT_SECURITY=443 EXPECT_WEB=331 ;;
  *) echo "--commit 은 1·2·3" >&2; exit 2 ;;
esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 TRP6 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

changed() {  # <기준> 뒤 바뀐 경로(추적 diff + 추적 안 된 새 파일)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2 영문번역 땅 + §1-3 허락 줄의 파일 — 경계 ① 몫(서버)
ALLOWED_1='apps/api-py/esgapi/translation/tools/page_tags\.py|apps/api-py/esgapi/translation/tests/tools/test_page_tags\.py|apps/api-py/esgapi/translation/service/actions/pages\.py|apps/api-py/esgapi/translation/contracts/pages_shapes\.py|apps/api-py/esgapi/translation/tests/service/actions/test_pages\.py|apps/api-py/esgapi/translation/service/apis/translation\.py|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|apps/api-py/tests/security/test_(translation|tenant_paths|login|operator_company)\.py|docs/development\.md|apps/api-py/scripts/(section4|planted-breaks)-TRP6\.sh|apps/api-py/esgapi/core/permissions\.py|apps/api-py/esgapi/core/tests/test_(permissions|permissions_wiring|transaction_rules)\.py|apps/api-py/esgapi/config/tests/test_api_(contract|errors)\.py|apps/api-py/esgapi/inventory/tests/test_s3sheets_is_pure\.py'
# §1-2 경계 ② 몫(웹 — 영문번역 슬라이스·화면·e2e)
ALLOWED_2='apps/web/src/entities/translation/api/(server|store|testing|server\.test)\.ts|apps/web/src/pages/translation-new/ui/(NewTranslationScreen\.tsx|NewTranslationScreen\.test\.tsx|PartRangeFields\.tsx)|apps/web/e2e/translation-server(\.spec)?\.ts'
case "$COMMIT" in
  1) ALLOWED="^($ALLOWED_1)$" ;;
  *) ALLOWED="^($ALLOWED_1|$ALLOWED_2)$" ;;
esac

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · OUTSIDE=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-2 끝(0바이트)·§1-3 끝(0줄)의 목록. 영문번역 기존 파일은 「새 파일·허락 파일 밖」으로 따로 본다(단계 2 의 둘째 셈).
# inventory 는 목록 시험 한 줄만(§1-3 밖 — 감독 허락 10-26, 허락 주인 온실가스 67) — 단계 3 이 +1/-0 으로 본다
INV_LIST="$E/inventory/tests/test_s3sheets_is_pure.py"
ZERO=("$T/engines" "$T/flows" "$T/outputs" "$T/tests/data" "$E/organization" "$E/user" "$E/runs" "$E/greenwash"
  "$E/dataverify" "$E/inventory" ":(exclude)$INV_LIST" "$E/materiality" "$E/reference" "$E/reconcile" "$A/.importlinter" "$E/config/api.py"
  "$A/gunicorn.conf.py" "$E/core/service/services/documents.py" "$E/core/service/selectors/documents.py"
  "$A/tests_integration" "$A/conftest.py" "$A/tests/support" "$S/conftest.py" "$S/seed.py" "$A/scripts/planted-breaks.sh"
  "$A/pyproject.toml" "$A/uv.lock" package.json pnpm-lock.yaml apps/web/package.json
  "$W/shared" "$W/app" "$W/widgets" "$W/entities/translation/model" "$W/entities/translation/ui"
  "$W/entities/translation/config" "$W/entities/translation/hooks" "$W/pages/translation-new/model")
[ "$COMMIT" = 1 ] && ZERO+=(apps/web)
# 영문번역 땅 안에서 바뀌어도 되는 것(나머지 기존 파일은 0바이트 — tools/docx_reader.py·contracts·actions 의 기존 파일 포함)
TR_OWN='esgapi/translation/(tools/page_tags|tests/tools/test_page_tags|service/actions/pages|contracts/pages_shapes|tests/service/actions/test_pages|service/apis/translation)\.py'
CORE_TABLE='esgapi/core/permissions\.py|esgapi/core/tests/test_(permissions|permissions_wiring|transaction_rules)\.py'

s2() {
  local n tr_out core_out grid
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  tr_out="$( { git diff --name-only "$BASE" -- "$T"; git ls-files -o --exclude-standard --full-name -- "$T"; } \
    | sed "s|^$A/||" | grep -v -E "^($TR_OWN)$" | grep -c .)"
  core_out="$(git diff --name-only "$BASE" -- "$E/core" | sed "s|^$A/||" | grep -v -E "^($CORE_TABLE)$" | grep -c .)"
  grid="$(git diff --name-only "$BASE" -- "$W/pages/translation-new/ui" | grep -c 'PageGrid')"
  echo "  0줄 목록 바뀐 파일 $n · 영문번역 땅의 허락 밖 $tr_out · core 표 밖 $core_out · PageGrid* $grid"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ] && [ "$tr_out" = 0 ] && [ "$core_out" = 0 ] && [ "$grid" = 0 ] || return 1
  # 요청 안에서 흐름의 문서 읽기·docx 읽개·python-docx 를 부르지 않는다(§1-5)
  if grep -n "read_document\|read_docx\|import docx" "$T/tools/page_tags.py" "$T/service/actions/pages.py"; then
    echo "  ★ 금지 이름이 있다"; return 1
  fi
  echo "  grep read_document·read_docx·import docx(page_tags·pages) 0줄"
}

# §1-3 허락 「-」 줄(기준의 파일:줄 — C0 보고 머리의 표, 71 e5 C0 통과·61 분류 확정 2026-10-26)
MINUS_ALLOWED='esgapi/core/permissions.py:46
esgapi/core/tests/test_permissions.py:225 esgapi/core/tests/test_permissions.py:239 esgapi/core/tests/test_permissions.py:273
esgapi/core/tests/test_permissions.py:343 esgapi/core/tests/test_permissions_wiring.py:334
esgapi/core/tests/test_transaction_rules.py:306
esgapi/config/tests/test_api_contract.py:256 esgapi/config/tests/test_api_contract.py:259
esgapi/config/tests/test_api_contract.py:276 esgapi/config/tests/test_api_contract.py:323
esgapi/config/tests/test_api_contract.py:335 esgapi/config/tests/test_api_contract.py:448
esgapi/config/tests/test_api_contract.py:449 esgapi/config/tests/test_api_contract.py:651
esgapi/config/tests/test_api_errors.py:67 esgapi/config/tests/test_api_errors.py:98
tests/security/test_login.py:284 tests/security/test_login.py:321 tests/security/test_operator_company.py:155
tests/security/test_tenant_paths.py:174 tests/security/test_tenant_paths.py:381 tests/security/test_tenant_paths.py:425
tests/security/test_tenant_paths.py:455 tests/security/test_tenant_paths.py:480 tests/security/test_tenant_paths.py:594
generated/api.d.ts:* generated/api.d.ts.source-sha256:* generated/openapi.json:*'

minus_lines() {  # 공유 경로의 「-」 줄을 <파일>:<기준 줄> 로
  git diff -U0 "$BASE" -- "$E/core" "$E/config" "$S" "$A/generated" | python3 -I -c '
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
  local code=0 got bad
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
  echo "  「-」 줄 $(echo "$got" | grep -c . ) · 허락 밖 $(echo "$bad" | grep -c .)"
  echo "$bad" | grep . | sed 's/^/  ★ /'
  [ -z "$bad" ] || code=1
  git diff --numstat "$BASE" -- "$E/core" "$E/config" "$S" "$A/generated" | sed 's/^/  numstat /'
  # 71(e5)에 보낼 값: core·config·generated·security·runs 의 diff sha256 16자(IR3c 꼴 — inventory 줄은 따로)
  git diff "$BASE" -- "$E/core" "$E/config" "$A/generated" "$S" "$E/runs" | shasum -a 256 \
    | cut -c1-16 | sed 's/^/  core·config·generated·security·runs diff sha256 16자 /'
  git diff "$BASE" -- "$E/core" "$E/config" | shasum -a 256 | cut -c1-16 | sed 's/^/  core·config diff sha256 16자 /'
  git diff "$BASE" -- "$S" | shasum -a 256 | cut -c1-16 | sed 's/^/  security diff sha256 16자 /'
  [ -z "$(git diff --name-only "$BASE" -- "$E/runs")" ] || { echo "  ★ runs 는 0줄"; code=1; }
  got="$(git diff --numstat "$BASE" -- "$INV_LIST" | awk '{print $1" "$2}')"
  echo "  inventory 목록 시험 numstat +${got% *}/-${got#* } (감독 허락 +1/-0 — 71 묶음 밖) · sha256 16자 $(git diff "$BASE" -- "$INV_LIST" | shasum -a 256 | cut -c1-16)"
  [ "$got" = "1 0" ] || code=1
  got="$(git diff --numstat "$BASE" -- docs/development.md | awk '{print $1" "$2}')"
  echo "  docs/development.md numstat +${got% *}/-${got#* } (허락 +1/-0)"
  [ "$got" = "1 0" ] || code=1
  return $code
}

s4() {
  local log kept broken
  log="$(cd "$A" && uv run --frozen lint-imports 2>&1)"
  echo "$log" > "$OUT/s4-lint-imports.log"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\2/p')"
  echo "  kept=$kept broken=$broken (기준 $BASE_CONTRACTS)"
  [ "$kept" = "$BASE_CONTRACTS" ] && [ "$broken" = 0 ]
}

s5() {
  local log n code
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/translation -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  if [ "$code" != 0 ] && echo "$log" | grep -q "test_the_attack_set_counts_within_two_seconds"; then
    echo "  시간 시험 빨강 — $(uptime | sed 's/.*load/load/') — 한 번 더"
    log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/translation -m "not django_db" 2>&1)"
    code=$?
    echo "$log" > "$OUT/s5-pure.log"
  fi
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  translation 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] || return 1
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/core esgapi/config -m "not django_db" 2>&1)"
  code=$?
  echo "  core·config(순수 몫) $(echo "$log" | tail -1)"
  [ "$code" = 0 ]
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
       | select($h[0].paths[$p][.key] != .value) | .value.operationId]}' > "$g/components.json" || return 1
  echo "  기준 컴포넌트 $(jq .base "$g/components.json") · COMPONENTS_CHANGED=$(jq '.changed | length' "$g/components.json") · COMPONENTS_ADDED=$(jq '.added | length' "$g/components.json") $(jq -c .added "$g/components.json") · PATHS_ADDED=$(jq '.paths | length' "$g/components.json") $(jq -c .paths "$g/components.json") · 없어진 path $(jq -c .pathsGone "$g/components.json") · 바뀐 동작 $(jq -c .pathsChanged "$g/components.json")"
  git diff --numstat "$BASE" -- "$A/generated" | sed 's/^/  numstat /'
  [ "$(jq .base "$g/components.json")" = "$BASE_COMPONENTS" ] || code=1
  [ "$(jq '.changed | length' "$g/components.json")" = 0 ] || code=1
  [ "$(jq '.pathsGone | length' "$g/components.json")" = 0 ] || code=1
  [ "$(jq '.pathsChanged | length' "$g/components.json")" = 0 ] || { echo "  ★ 바뀐 동작 0 이어야 한다"; code=1; }
  [ "$(jq -c .added "$g/components.json")" = '["TranslationDocumentPages"]' ] || { echo "  ★ 새 컴포넌트는 하나"; code=1; }
  [ "$(jq -c .paths "$g/components.json")" = '["/translation/documents/{document_id}/pages"]' ] \
    || { echo "  ★ 새 path 는 하나"; code=1; }
  return $code
}

s8() {
  local code=0
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s8-layout.log" 2>&1 || code=1
  tail -1 "$OUT/s8-layout.log" | sed 's/^/  layout /'
  (cd "$A" && uv run --frozen pyright esgapi/translation esgapi/core esgapi/config tests/security) > "$OUT/s8-pyright.log" 2>&1 || code=1
  tail -1 "$OUT/s8-pyright.log" | sed 's/^/  pyright /'
  (cd "$A" && uv run --frozen ruff check . && uv run --frozen ruff format --check .) > "$OUT/s8-ruff.log" 2>&1 || code=1
  tail -1 "$OUT/s8-ruff.log" | sed 's/^/  ruff /'
  bash -n "$A/scripts/planted-breaks-TRP6.sh" && /bin/bash -n "$A/scripts/section4-TRP6.sh" || code=1
  return $code
}

s9() {
  local log start
  start=$(date +%s)
  log="$(scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s9-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  [ $(( $(date +%s) - start )) -le 30 ] || echo "  30초 넘음 — $(uptime | sed 's/.*load/load/')"
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" bcode scode nb ns
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && scripts/test-business.sh -p no:cacheprovider esgapi/translation esgapi/core esgapi/config) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  nb="$(tail -1 "$blog" | sed -n 's/^\([0-9]*\) passed\(, \([0-9]*\) skipped\)\{0,1\}.*/\1 \3/p' | awk '{print $1 + $2}')"
  ns="$(tail -1 "$slog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  업무(translation·core·config) $(tail -1 "$blog") EXIT=$bcode (기대 $EXPECT_BUSINESS) · 보안 $(tail -1 "$slog") EXIT=$scode (기대 $EXPECT_SECURITY)"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ] && [ "$nb" = "$EXPECT_BUSINESS" ] && [ "$ns" = "$EXPECT_SECURITY" ]
}

s11() {
  local log
  log="$("$A/scripts/planted-breaks-TRP6.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s11-planted.log"
  echo "$log" | cut -c1-220 | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s12() {
  local d="$OUT/s12.diff" n_key n_bin n_name=0 n_bytes
  # 이 스크립트 자신은 무늬를 글자로 싣는다 — 뺀다
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-TRP6.sh"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-TRP6.sh" \
      | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb|docx|pdf)$')"
  n_bytes="$(git diff --numstat "$BASE" | grep -c '^-')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴·키 자리 $n_key · .xlsx/.csv/.ipynb/.docx/.pdf $n_bin · 바이너리 $n_bytes · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_bytes" = 0 ] && [ "$n_name" = 0 ]
}

s13() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-331" "Concerns: MARC-ISSUE-334" "Derives-from: MARC-ENT-452" \
    "Constraint: core confirm_upload 0줄" "Directive: 이 쪽 수는 그리드 표시용" "Not-tested:" "Co-Authored-By:"; do
    grep -q "^$t" "$MSG" && echo "  있음 $t" || { echo "  ★ 없음 $t"; code=1; }
  done
  if [ "$COMMIT" = 1 ]; then
    grep -q "^Constraint: 요청 안에서 read_document·python-docx 를 부르지 않음" "$MSG" || { echo "  ★ ① Constraint 없음"; code=1; }
  fi
  return $code
}

step 1 "바뀐 경로가 §1-2·§1-3 안(OUTSIDE=0)" s1
step 2 "0줄 목록 diff 0 · 영문번역 기존 파일 0바이트 · 금지 이름 grep 0" s2
step 3 "허락 줄 「-」 ⊆ C0 표 · numstat · sha256(71 에)" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험 초록·수(시간 시험 포함)" s5
step 7 "generated/ 다시 뽑아 cmp · PATHS_ADDED=1 · COMPONENTS_ADDED=1 · COMPONENTS_CHANGED=0" s7
step 8 "check_test_layout·pyright·ruff·bash -n" s8
step 9 "뿌리 verify.sh --fast" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무·보안(컨테이너 postgres 하나)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
if [ "$PLANTED" = 1 ]; then
  step 11 "심은 파손(경계 $COMMIT 까지의 몫 $EXPECT_PLANTED)" s11
else
  not_run 11 "심은 파손" "--planted 없음"
fi
s14() {  # ② 웹 — 영문번역 슬라이스·화면 vitest 수 · tsc · eslint · prettier · 웹 verify(포트는 감독이 준 S4_WEB_PORT·S4_WEB_TEST_PORT)
  local log code=0 n
  log="$(cd apps/web && pnpm exec vitest run src/entities/translation src/pages/translation-new 2>&1)" || code=1
  echo "$log" > "$OUT/s14-vitest.log"
  n="$(echo "$log" | sed -n 's/^ *Tests  \([0-9]*\) passed.*/\1/p')"
  echo "  vitest(영문번역 슬라이스·화면) $n passed (기준 $BASE_WEB → 기대 $EXPECT_WEB)"
  [ "$n" = "$EXPECT_WEB" ] || code=1
  (cd apps/web && pnpm exec tsc --noEmit && pnpm exec eslint src tools e2e && pnpm exec prettier --check src tools e2e) \
    > "$OUT/s14-static.log" 2>&1 || { echo "  ★ tsc·eslint·prettier"; code=1; }
  if [ -n "${S4_WEB_PORT:-}" ] && [ -n "${S4_WEB_TEST_PORT:-}" ]; then
    while [ -e .git/verify.lock ] || [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done
    WEB_PORT="$S4_WEB_PORT" WEB_TEST_PORT="$S4_WEB_TEST_PORT" apps/web/scripts/verify.sh > "$OUT/s14-web-verify.log" 2>&1
    grep -E "^VERIFY=" "$OUT/s14-web-verify.log" | sed 's/^/  /'
    grep -q "^VERIFY=PASS" "$OUT/s14-web-verify.log" || code=1
  else
    echo "  ★ 웹 verify 안 돌림(S4_WEB_PORT·S4_WEB_TEST_PORT 없음)"; code=1
  fi
  return $code
}

if [ "$COMMIT" -ge 2 ]; then
  step 14 "웹 vitest 수·tsc·eslint·prettier·웹 verify" s14
fi
step 12 "추가 줄의 키 꼴·자료 파일·바이너리·실재 기업명 0" s12
if [ -n "$MSG" ]; then
  step 13 "커밋 메시지 트레일러" s13
fi
echo "SECTION4_FAIL=$FAILS"
