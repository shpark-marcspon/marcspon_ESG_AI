#!/usr/bin/env bash
# S3C-b2b(MARC-TICK-218)의 심은 파손(발주서 §3-2 P1~P14 + 검증 R1 의 P15): 엔진 판 colab_157 에 파손 하나를 심고, 그것을 물어야 할 시험이
#   빨개지는지 본다.  BASE 21d9345(merge band/S3C-b2a). 꼴은 planted-breaks-S3C-b2a.sh 그대로.
#   사용: apps/api-py/scripts/planted-breaks-S3C-b2b.sh --commit <1|2>
#   커밋 ① 은 P1~P7. ② 는 전부(① 몫 + P8~P15).
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

I=esgapi/inventory
E=esgapi/inventory/engines/scope3/colab_157
T=esgapi/inventory/tests/engines/scope3/colab_157

backup="$(mktemp -d /private/tmp/pb-s3cb2b.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cb2b.*) ;; *) exit 99 ;; esac
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
TV="$T/test_travel.py"
plant_replace P1 "flight 비교를 startswith(\"flight\") 로(T2)" "$E/travel.py" \
  'geo_mode = "air" if mode.value == "flight" else' 'geo_mode = "air" if mode.value.startswith("flight") else' \
  test_travel "$TV"

plant_replace P2 "출장 계수 or car 를 is None 으로(T2)" "$E/travel.py" \
  '    ef = ef_map.factors.get(mode.value) or ef_map.factors.get(TRAVEL_EF_FALLBACK_CODE)' \
  '    ef = ef_map.factors.get(mode.value) if mode.value in ef_map.factors else ef_map.factors.get(TRAVEL_EF_FALLBACK_CODE)' \
  test_travel "$TV"

plant_replace P3 "통근 교차검증 100 km → 101(T3)" "$E/constants.py" \
  'COMMUTE_AI_CHECK_KM: Final = 100' 'COMMUTE_AI_CHECK_KM: Final = 101' \
  test_travel "$TV"

plant_replace P4 "버스+지하철 평균 지움(T3)" "$E/travel.py" \
  '    if _has_bus_and_subway(mode_text):' '    if False:' \
  test_travel "$TV"

plant_replace P5 "출장·통근 맵을 다시 읽은 db 로(T4)" "$E/factor_book.py" \
  '    initial = load_ef_sheet(book, sheet_name, header_row=header)' \
  '    initial, _ = ef_reload_sheet_auto(book, sheet_name, ["표준코드", "EF"])' \
  test_travel "$TV"

plant_replace P6 "통근 근무일수 기본 245 → 250(T3)" "$E/constants.py" \
  'COMMUTE_DEFAULT_WORKDAYS: Final = 245' 'COMMUTE_DEFAULT_WORKDAYS: Final = 250' \
  test_travel "$TV"

plant_replace P7 "C6-1 녹이기 ValueError 를 막음(T1)" "$E/travel.py" \
  'value_name="이동횟수", annual_col_hint=' 'value_name="이동횟수_", annual_col_hint=' \
  test_travel "$TV"

if [ "$COMMIT" = "2" ]; then
  # ── 커밋 ② 몫 ──
  TS="$T/test_travel_sheet.py"
  plant_replace P8 "후처리를 시트마다(합친 view 안 씀)(T5)" "$E/pipeline.py" \
    '            fixed = postprocess_category(activity, category, [p for *_, p in waiting])' \
    '            fixed = tuple(postprocess_category(activity, category, [p])[0] for *_, p in waiting)' \
    test_travel_sheet "$TS"
  plant_replace P9 "후처리를 고리 안으로(T6)" "$E/pipeline.py" \
    '                waiting = (len(outcomes), sheet.name, processor, done.pending)
                pending.setdefault(done.pending.category, []).append(waiting)' \
    '                done = postprocess_category(activity, done.pending.category, [done.pending])[0]' \
    test_travel_sheet "$TS"
  plant_replace P10 "_fix_result_c6 왕복계수를 늘 2(T2)" "$E/travel.py" \
    '    factor = round_trip_factor(row)
    emission_t = dist * factor' '    factor = 2
    emission_t = dist * factor' \
    test_travel_sheet "$TS"
  plant_replace P11 "SUPPORTED_KEYS 에서 c7 지움(T7)" "$E/pipeline.py" \
    '"c6_dist", "c6_spend", "c7", "c5"}' '"c6_dist", "c6_spend", "c5"}' \
    test_travel_sheet "$TS"
  plant_replace P12 "serialize 가 workdays 빼먹음(T7)" "$E/serialize.py" \
    '        "workdays": decimal_text(distance.workdays),' '        "workdays": None,' \
    test_travel_sheet "$TS"
  plant_replace P13 "거리 길을 안 부른 줄에도 geoMode(T9)" "$E/activity.py" \
    'calc.code if calc.measured else None' 'calc.code' \
    test_travel_sheet "$TS"
  plant_replace P14 "칸 값을 집었는가 대신 via 글자로 가림(T9)" "$E/activity.py" \
    'main_loop = main_loop_via is not None and dist.picked' 'main_loop = dist.distance_via != "input"' \
    test_transport_sheet "$T"
  plant_replace P15 "_fix_result_c6 인원 차례 뒤집기(검증 R1·V3, T5)" "$E/travel.py" \
    '    people = fix_num(row.get("출장인원") or row.get("인원수")) or 1
    trips = fix_num(row.get("이동횟수")) or 1
    factor = round_trip_factor(row)' '    people = fix_num(row.get("인원수") or row.get("출장인원")) or 1
    trips = fix_num(row.get("이동횟수")) or 1
    factor = round_trip_factor(row)' \
    test_travel_sheet "$TS"
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
