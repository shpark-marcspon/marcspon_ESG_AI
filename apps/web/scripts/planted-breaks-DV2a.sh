#!/usr/bin/env bash
# 밴드 DV2a 의 심은 파손(발주서 §3-4).   사용: apps/web/scripts/planted-breaks-DV2a.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P16(발주서 표) · R1~R3(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-TRW1a.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 경계마다 돈다: 대상 파일이 아직 없는 파손(뒤 경계 몫)은 「뒤 경계」로 적고 셈에 넣지 않는다. 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
E=$S/entities/dataverify
SV=$E/api/server.ts
OP=$E/model/options.ts
EDK=$E/model/edk.ts
CK=$E/model/checks.ts
SE=$S/entities/session/model/session.ts
MENU=$S/app/shell/moduleMenu.tsx
GWR=$S/app/greenwash/GreenwashRoutes.tsx
NEWS=$S/pages/dataverify-new/ui/NewScreen.tsx
RES=$S/pages/dataverify-result/ui/ResultScreen.tsx
E2E=$W/e2e/dataverify-server.ts
DVR=$S/app/dataverify/DataverifyRoutes.tsx
TOUCHED=()
for file in "$SV" "$OP" "$EDK" "$CK" "$SE" "$MENU" "$GWR" "$NEWS" "$RES" "$E2E" "$DVR"; do
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
L=src/app/guards/layers.test.ts
D=src/entities/dataverify
API=$D/api/server.test.ts
OPT=$D/model/options.test.ts
CHK=$D/model/checks.test.ts
HOOKS=$D/hooks/hooks.test.tsx

echo "▶ 발주서 표 (P1~P16)"
code_break P1 "$OP" "export const pyJsonOctets" "encode(pyJson(value))" "encode(JSON.stringify(value))" \
  "pyJsonOctets → JSON.stringify 길이" \
  "$VT $OPT $API" \
  "★A: 파이썬이 잰 바이트와 같고
JSON.stringify 로는 상한 안이어도"
code_break P2 "$OP" "export const isTooLarge" "pyJsonOctets(options) > OPTIONS_MAX_OCTETS" "pyJsonOctets(options) >= OPTIONS_MAX_OCTETS" \
  "상한 > → >=" \
  "$VT $OPT $API" \
  "상한은 「>」
옵션 셈 = 상한이면 보내고"
code_break P3 "$SV" "async function postRun" "params: { header: { 'Idempotency-Key': key } }," "params: {}," \
  "Idempotency-Key 빠짐" \
  "$VT $API" \
  "Idempotency-Key 소문자 UUID
열쇠: 실패 뒤 같은 본문은 같은 열쇠"
code_break P4 "$OP" "export const buildOptions" "({ input })" "({ input, source: 'file' })" \
  "options 에 source" \
  "$VT $OPT $API" \
  "options 열쇠는 input 하나
본문 열쇠는 module·options"
code_break P5 "$SV" "failure.code === 'INVALID_OPTIONS'" "return isTooLarge(options) ?" "return true ?" \
  "400 INVALID_OPTIONS 늘 크기 글(too_large)" \
  "$VT $API" \
  "400 INVALID_OPTIONS: 다시 재서"
code_break P6 "$EDK" "function isEdkItem" "if (!(key in value)) return false;" "if (!(key in value)) continue;" \
  "열쇠 빠진 항목 받음" \
  "$VT $D/model/edk.test.ts" \
  "항목 열쇠가 하나라도 빠지면 shape"
code_break P7 "$SV" "listener(run);" "if (run.status === 'queued' || run.status === 'processing')" "if (run.status !== 'failed')" \
  "done 뒤에도 폴링" \
  "$VT $API $HOOKS" \
  "계속 → done 에서 멈춤
done 에서 멈춤"
code_break P8 "$CK" "summary.uncomputable =" "summary.nonNumeric + summary.divisionByZero + summary.toolErrors;" "summary.nonNumeric + summary.divisionByZero;" \
  "계산 못 함에서 도구 오류(error) 뺌" \
  "$VT $CHK" \
  "판 DV-04 수"
code_break P9 "$CK" "verdict: verdictOf" "diff: year.diff," "diff: year.diff ?? '0'," \
  "차이 null → 0" \
  "$VT $CHK" \
  "줄의 해: 판정·차이"
code_break P10 "$SE" "const own: readonly SessionArea[]" ": ['greenwash', 'translation', 'dataverify'];" ": ['greenwash', 'translation'];" \
  "own(고객사 사용자)에서 dataverify 뺌" \
  "$VT src/entities/session" \
  "service·admin: /dataverify/** stay"
code_break P11 "$MENU" "const ITEMS" "['validation', FileCheckIcon, false]" "['validation', FileCheckIcon, true]" \
  "메뉴 「데이터 검증」 끔" \
  "$VT src/app/shell src/app/dataverify" \
  "켬 셋·끔 셋"
if [ -f "$MENU" ]; then
code_break P12 "$GWR" "const MENU =" "const MENU = moduleMenu(shell.menu);" "const MENU: AppShellMenuItem[] = [...moduleMenu(shell.menu)];" \
  "GreenwashRoutes 에 MENU 사본 되살림" \
  "$VT $L" \
  "MENU 사본"
else later=$((later + 1)); echo "  P12  뒤 경계  GreenwashRoutes 에 MENU 사본 되살림 ($MENU 없음)"; fi
code_break P13 "$NEWS" "const ready =" "data !== null && !tooLarge;" "data !== null;" \
  "끔 상태(options 서버 셈 넘음)의 [검증 시작]이 켜짐" \
  "$VT src/pages/dataverify-new" \
  "끔(요청 0)"
code_break P14 "$SV" "async function postRun" "body: { module: MODULE, options }," "body: { module: MODULE, options, resumeFromRunId: 1 }," \
  "POST /runs 에 resumeFromRunId(다시 실행이 이어 돌기)" \
  "$VT $API" \
  "rerun: 받은 options 그대로"
code_break P15 "$RES" "rowsParsed === 'unparsed'" "rowsParsed === 'unparsed'" "rowsParsed === 'unparsed' && false" \
  "unparsed 에 빈 표" \
  "$VT src/pages/dataverify-result" \
  "unparsed"
if [ -f "$E2E" ]; then
code_break P16 "$SV" "if (pending?.key === key) pending = null;" "if (pending?.key === key) pending = null;" "void 0;" \
  "e2e: 성공 뒤 새 검증의 누름이 앞 Idempotency-Key 를 다시 씀(빌드한 웹 — 흉내 서버가 열쇠를 적는다)" \
  "WEB_TEST_PORT=${WEB_TEST_PORT:-22525} pnpm --filter @esg/web exec playwright test e2e/dataverify-server.spec.ts" \
  "dataverify-server.spec.ts"
else later=$((later + 1)); echo "  P16  뒤 경계  e2e 성공 뒤 열쇠 다시 씀 ($E2E 없음)"; fi

echo
echo "▶ 러너 몫 (R1 ① · R2 ② · R3 ③)"
code_break R1 "$SV" "function kindOf" "if (failure.code === 'RUN_NOT_DONE') return 'not_done';" "if (failure.code === 'RUN_NOT_DONE') return 'not_found';" \
  "결과 409 RUN_NOT_DONE 을 not_found 로(끝나지 않음과 없음이 섞임)" \
  "$VT $API $HOOKS" \
  "queued·failed → not_done
끝나지 않음 → not_done"

code_break R2 "$DVR" "followSessionEnd(context.session" "() => made.store.forget()" "() => {}" \
  "세션 끝에 저장소가 쥔 열쇠를 버리지 않음(다른 사람이 같은 탭에서 앞 열쇠를 다시 씀)" \
  "$VT src/app/dataverify" \
  "틀의 [로그아웃]은 저장소의 forget 을 부른다"

code_break R3 "$NEWS" "const start = () =>" "if (problems.length > 0) {" "if (problems.length < 0) {" \
  "기업 칸이 틀려도 [검증 시작]이 보냄(2e ⑤ — 누르면 칸 글·첫 오류 칸 초점·요청 0)" \
  "$VT src/pages/dataverify-new" \
  "빈 칸은 [검증 시작]을 누르면 글 셋"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "LATER=$later"
echo "PLANTED=$passed/$total"
