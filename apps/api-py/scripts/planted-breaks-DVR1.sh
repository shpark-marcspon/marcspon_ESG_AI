#!/usr/bin/env bash
# DVR1(MARC-TICK-379) 의 심은 파손(발주서 §3): reconcile 의 AST 순수·축 시험이 상대 import 를 푸는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-DVR1.sh
# 줄마다 제품 파일 끝에 `if False:` 아래 import 한 줄을 심고(돌 때는 안 불린다 — AST 만 본다), 그 시험 파일을 두 번 돈다:
#   가지(작업 트리의 시험) · BASE(같은 경로의 BASE 시험을 잠깐 덮어쓴 것). 기대 칸 r=빨강(pytest 1) g=초록(0).
# 틀은 planted-breaks-DVA1.sh: 심기 전 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp(checkout·restore·stash 0).
#   시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 종료 1.
# 끝 줄 PLANTED=<가지 칸이 기대대로인 수>/<줄 수> BASE_AS_EXPECTED=<n>/<줄 수> FINGERPRINT=same|differs.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크·컨테이너 0.
set -u
cd "$(dirname "$0")/.."
BASE=aff154be

R=esgapi/reconcile
T=$R/tests
PURE=$T/test_calc_is_pure.py
SUMMARY=$T/test_job_summary.py
TASKS=$T/test_tasks_registered.py

backup="$(mktemp -d /private/tmp/dvr1-planted.XXXXXX)"
case "$backup" in /private/tmp/dvr1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
held=""
restore() {
  for pair in $held; do cp "$backup/${pair%%=*}" "${pair#*=}"; done
  held=""
}
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

hold() {  # hold <이름> <파일>: 되쓸 사본을 든다
  cp "$2" "$backup/$1"
  held="$held $1=$2"
}

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

verdict() {  # verdict <시험 파일> → r|g|dead
  uv run --frozen pytest "$1" -q -p no:cacheprovider >/dev/null 2>&1
  case $? in 0) echo g ;; 1) echo r ;; *) echo dead ;; esac
}

# 줄: <id>|<제품 파일>|<심는 import>|<시험 파일>|<BASE 기대>|<가지 기대>
# P1 calc 에 금지 상대 꼴 · P2 같은 자리 절대 꼴 · P3a/b tasks.py 가 자기 꾸러미 models 를 상대 꼴로(BASE 구멍)
# · P3c tasks.py 가 core models 를 상대 꼴로(BASE 도 잡던 대조) · P4 job_summary 에 금지 상대 꼴(뿌리 축 — 풀면
#   esgapi, 절대 꼴과 같은 판정) · P5 calc 의 정당한 상대 꼴(BASE 는 헛빨강) · R1(러너) job_summary 의 셀러리 절대 꼴
ROWS="P1|$R/calc/count.py|from ...core import jobs|$PURE|r|r
P2|$R/calc/count.py|from esgapi.core import jobs|$PURE|r|r
P3a|$R/tasks.py|from . import models|$TASKS|g|r
P3b|$R/tasks.py|from .models import ParseRow|$TASKS|g|r
P3c|$R/tasks.py|from ..core import models|$TASKS|r|r
P4|$R/calc/job_summary.py|from ...config import celery|$SUMMARY|r|g
P5|$R/calc/count.py|from .types import DocModel|$PURE|r|g
R1|$R/calc/job_summary.py|import celery|$SUMMARY|r|r"

total=0
ok=0
base_ok=0
echo "id   | 시험                          | BASE 기대/실제 | 가지 기대/실제"
while IFS='|' read -r id target line test want_base want_branch; do
  total=$((total + 1))
  hold target "$target"
  printf '\nif False:  # 심은 파손 DVR1 %s\n    %s\n' "$id" "$line" >>"$target"
  got_branch="$(verdict "$test")"
  hold test "$test"
  git show "$BASE:apps/api-py/$test" >"$test"
  got_base="$(verdict "$test")"
  restore
  cmp -s "$backup/target" "$target" && cmp -s "$backup/test" "$test" || { echo "  ★ $id 되쓰기 실패" >&2; exit 1; }
  [ "$got_branch" = "$want_branch" ] && ok=$((ok + 1))
  [ "$got_base" = "$want_base" ] && base_ok=$((base_ok + 1))
  printf '%-4s | %-29s | %s/%-12s | %s/%s\n' "$id" "${test#"$T"/}" "$want_base" "$got_base" "$want_branch" "$got_branch"
done <<EOF
$ROWS
EOF

after="$(fingerprint)"
fp=same
if [ "$before" != "$after" ]; then
  fp=differs
  diff <(echo "$before") <(echo "$after") >&2
fi
echo "PLANTED=$ok/$total BASE_AS_EXPECTED=$base_ok/$total FINGERPRINT=$fp"
[ "$ok" = "$total" ] && [ "$base_ok" = "$total" ] && [ "$fp" = same ]
