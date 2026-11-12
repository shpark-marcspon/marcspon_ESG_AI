#!/usr/bin/env bash
# S3K2a 의 심은 고장(발주서 band-handoffs/S3K2a-order.md §3): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S3K2a.sh --commit <1|2>
#   경계별 배치(누적): ① P1~P8·P10~P13(12 — P13 은 러너가 더한 표 밖 하나) · ② +P9(13).
# 틀은 planted-breaks-S12b-1.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 을
#   쓰지 않는다 — checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강 = 그 시험 파일의 pytest 종료 1(수집 실패 2 는 「죽음」 — 빨강이 아니다). 시험 칸이 「biz:」로 시작하면 업무 층,
#   「sec:」로 시작하면 보안 층(둘 다 이 워크트리의 compose postgres 가 떠 있어야 한다), 그 밖은 순수 층.
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
U=$I/service/utils/scope3_state.py
AC=$I/service/actions/scope3_state.py
SV=$I/service/services/scope3_state.py
SL=$I/service/selectors/scope3_state.py
AP=$I/service/apis/scope3_state.py
AD=$I/service/actions/dashboard.py
AT=$IT/service/actions/test_scope3_state.py
RT=$IT/service/actions/test_scope3_state_race.py
DT=$IT/service/actions/test_dashboard.py
PE=esgapi/core/permissions.py
TP=tests/security/test_tenant_paths.py

backup="$(mktemp -d /private/tmp/s3k2a-planted.XXXXXX)"
case "$backup" in /private/tmp/s3k2a-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 R 을 가장 새 실행(failed·진행 중 포함)으로 · P2 결과 rejected 를 R 로 · P3 핀 무시 · P4 풀어도 핀 남김 ·
#   P5 reportYear 거름 뺌 · P6 카테고리마다 「그 시트가 있는 마지막 실행」(섞기 — 559) · P7 풀기 정책 COMPANY ·
#   P8 company_of 대신 주체의 회사(운영 관리자 0 → 1) · P10 failed 만인 카테고리 잠금 통과 · P11 runId 무시 ·
#   P12 unique 위반 삼킴 뺌(Q8 — 감독 처분: ignore_conflicts 대신 create_year 꼴) · P13(러너 표 밖) 잠금 읽기의 해 거름 뺌
# ② P9 share 분모를 Scope 1·2·3 합으로
ROWS="P1|1|$U|        if candidate.status != \"done\":\n            continue\n        body = result_of(candidate.id)\n        if is_done_result(body):\n            return Base(latest=latest, run_id=candidate.id, body=body)|        return Base(latest=latest, run_id=candidate.id, body=result_of(candidate.id))|biz:$AT
P2|1|$U|        if is_done_result(body):|        if body is not None:|biz:$AT
P3|1|$AC|    if lock is not None:|    if False:|biz:$AT
P4|1|$AC|        services.clear_lock(company_id, row.id)|        pass|biz:$AT
P5|1|$U|        and report_year == year\n||biz:$AT
P6|1|$AC|            current=_current(category, base, lock, pinned),§def _states(|            current=_current(category, _mixed(company_id, category, base), lock, pinned),§def _mixed(company_id: int, category: str, base: Base) -> Base:\n    if base.body is None or category_value(base.body, category).sheets:\n        return base\n    for c in _candidates(company_id):\n        b = _bodies(company_id, [c.id]).get(c.id)\n        if c.status == \"done\" and b is not None and b.get(\"reportYear\") == base.body.get(\"reportYear\") and category_value(b, category).sheets:\n            return Base(latest=base.latest, run_id=c.id, body=b)\n    return base\n\n\ndef _states(|biz:$AT
P7|1|$PE|    \"inventory_scope3_unlock\": OPERATOR,|    \"inventory_scope3_unlock\": COMPANY,|esgapi/core/tests/test_permissions.py
P8|1|$AP|    found = actions.year_state(company_of(principal), year)|    found = actions.year_state(principal.company_id or 1, year)|sec:$TP::test_an_operator_bearer_with_two_companies_is_400_on_the_company_work
P10|1|$AC|    if current is None or not lockable(current.value):|    if current is None:|biz:$AT
P11|1|$AC|    if run_id != current.run_id:|    if False:|biz:$AT
P12|1|$SV|        if constraint_name(exc) in _UNIQUE:\n            return\n        raise|        raise|biz:$RT
P13|1|$SL|filter(year=year, locked_at__isnull=False)|filter(locked_at__isnull=False)|biz:$AT
P9|2|$AD|categories=top_categories(values, scope3)|categories=top_categories(values, total)|biz:$DT"

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

case "$COMMIT" in 1) want=12 ;; 2) want=13 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
