#!/usr/bin/env bash
# 밴드 AD2W 의 심은 파손.   사용: apps/web/scripts/planted-breaks-AD2W.sh --commit <2|3|4>(①② 는 커밋 하나 — --commit 2 가 P1~P4)
# 경계마다 그 경계의 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD4X.sh·F9.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 2 | 3 | 4) ;; *) echo "사용: $0 --commit <2|3|4>"; exit 2 ;; esac

W=apps/web
S=$W/src
AI=$S/entities/ai-setting
PAGE=$S/pages/admin-ai-settings
SCREEN=$PAGE/ui/AiSettingsScreen.tsx
LAYERS=$S/app/guards/layers.test.ts
TOUCHED=("$SCREEN" "$PAGE/hooks/usePromptModel.ts" "$AI/model/slot.ts" "$LAYERS")
for extra in "$PAGE/hooks/useDraft.ts" "$AI/model/draft.ts" "$AI/model/chars.ts" "$AI/model/fields.ts" "$S/app/admin/AdminRoutes.tsx"; do [ -f "$extra" ] && TOUCHED+=("$extra"); done

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
    const at = start < 0 ? -1 : lines.findIndex((line, index) => index >= start && line.includes(from));
    if (at < 0) process.exit(3);
    lines[at] = lines[at].replace(from, to);
    fs.writeFileSync(file, lines.join("\n"));
  ' "$@"
}
changed_lines() { diff "$KEEP/$1" "$1" | grep -c '^<'; }

report() { # <번> <ok|fail> <말>
  total=$((total + 1))
  if [ "$2" = ok ]; then passed=$((passed + 1)); echo "  $1  빨개짐   $3"; else echo "  $1  못 잼    $3"; fi
}

# <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로)>
code_break() {
  local n="$1" file="$2"
  restore
  if ! plant "$file" "$3" "$4" "$5"; then report "$n" fail "심지 못했다: $6"; return; fi
  if [ "$(changed_lines "$file")" != 1 ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $6"; restore; return; fi
  bash -c "$7" > "$OUT" 2>&1
  local code=$? missing=0 pattern
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" "$OUT" || { missing=$((missing + 1)); echo "       출력에 없다: $pattern"; }
  done <<< "$8"
  local red
  red="$(grep -E '^ +(×|✗|FAIL) ' "$OUT" | sed -E 's/^ +//' | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
# 껍데기의 react import 줄(③ 이 useEffect 를 더했다 — 처음 나오는 「} from 'react';」 줄).
REACT_IMPORT="} from 'react';"
E2E="WEB_TEST_PORT=${WEB_TEST_PORT:-5384} pnpm --filter @esg/web exec playwright test"

if [ "$COMMIT" = 2 ]; then
  echo "▶ ①② 슬롯·prompt-model 보기 (P1·P1b·P2·P2b·P3·P4)"
  code_break P1 "$SCREEN" "$REACT_IMPORT" "from 'react';" "from 'react'; import { idOut } from '../../../entities/greenwash-setting/model/index.ts';" \
    '껍데기에 entities/greenwash-setting import 한 줄' \
    "$VT src/app/guards/layers.test.ts" \
    'AiSettingsScreen.tsx'
  code_break P1b "$SCREEN" "$REACT_IMPORT" "from 'react';" "from 'react'; import { PARTS } from '../../../entities/greenwash/ui/index.ts';" \
    '껍데기에 entities/greenwash/ui/index.ts import 한 줄' \
    "$VT src/app/guards/layers.test.ts" \
    'AiSettingsScreen.tsx'
  code_break P2 "$LAYERS" "dir: 'app/admin'," "'ai-setting-modules.ts': {" "'nope.ts': { packages: /^\$/, files: [] }, 'ai-setting-modules.ts': {" \
    'layers 규칙에 없는 파일 경로 한 줄' \
    "$VT src/app/guards/layers.test.ts" \
    '칸 규칙의 맨 위 파일·시험 이름과 슬라이스 경계의 폴더는 디스크에 있다'
  code_break P2b "$LAYERS" "'AdminRoutes.tsx': {" "files: ['runtime.ts', 'ai-setting-modules.ts']," "files: ['runtime.ts', 'ai-setting-modules.ts', 'nope.ts']," \
    "layers 규칙 files: 에 없는 파일 한 줄" \
    "$VT src/app/guards/layers.test.ts" \
    '칸 규칙의 맨 위 파일·시험 이름과 슬라이스 경계의 폴더는 디스크에 있다'
  code_break P3 "$PAGE/hooks/usePromptModel.ts" 'const ask = useCallback' 'if (asked.current.has(wanted)) return;' 'if (false) return;' \
    '판 key 캐시 지움(고를 때마다 GET)' \
    "$VT src/pages/admin-ai-settings" \
    '다시 골라도 0'
  code_break P4 "$AI/model/slot.ts" 'export function versionLabel' 'row.title === null ? row.number : `${row.number} · ${row.title}`' '`${row.number} · ${row.title ?? '"''"'}`' \
    "이름 꼴 title ?? ''(null 판에 「v1 · 」)" \
    "$VT src/pages/admin-ai-settings" \
    '「v3 · 이름」'
fi

if [ "$COMMIT" = 3 ]; then
  echo "▶ ③ 판 초안·한 번 저장 (P5~P11)"
  code_break P5 "$SCREEN" 'const submitSave' 'const body = bodyOf(model, draft.draft, {' 'const body = ((given: object) => given as never)({ criteria: null,' \
    '처리기 우회: bodyOf 를 건너뛰고 {criteria, title, memo} 만 지어 보냄' \
    "$VT src/pages/admin-ai-settings" \
    '본문 키 넷'
  code_break P6 "$SCREEN" 'const submitSave' ' || sending.current) return;' ') return;' \
    '보내기 막음(sending) 지움' \
    "$VT src/pages/admin-ai-settings" \
    '보내는 중 두 번'
  code_break P7 "$SCREEN" 'const canApply =' '!dirty;' 'true;' \
    '[이 버전 적용] 의 off 셈에서 고침(dirty) 뺌(처리기 가드도 같은 셈)' \
    "$VT src/pages/admin-ai-settings" \
    '끔 단추 셋'
  code_break P8 "$PAGE/hooks/useDraft.ts" 'const counted = useMemo(' '(pm && mine ? changes(pm, mine) : NONE)' '(pm && mine ? { model: true, prompts: [], total: 1 } : NONE)' \
    '셈이 「손댄 적 있음」으로(되돌려도 1)' \
    "$VT src/pages/admin-ai-settings" \
    '같은 값으로 되돌리면 0'
  code_break P9 "$SCREEN" 'const onPick = ' 'if (dirty) {' 'if (false) {' \
    '고친 채 다른 판 누름이 창 없이 바뀜' \
    "$VT src/pages/admin-ai-settings" \
    '고친 채 다른 판(v2) 누름'
  code_break P10 "$S/app/admin/AdminRoutes.tsx" 'useBlocker({' 'shouldBlockFn: () => dirty.current,' 'shouldBlockFn: () => false,' \
    'useBlocker 막음 지움(메뉴 이동이 창 없이 감)' \
    "$E2E e2e/admin.spec.ts -g 'AD-02 한 번 저장' --reporter=line" \
    'AD-02 한 번 저장'
  code_break P11 "$SCREEN" 'const submitSave' 'setPicked(outcome.key);' 'void outcome.key;' \
    '201 뒤 새 판 고름(→ 그 판 prompt-model 다시 읽기) 지움' \
    "$VT src/pages/admin-ai-settings" \
    'v4 고름·prompt-model 14'
fi

if [ "$COMMIT" = 4 ]; then
  echo "▶ ④ 프롬프트 칸 고침 (P12~P14 · P15 — 감독 덧붙임 cd 답)"
  code_break P12 "$AI/model/chars.ts" 'export const codepoints' '[...text].length' 'text.length' \
    'codepoints → s.length(UTF-16 길이)' \
    "$VT src/entities/ai-setting/model" \
    '4바이트 글자(이모지·한자 확장 B) 8000자 = 8000'
  code_break P13 "$AI/model/chars.ts" 'export const pyStrip' 'stripWith(PY_SPACE)' '(text: string) => text.trim()' \
    'pyStrip → s.trim()' \
    "$VT src/entities/ai-setting/model" \
    'Python 공백 29자를 전부 앞뒤에서 뗀다'
  code_break P14 "$AI/model/fields.ts" 'return {' 'prompt: Number(hit[2]),' 'prompt: Number(hit[2]) - 1,' \
    'fields 경로 칸 번호 −1' \
    "$VT src/entities/ai-setting/model/fields.test.ts" \
    'prompts.steps.0.prompts.3.memo → (0, 3, memo)'
  code_break P15 "$SCREEN" 'const submitSave' 'if (!(await settings.refreshKeep())) {' 'if (!(await settings.refresh())) {' \
    '저장 뒤 목록 다시 읽기 실패를 화면 전체 실패 상자로(cd 답 어김)' \
    "$VT src/pages/admin-ai-settings" \
    '저장은 됐는데 목록 다시 읽기만 실패'
fi

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
