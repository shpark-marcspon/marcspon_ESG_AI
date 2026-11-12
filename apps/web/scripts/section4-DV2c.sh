#!/usr/bin/env bash
# 밴드 DV2c 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV2c.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV2c)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 20994·20995). 원시 출력은 워크트리 밖 DV2c.out/ 에.
# 땅(§1): entities/dataverify/config/text.ts · model/status.ts(주석) · pages/dataverify-{new,status,result,list} · e2e/dataverify-server(.spec).ts ·
#   이 스크립트 둘. 0줄: 서버 · shared · app · entities/session · 그린워싱·영문번역 땅.
# 「계산 Plan」은 엑셀 시트 이름을 말하는 글 둘(DV-00 「결과 엑셀」 줄 · DV-04 엑셀 카드)만 — 감독 회신(10-25, 발주서 셋을 둘로).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-20994}" WEB_TEST_PORT="${WEB_TEST_PORT:-20995}"

B=689e7182
W=apps/web/src
TEXT=$W/entities/dataverify/config/text.ts
OUTDIR="$(cd .. && pwd)/DV2c.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/(config/text(\.test)?\.ts|model/status\.ts)|pages/dataverify-(new|status|result|list)/.+)|e2e/dataverify-server(\.spec)?\.ts|scripts/(section4|planted-breaks)-DV2c\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1 수정 허용, 스테이징 밖 변경 0 · model/status.ts 는 주석만 · dataverify-list 는 시험만"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark
test -z "$(git diff --cached -U0 "$B" -- "$W/entities/dataverify/model/status.ts" | grep -E '^[-+][^-+]' | grep -vE '^[-+][[:space:]]*(//|/\*|\*)')" ; mark
test -z "$(git diff --cached --name-only "$B" -- "$W/pages/dataverify-list" | grep -vE '\.test\.tsx?$')" ; mark

say "[2] §1 0줄 구역(서버·shared·app·session·남의 땅·의존) diff 0"
ZERO=(apps/api-py "$W/shared" "$W/app" "$W/entities/session" "$W/widgets" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/entities/translation" "$W/pages/greenwash-"* "$W/pages/translation-"* apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark

say "[3] 기존 시험의 - 줄은 「계산 Plan」→「계산 계획」 낱말 바꿈뿐(원문 → DV2c.out/test-minus.txt)"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' apps/web/e2e | grep -E '^-[^-]' > "$T/test-minus.txt"
cp "$T/test-minus.txt" "$OUTDIR/test-minus.txt"
echo "minus=$(grep -c . "$T/test-minus.txt")"; cat "$T/test-minus.txt"
test -z "$(grep -v '계산 Plan' "$T/test-minus.txt")" ; mark

say "[4] text.ts 의 「계산 Plan」은 엑셀 시트 글 둘만 · 「계산 계획」이 화면 글에(+ 양성 대조: BASE 는 11)"
git show ":$TEXT" | grep -n '계산 Plan'
n="$(git show ":$TEXT" | grep -c '계산 Plan')"; m="$(git show ":$TEXT" | grep '계산 Plan' | grep -c '시트 7개')"
echo "plan=$n sheet=$m"
[ "$n" -eq 2 ] && [ "$m" -eq 2 ] ; mark
[ "$(git show "$B:$TEXT" | grep -c '계산 Plan')" -eq 11 ] ; mark

say "[5] 데이터 검증 웹에 옛 InfoIcon 0 · 안내 아이콘은 PageInfoIcon(+ 양성 대조: BASE StatusScreen 엔 걸린다)"
DV_FILES="$(git ls-files -- "$W/entities/dataverify" "$W/pages/dataverify-"* "$W/app/dataverify" | sort -u)"
hits="$(for f in $DV_FILES; do git show ":$f" | grep -nE '(^|[^A-Za-z])InfoIcon\b' | sed "s#^#$f:#"; done)"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
git show "$B:$W/pages/dataverify-status/ui/StatusScreen.tsx" | grep -qE '(^|[^A-Za-z])InfoIcon\b' ; mark
for f in "$W/pages/dataverify-status/ui/StatusScreen.tsx" "$W/pages/dataverify-result/ui/ResultScreen.tsx"; do
  echo "  $f: PageInfoIcon 쓰임 $(git show ":$f" | grep -c 'icon={<PageInfoIcon />}')"
done
[ "$(git show ":$W/pages/dataverify-status/ui/StatusScreen.tsx" | grep -c 'icon={<PageInfoIcon />}')" -eq 3 ] && [ "$(git show ":$W/pages/dataverify-result/ui/ResultScreen.tsx" | grep -c 'icon={<PageInfoIcon />}')" -eq 2 ] ; mark

say "[6] 이름 꼴 밖 오류 글은 판 글자 그대로 text.ts 한 곳 · NewScreen 이 그 열쇠로 그림 · 새 글은 이 한 줄뿐"
BAD='파일 이름에 쓸 수 없는 글자가 있거나 너무 길어요 · 이름을 고쳐 다시 올려 주세요'
[ "$(git grep --cached -c -F "$BAD" -- apps/web/src | grep -v '\.test\.' | cut -d: -f2 | paste -sd+ - | bc)" -eq 1 ] ; mark
git show ":$W/pages/dataverify-new/ui/NewScreen.tsx" | grep -q 'words.errors.badName' ; mark
git diff --cached -U0 "$B" -- "$TEXT" | grep -E '^\+[^+]' | grep -v '계산 계획' | tee "$T/text-plus.txt"
test -z "$(grep -v -F "$BAD" "$T/text-plus.txt" | grep -vE '^\+[[:space:]]*badName:$')" ; mark

say "[7] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV2c.sh > "$T/planted.log" 2>&1
grep -E '^  [CR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
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

say "[9] 추적 diff 에 키 꼴·금지어·.pdf·.docx·.xlsx·.json 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2c.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV2c.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
