#!/usr/bin/env bash
# K1b-1 의 심은 고장(발주서 band-handoffs/K1b-1-order.md §3-6): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K1b-1.sh --commit <1|2|3>
#   경계별 배치: ① P1~P5(5) · ② P6~P12(누적 12) · ③ P13·P14(누적 14).
# 틀은 planted-breaks-IR4.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을 쓰지
#   않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
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
case "$COMMIT" in 1|2|3) ;; *) echo "--commit 1·2·3" >&2; exit 2 ;; esac

O=esgapi/organization
MG=$O/migrations
OT=$O/tests

backup="$(mktemp -d /private/tmp/k1b1-planted.XXXXXX)"
case "$backup" in /private/tmp/k1b1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 본사 하나 제약 뺌(UNIQUE (company, id) 로 — 늘 참) · P2 이름 unique 의 deleted_at IS NULL 뺌 · P3 복합 FK 줄 뺌
#   · P4 0003 이 「본사」 이름을 안 봄 · P5 시드가 본사를 두 번(있는지 안 보고 늘 새로)
# ② P6 branches 목록이 deleted_at 을 안 거름 · P7 일괄 삭제가 본사만 건너뜀(요청 전체 거절 대신) · P8 PUT 이 빠진 시설을
#   삭제 표시 안 함 · P9 facility_codes_in_use 를 부르지 않음 · P10 branches 권한을 CUSTOMER 로 · P11 admin 하나를 COMPANY 로
#   · P12 action 의 @transaction.atomic 뺌(둘째 services 부름에 심은 실패 — 감독 보정 4)
# ③ P13 test_tenant_paths 분류에서 새 경로 하나(/facility-codes) 뺌 · P14 코드 목록 읽기를 회사 고름으로(NOT_CHOOSING 빨강)
#   · P15(커밋 ④ — 가지 리뷰 M1) PUT 고침의 ① 단계(잠깐 삭제 표시)를 건너뜀 → 맞바꾸기·사슬 시험 빨강
ROWS="P1|1|$MG/0002_branches_facilities.py|                fields=(\"company\",),|                fields=(\"company\", \"id\"),|biz:$OT/test_models_branches.py
P2|1|$MG/0002_branches_facilities.py|                condition=models.Q((\"deleted_at__isnull\", True)),\n                fields=(\"company\", \"name\"),|                fields=(\"company\", \"name\"),|biz:$OT/test_models_branches.py
P3|1|$MG/0002_branches_facilities.py|        same_company_foreign_key(table=FACILITIES, column=\"site_id\", target=\"sites\"),\n||biz:$OT/test_models_branches.py
P4|1|$MG/0003_headquarters_seed.py|        named = alive.filter(name=HEADQUARTERS_NAME).order_by(\"id\").first()|        named = None|biz:$OT/test_migrations_0003.py
P5|1|$O/service/services/branches.py|    if found is not None:\n        return found.id\n    named = selectors.alive_site_named(company_id, HEADQUARTERS_NAME)|    named = None|biz:$OT/management/commands/test_seed_company.py
P6|2|$O/service/selectors/branches.py|    return Site.for_company(company_id).filter(deleted_at__isnull=True)|    return Site.for_company(company_id).all()|biz:$OT/service/apis/test_branches.py
P7|2|$O/service/actions/branches.py|    problem = _batch_problem(company_id, ids, touches_headquarters=True)\n    if problem is not None:\n        return problem\n    deleted = services.mark_sites_deleted|    ids = [b.id for b in selectors.alive_branches(company_id, ids) if not b.is_headquarters]\n    problem = _batch_problem(company_id, ids, touches_headquarters=True)\n    if problem is not None:\n        return problem\n    deleted = services.mark_sites_deleted|biz:$OT/service/apis/test_branches.py
P8|2|$O/service/actions/branches.py|    drop = set(current) - {row.id for row in facilities if row.id is not None}|    drop: set[int] = set()|biz:$OT/service/apis/test_branches.py
P9|2|$O/service/services/facility_codes.py|    used = facility_codes_in_use(wanted)|    used: frozenset[int] = frozenset()|biz:$OT/service/services/test_facility_codes.py
P10|2|esgapi/core/permissions.py|    \"organization_branches_list\": COMPANY,|    \"organization_branches_list\": CUSTOMER,|esgapi/core/tests/test_permissions.py::test_the_table_is_these_needs esgapi/core/tests/test_permissions.py::test_both_kinds_do_the_company_work
P11|2|esgapi/core/permissions.py|    \"organization_admin_facility_codes_create\": OPERATOR,|    \"organization_admin_facility_codes_create\": COMPANY,|esgapi/core/tests/test_permissions.py::test_the_table_is_these_needs esgapi/core/tests/test_permissions.py::test_both_kinds_do_the_company_work
P12|2|$O/service/actions/branches.py|@transaction.atomic\ndef save_branch(|def save_branch(|biz:$OT/service/actions/test_branches.py
P13|3|tests/security/test_tenant_paths.py|    (\"GET\", \"/facility-codes\"): \"reference\",\n||sec:tests/security/test_tenant_paths.py::test_every_operation_is_in_the_table
P14|3|$O/service/apis/branches.py|    permitted(request, \"organization_facility_codes_list\")\n|    company_of(permitted(request, \"organization_facility_codes_list\"))\n|sec:tests/security/test_tenant_paths.py::test_an_operator_bearer_with_two_companies_is_400_on_the_company_work tests/security/test_operator_company.py
P15|3|$O/service/services/branches.py|            if kept:  # ① 고칠 줄을 부분 unique 밖으로(한 문장)\n|            if False:  # ① 고칠 줄을 부분 unique 밖으로(한 문장)\n|biz:$OT/service/apis/test_branches.py"

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

case "$COMMIT" in 1) want=5 ;; 2) want=12 ;; 3) want=15 ;; esac  # ②③ 은 그 경계에서 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
