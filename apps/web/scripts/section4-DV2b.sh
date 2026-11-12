#!/usr/bin/env bash
# 밴드 DV2b 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV2b.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV2b)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 21434·21435 — 워크트리 .env). 원시 출력은 워크트리 밖 DV2b.out/ 에.
# 땅(§1): entities/dataverify(더하기) · pages/dataverify-{list(새),new,status,result} · app/dataverify(DataverifyRoutes·router.test) ·
#   e2e/dataverify-server(.spec).ts · 이 스크립트 둘. 0줄: router.tsx·L·session.ts·app/shell·그린워싱·영문번역 땅·shared·서버.
# DV2a §4 의 1·3·4·6·7·8·9·10 꼴 + [2] 0줄 구역 diff 0 + [5] 「감독이 채움」에 없는 판 칸 이름이 config/text.ts 의 목록 글에 0.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-21434}" WEB_TEST_PORT="${WEB_TEST_PORT:-21435}"

B=4a70a7ba
W=apps/web/src
OUTDIR="$(cd .. && pwd)/DV2b.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/.+|pages/dataverify-(list|new|status|result)/.+|app/dataverify/(DataverifyRoutes\.tsx|router\.test\.tsx))|e2e/dataverify-server(\.spec)?\.ts|scripts/(section4|planted-breaks)-DV2b\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1 수정 허용, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark
echo "  dataverify-status·result 는 머리 제목만(화면 파일 - 줄 원문):"
git diff --cached "$B" -- "$W/pages/dataverify-status/ui/StatusScreen.tsx" "$W/pages/dataverify-result/ui/ResultScreen.tsx" | grep '^-[^-]' | sed 's/^/    /'

say "[2] §1 0줄 구역(router·L·session·app/shell·남의 땅·shared·서버·의존) diff 0"
ZERO=("$W/app/router.tsx" "$W/app/guards" "$W/entities/session" "$W/app/shell" "$W/shared" "$W/widgets" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/entities/translation" "$W/entities/ai-setting" "$W/pages/greenwash-"* "$W/pages/translation-"* "$W/pages/admin-"* "$W/pages/dataverify-intro" "$W/app/greenwash" "$W/app/translation" "$W/app/auth" "$W/app/admin" apps/api-py apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- apps/web/e2e | grep -v -E '^apps/web/e2e/dataverify-server(\.spec)?\.ts$')" ; mark

say "[3] 기존 시험의 - 줄 0(router.test·e2e dataverify-server(.spec)·NewScreen.test 는 이 밴드가 고치는 자리 — - 줄 원문을 아래에)"
EXCEPT=("$W/app/dataverify/router.test.tsx" apps/web/e2e/dataverify-server.ts apps/web/e2e/dataverify-server.spec.ts "$W/pages/dataverify-new/ui/NewScreen.test.tsx")
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' $(printf ":!%s " "${EXCEPT[@]}") | grep '^-[^-]' > "$T/test-minus.txt"
cat "$T/test-minus.txt"
test ! -s "$T/test-minus.txt" ; mark
echo "  예외 넷의 - 줄 원문(→ DV2b.out/except-minus.txt):"
for f in "${EXCEPT[@]}"; do git diff --cached "$B" -- "$f" | grep '^-[^-]' | sed "s#^#  $f: #"; done | tee "$OUTDIR/except-minus.txt"

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

say "[5] 「감독이 채움」에 없는 판 칸 이름(「(핵심 n)」·「1회차」·회차·작업 회사·고객사)이 DV_TEXT.list·source 글에 0 (+ 양성 대조: 판 DV-01a 글)"
cat > "$T/board.mjs" <<'NODE'
const { DV_TEXT } = await import(process.argv[2]);
const all = (v) => typeof v === 'string' ? [v] : typeof v === 'function' ? [String(v)] : v && typeof v === 'object' ? Object.values(v).flatMap(all) : [];
const words = /핵심|회차|작업 회사|고객사/;
const hits = [...all(DV_TEXT.list), ...all(DV_TEXT.source)].filter((t) => words.test(t));
for (const h of hits) console.log('  ' + h.slice(0, 120));
const control = words.test('운영 관리자 · 작업 회사 고객사 A · 파일 6건');
console.log(`board_words=${hits.length} control=${control}`);
process.exit(hits.length === 0 && control ? 0 : 1);
NODE
git show ":$W/entities/dataverify/config/text.ts" > "$T/text.ts"
node "$T/board.mjs" "$T/text.ts" ; mark

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
apps/web/scripts/planted-breaks-DV2b.sh > "$T/planted.log" 2>&1
grep -E '^  [BR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
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

say "[9] 데이터 검증 파일의 console.·localStorage·sessionStorage 0(주석 밖, + 양성 대조)"
hits="$(scan '\bconsole\.|localStorage|sessionStorage')"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: entities/session 엔 걸린다"
grep -rqE 'localStorage|sessionStorage' "$W/entities/session" ; mark

say "[10] 추적 diff 에 키 꼴·실재 기업명(금지어 목록)·.pdf·.docx·.xlsx·새 .json 0 · apps/api-py diff 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2b.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2b.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx)$')" ; mark
test -z "$(git diff --cached --name-only --diff-filter=A "$B" | grep -iE '\.json$')" ; mark
git diff --cached --quiet "$B" -- apps/api-py ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
