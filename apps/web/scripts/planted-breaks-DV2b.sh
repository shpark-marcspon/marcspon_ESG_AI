#!/usr/bin/env bash
# 밴드 DV2b 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-DV2b.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. B1~B8(발주서 표) · R1~R2(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2a.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
E=$S/entities/dataverify
SRC=$E/model/source.ts
LS=$S/pages/dataverify-list/ui/ListScreen.tsx
LF=$S/pages/dataverify-list/model/filter.ts
NEWS=$S/pages/dataverify-new/ui/NewScreen.tsx
FORM=$S/pages/dataverify-new/model/form.ts
TOUCHED=()
for file in "$SRC" "$LS" "$LF" "$NEWS" "$FORM"; do
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
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-70 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
LIST=src/pages/dataverify-list
NEW=src/pages/dataverify-new
ROUTER=src/app/dataverify

echo "▶ 발주서 표 (B1~B8)"
code_break B1 "$LS" "export function labelOf" "DV_TEXT.source.pastedAt(atText(run.createdAt))" "DV_TEXT.source.pastedAt('')" \
  "붙여 넣은 줄에 시각 대신 빈 글" \
  "$VT $LIST" \
  "파일명 칸: 파일 이름"
code_break B2 "$NEWS" "const inputSource = useMemo" "? fileSource(fileName)" "? PASTE_SOURCE" \
  "파일 실행을 붙여 넣기로 실음" \
  "$VT $NEW" \
  "파일로 시작 → options.source"
code_break B3 "$FORM" "export const optionsTooLarge" "buildInput(companyOf(draft), data), source)" "buildInput(companyOf(draft), data))" \
  "크기 셈에서 source 뺌" \
  "$VT $NEW" \
  "크기 셈에 source 가 든다"
code_break B4 "$LS" "const nextOf" ": run.status === 'failed' ? 'rerun'" ": run.status === 'failed' ? 'result'" \
  "failed 줄에 [결과 보기]" \
  "$VT $LIST" \
  "상태 배지·다음 할 일"
code_break B5 "$LS" "const showMine" "const showMine = !operator;" "const showMine = true;" \
  "운영 관리자에 「내가 올린 것만」" \
  "$VT $LIST $ROUTER" \
  "운영 관리자: 「내가 올린 것만」 0
실행이 있으면 /dataverify 는 목록"
code_break B6 "$LS" "if (nothingYet" "if (nothingYet && intro !== undefined)" "if (false && nothingYet && intro !== undefined)" \
  "빈 목록에 표 머리만(DV-00 대신)" \
  "$VT $LIST $ROUTER" \
  "빔: 거름 없는 첫 쪽 0건 → intro
실행이 있으면 /dataverify 는 목록"
code_break B7 "$LS" "id: 'lastRun'" "{atText(row.original.run.createdAt)}" "{atText(row.original.run.createdAt)} · 1회차" \
  "서버에 없는 칸(「1회차」 회차)을 그림" \
  "$VT $LIST" \
  "요약 칸: 보고연도"
code_break B8 "$NEWS" "const inputSource = useMemo" "source === 'paste' ? PASTE_SOURCE" "source === 'paste' ? fileSource('pasted.json')" \
  "e2e: 붙여 넣기 본문에 파일 이름(빌드한 웹 — 흉내 서버가 본문을 적는다)" \
  "WEB_TEST_PORT=${WEB_TEST_PORT:-21435} pnpm --filter @esg/web exec playwright test e2e/dataverify-server.spec.ts" \
  "dataverify-server.spec.ts"

echo
echo "▶ 러너 몫 (R1·R2)"
code_break R1 "$LF" "case 'active':" "return ['queued', 'processing'];" "return ['queued'];" \
  "「대기·처리 중」 탭이 queued 만 보냄(처리 중 줄이 빠짐)" \
  "$VT $LIST" \
  "탭 → status 쿼리"
code_break R2 "$SRC" "export const isSourceName" "NAME.test(name) && [...name].length <= SOURCE_NAME_MAX" "NAME.test(name)" \
  "파일 이름 길이 상한(255 code point) 뺌 — 서버가 422 로 거절할 이름을 보냄" \
  "$VT src/entities/dataverify/model/source.test.ts" \
  "받는 이름 · 거절하는 이름"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
