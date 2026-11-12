#!/usr/bin/env bash
# RPS2 의 심은 파손(발주서 band-handoffs/RPS2-order.md §2-5): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RPS2.sh
# 틀은 planted-breaks-RPQ1.sh: 심기 전 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 되돌림 0).
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 옛 글·새 글의 \n 은 줄바꿈, ␤ 는 소스의 글자 그대로의 \n(역슬래시 n).
# 빨강 = 그 시험의 종료 1(수집 실패 2 는 빨강이 아니다). 순수 층만(업무 층·웹 0).
# 심는 꼴: R3 「이웃을 뷰 전체로(잘린 블록 포함)」는 check() 가 뷰를 받지 않아 그대로 못 심는다 — 잘려 빠진 자리를
#   건너 다음 실은 블록으로 넘어가는 꼴(break→continue)로 흉내(N4 의 k=2 단언이 문다). R8·R9 는 러너 몫.
#   V1~V3 은 독립 검증이 심어 초록이던 셋(시험을 더해 무는 것을 확인), R10 은 감독 처분 R1(출처 「연.월」 토막).
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

P=esgapi/drafting
CK=$P/engines/v2/checks.py
TX=$P/engines/v2/texts.py
TC=$P/tests/engines/v2/test_checks.py
TT=$P/tests/engines/v2/test_texts.py

backup="$(mktemp -d /private/tmp/rps2-planted.XXXXXX)"
case "$backup" in /private/tmp/rps2-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- "$(git rev-parse --show-toplevel)" | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
def real(s):
    return s.replace("\\n", "\n").replace("␤", "\\n")
path, old, new = sys.argv[1], real(sys.argv[2]), real(sys.argv[3])
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PYEOF
}

# 줄: <id>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
ROWS="R1 넓힘을 같은 쪽 given 전부로|$CK|    return [*(b for b in page if b.kind == TABLE), *near]|    return page|$TC::test_rps2_n2_a_wrong_year_is_not_let_through_by_a_far_block_or_another_page
R2 짧음 조건 뺌(긴 블록도 넓힘)|$CK|                if _short(block):|                if True:|$TC::test_rps2_n1_a_long_block_stays_strict
R3 빠진 자리를 건너 넓힘(뷰 전체 흉내)|$CK|            if found is None:\n                break|            if found is None:\n                continue|$TC::test_rps2_n4_a_neighbour_cut_from_the_material_is_not_read_and_the_walk_stops_there
R4 이웃 쪽 경계 무시|$CK|    page = [b for b in given.values() if b.page == block.page]|    page = list(given.values())|$TC::test_rps2_n3_neighbours_do_not_cross_the_page
R5 날짜 꼴 뺌|$CK|    rest = DATE.sub(\" \", text)|    found, rest = set(), text|$TC::test_rps2_d1_a_date_reads_as_year_month_day
R6 소수 점을 날짜처럼 쪼갬|$CK|NUMBER: Final = re.compile(r\"\\d[\\d,]*(?:\\.\\d+)?\")|NUMBER: Final = re.compile(r\"\\d[\\d,]*\")|$TC::test_rps2_d2_decimals_and_version_numbers_are_not_dates
R7 MARKER_RULES 한 글자 고치고 판 그대로|$TX|행 번호로 댄다.|행 번호로 단다.|$TT
R8 정수 앞 0 그대로|$CK|    return piece if \".\" in piece else piece.lstrip(\"0\") or \"0\"|    return piece|$TC::test_rps2_d3_leading_zeros_of_whole_numbers_are_dropped
R9 짧은 표도 넓힘|$CK|    return block.kind == HEADING or (block.kind != TABLE and len(block.text) <= SHORT_MAX)|    return block.kind == HEADING or len(block.text) <= SHORT_MAX|$TC::test_rps2_n5_a_table_source_is_not_widened_even_if_short
V1 이웃 하나 더(k+1 까지 샘)|$CK|        for distance in range(1, NEIGHBOURS + 1):|        for distance in range(1, NEIGHBOURS + 2):|$TC::test_rps2_v1_a_block_two_places_away_is_not_read_with_k_1
V2 제목도 글자 수로만|$CK|    return block.kind == HEADING or (block.kind != TABLE and len(block.text) <= SHORT_MAX)|    return block.kind != TABLE and len(block.text) <= SHORT_MAX|$TC::test_rps2_v2_a_heading_is_widened_even_when_longer_than_the_short_limit
V3 같은 쪽 표 대신 이웃만|$CK|    return [*(b for b in page if b.kind == TABLE), *near]|    return near|$TC::test_rps2_v3_a_table_beyond_the_neighbours_on_the_same_page_is_read
R10 출처 연.월 토막 뺌|$CK|    if source:|    if False:|$TC::test_rps2_r1_a_dotted_source_date_also_gives_its_year_month"

planted=0
caught=0
bad=0
while IFS='|' read -r id file old new tests; do
  [ -n "$id" ] || continue
  old="${old//\\&/&}"; new="${new//\\&/&}"
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
  env -u OPENAI_API_KEY -u LLM_OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests \
    > "$backup/log" 2>&1
  code=$?
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

if [ "$planted" != 13 ]; then echo "★ 심은 수 $planted ≠ 13"; bad=$((bad + 1)); fi
after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
