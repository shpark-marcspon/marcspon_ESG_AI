#!/usr/bin/env bash
# 밴드 DV2d 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV2d.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV2d)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 23614·23615). 원시 출력은 워크트리 밖 DV2d.out/ 에. SKIP_GATES=1 이면 [8] 게이트를 건너뛴다(빠른 확인용).
# 땅(§1): entities/dataverify/api/** · pages/dataverify-new/** · pages/dataverify-(status|result) 시험(rerun 본문 launchKey 단언 — 감독 회신 10-25) · app/dataverify/router.test.tsx · e2e/dataverify-server(.spec).ts · 이 스크립트 둘.
#   0줄: 서버 · shared · app(데이터 검증 router.test 밖) · entities/session · 그린워싱·영문번역 땅 · 의존.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23614}" WEB_TEST_PORT="${WEB_TEST_PORT:-23615}"

B=13ceba3f
W=apps/web/src
ROUTER=$W/app/dataverify/router.test.tsx
SERVER=$W/entities/dataverify/api/server.ts
OUTDIR="$(cd .. && pwd)/DV2d.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/api/.+|pages/dataverify-new/.+|pages/dataverify-(status|result)/ui/[A-Za-z]+Screen\.test\.tsx|app/dataverify/router\.test\.tsx)|e2e/dataverify-server(\.spec)?\.ts|scripts/(section4|planted-breaks)-DV2d\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1 수정 허용, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] §1 0줄 구역(서버·shared·app(router.test 밖)·session·남의 땅·의존) diff 0"
ZERO=(apps/api-py "$W/shared" "$W/app" ":!$ROUTER" "$W/entities/session" "$W/widgets" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/entities/translation" "$W/pages/greenwash-"* "$W/pages/translation-"* ":!$W/pages/dataverify-status/**/*.test.tsx" ":!$W/pages/dataverify-result/**/*.test.tsx" "$W/pages/dataverify-status" "$W/pages/dataverify-result" "$W/pages/dataverify-list" apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark

say "[3] 기존 시험·e2e 의 - 줄은 본문 열쇠 목록에 launchKey 를 더하는 갈음뿐(원문 → DV2d.out/test-minus.txt)"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' apps/web/e2e | grep -E '^-[^-]' > "$T/test-minus.txt"
cp "$T/test-minus.txt" "$OUTDIR/test-minus.txt"
echo "minus=$(grep -c . "$T/test-minus.txt")"; cat "$T/test-minus.txt"
# 갈음 하나 더(감독 회신 10-25): e2e 「성공 뒤 새 누름」의 두 본문 통째 같음 → launchKey 뺀 본문 같음 + launchKey 다름.
test -z "$(grep -v -E "module·options|'module', 'options'|'module,options'" "$T/test-minus.txt" | grep -v -F -x -- '-  expect(api.posts()[0]!.body).toEqual(api.posts()[1]!.body);')" ; mark
say "[3b] DV-03·04 시험(감독 회신 10-25로 §1 에 더함)은 + 줄만 · launchKey 단언뿐"
git diff --cached -U0 "$B" -- "$W/pages/dataverify-status" "$W/pages/dataverify-result" | grep -E '^[-+][^-+]' | tee "$T/dv34.txt"
test "$(grep -c '^-' "$T/dv34.txt")" -eq 0 ; mark
test -z "$(grep -v -E 'launchKey: expect\.stringMatching\($|^\+ +/\^\[0-9a-f\]\{8\}-.*\$/,$|^\+ +\),$' "$T/dv34.txt")" ; mark

say "[4] router.test.tsx: - 줄 0 · 새 expect 0 (예열 beforeAll 만 더함)"
git diff --cached -U0 "$B" -- "$ROUTER" | grep -E '^[-+][^-+]' > "$T/router.txt"
echo "minus=$(grep -c '^-' "$T/router.txt") plus=$(grep -c '^+' "$T/router.txt")"
test "$(grep -c '^-' "$T/router.txt")" -eq 0 ; mark
test "$(grep -c 'expect(' "$T/router.txt")" -eq 0 ; mark
grep -q 'loadRouteChunk' "$T/router.txt" ; mark

say "[5] 새 의존 0 · 새 import 줄 0(시험 밖) · launchKey 는 크기 셈(isTooLarge) 밖"
git diff --cached -U0 "$B" -- apps/web/src ':!*.test.ts' ':!*.test.tsx' | grep -E '^\+import' ; test $? -eq 1 ; mark
git show ":$SERVER" | grep -n 'isTooLarge(' | tee "$T/large.txt"
test -z "$(grep 'launchKey' "$T/large.txt")" && [ "$(grep -c 'isTooLarge(options)' "$T/large.txt")" -eq 2 ] ; mark

say "[6] router.test.tsx 만 10번 반복 = 10/10 (부하 그대로 — uptime 을 적는다)"
uptime | tee "$OUTDIR/router-repeat-uptime.txt"
ok=0
for i in 1 2 3 4 5 6 7 8 9 10; do
  start=$(date +%s)
  if pnpm --filter @esg/web exec vitest run src/app/dataverify/router.test.tsx > "$T/router-$i.log" 2>&1; then ok=$((ok + 1)); r=pass; else r=FAIL; cp "$T/router-$i.log" "$OUTDIR/router-repeat-$i.log"; fi
  echo "  $i $r $(( $(date +%s) - start ))s · $(uptime | sed -E 's/.*load averages?: //')"
done | tee "$T/repeat.txt"
ok="$(grep -c ' pass ' "$T/repeat.txt")"
cp "$T/repeat.txt" "$OUTDIR/router-repeat.txt"
echo "ROUTER_REPEAT=$ok/10"
test "$ok" -eq 10 ; mark

say "[7] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV2d.sh > "$T/planted.log" 2>&1
grep -E '^  [ERX][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

if [ "${SKIP_GATES:-0}" != 1 ]; then
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
else say "[8] 게이트 건너뜀(SKIP_GATES=1)"; fi

say "[9] 추적 diff 에 키 꼴·금지어·.pdf·.docx·.xlsx·.json 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2d.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2d.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
