#!/usr/bin/env bash
# 밴드 S3R2 의 심은 파손(verify 밖, 밴드 몫). 하나씩 심고 → 그 시험이 빨개지는지 → 되돌린다.
#   사용: apps/api-py/scripts/planted-breaks-S3R2.sh [P…]     (기본 P1~P18)
# P15 = 대조 1(ENT-294) 의 dump sha — 판 rest(C3 든 판)의 머리 dump JSON·결과 파일 내용 sha 가 BASE 사본으로 지은 것
#       (S3R2_OUT/c3/rest.base.*, S3R2_OUT/compare1.sh 가 지음)과 달라야 한다. 기준(심기 전)이 같지 않으면 P15 는 GREEN(!) 로 셈.
# P16 = 표 밖 하나(같은 엑셀 줄 #n), P17 = 검증 V3(run_to_dict 가 names 를 안 넘김), P18 = 검증 R1(고르는 판정의 strip).
# P10b = P10 의 경로 판(T4, django_db) — S3R2_DB=1 이고 그 워크트리 compose 의 postgres·storage 가 떠 있을 때만 센다.
# 되돌림은 심기 전 사본(S3R2_OUT/planted/)에서. 끝에 고칠 파일들의 sha 를 심기 전과 견준다(FINGERPRINT=same).
# 끝 줄: PLANTED=<빨강>/<전체> FINGERPRINT=same|changed
# R5(검증 권고·감독 처분): 심을 자리를 못 찾거나 심은 뒤 고칠 파일 지문이 그대로면 그 P 는 NOT-PLANTED 로 전체에만 센다.
#   인자 없이 돌면 전체 = 기대 수(S3R2_DB=1 이면 19, 아니면 18 — P10b 뺌)여야 한다. 아니면 실패.
# ★ esg-app main 의 .git/verify.lock 이 있으면 돌지 않는다. LLM 실호출 0(모의 공급사만), 컨테이너 0.
set -uo pipefail
cd "$(dirname "$0")/.."   # apps/api-py
API=$(pwd)
WEB=$(cd ../web && pwd)
OUT=${S3R2_OUT:-$(cd ../../.. && pwd)/S3R2.out}/planted
LOCK=/Users/leedongeon/Desktop/marcspon/esg-app/.git/verify.lock
mkdir -p "$OUT"
if [ -e "$LOCK" ]; then echo "verify.lock 있음 — 돌지 않는다"; exit 3; fi
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

SER=esgapi/inventory/engines/scope3/colab_157/serialize.py
SHP=esgapi/inventory/contracts/shapes.py
PIN="esgapi/inventory/tests/data/flow-shapes/scope3.colab.result@1.schema.json"
OAPI=generated/openapi.json
FAKE=$WEB/src/entities/ghg-scope3/api/testing.ts
ENG=esgapi/inventory/engines/scope3/colab_157/energy.py
TARGETS=("$SER" "$SHP" "$PIN" "$OAPI" "$FAKE" "$ENG")
C3OUT=${S3R2_OUT:-$(cd ../../.. && pwd)/S3R2.out}/c3
LABIN=/Users/leedongeon/Desktop/marcspon/esg-lab/out/S3R2/rest/inputs
T_IN=esgapi/inventory/tests/engines/scope3/colab_157/test_serialize_input.py
BASE_REV=${S3R2_BASE:-07d04fa5}

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
check() {  # check <P> <설명> <명령…> — 명령이 실패(빨강)해야 한다
  local p=$1 what=$2; shift 2
  total=$((total + 1)); CHECKED=1
  if [ "$(fingerprint)" = "$before" ]; then echo "$p NOT-PLANTED $what :: 심은 뒤 지문이 그대로"; restore; return 0; fi
  "$@" > "$OUT/$p.log" 2>&1
  local code=$?
  local names
  names=$(grep -E '^FAILED ' "$OUT/$p.log" | sed -E 's/^FAILED //; s/ - .*//' | head -3 | tr '\n' ';')
  [ -n "$names" ] || names=$(grep -E '^ +× ' "$OUT/$p.log" | head -3 | tr '\n' ';')
  if [ $code -ne 0 ]; then red=$((red + 1)); echo "$p RED  $what :: ${names:-exit $code}"; else echo "$p GREEN(!) $what"; fi
  restore
}
pt() { uv run --frozen pytest -q --no-header -p no:cacheprovider -m "not django_db" "$@"; }
vt() { (cd "$WEB" && pnpm exec vitest run src/entities/ghg-scope3/api/server.test.ts); }

# dump1 — 판 rest 를 머리로 dump(+결과 파일) 해 BASE 것과 견준다: 같으면 0, 다르면(또는 실패) 1
xsha() { uv run --frozen python -I -c '
import hashlib, sys, zipfile
z = zipfile.ZipFile(sys.argv[1]); h = hashlib.sha256()
for n in sorted(z.namelist()):
    if n == "docProps/core.xml": continue
    h.update(n.encode() + b"\0" + z.read(n) + b"\0")
print(h.hexdigest())' "$1"; }
dump1() {
  local tp bk an
  tp=$(find "$LABIN" -maxdepth 1 -name '*.xlsx' | head -1); bk=$(find "$LABIN" -mindepth 2 -name '*.xlsx' | head -1)
  an=/Users/leedongeon/Desktop/marcspon/esg-lab/py/scope3colab/answers.rest.synthetic.json
  rm -f "$OUT/P15.rf.xlsx" "$OUT/P15.ff.xlsx"
  env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.inventory.tests.scope3colab_dump --template "$tp" \
    --factor-book "$bk" --answers "$an" --result-file "$OUT/P15.rf.xlsx" --filled-file "$OUT/P15.ff.xlsx" > "$OUT/P15.dump.json" || return 1
  local d=0 r=0
  cmp -s "$OUT/P15.dump.json" "$C3OUT/rest.base.dump.json" || d=1
  [ "$(xsha "$OUT/P15.rf.xlsx")" = "$(xsha "$C3OUT/rest.base.rf.xlsx")" ] || r=1
  echo "dump JSON 다름=$d · 결과 파일 내용 다름=$r"
  [ "$d$r" = 00 ]
}

want() { [ $# -eq 0 ] || [[ " $* " == *" $P "* ]]; }
ARGS=("$@")
run_p() {
  P=$1
  want "${ARGS[@]+"${ARGS[@]}"}" || return 0
  CHECKED=0
  case $P in
  P1) py $SER '"c1": {"country": ("국가",), "site": ("사업장",), "name": ("품목명",)}' \
           '"c1": {"country": ("국가",), "site": ("사업장",), "name": ("분류",)}' \
      && check P1 "C1 name 을 분류 열에서" pt $T_IN ;;
  P2) ALL=1 py $SER '"name": ("자재명", "제품명")' '"name": ("제품명", "자재명")' \
      && check P2 "C4 후보 열 차례 뒤집음" pt $T_IN -k "two_candidate or once_per_category or every_processor" ;;
  P3) py $SER '_LEASED: Final = {"country": ("국가",), "name": ("자산명",)' '_LEASED: Final = {"country": ("국가",), "name": ("임차자산명",)' \
      && check P3 "C8 name 을 바꿈 전 이름(임차자산명)에서" pt $T_IN -k "t1 or t2" ;;
  P4) py $SER '        return decimal_text(value)  # NaN·inf → None' '        return decimal_text(value) or "nan"' \
      && check P4 'NaN 을 "nan" 글로' pt $T_IN -k "missing_columns" ;;
  P5) py $SER '        return decimal_text(value)  # NaN·inf → None' '        return str(value)' \
      && check P5 "수를 str(value) 로" pt $T_IN -k "value_forms" ;;
  P6) py $SER '                row["input"] = _input(processor.key, values, name_column)' \
           '                row["input"] = _input(processor.key, frame.iloc[min(i + 1, len(frame) - 1)], name_column)' \
      && check P6 "values 를 다음 줄에서" pt $T_IN -k "t2 or own_frame_row" ;;
  P7) py $SER '                row["input"] = _input(processor.key, values, name_column)' \
           '                row = {"rowId": row["rowId"], "input": _input(processor.key, values, name_column), **{k: v for k, v in row.items() if k != "rowId"}}' \
      && check P7 "input 을 rowId 뒤로" pt $T_IN -k "t3_rows_fit or last_key" ;;
  P8) git show "$BASE_REV:apps/api-py/$PIN" > "$PIN" \
      && check P8 "고정 스키마를 다시 안 뽑음" pt esgapi/inventory/tests/test_flow_shapes.py -k pinned ;;
  P9) git show "$BASE_REV:apps/api-py/$OAPI" > "$OAPI" \
      && check P9 "openapi 를 다시 안 뽑음" uv run --frozen pytest -q --no-header -p no:cacheprovider esgapi/config/tests/test_api_contract.py ;;
  P10) ALL=1 py $SHP '    input: NotRequired[ColabRowInputJson]' '    input: ColabRowInputJson' \
      && check P10 "input 을 늘 있는 칸으로" pt $T_IN -k "old_body" ;;
  P11) py "$FAKE" "    originSteps: [origin('group')],
    missing: [],
    input: rowInput," "    originSteps: [origin('group')],
    missing: []," \
      && check P11 "웹 가짜(구매 줄)에서 input 뺌" vt ;;
  P12) py $SER '                row["input"] = _input(processor.key, values, name_column)' \
           '                row["input"] = _input(processor.key, values, name_column)
                if processor.key == "c9_spend":
                    row["mode"] = {"value": str(values.get("운송수단")), "origin": "rule"}' \
      && check P12 "C9-2 mode 를 입력 운송수단으로" pt $T_IN -k "mode_stays_null" ;;
  P13) py $SER '        out[field] = None if column is None or column not in values.index else input_text(values[column])
    return out' '        out[field] = None if column is None or column not in values.index else input_text(values[column])
    out["비고"] = input_text(values.get("비고"))
    return out' \
      && check P13 "input 에 닫힌 목록 밖 열(비고)" pt $T_IN -k "closed_list or rejects_unknown or t3" ;;
  P14) py $SER '"c2": {"country": ("국가",), "site": ("사업장",), "name": ("자산명",)}' \
            '"c2": {"country": ("국가",), "site": ("사업장",), "name": ("품목/자산명",)}' \
      && check P14 "C2 name 을 품목/자산명(그룹)에서" pt $T_IN -k "group_name or every_processor" ;;
  P16) py $SER '                row["input"] = _input(processor.key, values, name_column)' \
            '                row["input"] = _input(processor.key, frame.iloc[-1] if "#" in ids[i] else values, name_column)' \
      && check P16 "(표 밖) 같은 엑셀 줄(#n) 줄의 input 을 다른 줄에서" pt $T_IN -k "own_frame_row" ;;
  P15) dump1 > "$OUT/P15.base-check.log" 2>&1 || { total=$((total + 1)); CHECKED=1; echo "P15 GREEN(!) 기준(심기 전)이 BASE 와 같지 않음 — $OUT/P15.base-check.log"; return 0; }
      py $ENG '        rename["연료/에너지명"] = "에너지원"' '        pass  # P15' \
      && check P15 "C3 표준화 이름 바꿈(연료/에너지명→에너지원) 지움 — 대조 1 dump sha" dump1 ;;
  P10b) [ "${S3R2_DB:-0}" = 1 ] || { CHECKED=1; return 0; }   # 컨테이너(postgres·storage)가 떠 있을 때만 — 경계 ②
      ALL=1 py $SHP '    input: NotRequired[ColabRowInputJson]' '    input: ColabRowInputJson' \
      && check P10b "input 을 늘 있는 칸으로 — 경로의 옛 결과(T4)" env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY \
           scripts/test-business.sh esgapi/inventory/tests/service/apis/test_scope3_runs_input.py -p no:cacheprovider ;;
  P17) py $SER '"sheets": [sheet_to_dict(outcome, factor_column, names) for outcome in result.sheets],' \
            '"sheets": [sheet_to_dict(outcome, factor_column) for outcome in result.sheets],' \
      && check P17 "(검증 V3) run_to_dict 가 names 를 안 넘김 — 시트 단위로 고름" pt $T_IN -k "b1 or r1" ;;
  P18) py $SER '    return text is not None and text.strip() != ""' '    return text is not None' \
      && check P18 "(R1) 고르는 판정에서 공백 글도 값으로 침" pt $T_IN -k "r1" ;;
  esac
  if [ "$CHECKED" = 0 ]; then total=$((total + 1)); echo "$P NOT-PLANTED :: 심을 자리를 못 찾음"; restore; fi
}
for p in P1 P2 P3 P4 P5 P6 P7 P8 P9 P10 P10b P11 P12 P13 P14 P15 P16 P17 P18; do run_p $p; done
restore
trap - EXIT
after=$(fingerprint)
expect_ok=1
if [ ${#ARGS[@]} -eq 0 ]; then
  expect=$([ "${S3R2_DB:-0}" = 1 ] && echo 19 || echo 18)
  [ "$total" -eq "$expect" ] || { expect_ok=0; echo "기대 수 $expect 인데 전체 $total"; }
fi
echo "PLANTED=$red/$total FINGERPRINT=$([ "$before" = "$after" ] && echo same || echo changed)"
[ "$red" -eq "$total" ] && [ "$before" = "$after" ] && [ "$expect_ok" = 1 ]
