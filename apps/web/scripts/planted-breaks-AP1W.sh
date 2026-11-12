#!/usr/bin/env bash
# 밴드 AP1W 의 심은 파손(발주서 §3-4).   사용: apps/web/scripts/planted-breaks-AP1W.sh --commit <1|2|3>
# --commit 1 = P1~P7(@3 으로 옮김) · 2 = P1~P7 다시 + P8~P11·P21·P25(배치·셈) · 3 = 그 위에 P12~P20·P22~P24(모듈 초안 슬롯·저장 중 막음).
# 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD2S.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
#   PLANT_ALL=<n> 이면 머리 아래 <옛 글자>가 든 줄 n 개를 다(파손 하나가 두 처리기를 함께 우회할 때 — P19).
# 이름 무늬는 실패 줄(vitest ×)에서만 찾는다 — 통과한 시험 이름에 걸려 초록을 빨강으로 세지 않게.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "사용: $0 --commit <1|2|3>"; exit 2 ;; esac

S=apps/web/src
ENT=$S/entities/ai-setting
PAGE=$S/pages/admin-ai-settings
SERVER=$ENT/api/server.ts
DRAFT=$ENT/model/draft.ts
SLOT=$ENT/model/slot.ts
LINES=$PAGE/model/lines.ts
REFUSAL=$PAGE/model/refusal.ts
SCREEN=$PAGE/ui/AiSettingsScreen.tsx
DRAFTHOOK=$PAGE/hooks/useDraft.ts
SAVEHOOK=$PAGE/hooks/useSave.ts
LAYERS=$S/app/guards/layers.test.ts
TOUCHED=()
for file in "$SERVER" "$DRAFT" "$SLOT" "$LINES" "$REFUSAL" "$SCREEN" "$PAGE/ui/DetailCards.tsx" \
  "$PAGE/hooks/useDraft.ts" "$PAGE/hooks/useSave.ts" "$S/app/guards/layers.test.ts"; do
  [ -f "$file" ] && TOUCHED+=("$file")
done

KEEP="$(mktemp -d)"
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
for file in "${TOUCHED[@]}"; do
  mkdir -p "$KEEP/$(dirname "$file")"
  cp "$file" "$KEEP/$file"
done
sums_before="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"

restore() { local each; for each in "${TOUCHED[@]}"; do cp "$KEEP/$each" "$each"; done; }
trap 'restore' EXIT INT TERM

passed=0
total=0
OUT="$KEEP/out.txt"

plant() {
  node -e '
    const fs = require("node:fs");
    const [file, head, from, to] = process.argv.slice(1);
    const lines = fs.readFileSync(file, "utf8").split("\n");
    const start = lines.findIndex((line) => line.includes(head));
    const all = Number(process.env.PLANT_ALL || 1);
    let done = 0;
    for (let index = Math.max(start, 0); start >= 0 && index < lines.length && done < all; index++)
      if (lines[index].includes(from)) { lines[index] = lines[index].replace(from, to); done++; }
    if (done < all) process.exit(3);
    fs.writeFileSync(file, lines.join("\n"));
  ' "$@"
}
changed_lines() { diff "$KEEP/$1" "$1" | grep -c '^<'; }

report() { # <번> <ok|fail> <말>
  total=$((total + 1))
  if [ "$2" = ok ]; then passed=$((passed + 1)); echo "  $1  빨개짐   $3"; else echo "  $1  못 잼    $3"; fi
}

# <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로 — 실패 줄에서)>
code_break() {
  local n="$1" file="$2"
  restore
  if ! plant "$file" "$3" "$4" "$5"; then report "$n" fail "심지 못했다: $6"; return; fi
  if [ "$(changed_lines "$file")" != "${PLANT_ALL:-1}" ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $6"; restore; return; fi
  bash -c "$7" > "$OUT" 2>&1
  local code=$? missing=0 pattern red_lines
  red_lines="$(grep -E '^ *(×|✘|FAIL) ' "$OUT")"
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" <<< "$red_lines" || { missing=$((missing + 1)); echo "       실패 줄에 없다: $pattern"; }
  done <<< "$8"
  local red
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-60 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run src/pages/admin-ai-settings src/entities/ai-setting"

echo "▶ ① @3 으로 옮김 (P1~P7)"
code_break P1 "$SERVER" 'export function isPromptModel' 'some(value.promptGroups, isGroup) &&' 'true &&' \
  'isPromptModel 이 promptGroups 를 안 봄' \
  "$VT" \
  'isPromptModel @3'
code_break P2 "$DRAFT" 'export function bodyOf' 'key: slot.key,' 'key: pm.promptGroups[index]?.key ?? slot.key,' \
  'bodyOf 모델 칸 key 를 묶음 key 로' \
  "$VT" \
  'bodyOf: modelSettings.steps = 모델 칸 차례'
code_break P3 "$DRAFT" 'export function bodyOf' 'steps: pm.promptGroups.map((group, index) => ({' 'steps: pm.models.map((group, index) => ({' \
  'bodyOf prompts.steps 를 모델 칸 차례로' \
  "$VT" \
  'bodyOf: modelSettings.steps = 모델 칸 차례'
code_break P4 "$DRAFT" 'export function withRoute' 'choiceOf(pm, slot, route)' 'choiceOf(pm, 0, route)' \
  'withRoute 가 늘 칸 0 의 선택지를 봄' \
  "$VT" \
  'withRoute: 그 칸 경로의 temperature 규칙'
code_break P5 "$DRAFT" 'export function changedModels' 'pm.models.flatMap(' 'pm.models.slice(0, 1).flatMap(' \
  'changes 가 모델 칸 0 만 견줌' \
  "$VT" \
  'changes: 칸 1 출력 상한만'
code_break P6 "$SLOT" 'export const promptLabel' 'pm.promptGroups[group]?.prompts[prompt]?.label' 'pm.promptGroups[0]?.prompts[prompt]?.label' \
  '거절 칸 label 이 늘 묶음 0' \
  "$VT" \
  'prompts.steps.4.prompts.1.text'
code_break P7 "$LINES" 'export const promptCount' 'model.promptGroups.reduce(' 'model.promptGroups.slice(0, 1).reduce(' \
  'promptCount 가 첫 묶음만' \
  "$VT" \
  'promptCount = 묶음 칸 합 14'

if [ "$COMMIT" -ge 2 ]; then
  echo "▶ ② 배치·카드·모듈 선언·셈 (P8~P11 · P21 · P25)"
  code_break P8 "$SCREEN" 'const slotList' 'current.promptGroups.flatMap(' 'current.promptGroups.slice(0, 1).flatMap(' \
    '셋째 열이 첫 묶음만' \
    "$VT" \
    'W2 셋째 열'
  code_break P9 "$SCREEN" 'const grouped =' '?? 0) > 1;' '?? 0) > 0;' \
    '묶음이 하나여도 묶음 머리(칸 번호 빠짐)' \
    "$VT" \
    'W5 그린워싱 꼴
셋째 열 「단계 — 프롬프트」'
  code_break P10 "$LINES" 'export function modelUses' 'for (const key of group.modelSlots)' 'for (const key of Object.keys(uses))' \
    'modelUses 가 modelSlots 를 무시(모든 칸이 모든 묶음에)' \
    "$VT" \
    'W1 모델 카드
modelUses: 칸 key'
  code_break P11 "$SCREEN" 'slots.map(({ groupIndex' 'setSlot({ group: groupIndex, prompt: promptIndex });' 'setSlot({ group: 0, prompt: promptIndex });' \
    '처리기 우회: 셋째 열 누름이 묶음 대신 0' \
    "$VT" \
    'W2 셋째 열'
  code_break P21 "$DRAFT" 'export function changes' 'const model = changedModels(pm, draft).length;' 'const model = Math.min(1, changedModels(pm, draft).length);' \
    '모델 몫을 통째 1 로(Q4 (가))' \
    "$VT" \
    'W6 모델 칸마다 1
changes 모델 몫 = 고친 모델 칸 수'
  code_break P25 "$LINES" 'export function changeList' 'if (models.length < 2 && promptGroups.length < 2) {' 'if (models.length < 2) {' \
    '저장 창 목록 꼴 조건을 「모델 칸 ≥2」 하나로 좁힘' \
    "$VT" \
    'W7 모델 칸 하나·묶음 다섯'
fi

if [ "$COMMIT" -ge 3 ]; then
  echo "▶ ③ 모듈 초안 슬롯·저장 중 막음 (P12~P20 · P22~P24)"
  code_break P12 "$DRAFTHOOK" 'const counted: ModuleChanges' 'total: common.total + moduleCount,' 'total: common.total,' \
    '셈이 모듈 몫을 안 셈' \
    "$VT" \
    'M1 모듈 고침'
  code_break P13 "$DRAFTHOOK" 'const clear =' 'useCallback(() => setEdit(null), []);' 'useCallback(() => setEdit((before) => before && { ...before, draft: null }), []);' \
    'clear 가 모듈 초안을 남김' \
    "$VT" \
    'M2 같은 판 열쇠에 남는 길'
  code_break P14 "$DRAFTHOOK" 'dirty: counted.total > 0,' 'counted.total' 'common.total' \
    'dirty 가 모듈 몫을 무시' \
    "$VT" \
    'M1 모듈 고침'
  code_break P15 "$SAVEHOOK" 'const submitSave' "form.mode === 'copy' ? null : draft.moduleBody," 'draft.moduleBody,' \
    '복제에 모듈 초안' \
    "$VT" \
    'M3 복제는'
  code_break P16 "$DRAFTHOOK" 'moduleBody: moduleEdited' 'moduleEdited ? moduleDraft : null' 'moduleDraft ?? null' \
    '셈 0 인데 moduleBody 에 초안' \
    "$VT" \
    'M3 모듈을 되돌려'
  code_break P17 "$SAVEHOOK" 'const canSave' 'draft.valid;' 'true;' \
    'canSave 가 draft.valid 를 안 봄' \
    "$VT" \
    'M4 useSave.canSave'
  code_break P18 "$REFUSAL" 'export function refusalOf' 'module &&' 'false &&' \
    'refusalOf 가 모듈에 안 물음' \
    "$VT" \
    'M7 FAKE_DRAFT_X
공통 code 밖이면 모듈에 먼저 묻는다'
  PLANT_ALL=2 code_break P19 "$DRAFTHOOK" 'const update = useCallback' 'if (locked.current) return false;' 'if (false) return false;' \
    '처리기 우회: update·updateModule 이 잠금을 안 봄(두 줄)' \
    "$VT" \
    'M8(Q7)
M9(Q7)
U5 저장 201 뒤 목록 받는 중 칸 고침은 받지 않는다'
  code_break P20 "$LAYERS" 'AP1W ③: 모듈 초안 슬롯의 카드 꼴' "!typeOnly && target === 'react'" "false && target === 'react'" \
    'layers extra 가 model 의 react 값 import 를 안 잡음' \
    "pnpm --filter @esg/web exec vitest run src/app/guards/layers.test.ts" \
    'model 은 react 를 타입으로만'
  code_break P22 "$SAVEHOOK" 'const submitSave' 'draft.clear();' '' \
    'useSave 가 저장 성공 뒤 초안을 안 비움' \
    "$VT" \
    'M2 같은 판 열쇠에 남는 길'
  code_break P23 "$SAVEHOOK" 'const submitSave' 'if (!banded) draft.setLocked(false);' 'draft.setLocked(false);' \
    '정보 띠가 서도 finally 가 잠금을 풂' \
    "$VT" \
    'M9(Q7)'
  code_break P24 "$DRAFTHOOK" 'valid:' 'slot && moduleEdited && slot.blocked' 'slot && slot.blocked' \
    'blocked 를 바탕 읽는 중·셈 0 에도 물음' \
    "$VT" \
    'M5 바탕 몫 읽는 중'
fi

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
