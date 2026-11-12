#!/usr/bin/env bash
# S12b-1 의 심은 고장(발주서 band-handoffs/S12b-1-order.md §3-8): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지
#   본다. 사용: apps/api-py/scripts/planted-breaks-S12b-1.sh --commit <1|2|3|4>
#   경계별 배치(누적): ① P1~P6(6) · ② +P7~P15(15) · ③ +P16~P22(22 — P21·P22 는 검증 B1·R8) · ④ 같음(22 — main 들인 뒤 다시).
# 틀은 planted-breaks-S12a-2.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
#   쓰지 않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(둘 다 이 워크트리의 compose postgres 가 떠 있어야 한다).
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

COMMIT=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1|2|3|4) ;; *) echo "--commit 1·2·3·4" >&2; exit 2 ;; esac

I=esgapi/inventory
IT=$I/tests
TX=$I/tools/scope12_xlsx.py
TT=$IT/tools/test_scope12_xlsx.py
AX=$I/service/actions/scope12_excel.py
AT=$IT/service/actions/test_scope12_excel.py
AE=$I/service/actions/entries.py
AP=$I/service/apis/scope12_excel.py
APT=$IT/service/apis/test_scope12_excel.py
PE=esgapi/core/permissions.py
TP=tests/security/test_tenant_paths.py

backup="$(mktemp -d /private/tmp/s12b1-planted.XXXXXX)"
case "$backup" in /private/tmp/s12b1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"
plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈, § 로 여러 자리)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, olds, news = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
pairs = list(zip(olds.split("§"), news.split("§"), strict=True))
for old, new in pairs:
    if text.count(old) != 1:
        print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
        sys.exit(1)
    text = text.replace(old, new, 1)
open(path, "w", encoding="utf-8").write(text)
PYEOF
}

# 줄: <id>|<경계>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
# ② P7 숨긴 선택 실음(list_rows·index_detail 두 겹을 같이 뺌 — 한 겹만이면 다른 겹이 막아 초록) · P8 꺼진 사업장 ·
#   P9 주기 글자 뒤집음 · P10 총계를 칸 합으로 · P11 월 행 분기 합에서 달 빠짐(2·5·8·11월) · P12 scope 거름 뺌 · P13 해 없음(선택 0)에 파일 ·
#   P14 남의 siteId 받음(판정과 블록 거름 두 겹을 같이 뺌) · P15 선택 판이 행 계수를 이김
# ③ P16 양식 정책 CUSTOMER · P17 company_of 대신 주체 회사(운영 관리자 줄 0) · P18 Content-Disposition 뺌 ·
#   P19 test_tenant_paths 표에서 양식 경로 뺌 · P20 nosniff 뺌 · P21 선택 잎 없는 n번째 뿌리를 404 로(검증 B1) ·
#   P22 경로층 scope 길이 문턱 뺌(검증 R8)
# ① P1 시트 차례 바꿈 · P2 머리 한 글자 바꿈 · P3 병합 뺌 · P4 zip 시각 고정 뺌 · P5 Decimal 을 그대로(지수 꼴) ·
#   P6 글 칸 고정 뺌(수식)
ROWS="P1|1|$TX|TEMPLATE_SHEETS: Final = (\"년도\", \"분기\", \"월\")|TEMPLATE_SHEETS: Final = (\"분기\", \"년도\", \"월\")|$TT
P2|1|$TX|    \"단위(수정X)\",|    \"단위(수정 X)\",|$TT
P3|1|$TX|            if index - start > 1:|            if False:|$TT
P4|1|$TX|            info = zipfile.ZipInfo(entry.filename, date_time=FIXED_DATE)|            info = zipfile.ZipInfo(entry.filename, date_time=entry.date_time)|$TT
P5|1|$TX|        cell.value = format(value, \"f\")\n        cell.data_type = \"n\"|        cell.value = value|$TT
P6|1|$TX|        cell.data_type = \"s\"  # \`=\` 로 시작해도 글 칸(수식 주입 0)\n||$TT
P7|2|$AE|    if found is None or found.hidden:§if not row.hidden}|    if found is None:§if True}|biz:$AT
P8|2|$AX|search_sites(company_id).branches if site.inventory_enabled]|search_sites(company_id).branches]|biz:$AT
P9|2|$TX|PERIOD_LABELS: Final = {\"month\": \"월\", \"quarter\": \"분기\"|PERIOD_LABELS: Final = {\"month\": \"분기\", \"quarter\": \"월\"|biz:$AT
P10|2|$AX|        total=row.emission,|        total=row_total(False, cells[\"quarter\"].emissions),|biz:$AT
P11|2|$TX|        return (month - 1) // 3|        return (month - 1) // 3 if month % 3 != 2 else None|biz:$AT
P12|2|$AX|    return [found or empty]|    return list(rows.scopes)|biz:$AT
P13|2|$AX|    if isinstance(rows, Invalid) or not rows.configured:|    if isinstance(rows, Invalid):|biz:$AT
P14|2|$AX|        if site_name is None:\n            return NotFound()  # 남의§        if site_id is None or block.site_id == site_id|        if False:\n            return NotFound()  # 남의§        if True|biz:$AT
P15|2|$AX|    return row.factor if row.factor is not None else detail.factor|    return detail.factor|biz:$AT
P16|3|$PE|    \"inventory_scope12_template\": COMPANY,|    \"inventory_scope12_template\": CUSTOMER,|biz:$APT
P17|3|$AP|    found = actions.template(company_of(principal), year, scope, site_id)|    found = actions.template(principal.company_id or 0, year, scope, site_id)|biz:$APT
P18|3|$AP|    response[\"Content-Disposition\"] = disposition\n||biz:$APT
P19|3|$TP|    (\"GET\", \"/inventory/scope12/years/{year}/template\"): \"entry_paths\",\n||sec:$TP::test_every_operation_is_in_the_table
P20|3|$AP|    response[\"X-Content-Type-Options\"] = \"nosniff\"\n||biz:$APT
P21|3|$AX|    return [found or empty]|    return [found] if found else NotFound()|biz:$AT
P22|3|$AP|Query(max_length=3,|Query(max_length=10,|biz:$APT"

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  if [ "${tests#biz:}" != "$tests" ]; then
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 순수 갈래도(5d R7 · runner-common §5)
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=6 ;; 2) want=15 ;; 3) want=22 ;; 4) want=22 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
