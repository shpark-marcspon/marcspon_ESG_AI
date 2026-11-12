#!/usr/bin/env bash
# 밴드 AD4W 의 심은 파손(발주서 §3-3 + critic 처분 B1·R1).   사용: apps/web/scripts/planted-breaks-AD4W.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD4X.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 브라우저 시험이 있는 파손(P1·P3·P10)은 playwright 가 빌드부터 다시 한다(WEB_TEST_PORT, 기본 5388).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
RUN=$S/entities/run-log
UI=$S/pages/admin-runs/ui
SCREEN=$UI/RunsScreen.tsx
DIALOG=$UI/RunDetailDialog.tsx
HOOK=$S/pages/admin-runs/hooks/useRunDetail.ts
SRV=$RUN/api/server.ts
MODEL=$RUN/model/detail.ts
TEXT=$RUN/config/text.ts
TOUCHED=("$SCREEN" "$DIALOG" "$HOOK" "$SRV" "$MODEL" "$TEXT")

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
  red="$(grep -E '^ +(×|✗|✘|FAIL) ' "$OUT" | sed -E 's/^ +//' | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
E2E="WEB_TEST_PORT=${WEB_TEST_PORT:-5388} pnpm --filter @esg/web exec playwright test e2e/admin.spec.ts -g 'AD-04a'"

echo "▶ AD-04a 실행 상세 (P1~P13)"
code_break P1 "$SCREEN" '<tr' 'onClick={(event) => open(row.id, event)}' 'onClick={(event) => open(rows[0]!.id, event)}' \
  '처리기 우회: 줄 누름이 첫 줄 id 를 엶' \
  "$VT src/pages/admin-runs; $E2E" \
  '1 둘째 줄 시각 칸 누름
AD-04a 실행 상세(밴드 AD4W)'
code_break P2 "$SCREEN" 'const detail = useRunDetail' 'useRunDetail(port, opened)' 'useRunDetail(port, null)' \
  '처리기 우회: 훅에 늘 null' \
  "$VT src/pages/admin-runs" \
  '1 둘째 줄 시각 칸 누름
2 문서 단추'
code_break P3 "$SCREEN" '단추에는 title 을 달지 않는다' 'data-run-open' 'data-run-open onClick={(event) => event.stopPropagation()}' \
  '문서 단추 누름이 줄 처리기에 닿지 않음(stopPropagation)' \
  "$VT src/pages/admin-runs; $E2E" \
  '2 문서 단추
AD-04a 실행 상세(밴드 AD4W)'
code_break P4 "$SRV" 'function isDetail' "nullable(detail.documentId, 'number') &&" "typeof detail.documentId === 'number' &&" \
  'isDetail 문서 칸을 non-null 검사로' \
  "$VT src/entities/run-log/api src/pages/admin-runs" \
  '문서 두 칸 null(문서를 지운 실행 — ND1) → ok
6 문서 두 칸 null'
code_break P5 "$SRV" 'async detail(runId)' "{ kind: 'notFound' }" "{ kind: 'failed' }" \
  'notFound 를 failed 로 접음' \
  "$VT src/entities/run-log/api src/pages/admin-runs" \
  '404 RUN_NOT_FOUND → notFound
7 404'
code_break P6 "$MODEL" 'export function stepFigures' 'if (!recorded || step.tokens === null' 'if (step.tokens === null' \
  'stepFigures 가 recorded 를 안 봄' \
  "$VT src/entities/run-log/model" \
  '기록 없음(stepUsageRecorded 거짓) + 값'
code_break P7 "$MODEL" 'export function stepFigures' 'if (step.tokens === 0 && step.costUsd === 0)' 'if (false)' \
  '0 토큰 「–」 갈래 지움' \
  "$VT src/entities/run-log/model src/pages/admin-runs" \
  '토큰 0 · 비용 0
3 단계 기록 있음'
code_break P8 "$HOOK" 'port.detail(id).then(' 'if (mine !== generation.current) return;' 'if (false) return;' \
  '세대 셈 지움' \
  "$VT src/pages/admin-runs" \
  '11 늦은 답은 버린다'
code_break P9 "$HOOK" 'useEffect(() => {' 'if (runId === null || seq === null) return;' "if (runId === null || seq === null || stored?.state.phase === 'ready') return;" \
  '다시 열 때 요청 안 함(받은 상세가 있으면 부르지 않는 캐시)' \
  "$VT src/pages/admin-runs" \
  '10 닫고 같은 줄을 다시 열면'
code_break P10 "$SRV" 'async detail(runId)' 'params: { path: { run_id: runId } },' 'params: { path: { run_id: runId }, query: { companyId: 1 } },' \
  '상세 요청에 companyId: 1' \
  "$VT src/entities/run-log/api; $E2E" \
  '경로 정확히 /run-logs/31, 질의 없음
AD-04a 실행 상세(밴드 AD4W)'
code_break P11 "$MODEL" 'export function stepLabel' 'Object.hasOwn(steps, name) ? steps[name]! : name' 'name' \
  'stepLabel 이 표를 안 봄' \
  "$VT src/entities/run-log/model src/pages/admin-runs" \
  '표에 있으면 그 글
3 단계 기록 있음'
code_break P12 "$DIALOG" 'onCloseAutoFocus' 'returnFocus.focus();' 'void returnFocus;' \
  '닫을 때 초점 되돌림 지움' \
  "$VT src/pages/admin-runs" \
  '9 [닫기]·Escape'
code_break P13 "$TEXT" 'review: {' "pending: '미검토'," "pending: '검토 전'," \
  'pending 글을 「검토 전」으로 되돌림' \
  "$VT src/entities/run-log/config src/pages/admin-runs" \
  '검토 pending 은 「미검토」
검토 배지 셋
「검토: 검토 중」'

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
