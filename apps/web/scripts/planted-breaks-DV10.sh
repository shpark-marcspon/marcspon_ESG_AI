#!/usr/bin/env bash
# 밴드 DV10 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-DV10.sh
# 파손을 하나씩 심고, 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P4(발주서 §3 표) · R1~R3(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2c.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
TEXT=$S/entities/dataverify/config/text.ts
CHECKS=$S/entities/dataverify/model/checks.ts
RSCR=$S/pages/dataverify-result/ui/ResultScreen.tsx
TOUCHED=("$TEXT" "$CHECKS" "$RSCR")

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
code_break P1 "$RSCR" 1 "검토 글을 다시 맨 글자(<p>)로" "$VT $RESULT" \
  "예시: 머리
검토 글: heading·strong·list·table 요소" \
  'data-testid="review-text"' '<MarkdownText data-testid="review-text">{review.report}</MarkdownText>' '<p data-testid="review-text">{review.report}</p>'
code_break P2 "$RSCR" 1 "차이 단위 뺌(대상 단위를 넘기지 않음)" "$VT $RESULT" \
  "펼침: [보기] → 이름 단 줄 다섯" \
  "if (ex.kind === 'sum')" "line.items.rule === 'sum' ? line.items.unit : null," "null,"
code_break P3 "$TEXT" 1 "비율에도 단위 붙임" "$VT $CONF" \
  "값을 끼운다" \
  "diffValue: (" '`${diff}%p · 허용 오차' '`${diff}%p${unit ? ` ${unit}` : ""} · 허용 오차'
code_break P4 "$RSCR" 3 "출처를 다시 <a> 로(칩 아님)" "$VT $RESULT" \
  "제목 있음 → 칩 이름 = 제목
제목 없음 → 칩이 주소에서 이름을 짓는다" \
  "function SourceLine(" "<LinkChip" '<a target="_blank" rel="noopener noreferrer" href={webLink(source.url) ?? undefined}' \
  "function SourceLine(" "label={source.title ?? undefined}" ">{source.title ?? source.url}" \
  "function SourceLine(" "/>" "</a>"

echo
echo "▶ 러너 몫 (R1~R3)"
code_break R1 "$RSCR" 1 "출처 주소를 webLink 없이 칩에(utm_source=openai 가 href 에 남음)" "$VT $RESULT" \
  "utm_source=openai 는 href·title 모두에서 뗌" \
  "function SourceLine(" "url={webLink(source.url) ?? source.url}" "url={source.url}"
code_break R2 "$RSCR" 1 "리스크 원문(Raw)을 다시 맨 글자로" "$VT $RESULT" \
  "리스크 unparsed 원문·실패 일부 원문도 같은 부품
리스크: unparsed 원문" \
  "function Raw(" '<MarkdownText data-testid="raw">{children}</MarkdownText>' '<p data-testid="raw">{children}</p>'
code_break R3 "$CHECKS" 1 "단위 칸 trim·빈 칸 거름 뺌" "$VT $MODEL" \
  "대상 단위(밴드 DV10)" \
  "function unitOf(" "return trimmed === '' ? null : trimmed;" "return unit;"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
