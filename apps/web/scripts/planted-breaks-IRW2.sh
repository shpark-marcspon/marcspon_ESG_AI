#!/usr/bin/env bash
# 밴드 IRW2 웹 몫의 심은 파손(발주서 §3 — planted-breaks-IRW1.sh 꼴).   사용: apps/web/scripts/planted-breaks-IRW2.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P6~P12(발주서 표 — ②) · P13~P16(③) · R1~R3(러너 몫 ②) · R4~R7(러너 몫 ③).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed. 대상 파일·글자가 아직 없는 파손(뒤 경계 몫)은 「뒤 경계」로 적고 셈에 넣지 않는다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export -n OPENAI_API_KEY ANTHROPIC_API_KEY 2>/dev/null; unset OPENAI_API_KEY ANTHROPIC_API_KEY

W=apps/web
S=$W/src
E=$S/entities/materiality
SV=$E/api/server.ts
VCM=$E/model/valueChain.ts
INP=$E/model/input.ts
NEW=$S/pages/materiality-new/ui/NewScreen.tsx
VCF=$S/pages/materiality-new/ui/ValueChainField.tsx
LST=$S/pages/materiality-list/ui/ListScreen.tsx
RES=$S/pages/materiality-result/ui/ResultScreen.tsx
E2E=$W/e2e/materiality-server.spec.ts
TOUCHED=()
for file in "$SV" "$VCM" "$INP" "$NEW" "$VCF" "$LST" "$RES"; do
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
PW="WEB_TEST_PORT=${WEB_TEST_PORT:-23275} pnpm --filter @esg/web exec playwright test e2e/materiality-server.spec.ts"
D=src/entities/materiality
MODEL=$D/model
API=$D/api/newRun.test.ts
NEWT=src/pages/materiality-new
# e2e 는 ③ 에서 붙는다(파일이 IRW2 시험을 품을 때만).
e2e() { grep -qF 'IRW2' "$E2E" 2>/dev/null && echo '; r=$?; '"$PW"' || r=1; (exit $r)' || echo ""; }
e2e_name() { grep -qF 'IRW2' "$E2E" 2>/dev/null && echo "materiality-server.spec.ts" || echo ""; }

echo "▶ 발주서 표 (P6~P12 — ②)"
code_break P6 "$VCM" "export function rowsFromPaste" "lines.shift();" "void 0;" \
  "붙여 넣기 열 이름 줄을 행으로" \
  "$VT $MODEL $NEWT$(e2e)" \
  "첫 줄이 열 이름 다섯이면 뗀다
열 이름 줄 뗌
$(e2e_name)"
code_break P7 "$VCM" "export function rowsFromPaste" "value_chain_stage: normalizeStage(texts[2]!) ?? ''," "value_chain_stage: (normalizeStage(texts[2]!) ?? texts[2]!) as '',"  \
  "밸류체인 모름을 그대로 보냄(붙여 넣기)" \
  "$VT $MODEL $NEWT$(e2e)" \
  "못 맞춘 밸류체인은 행을 넣고 그 칸만 비운다
밸류체인 빈 행 여럿
$(e2e_name)"
code_break P8 "$INP" "draft.valueChain.length === 0" "null" "[]" \
  "0행에 valueChain: []" \
  "$VT $MODEL" \
  "가치사슬: 0행 → null"
code_break P9 "$INP" "dateRange:" "}~\${UNTIL_TODAY}" "} ~ \${UNTIL_TODAY}" \
  "dateRange 에 공백" \
  "$VT $MODEL $NEWT" \
  "리서치 조건
통과 → POST /runs 한 번"
code_break P10 "$NEW" "const target = found" "if (target) setFocusTo" "if (false) setFocusTo" \
  "첫 오류 칸 초점 뺌" \
  "$VT $NEWT" \
  "빈 폼 → 칸마다 글
시작일: 오늘"
code_break P11 "$VCF" "if (!read.ok) {" "fail(first.name, rejectedError(read));" "fail(first.name, read.message);" \
  "서버 message 를 화면에" \
  "$VT $NEWT" \
  "서버 거절 kind"
code_break P12 "$SV" "async createRun(input)" "if (pendingNew === null || pendingNew.body !== body)" "if (true || pendingNew.body !== body)" \
  "실패 뒤 다시 누름 새 열쇠" \
  "$VT $API $NEWT" \
  "실패 뒤 같은 입력이면 같은 두 열쇠
다시 누르면 같은 열쇠"

echo
echo "▶ 발주서 표 (P13~P16 — ③)"
LISTT=src/pages/materiality-list
RESULTT=src/pages/materiality-result
ROUTET=src/app/materiality
code_break P13 "$LST" "const changeTab = " "setRerunFailed(false);" "void 0;" \
  "m4 되돌림(탭을 바꿔도 다시 실행 실패 글이 남음)" \
  "$VT $LISTT" \
  "m4 다시 실행 실패 글은 상태 탭"
code_break P14 "$RES" "function readableUrl" "return shown.replace(BIDI_CONTROLS, '');" "return shown;" \
  "J1 방향 제어 문자 걷기 뺌" \
  "$VT $RESULTT" \
  "J1 보이는 주소에서 방향 제어 문자를 걷는다"
code_break P15 "$RES" "{sub !== null && (" "text-style-pre-caption-03" "text-style-pre-caption-02" \
  "N1 숫자 카드 sub 굵기 되돌림" \
  "$VT $RESULTT" \
  "N1 숫자 카드 sub"
code_break P16 "$LST" "if (nothingYet && intro" "nothingYet && intro !== undefined" "false" \
  "Q9 빈 목록이 IR-01 빈 꼴" \
  "$VT $LISTT $ROUTET$(e2e)" \
  "Q9 거름 없는 첫 쪽 0건 → intro
빈 목록 → /materiality 그대로 IR-00 몸
$(e2e_name)"

echo
echo "▶ 러너 몫 (R4~R7 ③)"
code_break R4 "$LST" "const head = " "start === '' ? '~' : \`\${start} ~\`" "\`\${start} ~\`" \
  "W8 「~끝」 원문의 앞 빈칸" \
  "$VT $LISTT" \
  "W8 원문이 「~끝」 꼴이면 앞 빈칸 0"
code_break R5 "$LST" "const BADGE_WRAP" "'h-auto w-auto whitespace-normal py-0.5'" "''" \
  "N2 상태 배지 줄바꿈 뺌" \
  "$VT $LISTT" \
  "N2(Q10) 산업 머리 168"
code_break R6 "$RES" "data-card=\"report\"" "{runFailed ?" "{false ?" \
  "m3 실행 못 읽음에도 단추 자리 비움" \
  "$VT $RESULTT" \
  "m3 실행이 불러오지 못함(500)
m3 실행이 없음(404)"

code_break R7 "$LST" "data-testid=\"period\"" "whitespace-normal tabular-nums" "whitespace-nowrap tabular-nums" \
  "N2 리서치 기간 한 줄로(1440 카드 안 가로 스크롤 — 검증 3 B1)" \
  "$VT $LISTT$(e2e)" \
  "N2(Q10) 산업 머리 168
$(e2e_name)"

echo
echo "▶ 러너 몫 (R1~R3 ②)"
code_break R1 "$VCM" "let [unit, description]" "if (above && unit === '') {" "if (above) {" \
  "(나) 어김 — 사업 부문이 있어도 위 행을 물려받음" \
  "$VT $MODEL" \
  "사업 부문이 빈 행만 위 데이터 행에서 물려받는다"
code_break R2 "$VCF" "const RULE" "maxMb: 1," "maxMb: 100," \
  "1MB 판정 뺌(큰 파일을 서버로 보냄)" \
  "$VT $NEWT" \
  "판정 밖: 1MB 넘음"
code_break R3 "$VCF" "const put = " "setAlert(stagelessRows(next).length > 0);" "setAlert(false);" \
  "넣자마자 밸류체인 빈 칸을 보이지 않음" \
  "$VT $NEWT" \
  "ok → 표"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "LATER=$later"
echo "PLANTED=$passed/$total"
