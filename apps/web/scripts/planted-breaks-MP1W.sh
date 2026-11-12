#!/usr/bin/env bash
# 밴드 MP1W 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-MP1W.sh
# 파손을 하나씩 심고(파일마다 한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-ND1W.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 다른 점: 한 파손이 파일 둘을 고칠 수 있고(P4), 빨개질 시험 이름은 실패 줄(× · ✘ · FAIL 로 시작)에서만 찾는다.
# 포트는 WEB_TEST_PORT(기본 5394 — 브라우저 시험이 빌드해 미리보기를 띄운다).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_TEST_PORT="${WEB_TEST_PORT:-5394}"

W=apps/web
S=$W/src
SERVER=$S/entities/run-log/api/server.ts
SCREEN=$S/pages/admin-runs/ui/RunsScreen.tsx
ROUTES=$S/app/admin/AdminRoutes.tsx
TOUCHED=("$SERVER" "$SCREEN" "$ROUTES")

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

# <번> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로)> <심기 하나 = 파일 TAB 머리 TAB 옛 TAB 새>...
code_break() {
  local n="$1" say="$2" command="$3" patterns="$4"
  shift 4
  restore
  local spec file head from to
  for spec in "$@"; do
    IFS=$'\t' read -r file head from to <<< "$spec"
    if ! plant "$file" "$head" "$from" "$to"; then report "$n" fail "심지 못했다: $say ($file)"; restore; return; fi
    if [ "$(changed_lines "$file")" != 1 ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $say ($file)"; restore; return; fi
  done
  bash -c "$command" > "$OUT" 2>&1
  local code=$? missing=0 pattern red_lines
  red_lines="$(grep -E '^ *(×|✘|FAIL) ' "$OUT")"
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" <<< "$red_lines" || { missing=$((missing + 1)); echo "       실패 줄에 없다: $pattern"; }
  done <<< "$patterns"
  local red
  red="$(sed -E 's/^ +//' <<< "$red_lines" | sort -u | head -6 | cut -c1-110 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$say — EXIT=$code · $red"; else report "$n" fail "$say — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
PW="pnpm --filter @esg/web exec playwright test e2e/admin.spec.ts -g 'MP1W'"
T=$'\t'
COND="state.phase === 'ready' && state.metrics.aiProviderMock"

echo "▶ 안내 띠 = 서버 지표 (P1~P4)"
code_break P1 'isMetrics 의 aiProviderMock 줄을 늘 참으로(칸 확인 뺌)' \
  "$VT src/entities/run-log/api" \
  'metrics 꼴 틀림: aiProviderMock 없음(MP1W)
metrics 꼴 틀림: aiProviderMock 이 글자(MP1W)' \
  "$SERVER${T}function isMetrics${T}typeof metrics.aiProviderMock === 'boolean'${T}true"
code_break P2 '띠 조건을 늘 참으로' \
  "$VT src/pages/admin-runs; a=\$?; $PW; b=\$?; exit \$((a | b))" \
  '모의 공급사 안내 띠: aiProviderMock 거짓이면 없다
AD-04 안내 띠(밴드 MP1W)' \
  "$SCREEN${T}const aiMock${T}$COND${T}true"
code_break P3 '지표 실패·받는 중에도 띠(조건에서 ready 확인 뺌)' \
  "$VT src/pages/admin-runs" \
  '모의 공급사 안내 띠: 지표 실패면 없다
모의 공급사 안내 띠: 지표를 받는 중엔 없고' \
  "$SCREEN${T}const aiMock${T}$COND${T}(state.phase !== 'ready' || state.metrics.aiProviderMock)"
code_break P4 'AdminRoutes 가 상수 true 를 넘기고 화면이 그 prop 을 우선(우회 되살림)' \
  "$VT src/app/admin/router.test.tsx" \
  '서버 지표 aiProviderMock false' \
  "$ROUTES${T}export function RunsRoute${T}<RunsScreen port={port} />${T}<RunsScreen port={port} {...{ aiProviderMock: true }} />" \
  "$SCREEN${T}const aiMock${T}$COND${T}(arguments[0] as { aiProviderMock?: boolean }).aiProviderMock ?? ($COND)"

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
