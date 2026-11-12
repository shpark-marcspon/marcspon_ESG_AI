#!/usr/bin/env bash
# 밴드 AP1W 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-AP1W.sh --commit <1|2|3>
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B(= AP1b 병합)가 박혀 있다 — 가지(band/AP1W)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5407·5408).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5407}" WEB_TEST_PORT="${WEB_TEST_PORT:-5408}"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "사용: $0 --commit <1|2|3>"; exit 2 ;; esac

B=f386c13d
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

W='apps/web'
S="$W/src"
E="$S/entities/ai-setting"
P="$S/pages/admin-ai-settings"
SU="$S/shared/ui/ai-setting"
# 발주서 1-1(경계까지 누적). AP1b 가 더한 웹 시험은 server.test.ts 안이라 따로 없다(★1).
ALLOWED="$E/model/(slot|draft|fields|index)\\.ts|$E/model/(draft|fields)\\.test\\.ts|$E/api/(server|testing)\\.ts|$E/api/server\\.test\\.ts"
ALLOWED="$ALLOWED|$P/model/(lines|refusal)\\.ts|$P/model/(lines|refusal)\\.test\\.ts|$P/hooks/useSave\\.ts"
ALLOWED="$ALLOWED|$P/ui/(AiSettingsScreen|DetailCards)\\.tsx|$P/ui/AiSettingsScreen\\.test\\.tsx|$W/e2e/ai-prompt-model\\.ts|$W/scripts/(section4|planted-breaks)-AP1W\\.sh"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED|$SU/ui/(ModelCard|SaveDialog)\\.tsx|$SU/index\\.ts|$E/config/text(\\.test)?\\.ts|$P/model/index\\.ts|$P/hooks/useDraft\\.ts|$S/app/admin/ai-setting-modules(\\.test)?\\.ts"
[ "$COMMIT" -ge 3 ] && ALLOWED="$ALLOWED|$P/model/index\\.test\\.ts|$S/app/guards/layers\\.test\\.ts"
ALLOWED="^($ALLOWED)\$"

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 목록 1-1(커밋 $COMMIT 까지), 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E "$ALLOWED")" ; mark
test -z "$(git status --porcelain | grep -v '^[AM] ')" ; mark

say "[2] 1-2 0줄"
if [ "$COMMIT" = 1 ]; then SHARED=("$S/shared"); else
  SHARED=("$S/shared" ":!$SU/ui/ModelCard.tsx" ":!$SU/ui/SaveDialog.tsx" ":!$SU/index.ts"); fi
git diff --cached --quiet "$B" -- apps/api-py "${SHARED[@]}" "$S/widgets" "$S/app/router.tsx" "$S/app/admin/AdminRoutes.tsx" \
  "$S/app/admin/router.test.tsx" "$S/entities/greenwash" "$S/entities/greenwash-setting" $S/pages/greenwash-* \
  "$P/hooks/useAiSettings.ts" "$P/hooks/usePromptModel.ts" "$W/e2e/admin.spec.ts" "$W/e2e/ai-settings.ts" \
  packages "$W/package.json" pnpm-lock.yaml ; mark

say "[3] <BASE>.. 누적 diff 의 기존 시험 - 줄(answers 「기존 시험 고침 표」 ①~$COMMIT — 줄은 보고에 표로 짝지음, 여기서는 지문)"
minus="$(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' "$W/e2e/*" | grep '^-[^-]')"
echo "$minus" > "$T/minus.txt"
echo "(- 줄 $(grep -c . <<< "$minus") · 원문 $T/minus.txt)"
case "$COMMIT" in
  1) want_minus=c615afff179078cb ;;
  2) want_minus=7474b9787dd2d243 ;;
  3) want_minus=305f48d2841dd5f5 ;;
esac
got_minus="$(shasum -a 256 < "$T/minus.txt" | cut -c1-16)"
echo "지문 $got_minus (기대 $want_minus)"
[ "$got_minus" = "$want_minus" ] ; mark

say "[4] @2·AP1b 손 줄 흔적 0(@2 글자는 server.test.ts 의 「@2 답 → failed」 거짓 사례만 — §3-1)"
git grep -nE "AiPromptModel'|AiPromptStep|PromptStep|fromV3|isPromptModel3" -- "$S" "$W/e2e" ; test $? -eq 1 ; mark
git grep -nE "ai\\.prompt-model@2" -- "$S" "$W/e2e" ":!$E/api/server.test.ts" ; test $? -eq 1 ; mark

say "[5] ${P}·${E} 제품 코드(시험·testing.ts 뺌)에 greenwash import 0 · judge|translate 글자 0"
git grep -nE "from ['\"][^'\"]*greenwash" -- "$P" "$E" ':!*.test.ts' ':!*.test.tsx' ':!*/testing.ts' ; test $? -eq 1 ; mark
git grep -nE "judge|translate" -- "$P" "$E" ':!*.test.ts' ':!*.test.tsx' ':!*/testing.ts' ; test $? -eq 1 ; mark

say "[6] ${P} 의 entities import 는 entities/ai-setting/ 만 · model·hooks 가 config(문구 표)를 가져오지 않음"
grep -rnE "from ['\"][^'\"]*entities/" "$P" | grep -v "entities/ai-setting/" ; test $? -eq 1 ; mark
grep -rnE "from ['\"][^'\"]*/config/" "$P/hooks" "$P/model" ; test $? -eq 1 ; mark

case "$COMMIT" in 1) want=7/7 ;; 2) want=13/13 ;; 3) want=25/25 ;; esac
say "[7] 심은 파손 ($want, FINGERPRINT=same)"
"$W/scripts/planted-breaks-AP1W.sh" --commit "$COMMIT" > "$T/planted.log" 2>&1
grep -E '^  P[0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
p="$(sed -n 's/^PLANTED=//p' "$T/planted.log")"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ "$p" = "$want" ] ; mark

say "[8] tsc · lint(오류 0) · layers.test"
pnpm --filter @esg/web typecheck > "$T/tsc.log" 2>&1 ; mark
pnpm --filter @esg/web lint > "$T/lint.log" 2>&1 ; code=$? ; tail -1 "$T/lint.log" ; (exit $code) ; mark
pnpm --filter @esg/web exec vitest run src/app/guards/layers.test.ts > "$T/layers.log" 2>&1 ; code=$?
grep -E 'Tests  ' "$T/layers.log" ; (exit $code) ; mark

say "[9] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수 — BASE 2454 · 165) · 루트 빠른 게이트"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
"$W/scripts/verify.sh" > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
(exit $code) ; mark
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

say "[10] 키 꼴 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다. 실재 기업명은 무늬로도 싣지 않는다 — 눈으로 본다)"
git diff --cached "$B" -- . ":!$W/scripts/section4-AP1W.sh" | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark

say "    AiSettingsScreen.tsx 줄 수(BASE → 뒤) · port.create 는 useSave.ts 한 곳"
echo "BASE $(git show "$B:$P/ui/AiSettingsScreen.tsx" | wc -l | tr -d ' ') → $(wc -l < "$P/ui/AiSettingsScreen.tsx" | tr -d ' ')"
hits="$(git grep -n -E 'port\s*\.\s*create|\.create\(' -- "$P" ':!*.test.ts' ':!*.test.tsx' | grep -v -E '^[^:]+:[0-9]+:\s*(//|\*)')"
echo "$hits"
[ "$(grep -c . <<< "$hits")" -eq 1 ] && grep -q "^$P/hooks/useSave.ts:" <<< "$hits" ; mark

echo
echo "원시 출력: $T"
echo "SECTION4_FAIL=$fail"
