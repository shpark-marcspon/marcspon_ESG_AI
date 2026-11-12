#!/usr/bin/env bash
# 밴드 DV1f(MARC-TICK-270: 데이터 검증 실행 옵션의 입력 출처 source)의 §4 자기검증(발주서 band-handoffs/DV1f-order.md §4).
#   사용: apps/api-py/scripts/section4-DV1f.sh [--with-containers] [--step <n>]
#   --with-containers 면 단계 9(업무)와 단계 10 의 업무 층을 돈다 — 안 주면 단계 9 는 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 DV1f.out), DV1f_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
DV="$E/dataverify"
FS="$DV/tests/data/flow-shapes"
OUT="${S4_OUT:-$ROOT/../DV1f.out}"
FORBIDDEN="${DV1f_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(926e7f98)에서 잰 수: 순수 = pytest esgapi/dataverify -m "not django_db" 416 · 업무(dataverify) 23.
# 기대(늘기만): 순수 +33(test_options_shapes 2 · test_binding_156 31) · 업무 +9(test_runs_dataverify).
BASE_PURE=416 EXPECT_PURE=449 BASE_BUSINESS=23 EXPECT_BUSINESS=32 EXPECT_PLANTED=8
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
echo "── 밴드 DV1f §4 · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1-2 수정 허용(닫힌 목록)
ALLOWED='^(apps/api-py/esgapi/dataverify/contracts/options_shapes\.py|apps/api-py/esgapi/dataverify/flows/binding_156\.py|apps/api-py/esgapi/dataverify/tests/data/flow-shapes/options/dataverify\.options@1\.schema\.json|apps/api-py/esgapi/dataverify/tests/.*|apps/api-py/scripts/(section4|planted-breaks)-DV1f\.sh)$'

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · outside=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

# §1-2 「0바이트」·§1-3 의 0줄 목록 + greenwash·translation·apps/web · §1-4 의 테스트 감독 몫
ZERO=("$DV/engines" "$DV/prompts" "$DV/flows/colab_156.py" "$DV/flows/registration.py" "$DV/outputs"
  "$DV/contracts/shapes.py" "$DV/contracts/wire.py" "$DV/apps.py" "$DV/service" "$DV/api.py"
  "$FS/dataverify.input@1.schema.json" "$FS/dataverify.result@2.schema.json" "$DV/tests/data/examples"
  "$E/core" "$E/config" "$E/runs" "$E/user" "$A/generated" "$A/tests/security" "$A/.importlinter" README.md docs
  "$E/greenwash" "$E/translation" apps/web "$A/tests_integration" "$A/conftest.py" "$A/tests/support")

s2() {
  local n
  n="$(git diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)"
  n=$((n + $(git ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)))
  echo "  0줄 목록 바뀐 파일 $n"
  git diff --name-only "$BASE" -- "${ZERO[@]}" | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

s3() {
  local log kept broken base
  base="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
  log="$(cd "$A" && uv run --frozen lint-imports 2>&1)"
  echo "$log" > "$OUT/s3-lint-imports.log"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken\.$/\2/p')"
  echo "  kept=$kept broken=$broken (기준 계약 $base)"
  [ "$kept" = "$base" ] && [ "$broken" = 0 ]
}

s4() {
  local log n code
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify \
    -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s4-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ]
}

s5() {
  local code=0 g="$OUT/s5-shapes"
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && uv run --frozen python - "$g" <<'PYEOF') || return 1
import json, sys
from pathlib import Path
from esgapi.dataverify.contracts import options_shapes, shapes
out = Path(sys.argv[1])
for name, adapter in {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES, **options_shapes.OPTIONS_SHAPES}.items():
    (out / f"{name}.schema.json").write_text(json.dumps(adapter.json_schema(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
PYEOF
  for pair in "dataverify.options@1 options/" "dataverify.input@1 " "dataverify.result@2 "; do
    set -- $pair
    if cmp -s "$g/$1.schema.json" "$FS/${2:-}$1.schema.json"; then echo "  cmp $1 = 고정 파일"; else echo "  ★ cmp $1 ≠ 고정 파일"; code=1; fi
  done
  [ "$(ls "$FS/options")" = "dataverify.options@1.schema.json" ] && echo "  options/ 고정 파일은 @1 하나" \
    || { echo "  ★ options/ 에 @1 말고 다른 파일"; code=1; }
  git diff --quiet "$BASE" -- "$FS/dataverify.input@1.schema.json" "$FS/dataverify.result@2.schema.json" \
    && echo "  input@1·result@2 = 기준" || { echo "  ★ input@1·result@2 가 기준과 다름"; code=1; }
  git diff --quiet "$BASE" -- "$FS/options/dataverify.options@1.schema.json" \
    && { echo "  ★ options@1 고정 파일이 기준 그대로(다시 뽑지 않음)"; code=1; } || echo "  options@1 다시 뽑음(기준과 다름)"
  return $code
}

s6() {
  local g="$OUT/s6-generated" code=0
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi) \
    > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    git show "$BASE:$A/generated/$f" > "$g/base-$f"
    if cmp -s "$g/$f" "$g/base-$f"; then echo "  cmp $f = 기준"; else echo "  ★ cmp $f ≠ 기준"; code=1; fi
  done
  return $code
}

s7() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py) > "$OUT/s7-layout.log" 2>&1
  local code=$?
  tail -1 "$OUT/s7-layout.log" | sed 's/^/  /'
  return $code
}

s8() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s8-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s9() {
  local dlog="$OUT/s9-dataverify.log" blog="$OUT/s9-business.log" dcode bcode n
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s9-up.log" 2>&1 || { tail -3 "$OUT/s9-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/dataverify) > "$dlog" 2>&1
  dcode=$?
  n="$(tail -1 "$dlog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 업무 $(tail -1 "$dlog") EXIT=$dcode (기준 $BASE_BUSINESS → 기대 $EXPECT_BUSINESS)"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/dataverify esgapi/runs) > "$blog" 2>&1
  bcode=$?
  echo "  업무(dataverify·runs) $(tail -1 "$blog") EXIT=$bcode"
  [ "$dcode" = 0 ] && [ "$n" = "$EXPECT_BUSINESS" ] && [ "$bcode" = 0 ]
}

s10() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-DV1f.sh" $flag 2>&1)"
  echo "$log" > "$OUT/s10-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s11() {
  local d="$OUT/s11.diff" n_key n_bin n_json n_name=0
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(xlsx|csv|ipynb)$')"
  n_json="$(changed | grep -E '\.json$' | grep -v -c -x "$FS/options/dataverify.options@1.schema.json")"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴 $n_key · .xlsx/.csv/.ipynb $n_bin · 고정 스키마 밖 .json $n_json · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_json" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-2 안(outside=0)" s1
step 2 "0줄 목록 diff 0" s2
step 3 "lint-imports 전부 KEPT·수 = 기준" s3
step 4 "순수 시험 초록·수(늘기만)" s4
step 5 "고정 스키마 다시 뽑아 cmp · input@1·result@2 = 기준" s5
step 6 "generated/ 다시 뽑아 기준과 바이트 같음" s6
step 7 "check_test_layout" s7
step 8 "뿌리 verify.sh --fast" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "업무(컨테이너 postgres — dataverify·runs)" s9
else
  not_run 9 "업무(컨테이너)" "--with-containers 없음"
fi
step 10 "심은 파손($EXPECT_PLANTED)" s10
step 11 "추적 diff 의 키 꼴·.xlsx/.csv/.ipynb·업로드 견본 .json·실재 기업명 0" s11
echo "SECTION4_FAIL=$FAILS"
