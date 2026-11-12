#!/usr/bin/env bash
# 밴드 AD4P 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-AD4P.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD2S.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘)에 댄다. 명령이 둘(단위; 브라우저)이면 명령마다 EXIT 를 따로 보고 둘 다 빨개야 빨강(교훈 1절).
# 브라우저 시험이 있는 파손(P1·P4)은 playwright 가 빌드부터 다시 한다(WEB_TEST_PORT, 기본 5434).
# 꼴은 planted-breaks-RF1W.sh 그대로(심기·되돌림·지문·둘 다 빨강).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
SRV=$S/entities/run-log/api/server.ts
DETAIL=$S/entities/run-log/model/detail.ts
LAUNCH=$S/entities/run-log/model/launch.ts
TOUCHED=("$SRV" "$DETAIL" "$LAUNCH")

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

# <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로 — 실패 줄에서 찾는다)>
code_break() {
  local n="$1" file="$2"
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
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-60 | head -6 | tr '\n' '|')"
  local exits
  exits="$(grep -oE 'UNIT_EXIT=[0-9]+ E2E_EXIT=[0-9]+' "$OUT")"
  [ -n "$exits" ] && red="$exits · $red"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
E2E="WEB_TEST_PORT=${WEB_TEST_PORT:-5434} pnpm --filter @esg/web exec playwright test e2e/admin.spec.ts -g 'AD4P'"
# 둘 다 빨개야 EXIT=1(하나라도 초록이면 0 — 「a; b」 의 끝 EXIT 만 보는 구멍을 막는다).
both() { echo "$1; a=\$?; $2; b=\$?; echo \"UNIT_EXIT=\$a E2E_EXIT=\$b\"; [ \$a -ne 0 ] && [ \$b -ne 0 ] && exit 1; exit 0"; }
UNITS="src/entities/run-log src/pages/admin-runs"

echo "▶ AD-04·04a 다듬기 (P1~P8)"
code_break P1 "$SRV" 'async file(' "{ kind: 'notFound' }" "{ kind: 'failed' }" \
  'file() 의 notFound 갈래 뺌(404 → failed)' \
  "$(both "$VT $UNITS" "$E2E")" \
  '404 RUN_NOT_FOUND → notFound
④ 받기 404 RUN_FILE_NOT_FOUND
(밴드 AD4P)'
code_break P2 "$SRV" 'const FILE_NOT_FOUND_CODES' "'RUN_FILE_NOT_FOUND'," "'RUN_FILE_NOT_FOUND_X'," \
  'RUN_FILE_NOT_FOUND 만 빠뜨림' \
  "$VT $UNITS" \
  '404 RUN_FILE_NOT_FOUND → notFound
④ 받기 404 RUN_FILE_NOT_FOUND'
code_break P3 "$SRV" 'async file(' "failure.kind === 'api' &&" "failure.kind === 'api' ||" \
  '503 도 notFound(서버 거절 전부)' \
  "$VT $UNITS" \
  '503 STORAGE_UNAVAILABLE → failed
④-2 받기 503'
code_break P4 "$DETAIL" 'export function shownFiles(' 'file.step === null || !outputs.has(file.name)' 'true || !outputs.has(file.name)' \
  'shownFiles 거르기 뺌' \
  "$(both "$VT $UNITS" "$E2E")" \
  '같은 이름(단계 중간 report + 흐름 출력)
② 상세: 같은 이름 둘
(밴드 AD4P)'
code_break P5 "$DETAIL" 'export function shownFiles(' '!outputs.has(file.name)' 'false' \
  'shownFiles 가 이름 다른 중간 파일도 뺌' \
  "$VT $UNITS" \
  '이름이 다른 중간 파일은 남고
② 상세: 같은 이름 둘'
code_break P6 "$DETAIL" 'export function downloadable(' "detail.status !== 'failed'" 'true' \
  '실패 실행 조건 뺌' \
  "$VT $UNITS" \
  '③ 상세: 실패 실행'
code_break P7 "$LAUNCH" 'export function launchMark(' 'size < 2' 'size < 1' \
  'launchMark 의 >= 2 를 >= 1 로' \
  "$VT $UNITS" \
  'size 1 → null
① 표: launchSize 3 줄에
⑤ 상세: launchSize 3'
code_break P8 "$SRV" 'isAiSetting(row.aiSetting) &&' 'hasLaunchFields(row)' 'true' \
  '가드에서 다섯 칸 검사 뺌' \
  "$VT src/entities/run-log/api" \
  '줄: launchKey 빠짐 → failed
상세: launchSize 가 글자 → failed'

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
