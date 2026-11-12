#!/usr/bin/env bash
# S12a 의 심은 고장(발주서 band-handoffs/S12a-order.md §3-8): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S12a.sh --commit <1|2|3|4|5>
#   경계별 배치(누적): ① P1~P7(7) · ② P8~P15(15) · ③ P16~P18(18) · ④ P19~P23(23) · ⑤ P24~P26(26).
# 틀은 planted-breaks-K1b-2b.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
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
case "$COMMIT" in 1|2|3|4|5) ;; *) echo "--commit 1·2·3·4·5" >&2; exit 2 ;; esac

I=esgapi/inventory
MG=$I/migrations/0003_entries.py
IT=$I/tests
CA=$I/calc/entry_emission.py
CT=$IT/calc/test_entry_emission.py
AE=$I/service/actions/entries.py
AT=$IT/service/actions/test_entries.py
SI=$I/service/selectors/index_selection.py
O=esgapi/organization
OA=$O/service/actions/branches.py
OS=$O/service/services/branches.py
OAT=$O/tests/service/actions/test_branches.py
OST=$O/tests/service/services/test_branches.py
RT=$IT/service/actions/test_entries_race.py

backup="$(mktemp -d /private/tmp/s12a-planted.XXXXXX)"
case "$backup" in /private/tmp/s12a-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 행 → 자산/시설 같은 회사 짝 키 뺌 · P2 값 (row, slot) unique 를 (id, slot) 으로(늘 지남) · P3 히스토리 grant 에 UPDATE
#   · P4 amount CHECK 를 -1 까지 풂 · P5 분모 환산 건너뜀 · P6 분자 kg → t 건너뜀 · P7 셈이 default_factor_unit 을 부름
# ② P8 판 id 를 지금 기본 판으로 · P9 히스토리 안 씀 · P10 N/A 를 합에 넣음 · P11 잠김 검사 뺌 · P12 다른 코드 자산/시설
#   받음 · P13 selections_with_data 빈 집합 · P14 저장의 @transaction.atomic 뺌 · P15 꺼진 사업장 받음
# ③ P16 풀기 칸 COMPANY · P17 test_tenant_paths 표에서 히스토리 경로 한 줄 뺌 · P18 상세의 행 읽기가 회사 조건 없이(unscoped)
# ④ P19 sites_in_use 빈 집합 · P20 코드 바꿈 판정 뺌(빠진 줄만 물음) · P21 R8 잠깐 삭제 표시의 site_id 조건 뺌
#   · P22 본사 CHECK 가름 뺌(이름 표 빈 집합 → 다시 던짐 500) · P23 늦은 지움 200(잠금 아래 다시 봄 뺌)
# ⑤ P24 저장의 lock_branch 뺌(잠그지 않는 search_sites 읽기) · P25 선택 잠금 뺌(lock_selection → selection_of)
#   · P26 지움의 lock_branches 뺌(잠그지 않는 alive_branches 읽기)
ROWS="P1|1|$MG|        same_company_foreign_key(table=ROWS, column=\"site_facility_id\", target=\"site_facilities\"),\n||biz:$IT/test_models_entries.py
P2|1|$MG|constraint=models.UniqueConstraint(fields=(\"row\", \"slot\"), name=\"inventory_entry_values_unique\"),|constraint=models.UniqueConstraint(fields=(\"id\", \"slot\"), name=\"inventory_entry_values_unique\"),|biz:$IT/test_models_entries.py
P3|1|$MG|        grant(f'\"{HISTORY}\"', \"SELECT, INSERT\"),|        grant(f'\"{HISTORY}\"', \"SELECT, INSERT, UPDATE\"),|sec:tests/security/test_owner.py
P4|1|$MG|(\"amount__gte\", 0)|(\"amount__gte\", -1)|biz:$IT/test_models_entries.py
P5|1|$CA|        quantity = quantity * to_denominator|        quantity = quantity|$CT
P6|1|$CA|        tonnes = quantity * weighted * to_tonnes|        tonnes = quantity * weighted|$CT
P7|1|$CA|from typing import Final\n§    numerator, slash, denominator = version.factor_unit.partition(\"/\")|from typing import Final\n\nfrom esgapi.inventory.service.utils.ghg_pool import default_factor_unit\n§    numerator, slash, denominator = default_factor_unit(version.ncv is not None, version.input_unit).partition(\"/\")|$CT
P8|2|$AE|    pinned = pool.pinned_version(chosen.factor_version_id)|    pinned = pool.pinned_version(pool.default_versions([node_id])[node_id])|biz:$AT
P9|2|$AE|    services.insert_history(company_id, lines)\n||biz:$AT
P10|2|$AE|_figures(row_total(row.na, amounts.values())|_figures(row_total(False, amounts.values())|biz:$AT
P11|2|$AE|    if chosen.locked_at is not None:\n        return Locked()\n    leaf = pool|    leaf = pool|biz:$AT
P12|2|$AE|        row.id for row in facilities_of(company_id, site_id) if row.facility_code_id == leaf.facility_code_id|        row.id for row in facilities_of(company_id, site_id)|biz:$AT
P13|2|$SI|    return frozenset(rows.values_list(\"selection__facility_node_id\", flat=True))|    return frozenset()|biz:$IT/service/selectors/test_entries.py $AT
P14|2|$AE|@transaction.atomic\ndef save_rows(|def save_rows(|biz:$AT
P15|2|$AE|    if site is None or not site.inventory_enabled:|    if site is None:|biz:$AT
P16|3|esgapi/core/permissions.py|    \"inventory_scope12_unlock\": OPERATOR,|    \"inventory_scope12_unlock\": COMPANY,|sec:tests/security/test_entries.py
P17|3|tests/security/test_tenant_paths.py|    (\"GET\", \"/inventory/scope12/years/{year}/indexes/{node_id}/rows/{row_id}/history\"): \"entry_paths\",\n||sec:tests/security/test_tenant_paths.py
P18|3|$I/service/selectors/entries.py|    rows = InventoryEntryRow.for_company(company_id).filter(selection_id=selection_id, deleted_at__isnull=True)|    rows = InventoryEntryRow.unscoped.filter(selection_id=selection_id, deleted_at__isnull=True)|esgapi/core/tests/isolation/test_static_rules.py::test_product_code_does_not_use_unscoped esgapi/core/tests/test_selector_scope.py::test_selectors_scope_every_read
P19|4|$I/service/selectors/entries.py|    return frozenset(rows.values_list(\"site_facility__site_id\", flat=True))|    return frozenset()|biz:$AT $IT/service/selectors/test_entries.py
P20|4|$OS|    used = facilities_in_use(company_id, {*drop, *recoded})|    used = facilities_in_use(company_id, drop)|biz:$AT $OAT $OST
P21|4|$OS|                facilities.filter(site_id=site_id, pk__in=[row.id for row in kept]).update(deleted_at=now)|                facilities.filter(pk__in=[row.id for row in kept]).update(deleted_at=now)|biz:$OST
P22|4|$OS|HEADQUARTERS_CHECKS: Final = frozenset({\"sites_headquarters_alive\", \"sites_headquarters_inventory_on\"})|HEADQUARTERS_CHECKS: Final = frozenset[str]()|biz:$OST $OAT
P23|4|$OA|    if len(locked) != len(set(ids)):\n        return NotFound()\n||biz:$OAT
P24|5|$AE|    site = lock_branch(company_id, site_id)|    site = next((b for b in search_sites(company_id).branches if b.id == site_id), None)|biz:$RT
P25|5|$AE|        selections.lock_selection(company_id, year_id, node_id)|        selections.selection_of(company_id, year_id, node_id)|biz:$RT
P26|5|$OA|    locked = selectors.lock_branches(company_id, ids)|    locked = selectors.alive_branches(company_id, ids)|biz:$RT"

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

case "$COMMIT" in 1) want=7 ;; 2) want=15 ;; 3) want=18 ;; 4) want=23 ;; 5) want=26 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
