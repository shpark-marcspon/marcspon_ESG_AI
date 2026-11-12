#!/usr/bin/env bash
# 밴드 S3a(MARC-TICK-66)의 심은 파손 스물다섯(1~23 은 발주서의 것, 24·25 는 검증 뒤에 더한 읽개의 둘): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3a.sh        마지막 줄 PLANTED=<잡은 수>/25
# 심기 전의 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(되돌리는 데 git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다. 다르면 PLANTED 를 내지 않고 종료 1.
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 FAILED 줄에 있다
#   (다른 까닭으로 빨개진 것을 잡았다고 세지 않는다).
# 컨테이너 0, 네트워크 0. 순수 층만 돈다. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."

A=apps/api-py
READER="$A/esgapi/inventory/xlsx_reader.py"
GRID="$A/esgapi/inventory/calc/scope3_sheets/grid.py"
FACTORS="$A/esgapi/inventory/calc/scope3_sheets/factors.py"
DROPDOWNS="$A/esgapi/inventory/calc/scope3_sheets/dropdowns.py"
CROSSCHECK="$A/esgapi/inventory/calc/scope3_sheets/crosscheck.py"
SUPPORT="$A/esgapi/inventory/tests/s3sheets_support.py"
T=esgapi/inventory/tests
T_GRID="$T/test_s3sheets_grid.py"
T_READER="$T/test_s3sheets_reader.py"
T_LIMITS="$T/test_s3sheets_reader_limits.py"
T_PURE="$T/test_s3sheets_is_pure.py"
T_SAMPLES="$T/test_s3sheets_samples.py"
T_FACTORS="$T/test_s3sheets_factors.py"
T_DROPDOWNS="$T/test_s3sheets_dropdowns.py"
T_CROSSCHECK="$T/test_s3sheets_crosscheck.py"

keep="$(mktemp -d)"          # 저장소 밖
log="$(mktemp -d)"
FILES=("$READER" "$GRID" "$FACTORS" "$DROPDOWNS" "$CROSSCHECK" "$SUPPORT")
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}" 2>&1; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

total=0; ok=0
edit() { # <파일> <있던 글자> <바꿀 글자>   글자가 정확히 한 번 있어야 한다(없으면 심지 못한 것이다: 종료 3)
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
pure_tests() { (cd "$A" && uv run --frozen pytest -q -rf -p no:cacheprovider -m "not django_db and not security" "$@"); }
# <번호와 설명> <로그 파일> <종료 코드> <FAILED 줄에 있어야 하는 테스트 이름…>
judge() {
  local name="$1" file="$2" code="$3" caught=0 wanted
  shift 3
  total=$((total + 1))
  grep -E '^[0-9]+ (passed|failed)|^FAILED' "$file" | sed 's/^/    /' | cut -c1-200 | head -6
  [ "$code" -ne 0 ] || caught=1
  for wanted in "$@"; do
    grep -q "^FAILED .*$wanted" "$file" || { caught=1; echo "    (FAILED 줄에 없다: $wanted)"; }
  done
  if [ "$caught" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  restore_files
}
# <번호> <설명> <파일> <있던 글자> <바꿀 글자> <테스트 파일> <FAILED 줄에 있어야 하는 테스트 이름…>
plant() {
  local number="$1" what="$2" file="$3" old="$4" new="$5" tests="$6" code
  shift 6
  edit "$file" "$old" "$new" || exit 3
  pure_tests "$tests" > "$log/$number.txt" 2>&1; code=$?
  judge "$number. $what" "$log/$number.txt" "$code" "$@"
}

# ── 경계 ①: 읽힌 표와 읽개 ──
plant 1 "읽개가 <rPh> 의 <t> 도 잇는다" "$READER" \
  'elif child.tag == f"{_MAIN}r":' 'elif child.tag in (f"{_MAIN}r", f"{_MAIN}rPh"):' \
  "$T_READER" test_phonetic_text_is_not_appended
plant 2 "파서의 DOCTYPE 거절을 뺌" "$READER" \
  'raise _Rejected("doctype", "", f"DOCTYPE 선언({name})이 있다")' 'return None' \
  "$T_LIMITS" test_a_doctype_is_refused_utf8 test_a_doctype_is_refused_utf16
plant 3 "decimal 에 파일 속 글자를 그대로" "$READER" \
  'return NumberCell(text, shortest)' 'return NumberCell(text, text)' \
  "$T_READER" test_the_decimal_is_the_shortest_round_trip_form
plant 4 "시트 차례를 zip 의 차례로" "$READER" \
  'for (name, _), path in zip(sheet_refs, paths, strict=True):' \
  'for (name, _), path in sorted(zip(sheet_refs, paths, strict=True), key=lambda pair: list(sizes).index(pair[1])):' \
  "$T_READER" test_sheets_come_in_workbook_order_not_zip_order
plant 5 "scope3_sheets/grid.py 가 zipfile 을 import" "$GRID" \
  $'\nimport re\n' $'\nimport re\nimport zipfile\n' \
  "$T_PURE" test_no_module_in_the_folder_imports_files_zip_xml_network_django_or_the_reader
plant 6 "표본의 계수 하나를 9. 로 시작하지 않게" "$SUPPORT" \
  'number("9.90031")' 'number("8.90031")' \
  "$T_SAMPLES" test_every_factor_in_the_sample_book_is_a_made_up_number_starting_with_nine
plant 7 "글자 없는 <f>(딸린 칸)를 수식 아닌 칸으로 읽는다" "$READER" \
  'followers.append((address, index, value))' 'cells.update({address: value} if value is not None else {})' \
  "$T_READER" test_shared_formula_followers_carry_no_formula_text
plant 8 "수의 글자 문법 검사를 빼고 float() 에 바로" "$READER" \
  'if _NUMBER.fullmatch(text) is None:' 'if False:' \
  "$T_LIMITS" 'test_number_text_outside_the_grammar_is_refused\[1_000\]' 'test_number_text_outside_the_grammar_is_refused\[ 12 \]'
plant 9 "선언된 크기의 합 검사를 뺌" "$READER" \
  'if total > MAX_OPENED_BYTES:' 'if False:' \
  "$T_LIMITS" test_opened_entries_over_the_total_limit_are_refused
plant 10 "같은 이름의 항목 거절을 뺌" "$READER" \
  'if entry.filename in sizes:' 'if False:' \
  "$T_LIMITS" test_two_entries_with_the_same_name_are_refused
plant 11 "빈 <v/> 의 t=str 를 cached=None 으로" "$READER" \
  'return TextCell(text)  # 빈 <v/> 는 빈 글자다(없음이 아니다)' 'return TextCell(text) if text else None' \
  "$T_READER" test_an_empty_stored_string_is_an_empty_text_not_none
plant 12 "범위 펼치기의 상한을 뺌" "$GRID" \
  'if range_size(cells) > MAX_RANGE_CELLS:' 'if False:' \
  "$T_GRID" test_expanding_a_range_over_the_limit_is_a_branch_not_a_list

plant 24 "STORED·DEFLATED 밖의 압축 방식 거절을 뺌" "$READER" \
  'if entry.compress_type not in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED):' 'if False:' \
  "$T_LIMITS" 'test_entries_compressed_with_anything_but_stored_or_deflated_are_refused\[lzma\]'
plant 25 "항목을 끝까지 푼 뒤에 자른다" "$READER" \
  'data = stream.read(sizes[name] + 1)' 'data = stream.read()' \
  "$T_LIMITS" test_an_entry_that_inflates_past_its_declared_size_is_refused_without_inflating_it_all

# ── 경계 ②: 계수 책 적재기 ──
plant 13 "머리글을 안 견준다" "$FACTORS" \
  'mismatches = _header_mismatches(sheet, shape)' 'mismatches: list[HeaderMismatch] = []' \
  "$T_FACTORS" test_one_different_header_letter_refuses_only_that_sheet
plant 14 "- 를 0 으로" "$FACTORS" \
  'return Placeholder(cell.text)' 'return NumberCell("0", "0")' \
  "$T_FACTORS" test_a_dash_in_a_value_cell_is_a_placeholder_not_zero
plant 15 "빈 줄에서 읽기를 멈춘다" "$FACTORS" \
  '        # 값 열에 칸이 하나라도 있으면 계수 행이다. 빈 줄 뒤에도 계속 본다(평균 줄이 뒤에 온다).' \
  '        if row - 1 not in by_row: break' \
  "$T_FACTORS" test_rows_after_a_blank_row_are_loaded
plant 16 "수식 칸을 버린다" "$FACTORS" \
  'derived.append(DerivedEntry(letter, column.header, cell.formula, master, master_formula, cell.cached))' 'pass' \
  "$T_FACTORS" test_derived_cells_are_loaded_with_master_follower_and_cached_value test_every_cell_is_accounted_for_exactly_once
plant 17 "수로 든 이름표를 글자로" "$FACTORS" \
  'labels.append(LabelEntry(letter, column.header, cell))' \
  'labels.append(LabelEntry(letter, column.header, TextCell(cell.decimal) if isinstance(cell, NumberCell) else cell))' \
  "$T_FACTORS" test_a_label_stored_as_a_number_stays_a_number
plant 18 "꼴에 없는 열의 칸을 조용히 버린다" "$FACTORS" \
  'extras.append(ExtraEntry(letter, cell))  # 머리글 없는 열의 칸. 버리지 않는다' 'pass' \
  "$T_FACTORS" test_a_cell_in_a_column_without_a_header_is_not_lost test_every_cell_is_accounted_for_exactly_once

# ── 경계 ③: 드롭다운과 어긋남 검사 ──
plant 19 "정의된 이름의 범위를 한 줄 짧게" "$DROPDOWNS" \
  'for address in addresses:' 'for address in addresses[:-1]:' \
  "$T_DROPDOWNS" test_the_eleven_named_lists_have_the_lengths_of_the_sample
plant 20 "견주기 전에 strip()" "$CROSSCHECK" \
  'key: tuple[str, ...] = (item.text,)' 'key: tuple[str, ...] = (item.text.strip(),)' \
  "$T_CROSSCHECK" test_a_trailing_space_is_not_a_match_and_is_counted_as_near
plant 21 "template_only 와 db_only 를 바꿈" "$CROSSCHECK" \
  $'            tuple(template_only),\n            tuple(db_only),\n' $'            tuple(db_only),\n            tuple(template_only),\n' \
  "$T_CROSSCHECK" test_the_direction_is_not_flipped
plant 22 "같은 짝 두 줄을 사전에 덮어씀" "$CROSSCHECK" \
  'by_key.setdefault(key, []).append(where)' 'by_key[key] = [where]' \
  "$T_CROSSCHECK" test_both_rows_of_a_repeated_pair_are_reported
plant 23 "K11 의 unit 을 단위 목록 셋의 합집합 하나와 견줌" "$CROSSCHECK" \
  'texts = {item.text for item in items}' \
  'texts = {item.text for name in MAPPING_TARGETS[group] for item in (_list_items(name, dropdowns) or [])}' \
  "$T_CROSSCHECK" test_the_unit_group_is_compared_with_each_unit_list_separately

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if ! cmp -s "$keep/.sums-before" "$keep/.sums-after" || ! cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "★ 되돌린 뒤의 파일이 처음과 다르다(sha256 이나 git status)" >&2
  diff "$keep/.sums-before" "$keep/.sums-after" >&2
  exit 1
fi
echo "되돌림 확인: sha256 $(wc -l < "$keep/.sums-after" | tr -d ' ')개 같음 · git status 같음"
echo "PLANTED=$ok/$total"
[ "$ok" -eq 25 ] && [ "$total" -eq 25 ]
