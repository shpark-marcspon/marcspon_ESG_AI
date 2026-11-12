#!/usr/bin/env bash
# 밴드 SW1 의 §4 자기검증(발주서 band-handoffs/SW1-order.md §4 — API 를 /api 아래로, whitenoise 정적 서빙과 SPA fallback,
# 이미지에 웹 빌드). 줄마다 EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
#
#   apps/api-py/scripts/section4-SW1.sh                  1~9
#   apps/api-py/scripts/section4-SW1.sh --step 1,3       일부(번호는 발주서 §4 의 번호)
#   apps/api-py/scripts/section4-SW1.sh --step 10        전량 scripts/verify.sh 1회 — 감독의 「돌려라」를 받은 뒤에만
#   apps/api-py/scripts/section4-SW1.sh --after-commit   1~9 + git status --porcelain 0
#
# 환경 변수:
#   SW1_BASE  기준 커밋(기본: 워크트리를 만들 때의 main 4fe8407)
#   SW1_OUT   산출물 자리(기본: 워크트리 곁의 SW1.out). 산출물은 $SW1_OUT/section4/ 아래
# 9 의 check-build-context.sh 는 docker build 를 부른다(러너의 컨테이너 규칙과 scripts/with-build-lock.sh 로 감싼다).
# 6 은 gen-ts-types.sh 를 다시 돌린다(pnpm dlx openapi-typescript@7.13.0 — 네트워크와 node/pnpm PATH 가 필요하다).
# macOS 의 /bin/bash 3.2 에서 돈다(mapfile·연관 배열을 쓰지 않는다).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${SW1_BASE:-4fe8407}"
OUT="${SW1_OUT:-$SIDE/SW1.out}"
S4="$OUT/section4"
mkdir -p "$S4"
NODE_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
A="apps/api-py"
E="$A/esgapi"

STEPS=",1,2,3,4,5,6,7,8,9,"
AFTER=0
case "${1:-}" in
  --step) STEPS=",${2:?--step 뒤에 번호}," ;;
  --after-commit) AFTER=1 ;;
  "") ;;
  *) echo "사용: $0 [--step 1,2,… | --after-commit]"; exit 2 ;;
esac
want() { case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "기준 $BASE, HEAD $(git -C "$ROOT" rev-parse --short HEAD), 산출물 $S4"

# ── 1. 빠른 게이트 ──
if want 1; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh --fast) > "$S4/verify-fast.log" 2>&1
  last=$(tail -1 "$S4/verify-fast.log")
  echo "    $last"
  report 1 "verify.sh --fast" "$([ "$last" = "VERIFY_FAST=PASS" ] && echo 0 || echo 1)"
fi

# ── 2. lock: uv 0.7.13 의 --check, 기준 대비 지운 줄 0, 더한 줄은 whitenoise 블록과 esgapi 의존 두 줄뿐 ──
if want 2; then
  (cd "$API_PY" && uvx --from 'uv==0.7.13' uv lock --check) > "$S4/lock-check.log" 2>&1
  c=$?
  git -C "$ROOT" diff "$BASE" -- "$A/uv.lock" > "$S4/lock.diff"
  removed=$(grep -c '^-[^-]' "$S4/lock.diff")
  grep '^+[^+]' "$S4/lock.diff" \
    | grep -v -E 'whitenoise|^\+\[\[package\]\]$|^\+version = "6\.12\.0"$|^\+source = \{ registry = "https://pypi.org/simple" \}$|^\+wheels = \[$|^\+\]$' \
    > "$S4/lock-extra.txt"
  extra=$(grep -c . "$S4/lock-extra.txt")
  added=$(grep -c '^+[^+]' "$S4/lock.diff")
  echo "    uv lock --check 종료 $c · 지운 줄 $removed · 더한 줄 $added(그 밖 $extra)"
  sed 's/^/    그 밖: /' "$S4/lock-extra.txt"
  report 2 "lock 더하기만" "$([ "$c$removed$extra" = 000 ] && echo 0 || echo 1)"
fi

# ── 3. manage.py check: 시험 설정, 절대 WEB_DIST_DIR. 상대 경로·index 없음은 거부 ──
if want 3; then
  dist="$S4/dist"
  empty="$S4/dist-empty"
  rm -rf "$dist" "$empty"
  mkdir -p "$dist/assets" "$empty"
  printf '<!doctype html><title>sw1</title>' > "$dist/index.html"
  check() { (cd "$API_PY" && env "$@" DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py check) > "$S4/check.log" 2>&1; }
  check WEB_DIST_DIR=
  a=$?
  check WEB_DIST_DIR="$dist"
  b=$?
  check WEB_DIST_DIR=relative/dist
  r=$?
  grep -q 'WEB_DIST_DIR 는 절대 경로' "$S4/check.log"
  rm_=$?
  check WEB_DIST_DIR="$empty"
  n=$?
  grep -q 'WEB_DIST_DIR 에 index.html 이 없다' "$S4/check.log"
  nm=$?
  echo "    꺼짐 $a · 절대 경로 $b · 상대 경로 $r(문구 $rm_) · index 없음 $n(문구 $nm)  (0 0 ≠0(0) ≠0(0) 이 기대)"
  ok=1
  [ "$a$b$rm_$nm" = 0000 ] && [ "$r" != 0 ] && [ "$n" != 0 ] && ok=0
  report 3 "manage.py check 와 기동 거부" "$ok"
fi

# ── 4. 새 순수·업무 시험(표적) ──
if want 4; then
  (cd "$API_PY" && uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_web.py \
    esgapi/config/tests/test_api_contract.py esgapi/config/tests/test_settings.py \
    esgapi/core/tests/test_observability_middleware.py) > "$S4/targeted.log" 2>&1
  e=$?
  echo "    $(tail -1 "$S4/targeted.log")"
  report 4 "새 시험(test_web·계약·설정·미들웨어)" "$e"
fi

# ── 5. 심은 파손: PLANTED=<전체>/<전체>, 되돌린 뒤 지문 같음 ──
if want 5; then
  SW1_OUT="$OUT" "$API_PY/scripts/planted-breaks-SW1.sh" > "$S4/planted.log" 2>&1
  e=$?
  sed 's/^/  /' "$S4/planted.log"
  report 5 "심은 파손 전부 빨강·지문 같음" "$e"
fi

# ── 6. generated 다시 뽑기: 지금 커밋과 diff 0, 기준 대비 api.d.ts 같음·openapi.json 은 servers 한 덩이 ──
if want 6; then
  G="$A/generated"
  (cd "$API_PY" && PATH="$NODE_DIR:$PATH" scripts/gen-ts-types.sh) > "$S4/gen-ts-types.log" 2>&1
  ge=$?
  git -C "$ROOT" diff --quiet HEAD -- "$G"
  now=$?
  git -C "$ROOT" diff --quiet "$BASE" -- "$G/api.d.ts"
  dts=$?
  git -C "$ROOT" diff -U0 "$BASE" -- "$G/openapi.json" | grep '^[-+][^-+]' > "$S4/openapi.diff"
  body=$(tr -d ' \n' < "$S4/openapi.diff")
  want_body='-"servers":[]+"servers":[+{+"url":"/api"+}+]'
  echo "    다시 뽑기 종료 $ge · HEAD 대비 diff $now · 기준 대비 api.d.ts $dts · openapi.json diff: $body"
  report 6 "generated 같음(servers 한 덩이)" "$([ "$ge$now$dts" = 000 ] && [ "$body" = "$want_body" ] && echo 0 || echo 1)"
fi

# ── 7. 허용 경로(§1) 밖 diff 0, 0줄 목록 0, 라우터 경로 글자 0 ──
# settings 의 test_business·test_security 는 감독 처분(가지 리뷰 LOW 4, WHITENOISE_ROOT = None 한 줄씩)으로 더함.
ALLOWED="^($A/(pyproject\.toml|uv\.lock)|$E/config/(urls|api|web)\.py|$E/config/settings/(base|test_business|test_security)\.py|$E/(config|core|user|organization|inventory|reference)/tests/.+\.py|$A/tests/security/.+\.py|$A/tests/support/http\.py|$A/tests_integration/(conftest|test_observability_flow|test_upload_flow|test_flow|test_web_flow)\.py|$A/generated/(openapi\.json|api\.d\.ts\.source-sha256)|$A/scripts/(rehearsal|section4-SW1|planted-breaks-SW1)\.sh|docker/api-py\.Dockerfile|compose\.yaml)$"
ZERO=(
  apps/web packages pnpm-lock.yaml package.json pnpm-workspace.yaml "$E/greenwash" greenwashing
  scripts/verify.sh scripts/check-gates.sh scripts/git-hooks .importlinter "$A/.importlinter" .env.example .dockerignore
  docker/parser.Dockerfile "$A/scripts/check-build-context.sh" README.md infra "$E/config/env.py"
  scripts/section4-PY5.sh scripts/section4-XC.sh "$A/scripts/section4-PY5.sh" "$A/scripts/section4-XC.sh"
  "$A/scripts/planted-breaks-XC.sh" "$A/scripts/archive" "$A/generated/api.d.ts"
)
if want 7; then
  { git -C "$ROOT" diff --name-only "$BASE"; git -C "$ROOT" ls-files -o --exclude-standard --full-name; } \
    | sort -u > "$S4/changed.txt"
  grep -Ev "$ALLOWED" "$S4/changed.txt" > "$S4/outside.txt"
  n=$(grep -c . "$S4/outside.txt")
  zero=$(git -C "$ROOT" diff --name-only "$BASE" -- "${ZERO[@]}" | grep -c .)
  zero_new=$(git -C "$ROOT" ls-files -o --exclude-standard -- "${ZERO[@]}" | grep -c .)
  pre=$(grep -c '^\.pre-commit' "$S4/changed.txt")
  # 라우터 데코레이터의 경로 글자: 모듈의 api.py 와 service/apis/*.py(시험 폴더는 빼고 — :(glob) 의 * 는 / 를 넘지 않는다)
  routes=$(git -C "$ROOT" diff -U0 "$BASE" -- ":(glob)$E/*/service/apis/*.py" ":(glob)$E/*/api.py" \
    ":(exclude)$E/config/api.py" | grep -c '^[-+][^-+]')
  # config/api.py 의 라우터 거는 줄과 상태 확인 경로 두 줄은 그대로
  git -C "$ROOT" show "$BASE:$E/config/api.py" | grep -E '^api\.add_router|^@api\.get\(' > "$S4/routes-base.txt"
  grep -E '^api\.add_router|^@api\.get\(' "$ROOT/$E/config/api.py" > "$S4/routes-head.txt"
  cmp -s "$S4/routes-base.txt" "$S4/routes-head.txt"
  cfg=$?
  echo "    바뀐 파일 $(grep -c . "$S4/changed.txt"), 허용 밖 $n, 0줄 목록 $zero(+새 파일 $zero_new), .pre-commit* $pre, 라우터 글자 $routes, config/api.py 라우터·상태 확인 줄 다름 $cfg"
  sed 's/^/    밖: /' "$S4/outside.txt"
  report 7 "허용 밖 0·0줄 목록 0·라우터 글자 0" "$([ "$n$zero$zero_new$pre$routes$cfg" = 000000 ] && echo 0 || echo 1)"
fi

# ── 8. 옛 경로 남음 0: Django 시험 클라이언트로 접두 없는 API 경로를 부르는 글자 ──
# 식: .get|post|put|patch|delete|head|generic( 다음 첫 인자가 "/<API 첫 마디>…" 인 줄. 대상은 시험(esgapi/**/tests, tests/)과
# rehearsal.sh — 제품 코드의 라우터 데코레이터는 접두 없는 경로가 맞다. 뺀다: ninja TestClient(주소표를 안 거침)·
# RequestFactory(미들웨어를 직접 부름)·통합 시험(base_url 이 …/api)·config/tests/test_web.py(화면 경로 /greenwash 와
# 옛 자리의 POST /auth/login 을 일부러 부른다). 닫힌 밴드 스크립트는 대상 밖.
# 여러 줄 부름의 첫 인자 후보(old-paths-wrapped.txt)는 셈만 찍는다 — openapi 키 표가 섞여 손으로 본다.
OLD_RE="\.(get|post|put|patch|delete|head|generic)\([[:space:]]*f?[\"']/(auth|me|users|sites|inventory|reference|documents|runs|greenwash|healthz|readyz)([/\"'?{]|$)"
if want 8; then
  git -C "$ROOT" grep -n -E "$OLD_RE" -- ":(glob)$E/**/tests/**" "$A/tests" "$A/scripts/rehearsal.sh" \
    ":(exclude)$E/config/tests/test_web.py" \
    | grep -v -E 'TestClient|_client\(\)|RequestFactory' > "$S4/old-paths.txt"
  # 여러 줄에 걸친 부름(인자가 다음 줄)의 첫 인자 줄
  git -C "$ROOT" grep -n -E "^[[:space:]]+f?[\"']/(auth|me|users|sites|inventory|reference|documents|runs|greenwash|healthz|readyz)[/\"'?{]" \
    -- ":(glob)$E/**/tests/**/*.py" "$A/tests" > "$S4/old-paths-wrapped.txt"
  n=$(grep -c . "$S4/old-paths.txt")
  w=$(grep -c . "$S4/old-paths-wrapped.txt")
  echo "    한 줄 부름 $n · 여러 줄 부름의 첫 인자 후보 $w(손으로 본다 — openapi 키 표가 섞인다)"
  sed 's/^/    옛: /' "$S4/old-paths.txt"
  report 8 "옛 경로 부름 0" "$([ "$n" = 0 ] && echo 0 || echo 1)"
fi

# ── 9. 게이트 자기 검사와 빌드 컨텍스트 ──
if want 9; then
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/check-gates.sh) > "$S4/check-gates.log" 2>&1
  g=$?
  (cd "$ROOT" && scripts/with-build-lock.sh "$A/scripts/check-build-context.sh") > "$S4/check-build-context.log" 2>&1
  b=$?
  echo "    $(grep '^GATES=' "$S4/check-gates.log" | tail -1) (종료 $g) · check-build-context 종료 $b: $(tail -1 "$S4/check-build-context.log")"
  report 9 "check-gates.sh·check-build-context.sh" "$([ "$g$b" = 00 ] && echo 0 || echo 1)"
fi

# ── 10. 전량 verify 1회(감독의 「돌려라」 뒤에만, --step 10) ──
if want 10; then
  start=$(date +%s)
  (cd "$ROOT" && PATH="$NODE_DIR:$PATH" scripts/verify.sh) > "$S4/verify.log" 2>&1
  last=$(tail -1 "$S4/verify.log")
  echo "    $last ($(($(date +%s) - start))초)"
  report 10 "verify.sh 전량" "$([ "$last" = "VERIFY=PASS" ] && echo 0 || echo 1)"
fi

if [ "$AFTER" = 1 ]; then
  porcelain=$(git -C "$ROOT" status --porcelain)
  echo "    git status --porcelain: $(printf '%s' "$porcelain" | grep -c .) 줄"
  [ -n "$porcelain" ] && printf '%s\n' "$porcelain" | sed 's/^/    /'
  report after "커밋 뒤 작업 트리 깨끗함" "$([ -z "$porcelain" ] && echo 0 || echo 1)"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = 0 ]
