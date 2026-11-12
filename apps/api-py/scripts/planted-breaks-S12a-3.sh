#!/usr/bin/env bash
# S12a-3 의 심은 고장(발주서 band-handoffs/S12a-3-order.md §3-6): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지
#   본다. 사용: apps/api-py/scripts/planted-breaks-S12a-3.sh --commit <1|2>
#   경계별 배치(누적): ① P1~P8(8) · ② +P9~P13(13).
# 틀은 앞 밴드의 planted-breaks 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
#   쓰지 않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(둘 다 이 워크트리의 compose postgres 가 떠 있어야 한다). 어느 갈래든 verify.lock 이
#   있는 동안은 돌리지 않는다.
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
case "$COMMIT" in 1|2) ;; *) echo "--commit 1·2" >&2; exit 2 ;; esac

I=esgapi/inventory
IT=$I/tests
UD=$I/service/utils/dashboard.py
UT=$IT/service/utils/test_dashboard.py
AT=$IT/service/actions/test_dashboard.py
SE=$I/service/selectors/entries.py
SD=$I/service/schemas/dashboard.py
APT=$IT/service/apis/test_dashboard.py
PE=esgapi/core/permissions.py
TP=tests/security/test_tenant_paths.py
SET=tests/security/test_entries.py
RS=$IT/test_route_shapes.py

backup="$(mktemp -d /private/tmp/s12a3-planted.XXXXXX)"
case "$backup" in /private/tmp/s12a3-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() {  # 심은 파일(들)을 되쓴다 — 「^」 로 나눈 둘까지(P12: 회사 거름 둘을 같이 걷음)
  local f n=0
  if [ -n "$current" ]; then
    for f in $current; do cp "$backup/keep$n" "$f"; n=$((n + 1)); done
    current=""
  fi
}
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
# ① P1 꺼진 사업장 거름 뺌 · P2 상위 5 를 잎(path[-1]) 기준으로 · P3 상위 5 를 6 으로 · P4 share 분모를 전체(셈에 든 줄 합)로
#   · P5 complete 가 problem 을 안 봄 · P6 같은 값 차례를 뒤집음 · P7 sum_or_none 대신 sum(None 줄에서 빨강)
#   · P8 year_rows 의 problem 칸 뺌(업무 층 — 문제 행 → complete 거짓)
# ② P9 권한 칸 CUSTOMER(운영 관리자 403) · P10 test_tenant_paths 표에서 대시보드 줄 뺌 · P11 SCOPE12_SCREEN_OPERATIONS 에
#   대시보드(R7 되돌림) · P12 회사 거름 걷음 — 발주서는 「actions 의 사업장 거름」이지만 사업장 거름은 회사 범위 안의 것이라
#   걷어도 남의 행이 닿지 않는다(빨강 0 — year_rows 가 회사 범위). 회사 거름 둘(year_rows 의 for_company · 켠 사업장
#   거름 — 남의 사업장은 내 켠 사업장에 없다)을 같이 걷는다(파일 둘, 「^」 — 보안 층 격리 시험이 빨강. year_rows 하나만
#   걷으면 초록이다 — 실측, 보고에) · P13 카테고리 꼴 이름을 Scope3Colab 앞머리로(이름 앞머리 단언 빨강)
ROWS="P1|1|$UD|        if line.site_id in site_ids and line.node_id in visible|        if line.node_id in visible|$UT
P2|1|$UD|            by_source[root][path[SOURCE_DEPTH].id].append(line.emission)|            by_source[root][path[-1].id].append(line.emission)|$UT
P3|1|$UD|TOP_SOURCES: Final = 5|TOP_SOURCES: Final = 6|$UT
P4|1|$UD|share=share(total, value))|share=share(total, sum_or_none(line.emission for _, line in counted)))|$UT
P5|1|$UD|        complete=all(line.problem is None for _, line in counted),|        complete=True,|$UT
P6|1|$UD|        valued.sort(key=lambda item: order.get(item[0], 0))|        valued.sort(key=lambda item: -order.get(item[0], 0))|$UT
P7|1|$UD|        value = sum_or_none(by_root.get(root, ()))|        value = sum(by_root.get(root, ()), Decimal(0))|$UT
P8|1|$SE|        \"emission_problem\",  # S12a-3\n||biz:$AT
P9|2|$PE|    \"inventory_scope12_dashboard\": COMPANY,|    \"inventory_scope12_dashboard\": CUSTOMER,|biz:$APT
P10|2|$TP|    (\"GET\", \"/inventory/scope12/dashboard\"): \"entry_paths\",\n||sec:$TP::test_every_operation_is_in_the_table
P11|2|$RS|        \"inventory_scope12_history_restore\",\n    }|        \"inventory_scope12_history_restore\",\n        \"inventory_scope12_dashboard\",\n    }|$RS
P12|2|$SE^$UD|    rows = InventoryEntryRow.for_company(company_id).filter(\n        deleted_at__isnull=True,\n        selection__deleted_at__isnull=True,\n        selection__hidden=False,^        if line.site_id in site_ids and line.node_id in visible|    rows = InventoryEntryRow.unscoped.filter(\n        deleted_at__isnull=True,\n        selection__deleted_at__isnull=True,\n        selection__hidden=False,^        if line.node_id in visible|sec:$SET::test_the_dashboard_carries_only_my_company
P13|2|$SD|class Scope12DashboardCategoryOut(Schema):§list[Scope12DashboardCategoryOut]|class Scope3ColabCategoryOut(Schema):§list[Scope3ColabCategoryOut]|$RS"

planted=0
caught=0
bad=0
while IFS='|' read -r id at file old new tests; do
  [ -n "$id" ] || continue
  [ "$at" -le "$COMMIT" ] || continue
  planted=$((planted + 1))
  files="$(echo "$file" | tr '^' ' ')"
  missing=0
  for f in $files; do [ -f "$f" ] || { echo "$id ★ 파일이 없다: $f"; missing=1; }; done
  if [ "$missing" = 1 ]; then bad=$((bad + 1)); continue; fi
  n=0
  for f in $files; do cp "$f" "$backup/keep$n"; n=$((n + 1)); done
  current="$files"
  n=1
  failed_plant=0
  for f in $files; do
    if ! plant "$f" "$(echo "$old" | cut -d'^' -f$n)" "$(echo "$new" | cut -d'^' -f$n)"; then failed_plant=1; fi
    n=$((n + 1))
  done
  if [ "$failed_plant" = 1 ]; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  if [ "${tests#biz:}" != "$tests" ]; then
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY scripts/test-business.sh -p no:cacheprovider ${tests#biz:} > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#sec:}" != "$tests" ]; then
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 전량 verify 와 겹치지 않는다
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY scripts/test-security.sh -p no:cacheprovider ${tests#sec:} > "$backup/log" 2>&1
    code=$?
  else
    while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 20; done  # 순수 갈래도(5d R7 · runner-common §5)
    # shellcheck disable=SC2086  # tests 는 빈칸으로 나눈 경로 목록이다
    env -u LLM_OPENAI_API_KEY -u LLM_ANTHROPIC_API_KEY -u LLM_GEMINI_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
  nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  restore
  n=0
  for f in $files; do
    if ! cmp -s "$backup/keep$n" "$f"; then echo "$id ★ 되쓰기 실패: $f"; bad=$((bad + 1)); fi
    n=$((n + 1))
  done
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code, $tests) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

case "$COMMIT" in 1) want=8 ;; 2) want=13 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
