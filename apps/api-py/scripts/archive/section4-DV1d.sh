#!/usr/bin/env bash
# 밴드 DV1d(MARC-TICK-235: 데이터 검증 흐름 전역 등록·실행기 끼움)의 §4 자기검증(발주서 band-handoffs/DV1d-order.md §4).
#   사용: apps/api-py/scripts/section4-DV1d.sh [--with-containers] [--step <n>]
#   --with-containers 면 단계 10(업무·보안)과 단계 11 의 업무 층을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 DV1d.out), DV1d_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
DV="$E/dataverify"
OUT="${S4_OUT:-$ROOT/../DV1d.out}"
FORBIDDEN="${DV1d_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(fd613e0)에서 잰 수: 그 트리를 git archive 로 풀어 --collect-only.
#   순수 = pytest esgapi/dataverify -m "not django_db" 345 · lint-imports 계약 17.
# 기대(늘기만): 순수 +47(끼움 test_binding_156 40 · 앱 test_apps 3 · 옵션 꼴 test_options_shapes 4) · 업무 0 → 16.
BASE_PURE=345 EXPECT_PURE=392 BASE_CONTRACTS=17 EXPECT_BUSINESS=16
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

ONLY=""; CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "사용: $0 [--with-containers] [--step <n>]" >&2; exit 2 ;;
  esac
done
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 DV1d §4 · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

ALLOWED='^(apps/api-py/esgapi/dataverify/apps\.py|apps/api-py/esgapi/dataverify/flows/binding_156\.py|apps/api-py/esgapi/dataverify/contracts/options_shapes\.py|apps/api-py/esgapi/dataverify/tests/data/flow-shapes/options/dataverify\.options@1\.schema\.json|apps/api-py/esgapi/dataverify/tests/test_apps\.py|apps/api-py/esgapi/dataverify/tests/flows/test_binding_156\.py|apps/api-py/esgapi/dataverify/tests/flows/test_runs_dataverify\.py|apps/api-py/esgapi/dataverify/tests/contracts/test_options_shapes\.py|apps/api-py/esgapi/dataverify/tests/flows/support\.py|apps/api-py/esgapi/dataverify/flows/registration\.py|apps/api-py/esgapi/dataverify/flows/colab_156\.py|apps/api-py/esgapi/dataverify/tests/flows/test_registration\.py|apps/api-py/scripts/(section4|planted-breaks)-DV1d\.sh|apps/api-py/esgapi/config/apps_list\.py|apps/api-py/esgapi/config/tests/test_settings\.py|README\.md|docs/development\.md)$'

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · outside=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-4 0줄 + docstring 만 허락한 셋(docstring 뺀 AST 덤프가 <기준> 과 같음)
ZERO=("$DV/engines" "$DV/contracts/shapes.py" "$DV/contracts/wire.py" "$DV/outputs" "$DV/prompts"
  "$DV/tests/data/flow-shapes/dataverify.input@1.schema.json" "$DV/tests/data/flow-shapes/dataverify.result@1.schema.json"
  "$DV/tests/data/examples/result-sample.json" "$E/core" "$E/runs" "$E/config/api.py" "$A/generated" "$A/tests/security"
  "$A/tests_integration" "$A/conftest.py" "$A/tests/support" "$A/.importlinter" "$E/greenwash" "$E/translation" apps/web)
DOCSTRING_ONLY=("$DV/flows/registration.py" "$DV/flows/colab_156.py" "$DV/tests/flows/test_registration.py")

s2() {
  local code=0 n f
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  [ "$n" = 0 ] || code=1
  for f in "${DOCSTRING_ONLY[@]}"; do
    git show "$BASE:$f" > "$OUT/s2-base.py"
    if python3 -I - "$OUT/s2-base.py" "$f" <<'PYEOF'; then echo "  docstring 만: $f"; else echo "  ★ docstring 밖이 바뀜: $f"; code=1; fi
import ast, sys

def bare(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list) and body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) and isinstance(body[0].value.value, str):
            node.body = body[1:] or [ast.Pass()]
    return ast.dump(tree)

sys.exit(0 if bare(sys.argv[1]) == bare(sys.argv[2]) else 1)
PYEOF
  done
  return $code
}

# §1-3 공통 줄: 더하기만(README 만 -1/+1) — numstat 과 「-」 줄 원문
s3() {
  local code=0 f want got
  for pair in "$E/config/apps_list.py 1 0" "$E/config/tests/test_settings.py 1 0" "docs/development.md 1 0" "README.md 1 1"; do
    set -- $pair
    f="$1"; want="$2 $3"
    got="$(git diff --numstat "$BASE" -- "$f" | awk '{print $1" "$2}')"
    echo "  $f numstat +${got% *}/-${got#* } (허락 +$2/-$3)"
    [ "$got" = "$want" ] || code=1
  done
  echo "  README 의 「-」 줄:"
  git diff "$BASE" -- README.md | grep -E '^-[^-]' | sed 's/^/    /'
  git diff "$BASE" -- README.md | grep -E '^-[^-]' | grep -q '^-| 데이터 검증 |' || code=1
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
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify \
    -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ] || return 1
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/config/tests/test_settings.py esgapi/core/tests/test_flows_core_names.py -m "not django_db" 2>&1)"
  code=$?
  echo "  test_settings·test_flows_core_names $(echo "$log" | tail -1)"
  [ "$code" = 0 ]
}

s6() {
  local code=0 g="$OUT/s6-shapes"
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && uv run --frozen python - "$g" <<'PYEOF') || return 1
import json, sys
from pathlib import Path
from esgapi.dataverify.contracts import options_shapes, shapes
out = Path(sys.argv[1])
for name, adapter in {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES, **options_shapes.OPTIONS_SHAPES}.items():
    (out / f"{name}.schema.json").write_text(json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
  for pair in "dataverify.options@1 options/" "dataverify.input@1 " "dataverify.result@1 "; do
    set -- $pair
    if cmp -s "$g/$1.schema.json" "$DV/tests/data/flow-shapes/${2:-}$1.schema.json"; then echo "  cmp $1 = 고정 파일"; else echo "  ★ cmp $1 ≠ 고정 파일"; code=1; fi
  done
  git diff --quiet "$BASE" -- "$DV/tests/data/flow-shapes/dataverify.input@1.schema.json" \
    "$DV/tests/data/flow-shapes/dataverify.result@1.schema.json" || { echo "  ★ input@1·result@1 이 기준과 다름"; code=1; }
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
  git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ generated/ 가 기준과 다름"; code=1; }
  return $code
}

s8() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s8-layout.log" 2>&1
  local code=$?
  tail -1 "$OUT/s8-layout.log" | sed 's/^/  /'
  return $code
}

s9() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s9-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" dlog="$OUT/s10-dataverify.log" bcode scode dcode n
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/dataverify) > "$dlog" 2>&1
  dcode=$?
  n="$(tail -1 "$dlog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -n 4 -p no:cacheprovider esgapi/dataverify \
    esgapi/runs esgapi/config esgapi/core esgapi/greenwash esgapi/translation) > "$blog" 2>&1
  bcode=$?
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$slog" 2>&1
  scode=$?
  echo "  dataverify 업무 $(tail -1 "$dlog") EXIT=$dcode (기대 $EXPECT_BUSINESS)"
  echo "  업무(dataverify·runs·config·core·greenwash·translation) $(tail -1 "$blog") EXIT=$bcode · 보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$dcode" = 0 ] && [ "$n" = "$EXPECT_BUSINESS" ] && [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s11() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-DV1d.sh" $flag 2>&1)"
  echo "$log" > "$OUT/s11-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2 && $2==14{print "ok"}')" = ok ]
}

s12() {
  local d="$OUT/s12.diff" n_key n_bin n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb)$')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .xlsx/.csv/.ipynb $n_bin · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2·§1-3 안(outside=0)" s1
step 2 "§1-4 0줄 · docstring 만 셋은 AST 같음" s2
step 3 "공통 줄 numstat·「-」 줄 원문" s3
step 4 "lint-imports 전부 KEPT·수 = 기준" s4
step 5 "순수 시험(dataverify not django_db · test_settings · test_flows_core_names) 초록·수" s5
step 6 "고정 스키마 셋 다시 뽑아 cmp" s6
step 7 "generated/ 다시 뽑아 0바이트" s7
step 8 "check_test_layout" s8
step 9 "뿌리 verify.sh --fast" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무·보안(컨테이너 postgres)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 11 "심은 파손 14(P1~P12·P12b·P14)" s11
step 12 "추적 diff 의 키 꼴·.xlsx/.csv/.ipynb·실재 기업명 0" s12
echo "SECTION4_FAIL=$FAILS"
