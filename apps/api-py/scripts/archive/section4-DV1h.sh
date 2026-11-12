#!/usr/bin/env bash
# 밴드 DV1h(MARC-TICK-294: 흔들리는 이름 꼬리 시험 · 주석 넷)의 §4 자기검증(발주서 band-handoffs/DV1h-order.md §4).
#   사용: apps/api-py/scripts/section4-DV1h.sh [--with-containers] [--step <n>]
#   --with-containers 면 단계 7(업무)·9(심은 파손의 업무 층)·10(30번 반복)을 돈다 — 안 주면 7·10 은 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키). 로그 자리 S4_OUT(기본 워크트리 곁의 DV1h.out).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
DV="$E/dataverify"
FS="$DV/tests/data/flow-shapes"
TB="esgapi/dataverify/tests/flows/test_binding_156.py"
TR="esgapi/dataverify/tests/flows/test_runs_dataverify.py"
OUT="${S4_OUT:-$ROOT/../DV1h.out}"
# <기준>(6a7d22ec)에서 잰 수: 순수 = pytest esgapi/dataverify -m "not django_db" 493 · 업무(dataverify) 61.
# 기대: 순수 그대로 · 업무 +1(test_runs_dataverify 의 test_the_name_tail_is_not_hex — 모듈이 django_db).
EXPECT_PURE=493 EXPECT_BUSINESS=62 EXPECT_PLANTED=4 REPEAT=30
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
echo "── 밴드 DV1h §4 · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

# §1 수정 허용(닫힌 목록)
ALLOWED='^(apps/api-py/esgapi/dataverify/tests/flows/test_runs_dataverify\.py|apps/api-py/esgapi/dataverify/tests/flows/test_binding_156\.py|apps/api-py/esgapi/dataverify/contracts/wire\.py|apps/api-py/esgapi/dataverify/contracts/shapes\.py|apps/api-py/esgapi/dataverify/flows/colab_156\.py|apps/api-py/scripts/(section4|planted-breaks)-DV1h\.sh)$'
# 주석·docstring 만 허용하는 실행 코드 파일
CODE=("$DV/contracts/wire.py" "$DV/contracts/shapes.py" "$DV/flows/colab_156.py")

s1() {
  local all staged outside sout
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  staged="$(git diff --cached --name-only)"
  sout="$(echo "$staged" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · outside=$outside · 스테이징 $(echo "$staged" | grep -c .) · 스테이징 outside=$sout"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ] && [ "$sout" = 0 ]
}

s2() {
  local n
  n="$(changed | grep -v "^$DV/" | grep -v -E '^apps/api-py/scripts/(section4|planted-breaks)-DV1h\.sh$' | grep -c .)"
  echo "  esgapi/dataverify 밖 바뀐 파일(이 밴드 스크립트 둘 밖) $n"
  [ "$n" = 0 ]
}

s3() {  # 고정 스키마 셋을 다시 뽑아 기준과 cmp · generated/ 셋을 다시 뽑아 기준과 cmp
  local g="$OUT/s3-shapes" code=0 f
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
    git show "$BASE:$FS/${2:-}$1.schema.json" > "$g/base-$1.schema.json"
    if cmp -s "$g/$1.schema.json" "$g/base-$1.schema.json"; then echo "  cmp $1 = 기준"; else echo "  ★ cmp $1 ≠ 기준"; code=1; fi
  done
  git diff --quiet "$BASE" -- "$FS" "$A/generated" && echo "  flow-shapes·generated 추적 diff 0" \
    || { echo "  ★ flow-shapes·generated 가 기준과 다름"; code=1; }
  (cd "$A" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi) \
    > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    git show "$BASE:$A/generated/$f" > "$g/base-$f"
    if cmp -s "$g/$f" "$g/base-$f"; then echo "  cmp generated/$f = 기준"; else echo "  ★ cmp generated/$f ≠ 기준"; code=1; fi
  done
  return $code
}

s4() {  # 실행 코드 줄 diff 0 — 주석은 AST 에 없고, docstring(문 자리의 글자 식)은 지우고 견준다
  local d="$OUT/s4-ast" code=0 f
  rm -rf "$d" && mkdir -p "$d"
  for f in "${CODE[@]}"; do
    git show "$BASE:$f" > "$d/base.py"
    (cd "$A" && uv run --frozen python - "$d/base.py" "$ROOT/$f" <<'PYEOF')
import ast, sys

def bare(path: str) -> str:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            node.body = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                                                 and isinstance(s.value.value, str))] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)

sys.exit(0 if bare(sys.argv[1]) == bare(sys.argv[2]) else 1)
PYEOF
    if [ $? = 0 ]; then echo "  AST(docstring 뺌) = 기준: $f"; else echo "  ★ 실행 코드가 바뀜: $f"; code=1; fi
  done
  return $code
}

s5() {
  local n
  n="$(grep -rn 9b2e "$DV" | grep -c .)"
  echo "  grep -rn 9b2e esgapi/dataverify: $n"
  [ "$n" = 0 ]
}

s6() {
  local log n code
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify \
    -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s6-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 순수 $(echo "$log" | tail -1) · 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ]
}

up_postgres() {
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/up.log" 2>&1 || { tail -3 "$OUT/up.log"; return 1; }
  fi
}

s7() {
  local dlog="$OUT/s7-business.log" code n
  up_postgres || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/dataverify) > "$dlog" 2>&1
  code=$?
  n="$(tail -1 "$dlog" | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  dataverify 업무 $(tail -1 "$dlog") EXIT=$code · 기대 $EXPECT_BUSINESS"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_BUSINESS" ]
}

s8() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s8-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s9() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-DV1h.sh" $flag 2>&1)"
  echo "$log" > "$OUT/s9-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s10() {  # 고친 두 시험 파일을 REPEAT 번 — 꼬리가 우연히 걸리지 않는 것을 숫자로(업무 층은 --reuse-db)
  local i green=0 log="$OUT/s10-repeat" code bcode
  rm -rf "$log" && mkdir -p "$log"
  up_postgres || return 1
  for i in $(seq 1 "$REPEAT"); do
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" "$TB") \
      > "$log/$i-pure.log" 2>&1
    code=$?
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --reuse-db "$TR") \
      > "$log/$i-business.log" 2>&1
    bcode=$?
    if [ "$code" = 0 ] && [ "$bcode" = 0 ]; then green=$((green + 1)); else echo "  ★ $i 회차 빨강 — $log/$i-*.log"; fi
  done
  echo "  REPEAT=$green/$REPEAT($(tail -1 "$log/1-pure.log") · $(tail -1 "$log/1-business.log"))"
  [ "$green" = "$REPEAT" ]
}

step 1 "바뀐 경로·스테이징이 §1 안(outside=0)" s1
step 2 "esgapi/dataverify 밖 diff 0" s2
step 3 "고정 스키마·generated 다시 뽑아 기준과 바이트 같음" s3
step 4 "실행 코드 줄 diff 0(주석·docstring 밖)" s4
step 5 "grep -rn 9b2e esgapi/dataverify 0" s5
step 6 "순수 시험 초록·수" s6
if [ "$CONTAINERS" = 1 ]; then
  step 7 "업무(컨테이너 postgres — dataverify)" s7
else
  not_run 7 "업무(컨테이너)" "--with-containers 없음"
fi
step 8 "뿌리 verify.sh --fast" s8
step 9 "심은 파손($EXPECT_PLANTED)" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "고친 두 시험 파일 ${REPEAT}번 반복" s10
else
  not_run 10 "${REPEAT}번 반복(업무 층)" "--with-containers 없음"
fi
echo "SECTION4_FAIL=$FAILS"
