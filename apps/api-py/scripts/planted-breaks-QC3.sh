#!/usr/bin/env bash
# QC3 의 심은 파손(발주서 band-handoffs/QC3-order.md §A-3·§B·§C-4): 파손 하나를 심고, 그것을 물어야 할 것이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-QC3.sh
# 틀은 planted-breaks-RP2a.sh 그대로: 심기 전의 파일을 임시 폴더에 cp 로 들고 있다가 되쓴다(git 을 쓰지 않는다 —
#   checkout·restore·stash 0). 시작과 끝의 지문(git status 와 HEAD 와의 diff)이 다르면 무엇이 다른지 찍고 종료 1.
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 아니면 그 줄은 「못 심음」이고 실패로 센다.
# 빨강: 검사 칸이 「lint:<계약 id>」면 lint-imports 종료 ≠ 0 이고 그 계약이 BROKEN 줄에 있을 때, 「biz:」로 시작하면 업무 층
#   pytest 종료 1(이 워크트리의 compose postgres 가 떠 있어야 한다), 그 밖은 순수 층 pytest 종료 1(수집 실패 2 는 「죽음」).
# 「kept:<계약 id>」는 거꾸로 그 계약이 KEPT 여야 맞음으로 센다(시험 자리 심음).
# 끝 줄 PLANTED=<기대대로 된 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

backup="$(mktemp -d /private/tmp/qc3-planted.XXXXXX)"
case "$backup" in /private/tmp/qc3-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
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

D=esgapi/core/documents
T=esgapi/core/tests/documents
# 줄: <id>|<파일>|<옛 글>|<새 글>|<검사>
# A1 drafting 의 tools 가 translation 을 import · A2 greenwash 의 flows 가 materiality 를 import (차-2 계약 빨강)
# A3 drafting 의 시험이 translation 을 import — 차-2 는 KEPT 여야 한다(ignore_imports 의 시험 줄이 헛돌지 않는가 — 「초록」이 기대)
# B1 EPOCH_PARSER_SHA 한 글자(넓힌 지문과 어긋남) · C1 정리 함수 부름을 뺌(NUL 이 그대로 INSERT → DataError)
# C2 글자 자리 쪽 정리 부름을 뺌(container id 의 NUL → DataError, 검증 권고 R1)
ROWS="A1|esgapi/drafting/tools/blocks_text.py|import hashlib\n|import hashlib\nimport esgapi.translation  # QC3 심음\n|lint:business-modules-apart
A2|esgapi/greenwash/flows/registration.py|from typing import Final\n|from typing import Final\nimport esgapi.materiality  # QC3 심음\n|lint:business-modules-apart
A3|esgapi/drafting/tests/tools/test_blocks_text.py|import hashlib\n|import hashlib\nimport esgapi.translation  # QC3 심음\n|kept:business-modules-apart
B1|$D/contract.py|    1: \"60f829dd|    1: \"70f829dd|$T/test_contract.py
C1|$D/services.py|    document, nul_document = scrub_nul(parsed.document)|    document, nul_document = parsed.document, 0|biz:$T/test_services.py
C2|$D/services.py|    places, nul_places = scrub_nul(parsed.char_places or {})|    places, nul_places = parsed.char_places or {}, 0|biz:$T/test_services.py"

red=0; total=0
while IFS='|' read -r id file old new check; do
  [ -n "$id" ] || continue
  total=$((total + 1))
  cp "$file" "$backup/keep"; current="$file"
  if ! plant "$file" "$old" "$new"; then echo "$id 못 심음"; restore; continue; fi
  case "$check" in
    lint:*|kept:*)
      contract="${check#*:}"
      out="$(uv run --frozen lint-imports 2>&1)"; code=$?
      # 계약 이름의 앞 낱말(「차-2.」)로 줄을 찾는다 — 긴 이름은 lint 출력에서 줄이 바뀐다
      head="$(sed -n "/^\[importlinter:contract:$contract\]/,/^name/p" .importlinter | sed -n 's/^name = \([^ ]*\) .*/\1/p')"
      verdict="$(printf '%s\n' "$out" | grep -F "$head " | grep -oE 'KEPT|BROKEN' | head -1)"
      if [ "${check%%:*}" = lint ]; then want=BROKEN; else want=KEPT; fi
      if [ -n "$head" ] && [ "$verdict" = "$want" ]; then
        echo "$id 기대대로 $want (lint $contract, 종료 $code)"; red=$((red + 1))
      else
        echo "$id ★ 기대 $want · 실제 ${verdict:-없음} (lint 종료 $code)"
      fi ;;
    biz:*)
      env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider "${check#biz:}" >"$backup/out" 2>&1; code=$?
      if [ "$code" -eq 1 ]; then echo "$id 빨강 ($(grep -m1 -oE 'DataError|FAILED [^ ]+' "$backup/out"))"; red=$((red + 1)); else echo "$id 종료 $code"; fi ;;
    *)
      env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider "$check" >"$backup/out" 2>&1; code=$?
      if [ "$code" -eq 1 ]; then echo "$id 빨강 ($(grep -m1 -oE 'FAILED [^ ]+' "$backup/out"))"; red=$((red + 1)); else echo "$id 종료 $code"; fi ;;
  esac
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; total=$((total + 1)); fi
done <<EOF
$ROWS
EOF

after="$(fingerprint)"
if [ "$before" = "$after" ]; then same=same; else same=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$red/$total FINGERPRINT=$same"
[ "$red" -eq "$total" ] && [ "$same" = same ]
