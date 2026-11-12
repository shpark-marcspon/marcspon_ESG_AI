#!/usr/bin/env bash
# 밴드 TRW0a 의 심은 파손(발주서 §3-4).   사용: apps/web/scripts/planted-breaks-TRW0a.sh [--commit 1|2]
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. --commit 1 = ① 몫(P1~P6·R1), 2 = ① + ②(P7~P16·R2). 기본 2.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-RF1W.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다. 단위 시험만(브라우저 0).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

COMMIT=2
[ "${1:-}" = "--commit" ] && COMMIT="${2:-2}"

W=apps/web
S=$W/src
SF=$S/shared/ui/step-flow/ui/StepFlow.tsx
GSF=$S/entities/greenwash/ui/StepFlow.tsx
DB=$S/shared/ui/download-button/ui/DownloadButton.tsx
GLF=$S/entities/greenwash/ui/LoadFailure.tsx
SB=$S/shared/lib/saveBlob.ts
TM=$S/shared/lib/time.ts
TOUCHED=("$SF" "$GSF" "$DB" "$GLF" "$SB" "$TM")
if [ "$COMMIT" = 2 ]; then
  RG=$S/entities/translation/model/range.ts
  GRID=$S/pages/translation-new/ui/PageGrid.tsx
  PRF=$S/pages/translation-new/ui/PartRangeFields.tsx
  PFC=$S/pages/translation-new/ui/PreflightCard.tsx
  GM=$S/pages/translation-new/model/grid.ts
  TOUCHED+=("$RG" "$GRID" "$PRF" "$PFC" "$GM")
fi

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

# <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로 — 실패 줄에서 찾는다)>
code_break() {
  local n="$1" file="$2"
  restore
  if ! plant "$file" "$3" "$4" "$5"; then report "$n" fail "심지 못했다: $6"; return; fi
  if [ "$(changed_lines "$file")" != 1 ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $6"; restore; return; fi
  bash -c "$7" > "$OUT" 2>&1
  local code=$? missing=0 pattern red_lines
  red_lines="$(grep -E '^ *(×|✘|FAIL) ' "$OUT")"
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" <<< "$red_lines" || { missing=$((missing + 1)); echo "       실패 줄에 없다: $pattern"; }
  done <<< "$8"
  local red
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-70 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
L=src/app/guards/layers.test.ts

echo "▶ ① 공통 올림 (P1~P6·R1)"
code_break P1 "$SF" "<span" "aria-current={on ? 'step' : undefined}" "aria-current={undefined}" \
  "shared StepFlow 의 aria-current 지움" \
  "$VT src/shared/ui/step-flow src/entities/greenwash/ui/badges.test.tsx" \
  "ol 이름과 단계 이름은 받은 것, 지금 단계 하나에만 aria-current=\"step\"
세 단계를 순서 있는 목록으로 그리고, 지금 단계에만 aria-current=\"step\""
code_break P2 "$GSF" "function StepFlow" "steps = GW_TEXT.stepFlow.steps," "steps = []," \
  "그린워싱 StepFlow 감싸개가 GW_TEXT 단계 대신 빈 목록" \
  "$VT src/entities/greenwash/ui/badges.test.tsx" \
  "세 단계를 순서 있는 목록으로 그리고, 지금 단계에만 aria-current=\"step\""
# P3: 꺼진 누름은 공용 Button 이 캡처 단계에서 먼저 막는다(press 안의 disabled 줄은 DOM 으로 닿지 않는 두 번째 막음) — 그래서 Button 에 넘기는 disabled 를 지운다.
code_break P3 "$DB" "<Button" "disabled={disabled}" "disabled={false}" \
  "DownloadButton 의 disabled 검사 지움(Button 에 넘기는 disabled)" \
  "$VT src/shared/ui/download-button" \
  "disabled 면 눌러도 load 0, aria-disabled"
code_break P4 "$DB" "const press" "if (disabled || busyRef.current) return;" "if (disabled) return;" \
  "DownloadButton 의 busyRef 막음 지움" \
  "$VT src/shared/ui/download-button" \
  "받는 중 두 번 눌러도 load 한 번"
code_break P5 "$SB" "export function saveBlob" "setTimeout(() => URL.revokeObjectURL(url), 0);" "setTimeout(() => undefined, 0);" \
  "saveBlob 의 revoke 지움" \
  "$VT src/shared/lib/saveBlob.test.ts" \
  "<a> 의 download·href, 누름 한 번, 뗌, revoke 는 타이머 뒤"
code_break P6 "$TM" "const KST_OFFSET_MS" "9 * 60 * 60 * 1000" "8 * 60 * 60 * 1000" \
  "formatKst 오프셋 8시간" \
  "$VT src/entities/greenwash/model/results.test.ts" \
  "ISO → 「YYYY-MM-DD HH:mm」, 오프셋이 달라도 같은 순간"
code_break R1 "$GLF" "function LoadFailure" "retryLabel = GW_TEXT.load.retry," "retryLabel = GW_TEXT.load.toList," \
  "(러너 몫) 그린워싱 LoadFailure 감싸개의 [다시 시도] 기본 글이 [목록으로] 글" \
  "$VT src/entities/greenwash/ui/load-failure.test.tsx" \
  "failed: 오류 꼴 글 + [다시 시도]·[목록으로], 누르면 각 콜백"

if [ "$COMMIT" = 2 ]; then
  echo
  echo "▶ ② 새 번역 입력 (P7~P16·R2)"
  # 칸 규칙 시험 이름은 pages 의 partFilter 줄을 모두 「pages/greenwash-*」 로 적는다(L 의 이름 짓기 — 영문번역 줄도 같은 이름).
  code_break P7 "$GM" "import { PART_KEYS }" "entities/translation/model/index.ts" "entities/translation/model/parts.ts" \
    "translation-new 의 시험 밖 파일(model/grid.ts)이 entities/translation/model/parts.ts(문 아님)를 가져옴" \
    "$VT $L" \
    "entities/translation 에는 밖에서 공개 표면
pages/greenwash-* 의 model/ 은 정해진 것만 가져온다"
  code_break P8 "$RG" "export function parseRange" "if (trimmed.includes(',')) return" "if (trimmed.includes('\\u0000')) return" \
    "쉼표를 받음(comma 대신 not_number)" \
    "$VT src/entities/translation/model/range.test.ts" \
    "「1,3」 → comma"
  code_break P9 "$RG" "export function parseRange" "if (to > lastPage)" "if (to >= lastPage)" \
    "over_last 의 > 를 >= 로(마지막 쪽을 막음)" \
    "$VT src/entities/translation/model/range.test.ts" \
    "「64」 → 받음
마지막 쪽을 넘으면 over_last"
  code_break P10 "$RG" "export function dragRange" "return { from: Math.min(anchor, page), to: Math.max(anchor, page) };" "return { from: anchor, to: page };" \
    "dragRange 가 차례를 바꾸지 않음" \
    "$VT src/entities/translation/model/range.test.ts src/pages/translation-new/ui/PageGrid.test.tsx" \
    "dragRange 는 차례 무관
거꾸로 끌어도 from ≤ to"
  code_break P11 "$RG" "export function extendRange" "return { from: Math.min(range.from, page), to: Math.max(range.to, page) };" "return { from: range.from, to: Math.max(range.to, page) };" \
    "extendRange 앞쪽 늘림 빠짐" \
    "$VT src/entities/translation/model/range.test.ts" \
    "extendRange: 없으면 한 쪽, 뒤로·앞으로 늘림, 안이면 그대로"
  code_break P12 "$RG" "export function overlapOf" "byPage.set(page, [...(byPage.get(page) ?? []), part]);" "byPage.set(page, [...(byPage.get(page) ?? []).slice(0, 1), part]);" \
    "overlapOf 셋 겹침을 둘로" \
    "$VT src/entities/translation/model/range.test.ts" \
    "셋 겹침"
  code_break P13 "$GRID" "export function PageGrid" "useState(() => visibleCount(pageCount, 0, step))" "useState(() => pageCount)" \
    "PageGrid 첫 칸 수 = pageCount" \
    "$VT src/pages/translation-new/ui/PageGrid.test.tsx" \
    "칸 수 = min(쪽 수, 40), [더 보기] 한 번 → 쪽 수까지(또는 80)"
  code_break P14 "$GRID" "const onKeyDown" "if (event.key !== 'Enter' && event.key !== ' ') return;" "if (event.key !== ' ') return;" \
    "PageGrid 의 Enter 처리 지움" \
    "$VT src/pages/translation-new/ui/PageGrid.test.tsx" \
    "Enter·Space = 누름(빈 파트면 그 한 쪽)
구간 안의 쪽 누름 = 끝이 그 쪽으로 준다"
  # P15: CEO 한도 입력 칸은 없앴다(6쪽 고정 — 사용자 10-22 밤, 감독 전달). 갈음: CEO 7쪽에서 한도 오류 글이 안 나옴.
  code_break P15 "$PRF" "const below" "part === 'ceo' ? ceoError(range) : null" "part === 'ceo' ? ceoError(null) : null" \
    "CEO 한도(6쪽) 검사 지움 — CEO 7쪽에서 오류 글이 안 나옴" \
    "$VT src/pages/translation-new/ui/PartRangeFields.test.tsx" \
    "CEO 7쪽이면 CEO 칸에 한도 오류 글(6쪽 고정), 6쪽이면 오류 없음"
  code_break P16 "$PFC" "import { Card }" "../../../shared/ui/card/index.ts" "../../../entities/greenwash/ui/index.ts" \
    "translation-new ui 가 entities/greenwash/ui/index.ts 를 가져옴(층·문은 열려 있음 — 새 SliceRule 의 also 가 잡아야)" \
    "$VT $L" \
    "pages/greenwash-* 의 ui/ 은 정해진 것만 가져온다"
  code_break R2 "$GRID" "aria-pressed=" "parts.includes(active)" "parts.length > 0" \
    "(러너 몫) aria-pressed 가 고른 파트가 아니라 칠한 파트 아무거나" \
    "$VT src/pages/translation-new/ui/PageGrid.test.tsx" \
    "겹친 쪽은 겹침 꼴(data-overlap)과 파트 점"
fi

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
