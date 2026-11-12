#!/usr/bin/env bash
# 밴드 TRW0a 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-TRW0a.sh [--commit 1|2]
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/TRW0a)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# --commit 1 = ① 경계(공통 올림·layers ① 줄), 2 = ② 경계(① + 새 번역 입력). 기본 2.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 23874·23875). 해시·numstat 은 워크트리 밖 TRW0a.out/ 에.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23874}" WEB_TEST_PORT="${WEB_TEST_PORT:-23875}"

COMMIT=2
[ "${1:-}" = "--commit" ] && COMMIT="${2:-2}"
B=4e28a54
W=apps/web/src
OUTDIR="$(cd .. && pwd)/TRW0a.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

# 1-2 수정 허용(① 몫, ② 몫).
ALLOW1='^apps/web/(src/(shared/ui/(step-flow|load-failure|risk-badge)/(index\.ts|ui/(StepFlow|LoadFailure|RiskBadge)(\.test)?\.tsx)|shared/ui/download-button/(index\.ts|ui/DownloadButton(\.test)?\.tsx)|shared/ui/text(\.test)?\.ts|shared/lib/(saveBlob(\.test)?|time)\.ts|entities/greenwash/ui/((StepFlow|LoadFailure|RiskBadge|ExcelButton)\.tsx|index\.ts|(badges|design-fixes|load-failure)\.test\.tsx)|entities/greenwash/model/(time|index|results\.test|failure\.test)\.ts|pages/admin-runs/ui/(saveFile(\.test)?\.ts|RunsScreen\.tsx)|app/guards/layers\.test\.ts)|scripts/(section4|planted-breaks)-TRW0a\.sh)$'
ALLOW2='^apps/web/src/(entities/translation/(model|config)/[^/]+\.tsx?|pages/translation-new/(index\.ts|(model|ui)/[^/]+\.tsx?))$'
if [ "$COMMIT" = 1 ]; then ALLOW="$ALLOW1"; else ALLOW="($ALLOW1)|($ALLOW2)"; fi

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1-2 의 경계 몫(--commit $COMMIT), 스테이징 밖 변경 0, entities/translation/ui 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark
test ! -e "$W/entities/translation/ui" ; mark

say "[2] §1-3 0줄 목록 diff 0"
ZERO=("$W/pages/greenwash-"* "$W/app/greenwash" "$W/entities/greenwash/api" "$W/entities/greenwash/hooks" "$W/entities/greenwash/config" "$W/pages/demo-parts" "$W/widgets" "$W/shared/api" "$W/shared/ui/ai-setting" "$W/shared/ui/app-shell" "$W/shared/ui/button" "$W/shared/ui/card" "$W/shared/ui/data-table" "$W/shared/ui/dialog" "$W/shared/ui/empty" "$W/shared/ui/file-dropzone" "$W/shared/ui/filter-select" "$W/shared/ui/header-greeting" "$W/shared/ui/load-skeleton" "$W/shared/ui/page-info" "$W/shared/ui/required-mark" apps/api-py apps/web/e2e apps/web/package.json pnpm-lock.yaml packages apps/web/playwright.config.ts)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
# app/** 는 L 밖 0, 그린워싱 model 은 index·시험 둘·time 밖 0
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/app" | grep -v '^apps/web/src/app/guards/layers\.test\.ts$')" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/entities/greenwash/model" | grep -v -E '/model/(index|time|results\.test|failure\.test)\.ts$')" ; mark

say "[3] 옮긴 몸 대조(BASE 옛 자리 ↔ 인덱스의 shared 새 자리, 허락 차이만 지운 뒤 diff 0)"
cat > "$T/norm.mjs" <<'NODE'
// 허락 차이(§4-3)만 지운다: 맨 앞 // 머리말 덩어리 · import 문 · GW_TEXT/PARTS_TEXT 줄 · StepFlow steps?/label? → 필수와 그 JSDoc ·
// ExcelButton → DownloadButton · 지역 saveBlob 몸(ExcelButton).
import { readFileSync } from 'node:fs';
const [file, kind] = process.argv.slice(2);
let s = readFileSync(file, 'utf8');
const lines = s.split('\n');
while (lines.length && (lines[0].startsWith('//') || lines[0] === '')) lines.shift();
s = lines.join('\n');
s = s.replace(/^import[\s\S]*?;\n/gm, '');
s = s.replace(/\/\*\* Blob 을 이 탭에서[\s\S]*?\n}\n\n/, '');
s = s.replace(/ExcelButton/g, 'DownloadButton');
if (kind === 'step') {
  s = s.replace(/^ *\/\*\* (단계 이름|목록의 이름)[^\n]*\n/gm, '');
  s = s.replace(/^( *)(steps|label)\?:/gm, '$1$2:');
  s = s.replace(/^ *(steps|label),\n/gm, '');
}
s = s.split('\n').filter((line) => !/GW_TEXT|PARTS_TEXT/.test(line)).join('\n');
process.stdout.write(s);
NODE
body() { # <옛 경로(BASE)> <새 경로(인덱스)> <kind>
  git show "$B:$1" > "$T/old" ; git show ":$2" > "$T/new"
  node "$T/norm.mjs" "$T/old" "$3" > "$T/old.n" ; node "$T/norm.mjs" "$T/new" "$3" > "$T/new.n"
  echo "  $2 ← $1 : 뺀 뒤 $(wc -l < "$T/new.n" | tr -d ' ')줄"
  diff "$T/old.n" "$T/new.n"
}
body $W/entities/greenwash/ui/StepFlow.tsx $W/shared/ui/step-flow/ui/StepFlow.tsx step ; mark
body $W/entities/greenwash/ui/LoadFailure.tsx $W/shared/ui/load-failure/ui/LoadFailure.tsx - ; mark
body $W/entities/greenwash/ui/RiskBadge.tsx $W/shared/ui/risk-badge/ui/RiskBadge.tsx - ; mark
body $W/entities/greenwash/ui/ExcelButton.tsx $W/shared/ui/download-button/ui/DownloadButton.tsx - ; mark
body $W/pages/admin-runs/ui/saveFile.ts $W/shared/lib/saveBlob.ts - ; mark
body $W/pages/admin-runs/ui/saveFile.test.ts $W/shared/lib/saveBlob.test.ts - ; mark
body $W/entities/greenwash/model/time.ts $W/shared/lib/time.ts - ; mark
# ExcelButton 의 지역 saveBlob 은 지움(두 벌 0) — shared/lib 의 것을 부른다
! git show ":$W/shared/ui/download-button/ui/DownloadButton.tsx" | grep -q 'export function saveBlob' && git show ":$W/shared/ui/download-button/ui/DownloadButton.tsx" | grep -q "from '../../../lib/saveBlob.ts'" ; mark

say "[4] 그린워싱 diff(a2 ⓐ): import·export 문 밖 0(감싸개 둘·RiskBadge.tsx 밖), 시험의 expect( 줄 = BASE"
cat > "$T/strip.mjs" <<'NODE'
// import·export … from 문(여러 줄 포함)을 지운 나머지.
import { readFileSync } from 'node:fs';
const s = readFileSync(process.argv[2], 'utf8');
process.stdout.write(s.replace(/^(import|export)\b[^;]*?\bfrom\s*'[^']+';\n/gm, '').replace(/^import\s+'[^']+';\n/gm, ''));
NODE
GW_FILES="$(git diff --cached --name-only --no-renames "$B" -- "$W/entities/greenwash" "$W/pages" "$W/app/greenwash" | grep -E '^apps/web/src/(entities/greenwash/|pages/greenwash-|app/greenwash/)')"
WRAP='^apps/web/src/entities/greenwash/ui/(StepFlow|LoadFailure|RiskBadge)\.tsx$'
bad=0
for f in $GW_FILES; do
  if grep -qE "$WRAP" <<< "$f"; then echo "  감싸개: $f ($(git show ":$f" 2>/dev/null | wc -l | tr -d ' ')줄)"; continue; fi
  if ! git cat-file -e ":$f" 2>/dev/null; then
    case "$f" in
      */model/time.ts|*/ui/ExcelButton.tsx) echo "  git mv 옛 자리: $f" ;;
      *) echo "  지워짐(뜻밖): $f"; bad=1 ;;
    esac; continue
  fi
  git show "$B:$f" > "$T/a" 2>/dev/null || { echo "  새 파일(뜻밖): $f"; bad=1; continue; }
  git show ":$f" > "$T/b"
  if diff <(node "$T/strip.mjs" "$T/a") <(node "$T/strip.mjs" "$T/b") > "$T/d"; then echo "  import·export 만: $f"; else echo "  그 밖 줄이 바뀜: $f"; cat "$T/d"; bad=1; fi
  case "$f" in *.test.ts|*.test.tsx)
    diff <(grep 'expect(' "$T/a") <(grep 'expect(' "$T/b") > /dev/null || { echo "  expect( 줄이 바뀜: $f"; bad=1; } ;;
  esac
done
# 감싸개는 분기·상태 0(if·useState·?: 0), 각 ≤ 30줄
for f in StepFlow LoadFailure RiskBadge; do
  c="$(git show ":$W/entities/greenwash/ui/$f.tsx")"
  [ "$(wc -l <<< "$c")" -le 30 ] || { echo "  감싸개가 30줄 넘음: $f"; bad=1; }
  grep -qE '\bif\b|useState|useRef| \? ' <<< "$c" && { echo "  감싸개에 분기·상태: $f"; bad=1; }
done
git diff --cached "$B" -- "$W/entities/greenwash" "$W/pages/greenwash-"* "$W/app/greenwash" > "$OUTDIR/greenwash.diff"
shasum -a 256 "$OUTDIR/greenwash.diff" | cut -d' ' -f1 | tee "$OUTDIR/greenwash.diff.sha256"
git diff --cached --numstat "$B" -- "$W/entities/greenwash" "$W/pages/greenwash-"* "$W/app/greenwash" | tee "$OUTDIR/greenwash.diff.numstat"
test "$bad" -eq 0 ; mark

say "[5] 8e 몫: shared/**·L·admin-runs diff 해시·numstat, L 의 - 줄이 1-4 표의 것뿐"
git diff --cached "$B" -- "$W/shared" "$W/app/guards/layers.test.ts" "$W/pages/admin-runs" > "$OUTDIR/platform-web.diff"
shasum -a 256 "$OUTDIR/platform-web.diff" | cut -d' ' -f1 | tee "$OUTDIR/platform-web.diff.sha256"
git diff --cached --numstat "$B" -- "$W/shared" "$W/app/guards/layers.test.ts" "$W/pages/admin-runs" | tee "$OUTDIR/platform-web.diff.numstat"
cat > "$T/minus-allowed.txt" <<'TXT'
-    doors: ['address.ts', 'useLoad.ts'],
-    toolsDoors: ['address.ts', 'useLoad.ts'],
-        ['address.ts', 'useLoad.ts', 'testing/layout.ts']
-    minEntering: 7, // 실측 7
-        sharedUiDoor(rel),
TXT
git diff --cached "$B" -- "$W/app/guards/layers.test.ts" | grep '^-[^-]' > "$T/minus.txt"
cat "$T/minus.txt"
bad_minus="$(grep -v -x -F -f "$T/minus-allowed.txt" "$T/minus.txt" | grep -c .)"
echo "bad_minus=$bad_minus"
test "$bad_minus" -eq 0 ; mark

say "[6] 영문번역 파일이 entities/greenwash·pages/greenwash-*·shared/api·fetch(·msw 를 가져오거나 부르지 않음(+ 양성 대조)"
TR_FILES="$(git ls-files -- "$W/entities/translation" "$W/pages/translation-"* 2>/dev/null)"
echo "영문번역 파일 $(grep -c . <<< "$TR_FILES")개"
FORBID="entities/greenwash/|pages/greenwash-|shared/api/|\bfetch\(|\bmsw\b"
# 주석 줄(//·/*·*)은 뺀다 — 「그린워싱 partLook 과 같은 값」 같은 머리말이 경로를 말한다(가져오기·부르기가 아님).
hits="$(for f in $TR_FILES; do git show ":$f" | grep -nE "$FORBID" | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' | sed "s#^#$f:#"; done)"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: pages/greenwash-new 의 화면 파일 하나엔 걸린다"
grep -qE "$FORBID" "$W/pages/greenwash-new/ui/"*.tsx ; mark

say "[7] 영문번역 ui·model 의 한국어 글자 줄 0(주석 밖 — config/text.ts·시험 밖)"
cat > "$T/hangul.mjs" <<'NODE'
import { readFileSync } from 'node:fs';
// 주석만 지운다(문자열은 남긴다 — 그 안의 한국어가 잡을 것).
const strip = (src) => src.replace(/\/\*[\s\S]*?\*\//g, '').replace(/(^|[^:'"`])\/\/.*$/gm, '$1');
let n = 0;
for (const file of process.argv.slice(2)) {
  strip(readFileSync(file, 'utf8')).split('\n').forEach((line, i) => {
    if (/[가-힣]/.test(line)) { n++; console.log(`${file}:${i + 1}: ${line.trim()}`); }
  });
}
console.log(`hangul_lines=${n}`);
process.exit(n === 0 ? 0 : 1);
NODE
CODE="$(grep -vE '\.test\.tsx?$|/config/text\.ts$' <<< "$TR_FILES" | grep .)"
if [ -n "$CODE" ]; then node "$T/hangul.mjs" $CODE ; mark; else echo "영문번역 코드 파일 0(① 경계)"; true ; mark; fi

say "[8] 심은 파손(--commit $COMMIT, FINGERPRINT=same)"
apps/web/scripts/planted-breaks-TRW0a.sh --commit "$COMMIT" > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-220
cp "$T/planted.log" "$OUTDIR/planted-$COMMIT.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[9] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수 · 그린워싱 e2e 세 파일) · 루트 --fast"
GW_E2E=(e2e/greenwash.spec.ts e2e/greenwash-server.spec.ts e2e/parts.spec.ts)
# e2e·playwright 설정은 [2] 에서 BASE 와 같음을 봤다 — 지금 트리의 --list 수 = BASE 의 수(--list 는 testDir 기준 이름이라 e2e/ 가 붙지 않는다).
expect_e2e="$( (cd apps/web && npx playwright test --list "${GW_E2E[@]}" 2>/dev/null) | grep -cE '› (greenwash|greenwash-server|parts)\.spec\.ts:')"
echo "그린워싱 e2e 세 파일 BASE 수 = $expect_e2e"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify-$COMMIT.log"
(exit $code) ; mark
gw_ok="$(grep -cE '✓ .*› e2e/(greenwash|greenwash-server|parts)\.spec\.ts' "$T/web.log")"
gw_bad="$(grep -cE '(✘|×) .*› e2e/(greenwash|greenwash-server|parts)\.spec\.ts' "$T/web.log")"
echo "그린워싱 e2e 통과 $gw_ok / BASE $expect_e2e · 실패 $gw_bad"
[ "$gw_ok" -eq "$expect_e2e" ] && [ "$gw_bad" -eq 0 ] && [ "$expect_e2e" -gt 0 ] ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
start=$(date +%s)
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; echo "($(( $(date +%s) - start ))s)"
cp "$T/fast.log" "$OUTDIR/fast-verify-$COMMIT.log"
(exit $code) ; mark

say "[10] 추적 diff 에 키 꼴·실재 기업명(금지어 목록)·.pdf·.docx·.xlsx 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-TRW0a.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-TRW0a.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx)$')" ; mark

echo
echo "원시 출력: $T · 해시: $OUTDIR"
echo "SECTION4_FAIL=$fail"
