#!/usr/bin/env bash
# 밴드 RPA4(MARC-TICK-449: 원고작성 AI 설정 화면 글 — 페이지 낱말·자리 {페이지 글}·글 판 @2·모의 안내 뺌·모의 위끝 칸 나눔)의
# §4 자기검증(발주서 band-handoffs/RPA4-order.md §4). 틀은 section4-RPQ1.sh.
#   사용: apps/api-py/scripts/section4-RPA4.sh --commit 1 [--with-containers] [--planted] [--msg <파일>] [--step <n>]
#   --with-containers 면 단계 10(업무·보안)을 돈다 — 안 주면 「안 돌림」(EXIT=1 로 센다 — 조용한 초록 0).
# 단계마다 「[n] <설명> EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. <기준> = git merge-base main HEAD.
# 전량 scripts/verify.sh 는 여기서 돌리지 않는다(lock 확인 뒤 따로 — §4-15). AI 공급사 호출 0(env -u 키).
# 환경 변수: S4_OUT(로그 자리, 기본 워크트리 곁의 RPA4.out — 검증자는 RPA4.verify), RPA4_FORBIDDEN(실재 기업명 낱말
#   파일, 기본 워크트리 곁의 G1a.out/forbidden-words.txt — 낱말은 찍지 않고 수만), MARCSPON_ROOT(보고 파일을 찾는 뿌리).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
cd "$HERE/../../.."
ROOT="$(pwd)"
A=apps/api-py
E="$A/esgapi"
P="$E/drafting"
W=apps/web/src
OUT="${S4_OUT:-$ROOT/../RPA4.out}"
FORBIDDEN="${RPA4_FORBIDDEN:-$ROOT/../G1a.out/forbidden-words.txt}"
MROOT="${MARCSPON_ROOT:-$ROOT/../..}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0; PLANTED=0; MSG=""
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --planted) PLANTED=1; shift ;;
    --msg) MSG="${2:-}"; shift 2 ;;
    *) echo "사용: $0 --commit 1 [--with-containers] [--planted] [--msg <파일>] [--step <n>]" >&2; exit 2 ;;
  esac
done
[ "$COMMIT" = 1 ] || { echo "--commit 1 이 필요하다" >&2; exit 2; }
BASE="$(git merge-base main HEAD)"
[ -n "$BASE" ] || { echo "merge-base 를 못 읽음" >&2; exit 2; }
BASE_CONTRACTS="$(git show "$BASE:$A/.importlinter" | grep -c '^\[importlinter:contract')"
mkdir -p "$OUT"
echo "── 밴드 RPA4 §4 · 경계 $COMMIT · 기준 ${BASE:0:8} · HEAD $(git rev-parse --short HEAD) · 로그 $OUT · $(uptime | sed 's/.*load/load/')"
FAILS=0

step() {  # step <번호> <설명> <명령…>
  local n="$1" what="$2" start; shift 2
  if [ -n "$ONLY" ] && [ "$ONLY" != "$n" ]; then return 0; fi
  echo "── [$n] $what"
  start=$(date +%s)
  "$@"
  local code=$?
  echo "[$n] $what EXIT=$code $(( $(date +%s) - start ))s"
  [ "$code" -eq 0 ] || FAILS=$((FAILS + 1))
}

not_run() {  # <n> <설명> <까닭>
  if [ -n "$ONLY" ] && [ "$ONLY" != "$1" ]; then return 0; fi
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}

changed() {  # <기준> 이후 바뀐 파일 + 새 파일(뿌리 기준 경로)
  { git diff --no-renames --name-only "$BASE"; git ls-files -o --exclude-standard --full-name; } | sort -u
}

BASE_TREE="$OUT/base-tree"
base_tree() {
  [ -f "$BASE_TREE/.ref" ] && [ "$(cat "$BASE_TREE/.ref")" = "$BASE" ] && return 0
  rm -rf "$BASE_TREE" && mkdir -p "$BASE_TREE"
  git archive "$BASE" "$A" | tar -x -C "$BASE_TREE" || return 1
  echo "$BASE" > "$BASE_TREE/.ref"
}

# 1: 순수 층(drafting — not django_db). N0 = 기준 트리에서 모은 수 → N1 통과(늘기만).
s1() {
  local log n n0 code
  base_tree || return 1
  n0="$(cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest esgapi/drafting \
    -m "not django_db" -q -p no:cacheprovider --collect-only 2>&1 | tail -1 | sed -n 's/^\([0-9]*\)\/*[0-9]* *tests* .*/\1/p')"
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen pytest -q esgapi/drafting -m "not django_db" \
    -p no:cacheprovider 2>&1)"
  code=$?
  echo "$log" > "$OUT/s1-pure.log"
  n="$(echo "$log" | tail -1 | sed -n 's/^\([0-9]*\) passed.*/\1/p')"
  echo "  N0(기준 트리) ${n0:-?} → N1 ${n:-?} 통과 · $(echo "$log" | tail -1)"
  [ "$code" = 0 ] && [ -n "$n0" ] && [ "${n:-0}" -gt "$n0" ]
}

s2() {
  local log kept broken
  log="$(cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen lint-imports 2>&1)"
  kept="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\1/p')"
  broken="$(echo "$log" | sed -n 's/^Contracts: \([0-9]*\) kept, \([0-9]*\) broken.*/\2/p')"
  echo "  계약 KEPT ${kept:-?} (기준 $BASE_CONTRACTS) · broken ${broken:-?}"
  [ "${kept:-0}" = "$BASE_CONTRACTS" ] && [ "${broken:-1}" = 0 ]
}

s3() {
  (cd "$A" && uv run --frozen python scripts/check_test_layout.py 2>&1 | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

s4() {
  local code=0
  (cd "$A" && uv run --frozen pyright esgapi/drafting 2>&1 | tail -1 | sed 's/^/  pyright /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff check . 2>&1 | tail -1 | sed 's/^/  ruff check /'; exit "${PIPESTATUS[0]}") || code=1
  (cd "$A" && uv run --frozen ruff format --check . 2>&1 | tail -1 | sed 's/^/  ruff format /'; exit "${PIPESTATUS[0]}") || code=1
  return $code
}

# 5: 경로 §1-2 닫힌 목록 · 0줄 목록 · 남의 땅 diff 0 · 금지 꼴 더함 0
ALLOWED="^$P/engines/v2/(texts|prompts|__init__)\.py\$
^$P/flows/(prompt_model_v2|draft_v2)\.py\$
^$P/prompts/README\.md\$
^$P/tests/.*
^$A/scripts/(section4|planted-breaks)-RPA4\.sh\$
^$W/entities/drafting-setting/config/text(\.test)?\.ts\$
^$W/entities/drafting-setting/model/flow(\.test)?\.ts\$
^$W/entities/drafting-setting/api/server\.test\.ts\$
^$W/app/admin/ai-setting-modules(\.test)?\.ts\$
^apps/web/e2e/ai-settings-drafting(\.spec)?\.ts\$"
ZERO="^$P/engines/v1/
^$P/tests/engines/v1/
^$P/flows/(binding_v2|reuse)\.py\$
^$P/contracts/
^$P/prompts/[^/]+/[^/]+\.md\$
^$P/service/
^$P/models\.py\$
^$P/migrations/
^$E/(core|runs|config|translation)/
^$A/generated/
^$A/tests/security/
^$W/entities/ai-setting/
^$W/entities/drafting-setting/ui/
^$W/(pages|shared|widgets)/
^apps/web/e2e/(visual|admin)\.spec\.ts\$
^compose\.yaml\$
^$A/(pyproject\.toml|uv\.lock)\$
^apps/web/package\.json\$
^pnpm-"
s5() {
  local all outside zero code=0
  all="$(changed)"
  echo "$all" | sed 's/^/  /'
  outside="$(echo "$all" | grep -v -E -e "$(echo "$ALLOWED" | paste -sd'|' -)" | grep -c .)"
  [ "$outside" -eq 0 ] || { echo "$all" | grep -v -E -e "$(echo "$ALLOWED" | paste -sd'|' -)" | sed 's/^/  ★ 밖: /'; code=1; }
  zero="$(echo "$all" | grep -E -e "$(echo "$ZERO" | paste -sd'|' -)" | grep -c .)"
  [ "$zero" -eq 0 ] || { echo "$all" | grep -E -e "$(echo "$ZERO" | paste -sd'|' -)" | sed 's/^/  ★ 0줄 목록: /'; code=1; }
  echo "  바뀐 파일 $(echo "$all" | grep -c .) · outside=$outside · 0줄 목록 $zero"
  git diff --quiet "$BASE" -- "$E/core" "$E/runs" "$E/config" "$E/translation" "$A/generated" "$A/tests/security" \
    "$W/shared" "$W/widgets" "$W/pages" "$W/entities/ai-setting" "$P/engines/v1" "$P/tests/engines/v1" "$P/flows/binding_v2.py" \
    || { echo "  ★ 남의 땅·0줄 diff"; code=1; }
  # a8 허락 ③: 두 파일 numstat 합(+9/−11 안팎)
  git diff --numstat "$BASE" -- "$W/app/admin/ai-setting-modules.ts" "$W/app/admin/ai-setting-modules.test.ts" \
    | awk '{a+=$1; d+=$2} END {print "  a8 두 파일 +" a "/−" d}'
  git diff "$BASE" -- "$P" "$W/entities/drafting-setting" "$W/app/admin" apps/web/e2e > "$OUT/s5.diff"
  if grep -E '^\+' "$OUT/s5.diff" | grep -v -E '^\+\+\+' | grep -E 'except Exception|# type: ignore|# noqa' | grep -c . | grep -qv '^0$'; then
    echo "  ★ 금지 꼴(except Exception·type: ignore·noqa) 더함"; code=1
  fi
  git diff --numstat "$BASE" | sed 's/^/  numstat /'
  return $code
}

# 6: 선언 지문(RPA4 — S2 system·S2 user 머리 한 줄·S3 system 표지 한 줄) — BASE 트리와 작업본. call_requests·dry_requests·calls·results 는 sha 같음 · requests 는 선언 바뀜을
#    되돌리면 칸마다 같음(texts_digest --compare)
s6() {
  local digest="$P/tests/flows/texts_digest.py" base_txt="$OUT/s6-base.txt" new_txt="$OUT/s6-new.txt"
  base_tree || return 1
  cp "$digest" "$BASE_TREE/$digest"
  rm -rf "$OUT/s6-dump-base" "$OUT/s6-dump-new"
  (cd "$BASE_TREE/$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY PYTHONPATH=. "$ROOT/$A/.venv/bin/python" \
    -m esgapi.drafting.tests.flows.texts_digest --dump "$OUT/s6-dump-base") > "$base_txt" || return 1
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.drafting.tests.flows.texts_digest \
    --dump "$OUT/s6-dump-new") > "$new_txt" || return 1
  echo "  지문 줄 $(grep -c . "$new_txt") · 호출 $(grep ' calls ' "$new_txt" | awk '{print $1"="$3}' | paste -sd' ' -)"
  if ! diff <(grep -v ' requests ' "$base_txt") <(grep -v ' requests ' "$new_txt") | sed 's/^/  ★ /' | grep . ; then
    echo "  call_requests·dry_requests·calls·results sha 같음(경우 다섯)"
  else
    echo "FINGERPRINT=differs"; return 1
  fi
  [ "$(diff <(grep ' requests ' "$base_txt") <(grep ' requests ' "$new_txt") | grep -c '^>')" = 5 ] \
    || { echo "  ★ requests sha 가 다섯 경우 다 달라야 한다(분모)"; echo "FINGERPRINT=differs"; return 1; }
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY uv run --frozen python -m esgapi.drafting.tests.flows.texts_digest \
    --compare "$OUT/s6-dump-base" "$OUT/s6-dump-new") | sed 's/^/  /'
  [ "${PIPESTATUS[0]}" = 0 ]
}

s7() {
  local d="$OUT/s7.diff" n_key n_bin n_lab n_name=0 report="$MROOT/band-reports/RPA4.md"
  { git diff "$BASE"; git ls-files -o --exclude-standard --full-name | while read -r f; do git diff --no-index /dev/null "$f"; done; } \
    > "$d" 2>/dev/null
  [ -n "$MSG" ] && [ -f "$MSG" ] && sed 's/^/+/' "$MSG" >> "$d"
  [ -f "$report" ] && sed 's/^/+/' "$report" >> "$d"
  n_key="$(grep -E '^\+' "$d" | grep -c -E 'sk-[A-Za-z0-9_-]{16,}|sk-ant-[A-Za-z0-9_-]{8,}|AKIA[0-9A-Z]{16}|BEGIN (RSA |EC )?PRIVATE KEY')"
  n_bin="$(changed | grep -c -E '\.(pdf|xlsx|docx|ipynb)$')"
  n_lab="$(grep -E '^\+' "$d" | grep -c -E 'from esg[l]ab|import esg[l]ab')"
  if [ -f "$FORBIDDEN" ]; then
    n_name="$(grep -E '^\+' "$d" | grep -c -F -f "$FORBIDDEN")"
  else
    echo "  ★ 실재 기업명 낱말 파일이 없다"; n_name=1
  fi
  # {쪽 글} 그물: v1 글·시험·README·B1(test_texts)·B6(test_binding_v2_settings·service test_ai_settings)·texts_digest 밖 0, apps/web 0
  n_slot="$(git grep -l -F '{쪽 글}' -- "$A" apps/web | grep -v -E "^$P/engines/v1/|^$P/tests/engines/v1/|^$P/prompts/README\.md\$|^$P/tests/engines/v2/test_texts\.py\$|^$P/tests/flows/test_binding_v2_settings\.py\$|^$P/tests/service/apis/test_ai_settings\.py\$|^$P/tests/flows/texts_digest\.py\$|^$A/scripts/(section4|planted-breaks)-RPA4\.sh\$" | grep -c .)"
  n_web_slot="$(git grep -c -F '{쪽 글}' -- apps/web | grep -c .)"
  git grep -l -F '{쪽 글}' -- "$A" apps/web | sed 's/^/  {쪽 글} 있는 파일: /'
  # 판 말 그물: 흉내·서버 선언에 (S2)·(S3)·쪽 붙이기·쪽 → 목차·(ms) 0(머리말 포함)
  n_board="$(grep -c -E '\(S2\)|\(S3\)|쪽 붙이기|쪽 → 목차|\(ms\)' apps/web/e2e/ai-settings-drafting.ts "$P/flows/prompt_model_v2.py" | awk -F: '{s+=$2} END {print s}')"
  echo "  키 꼴 $n_key · .pdf/.xlsx/.docx/.ipynb $n_bin · esg-lab import $n_lab · 실재 기업명 낱말 $n_name · {쪽 글} 그물 밖 $n_slot · web {쪽 글} $n_web_slot · 판 말 그물 $n_board"
  [ "$n_key" = 0 ] && [ "$n_bin" = 0 ] && [ "$n_lab" = 0 ] && [ "$n_name" = 0 ] && [ "$n_slot" = 0 ] && [ "$n_web_slot" = 0 ] && [ "$n_board" = 0 ]
}

s8() {
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen \
    python manage.py makemigrations --check --dry-run 2>&1 | grep -v -i warn | tail -2 | sed 's/^/  /'; exit "${PIPESTATUS[0]}")
}

# 9: generated/ 를 다시 뽑아 cmp(0 바뀜 — 작업본 = 기준) · apps/web typecheck
s9() {
  local g="$OUT/s9-generated" code=0 f
  rm -rf "$g" && mkdir -p "$g"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business \
    uv run --frozen python manage.py export_openapi) > "$g/openapi.json" 2> "$g/export.log" || { echo "  ★ export 실패"; return 1; }
  (cd "$A" && pnpm dlx openapi-typescript@7.13.0 "$g/openapi.json" -o "$g/api.d.ts") > "$g/ts.log" 2>&1 \
    || { echo "  ★ openapi-typescript 실패"; return 1; }
  shasum -a 256 "$g/openapi.json" | cut -d' ' -f1 > "$g/api.d.ts.source-sha256"
  for f in openapi.json api.d.ts api.d.ts.source-sha256; do
    if cmp -s "$g/$f" "$A/generated/$f"; then echo "  cmp $f = 작업본"; else echo "  ★ cmp $f ≠ 작업본"; code=1; fi
  done
  git diff --quiet "$BASE" -- "$A/generated" || { echo "  ★ generated 가 기준과 다름"; code=1; }
  (cd apps/web && pnpm -s typecheck > "$OUT/s9-web-typecheck.log" 2>&1) || { echo "  ★ apps/web typecheck"; code=1; }
  echo "  apps/web typecheck $(tail -1 "$OUT/s9-web-typecheck.log")"
  return $code
}

s10() {
  local blog="$OUT/s10-business.log" slog="$OUT/s10-security.log" bcode scode
  if [ "$(docker compose ps --status running --services 2> /dev/null | grep -c '^postgres$')" = 0 ]; then
    docker compose up -d --wait postgres > "$OUT/s10-up.log" 2>&1 || { tail -3 "$OUT/s10-up.log"; return 1; }
  fi
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db esgapi/drafting) > "$blog" 2>&1
  bcode=$?
  echo "  업무 $(tail -1 "$blog") EXIT=$bcode"
  (cd "$A" && env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/test-security.sh -p no:cacheprovider -k drafting) > "$slog" 2>&1
  scode=$?
  echo "  보안 $(tail -1 "$slog") EXIT=$scode"
  [ "$bcode" = 0 ] && [ "$scode" = 0 ]
}

s11() {
  local log code
  if [ "$(git rev-parse HEAD)" = "$BASE" ]; then
    log="$(python3 -I scripts/check_test_weakening.py --warn main HEAD 2>&1)"
  else
    log="$(python3 -I scripts/check_test_weakening.py main HEAD 2>&1)"
  fi
  code=$?
  echo "$log" > "$OUT/s11-weaken.log"
  echo "$log" | tail -3 | sed 's/^/  /'
  return $code
}

s12() {
  local log
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY "$A/scripts/planted-breaks-RPA4.sh" 2>&1)"
  echo "$log" > "$OUT/s12-planted.log"
  echo "$log" | sed 's/^/  /'
  echo "$log" | grep -q "^FINGERPRINT=same" \
    && [ "$(echo "$log" | sed -n 's/^PLANTED=\([0-9]*\)\/\([0-9]*\)$/\1 \2/p' | awk '$1==$2{print "ok"}')" = ok ]
}

s13() {
  local code=0 t
  [ -f "$MSG" ] || { echo "  ★ 메시지 파일이 없다: $MSG"; return 1; }
  for t in "Ticket: MARC-TICK-449" "Concerns: MARC-ISSUE-514" "Concerns: MARC-ISSUE-490" "Derives-from: MARC-ENT-459" \
    "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"; do
    grep -q -x -F "$t" "$MSG" || { echo "  ★ 트레일러 없음: $t"; code=1; }
  done
  for t in Constraint Rejected Directive Not-tested; do
    grep -q -E "^$t: " "$MSG" || { echo "  ★ 트레일러 없음: $t:"; code=1; }
  done
  head -1 "$MSG" | grep -q -E "^fix\(drafting\): RPA4 (①|③) " || { echo "  ★ 제목 꼴"; code=1; }
  echo "  제목 $(head -1 "$MSG") · 트레일러 $(grep -c -E '^[A-Z][A-Za-z-]+: ' "$MSG") 줄"
  return $code
}

WEB_PORT_V="$(sed -n 's/^WEB_PORT=//p' .env | grep . || echo 15173)"
s14() {
  local log code=0 n_vis
  log="$(WEB_PORT="$WEB_PORT_V" WEB_TEST_PORT="$((WEB_PORT_V + 1))" apps/web/scripts/verify.sh 2>&1)"
  echo "$log" > "$OUT/s14-web-verify.log"
  echo "$log" | grep -E "VERIFY=" | sed 's/^/  /'
  echo "$log" | grep -q "VERIFY=PASS" || code=1
  (cd apps/web && pnpm --filter @esg/web exec vitest run src/entities/drafting-setting src/app/admin/ai-setting-modules.test.ts) \
    > "$OUT/s14-vitest.log" 2>&1 || code=1
  grep -E "^ *Tests " "$OUT/s14-vitest.log" | sed 's/^/  vitest 표적 /'
  (cd apps/web && WEB_PORT="$WEB_PORT_V" WEB_TEST_PORT="$((WEB_PORT_V + 1))" pnpm --filter @esg/web exec playwright test \
    e2e/ai-settings-drafting.spec.ts) > "$OUT/s14-playwright.log" 2>&1 || code=1
  grep -E "passed|failed|flaky" "$OUT/s14-playwright.log" | tail -2 | sed 's/^/  playwright /'
  n_vis="$(grep -c -i -E 'drafting|AD-02-RP' apps/web/e2e/visual.spec.ts)"
  echo "  e2e/visual.spec.ts 의 drafting·AD-02-RP 장 $n_vis"
  return $code
}

s15() {
  local log code
  log="$(env -u OPENAI_API_KEY -u ANTHROPIC_API_KEY scripts/verify.sh --fast 2>&1)"
  code=$?
  echo "$log" > "$OUT/s15-verify-fast.log"
  echo "$log" | grep -E "VERIFY_FAST=" | sed 's/^/  /'
  [ "$code" = 0 ] && echo "$log" | grep -q "VERIFY_FAST=PASS"
}

step 1 "순수 시험(drafting — not django_db) N0 → N1" s1
step 2 "lint-imports 전부 KEPT·수 = 기준" s2
step 3 "check_test_layout" s3
step 4 "pyright drafting 0 · ruff check · ruff format --check" s4
step 5 "경로 §1-2 안 · 0줄 목록 · 남의 땅 diff 0" s5
step 6 "선언 지문(바뀐 바이트 = S2 system·S2 user 머리·S3 system 표지 한 줄뿐)" s6
step 7 "금지 글·키 꼴·바이너리·esg-lab import·실재 기업명 0 · {쪽 글}·판 말 그물" s7
step 8 "makemigrations --check --dry-run" s8
step 9 "generated/ 다시 뽑아 cmp(0 바뀜) · apps/web typecheck" s9
if [ "$CONTAINERS" = 1 ]; then
  step 10 "업무(drafting) · 보안(-k drafting)" s10
else
  not_run 10 "업무·보안(컨테이너)" "--with-containers 없음"
fi
step 11 "WEAKEN(check_test_weakening — 커밋 전엔 --warn)" s11
if [ "$PLANTED" = 1 ]; then step 12 "심은 파손" s12; fi
if [ -n "$MSG" ]; then step 13 "커밋 메시지 트레일러(§5)" s13; fi
step 14 "apps/web verify · 표적 vitest · playwright drafting · visual 장 0" s14
step 15 "뿌리 verify.sh --fast" s15
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" -eq 0 ]
