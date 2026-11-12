#!/usr/bin/env bash
# 밴드 AD4X 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-AD4X.sh --commit <1|2|3>
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/AD4X)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5385·5386).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5385}" WEB_TEST_PORT="${WEB_TEST_PORT:-5386}"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "사용: $0 --commit <1|2|3>"; exit 2 ;; esac

B=e4db316
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 목록 1-1, 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E '^apps/web/(src/(entities/(run-log|audit-log)/|pages/admin-(runs|audit)/|app/admin/(AdminRoutes\.tsx|router\.test\.tsx))|e2e/((run-logs|audit)\.ts|admin\.spec\.ts)|scripts/(section4|planted-breaks)-AD4X\.sh)')" ; mark
test -z "$(git status --porcelain | grep -v '^[AM] ')" ; mark

say "[2] 1-2 0줄"
git diff --cached --quiet "$B" -- apps/web/src/shared apps/web/src/widgets apps/web/src/app/router.tsx apps/web/src/app/guards apps/web/src/app/admin/runtime.ts apps/api-py packages apps/web/package.json pnpm-lock.yaml ; mark

say "[3] AdminRoutes 는 AuditRoute 몫만 — hunk 머리(168 앞·189 뒤 0)"
git diff --cached -U0 "$B" -- apps/web/src/app/admin/AdminRoutes.tsx | grep '^@@'
git diff --cached -U0 "$B" -- apps/web/src/app/admin/AdminRoutes.tsx | sed -n 's/^@@ -\([0-9]*\)\(,\([0-9]*\)\)\{0,1\} .*/\1 \3/p' | awk '{ n = ($2 == "" ? 1 : $2); end = $1 + (n == 0 ? 0 : n - 1); if ($1 < 168 || end > 188) bad = 1 } END { exit bad }' ; mark

say "[4] 기존 시험의 - 줄 원문(보고의 「원본 요약 3」·감독 허락 표와 짝)"
git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep '^-[^-]'
echo "(- 줄 $(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep -c '^-[^-]'))"

say "[5] 그린워싱 import 0(import 줄만 — 주석의 선례 글은 뺀다)"
grep -rnE "from ['\"][^'\"]*entities/greenwash/" apps/web/src/entities/run-log apps/web/src/entities/audit-log apps/web/src/pages/admin-runs apps/web/src/pages/admin-audit ; test $? -eq 1 ; mark

say "[6] 키 꼴 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다. 실재 기업명은 무늬로도 싣지 않는다 — 눈으로 본다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-AD4X.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark

say "[7] 심은 파손 (① 5/5 · ② 8/8 · ③ 4/4, FINGERPRINT=same)"
apps/web/scripts/planted-breaks-AD4X.sh --commit "$COMMIT" > "$T/planted.log" 2>&1
grep -E '^  P[0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
p="$(sed -n 's/^PLANTED=//p' "$T/planted.log")"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && case "$COMMIT" in 1) want=5/5 ;; 2) want=8/8 ;; 3) want=4/4 ;; esac ; [ "$p" = "$want" ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수, BASE 152 파일/2015 · 154)"
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
