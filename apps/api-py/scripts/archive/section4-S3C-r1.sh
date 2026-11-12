#!/usr/bin/env bash
# 밴드 S3C-r1(MARC-TICK-354: 읽개 openpyxl·pandas 꼴 241 + 코랩과 다르게 옮긴 자리 395)의 §4 자기검증. 꼴은 section4-S3C-c2.sh.
#   사용: apps/api-py/scripts/section4-S3C-r1.sh --commit 1|2 [--step <n>]
#   커밋 둘 — 단계 0~9. 기록은 워크트리 밖(/private/tmp/s3cr1.*).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(병합 뒤 테스트 감독 몫). 업무(django_db)·보안 층, 컨테이너도 안 돌린다. AI 공급사 호출 0.
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=4ee85e0d   # 워크트리를 세운 main(merge band/S3C-c2, 2026-10-28) = 발주서의 4ee85e0d
A=apps/api-py
E="$A/esgapi"
I="$E/inventory"
C="$I/engines/scope3/colab_157"
SCHEMA="$I/tests/data/flow-shapes/scope3.colab.result@1.schema.json"
export LC_ALL=C

COMMIT=""; ONLY=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit 1|2 [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit 1|2 가 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/s3cr1.XXXXXX)"
case "$T" in /private/tmp/s3cr1.*) ;; *) exit 99 ;; esac
FAILS=0

wanted() { # <단계>
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ] || return 1
  case "$1" in
    0 | 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8 | 9) return 0 ;;
    *) return 1 ;;
  esac
}
step() { # <n> <설명> <셸 글>
  local n="$1" desc="$2" code
  shift 2
  echo
  echo "[$n] $desc"
  (eval "$*")
  code=$?
  echo "[$n] $desc EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
added_lines() { # 이 밴드 스크립트 둘을 뺀 diff 의 더한 줄(추적 안 된 새 파일 포함)
  git diff "$BASE" -- "$A" ":(exclude)$A/scripts/section4-S3C-r1.sh" ":(exclude)$A/scripts/planted-breaks-S3C-r1.sh" | grep "^+" | grep -v "^+++"
  git ls-files --others --exclude-standard -- "$A" ":(exclude)$A/scripts/section4-S3C-r1.sh" ":(exclude)$A/scripts/planted-breaks-S3C-r1.sh" \
    | while IFS= read -r f; do sed "s/^/+/" "$f"; done
}
export -f added_lines
export ROOT BASE A E I C T COMMIT SCHEMA

echo "── 밴드 S3C-r1 §4 · 커밋 $COMMIT · BASE ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"

# ── 0. BASE 머리 ──
if wanted 0; then
  step 0 "BASE ⊂ HEAD(발주서 머리 4ee85e0d) · 4ee85e0d..BASE apps/api-py 차이 0" '
    git merge-base --is-ancestor "$BASE" HEAD; h=$?
    git diff --quiet 4ee85e0d "$BASE" -- "$A"; f=$?
    echo "  BASE ⊂ HEAD EXIT=$h · 4ee85e0d..BASE apps/api-py diff EXIT=$f"
    [ "$h$f" = 00 ]'
fi

# ── 1. inventory 시험 ──
if wanted 1; then
  step 1 "pytest inventory 전량(순수 — django_db·security 표지 제외)" '(cd "$A" && s=$(date +%s); env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi/inventory > "$T/inv.txt" 2>&1; code=$?; e=$(date +%s); tail -1 "$T/inv.txt"; echo "  걸린 시간 $((e - s))초"; exit $code)'
fi

# ── 2. import 계약 ──
if wanted 2; then
  step 2 "lint-imports 0 broken + inventory 계약 다섯 kept" '
    (cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1); code=$?
    tail -1 "$T/lint.txt"
    miss=0
    for c in inventory-engine-not-contracts inventory-contracts-not-engines inventory-tools-know-no-axis inventory-engines-apart inventory-scope3-versions-apart; do
      grep -q "^\[importlinter:contract:$c\]" "$A/.importlinter" || { echo "  ★ 계약 $c 가 .importlinter 에 없다"; miss=1; }
    done
    grep -q "0 broken" "$T/lint.txt"; b=$?
    [ "$code" = 0 ] && [ "$b" = 0 ] && [ "$miss" = 0 ]'
fi

# ── 3. 0줄 경로 ──
if wanted 3; then
  # 두 커밋 공통(발주서 1-2): 읽개 허용 목록 시험·grid·계약·고정 스키마·serialize·frames 등·경계 경로
  P0="$I/tests/test_s3sheets_is_pure.py $I/tools/scope3_sheets $I/contracts $I/tests/data/flow-shapes $I/tests/flows/test_vocab.py $I/tests/test_flows.py $I/flows $I/prompts $C/serialize.py $C/frames.py $C/template.py $C/factor_book.py $C/activity.py $E/core $E/config $A/.importlinter $A/generated $E/runs $E/organization $E/reconcile/tests $A/tests/security $E/translation $I/README.md"
  if [ "$COMMIT" = 1 ]; then
    P0="$P0 $I/engines $I/tests/engines"  # 커밋 1 은 엔진 0줄
  else  # 커밋 2: ⑥ 그대로라 purchase 도 0줄(감독 보정 4)
    for f in spend waste transport travel travel_mode distance company_mapping pdcompat llm ports units constants purchase; do P0="$P0 $C/$f.py"; done
  fi
  export P0
  step 3 "1-2 0줄 경로(커밋 $COMMIT — 양성 대조 포함)" '
    for p in $P0; do n="$(git ls-files -- "$p" | wc -l | tr -d " ")"; [ "$n" -gt 0 ] || { echo "  ★ 추적 파일 0 인 경로(양성 대조 실패): $p"; exit 1; }; done
    git diff --quiet "$BASE" -- $P0; code=$?
    new="$(git ls-files --others --exclude-standard -- $P0 | wc -l | tr -d " ")"
    git diff --stat "$BASE" -- $P0 | tail -5 | sed "s/^/  /"
    echo "  경로 $(echo $P0 | wc -w | tr -d " ")개 · git diff EXIT=$code · 추적 안 된 새 파일 $new"
    t=0
    if [ "$COMMIT" = 2 ]; then
      c1="$(git log --format=%H --grep="^Ticket: MARC-TICK-354" "$BASE..HEAD" | tail -1)"
      [ -n "$c1" ] || { echo "  ★ 커밋 1 을 못 찾음"; exit 1; }
      git diff --quiet "$c1" -- "$I/tools" "$I/tests/test_s3sheets_reader.py" "$I/tests/test_s3sheets_reader_limits.py" "$I/tests/scope3colab_dump.py" "$I/tests/test_scope3colab_dump.py"; t=$?
      echo "  tools·읽개 시험·dump 가 커밋 1(${c1:0:8})과 같음 EXIT=$t"
    fi
    [ "$code" = 0 ] && [ "$new" = 0 ] && [ "$t" = 0 ]'
fi

# ── 4. 의존성 ──
if wanted 4; then
  step 4 "의존성 0줄: pyproject.toml uv.lock" '
    git diff --quiet "$BASE" -- "$A/pyproject.toml" "$A/uv.lock"; d=$?
    echo "  diff EXIT=$d"; [ "$d" = 0 ]'
fi

# ── 5. 타입·꼴 ──
if wanted 5; then
  step 5 "pyright 0 errors · ruff check · ruff format --check · 더한 완화 줄 0" '
    (cd "$A" && uv run --frozen pyright > "$T/pyright.txt" 2>&1); p=$?; tail -1 "$T/pyright.txt"
    (cd "$A" && uv run --frozen ruff check esgapi/inventory scripts > "$T/ruff.txt" 2>&1); r=$?; tail -1 "$T/ruff.txt"
    (cd "$A" && uv run --frozen ruff format --check esgapi/inventory > "$T/fmt.txt" 2>&1); f=$?; tail -1 "$T/fmt.txt"
    added_lines > "$T/added.txt"
    i="$(grep -c "pyright: ignore\|type: ignore\|# pyright:\|noqa" "$T/added.txt")"
    git diff "$BASE" -- "$A" ":(exclude)$A/scripts/section4-S3C-r1.sh" ":(exclude)$A/scripts/planted-breaks-S3C-r1.sh" | grep "^-" | grep -v "^---" > "$T/removed.txt"
    rm_="$(grep -c "pyright: ignore\|type: ignore\|# pyright:\|noqa" "$T/removed.txt")"
    echo "  더한 줄의 완화(pyright·type ignore·noqa) ${i} · 지운 완화 -${rm_}"
    [ "$p$r$f" = 000 ] && [ "$(tail -1 "$T/pyright.txt" | cut -d" " -f1)" = 0 ] && [ "$i" = 0 ]'
fi

# ── 6. 심은 파손 ──
if wanted 6; then
  case "$COMMIT" in 1) WANT=10 ;; 2) WANT=6 ;; esac  # 커밋 1: P1~P8 + P16(t="b") + P17(검증 B1) · 커밋 2: 보고 「심은 파손」
  export WANT
  step 6 "심은 파손 PLANTED=${WANT}/${WANT} + c2 --commit 1 15/15 · c1b-2 --commit 1 13/13 · c1b-1 --commit 1 13/13 · c1a --commit 2 19/19 · b2b --commit 2 15/15 · S3C-a --commit 3 14/16(BASE 수 그대로) — 일곱 다 FINGERPRINT=same" '
    "$A/scripts/planted-breaks-S3C-r1.sh" --commit "$COMMIT" > "$T/planted.txt" 2>&1; c=$?
    "$A/scripts/planted-breaks-S3C-c2.sh" --commit 1 > "$T/planted-c2.txt" 2>&1; d=$?
    "$A/scripts/planted-breaks-S3C-c1b-2.sh" --commit 1 > "$T/planted-c1b2.txt" 2>&1; q=$?
    "$A/scripts/planted-breaks-S3C-c1b-1.sh" --commit 1 > "$T/planted-c1b1.txt" 2>&1; p=$?
    "$A/scripts/planted-breaks-S3C-c1a.sh" --commit 2 > "$T/planted-c1a.txt" 2>&1; a=$?
    "$A/scripts/planted-breaks-S3C-b2b.sh" --commit 2 > "$T/planted-b2b.txt" 2>&1; b=$?
    "$A/scripts/planted-breaks-S3C-a.sh" --commit 3 > "$T/planted-s3ca.txt" 2>&1
    for f in planted:r1 planted-c2:c2 planted-c1b2:c1b-2 planted-c1b1:c1b-1 planted-c1a:c1a planted-b2b:b2b planted-s3ca:S3C-a; do tail -2 "$T/${f%%:*}.txt" | sed "s/^/  ${f##*:} /"; done
    for f in planted planted-c2 planted-c1b2 planted-c1b1 planted-c1a planted-b2b planted-s3ca; do [ "$(tail -2 "$T/$f.txt" | head -1)" = "FINGERPRINT=same" ] || exit 1; done
    [ "$c$d$q$p$a$b" = 000000 ] && [ "$(tail -1 "$T/planted.txt")" = "PLANTED=$WANT/$WANT" ] && [ "$(tail -1 "$T/planted-c2.txt")" = "PLANTED=15/15" ] && [ "$(tail -1 "$T/planted-c1b2.txt")" = "PLANTED=13/13" ] && [ "$(tail -1 "$T/planted-c1b1.txt")" = "PLANTED=13/13" ] && [ "$(tail -1 "$T/planted-c1a.txt")" = "PLANTED=19/19" ] && [ "$(tail -1 "$T/planted-b2b.txt")" = "PLANTED=15/15" ] && [ "$(tail -1 "$T/planted-s3ca.txt")" = "PLANTED=14/16" ]'
fi

# ── 7. 고정 스키마 0바이트 차이 ──
if wanted 7; then
  step 7 "고정 스키마를 다시 뽑아 고정 파일과 cmp 0, BASE 의 고정 파일과도 0바이트 차이(계약 0줄)" '
    (cd "$A" && uv run --frozen python -c "import json, sys; from esgapi.inventory.contracts import shapes; sys.stdout.write(json.dumps(shapes.RESULT_SHAPES[\"scope3.colab.result@1\"].json_schema(), ensure_ascii=False, indent=2) + \"\n\")" > "$T/regen.json"); r=$?
    cmp "$T/regen.json" "$SCHEMA"; m=$?
    git show "$BASE:$SCHEMA" > "$T/base.json"
    cmp "$T/base.json" "$T/regen.json"; b=$?
    echo "  다시 뽑기 EXIT=$r · 고정 파일 cmp EXIT=$m · BASE 고정 파일 cmp EXIT=$b"
    [ "$r$m$b" = 000 ]'
fi

# ── 8·9 공통: esg-lab 입력 판(코랩 쪽만 돌려 inputs/ 를 지음 — esg-lab 추적 파일 0줄, 산출 esg-lab/out/S3C-c1b-2/) ──
LAB="$(cd "$ROOT/../../esg-lab" && pwd)"
LABOUT="$LAB/out/S3C-r1/s4"
export LAB LABOUT
lab_answers() { # <판> → 그 판의 답 파일(esg-lab cli.py INPUTS 와 같은 짝)
  case "$1" in
    base | base-v22) echo "$LAB/py/scope3colab/answers.synthetic.json" ;;
    distance | distance-v22 | distance-v22map) echo "$LAB/py/scope3colab/answers.distance.synthetic.json" ;;
    distance-transport) echo "$LAB/py/scope3colab/answers.distance-transport.synthetic.json" ;;
    rest) echo "$LAB/py/scope3colab/answers.rest.synthetic.json" ;;
    filled) echo "$LAB/py/scope3colab/answers.filled.synthetic.json" ;;
  esac
}
lab_inputs() { # <판> → 코랩 쪽만 돌려 $LABOUT/<판>/inputs 를 짓는다
  mkdir -p "$LABOUT"
  (cd "$LAB/py" && uv run --frozen --group scope3colab python -m scope3colab run --input "$1" --out "$LABOUT/$1" > "$LABOUT/$1.colab.log" 2>&1)
}
lab_template() { find "$LABOUT/$1/inputs" -maxdepth 1 -name "*.xlsx" | head -1; }
lab_book() { find "$LABOUT/$1/inputs" -mindepth 2 -name "*.xlsx" | head -1; }
export -f lab_answers lab_inputs lab_template lab_book

# ── 8. 기존 kind 줄 바이트(BASE 대 이 가지의 result_to_dict) ──
if wanted 8; then
  step 8 "BASE(우회 있음) 대 이 가지(우회 없음) 여덟 판: result_to_dict 통째 jq -S cmp 0(factorSheets 여덟 그대로), 파일 인자 없는 dump JSON jq -S cmp 0" '
    mkdir -p "$T/base-src"
    git archive "$BASE" "$A" | tar -x -C "$T/base-src"
    cat > "$T/result.py" <<'"'"'PY'"'"'
import json, sys
from pathlib import Path
from esgapi.inventory.engines.scope3.colab_157.pipeline import run
from esgapi.inventory.engines.scope3.colab_157.serialize import result_to_dict
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client
from esgapi.inventory.tests.scope3colab_dump import TAGS, OrderedAnswers, RecordingGeocoder, load_answers, read_book
template, book, answers = (Path(p) for p in sys.argv[1:4])
result = run(read_book(template), read_book(book), 2025, mock_client(OrderedAnswers(load_answers(answers))), RecordingGeocoder(), TAGS, ROUTE)
sys.stdout.write(json.dumps(result_to_dict(result, "scope3.colab.result@1"), ensure_ascii=False, indent=2) + "\n")
PY
    PY="$ROOT/$A/.venv/bin/python"
    bad=0
    for v in rest base distance-transport distance base-v22 distance-v22 distance-v22map filled; do
      lab_inputs "$v" || { echo "  ★ $v 입력 짓기 실패"; bad=1; continue; }
      tp="$(lab_template "$v")"; bk="$(lab_book "$v")"; an="$(lab_answers "$v")"
      for side in base head; do
        src="$ROOT/$A"; [ "$side" = base ] && src="$T/base-src/$A"
        (cd "$src" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH="$src" "$PY" -I -c "import sys; sys.path.insert(0, \"$src\"); exec(open(\"$T/result.py\").read())" "$tp" "$bk" "$an" > "$T/$v.$side.json" 2> "$T/$v.$side.err") || { echo "  ★ $v $side 실행 실패"; bad=1; }
        (cd "$src" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH="$src" "$PY" -m esgapi.inventory.tests.scope3colab_dump --template "$tp" --factor-book "$bk" --answers "$an" > "$T/$v.$side.dump.json" 2>> "$T/$v.$side.err") || { echo "  ★ $v $side dump 실패"; bad=1; }
      done
      # 허용 차이 0: 결과 통째(factorSheets 여덟 포함) jq -S 바이트와 dump JSON 바이트
      jq -S . "$T/$v.base.json" > "$T/$v.base.all.json"; jq -S . "$T/$v.head.json" > "$T/$v.head.all.json"
      cmp -s "$T/$v.base.all.json" "$T/$v.head.all.json"; r=$?
      nb="$(jq ".factorSheets | length" "$T/$v.base.json")"
      fs="$(jq -c "[.factorSheets[] | .sheet]" "$T/$v.head.json")"
      st="$(jq -r "[.sheets[] | select((.category // \"\") | test(\"^Category(11|14)$\")) | .status] | group_by(.) | map(\"\(.[0])×\(length)\") | join(\",\")" "$T/$v.head.json")"
      jq -S . "$T/$v.base.dump.json" > "$T/$v.base.dump.s.json"; jq -S . "$T/$v.head.dump.json" > "$T/$v.head.dump.s.json"
      cmp -s "$T/$v.base.dump.s.json" "$T/$v.head.dump.s.json"; d=$?; cmp -s "$T/$v.base.dump.json" "$T/$v.head.dump.json"; db=$?
      echo "  $v: 결과 통째 cmp EXIT=$r · factorSheets BASE ${nb} = $fs · C11·C14 시트 상태 ${st:-없음} · dump jq -S cmp EXIT=$d · 바이트 cmp EXIT=$db"
      [ "$nb" = 8 ] || { echo "  ★ factorSheets 가 여덟이 아니다"; bad=1; }
      [ "$r$d$db" = 000 ] || bad=1
    done
    [ "$bad" = 0 ]'
fi

# ── 9. esg-lab 대조 기계 판정(여덟 판 — 줄 대조 + 출력 파일 둘의 꼴 + 결과 파일 칸 값) ──
if wanted 9; then
  cat > "$T/cells.py" <<'PY'
"""S3C-c2 §4 [9] 칸 값 대조: 엔진 결과 파일과 코랩 `work/result/*_result.xlsx` 를 openpyxl 로 열어 시트·칸 값을 견준다.

    python scripts/compare-result-cells-S3C-c2.py <엔진 result.xlsx> <코랩 result.xlsx>

수는 `Decimal(repr(값))` 같음(허용 0), 글은 글자 같음, 빈 칸은 None. 머리 줄(열 이름)도 칸이다. 차이 칸 수를 찍고 0 이면
종료 0, 아니면 1(처음 열 칸을 찍는다). 감독 보정 4(10-28).
"""

import sys
from decimal import Decimal

import openpyxl


def norm(value: object) -> object:
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, int | float):
        return Decimal(repr(value))
    return repr(value)


def cells(path: str) -> dict[str, dict[str, object]]:
    book = openpyxl.load_workbook(path)
    return {
        ws.title: {c.coordinate: norm(c.value) for row in ws.iter_rows() for c in row if c.value is not None}
        for ws in book.worksheets
    }


def main() -> int:
    engine, colab = cells(sys.argv[1]), cells(sys.argv[2])
    diffs: list[str] = []
    if list(engine) != list(colab):
        diffs.append(f"시트 차례 {list(engine)} != {list(colab)}")
    for name in colab:
        e, c = engine.get(name, {}), colab[name]
        diffs += [f"{name}!{k}: {e.get(k)!r} != {c.get(k)!r}" for k in sorted(e.keys() | c.keys()) if e.get(k) != c.get(k)]
    n = sum(len(v) for v in colab.values())
    print(f"칸 {n} · 차이 {len(diffs)}")
    for line in diffs[:10]:
        print("  " + line)
    return 0 if not diffs else 1


if __name__ == "__main__":
    sys.exit(main())
PY
  cat > "$T/reread.py" <<'PY'
"""S3C-r1 §4 [9] 더함: dump 가 쓴 결과 파일·채운 템플릿을 우리 읽개로 다시 읽어 ReaderProblem 0."""

import sys
from pathlib import Path

from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

bad = 0
for name in sys.argv[1:]:
    book = read_workbook(Path(name).read_bytes())
    if isinstance(book, ReaderProblem):
        bad += 1
        print(f"  ★ {Path(name).name}: {book}")
print(f"  다시 읽기 {len(sys.argv) - 1} · ReaderProblem {bad}")
sys.exit(1 if bad else 0)
PY
  step 9 "esg-lab 대조: 여덟 판 run --engine-result --engine-result-file --engine-filled-file EXIT=0 · 줄 차이 0 · outputs.json 차이 0 · 코랩 result.xlsx 칸 값 차이 0 · rest 27줄 · filled 11줄 + 출력 16파일 우리 읽개 ReaderProblem 0" '
    bad=0
    for v in rest base distance-transport distance base-v22 distance-v22 distance-v22map filled; do
      lab_inputs "$v" || { echo "  ★ $v 입력 짓기 실패"; bad=1; continue; }
      tp="$(lab_template "$v")"; bk="$(lab_book "$v")"; an="$(lab_answers "$v")"
      rf="$LABOUT/$v.engine_result.xlsx"; ff="$LABOUT/$v.engine_filled.xlsx"; rm -f "$rf" "$ff"
      (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.inventory.tests.scope3colab_dump --template "$tp" --factor-book "$bk" --answers "$an" --result-file "$rf" --filled-file "$ff" > "$LABOUT/$v.engine.json" 2> "$LABOUT/$v.engine.err"); dc=$?
      (cd "$LAB/py" && uv run --frozen --group scope3colab python -m scope3colab run --input "$v" --out "$LABOUT/$v-cmp" --engine-result "$LABOUT/$v.engine.json" --engine-result-file "$rf" --engine-filled-file "$ff" > "$LABOUT/$v-cmp.log" 2>&1); c=$?
      miss="$(grep "^- 엔진 쪽 줄 없음(열쇠): " "$LABOUT/$v-cmp/diff.md" | sed "s/^- 엔진 쪽 줄 없음(열쇠): //")"
      n="$(grep -E "^차이 [0-9]+줄" "$LABOUT/$v-cmp/diff.md" | sed -E "s/^차이 ([0-9]+)줄.*/\1/")"
      o="$(grep -E "^차이 [0-9]+줄" "$LABOUT/$v-cmp/outputs.md" | sed -E "s/^차이 ([0-9]+)줄.*/\1/")"
      colab_rf="$(find "$LABOUT/$v-cmp/work/result" -name "*_result.xlsx" | head -1)"
      cells="$(cd "$A" && uv run --frozen python -I "$T/cells.py" "$rf" "$colab_rf" 2>&1 | head -3 | tr "\n" " ")"
      (cd "$A" && uv run --frozen python -I "$T/cells.py" "$rf" "$colab_rf" > /dev/null 2>&1); k=$?
      rows="$(grep -E "^- 코랩 쪽 줄: " "$LABOUT/$v-cmp/diff.md" | sed -E "s/^- 코랩 쪽 줄: ([0-9]+).*/\1/")"
      echo "  $v: dump EXIT=$dc · 대조 EXIT=$c · 줄 ${rows} 차이 ${n:-0} · 출력 파일 차이 ${o:-0} · 결과 칸 ${cells}· 엔진 쪽 줄 없음 ${miss:-없음}"
      [ "$dc$c$k" = 000 ] && [ "${n:-0}" = 0 ] && [ "${o:-0}" = 0 ] && [ -z "$miss" ] || bad=1
      [ "$v" = rest ] && { [ "$rows" = 27 ] || bad=1; }
      [ "$v" = filled ] && { [ "$rows" = 11 ] || bad=1; grep "filled-template" "$LABOUT/$v-cmp/colab-stdout.log" | sed "s/^/    코랩 /"; }
    done
    (cd "$A" && uv run --frozen python "$T/reread.py" "$LABOUT"/*.engine_result.xlsx "$LABOUT"/*.engine_filled.xlsx); rr=$?
    [ "$rr" = 0 ] || bad=1
    git -C "$LAB" status --porcelain --untracked-files=no | grep -q . && { echo "  ★ esg-lab 추적 파일이 바뀌었다"; bad=1; }
    [ "$bad" = 0 ]'
fi

echo
echo "SECTION4_FAIL=$FAILS"
rm -rf "$T"
[ "$FAILS" = 0 ]
