#!/usr/bin/env bash
# 밴드 DV4 의 심은 파손(발주서 §3).   사용: apps/web/scripts/planted-breaks-DV4.sh
# 파손을 하나씩 심고, 지키는 시험이 빨개지는지 잰 뒤 원본 바이트로 되돌린다. P1~P4(발주서 표) · R1(러너 몫) · X1(검증자 B1 — 숨긴 상태 글).
# 끝 두 줄: PLANTED=<빨개진>/<심은> · FINGERPRINT=same|changed(건드린 파일의 sha256 이 처음과 같은가).
# 꼴은 planted-breaks-DV2d.sh 를 따른다: <머리 무늬>가 처음 나오는 줄부터 아래로, <옛 글자>가 든 첫 줄에서 그 글자를 <새 글자>로(글자 그대로).
# 이름 무늬는 실패 줄(×·✘·FAIL·FAILED)에 댄다.
set -u
cd "$(dirname "$0")/../../.."
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"

W=apps/web
S=$W/src
LIST=$S/pages/dataverify-list/ui/ListScreen.tsx
TEXT=$S/entities/dataverify/config/text.ts
XLSX=apps/api-py/esgapi/dataverify/outputs/xlsx.py
TOUCHED=("$LIST" "$TEXT" "$XLSX")

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

# <번> <파일> <바뀔 줄 수> <말> <명령> <빨개질 시험 이름 무늬들(줄바꿈으로 나눔)> -- (<머리> <옛> <새>)…
code_break() {
  local n="$1" file="$2" want="$3" say="$4" cmd="$5" patterns="$6"
  shift 6
  restore
  while [ $# -ge 3 ]; do
    if ! plant "$file" "$1" "$2" "$3"; then report "$n" fail "심지 못했다: $say"; restore; return; fi
    shift 3
  done
  if [ "$(changed_lines "$file")" != "$want" ]; then report "$n" fail "바뀐 줄이 $want 이 아니다: $say"; restore; return; fi
  bash -c "$cmd" > "$OUT" 2>&1
  local code=$? missing=0 pattern red_lines
  red_lines="$(grep -E '^ *(×|✘|FAIL|FAILED) ' "$OUT")"
  while IFS= read -r pattern; do
    [ -z "$pattern" ] && continue
    grep -qF -- "$pattern" <<< "$red_lines" || { missing=$((missing + 1)); echo "       실패 줄에 없다: $pattern"; }
  done <<< "$patterns"
  local red
  red="$(sed -E 's/^ +//' <<< "$red_lines" | cut -c1-70 | head -6 | tr '\n' '|')"
  restore
  if [ "$code" -ne 0 ] && [ "$missing" -eq 0 ]; then report "$n" ok "$say — EXIT=$code · $red"; else report "$n" fail "$say — EXIT=$code, 없는 무늬 $missing"; fi
}

VT="pnpm --filter @esg/web exec vitest run"
PY="cd apps/api-py && uv run pytest esgapi/dataverify/tests/outputs/test_xlsx.py -q -m 'not django_db'"

echo "▶ 발주서 표 (P1~P4)"
code_break P1 "$LIST" 1 "첫 읽기를 옛 갈래(aria-busy 빈 틀 — 목록 틀 0)로 되돌림" "$VT src/pages/dataverify-list" \
  "첫 그림부터 제목·설명 막대·표 머리 + 스켈레톤 줄 5
0건이면 받은 뒤에야 DV-00" \
  "if (nothingYet && intro" "if (nothingYet && intro !== undefined) return <>{intro}</>;" \
  "if (firstLoad) return <div data-screen=\"dataverify-list\" aria-busy />; if (nothingYet && intro !== undefined) return <>{intro}</>;"
code_break P2 "$LIST" 1 "첫 읽기에서 0건 판정(DV-00) 먼저" "$VT src/pages/dataverify-list" \
  "첫 그림부터 제목·설명 막대·표 머리 + 스켈레톤 줄 5
0건이면 받은 뒤에야 DV-00
첫 읽기 실패" \
  "const nothingYet =" "status.state === 'ready' && !serverFiltered" "firstLoad || (status.state === 'ready' && !serverFiltered" \
  "const nothingYet =" "status.page.count === 0;" "status.page.count === 0);"
code_break P3 "$TEXT" 1 "checksLead 를 옛 글(허용 오차 \${tolerance})로" "$VT src/entities/dataverify/config" \
  "값을 끼운다" \
  "checksLead: (tolerance" "허용 오차는 검사마다 AI 가 정해요(빠지면 \${tolerance})" "허용 오차 \${tolerance}"
code_break P4 "$XLSX" 1 "엑셀 설정 시트 행 이름을 \"tolerance\" 로" "$PY" \
  "test_the_summary_and_settings_come_from_the_result" \
  "def settings_rows(" "\"계산 허용 오차(빠질 때)\"" "\"tolerance\""

echo
echo "▶ 러너 몫 (R1)"
code_break R1 "$LIST" 1 "첫 읽기에 설명 막대 자리 0(다시 읽기만 descriptionPending)" "$VT src/pages/dataverify-list" \
  "첫 그림부터 제목·설명 막대·표 머리 + 스켈레톤 줄 5" \
  "<PageTitle" "descriptionPending={loading}" "descriptionPending={loading && !firstLoad}"

echo
echo "▶ 검증자 몫 (X1)"
code_break X1 "$LIST" 1 "숨긴 상태 글을 늘 비움(첫 읽기 「불러오는 중」 낭독 0 — 검증자 B1)" "$VT src/pages/dataverify-list" \
  "첫 그림부터 제목·설명 막대·표 머리 + 스켈레톤 줄 5" \
  "role=\"status\"" "{announceLoading ? words.loading : null}" "{null}"

echo
sums_after="$(restore; for file in "${TOUCHED[@]}"; do sha "$file"; done)"
[ "$sums_before" = "$sums_after" ] && echo "FINGERPRINT=same" || echo "FINGERPRINT=changed"
echo "PLANTED=$passed/$total"
