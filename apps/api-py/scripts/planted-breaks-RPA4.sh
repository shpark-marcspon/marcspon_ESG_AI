#!/usr/bin/env bash
# RPA4 의 심은 파손(발주서 band-handoffs/RPA4-order.md §3): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RPA4.sh
# 틀은 planted-breaks-RPQ1.sh: 심기 전 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 되돌림 0).
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 옛 글·새 글의 \n 은 줄바꿈, ␤ 는 소스의 글자 그대로의 \n(역슬래시 n).
# 빨강 = 그 시험의 종료 1(수집 실패 2 는 빨강이 아니다). 시험 칸 머리 biz: 업무 층(compose postgres 필요) · web: vitest.
# R1~R16 은 발주서 §3(#3 뒤로 — R17 없음). R4 는 prompt_model_v2 의 PAGES_SLOT 을 v1 import 로 다시 묶음.
#   R15 는 웹 modelNote 되살림 둘(표 text.ts · 모듈 줄 ai-setting-modules.ts). R18·R19 는 러너 몫(v2 끼움이 재료 자리를
#   안 끼움 · 자리 지킴을 끔 — 업무 층 B6). R20 은 경계 ③(map 대조 줄)의 끝 문장.
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

P=esgapi/drafting
F=$P/flows
FT=$P/tests/flows
TX=$P/engines/v2/texts.py
TP=$P/engines/v2/prompts.py
TT=$P/tests/engines/v2/test_texts.py
TPT=$P/tests/engines/v2/test_prompts.py
DV=$F/draft_v2.py
PM=$F/prompt_model_v2.py
WT=../web/src/entities/drafting-setting/config/text.ts
WM=../web/src/app/admin/ai-setting-modules.ts
WF=../web/src/entities/drafting-setting/model/flow.ts

backup="$(mktemp -d /private/tmp/rpa4-planted.XXXXXX)"
case "$backup" in /private/tmp/rpa4-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
current=""
restore() { if [ -n "$current" ]; then cp "$backup/keep" "$current"; current=""; fi; }
trap 'restore; rm -rf "$backup"' EXIT
trap 'exit 130' INT TERM

fingerprint() {
  git status --porcelain --untracked-files=all
  printf 'diff %s\n' "$(git diff HEAD -- "$(git rev-parse --show-toplevel)" | shasum -a 256 | cut -d' ' -f1)"
}
before="$(fingerprint)"

plant() {  # plant <파일> <옛 글> <새 글>
  python3 -I - "$1" "$2" "$3" <<'PYEOF'
import sys
def real(s):
    return s.replace("\\n", "\n").replace("␤", "\\n")
path, old, new = sys.argv[1], real(sys.argv[2]), real(sys.argv[3])
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    print(f"  ★ 옛 글자가 정확히 한 번이 아니다({text.count(old)}번): {old[:70]!r}")
    sys.exit(1)
open(path, "w", encoding="utf-8").write(text.replace(old, new, 1))
PYEOF
}

# 줄: <id>|<파일>|<옛 글>|<새 글>|<빨개질 시험(빈칸으로 나눔)>
MIN='max_output_tokens=min(model.max_output_tokens, MOCK_MAX_OUTPUT_TOKENS))'
ROWS="R1 S2 를 v1 끼움으로|$DV|v2_prompts.map_texts(|prompts.map_texts(|$FT/test_draft_v2.py
R2 S3 를 v1 끼움으로|$DV|v2_prompts.draft_texts(|prompts.draft_texts(|$FT/test_draft_v2.py
R3 v2 슬롯을 옛 글자로|$TX|PAGES_SLOT: Final = \"{페이지 글}\"|PAGES_SLOT: Final = \"{쪽 글}\"|$TT
R4 prompt_model 슬롯을 v1 import 로|$PM|MODULE: Final = \"drafting\"|from esgapi.drafting.engines.v1.texts import PAGES_SLOT\n\nMODULE: Final = \"drafting\"|$FT/test_prompt_model_v2.py $FT/test_binding_v2_settings.py
R5 표지 「쪽 머리다」 되돌림·판 그대로|$TX|줄은 페이지 머리다.|줄은 쪽 머리다.|$TT
R6 map_system 한 글자·판 그대로|$TX|빈 목록을 준다.|빈 목록을 돌려준다.|$TT
R7 글 판 @1|$TX|TEXTS_VERSION: Final = \"drafting-texts@2\"|TEXTS_VERSION: Final = \"drafting-texts@1\"|$TT $FT/test_binding_v2.py $FT/test_binding_v2_settings.py
R8 모의 min 뺌|$DV|$MIN|max_output_tokens=model.max_output_tokens)|$FT/test_draft_v2.py
R9 모의 min 을 고정 4000|$DV|$MIN|max_output_tokens=MOCK_MAX_OUTPUT_TOKENS)|$FT/test_draft_v2.py
R10 live 갈래도 깎음|$DV|        return inputs.models\n|        return StageModels(map=_mocked(inputs.models.map), draft=_mocked(inputs.models.draft))\n|$FT/test_draft_v2.py
R11 MOCK_MAX 3999|$DV|MOCK_MAX_OUTPUT_TOKENS: Final = 4000|MOCK_MAX_OUTPUT_TOKENS: Final = 3999|$FT/test_draft_v2.py
R12 모델 칸 label (S2) 되돌림|$PM|_slot(MAP, \"목차 달기\")|_slot(MAP, \"쪽 붙이기 모델(S2)\")|$FT/test_prompt_model_v2.py
R13 고정 label (ms) 되돌림|$PM|호출 시간 상한(밀리초)|호출 시간 상한(ms)|$FT/test_prompt_model_v2.py
R14 메모 「쪽마다」|$PM|\"페이지마다 그 내용이|\"쪽마다 그 내용이|$FT/test_prompt_model_v2.py
R15a 웹 modelNote 되살림(표)|$WT|    slotLabel: '칸',\n|    slotLabel: '칸',\n    modelNote: '지어낸 모의 안내 4,000',\n|web:src/entities/drafting-setting/config/text.test.ts
R15b 웹 modelNote 되살림(모듈 줄)|$WM|    name: own.module.name,\n    flow: draftingFlowSlot(own.flow),|    name: own.module.name,\n    modelNote: '지어낸 모의 안내 4,000',\n    flow: draftingFlowSlot(own.flow),|web:src/app/admin/ai-setting-modules.test.ts
R16 웹 자리 옛 글자|$WF|  map_user: ['{목차}', '{페이지 글}'],|  map_user: ['{목차}', '{쪽 글}'],|web:src/entities/drafting-setting/model/flow.test.ts
R18 v2 끼움이 재료 자리를 안 끼움|$TP|{OUTLINE_SLOT: outline, PAGES_SLOT: pages}|{OUTLINE_SLOT: outline}|$TPT $FT/test_draft_v2.py
R19 자리 지킴 끔(업무 층 B6)|$PM|missing = missing_slots(prompt.text, REQUIRED.get(FIELDS[prompt.key], ()))|missing: list[str] = []|biz:$P/tests/service/apis/test_ai_settings.py
R20 map 대조 줄 끝 문장 뺌·판 그대로(경계 ③)|$TX| \"\n        \"빈 목록은 그런 문단이 하나도 없을 때만 준다.␤\"|␤\"|$TT"

planted=0
caught=0
bad=0
while IFS='|' read -r id file old new tests; do
  [ -n "$id" ] || continue
  old="${old//\\&/&}"; new="${new//\\&/&}"
  planted=$((planted + 1))
  if [ ! -f "$file" ]; then echo "$id ★ 파일이 없다: $file"; bad=$((bad + 1)); continue; fi
  cp "$file" "$backup/keep"
  current="$file"
  if ! plant "$file" "$old" "$new"; then restore; echo "$id ★ 못 심음"; bad=$((bad + 1)); continue; fi
  if [ "${tests#biz:}" != "$tests" ]; then
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db ${tests#biz:} \
      > "$backup/log" 2>&1
    code=$?
  elif [ "${tests#web:}" != "$tests" ]; then
    (cd ../web && pnpm --filter @esg/web exec vitest run "${tests#web:}") > "$backup/log" 2>&1
    code=$?
  else
    # shellcheck disable=SC2086  # 빈칸으로 나눈 경로 목록
    env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q -p no:cacheprovider $tests > "$backup/log" 2>&1
    code=$?
  fi
  if [ "$code" = 1 ]; then red=1; else red=0; fi
  if [ "${tests#web:}" != "$tests" ]; then
    failed="$(grep -E '^ *(FAIL|×) ' "$backup/log" 2>/dev/null | sed 's/.*> //' | sort -u | head -4 | paste -sd';' -)"
    nfail="$(grep -c -E '^ *FAIL ' "$backup/log" 2>/dev/null)"
  else
    failed="$(grep -o '^FAILED [^ ]*' "$backup/log" 2>/dev/null | sed 's/^FAILED //' | sed 's/.*:://' | head -4 | paste -sd' ' -)"
    nfail="$(grep -c '^FAILED ' "$backup/log" 2>/dev/null)"
  fi
  restore
  if ! cmp -s "$backup/keep" "$file"; then echo "$id ★ 되쓰기 실패"; bad=$((bad + 1)); fi
  caught=$((caught + red))
  echo "$id $([ "$red" = 1 ] && echo 빨강 || echo ★초록) (EXIT=$code) 빨강 ${nfail:-0}개: ${failed:-}"
done <<EOF
$ROWS
EOF

if [ "$planted" != 20 ]; then echo "★ 심은 수 $planted ≠ 20"; bad=$((bad + 1)); fi
after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
