#!/usr/bin/env bash
# 밴드 ND1W 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-ND1W.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/ND1W)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5385·5386).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5385}" WEB_TEST_PORT="${WEB_TEST_PORT:-5386}"

B=fd613e0
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 목록 1-1, 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E '^apps/web/(src/(entities/run-log/(api/(server|server\.test|testing)\.ts|model/detail(\.test)?\.ts|config/text(\.test)?\.ts)|pages/admin-runs/ui/RunsScreen(\.test)?\.tsx)|e2e/(run-logs|admin\.spec)\.ts|scripts/(section4|planted-breaks)-ND1W\.sh)$')" ; mark
test -z "$(git status --porcelain | grep -v '^[AM] ')" ; mark

say "[2] 1-2 0줄(api-py·generated·shared·widgets·app·RunDetailDialog)"
git diff --cached --stat "$B" -- apps/api-py shared apps/web/src/shared apps/web/src/widgets apps/web/src/app apps/web/src/pages/admin-runs/ui/RunDetailDialog.tsx
git diff --cached --quiet "$B" -- apps/api-py shared apps/web/src/shared apps/web/src/widgets apps/web/src/app apps/web/src/pages/admin-runs/ui/RunDetailDialog.tsx ; mark

say "[3] 기존 시험의 - 줄 0"
git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep '^-[^-]'
test "$(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep -c '^-[^-]')" -eq 0 ; mark

say "[4] 심은 파손 (PLANTED=4/4, FINGERPRINT=same)"
apps/web/scripts/planted-breaks-ND1W.sh > "$T/planted.log" 2>&1
grep -E '^  P[0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
grep -q '^FINGERPRINT=same' "$T/planted.log" && grep -q '^PLANTED=4/4$' "$T/planted.log" ; mark

say "[5] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수, BASE 158 파일/2194 · 160)"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

say "[6] 키 꼴 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-ND1W.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark

echo
echo "원시 출력: $T"
echo "SECTION4_FAIL=$fail"
