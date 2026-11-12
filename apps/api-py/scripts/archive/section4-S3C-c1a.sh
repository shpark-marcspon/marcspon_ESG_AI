#!/usr/bin/env bash
# 밴드 S3C-c1a(MARC-TICK-340: Scope 3 코랩 흐름 c 몫 ① — 결과 꼴 일곱 열쇠 + C3·C8·C13)의 §4 자기검증. 꼴은 section4-S3C-b2b.sh 를 줄였다.
#   사용: apps/api-py/scripts/section4-S3C-c1a.sh --commit <1|2> [--step <n>]
#   --commit 1 은 단계 0~7, 2 는 0~9.
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(병합 뒤 테스트 감독 몫). 업무(django_db)·보안 층, 컨테이너도 안 돌린다. AI 공급사 호출 0.
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=c009fa99511fbea6876ad2993d2238d7fd8ac6e7   # 워크트리를 세운 main(merge band/GPW1, 2026-10-27) = 발주서의 c009fa99
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
    *) echo "사용: $0 --commit <1|2> [--step <n>]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2) ;; *) echo "--commit <1|2> 이 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/s3cc1a.XXXXXX)"
case "$T" in /private/tmp/s3cc1a.*) ;; *) exit 99 ;; esac
FAILS=0

wanted() { # <단계>
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ] || return 1
  case "$COMMIT:$1" in
    *:0 | *:1 | *:2 | *:3 | *:4 | *:5 | *:6 | *:7) return 0 ;;
    2:8 | 2:9) return 0 ;;
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
  git diff "$BASE" -- "$A" ":(exclude)$A/scripts/section4-S3C-c1a.sh" ":(exclude)$A/scripts/planted-breaks-S3C-c1a.sh" | grep "^+" | grep -v "^+++"
  git ls-files --others --exclude-standard -- "$A" ":(exclude)$A/scripts/section4-S3C-c1a.sh" ":(exclude)$A/scripts/planted-breaks-S3C-c1a.sh" \
    | while IFS= read -r f; do sed "s/^/+/" "$f"; done
}
export -f added_lines
export ROOT BASE A E I C T COMMIT SCHEMA

echo "── 밴드 S3C-c1a §4 · 커밋 $COMMIT · BASE ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"

# ── 0. BASE 머리 ──
if wanted 0; then
  step 0 "BASE ⊂ HEAD, c009fa99..BASE 의 inventory 차이 0(발주서 머리)" '
    git merge-base --is-ancestor "$BASE" HEAD; h=$?
    git diff --quiet c009fa99 "$BASE" -- "$I"; d=$?
    echo "  BASE ⊂ HEAD EXIT=$h · c009fa99..BASE inventory 차이 EXIT=$d"
    [ "$h$d" = 00 ]'
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
  P0=""; for f in activity template purchase spend waste transport travel travel_mode distance company_mapping frames pdcompat llm ports units; do P0="$P0 $C/$f.py"; done
  P0="$P0 $I/flows/registration.py $I/prompts $I/tools $E/core $E/config $A/.importlinter $A/generated $E/runs $E/organization"
  [ "$COMMIT" = 1 ] && P0="$P0 $C/pipeline.py $C/serialize.py $I/tests/scope3colab_dump.py"
  export P0
  step 3 "1-2 0줄 경로(activity·template·import 만 쓰는 파일·units·registration·프롬프트·tools·경계, 커밋 ① 은 pipeline·serialize·dump 도)" '
    for p in $P0; do n="$(git ls-files -- "$p" | wc -l | tr -d " ")"; [ "$n" -gt 0 ] || { echo "  ★ 추적 파일 0 인 경로(양성 대조 실패): $p"; exit 1; }; done
    git diff --quiet "$BASE" -- $P0; code=$?
    new="$(git ls-files --others --exclude-standard -- $P0 | wc -l | tr -d " ")"
    git diff --stat "$BASE" -- $P0 | tail -5 | sed "s/^/  /"
    echo "  경로 $(echo $P0 | wc -w | tr -d " ")개 · git diff EXIT=$code · 추적 안 된 새 파일 $new"
    [ "$code" = 0 ] && [ "$new" = 0 ]'
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
    i="$(grep -c "pyright: ignore\|type: ignore\|# pyright:" "$T/added.txt")"
    echo "  더한 줄의 완화(pyright·type ignore) ${i}"
    [ "$p$r$f" = 000 ] && [ "$(tail -1 "$T/pyright.txt" | cut -d" " -f1)" = 0 ] && [ "$i" = 0 ]'
fi

# ── 6. 심은 파손 ──
if wanted 6; then
  WANT=7; [ "$COMMIT" = 2 ] && WANT=19  # 발주서 P1~P15 + 감독 권고 R1(P16) + 검증 권고 R3~R5(P17~P19)
  export WANT
  step 6 "심은 파손 PLANTED=${WANT}/${WANT} + 앞 밴드 planted-breaks-S3C-b2b.sh --commit 2 그대로 묾" '
    "$A/scripts/planted-breaks-S3C-c1a.sh" --commit "$COMMIT" > "$T/planted.txt" 2>&1; c=$?
    "$A/scripts/planted-breaks-S3C-b2b.sh" --commit 2 > "$T/planted-b2b.txt" 2>&1; b=$?
    tail -2 "$T/planted.txt" | sed "s/^/  c1a /"; tail -1 "$T/planted-b2b.txt" | sed "s/^/  b2b /"
    [ "$c$b" = 00 ] && [ "$(tail -1 "$T/planted.txt")" = "PLANTED=$WANT/$WANT" ] && [ "$(tail -1 "$T/planted-b2b.txt")" = "PLANTED=15/15" ]'
fi

# ── 7. 허용 스키마 diff ──
if wanted 7; then
  step 7 "고정 스키마를 다시 뽑아 고정 파일과 같고, BASE 와의 차이는 새 \$defs·rows oneOf 갈래 하나·mapping 새 kind 일곱뿐" '
    (cd "$A" && uv run --frozen python -c "import json, sys; from esgapi.inventory.contracts import shapes; sys.stdout.write(json.dumps(shapes.RESULT_SHAPES[\"scope3.colab.result@1\"].json_schema(), ensure_ascii=False, indent=2) + \"\n\")" > "$T/regen.json"); r=$?
    cmp "$T/regen.json" "$SCHEMA"; m=$?
    git show "$BASE:$SCHEMA" > "$T/base.json"
    python3 -I - "$T/base.json" "$T/regen.json" <<'"'"'PY'"'"'
import json, sys
a, b = (json.load(open(p, encoding="utf-8")) for p in sys.argv[1:])
KINDS = ["fuel_energy", "leased_asset", "leased_out_asset", "product_use", "product_eol", "franchise", "investment"]
NEW = {"ColabEnergyRowJson", "ColabEnergyMatchJson", "ColabAllocationJson", "ColabProductUseJson", "ColabInvestmentJson"}
problems = []
if {k: v for k, v in a.items() if k != "$defs"} != {k: v for k, v in b.items() if k != "$defs"}:
    problems.append("맨 위(꼴 밖 칸)가 다르다")
ad, bd = a["$defs"], b["$defs"]
if set(ad) - set(bd):
    problems.append(f"없어진 $defs: {sorted(set(ad) - set(bd))}")
if set(bd) - set(ad) != NEW:
    problems.append(f"새 $defs 가 허용 다섯과 다르다: {sorted(set(bd) - set(ad))}")
for name in sorted(set(ad) & set(bd)):
    if name == "ColabProcessedSheetJson":
        continue
    if ad[name] != bd[name]:
        problems.append(f"기존 $defs 바뀜: {name}")
old, new = ad["ColabProcessedSheetJson"], bd["ColabProcessedSheetJson"]
oi, ni = old["properties"]["rows"]["items"], new["properties"]["rows"]["items"]
if ni["oneOf"] != oi["oneOf"] + [{"$ref": "#/$defs/ColabEnergyRowJson"}]:
    problems.append("rows oneOf 가 「기존 + 새 갈래 하나」 가 아니다")
want = dict(oi["discriminator"]["mapping"], **{k: "#/$defs/ColabEnergyRowJson" for k in KINDS})
if ni["discriminator"]["mapping"] != want or set(oi["discriminator"]["mapping"]) & set(KINDS):
    problems.append("discriminator.mapping 이 「기존 + 새 kind 일곱」 이 아니다")
rest_old = json.loads(json.dumps(old)); rest_new = json.loads(json.dumps(new))
for d in (rest_old, rest_new):
    d["properties"]["rows"]["items"].pop("oneOf"); d["properties"]["rows"]["items"]["discriminator"].pop("mapping")
if rest_old != rest_new:
    problems.append("ColabProcessedSheetJson 의 rows 밖 칸이 바뀌었다")
counts = (len(oi["oneOf"]), len(ni["oneOf"]), len(oi["discriminator"]["mapping"]), len(ni["discriminator"]["mapping"]))
print("  새 $defs", sorted(set(bd) - set(ad)), "· oneOf %d→%d · mapping %d→%d" % counts)
for p in problems:
    print("  ★", p)
sys.exit(1 if problems else 0)
PY
    d=$?
    echo "  다시 뽑기 EXIT=$r · 고정 파일 cmp EXIT=$m · 허용 diff 판정 EXIT=$d"
    [ "$r$m$d" = 000 ]'
fi

# ── 8·9 공통: esg-lab 입력 판(코랩 쪽만 돌려 inputs/ 를 지음 — esg-lab 추적 파일 0줄, 산출 esg-lab/out/S3C-c1a/) ──
LAB="$(cd "$ROOT/../../esg-lab" && pwd)"
LABOUT="$LAB/out/S3C-c1a"
export LAB LABOUT
lab_answers() { # <판> → 그 판의 답 파일(esg-lab cli.py INPUTS 와 같은 짝)
  case "$1" in
    base | base-v22) echo "$LAB/py/scope3colab/answers.synthetic.json" ;;
    distance | distance-v22 | distance-v22map) echo "$LAB/py/scope3colab/answers.distance.synthetic.json" ;;
    distance-transport) echo "$LAB/py/scope3colab/answers.distance-transport.synthetic.json" ;;
    rest) echo "$LAB/py/scope3colab/answers.rest.synthetic.json" ;;
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
  step 8 "기존 kind 줄 바이트: base·distance-transport·distance 의 result_to_dict 에서 기존 kind 시트 rows cmp 0, 허용 차이(factorSheets 끝 둘 · C3·C8·C13 시트 항목) 밖 0, dump cmp 0" '
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
    for v in base distance-transport distance; do
      lab_inputs "$v" || { echo "  ★ $v 입력 짓기 실패"; bad=1; continue; }
      tp="$(lab_template "$v")"; bk="$(lab_book "$v")"; an="$(lab_answers "$v")"
      for side in base head; do
        src="$ROOT/$A"; [ "$side" = base ] && src="$T/base-src/$A"
        (cd "$src" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH="$src" "$PY" -I -c "import sys; sys.path.insert(0, \"$src\"); exec(open(\"$T/result.py\").read())" "$tp" "$bk" "$an" > "$T/$v.$side.json" 2> "$T/$v.$side.err") || { echo "  ★ $v $side 실행 실패"; bad=1; }
        (cd "$src" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH="$src" "$PY" -m esgapi.inventory.tests.scope3colab_dump --template "$tp" --factor-book "$bk" --answers "$an" > "$T/$v.$side.dump.json" 2>> "$T/$v.$side.err") || { echo "  ★ $v $side dump 실패"; bad=1; }
      done
      # 기존 kind 시트(C3·C8·C13 밖 Category)의 rows 바이트
      OLD='"'"'[.sheets[] | select((.category // "") | test("^Category(3|8|13)$") | not)]'"'"'
      jq -S "$OLD" "$T/$v.base.json" > "$T/$v.base.old.json"; jq -S "$OLD" "$T/$v.head.json" > "$T/$v.head.old.json"
      cmp -s "$T/$v.base.old.json" "$T/$v.head.old.json"; r=$?
      # 허용 차이를 걷은 나머지: factorSheets 를 앞 다섯으로, C3·C8·C13 시트 항목을 뺌
      REST='"'"'.factorSheets |= .[0:5] | .sheets |= [.[] | select((.category // "") | test("^Category(3|8|13)$") | not)]'"'"'
      jq -S "$REST" "$T/$v.base.json" > "$T/$v.base.rest.json"; jq -S "$REST" "$T/$v.head.json" > "$T/$v.head.rest.json"
      cmp -s "$T/$v.base.rest.json" "$T/$v.head.rest.json"; o=$?
      fs="$(jq -c "[.factorSheets[5:][] | .sheet]" "$T/$v.head.json")"
      nb="$(jq ".factorSheets | length" "$T/$v.base.json")"  # 양성 대조: BASE 쪽이 정말 BASE 코드(계수 시트 다섯)
      st="$(jq -r "[.sheets[] | select((.category // \"\") | test(\"^Category(3|8|13)$\")) | .status] | group_by(.) | map(\"\(.[0])×\(length)\") | join(\",\")" "$T/$v.head.json")"
      cmp -s "$T/$v.base.dump.json" "$T/$v.head.dump.json"; d=$?
      echo "  $v: 기존 kind rows cmp EXIT=$r · 허용 밖 cmp EXIT=$o · factorSheets BASE ${nb} → 새 끝 $fs · C3·C8·C13 시트 상태 ${st:-없음} · dump cmp EXIT=$d"
      [ "$nb" = 5 ] || { echo "  ★ BASE 쪽 factorSheets 가 다섯이 아니다(BASE 코드로 돌지 않음)"; bad=1; }
      [ "$fs" = "[\"에너지\",\"에너지_C3\"]" ] || { echo "  ★ factorSheets 끝 둘이 에너지·에너지_C3 이 아니다"; bad=1; }
      [ "$r$o$d" = 000 ] || bad=1
    done
    [ "$bad" = 0 ]'
fi

# ── 9. esg-lab 대조 기계 판정 ──
if wanted 9; then
  step 9 "esg-lab 대조: rest 는 EXIT=1·엔진 쪽 줄 없음 = C11, C12, C14, C15·차이 14, 나머지 여섯 EXIT=0" '
    bad=0
    for v in rest base distance-transport distance base-v22 distance-v22 distance-v22map; do
      lab_inputs "$v" || { echo "  ★ $v 입력 짓기 실패"; bad=1; continue; }
      tp="$(lab_template "$v")"; bk="$(lab_book "$v")"; an="$(lab_answers "$v")"
      (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.inventory.tests.scope3colab_dump --template "$tp" --factor-book "$bk" --answers "$an" > "$LABOUT/$v.engine.json" 2> "$LABOUT/$v.engine.err"); dc=$?
      (cd "$LAB/py" && uv run --frozen --group scope3colab python -m scope3colab run --input "$v" --out "$LABOUT/$v-cmp" --engine-result "$LABOUT/$v.engine.json" > "$LABOUT/$v-cmp.log" 2>&1); c=$?
      miss="$(grep "^- 엔진 쪽 줄 없음(열쇠): " "$LABOUT/$v-cmp/diff.md" | sed "s/^- 엔진 쪽 줄 없음(열쇠): //")"
      n="$(grep -E "^차이 [0-9]+줄" "$LABOUT/$v-cmp/diff.md" | sed -E "s/^차이 ([0-9]+)줄.*/\1/")"
      echo "  $v: dump EXIT=$dc · 대조 EXIT=$c · 차이 ${n:-0} · 엔진 쪽 줄 없음 ${miss:-없음}"
      [ "$dc" = 0 ] || bad=1
      if [ "$v" = rest ]; then
        others="$(grep "^| C" "$LABOUT/$v-cmp/diff.md" | grep -v "| (줄) | 있음 | — |" | wc -l | tr -d " ")"
        echo "    rest 의 「(줄) 있음 —」 밖 차이 ${others}"
        [ "$c" = 1 ] && [ "$miss" = "C11, C12, C14, C15" ] && [ "$n" = 14 ] && [ "$others" = 0 ] || bad=1
      else
        [ "$c" = 0 ] || bad=1
      fi
    done
    git -C "$LAB" status --porcelain --untracked-files=no | grep -q . && { echo "  ★ esg-lab 추적 파일이 바뀌었다"; bad=1; }
    [ "$bad" = 0 ]'
fi

echo
echo "SECTION4_FAIL=$FAILS"
rm -rf "$T"
[ "$FAILS" = 0 ]
