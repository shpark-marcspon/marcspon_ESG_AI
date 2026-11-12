#!/usr/bin/env bash
# S3C-c1b-1(MARC-TICK-341)의 심은 파손(발주서 §3-2 P1~P10 + P11·P12 + 검증 권고 R2 의 P13): 엔진 판 colab_157 의 C12·C15 몫에 파손 하나를 심고, 그것을
#   물어야 할 시험이 빨개지는지 본다.  BASE c2cfe984(merge band/S3C-c1a). 꼴은 planted-breaks-S3C-c1a.sh 그대로.
#   사용: apps/api-py/scripts/planted-breaks-S3C-c1b-1.sh --commit 1   (커밋 하나 — 전부)
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

backup="$(mktemp -d /private/tmp/pb-s3cc1b1.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cc1b1.*) ;; *) exit 99 ;; esac
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

plant_replace P1 "C12 코드를 「|」 뒤까지 씀(T1)" "$E/product.py" \
  '    return s.split("|")[0].strip() if "|" in s else s' '    return s' \
  test_product_eol_sheet "$T"

plant_replace P2 "FCF 표 폐지류 0.01 → 0.02(T1)" "$E/constants.py" \
  '{"음식물류": 0.0, "폐지류": 0.01, "폐목재류": 0.0}' '{"음식물류": 0.0, "폐지류": 0.02, "폐목재류": 0.0}' \
  test_product_eol_sheet "$T"

plant_replace P3 "흠 ① 고쳐 버림 — 처리비중 NaN 을 None 으로 거름(기대값이 빨개져야)" "$E/product.py" \
  '    if v is None:
        return None
    return v / 100.0' '    if v is None or v != v:
        return None
    return v / 100.0' \
  test_product_eol_sheet "$T"

plant_replace P4 "흠 ② 고쳐 버림 — 코드 「nan」 을 빈 코드로" "$E/product.py" \
  '    if not s or s == "-" or "선택안함" in s:' '    if not s or s == "-" or s == "nan" or "선택안함" in s:' \
  test_product_eol_sheet "$T"

plant_replace P5 "흠 ③ 고쳐 버림 — C15 NaN 을 0 으로" "$E/product.py" \
  '    return value if value else 0.0' '    return value if value and value == value else 0.0' \
  test_investment_sheet "$T"

plant_replace P6 "C12 이름 갈래 끔 — 코드가 없으면 바로 평균(T1)" "$E/product.py" \
  '        if product:
            return lookup_waste_ef(waste_c5, product, treatment)
' '' \
  test_product_eol_sheet "$T"

plant_replace P7 "C15 배출량을 단위 붙은 이름으로(T2)" "$E/product.py" \
  '        df["배출량"] = [' '        df["배출량(tCO2e)"] = [' \
  test_investment_sheet "$T"

plant_replace P8 "PRODUCT_KEYS 에서 c15 뺌(T5)" "$E/pipeline.py" \
  'frozenset({"c12", "c15"})' 'frozenset({"c12"})' \
  test_product_eol_sheet "$T"

plant_replace P9 "serialize 가 C12 biogenic 을 빼먹음(T1·T4)" "$E/serialize.py" \
  '        "biogenic": _biogenic(meta.biogenic),' '        "biogenic": None,' \
  test_product_eol_sheet "$T"

plant_replace P10 "factorSheets 에서 폐기물_C12 를 맨 앞으로(T3)" "$E/pipeline.py" \
  '    sheets = (
        activity.transport,' '    sheets = (
        product.waste_c12,
        activity.transport,' \
  test_product_eol_sheet "$T"

plant_replace P11 "폐기물_C12 코드 칸을 수로 읽음 — str_cols 끔(T3)" "$E/factor_book.py" \
  '    codes = list(WASTE_C12_CODE_COLUMNS)' '    codes: list[str] = []' \
  test_product_eol_sheet "$T"

plant_replace P13 "C12 이름 생물기원에서 not big 지움(검증 권고 R2)" "$E/product.py" \
  '        elif product and not big:' '        elif product:' \
  test_product_eol_sheet "$T"

plant_replace P12 "dump C15 item 을 「비고」 로(T6)" "$I/tests/scope3colab_dump.py" \
  '"C15": ("피투자기업명",),' '"C15": ("비고",),' \
  test_scope3colab_dump "$DUMP"

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
