#!/usr/bin/env bash
# 밴드 AD2S 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-AD2S.sh --commit <1|2>
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/AD2S)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5389·5390).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5389}" WEB_TEST_PORT="${WEB_TEST_PORT:-5390}"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2) ;; *) echo "사용: $0 --commit <1|2>"; exit 2 ;; esac

B=1a45b1b
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

P='apps/web/src/pages/admin-ai-settings'
ALLOWED="$P/ui/AiSettingsScreen(\\.test)?\\.tsx|apps/web/e2e/(ai-settings|admin\\.spec)\\.ts|apps/web/scripts/(section4|planted-breaks)-AD2S\\.sh"
[ "$COMMIT" = 2 ] && ALLOWED="$ALLOWED|$P/hooks/(useSave|index)\\.ts|$P/model/(lines|refusal|index)\\.ts|$P/model/(lines|refusal)\\.test\\.ts|$P/ui/DetailCards\\.tsx"
ALLOWED="^($ALLOWED)\$"

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 목록 1-1(커밋 $COMMIT 까지), 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E "$ALLOWED")" ; mark
test -z "$(git status --porcelain | grep -v '^[AM] ')" ; mark

say "[2] 1-2 0줄"
git diff --cached --quiet "$B" -- apps/web/src/shared apps/web/src/widgets apps/web/src/app apps/web/src/entities \
  "$P/hooks/useAiSettings.ts" "$P/hooks/useDraft.ts" "$P/hooks/usePromptModel.ts" \
  apps/web/src/pages/greenwash-* apps/web/playwright.config.ts apps/api-py packages apps/web/package.json pnpm-lock.yaml ; mark

say "[3] 기존 시험의 - 줄 원문(「원본 요약 3」과 짝 — e2e/ai-settings.ts 의 시그니처·return 둘뿐)"
minus="$(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*' | grep '^-[^-]')"
echo "$minus"
echo "(- 줄 $(grep -c . <<< "$minus"))"
[ "$minus" = "-export async function fakeAiSettingApi(page: Page) {
-  return { calls, sent };" ] ; mark

say "[4] $P 의 entities import 는 entities/ai-setting/ 만 · model·hooks 가 config(문구 표)를 가져오지 않음(import 줄만)"
grep -rnE "from ['\"][^'\"]*entities/" "$P" | grep -v "entities/ai-setting/" ; test $? -eq 1 ; mark
if [ -d "$P/model" ] || [ -d "$P/hooks" ]; then
  grep -rnE "from ['\"][^'\"]*/config/" "$P/hooks" $( [ -d "$P/model" ] && echo "$P/model" ) ; test $? -eq 1 ; mark
fi

say "[5] 키 꼴 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다. 실재 기업명은 무늬로도 싣지 않는다 — 눈으로 본다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-AD2S.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark

say "[6] admin.spec.ts hunk 머리 하나(AD-02 나가기(AD2W ③) 끝 :720 뒤 · trapUnrouted 주석 앞)"
git diff --cached -U0 "$B" -- apps/web/e2e/admin.spec.ts | grep '^@@'
test "$(git diff --cached -U0 "$B" -- apps/web/e2e/admin.spec.ts | grep -c '^@@')" -eq 1 ; mark
git diff --cached -U0 "$B" -- apps/web/e2e/admin.spec.ts | grep -q '^@@ -721,0 ' ; mark

if [ "$COMMIT" = 1 ]; then want=10/10; else want=15/15; fi
say "[7] 심은 파손 ($want, FINGERPRINT=same)"
apps/web/scripts/planted-breaks-AD2S.sh --commit "$COMMIT" > "$T/planted.log" 2>&1
grep -E '^  P[0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
p="$(sed -n 's/^PLANTED=//p' "$T/planted.log")"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ "$p" = "$want" ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수)"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

if [ "$COMMIT" = 2 ]; then
  say "[9] AiSettingsScreen.tsx 줄 수(BASE 829 → 뒤) · 판을 만드는 부름(port.create)은 useSave.ts 한 곳"
  echo "BASE $(git show "$B:$P/ui/AiSettingsScreen.tsx" | wc -l | tr -d ' ') → $(wc -l < "$P/ui/AiSettingsScreen.tsx" | tr -d ' ')"
  # 주석 줄(//)은 뺀다 — 머리 주석이 port.create 를 글로 부른다.
  hits="$(git grep -n -E 'port\s*\.\s*create|\.create\(' -- "$P" ':!*.test.ts' ':!*.test.tsx' | grep -v -E '^[^:]+:[0-9]+:\s*//')"
  echo "$hits"
  [ "$(grep -c . <<< "$hits")" -eq 1 ] && grep -q "^$P/hooks/useSave.ts:" <<< "$hits" ; mark
fi

echo
echo "원시 출력: $T"
echo "SECTION4_FAIL=$fail"
