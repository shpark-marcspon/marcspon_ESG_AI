#!/usr/bin/env bash
# 밴드 AD4W 의 자기검증(발주서 §4 + critic 처분 R8).   사용: apps/web/scripts/section4-AD4W.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/AD4W)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5387·5388).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5387}" WEB_TEST_PORT="${WEB_TEST_PORT:-5388}"

B=6ded424
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

R='apps/web/src/entities/run-log'
P='apps/web/src/pages/admin-runs'
ALLOWED="^($R/model/(detail|index|run)\\.ts|$R/model/(detail|run)\\.test\\.ts|$R/config/text(\\.test)?\\.ts|$R/api/(server|index|testing)\\.ts|$R/api/server\\.test\\.ts|$P/ui/RunsScreen(\\.test)?\\.tsx|$P/ui/RunDetailDialog(\\.test)?\\.tsx|$P/hooks/(useRunDetail|index)\\.ts|apps/web/e2e/(run-logs\\.ts|admin\\.spec\\.ts)|apps/web/scripts/(section4|planted-breaks)-AD4W\\.sh)\$"

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 목록 1-1(파일 이름으로), 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E "$ALLOWED")" ; mark
test -z "$(git status --porcelain | grep -v '^[AM] ')" ; mark

say "[2] 1-2 0줄"
git diff --cached --quiet "$B" -- apps/web/src/shared apps/web/src/widgets apps/web/src/app apps/api-py packages apps/web/package.json pnpm-lock.yaml ; mark

say "[3] 기존 시험의 - 줄 원문(「원본 요약 3」과 짝)"
git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep '^-[^-]'
echo "(- 줄 $(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep -c '^-[^-]'))"

say "[4] 다른 entities import 0(import 줄만)"
grep -rnE "from ['\"][^'\"]*entities/(greenwash|audit-log|account)/" apps/web/src/entities/run-log apps/web/src/pages/admin-runs ; test $? -eq 1 ; mark

say "[5] 키 꼴 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다. 실재 기업명은 무늬로도 싣지 않는다 — 눈으로 본다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-AD4W.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark

say "[6] admin.spec.ts hunk 머리(:16 import · AD4X ② 끝과 AD-05 AI 설정 줄 사이 하나)"
git diff --cached -U0 "$B" -- apps/web/e2e/admin.spec.ts | grep '^@@'
test "$(git diff --cached -U0 "$B" -- apps/web/e2e/admin.spec.ts | grep -c '^@@')" -eq 2 ; mark

say "[7] 심은 파손 (13/13, FINGERPRINT=same)"
apps/web/scripts/planted-breaks-AD4W.sh > "$T/planted.log" 2>&1
grep -E '^  P[0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
p="$(sed -n 's/^PLANTED=//p' "$T/planted.log")"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ "$p" = 13/13 ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수, BASE 154 파일/2066 · 157)"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

echo
echo "원시 출력: $T"
echo "SECTION4_FAIL=$fail"
