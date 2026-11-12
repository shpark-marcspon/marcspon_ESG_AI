#!/usr/bin/env bash
# S3V1(MARC-TICK-575)의 심은 파손(발주서 §3): 계수 책 v1.1 · 양식 v2.2 · 출장 Spend 조각 견줌 · C5 출처 글 · C8/C13 용어.
#   BASE efa07262. 꼴은 archive/planted-breaks-S3C-r1.sh 그대로(git 을 쓰지 않는다 — 베껴 둔 바이트로 되쓴다).
#   사용: apps/api-py/scripts/planted-breaks-S3V1.sh        (P7 은 Postgres 가 떠 있어야 한다 — test-business.sh)
# xlsx 파손은 zip 부품 하나의 글자를 「정확히 한 번」 바꿔 다시 묶는다(그 밖 부품 바이트는 그대로).
# 줄마다  <id> <심은 것> → 빨강|초록|죽음 (<실패한 시험 파일>) 기대 <낱말> 맞음|다름.  끝에 FINGERPRINT=same|differs, PLANTED=<맞음>/<심은 수>.
# 종료 0 은 「PLANTED 가 다 맞음 ∧ 지문이 같음」일 때뿐이다. lock(main 저장소 .git/verify.lock)이 있으면 돌지 않는다.
set -u
cd "$(dirname "$0")/.."

MAIN_GIT="$(git rev-parse --git-common-dir)"
if [ -e "$MAIN_GIT/verify.lock" ]; then echo "verify.lock 있음 — 돌지 않는다" >&2; exit 3; fi

I=esgapi/inventory
D="$I/data/scope3"
BOOK="$D/scope3-factor-book.xlsx"
TPL="$D/scope3-template-v2.2.xlsx"
TB="$I/tests/service/utils/test_scope3_packaged_book.py"
TT="$I/tests/service/utils/test_scope3_packaged_template.py"
TS="$I/tests/service/utils/test_scope3_sources.py"
TST="$I/tests/service/utils/test_scope3_state.py"
TF="$I/tests/flows/test_binding_157.py"
TV="$I/tests/engines/scope3/colab_157/test_travel_spend.py"
TA="$I/tests/service/apis/test_scope3_runs.py"
NON_DB=("$TB" "$TT" "$TS" "$TST" "$TF" "$TV")

backup="$(mktemp -d /private/tmp/pb-s3v1.XXXXXX)"
case "$backup" in /private/tmp/pb-s3v1.*) ;; *) exit 99 ;; esac
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
  shasum -a 256 "$BOOK" "$TPL"
}
fingerprint > "$backup/.fingerprint-before"

keep() { cp "$1" "$backup/$(echo "$1" | tr / _)"; touched+=("$1"); }

replace_once() { # <파일> <옛> <새>
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

zip_replace() { # <xlsx> <부품> <옛 정규식> <새>   — 정규식이 정확히 한 번 맞을 때만(count=all 이면 모두, 하나 이상)
  python3 -I - "$1" "$2" "$3" "$4" "${5:-one}" <<'PY'
import re, sys, zipfile, io
path, part, old, new, mode = sys.argv[1:6]
src = zipfile.ZipFile(path)
infos = src.infolist()
data = {i.filename: src.read(i.filename) for i in infos}
src.close()
text = data[part].decode()
out, n = re.subn(old, new, text)
if (mode == "one" and n != 1) or n == 0:
    sys.exit(1)
data[part] = out.encode()
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w") as dst:
    for info in infos:
        zi = zipfile.ZipInfo(info.filename, date_time=info.date_time)
        zi.compress_type = zipfile.ZIP_DEFLATED
        zi.external_attr = info.external_attr
        dst.writestr(zi, data[info.filename])
open(path, "wb").write(buf.getvalue())
PY
}

RED=""; RC=0
run_tests() { # <db|plain> <시험 경로…>
  local kind="$1"; shift
  if [ "$kind" = db ]; then
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider -rf "$@" > "$backup/run.txt" 2>&1
  else
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider -rf -m "not django_db" "$@" > "$backup/run.txt" 2>&1
  fi
  RC=$?
  grep "^FAILED " "$backup/run.txt" | sed -e 's/^FAILED //' -e 's/ - .*//' -e 's|.*/||' | sort -u > "$backup/red.txt"
  RED="$(tr '\n' ',' < "$backup/red.txt" | sed 's/,$//')"
}

planted=0; expected=0
report() { # <id> <설명> <기대 낱말>
  local verdict ok="다름"
  case "$RC" in 0) verdict="초록" ;; 1) verdict="빨강" ;; *) verdict="죽음(종료 $RC)" ;; esac
  if [ "$RC" = 1 ]; then case ",$RED," in *"$3"*) ok="맞음" ;; esac; fi
  planted=$((planted + 1))
  [ "$ok" = "맞음" ] && expected=$((expected + 1))
  printf '%s %s → %s (%s) 기대 %s %s\n' "$1" "$2" "$verdict" "${RED:-없음}" "$3" "$ok"
}
cant() { printf '%s %s → 못 심음 다름\n' "$1" "$2"; planted=$((planted + 1)); restore; }

plant_text() { # <id> <설명> <파일> <옛> <새> <기대 낱말> <db|plain> <시험…>
  local id="$1" what="$2" file="$3" old="$4" new="$5" want="$6" kind="$7"; shift 7
  keep "$file"
  if ! replace_once "$file" "$old" "$new"; then cant "$id" "$what"; return; fi
  run_tests "$kind" "$@"; restore; report "$id" "$what" "$want"
}

plant_zip() { # <id> <설명> <xlsx> <부품> <옛 정규식> <새> <one|all> <기대 낱말> <시험…>
  local id="$1" what="$2" file="$3" part="$4" old="$5" new="$6" mode="$7" want="$8"; shift 8
  keep "$file"
  if ! zip_replace "$file" "$part" "$old" "$new" "$mode"; then cant "$id" "$what"; return; fi
  run_tests plain "$@"; restore; report "$id" "$what" "$want"
}

# ── 계수 책 ──
plant_zip P1 "책에 Scope 1·2 시트 이름 하나 남김(환율_참조 — 전력_국가별 부품을 가리킴)" "$BOOK" xl/workbook.xml \
  '(<sheet name="전력_국가별" sheetId="11" r:id="rId11"/>)' '\1<sheet name="환율_참조" sheetId="10" r:id="rId11"/>' one \
  test_the_book_has_the_scope3_sheets_only "${NON_DB[@]}"
plant_zip P2 "책 lastModifiedBy 되살림(지어낸 사람 이름)" "$BOOK" docProps/core.xml \
  '<cp:lastModifiedBy></cp:lastModifiedBy>' '<cp:lastModifiedBy>가상인물</cp:lastModifiedBy>' one \
  test_the_person_cells_are_empty "${NON_DB[@]}"
plant_zip P3 "구매_USEPA 수식 칸 저장 값 지움(openpyxl 다시 저장 꼴)" "$BOOK" xl/worksheets/sheet7.xml \
  '(</f>)<v>[^<]*</v>' '\1' all \
  test_the_purchase_sheet_keeps_its_saved_values "${NON_DB[@]}"
# ── 양식 ──
plant_zip P4 "운송 Spend 드롭다운에 책에 없는 이름(E9 ← 옛 「내륙 수로 화물」)" "$TPL" xl/worksheets/sheet23.xml \
  '<c r="E9" s="46" t="s"><v>555</v></c>' '<c r="E9" s="46" t="s"><v>480</v></c>' one \
  test_the_transport_spend_dropdown_is_the_book_names "${NON_DB[@]}"
plant_zip P5 "정의된 이름만 \$E\$19 그대로(빈 칸 항목)" "$TPL" xl/workbook.xml \
  '(DD_TRANSPORT_SPEND">배출계수_드롭다운!\$E\$3:\$E\$)9<' '\g<1>19<' one \
  test_the_transport_spend_dropdown_is_the_book_names "${NON_DB[@]}"
plant_zip P6 "회사 이름 칸 하나를 지어낸 다른 이름으로(회사별_교통수단매핑 E2 저장 값)" "$TPL" xl/worksheets/sheet26.xml \
  '(<c r="E2" t="str"><f>[^<]*</f><v>)예시기업(</v>)' '\1가상회사갑\2' one \
  test_the_company_cells_are_the_example_only "${NON_DB[@]}"
plant_text P7 "FILE_NAME 옛 판" "$I/service/actions/scope3_runs.py" \
  'FILE_NAME: Final = "Scope3_템플릿_수정본_v2.2.xlsx"' 'FILE_NAME: Final = "Scope3_템플릿_수정본_v2.1.xlsx"' \
  test_scope3_runs db "$TA"
plant_text P8 "책 sha 상수 옛 값" "$TF" \
  '"scope3-factor-book.xlsx": "2b76427c174a90d3f43ff7a5cc6032795924d9bd90eeda8ad5571874b59a036b"' \
  '"scope3-factor-book.xlsx": "f658e1a258e7b9292107230434c66e51491e3339d7e81f19133ed83676cec42f"' \
  test_binding_157 plain "${NON_DB[@]}"
# ── 엔진 ──
plant_text P9 "spend.py:209 되돌림(조각 견줌 → 통째 같음)" "$I/engines/scope3/colab_157/spend.py" \
  'db[[title in [p.strip() for p in t.split(" / ")] for t in colab_str(db[title_col])]]' \
  'db[[t.strip() == title for t in colab_str(db[title_col])]]' \
  test_travel_spend plain "${NON_DB[@]}"
plant_text P10 "waste.py:57 마지막 「배출계수」 열" "$I/engines/scope3/colab_157/waste.py" \
  '    ef_col = next((c for c in columns if "배출계수" in c), None)' \
  '    ef_col = next((c for c in reversed(columns) if "배출계수" in c), None)' \
  test_the_c5_lookup_takes_the_first_factor_column plain "${NON_DB[@]}"
plant_text P11 "Q9 알려진 다름에 한 줄 더" "$TB" \
  'frozenset({("폐지류", "기타"), ("폐목재류", "기타")})' 'frozenset({("폐지류", "기타"), ("폐목재류", "기타"), ("가상", "기타")})' \
  test_the_c5_origin_column_matches_the_engine_rule_but_the_known_rows plain "${NON_DB[@]}"
plant_zip P12 "에너지_C3 남긴 「도시가스(LNG) Nm³」 줄 이름을 천연가스로(결정 MARC-ENT-654 줄 사라짐 — 뒤집힌 P12)" "$BOOK" xl/worksheets/sheet2.xml \
  '<c r="B5" s="208" t="s"><v>16</v></c>' '<c r="B5" s="208" t="s"><v>18</v></c>' one \
  test_the_c3_sheet_keeps_the_city_gas_nm3_row "${NON_DB[@]}"
# ── 러너 표 밖 ──
plant_text P13 "C5 출처 글(MARC-ENT-634 답) 바꿈" "$I/service/utils/scope3_sources.py" \
  'HEAD_GIVEN: Final = {"폐기물_C5": "환경부 환경성적표지"}' 'HEAD_GIVEN: Final = {"폐기물_C5": "환경부 EPD"}' \
  test_scope3_sources plain "${NON_DB[@]}"
plant_text P14 "C8 용어 옛 글(덧 5)" "$I/service/utils/scope3_state.py" \
  '    "C8": "업스트림 임차 자산",' '    "C8": "상류 임차 자산",' \
  test_scope3_state plain "${NON_DB[@]}"
plant_zip P15 "책 core.xml 에 이름 담는 칸(dc:title) 더함" "$BOOK" docProps/core.xml \
  '(<dc:creator>openpyxl</dc:creator>)' '\1<dc:title>가상인물</dc:title>' one \
  test_the_other_name_parts_hold_no_person "${NON_DB[@]}"

restore
fingerprint > "$backup/.fingerprint-after"
same="same"
if ! cmp -s "$backup/.fingerprint-before" "$backup/.fingerprint-after"; then
  same="differs"; echo "작업 트리가 처음과 다르다:"; diff "$backup/.fingerprint-before" "$backup/.fingerprint-after"
fi
echo "FINGERPRINT=$same"
echo "PLANTED=$expected/$planted"
[ "$expected" -eq "$planted" ] && [ "$same" = "same" ] && exit 0
exit 1
