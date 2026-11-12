#!/usr/bin/env bash
# 일부러 망가뜨려 보고, 지키는 것이 실제로 빨개지는지 잰다.   사용: apps/web/scripts/planted-breaks-F9.sh
# 마지막 줄이 PLANTED=14/14 여야 한다. 그 앞에 「기대: 초록」 한 줄(빨개지지 않는 것이 맞는 손상)이 있다.
#
#   1~8   계약 타입(apps/api-py/generated/api.d.ts)의 한 줄을 바꾼다 → web 의 typecheck 가, 그 동작을 부르는 파일의 줄에서 빨개지는가
#   9~14  web 의 코드 한 줄을 바꾼다 → 그것을 지키는 테스트·검사가 빨개지는가
#
# 닻(머리 무늬·옛 글자·기대 글자)은 코드가 옮겨 가면 낡는다 — 「심지 못했다」면 닻을 지금 코드에 맞춘다(밴드 SB1 ⑥, sid:MARC-ISSUE-136):
#   7  웹이 FactorsOut.total 대신 count 를 읽는다(isNext·results 와 함께) → count 로.
#   9  무효화 호출이 여러 줄이 되었다 → 그 안의 queryKey 한 줄을 다른 키로(무효화가 ["get"] 조회에 닿지 않는다).
#   11·14  prettier 뒤 홑따옴표다. 11 의 기대 글자는 지금 시험 제목(계약 타입은 shared/api 안에만).
#   12·13  main.tsx 의 api 갈래와 lazy 는 app/router.tsx 의 데모 경로(/dev/api, DEMOS 일 때만)로 옮겼다(밴드 RT1·WC1 ②).
#          12 는 그 경로를 지우고 e2e 로, 13 은 router.tsx 가 ApiPage 를 정적으로 가져오게 하고 데모를 여는 빌드(VITE_DEMOS=1)로 본다.
#
# 건드린 파일은 저장소 밖의 사본에서 되돌리고(끝날 때, 중간에 끊겨도) sha256 을 처음 것과 견준다. 다르면 PLANTED 를 내지 않고 종료 1.
# 사본을 잃었으면: git show HEAD:<경로> > <경로>
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

D=apps/api-py/generated/api.d.ts
W=apps/web
TOUCHED=("$D" "$W/src/shared/api/hooks/useInvalidatingMutation.ts" "$W/src/shared/api/client.ts" "$W/src/pages/demo-api/ApiPage.tsx" "$W/src/app/router.tsx")

# 깨끗한 데서만 시작한다(계약 타입이 이미 고쳐져 있으면 무엇을 되돌려야 하는지 알 수 없다).
if ! git diff --quiet HEAD -- "$D"; then echo "계약 타입이 HEAD 와 다르다. 시작하지 않는다: $D"; exit 1; fi

env_value() { sed -n "s/^$1=//p" .env 2>/dev/null | tail -1; }
if [ -z "${WEB_TEST_PORT:-}" ]; then
  port="$(env_value API_PY_PORT)"
  [ -n "$port" ] && export WEB_TEST_PORT=$((port + 2))
fi

KEEP="$(mktemp -d)"
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
for file in "${TOUCHED[@]}"; do
  mkdir -p "$KEEP/$(dirname "$file")"
  cp "$file" "$KEEP/$file"
done
sums_before="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
git status --porcelain > "$KEEP/status-before.txt"

# 반복 변수는 local 로 둔다(부르는 함수의 file 을 덮어쓰지 않게).
restore() { local each; for each in "${TOUCHED[@]}"; do cp "$KEEP/$each" "$each"; done; }
trap 'restore' EXIT INT TERM

passed=0
total=0
OUT="$KEEP/out.txt"

# 파일의 한 줄만 바꾼다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로.
# 머리 무늬와 옛 글자는 정규식이 아니라 글자 그대로다. 못 찾으면 종료 3.
plant() {
  node -e '
    const fs = require("node:fs");
    const [file, head, from, to] = process.argv.slice(1);
    const lines = fs.readFileSync(file, "utf8").split("\n");
    const start = lines.findIndex((line) => line.includes(head));
    const at = start < 0 ? -1 : lines.findIndex((line, index) => index >= start && line.includes(from));
    if (at < 0) process.exit(3);
    lines[at] = lines[at].replace(from, to);
    fs.writeFileSync(file, lines.join("\n"));
  ' "$@"
}

# 사본과 견줘 바뀐 줄의 수(지워진 줄과 더해진 줄이 하나씩이면 1).
changed_lines() { diff "$KEEP/$1" "$1" | grep -c '^<'; }
added_lines() { diff "$KEEP/$1" "$1" | grep -c '^>'; }

report() { # <번> <ok|fail> <말>
  total=$((total + 1))
  if [ "$2" = ok ]; then passed=$((passed + 1)); echo "  $1  빨개짐   $3"; else echo "  $1  못 잼    $3"; fi
}

# 1~8: 계약 타입의 한 줄 → typecheck 가 빨갛고, 출력에 기대한 파일·칸의 줄이 있다.
contract() { # <번> <머리 무늬> <옛> <새> <기대 무늬(정규식)> <말> [<기대 줄 수의 아래 끝>]
  local n="$1" want="${7:-1}"
  restore
  if ! plant "$D" "$2" "$3" "$4"; then report "$n" fail "심지 못했다: $6"; return; fi
  if [ "$(changed_lines "$D")" != 1 ] || [ "$(added_lines "$D")" != 1 ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $6"; restore; return; fi
  pnpm --filter @esg/web typecheck > "$OUT" 2>&1
  local code=$? hits
  hits="$(grep -cE "$5" "$OUT")"
  restore
  if [ "$code" -ne 0 ] && [ "$hits" -ge "$want" ]; then report "$n" ok "$6 — typecheck EXIT=$code, 기대한 줄 $hits (무늬: $5)"; else report "$n" fail "$6 — typecheck EXIT=$code, 기대한 줄 $hits/$want (무늬: $5)"; fi
}

# 9~14: web 의 한 줄 → 명령이 빨갛고, 출력에 기대한 글자가 전부 있다.
code_break() { # <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <기대 무늬들(줄바꿈으로 나눈 글자 그대로)>
  local n="$1" file="$2"
  restore
  if ! plant "$file" "$3" "$4" "$5"; then report "$n" fail "심지 못했다: $6"; return; fi
  if [ "$(changed_lines "$file")" != 1 ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $6"; restore; return; fi
  bash -c "$7" > "$OUT" 2>&1
  local code=$? missing=0 pattern
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" "$OUT" || { missing=$((missing + 1)); echo "       출력에 없다: $pattern"; }
  done <<< "$8"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

echo "▶ 계약 타입의 한 줄을 바꾼다 (1~8)"
PAGE='src/pages/demo-api/ApiPage\.tsx\([0-9]+,[0-9]+\): error TS[0-9]+:'
contract 1 '    "/sites": {' '"/sites"' '"/sites2"' "$PAGE.*\"/sites\"" '경로 "/sites" → "/sites2" (목록과 만들기 두 줄)' 2
contract 2 '        ExchangeOut: {' 'tenant:' 'tenantX:' "$PAGE.*'tenant'" 'ExchangeOut.tenant (교환의 답을 읽는 줄)'
contract 3 '        MeOut: {' 'tenantId:' 'tenantIdX:' "$PAGE.*'tenantId'" 'MeOut.tenantId (/me 의 답을 읽는 줄)'
contract 4 '        SitesOut: {' 'sites:' 'sitesX:' "$PAGE.*'sites'" 'SitesOut.sites (목록을 그리는 줄)'
contract 5 '        SiteIn: {' 'name:' 'nameX:' "$PAGE.*'name" 'SiteIn.name (POST /sites 의 본문을 짓는 줄)'
contract 6 '        CalcIn: {' 'gwpSetId:' 'gwpSetIdX:' "src/pages/demo-api/examples\.ts\([0-9]+,[0-9]+\): error TS[0-9]+:.*'gwpSetId" 'CalcIn.gwpSetId (계산의 예시 요청 상수)'
contract 7 '        FactorsOut: {' 'count:' 'countX:' "$PAGE.*'count'" 'FactorsOut.count (기준정보의 답을 읽는 줄)'
contract 8 '        Scope3NoCandidatesOut: {' 'status: "no_candidates"' 'status: "no_candidatez"' "src/pages/demo-api/ApiPage\.tsx\([0-9]+,[0-9]+\): error TS2367:" '후보 추리기 답의 status 값 "no_candidates" (그 글자와 견주는 줄)'

echo "▶ web 의 한 줄을 바꾼다 (9~14)"
code_break 9 "$W/src/shared/api/hooks/useInvalidatingMutation.ts" 'onSuccess: async' 'queryKey: INVALIDATE_AFTER_MUTATION,' "queryKey: ['(심은 파손)']," \
  '변경 뒤의 무효화가 ["get"] 조회에 닿지 않게 키를 바꿈' \
  'pnpm --filter @esg/web exec vitest run src/shared/api' \
  '변경 뒤의 무효화 > 성공하면 ["get"] 으로 시작하는 조회가 전부 다시 불린다'

code_break 10 "$W/src/shared/api/client.ts" 'function guarded' 'if (response.ok) return response;' 'return response;' \
  'response.ok 로 막는 자리를 지움' \
  'pnpm --filter @esg/web exec vitest run src/shared/api' \
  '조회 > 502 빈 본문(Content-Length: 0) → unexpected
조회 > 502 빈 본문(chunked) → unexpected
> 502 빈 본문(Content-Length: 0) → unexpected, 무효화 0
> 502 빈 본문(chunked) → unexpected, 무효화 0'

code_break 11 "$W/src/pages/demo-api/ApiPage.tsx" "import './api-demo.css';" "import './api-demo.css';" "import './api-demo.css'; import type { paths as Contract } from '../../../../api-py/generated/api.d.ts';" \
  'api-demo 가 계약 타입을 직접 import' \
  'pnpm --filter @esg/web exec vitest run src/app/guards/layers.test.ts' \
  '계약 타입(api-py/generated/api.d.ts)을 가져오는 파일은 shared/api 안에만 있다'

code_break 12 "$W/src/app/router.tsx" "path: 'dev/api'," "'dev/api'" "'dev/api-gone'" \
  'router.tsx 의 데모 경로 /dev/api 를 지움' \
  "cd $W && pnpm exec playwright test e2e/api-demo.spec.ts" \
  '/dev/api 가 빌드에서 뜨고'

# 진입 청크 검사(section4-F9.sh 의 것과 같은 줄).
ENTRY_CHECK='ENTRY="apps/web/dist/$(sed -n '"'"'s/.*<script[^>]*src="\.\{0,1\}\/\{0,1\}\([^"]*\)".*/\1/p'"'"' apps/web/dist/index.html | head -1)" ; test -f "$ENTRY" && ! grep -q "No QueryClient set" "$ENTRY" && test "$(grep -l "No QueryClient set" apps/web/dist/assets/*.js | wc -l)" -ge 1'
code_break 13 "$W/src/app/router.tsx" "import type { RouterHistory } from '@tanstack/react-router';" "import type { RouterHistory } from '@tanstack/react-router';" "import type { RouterHistory } from '@tanstack/react-router'; import '../pages/demo-api/ApiPage.tsx';" \
  'router.tsx 가 ApiPage 를 정적으로 import' \
  "VITE_DEMOS=1 pnpm --filter @esg/web build > /dev/null 2>&1 || { echo 빌드-실패; exit 0; }; $ENTRY_CHECK ; code=\$?; echo 진입-청크-검사=\$code; grep -q 'No QueryClient set' \"\$ENTRY\" && echo 진입-청크에-든다; exit \$code" \
  '진입-청크-검사=1
진입-청크에-든다'

code_break 14 "$W/src/pages/demo-api/ApiPage.tsx" "setToken('');" '      forgetExchange();' '      // (심은 파손)' \
  '교환 뒤 변경 기록을 지우는 줄을 뺌' \
  'pnpm --filter @esg/web exec vitest run src/pages/demo-api' \
  '토큰이 남았다: mutationCache'

# 빨개지지 않는 것이 맞는 손상: operationId 를 두 자리 다 개명해도 web 은 초록이다(openapi-fetch 는 경로와 메서드로 타입을 찾는다).
restore
plant "$D" 'get: operations["accounts_sites_list"]' 'accounts_sites_list' 'accounts_sites_list_renamed' && plant "$D" '    accounts_sites_list: {' 'accounts_sites_list' 'accounts_sites_list_renamed'
planted_two="$(changed_lines "$D")"
pnpm --filter @esg/web typecheck > "$OUT" 2>&1
green_code=$?
restore
if [ "$planted_two" = 2 ] && [ "$green_code" -eq 0 ]; then
  echo "기대: 초록 → 초록   operationId accounts_sites_list 를 두 자리 다 개명 (바뀐 줄 2, typecheck EXIT=0). 이 이름은 api-py 의 계약 테스트가 지킨다"
  green=ok
else
  echo "기대: 초록 → 어긋남   바뀐 줄 $planted_two, typecheck EXIT=$green_code"
  green=fail
fi

# 13 이 남긴 빌드를 지금 코드의 것으로 되돌린다.
pnpm --filter @esg/web build > /dev/null 2>&1

restore
trap - EXIT INT TERM
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
if [ "$sums_before" != "$sums_after" ]; then echo "되돌린 파일의 sha256 이 처음과 다르다. 사본: $KEEP"; exit 1; fi
if ! git status --porcelain | diff -q - "$KEEP/status-before.txt" > /dev/null; then echo "git status 가 처음과 다르다. 사본: $KEEP"; exit 1; fi
rm -rf "$KEEP"

echo "PLANTED=$passed/$total"
[ "$passed" -eq 14 ] && [ "$total" -eq 14 ] && [ "$green" = ok ]
