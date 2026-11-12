#!/usr/bin/env bash
# 밴드 TRW0b 의 심은 파손(발주서 §3-1).   사용: apps/web/scripts/planted-breaks-TRW0b.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P15(발주서 표 + 감독 더함) · R1~R4(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-TRW0a.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다. 단위 시험만(브라우저 0).
#   P3 은 감독 갈음(확정 판 v136 — 운영 관리자 숨김 없음, sid:MARC-ENT-380): readOnly 무시 → workCompany 머리 줄 빠짐.
#   P10 은 감독 갈음(디자인 e9 10-23): [모두 받기]는 받을 파일 0 일 때만 끈다 — 그 끔을 지움.
#   P15 는 감독 더함(sid:MARC-ISSUE-307 7 · 그린워싱 GR2): 전각 물결 갈래 지움.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
ST=$S/entities/translation/model/status.ts
RG=$S/entities/translation/model/range.ts
TABS=$S/entities/translation/ui/PartTabs.tsx
FAIL=$S/entities/translation/ui/PartFailureCard.tsx
TILES=$S/entities/translation/ui/StatTiles.tsx
BT=$S/entities/translation/ui/BatchTable.tsx
ALL=$S/pages/translation-run/ui/AllSummary.tsx
QA=$S/pages/translation-run/ui/QaIssueTable.tsx
HEAD=$S/pages/translation-run/ui/PartResultHeader.tsx
GRID=$S/pages/translation-new/ui/PageGrid.tsx
GLF=$S/pages/translation-new/ui/GlossaryField.tsx
PRF=$S/pages/translation-new/ui/PartRangeFields.tsx
TOUCHED=("$ST" "$RG" "$TABS" "$FAIL" "$TILES" "$BT" "$ALL" "$QA" "$HEAD" "$GRID" "$GLF" "$PRF")

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
E=src/entities/translation
R=src/pages/translation-run
N=src/pages/translation-new

echo "▶ 발주서 표 (P1~P15)"
code_break P1 "$TABS" "export function PartTabs" "length <= 1)" "length <= 0)" \
  "파트 하나여도 tablist" \
  "$VT $E/ui/PartTabs.test.tsx" \
  "파트 탭이 하나뿐이면 tablist 없이 children 만"
code_break P2 "$FAIL" "export function PartFailureCard" "const canRetry = !rejected && onRetry !== undefined;" "const canRetry = onRetry !== undefined;" \
  "rejected 에 다시 단추" \
  "$VT $E/ui/PartFailureCard.test.tsx" \
  "rejected(too_large): onRetry 가 있어도 다시 단추 0
rejected 에 [목록으로]만(onBack)"
code_break P3 "$BT" "return (" "{workCompany !== undefined && (" "{false && (" \
  "(갈음) workCompany 머리 줄 빠짐" \
  "$VT $E/ui/BatchTable.test.tsx" \
  "운영 관리자: workCompany 가 있으면 머리 줄"
code_break P4 "$FAIL" "{canRetry && (" "{single ? words.retrySingle : words.retryPart}" "{words.retryPart}" \
  "single 무시" \
  "$VT $E/ui/PartFailureCard.test.tsx" \
  "single → [다시 실행](파트 하나)"
code_break P5 "$TILES" "export function StatTiles" "{item.value === null ? words.none : item.value}" "{item.value ?? 0}" \
  "null 을 「0」" \
  "$VT $E/ui/StatTiles.test.tsx" \
  "null 은 「–」, 0 은 「0」"
code_break P6 "$ST" "export function screenTitleKey" "return 'needs_retry';" "return 'done';" \
  "screenTitle 한 갈래(실패 남음) 바꿈" \
  "$VT $E/model/status.test.ts $E/ui/labels.test.ts" \
  "도는 것 없이 실패가 있으면 needs_retry
화면 제목 세 갈래"
code_break P7 "$ST" "export function batchSummary" "return SUMMARY_ORDER.flatMap(" "return [...SUMMARY_ORDER].reverse().flatMap(" \
  "batchSummary 차례 뒤집음" \
  "$VT $E/model/status.test.ts" \
  "차례: 완료 → 진행 중 → 대기 → 실패
완료 2 · 진행 중 1"
code_break P8 "$BT" "const partCell" "{part.earlier.length > 0 ?" "{part.earlier.length >= 0 ?" \
  "회차 펼침 단추 늘 보임" \
  "$VT $E/ui/BatchTable.test.tsx" \
  "회차: 앞 회차가 있으면"
code_break P9 "$BT" "const partCell" "aria-expanded={open.has(key)}" "aria-expanded={false}" \
  "회차 펼침 aria-expanded 안 바뀜" \
  "$VT $E/ui/BatchTable.test.tsx" \
  "회차: 앞 회차가 있으면"
code_break P10 "$ALL" "label={words.downloadAll}" "disabled={downloadAll.disabled}" "disabled={false}" \
  "(갈음) [모두 받기] 받을 파일 0 에도 켜짐 → load" \
  "$VT $R/ui/AllSummary.test.tsx" \
  "[모두 받기] 끔(받을 자동 수정 병기본 0)"
code_break P11 "$QA" "SEVERITIES.map" "counts[level]" "counts.all" \
  "심각도 탭 수를 전체 수로" \
  "$VT $R/ui/QaIssueTable.test.tsx" \
  "심각도 탭 수 = 자료 셈"
code_break P12 "$QA" "const shown = filterIssues" "severity: severity === 'all' ? undefined : severity," "severity: undefined," \
  "High 거르기 빠짐" \
  "$VT $R/ui/QaIssueTable.test.tsx" \
  "High 탭 → High 줄만"
code_break P13 "$HEAD" "const present" "return load ? [{ key, load }] : [];" "return [{ key, load: load ?? (async () => ({ blob: new Blob(), fileName: '' })) }];" \
  "Word 단추를 files 와 상관없이 셋" \
  "$VT $R/ui/PartResultHeader.test.tsx" \
  "Word 단추는 files 에 있는 것만"
code_break P14 "$ALL" "import type { Loader }" "./PartResultHeader.tsx" "../../translation-new/ui/partLook.ts" \
  "translation-run ui 가 pages/translation-new/ui/partLook.ts 를 가져옴(같은 층의 다른 슬라이스)" \
  "$VT $L" \
  "pages/greenwash-* 의 ui/ 은 정해진 것만 가져온다"
code_break P15 "$RG" "const RANGE_TEXT" "[~\\-\\uFF5E\\u301C]" "[~\\-]" \
  "전각 물결 갈래 지움" \
  "$VT $E/model/range.test.ts" \
  "「1～3」 → 받음
「1〜3」 → 받음"

echo
echo "▶ 러너 몫 (R1~R4)"
code_break R1 "$BT" "const partActions" "(kind === 'server_error' || kind === 'partial') &&" "kind !== null &&" \
  "목록의 막은 파트(까닭 있음)에도 다시 단추(393)" \
  "$VT $E/ui/BatchTable.test.tsx" \
  "막은 파트(분량 많음)는 다시 단추 0"
code_break R2 "$GRID" "const shown = Math.min(" "visibleCount(pageCount, 0, step)" "visibleCount(0, 0, step)" \
  "PageGrid 첫 칸 수가 쪽 수를 따르지 않음(ISSUE-307 1 — 0쪽으로 뜬 그대로)" \
  "$VT $N/ui/PageGrid.test.tsx" \
  "0쪽으로 뜬 뒤 쪽 수가 오면 첫 칸들이 나온다"
code_break R3 "$GLF" "onChange={(event)" "if (picked && judgeFiles([picked], [], RULE).accepted.length > 0)" "if (picked)" \
  "용어집 [바꾸기] 꼴 검사 지움(ISSUE-307 2)" \
  "$VT $N/ui/GlossaryField.test.tsx" \
  "[바꾸기] 로 고른 파일도 드롭존과 같은 꼴 검사"
code_break R4 "$PRF" "mergeRanges(others" ".join(', ')," ".join(''),"  \
  "셋 겹침의 쪽 이음 글이 사라짐" \
  "$VT $N/ui/PartRangeFields.test.tsx" \
  "셋이 겹치면 겹친 쪽 하나 + 이름 묶음"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
