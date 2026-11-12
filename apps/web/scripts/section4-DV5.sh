#!/usr/bin/env bash
# 밴드 DV5 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV5.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV5)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 23244·23246). 원시 출력은 워크트리 밖 DV5.out/ 에. SKIP_GATES=1 이면 [4] 게이트를 건너뛴다.
# 땅(§1 + 감독 회신 10-29 form.ts·form.test.ts): entities/dataverify/model/edk(.test).ts · pages/dataverify-new/ui/NewScreen(.test).tsx ·
#   pages/dataverify-new/model/form(.test).ts · entities/dataverify/config/text.ts · e2e/dataverify-server.spec.ts · 이 스크립트 둘.
#   0줄: 서버 전부 · shared · generated · 의존.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23244}" WEB_TEST_PORT="${WEB_TEST_PORT:-23246}"

B=568fb2cb
W=apps/web/src
OUTDIR="$(cd .. && pwd)/DV5.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/model/edk(\.test)?\.ts|pages/dataverify-new/ui/NewScreen(\.test)?\.tsx|pages/dataverify-new/model/form(\.test)?\.ts|entities/dataverify/config/text\.ts)|e2e/dataverify-server\.spec\.ts|scripts/(section4|planted-breaks)-DV5\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1 수정 허용, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄 구역(서버·shared·generated·packages·의존) diff 0"
ZERO=(apps/api-py "$W/shared" packages apps/web/package.json pnpm-lock.yaml package.json)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
gen="$(git ls-files | grep '/generated/' )"
if [ -n "$gen" ]; then git diff --cached --quiet "$B" -- $gen ; mark; else echo "generated 추적 파일 0"; true ; mark; fi

say "[3] text.ts 는 companyFilled 한 쌍(주석·글)만 더함 · 지운 줄 0"
git diff --cached -U0 "$B" -- "$W/entities/dataverify/config/text.ts" | grep -E '^[-+][^-+]' | tee "$T/text.txt"
test -z "$(grep -v -E '^\+    (/\*\* 서버 입력 꼴 파일·글의 회사 정보로|companyFilled: )' "$T/text.txt")" && [ "$(grep -c . "$T/text.txt")" -eq 2 ] ; mark

say "[3b] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV5.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

if [ "${SKIP_GATES:-0}" != 1 ]; then
say "[4] apps/web 게이트 (VERIFY=PASS)"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "(web verify $(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark
else say "[4] 게이트 건너뜀(SKIP_GATES=1)"; fi

say "[5] 추적 diff 에 키 꼴·.pdf·.docx·.xlsx·.json 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV5.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
