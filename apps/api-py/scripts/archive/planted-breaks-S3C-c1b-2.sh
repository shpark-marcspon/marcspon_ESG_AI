#!/usr/bin/env bash
# S3C-c1b-2(MARC-TICK-342)의 심은 파손(발주서 §3-2 P1~P10 + 감독 보정 3 의 P11 + T7 의 P12 + 검증 B1 의 P13): 엔진 판 colab_157 의 C11·C14 몫에 파손 하나를
#   심고, 그것을 물어야 할 시험이 빨개지는지 본다.  BASE 91eef564(merge band/S3C-c1b-1). 꼴은 planted-breaks-S3C-c1b-1.sh 그대로.
#   P3 은 energy.py(이 밴드 0줄)에 잠깐 심고 바이트로 되쓴다 — C14 후처리가 그 함수로 사슬을 부른다.
#   사용: apps/api-py/scripts/planted-breaks-S3C-c1b-2.sh --commit 1   (커밋 하나 — 전부)
# 심기 전의 파일을 임시 폴더에 베껴 두었다가 그 바이트로 되쓴다(git 을 쓰지 않는다 — checkout·stash·restore·reset 0).
#   끝나면 작업 트리가 처음과 같아야 한다: 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 셈에 들어가 다름이 된다.
# 빨강 = pytest 종료 1 이고, 실패한 시험 노드 가운데 하나라도 기대 낱말(파일 이름 조각)을 품음. 종료 2 이상(수집 실패 등)은 「죽음」 — 다름.
# 줄마다  <id> <심은 것> → 빨강|초록|죽음 (<실패한 시험 파일>) 맞음|다름.  끝에 FINGERPRINT=same|differs, PLANTED=<맞음>/<심은 수>.
# 종료 0 은 「PLANTED 가 다 맞음 ∧ 지문이 같음」일 때뿐이다.
# 셸 규칙(bash 3.2): 명령 치환에 종료 코드를 싣지 않는다(시험 결과는 전역 RED·RC 로 받는다).
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1) ;; *) echo "--commit 1" >&2; exit 2 ;; esac

I=esgapi/inventory
E=esgapi/inventory/engines/scope3/colab_157
T=esgapi/inventory/tests/engines/scope3/colab_157

backup="$(mktemp -d /private/tmp/pb-s3cc1b2.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cc1b2.*) ;; *) exit 99 ;; esac
touched=()
restore() {
  local f
  for f in "${touched[@]:-}"; do [ -n "$f" ] && cp "$backup/$(echo "$f" | tr / _)" "$f"; done
  touched=()
}
trap 'restore; rm -rf "$backup"' EXIT

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
fingerprint > "$backup/.fingerprint-before"

keep() { # <파일>
  cp "$1" "$backup/$(echo "$1" | tr / _)"; touched+=("$1")
}

replace_once() { # <파일> <옛 글자> <새 글자>   — 옛 글자가 정확히 한 번일 때만 바꾸고 0
  python3 -I - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1], sys.argv[2], sys.argv[3]
with open(path, encoding="utf-8", newline="") as fh:
    text = fh.read()
if text.count(old) != 1:
    sys.exit(1)
with open(path, "w", encoding="utf-8", newline="") as fh:
    fh.write(text.replace(old, new))
PY
}

RED=""; RC=0
run_tests() { # <시험 경로…>  → 전역 RC(pytest 종료)·RED(실패한 시험 파일 이름을 , 로)
  env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -rf "$@" > "$backup/run.txt" 2>&1
  RC=$?
  grep "^FAILED " "$backup/run.txt" | sed -e 's/^FAILED //' -e 's/::.*//' -e 's|.*/||' | sort -u > "$backup/red.txt"
  RED="$(tr '\n' ',' < "$backup/red.txt" | sed 's/,$//')"
}

planted=0; expected=0
report() { # <id> <설명> <기대 낱말>   (RC·RED 를 읽는다)
  local verdict ok="다름"
  case "$RC" in
    0) verdict="초록" ;;
    1) verdict="빨강" ;;
    *) verdict="죽음(종료 $RC)" ;;
  esac
  if [ "$RC" = 1 ]; then
    case ",$RED," in *"$3"*) ok="맞음" ;; esac
  fi
  planted=$((planted + 1))
  [ "$ok" = "맞음" ] && expected=$((expected + 1))
  printf '%s %s → %s (%s) 기대 %s %s\n' "$1" "$2" "$verdict" "${RED:-없음}" "$3" "$ok"
}

plant_replace() { # <id> <설명> <파일> <옛> <새> <기대 낱말> <시험 경로…>
  local id="$1" what="$2" file="$3" old="$4" new="$5" want="$6"; shift 6
  keep "$file"
  if ! replace_once "$file" "$old" "$new"; then
    printf '%s %s → 못 심음(옛 글자가 한 번이 아니다) 다름\n' "$id" "$what"; planted=$((planted + 1)); restore; return
  fi
  run_tests "$@"
  restore
  report "$id" "$what" "$want"
}

DUMP="$I/tests/test_scope3colab_dump.py"
PU="$T/test_product_use_sheet.py"
FR="$T/test_franchise_sheet.py"

plant_replace P1 "C11 후처리가 처리 때 셈(:6961)을 다시 씀 — 최종 :8720 대신(T1)" "$E/product.py" \
  '    calc = calc_c11_8720(energy, row)' '    calc = calc_c11_6961(energy, row)' \
  test_product_use_sheet "$PU"

plant_replace P2 "후처리 차례를 C11_·C14_ 먼저(T3)" "$E/pipeline.py" \
  '    for category in dict.fromkeys(c for c in order if c in pending or c in product_pending):' \
  '    for category in sorted(dict.fromkeys(c for c in order if c in pending or c in product_pending), key=lambda c: c not in product_pending):' \
  test_product_use_sheet "$PU"

plant_replace P3 "C14 후처리가 사슬에 단위 힌트를 안 넘김(T2 — energy.py 에 잠깐)" "$E/energy.py" \
  '    found = lookup_energy_ef(db, energy_name, unit_hint=unit_raw)' '    found = lookup_energy_ef(db, energy_name)' \
  test_franchise_sheet "$FR"

plant_replace P4 "C11·C14 매핑 칸(:7613·:7623)을 빼먹음(T1)" "$E/product.py" \
  '        out.update(_match_columns(match))' '        out.update({})' \
  test_product_use_sheet "$PU"

plant_replace P5 "PRODUCT_POST_KEYS 에서 c14 뺌(T5)" "$E/pipeline.py" \
  'frozenset({"c11", "c14"})' 'frozenset({"c11"})' \
  test_franchise_sheet "$T"

plant_replace P6 "serialize 가 product 를 빼먹음(T4)" "$E/serialize.py" \
  '        "product": None
        if use is None' '        "product": None
        if True' \
  test_product_use_sheet "$PU"

plant_replace P7 "serialize match 를 null 로(T4)" "$E/serialize.py" \
  '        "match": _match(meta.match),' '        "match": None,' \
  test_product_use_sheet "$T"

plant_replace P8 "dump C11 item 차례 뒤집음(T6)" "$I/tests/scope3colab_dump.py" \
  '"C11": ("제품명", "에너지명"),' '"C11": ("에너지명", "제품명"),' \
  test_scope3colab_dump "$DUMP"

plant_replace P9 "C11·C14 가 다른 AI 배수 캐시를 씀(부름 수가 늚)" "$E/pipeline.py" \
  '    product = ProductRun(read_waste_c12_sheet(factor_book), activity.waste, energy)' \
  '    product = ProductRun(read_waste_c12_sheet(factor_book), activity.waste, EnergyRun(energy.energy, energy.energy_c3, context, type(energy.units)()))' \
  test_product_use_sheet "$PU"

plant_replace P10 "C11·C14 후처리 예외를 삼키지 않음(T3)" "$E/pipeline.py" \
  '            with contextlib.suppress(Exception):  # 코랩 `[경고] … 후처리 실패` → 처리 때 값(`:8903-8905`)' \
  '            with contextlib.nullcontext():' \
  test_product_use_sheet "$PU"

plant_replace P11 "처리 때 C11 셈(:6961, 날 이름 맥락) 건너뜀 — 부름 수가 줆(감독 보정 3)" "$E/product.py" \
  '    calcs = [calc_c11_6961(run.energy, row) if key == "c11" else None for _, row in df.iterrows()]' \
  '    calcs = [calc_c11_8720(run.energy, row) if key == "c11" else None for _, row in df.iterrows()]' \
  test_product_use_sheet "$PU"

plant_replace P12 "후처리 환산 맥락을 늘 날 이름으로(T7 — :8742 std_name or energy_name)" "$E/product.py" \
  '    context_name = str(_colab_or(found.name, energy_name))' '    context_name = energy_name' \
  test_product_use_sheet "$PU"

plant_replace P13 "후처리 차례를 BASE 꼴(첫 기다림 시트)로 — 첫 처리 시트 대신(검증 B1)" "$E/pipeline.py" \
  '    order = [o.processor.category for o in outcomes if isinstance(o, ProcessedSheet)]' \
  '    order = [*pending, *product_pending]' \
  test_product_use_sheet "$PU"

restore
fingerprint > "$backup/.fingerprint-after"
same="same"
if ! cmp -s "$backup/.fingerprint-before" "$backup/.fingerprint-after"; then
  same="differs"
  echo "작업 트리가 처음과 다르다:"
  diff "$backup/.fingerprint-before" "$backup/.fingerprint-after"
fi
echo "FINGERPRINT=$same"
echo "PLANTED=$expected/$planted"
[ "$expected" -eq "$planted" ] && [ "$same" = "same" ] && exit 0
exit 1
