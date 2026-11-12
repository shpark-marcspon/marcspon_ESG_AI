#!/usr/bin/env bash
# 밴드 DVX1 ② 의 자기검증 — 웹 몫(발주서 band-handoffs/DVX1-order.md §4 ②).   사용: apps/web/scripts/section4-DVX1.sh
# 스테이징한 뒤에 돈다(경로 검사는 git diff --cached). 줄마다 "EXIT=<종료 코드>", 끝 줄 SECTION4_FAIL=<0 이 아닌 EXIT 의 수>.
# 기준 둘: B1 = git merge-base main HEAD(밴드 바닥 — 0바이트 구역), B2 = 이 경계의 바닥(기본 HEAD — 스테이징만. ② 첫 판은
#   B2=3f4430d7 로 돌았다. 감독이 main 을 들인 뒤(94dd44d1)로는 B2..HEAD 에 main 의 변경이 섞여 HEAD 로 잰다). 가지(band/DVX1)에서만 뜻이 있다.
# 경계 이름은 BOUNDARY(기본 「②」 — [10] 머리 글에만). 포트는 WEB_PORT·WEB_TEST_PORT(기본 22934·22936). 원시 출력은 워크트리 밖 DVX1.out/web-s4/ 에. SKIP_GATES=1 이면 [9] 게이트를 건너뛴다.
# 견본 이름 낱말은 스크립트 밖(DVX1_FORBIDDEN, 기본 DVX1.out/forbidden-words.txt — 감독이 준 줄)에서 읽는다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_PORT="${WEB_PORT:-22934}" WEB_TEST_PORT="${WEB_TEST_PORT:-22936}"
unset OPENAI_API_KEY ANTHROPIC_API_KEY LLM_OPENAI_API_KEY LLM_ANTHROPIC_API_KEY LLM_GEMINI_API_KEY

B1="$(git merge-base main HEAD)"
B2="${B2:-HEAD}"
W=apps/web/src
D=apps/api-py/esgapi/dataverify
OUTDIR="$(cd .. && pwd)/DVX1.out/web-s4"
FORBIDDEN="${DVX1_FORBIDDEN:-$(cd .. && pwd)/DVX1.out/forbidden-words.txt}"
mkdir -p "$OUTDIR"
T="$(mktemp -d)"
fail=0
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || fail=$((fail + 1)); }
say() { echo; echo "▶ $*"; }

# 발주서 §1-1 ② + 감독 넓힘(R1·R2 — 읽개·그 시험·서버 planted·section4 의 셈 줄 · 가지 리뷰 B1·N — 응답 꼴 kind 둘·그 시험·쌍둥이·
#   generated(gen-ts-types.sh 로만 — [3] 이 다시 지어 견줌)).
ALLOW='^(apps/web/(src/(entities/dataverify/api/((store|server|testing|index)\.ts|contract/(edkRead|index)\.ts|[^/]+\.test\.ts)|entities/dataverify/config/text(\.test)?\.ts|pages/dataverify-new/.+)|e2e/dataverify-server(\.spec)?\.ts|scripts/(section4|planted-breaks)-DVX1\.sh)|apps/api-py/(esgapi/dataverify/tools/edk_xlsx\.py|esgapi/dataverify/contracts/edk_read_shapes\.py|esgapi/dataverify/tests/(tools/test_edk_xlsx(_twin)?|contracts/test_edk_read_shapes)\.py|generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)|scripts/(section4|planted-breaks)-DVX1\.sh))$'

say "[1] ② 의 바뀐 파일(B2..스테이징, 새 파일 포함) ⊆ 수정 허용 · 스테이징 밖 변경 0"
git diff --cached --name-status -M "$B2"
outside="$(git diff --cached --name-only --no-renames "$B2" | grep -v -E "$ALLOW")"
echo "outside=$(grep -c . <<< "$outside")"; [ -n "$outside" ] && echo "$outside"
test -z "$outside" ; mark
test -z "$(git status --porcelain | grep -v '^[RAMD] ')" ; mark

say "[2] 0바이트 구역(B1..스테이징): model/edk.ts · shared · app · packages · 의존 · 계약·흐름·엔진·출력·프롬프트·actions 셋·tests/data"
ZERO=("$W/entities/dataverify/model/edk.ts" "$W/shared" "$W/app" packages apps/web/package.json pnpm-lock.yaml package.json
  apps/api-py/pyproject.toml apps/api-py/uv.lock "$D/flows" "$D/engines" "$D/outputs" "$D/prompts" "$D/tests/data"
  "$D/contracts/shapes.py" "$D/contracts/options_shapes.py" "$D/contracts/wire.py" "$D/contracts/run_list_shapes.py"
  "$D/contracts/digest_shapes.py" "$D/contracts/ai_setting_shapes.py" "$D/service/actions/result.py" "$D/service/actions/runs.py"
  "$D/service/actions/ai_settings.py" apps/api-py/esgapi/translation apps/api-py/esgapi/materiality apps/api-py/esgapi/config/api.py)
git diff --cached --stat "$B1" -- "${ZERO[@]}"
git diff --cached --quiet "$B1" -- "${ZERO[@]}" ; mark

say "[3] generated = gen-ts-types.sh 로 다시 지은 것과 바이트 같음(손으로 고친 줄 0)"
(cd apps/api-py && scripts/gen-ts-types.sh > "$T/gen.log" 2>&1) && git diff --quiet -- apps/api-py/generated ; mark

say "[4] 웹 기존 시험의 − 단언 0(import·머리 주석 줄 빼고 — ② 첫 판의 NewScreen.test.tsx:407 한 줄은 53da09b4 에 들었다)"
git diff --cached -U0 "$B2" -- $(git diff --cached --name-only "$B2" | grep -E '^apps/web/.*\.test\.tsx?$|^apps/web/e2e/.*\.spec\.ts$') \
  | grep -E '^-[^-]' | tee "$T/minus.txt"
asserts="$(grep -vE '^-(import |// )' "$T/minus.txt")"
if [ "$B2" = 3f4430d7 ]; then
  [ "$(grep -c . <<< "$asserts")" -eq 1 ] && grep -qF "expect(screen.getAllByRole('alert')).toHaveLength(1);" <<< "$asserts" ; mark
else test -z "$asserts" ; mark; fi

say "[5] 서버·웹 상한 같음: MAX_ITEMS 2,000 · 1MiB · 칸 글자 2,000"
SERVER_LIMITS='^MAX_ITEMS: Final = 2_000$|^MAX_BYTES: Final = 1024 \* 1024$|^MAX_CELL_CHARS: Final = 2_000$'
WEB_LIMITS='^export const EDK_MAX_ITEMS = 2000;$|^export const EDK_XLSX_MAX_BYTES = 1024 \* 1024;$|^export const EDK_MAX_CELL_CHARS = 2000;$'
grep -nE "$SERVER_LIMITS" "$D/tools/edk_xlsx.py"
grep -nE "$WEB_LIMITS" "$W/entities/dataverify/api/contract/edkRead.ts"
[ "$(grep -cE "$SERVER_LIMITS" "$D/tools/edk_xlsx.py")" -eq 3 ] \
  && [ "$(grep -cE "$WEB_LIMITS" "$W/entities/dataverify/api/contract/edkRead.ts")" -eq 3 ] ; mark
# kind 열이 서버 Literal 과 같은 차례인가
server_kinds="$(sed -n '/^DataverifyEdkRejectionKind = Literal\[/,/^\]/p' "$D/contracts/edk_read_shapes.py" | grep -oE '"[a-z_]+"' | tr -d '"' | tr '\n' ' ')"
web_kinds="$(sed -n '/^export const EDK_READ_KINDS/,/\] as const/p' "$W/entities/dataverify/api/contract/edkRead.ts" | grep -oE "'[a-z_]+'" | tr -d "'" | tr '\n' ' ')"
echo "server: $server_kinds"; echo "web:    $web_kinds"
[ -n "$web_kinds" ] && [ "$server_kinds" = "$web_kinds" ] ; mark

say "[6] D/tools 에 esgapi.translation·esgapi.materiality import 0"
! grep -nE '^\s*(from|import) esgapi\.(translation|materiality)' "$D"/tools/*.py ; mark

say "[7] 새 .xlsx·.json 파일 0 · 키 꼴 0 · console.·보관소 0(더한 줄)"
test -z "$(git diff --cached --name-only --diff-filter=A "$B1" | grep -iE '\.(pdf|docx|xlsx|json)$')" ; mark
git diff --cached "$B2" -- . ':!apps/web/scripts/section4-DVX1.sh' | grep '^+' | grep -nE 'sk-[A-Za-z0-9]{16,}|AKIA[0-9A-Z]{12,}|ghp_[A-Za-z0-9]{20,}|xox[bp]-|-----BEGIN' ; test $? -eq 1 ; mark
git diff --cached "$B2" -- apps/web/src | grep '^+' | grep -nE 'console\.|localStorage|sessionStorage|indexedDB' ; test $? -eq 1 ; mark

say "[8] 실재 기업명·견본 이름 낱말 0(B1..스테이징 더한 줄 + 커밋 메시지 초안)"
if [ -s "$FORBIDDEN" ]; then
  words="$(grep -c . "$FORBIDDEN")"
  hits="$( { git diff --cached "$B1" | grep '^+'; cat "$(cd .. && pwd)"/DVX1.out/commit-*.txt 2>/dev/null; } | grep -c -F -f "$FORBIDDEN")"
  echo "낱말 $words · 맞음 $hits"
  [ "$hits" -eq 0 ] ; mark
else echo "낱말 파일 없음: $FORBIDDEN"; false ; mark; fi

say "[8b] 심은 파손 웹(PLANTED=a/a · FINGERPRINT=same)"
apps/web/scripts/planted-breaks-DVX1.sh > "$T/planted.log" 2>&1
grep -E '^  [PR][0-9]+ |^FINGERPRINT=|^PLANTED=' "$T/planted.log" | cut -c1-170
cp "$T/planted.log" "$OUTDIR/planted.log"
p="$(grep '^PLANTED=' "$T/planted.log" | cut -d= -f2)"
grep -q '^FINGERPRINT=same' "$T/planted.log" && [ -n "$p" ] && [ "${p%/*}" = "${p#*/}" ] ; mark

if [ "${SKIP_GATES:-0}" != 1 ]; then
say "[9] 서버 순수(dataverify) + apps/web 게이트 (VERIFY=PASS)"
(cd apps/api-py && uv run --frozen pytest -q -p no:cacheprovider esgapi/dataverify -m "not django_db" 2>&1 | tail -1) ; mark
if [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; then echo "verify.lock 이 있다 — 기다린다"; while [ -e "$(git rev-parse --git-common-dir)/verify.lock" ]; do sleep 10; done; fi
start=$(date +%s)
apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$?
grep -E '^▶|^EXIT=|Test Files|Tests  | passed| failed|^VERIFY=' "$T/web.log"
echo "(web verify $(( $(date +%s) - start ))s)"
cp "$T/web.log" "$OUTDIR/web-verify.log"
(exit $code) ; mark
else say "[9] 게이트 건너뜀(SKIP_GATES=1)"; fi

say "[10] ${BOUNDARY:-②} 스테이징 sha256 앞16(B2..스테이징 — 「커밋 전」 줄)"
git diff --cached --binary | shasum -a 256 | cut -c1-16
true ; mark

echo
echo "원시 출력: $T · 결과: $OUTDIR"
echo "SECTION4_FAIL=$fail"
