#!/usr/bin/env bash
# 밴드 RF1W 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-RF1W.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD2S.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘)에 댄다. 명령이 둘(단위; 브라우저)이면 명령마다 EXIT 를 따로 보고 둘 다 빨개야 빨강(교훈 1절).
# 브라우저 시험이 있는 파손(P2·P6)은 playwright 가 빌드부터 다시 한다(WEB_TEST_PORT, 기본 5392).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
SRV=$S/entities/run-log/api/server.ts
HOOK=$S/pages/admin-runs/hooks/useRunFile.ts
DIALOG=$S/pages/admin-runs/ui/RunDetailDialog.tsx
TOUCHED=("$SRV" "$HOOK" "$DIALOG")

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
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-60 | head -6 | tr '\n' '|')"
  local exits
  exits="$(grep -oE 'UNIT_EXIT=[0-9]+ E2E_EXIT=[0-9]+' "$OUT")"
  [ -n "$exits" ] && red="$exits · $red"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
E2E="WEB_TEST_PORT=${WEB_TEST_PORT:-5392} pnpm --filter @esg/web exec playwright test e2e/admin.spec.ts -g 'RF1W'"
# 둘 다 빨개야 EXIT=1(하나라도 초록이면 0 — 「a; b」 의 끝 EXIT 만 보는 구멍을 막는다).
both() { echo "$1; a=\$?; $2; b=\$?; echo \"UNIT_EXIT=\$a E2E_EXIT=\$b\"; [ \$a -ne 0 ] && [ \$b -ne 0 ] && exit 1; exit 0"; }

echo "▶ AD-04a 결과 파일 [내려받기] (P1~P6)"
code_break P1 "$SRV" 'async file(' "parseAs: 'blob'," "parseAs: 'blob', pathSerializer: (path: string, values: Record<string, unknown>) => path.replace('{run_id}', String(values.run_id)).replace('{name}', String(values.name)),"  \
  '이름 encode 뺌(경로 칸을 날 글자로)' \
  "$VT src/entities/run-log/api" \
  'URL = /run-logs/7/files/<encode 된 이름>'
code_break P2 "$SRV" 'async file(' 'fileNameFromDisposition(' 'name ?? fileNameFromDisposition(' \
  'Content-Disposition 무시하고 늘 줄 이름' \
  "$(both "$VT src/entities/run-log/api src/pages/admin-runs" "$E2E")" \
  '(따옴표 꼴)도 서버 이름
② 누르면 요청 하나
(밴드 RF1W): 상세 → step null 줄만 단추'
code_break P3 "$DIALOG" '<span className="min-w-0 break-all">{file.name}</span>' '{file.step === null && (' '{(file.step === null || true) && (' \
  'step 판정 뺌(모든 줄 단추)' \
  "$VT src/pages/admin-runs" \
  '① step null 줄만 [내려받기]'
code_break P4 "$HOOK" 'const download = useCallback(' 'if (runId === null || seq === null || busy.current) return;' 'if (runId === null || seq === null) return;' \
  '받는 중 막음을 처리기에서 뺌(꼴만 꺼짐)' \
  "$VT src/pages/admin-runs" \
  '③ 받는 중'
code_break P5 "$HOOK" '.then((outcome) => {' 'if (mine !== generation.current) return;' 'if (false) return;' \
  '늦은 답 버리기 뺌' \
  "$VT src/pages/admin-runs" \
  '⑤ 받는 중 모달 닫음'
code_break P6 "$DIALOG" 'data-testid="file-error"' "{fetching.phase === 'failed' && (" '{false && (' \
  '실패 글 안 그림' \
  "$(both "$VT src/pages/admin-runs" "$E2E")" \
  '④ 실패(503)
(밴드 RF1W): 상세 → step null 줄만 단추'

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
