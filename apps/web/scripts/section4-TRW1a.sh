#!/usr/bin/env bash
# 밴드 TRW1a 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-TRW1a.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/TRW1a)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 21174·21175). 해시·numstat 은 워크트리 밖 TRW1a.out/ 에(h1~h5.diff.*).
# 땅(§1-2): 영문번역 entities(api·hooks 새 · model·config·ui 더하기) · pages/translation-{list,new,run} · app/translation ·
#   e2e/translation-server(.spec).ts · 이 스크립트 둘 · 허락 H1 router.tsx · H2 session.ts(+시험) · H3 L · H4 DownloadButton 둘 · H5 GreenwashRoutes.tsx 2줄.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-21174}" WEB_TEST_PORT="${WEB_TEST_PORT:-21175}"

B=ca59cc3e
W=apps/web/src
L=$W/app/guards/layers.test.ts
H1=$W/app/router.tsx
H2=("$W/entities/session/model/session.ts" "$W/entities/session/model/session.test.ts")
H4=("$W/shared/ui/download-button/ui/DownloadButton.tsx" "$W/shared/ui/download-button/ui/DownloadButton.test.tsx")
H5=$W/app/greenwash/GreenwashRoutes.tsx
H5E=apps/web/e2e/greenwash.spec.ts
OUTDIR="$(cd .. && pwd)/TRW1a.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/translation/(api|hooks|model|ui)/.+|entities/translation/config/text(\.test)?\.ts|pages/translation-(list|new|run)/.+|app/translation/.+|app/router\.tsx|app/guards/layers\.test\.ts|entities/session/model/session(\.test)?\.ts|shared/ui/download-button/ui/DownloadButton(\.test)?\.tsx|app/greenwash/GreenwashRoutes\.tsx)|e2e/translation-server(\.spec)?\.ts|e2e/greenwash\.spec\.ts|scripts/(section4|planted-breaks)-TRW1a\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1-2, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄 구역 · H1~H5 의 - 줄·sha256·numstat(→ TRW1a.out/h<n>.diff.*) · H1 - ≤ 1(제네릭 줄) · H5 각 파일 합 ≤ 3"
ZERO=("$W/widgets" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/pages/greenwash-"* "$W/pages/admin-"* "$W/entities/audit-log" "$W/app/auth" "$W/app/admin" apps/api-py apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
echo "  shared 는 H4 두 파일만"
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/shared" | grep -v -E '/shared/ui/download-button/ui/DownloadButton(\.test)?\.tsx$')" ; mark
echo "  app/greenwash 는 GreenwashRoutes.tsx 만 · 기존 e2e 0줄"
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/app/greenwash" | grep -v -E '/GreenwashRoutes\.tsx$')" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- apps/web/e2e | grep -v -E '^apps/web/e2e/(translation-server(\.spec)?|greenwash\.spec)\.ts$')" ; mark
hdiff() { # <n> <경로들…>
  local n="$1"; shift
  git diff --cached "$B" -- "$@" > "$OUTDIR/h$n.diff"
  shasum -a 256 "$OUTDIR/h$n.diff" | cut -d' ' -f1 > "$OUTDIR/h$n.diff.sha256"
  git diff --cached --numstat "$B" -- "$@" > "$OUTDIR/h$n.diff.numstat"
  local minus; minus="$(grep -c '^-[^-]' "$OUTDIR/h$n.diff")"
  echo "  H$n sha256=$(cat "$OUTDIR/h$n.diff.sha256") minus=$minus numstat: $(tr '\n' ' ' < "$OUTDIR/h$n.diff.numstat")"
  echo "$minus" > "$OUTDIR/h$n.diff.minus"
}
hdiff 1 "$H1"
hdiff 2 "${H2[@]}"
hdiff 3 "$L"
hdiff 4 "${H4[@]}"
hdiff 5 "$H5" "$H5E"
echo "  H1 의 - 는 루트 context 제네릭 한 줄만(prettier 가 TranslationRouterContext 를 붙이며 접음 — 감독 알림 10-23)"
test "$(cat "$OUTDIR/h1.diff.minus")" -le 1 && { [ "$(cat "$OUTDIR/h1.diff.minus")" -eq 0 ] || grep -qxF -- '-    AppRouterContext & SessionContext & AdminRouterContext' "$OUTDIR/h1.diff"; } ; mark
# H5 = GreenwashRoutes.tsx 두 줄(≤ 3) + e2e/greenwash.spec.ts:412 한 줄과 주석 한 줄(≤ 3 — 그린워싱·플랫폼-웹 허락 10-23).
h5="$(awk '$3 ~ /GreenwashRoutes/ { s += $1 + $2 } END { print s + 0 }' "$OUTDIR/h5.diff.numstat")"
h5e="$(awk '$3 ~ /greenwash\.spec/ { s += $1 + $2 } END { print s + 0 }' "$OUTDIR/h5.diff.numstat")"
echo "  H5 합(+·-) GreenwashRoutes=$h5 · greenwash.spec=$h5e"
test "$h5" -le 3 && test "$h5e" -le 3 ; mark

say "[3] 기존 시험의 - 줄 0(TRW0a·TRW0b 시험 포함 — H2·H4 시험은 더하기만, L 은 H3 로 [2] 에 적음)"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' ":!$L" | grep '^-[^-]' > "$T/test-minus.txt"
cat "$T/test-minus.txt"
test ! -s "$T/test-minus.txt" ; mark
echo "  영문번역 기존 model·config·ui 파일의 - 줄(config grid.note 한 줄만 허락 — 감독 판단 5)"
git diff --cached --diff-filter=M "$B" -- "$W/entities/translation/model" "$W/entities/translation/ui" "$W/entities/translation/config" | grep '^-[^-]' | grep -v -F "note: '쪽 칸은 [PAGE n] 번호만 보이는 자리 그림" > "$T/tr-minus.txt"
cat "$T/tr-minus.txt"
test ! -s "$T/tr-minus.txt" ; mark

say "[4] 영문번역 파일의 fetch(·XMLHttpRequest·msw·entities/greenwash·pages/greenwash- 0(주석 밖, + 양성 대조)"
TR_FILES="$(git ls-files -- "$W/entities/translation" "$W/pages/translation-"* "$W/app/translation"; git diff --cached --name-only --diff-filter=A "$B" -- "$W/entities/translation" "$W/pages/translation-"* "$W/app/translation")"
TR_FILES="$(sort -u <<< "$TR_FILES" | grep .)"
echo "영문번역 파일 $(grep -c . <<< "$TR_FILES")개"
FORBID="entities/greenwash|pages/greenwash-|\bfetch\(|XMLHttpRequest|\bmsw\b"
hits="$(for f in $TR_FILES; do git show ":$f" | grep -nE "$FORBID" | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' | sed "s#^#$f:#"; done)"
# 감독 판단 2: app/translation 의 sendUpload(서명 PUT — GreenwashRoutes.tsx:108 복사)는 전역 통신을 쓴다. 그 한 줄만 뺀다(개수 1 을 따로 본다).
upload_hits="$(grep -cF 'app/translation/TranslationRoutes.tsx:' <<< "$hits")"
echo "  sendUpload 줄(허락): $upload_hits"
hits="$(grep -vE '^apps/web/src/app/translation/TranslationRoutes\.tsx:[0-9]+:  const response = await globalThis\.fetch\(url, \{$' <<< "$hits" | grep .)"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: pages/greenwash-new 의 화면 파일엔 걸린다"
grep -qE "$FORBID" "$W/pages/greenwash-new/ui/"*.tsx ; mark

say "[5] 영문번역 ui·model·api·hooks·화면의 한국어 글자 줄 0(주석 밖 — config/text.ts·시험·testing.ts 밖)"
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
CODE="$(grep -vE '\.test\.tsx?$|/config/text\.ts$|/testing\.ts$' <<< "$TR_FILES" | grep .)"
node "$T/hangul.mjs" $CODE ; mark

say "[6] 화면 글에 「비용」 0(config/text.ts — sid:MARC-ENT-334)"
git show ":$W/entities/translation/config/text.ts" | grep -n '비용' | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' ; test $? -eq 1 ; mark

say "[7] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-TRW1a.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=|^LATER=' "$T/planted.log" | cut -c1-160
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수 — B 는 단위 2572·브라우저 169, ca59cc3e verify notes) · 루트 --fast"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
start=$(date +%s)
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; echo "($(( $(date +%s) - start ))s)"
cp "$T/fast.log" "$OUTDIR/fast-verify.log"
(exit $code) ; mark

say "[9] 추적 diff 에 키 꼴·실재 기업명(금지어 목록)·.pdf·.docx·.xlsx 0 · apps/api-py diff 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-TRW1a.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-TRW1a.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx)$')" ; mark
git diff --cached --quiet "$B" -- apps/api-py ; mark

echo
echo "원시 출력: $T · 해시: $OUTDIR"
echo "SECTION4_FAIL=$fail"
