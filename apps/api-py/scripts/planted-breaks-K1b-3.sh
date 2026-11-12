#!/usr/bin/env bash
# K1b-3 의 심은 고장(발주서 band-handoffs/K1b-3-order.md §3-7 서버 몫): 고장 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-K1b-3.sh --commit <1|2>
#   경계별 배치(누적): ① P1·P3~P7·P9(7) · ② + P2·P8(9).
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
case "$COMMIT" in 1|2) ;; *) echo "--commit 1·2" >&2; exit 2 ;; esac

O=esgapi/organization
OA=$O/service/actions/branches.py
OS=$O/service/services/branches.py
SC=$O/service/schemas/branches.py
AP=$O/service/apis/branches.py
OT=$O/tests/service
APT=$OT/apis/test_branches.py
STT=$OT/actions/test_branches_stale.py
RT=$OT/actions/test_branches_save_race.py

backup="$(mktemp -d /private/tmp/k1b3-planted.XXXXXX)"
case "$backup" in /private/tmp/k1b3-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
# ① P1 비교 줄 뺌 · P3 update_site_row 의 updated_at 올림 뺌 · P4 비교를 lock_branch 앞(회사 조건 없는 Site.unscoped 읽기)으로
#   · P5 _refused 의 Stale case 뺌(TypeError → 500) · P6 검증이 시간대 없는 값 받음 · P7 응답 판을 잠근 행(고치기 전) 값으로
#   · P9 _detail_out 이 createdAt 을 updatedAt 에
# ② P2 lock_branch 앞에서 잠금 없이 읽은 판과 비교(R1) · P8 판단 2 의 +1µs 뺌(R2)
ROWS="P1|1|$OA|    if branch.updated_at != seen_at:  # 잠근 행과 견준다(순간 비교 — 표기·시간대 무관)\n        return Stale()\n||biz:$STT $APT
P3|1|$OS|                updated_at=max(timezone.now(), after + timedelta(microseconds=1)),\n||biz:$STT $APT
P4|1|$OA|    branch = selectors.lock_branch(company_id, branch_id)\n    if branch is None:\n        return NotFound()\n    if branch.updated_at != seen_at:|    from esgapi.organization.models import Site\n\n    peek = Site.unscoped.filter(pk=branch_id).first()\n    if peek is not None and peek.updated_at != seen_at:\n        return Stale()\n    branch = selectors.lock_branch(company_id, branch_id)\n    if branch is None:\n        return NotFound()\n    if False:|biz:$APT
P5|1|$AP|        case actions.Stale():\n            return ApplicationError(\"conflict\", \"stale\", STALE)\n||biz:$APT
P6|1|$SC|    if value.tzinfo is None or value.utcoffset() is None:\n        raise ValueError(\"시간대가 있는 ISO 8601 시각만 받는다\")\n||biz:$APT
P7|1|$OA|    return NotFound() if found is None else found  # 잠근 행이다 — None 일 수 없다|    return NotFound() if found is None else type(found)(branch=branch, facilities=found.facilities)|biz:$STT $APT
P9|1|$AP|        updatedAt=found.branch.updated_at,|        updatedAt=found.branch.created_at,|biz:$APT
P2|2|$OA|    branch = selectors.lock_branch(company_id, branch_id)\n    if branch is None:\n        return NotFound()\n    if branch.updated_at != seen_at:|    peek = selectors.branch_detail(company_id, branch_id)\n    if peek is not None and peek.branch.updated_at != seen_at:\n        return Stale()\n    branch = selectors.lock_branch(company_id, branch_id)\n    if branch is None:\n        return NotFound()\n    if False:|biz:$RT
P8|2|$OS|after + timedelta(microseconds=1))|after)|biz:$RT"

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

case "$COMMIT" in 1) want=7 ;; 2) want=9 ;; esac  # 경계마다 더한다
if [ "$planted" != "$want" ]; then echo "★ 심은 수 $planted ≠ 경계 $COMMIT 의 배치 $want"; bad=$((bad + 1)); fi

after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
