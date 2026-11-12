#!/usr/bin/env bash
# QC4 의 심은 파손(발주서 band-handoffs/QC4-order.md 「심은 파손」): 정적 규칙을 비켜 가던 꼴 셋을 제품 파일에 심고, 그것을
# 물어야 할 시험이 지금 판에서는 빨개지고 BASE 판(4dbac207 의 test_static_rules.py)에서는 초록이었는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-QC4.sh
# 틀은 planted-breaks-QC3.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓴다(git 을 쓰지 않는다 —
#   checkout·restore·stash 0). BASE 판은 `git show 4dbac207:<시험 파일>` 을 잠깐 시험 파일 자리에 써 돌리고 되쓴다.
# 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 기대: 지금 판 pytest 종료 1(그 시험 하나) · BASE 판 종료 0. 끝 줄 PLANTED=<기대대로 된 수>/<심은 수>, FINGERPRINT=same|differs.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크·컨테이너 0.
set -u
cd "$(dirname "$0")/.."

backup="$(mktemp -d /private/tmp/qc4-planted.XXXXXX)"
case "$backup" in /private/tmp/qc4-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
RULES=esgapi/core/tests/isolation/test_static_rules.py
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; cp "$backup/rules" "$RULES"; }
cp "$RULES" "$backup/rules"
git show "4dbac207:apps/api-py/$RULES" >"$backup/rules-base" || exit 2
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- . | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>  (\n 은 줄바꿈)
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
path, old, new = sys.argv[1], sys.argv[2].replace("\\n", "\n"), sys.argv[3].replace("\\n", "\n")
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PYEOF
}

run() {  # run <시험 id> — pytest 종료 코드
  env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider "$1" >"$backup/out" 2>&1
}

A=esgapi/inventory/service/actions/ghg_pool.py
IMPORT='from django.db import transaction\n'
QS="$RULES::test_querysets_are_built_only_in_the_entrances"
ME="$RULES::test_the_model_entrances_are_called_only_from_their_places"
# 줄: <id>|<파일>|<옛 글>|<새 글>|<시험>
# R2 QuerySet 하위 클래스로 짓기 · R3a 모듈을 붙여 부른 입구 · R3b 함수 안 모델 별칭
ROWS="R2|$A|$IMPORT|${IMPORT}from django.db import models  # QC4 심음\nclass _R(models.QuerySet):\n    pass\nrows = _R(model=CompanyIndexSelection)\n|$QS
R3a|$A|$IMPORT|${IMPORT}import esgapi.inventory.models as m  # QC4 심음\nm.CompanyIndexSelection.used_node_ids([1])\n|$ME
R3b|$A|$IMPORT|${IMPORT}def _qc4():  # QC4 심음\n    s = CompanyIndexSelection\n    return s.used_factor_ids([1])\n|$ME"

red=0; total=0
while IFS='|' read -r id file old new check; do
  [ -n "$id" ] || continue
  total=$((total + 1))
  cp "$file" "$backup/keep"; current="$file"
  if ! plant "$file" "$old" "$new"; then echo "$id 못 심음"; restore; continue; fi
  run "$check"; now=$?
  failed="$(grep -m1 -oE 'FAILED [^ ]+' "$backup/out")"
  cp "$backup/rules-base" "$RULES"
  run "$check"; base=$?
  cp "$backup/rules" "$RULES"
  if [ "$now" -eq 1 ] && [ "$base" -eq 0 ]; then
    echo "$id 빨강 ($failed) · BASE 초록"; red=$((red + 1))
  else
    echo "$id ★ 지금 종료 $now · BASE 종료 $base"
  fi
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; total=$((total + 1)); fi
done <<EOF
$ROWS
EOF

after="$(fingerprint)"
if [ "$before" = "$after" ]; then same=same; else same=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$red/$total FINGERPRINT=$same"
[ "$red" -eq "$total" ] && [ "$same" = same ]
