#!/usr/bin/env bash
# S3V1(MARC-TICK-575) 발주서 §4 자기검증 — 워크트리 뿌리에서 돌린다: apps/api-py/scripts/section4-S3V1.sh
#   줄마다 「EXIT=<코드> <초>s <이름>」 또는 「<이름> = <값>」. 끝에 SECTION4=PASS|FAIL.
#   git 밖 도구(짓개·위생·★J 대조 — 받은 양식의 실재 기업명을 읽으므로 저장소에 두지 않는다)는 S3V1_OUT
#   (기본 <워크트리>/../S3V1.out)에서 부르고, 없으면 SKIP 으로 찍는다(병합 뒤 main 에서 돌릴 때).
#   Postgres(.env 의 compose)가 떠 있어야 test-business 가 돈다. lock 이 있으면 돌지 않는다.
set -u
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
MAIN_GIT="$(git rev-parse --git-common-dir)"
if [ -e "$MAIN_GIT/verify.lock" ]; then echo "verify.lock 있음 — 돌지 않는다" >&2; exit 3; fi
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export WEB_TEST_PORT="${WEB_TEST_PORT:-21911}"  # 러너 21911 · 검증 21912(발주서 머리)
B=efa07262
# 범위 diff 의 바닥: main 을 들인 뒤에는 main(merge-base) — 이 밴드의 변경만 본다. 들이기 전이면 BASE 와 같다.
SB="${S3V1_SCOPE_BASE:-$(git merge-base HEAD main)}"
echo "scope-base = $SB (BASE $B)"
A=apps/api-py/esgapi/inventory
OUT="${S3V1_OUT:-$ROOT/../S3V1.out}"
R11="/Users/leedongeon/Desktop/marcspon/received/2026-11-10/배출계수_통합_DB_v1.1 .xlsx"
R22="/Users/leedongeon/Desktop/marcspon/received/2026-10-22/Scope3_템플릿_수정본_v2.2.xlsx"
fail=0

gate() { # <이름> <명령…>
  local name="$1" s=$SECONDS rc; shift
  "$@" > "/private/tmp/s4-s3v1-$name.log" 2>&1; rc=$?
  echo "EXIT=$rc $((SECONDS - s))s $name"
  [ "$rc" = 0 ] || fail=1
}
want() { # <이름> <값> <기대>
  local mark="ok"; [ "$2" = "$3" ] || { mark="BAD(기대 $3)"; fail=1; }
  echo "$1 = $2 $mark"
}

gate pytest-inventory-non-db bash -c "cd apps/api-py && uv run --frozen pytest esgapi/inventory -q -n 2 -m 'not django_db'"
gate same-factor+engine bash -c "cd apps/api-py && uv run --frozen pytest esgapi/inventory/tests/service/utils/test_scope3_factors_same.py esgapi/inventory/tests/engines/scope3/colab_157 -q -m 'not django_db'"
gate importlinter bash -c "cd apps/api-py && uv run --frozen lint-imports"

want factors-same-diff "$(git diff $SB -- $A/tests/service/utils/test_scope3_factors_same.py | wc -l | tr -d ' ')" 0
want engines-files "$(git diff --name-only $SB -- $A/engines | tr '\n' ' ' | sed 's/ $//')" \
  "$A/engines/scope3/colab_157/company_mapping.py $A/engines/scope3/colab_157/spend.py"
want forbidden-diff "$(git diff $SB -- $A/tools $A/contracts apps/api-py/esgapi/core apps/api-py/esgapi/runs apps/api-py/esgapi/config apps/api-py/.importlinter apps/api-py/pyproject.toml apps/api-py/uv.lock packages | wc -l | tr -d ' ')" 0
want web-files "$(git diff --name-only $SB -- apps/web | tr '\n' ' ' | sed 's/ $//')" \
  "apps/web/src/entities/ghg-scope3/config/text.ts apps/web/src/entities/run-log/config/text.ts"
want run-log-numstat "$(git diff --numstat $SB -- apps/web/src/entities/run-log/config/text.ts | cut -f1-2 | tr '\t' '/')" "2/2"
want outside-1-2 "$(git diff --name-only $SB | grep -vE '^apps/api-py/(esgapi/inventory/|generated/|scripts/(planted-breaks|section4)-S3V1\.sh$)|^apps/web/src/entities/(ghg-scope3|run-log)/config/text\.ts$' | wc -l | tr -d ' ')" 0
want s3sheets-diff "$(git diff --name-only $SB -- $A/tests/test_s3sheets_* $A/tests/s3sheets_* | wc -l | tr -d ' ')" 0
want new-xlsx "$(git diff --name-only --diff-filter=A $SB -- '*.xlsx' | tr '\n' ' ' | sed 's/ $//')" "$A/data/scope3/scope3-template-v2.2.xlsx"
# 셈 줄: 바닥(SB) 의 수 + 이 밴드가 더한 17(1752 → 1769, BASE 에서 잰 값)
base_tests="$(git grep -h 'def test_' "$SB" -- "$A/tests" | wc -l | tr -d ' ')"
want def-test-count "$(grep -rh 'def test_' $A/tests | wc -l | tr -d ' ')" "$((base_tests + 17))"
echo "  (scope-base $base_tests + 17 · BASE efa07262 $(git grep -h 'def test_' $B -- "$A/tests" | wc -l | tr -d ' '))"
want old-terms "$(grep -rn '상류 임차\|하류 임차' apps/api-py/esgapi apps/web/src apps/web/e2e apps/api-py/generated | wc -l | tr -d ' ')" 0
echo "old-v2.1-text(옛 판을 말하는 글만 남아야 함):"
grep -rnE 'v2\.1|scope3-template-v2\.1|수정본_v2\.1' apps/api-py/esgapi apps/web/src apps/web/e2e apps/api-py/generated \
  --include='*.py' --include='*.ts' --include='*.tsx' --include='*.json' --include='*.md' | grep -v '/greenwash/' | cut -c1-140 | sed 's/^/  /'

if [ -f "$R11" ] && [ -f "$R22" ]; then
  want received-book-sha "$(shasum -a 256 "$R11" | cut -c1-16)" 2947b451912ce1fd
  want received-template-sha "$(shasum -a 256 "$R22" | cut -c1-16)" 654243beda187ea1
else
  echo "received-sha = SKIP(받은 원본 없음)"
fi
want book-sha "$(shasum -a 256 $A/data/scope3/scope3-factor-book.xlsx | cut -c1-16)" 2b76427c174a90d3
want template-sha "$(shasum -a 256 $A/data/scope3/scope3-template-v2.2.xlsx | cut -c1-16)" c51abfd6e023424b

if [ -f "$OUT/build/hygiene.py" ] && [ -f "$R22" ]; then
  python3 -I "$OUT/build/hygiene.py" $A/data/scope3/*.xlsx | tail -1 | sed 's/^/  /'
  python3 -I "$OUT/build/hygiene.py" $A/data/scope3/*.xlsx > /dev/null || fail=1
else
  echo "HYGIENE = SKIP(git 밖 도구 없음)"
fi
if [ -f "$OUT/build/check_j2.py" ] && [ -f "$R22" ]; then
  J2="$(cd apps/api-py && uv run --frozen python "$OUT/build/check_j2.py" 2>&1 | tail -1)"
  want template-engine-same-as-received "$J2" "bodies equal after name swap: True"
else
  echo "template-engine-same-as-received = SKIP(git 밖 도구 없음)"
fi

gate planted-breaks bash apps/api-py/scripts/planted-breaks-S3V1.sh
grep -E "^(FINGERPRINT|PLANTED)=" /private/tmp/s4-s3v1-planted-breaks.log | sed 's/^/  /'
gate test-business apps/api-py/scripts/test-business.sh -n 2
gate tsc pnpm --filter web exec tsc --noEmit
gate web-verify apps/web/scripts/verify.sh
gate verify-fast scripts/verify.sh --fast

echo "SECTION4=$([ "$fail" = 0 ] && echo PASS || echo FAIL)"
[ "$fail" = 0 ]
