#!/usr/bin/env bash
# 밴드 DV6 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-DV6.sh
# 파손을 하나씩 심고, 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P4(발주서 표) · R1(러너 몫) · R2(검증 B1 짝).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2c.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
TEXT=$S/entities/dataverify/config/text.ts
EXPL=$S/entities/dataverify/model/explain.ts
RSCR=$S/pages/dataverify-result/ui/ResultScreen.tsx
TOUCHED=("$TEXT" "$EXPL" "$RSCR")

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
  red_lines="$(grep -E '^ *(×|✘|FAIL) ' "$OUT")"
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
RESULT=src/pages/dataverify-result
MODEL=src/entities/dataverify/model
CONF=src/entities/dataverify/config

echo "▶ 발주서 표 (P1~P4)"
code_break P1 "$EXPL" 1 "실제값(더한 값의 합)을 Number 덧셈으로" "$VT $MODEL $RESULT" \
  "0.1 + 0.2 = 0.3 정확히
펼침: [보기] → 이름 단 줄 다섯" \
  "export function decimalSum(" "string | null {" "string | null { return String(addends.reduce((a, t) => a + Number(t), 0));"
code_break P2 "$TEXT" 1 "partialTag 를 옛 글 「최대 횟수에 닿음」으로" "$VT $CONF $RESULT" \
  "「최대 횟수」「정해진 횟수」 0 — 글과 글을 짓는 함수의 몸 모두
「최대 횟수」「정해진 횟수」 0 — 펼침·띠·단계 줄 모두" \
  "partialTag:" "'다 마치기 전에 멈춤'" "'최대 횟수에 닿음'"
code_break P3 "$TEXT" 1 "doneLine 검산 셈을 「회」로" "$VT $CONF" \
  "값을 끼운다" \
  "doneLine: (" "검산 \${counts.checks}건" "검산 \${counts.checks}회"
code_break P4 "$RSCR" 1 "펼침에서 판정 줄 뺌(합계)" "$VT $RESULT" \
  "펼침: [보기] → 이름 단 줄 다섯" \
  "if (ex.kind === 'sum')" "      verdict," ""

echo
echo "▶ 러너 몫 (R1 · R2)"
code_break R1 "$RSCR" 1 "계산 못 함 실제값 뒤 이유(notes) 뺌" "$VT $RESULT" \
  "펼침: [보기] → 이름 단 줄 다섯" \
  "const reason =" '`${dash} · ${reason}`' "dash"

code_break R2 "$RSCR" 2 "비율 펼침의 입력값(적힌 %)↔실제값(계산한 %) 맞바꿈 — 검증 B1" "$VT $RESULT" \
  "펼침(비율): 입력값 = 적힌 % · 실제값 = 계산한 %" \
  "if (ex.kind === 'ratio')" "input(rows.percent(ex.expected))" "input(rows.percent(ex.percent))" \
  "if (ex.kind === 'ratio')" "actual(rows.percent(ex.percent))" "actual(rows.percent(ex.expected))"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
