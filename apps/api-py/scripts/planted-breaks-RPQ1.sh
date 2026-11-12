#!/usr/bin/env bash
# RPQ1 의 심은 파손(발주서 band-handoffs/RPQ1-order.md §3): 파손 하나를 심고, 그것을 물어야 할 시험이 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-RPQ1.sh
# 틀은 planted-breaks-RPA1.sh: 심기 전 파일을 임시 폴더에 cp 로 들고 있다가 되쓰고 cmp 로 확인한다(git 되돌림 0).
# 심기는 「옛 글자가 파일에 정확히 한 번」일 때만 한다. 옛 글·새 글의 \n 은 줄바꿈, ␤ 는 소스의 글자 그대로의 \n(역슬래시 n).
# 빨강 = 그 시험의 종료 1(수집 실패 2 는 빨강이 아니다). 시험 칸 머리 biz: 업무 층(compose postgres 필요) · web: vitest.
# 심는 꼴(1차 실측 전 설계): R3 은 칸 글이 여러 줄이라 모듈 끝에서 DEFAULT_TEXTS 를 v1 map 칸으로 다시 지음.
#   R10·R11·R12·R13 은 러너 몫(발주서 「둘 더」 + B8·B5 업무 층 분모).
# 끝 줄 PLANTED=<기대대로 빨개진 수>/<심은 수>, FINGERPRINT=same|differs. 종료 0 은 둘 다 맞을 때뿐이다.
# macOS /bin/bash 3.2. 파이썬 도움 코드는 python3 -I. LLM·네트워크 0.
set -u
cd "$(dirname "$0")/.."

P=esgapi/drafting
F=$P/flows
FT=$P/tests/flows
TX=$P/engines/v2/texts.py
TT=$P/tests/engines/v2/test_texts.py
RS=../web/src/pages/drafting-draft/ui/RunScreen.tsx
RT=src/pages/drafting-draft/ui/RunScreen.test.tsx

backup="$(mktemp -d /private/tmp/rpq1-planted.XXXXXX)"
case "$backup" in /private/tmp/rpq1-planted.*) ;; *) echo "임시 폴더가 이상하다: $backup" >&2; exit 2 ;; esac
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
TAIL='return f"{system}␤␤{MARKER_RULES}␤␤{WRITING_RULES}"'
ROWS="R1 꼬리 안 붙임|$TX|$TAIL|return f\"{system}␤␤{MARKER_RULES}\"|$TT $FT/test_draft_v2.py
R2 한국어 줄 지움|$TX|- bullet 은 늘 한국어로 쓴다. 자료가 영어 등 다른 말이어도 같다.|- bullet 을 쓴다.|$TT
R3 map 글을 v1 로|$TX|MARKER_RULES: Final = (|DEFAULT_TEXTS = PromptTexts(map_system=V1_TEXTS.map_system, map_user=V1_TEXTS.map_user, draft_system=DEFAULT_TEXTS.draft_system, draft_user=DEFAULT_TEXTS.draft_user)\n\nMARKER_RULES: Final = (|$TT
R4 versions 에 texts 없음|$F/binding_v2.py|            \"texts\": v2_texts.TEXTS_VERSION,\n||$FT/test_binding_v2.py $FT/test_binding_v2_settings.py
R5 판 대조를 옛 실행 갈래 뒤로|$F/binding_v2.py|        if \"texts\" in versions and versions[\"texts\"] != v2_texts.TEXTS_VERSION:  # 모든 갈래 전(옛 실행 갈래 포함)\n            raise AiSettingMismatch(\"versions.texts 가 지금 글 판과 다르다\")\n        if \"aiSettingId\" not in versions:\n            return DEFAULT_TEXTS, CODE_MODELS  # 열쇠 없는 옛 실행(RPA1 앞) — 코드 값\n|        if \"aiSettingId\" not in versions:\n            return DEFAULT_TEXTS, CODE_MODELS\n        if \"texts\" in versions and versions[\"texts\"] != v2_texts.TEXTS_VERSION:\n            raise AiSettingMismatch(\"versions.texts 가 지금 글 판과 다르다\")\n|$FT/test_binding_v2_settings.py
R6 글만 고치고 판 그대로|$TX|- 한 bullet 에 사실 하나만 쓴다.|- 한 bullet 에 사실 하나만 적는다.|$TT
R7 고정 값에서 writing 뺌|$F/prompt_model_v2.py|                {\"key\": \"writing\", \"label\": \"글 규칙\", \"value\": WRITING_RULES},\n||$FT/test_prompt_model_v2.py
R8 웹 map 줄 셈 되살림|$RS|name === 'draft' \&\& step \&\& step.done|name !== 'extract' \&\& step \&\& step.done|web:$RT
R9 웹 draft 셈 뺌|$RS|name === 'draft' \&\& step \&\& step.done|name === 'report' \&\& step \&\& step.done|web:$RT
R10 판만 올리고 핀 없음|$TX|TEXTS_VERSION: Final = \"drafting-texts@1\"|TEXTS_VERSION: Final = \"drafting-texts@2\"|$TT $FT/test_binding_v2.py
R11 꼬리 차례 뒤집음|$TX|$TAIL|return f\"{system}␤␤{WRITING_RULES}␤␤{MARKER_RULES}\"|$TT $FT/test_draft_v2.py
R12 저장 판 꼬리 빠짐(업무 층 B8)|$TX|$TAIL|return f\"{system}␤␤{MARKER_RULES}\"|biz:$FT/test_runs_drafting_settings.py
R13 이어 받기가 texts 를 안 견줌(업무 층 B5)|$F/binding_v2.py|    return {k: v for k, v in left.items() if k not in FACT_KEYS} == {\n        k: v for k, v in right.items() if k not in FACT_KEYS\n|    skip = {*FACT_KEYS, \"texts\"}\n    return {k: v for k, v in left.items() if k not in skip} == {\n        k: v for k, v in right.items() if k not in skip\n|biz:$FT/test_runs_drafting.py"

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

if [ "$planted" != 13 ]; then echo "★ 심은 수 $planted ≠ 13"; bad=$((bad + 1)); fi
after="$(fingerprint)"
if [ "$before" = "$after" ]; then fp=same; else fp=differs; diff <(echo "$before") <(echo "$after"); fi
echo "PLANTED=$caught/$planted"
echo "FINGERPRINT=$fp"
[ "$caught" = "$planted" ] && [ "$bad" = 0 ] && [ "$fp" = same ]
