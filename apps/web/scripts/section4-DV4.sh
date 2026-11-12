#!/usr/bin/env bash
# 밴드 DV4 의 자기검증(발주서 §4).   사용: apps/web/scripts/section4-DV4.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 커밋 B 가 박혀 있다 — 가지(band/DV4)에서만 뜻이 있다. 병합 뒤 main 에서는 돌리지 않는다.
# 포트는 WEB_PORT·WEB_TEST_PORT(기본 21044·21046). 원시 출력은 워크트리 밖 DV4.out/ 에. SKIP_GATES=1 이면 [5] 게이트를 건너뛴다.
# 땅(§1): pages/dataverify-list/ui/ListScreen(.test).tsx · entities/dataverify/config/text(.test).ts · pages/dataverify-result/ui/ResultScreen.test.tsx ·
#   e2e/dataverify-server.spec.ts · api-py dataverify/outputs/xlsx.py · 그 시험 · 이 스크립트 둘. 0줄: engines·flows·contracts·shared·generated.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-21044}" WEB_TEST_PORT="${WEB_TEST_PORT:-21046}"

B=c0623cf4
W=apps/web/src
P=apps/api-py/esgapi/dataverify
OUTDIR="$(cd .. && pwd)/DV4.out"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

ALLOW='^(apps/web/(src/(pages/dataverify-list/ui/ListScreen(\.test)?\.tsx|entities/dataverify/config/text(\.test)?\.ts|pages/dataverify-result/ui/ResultScreen\.test\.tsx)|e2e/dataverify-server\.spec\.ts|scripts/(section4|planted-breaks)-DV4\.sh)|apps/api-py/esgapi/dataverify/(outputs/xlsx\.py|tests/outputs/test_xlsx\.py|tests/contracts/test_shapes\.py))$'

say "[1] 바뀐 파일(스테이징, 새 파일 포함) ⊆ §1 수정 허용, 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B"
outside="$(git diff --cached --name-only --no-renames "$B" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0줄 구역(engines·flows·contracts·shared·generated·의존) diff 0"
ZERO=("$P/engines" "$P/flows" "$P/contracts" "$W/shared" apps/api-py/generated packages apps/web/package.json apps/api-py/pyproject.toml apps/api-py/uv.lock pnpm-lock.yaml package.json)
git diff --cached --stat "$B" -- "${ZERO[@]}"
git diff --cached --quiet "$B" -- "${ZERO[@]}" ; mark

say "[3] text.ts 는 checksLead·checksLeadFailed 와 그 주석 줄 + list.loading 한 쌍(검증자 B1, 감독 회신 10-28)만 · xlsx.py 는 설정 행 이름과 머리말 한 줄만"
git diff --cached -U0 "$B" -- "$W/entities/dataverify/config/text.ts" | grep -E '^[-+][^-+]' | tee "$T/text.txt"
test -z "$(grep -v -E 'checksLead|표 머리\(2e ⑦|허용 오차는 검사마다 AI 가 정해요|허용 오차 \$\{tolerance\} · 항목 단위|^\+    loading: .불러오는 중.,$|^\+    /\*\* 읽는 동안 300ms 뒤 숨긴 상태 글' "$T/text.txt")" && [ "$(grep -c . "$T/text.txt")" -eq 8 ] ; mark
git diff --cached -U0 "$B" -- "$P/outputs/xlsx.py" | grep -E '^[-+][^-+]' | tee "$T/xlsx.txt"
test "$(grep -c . "$T/xlsx.txt")" -eq 4 && grep -q '^+        ("계산 허용 오차(빠질 때)", settings\["tolerance"\]),$' "$T/xlsx.txt" ; mark

say "[4] 심은 파손(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DV4.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-160
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

if [ "${SKIP_GATES:-0}" != 1 ]; then
say "[5] apps/web 게이트 (VERIFY=PASS) · 서버 pytest(not django_db)·ruff"
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "(web verify $(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark
start=$(date +%s)
(cd apps/api-py && uv run pytest esgapi/dataverify -q -m "not django_db") > "$T/pytest.log" 2>&1 ; code=$?
tail -2 "$T/pytest.log" ; echo "(pytest $(( $(date +%s) - start ))s)"
cp "$T/pytest.log" "$OUTDIR/pytest.log"
(exit $code) ; mark
(cd apps/api-py && uv run ruff check esgapi/dataverify/outputs/xlsx.py esgapi/dataverify/tests/outputs/test_xlsx.py && uv run ruff format --check esgapi/dataverify/outputs/xlsx.py esgapi/dataverify/tests/outputs/test_xlsx.py) ; mark
else say "[5] 게이트 건너뜀(SKIP_GATES=1)"; fi

say "[6] 추적 diff 에 키 꼴·.pdf·.docx·.xlsx·.json 0 (이 스크립트 자신은 뺀다)"
git diff --cached "$B" -- . ':!apps/web/scripts/section4-DV4.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
test -z "$(git diff --cached --name-only "$B" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
