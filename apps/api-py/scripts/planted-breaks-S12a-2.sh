#!/usr/bin/env bash
# S12a-2 의 심은 고장(발주서 band-handoffs/S12a-2-order.md §3-8): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지
#   본다. 사용: apps/api-py/scripts/planted-breaks-S12a-2.sh --commit <1|2|3|4>
#   경계별 배치(누적): ① P1~P6(6) · ② +P7~P22·P32·P34·P35(25) · ③ +P23~P26·P33·P36(31) · ④ +P27~P31·P37(37).
#   P32·P33 은 C0 뒤 더한 것(감독 27 길 (i) — 지운 계수 factor 줄 복구 · e7 조건 — 보안 층의 factor 줄 복구 403).
# 틀은 planted-breaks-S12a.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
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
MG=$I/migrations/0004_entry_periods_factors.py
IT=$I/tests
MT=$IT/test_models_entries.py
UE=$I/service/utils/entries.py
UT=$IT/service/utils/test_entries.py
AE=$I/service/actions/entries.py
AT=$IT/service/actions/test_entries.py
SP=$I/service/selectors/ghg_pool.py
ST=$IT/service/selectors/test_entries.py
PE=esgapi/core/permissions.py
PT=esgapi/core/tests/test_permissions.py
APT=$IT/service/apis/test_entries.py
SE=$I/service/selectors/entries.py
TP=tests/security/test_tenant_paths.py
SET=tests/security/test_entries.py
RS=$IT/test_route_shapes.py
RACE=$IT/service/actions/test_entries_race.py
OB=esgapi/organization/service/actions/branches.py
OR=esgapi/organization/tests/service/actions/test_branches_race.py

backup="$(mktemp -d /private/tmp/s12a2-planted.XXXXXX)"
case "$backup" in /private/tmp/s12a2-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 주기 → 사업장 짝 키 뺌 · P2 slot CHECK 를 월만으로(「분기·연 → 월」, 글에 세로줄이 없게) · P3 직접입력 grant 에
#   UPDATE · P4 factor_refs 뺌(늘 참인 갈래를 더함)
#   · P5 slots(…,"quarter") 가 월 칸 · P6 sum_or_none 기본 문맥(470 M3)
# ② P7 옛 칸이 셈에 남음 · P8 주기 밖 칸 받음 · P9 period 줄 0 · P10 복구가 before 로 · P11 복구 잠김 검사 뺌 ·
#   P12 계수 바꿈 뒤 다시 셈 0 · P13 다른 잎 계수 받음 · P14 빈 사유 받음 · P15 계수 줄 복구를 고객사에 · P16 선택 판이
#   행 판을 이김 · P17 unit 줄 0(M2) · P18 꺼진 사업장 추정(M4) · P19 추정만 바뀜이 히스토리(R5) · P20 restore_stale 뺌 ·
#   P21 선택 판 고름·복구가 None 아님(C) · P22 used_factor_ids 가 행을 안 봄(B1) · P32 지운 풀 계수 factor 줄 복구(길 i)
#   · P34 계수 줄 복구가 줄의 옛 판을 잡음(감독 27 R4 — 판단 C 는 그 계수의 지금 판) · P35 복구의 「선택 계수면 None」 뺌(5d 닫힘 1)
# ③ P23 계수 경로 COMPANY · P24 test_tenant_paths 표에서 입력주기 경로 뺌 · P25 복구가 회사·행 조건 없이 히스토리 읽음 ·
#   P26 route_shapes 면제를 접두로 되돌림(R7) · P33 factor 줄 복구의 운영 관리자 판정 뺌(e7 조건 — 보안 층이 빨강)
#   · P36 history_line 의 행 조건만 뺌(회사 조건 둠 — 검증 5d ③ W1·B2)
# ④ P27 set_branches_inventory 의 lock_branches 뺌(470 M1) · P28 계수 바꿈의 잎 잠금(lock_nodes → 잠그지 않는 alive_nodes)
#   · P29 블록의 사업장 잠금(lock_branch → 잠그지 않는 alive_branches — 주기 바꿈 시험이 문다) · P30·P31 잠금 아래 행
#   다시 읽기(lock_rows)를 빼고 잠금 전에 읽은 행(seen)을 씀 — 계수 바꿈·복구가 같은 _locked_row 한 줄을 쓰므로 심는
#   글은 같고 무는 시험이 다르다(해 잠금이 입력 저장과 줄 세우므로 잠그지 않는 「새로」 읽기는 같은 결과 — 보고에)
#   · P37 _block 의 선택 잠금 lock=True → False(5d ④ V2 — 잠그기 대 주기·계수·복구, [period] 는 주기 행이 있는 블록)
ROWS="P1|1|$MG|        same_company_foreign_key(table=PERIODS, column=\"site_id\", target=\"sites\"),\n||biz:$MT
P2|1|$MG|Q[1-4]))?|0[1-9]))|biz:$MT
P3|1|$MG|        grant(f'\"{CUSTOM}\"', \"SELECT, INSERT\"),|        grant(f'\"{CUSTOM}\"', \"SELECT, INSERT, UPDATE\"),|sec:tests/security/test_owner.py
P4|1|$MG|                condition=models.Q(\n                    models.Q(\n                        models.Q((\"kind\", \"factor\"), _negated=True),|                condition=models.Q(\n                    models.Q((\"id__gte\", 0)),\n                    models.Q(\n                        models.Q((\"kind\", \"factor\"), _negated=True),|biz:$MT
P5|1|$UE|        return tuple(f\"{year:04d}-Q{quarter}\" for quarter in range(1, 5))|        return tuple(f\"{year:04d}-{month:02d}\" for month in range(1, 13))|$UT
P6|1|$UE|    if not found:\n        return None\n    with localcontext(prec=_SUM_PRECISION):\n        return sum(found, Decimal(0))\n\n\ndef gases_of(|    return sum(found, Decimal(0)) if found else None\n\n\ndef gases_of(|$UT
P7|2|$AE|    return [amount for slot, amount in values.items() if slot in allowed]|    return list(values.values())|biz:$AT
P8|2|$AE|        allowed_slots=allowed,|        allowed_slots=allowed.union(slots(year)),|biz:$AT
P9|2|$AE|            for row in rows\n        ],\n    )\n    _refigure(company_id, rows, year=year, period=period|            for row in rows\n            if False\n        ],\n    )\n    _refigure(company_id, rows, year=year, period=period|biz:$AT
P10|2|$AE|    amount = _amount(line.after)|    amount = _amount(line.before)|biz:$AT
P11|2|$AE|    if problem == RESTORE_LOCKED:\n        return Locked()\n||biz:$AT
P12|2|$AE|    moved = replace(row, factor_version_id=version_id, custom_factor_id=custom_id)\n    _refigure(|    moved = replace(row, factor_version_id=version_id, custom_factor_id=custom_id)\n    return\n    _refigure(|biz:$AT
P13|2|$SP|            factor_id=factor_id,\n            factor__facility_node_id=node_id,\n|            factor_id=factor_id,\n|biz:$AT $ST
P14|2|$AE|        return {\"reason\": NEED_REASON} if required else {}|        return {}|biz:$AT
P15|2|$AE|    if line.kind == \"factor\" and not is_allowed(ROW_FACTOR, kind=actor.kind):|    if line.kind == \"factor\" and not is_allowed(ROW_FACTOR, kind=\"admin\"):|biz:$AT
P16|2|$AE|    return calc_version(factor if factor is not None else pinned)|    return calc_version(pinned)|biz:$AT
P17|2|$AE|    if before is not None and before.unit != row.unit:\n        lines.append(line(\"unit\", None, before.unit, row.unit))\n||biz:$AT
P18|2|$AE|selectors.estimated_lines(company_id, year_id) if line.site_id in site_ids]|selectors.estimated_lines(company_id, year_id)]|biz:$AT
P19|2|$AE|        if old_amount != amount:\n            lines.append(line(\"value\"|        if True:\n            lines.append(line(\"value\"|biz:$AT
P20|2|$AE|    if problem == RESTORE_STALE:\n        return RestoreStale()\n||biz:$AT
P21|2|$AE|    if custom_id is None and version_id == chosen.factor_version_id:\n        version_id = None\n§        target = (None, None) if factor_id == pinned.id else (version_id, None)|§        target = (version_id, None)|biz:$AT
P22|2|$I/models.py|        rows = models.QuerySet[\"InventoryEntryRow\"](model=cls).filter(|        rows = models.QuerySet[\"InventoryEntryRow\"](model=cls).none().filter(|biz:$AT $ST
P32|2|$AE|    if line.kind == \"factor\" and line.after_version_id is not None:\n        return _gone_version(line.after_version_id, node_id)\n||biz:$AT
P34|2|$AE|    return pool.current_version_id(view.id, node_id), None|    return line.after_version_id, None|biz:$AT
P35|2|$AE|    if isinstance(view, NotFound) or view.id == pinned.id:|    if isinstance(view, NotFound):|biz:$AT
P23|3|$PE|    \"inventory_scope12_row_factor_save\": OPERATOR,|    \"inventory_scope12_row_factor_save\": COMPANY,|biz:$APT $PT
P24|3|$TP|    (\"PUT\", \"/inventory/scope12/years/{year}/indexes/{node_id}/sites/{site_id}/period\"): \"entry_paths\",\n||sec:$TP::test_every_operation_is_in_the_table
P25|3|$SE|    rows = InventoryEntryHistory.for_company(company_id).filter(row_id=row_id, pk=history_id)|    rows = InventoryEntryHistory.unscoped.filter(pk=history_id)|sec:$SET
P26|3|$RS|        and operation_id not in SCOPE12_SCREEN_OPERATIONS|        and not operation_id.startswith(\"inventory_scope12_\")|$RS
P33|3|$AE|    if line.kind == \"factor\" and not is_allowed(ROW_FACTOR, kind=actor.kind):\n        return Forbidden(ROW_FACTOR)\n||sec:$SET::test_a_customer_bearer_cannot_restore_a_factor_line
P36|3|$SE|    rows = InventoryEntryHistory.for_company(company_id).filter(row_id=row_id, pk=history_id)|    rows = InventoryEntryHistory.for_company(company_id).filter(pk=history_id)|biz:$AT $APT
P27|4|$OB|    selectors.lock_branches(company_id, ids)\n    problem = _batch_problem(|    problem = _batch_problem(|biz:$OR
P28|4|$AE|    if factor_lock and node_id not in pool.lock_nodes({node_id}):|    if factor_lock and node_id not in pool.alive_nodes([node_id]):|biz:$RACE::test_a_factor_change_racing_the_pool_delete_of_that_factor_leaves_no_row_on_it
P29|4|$AE|import facilities_of, lock_branch, search_sites§    site = lock_branch(company_id, site_id)\n    if site is None or not site.inventory_enabled:\n        return NotFound()\n    leaf =|import alive_branches, facilities_of, lock_branch, search_sites§    site = next(iter(alive_branches(company_id, [site_id])), None)\n    if site is None or not site.inventory_enabled:\n        return NotFound()\n    leaf =|biz:$RACE::test_a_site_delete_holding_the_site_makes_the_period_change_wait_and_miss
P30|4|$AE|    row = next((line for line in selectors.lock_rows(company_id, chosen.id, seen.site_id) if line.id == row_id), None)|    row = seen|biz:$RACE::test_a_factor_change_waiting_behind_a_save_figures_with_the_saved_value
P31|4|$AE|    row = next((line for line in selectors.lock_rows(company_id, chosen.id, seen.site_id) if line.id == row_id), None)|    row = seen|biz:$RACE::test_a_restore_waiting_behind_a_save_chains_the_history
P37|4|$AE|pool.lock_nodes({node_id}):\n        return NotFound()\n    found = _year_and_selection(company_id, year, node_id, lock=True)|pool.lock_nodes({node_id}):\n        return NotFound()\n    found = _year_and_selection(company_id, year, node_id, lock=False)|biz:$RACE::test_no_change_after_the_lock_from_a_period_factor_or_restore"

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

case "$COMMIT" in 1) want=6 ;; 2) want=25 ;; 3) want=31 ;; 4) want=37 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
