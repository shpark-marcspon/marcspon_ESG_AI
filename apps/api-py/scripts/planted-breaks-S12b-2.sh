#!/usr/bin/env bash
# S12b-2 의 심은 고장(발주서 band-handoffs/S12b-2-order.md §3): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S12b-2.sh --commit <1|2|3>   (경계별 누적)
# 틀은 planted-breaks-S12b-1.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
#   쓰지 않는다). 시작과 끝의 지문이 다르면 무엇이 다른지 찍고 종료 1. 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」). 시험 칸이 「biz:」면 업무 층, 「sec:」면 보안 층.
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
case "$COMMIT" in 1|2|3) ;; *) echo "--commit 1·2·3" >&2; exit 2 ;; esac

I=esgapi/inventory
IT=$I/tests
TU=$I/tools/scope12_upload.py
TR=$I/tools/xlsx_reader.py
TT=$IT/tools/test_scope12_upload.py
TL=$IT/test_s3sheets_reader_limits.py
AU=$I/service/actions/scope12_upload.py
AT=$IT/service/actions/test_scope12_upload.py
AP=$I/service/apis/scope12_excel.py
APT=$IT/service/apis/test_scope12_upload.py
PE=esgapi/core/permissions.py
TP=tests/security/test_tenant_paths.py
TS=tests/security/test_scope12_upload.py

backup="$(mktemp -d /private/tmp/s12b2-planted.XXXXXX)"
case "$backup" in /private/tmp/s12b2-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 머리 대조 뺌 · P2 병합 채움 안 함 · P3 수식 칸 받음 · P4 병합 상한 뺌 · P5 XML 깊이 상한 뺌 · 표 밖: P23 요소 수 상한 뺌 · P24 맞닿은 병합 받음 · P25 전각 ID 받음
# ②(+P27 오류 차례 뺌 — 검증 R4 · P32 판정 차례 ①② 되돌림 — 감독 처분) P6 값 있는 칸 덮어씀 · P7 set_rollback 뺌 · P8 시트 주기 대조 뺌(G열·시트 글자대로) · P9 지난 해 칸 받음 · P10 여럿이면 첫 자산/시설 ·
#   P11 잠긴 잎 받음 · P12 꺼진 사업장 이름 찾음 · P13 단위 대조 뺌 · P14 unresolved 0 · P15 lock_year 뺌 · P16 na 안 넘김 ·
#   P17 estimated 를 False 로 · 표 밖: P26 사업장 id 차례를 잎 차례로
# ③ P18 정책 CUSTOMER · P19 company_of 대신 주체 회사 · P20 413 선언 뺌 · P21 test_tenant_paths 표에서 뺌 · P22 오류 글에 칸 값 ·
#   표 밖(6d (자) H13 단언마다): P28 글에 사업장 이름 · P29 글에 잎 id · P30 주체 회사로 씀 · P31 같은 값을 오류로(두 번째 200 깨짐) · P33 선택 0 을 404 아닌 답으로 · P34 운영 관리자를 service 로 적음(검증 R7) · P35 일의 양 상한 뺌(가지 리뷰 M1)
ROWS="P1|1|$TU|        if not _head_is(by_name[name], columns):|        if False:|$TT
P2|1|$TU|        return self.starts[index] if index >= 0 and row <= self.ends[index] else row|        return row|$TT
P3|1|$TU|            if isinstance(cell, FormulaCell):\n                problems.append|            if False:\n                problems.append|$TT
P4|1|$TR|    if len(merges) > MAX_MERGES:|    if False:|$TL
P5|1|$TR|        if self._depth > MAX_XML_DEPTH:|        if False:|$TL
P23|1|$TR|        if self._elements > MAX_XML_ELEMENTS:|        if False:|$TL
P24|1|$TU|    if any(after[0] <= before[1] for before, after in pairwise(found)):|    if any(after[0] < before[1] for before, after in pairwise(found)):|$TT
P25|1|$TU|    if not text.isascii() or not text.isdecimal() or len(text) > 18:|    if not text.isdecimal() or len(text) > 18:|$TT
P6|2|$AU|        else:\n            problems.append(LineProblem(cell.address, HAS_VALUE))|        else:\n            values.append(_slot_input(slot, cell.text, old))|biz:$AT
P7|2|$AU|            transaction.set_rollback(True)\n||biz:$AT
P8|2|$AU|    if line.period != block.period:|    if False:|biz:$AT
P9|2|$AU|        slot = by_label.get(cell.label)|        slot = by_label.get(cell.label, slots(year, block.period)[0])|biz:$AT
P10|2|$AU|    if len(block.facilities) != 1:§    (facility,) = block.facilities|    if False:§    facility = block.facilities[0]|biz:$AT
P11|2|$AU|    return LOCKED_LEAF if detail.locked_at is not None else None|    return None|biz:$AT
P12|2|$AU|search_sites(company_id).branches if site.inventory_enabled}|search_sites(company_id).branches}|biz:$AT
P13|2|$AU|    if before is not None and line.unit != before.unit:|    if False:|biz:$AT
P14|2|$AU|        unresolved=_unresolved(details),|        unresolved=0,|biz:$AT
P15|2|$AU|    if selections.lock_year(company_id, year) is None:|    if selections.year_of(company_id, year) is None:|biz:$AT
P16|2|$AU|        na=before.na if before is not None else False,|        na=False,|biz:$AT
P17|2|$AU|    return SlotInput(slot, text, old.estimated if old is not None else False)|    return SlotInput(slot, text, False)|biz:$AT
P26|2|$AU|key=lambda found: (found.site_id, found.node_id)|key=lambda found: (found.node_id, found.site_id)|biz:$AT
P27|2|$AU|    ordered = sorted(problems, key=_place)|    ordered = list(problems)|biz:$AT
P32|2|$AU|    rows = entries.list_rows(company_id, year)\n    if isinstance(rows, Invalid) or not rows.configured:\n        return NotFound()\n    book = read_upload(data, year)\n    if isinstance(book, UploadProblem):\n        return Invalid({FILE: book.message})\n|    book = read_upload(data, year)\n    if isinstance(book, UploadProblem):\n        return Invalid({FILE: book.message})\n    rows = entries.list_rows(company_id, year)\n    if isinstance(rows, Invalid) or not rows.configured:\n        return NotFound()\n|biz:$AT
P35|3|$AU|    if (len(leaves) + len(plans)) * work > UPLOAD_WORK_MAX:|    if False:|biz:$AT
P36|3|$AU|    if len(leaves) * work > UPLOAD_WORK_MAX:|    if False:|biz:$AT
P37|3|$AU|    return DETAIL_WORK + SITE_WORK * len(sites) + facilities|    return DETAIL_WORK + SITE_WORK * len(sites)|biz:$AT
P38|3|$AU|    if (len(leaves) + len(plans)) * work > UPLOAD_WORK_MAX:|    if len(plans) * work > UPLOAD_WORK_MAX:|biz:$AT
P39|3|$AU|    leaves = {line.node_id for line in book.lines} & chosen|    leaves = {line.node_id for line in book.lines}|biz:$AT
P18|3|$PE|    \"inventory_scope12_upload\": COMPANY,|    \"inventory_scope12_upload\": CUSTOMER,|biz:$APT
P19|3|$AP|    found = upload_actions.upload(company_of(principal), year, request.body, actor)|    found = upload_actions.upload(principal.company_id or 0, year, request.body, actor)|biz:$APT
P20|3|$AP|    response={200: EntryUploadOut, **TOKEN_BODY_ERROR_RESPONSES, 404: ErrorBody},|    response={200: EntryUploadOut, **TOKEN_ERROR_RESPONSES, 404: ErrorBody},|esgapi/config/tests/test_api_contract.py
P21|3|$TP|    (\"POST\", \"/inventory/scope12/years/{year}/uploads\"): \"entry_paths\",\n||sec:$TP::test_every_operation_is_in_the_table
P22|3|$AU|            problems.append(LineProblem(cell.address, wrong))|            problems.append(LineProblem(cell.address, f\"{wrong} {cell.text}\"))|biz:$AT
P28|3|$AU|    if line.site not in sites:\n        return NO_SITE|    if line.site not in sites:\n        return f\"{NO_SITE} {line.site}\"|sec:$TS
P29|3|$AU|    if detail is None:\n        return NO_LEAF|    if detail is None:\n        return f\"{NO_LEAF} {line.node_id}\"|sec:$TS
P30|3|$AP|    found = upload_actions.upload(company_of(principal), year, request.body, actor)|    found = upload_actions.upload(principal.company_id or 0, year, request.body, actor)|sec:$TS
P31|3|$AU|        elif old.amount == parse_decimal(cell.text):|        elif False:|sec:$TS
P34|3|$AP|    actor = Actor(kind=principal.kind, user_id=int(principal.user_id))|    actor = Actor(kind=\"service\", user_id=int(principal.user_id))|biz:$APT
P33|3|$AU|    if isinstance(rows, Invalid) or not rows.configured:\n        return NotFound()|    if isinstance(rows, Invalid) or not rows.configured:\n        return Invalid({FILE: CHANGED})|sec:$TS"

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
  while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    # shellcheck disable=SC2086
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086
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
done <<ROWS_END
$ROWS
ROWS_END

case "$COMMIT" in 1) want=8 ;; 2) want=23 ;; 3) want=39 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
