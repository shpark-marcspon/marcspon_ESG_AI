#!/usr/bin/env bash
# 밴드 DV2a 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV2a.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV2a)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다. 경계마다 돈다(뒤 경계 몫은 「뒤 경계」로 적고 넘어간다).
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 22524·22525). 해시·numstat 은 워크트리 밖 DV2a.out/ 에(h1~h6.diff.*).
# 땅(§1-2): entities/dataverify(api·hooks·model·config·ui 새) · pages/dataverify-{intro,new,status,result} · app/dataverify ·
#   e2e/dataverify-server(.spec).ts · 이 스크립트 둘 · 허락 H1 router.tsx · H2 session.ts(+시험) · H3 L · H4 app/shell/moduleMenu(.test) ·
#   H5 GreenwashRoutes.tsx·e2e/greenwash.spec.ts 두 줄 · H6 TranslationRoutes.tsx.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-22524}" WEB_TEST_PORT="${WEB_TEST_PORT:-22525}"

B=926e7f98
W=apps/web/src
L=$W/app/guards/layers.test.ts
H1=$W/app/router.tsx
H2=("$W/entities/session/model/session.ts" "$W/entities/session/model/session.test.ts")
H4=("$W/app/shell/moduleMenu.tsx" "$W/app/shell/moduleMenu.test.ts")
H5=$W/app/greenwash/GreenwashRoutes.tsx
H5E=apps/web/e2e/greenwash.spec.ts
H6=$W/app/translation/TranslationRoutes.tsx
OUTDIR="$(cd .. && pwd)/DV2a.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/(api|hooks|model|ui)/.+|entities/dataverify/config/text(\.test)?\.ts|pages/dataverify-(intro|new|status|result)/.+|app/dataverify/.+|app/shell/moduleMenu(\.test)?\.tsx?|app/router\.tsx|app/guards/layers\.test\.ts|entities/session/model/session(\.test)?\.ts|app/greenwash/GreenwashRoutes\.tsx|app/translation/TranslationRoutes\.tsx)|e2e/dataverify-server(\.spec)?\.ts|e2e/greenwash\.spec\.ts|scripts/(section4|planted-breaks)-DV2a\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1-2, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄 구역 · H1~H6 의 - 줄·sha256·numstat(→ DV2a.out/h<n>.diff.*) · 청 어림 ±50%(넘침은 경계마다, 모자람은 끝 경계 ③ 에서만)"
ZERO=("$W/shared" "$W/widgets" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/entities/translation" "$W/entities/ai-setting" "$W/pages/greenwash-"* "$W/pages/translation-"* "$W/pages/admin-"* "$W/app/auth" "$W/app/admin" apps/api-py apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
echo "  app/greenwash 는 GreenwashRoutes.tsx 만 · app/translation 은 TranslationRoutes.tsx 만 · 기존 e2e 는 greenwash.spec.ts 만"
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/app/greenwash" | grep -v -E '/GreenwashRoutes\.tsx$')" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/app/translation" | grep -v -E '/TranslationRoutes\.tsx$')" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- apps/web/e2e | grep -v -E '^apps/web/e2e/(dataverify-server(\.spec)?|greenwash\.spec)\.ts$')" ; mark
STAGE="${STAGE:-}"
[ -z "$STAGE" ] && { if git cat-file -e ":$W/pages/dataverify-result/index.ts" 2>/dev/null; then STAGE=3; elif git cat-file -e ":$H4" 2>/dev/null || git cat-file -e ":${H4[0]}" 2>/dev/null; then STAGE=2; else STAGE=1; fi; }
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
hdiff 1 2 45 "$H1"
hdiff 2 4 23 "${H2[@]}"
hdiff 3 20 190 "$L"
hdiff 4 0 70 "${H4[@]}"
hdiff 5 46 6 "$H5" "$H5E"
hdiff 6 44 4 "$H6"
test "$over" -eq 0 ; mark
echo "  H1~H3 의 - 줄 전부(같은 줄 고침인지 — 보고에 원문으로):"
cat "$OUTDIR/h1.diff" "$OUTDIR/h2.diff" "$OUTDIR/h3.diff" | grep '^-[^-]' | tee "$OUTDIR/h123-minus.txt" | sed 's/^/    /'
echo "  H5 spec 은 - 2 · + 2 안"
h5e_m="$(awk '$3 ~ /greenwash\.spec/ { s += $2 } END { print s + 0 }' "$OUTDIR/h5.diff.numstat")"
h5e_p="$(awk '$3 ~ /greenwash\.spec/ { s += $1 } END { print s + 0 }' "$OUTDIR/h5.diff.numstat")"
echo "  greenwash.spec -$h5e_m/+$h5e_p"
test "$h5e_m" -le 2 && test "$h5e_p" -le 2 ; mark

say "[3] 기존 시험의 - 줄 0(L·session.test 는 [2] 에, H5 spec 두 줄 밖)"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' ":!$L" ":!$W/entities/session/model/session.test.ts" | grep '^-[^-]' > "$T/test-minus.txt"
cat "$T/test-minus.txt"
test ! -s "$T/test-minus.txt" ; mark
git diff --cached "$B" -- "${H2[1]}" | grep '^-[^-]' ; test $? -eq 1 ; mark

DV_FILES="$(git ls-files -- "$W/entities/dataverify" "$W/pages/dataverify-"* "$W/app/dataverify"; git diff --cached --name-only --diff-filter=A "$B" -- "$W/entities/dataverify" "$W/pages/dataverify-"* "$W/app/dataverify")"
DV_FILES="$(sort -u <<< "$DV_FILES" | grep .)"
echo "데이터 검증 파일 $(grep -c . <<< "$DV_FILES")개"
scan() { # <무늬> — 주석 밖 줄
  for f in $DV_FILES; do git show ":$f" | grep -nE "$1" | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' | sed "s#^#$f:#"; done
}

say "[4] 데이터 검증 파일의 fetch(·XMLHttpRequest·msw·entities/greenwash·entities/translation·pages/greenwash-·pages/translation- 0(+ 양성 대조)"
FORBID="entities/greenwash|entities/translation|pages/greenwash-|pages/translation-|\bfetch\(|XMLHttpRequest|\bmsw\b"
hits="$(scan "$FORBID")"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: app/translation 의 경로 파일엔 걸린다"
grep -qE "$FORBID" "$W/app/translation/TranslationRoutes.tsx" ; mark

say "[5] *Routes.tsx 셋에 「AppShellMenuItem[] = [」 0 (양성 대조: B 의 GreenwashRoutes.tsx 사본 하나 · 한 자리는 moduleMenu.tsx)"
if [ "$STAGE" = 1 ]; then echo "  뒤 경계(② 가 메뉴를 올린다)"; else
  n=0; for f in "$H5" "$H6" "$W/app/dataverify/DataverifyRoutes.tsx"; do c="$(git show ":$f" 2>/dev/null | grep -c 'AppShellMenuItem\[\] = \[')"; echo "  $f: $c"; n=$((n + c)); done
  test "$n" -eq 0 ; mark
  test "$(git show "$B:$H5" | grep -c 'AppShellMenuItem\[\] = \[')" -eq 1 && git show ":${H4[0]}" | grep -q 'export const moduleMenu' ; mark
fi

say "[6] 데이터 검증 ui·model·api·hooks·화면·app 의 한국어 글자 줄 0(주석 밖 — config/text.ts·시험·testing.ts 밖)"
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
CODE="$(grep -vE '\.test\.tsx?$|/config/text\.ts$|/testing\.ts$' <<< "$DV_FILES" | grep .)"
node "$T/hangul.mjs" $CODE ; mark
echo "  양성 대조: config/text.ts 엔 걸린다"
! node "$T/hangul.mjs" "$W/entities/dataverify/config/text.ts" > /dev/null ; mark

say "[7] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV2a.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=|^LATER=' "$T/planted.log" | cut -c1-160
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수 — B 의 수는 보고에) · 루트 --fast"
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

say "[9] 데이터 검증 파일의 console.·localStorage·sessionStorage 0(주석 밖, + 양성 대조)"
hits="$(scan '\bconsole\.|localStorage|sessionStorage')"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: entities/session 엔 걸린다"
grep -rqE 'localStorage|sessionStorage' "$W/entities/session" ; mark

say "[10] 추적 diff 에 키 꼴·실재 기업명(금지어 목록)·.pdf·.docx·.xlsx·새 .json 0 · apps/api-py diff 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2a.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2a.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx)$')" ; mark
test -z "$(git diff --cached --name-only --diff-filter=A "$B" | grep -iE '\.json$')" ; mark
git diff --cached --quiet "$B" -- apps/api-py ; mark

echo
echo "원시 출력: $T · 해시: $OUTDIR"
echo "SECTION4_FAIL=$fail"
