#!/usr/bin/env bash
# 밴드 AD4X 의 심은 파손.   사용: apps/web/scripts/planted-breaks-AD4X.sh --commit <1|2|3>
# 경계마다 그 경계의 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-F9.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "사용: $0 --commit <1|2|3>"; exit 2 ;; esac

W=apps/web
S=$W/src
RUN=$S/entities/run-log
SCREEN=$S/pages/admin-runs/ui/RunsScreen.tsx
AUDIT=$S/entities/audit-log
ROUTES=$S/app/admin/AdminRoutes.tsx
TOUCHED=("$RUN/model/run.ts" "$RUN/api/server.ts" "$SCREEN" "$AUDIT/model/audit.ts" "$AUDIT/api/server.ts" "$ROUTES")
for extra in "$S/pages/admin-runs/hooks/useRunExport.ts"; do [ -f "$extra" ] && TOUCHED+=("$extra"); done

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
E2E="WEB_TEST_PORT=${WEB_TEST_PORT:-5386} pnpm --filter @esg/web exec playwright test"

if [ "$COMMIT" = 1 ]; then
  echo "▶ ① 열·거르기 (P1~P5)"
  code_break P1 "$RUN/model/run.ts" 'export function runQuery' 'query.review = filter.review' 'void filter.review' \
    'runQuery 가 review 를 싣지 않음' \
    "$VT src/pages/admin-runs src/entities/run-log/model" \
    '「검토: 검토 중」 → review=in_review'
  code_break P2 "$SCREEN" 'const narrowed' "filter.review !== 'all';" 'false;' \
    'narrowed 에서 review 뺌' \
    "$VT src/pages/admin-runs" \
    '검토만 걸고 0건'
  code_break P3 "$RUN/model/run.ts" 'export function aiSettingText' 'if (setting.id === null)' 'if (setting.id === -1)' \
    'aiSettingText 가 id null 에도 name' \
    "$VT src/entities/run-log/model src/pages/admin-runs" \
    'AI 설정: 없음 → 「–」(missing)
AI 설정 칸: 판 이름(v3)'
  code_break P4 "$RUN/api/server.ts" 'function isRow' '(row.review === null ||' '(true ||' \
    'isRow 의 review 검사 지움' \
    "$VT src/entities/run-log/api" \
    'review 모르는 값'
  code_break P5 "$SCREEN" '{row.review === null ?' 'row.review === null' 'row.review === undefined' \
    'null 검토에도 배지 갈래' \
    "$VT src/pages/admin-runs" \
    '검토 배지 셋'
fi

if [ "$COMMIT" = 2 ]; then
  echo "▶ ② 엑셀 (P6~P13)"
  SRV="$RUN/api/server.ts"
  code_break P6 "$SCREEN" 'const exportRuns' '.exportFile(listQuery)' '.exportFile({})' \
    '처리기 우회: 빈 쿼리로 export' \
    "$VT src/pages/admin-runs" \
    '거르기 넷(모듈·상태·검토·기간) 뒤 누름'
  code_break P7 "$SCREEN" 'const exportRuns' '.exportFile(listQuery)' '.exportFile(runQuery(filter, now()))' \
    '처리기 우회: 칸의 글로 쿼리를 따로 지음' \
    "$VT src/pages/admin-runs" \
    '검색 칸에 친 글이 300ms 안이면'
  code_break P8 "$SCREEN" 'const exportRuns' 'if (exportBusy.current) return;' 'if (exportBusy.current && false) return;' \
    'busyRef 검사 지움' \
    "$VT src/pages/admin-runs" \
    '빠른 두 번(같은 그리기 안)'
  code_break P9 "$SCREEN" 'const exportRuns' 'if (state.count === 0) return;' 'if (state.count === 0 && false) return;' \
    '0건 처리기 막음만 지움(aria-disabled 그대로)' \
    "$VT src/pages/admin-runs" \
    '0건: 끔(aria-disabled'
  code_break P10 "$SRV" 'async exportFile' "{ kind: 'tooLarge' }" "{ kind: 'failed' }" \
    'tooLarge 를 failed 로 접음' \
    "$VT src/entities/run-log/api src/pages/admin-runs" \
    '409 RUN_LOG_EXPORT_TOO_LARGE → tooLarge
409 상한 넘음 → 그 글(alert)'
  code_break P11 "$SRV" 'async exportFile' "answer.response.headers.get('Content-Disposition')," 'null,' \
    '이름을 늘 대체 이름' \
    "$VT src/entities/run-log/api; $E2E e2e/admin.spec.ts -g '엑셀 내보내기'" \
    '경로 정확히, 쿼리는 넘긴 그대로
suggestedFilename'
  code_break P12 "$SCREEN" 'const exportRuns' 'save(outcome.blob, outcome.fileName)' 'save(new Blob([]), outcome.fileName)' \
    'save 에 빈 Blob' \
    "$VT src/pages/admin-runs" \
    'save(흉내 몸 Blob, 해독한 이름)'
  code_break P13 "$SRV" 'async exportFile' "parseAs: 'blob'," '' \
    "parseAs: 'blob' 지움" \
    "$VT src/entities/run-log/api" \
    'Blob 바이트 = 흉내 몸'
fi

if [ "$COMMIT" = 3 ]; then
  echo "▶ ③ AD-05 (P14~P17)"
  code_break P14 "$AUDIT/model/audit.ts" 'function settingTarget' 'Object.hasOwn(words.modules, row.module) ?' 'false ?' \
    'module 을 이름표에서 안 찾음' \
    "$VT src/entities/audit-log/model" \
    '만듦: 「AI 설정」 링크(version v3)'
  code_break P15 "$AUDIT/model/audit.ts" 'function settingTarget' 'row.targetId !== null && label !== null' 'label !== null' \
    'id null 적용에도 version = label' \
    "$VT src/entities/audit-log/model" \
    '적용인데 targetId null 이면'
  code_break P16 "$ROUTES" 'function auditTarget' "link.kind === 'accounts' ?" 'true ?' \
    'AuditRoute 가 kind 를 안 보고 accounts' \
    "$VT src/app/admin/router.test.tsx" \
    'AI 설정 줄(밴드 AD4X ③)'
  code_break P17 "$AUDIT/api/server.ts" 'function isRow' "nullable(row.module, 'string')" 'true' \
    'audit isRow 의 module 검사 지움' \
    "$VT src/entities/audit-log/api" \
    'module 이 수'
fi

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
