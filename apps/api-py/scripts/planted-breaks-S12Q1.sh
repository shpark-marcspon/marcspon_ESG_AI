#!/usr/bin/env bash
# 밴드 S12Q1(MARC-TICK-573)의 심은 파손: 하나씩 심고, 그것을 잡아야 하는 시험이 이름으로 빨개지는지 본다.
#   사용: apps/api-py/scripts/planted-breaks-S12Q1.sh        마지막 줄 PLANTED=<잡은 수>/<심은 수> FINGERPRINT=same|changed
#   ★ 돌리기 전 main 저장소의 .git/verify.lock 이 없어야 한다(있으면 종료 2). Postgres(compose esg-app-S12Q1)·e2e 포트
#     WEB_TEST_PORT(기본 21901 — 검증자는 21902 를 준다)를 쓴다.
# 심기 전 파일을 저장소 밖 임시 폴더에 베껴 두었다가 되돌린다(git 을 쓰지 않는다. 죽어도 trap 이 되돌린다).
# 끝에서 베껴 둔 파일의 sha256 과 `git status --porcelain` 이 처음과 같은지 잰다(FINGERPRINT). 다르면 종료 1.
# 「잡음」 = 그 실행이 0 이 아닌 코드로 끝나고 적어 둔 시험 이름(일부)이 실패 줄에 있다. P17 은 grep 이 1 줄 이상.
set -u
export PYTHONDONTWRITEBYTECODE=1
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
MAIN="$(cd "$ROOT/../../esg-app" && pwd)"
[ -e "$MAIN/.git/verify.lock" ] && { echo "verify.lock 이 있다 — 멈춘다" >&2; exit 2; }
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
PORT="${WEB_TEST_PORT:-21901}"

A=apps/api-py/esgapi/inventory
W=apps/web/src
ACT="$A/service/actions/index_selection.py"
UTIL="$A/service/utils/index_selection.py"
FAKE="$W/entities/ghg/api/testing.ts"
E2E_FAKE=apps/web/e2e/ghg-server.ts
INV="$W/pages/ghg-inventory/ui/InventoryScreen.tsx"
DETAIL="$W/pages/ghg-inventory/ui/EntryDetailDialog.tsx"
SITE="$W/pages/ghg-inventory/ui/EntrySiteBlock.tsx"
ENTRIES="$W/entities/ghg/model/entries.ts"
TOASTER="$W/shared/ui/toast/ui/Toaster.tsx"
STORE="$W/shared/ui/toast/ui/store.ts"
CSS="$W/shared/ui/toast/ui/toast.css"
S9="$W/pages/ghg-inventory/ui/EntryFactorEditDialog.tsx"
S8="$W/pages/ghg-inventory/ui/EntryFactorDialog.tsx"
LEAF="$W/pages/ghg-index-pool/ui/FacilityPanel.tsx"
FILES=("$ACT" "$UTIL" "$FAKE" "$E2E_FAKE" "$INV" "$DETAIL" "$SITE" "$ENTRIES" "$TOASTER" "$STORE" "$CSS" "$S9" "$S8" "$LEAF")

keep="$(mktemp -d)"; log="$(mktemp -d)"
for f in "${FILES[@]}"; do
  [ -f "$f" ] || { echo "파일이 없다: $f" >&2; exit 2; }
  cp "$f" "$keep/$(echo "$f" | tr / _)"
done
sums() { shasum -a 256 "${FILES[@]}"; }
sums > "$keep/.sums-before"
git status --porcelain > "$keep/.status-before"
restore_files() { for f in "${FILES[@]}"; do cp "$keep/$(echo "$f" | tr / _)" "$f"; done; }
trap 'restore_files' EXIT INT TERM

edit() { # <파일> <있던 글자> <바꿀 글자> — 있던 글자가 정확히 한 번(아니면 종료 3)
  python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심을 자리가 {text.count(old)}곳이다(1곳이어야 한다): {path}: {old[:60]!r}")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
  [ $? -eq 0 ] || exit 3
}
pure() { (cd apps/api-py && uv run --frozen pytest -q -rf -p no:cacheprovider "$@"); }
business() { (cd apps/api-py && bash -c '. scripts/db-env.sh; export TEST_DATABASE_URL_PY_OWNER="$OWNER_DATABASE_URL"; uv run --frozen pytest -q -rf -p no:cacheprovider "$@"' _ "$@"); }
vit() { (cd apps/web && pnpm exec vitest run "$@"); }
e2e() { (cd apps/web && WEB_TEST_PORT="$PORT" pnpm exec playwright test e2e/ghg-server.spec.ts -g "$1"); }

total=0; ok=0
judge() { # <번호> <설명> <잡을 시험 이름(일부)> — 앞에서 돌린 실행의 로그 $log/<번호>
  local n="$1" what="$2" want="$3" code
  code="$(cat "$log/$n.code")"
  total=$((total + 1))
  if [ "$code" != 0 ] && grep -F -- "$want" "$log/$n" | grep -qE "FAIL|FAILED|✘|failed|×"; then
    ok=$((ok + 1)); echo "  $n RED   $what — $want"
  else
    echo "  $n MISS  $what — $want (exit $code)"
  fi
}
run() { # 실행마다 lock 을 다시 본다(lock 아래서는 부분 실행도 0 — 심은 것은 trap 이 되돌린다).
  local n="$1"; shift
  [ -e "$MAIN/.git/verify.lock" ] && { echo "verify.lock 이 생겼다 — $n 앞에서 멈춘다(EXIT=2)" >&2; exit 2; }
  "$@" > "$log/$n" 2>&1; echo $? > "$log/$n.code"; restore_files
}

echo "== 심은 파손(S12Q1)"
edit "$ACT" '    found = _problem(wanted, alive_leaves, versions, new)' '    if any(company_facility_counts(company_id).get(locked[n].facility_code_id or 0, 0) == 0 for n in new if n in alive_leaves):
        transaction.set_rollback(True)
        return Invalid({"facilityNodeIds": "심은 시설 0 거절"})
    found = _problem(wanted, alive_leaves, versions, new)'
run P1 business esgapi/inventory/tests/service/actions/test_index_selection.py
judge P1 "서버 시설 0 거절 되살림" test_a_leaf_without_facilities_is_chosen_and_its_detail_is_empty

edit "$UTIL" '            can = selectable(node_id in factored)' '            can = selectable(node_id in factored) and count > 0'
run P2 pure esgapi/inventory/tests/service/utils/test_index_selection.py
judge P2 "selectable 시설 수 되살림(위 단만)" test_a_leaf_without_facilities_counts_toward_its_upper_node

edit "$ACT" '    if any(node_id not in versions for node_id in new):
        return NO_FACTOR
' ''
run P3 business esgapi/inventory/tests/service/actions/test_index_selection.py
judge P3 "NO_FACTOR 뺌" test_every_refusal_is_422_and_writes_nothing

edit "$FAKE" "    if (fresh.some((id) => defaultFactorOf(id) === undefined))" "    if (fresh.some((id) => facilityCount(leaves.get(id)!.facilityCodeId) === 0))
      return refusal(422, 'VALIDATION_ERROR', { facilityNodeIds: ['심은 시설 0'] });
    if (fresh.some((id) => defaultFactorOf(id) === undefined))"
run P4 vit src/entities/ghg/api/selection.test.ts
judge P4 "가짜(testing.ts)만 시설 0 거절" "save 422 두 칸"

edit "$E2E_FAKE" "        if (fresh.some((id) => !hasDefault(id)))" "        if (fresh.some((id) => facilityCount(leaves.get(id)!.codeId) === 0))
          return badNodes('심은 시설 0');
        if (fresh.some((id) => !hasDefault(id)))"
run P5 e2e "S12-05 고객사"
judge P5 "e2e 흉내만 시설 0 거절" "S12-05 고객사"

edit "$INV" '          save={save}
        />
      )}
    </div>' '          save={save}
        />
      )}
      {loaded.state === '"'"'ready'"'"' && !loaded.base.configured && (
        <div role="dialog" aria-label="심은 창" />
      )}
    </div>'
run P6 vit src/pages/ghg-inventory/ui/InventoryScreen.test.tsx
judge P6 "빈 해 창 되살림" "S12-02a 고른 잎 0"

edit "$DETAIL" '                {index.sites.length === 0 && (' '                {index.sites.length >= 0 && ('
run P7 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx -t "S12-05"
judge P7 "sites 있어도 안내" "sites 가 있으면 안내 0"

edit "$ENTRIES" '  if (on && draft.edited.na) return draft;
' ''
run P8 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx -t "S12-03 추정치"
judge P8 "추정 켬이 N/A 줄도" "N/A 줄은 켜지 않음"

edit "$ENTRIES" '      !edited.na && edited.values.some((value) => value.estimated),' '      !edited.na && edited.values.every((value) => value.estimated),'
run P9 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx -t "S12-03 추정치"
judge P9 "켜짐 = 「전부」" "섞임"

edit "$DETAIL" '                  estimatedDisabled={locked || lockBusy || saving}' '                  estimatedDisabled={lockBusy || saving}'
run P10 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx -t "S12-03 추정치"
judge P10 "잠긴 판 추정 단추 켬" "잠긴 판·저장 중 단추 끔"

edit "$DETAIL" '                        factorEdit={
                          pool ?' '                        factorEdit={
                          pool || !pool ?'
run P11 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx -t "출처 칸"
judge P11 "[수정]이 고객사에도" "고객사(pool 없음)"

edit "$SITE" '                        {factorEdit && draft.before && (' '                        {factorEdit && ('
run P12 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx -t "출처 칸"
judge P12 "저장 안 된 행 [수정]" "고객사(pool 없음)"

edit "$TOASTER" "  if (items.length === 0 || typeof document === 'undefined') return null;" "  if (typeof document === 'undefined') return null;"
run P13 vit src/shared/ui/toast
judge P13 "포털 늘 붙음(★D)" "토스트가 없으면 포털도 없다"

edit "$CSS" '@media (prefers-reduced-motion: no-preference) {' '.toast-m-in {
  animation: toast-m-in 220ms both;
}
@media (prefers-reduced-motion: no-preference) {'
run P14 vit src/shared/ui/toast
judge P14 "reduced-motion 움직임" "no-preference 안"

edit "$STORE" '  const kept = staying.slice(0, MAX - 1).map((item) => item.id);' '  const kept = staying.map((item) => item.id);'
run P15 vit src/shared/ui/toast
judge P15 "넷째가 오래된 것을 안 지움" "넷째가 오면"

edit "$TOASTER" '        timer.current = null;
        dismissToast(item.id);' '        timer.current = null;'
run P16 vit src/shared/ui/toast
judge P16 "3초 뒤 남음" "3초 뒤 나가는 움직임"

edit "$TOASTER" '          aria-label={item.closeLabel}' '          aria-label={item.closeLabel || '"'"'닫기'"'"'}'
grep -rnE "[가-힣]" apps/web/src/shared/ui/toast --include='*.ts' --include='*.tsx' | grep -v '\.test\.' | grep -vE ':\s*(//|\*|/\*)' > "$log/P17"; echo $? > "$log/P17.code"; restore_files
total=$((total + 1))
if [ "$(cat "$log/P17.code")" = 0 ]; then ok=$((ok + 1)); echo "  P17 RED   shared 안 글자 — §4 한글 grep $(wc -l < "$log/P17") 줄"; else echo "  P17 MISS  shared 안 글자"; fi

# ⑤ S12-03a: [수정]이 빈 판으로 엶 · 풀 계수 저장 뒤에도 S8 을 다시 엶.
edit "$S9" '          customFactorFormOf(filled, options.value)' '          emptyFactorForm(options.value)'
run P18 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge P18 "[수정] 빈 판" "S12-03a 직접 입력 저장 뒤"

edit "$DETAIL" "    if (site && row?.factor && 'customId' in row.factor)" "    if (site && row?.factor)"
run P19 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge P19 "풀 계수도 S8 다시 엶" "#2 S9 선택"

# 표 밖(러너): 성공 톤이 role=alert 로 바뀌면(permits 3 status·polite) 잡는다.
edit "$TOASTER" "      role={error ? 'alert' : 'status'}" "      role=\"alert\""
run X1 vit src/shared/ui/toast
judge X1 "성공 톤 role=alert" "성공 톤: role status"

# 표 밖(러너) ⑤: 저장 뒤 창 가스 표가 끈 가스까지 보이면 잡는다.
edit "$S8" '  const included = factor.gases.filter((gas) => gas.enabled);' '  const included = factor.gases;'
run X2 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge X2 "저장 뒤 창이 끈 가스도" "S12-03a 직접입력 계수 = 저장 뒤 창 꼴"

# 표 밖(검증 ⑤ B1): 저장 뒤 창 제목 줄 [수정]의 끔에서 dirty·disabled 를 하나씩 뺌.
edit "$S8" '                  className="min-w-20"
                  data-testid="entry-factor-edit-open"
                  disabled={edit.disabled || edit.dirty}' '                  className="min-w-20"
                  data-testid="entry-factor-edit-open"
                  disabled={edit.disabled}'
run X20 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge X20 "저장 뒤 창 [수정] 고친 동안 켬" "제목 줄 [수정] 끔"

edit "$S8" '                  className="min-w-20"
                  data-testid="entry-factor-edit-open"
                  disabled={edit.disabled || edit.dirty}' '                  className="min-w-20"
                  data-testid="entry-factor-edit-open"
                  disabled={edit.dirty}'
run X22 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge X22 "저장 뒤 창 [수정] 잠긴 판 켬" "제목 줄 [수정] 끔"

# 표 밖(러너) ⑥ S12-07: 종류를 묶음에서 안 읽음 · 목록 밖 지금 값을 지움 · 묶음 머리가 영문 kind.
edit "$LEAF" '                change({ unitKind: kind, unit });' "                change({ unitKind: 'mass', unit });"
run X30 vit src/pages/ghg-index-pool/ui/FacilityPanel.test.tsx
judge X30 "종류를 묶음에서 안 읽음" "고르면 종류는 그 묶음에서"

edit "$LEAF" "              {unitPicked !== '' && !unitListed && (" "              {false && !unitListed && ("
run X31 vit src/pages/ghg-index-pool/ui/FacilityPanel.test.tsx
judge X31 "목록 밖 지금 값 지움" "있는 잎을 열면 그 단위가"

edit "$LEAF" '                    label={GHG_TEXT.pool.unitKinds[one.kind] ?? one.kind}' '                    label={one.kind}'
run X32 vit src/pages/ghg-index-pool/ui/FacilityPanel.test.tsx
judge X32 "묶음 머리 영문 kind" "드롭다운 하나"

# 표 밖(러너) ⑦ 디자인 대조: 추정 끔이 흐리지 않음(F1) · 풀 계수 보기에도 사이 32(F2 샘) · S9 칸 왼쪽으로 되돌림(F5).
edit "$DETAIL" "        estimated ? '' : 'opacity-40'" "        ''"
run X40 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge X40 "추정 끔 흐림 0" "#7 → S12-03 추정치 단추 하나"

edit "$S8" "          custom && 'gap-8'," "          'gap-8',"
run X41 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge X41 "풀 계수 보기에도 사이 32" "풀 계수 보기는 옛 꼴 그대로"

edit "$S9" "className={cn(CELL, 'truncate text-center')}" "className={cn(CELL, 'truncate')}"
run X43 vit src/pages/ghg-inventory/ui/EntryDetailDialog.test.tsx
judge X43 "S9 칸 왼쪽" "S9 꼴(값 파일 ③)"

restore_files
trap - EXIT INT TERM
sums > "$keep/.sums-after"
git status --porcelain > "$keep/.status-after"
if cmp -s "$keep/.sums-before" "$keep/.sums-after" && cmp -s "$keep/.status-before" "$keep/.status-after"; then
  echo "PLANTED=$ok/$total FINGERPRINT=same"
  [ "$ok" = "$total" ] || exit 1
else
  echo "PLANTED=$ok/$total FINGERPRINT=changed"; exit 1
fi
