#!/usr/bin/env bash
# 밴드 AD2S 의 심은 파손.   사용: apps/web/scripts/planted-breaks-AD2S.sh --commit <1|2>
# --commit 1 = P1~P10(저장 흐름 경쟁 ①② · P10 은 감독 처분 R1) · --commit 2 = P1~P10 을 옮긴 자리에서 다시 + P11~P15(동작 0 정리 · P15 는 감독 처분 R2).
# 하나씩 심고(한 줄), 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다.
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-AD2W.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(vitest ×, playwright ✘)에서만 찾는다 — 통과한 시험 이름에 걸려 초록을 빨강으로 세지 않게.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

COMMIT=""
[ "${1:-}" = "--commit" ] && COMMIT="${2:-}"
case "$COMMIT" in 1 | 2) ;; *) echo "사용: $0 --commit <1|2>"; exit 2 ;; esac

W=apps/web
S=$W/src
PAGE=$S/pages/admin-ai-settings
SCREEN=$PAGE/ui/AiSettingsScreen.tsx
TOUCHED=("$SCREEN")
for extra in "$PAGE/hooks/useSave.ts" "$PAGE/model/lines.ts" "$PAGE/model/refusal.ts"; do [ -f "$extra" ] && TOUCHED+=("$extra"); done

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

# <번> <파일> <머리 무늬> <옛> <새> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔, 글자 그대로 — 실패 줄에서)>
code_break() {
  local n="$1" file="$2"
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
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-60 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$6 — EXIT=$code · $red"; else report "$n" fail "$6 — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run src/pages/admin-ai-settings"
E2E="WEB_TEST_PORT=${WEB_TEST_PORT:-5390} pnpm --filter @esg/web exec playwright test e2e/admin.spec.ts -g 'AD2S'"
BOTH="$VT; a=\$?; $E2E; b=\$?; [ \$a -eq 0 ] && [ \$b -eq 0 ]"

U1='U1 저장 중 막힌 이동'
U2='U2 저장 중 막힌 이동'
U3='U3 저장 201 뒤'
U4='U4 정보 띠'
U5='U5 저장 201 뒤'
E1='AD-02 저장 중 뒤로가기'

# 끔·보냄의 자리: ① 은 화면, ② 는 화면(그림·단추) + useSave(onPick 은 화면에 남는다 — retrySaved 는 훅으로 옮긴다).
if [ "$COMMIT" = 1 ]; then RETRY_FILE=$SCREEN; else RETRY_FILE=$PAGE/hooks/useSave.ts; fi

echo "▶ ①② 저장 흐름 경쟁 (P1~P10 — 커밋 $COMMIT 자리)"
code_break P1 "$SCREEN" '{(leaveTo !== null ||' '(leavePending && !saving && dirty)' '(leavePending && dirty)' \
  '나가기 창 그림 조건에서 !saving 지움(저장 중에 창)' \
  "$BOTH" \
  "$U1
$E1"
code_break P2 "$SCREEN" 'const leavePending =' 'if (leavePending && !saving && !dirty)' 'if (leavePending && !dirty)' \
  '처리기 우회: 보냄 효과가 saving 을 안 봄(201 뒤 목록 받는 중에 proceed)' \
  "$VT" \
  "$U1"
code_break P3 "$SCREEN" 'const leavePending =' 'proceedLeave.current?.();' 'void 0;' \
  '보냄 효과 지움(저장됐는데 머묾 · [나가기] 도 안 감)' \
  "$BOTH" \
  "$U1
$E1"
code_break P4 "$SCREEN" 'const leavePending =' 'if (leavePending && !saving && !dirty)' 'if (leavePending && !saving)' \
  '보냄 효과가 dirty 를 안 봄(실패 뒤에도 조용히 보냄)' \
  "$BOTH" \
  "$U2
$E1"
code_break P5 "$SCREEN" 'const onPick = ' 'if (saving) return;' '' \
  '처리기 우회: onPick 의 saving 막음 지움' \
  "$VT" \
  "$U3
$U4"
code_break P6 "$SCREEN" 'footer={' 'off={state.loadingMore || saving}' 'off={state.loadingMore}' \
  '[더 보기] off 에서 saving 지움' \
  "$VT" \
  "$U3
$U4"
code_break P7 "$SCREEN" 'const canApply =' '!saving;' 'true;' \
  'canApply 에서 !saving 지움' \
  "$VT" \
  "$U3"
code_break P8 "$SCREEN" 'newVersion={{' 'off: dirty || model === null || saving,' 'off: dirty || model === null,' \
  'newVersion.off 에서 saving 지움' \
  "$VT" \
  "$U3"
code_break P9 "$RETRY_FILE" 'const retrySaved' 'setSaving(true);' '' \
  'retrySaved 가 saving 을 안 세움' \
  "$VT" \
  "$U4"
code_break P10 "$SCREEN" '<SaveBar' 'saveOff={!draft.valid || saving}' 'saveOff={!draft.valid}' \
  '저장 막대 saveOff 에서 saving 지움(감독 처분 R1)' \
  "$VT" \
  "$U5"

if [ "$COMMIT" = 2 ]; then
  LINES=$PAGE/model/lines.ts
  echo "▶ ② 동작 0 정리 (P11~P15)"
  code_break P11 "$LINES" 'export function componentLines' ".filter((one) => one.body.kind !== 'lines')" '.filter(() => true)' \
    'componentLines 가 lines 줄을 고정 묶음 앞에도 넣음' \
    "$VT" \
    '차례: 모델 · 프롬프트
구성 열은 r3 차례'
  code_break P12 "$LINES" 'export function modelSum' 'new Set(names).size <= 1' 'names.length > 0' \
    'modelSum 이 늘 modelOne' \
    "$VT" \
    '단계 하나 → 하나
모델 꼬리:'
  code_break P13 "$PAGE/model/refusal.ts" 'export function refusalOf' "startsWith('AI_MODEL_')" "startsWith('NO_SUCH_')" \
    'refusalOf 가 AI_MODEL_ 을 일반 실패로' \
    "$VT" \
    'AI_MODEL_* →
모델 거절(AI_MODEL_ROUTE_UNAVAILABLE)'
  code_break P14 "$PAGE/hooks/useSave.ts" 'const submitSave' 'onSaved(outcome.key, outcome.number);' 'void outcome;' \
    'useSave 가 성공 뒤 onSaved 를 안 부름(새 판 고름 빠짐)' \
    "$VT" \
    '[새 버전으로 저장] → 저장 창
'"$U3"
  code_break P15 "$PAGE/hooks/useSave.ts" 'const submitSave' 'onCreated();' 'void 0;' \
    'useSave 가 onCreated 를 안 부름(앞 알림이 남음 — 감독 처분 R2)' \
    "$VT" \
    'U6 새 판이 만들어지면'
fi

echo
sums_after="$(for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
