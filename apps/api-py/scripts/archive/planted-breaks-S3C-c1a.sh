#!/usr/bin/env bash
# S3C-c1a(MARC-TICK-340)의 심은 파손(발주서 §3-2 P1~P15 + R1 P16 + R3~R5 P17~P19): 엔진 판 colab_157·계약에 파손 하나를 심고, 그것을 물어야 할 시험이
#   빨개지는지 본다.  BASE c009fa99(merge band/GPW1). 꼴은 planted-breaks-S3C-b2b.sh 그대로.
#   사용: apps/api-py/scripts/planted-breaks-S3C-c1a.sh --commit <1|2>
#   커밋 ① 은 P1~P7. ② 는 전부(① 몫 + P8~P15 + 감독 권고 R1 의 P16 + 검증 권고 R3·R4·R5 의 P17~P19).
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
case "$COMMIT" in 1|2) ;; *) echo "--commit 1 또는 2" >&2; exit 2 ;; esac

I=esgapi/inventory
E=esgapi/inventory/engines/scope3/colab_157
T=esgapi/inventory/tests/engines/scope3/colab_157

backup="$(mktemp -d /private/tmp/pb-s3cc1a.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cc1a.*) ;; *) exit 99 ;; esac
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

VOCAB="$I/tests/flows/test_vocab.py"

# ── 커밋 ① 몫 ──
plant_replace P1 "사슬 1단 건너뜀 — 셀 25 판이 셀 24(:479·폴백)로 넘기지 않음(T1)" "$E/energy.py" \
  '    name, ef_legacy, unit, legacy_via = lookup_energy_ef_6822(db, energy_name)' \
  '    name, ef_legacy, unit, legacy_via = None, None, None, "none"' \
  test_energy_chain "$T"

plant_replace P2 "fuzzy 문턱 0.72 → 0.73(T1)" "$E/constants.py" \
  'ENERGY_FUZZY_THRESHOLD: Final = 0.72' 'ENERGY_FUZZY_THRESHOLD: Final = 0.73' \
  test_energy_chain "$T"

plant_replace P3 "폴백 계수 「휘발유」 지움(T1)" "$E/constants.py" \
  '    "휘발유": ("휘발유", 2.30, "L"),
' '' \
  test_energy_chain "$T"

plant_replace P4 "AI 배수 캐시 끔 — 부를 때마다 새 캐시(T2)" "$E/energy.py" \
  '    return ai_unit_conversion_factor(context, cache, input_unit, base, energy_name)' \
  '    return ai_unit_conversion_factor(context, UnitFactorCache(), input_unit, base, energy_name)' \
  test_energy_units "$T"

plant_replace P5 "발열량 다리 도시가스(LNG) 38.5 → 38.6(T2)" "$E/constants.py" \
  '    "도시가스(LNG)": ("Nm³", 38.5),' '    "도시가스(LNG)": ("Nm³", 38.6),' \
  test_energy_units "$T"

plant_replace P6 "새 kind investment 를 계약에서 뺌(T6·T9)" "$I/contracts/shapes.py" \
  '"product_eol", "franchise", "investment"
]' '"product_eol", "franchise"
]' \
  test_energy_shapes "$T" "$VOCAB"

plant_replace P7 "엔진 Literal 에만 kind 하나 더함(T9)" "$E/energy.py" \
  '"product_eol", "franchise", "investment"
]' '"product_eol", "franchise", "investment", "virtual_kind"
]' \
  test_vocab "$T" "$VOCAB"

if [ "$COMMIT" = "2" ]; then
  # ── 커밋 ② 몫 ──
  DUMP="$I/tests/test_scope3colab_dump.py"
  plant_replace P8 "C3 「사용량」 을 환산 뒤 값으로 덮음(T3)" "$E/energy.py" \
    '    out["EF매핑명"] = found.name' \
    '    out["EF매핑명"] = found.name
    out["사용량"] = usage' \
    test_energy_sheet "$T"

  plant_replace P9 "C3 월별/연간 차례 뒤집음 — 연간 줄이 먼저(T3·T8)" "$E/energy.py" \
    '    return melt_monthly_or_annual(df, month_var_name="사용월", value_name="사용량", annual_col_hint="연간사용량")' \
    '    melted = melt_monthly_or_annual(df, month_var_name="사용월", value_name="사용량", annual_col_hint="연간사용량")
    return melted.sort_values("입력방식", key=lambda s: s.eq("월별"), kind="stable")' \
    test_energy_sheet "$T" "$DUMP"

  plant_replace P10 "C8·C13 면적·인원을 앞 정의(:5375)처럼 — 건물전체 월별사용량을 접지 않음(T4)" "$E/energy.py" \
    '    df = collapse_monthly_to_value(df, "건물전체사용량", annual_cols=["건물전체사용량", "건물전체 연간사용량"])' \
    '    df = df.copy()' \
    test_energy_sheet "$T"

  plant_replace P11 "dump C13 이어 셈을 시트마다 1부터(T8)" "$I/tests/scope3colab_dump.py" \
    '        for part in parts:
' '        for part in parts:
            n = 0 if key == "C13" else n
' \
    test_scope3colab_dump "$DUMP"

  plant_replace P12 "ENERGY_KEYS 에서 c8_area 뺌(T7)" "$E/pipeline.py" \
    '{"c3", "c8_energy", "c8_area", "c8_person",' '{"c3", "c8_energy", "c8_person",' \
    test_energy_sheet "$T"

  plant_replace P13 "serialize 가 allocation 을 빼먹음(T4·T6)" "$E/serialize.py" \
    '    match, allocation = meta.match, meta.allocation' '    match, allocation = meta.match, None' \
    test_energy_sheet "$T"

  plant_replace P14 "dump C8 item 후보 차례 뒤집음(T8)" "$I/tests/scope3colab_dump.py" \
    '"C8": ("에너지원", "에너지종류"),' '"C8": ("에너지종류", "에너지원"),' \
    test_scope3colab_dump "$DUMP"

  plant_replace P15 "C8·C13 본 고리가 사슬에 단위 힌트를 넘김(T4)" "$E/energy.py" \
    '    found = lookup_energy_ef(run.energy.frame, energy_name)' \
    '    found = lookup_energy_ef(run.energy.frame, energy_name, unit_raw)' \
    test_energy_sheet "$T"

  # 감독 권고 R1(10-27): C3 별칭의 가스 차례(`:9069` — 힌트 없음이면 도시가스 먼저)
  plant_replace P16 "C3 별칭 가스 차례 뒤집음 — 힌트 없어도 천연가스 먼저(R1)" "$E/energy.py" \
    '        if u == "kg":
            add("천연가스(LNG)", "도시가스(LNG)")
        else:
            add("도시가스(LNG)", "천연가스(LNG)")' \
    '        if u == "kg":
            add("천연가스(LNG)", "도시가스(LNG)")
        else:
            add("천연가스(LNG)", "도시가스(LNG)")' \
    test_energy_sheet "$T"

  # 경계 2 검증 권고 R3·R4·R5(10-27) — 시험만 얹고 셈 코드는 0줄
  plant_replace P17 "폴백 계수 산정 출처를 rule 로(R3 — 발주서 2-2 estimate)" "$E/energy.py" \
    '"estimate" if via == "fallback_patch" else "rule"' '"rule"' \
    test_energy_sheet "$T"

  plant_replace P18 "배분 분모 0 이면 비율 0.0(R4 — 코랩은 None)" "$E/energy.py" \
    '        if not total:
            return None' '        if not total:
            return 0.0' \
    test_energy_sheet "$T"

  plant_replace P19 "C3 계수 0 에서도 배출량을 셈(R5 — 코랩 and ef_val)" "$E/energy.py" \
    '    emission = (usage * ef_val / 1000) if (usage is not None and ef_val) else None' \
    '    emission = (usage * ef_val / 1000) if (usage is not None and ef_val is not None) else None' \
    test_energy_sheet "$T"
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
