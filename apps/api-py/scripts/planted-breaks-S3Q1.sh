#!/usr/bin/env bash
# 밴드 S3Q1 의 심은 파손(발주서 §3 이 정본): 하나씩 심고, 그것을 잡아야 하는 테스트가 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3Q1.sh [--server|--web|--all]   (기본 --all)
#     --server  P1~P11 · P16 · P17(서버 — 업무 층은 compose 의 postgres 가 떠 있어야 한다)
#     --web     P12~P15 · P18(웹 vitest — PATH 에 node 22)
#   끝 줄: PLANTED=<잡은 수>/<심은 수> FINGERPRINT=same|changed
# 0번은 심지 않고 돌린다: 겨냥한 테스트가 전부 초록이어야 한다(처음부터 빨간 것을 「잡았다」고 세지 않게).
# 심기 전의 파일을 저장소 밖 임시 폴더(mktemp -d)에 베껴 두었다가 되돌린다(git 을 쓰지 않는다. 죽어도 trap 이
# 되돌린다). 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다(FINGERPRINT).
# 「잡음」의 기준: 테스트가 0 이 아닌 코드로 끝나고, **이름으로 적어 둔 그 테스트**가 실패 줄에 있다.
# ★ main 저장소의 .git/verify.lock 이 있으면 시작하지 않는다(러너 공통 §5). AI 공급사 호출 0. bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:---all}"
case "$MODE" in --server | --web | --all) ;; *) echo "사용: $0 [--server|--web|--all]" >&2; exit 2 ;; esac
COMMON="$(git rev-parse --git-common-dir)"
[ -e "$COMMON/verify.lock" ] && { echo "verify.lock 이 있다 — 돌리지 않는다" >&2; exit 4; }
export PYTHONDONTWRITEBYTECODE=1

A=apps/api-py
I="$A/esgapi/inventory"
ACTIONS="$I/service/actions/scope3_runs.py"
APIS="$I/service/apis/scope3_runs.py"
PRODUCT="$I/engines/scope3/colab_157/product.py"
SERIALIZE="$I/engines/scope3/colab_157/serialize.py"
SOURCES="$I/service/utils/scope3_sources.py"
SHAPES="$I/contracts/shapes.py"
W=apps/web/src
SERVER_TS="$W/entities/ghg-scope3/api/server.ts"
TESTING_TS="$W/entities/ghg-scope3/api/testing.ts"
WINDOW_TSX="$W/pages/ghg-scope3/ui/FactorWindowDialog.tsx"
EDIT_TSX="$W/pages/ghg-scope3/ui/RowEditParts.tsx"
WINDOW_TS="$W/entities/ghg-scope3/model/factorWindow.ts"

T_ORIGINAL=esgapi/inventory/tests/service/apis/test_scope3_original.py
T_TREAT=esgapi/inventory/tests/engines/scope3/colab_157/test_c12_treatments.py
T_EOL=esgapi/inventory/tests/engines/scope3/colab_157/test_product_eol_sheet.py
T_SOURCES=esgapi/inventory/tests/service/utils/test_scope3_sources.py
T_FLOW=esgapi/inventory/tests/test_flow_shapes.py

keep="$(mktemp -d)"
log="$(mktemp -d)"
FILES=("$ACTIONS" "$APIS" "$PRODUCT" "$SERIALIZE" "$SOURCES" "$SHAPES" "$SERVER_TS" "$TESTING_TS" "$WINDOW_TSX" "$EDIT_TSX" "$WINDOW_TS" "$W/pages/ghg-scope3/ui/CategoryDetail.tsx")
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
edit() { # <파일> <있던 글자> <바꿀 글자>
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
}
pure_tests() { (cd "$A" && PYTHONPYCACHEPREFIX="$(mktemp -d)" uv run --frozen pytest -q -rfE -p no:cacheprovider -m "not django_db and not security" "$@"); }
business_tests() { "$A/scripts/test-business.sh" -rfE -p no:cacheprovider "$@"; }
web_tests() { (cd apps/web && pnpm exec vitest run --reporter=verbose "$@"); }
# <번호와 설명> <로그 파일> <종료 코드> <red:이름 …>  — pytest 는 FAILED/ERROR 줄, vitest 는 × 줄에서 이름을 찾는다
judge() {
  local name="$1" file="$2" code="$3" missed=0 want
  shift 3
  total=$((total + 1))
  [ "$code" -ne 0 ] || missed=1
  for want in "$@"; do
    want="${want#red:}"
    grep -E '^(FAILED|ERROR) |^ +(×|✗|FAIL) ' "$file" | grep -q -F "$want" || { missed=1; echo "    (실패 줄에 없다: $want)"; }
  done
  if [ "$missed" -eq 0 ]; then ok=$((ok + 1)); echo "$name → 잡음"; else echo "$name → ★ 못 잡음"; tail -15 "$file" | sed 's/^/    | /'; fi
  grep -E '^(FAILED|ERROR) |^ +(×|✗) ' "$file" | sed 's/^/    /' | cut -c1-200 | head -6
  restore_files
}
zero() { # <로그> <코드>  심지 않은 판이 초록이어야 한다
  if [ "$2" != 0 ]; then echo "0. 심지 않았는데 빨갛다 → ★ 멈춘다" >&2; tail -20 "$1" >&2; exit 1; fi
  echo "0. 심지 않음 → 초록"
}

server() {
  pure_tests "$T_TREAT" "$T_EOL" "$T_SOURCES" "$T_FLOW" > "$log/0p.txt" 2>&1; zero "$log/0p.txt" $?
  business_tests "$T_ORIGINAL" > "$log/0b.txt" 2>&1; zero "$log/0b.txt" $?

  # P1. 회사 조건을 뺀다: 실행을 이웃 회사에서도 찾고 문서는 그 실행의 회사로 찾는다.
  edit "$ACTIONS" '    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE or run.document_id is None:' '    run = next(
        (r for c in range(1, company_id + 10) if (r := run_selectors.find_run(company_id=c, run_id=run_id))), None
    )
    if run is None or run.module != MODULE or run.document_id is None:' || exit 3
  edit "$ACTIONS" 'find_document(company_id=company_id, document_id=run.document_id)' 'find_document(company_id=run.company_id, document_id=run.document_id)' || exit 3
  business_tests "$T_ORIGINAL" > "$log/P1.txt" 2>&1; code=$?
  judge "P1. 원본: 회사 조건 뺌" "$log/P1.txt" "$code" red:test_another_companys_run_and_a_missing_run_are_404_without_the_bytes

  # P2. 꼴을 pdf 로 고정한다(core 경로 꼴 그대로 베낀 흠).
  edit "$ACTIONS" '    dot = file_name.rfind(".")' '    return "application/pdf"
    dot = file_name.rfind(".")' || exit 3
  business_tests "$T_ORIGINAL" > "$log/P2.txt" 2>&1; code=$?
  judge "P2. 원본: pdf 꼴 고정" "$log/P2.txt" "$code" red:test_both_roles_download_the_uploaded_bytes_with_its_name_and_three_headers red:test_the_media_type_follows_the_uploaded_name

  # P3. 바이트 1 자름.
  edit "$ACTIONS" 'media_type_of(document.file_name), got.data)' 'media_type_of(document.file_name), got.data[:-1])' || exit 3
  business_tests "$T_ORIGINAL" > "$log/P3.txt" 2>&1; code=$?
  judge "P3. 원본: 바이트 1 자름" "$log/P3.txt" "$code" red:test_both_roles_download_the_uploaded_bytes_with_its_name_and_three_headers

  # P4. 문서 null 실행을 거르지 않고 단언한다(→ 500).
  edit "$ACTIONS" '    if run is None or run.module != MODULE or run.document_id is None:
        return NotFound()' '    if run is None or run.module != MODULE:
        return NotFound()
    assert run.document_id is not None' || exit 3
  business_tests "$T_ORIGINAL" > "$log/P4.txt" 2>&1; code=$?
  judge "P4. 원본: 문서 null → 500" "$log/P4.txt" "$code" red:test_a_run_without_a_document_is_404

  # P5. 가중 고리 차례를 바꾼다(재활용 → 소각 → 매립 — float 합의 차례가 바뀐다).
  edit "$PRODUCT" '        for pct, found in ((pct_lf, f_lf), (pct_inc, f_inc), (pct_rec, f_rec)):' '        for pct, found in ((pct_rec, f_rec), (pct_inc, f_inc), (pct_lf, f_lf)):' || exit 3
  pure_tests "$T_TREAT" "$T_EOL" > "$log/P5.txt" 2>&1; code=$?
  judge "P5. 엔진: 가중 고리 차례 바꿈" "$log/P5.txt" "$code" red:test_the_used_parts_rebuild_the_weighted_factor_in_the_engine_order

  # P6. 비중을 ×100 한 번 더(0~1 이 아니라 %).
  edit "$SERIALIZE" '                "share": decimal_text(part.share),' '                "share": decimal_text(None if part.share is None else part.share * 100),' || exit 3
  pure_tests "$T_TREAT" > "$log/P6.txt" 2>&1; code=$?
  judge "P6. 직렬화: 비중 ×100 두 번" "$log/P6.txt" "$code" red:test_code_name_and_big_rows_carry_each_treatment_share_and_factor

  # P7. NaN 비중을 0 으로(MARC-ISSUE-390 고침 — 수가 바뀐다).
  edit "$PRODUCT" '    if isinstance(a, float) and math.isnan(a):
        return a' '    if isinstance(a, float) and math.isnan(a):
        return b' || exit 3
  pure_tests "$T_TREAT" "$T_EOL" > "$log/P7.txt" 2>&1; code=$?
  judge "P7. 엔진: NaN 비중을 0 으로(390 고침)" "$log/P7.txt" "$code" red:test_colab_same_defect_an_empty_share_cell_stays_nan_and_blanks_the_weighted_factor red:test_colab_same_defect_empty_shares_blank_the_factor_and_fossil

  # P8. 비중이 하나도 없는 줄의 shareTotal 을 1 로.
  edit "$PRODUCT" '        return C12Treatments("average", None, averages)' '        return C12Treatments("average", 1.0, averages)' || exit 3
  pure_tests "$T_TREAT" > "$log/P8.txt" 2>&1; code=$?
  judge "P8. 엔진: no_pct shareTotal 1" "$log/P8.txt" "$code" red:test_no_share_at_all_is_the_average_branch_with_the_treatment_averages

  # P9. A1 통째를 출처로.
  edit "$SOURCES" '    parts = [part.strip() for part in text.split("|")]' '    return text
    parts = [part.strip() for part in text.split("|")]' || exit 3
  pure_tests "$T_SOURCES" > "$log/P9.txt" 2>&1; code=$?
  judge "P9. 출처: A1 통째" "$log/P9.txt" "$code" red:test_the_head_text_is_after_the_source_word_or_the_second_part_for_the_exception red:test_a_book_reads_into_heads_and_c3_notes

  # P10. C3 줄 비고를 건너뛰고 시트 머리로.
  edit "$SOURCES" '    if sheet == C3_SHEET:
        name = _text(title)' '    if sheet == "가상 아님":
        name = _text(title)' || exit 3
  pure_tests "$T_SOURCES" > "$log/P10.txt" 2>&1; code=$?
  judge "P10. 출처: C3 비고 → 시트 머리" "$log/P10.txt" "$code" red:test_c3_rows_take_their_note_first_then_the_head

  # P11. sourceText 를 필수로(옛 결과·머리 출처 없는 줄이 꼴을 못 지난다).
  edit "$SHAPES" '    sourceText: NotRequired[str]' '    sourceText: str' || exit 3
  pure_tests "$T_FLOW" "$T_TREAT" > "$log/P11.txt" 2>&1; code=$?
  judge "P11. 계약: sourceText 필수" "$log/P11.txt" "$code" red:test_the_json_schema_is_pinned red:test_rows_without_a_factor_and_c15_rows_have_no_treatments_key

  # P17(검증 V1). 문서 상태를 보지 않는다(올림 전 문서의 바이트가 나간다).
  edit "$ACTIONS" '    if document is None or document.status != "uploaded":' '    if document is None:' || exit 3
  business_tests "$T_ORIGINAL" > "$log/P17.txt" 2>&1; code=$?
  judge "P17. 원본: 문서 상태를 안 봄" "$log/P17.txt" "$code" red:test_a_document_not_uploaded_is_404_even_with_the_object_in_storage

  # P16(러너 몫 하나 더). 원본 감사 줄을 뺀다.
  edit "$APIS" '    record_event(
        at=now(),
        company_id=company_id,
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        action="download",
        event="document_downloaded",' '    (lambda **_: None)(
        at=now(),
        company_id=company_id,
        actor_kind=principal.kind,
        actor_user_id=int(principal.user_id),
        action="download",
        event="document_downloaded",' || exit 3
  business_tests "$T_ORIGINAL" > "$log/P16.txt" 2>&1; code=$?
  judge "P16. 원본: 감사 줄 뺌" "$log/P16.txt" "$code" red:test_both_roles_download_the_uploaded_bytes_with_its_name_and_three_headers
}

CATEGORY_TSX="$W/pages/ghg-scope3/ui/CategoryDetail.tsx"
V_SERVER=src/entities/ghg-scope3/api/server.test.ts
V_DETAIL=src/entities/ghg-scope3/model/detail.test.ts
V_CATEGORY=src/pages/ghg-scope3/ui/CategoryDetail.test.tsx

web() {
  web_tests "$V_SERVER" "$V_DETAIL" "$V_CATEGORY" > "$log/0w.txt" 2>&1; zero "$log/0w.txt" $?

  # P12. 웹이 합계 비중을 셈한다(서버 shareTotal 대신 줄 합).
  edit "$WINDOW_TS" '    total: { share: percentOf(treatments.shareTotal), factor: weighted },' '    total: {
      share: treatments.parts.reduce((sum, part) => sum + (percentOf(part.share) ?? 0), 0),
      factor: weighted,
    },' || exit 3
  web_tests "$V_DETAIL" > "$log/P12.txt" 2>&1; code=$?
  judge "P12. 웹: 합계를 셈함" "$log/P12.txt" "$code" "red:웹은 합을 셈하지 않는다"

  # P13. 창(보기)에 입력칸을 넣는다.
  edit "$WINDOW_TSX" '      <table className={TABLE} data-testid="s3-window-treatments">' '      <input aria-label="가상 입력" />
      <table className={TABLE} data-testid="s3-window-treatments">' || exit 3
  web_tests "$V_CATEGORY" > "$log/P13.txt" 2>&1; code=$?
  judge "P13. 웹: 창에 입력칸" "$log/P13.txt" "$code" "red:보기만: 라디오·입력칸"

  # P14. 잠기면 [원본 다운로드]도 막는다.
  edit "$CATEGORY_TSX" '                busy={original.busy}' '                busy={original.busy || locked}' || exit 3
  web_tests "$V_CATEGORY" > "$log/P14.txt" 2>&1; code=$?
  judge "P14. 웹: 잠기면 단추 막힘" "$log/P14.txt" "$code" "red:잠겨도 켬"

  # P15. 가짜에 「기타」(openapi enum 밖).
  edit "$TESTING_TS" "      { treatment: '재활용', share: '0.775', factor: '0.0186', used: true }," "      { treatment: '기타', share: '0.775', factor: '0.0186', used: true }," || exit 3
  web_tests "$V_SERVER" > "$log/P15.txt" 2>&1; code=$?
  judge "P15. 가짜: 「기타」" "$log/P15.txt" "$code" "red:S3Q1 ★ 새 칸 가짜"

  # P18(러너 몫 하나 더). 파서가 sourceText 를 버린다(시트 이름만).
  edit "$SERVER_TS" "        isText(body.sourceText) && body.sourceText.trim() !== '' ?" "        false ?" || exit 3
  web_tests "$V_SERVER" "$V_CATEGORY" > "$log/P18.txt" 2>&1; code=$?
  judge "P18. 웹: sourceText 버림" "$log/P18.txt" "$code" "red:활동·에너지 줄 출처 = sourceText" "red:출처 칸: 서버 sourceText"
}

case "$MODE" in
  --server) server ;;
  --web) web ;;
  --all) server; web ;;
esac

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
fingerprint=same
if ! diff -q "$keep/.sums-before" "$keep/.sums-after" > /dev/null || ! diff -q "$keep/.status-before" "$keep/.status-after" > /dev/null; then
  fingerprint=changed
  echo "★ 되돌린 뒤의 파일·상태가 처음과 다르다 (사본: $keep)"
fi
echo "(기록 $log)"
echo "PLANTED=$ok/$total FINGERPRINT=$fingerprint"
[ "$ok" = "$total" ] && [ "$fingerprint" = same ]
