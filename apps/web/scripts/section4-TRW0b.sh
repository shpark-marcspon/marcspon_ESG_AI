#!/usr/bin/env bash
# 밴드 TRW0b 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-TRW0b.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached, 내용은 인덱스). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/TRW0b)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 23214·23215). 해시·numstat 은 워크트리 밖 TRW0b.out/ 에.
# 땅(§1-2 + 감독 더함 10-23): 영문번역 entities(model status·testing·range 전각 물결 · config · ui) · pages/translation-run ·
#   pages/translation-new 의 PageGrid·GlossaryField·PartRangeFields(+ 시험 — sid:MARC-ISSUE-307 1·2·3·5, 겹침 글) · L 의 영문번역 SliceRule 두 자리.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-23214}" WEB_TEST_PORT="${WEB_TEST_PORT:-23215}"

B=71bfce3
W=apps/web/src
L=$W/app/guards/layers.test.ts
OUTDIR="$(cd .. && pwd)/TRW0b.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^apps/web/(src/(entities/translation/(model/(status|status\.test|testing|index|range|range\.test)\.ts|config/text(\.test)?\.ts|ui/[^/]+\.tsx?)|pages/translation-run/(index\.ts|(model|ui)/[^/]+\.tsx?)|pages/translation-new/ui/(PageGrid|GlossaryField|PartRangeFields)(\.test)?\.tsx|app/guards/layers\.test\.ts)|scripts/(section4|planted-breaks)-TRW0b\.sh)$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1-2(+ 감독 더함), 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
git status --porcelain | grep -v '^[RAMD] ' ; test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄: shared·app(L 밖)·widgets·그린워싱·어드민·translation-new(허락 셋 밖)·api-py·e2e·package.json·잠금 파일 · L 의 diff 는 영문번역 SliceRule 두 자리만"
ZERO=("$W/shared" "$W/widgets" "$W/entities/greenwash" "$W/pages/greenwash-"* "$W/pages/admin-"* "$W/app/greenwash" "$W/app/admin" apps/api-py apps/web/e2e apps/web/package.json pnpm-lock.yaml package.json packages)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/app" | grep -v '^apps/web/src/app/guards/layers\.test\.ts$')" ; mark
test -z "$(git diff --cached --name-only --no-renames "$B" -- "$W/pages/translation-new" | grep -v -E '/ui/(PageGrid|GlossaryField|PartRangeFields)(\.test)?\.tsx$')" ; mark
git diff --cached "$B" -- "$L" > "$OUTDIR/platform-web.diff"
shasum -a 256 "$OUTDIR/platform-web.diff" | cut -d' ' -f1 | tee "$OUTDIR/platform-web.diff.sha256"
git diff --cached --numstat "$B" -- "$L" | tee "$OUTDIR/platform-web.diff.numstat"
cat > "$T/L-minus.txt" <<'TXT'
-    //   doors 는 비어 있다: 디스크에 있는 문만 적는다(아래 「폴더는 디스크에 있다」 시험) — ui/ 는 TRW0b 가 만들며 'ui/index.ts' 를 더한다(감독 판단).
-    doors: [],
-    //   ui 칸은 TRW0b 가 더한다. model/testing.ts = 시험 도우미(TRW0b 의 ui 시험이 쓴다).
-    packages: { model: /^$/, config: /^$/ },
TXT
cat > "$T/L-plus.txt" <<'TXT'
+    //   doors 는 디스크에 있는 문만 적는다(아래 「폴더는 디스크에 있다」 시험) — ui/ 는 TRW0b 가 만들며 'ui/index.ts' 를 더했다(감독 판단).
+    doors: ['ui/index.ts'],
+    //   ui = 두 화면 이상이 쓰는 모양 부품과 상태 글(TRW0b — 그린워싱 ui 칸과 같은 패키지·shared/ui 부품 표면). model/testing.ts = 시험 도우미(ui 시험이 쓴다).
+    packages: { model: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },
+      ui: sharedUiDoor,
TXT
grep '^-[^-]' "$OUTDIR/platform-web.diff" > "$T/minus.txt"; grep '^+[^+]' "$OUTDIR/platform-web.diff" > "$T/plus.txt"
cat "$T/minus.txt" "$T/plus.txt"
diff "$T/L-minus.txt" "$T/minus.txt" && diff "$T/L-plus.txt" "$T/plus.txt" ; mark
# 세 자리가 영문번역 SliceRule 안: 바뀐 줄 바로 위 10줄 안에 dir: 'entities/translation' 이 있다(DOORS 줄은 같은 줄 아래 한 줄)
git show ":$L" > "$T/L"
node -e '
  const lines = require("node:fs").readFileSync(process.argv[1], "utf8").split("\n");
  const want = ["doors: [\x27ui/index.ts\x27],", "packages: { model: /^$/, ui: GW_UI_PACKAGES, config: /^$/ },"];
  let bad = 0;
  // 같은 글의 줄이 다른 슬라이스에도 있다(doors 'ui/index.ts') — dir 'entities/translation' 줄 바로 아래 셋 안에서 찾는다.
  const dirs = lines.flatMap((l, i) => (l.includes("dir: \x27entities/translation\x27") ? [i] : []));
  for (const w of want) {
    const at = lines.findIndex((l, i) => l.trim() === w && dirs.some((d) => i > d && i - d <= 3));
    const near = lines.slice(Math.max(0, at - 3), at + 1).some((l) => l.includes("dir: \x27entities/translation\x27"));
    console.log(`  ${w} @${at + 1} 영문번역 줄 안: ${near}`); if (at < 0 || !near) bad++;
  }
  const ui = lines.findIndex((l, i) => l.trim() === "ui: sharedUiDoor," && lines.slice(Math.max(0, i - 4), i).some((p) => p.includes("time.ts")) && lines.slice(Math.max(0, i - 20), i).some((p) => p.includes("dir: \x27entities/translation\x27")));
  console.log(`  ui: sharedUiDoor @${ui + 1} 영문번역 줄 안: ${ui >= 0}`); if (ui < 0) bad++;
  process.exit(bad);
' "$T/L" ; mark

say "[3] 기존 시험의 - 줄 = 허락된 것뿐(L 넷 · PartRangeFields.test 둘 — ISSUE-307 5 제목·머리말)"
cat > "$T/test-minus-allowed.txt" <<'TXT'
-// CEO 쪽이 없으면 한도 칸 없음, 겹침 줄, 「번역할 쪽」 합.
-  it('CEO 7쪽이면 CEO 칸에 한도 오류 글(6쪽 고정), 6쪽이면 오류 없음', () => {
TXT
cat "$T/L-minus.txt" >> "$T/test-minus-allowed.txt"
git diff --cached --diff-filter=M "$B" -- '*.test.ts' '*.test.tsx' | grep '^-[^-]' > "$T/test-minus.txt"
cat "$T/test-minus.txt"
bad_minus="$(grep -v -x -F -f "$T/test-minus-allowed.txt" "$T/test-minus.txt" | grep -c .)"
echo "bad_minus=$bad_minus"
test "$bad_minus" -eq 0 ; mark

say "[4] 영문번역 파일이 entities/greenwash·pages/greenwash-*·shared/api·fetch(·msw 를 가져오거나 부르지 않음(+ 양성 대조)"
TR_FILES="$(git ls-files -- "$W/entities/translation" "$W/pages/translation-"*)"
echo "영문번역 파일 $(grep -c . <<< "$TR_FILES")개"
FORBID="entities/greenwash/|pages/greenwash-|shared/api/|\bfetch\(|\bmsw\b"
hits="$(for f in $TR_FILES; do git show ":$f" | grep -nE "$FORBID" | grep -vE '^[0-9]+:[[:space:]]*(//|/\*|\*)' | sed "s#^#$f:#"; done)"
[ -n "$hits" ] && echo "$hits"
test -z "$hits" ; mark
echo "  양성 대조: pages/greenwash-new 의 화면 파일 하나엔 걸린다"
grep -qE "$FORBID" "$W/pages/greenwash-new/ui/"*.tsx ; mark

say "[5] 영문번역 ui·model 의 한국어 글자 줄 0(주석 밖 — config/text.ts·시험·testing.ts 밖)"
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
CODE="$(grep -vE '\.test\.tsx?$|/config/text\.ts$|/model/testing\.ts$' <<< "$TR_FILES" | grep .)"
node "$T/hangul.mjs" $CODE ; mark

say "[6] 심은 파손(FINGERPRINT=same)"
apps/web/scripts/planted-breaks-TRW0b.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

say "[7] apps/web 게이트 (VERIFY=PASS · 단위 건수) · 루트 --fast"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
start=$(date +%s)
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; echo "($(( $(date +%s) - start ))s)"
cp "$T/fast.log" "$OUTDIR/fast-verify.log"
(exit $code) ; mark

say "[8] 추적 diff 에 키 꼴·실재 기업명(금지어 목록)·.pdf·.docx·.xlsx 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-TRW0b.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
WORDS="$(cd .. && pwd)/G1a.out/forbidden-words.txt"
if [ -f "$WORDS" ]; then
  n="$(git diff --cached "$B" -- . ':!apps/web/scripts/section4-TRW0b.sh' | grep '^+' | grep -c -i -F -f <(grep -v '^#' "$WORDS" | grep .))"
  echo "금지어 $(grep -v '^#' "$WORDS" | grep -c .)개 · 걸린 줄 $n"
  test "$n" -eq 0 ; mark
else echo "금지어 목록 없음: $WORDS"; false ; mark; fi
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx)$')" ; mark

echo
echo "원시 출력: $T · 해시: $OUTDIR"
echo "SECTION4_FAIL=$fail"
