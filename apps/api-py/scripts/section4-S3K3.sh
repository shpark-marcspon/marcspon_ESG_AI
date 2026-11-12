#!/usr/bin/env bash
# 밴드 S3K3(MARC-TICK-456)의 §3 자기검증 몫: 성공 결과 금 sha(5) · 0줄 경로(1) · 경계 줄(2). 밴드 몫·verify 밖.
#   사용: apps/api-py/scripts/section4-S3K3.sh [--step 1|2|3]
#   [1] 금 sha: 지어낸 템플릿 둘(엔진 시험 test_pipeline.all_sheets — 21키 전부 · resume 시험 SHEETS — 시트 일부) × 같은
#       모의 답으로 run_flow(scope3.colab@157) 결과 dict 의 json(sort_keys, ensure_ascii=False) sha256 = BASE 에서 잰 값(C0 ★D)
#   [2] 0줄 경로(§1-2): BASE..워크트리 diff 줄 0
#   [3] 경계 줄(7a 칸): BASE..HEAD numstat 빈 줄 · sha16 e3b0c44298fc1c14(빈 diff) · BASE..워크트리도 빈 줄(커밋 전에도 문다)
# 단계마다 「[n] … EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 공급사 호출 0(모의), 키 0. 뿌리 .git/verify.lock 이 있으면 돌지 않는다.
set -u
cd "$(dirname "$0")/../../.."
BASE=2ca8af52de0a7e406f580a9a3024b6212c0cb7dc
A=apps/api-py
I=$A/esgapi/inventory
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--step 1|2|3]" >&2; exit 2 ;;
  esac
done
COMMON="$(git rev-parse --git-common-dir)"
case "$COMMON" in /*) ;; *) COMMON="$(cd "$COMMON" && pwd)" ;; esac
if [ -e "$COMMON/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다(돌리지 않음)" >&2; exit 3; fi
FAILS=0
wanted() { [ -z "$ONLY" ] || [ "$ONLY" = "$1" ]; }
step() { # <n> <설명> <셸 글>
  local n="$1" desc="$2" code; shift 2
  echo; echo "[$n] $desc"
  (eval "$*"); code=$?
  echo "[$n] $desc EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
export A I BASE

GOLDEN_PY='
import hashlib, json
from esgapi.core.flows.run import run_flow
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.tests.engines.scope3.colab_157.support import ColabReplies, FakeGeocoder, activity_book, sheet, workbook, xlsx_bytes
from esgapi.inventory.tests.engines.scope3.colab_157.test_pipeline import all_sheets
from esgapi.inventory.tests.engines.scope3.colab_157.test_purchase import BOOK_ROWS, TAGS
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tests.flows import test_scope3_colab_157_resume as R

WANT = {
    "full21": "2b3492c3524bdde58d837040e142b45fb398a4f3f3669518e3fa634ed39be492",
    "partial": "f886c3f80bebf7d6659f9f4ca18931417de51dbcfae97b61a26780ea09cb9964",
}

def sha(body):
    return hashlib.sha256(json.dumps(body, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()

def full():
    inputs = colab.ColabInputs(template=xlsx_bytes(workbook(*all_sheets())), report_year=2025, route=ROUTE, tags=TAGS)
    book = activity_book(sheet("구매_USEPA", BOOK_ROWS))
    adapters = colab.ColabAdapters(llm=mock_client(ColabReplies()), factor_book=book, geocoder=FakeGeocoder())
    (only,) = run_flow(colab.FLOW, inputs, adapters).output.results
    return only

def part():
    (only,) = run_flow(colab.FLOW, R.inputs_of(R.SHEETS), R.adapters_of(R.Provider())).output.results
    return only

bad = 0
for name, fn in (("full21", full), ("partial", part)):
    got = sha(fn())
    mark = "같음" if got == WANT[name] else "★ 다름 (BASE " + WANT[name][:16] + ")"
    print("  " + name + " " + got[:16] + " " + mark)
    bad += got != WANT[name]
raise SystemExit(bad)
'
export GOLDEN_PY

if wanted 1; then
  step 1 "성공 결과 금 sha 둘 = BASE" '(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY -u GEMINI_API_KEY uv run --frozen python -c "$GOLDEN_PY")'
fi

if wanted 2; then
  step 2 "0줄 경로(§1-2): BASE..워크트리 diff 줄 0" '
    P="$I/engines $I/contracts $I/prompts $I/tools $I/service $I/models.py $I/migrations $I/flows/binding_157.py $A/esgapi/core $A/esgapi/runs $A/generated apps/web $A/pyproject.toml $A/uv.lock $A/.importlinter $A/esgapi/config"
    n="$(git diff "$BASE" -- $P | wc -l | tr -d " ")"; u="$(git status --porcelain --untracked-files=all -- $P | wc -l | tr -d " ")"
    echo "  diff ${n}줄 · 추적 밖 새 파일 ${u}"
    [ "$n" = 0 ] && [ "$u" = 0 ]'
fi

if wanted 3; then
  step 3 "경계 줄(7a 칸): numstat 빈 줄 · sha16" '
    P="$A/esgapi/core $A/esgapi/config $A/generated $A/tests/security $A/esgapi/runs"
    n="$(git diff --numstat "$BASE" HEAD -- $P | wc -l | tr -d " ")"
    h="$(git diff "$BASE" HEAD -- $P | shasum -a 256 | cut -c1-16)"
    w="$(git diff --numstat "$BASE" -- $P | wc -l | tr -d " ")"  # 커밋 전(스테이징·워크트리)도 BASE 와 견줌
    u="$(git status --porcelain --untracked-files=all -- $P | wc -l | tr -d " ")"
    echo "  HEAD $(git rev-parse --short HEAD) · numstat ${n}줄 · sha16 ${h} · BASE..워크트리 numstat ${w}줄 · 추적 밖·고친 것 ${u}"
    [ "$n" = 0 ] && [ "$h" = e3b0c44298fc1c14 ] && [ "$w" = 0 ] && [ "$u" = 0 ]'
fi

echo
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
