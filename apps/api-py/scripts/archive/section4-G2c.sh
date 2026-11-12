#!/usr/bin/env bash
# 밴드 G2c-1(MARC-TICK-187: 판정 기준표 — EVAL 을 고정 틀 + greenwash.criteria@1 로)의 §4 자기검증
# (발주서 band-handoffs/G2c-order.md §4, 개정 2).
#   사용: apps/api-py/scripts/section4-G2c.sh --commit <2|3> [--step <n>]
#   --commit 2 는 커밋 ①② 경계(단계 10 의 심은 파손이 열둘), 3 은 ③ 경계(열다섯).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# <기준> = git merge-base main HEAD(발주서 선결 2 — 해시를 박지 않는다). 전량 scripts/verify.sh 는 돌리지 않는다(감독
# 몫). 컨테이너 0. AI 공급사 호출 0 — 시험은 env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY.
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 G2c.out — 심은 파손에도 G2C_OUT 으로 넘긴다), G2C_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
G="$A/esgapi/greenwash"
OUT="${S4_OUT:-$ROOT/../G2c.out}"   # 로그 자리. 검증자는 S4_OUT 로 따로 둔다(러너 로그를 덮지 않게)
FORBIDDEN="${G2C_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
BASE_TESTS=462   # <기준>(0b076a7)에서 잰 pytest -q esgapi/greenwash 의 수(G2c.out/pytest-greenwash-base.log)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit <2|3> [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 2 | 3) ;; *) echo "--commit <2|3> 이 필요하다" >&2; exit 2 ;; esac
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
echo "기준 $BASE · HEAD $(git rev-parse HEAD) · --commit $COMMIT"
mkdir -p "$OUT"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2"; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

# §1-2 수정 허용(닫힌 목록)
ALLOWED='^apps/api-py/esgapi/greenwash/contracts/criteria_shapes\.py$
^apps/api-py/esgapi/greenwash/contracts/__init__\.py$
^apps/api-py/esgapi/greenwash/flows/criteria_e0\.py$
^apps/api-py/esgapi/greenwash/flows/colab_e0\.py$
^apps/api-py/esgapi/greenwash/README\.md$
^apps/api-py/esgapi/greenwash/tests/contracts/test_criteria_shapes\.py$
^apps/api-py/esgapi/greenwash/tests/flows/test_criteria_e0\.py$
^apps/api-py/esgapi/greenwash/tests/flows/test_criteria_flow\.py$
^apps/api-py/esgapi/greenwash/tests/flows/support\.py$
^apps/api-py/esgapi/greenwash/tests/data/flow-shapes/criteria/greenwash\.criteria@1\.schema\.json$
^apps/api-py/esgapi/greenwash/tests/data/contract-examples/criteria/criteria-(default|edited)\.json$
^apps/api-py/scripts/section4-G2c\.sh$
^apps/api-py/scripts/planted-breaks-G2c\.sh$'

s1() {
  local all outside
  all="$(changed)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$(echo "$ALLOWED" | paste -sd'|' -)" | grep -c . )"
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside"
  [ "$outside" -eq 0 ]
}

# §1-3 0줄(바이트 그대로) — <기준> 에 있는 자리인지도 센다
ZERO="$G/engines $G/prompts $G/contracts/shapes.py $G/contracts/review_shapes.py $G/contracts/compare_shapes.py
$G/contracts/terms_shapes.py $G/contracts/wire.py $G/tests/data/golden $G/tests/data/gw1-ast-sha256.txt
$G/tests/test_copy_ast.py $G/tests/data/flow-shapes/greenwash.result@1.schema.json $G/tests/data/flow-shapes/terms
$G/tests/data/flow-shapes/review $G/tests/data/flow-shapes/compare $G/tests/data/contract-examples/result-normal.json
$G/tests/data/contract-examples/result-dry-run.json $G/tests/data/contract-examples/result-no-pages.json
$G/tests/data/contract-examples/result-many.json $G/tests/data/contract-examples/review
$G/tests/data/contract-examples/compare $G/flows/registration.py $G/flows/rewrite_r1.py $G/service $G/api.py
$G/outputs $G/tools $G/tests/flows/test_colab_e0.py $A/.importlinter $A/esgapi/config $A/esgapi/core $A/tests/security
$A/pyproject.toml $A/uv.lock $A/generated README.md scripts apps/web compose.yaml docker infra"

s2() {
  local missing=0 p n bad
  for p in $ZERO; do
    n="$(git ls-tree -r --name-only "$BASE" -- "$p" | grep -c .)"
    [ "$n" -gt 0 ] || { echo "  ★ <기준> 에 없는 자리: $p"; missing=$((missing + 1)); }
  done
  # shellcheck disable=SC2086
  bad="$( { git diff --name-only "$BASE" -- $ZERO; git ls-files -o --exclude-standard --full-name -- $ZERO; } | sort -u)"
  mig="$(changed | grep -c '/migrations/')"
  echo "  0줄 자리 $(echo $ZERO | wc -w | tr -d ' ') · <기준> 에 없는 자리 $missing · 바뀐 것 $(echo "$bad" | grep -c .) · migrations $mig"
  [ -n "$bad" ] && echo "$bad" | sed 's/^/  ★ /'
  [ -z "$bad" ] && [ "$missing" -eq 0 ] && [ "$mig" -eq 0 ]
}

s3() {
  local f="$G/flows/colab_e0.py"
  git diff -U0 "$BASE" -- "$f" | grep -E '^(@@|[-+])' | grep -v -E '^(\+\+\+|---) ' | sed 's/^/  /'
  python3 - "$BASE" "$f" <<'PY'
import subprocess, sys
base, f = sys.argv[1], sys.argv[2]
num = subprocess.run(["git", "diff", "--numstat", base, "--", f], capture_output=True, text=True, check=True).stdout.split()
removed = int(num[1]) if num else 0
diff = subprocess.run(["git", "diff", "-U0", base, "--", f], capture_output=True, text=True, check=True).stdout
names = ("LlmChatBridge", "GreenwashInputs", "judge", "_judge", "_scan_pages", "__init__", "__post_init__")
heads = [l[1:].strip() for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
bad = [h for h in heads if h.startswith(("def ", "class ")) and not any(h.split()[1].startswith(n + "(") or h.split()[1].startswith(n + ":") or h.split()[1] == n for n in names)]
print(f"  지운 줄 {removed}(한도 40) · 이름 밖의 def/class 지움 {bad}")
sys.exit(0 if removed <= 40 and not bad else 1)
PY
}

s4() { (cd "$A" && uv run --frozen lint-imports 2>&1 | tail -3 | sed 's/^/  /'; exit "${PIPESTATUS[0]}"); }

s5() {
  local log="$OUT/s5-pytest.log" code total new
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/greenwash) > "$log" 2>&1
  code=$?
  total="$(grep -E '^[0-9]+ passed' "$log" | sed -E 's/^([0-9]+) passed.*/\1/')"
  new="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider --collect-only \
    $(ls esgapi/greenwash/tests/contracts/test_criteria_shapes.py esgapi/greenwash/tests/flows/test_criteria_e0.py \
      esgapi/greenwash/tests/flows/test_criteria_flow.py 2>/dev/null) | grep -c '::')"
  tail -1 "$log" | sed 's/^/  /'
  echo "  기준 $BASE_TESTS + 새 $new = $((BASE_TESTS + new)) · 지금 ${total:-?}"
  [ "$code" -eq 0 ] && [ "${total:-0}" -eq $((BASE_TESTS + new)) ]
}

s6() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider \
    esgapi/greenwash/tests/test_copy_ast.py 2>&1 | tail -1 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s7() {
  local p="$G/tests/data/golden/sample-mock.json" a b
  a="$(git show "$BASE:$p" | shasum -a 256 | cut -d' ' -f1)"
  b="$(shasum -a 256 "$p" | cut -d' ' -f1)"
  echo "  <기준> $a · 지금 $b"
  [ -n "$a" ] && [ "$a" = "$b" ]
}

s8() {
  (cd "$A" && uv run --frozen python -c '
import hashlib, sys
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows.criteria_e0 import build_eval_prompt, default_criteria
built = hashlib.sha256(build_eval_prompt(default_criteria(), PROMPT_VERSION).encode("utf-8")).hexdigest()
engine = hashlib.sha256(default_prompts(PROMPT_VERSION).eval_system_prompt.encode("utf-8")).hexdigest()
print(f"  조립 {built}\n  엔진 {engine}")
sys.exit(0 if built == engine else 1)
')
}

s9() {
  local log="$OUT/s9-verify-fast.log"
  scripts/verify.sh --fast > "$log" 2>&1
  local code=$?
  tail -1 "$log" | sed 's/^/  /'
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "VERIFY_FAST=PASS" ]
}

s10() {
  local log="$OUT/s10-planted.log"
  G2C_OUT="$OUT" "$A/scripts/planted-breaks-G2c.sh" --commit "$COMMIT" > "$log" 2>&1
  local code=$?
  grep -E '^\[|^FINGERPRINT|^PLANTED' "$log" | sed 's/^/  /'
  local want=12; [ "$COMMIT" = 3 ] && want=16   # 16 = 가지 리뷰 3
  [ "$code" -eq 0 ] && [ "$(tail -1 "$log")" = "PLANTED=$want/$want" ]
}

s11() {
  local all keys bin lab words body
  all="$(changed)"
  # 추가 줄: <기준> 에 있던 파일은 diff 의 + 줄, 새 파일은 전부. 키 꼴은 이 스크립트(정규식 글자)를 빼고 본다
  body="$(for f in $all; do
    if git cat-file -e "$BASE:$f" 2>/dev/null; then git diff "$BASE" -- "$f" | grep -E '^\+' | grep -v -E '^\+\+\+ ';
    elif [ -f "$f" ]; then sed "s|^|+$f:|" "$f"; fi; done)"
  keys="$(echo "$body" | grep -v -F "+$A/scripts/section4-G2c.sh:" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|OPENAI_API_KEY=[^[:space:]"$]')"
  bin="$(echo "$all" | grep -c -E '\.(pdf|xlsx|ipynb)$')"
  # esg-lab 언급은 더한 줄에서(기준에 이미 있던 README 머리 글 등은 이 밴드 것이 아니다). 이 스크립트 둘(정규식 글자)은 뺀다
  lab="$(echo "$body" | grep -v -E "^\+$A/scripts/(section4|planted-breaks)-G2c\.sh:" | grep -c -E 'esg-lab|py/greenwash')"
  if [ -f "$FORBIDDEN" ]; then words="$(echo "$body" | grep -c -i -F -f "$FORBIDDEN")"; else words="파일 없음"; fi
  echo "  키 꼴 $keys · pdf/xlsx/ipynb $bin · esg-lab 언급(더한 줄) $lab(이 스크립트 둘 뺌) · 실재 기업명(추가 줄) $words"
  [ "$keys" -eq 0 ] && [ "$bin" -eq 0 ] && [ "$lab" -eq 0 ] && [ "$words" = 0 ]
}

step 1 "바뀐 파일이 §1-2 안" s1
step 2 "0줄 목록 diff 0(§1-3)" s2
step 3 "colab_e0.py 의 diff 가 §2-4 자리 안" s3
step 4 "lint-imports 전부 KEPT" s4
step 5 "pytest esgapi/greenwash 초록, 수 = 기준 + 새" s5
step 6 "test_copy_ast(엔진 아홉 AST 그대로)" s6
step 7 "골든 sample-mock.json sha256 = <기준>" s7
step 8 "기본 판 조립 sha256 = 엔진 EVAL sha256" s8
step 9 "verify.sh --fast" s9
step 10 "심은 파손" s10
step 11 "키 꼴·바이너리·esg-lab·실재 기업명 0" s11
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
