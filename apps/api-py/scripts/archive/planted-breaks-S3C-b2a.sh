#!/usr/bin/env bash
# S3C-b2a(MARC-TICK-209)의 심은 파손(발주서 §3-2 P1~P17): 엔진 판 colab_157 에 파손 하나를 심고, 그것을 물어야 할 시험이
#   빨개지는지 본다.  BASE ff6ba81(merge band/G1b-2b). 꼴은 planted-breaks-S3C-b1.sh 그대로.
#   사용: apps/api-py/scripts/planted-breaks-S3C-b2a.sh --commit <1|2>
#   커밋 ① 은 P1~P10·P18~P20(검증 B1). ② 는 전부(① 몫 + P11~P17·P21~P22 — 검증 B2).
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

backup="$(mktemp -d /private/tmp/pb-s3cb2a.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cb2a.*) ;; *) exit 99 ;; esac
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
plant_replace P1 "geodesic 을 Geodesic.WGS84(m) ÷ 1000 으로(D1)" "$E/distance.py" \
  '    return float(_GEOD.Inverse(lat1, lon1, lat2, lon2, Geodesic.DISTANCE)["s12"])' \
  '    return float(Geodesic.WGS84.Inverse(lat1, lon1, lat2, lon2, Geodesic.DISTANCE)["s12"]) / 1000' \
  test_distance "$T"

plant_replace P2 "보정계수 road 1.3 → 1.0(D2)" "$E/constants.py" \
  '{"road": 1.3, "parcel": 1.35,' '{"road": 1.0, "parcel": 1.35,' \
  test_distance "$T"

plant_replace P3 "국내 상한 800 → 801(D2)" "$E/distance.py" \
  'if mode in ["road", "parcel"] and value > 800:' 'if mode in ["road", "parcel"] and value > 801:' \
  test_distance "$T"

plant_replace P4 "도시 정규화 실패를 캐시(D2)" "$E/distance.py" \
  '        raise CityNameFailed(outcome.reason)' '        run.cities[city] = city
        raise CityNameFailed(outcome.reason)' \
  test_distance "$T"

plant_replace P5 "지오코더 물음에 늘 , KR(D2)" "$E/distance.py" \
  'country_hint if country_hint == "KR" else None)' '"KR")' \
  test_distance "$T"

plant_replace P6 "IATA 세 글자 갈래 지움(D2)" "$E/distance.py" \
  '    return bool(re.fullmatch(r"[A-Za-z]{3}", t.strip()))' '    return False' \
  test_distance "$T"

plant_replace P7 "AI 직선 프롬프트 한 글자(D3)" "$I/prompts/scope3-colab-distance-straight/1.md" \
  '직선거리(대권거리' '직선거리 (대권거리' \
  test_distance "$T"

plant_replace P8 "옛 판 운송수단(:1153) 건너뜀(D4)" "$E/transport.py" \
  '        mode, source = infer_transport_mode_1153(row)' '        mode, source = "unknown", "default"' \
  test_transport_mode "$T"

plant_replace P9 "운송 계수 맵을 첫 읽기로(D5)" "$E/factor_book.py" \
  '    if not reloaded.empty:
        return FactorSheetRead(sheet_name, reloaded, "reloaded", header)' '    if not reloaded.empty and sheet_name != TRANSPORT_SHEET:
        return FactorSheetRead(sheet_name, reloaded, "reloaded", header)' \
  test_transport_mode "$T"

plant_replace P10 "무게 AI 실패 1배 → None(D6)" "$E/transport.py" \
  'WeightConversion(v * 1.0, "ai_failed")' 'None' \
  test_transport_mode "$T"

plant_replace P18 "AI 실거리 None 을 캐시 안 함(검증 B1, D2)" "$E/distance.py" \
  '    run.road[key] = value' '    if value is not None:
        run.road[key] = value' \
  test_distance "$T"

plant_replace P19 "AI 직선 None 을 캐시 안 함(검증 B1, D2)" "$E/distance.py" \
  '    run.straight[key] = value' '    if value is not None:
        run.straight[key] = value' \
  test_distance "$T"

plant_replace P20 "공항 AI None 을 캐시 안 함(검증 B1, D2)" "$E/distance.py" \
  '    run.airports[key] = name' '    if name is not None:
        run.airports[key] = name' \
  test_distance "$T"

if [ "$COMMIT" = "2" ]; then
  # ── 커밋 ② 몫 ──
  TR="$T/test_transport_sheet.py"
  plant_replace P11 "본 고리 mode 를 추정 mode 로(D6)" "$E/activity.py" \
    'found = get_distance_km(run.distances, row2.get("출발지"), row2.get("도착지"))' \
    'found = get_distance_km(run.distances, row2.get("출발지"), row2.get("도착지"), __import__("esgapi.inventory.engines.scope3.colab_157.transport", fromlist=["x"]).infer_transport_mode(run.llm, run.transport_modes, pd.Series(row2, dtype=object)).code)' \
    test_transport_sheet "$TR"
  plant_replace P12 "본 고리 country 를 국가 칸으로(D6)" "$E/activity.py" \
    'found = get_distance_km(run.distances, row2.get("출발지"), row2.get("도착지"))' \
    'found = get_distance_km(run.distances, row2.get("출발지"), row2.get("도착지"), "road", str(row2.get("국가") or "KR"))' \
    test_transport_sheet "$TR"
  plant_replace P13 "표준화 무게 or → is None(D6)" "$E/transport.py" \
    '        if given:  # 코랩' '        if given is not None:  # 코랩' \
    test_transport_sheet "$TR"
  plant_replace P14 "SUPPORTED_KEYS 에서 c4_dist 지움(D8)" "$E/pipeline.py" \
    '{"c4_dist", "c4_spend", "c9_dist",' '{"c4_spend", "c9_dist",' \
    test_pipeline "$T"
  plant_replace P15 "serialize 가 distance 빼먹음(D9)" "$E/serialize.py" \
    '        "distance": _distance(distance),' '        "distance": None,' \
    test_transport_sheet "$TR"
  plant_replace P16 "줄 origin 에서 distance 단계 뺌(D9)" "$E/activity.py" \
    'frozenset(
    {"mapping", "unit", "fx", "factor", "mode", "distance"}
)' 'frozenset(
    {"mapping", "unit", "fx", "factor", "mode"}
)' \
    test_transport_sheet "$TR"
  plant_replace P17 "본 고리 via 를 input 으로(D6)" "$E/activity.py" \
    'main_loop_via = found.via if found.km is not None else None' 'main_loop_via = "input" if found.km is not None else None' \
    test_transport_sheet "$TR"
  plant_replace P21 "calc 무게 다시 환산에서 「화물중량」 열쇠 지움(검증 B2 W2)" "$E/transport.py" \
    '"운송량", "화물중량"]' '"운송량"]' \
    test_transport_sheet "$TR"
  plant_replace P22 "메타 무게 단계를 표준화 것만으로(검증 B2 W3)" "$E/activity.py" \
    'weight = standardized if standardized is not None else calc.weight' 'weight = standardized' \
    test_transport_sheet "$TR"
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
