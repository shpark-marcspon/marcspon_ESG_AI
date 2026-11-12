#!/usr/bin/env bash
# 밴드 AD2W 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-AD2W.sh --commit <2|3|4>(①② 는 커밋 하나 — --commit 2)
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/AD2W)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 5383·5384).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-5383}" WEB_TEST_PORT="${WEB_TEST_PORT:-5384}"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 2 | 3 | 4) ;; *) echo "사용: $0 --commit <2|3|4>"; exit 2 ;; esac

B=6ded424
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }
GW=apps/web/src/entities/greenwash-setting

say "[1] 바뀐 파일(스테이징) ⊆ 수정 허용 1-1 + 그린워싱 땅 1-2 다섯, 스테이징 밖 변경 0"
git diff --cached --name-status "$B"
git status --porcelain
test -z "$(git diff --cached --name-only "$B" | grep -v -E '^apps/web/(src/(app/admin/(AdminRoutes\.tsx|ai-setting-modules(\.test)?\.ts|runtime\.ts|router\.test\.tsx)|app/guards/layers\.test\.ts|pages/admin-ai-settings/|entities/ai-setting/|shared/ui/ai-setting/|entities/greenwash-setting/(model/setting(\.test)?\.ts|api/(server(\.test)?|testing)\.ts))|e2e/(admin\.spec\.ts|ai-prompt-model\.ts)|scripts/(section4|planted-breaks)-AD2W\.sh)')" ; mark
test -z "$(git status --porcelain | grep -v '^[AMD] ')" ; mark

say "[2] 1-3 0줄(라우터·guards 의 다른 파일·greenwash 앱·shared/api·lib·다른 슬라이스·그린워싱 문구 표·흉내 ai-settings.ts·api-py·packages)"
git diff --cached --quiet "$B" -- apps/web/src/app/router.tsx apps/web/src/app/greenwash apps/web/src/app/auth apps/web/src/shared/api apps/web/src/shared/lib apps/web/src/widgets apps/web/src/entities/greenwash apps/web/src/entities/run-log apps/web/src/entities/audit-log apps/web/src/entities/account apps/web/src/entities/session "$GW/config" "$GW/model/index.ts" "$GW/api/index.ts" apps/web/e2e/ai-settings.ts apps/api-py packages apps/web/package.json pnpm-lock.yaml ; mark

say "[3] 1-2 그린워싱 땅 diff(82 에게 — 해시·numstat) · 기존 시험의 - 줄 원문(1-5 표와 짝)"
git diff --cached --numstat "$B" -- "$GW"
echo "그린워싱 땅 diff sha256: $(git diff --cached "$B" -- "$GW" | shasum -a 256 | cut -d' ' -f1)"
git diff --cached "$B" -- "$GW" | grep '^-[^-]'
echo "--- 시험 - 줄"
git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*.spec.ts' | grep '^-[^-]' | cut -c1-200
echo "(- 줄 $(git diff --cached "$B" -- '*.test.ts' '*.test.tsx' 'apps/web/e2e/*.spec.ts' | grep -c '^-[^-]'))"

say "[4] 껍데기에 그린워싱 글자 0(pages/admin-ai-settings — 시험 포함)"
grep -rn "greenwash" apps/web/src/pages/admin-ai-settings ; test $? -eq 1 ; mark

say "[5] sid:MARC-ISSUE-278 닫는 조건: entities/ai-setting/** 의 export 마다 그 파일 밖 부르는 곳 ≥1(문 index.ts 의 이름은 slice 밖에서만 셈) · 옛 목 파일 0"
node -e '
  const fs = require("node:fs"); const cp = require("node:child_process");
  const root = "apps/web/src/entities/ai-setting/";
  const files = cp.execSync(`find ${root} -name "*.ts" ! -name "*.test.ts"`, { encoding: "utf8" }).split("\n").filter(Boolean);
  let bad = 0;
  for (const file of files) {
    const src = fs.readFileSync(file, "utf8");
    const names = [
      ...[...src.matchAll(/^export (?:async )?(?:const|function|interface|type|class) ([A-Za-z0-9_]+)/gm)].map((m) => m[1]),
      ...[...src.matchAll(/^export (?:type )?\{([^}]*)\}/gm)].flatMap((m) => m[1].split(",").map((n) => n.trim()).filter(Boolean)),
    ];
    for (const name of names) {
      let hits = "";
      // 문(index.ts)의 이름은 slice 밖에서만 센다 — 다시 내보내기만 하는 이름이 정의 파일 때문에 초록이 되지 않게(검증 ④ B1).
      const door = file.endsWith("/index.ts");
      const skip = door ? `grep -v "^${root}" | grep -v "app/guards/layers.test.ts"` : `grep -v "^${file}$"`;
      try { hits = cp.execSync(`grep -rlw -- ${name} apps/web/src apps/web/e2e | ${skip}`, { encoding: "utf8" }); } catch {}
      const n = hits.split("\n").filter(Boolean).length;
      console.log(`  ${file.slice(root.length)} ${name} ${n}`);
      if (n < 1) bad++;
    }
  }
  console.log(`쓰는 곳 0 인 내보냄 ${bad}`);
  process.exit(bad ? 1 : 0);
' ; mark
test ! -e apps/web/src/entities/ai-setting/api/mock && test ! -e apps/web/src/entities/ai-setting/model/assemble.ts && test ! -e apps/web/src/entities/ai-setting/model/criteria.ts ; mark

say "[6] 키 꼴·코랩 글 0(바뀐 줄 — 이 스크립트 자신의 무늬 줄은 뺀다. 실재 기업명은 무늬로도 싣지 않는다 — 눈으로 본다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-AD2W.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN|당신은' ; test $? -eq 1 ; mark

say "[7] 심은 파손 (②까지 6/6 · ③ 7/7 · ④ 4/4 — P15 는 감독 덧붙임, FINGERPRINT=same)"
apps/web/scripts/planted-breaks-AD2W.sh --commit "$COMMIT" > "$T/planted.log" 2>&1
grep -E '^  P[0-9b]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-200
p="$(sed -n 's/^PLANTED=//p' "$T/planted.log")"
case "$COMMIT" in 2) want=6/6 ;; 3) want=7/7 ;; 4) want=4/4 ;; esac
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ "$p" = "$want" ] ; mark

say "[8] apps/web 게이트 (VERIFY=PASS · 단위·브라우저 건수, BASE 154 파일/2066 · 157)"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "($(( $(date +%s) - start ))s)"
(exit $code) ; mark
say "    루트 빠른 게이트 (VERIFY_FAST=PASS)"
scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

echo
echo "원시 출력: $T"
echo "SECTION4_FAIL=$fail"
