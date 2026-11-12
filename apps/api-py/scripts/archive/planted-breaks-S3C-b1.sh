#!/usr/bin/env bash
# S3C-b1(MARC-TICK-208)의 심은 파손(발주서 §3-2 P1~P19): 엔진 판 colab_157 에 파손 하나를 심고, 그것을 물어야 할 시험이
#   빨개지는지 본다.  BASE 78d779e(merge band/S3C-b0).
#   사용: apps/api-py/scripts/planted-breaks-S3C-b1.sh --commit <1|2>
#   커밋 ① 은 P1·P8a·P8b·P10·P11·P12·P13·P17·P18. ② 는 전부(① 몫 + P2~P7·P9·P14~P16·P19).
#   ② 몫은 경계 ② 에서 아래 「커밋 ② 몫」 칸에 채운다 — 채우기 전에는 「P? not defined」를 찍고 셈에 넣어 종료 1(조용히 넘어가지 않는다).
# 심기 전의 파일을 임시 폴더에 베껴 두었다가 그 바이트로 되쓴다(git 을 쓰지 않는다 — checkout·stash·restore·reset 0).
#   끝나면 작업 트리가 처음과 같아야 한다: 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 셈에 들어가 다름이 된다.
# 표적 시험은 시험 폴더 colab_157 통째. 빨강 = pytest 종료 1 이고, 실패한 시험 노드 가운데 하나라도 기대 낱말(파일 이름 조각)을
#   품음. 종료 2 이상(수집 실패 등)은 「죽음」 — 다름.
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
case "$COMMIT" in 1|2) ;; *) echo "--commit 1 또는 2" >&2; exit 2 ;; esac

E=esgapi/inventory/engines/scope3/colab_157
T=esgapi/inventory/tests/engines/scope3/colab_157

backup="$(mktemp -d /private/tmp/pb-s3cb1.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cb1.*) ;; *) exit 99 ;; esac
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

undefined() { # <id> <설명>  — 경계 ② 에서 채울 자리
  printf '%s %s → %s not defined 다름\n' "$1" "$2" "$1"
  planted=$((planted + 1))
}

# ── 커밋 ① 몫 ──
plant_replace P1 "ef_auto_header_row 의 머리글 낱말 점수 20 → 0" "$E/factor_book.py" \
  "                    score += 20" "                    score += 0" \
  test_factor "$T"

plant_replace P8a "units: AI 캐시가 None 을 기억 안 함" "$E/units.py" \
  "    cache.factors[key] = factor" "    if factor is not None:
        cache.factors[key] = factor" \
  test_units "$T"

plant_replace P8b "travel_mode: AI 캐시가 None 을 기억 안 함" "$E/travel_mode.py" \
  "    cache.modes[text] = found" "    if found is not None:
        cache.modes[text] = found" \
  test_travel_mode "$T"

plant_replace P10 "_TREATMENT_ALIAS 에서 「기타」 지움" "$E/constants.py" \
  '    "기타": "기타", "other": "기타", "etc": "기타",
' '    "other": "기타", "etc": "기타",
' \
  test_waste "$T"

plant_replace P11 "생물기원을 소각 밖에도" "$E/waste.py" \
  "    if fcf is None or not incineration_tco2e:" "    if fcf is None:" \
  test_waste "$T"

plant_replace P12 "회사별 매핑이 찬 칸도 덮음" "$E/company_mapping.py" \
  'blank_mask = (cur.isna() | (stripped == "") | (stripped.str.lower() == "none")).astype(bool)' \
  'blank_mask = (cur.isna() | (stripped == "") | (stripped.str.lower() == "none") | True).astype(bool)' \
  test_company_mapping "$T"

plant_replace P13 "JSON_RETRY_SUFFIX 한 글자(반드시 → 반드시!)" "$E/llm.py" \
  "반드시" "반드시!" \
  test_llm "$T"

plant_replace P17 "purchase: hint_origin 을 「사용자 아님 → ai」 로" "$E/purchase.py" \
  'hint_origin = group.origin if not user_hint else "rule"' 'hint_origin = "ai" if not user_hint else "rule"' \
  test_origin "$T"

plant_replace P18 "purchase: 낱말 조각 +15 를 그룹 몫으로" "$E/purchase.py" \
  "                keyword_score += 15" "                group_score += 15" \
  test_origin "$T"

if [ "$COMMIT" = "2" ]; then
  # ── 커밋 ② 몫 — 경계 ② 에서 undefined 줄을 plant_replace 로 갈아 끼운다(발주서 §3-2 의 빨강 칸이 기대 낱말) ──
  plant_replace P2 "get_spend_ef_col: 원화 열 대신 USD 열 먼저(S2)" "$E/spend.py" \
    '    krw_col = find_precomputed_krw_ef_col(db, year)
    if krw_col:
        return krw_col
    return find_usd_ef_col(db)' '    usd_col = find_usd_ef_col(db)
    if usd_col:
        return usd_col
    return find_precomputed_krw_ef_col(db, year)' \
    test_transport_spend "$T"

  plant_replace P3 "lookup_transport_spend_ef: 확장 힌트를 안 붙임 — expanded = q(S2)" "$E/spend.py" \
    "        expanded = f\"{q} {TRANSPORT_CODE_TO_SPEND_HINT.get(code, '')}\".strip()" "        expanded = q" \
    test_transport_spend "$T"

  plant_replace P4 "옛 판 :865 의 기본 제목(General Freight Trucking, Local) 대안 지움(S2)" "$E/spend.py" \
    '    default = db[colab_str(db[title_col]).str.contains("General Freight Trucking, Local", na=False, regex=True)]' \
    '    default = db.iloc[0:0]' \
    test_transport_spend "$T"

  plant_replace P5 "옛 판 :865 가 q=\"\" 면 찾지 않음(버릇 지움, S2)" "$E/spend.py" \
    '    q = str(mode_or_item).strip().lower()
' '    q = str(mode_or_item).strip().lower()
    if not q.strip():
        return None
' \
    test_transport_spend "$T"

  plant_replace P6 "출장 점수 100+len → 101+len(S3)" "$E/spend.py" \
    "                score += 100 + len(kn)" "                score += 101 + len(kn)" \
    test_travel_spend "$T"

  plant_replace P7 "출장 Spend /1000 지움(S3)" "$E/spend.py" \
    "    emission_t = (spend_krw * ef / 1000.0) if ef is not None else None" \
    "    emission_t = (spend_krw * ef) if ef is not None else None" \
    test_travel_spend "$T"

  plant_replace P9 "C5 row.get(\"단위\") or \"kg\" 를 NaN 이면 kg 로(S4)" "$E/waste.py" \
    '    unit_str = fix_text(row.get("단위") or "kg")' '    unit_str = fix_text(row.get("단위")) or "kg"' \
    test_waste_sheet "$T"

  plant_replace P14 "SUPPORTED_KEYS 에서 c5 지움(S7)" "$E/pipeline.py" \
    'ACTIVITY_KEYS: Final[frozenset[str]] = frozenset({"c4_spend", "c9_spend", "c6_spend", "c5"})' \
    'ACTIVITY_KEYS: Final[frozenset[str]] = frozenset({"c4_spend", "c9_spend", "c6_spend"})' \
    test_pipeline "$T"

  plant_replace P15 "serialize 가 kind 빼먹음(S8)" "$E/serialize.py" \
    '        "kind": "purchase",
' '' \
    test_serialize_activity "$T"

  plant_replace P16 "줄 origin 을 factor 단계만으로(S8)" "$E/activity.py" \
    'numeric: list[ColabOrigin] = [s.origin for s in steps if s.step in _NUMERIC_STEPS]' \
    'numeric: list[ColabOrigin] = [s.origin for s in steps if s.step == "factor"]' \
    test_serialize_activity "$T"

  plant_replace P19 "serialize 가 활동 줄 factor 키 차례를 바꿈(S8 key_order[colab:activity])" "$E/serialize.py" \
    '            "sheet": factor.sheet,
            "title": factor.title,
' '            "title": factor.title,
            "sheet": factor.sheet,
' \
    test_shapes esgapi/inventory/tests/contracts/test_shapes.py
fi

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
