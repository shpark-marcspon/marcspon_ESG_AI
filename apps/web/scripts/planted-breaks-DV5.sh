#!/usr/bin/env bash
# 밴드 DV5 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-DV5.sh
# 파손을 하나씩 심고, 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P4(발주서 표) · R1(러너 몫) · X1(검증자 B1 — 토픽 빈 목록).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2d.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL·FAILED)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
EDK=$S/entities/dataverify/model/edk.ts
NEW=$S/pages/dataverify-new/ui/NewScreen.tsx
TOUCHED=("$EDK" "$NEW")

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
TESTS="src/entities/dataverify/model/edk.test.ts src/pages/dataverify-new"

echo "▶ 발주서 표 (P1~P4)"
code_break P1 "$EDK" 1 "서버 입력 꼴 판별 뺌(맨 위 data 를 보지 않음)" "$VT $TESTS" \
  "data 를 데이터만 든 꼴과 같게 읽고 company 칸 넷을 싣는다
파일 → 거절 0" \
  "export function readEdk(" "if (isObject(value) && value.schemaVersion === INPUT_SHAPE) {" "if (false) {"
code_break P2 "$NEW" 1 "빈 칸 아닌 기업명도 덮음" "$VT $TESTS" \
  "먼저 쓴 기업명은 그대로" \
  "function fillEmpty(" "prev.name.trim() === ''" "true"
code_break P3 "$EDK" 1 "company 보고연도 칸 판별 뺌(꼴 밖도 씀)" "$VT $TESTS" \
  "company 칸 하나가 꼴 밖이면 그 칸만 빠진다" \
  "function companyFrom(" "typeof year === 'string' && YEAR.test(year)" "year !== undefined"
code_break P4 "$EDK" 1 "schemaVersion 값 확인 뺌(열쇠만 있으면 서버 입력 꼴)" "$VT $TESTS" \
  "schemaVersion 이 다른 값이면 shape
꼴이 틀린 입력" \
  "export function readEdk(" "value.schemaVersion === INPUT_SHAPE" "'schemaVersion' in value"

echo
echo "▶ 러너 몫 (R1)"
code_break R1 "$NEW" 1 "사용자가 고른 보고연도도 덮음" "$VT $TESTS" \
  "보고연도를 먼저 골랐으면 덮지 않는다" \
  "function fillEmpty(" "    yearOpen &&" "    true &&"

echo
echo "▶ 검증자 몫 (X1 — 검증 B1)"
code_break X1 "$NEW" 1 "토픽이 있어도 파일 토픽을 더함(빈 목록 확인 → true)" "$VT $TESTS" \
  "토픽을 먼저 넣었으면 토픽은 그대로" \
  "function fillEmpty(" "prev.materialTopics.length === 0" "true"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
