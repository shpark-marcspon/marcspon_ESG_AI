#!/usr/bin/env bash
# 밴드 F9 의 자기검증.   사용: apps/web/scripts/section4-F9.sh [--pure|--containers]
#   --pure        컨테이너 없이 재는 것 전부(기본)
#   --containers  떠 있는 api-py 에 닿는 확인 하나(e2e/live). docker 를 쓴다. 띄우고, 재고, 내리고, 자기 이미지를 지운다
# 줄마다 "EXIT=<종료 코드>" 를 낸다. 마지막 줄은 SECTION4_NONZERO=<0 이 아닌 EXIT 의 수>.
# 포트는 .env 의 API_PY_PORT 에서 정한다(web +1, web 테스트 +2). 15173 을 쓰지 않는다.
# 가지(band/F9)에서 도는 자기검증이다. 기준 커밋이 박혀 있어, 병합 뒤 main 에서는 「공유 파일은 추가만」「0줄」「허용 경로 밖」 줄들이 뜻이 없다.
# 밴드 F9 당시의 자기검증, 지금 main 에서는 돌리지 않는다 — 진입 청크 줄은 밴드 WC1 뒤 게이트의 프로덕션 빌드에 데모가 들지 않고 TanStack Query 를 쓰는 것이 데모 api 뿐이라 「다른 청크에 ≥ 1」이 늘 거짓이다(SB2 ③ 실측: 프로덕션 빌드 청크 둘 다 0, VITE_DEMOS=1 빌드는 진입 0·ApiPage 1).
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

MODE="${1:---pure}"
case "$MODE" in --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]"; exit 2 ;; esac

B=05acee0
T="$(mktemp -d)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
test -n "$PROJECT" || { echo ".env 에 COMPOSE_PROJECT_NAME 이 없다(scripts/worktree-env.sh 로 만든다)"; exit 2; }
API_PY_PORT="$(env_value API_PY_PORT)"
test -n "$API_PY_PORT" || { echo ".env 에 API_PY_PORT 가 없다. web 의 포트를 거기서 정하므로 멈춘다(scripts/worktree-env.sh 로 만든 .env 에는 있다)"; exit 2; }
export WEB_PORT=$((API_PY_PORT + 1)) WEB_TEST_PORT=$((API_PY_PORT + 2)) API_PY_ORIGIN="http://127.0.0.1:$API_PY_PORT"

nonzero=0
# 바로 앞 명령의 종료 코드를 EXIT= 줄로 낸다.
mark() { local code=$?; echo "EXIT=$code"; [ "$code" -eq 0 ] || nonzero=$((nonzero + 1)); }
say() { echo; echo "▶ $*"; }

if [ "$MODE" = "--pure" ]; then
  git status --porcelain > "$T/before.txt"

  say "루트의 빠른 게이트 (끝 줄 VERIFY_FAST=PASS)"
  scripts/verify.sh --fast > "$T/fast.log" 2>&1 ; code=$? ; tail -3 "$T/fast.log" ; (exit $code) ; mark

  say "web 의 게이트 일곱 단계 (VERIFY=PASS. 단위·브라우저 건수)"
  apps/web/scripts/verify.sh > "$T/web.log" 2>&1 ; code=$? ; grep -E '^▶|^EXIT=|Test Files|Tests  | passed|들었다: |^VERIFY=' "$T/web.log" ; (exit $code) ; mark
  say "  위가 빨갛다면 그 빨강의 귀속: 일곱 단계 가운데 앞의 여섯이 EXIT=0 이고, 일곱째(no_real_data)가 든 줄이 전부 apps/api-py/ 아래인가"
  test "$(grep -c '^EXIT=' "$T/web.log")" = 7 && test "$(grep '^EXIT=' "$T/web.log" | head -6 | sort -u)" = "EXIT=0" && test -z "$(grep '들었다: ' "$T/web.log" | grep -v '들었다: apps/api-py/')" ; mark

  say "  이 밴드가 더하거나 고친 파일은 no_real_data 에 한 줄도 걸리지 않았다: 걸린 파일이 전부 기준($B)에 있던 파일이고 그 뒤로 안 바뀌었다, apps/web/ 아래 0줄"
  grep '들었다: ' "$T/web.log" | sed 's/.*들었다: //' | sort -u > "$T/caught.txt" ; test -z "$(grep '^apps/web/' "$T/caught.txt")" && test -z "$(git ls-tree -r --name-only "$B" | sort | comm -13 - "$T/caught.txt")" && { test ! -s "$T/caught.txt" || git diff --quiet "$B" -- $(cat "$T/caught.txt"); } ; mark
  echo "걸린 줄 $(grep -c '들었다: ' "$T/web.log"), 걸린 파일 $(wc -l < "$T/caught.txt" | tr -d ' ')"

  say "새 단위 테스트 (src/shared/api, src/pages/demo-api)"
  pnpm --filter @esg/web exec vitest run src/shared/api src/pages/demo-api 2>&1 | tail -6 ; (exit "${PIPESTATUS[0]}") ; mark
  say "새 브라우저 테스트 (≤ 3)"
  pnpm --filter @esg/web exec playwright test e2e/api-demo.spec.ts 2>&1 | tail -6 ; (exit "${PIPESTATUS[0]}") ; mark
  say "평소 실행은 e2e/live 를 줍지 않는다(목록이 비지 않음을 같이 본다)"
  pnpm --filter @esg/web exec playwright test --list > "$T/list.txt" 2>&1 ; grep -q 'api-demo.spec.ts' "$T/list.txt" && ! grep -q 'live/' "$T/list.txt" ; mark
  tail -1 "$T/list.txt"

  say "의존성: 더한 것이 그 셋뿐, 고정된 판"
  node -e 'const d=require("./apps/web/package.json").dependencies; const w={"openapi-fetch":"0.17.0","openapi-react-query":"0.5.4","@tanstack/react-query":"5.103.0"}; for (const k in w) if (d[k]!==w[k]) process.exit(1)' ; mark
  test "$(git diff "$B" -- apps/web/package.json | grep -c '^[-+] ')" = 3 && test "$(git diff "$B" -- apps/web/package.json | grep -c '^- ')" = 0 ; mark
  say "잠금 파일: 지운 줄 0(있던 의존성의 판이 안 움직였다), 5.104 글자 0"
  test "$(git diff --numstat "$B" -- pnpm-lock.yaml | cut -f2)" = 0 && ! grep -q "5\.104\." pnpm-lock.yaml ; mark
  say "잠금 파일: 새로 든 꾸러미의 이름 집합이 그 다섯"
  git diff -U0 "$B" -- pnpm-lock.yaml | sed -n "s/^+  ['\"]\{0,1\}\(@\{0,1\}[^@'\" ]*\)@[0-9].*/\1/p" | sort -u | tee "$T/lock-names.txt" ; test "$(tr '\n' ' ' < "$T/lock-names.txt")" = "@tanstack/query-core @tanstack/react-query openapi-fetch openapi-react-query openapi-typescript-helpers " ; mark

  say "타입만 들어온다: 계약 타입을 가져오는 줄은 src/shared/api 안에만, 전부 import type"
  test -z "$(grep -rlE 'api-py/generated' apps/web/src apps/web/e2e apps/web/tools | grep -v '^apps/web/src/shared/api/')" ; mark
  test -z "$(grep -rnE "from ['\"][^'\"]*api-py/generated" apps/web/src/shared/api --include='*.ts' --include='*.tsx' | grep -v 'layers.test.ts' | grep -v 'import type')" ; mark

  say "진입 청크에 TanStack Query 0, 다른 청크에 ≥ 1 (위 web 게이트가 지은 dist)"
  ENTRY="apps/web/dist/$(sed -n 's/.*<script[^>]*src="\.\{0,1\}\/\{0,1\}\([^"]*\)".*/\1/p' apps/web/dist/index.html | head -1)" ; test -f "$ENTRY" && ! grep -q 'No QueryClient set' "$ENTRY" && test "$(grep -l 'No QueryClient set' apps/web/dist/assets/*.js | wc -l)" -ge 1 ; mark
  echo "진입 청크: $ENTRY"
  ls -l apps/web/dist/assets/*.js apps/web/dist/assets/*.css | awk '{print $5, $9}'

  say "공유 파일은 추가만: main.tsx(더한 줄 ≤ 10, 지운 줄 ≤ 3), vite.config.ts(지운 줄 ≤ 1), README(지운 줄 0, 덩어리 하나, Python 절 바로 앞)"
  test "$(git diff --numstat "$B" -- apps/web/src/main.tsx | cut -f1)" -le 10 && test "$(git diff --numstat "$B" -- apps/web/src/main.tsx | cut -f2)" -le 3 ; mark
  test "$(git diff --numstat "$B" -- apps/web/vite.config.ts | cut -f2)" -le 1 ; mark
  test "$(git diff --numstat "$B" -- README.md | cut -f2)" = 0 && test "$(git diff -U0 "$B" -- README.md | grep -c '^@@')" = 1 && git diff -U0 "$B" -- README.md | grep -qE '^@@ -104[67],0 ' ; mark
  say "README 의 Python 절은 그대로다"
  (cd apps/api-py && uv run --frozen python scripts/readme_audit.py paths --rev HEAD && uv run --frozen python scripts/readme_audit.py forward --rev HEAD) 2>&1 | tail -4 ; (exit "${PIPESTATUS[0]}") ; mark

  say "0줄이어야 하는 것"
  git diff --quiet "$B" -- apps/api-py apps/web/src/widgets/doc-viewer apps/web/src/widgets/review-table apps/web/src/pages/demo-viewer apps/web/src/pages/demo-table apps/web/src/shared/lib/testing apps/web/src/pages/demo-viewer/App.tsx apps/web/src/shared/lib/address.ts apps/web/src/app/styles/app.css apps/web/tsconfig.json apps/web/vitest.config.ts apps/web/playwright.config.ts apps/web/scripts/verify.sh apps/web/tools scripts compose.yaml .env.example ; mark
  test -z "$(git diff --diff-filter=MDR --name-only "$B" -- apps/web/e2e apps/web/src | grep -v '^apps/web/src/main.tsx$')" ; mark
  say "키·토큰이 web 에 없다(추적 파일과 새 파일)"
  test -z "$({ git ls-files -- apps/web; git ls-files -o --exclude-standard -- apps/web; } | sort -u | xargs grep -lE 'dev[-]keys|BEGIN (RSA )?PRIVATE[ ]KEY|eyJ[A-Za-z0-9_-]{20,}' 2>/dev/null)" ; mark
  say "live 폴더에 산출물이 떨어지지 않았다"
  test -z "$(ls apps/web/e2e/live | grep -v -E '^(api-live\.pw\.ts|playwright\.config\.ts)$')" ; mark

  say "심은 파손 (PLANTED=14/14 + 「기대: 초록」 한 줄)"
  apps/web/scripts/planted-breaks-F9.sh ; mark
  say "심은 것이 남지 않았다"
  git status --porcelain | diff - "$T/before.txt" ; mark
fi

if [ "$MODE" = "--containers" ]; then
  say "잠금: 다른 전량 실행이 돌고 있지 않다"
  test ! -e "$(git rev-parse --git-common-dir)/verify.lock" ; mark
  say "자원 문 (free ≥ 20%, 1분 부하 < 12). 빨가면 띄우지 않는다"
  free="$(memory_pressure | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')" ; load="$(sysctl -n vm.loadavg | awk '{print int($2)}')" ; echo "free=$free% load=$load" ; test "${free:-0}" -ge 20 && test "$load" -lt 12 ; mark
  if [ "$nonzero" -ne 0 ]; then echo "문이 빨갛다. 띄우지 않고 끝낸다"; echo "SECTION4_NONZERO=$nonzero"; exit 1; fi
  say "포트가 비어 있다 (api-py $API_PY_PORT, web 테스트 $WEB_TEST_PORT)"
  test -z "$(lsof -nP -iTCP:"$API_PY_PORT" -iTCP:"$WEB_TEST_PORT" -sTCP:LISTEN)" ; mark

  say "api-py 를 띄운다 (postgres, migrate-py 가 딸려 뜬다)"
  export EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)" && docker compose up -d --build --wait api-py > "$T/up.log" 2>&1 ; code=$? ; tail -4 "$T/up.log" ; (exit $code) ; mark
  say "이 실행만의 테넌트를 등록한다"
  F9_TENANT="f9-$(openssl rand -hex 4)" ; docker compose exec -T postgres psql -U "$(env_value POSTGRES_OWNER_USER)" -d "$(env_value POSTGRES_DB)_py" -c "INSERT INTO tenants (id, name, created_at) VALUES ('$F9_TENANT', '지어낸 회사', now())" ; mark
  say "계수를 들인다 (패키지에 실린 사본)"
  docker compose run --rm migrate-py python manage.py import_factors 2>&1 | tail -3 ; (exit "${PIPESTATUS[0]}") ; mark
  # 토큰은 출력하지 않는다. 둘째 것은 localhost 주소에서의 교환에 쓴다(같은 토큰을 다시 받지 않는 서버여도 되게).
  F9_TOKEN="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py token --tenant "$F9_TENANT" --ttl 600)"
  F9_TOKEN_2="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py token --tenant "$F9_TENANT" --ttl 600)"
  export F9_TENANT F9_TOKEN F9_TOKEN_2
  say "떠 있는 api-py 에 닿는 확인 (1 passed)"
  pnpm --filter @esg/web exec playwright test -c e2e/live/playwright.config.ts > "$T/live.log" 2>&1 ; code=$? ; grep -vE '^\[WebServer\]' "$T/live.log" | tail -25 ; (exit $code) ; mark
  if [ "$code" -ne 0 ]; then uptime; docker compose logs --no-color --tail 60 api-py migrate-py; fi
  unset F9_TOKEN F9_TOKEN_2

  say "내린다"
  docker compose down -v > "$T/down.log" 2>&1 ; code=$? ; tail -2 "$T/down.log" ; (exit $code) ; mark
  say "자기 컨테이너 0"
  test -z "$(docker ps -a --format '{{.Names}}' | grep "^$PROJECT-")" ; mark
  say "자기 이미지를 지운다"
  docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3; test -z "$(docker images --format "{{.Repository}}" | grep "^$PROJECT/")" ; mark
  say "자기가 띄운 web 서버 0"
  test -z "$(lsof -nP -iTCP:"$WEB_PORT" -iTCP:"$WEB_TEST_PORT" -sTCP:LISTEN)" ; mark
  say "live 폴더에 산출물이 떨어지지 않았다"
  test -z "$(ls apps/web/e2e/live | grep -v -E '^(api-live\.pw\.ts|playwright\.config\.ts)$')" ; mark
fi

say "허용 경로 밖 0"
test -z "$({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E '^(README\.md$|pnpm-lock\.yaml$|apps/web/(package\.json|vite\.config\.ts|src/main\.tsx)$|apps/web/src/(shared/api|pages/demo-api)/|apps/web/e2e/(api-demo\.spec\.ts|live/api-live\.pw\.ts|live/playwright\.config\.ts)$|apps/web/scripts/(section4|planted-breaks)-F9\.sh$)')" ; mark

rm -rf "$T"
echo
echo "SECTION4_NONZERO=$nonzero"
[ "$nonzero" -eq 0 ]
