#!/usr/bin/env bash
# 밴드 DV10 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV10.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 B = MD1 을 들인 병합 커밋(efe861db = main aa54d9d2 병합) — 이 밴드 커밋의 diff 만 센다. 가지(band/DV10)에서만 뜻이 있다.
# 땅: entities/dataverify/{config/text,model/checks}(.test).ts · pages/dataverify-result/** · 이 스크립트 둘. 0줄: shared · widgets · 서버 · package.json · lock.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

B=efe861db
W=apps/web/src
OUTDIR="$(cd .. && pwd)/DV10.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/dataverify/(config/text|model/checks)(\.test)?\.ts|pages/dataverify-result/.+)|scripts/(section4|planted-breaks)-DV10\.sh)$'

say "[0] B 는 HEAD 의 조상이고 MD1(aa54d9d2)을 품는다"
git merge-base --is-ancestor aa54d9d2 "$B" && git merge-base --is-ancestor "$B" HEAD ; mark

say "[1] 바뀐 파일(스테이징) ⊆ 데이터 검증 땅, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] shared·widgets·서버·의존 diff 0"
ZERO=(apps/api-py "$W/shared" "$W/widgets" "$W/app" packages apps/web/package.json pnpm-lock.yaml package.json)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark

say "[3] 「임시 꼴」 주석 0 · 화면에 <a 0 · RAW_BOX 0 (인덱스)"
R="$W/pages/dataverify-result/ui/ResultScreen.tsx"
test -z "$(git show ":$R" | grep -nE '임시 꼴|<a$|<a |RAW_BOX|whitespace-pre-wrap rounded')" ; mark

say "[4] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV10.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^       |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-220
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[5] 추적 diff 에 키 꼴·.pdf·.docx·.xlsx·.json 0 · 실제 주소는 example.* 만"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV10.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark
git diff --cached "$B" -- '*.test.ts' '*.test.tsx' | grep '^+' | grep -oE 'https?://[A-Za-z0-9.-]+' | sort -u | grep -vE '://(www\.)?example\.(com|org|net)$' ; test $? -eq 1 ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
