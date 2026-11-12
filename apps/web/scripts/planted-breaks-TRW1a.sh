#!/usr/bin/env bash
# 밴드 TRW1a 의 심은 파손(발주서 §3-4).   사용: apps/web/scripts/planted-breaks-TRW1a.sh
# 파손을 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P17(발주서 표) · R1(러너 몫).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-TRW0b.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 경계마다 돈다: 대상 파일이 아직 없는 파손(뒤 경계 몫)은 「뒤 경계」로 적고 셈에 넣지 않는다. 이름 무늬는 실패 줄(×·✘·FAIL)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
SV=$S/entities/translation/api/server.ts
CB=$S/entities/translation/api/contract/batch.ts
AD=$S/entities/translation/model/adapt.ts
SE=$S/entities/session/model/session.ts
DB=$S/shared/ui/download-button/ui/DownloadButton.tsx
RUN=$S/pages/translation-run/ui/RunScreen.tsx
LIST=$S/pages/translation-list/ui/ListScreen.tsx
NEW=$S/pages/translation-new/model/form.ts
NTS=$S/pages/translation-new/ui/NewTranslationScreen.tsx
TRR=$S/app/translation/TranslationRoutes.tsx
GWR=$S/app/greenwash/GreenwashRoutes.tsx
E2E=$W/e2e/translation-server.ts
TOUCHED=()
for file in "$SV" "$CB" "$AD" "$SE" "$DB" "$RUN" "$LIST" "$NEW" "$NTS" "$TRR" "$GWR" "$E2E"; do
  [ -f "$file" ] && TOUCHED+=("$file")
done

KEEP="$(mktemp -d)"
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
for file in "${TOUCHED[@]}"; do
  mkdir -p "$KEEP/$(dirname "$file")"
  cp "$file" "$KEEP/$file"
done
sums_before="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"

restore() { local each; for each in "${TOUCHED[@]}"; do cp "$KEEP/$each" "$each"; done; }
trap 'restore' EXIT INT TERM

passed=0
total=0
later=0
OUT="$KEEP/out.txt"

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
changed_lines() { diff "$KEEP/$1" "$1" | grep -c '^<'; }

report() { # <번> <ok|fail> <말>
  total=$((total + 1))
  if [ "$2" = ok ]; then passed=$((passed + 1)); echo "  $1  빨개짐   $3"; else echo "  $1  못 잼    $3"; fi
}

# <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로 — 실패 줄에서 찾는다)>
code_break() {
  local n="$1" file="$2"
  if [ ! -f "$file" ]; then later=$((later + 1)); echo "  $n  뒤 경계  $6 ($file 없음)"; return; fi
  restore
  if ! plant "$file" "$3" "$4" "$5"; then report "$n" fail "심지 못했다: $6"; return; fi
  if [ "$(changed_lines "$file")" != 1 ]; then report "$n" fail "바뀐 줄이 하나가 아니다: $6"; restore; return; fi
  bash -c "$7" > "$OUT" 2>&1
  local code=$? missing=0 pattern red_lines
  red_lines="$(grep -E '^ *(×|✘|FAIL) ' "$OUT")"
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" <<< "$red_lines" || { missing=$((missing + 1)); echo "       실패 줄에 없다: $pattern"; }
  done <<< "$8"
  local red
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-70 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
L=src/app/guards/layers.test.ts
E=src/entities/translation
API=$E/api/server.test.ts

echo "▶ 발주서 표 (P1~P17)"
code_break P1 "$SV" "const planned = input.parts.map" "optionsOf(input, part, range, batchId)" "optionsOf(input, part, range, makeKey())" \
  "파트마다 새 batchId" \
  "$VT $API" \
  "batchId 같음·launchKey 같음"
code_break P2 "$SV" "async startBatch(input)" "const launchKey = makeKey();" "const launchKey = batchId;" \
  "launchKey = batchId" \
  "$VT $API" \
  "batchId 같음·launchKey 같음"
code_break P3 "$SV" "client.POST('/runs'" "params: { header: { 'Idempotency-Key': makeKey() } }," "params: {}," \
  "Idempotency-Key 빠짐" \
  "$VT $API" \
  "Idempotency-Key 서로 다름"
code_break P4 "$SV" "planned.some(" "optionsOctets(options) > OPTIONS_MAX_OCTETS" "optionsOctets(options) >= OPTIONS_MAX_OCTETS" \
  "256KiB 경계 > → >=" \
  "$VT $API" \
  "옵션 바이트 = 상한이면 보내고"
code_break P5 "$SV" "export function optionsOf" "ceoPageLimit: part === 'ceo' ? CEO_PAGE_LIMIT : null," "...{}," \
  "ceoPageLimit 빠짐" \
  "$VT $API" \
  "ceoPageLimit 6/null"
code_break P6 "$SV" "async archive(" "if (missing === null || !/" "if (missing !== null && !/" \
  "X-Archive-Missing 없을 때 0" \
  "$VT $API" \
  "머리 null(없음·수 아님) → 거절"
code_break P7 "$SV" "async archive(" "return { kind: 'too_large' };" "return { kind: 'nothing' };" \
  "409 둘 뒤바뀜(ARCHIVE_TOO_LARGE → nothing)" \
  "$VT $API" \
  "409 ARCHIVE_TOO_LARGE → too_large"
code_break P8 "$SV" "subscribeBatch(" "if (batch.state === 'active')" "if (batch.state !== 'failed')" \
  "폴링이 done 에도 계속" \
  "$VT $E/hooks/hooks.test.tsx" \
  "active 면 pollMs 마다 다시, done 이 되면 멈춘다"
code_break P9 "$AD" "export function tabStateOf" "outcome === 'partial' ? 'failed_partial'" "outcome === 'partial' ? 'done'" \
  "partial 을 done 으로" \
  "$VT $E/model/adapt.test.ts" \
  "done · 요약 partial"
code_break P10 "$CB" "const run = obj({" "digest: digestSchema.nullable()," "digest: digestSchema.nullable().transform((d) => d ?? ({ outcome: 'done' } as unknown as TranslationDigest))," \
  "digest null 을 값으로 삼킴(?? 꼴)" \
  "$VT $API" \
  "끝나지 않은 파트의 digest 는 null 그대로"
code_break P11 "$SE" "const own: readonly SessionArea[]" ": ['greenwash', 'translation'];" ": ['greenwash'];" \
  "session own 에서 translation 뺌(고객사)" \
  "$VT src/entities/session/model/session.test.ts" \
  "service·admin: /translation/** stay"
code_break P12 "$DB" "const press = async" "if (!('kind' in file)) saveBlob(file.blob, file.fileName);" "if ('kind' in file) throw new Error('handled');" \
  "handled 를 실패로(무시)" \
  "$VT src/shared/ui/download-button" \
  "load 가 handled 로 끝나면 내려받지 않고 실패 글도 0"
code_break P13 "$RUN" "// [이 파트만 다시]는 TRW1b" "<PartFailureCard" "<PartFailureCard onRetry={() => undefined}" \
  "거절 카드에 onRetry" \
  "$VT src/pages/translation-run" \
  "서버 오류(failed) 파트도 다시 단추 0"
code_break P14 "$LIST" "const showMine" "const showMine = !operator;" "const showMine = true;" \
  "「내가 올린 것만」 운영 관리자에 보임" \
  "$VT src/pages/translation-list" \
  "운영 관리자 → 「내가 올린 것만」 0"
code_break P15 "$TRR" "import { TR_TEXT }" "import { TR_TEXT } from '../../entities/translation/config/text.ts';" "import { TR_TEXT } from '../../entities/translation/config/text.ts'; import '../greenwash/GreenwashRoutes.tsx';" \
  "app/translation 이 app/greenwash/GreenwashRoutes.tsx 를 가져옴" \
  "$VT $L" \
  "칸 규칙"
code_break P16 "$SV" "const planned = input.parts.map" "optionsOf(input, part, range, batchId)" "optionsOf(input, part, range, makeKey())" \
  "e2e: 둘째 POST /runs 의 batchId 다름(빌드한 웹 — 흉내 서버가 launchKey 짝 검사·spec 이 batchId 하나를 단언)" \
  "WEB_TEST_PORT=${WEB_TEST_PORT:-21175} pnpm --filter @esg/web exec playwright test e2e/translation-server.spec.ts" \
  "translation-server.spec.ts"
code_break P17 "$NEW" "export function readRanges" "pageCount ?? Number.POSITIVE_INFINITY" "pageCount ?? 0" \
  "pageCount null 에 over_last 를 0쪽으로" \
  "$VT src/pages/translation-new/ui/NewTranslationScreen.test.tsx" \
  "pageCount null(txt)"

echo
echo "▶ 러너 몫 (R1 · R2 · R3)"
code_break R1 "$SV" "function kindOf" "if (failure.code === 'RUN_NOT_DONE') return 'not_done';" "if (failure.code === 'RUN_NOT_DONE') return 'not_found';" \
  "결과 409 RUN_NOT_DONE 을 not_found 로(끝나지 않음과 없음이 섞임)" \
  "$VT $API" \
  "409 RUN_NOT_DONE 은 not_done"

code_break R2 "$NTS" "} from '../../../entities/translation/api/index.ts';" "../../../entities/translation/api/index.ts" "../../../entities/translation/api/store.ts" \
  "화면이 영문번역 api 깊은 경로(api/store.ts)를 가져옴(플랫폼-웹 78 허락 조건 — 문만)" \
  "$VT $L" \
  "칸 규칙"
code_break R3 "$GWR" "onSelect={(id) => {" "if (id === 'translation') go({ to: '/translation' });" "" \
  "H5: 그린워싱 틀의 「영문번역」 메뉴 이동 줄 지움" \
  "$VT src/app/translation/router.test.tsx" \
  "그린워싱 틀의 「영문번역」이 켜져 있고 누르면 /translation"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "LATER=$later"
echo "PLANTED=$passed/$total"
