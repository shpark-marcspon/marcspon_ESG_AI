#!/usr/bin/env bash
# 밴드 S3R3 의 서버 심은 파손(verify 밖, 밴드 몫). 하나씩 심고 → 그 시험이 빨개지는지 → 되돌린다.
#   사용: apps/api-py/scripts/planted-breaks-S3R3.sh [S…]     (기본 S1~S9)
# S1~S8 = 발주서 §3 표(S7 은 critic B1 처분 판 — 「useMonths 를 required 로」). S9 = 표 밖(useMonths 를 짓지 않음 — 키 열다섯).
# S8 = 대조(T6 sha)의 짝: C11 줄 activity.value 를 baseValue(환산값)로 — test_product_use_sheet 가 잡는다.
# S7b = S7 의 경로 판(T4, django_db) — S3R3_DB=1 이고 그 워크트리 compose 의 postgres 가 떠 있을 때만 센다.
# 되돌림은 심기 전 사본(S3R3_OUT/planted/)에서. 끝에 고칠 파일들의 sha 를 심기 전과 견준다(FINGERPRINT=same).
# 심을 자리를 못 찾거나 심은 뒤 고칠 파일 지문이 그대로면 그 S 는 NOT-PLANTED 로 전체에만 센다(S3R2 R5).
#   인자 없이 돌면 전체 = 기대 수(S3R3_DB=1 이면 10, 아니면 9)여야 한다. 아니면 실패.
# 끝 줄: PLANTED=<빨강>/<전체> FINGERPRINT=same|changed
# ★ esg-app main 의 .git/verify.lock 이 있으면 돌지 않는다. LLM 실호출 0(모의 공급사만).
set -uo pipefail
cd "$(dirname "$0")/.."   # apps/api-py
OUT=${S3R3_OUT:-$(cd ../../.. && pwd)/S3R3.out}/planted
LOCK=/Users/leedongeon/Desktop/marcspon/esg-app/.git/verify.lock
mkdir -p "$OUT"
if [ -e "$LOCK" ]; then echo "verify.lock 있음 — 돌지 않는다"; exit 3; fi

SER=esgapi/inventory/engines/scope3/colab_157/serialize.py
SHP=esgapi/inventory/contracts/shapes.py
PIN="esgapi/inventory/tests/data/flow-shapes/scope3.colab.result@1.schema.json"
OAPI=generated/openapi.json
TARGETS=("$SER" "$SHP" "$PIN" "$OAPI")
T_IN=esgapi/inventory/tests/engines/scope3/colab_157/test_serialize_input.py
T_PU=esgapi/inventory/tests/engines/scope3/colab_157/test_product_use_sheet.py
BASE_REV=${S3R3_BASE:-22485a27}

fingerprint() { for f in "${TARGETS[@]}"; do shasum -a 256 "$f"; done | shasum -a 256 | cut -c1-16; }
before=$(fingerprint)
for f in "${TARGETS[@]}"; do cp "$f" "$OUT/$(echo "$f" | tr '/' '_').orig"; done
restore() { for f in "${TARGETS[@]}"; do cp "$OUT/$(echo "$f" | tr '/' '_').orig" "$f"; done; }
trap restore EXIT

# py <파일> <옛 글> <새 글> — 글이 정확히 한 번(또는 ALL=1 이면 한 번 이상) 있어야 심는다
py() {
  uv run --frozen python - "$@" <<'EOF'
import os, sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
n = text.count(old)
if n == 0 or (n > 1 and os.environ.get("ALL") != "1"):
    sys.exit(f"심을 자리 {n}개: {old[:60]!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
EOF
}

red=0; total=0
CHECKED=0
check() {  # check <S> <설명> <명령…> — 명령이 실패(빨강)해야 한다
  local p=$1 what=$2; shift 2
  total=$((total + 1)); CHECKED=1
  if [ "$(fingerprint)" = "$before" ]; then echo "$p NOT-PLANTED $what :: 심은 뒤 지문이 그대로"; restore; return 0; fi
  "$@" > "$OUT/$p.log" 2>&1
  local code=$?
  local names
  names=$(grep -E '^FAILED ' "$OUT/$p.log" | sed -E 's/^FAILED //; s/ - .*//' | head -3 | tr '\n' ';')
  if [ $code -ne 0 ]; then red=$((red + 1)); echo "$p RED  $what :: ${names:-exit $code}"; else echo "$p GREEN(!) $what"; fi
  restore
}
pt() { uv run --frozen pytest -q --no-header -p no:cacheprovider -m "not django_db" "$@"; }

want() { [ $# -eq 0 ] || [[ " $* " == *" $P "* ]]; }
ARGS=("$@")
run_p() {
  P=$1
  want "${ARGS[@]+"${ARGS[@]}"}" || return 0
  CHECKED=0
  case $P in
  S1) py $SER '        "useMonths": ("수명(개월)",),' '        "useMonths": ("제품당 연간 에너지 사용량",),' \
      && check S1 "c11 useMonths 를 제품당 연간 에너지 사용량 열에서" pt $T_IN $T_PU ;;
  S2) py $SER '    "productCount", "sales", "weight", "weightUnit", "stores", "useMonths",' \
           '    "productCount", "useMonths", "sales", "weight", "weightUnit", "stores",' \
      && check S2 "useMonths 를 INPUT_KEYS 중간에" pt $T_IN ;;
  S3) py $SER '        "useMonths": ("수명(개월)",),' '        "useMonths": ("수명(개월) 혹은 평균 사용기간(개월)",),' \
      && check S3 "원천을 바꿈 전 이름(양식 머리 글)으로 — 늘 null" pt $T_IN $T_PU ;;
  S4) py $SER '        "weightUnit": ("제품중량 단위",),
    },' '        "weightUnit": ("제품중량 단위",),
        "useMonths": ("수명(개월)",),
    },' \
      && check S4 "c12 도 useMonths 를 채움" pt $T_IN -k "outside_c11" ;;
  S5) git show "$BASE_REV:apps/api-py/$PIN" > "$PIN" \
      && check S5 "고정 스키마를 다시 안 뽑음" pt esgapi/inventory/tests/test_flow_shapes.py -k pinned ;;
  S6) git show "$BASE_REV:apps/api-py/$OAPI" > "$OAPI" \
      && check S6 "openapi 를 다시 안 뽑음" uv run --frozen pytest -q --no-header -p no:cacheprovider esgapi/config/tests/test_api_contract.py ;;
  S7) py $SHP '    useMonths: NotRequired[str | None]' '    useMonths: str | None' \
      && check S7 "useMonths 를 required 로(키 열다섯 저장 결과가 거절됨)" pt $T_IN -k "fifteen_key" ;;
  S7b) [ "${S3R3_DB:-0}" = 1 ] || { CHECKED=1; return 0; }
      py $SHP '    useMonths: NotRequired[str | None]' '    useMonths: str | None' \
      && check S7b "useMonths 를 required 로 — 경로의 키 열다섯 결과(T4)" env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY \
           scripts/test-business.sh esgapi/inventory/tests/service/apis/test_scope3_runs_input.py -p no:cacheprovider ;;
  S8) py $SER '    investment, use = meta.investment, meta.product
' '    investment, use = meta.investment, meta.product
    amount = decimal_text(activity.base_value)  # S8
' \
      && check S8 "C11 activity.value ← baseValue(환산값)" pt $T_PU ;;
  S9) py $SER '    "productCount", "sales", "weight", "weightUnit", "stores", "useMonths",' \
           '    "productCount", "sales", "weight", "weightUnit", "stores",' \
      && check S9 "(표 밖) useMonths 를 짓지 않음 — 키 열다섯 그대로" pt $T_IN ;;
  esac
  if [ "$CHECKED" = 0 ]; then total=$((total + 1)); echo "$P NOT-PLANTED :: 심을 자리를 못 찾음"; restore; fi
}
for p in S1 S2 S3 S4 S5 S6 S7 S7b S8 S9; do run_p $p; done
restore
trap - EXIT
after=$(fingerprint)
expect_ok=1
if [ ${#ARGS[@]} -eq 0 ]; then
  expect=$([ "${S3R3_DB:-0}" = 1 ] && echo 10 || echo 9)
  [ "$total" -eq "$expect" ] || { expect_ok=0; echo "기대 수 $expect 인데 전체 $total"; }
fi
echo "PLANTED=$red/$total FINGERPRINT=$([ "$before" = "$after" ] && echo same || echo changed)"
[ "$red" -eq "$total" ] && [ "$before" = "$after" ] && [ "$expect_ok" = 1 ]
