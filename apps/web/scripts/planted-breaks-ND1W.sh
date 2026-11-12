#!/usr/bin/env bash
# 밴드 ND1W 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-ND1W.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD4X.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
RUN=$S/entities/run-log
SCREEN=$S/pages/admin-runs/ui/RunsScreen.tsx
TOUCHED=("$RUN/api/server.ts" "$RUN/model/detail.ts" "$SCREEN")

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
  red="$(grep -E '^ +(×|✗|FAIL) |error TS' "$OUT" | sed -E 's/^ +//' | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"

echo "▶ 문서 없는 줄 (P1~P4)"
code_break P1 "$RUN/api/server.ts" 'function isRow' "nullable(row.documentId, 'number')" "typeof row.documentId === 'number'" \
  '목록 가드를 옛 typeof … number 로' \
  "$VT src/entities/run-log/api src/pages/admin-runs" \
  '문서 두 칸 null 인 줄(문서 없는 실행 — ND1W)도 꼴 맞음
8 문서 없는 줄'
code_break P2 "$SCREEN" 'data-document-missing' '{words.empty}' "{''}" \
  'null 줄 문서 칸에 「–」 대신 빈 글' \
  "$VT src/pages/admin-runs" \
  '8 문서 없는 줄'
code_break P3 "$SCREEN" 'data-run-open' 'words.detail.openLabelNoDocument(at)' "words.detail.openLabel('')" \
  "aria-label 을 openLabel('') 로" \
  "$VT src/pages/admin-runs" \
  '8 문서 없는 줄'
code_break P4 "$RUN/model/detail.ts" 'export type RunLogDetail' "Schemas['RunLogDetailOut'];" "Omit<Schemas['RunLogDetailOut'], 'documentName'> & { documentName: string };" \
  'detail 넓힘 되살림(documentName string — Schemas 와 다름)' \
  "pnpm --filter @esg/web typecheck" \
  'src/entities/run-log/model/detail.test.ts('

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
