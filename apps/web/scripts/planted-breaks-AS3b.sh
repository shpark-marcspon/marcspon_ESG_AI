#!/usr/bin/env bash
# 밴드 AS3b 의 심은 파손(발주서 §3 「심은 파손」).   사용: apps/web/scripts/planted-breaks-AS3b.sh --commit <1|2>
# --commit 1 = Q1~Q8·Q13·Q14(대상 단어 카드·배선·셈 줄·layers) · 2 = 그 위에 Q9~Q12(처리 흐름 띠·셋째 열 걷기).
# 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. vitest 만 돈다 — e2e(§3-6·§3-7)로 잡는 몫은 보고 표에 적고 검증자가 따로 심는다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AP1W.sh 그대로: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(vitest ×)에서만 찾는다 — 통과한 시험 이름에 걸려 초록을 빨강으로 세지 않게.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2) ;; *) echo "사용: $0 --commit <1|2>"; exit 2 ;; esac

S=apps/web/src
GS=$S/entities/greenwash-setting
TERMS=$GS/model/terms.ts
FLOW=$GS/model/flow.ts
SLOTS=$GS/ui/index.ts
BAND=$GS/ui/FlowBand.tsx
MODULES=$S/app/admin/ai-setting-modules.ts
SCREEN=$S/pages/admin-ai-settings/ui/AiSettingsScreen.tsx
LAYERS=$S/app/guards/layers.test.ts
TOUCHED=()
for file in "$TERMS" "$FLOW" "$SLOTS" "$BAND" "$MODULES" "$SCREEN" "$LAYERS"; do
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

VT="pnpm --filter @esg/web exec vitest run src/entities/greenwash-setting src/app/admin/ai-setting-modules.test.ts src/pages/admin-ai-settings"

echo "▶ ① 대상 단어 카드·배선·셈 줄 (Q1~Q8 · Q13 · Q14)"
code_break Q1 "$TERMS" 'export function termsBlocked' 'return !draft.some((term) => term.enabled);' 'return false;' \
  '켠 것 0 검사 지움' \
  "$VT" \
  '켠 것 0 → 참, 하나 → 거짓
켠 것 0 이면 카드 밖 아래 글'
code_break Q2 "$TERMS" 'export function termsCount' 'return added + removed + toggled;' 'return Math.min(1, added + removed + toggled);' \
  '셈을 카드 하나 1 로' \
  "$VT" \
  '안 고침 0 · 더함 1 · 지움 1 · 스위치 1 · 셋 다 3'
code_break Q3 "$TERMS" 'export function termProblem' "if (draft.some((term) => termKey(term.text) === key)) return 'duplicate';" "if (false) return 'duplicate';" \
  '키 겹침 검사 지움' \
  "$VT" \
  '길이 0자·31자 · 괄호·따옴표 · 키 겹침 · 101번째
입력 오류: 칸 아래 빨강 한 줄'
code_break Q4 "$SLOTS" 'const withDefaults' ": { kind: 'failed' as const };" ": { kind: 'ok' as const, base: [] };" \
  '기본 단어 읽기 실패를 빈 목록으로' \
  "$VT" \
  '판 읽기 실패·기본 단어 읽기 실패 → failed'
code_break Q5 "$MODULES" 'async create(base, body, moduleDraft)' 'moduleDraft === null || moduleDraft === undefined ?' 'true ?' \
  'create 가 모듈 초안을 무시' \
  "$VT" \
  '고친 목록 → 그 목록 전체'
code_break Q6 "$MODULES" 'moduleDraft === null || moduleDraft === undefined ?' 'loaded.setting.terms' '(loaded.setting.terms ?? [])' \
  'module null 일 때 바탕 null 을 목록으로 펼침' \
  "$VT" \
  'null·undefined(안 고침·복제) → 바탕 판 terms 그대로
G2d: 단어 칸 없는 저장 판(12) 바탕이면 terms null 그대로'
code_break Q7 "$TERMS" 'export function termsRefusal' 'const text = words.refused[code as TermsCode];' "const text = Object.values(fields)[0]?.[0] ?? code;" \
  'TERMS_* 를 글 표 없이 서버 문장으로' \
  "$VT" \
  '넷 다 「대상 단어 — <웹 글>」'
code_break Q8 "$SLOTS" 'export const TERMS_SLOT_KEY' "= 'terms';" "= 'terms-x';" \
  '슬롯 key 를 terms 밖으로' \
  "$VT" \
  '슬롯 key 는 구성 줄 terms(body draft)와 짝'
code_break Q13 "$SCREEN" '<SaveBar' 'module.saveRule ??' 'undefined ??' \
  '화면이 saveRule 을 무시' \
  "$VT" \
  'saveRule 있으면 저장 막대 셈 줄이 그 글
모델 칸이 둘 이상이어도 saveRule 이 이김'
code_break Q14 "$LAYERS" 'extra: (file, rel, source) =>' "rel.startsWith(GREENWASH_SETTING + 'ui/') && !isTestFile(file) ?" "false ?" \
  'GS extra 의 ui→api 갈래 지움' \
  "pnpm --filter @esg/web exec vitest run src/app/guards/layers.test.ts" \
  'AS3b ①: ui 칸'

if [ "$COMMIT" -ge 2 ]; then
  echo "▶ ② 처리 흐름 띠 (Q9~Q12)"
  code_break Q9 "$FLOW" 'export const FLOW_KEYS' "'repair'," "'repairs'," \
    '마디 key 하나 바꿈' \
    "$VT" \
    '번호 마디 key 차례 = 서버 칸 key 차례
마디 넷 = 서버 칸 key 차례'
  code_break Q10 "$BAND" 'onClick={() => {' 'onPick(at);' 'onPick(picked);' \
    '마디 누름이 칸을 안 바꿈(고른 칸 그대로)' \
    "$VT" \
    '누름 → onPick(그 칸 자리)'
  code_break Q11 "$BAND" 'const isEdited' 'edited.some((one) => same(one, at))' 'false' \
    '고친 칸 표시 빠짐' \
    "$VT" \
    '고친 칸: 「● 고침」'
  code_break Q12 "$SCREEN" '<VersionColumn' '{!module.flow && (' '{true && (' \
    'flow 있어도 셋째 열을 그림' \
    "$VT" \
    'flow 있으면 셋째 열 0'
fi

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
