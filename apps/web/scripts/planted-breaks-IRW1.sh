#!/usr/bin/env bash
# 밴드 IRW1 의 심은 파손(발주서 §3-4).   사용: apps/web/scripts/planted-breaks-IRW1.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P17(발주서 표) · R1~R3(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2a.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 경계마다 돈다: 대상 파일이 아직 없는 파손(뒤 경계 몫)은 「뒤 경계」로 적고 셈에 넣지 않는다. 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export -n OPENAI_API_KEY ANTHROPIC_API_KEY 2>/dev/null; unset OPENAI_API_KEY ANTHROPIC_API_KEY

W=apps/web
S=$W/src
E=$S/entities/materiality
SV=$E/api/server.ts
CR=$E/api/contract/result.ts
ST=$E/model/steps.ts
RS=$E/model/result.ts
WN=$E/model/warnings.ts
SE=$S/entities/session/model/session.ts
MENU=$S/app/shell/moduleMenu.tsx
STS=$S/pages/materiality-status/ui/StatusScreen.tsx
RES=$S/pages/materiality-result/ui/ResultScreen.tsx
LST=$S/pages/materiality-list/ui/ListScreen.tsx
IRR=$S/app/materiality/MaterialityRoutes.tsx
E2E=$W/e2e/materiality-server.spec.ts
TOUCHED=()
for file in "$SV" "$CR" "$ST" "$RS" "$WN" "$SE" "$MENU" "$STS" "$RES" "$LST" "$IRR"; do
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
later=0
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
  if [ ! -f "$file" ]; then later=$((later + 1)); echo "  $n  뒤 경계  $6 ($file 없음)"; return; fi
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
PW="WEB_TEST_PORT=${WEB_TEST_PORT:-23415} pnpm --filter @esg/web exec playwright test e2e/materiality-server.spec.ts"
D=src/entities/materiality
API=$D/api/server.test.ts
CON=$D/api/contract/contract.test.ts
HOOKS=$D/hooks/hooks.test.tsx
MODEL=$D/model
STATUS=src/pages/materiality-status
RESULT=src/pages/materiality-result
LIST=src/pages/materiality-list
ROUTES=src/app/materiality
# e2e 는 ③ 에서 붙는다(없으면 vitest 만).
# 단위 시험이 먼저 빨개져도 e2e 는 돈다(둘 다 이름 무늬를 대야 하므로 — 하나라도 빨개지면 EXIT 1).
e2e() { [ -f "$E2E" ] && echo '; r=$?; '"$PW"' || r=1; (exit $r)' || echo ""; }
e2e_name() { [ -f "$E2E" ] && echo "materiality-server.spec.ts" || echo ""; }

echo "▶ 발주서 표 (P1~P17)"
code_break P1 "$CR" "const impactRow = obj(" "const impactRow = obj(" "const impactRow = z.object(" \
  "거울 .strict() 하나 뺌(2-1 줄이 모르는 칸을 받음)" \
  "$VT $CON" \
  "안쪽 모르는 칸은 거절"
code_break P2 "$SV" "body: { module: MODULE, launchKey, options }," "body: { module: MODULE, launchKey, options }," "body: { module: MODULE, launchKey, options, resumeFromRunId: id }," \
  "rerun 이 resumeFromRunId 를 실음" \
  "$VT $API$(e2e)" \
  "본문 열쇠는 module·launchKey·options 셋뿐
$(e2e_name)"
code_break P3 "$SV" "if (pending === null || pending.source !== id" "if (pending === null || pending.source !== id" "if (true || pending.source !== id" \
  "실패 뒤 다시 누름이 새 열쇠" \
  "$VT $API" \
  "열쇠: 실패(거절·끊김) 뒤 같은 실행은 같은 열쇠"
code_break P4 "$SV" "listener(run);" "if (run.status === 'queued' || run.status === 'processing')" "if (run.status !== 'failed')" \
  "done 뒤에도 폴링" \
  "$VT $API $HOOKS" \
  "done 에서 멈춤"
code_break P5 "$ST" "line: 'controversy'," "steps: ['keywords', 'controversy', 'report', 'part2_seed']," "steps: ['keywords', 'controversy', 'part2_seed']," \
  "1부 report 를 줄 6 으로(줄 2 에서 뺌 — 그 단계는 모르는 이름이 됨)" \
  "$VT $MODEL/steps.test.ts $STATUS" \
  "report 는 줄 2
$( [ -f "$STS" ] && echo 'StatusScreen' )"
code_break P6 "$RS" "export const pathwayUndecided" "sub.financial.status !== 'done' || sub.pathway.status === 'failed';" "sub.financial.status !== 'done' || sub.pathway.status !== 'done';" \
  "pathway not_run 을 정하지 못함으로" \
  "$VT $MODEL/result.test.ts" \
  "재무 done·0 줄의 pathway not_run 은 정함"
code_break P7 "$RS" "const financial = topic.subtopics.flatMap" "rowsOf(sub.financial)" "rowsOf(sub.pathway)" \
  "1-1 재무 쪽 = pathway rows" \
  "$VT $MODEL/result.test.ts" \
  "재무 rows(pathway 아님)"
code_break P8 "$RS" "export function mergedItems" "item.url.trim() : null;" "item.url : null;" \
  "url 앞뒤 공백 안 뗌" \
  "$VT $MODEL/result.test.ts" \
  "url 같으면(공백 뗌)"
code_break P9 "$WN" "const count =" "BY_ROW.has(line) ?" "true ?" \
  "경고를 토픽마다 한 줄로 셈(줄 수)" \
  "$VT $MODEL/warnings.test.ts" \
  "같은 code 는 한 줄
같은 토픽의 phase 둘은 하나"
code_break P10 "$CR" "warnings: value.warnings.map" "({ code: w.code, topic: w.topic })" "({ code: w.code, topic: w.topic, message: w.message })" \
  "경고에 서버 message 를 실음" \
  "$VT $CON" \
  "서버 message 는 화면 꼴에 싣지 않는다"
code_break P11 "$RES" "const SAFE_URL" "/^https?:\/\//" "/./" \
  "^https?:// 검사 뺌" \
  "$VT $RESULT" \
  "javascript: 링크 0"
code_break P12 "$RES" "const undecidedRows =" "kind === 'all'" "kind !== 'none'" \
  "정하지 못함 줄이 긍정 탭에도" \
  "$VT $RESULT" \
  "정하지 못함 줄은 「전체」 끝에만"
code_break P13 "$RES" "const researchReady =" "readyRun.files.includes(RESEARCH_FILE_NAME)" "readyRun.files.length > 0" \
  "리서치 엑셀 파일이 없어도 [리서치 엑셀 내려받기]를 그림(개정 2 — MARC-ENT-449, 옛 「websearch 단추 그림」 자리)" \
  "$VT $RESULT" \
  "리서치 엑셀(1-1 탭 머리)"
code_break R4 "$RES" "const reportReady =" "readyRun.files.includes(REPORT_FILE_NAME)" "readyRun.files.length > 0" \
  "최종 엑셀이 없어도 [엑셀 내려받기]를 그림(websearch 만 있는 실행)" \
  "$VT $RESULT" \
  "websearch 만 있으면 단추 0"
code_break P14 "$SE" "const own: readonly SessionArea[]" ": ['greenwash', 'translation', 'dataverify', 'materiality'];" ": ['greenwash', 'translation', 'dataverify'];" \
  "own(고객사 사용자)에서 materiality 뺌" \
  "$VT src/entities/session $( [ -f "$IRR" ] && echo $ROUTES )" \
  "service·admin: /materiality/** stay
$( [ -f "$IRR" ] && echo 'service: /materiality/runs/7' )"
code_break P15 "$LST" "const onRowClick" "else onViewStatus(id);" "else act(row);" \
  "failed 줄 누름이 rerun(새 실행·비용)" \
  "$VT $LIST$(e2e)" \
  "failed → 그 실행의 IR-03
$(e2e_name)"
code_break P16 "$LST" "const filtered =" "tab !== 'all' || mineOnly" "true" \
  "빈 목록이 IR-01 빈 꼴이 아님(거른 빔 꼴로)" \
  "$VT $LIST$(e2e)" \
  "빈 목록 → IR-01 빈 꼴
$(e2e_name)"
if grep -qF "['materiality', ChartSquareIcon, false]" "$MENU"; then
code_break P17 "$MENU" "const ITEMS" "['materiality', ChartSquareIcon, false]" "['materiality', ChartSquareIcon, true]" \
  "메뉴 「중대성평가」 끔" \
  "$VT src/app/shell $ROUTES$(e2e)" \
  "켬 넷·끔 둘
$(e2e_name)"
else later=$((later + 1)); echo "  P17  뒤 경계  메뉴 「중대성평가」 끔 (H4 — ③ 에서 켬)"; fi

echo
echo "▶ 러너 몫 (R1 ① · R2·R4 ② · R3 ③)"
code_break R1 "$SV" "function kindOf" "if (failure.code === 'RUN_NOT_DONE') return 'not_done';" "if (failure.code === 'RUN_NOT_DONE') return 'not_found';" \
  "결과 409 RUN_NOT_DONE 을 not_found 로(끝나지 않음과 없음이 섞임 — IR-04 가 IR-03 으로 가지 않음)" \
  "$VT $API $HOOKS" \
  "404 not_found · 409(진행·실패) not_done
ready · not_done · missing"
code_break R2 "$IRR" "followSessionEnd(context.session" "() => made.store.forget()" "() => {}" \
  "세션 끝에 저장소가 쥔 열쇠를 버리지 않음" \
  "$VT $ROUTES" \
  "forget"
code_break R3 "$LST" "const { status, retry } = useRuns" "mine: mineOnly," "mine: false," \
  "「내가 돌린 것만」이 mine 을 싣지 않음" \
  "$VT $LIST" \
  "「내가 돌린 것만」 → mine=true"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "LATER=$later"
echo "PLANTED=$passed/$total"
