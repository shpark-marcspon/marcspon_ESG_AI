#!/usr/bin/env bash
# 밴드 DVX1 ② 의 심은 파손 — 웹 몫(발주서 band-handoffs/DVX1-order.md §3 P10~P13 + 러너 몫 R1·R2).   사용: apps/web/scripts/planted-breaks-DVX1.sh
# 서버 몫(P1~P9·P14~P16·PR1~PR3)은 apps/api-py/scripts/planted-breaks-DVX1.sh. 파손을 하나씩 심고, 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV5.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL·FAILED)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
FORM=$S/pages/dataverify-new/model/form.ts
NEW=$S/pages/dataverify-new/ui/NewScreen.tsx
TOUCHED=("$FORM" "$NEW")

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

# <번> <파일> <바뀔 줄 수> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔)> -- (<머리> <옛> <새>)…
code_break() {
  local n="$1" file="$2" want="$3" say="$4" cmd="$5" patterns="$6"
  shift 6
  restore
  while [ $# -ge 3 ]; do
    if ! plant "$file" "$1" "$2" "$3"; then report "$n" fail "심지 못했다: $say"; restore; return; fi
    shift 3
  done
  if [ "$(changed_lines "$file")" != "$want" ]; then report "$n" fail "바뀐 줄이 $want 이 아니다: $say"; restore; return; fi
  bash -c "$cmd" > "$OUT" 2>&1
  local code=$? missing=0 pattern red_lines
  red_lines="$(grep -E '^ *(×|✘|FAIL|FAILED) ' "$OUT")"
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" <<< "$red_lines" || { missing=$((missing + 1)); echo "       실패 줄에 없다: $pattern"; }
  done <<< "$patterns"
  local red
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-70 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$say — EXIT=$code · $red"; else report "$n" fail "$say — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
TESTS="src/pages/dataverify-new"

echo "▶ 발주서 표 (P10~P13)"
code_break P10 "$FORM" 1 "엑셀 답을 readData 를 거치지 않고 바로 ok(판별·256KiB 셈·미리 읽기 셈 빠짐)" "$VT $TESTS" \
  "바꾼 data 가 256KiB 를 넘으면
.xlsx 는 맨 바이트로 서버 읽기 한 번" \
  "export function readXlsxAnswer" "const read = readData(JSON.stringify(answer.data));" \
  "const read = { kind: 'ok', data: answer.data, preview: { themes: 0, items: 0, envItems: 0, envKeyItems: 0, years: [] } } as DataRead;"
code_break P11 "$NEW" 1 "보고연도를 고른 칸도 엑셀 연도로 덮음" "$VT $TESTS" \
  "먼저 고른 보고연도는 그대로" \
  "function fillEmpty(" "    yearOpen &&" "    true &&"
code_break P12 "$NEW" 1 ".json 256KiB 앞 검사 뺌(1MiB 안이면 읽음)" "$VT $TESTS" \
  "256KiB 넘고 1MiB 안의 .json 은 읽지 않고" \
  "const readFile = " "if (file.size > OPTIONS_MAX_OCTETS) {" "if (false) {"
code_break P13 "$NEW" 2 "서버 message 를 화면에(거절 갈래 = 서버 글)" "$VT $TESTS" \
  "거절 kind 마다 그 글" \
  "const readFile = " "(answer) => done(readXlsxAnswer(answer))," \
  "(answer) => done(answer.ok ? readXlsxAnswer(answer) : { kind: 'xlsx_rejected', reason: answer.message as EdkReadKind, row: null })," \
  "function xlsxError(" "return xlsx[kind];" "return xlsx[kind] ?? kind;"

echo
echo "▶ 러너 몫 (R1·R2)"
code_break R1 "$NEW" 1 "확장자를 대소문자 그대로 가름(.XLSX 가 JSON 길로)" "$VT $TESTS" \
  "확장자는 대소문자 없이 가른다" \
  "const isXlsx = " "name.toLowerCase().endsWith('.xlsx')" "name.endsWith('.xlsx')"
code_break R2 "$NEW" 1 "양식 내려받기에 화면 보고연도를 싣지 않음" "$VT $TESTS" \
  "[엑셀 양식 내려받기]는 화면 보고연도로" \
  "<DownloadButton" "store.downloadEdkTemplate(company.reportingYear)" "store.downloadEdkTemplate()"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
