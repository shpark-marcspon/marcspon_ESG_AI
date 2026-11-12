#!/usr/bin/env bash
# S3C-r1(MARC-TICK-354)의 심은 파손(발주서 §3-2): 커밋 1 은 읽개 `tools/xlsx_reader.py`(MARC-ISSUE-241 — 절대 Target·
#   inlineStr·빈 수식 값·t="b"), 커밋 2 는 엔진 colab_157 의 코랩과 다르게 옮긴 자리(MARC-ISSUE-395). BASE 4ee85e0d.
#   꼴은 planted-breaks-S3C-c2.sh 그대로.
#   사용: apps/api-py/scripts/planted-breaks-S3C-r1.sh --commit 1|2
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
case "$COMMIT" in 1 | 2) ;; *) echo "--commit 1|2" >&2; exit 2 ;; esac

I=esgapi/inventory
E=esgapi/inventory/engines/scope3/colab_157
T=esgapi/inventory/tests/engines/scope3/colab_157

backup="$(mktemp -d /private/tmp/pb-s3cr1.XXXXXX)"
case "$backup" in /private/tmp/pb-s3cr1.*) ;; *) exit 99 ;; esac
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

R="$I/tools/xlsx_reader.py"
RL="$I/tests/test_s3sheets_reader_limits.py"
RR="$I/tests/test_s3sheets_reader.py"
RD="$I/tests/test_scope3colab_dump.py"

if [ "$COMMIT" = 1 ]; then
  plant_replace P1 "절대 Target 의 xl/ 앞머리 검사 뺌(/docProps/… 를 받음)" "$R" \
    '            if not part.startswith("xl/") or "" in part.split("/"):' \
    '            if "" in part.split("/"):' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"

  plant_replace P2 "앞 / 를 하나가 아니라 모두 뗌(//xl/… 를 받음)" "$R" \
    '            part = target[1:]' '            part = target.lstrip("/")' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"

  plant_replace P3 "절대 꼴에서 .. 검사 건너뜀" "$R" \
    '        if "\\" in target or ".." in target.split("/") or ":" in target:' \
    '        if "\\" in target or (".." in target.split("/") and not target.startswith("/")) or ":" in target:' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"

  plant_replace P4 "겹침 검사를 푼 이름이 아니라 (시트 이름, 관계 id) 로" "$R" \
    '        if len(set(paths)) != len(paths):' '        if len(set(sheet_refs)) != len(sheet_refs):' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"

  plant_replace P5 "inlineStr 을 첫 <t> 만" "$R" \
    '                    cells[address] = TextCell(_string_item(inline))' \
    '                    cells[address] = TextCell(next(iter(inline.itertext()), ""))' \
    test_s3sheets_reader "$RL" "$RR" "$RD"

  plant_replace P6 "<is> 없는 inlineStr → TextCell(\"\")" "$R" \
    '                if inline is not None:  # <is> 가 없으면 칸 없음(openpyxl 이 None 을 쓴 꼴)
                    cells[address] = TextCell(_string_item(inline))' \
    '                cells[address] = TextCell(_string_item(inline) if inline is not None else "")' \
    test_s3sheets_reader "$RL" "$RR" "$RD"

  plant_replace P7 "<f> 없는 빈 <v/> 도 None 으로 받음" "$R" \
    '    if cell_type == "n" and in_formula and text == "":' '    if text == "":' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"

  plant_replace P8 "<rPh> 글자를 붙임" "$R" \
    '        elif child.tag == f"{_MAIN}r":' '        elif child.tag in (f"{_MAIN}r", f"{_MAIN}rPh"):' \
    test_s3sheets_reader "$RL" "$RR" "$RD"

  plant_replace P17 "빈 수식 값 None 을 t 갈래 없이(t=\"s\" 수식 + 빈 <v/> 를 받음 — 경계 1 검증 B1)" "$R" \
    '    if cell_type == "n" and in_formula and text == "":' '    if in_formula and text == "":' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"

  plant_replace P16 "t=\"b\" 의 0·1 밖 값을 받음(감독 보정 1)" "$R" \
    '        if text not in ("0", "1"):' '        if text == "":' \
    test_s3sheets_reader_limits "$RL" "$RR" "$RD"
fi

EN="$E/energy.py"
PL="$E/pipeline.py"
OF="$E/output_files.py"
TC="$T/test_energy_chain.py"
TU="$T/test_energy_units.py"
TP="$T/test_product_use_sheet.py"
TR="$T/test_result_file.py"

if [ "$COMMIT" = 2 ]; then
  plant_replace P9 "6822 의 try 를 걷음(:479 예외가 시트를 깨뜨림)" "$EN" \
    '    try:
        name, ef, unit = lookup_energy_ef_479(db, energy_name)
    except Exception:
        name, ef, unit = None, None, None' \
    '    name, ef, unit = lookup_energy_ef_479(db, energy_name)' \
    test_energy_chain "$TC" "$TU" "$TP" "$TR"

  plant_replace P11 "_u_norm 을 옛 꼴로(0·False → 「0」·「false」)" "$EN" \
    '    return str(u or "").strip()' \
    '    return ("" if u is None or (isinstance(u, str) and u == "") else str(u)).strip()' \
    test_energy_units "$TC" "$TU" "$TP" "$TR"

  plant_replace P12 "활동 갈래 if fixed is None → if not fixed(빈 튜플을 예외로)" "$PL" \
    '        if fixed is None:' '        if not fixed:' \
    test_product_use_sheet "$TC" "$TU" "$TP" "$TR"

  plant_replace P13 "format(…, \".16g\") → repr(16자리 자름 없음)" "$OF" \
    '    xml = format(value, ".16g")' '    xml = repr(value)' \
    test_result_file "$TC" "$TU" "$TP" "$TR"

  plant_replace P18 "제품 갈래 if fixed_products is None → if not fixed_products(감독 보정 5)" "$PL" \
    '            if fixed_products is None:' '            if not fixed_products:' \
    test_product_use_sheet "$TC" "$TU" "$TP" "$TR"

  plant_replace P19 "detect_energy_name 이 모르는 이름을 원래 객체로(NaN 맥락의 「차이 없음」 시험이 무는지)" "$EN" \
    '    return str(raw)
' '    return raw  # type: ignore[return-value]
' \
    test_energy_units "$TC" "$TU" "$TP" "$TR"
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
