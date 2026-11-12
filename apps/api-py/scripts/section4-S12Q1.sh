#!/usr/bin/env bash
# 밴드 S12Q1(MARC-TICK-573 — Scope 1·2 의견 1차, sid:MARC-ENT-644)의 §4 자기검증(발주서 §4 를 한 파일로).
#   사용: apps/api-py/scripts/section4-S12Q1.sh            빠른 것(셈 줄·경로·grep·tsc·vitest-band·pytest-inventory·generated·심은 파손)
#         apps/api-py/scripts/section4-S12Q1.sh --gates    + 게이트 셋(test-business -n 2 · apps/web verify · 뿌리 verify --fast)
# 줄마다 「<이름> <값> (기대 <기대>)」, 다르면 앞에 ✗. 끝 줄 「0 이 아닌 EXIT: <n> · 기대와 다름: <m>」 — 둘 다 0 이어야 한다.
# ★ main 저장소 .git/verify.lock 이 있으면 돌리지 않는다(종료 2) — 단계마다 다시 본다. e2e 포트는 WEB_TEST_PORT(기본 21901 — 검증자 21902).
# ★ 셈 줄의 「뒤」 값은 이 밴드 머리(main 들이기 84c31cc9 뒤 · ⑦ 디자인 대조 고침 때)의 실측 — BASE→main(e2e +5 · scope3 +5)과 BASE→가지(e2e +5 · ghg-server +5) 합이다. 다음 경계가 셈을 바꾸면 이 표를 같이 고친다.
# bash 전용이다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
MAIN="$(cd "$ROOT/../../esg-app" && pwd)"
[ -e "$MAIN/.git/verify.lock" ] && { echo "verify.lock 이 있다 — 멈춘다" >&2; exit 2; }
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
B=54417b42
# main 들이기(84c31cc9 — 들인 main e6818deb) 뒤: 땅·경로 diff 는 들인 main 에 대고(이 가지 몫만), 셈 줄은 머리 실측(= main 몫 + 가지 몫).
M=e6818deb
GATES=0; [ "${1:-}" = "--gates" ] && GATES=1
W=apps/web/src
T="$(mktemp -d)"
bad=0; diff_=0

step() { # <이름> <명령…> — EXIT 줄
  local name="$1"; shift
  # 다른 세션이 도중에 lock 을 잡으면 그 자리에서 멈춘다(lock 아래서는 부분 실행도 0 — runner-common §5).
  [ -e "$MAIN/.git/verify.lock" ] && { echo "verify.lock 이 생겼다 — $name 앞에서 멈춘다(EXIT=2)" >&2; exit 2; }
  local s; s=$(date +%s)
  "$@" > "$T/$name.log" 2>&1
  local code=$?
  echo "EXIT=$code $(( $(date +%s) - s ))s $name"
  [ "$code" = 0 ] || { bad=$((bad + 1)); tail -15 "$T/$name.log" | sed 's/^/    /'; }
}
want() { # <이름> <값> <기대>
  if [ "$2" = "$3" ]; then echo "  $1 $2 (기대 $3)"; else echo "✗ $1 $2 (기대 $3)"; diff_=$((diff_ + 1)); fi
}

echo "== 서버"
step pytest-inventory bash -c 'cd apps/api-py && . scripts/db-env.sh && export TEST_DATABASE_URL_PY_OWNER="$OWNER_DATABASE_URL" && uv run --frozen pytest esgapi/inventory -q -n 2'
step importlinter bash -c 'cd apps/api-py && uv run --frozen lint-imports'
step gen-ts-types bash -c 'cd apps/api-py && ./scripts/gen-ts-types.sh'
want generated-diff "$(git diff --stat -- apps/api-py/generated | wc -l | tr -d ' ')" 0
want 남의-서버-0줄 "$(git diff $M -- apps/api-py/esgapi/inventory/service/actions/{scope12_upload,entries}.py apps/api-py/esgapi/inventory/{models.py,migrations,data,tools} apps/api-py/esgapi/{core,config,runs,organization,tests} apps/api-py/{.importlinter,pyproject.toml,uv.lock} | wc -l | tr -d ' ')" 0
want NO_FACILITY-밖 "$(grep -rnE 'NO_FACILITY' apps/api-py/esgapi --include='*.py' | grep -v scope12_upload | wc -l | tr -d ' ')" 0
want 남의땅-grep "$(grep -rnE 'NO_FACILITY|facilityNodeIds|index_selection' --include='*.py' apps/api-py/esgapi/{core,config}/tests | wc -l | tr -d ' ')" 21

echo "== 웹"
step tsc pnpm --filter web exec tsc --noEmit
step vitest-band pnpm --filter web exec vitest run src/shared/ui/toast src/entities/ghg src/pages/ghg-inventory src/pages/ghg-index-settings src/pages/ghg-index-pool src/app/ghg src/app/guards
want shared-toast-밖 "$(git diff $M --name-only -- apps/web/src/shared | grep -v '^apps/web/src/shared/ui/toast/' | wc -l | tr -d ' ')" 0
echo "  toast numstat:"; git diff $M --numstat -- apps/web/src/shared/ui/toast | sed 's/^/    /'
want 남의웹-0줄 "$(git diff $M -- apps/web/src/app/guards apps/web/src/app/admin apps/web/src/app/router.tsx apps/web/src/widgets packages apps/web/package.json pnpm-lock.yaml apps/web/e2e/visual*.ts apps/web/e2e/ghg-scope3-server.ts | wc -l | tr -d ' ')" 0
want toast-한글 "$(grep -rnE '[가-힣]' apps/web/src/shared/ui/toast --include='*.ts' --include='*.tsx' | grep -v '\.test\.' | grep -vE ':\s*(//|\*|/\*)' | wc -l | tr -d ' ')" 0
want model-text "$(grep -rnE 'config/text' apps/web/src/entities/ghg/model | grep -v '\.test\.' | wc -l | tr -d ' ')" 0

echo "== 경로 밖"
want 경로-밖 "$(git diff --name-only $M | grep -vE '^apps/(api-py/(esgapi/inventory/(service/(actions|utils)/index_selection\.py$|tests/)|scripts/(planted-breaks|section4)-S12Q1\.sh$)|web/(src/(shared/ui/toast/|entities/ghg/|pages/ghg-(inventory|index-settings)/|pages/ghg-index-pool/ui/(FacilityPanel|GhgIndexPoolScreen)(\.test)?\.tsx$|app/ghg/(GhgRoutes|router\.test|scope3\.router\.test)\.tsx$)|e2e/ghg-(server(\.spec)?|scope3-server\.spec)\.ts$))' | wc -l | tr -d ' ')" 0

echo "== 옛 글"
want 옛-글 "$(grep -rnE '조직구조에 이 자산/시설이 없어요|해당 연도의 인덱스를 설정할까요|setup-confirm|setupConfirm|setupCancel|setupOk|entry-saved|inventory-saved|facility-saved|지어낸 시설 0|이 회사에 그 자산/시설이 없다|noFacility\b|unitKindPlaceholder|unitPlaceholder' apps/web/src apps/web/e2e apps/api-py/esgapi | wc -l | tr -d ' ')" 0
want 옛-받는중 "$(grep -rn "'받는 중'" apps/web/src/entities/ghg apps/web/src/pages/ghg-inventory apps/web/e2e/ghg-server.spec.ts | wc -l | tr -d ' ')" 0
# 칸 표식이 「없음」을 단언하는 자리 셋(EntryDetailDialog.test 둘 · ghg-server.spec 하나)만 남는다.
want 칸-추정-표식 "$(grep -rnE 'estimatedLabel\(|entry-estimated-[a-z0-9$]' apps/web/src apps/web/e2e | wc -l | tr -d ' ')" 3

echo "== 셈 줄(BASE → 머리)"
want e2e-전체-test "$(grep -rhoE '^\s*test(\.only)?\(' apps/web/e2e | wc -l | tr -d ' ')" 430
want ghg-server.spec "$(grep -cE '^\s*test\(' apps/web/e2e/ghg-server.spec.ts)" 52
want ghg-scope3-server.spec "$(grep -cE '^\s*test\(' apps/web/e2e/ghg-scope3-server.spec.ts)" 56
its=""
for f in pages/ghg-inventory/ui/EntryDetailDialog.test.tsx pages/ghg-inventory/ui/InventoryScreen.test.tsx pages/ghg-inventory/ui/EntryBulk.test.tsx pages/ghg-index-settings/ui/IndexSettingsScreen.test.tsx entities/ghg/model/selection.test.ts app/ghg/router.test.tsx app/ghg/scope3.router.test.tsx pages/ghg-index-pool/ui/GhgIndexPoolScreen.test.tsx entities/ghg/api/server.test.ts; do
  its="$its $(grep -cE '^\s*it(\.each\(.*\))?\(' "$W/$f")"
done
want it-아홉 "$(echo $its)" "129 47 32 24 17 14 8 23 29"
want def-test-셋 "$(echo $(grep -c 'def test_' apps/api-py/esgapi/inventory/tests/service/{actions,utils,apis}/test_index_selection.py | cut -d: -f2))" "16 9 8"
want pool-model-it "$(grep -cE '^\s*it\(' $W/entities/ghg/model/pool.test.ts)" 12
want facility-panel-it "$(grep -cE '^\s*it\(' $W/pages/ghg-index-pool/ui/FacilityPanel.test.tsx)" 5
want toast-it "$(grep -rhoE '^\s*it\(' apps/web/src/shared/ui/toast | wc -l | tr -d ' ')" 16
want layers-wc "$(wc -l < $W/app/guards/layers.test.ts | tr -d ' ')" 6928

echo "== 심은 파손"
step planted-breaks bash apps/api-py/scripts/planted-breaks-S12Q1.sh
grep -E '^PLANTED=' "$T/planted-breaks.log" | sed 's/^/  /'

if [ "$GATES" = 1 ]; then
  echo "== 게이트"
  WEB_PORT="$(sed -n 's/^WEB_PORT=//p' .env | grep . || echo 15173)"
  step test-business apps/api-py/scripts/test-business.sh -n 2
  step web-verify env WEB_PORT="$WEB_PORT" WEB_TEST_PORT="${WEB_TEST_PORT:-21901}" apps/web/scripts/verify.sh
  grep -E 'VERIFY=' "$T/web-verify.log" | tail -1 | sed 's/^/  /'
  step verify-fast scripts/verify.sh --fast
fi

echo "기록 $T"
echo "0 이 아닌 EXIT: $bad · 기대와 다름: $diff_"
[ "$bad" = 0 ] && [ "$diff_" = 0 ]
