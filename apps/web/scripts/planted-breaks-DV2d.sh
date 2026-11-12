#!/usr/bin/env bash
# 밴드 DV2d 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-DV2d.sh
# 파손을 하나씩 심고, 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. E1~E5(발주서 표) · X1(검증자 B1) · R1(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2c.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
SERVER=$S/entities/dataverify/api/server.ts
NEWS=$S/pages/dataverify-new/ui/NewScreen.tsx
TOUCHED=("$SERVER" "$NEWS")

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
API=src/entities/dataverify/api
NEW=src/pages/dataverify-new

echo "▶ 발주서 표 (E1~E5)"
code_break E1 "$SERVER" 1 "실패 뒤 다시 보냄에 launchKey 새로" "$VT $API" \
  "실패 뒤 같은 본문 = 둘 다 같음
답 없음 뒤 같은 IK·같은 launchKey 다시 보냄" \
  "async function postRun(" "const { key, launchKey } = pending;" "const { key } = pending, launchKey = makeLaunchKey();"
code_break E2 "$SERVER" 1 "rerun 이 앞 누름의 launchKey(와 IK)를 이어 씀" "$VT $API" \
  "rerun = 둘 다 새로" \
  "async rerun(" "return postRun(options, true);" "return postRun(options);"
code_break E3 "$SERVER" 1 "launchKey = Idempotency-Key" "$VT $API" \
  "첫 [검증 시작] 본문에 소문자 UUID launchKey
rerun = 둘 다 새로" \
  "async function postRun(" "const { key, launchKey } = pending;" "const { key } = pending, launchKey = key;"
code_break X1 "$SERVER" 1 "실패 뒤 본문이 바뀌어도 앞 launchKey 를 이음(검증자 B1)" "$VT $API" \
  "실패 뒤 본문을 고쳐 다시 누름 = 둘 다 새로" \
  "async function postRun(" "launchKey: makeLaunchKey()" "launchKey: pending?.launchKey ?? makeLaunchKey()"
code_break E4 "$NEWS" 1 "오류 때 describedBy 0" "$VT $NEW" \
  "파일 칸 aria(DV2d)" \
  "<FileDropzone" "describedBy={error !== null ? dataErrorId : undefined}" "describedBy={undefined}"
code_break E5 "$NEWS" 1 "오류 없을 때도 invalid 참" "$VT $NEW" \
  "파일 칸 aria(DV2d)" \
  "<FileDropzone" "invalid={error !== null}" "invalid={true}"

echo
echo "▶ 러너 몫 (R1)"
code_break R1 "$SERVER" 1 "본문에서 launchKey 빠짐(옛 꼴)" "$VT $API $NEW" \
  "본문 열쇠는 module·options
첫 [검증 시작] 본문에 소문자 UUID launchKey
붙여 넣은 글로 시작 — 본문은 module·launchKey·options" \
  "async function postRun(" "body: { module: MODULE, launchKey, options }," "body: { module: MODULE, options },"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
