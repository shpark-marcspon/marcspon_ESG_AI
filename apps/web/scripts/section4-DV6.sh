#!/usr/bin/env bash
# 밴드 DV6 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV6.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV6)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 23434·23436). 원시 출력은 워크트리 밖 DV6.out/ 에.
# 땅(§1): entities/dataverify/config/text.ts(DV-03·DV-04 칸 + DV-03 각주) · model/{explain,checks,status}.ts(+ 시험) · model/index.ts(공개 표면 한 낱말)
#   · pages/dataverify-{result,status} · 이 스크립트 둘. 0줄: 서버 · shared · generated · 다른 모듈 · pages/dataverify-new · edk.ts(DVX1 땅).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23434}" WEB_TEST_PORT="${WEB_TEST_PORT:-23436}"

B=4dd3b484
W=apps/web/src
TEXT=$W/entities/dataverify/config/text.ts
OUTDIR="$(cd .. && pwd)/DV6.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/(config/text(\.test)?\.ts|model/(explain|checks|status|index)(\.test)?\.ts)|pages/dataverify-(result|status)/.+)|e2e/dataverify[^/]*\.spec\.ts|scripts/(section4|planted-breaks)-DV6\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1 수정 허용, 스테이징 밖 변경 0 · model/index.ts 는 내보내기 한 줄"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark
[ "$(git diff --cached -U0 "$B" -- "$W/entities/dataverify/model/index.ts" | grep -cE '^[-+][^-+]')" -le 2 ] ; mark

say "[2] §1 0줄 구역(서버·shared·generated·다른 모듈·DVX1 땅·의존) diff 0"
ZERO=(apps/api-py "$W/shared" "$W/app" packages "$W/entities/session" "$W/widgets" "$W/entities/greenwash" "$W/entities/translation" "$W/entities/ghg" "$W/pages/dataverify-new" "$W/pages/dataverify-list" "$W/entities/dataverify/model/edk.ts" "$W/entities/dataverify/api" apps/web/package.json pnpm-lock.yaml package.json)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark

say "[3] 기존 시험의 - 줄은 글자 단언뿐 — 구조 단언(길이·null·속성·클래스·toEqual) 0 (원문 → DV6.out/test-minus.txt)"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' apps/web/e2e | grep -E '^-[^-]' > "$T/test-minus.txt"
cp "$T/test-minus.txt" "$OUTDIR/test-minus.txt"
echo "minus=$(grep -c . "$T/test-minus.txt")"; cat "$T/test-minus.txt"
test -z "$(grep -E 'toHaveLength|toBeNull|toHaveCount|getAttribute|className|toHaveCSS|toHaveClass|toEqual|querySelectorAll' "$T/test-minus.txt")" ; mark

say "[4] text.ts(인덱스) 에 「최대 횟수」「정해진 횟수」 0 · 「검사 n회」 0 (+ 양성 대조: BASE 는 걸린다)"
git show ":$TEXT" | grep -nE '최대 횟수|정해진 횟수|검사 \$\{|\}회|검증한 산식'
test -z "$(git show ":$TEXT" | grep -E '최대 횟수|정해진 횟수|검사 \$\{|\}회|검증한 산식')" ; mark
[ "$(git show "$B:$TEXT" | grep -cE '최대 횟수|정해진 횟수')" -ge 4 ] ; mark
test -z "$(for f in "$W/pages/dataverify-result/ui/ResultScreen.tsx" "$W/pages/dataverify-status/ui/StatusScreen.tsx"; do git show ":$f" | grep -nE '최대 횟수|정해진 횟수'; done)" ; mark

say "[5] text.ts 의 DV-02 칸(newCheck: … status:) 은 BASE 와 같다 — DVX1 땅"
block() { awk '/^  newCheck: \{/{on=1} /^  status: \{/{on=0} on'; }
diff <(git show "$B:$TEXT" | block) <(git show ":$TEXT" | block) ; mark

say "[6] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV6.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[7] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수) · 루트 --fast"
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

say "[8] 추적 diff 에 키 꼴·금지어·.pdf·.docx·.xlsx·.json 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV6.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV6.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
