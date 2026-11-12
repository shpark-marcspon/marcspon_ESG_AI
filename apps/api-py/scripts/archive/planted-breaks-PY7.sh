#!/usr/bin/env bash
# 밴드 PY7 의 심은 파손 열여섯: 규칙을 하나씩 망가뜨리고, 그것을 잡아야 할 테스트(또는 계약)가 빨개지는지 본다.
#   사용: apps/api-py/esgapi/inventory/tests/planted-breaks-PY7.sh      마지막 줄 PLANTED=<잡은 수>/<심은 수>
# 심기 전의 파일을 임시 파일에 베껴 두었다가 되돌린다(git 을 쓰지 않는다). 끝나면 작업 트리가 처음과 같아야 한다.
# 업무 층 테스트가 잡는 파손이 있어 Postgres 만 띄우고 내린다(이 저장소의 compose 프로젝트의 것뿐).
# 임시 파일은 지우지 않는다(mktemp 의 것이라 운영체제가 치운다).
set -u
cd "$(dirname "$0")/../../.."   # apps/api-py

backup="$(mktemp)"
log="$(mktemp)"
before="$( { git status --porcelain; git diff; } | shasum | cut -d' ' -f1)"
touched=""
restore() { [ -n "$touched" ] && cp "$backup" "$touched"; touched=""; }
trap 'restore; (cd ../.. && docker compose down -v >/dev/null 2>&1)' EXIT

plant() { # <파일> <바꿀 글> <바꾼 글> [<바꿀 글> <바꾼 글> …]   바꿀 글마다 정확히 한 번 있어야 한다
  cp "$1" "$backup"; touched="$1"
  python3 - "$@" <<'PY'
import sys
path, pairs = sys.argv[1], sys.argv[2:]
text = open(path, encoding="utf-8").read()
for old, new in zip(pairs[0::2], pairs[1::2]):
    if text.count(old) != 1:
        sys.exit(f"심지 못함: {path} 에 바꿀 글이 {text.count(old)}번 있다: {old[:60]!r}")
    text = text.replace(old, new)
open(path, "w", encoding="utf-8").write(text)
PY
}
total=0; caught=0
verdict() { # <설명> <잡아야 할 테스트 이름(또는 계약)의 조각>   $log 에 방금 돌린 출력이 있다
  total=$((total + 1))
  local summary; summary="$(grep -E '^[0-9]+ (passed|failed)|^(FAILED|ERROR) |BROKEN|^Contracts:' "$log" | tail -1)"
  if grep -E '^(FAILED|ERROR) |BROKEN' "$log" | grep -q -- "$2"; then
    caught=$((caught + 1)); echo "잡힘    $1"
  else
    echo "★ 못 잡음  $1"
  fi
  echo "          잡은 것: $(grep -E '^(FAILED|ERROR) |BROKEN' "$log" | grep -- "$2" | head -1 | cut -c1-200)"
  echo "          빨간 것 $(grep -c -E '^(FAILED|ERROR) |BROKEN$' "$log") 개 / 요약: $summary"
}
also() { # <잡아야 할 조각>   같은 출력에서 하나 더 잡혔는지(수에는 넣지 않는다)
  if grep -E '^(FAILED|ERROR) |BROKEN' "$log" | grep -q -- "$1"; then echo "          같이 잡힘: $1"; else echo "          ★ 같이 잡히지 않음: $1"; fi
}
pure() { uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi/inventory >"$log" 2>&1; }
business() { scripts/test-business.sh -p no:cacheprovider esgapi/inventory/tests/test_scope3_api.py >"$log" 2>&1; }
contracts() { COLUMNS=400 uv run --frozen lint-imports >"$log" 2>&1; }

S3=esgapi/inventory/calc/scope3

(cd ../.. && docker compose up -d --wait postgres >/dev/null 2>&1) || { echo "Postgres 를 띄우지 못했다"; exit 2; }
echo "── 심지 않음: 순수(inventory)·업무(test_scope3_api)·계약이 초록인가"
pure; tail -1 "$log"
business; tail -1 "$log"
contracts; tail -1 "$log"
echo

plant $S3/ranking.py '            tf = counts.get(term)
            if tf is None:' '            tf = counts.get(term) or (1 if any(term in token for token in counts) else None)
            if tf is None:'
pure
verdict "1. 낱말 통째 일치를 부분 문자열 일치로" "test_whole_words_only_car_does_not_match_cargo"
restore

plant $S3/ranking.py 'BM25_B: Final = 0.75' 'BM25_B: Final = 0.0'
pure
verdict "2. BM25_B 를 0 으로" "test_shortlists_match_the_ts_cli"
also "test_the_pipeline_matches_the_ts_cli_row_by_row"
also "test_the_score_is_bm25_with_the_ported_constants"
restore

plant $S3/ranking.py '    return (-entry.score, entry.index)' '    return (-entry.score, -entry.index)'
pure
verdict "3. 동점을 표 순서 대신 역순으로" "test_ties_follow_table_order_and_unmatched_candidates_pad_in_table_order"
also "test_shortlists_match_the_ts_cli"
restore

plant $S3/ranking.py '*(token for text in query.keywords for token in tokenize(text, bigrams=False)),' \
  '*(token for text in query.keywords for token in tokenize(text, bigrams=bigrams)),'
pure
verdict "4. 영어 검색어에서도 한글 조각을 만듦" "test_english_keywords_never_make_hangul_bigrams"
restore

plant $S3/ranking.py '    if word.endswith("s") and not word.endswith(("ss", "us", "is")):' '    if word.endswith("s"):'
pure
verdict "5. singular 의 ss·us·is 예외를 뺌" "test_the_ss_us_is_exceptions_and_three_letter_words_stay"
also "test_plurals_fold_and_short_words_drop"
restore

plant $S3/llm_steps.py '    id_type: Any = Literal[tuple(candidate_ids)]  # pyright: ignore[reportInvalidTypeArguments]' \
  '    id_type: Any = str'
pure
verdict "6. 추천 스키마의 id 열거를 str 로 풂" "test_an_id_in_the_table_but_not_among_the_candidates_is_a_schema_mismatch"
also "test_recommendation_rejects_ids_outside_the_candidates_and_inconsistent_answers"
restore

plant $S3/llm_steps.py '        "item_name": row.item_name,
        "unit": row.unit,' '        "item_name": row.item_name,
        "quantity": row.quantity,
        "unit": row.unit,'
pure
verdict "7. item_for_prompt 에 quantity 를 넣음" "test_quantity_amount_weight_distance_and_factor_values_do_not_reach_the_prompt"
also "test_the_user_text_sent_to_the_provider_matches_the_ts_call_log"
also "test_numbers_do_not_go_into_the_item"
restore

plant $S3/calc.py '        if transport.distance_km is None:
            return NeedsDistance(factor.id)
        distance = parse_external_decimal(transport.distance_km)' \
  '        distance = parse_external_decimal(transport.distance_km or "0")'
pure
verdict "8. 거리 없는 운송 행을 0 km 로 계산함" "test_transport_row_without_distance_needs_distance"
also "test_the_pipeline_matches_the_ts_cli_row_by_row"
restore

plant $S3/ranking.py 'import math
import re
' 'import math
import re

import django  # noqa: F401
'
contracts
verdict "9. calc/scope3/ranking.py 에 import django → 계약 (다)" "다\. 순수 모듈"
pure
echo "          (같은 파손, 순수 층: $(grep -c -E '^FAILED .*test_scope3_is_pure' "$log") 개의 test_scope3_is_pure 가 빨갛다)"
restore

plant esgapi/inventory/services.py 'from esgapi.reference import selectors
' 'from esgapi.reference import selectors
from esgapi.reference.models import FactorRecordRow  # noqa: F401
'
contracts
verdict "10. services.py 가 reference.models 를 직접 import → 계약 (나)" "나\. 모듈끼리 models"
restore

plant esgapi/inventory/services.py 'SCOPE3_ROUTE: Final = "mock"' 'SCOPE3_ROUTE: Final = "light"'
pure
verdict "11. SCOPE3_ROUTE 를 light 로" "test_the_route_is_the_mock_route_and_is_one_constant"
also "test_classify_goes_through_the_mock_provider_with_no_network"
business
echo "          (같은 파손, 업무 층: $(grep -c -E '^FAILED ' "$log") 개가 빨갛다. 그 가운데 $(grep -E '^FAILED ' "$log" | grep -c 'test_two_groups_are_two_calls') 개가 test_two_groups_are_two_calls)"
restore

plant esgapi/inventory/services.py \
  'SCOPE3_DEFAULT_LICENSES: Final[frozenset[LicenseStatus]] = frozenset({"ok", "unverified"})' \
  'SCOPE3_DEFAULT_LICENSES: Final[frozenset[LicenseStatus]] = frozenset({"ok", "unverified", "disputed"})'
business
verdict "12. 이용 조건의 기본에 disputed 를 넣음" "test_disputed_factors_appear_only_when_asked_for"
restore

plant $S3/catalog.py '            elif isinstance(judged, Rejected):
                rejected.append(judged)' '            elif isinstance(judged, Rejected):
                pass'
pure
verdict "13. invalid_value_raw 줄을 싣지 않고 버림 (순수 층)" "test_a_qualified_line_with_a_non_strict_value_raw_is_rejected_not_dropped"
business
echo "          (같은 파손, 업무 층: $(grep -E '^FAILED ' "$log" | grep -c 'test_a_qualified_line_with_exponent_notation_is_left_out_and_reported') 개가 test_a_qualified_line_with_exponent_notation_is_left_out_and_reported)"
restore

plant esgapi/inventory/services.py '        for view in views
    )' '        for view in reversed(views)
    )'
business
verdict "14. 서비스가 표 순서를 뒤집음(id 순을 안 지킴)" "test_ties_are_broken_by_id_order_not_by_file_order"
also "test_the_service_catalog_keeps_that_order"
restore

plant esgapi/reference/selectors.py '        record__gas="CO2e",
' '' '        record_type="emission_factor", gas="CO2e", value__isnull=False, source__license_status__in=wanted
' '        record_type="emission_factor", value__isnull=False, source__license_status__in=wanted
'
business
verdict "15. 새 selector 에서 gas == CO2e 거름을 뺌" "test_the_selector_returns_the_qualified_lines_in_code_point_order_with_two_queries"
restore

plant esgapi/inventory/services.py '    except (LlmConfigError, LiveSetupError):' '    except LiveSetupError:'
business
verdict "16. LlmConfigError 를 잡지 않음" "test_without_the_seam_swap_classify_is_503_llm_not_configured"
pure
echo "          (같은 파손, 순수 층: $(grep -E '^FAILED ' "$log" | grep -c 'test_scope3_services') 개의 test_scope3_services 가 빨갛다)"
restore

after="$( { git status --porcelain; git diff; } | shasum | cut -d' ' -f1)"
echo
[ "$before" = "$after" ] && echo "되돌림: 작업 트리가 심기 전과 같다" || echo "★ 되돌림 실패: 작업 트리가 달라졌다"
echo "PLANTED=$caught/$total"
[ "$caught" = "$total" ] && [ "$before" = "$after" ]
