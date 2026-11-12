#!/usr/bin/env bash
# K1b-2b 의 심은 고장(발주서 band-handoffs/K1b-2b-order.md §3-8): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K1b-2b.sh --commit <1|2|3|4|5|6>
#   경계별 배치(누적): ① P1~P5(5) · ② P6~P12(12) · ③ P13~P15(15) · ④ P16~P23(23) · ⑤ P24~P25(25) · ⑥ P26(26 — 가지 리뷰 M1).
# 틀은 archive/planted-breaks-K1b-2a.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
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
case "$COMMIT" in 1|2|3|4|5|6) ;; *) echo "--commit 1·2·3·4·5·6" >&2; exit 2 ;; esac

I=esgapi/inventory
MG=$I/migrations/0002_index_selections.py
IT=$I/tests
U=$I/service/utils/index_selection.py
AC=$I/service/actions/index_selection.py
AT=$IT/service/actions/test_index_selection.py
AU=$IT/service/actions/test_ghg_pool_in_use.py
SR=esgapi/core/tests/isolation/test_static_rules.py

backup="$(mktemp -d /private/tmp/k1b2b-planted.XXXXXX)"
case "$backup" in /private/tmp/k1b2b-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 같은 회사 짝 키 뺌 · P2 alive unique 의 deleted_at 조건 뺌 · P3 grant 에 DELETE · P4 decimals CHECK 풂(0~30)
#   · P5 year_problem 위 끝 풂(올해+1)
# ② P6 잎 아닌 id 받음 · P7 availableCount 0 잎 받음 · P8 다시 저장이 잡은 판을 새 판으로(이미 고른 잎도 「새로」 —
#   새 행을 넣으려다 경합 갈래) · P9 데이터 있음 → 삭제 표시 · P10 기본 계수 없는 잎 받음 · P11 action 의
#   @transaction.atomic 뺌 · P12 시설 수가 꺼진 사업장도 셈
# ③ P13 두 줄 중 하나(index_tree)를 CUSTOMER 로 · P14 test_tenant_paths 표에서 한 경로(트리) 뺌
#   · P15 트리의 시설 수가 회사 조건 없이(남의 회사 자산/시설도 셈 — 보안 층이 빨강)
# ④ P16 nodes_in_use 를 빈 집합으로 · P17 M2 판정 뺌 · P18 L3 factors_in_use 안 부름 · P19 pinned_version 이 지운
#   계수를 거름 · P20 숨긴 선택을 사용 중에서 뺌 · P21 입구가 company_id 를 냄 · P22 입구가 삭제 표시 선택도 셈
#   · P23 표 밖(actions)에서 입구를 부름(dc 조건)
# ⑤ P24 씨앗 파일 낱줄 id 하나 바꿈(R7 빨강) · P25 지운 씨앗 노드 건너뜀 뺌(R9)
# ⑥ P26 고객사 저장의 잎 잠금(lock_nodes)을 잠그지 않는 읽기(alive_nodes)로 — 운영 관리자 지우기와 둘 다 선다
ROWS="P1|1|$MG|        same_company_foreign_key(table=SELECTIONS, column=\"inventory_year_id\", target=YEARS),\n||biz:$IT/test_models_index_selection.py
P2|1|$MG|                condition=models.Q((\"deleted_at__isnull\", True)),\n                fields=(\"inventory_year\", \"facility_node\"),|                fields=(\"inventory_year\", \"facility_node\"),|biz:$IT/test_models_index_selection.py
P3|1|$MG|        grant(f'\"{YEARS}\", \"{SELECTIONS}\"', \"SELECT, INSERT, UPDATE\"),|        grant(f'\"{YEARS}\", \"{SELECTIONS}\"', \"SELECT, INSERT, UPDATE, DELETE\"),|sec:tests/security/test_owner.py
P4|1|$MG|condition=models.Q((\"decimals__gte\", 0), (\"decimals__lte\", 3)),|condition=models.Q((\"decimals__gte\", 0), (\"decimals__lte\", 30)),|biz:$IT/test_models_index_selection.py
P5|1|$U|    if year > today.year:|    if year > today.year + 1:|$IT/service/utils/test_index_selection.py
P6|2|$AC|    alive_leaves = {node_id for node_id, info in locked.items() if info.level == LEAF}|    alive_leaves = set(locked)|biz:$AT
P7|2|$AC|    if any(counts.get(node_id, 0) == 0 for node_id in new):|    if False:|biz:$AT
P8|2|$AC|    new = {node_id for node_id in wanted if node_id not in current}|    new = set(wanted)|biz:$AT
P9|2|$AC|    with_rows = with_data(company_id, year_id, dropped) & dropped|    with_rows: set[int] = set()|biz:$AT
P10|2|$AC|    if any(node_id not in versions for node_id in new):|    if False:|biz:$AT
P11|2|$AC|@transaction.atomic\ndef save_selections(|def save_selections(|biz:$AT
P12|2|$AC|    sites = [branch for branch in search_sites(company_id).branches if branch.inventory_enabled]|    sites = list(search_sites(company_id).branches)|biz:$AT
P13|3|esgapi/core/permissions.py|    \"inventory_scope12_index_tree\": COMPANY,|    \"inventory_scope12_index_tree\": CUSTOMER,|esgapi/core/tests/test_permissions.py
P14|3|tests/security/test_tenant_paths.py|    (\"GET\", \"/inventory/scope12/index-tree\"): \"index_selection_paths\",\n||sec:tests/security/test_tenant_paths.py::test_every_operation_is_in_the_table
P15|3|$AC|    counts = leaf_counts(nodes, company_facility_counts(company_id))|    counts = leaf_counts(nodes, facility_counts(__import__(\"esgapi.organization.models\", fromlist=[\"SiteFacility\"]).SiteFacility.unscoped.values_list(\"facility_code_id\", flat=True)))|sec:tests/security/test_index_selection.py
P16|4|$I/service/selectors/index_selection.py|    return CompanyIndexSelection.used_node_ids(ids)|    return frozenset()|biz:$AU
P17|4|$I/service/actions/ghg_pool.py|    if changes_meaning and nodes_in_use([node_id]):|    if False:|biz:$AU
P18|4|$I/service/actions/ghg_pool.py|    pinned = factors_in_use(factors)|    pinned: frozenset[int] = frozenset()|biz:$AU
P19|4|$I/service/selectors/ghg_pool.py|filter(pk=version_id).first()|filter(pk=version_id, factor__deleted_at__isnull=True).first()|biz:$IT/service/selectors/test_ghg_pool.py
P20|4|$I/models.py|            deleted_at__isnull=True, facility_node_id__in=list(ids)|            deleted_at__isnull=True, hidden=False, facility_node_id__in=list(ids)|biz:$AU
P21|4|$I/models.py|        return frozenset(rows.values_list(\"facility_node_id\", flat=True))|        return frozenset(rows.values_list(\"company_id\", flat=True))|$SR::test_the_model_entrances_answer_only_pool_ids
P22|4|$I/models.py|            deleted_at__isnull=True, facility_node_id__in=list(ids)|            facility_node_id__in=list(ids)|$SR::test_the_model_entrances_answer_only_pool_ids
P23|4|$I/service/actions/ghg_pool.py|    pinned = factors_in_use(factors)|    pinned = factors_in_use(factors) or CompanyIndexSelection.used_factor_ids(factors)|$SR::test_the_model_entrances_are_called_only_from_their_places
P24|5|$I/data/ghg-pool-seed.json|\"gir-2025:main:r7\"|\"gir-2025:main:r3\"|$IT/service/utils/test_ghg_pool_seed_ids.py
P25|5|$I/service/actions/ghg_pool.py|        if deleted:  # R9|        if False:  # R9|biz:$IT/service/actions/test_ghg_pool_seed.py
P26|6|$AC|    locked = pool.lock_nodes(|    locked = pool.alive_nodes(|biz:$IT/service/actions/test_ghg_pool_race.py::test_a_company_save_and_an_admin_delete_of_the_same_leaf_end_with_one_side"

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

case "$COMMIT" in 1) want=5 ;; 2) want=12 ;; 3) want=15 ;; 4) want=23 ;; 5) want=25 ;; 6) want=26 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
