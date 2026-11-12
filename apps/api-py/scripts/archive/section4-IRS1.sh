#!/usr/bin/env bash
# 밴드 IRS1(MARC-TICK-374: IRO 서버 손질 — 엑셀 UTF-16 자름 · 비용 상한 한 자리 · (키워드 없음) 대조)의 §4 자기검증
# (발주서 band-handoffs/IRS1-order.md §4 — section4-IR3c.sh 꼴).
#   사용: apps/api-py/scripts/section4-IRS1.sh [--commit <n>] [--planted] [--msg <파일>] [--step <n>]
#   --commit n(1·2, 기본 2)은 그 경계까지의 허락 목록·수·심은 파손 몫으로 잰다. --planted 면 단계 8, --msg 면 단계 9.
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD(해시를 박지 않는다).
# 전량 scripts/verify.sh 는 돌리지 않는다. AI 공급사 호출 0(키 env 지움).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 IRS1.out), IRS1_FORBIDDEN(실재 기업명 낱말 파일, 기본 워크트리 곁의
#   G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
A=apps/api-py
M="$A/esgapi/materiality"
OUT="${S4_OUT:-$(cd "$ROOT/.." && pwd)/IRS1.out}"
FORBIDDEN="${IRS1_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
# <기준>(aff154be)에서 잰 수: 순수 = pytest esgapi/materiality -m "not django_db and not security" 726.
# 기대(늘기만): ① +7(test_xlsx 6 · test_final_xlsx 1) · ② +4(test_prompt_model_155 2 · test_binding_155 1 · test_wire 1).
BASE_PURE=726
unset OPENAI_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY ANTHROPIC_API_KEY
export LC_ALL=C

ONLY=""; PLANTED=0; MSG=""; COMMIT=2
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--commit <n>] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
ALLOWED_1="^$M/outputs/xlsx\.py$|^$M/tests/outputs/test_(final_)?xlsx\.py$|^$A/scripts/(section4|planted-breaks)-IRS1\.sh$"
ALLOWED_2="^$M/flows/(colab_155|binding_155|prompt_model_155)\.py$|^$M/contracts/wire\.py$"
ALLOWED_2="$ALLOWED_2|^$M/tests/flows/test_(prompt_model_155|binding_155)\.py$|^$M/tests/contracts/test_wire\.py$"
case "$COMMIT" in
  1) EXPECT_PURE=733 EXPECT_PLANTED=6 ALLOWED="$ALLOWED_1" ;;
  2) EXPECT_PURE=737 EXPECT_PLANTED=8 ALLOWED="$ALLOWED_1|$ALLOWED_2" ;;
  *) echo "--commit 은 1·2" >&2; exit 2 ;;
esac
ZERO="^$M/contracts/(shapes|options_shapes|digest_shapes|run_list_shapes|value_chain_shapes|ai_setting_shapes)\.py$"
ZERO="$ZERO|^$M/tests/data/|^$M/engines/|^$M/prompts/|^$M/outputs/(final_xlsx|digest)\.py$"
ZERO="$ZERO|^$M/flows/(iro_155|part2_155|registration)\.py$|^$M/(service|tools|migrations)/|^$M/(models|apps|api)\.py$"
ZERO="$ZERO|^$A/esgapi/(core|config|runs|dataverify|greenwash|translation|inventory|reference|organization|reconcile|user)/"
ZERO="$ZERO|^$A/\.importlinter$|^$A/generated/|^$A/tests/|^$A/tests_integration/|^apps/web/|README|^docs/"
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
mkdir -p "$OUT"
echo "── 밴드 IRS1 §4 · 경계 $COMMIT · 기준 ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
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

s1() {
  local all outside
  all="$(changed)"
  outside="$(echo "$all" | grep -v -E "$ALLOWED" | grep -c .)"
  echo "  바뀐 경로 $(echo "$all" | grep -c .) · OUTSIDE=$outside"
  echo "$all" | grep -v -E "$ALLOWED" | sed 's/^/  ★ /'
  [ "$outside" = 0 ]
}

s2() {
  local n
  n="$(changed | grep -c -E "$ZERO")"
  echo "  ZERO_CHANGED=$n"
  changed | grep -E "$ZERO" | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

s3() {
  local n
  n="$(git diff "$BASE" -- "$M/tests" | grep -c '^-[^-]')"
  echo "  시험 「-」 줄 $n"
  git diff "$BASE" -- "$M/tests" | grep '^-[^-]' | sed 's/^/  ★ /'
  [ "$n" = 0 ]
}

s4() {
  local code=0 files
  (cd "$A" && uv run --frozen lint-imports) > "$OUT/s4-lint-imports.log" 2>&1 || code=1
  grep -E "Contracts:" "$OUT/s4-lint-imports.log" | sed 's/^/  lint-imports /'
  (cd "$A" && uv run --frozen ruff check . && uv run --frozen ruff format --check .) > "$OUT/s4-ruff.log" 2>&1 || code=1
  tail -1 "$OUT/s4-ruff.log" | sed 's/^/  ruff /'
  files="$(changed | grep -E '\.py$' | sed "s#^$A/##")"
  # shellcheck disable=SC2086
  (cd "$A" && uv run --frozen pyright $files) > "$OUT/s4-pyright.log" 2>&1 || code=1
  tail -1 "$OUT/s4-pyright.log" | sed 's/^/  pyright /'
  return $code
}

s5() {
  local log n code
  log="$(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider esgapi/materiality -m "not django_db and not security" 2>&1)"
  code=$?
  echo "$log" > "$OUT/s5-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  materiality 순수 $(echo "$log" | tail -1) · 기준 $BASE_PURE → 기대 $EXPECT_PURE"
  [ "$code" = 0 ] && [ "$n" = "$EXPECT_PURE" ]
}

s6() {  # 새 인터프리터에서 각각 먼저 import(django 설정 없이). 고리는 fixed_groups() 부를 때만 나니 진짜 문은 ast 시험·P7
  local code=0 mod
  for mod in prompt_model_155 binding_155; do
    (cd "$A" && env -u DJANGO_SETTINGS_MODULE uv run --frozen python -c \
      "import esgapi.materiality.flows.$mod as m; import esgapi.materiality.flows.prompt_model_155 as pm; pm.fixed_groups()") \
      > "$OUT/s6-$mod.log" 2>&1
    local c=$?
    echo "  $mod 먼저 import · fixed_groups() EXIT=$c"
    [ "$c" = 0 ] || code=1
  done
  return $code
}

s7() {  # BMP 안 입력은 기준과 바이트 같다
  local base="$OUT/base" code
  rm -rf "$base" && mkdir -p "$base"
  git archive "$BASE" "$A" | tar -x -C "$base"
  for side in base head; do
    if [ "$side" = base ]; then pp="$base/$A"; else pp="$ROOT/$A"; fi
    # 작업본 .venv 의 파이썬을 그 쪽 사본 안에서 돌린다(sys.path[0] = 지금 폴더가 편집 설치보다 앞)
    (cd "$pp" && "$ROOT/$A/.venv/bin/python" - "$OUT/s7-$side.txt" <<'PY'
import json
import sys
from pathlib import Path

import esgapi
from esgapi.materiality.outputs import xlsx

ex = Path(esgapi.__file__).parent / "materiality" / "tests" / "data" / "examples"
out = []
for text in ["", "가", "a" * 32_767, "가" * 32_767, "가" * 32_768, "=" * 40_000, "가a\n" * 30_000, "가" * 70_000]:
    out.append(repr(xlsx.fit_cell(text)))
sample = json.loads((ex / "result-sample.json").read_text(encoding="utf-8"))
final = json.loads((ex / "result2-sample.json").read_text(encoding="utf-8"))
for n in (0, 32_767, 65_535, 70_000):
    sample["part1"]["topics"][1]["regulation"]["raw"] = "=" * n
    out.append(repr(xlsx.raw_json_chunks(sample)))
final["part2"]["topics"][0]["subtopics"][0]["impact"]["parsed"]["note"] = "가" * 70_000
out.append(repr(xlsx.raw_json_chunks(final)))
Path(sys.argv[1]).write_text(f"{xlsx.__file__}\n" + "\n".join(out), encoding="utf-8")
PY
    ) || return 1
  done
  head -1 "$OUT/s7-base.txt" | grep -q "^$base/" || { echo "  ★ 기준 쪽이 기준 사본을 읽지 않았다"; return 1; }
  tail -n +2 "$OUT/s7-base.txt" > "$OUT/s7-base.body"; tail -n +2 "$OUT/s7-head.txt" > "$OUT/s7-head.body"
  cmp -s "$OUT/s7-base.body" "$OUT/s7-head.body"
  code=$?
  echo "  BMP_SAME=$code ($(wc -c < "$OUT/s7-head.body" | tr -d ' ') 바이트)"
  [ "$code" = 0 ]
}

s8() {
  local log
  log="$(IRS1_OUT="$OUT" "$A/scripts/planted-breaks-IRS1.sh" --commit "$COMMIT" 2>&1)"
  echo "$log" > "$OUT/s8-planted.log"
  echo "$log" | grep -v -E '^    FAILED' | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk -v want="$EXPECT_PLANTED" '$1==$2 && $2==want{print "ok"}')" = ok ]
}

s9() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  if [ "$COMMIT" = 1 ]; then set -- "Ticket: MARC-TICK-374" "Concerns: MARC-ISSUE-425" "Co-Authored-By:"
  else set -- "Ticket: MARC-TICK-374" "Concerns: MARC-ISSUE-412, MARC-ISSUE-345" "Rejected: 엔진 constants 에 상한" \
    "Rejected: iro_155 에 상한" "Not-tested: 자정 경계 today" "Co-Authored-By:"; fi
  for t in "$@"; do
    grep -q "^$t" "$MSG" && echo "  있음 $t" || { echo "  ★ 없음 $t"; code=1; }
  done
  return $code
}

s10() {
  local d="$OUT/s10.diff" n_name=0 n_key
  # 이 스크립트 자신은 무늬를 글자로 싣는다 — 뺀다
  { git diff "$BASE" -- . ":(exclude)$A/scripts/section4-IRS1.sh"
    git ls-files -o --exclude-standard --full-name | grep -v -x "$A/scripts/section4-IRS1.sh" \
      | while read -r f; do git diff --no-index /dev/null "$f"; done; } > "$d" 2>/dev/null
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|marcspon-openai|spike/\.env')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다: $FORBIDDEN"; n_name=1
  fi
  echo "  키 꼴·키 자리 $n_key · 실재 기업명 낱말 $n_name"
  [ "$n_key" = 0 ] && [ "$n_name" = 0 ]
}

step 1 "바뀐 경로가 §1-1 안(OUTSIDE=0)" s1
step 2 "0바이트 목록(ZERO_CHANGED=0)" s2
step 3 "시험 「-」 줄 0" s3
step 4 "lint-imports·ruff·pyright" s4
step 5 "순수 시험 초록·수" s5
step 6 "고리 둘(각각 먼저 import)" s6
step 7 "BMP 안 입력은 기준과 바이트 같음(BMP_SAME=0)" s7
if [ "$PLANTED" = 1 ]; then
  step 8 "심은 파손(경계 $COMMIT 까지의 몫 $EXPECT_PLANTED)" s8
else
  not_run 8 "심은 파손" "--planted 없음"
fi
if [ -n "$MSG" ]; then step 9 "커밋 메시지 트레일러" s9; fi
step 10 "추가 줄의 키 꼴·실재 기업명 0" s10
echo "SECTION4_FAIL=$FAILS"
