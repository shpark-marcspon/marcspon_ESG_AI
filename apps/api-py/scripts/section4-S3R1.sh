#!/usr/bin/env bash
# 밴드 S3R1(MARC-TICK-448)의 §4 자기검증 몫 둘: esg-lab 대조(assemble 길)와 경계 줄. 밴드 몫·verify 밖.
#   사용: apps/api-py/scripts/section4-S3R1.sh [--step 1|2]
#   [1] esg-lab 여덟 판: 코랩 쪽만 돌려 입력을 짓고(esg-lab 추적 파일 0줄, 산출 esg-lab/out/S3R1/) → 엔진 쪽은
#       순서 답(esg-lab 답 파일)을 한 번 돌기로 열쇠별 답에 옮겨 적고 → 그 답으로 흐름을 단계째 돌려 일지를 짓고 →
#       assemble_run 의 ColabRun 으로 엔진 JSON·결과 파일·채운 템플릿(S3C-c2 길, tests/scope3colab_dump.py) →
#       `python -m scope3colab run --input <판> --engine-result … --engine-result-file … --engine-filled-file …` 종료 0.
#       판마다 「공급사 한 번 = 단계」 「assemble 실제 0」 도 본다.
#   [2] 경계 줄(7a 칸 전부): numstat 빈 줄 · 바이너리 0 · sha16(같은 경로 목록).
# 단계마다 「[n] … EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 공급사 호출 0(모의), 키 0.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=8dda222342eb7c88c8df90241ff700e15e6c5422
A=apps/api-py
LAB="$(cd "$ROOT/../../esg-lab" && pwd)"
LABOUT="$LAB/out/S3R1"
ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 [--step 1|2]" >&2; exit 2 ;;
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
export ROOT A LAB LABOUT BASE

lab_answers() {
  case "$1" in
    base | base-v22) echo "$LAB/py/scope3colab/answers.synthetic.json" ;;
    distance | distance-v22 | distance-v22map) echo "$LAB/py/scope3colab/answers.distance.synthetic.json" ;;
    distance-transport) echo "$LAB/py/scope3colab/answers.distance-transport.synthetic.json" ;;
    rest) echo "$LAB/py/scope3colab/answers.rest.synthetic.json" ;;
    filled) echo "$LAB/py/scope3colab/answers.filled.synthetic.json" ;;
  esac
}
export -f lab_answers

ENGINE_PY='
import hashlib, json, sys
from pathlib import Path
from esgapi.core.flows.run import run_flow
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRun, run
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.flows.scope3_journal_157 import Entry, call_key, entry_of, read_entries, result_of
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tests import scope3colab_dump as dump

template, book_path, answers, out_json, rf, ff = (Path(a) for a in sys.argv[1:7])

class Recorder:
    def __init__(self, inner):
        self.inner, self.by_key = inner, {}
    def call(self, request):
        got = self.inner.call(request)
        key = call_key(request)
        self.by_key.setdefault(key, []).append(entry_of(key, got))
        return got

class Keyed:
    def __init__(self, by_key):
        self.by_key, self.used, self.calls = by_key, {}, 0
    def call(self, request):
        key = call_key(request)
        n = self.used.get(key, 0)
        self.used[key] = n + 1
        self.calls += 1
        return result_of(self.by_key[key][n])

ordered = dump.OrderedAnswers(dump.load_answers(answers))
recorder = Recorder(mock_client(ordered))
book = dump.read_book(book_path)
tpl = dump.read_book(template)
once = run(tpl, book, 2025, recorder, dump.RecordingGeocoder(), dump.TAGS, ROUTE)
assert isinstance(once, ColabRun) and not ordered.problems, ordered.problems
assert ordered.used == len(ordered.answers), "짜 둔 답이 다 쓰이지 않았다"
one_calls = sum(len(v) for v in recorder.by_key.values())
inputs = colab.ColabInputs(template=template.read_bytes(), report_year=2025, route=ROUTE, tags=dump.TAGS)
stepped = Keyed(recorder.by_key)
flowed = run_flow(colab.FLOW, inputs, colab.ColabAdapters(llm=stepped, factor_book=book, geocoder=dump.RecordingGeocoder()))
journal = [e for s in colab.CATEGORY_STEPS for e in read_entries(flowed.steps[s].data["journal"])]
again = Keyed(recorder.by_key)
result = colab.assemble_run(inputs, colab.ColabAdapters(llm=again, factor_book=book, geocoder=dump.RecordingGeocoder()), journal)
assert isinstance(result, ColabRun)
assert again.calls == 0, f"assemble 실제 호출 {again.calls}"
assert stepped.calls == one_calls, f"공급사 단계 {stepped.calls} ≠ 한 번 {one_calls}"
out_json.write_text(json.dumps(dump.rows_of(result.sheets, tpl), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
files = dump.output_files(result)
rf.write_bytes(dump.write_result_file(files.result))
ff.write_bytes(dump.write_filled_template(template.read_bytes(), files.writes))
print(f"  공급사 한 번 {one_calls} = 단계 {stepped.calls} · assemble 실제 {again.calls}")
'
export ENGINE_PY

if wanted 1; then
  step 1 "esg-lab 대조 여덟 판(assemble_run 길) — 판마다 대조 종료 0 · 공급사 같음 · assemble 실제 0" '
    bad=0; mkdir -p "$LABOUT"
    for v in base distance-transport distance rest base-v22 distance-v22 distance-v22map filled; do
      (cd "$LAB/py" && uv run --frozen --group scope3colab python -m scope3colab run --input "$v" --out "$LABOUT/$v" > "$LABOUT/$v.colab.log" 2>&1) || { echo "  ★ $v 입력 짓기 실패"; bad=1; continue; }
      tp="$(find "$LABOUT/$v/inputs" -maxdepth 1 -name "*.xlsx" | head -1)"; bk="$(find "$LABOUT/$v/inputs" -mindepth 2 -name "*.xlsx" | head -1)"
      rf="$LABOUT/$v.engine_result.xlsx"; ff="$LABOUT/$v.engine_filled.xlsx"
      (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -c "$ENGINE_PY" "$tp" "$bk" "$(lab_answers "$v")" "$LABOUT/$v.engine.json" "$rf" "$ff" 2> "$LABOUT/$v.engine.err"); dc=$?
      (cd "$LAB/py" && uv run --frozen --group scope3colab python -m scope3colab run --input "$v" --out "$LABOUT/$v-cmp" --engine-result "$LABOUT/$v.engine.json" --engine-result-file "$rf" --engine-filled-file "$ff" > "$LABOUT/$v-cmp.log" 2>&1); c=$?
      echo "  $v: 엔진(assemble) EXIT=$dc · 대조 EXIT=$c"
      [ "$dc$c" = 00 ] || bad=1
    done
    [ "$bad" = 0 ]'
fi

if wanted 2; then
  step 2 "경계 줄(7a 칸 전부): numstat 빈 줄 · 바이너리 0 · sha16" '
    P="$A/esgapi/core $A/esgapi/config $A/esgapi/runs $A/generated $A/tests/security $A/.importlinter $A/pyproject.toml $A/uv.lock"
    n="$(git diff --numstat "$BASE" HEAD -- $P | wc -l | tr -d " ")"
    b="$(git diff --numstat "$BASE" HEAD -- $P | grep -c "^-")"
    h="$(git diff "$BASE" HEAD -- $P | shasum -a 256 | cut -c1-16)"
    w="$(git status --porcelain -- $P | wc -l | tr -d " ")"
    echo "  HEAD $(git rev-parse --short HEAD) · numstat ${n}줄 · 바이너리 ${b} · sha16 ${h} · 워크트리 안 고친 것 ${w}"
    [ "$n" = 0 ] && [ "$b" = 0 ] && [ "$w" = 0 ]'
fi

echo
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
