#!/usr/bin/env bash
# 밴드 K1b-3 ③ 웹의 심은 파손(발주서 3-7 ③).   사용: apps/web/scripts/planted-breaks-K1b-3.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. W1~W7(발주서 표) · W8(e2e — 「다른 탭 저장」 뒤 줄 n → n+1).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-TRW1a.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다. 뿌리 .git/verify.lock 이 있으면 돌리지 않는다(부르는 쪽이 기다린다).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
SV=$S/entities/ghg/api/server.ts
FK=$S/entities/ghg/api/testing.ts
BS=$S/pages/ghg-branch/ui/BranchScreen.tsx
E2E=$W/e2e/ghg-server.ts
TOUCHED=()
for file in "$SV" "$FK" "$BS" "$E2E"; do
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
API=src/entities/ghg/api/server.test.ts
SCR=src/pages/ghg-branch/ui/BranchScreen.test.tsx

echo "▶ 발주서 표 (W1~W7)"
code_break W1 "$SV" "async saveBranch(id, {" "body: { name, inventoryEnabled, facilities, updatedAt }," "body: { name, inventoryEnabled, facilities }," \
  "saveBranch 가 updatedAt 을 싣지 않음" \
  "$VT $API $SCR" \
  "PUT 경로 id 정수
줄 삭제 + 추가 → PUT 본문"
code_break W2 "$SV" "export const WRITE_CODES = [" "'STALE'," "" \
  "WRITE_CODES 에서 STALE 뺌" \
  "$VT $API $SCR" \
  "409 STALE(낡은 판) → rejected STALE
다른 탭이 저장한 뒤 [저장] → 409 STALE"
code_break W3 "$BS" "const next = draftOf(outcome.value);" "setVersion(outcome.value.updatedAt);" "" \
  "PUT 200 뒤 version 을 바꾸지 않음" \
  "$VT $SCR" \
  "줄 삭제 + 추가 → PUT 본문"
code_break W4 "$BS" "const reload = async () => {" "const again = await port.getBranch(branchId);" "const again = { kind: 'failed' as const };" \
  "[다시 불러오기]가 getBranch 를 부르지 않음" \
  "$VT $SCR" \
  "확인 → 다시 읽어 폼·판을 새로
고친 것이 없으면 확인 창 없이"
code_break W5 "$FK" "if (one[1] === 'GET') return json(200, branch);" "if (updatedAt !== branch.updatedAt) return refusal(409, 'STALE');" "" \
  "가짜가 판을 보지 않음(낡은 판도 200)" \
  "$VT $API $SCR" \
  "409 STALE(낡은 판) → rejected STALE
다른 탭이 저장한 뒤 [저장] → 409 STALE"
code_break W6 "$BS" "data-testid=\"branch-reload\"" "if (sameDraft(draft, base)) void reload();" "if (sameDraft(base, base)) void reload();" \
  "고친 것이 있어도 확인 창 없이 덮음" \
  "$VT $SCR" \
  "다른 탭이 저장한 뒤 [저장] → 409 STALE
확인 → 다시 읽어 폼·판을 새로"
code_break W7 "$SV" "async createBranch({" "body: { name, inventoryEnabled, facilities }," "body: { name, inventoryEnabled, facilities, updatedAt: '2026-10-28T09:00:00+09:00' } as never," \
  "POST 본문에 updatedAt 실음(어댑터 — 화면은 본문 칸을 고르지 않는다)" \
  "$VT $API $SCR" \
  "POST 본문 {name, inventoryEnabled, facilities
새 사업장(POST)은 판을 싣지 않는다"

echo
echo "▶ e2e (W8 — 늘리기 §B-7)"
code_break W8 "$E2E" "const bumpBranch = (" "if (line) branch.lines.push({ id: lineSeq++, ...line });" "" \
  "e2e: 흉내의 「다른 탭 저장」이 줄을 더하지 않음(다시 불러온 뒤 줄 n → n+1 이 깨짐)" \
  "WEB_TEST_PORT=${WEB_TEST_PORT:-20621} pnpm --filter @esg/web exec playwright test e2e/ghg-server.spec.ts -g K1b-3" \
  "ghg-server.spec.ts"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "LATER=$later"
echo "PLANTED=$passed/$total"
