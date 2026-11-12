#!/usr/bin/env bash
# 밴드 PY6(MARC-TICK-53)의 심은 파손 스물하나. 컨테이너 없이 돈다.
#   사용: apps/api-py/esgapi/reconcile/tests/planted-breaks-PY6.sh        마지막 줄 PLANTED=<잡은 수>/<심은 수>
# 규칙을 하나씩 망가뜨리고, 그것을 잡아야 할 테스트(또는 계약)가 빨개지는지 본다.
# 심기 전의 파일을 임시 폴더에 베껴 두었다가 되돌린다(git 을 쓰지 않는다). 끝나면 작업 트리가 처음과 같아야 한다.
#
# ★ 발주서의 10번(`unmasked_values` 가 늘 빈 목록)은 심지 못한다: 그 함수를 이 밴드가 옮기지 않았다(감독 결정 2026-10-08).
#   그 자리에 같은 파일(mask.py)의 다른 파손을 심었다: `mask_text` 가 값 후보를 하나만 가린다.
set -u
cd "$(dirname "$0")/../../.."     # apps/api-py
backup="$(mktemp -d)"
log="$(mktemp)"
before="$( { git status --porcelain; git diff; find esgapi/reconcile esgapi/core/ports esgapi/core/adapters esgapi/config/env.py -name '*.py' -exec shasum {} +; } | shasum | cut -d' ' -f1)"
touched=""
restore() { [ -n "$touched" ] && cp "$backup/file" "$touched"; touched=""; }
trap 'restore; rm -rf "$backup" "$log"' EXIT

plant() { # <파일> <바꿀 글> <바꾼 글>   글이 정확히 한 번 있어야 한다
  cp "$1" "$backup/file"; touched="$1"
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심지 못함: {path} 에 바꿀 글이 {text.count(old)}번 있다")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
total=0; caught=0
verdict() { # <설명> <잡아야 할 테스트 이름(또는 계약)의 조각> [더 잡아야 할 조각 …]   $log 에 방금 돌린 출력이 있다
  total=$((total + 1))
  local what="$1"; shift
  local ok=1 piece
  for piece in "$@"; do
    grep -E '^(FAILED|ERROR) |BROKEN' "$log" | grep -q -- "$piece" || ok=0
  done
  if [ "$ok" = 1 ]; then caught=$((caught + 1)); echo "잡힘    $what"; else echo "★ 못 잡음  $what"; fi
  echo "          잡아야 할 것: $*"
  echo "          빨간 것 $(grep -c -E '^(FAILED|ERROR) |BROKEN$' "$log") 개 / 요약: $(grep -E '^[0-9]+ (passed|failed)|^Contracts:' "$log" | tail -1)"
  restore
}
pure() { uv run --frozen pytest -q -m "not django_db and not security" esgapi/reconcile esgapi/core/tests/test_parser_port.py >"$log" 2>&1; }
N=esgapi/reconcile/calc/notation.py
F=esgapi/reconcile/calc/facts.py
K=esgapi/reconcile/calc/kinds.py
A=esgapi/core/adapters/parser.py

echo "── 심지 않음: 이 밴드의 순수 층이 초록인가"
pure; tail -1 "$log"
echo

plant $N '            if suffix == "" and sign == "none" and _is_year_integer(num):' '            if False:'
pure
verdict "1. classify_cell 이 year_like 표시를 안 붙임" "test_cell_keeps_sign_and_suffix_as_marks" "test_year_label_is_a_comma_less_year_in_a_numeric_cell"

plant $N '                start=start,
                end=end,' '                start=len(from_units(units[:start])),
                end=len(from_units(units[:end])),'
pure
verdict "2. scan_numbers 의 자리를 코드포인트로 냄" "test_the_positions_from_scan_numbers_give_the_expected_boxes" "test_python_equals_the_committed_ts_dump\[facts\]"

plant $N '    if no_pct and _ORDINAL_AFTER.match(after) and not unit_after and not _JO_DIGIT.match(after) and "," not in num:
        return "ordinal"
    if no_pct and _YEAR_AFTER.match(after) and _is_year_integer(num):
        return "year"' '    if no_pct and _is_year_integer(num) and not unit_after and not _LATIN.search(following):
        return "year"
    if no_pct and _ORDINAL_AFTER.match(after) and not unit_after and not _JO_DIGIT.match(after) and "," not in num:
        return "ordinal"
    if no_pct and _YEAR_AFTER.match(after) and _is_year_integer(num):
        return "year"'
pure
verdict "3. scan_numbers 의 갈래 차례를 바꿈(연도 판정을 ORDINAL_AFTER 앞으로)" "test_the_order_of_the_branches_is_the_meaning"

plant $F '            if row in header_rows or col in header_cols:' '            if False:'
pure
verdict "4. grid_facts 가 머리글 행·열의 숫자를 값 후보로" "test_header_years_page_columns_no_value_markers_and_page_numbers_are_not_candidates"
# 같은 파손을 네 문서 골든도 잡는가(TS 덤프가 있을 때만. 없으면 그렇다고 적는다).
if [ -f .lab-golden/ts/kb_2025_kor.json ]; then
  plant $F '            if row in header_rows or col in header_cols:' '            if False:'
  uv run --frozen python -m esgapi.reconcile.tests.golden.check_lab >"$log" 2>&1; code=$?
  echo "          (같은 파손, 네 문서 골든: 종료 코드 $code — 0 이 아니어야 한다. $(grep -m1 '^kb_2025_kor:' "$log"))"
  restore
else
  echo "          (네 문서 골든: .lab-golden/ts 가 없어 재지 않았다. make-golden.sh 를 먼저 돌린다)"
fi

plant $F '    return y1 <= page_height * _PAGE_MARGIN_RATIO or y0 >= page_height * (1 - _PAGE_MARGIN_RATIO)' '    return False'
pure
verdict "5. 쪽 번호 가장자리(8%) 판정을 끔" "test_page_number_needs_the_page_margin_and_a_short_integer"

plant $F '                    id=f"{block.id}#n{index + 1}",' '                    id=f"{block.id}#n{sum(1 for f in facts if f.where.block_id == block.id) + 1}",'
pure
verdict "6. 블록 속 숫자의 ID 순번(#n<k>)을 값 후보만 세어 매김" "test_numbers_in_text_cells_sentences_and_number_only_blocks_get_buckets" "test_python_equals_the_committed_ts_dump\[facts\]"

plant $F '        extraction = replace(extraction, kinds=classify_kinds(document, extraction))' '        found_kinds = classify_kinds(document, extraction)
        kept = tuple(fact for fact in extraction.facts if found_kinds[fact.id] == "value")
        extraction = replace(extraction, kinds=found_kinds, facts=kept)'
pure
verdict "7. 종류를 켜면 값이 아닌 것을 목록에서 뺌" "test_turning_kinds_on_keeps_every_candidate"

plant $K '        left = f"{block.page}|L{js_round(x0 / _COLUMN_SNAP)}"' '        left = f"{block.page}|L{round(x0 / _COLUMN_SNAP)}"'
pure
verdict "8. kinds 의 세로줄 열쇠에 파이썬 round()" "test_the_column_key_rounds_half_up_like_math_round" "test_python_equals_the_committed_ts_dump\[kinds\]"

plant esgapi/reconcile/calc/mask.py "        return f\"{MASK}{fact.unit_suffix or ''}\"" '        return MASK * len(fact.raw)'
pure
verdict "9. cell_text 가 숫자를 자릿수만큼의 기호로 가림(길이 누출)·단위 접미를 지움" "test_the_mask_is_one_symbol_whatever_the_number_of_digits" "test_no_candidate_number_is_left_and_header_years_and_row_names_stay"

plant esgapi/reconcile/calc/mask.py '    values = [token for token in scan_numbers(text) if token.kind == "value"]' '    values = [token for token in scan_numbers(text) if token.kind == "value"][:1]'
pure
verdict "10. (바꿔 심음) mask_text 가 값 후보를 하나만 가림" "test_the_mask_is_one_symbol_whatever_the_number_of_digits" "test_python_equals_the_committed_ts_dump\[masks\]"

plant esgapi/reconcile/calc/places.py '_SAME_LINE_RATIO: Final = 0.5' '_SAME_LINE_RATIO: Final = 0.0'
pure
verdict "11. same_line 의 문턱(절반)을 0 으로" "test_lines_that_overlap_by_less_than_half_stay_two_boxes"

plant $F 'import re
from collections.abc import Sequence' 'import django  # noqa: F401
import re
from collections.abc import Sequence'
COLUMNS=400 uv run --frozen lint-imports >"$log" 2>&1
uv run --frozen pytest -q -m "not django_db and not security" esgapi/reconcile/tests/test_calc_is_pure.py >>"$log" 2>&1
verdict "12. calc/facts.py 에 import django → 계약 (다) + 허용 목록 테스트" "다\\. 순수 모듈" "test_calc_imports_only_the_allowed_modules"

plant $A '            kind: ParseFailureKind = "rejected" if 400 <= err.code < 500 else "unavailable"' '            kind: ParseFailureKind = "rejected"'
pure
verdict "13. http 어댑터가 5xx 를 rejected 로" "test_5xx_is_unavailable"

plant $A '            headers={"Content-Type": "application/pdf"},' '            headers={"Content-Type": "application/json"},'
pure
verdict "14. http 어댑터가 Content-Type: application/json 으로 보냄" "test_the_request_is_exactly_the_contract"

plant $A '    char_places: Any = fields.get("charPlaces")' '    char_places: Any = fields.get("char_places")'
pure
verdict "15. decode_response 가 charPlaces 대신 char_places 키를 읽음" "test_200_with_the_envelope_is_parsed_with_no_warnings" "test_missing_char_places_is_an_invalid_response_not_a_warning"

plant esgapi/reconcile/services/parse.py '        if not same_source(document, places.places):' '        if False:'
pure
verdict "16. parse_and_extract 가 sha256 이 다른 글자 자리를 받아들임" "test_places_from_another_pdf_are_refused_and_no_box_comes_out"

plant esgapi/config/env.py '        if parts.scheme not in ("http", "https") or not parts.hostname:' '        if False:'
pure
verdict "17. PARSER_URL 의 틀린 꼴을 그대로 받음" "test_a_wrong_address_is_a_listed_problem_not_accepted"

plant $N 'NUMBER_BODY: Final = r"[0-9]{1,3}(?:,[0-9]{3})+(?![0-9])(?:\.[0-9]+)?|[0-9]+(?:\.[0-9]+)?"' 'NUMBER_BODY: Final = r"\d{1,3}(?:,\d{3})+(?!\d)(?:\.\d+)?|\d+(?:\.\d+)?"'
pure
verdict "18. ASCII 숫자 클래스([0-9])를 \\d 로" "test_python_equals_the_committed_ts_dump\[facts\]" "test_only_ascii_digits_are_digits"

plant $N '_JS_WORD_NEXT: Final = "(?=[A-Za-z0-9_])"' '_JS_WORD_NEXT: Final = r"\b"'
pure
verdict "19. 위\\b·기\\b·종\\b 를 파이썬 \\b 그대로" "test_python_equals_the_committed_ts_dump\[nonValues\]" "test_js_word_boundary_treats_hangul_as_a_non_word"

plant $K '_SENTENCE_END: Final = re.compile(r"[.。] ?\Z")' '_SENTENCE_END: Final = re.compile(r"[.。] ?$")'
pure
verdict "20. \\Z 를 \$ 로 (종류 규칙이 보는 블록 원문의 \`.\\n\` 뒤 숫자)" "test_python_equals_the_committed_ts_dump\[kinds\]" "test_a_period_then_a_newline_is_not_the_end_of_the_text"

plant $A '        except urllib.error.HTTPError as err:
            try:' '        except urllib.error.URLError as err:
            return _failed("unavailable", f"파서에 닿지 못했다: {err}")
        except urllib.error.HTTPError as err:
            try:'
pure
verdict "21. 어댑터의 except 차례를 바꿈(URLError 먼저)" "test_4xx_is_rejected_with_the_parsers_error_code"

after="$( { git status --porcelain; git diff; find esgapi/reconcile esgapi/core/ports esgapi/core/adapters esgapi/config/env.py -name '*.py' -exec shasum {} +; } | shasum | cut -d' ' -f1)"
echo
[ "$before" = "$after" ] && echo "되돌림: 작업 트리가 심기 전과 같다" || echo "★ 되돌림 실패: 작업 트리가 달라졌다"
echo "PLANTED=$caught/$total"
[ "$caught" = "$total" ] && [ "$before" = "$after" ]
