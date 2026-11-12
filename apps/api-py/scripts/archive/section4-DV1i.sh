#!/usr/bin/env bash
# 밴드 DV1i(MARC-TICK-345: 꼬리 단언 조임 · openapi 이름 겹침 시험 · 운영 관리자 낡은 문구)의 §4 자기검증
# (발주서 band-handoffs/DV1i-order.md §4). 틀은 section4-DV1h.sh 그대로다.
#   사용: apps/api-py/scripts/section4-DV1i.sh [--with-containers] [--step <n>]
#   --with-containers 면 단계 6(업무)·8(심은 파손의 업무 층)·9(10번 반복)를 돈다 — 안 주면 6·9 는 「안 돌림」(EXIT=1 로 센다).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). AI 공급사 호출 0(env -u 키). 로그 자리 S4_OUT(기본 워크트리 곁의 DV1i.out).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
TR="esgapi/dataverify/tests/flows/test_runs_dataverify.py"
TO="esgapi/runs/tests/service/apis/test_runs_operator.py"
TC="esgapi/config/tests/test_api_component_names.py"
OP2="$A/scripts/planted-breaks-OP2.sh"
OUT="${S4_OUT:-$ROOT/../DV1i.out}"
EXPECT_PLANTED=4 REPEAT=10
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
echo "── 밴드 DV1i §4 · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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
ALLOWED='^(apps/api-py/esgapi/dataverify/tests/flows/test_runs_dataverify\.py|apps/api-py/esgapi/config/tests/test_api_component_names\.py|apps/api-py/esgapi/runs/tests/service/apis/test_runs_operator\.py|apps/api-py/scripts/planted-breaks-OP2\.sh|apps/api-py/scripts/(section4|planted-breaks)-DV1i\.sh)$'

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

s2() {  # generated/ 셋을 다시 뽑아 기준과 cmp(실행 코드가 안 바뀌었으니 계약 문서도 그대로)
  local g="$OUT/s2-generated" code=0 f
  rm -rf "$g" && mkdir -p "$g"
  git diff --quiet "$BASE" -- "$A/generated" && echo "  generated 추적 diff 0" || { echo "  ★ generated 가 기준과 다름"; code=1; }
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

s3() {  # test_runs_operator.py 는 docstring 만(AST 에서 docstring 을 지우면 기준과 같음) · OP2 는 CREATE_CHECK 의 글 한 줄만
  local d="$OUT/s3-text" code=0 minus plus want
  rm -rf "$d" && mkdir -p "$d"
  git show "$BASE:$A/$TO" > "$d/base.py"
  (cd "$A" && uv run --frozen python - "$d/base.py" "$ROOT/$A/$TO" <<'PYEOF')
import ast, sys

def bare(path: str) -> str:
    tree = ast.parse(open(path, encoding="utf-8").read())
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if isinstance(body, list):
            node.body = [s for s in body if not (isinstance(s, ast.Expr) and isinstance(s.value, ast.Constant)
                                                 and isinstance(s.value.value, str))] or [ast.Pass()]
    return ast.dump(tree, include_attributes=False)

def doc(path: str) -> str:
    return ast.get_docstring(ast.parse(open(path, encoding="utf-8").read()), clean=False) or ""

same = bare(sys.argv[1]) == bare(sys.argv[2])
moved = doc(sys.argv[1]) != doc(sys.argv[2])
print(f"  {sys.argv[2].split('/apps/api-py/')[1]}: AST(docstring 뺌) {'= 기준' if same else '★ ≠ 기준'} · 머리말 {'바뀜' if moved else '★ 그대로'}")
sys.exit(0 if same and moved else 1)
PYEOF
  [ $? = 0 ] || code=1
  minus="$(git diff -U0 "$BASE" -- "$OP2" | grep -E '^-[^-]')"
  plus="$(git diff -U0 "$BASE" -- "$OP2" | grep -E '^\+[^+]')"
  want="$(sed -n '/if principal.kind == "admin" and body.module not in OPERATOR_RUN_MODULES:/{n;p;}' "$E/runs/service/apis/runs.py" | sed 's/^ *//')"
  echo "  OP2 − $(echo "$minus" | grep -c .)줄 + $(echo "$plus" | grep -c .)줄 · runs.py 원문: $want"
  [ "$(echo "$minus" | grep -c .)" = 1 ] && [ "$(echo "$plus" | grep -c .)" = 1 ] || { echo "  ★ OP2 diff 가 한 줄이 아님"; code=1; }
  echo "$minus" | grep -q "ApplicationError" || code=1
  echo "$plus" | grep -qF "    '        $want\\n'" || { echo "  ★ OP2 의 + 줄이 runs.py 원문과 다름"; code=1; }
  return $code
}

s4() {  # 실행 코드 줄 diff 0 — 바뀐 경로가 시험·심기 스크립트뿐
  local n
  n="$(changed | grep -v -E '/tests/|^apps/api-py/scripts/' | grep -c .)"
  echo "  tests/·scripts/ 밖 바뀐 파일 $n"
  [ "$n" = 0 ]
}

s5() {  # config 순수(새 이름 겹침 시험 포함)
  local log code
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/config \
    -m "not django_db" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-config-pure.log"
  echo "  config 순수 $(echo "$log" | tail -1)"
  [ "$code" = 0 ]
}

up_postgres() {
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/up.log" 2>&1 || { tail -3 "$OUT/up.log"; return 1; }
  fi
}

s6() {  # 업무: test_runs_dataverify(꼬리) · test_runs_operator(머리말만 바뀜)
  local dlog="$OUT/s6-business.log" code
  up_postgres || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider "$TR" "$TO") > "$dlog" 2>&1
  code=$?
  echo "  업무 $(tail -1 "$dlog") EXIT=$code"
  [ "$code" = 0 ]
}

s7() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  echo "$log" > "$OUT/s7-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY_FAST=PASS"
}

s8() {
  local log flag=""
  [ "$CONTAINERS" = 1 ] && flag="--with-containers"
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-DV1i.sh" $flag 2>&1)"
  echo "$log" > "$OUT/s8-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s9() {  # 새 config 시험과 고친 test_runs_dataverify 를 REPEAT 번(업무 층은 --reuse-db)
  local i green=0 log="$OUT/s9-repeat" code bcode
  rm -rf "$log" && mkdir -p "$log"
  up_postgres || return 1
  for i in $(seq 1 "$REPEAT"); do
    (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db" "$TC") \
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
step 2 "generated 다시 뽑아 기준과 바이트 같음" s2
step 3 "test_runs_operator 는 docstring 만 · OP2 는 CREATE_CHECK 글 한 줄 = runs.py 원문" s3
step 4 "실행 코드 줄 diff 0(tests/·scripts/ 밖 0)" s4
step 5 "config 순수 초록" s5
if [ "$CONTAINERS" = 1 ]; then
  step 6 "업무(컨테이너 postgres — 꼬리·운영 관리자 시험)" s6
else
  not_run 6 "업무(컨테이너)" "--with-containers 없음"
fi
step 7 "뿌리 verify.sh --fast" s7
step 8 "심은 파손($EXPECT_PLANTED)" s8
if [ "$CONTAINERS" = 1 ]; then
  step 9 "새 config 시험·고친 꼬리 시험 ${REPEAT}번 반복" s9
else
  not_run 9 "${REPEAT}번 반복(업무 층)" "--with-containers 없음"
fi
echo "SECTION4_FAIL=$FAILS"
