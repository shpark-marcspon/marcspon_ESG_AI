#!/usr/bin/env bash
# 밴드 IRW2 웹 몫(②·③)의 자기검증(발주서 §4 — section4-IRW1.sh 꼴).   사용: apps/web/scripts/section4-IRW2.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B = git merge-base main HEAD(가지 band/IRW2 에서만 뜻이 있다). 서버 몫(①)은 커밋 ONE 까지 — 그 뒤 apps/api-py 는 0줄
# (서버 자기검증은 apps/api-py/scripts/section4-IRW2.sh). 포트는 WEB_PORT·WEB_TEST_PORT(기본 23274·23275). 해시는 워크트리 밖 IRW2.out/web-h4.*.
# 땅(§1-2 웹): entities/materiality(api·hooks·model·ui·config/text) · pages/materiality-{intro,new,list,result} · app/materiality ·
#   e2e/materiality-server(.spec).ts · 이 스크립트 둘 · 허락 H4 router.tsx · app/shell/moduleMenu(.test) · L 주석.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23274}" WEB_TEST_PORT="${WEB_TEST_PORT:-23275}"
unset OPENAI_API_KEY ANTHROPIC_API_KEY

B="$(git merge-base main HEAD)"
ONE="${ONE:-876b02a1}"
W=apps/web/src
L=$W/app/guards/layers.test.ts
H4R=$W/app/router.tsx
H4M=("$W/app/shell/moduleMenu.tsx" "$W/app/shell/moduleMenu.test.ts")
READER=apps/api-py/esgapi/materiality/tools/value_chain_xlsx.py
VC=$W/entities/materiality/model/valueChain.ts
OUTDIR="$(cd .. && pwd)/IRW2.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

STAGE="${STAGE:-}"
[ -z "$STAGE" ] && { if git diff --cached --quiet "$B" -- "$W/pages/materiality-list" "$W/pages/materiality-result"; then STAGE=2; else STAGE=3; fi; }
echo "경계 STAGE=$STAGE · B=$B · ONE=$ONE"

ALLOW='^apps/web/(src/(entities/materiality/(api|hooks|model|ui)/.+|entities/materiality/config/text(\.test)?\.ts|pages/materiality-(intro|new|list|result)/.+|app/materiality/(MaterialityRoutes\.tsx|runtime\.ts|router\.test\.tsx)|app/shell/moduleMenu(\.test)?\.tsx?|app/router\.tsx|app/guards/layers\.test\.ts)|e2e/materiality-server(\.spec)?\.ts|scripts/(section4|planted-breaks)-IRW2\.sh)$'

say "[1] 웹 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1-2 · ① 뒤 apps/api-py 0줄 · 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B" -- apps/web
outside="$(git diff --cached --name-only --no-renames "$B" -- apps/web | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
# ① 뒤 가지 자기 커밋(병합 밖)과 스테이징이 apps/api-py·docs 를 건드리지 않는다(감독이 main 을 가지에 병합하면 그 몫은 main 것 — 10-28).
#   이 밴드 제 스크립트(apps/api-py/scripts/{section4,planted-breaks}-IRW2.sh)는 뺀다.
SRV=(apps/api-py docs ':!apps/api-py/scripts/section4-IRW2.sh' ':!apps/api-py/scripts/planted-breaks-IRW2.sh')
git log --oneline --no-merges --first-parent "$ONE"..HEAD -- "${SRV[@]}" ; git diff --cached --stat HEAD -- "${SRV[@]}"
test -z "$(git log --no-merges --first-parent --format=%h "$ONE"..HEAD -- "${SRV[@]}")" && git diff --cached --quiet HEAD -- "${SRV[@]}" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄 구역 · H4 의 - 줄·sha256·numstat(→ IRW2.out/web-h4*.diff.*)"
ZERO=("$W/shared" "$W/widgets" "$W/entities/session" "$W/entities/greenwash" "$W/entities/greenwash-setting" "$W/entities/translation" "$W/entities/translation-setting" "$W/entities/dataverify" "$W/entities/ai-setting" "$W/pages/greenwash-"* "$W/pages/translation-"* "$W/pages/dataverify-"* "$W/pages/admin-"* "$W/pages/materiality-status" "$W/app/auth" "$W/app/admin" "$W/app/greenwash" "$W/app/translation" "$W/app/dataverify" apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- apps/web/e2e | grep -v -E '^apps/web/e2e/materiality-server(\.spec)?\.ts$')" ; mark
over=0
hdiff() { # <이름> <청 -> <청 +> <경로들…>
  local n="$1" am="$2" ap="$3"; shift 3
  git diff --cached "$B" -- "$@" > "$OUTDIR/web-$n.diff"
  git diff --cached --numstat "$B" -- "$@" > "$OUTDIR/web-$n.diff.numstat"
  local minus plus
  minus="$(awk '{ s += $2 } END { print s + 0 }' "$OUTDIR/web-$n.diff.numstat")"
  plus="$(awk '{ s += $1 } END { print s + 0 }' "$OUTDIR/web-$n.diff.numstat")"
  local verdict=안
  [ "$minus" -gt $(( am * 3 / 2 + 1 )) ] && verdict=넘침
  [ "$plus" -gt $(( ap * 3 / 2 + 1 )) ] && verdict=넘침
  [ "$verdict" = 안 ] || over=$((over + 1))
  echo "  $n -$minus/+$plus (청 -$am/+$ap · ±50% $verdict)"
  for each in "$@"; do
    [ -f "$each" ] || continue
    echo "    $(git diff --cached --numstat "$B" -- "$each" | cut -f1,2 | tr '\t' '/') $each sha256=$(git diff --cached "$B" -- "$each" | shasum -a 256 | cut -c1-16)"
  done
}
hdiff h4-router 2 14 "$H4R"
if [ "$STAGE" = 3 ]; then
  hdiff h4-menu 5 10 "${H4M[@]}"
  hdiff h4-layers 3 3 "$L"
else
  echo "  ② : moduleMenu·L 0줄"
  git diff --cached --quiet "$B" -- "${H4M[@]}" "$L" ; mark
fi
test "$over" -eq 0 ; mark
echo "  H4 의 - 줄 전부(원문):"
cat "$OUTDIR"/web-h4*.diff | grep '^-[^-]' | tee "$OUTDIR/web-h4-minus.txt" | sed 's/^/    /'

say "[3] 기존 시험의 - 줄(H4 밖) — 원문(보고에 그대로): IRW1 제 시험은 Q9·m4 갈래만, 그 밖은 0"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' '*.spec.ts' ":!$L" ":!${H4M[1]}" | grep -E '^(\+\+\+|-[^-])' > "$T/test-minus.txt"
sed 's/^/    /' "$T/test-minus.txt"
echo "  - 줄 수: $(grep -c '^-' "$T/test-minus.txt")"
cp "$T/test-minus.txt" "$OUTDIR/web-test-minus.txt"
# ② 에서 허락한 - 줄은 text.test.ts 의 「비용」 검사 한 줄(판 IR-00 글 — 보고 물을 거리)뿐.
# ③ 은 더해 IRW1 제 시험의 Q9·m4·N2 갈래 9(ListScreen.test 머리 주석 둘·setup 인자 한 줄·W2 줄바꿈 칸 수 한 줄 ·
#   e2e 머리 주석 한 줄·빈 목록 시험 넷 — 원문은 보고) = 10.
[ "$STAGE" = 3 ] && ok_minus=10 || ok_minus=1
test "$(grep -c '^-' "$T/test-minus.txt")" -le "${TEST_MINUS_OK:-$ok_minus}" ; mark

IR_FILES="$(git ls-files -- "$W/entities/materiality" "$W/pages/materiality-"* "$W/app/materiality"; git diff --cached --name-only --diff-filter=A "$B" -- "$W/entities/materiality" "$W/pages/materiality-"* "$W/app/materiality")"
IR_FILES="$(sort -u <<< "$IR_FILES" | grep .)"
echo "중대성평가 파일 $(grep -c . <<< "$IR_FILES")개"
scan() { for f in $IR_FILES; do git show ":$f" 2>/dev/null | grep -nE "$1" | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' | sed "s#^#$f:#"; done; }

say "[4] 중대성평가 파일의 fetch(·XMLHttpRequest·msw·남의 모듈 땅(translation 포함) 0(+ 양성 대조)"
FORBID="entities/(greenwash|translation|dataverify)|pages/(greenwash|translation|dataverify)-|\bfetch\(|XMLHttpRequest|\bmsw\b"
hits="$(scan "$FORBID")"; [ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
grep -qE "$FORBID" "$W/app/dataverify/DataverifyRoutes.tsx" ; mark

say "[5] ui·model·api·hooks·화면·app 의 한국어 글자 줄 0(주석 밖 — config/text.ts·model/wire.ts·시험·testing.ts 밖, valueChain.ts 는 열 이름 다섯 줄만)"
cat > "$T/hangul.mjs" <<'NODE'
import { execFileSync } from 'node:child_process';
const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
const HEADER = /^'(사업 부문|사업 내용|밸류체인|이해관계자|관련 비즈니스 활동)',$/;
let n = 0;
for (const file of process.argv.slice(2)) {
  strip(execFileSync('git', ['show', `:${file}`], { encoding: 'utf8' })).split('\n').forEach((line, i) => {
    if (!/[가-힣]/.test(line)) return;
    if (file.endsWith('/model/valueChain.ts') && HEADER.test(line.trim())) return;
    n++; console.log(`${file}:${i + 1}: ${line.trim()}`);
  });
}
console.log(`hangul_lines=${n}`);
process.exit(n === 0 ? 0 : 1);
NODE
CODE="$(grep -vE '\.test\.tsx?$|/config/text\.ts$|/model/wire\.ts$|/testing\.ts$' <<< "$IR_FILES" | grep .)"
node "$T/hangul.mjs" $CODE ; mark
! node "$T/hangul.mjs" "$W/entities/materiality/model/wire.ts" > /dev/null ; mark
echo "  valueChain.ts 의 열 이름 줄: $(git show ":$VC" | grep -cE "^  '(사업 부문|사업 내용|밸류체인|이해관계자|관련 비즈니스 활동)',$")"

say "[6] 상한 여섯(50·200·20·50·200 · 100)이 서버 읽개·valueChain.ts 두 곳에서 같다 · 열 이름 다섯 같다"
srv_chars="$(grep -E '^MAX_CHARS: Final = ' "$READER" | sed -E 's/.*\((.*)\).*/\1/' | tr -d ' ')"
srv_rows="$(grep -E '^MAX_DATA_ROWS: Final = ' "$READER" | sed -E 's/.*= *//')"
web_chars="$(git show ":$VC" | grep -E 'VALUE_CHAIN_MAX_CHARS = ' | sed -E 's/.*\[(.*)\].*/\1/' | tr -d ' ')"
web_rows="$(git show ":$VC" | grep -E 'VALUE_CHAIN_MAX_ROWS = ' | sed -E 's/.*= *([0-9]+).*/\1/')"
echo "  서버 $srv_chars · $srv_rows | 웹 $web_chars · $web_rows"
[ "$srv_chars" = "50,200,20,50,200" ] && [ "$srv_chars" = "$web_chars" ] && [ "$srv_rows" = 100 ] && [ "$srv_rows" = "$web_rows" ] ; mark
srv_head="$(grep -E '^HEADER: Final = ' "$READER" | sed -E 's/.*\((.*)\).*/\1/' | tr -d '" ')"
web_head="$(git show ":$VC" | sed -n '/VALUE_CHAIN_HEADER = \[/,/\] as const/p' | grep -E "^  '" | tr -d "', \n")"
echo "  서버 $srv_head | 웹 $web_head"
[ -n "$srv_head" ] && [ "$(tr -d ',' <<< "$srv_head")" = "$web_head" ] ; mark

say "[7] console.·localStorage·sessionStorage·dangerouslySetInnerHTML 0(주석 밖)"
hits="$(scan '\bconsole\.|localStorage|sessionStorage|dangerouslySetInnerHTML')"; [ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark

say "[8] 웹 몫 추적 diff(기준 B — 서버 몫은 apps/api-py/scripts/section4-IRW2.sh [12])에 키 꼴·실재 기업명(금지어 목록)·.xlsx·새 .json 0"
git diff --cached "$B" -- apps/web ':!apps/web/scripts/section4-IRW2.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- apps/web ':!apps/web/scripts/section4-IRW2.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" -- apps/web | grep -iE '\.(pdf|docx|xlsx)$')" ; mark
test -z "$(git diff --cached --name-only --diff-filter=A "$B" -- apps/web | grep -iE '\.json$')" ; mark

say "[9] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-IRW2.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=|^LATER=' "$T/planted.log" | cut -c1-170
cp "$T/planted.log" "$OUTDIR/web-planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[10] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수)"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "(web verify $(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark

echo
echo "원시 출력: $T · 해시: $OUTDIR"
echo "SECTION4_FAIL=$fail"
