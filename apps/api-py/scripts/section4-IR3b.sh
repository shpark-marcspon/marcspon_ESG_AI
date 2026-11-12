#!/usr/bin/env bash
# 밴드 IR3b(MARC-TICK-310: 중대성평가 IRO 결과 경로·운영 관리자 실행·엑셀 둘·MARC-ISSUE-367)의 §4 자기검증
# (발주서 band-handoffs/IR3b-order.md §4).
#   사용: apps/api-py/scripts/section4-IR3b.sh [--commit <n>] [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --commit n(1·2·3, 기본 3)은 그 경계까지의 허락 목록·0줄 목록·수·심은 파손 몫으로 잰다.
#   --with-containers 면 단계 10(업무·보안)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다). --planted 면 단계 11.
#   --msg 면 단계 13(커밋 메시지 초안의 트레일러).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 IR3b.out), IR3b_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
M="$E/materiality"
FS="$M/tests/data/flow-shapes"
OUT="${S4_OUT:-$ROOT/../IR3b.out}"
FORBIDDEN="${IR3b_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(153c90b1)에서 잰 수: 순수 = pytest esgapi/materiality -m "not django_db" 396(test_binding_155 67 → 기준 파일을
#   따로 모아 셈) · 업무 21 · lint-imports 계약 17 · openapi 컴포넌트 308.
# 기대(늘기만): ① 순수 +7(test_binding_155) · ② 업무 +10(service/apis 경로 5 · 운영 관리자 5).
BASE_PURE=396 BASE_CONTRACTS=17 BASE_COMPONENTS=308
unset OPENAI_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY ANTHROPIC_API_KEY
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""; COMMIT=3
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
  1) EXPECT_PURE=403 EXPECT_PLANTED=4 EXPECT_BUSINESS=21 ;;
  2) EXPECT_PURE=403 EXPECT_PLANTED=12 EXPECT_BUSINESS=31 ;;
  3) EXPECT_PURE=403 EXPECT_PLANTED=14 EXPECT_BUSINESS=31 ;;
  *) echo "--commit 은 1·2·3" >&2; exit 2 ;;
esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 IR3b §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-2 이 트랙 — 경계 ① 몫
ALLOWED_1='apps/api-py/esgapi/materiality/flows/binding_155\.py|apps/api-py/esgapi/materiality/tests/flows/test_binding_155\.py|apps/api-py/scripts/(section4|planted-breaks)-IR3b\.sh'
# §1-2 경계 ② 몫(경로 새 파일·업무 시험) + §1-3 허락 줄의 파일(core·config·generated·runs.py ·S/** 셈 줄 셋)
ALLOWED_2='apps/api-py/esgapi/materiality/api\.py|apps/api-py/esgapi/materiality/service/(__init__|apis/__init__|apis/materiality|actions/__init__|actions/result)\.py|apps/api-py/esgapi/materiality/tests/service/.*|apps/api-py/esgapi/materiality/tests/flows/test_runs_materiality\.py|apps/api-py/esgapi/core/permissions\.py|apps/api-py/esgapi/core/tests/test_(permissions|permissions_wiring|transaction_rules)\.py|apps/api-py/esgapi/config/api\.py|apps/api-py/esgapi/config/tests/test_api_(contract|errors)\.py|apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|apps/api-py/esgapi/runs/service/apis/runs\.py|apps/api-py/tests/security/test_(login|operator_company|tenant_paths)\.py'
# §1-2·§1-3 경계 ③ 몫(보안 시험 새 파일 · README·development 각 한 줄)
ALLOWED_3='apps/api-py/tests/security/test_materiality\.py|README\.md|docs/development\.md'
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

# §1-2 끝·§1-3 끝·§1-4 의 0줄 목록(경계 ① 은 공유 줄 전부도 0)
ZERO=("$M/contracts" "$FS" "$M/tests/data/examples" "$M/engines" "$M/prompts" "$M/outputs"
  "$M/flows/colab_155.py" "$M/flows/part2_155.py" "$M/flows/iro_155.py" "$M/flows/registration.py" "$M/apps.py"
  "$A/.importlinter" "$E/core/tests/test_flows_core_names.py" "$E/config/apps_list.py" "$E/runs/tests" "$E/user"
  "$E/dataverify" "$E/greenwash" "$E/translation" "$E/inventory" "$E/reference" "$E/organization" "$E/reconcile" apps/web
  "$A/tests_integration" "$A/conftest.py" "$A/tests/support" "$A/tests/security/conftest.py" "$A/tests/security/seed.py"
  "$A/scripts/planted-breaks.sh")
if [ "$COMMIT" = 1 ]; then
  ZERO+=("$E/core" "$E/runs" "$E/config" "$A/generated" "$A/tests/security" README.md docs/development.md
    "$M/api.py" "$M/service" "$M/tests/service" "$M/tests/flows/test_runs_materiality.py")
elif [ "$COMMIT" = 2 ]; then
  ZERO+=("$A/tests/security/test_materiality.py" README.md docs/development.md)
fi

s2() {
  local n
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ] || return 1
  # binding_155.py: _path 몸·_DICT_KEY_FIELDS(와 그 docstring)·머리말 한 줄 밖은 AST 가 기준과 같다
  git show "$BASE:$M/flows/binding_155.py" > "$OUT/s2-base-binding_155.py"
  python3 -I - "$OUT/s2-base-binding_155.py" "$M/flows/binding_155.py" <<'PYEOF'
import ast, sys
base_src, head_src = (open(p, encoding="utf-8").read() for p in sys.argv[1:3])
def rest(src):
    tree = ast.parse(src)
    body, skip_doc = [], False
    for i, node in enumerate(tree.body):
        if i == 0 and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            continue  # 머리말은 아래에서 줄로 잰다
        if skip_doc and isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant):
            skip_doc = False
            continue
        skip_doc = False
        if isinstance(node, ast.FunctionDef) and node.name == "_path":
            continue
        if isinstance(node, ast.AnnAssign) and getattr(node.target, "id", "") == "_DICT_KEY_FIELDS":
            skip_doc = True
            continue
        body.append(ast.dump(node))
    return body, ast.get_docstring(tree, clean=False) or ""
(b, bd), (h, hd) = rest(base_src), rest(head_src)
bl, hl = bd.splitlines(), hd.splitlines()
added = [l for l in hl if l not in bl]
doc_ok = len(hl) == len(bl) + 1 and [l for l in hl if l in bl] == bl and len(added) == 1
print(f"  binding_155 AST(_path·_DICT_KEY_FIELDS·머리말 밖) {'= 기준' if b == h else '★ 다름'} · 머리말 +{len(hl) - len(bl)}줄 {'(한 줄)' if doc_ok else '★'}")
sys.exit(0 if b == h and doc_ok else 1)
PYEOF
}

# §1-3 허락 「-」 줄(기준의 파일:줄 — C0 보고 머리의 표, e5·73 C0 통과 2026-10-26)
MINUS_ALLOWED='esgapi/core/permissions.py:7 esgapi/core/permissions.py:45 esgapi/core/permissions.py:125 esgapi/core/permissions.py:127
esgapi/core/tests/test_permissions.py:35 esgapi/core/tests/test_permissions.py:201 esgapi/core/tests/test_permissions.py:212
esgapi/core/tests/test_permissions.py:245 esgapi/core/tests/test_permissions.py:261 esgapi/core/tests/test_permissions.py:263
esgapi/core/tests/test_permissions.py:264 esgapi/core/tests/test_permissions.py:314
esgapi/core/tests/test_permissions_wiring.py:1 esgapi/core/tests/test_permissions_wiring.py:302
esgapi/core/tests/test_transaction_rules.py:306
esgapi/config/api.py:1 esgapi/config/api.py:3 esgapi/config/api.py:9
esgapi/config/tests/test_api_contract.py:238 esgapi/config/tests/test_api_contract.py:239 esgapi/config/tests/test_api_contract.py:254
esgapi/config/tests/test_api_contract.py:298 esgapi/config/tests/test_api_contract.py:308
esgapi/config/tests/test_api_errors.py:67 esgapi/config/tests/test_api_errors.py:95
esgapi/runs/service/apis/runs.py:148
tests/security/test_login.py:284 tests/security/test_login.py:318 tests/security/test_operator_company.py:147
tests/security/test_tenant_paths.py:360 tests/security/test_tenant_paths.py:401 tests/security/test_tenant_paths.py:429
tests/security/test_tenant_paths.py:453 tests/security/test_tenant_paths.py:565
generated/api.d.ts:* generated/api.d.ts.source-sha256:* generated/openapi.json:*'

minus_lines() {  # 공유 경로의 「-」 줄을 <파일>:<기준 줄> 로
  git diff -U0 "$BASE" -- "$E/core" "$E/config" "$E/runs" "$A/tests/security" "$A/generated" | python3 -I -c '
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
  if [ "$COMMIT" = 1 ]; then
    echo "  경계 ① — 허락 줄 0(공유 파일 diff 는 단계 2 가 0 으로 본다)"
    return 0
  fi
  got="$(minus_lines)"
  echo "$got" > "$OUT/s3-minus.txt"
  # 허락 목록에 「<파일>:*」 가 있으면 그 파일 전부(생성물)
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
  git diff --numstat "$BASE" -- "$E/core" "$E/config" "$E/runs" "$A/tests/security" "$A/generated" | sed 's/^/  numstat /'
  [ "$(git diff --name-only "$BASE" -- "$E/runs")" = "$E/runs/service/apis/runs.py" ] || { echo "  ★ runs 는 runs.py :148 뿐"; code=1; }
  if [ "$COMMIT" = 3 ]; then
    for f in README.md docs/development.md; do
      got="$(git diff --numstat "$BASE" -- "$f" | awk '{print $1" "$2}')"
      echo "  $f numstat +${got% *}/-${got#* } (허락 +1/-1)"
      [ "$got" = "1 1" ] || code=1
    done
  fi
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
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/materiality -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  materiality 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] || return 1
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/core/tests/test_permissions.py esgapi/config/tests/test_api_contract.py -m "not django_db" 2>&1)"
  code=$?
  echo "  test_permissions·test_api_contract(순수 몫) $(echo "$log" | tail -1)"
  [ "$code" = 0 ]
}

s6() {
  local code=0 g="$OUT/s6-shapes"
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && uv run --frozen python - "$g" <<'PYEOF') || return 1
import json, sys
from pathlib import Path
from esgapi.materiality.contracts import options_shapes, shapes
out = Path(sys.argv[1])
for name, adapter in {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES, **options_shapes.OPTIONS_SHAPES}.items():
    (out / f"{name}.schema.json").write_text(json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
  for pair in "materiality.options@1 options/" "materiality.input@1 " "materiality.result@1 " "materiality.result@2 "; do
    set -- $pair
    if cmp -s "$g/$1.schema.json" "$FS/${2:-}$1.schema.json"; then echo "  cmp $1 = 고정 파일"; else echo "  ★ cmp $1 ≠ 고정 파일"; code=1; fi
  done
  git diff --quiet "$BASE" -- "$FS" || { echo "  ★ 고정 스키마가 기준과 다름"; code=1; }
  return $code
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
  echo "  기준 컴포넌트 $(jq .base "$g/components.json") · COMPONENTS_CHANGED=$(jq '.changed | length' "$g/components.json") · 늘어남 $(jq '.added | length' "$g/components.json") · PATHS_ADDED=$(jq '.paths | length' "$g/components.json") $(jq -c .paths "$g/components.json") · 없어진 path $(jq -c .pathsGone "$g/components.json") · 바뀐 동작 $(jq -c .pathsChanged "$g/components.json")"
  jq -r '.added | join(" ")' "$g/components.json" | fold -s -w 110 | sed 's/^/    + /'
  [ "$(jq .base "$g/components.json")" = "$BASE_COMPONENTS" ] || code=1
  [ "$(jq '.changed | length' "$g/components.json")" = 0 ] || code=1
  [ "$(jq '.pathsGone | length' "$g/components.json")" = 0 ] || code=1
  if [ "$COMMIT" = 1 ]; then
    git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ 경계 ① 인데 generated/ 가 기준과 다름"; code=1; }
  else
    [ "$(jq -c .paths "$g/components.json")" = '["/materiality/runs/{run_id}/result"]' ] || { echo "  ★ 새 path 는 하나여야 한다"; code=1; }
    [ "$(jq -c .pathsChanged "$g/components.json")" = '["runs_create"]' ] || { echo "  ★ 바뀐 동작은 runs_create 하나(⑪)"; code=1; }
    [ "$(jq '.added | length' "$g/components.json")" = 35 ] || { echo "  ★ 늘어난 컴포넌트는 35(C0)"; code=1; }
  fi
  return $code
}

s8() {
  local code=0
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s8-layout.log" 2>&1 || code=1
  tail -1 "$OUT/s8-layout.log" | sed 's/^/  layout /'
  (cd "$A" && uv run --frozen pyright esgapi/materiality) > "$OUT/s8-pyright.log" 2>&1 || code=1
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
  [ $(( $(date +%s) - start )) -le 30 ] || echo "  30초 넘음 — $(uptime | sed 's/.*load/load/')"
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" mlog="$OUT/s10-materiality.log" bcode scode mcode n
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && scripts/test-business.sh -p no:cacheprovider esgapi/materiality) > "$mlog" 2>&1
  mcode=$?
  n="$(tail -1 "$mlog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  materiality 업무 $(tail -1 "$mlog") EXIT=$mcode (기대 $EXPECT_BUSINESS)"
  (cd "$A" && scripts/test-business.sh -n 4 -p no:cacheprovider esgapi/materiality esgapi/runs esgapi/config esgapi/core \
    esgapi/dataverify esgapi/greenwash esgapi/translation esgapi/user) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  업무(materiality·runs·config·core·dataverify·greenwash·translation·user) $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$mcode" = 0 ] && [ "$n" = "$EXPECT_BUSINESS" ] && [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s11() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$("$A/scripts/planted-breaks-IR3b.sh" --commit "$COMMIT" $flag 2>&1)"
  echo "$log" > "$OUT/s11-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s12() {
  local d="$OUT/s12.diff" n_key n_bin n_name=0 n_bytes
  # 이 스크립트 자신은 무늬를 글자로 싣는다 — 뺀다
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-IR3b.sh"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-IR3b.sh" \
      | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb)$')"
  n_bytes="$(git diff --numstat "$BASE" | grep -c '^-')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴·키 자리 $n_key · .xlsx/.csv/.ipynb $n_bin · 바이너리 $n_bytes · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_bytes" = 0 ] && [ "$n_name" = 0 ]
}

s13() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-310" "Concerns: MARC-ISSUE-367" "Constraint: 실호출 0" "Co-Authored-By:"; do
    grep -q "^$t" "$MSG" && echo "  있음 $t" || { echo "  ★ 없음 $t"; code=1; }
  done
  if [ "$COMMIT" = 1 ]; then
    grep -q "^Directive: 끼움 거절 문장에 사용자가 지은 dict 열쇠는" "$MSG" || { echo "  ★ ① Directive 없음"; code=1; }
  else
    grep -q "^Derives-from: MARC-ENT-419" "$MSG" || { echo "  ★ Derives-from 없음"; code=1; }
  fi
  if [ "$COMMIT" = 2 ]; then
    grep -q "^Directive: 운영 관리자 실행 모듈은 OPERATOR_RUN_MODULES 하나로" "$MSG" || { echo "  ★ ② Directive 없음"; code=1; }
    grep -q "^Constraint: 결과 계약 0바이트" "$MSG" || { echo "  ★ ② Constraint 없음"; code=1; }
  fi
  return $code
}

step 1 "바뀐 경로가 §1-2·§1-3 안(OUTSIDE=0)" s1
step 2 "0줄 목록 diff 0 · binding_155 AST" s2
step 3 "허락 줄 「-」 ⊆ C0 표 · numstat" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험 초록·수" s5
step 6 "고정 스키마 넷 다시 뽑아 cmp · 기준과 0바이트" s6
step 7 "generated/ 다시 뽑아 cmp · COMPONENTS_CHANGED=0 · PATHS_ADDED" s7
step 8 "check_test_layout·pyright·ruff" s8
step 9 "뿌리 verify.sh --fast" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무·보안(컨테이너 postgres)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
if [ "$PLANTED" = 1 ]; then
  step 11 "심은 파손(경계 $COMMIT 까지의 몫 $EXPECT_PLANTED)" s11
else
  not_run 11 "심은 파손" "--planted 없음"
fi
step 12 "추가 줄의 키 꼴·.xlsx/.csv/.ipynb·바이너리·실재 기업명 0" s12
if [ -n "$MSG" ]; then
  step 13 "커밋 메시지 트레일러" s13
fi
echo "SECTION4_FAIL=$FAILS"
