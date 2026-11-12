#!/usr/bin/env bash
# 밴드 IRW1 의 자기검증(발주서 §4 — section4-DV2a.sh 꼴).   사용: apps/web/scripts/section4-IRW1.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B = git merge-base main HEAD(가지 band/IRW1 에서만 뜻이 있다 — 병합 뒤 main 에서는 돌리지 않는다). 경계마다 돈다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 23414·23415). 해시·numstat 은 워크트리 밖 IRW1.out/ 에(h1~h6.diff.*).
# 땅(§1-2): entities/materiality(api·hooks·model·ui·config/text) · pages/materiality-{list,status,result} · app/materiality ·
#   e2e/materiality-server(.spec).ts · 이 스크립트 둘 · 허락 H1 router.tsx · H2 session.ts(+시험) · H3 L · H4 app/shell/moduleMenu(.test) ·
#   H5 app/dataverify/router.test.tsx·e2e/dataverify-server.spec.ts · H6 e2e/greenwash.spec.ts.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23414}" WEB_TEST_PORT="${WEB_TEST_PORT:-23415}"
unset OPENAI_API_KEY ANTHROPIC_API_KEY

B="$(git merge-base main HEAD)"
W=apps/web/src
L=$W/app/guards/layers.test.ts
H1=$W/app/router.tsx
H2=("$W/entities/session/model/session.ts" "$W/entities/session/model/session.test.ts")
H4=("$W/app/shell/moduleMenu.tsx" "$W/app/shell/moduleMenu.test.ts")
H5=("$W/app/dataverify/router.test.tsx" apps/web/e2e/dataverify-server.spec.ts)
H6=apps/web/e2e/greenwash.spec.ts
OUTDIR="$(cd .. && pwd)/IRW1.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/materiality/(api|hooks|model|ui)/.+|entities/materiality/config/text(\.test)?\.ts|pages/materiality-(list|status|result)/.+|app/materiality/(MaterialityRoutes\.tsx|runtime\.ts|router\.test\.tsx)|app/shell/moduleMenu(\.test)?\.tsx?|app/router\.tsx|app/guards/layers\.test\.ts|entities/session/model/session(\.test)?\.ts|app/dataverify/router\.test\.tsx)|e2e/materiality-server(\.spec)?\.ts|e2e/(dataverify-server|greenwash)\.spec\.ts|scripts/(section4|planted-breaks)-IRW1\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1-2, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄 구역 · H1~H6 의 - 줄·sha256·numstat(→ IRW1.out/h<n>.diff.*) · 청 어림 ±50%(넘침은 경계마다, 모자람은 끝 경계 ③ 에서만)"
ZERO=("$W/shared" "$W/widgets" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/entities/translation" "$W/entities/translation-setting" "$W/entities/dataverify" "$W/entities/ai-setting" "$W/pages/greenwash-"* "$W/pages/translation-"* "$W/pages/dataverify-"* "$W/pages/admin-"* "$W/app/auth" "$W/app/admin" "$W/app/greenwash" "$W/app/translation" apps/api-py apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
echo "  app/dataverify 는 router.test.tsx 만 · 기존 e2e 는 dataverify-server.spec.ts·greenwash.spec.ts 만"
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/app/dataverify" | grep -v -E '/router\.test\.tsx$')" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- apps/web/e2e | grep -v -E '^apps/web/e2e/(materiality-server(\.spec)?|dataverify-server\.spec|greenwash\.spec)\.ts$')" ; mark
STAGE="${STAGE:-}"
[ -z "$STAGE" ] && { if git cat-file -e ":$W/pages/materiality-list/index.ts" 2>/dev/null; then STAGE=3; elif git cat-file -e ":$W/app/materiality/MaterialityRoutes.tsx" 2>/dev/null; then STAGE=2; else STAGE=1; fi; }
echo "  경계 STAGE=$STAGE"
over=0
hdiff() { # <n> <청 -> <청 +> <경로들…>
  local n="$1" am="$2" ap="$3"; shift 3
  git diff --cached "$B" -- "$@" > "$OUTDIR/h$n.diff"
  shasum -a 256 "$OUTDIR/h$n.diff" | cut -d' ' -f1 > "$OUTDIR/h$n.diff.sha256"
  git diff --cached --numstat "$B" -- "$@" > "$OUTDIR/h$n.diff.numstat"
  local minus plus
  minus="$(awk '{ s += $2 } END { print s + 0 }' "$OUTDIR/h$n.diff.numstat")"
  plus="$(awk '{ s += $1 } END { print s + 0 }' "$OUTDIR/h$n.diff.numstat")"
  echo "$minus" > "$OUTDIR/h$n.diff.minus"
  local hi_m=$(( am * 3 / 2 )) hi_p=$(( ap * 3 / 2 )) lo_p=$(( ap / 2 )) verdict=안
  [ "$minus" -gt "$hi_m" ] && verdict=넘침
  [ "$plus" -gt "$hi_p" ] && verdict=넘침
  [ "$STAGE" = 3 ] && [ "$plus" -lt "$lo_p" ] && verdict=모자람
  [ "$verdict" = 안 ] || over=$((over + 1))
  echo "  H$n -$minus/+$plus (청 -$am/+$ap · ±50% $verdict) sha256=$(cat "$OUTDIR/h$n.diff.sha256")"
}
hdiff 1 2 40 "$H1"
hdiff 2 3 23 "${H2[@]}"
hdiff 3 10 190 "$L"
hdiff 4 6 7 "${H4[@]}"
hdiff 5 5 6 "${H5[@]}"
hdiff 6 2 2 "$H6"
test "$over" -eq 0 ; mark
echo "  H1~H6 의 - 줄 전부(같은 줄 고침인지 — 보고에 원문으로):"
cat "$OUTDIR"/h[1-6].diff | grep '^-[^-]' | tee "$OUTDIR/h-minus.txt" | sed 's/^/    /'

say "[3] 기존 시험의 - 줄 0(L·session.test·moduleMenu.test·H5·H6 밖)"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' '*.spec.ts' ":!$L" ":!${H2[1]}" ":!${H4[1]}" ":!${H5[0]}" ":!${H5[1]}" ":!$H6" | grep '^-[^-]' > "$T/test-minus.txt"
cat "$T/test-minus.txt"
test ! -s "$T/test-minus.txt" ; mark
git diff --cached "$B" -- "${H2[1]}" | grep '^-[^-]' ; test $? -eq 1 ; mark

IR_FILES="$(git ls-files -- "$W/entities/materiality" "$W/pages/materiality-"* "$W/app/materiality"; git diff --cached --name-only --diff-filter=A "$B" -- "$W/entities/materiality" "$W/pages/materiality-"* "$W/app/materiality")"
IR_FILES="$(sort -u <<< "$IR_FILES" | grep .)"
echo "중대성평가 파일 $(grep -c . <<< "$IR_FILES")개"
scan() { # <무늬> [파일 거름] — 주석 밖 줄
  for f in $IR_FILES; do git show ":$f" | grep -nE "$1" | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' | sed "s#^#$f:#"; done
}

say "[4] 중대성평가 파일의 fetch(·XMLHttpRequest·msw·남의 모듈 땅 0(+ 양성 대조)"
FORBID="entities/(greenwash|translation|dataverify)|pages/(greenwash|translation|dataverify)-|\bfetch\(|XMLHttpRequest|\bmsw\b"
hits="$(scan "$FORBID")"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: app/dataverify 의 경로 파일엔 걸린다"
grep -qE "$FORBID" "$W/app/dataverify/DataverifyRoutes.tsx" ; mark

say "[5] 중대성평가 ui·model·api·hooks·화면·app 의 한국어 글자 줄 0(주석 밖 — config/text.ts·model/wire.ts·시험·testing.ts 밖)"
cat > "$T/hangul.mjs" <<'NODE'
import { execFileSync } from 'node:child_process';
// 주석만 지운다(문자열은 남긴다 — 그 안의 한국어가 잡을 것). 내용은 인덱스에서 읽는다.
const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
let n = 0;
for (const file of process.argv.slice(2)) {
  strip(execFileSync('git', ['show', `:${file}`], { encoding: 'utf8' })).split('\n').forEach((line, i) => {
    if (/[가-힣]/.test(line)) { n++; console.log(`${file}:${i + 1}: ${line.trim()}`); }
  });
}
console.log(`hangul_lines=${n}`);
process.exit(n === 0 ? 0 : 1);
NODE
CODE="$(grep -vE '\.test\.tsx?$|/config/text\.ts$|/model/wire\.ts$|/testing\.ts$' <<< "$IR_FILES" | grep .)"
node "$T/hangul.mjs" $CODE ; mark
echo "  양성 대조: config/text.ts·model/wire.ts 엔 걸린다"
! node "$T/hangul.mjs" "$W/entities/materiality/config/text.ts" > /dev/null ; mark
! node "$T/hangul.mjs" "$W/entities/materiality/model/wire.ts" > /dev/null ; mark

say "[6] websearch 파일 이름이 text·ui·화면에 0 · dangerouslySetInnerHTML 0 · _blank 엔 noopener"
hits="$(for f in $(grep -E '/config/text\.ts$|/ui/|^apps/web/src/(pages|app)/' <<< "$IR_FILES" | grep -vE '\.test\.tsx?$'); do git show ":$f" | grep -n 'materiality-websearch' | sed "s#^#$f:#"; done)"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
hits="$(scan 'dangerouslySetInnerHTML')"; [ -n "$hits" ] && echo "$hits"; test -z "$hits" ; mark
# _blank 줄의 앞뒤 두 줄 안에 noopener(JSX 속성은 줄마다 하나라 다음 줄에 온다) · 시험 파일 밖.
hits="$(for f in $(grep -vE '\.test\.tsx?$' <<< "$IR_FILES"); do git show ":$f" | awk -v f="$f" '{ line[NR] = $0 } END { for (i = 1; i <= NR; i++) if (line[i] ~ /_blank/) { ok = 0; for (j = i - 2; j <= i + 2; j++) if (line[j] ~ /noopener/) ok = 1; if (!ok) print f ":" i ": " line[i] } }'; done)"
[ -n "$hits" ] && echo "$hits"; test -z "$hits" ; mark
echo "  _blank 줄 수(시험 밖): $(for f in $(grep -vE '\.test\.tsx?$' <<< "$IR_FILES"); do git show ":$f" | grep -c '_blank'; done | awk '{ s += $1 } END { print s + 0 }')"

say "[7] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-IRW1.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=|^LATER=' "$T/planted.log" | cut -c1-160
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수) · 루트 --fast"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "(web verify $(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
start=$(date +%s)
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; echo "(fast $(( $(date +%s) - start ))s)"
cp "$T/fast.log" "$OUTDIR/fast-verify.log"
(exit $code) ; mark

say "[9] 중대성평가 파일의 console.·localStorage·sessionStorage 0(주석 밖, + 양성 대조)"
hits="$(scan '\bconsole\.|localStorage|sessionStorage')"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: entities/session 엔 걸린다"
grep -rqE 'localStorage|sessionStorage' "$W/entities/session" ; mark

say "[10] 추적 diff 에 키 꼴·실재 기업명(금지어 목록)·.pdf·.docx·.xlsx·새 .json 0 · apps/api-py diff 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-IRW1.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-IRW1.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx)$')" ; mark
test -z "$(git diff --cached --name-only --diff-filter=A "$B" | grep -iE '\.json$')" ; mark
git diff --cached --quiet "$B" -- apps/api-py ; mark

echo
echo "원시 출력: $T · 해시: $OUTDIR"
echo "SECTION4_FAIL=$fail"
