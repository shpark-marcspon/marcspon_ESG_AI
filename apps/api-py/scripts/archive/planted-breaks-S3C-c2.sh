#!/usr/bin/env bash
# S3C-c2(MARC-TICK-352)의 심은 파손(발주서 §3-2 P1~P14 + C11 열 차례의 P15): 엔진 판 colab_157 의 출력 파일 내용
#   (`output_files.py`)에 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.  BASE cb08265f(merge band/DT1).
#   꼴은 planted-breaks-S3C-c1b-2.sh 그대로.
#   사용: apps/api-py/scripts/planted-breaks-S3C-c2.sh --commit 1   (커밋 하나 — 전부)
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

backup="$(mktemp -d /private/tmp/pb-s3cc2.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cc2.*) ;; *) exit 99 ;; esac
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

O="$E/output_files.py"
FT="$T/test_filled_template.py"
RF="$T/test_result_file.py"

plant_replace P1 "배율을 /1000 나눗셈으로(T2)" "$O" \
  '        writer.set(r, ef_col, ef_val * scale)  # 곱셈(`:9431`) — 늘 float' \
  '        writer.set(r, ef_col, ef_val / (1.0 / scale))' \
  test_filled_template "$FT"

plant_replace P2 "회색 열을 줄 안 첫 칸으로(T5)" "$O" \
  '                    ef_col, ef_header_text = c, v' \
  '                    ef_col, ef_header_text = (ef_col or c), (ef_header_text or v)' \
  test_filled_template "$FT"

plant_replace P3 "병합 머리 끝 무시(T5)" "$O" \
  '                    header_end = max(header_end, cells.last.row)' '                    header_end = header_end' \
  test_filled_template "$FT"

plant_replace P4 "_EF_META_COLS 에서 배출계수기준컬럼 뺌(T5)" "$O" \
  '{"배출계수기준연도", "배출계수기준컬럼", ' '{"배출계수기준연도", ' \
  test_filled_template "$FT"

plant_replace P5 "numpy 정수도 수로 봄(T5 colab_same_defect_)" "$O" \
  '    return isinstance(v, int | float) and not isinstance(v, bool)' \
  '    return isinstance(v, int | float | np.integer) and not isinstance(v, bool)' \
  test_filled_template "$FT"

plant_replace P6 "비고 짝 → 늘 위치 짝(T2)" "$O" \
  '        if note_col_ws and note_col_df is not None:' '        if False:' \
  test_filled_template "$FT"

plant_replace P7 "회색 열 없는 시트에서 커서 안 옮김(T4)" "$O" \
  '            reports.append(FilledSheet(sheet.name, "no_gray_columns", 0, None, 0))' \
  '            cursors[category] = start
            reports.append(FilledSheet(sheet.name, "no_gray_columns", 0, None, 0))' \
  test_filled_template "$FT"

plant_replace P8 "표준화 실패 시트도 커서 옮김(T4)" "$O" \
  '            reports.append(FilledSheet(sheet.name, "standardize_failed", 0, None, 0))' \
  '            cursors[category] = cursors.get(category, 0) + 2
            reports.append(FilledSheet(sheet.name, "standardize_failed", 0, None, 0))' \
  test_filled_template "$FT"

plant_replace P9 "결과 열을 처리 뒤 frame 들의 concat 으로(후처리 열 끝 붙임 무시, T1)" "$O" \
  '    columns = _first_file_columns(frames, absent)' '    columns = _first_file_columns([p.frame for p in parts], absent)' \
  test_result_file "$RF"

plant_replace P10 "TEMPLATE_ROW 를 결과 파일에 남김(T1)" "$O" \
  'if c not in COLS_TO_DROP and c != TEMPLATE_ROW and ' 'if c not in COLS_TO_DROP and ' \
  test_result_file "$RF"

plant_replace P11 "결과 시트를 Category 번호 차례로(T1)" "$O" \
  '    return tuple(build_result_sheet(cat, ps, cat in post_failed) for cat, ps in by_category.items())' \
  '    return tuple(build_result_sheet(cat, ps, cat in post_failed) for cat, ps in sorted(by_category.items(), key=lambda kv: int(kv[0][8:])))' \
  test_result_file "$RF"

plant_replace P12 "병합 칸을 왼쪽 위로 안 보냄(T5)" "$O" \
  '            row, column = cells.first.row, cells.first.column' '            pass' \
  test_filled_template "$FT"

plant_replace P13 "None 값도 씀(T2)" "$O" \
  '        if value is None:
            return' '        if value is None:
            value = 0' \
  test_filled_template "$FT"

plant_replace P14 "표준화 다시 돌기에서 캐시를 새로(부름이 늚, T4)" "$O" \
  '            calc_c11_6961(runs.energy, row)' \
  '            calc_c11_6961(type(runs.energy)(runs.energy.energy, runs.energy.energy_c3, runs.energy.llm, type(runs.energy.units)()), row)' \
  test_filled_template "$FT"

plant_replace P15 "C11 열 차례를 처리 때 dict 꼴로(rest 판 C11 열 차례)" "$O" \
  '    if category == "Category11":' '    if False:' \
  test_result_file "$RF"

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
