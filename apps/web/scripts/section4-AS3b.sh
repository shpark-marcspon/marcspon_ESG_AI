#!/usr/bin/env bash
# 밴드 AS3b 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-AS3b.sh --commit <1|2>
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B(= 워크트리 BASE, TR4 병합 — 37faeb3a..B 는 apps/web 0줄)가 박혀 있다 — 가지(band/AS3b)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5411·5412).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5411}" WEB_TEST_PORT="${WEB_TEST_PORT:-5412}"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2) ;; *) echo "사용: $0 --commit <1|2>"; exit 2 ;; esac

B=b644b054
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

W='apps/web'
S="$W/src"
E="$S/entities/ai-setting"
P="$S/pages/admin-ai-settings"
GS="$S/entities/greenwash-setting"
# 발주서 1-1(그린워싱 땅) + 1-2(허락 청 #1~#12). 경계 ② 는 흐름(flow.ts·FlowBand)과 slot index·화면 시험이 더 든다.
ALLOWED="$GS/model/(terms|index)\\.ts|$GS/model/terms\\.test\\.ts|$GS/api/(server|testing|index)\\.ts|$GS/api/server\\.test\\.ts"
ALLOWED="$ALLOWED|$GS/config/text(\\.test)?\\.ts|$GS/ui/[A-Za-z]+(\\.test)?\\.tsx?|$W/e2e/ai-settings-greenwash\\.spec\\.ts|$W/scripts/(section4|planted-breaks)-AS3b\\.sh"
ALLOWED="$ALLOWED|$E/model/slot\\.ts|$P/ui/AiSettingsScreen(\\.test)?\\.tsx|$E/config/text(\\.test)?\\.ts|$S/app/admin/ai-setting-modules(\\.test)?\\.ts"
ALLOWED="$ALLOWED|$S/app/admin/router\\.test\\.tsx|$S/app/guards/layers\\.test\\.ts|$W/e2e/admin\\.spec\\.ts|$W/e2e/ai-settings\\.ts"
[ "$COMMIT" -ge 2 ] && ALLOWED="$ALLOWED|$GS/model/flow(\\.test)?\\.ts|$E/model/index\\.ts"
ALLOWED="^($ALLOWED)\$"

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 1-1·허락 표(커밋 $COMMIT 까지), 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E "$ALLOWED")" ; mark
test -z "$(git status --porcelain | grep -v '^[AM] ')" ; mark

say "[2] 1-3 0줄(서버 · shared·widgets · 라우터 · 껍데기 hooks·model·DetailCards · E/api · 그린워싱 화면·슬라이스 · prompt-model 흉내 · 패키지)"
git diff --cached --quiet "$B" -- apps/api-py "$S/shared" "$S/widgets" "$S/app/router.tsx" "$S/app/admin/AdminRoutes.tsx" \
  "$P/hooks" "$P/model" "$P/ui/DetailCards.tsx" "$E/api" $S/pages/greenwash-* "$S/entities/greenwash" \
  "$W/e2e/greenwash-server.ts" "$W/e2e/ai-prompt-model.ts" packages "$W/package.json" pnpm-lock.yaml "$W/generated" ; mark

say "[3] 허락 줄 numstat(-w 따로) · 기존 시험 - 줄 지문"
PERMITTED=("$E/model/slot.ts" "$E/model/index.ts" "$P/ui/AiSettingsScreen.tsx" "$P/ui/AiSettingsScreen.test.tsx" "$E/config/text.ts" "$E/config/text.test.ts" \
  "$S/app/admin/ai-setting-modules.ts" "$S/app/admin/ai-setting-modules.test.ts" "$S/app/admin/router.test.tsx" "$S/app/guards/layers.test.ts" \
  "$W/e2e/admin.spec.ts" "$W/e2e/ai-settings.ts")
git diff --cached --numstat "$B" -- "${PERMITTED[@]}"
echo "(-w)"; git diff --cached -w --numstat "$B" -- "${PERMITTED[@]}"
minus="$(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' "$W/e2e/*" | grep '^-[^-]')"
echo "$minus" > "$T/minus.txt"
echo "(- 줄 $(grep -c . <<< "$minus") · 원문 $T/minus.txt)"
case "$COMMIT" in
  1) want_minus=4d3bd25e520fa760 ;;
  2) want_minus=d4687089deaf6534 ;;
esac
got_minus="$(shasum -a 256 < "$T/minus.txt" | cut -c1-16)"
echo "지문 $got_minus (기대 $want_minus)"
[ "$got_minus" = "$want_minus" ] ; mark

say "[4] 지운 it 셈(이름만 바뀐 셋 — ai-setting-modules.test.ts 둘·router.test.tsx 하나, 짝 없는 지움 0)"
gone="$(git diff --cached "$B" | grep -E '^-\s*(it|test)(\.each)?\(')"
echo "$gone"
echo "(지운 it $(grep -c . <<< "$gone") · 더한 it $(git diff --cached "$B" | grep -cE '^\+\s*(it|test)(\.each)?\('))"
[ "$(grep -c . <<< "$gone")" -eq 3 ] ; mark

say "[5] 껍데기(${P}·${E}) 제품 코드에 greenwash import 0 · GS/ui 는 entities/ai-setting·GS/api 를 가져오지 않음"
git grep -nE "from ['\"][^'\"]*greenwash" -- "$P" "$E" ':!*.test.ts' ':!*.test.tsx' ':!*/testing.ts' ; test $? -eq 1 ; mark
git grep -nE "from ['\"][^'\"]*(ai-setting/|\\.\\./api/)" -- "$GS/ui" ':!*.test.tsx' ':!*.test.ts' ; test $? -eq 1 ; mark
git grep -nE "TermsDraft" -- "$P" "$E" ; test $? -eq 1 ; mark

case "$COMMIT" in 1) want=10/10 ;; 2) want=14/14 ;; esac
say "[6] 심은 파손 ($want, FINGERPRINT=same)"
"$W/scripts/planted-breaks-AS3b.sh" --commit "$COMMIT" > "$T/planted.log" 2>&1
grep -E '^  Q[0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
p="$(sed -n 's/^PLANTED=//p' "$T/planted.log")"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ "$p" = "$want" ] ; mark

say "[7] tsc · lint(오류 0) · layers.test"
pnpm --filter @esg/web typecheck > "$T/tsc.log" 2>&1 ; mark
pnpm --filter @esg/web lint > "$T/lint.log" 2>&1 ; code=$? ; tail -1 "$T/lint.log" ; (exit $code) ; mark
pnpm --filter @esg/web exec vitest run src/app/guards/layers.test.ts > "$T/layers.log" 2>&1 ; code=$?
grep -E 'Tests  ' "$T/layers.log" ; (exit $code) ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수 — BASE 2545 · 165 웹 실측은 보고) · 루트 빠른 게이트"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
"$W/scripts/verify.sh" > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
(exit $code) ; mark
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

say "[9] 키 꼴 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다. 실재 기업명은 무늬로도 싣지 않는다 — 눈으로 본다)"
git diff --cached "$B" -- . ":!$W/scripts/section4-AS3b.sh" | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark

say "    apps/web numstat 합 · diff 지문(플랫폼-웹 e87939 에게)"
git diff --cached --numstat "$B" -- "$W" | awk '{a+=$1; d+=$2} END {print "+" a " -" d " (" NR " 파일)"}'
echo "diff $(git diff --cached "$B" -- "$W" | shasum -a 256 | cut -c1-16)"

echo
echo "원시 출력: $T"
echo "SECTION4_FAIL=$fail"
