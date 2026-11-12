#!/usr/bin/env bash
# 데모를 열지 않는 프로덕션 빌드(VITE_DEMOS 없이)에 데모 넷이 들지 않았는가(밴드 WC1 ② P4).   사용: apps/web/scripts/check-no-demos.sh
# VITE_DEMOS 를 지우고 빌드한 뒤 dist/assets 에서 데모에만 있는 글자 하나씩(넷)을 찾는다. 하나라도 나오면 EXIT=1.
# 먼저 표식 글자가 그 데모 원본 파일에 있는지 본다: 없으면(표식이 낡음) EXIT=2 — 낡은 표식은 늘 0건이라 통과로 새기 때문이다.
# dist/assets 가 없거나 grep 이 오류를 내면 EXIT=2(0건 통과로 삼키지 않는다).
# 갈래:
#   (인자 없음)    VITE_DEMOS 없이 빌드하고 찾는다. verify.sh 가 부르는 꼴.
#   --self-check   VITE_DEMOS=1 로 빌드하고 넷 다 나와야 EXIT=0(표식이 실제로 잡는지). 빌드 한 번이 더 들어 verify 에는 넣지 않았다.
#   --no-build     빌드하지 않고 지금 dist/assets 만 찾는다(기본 모드의 판정).
# 끝나면 dist 에는 마지막 빌드가 남는다(verify.sh 의 브라우저 단계는 자기 빌드를 다시 한다).
set -euo pipefail
cd "$(dirname "$0")/.."

# 「표식 글자|그 글자가 있는 데모 파일」. 데모 파일의 그 글자를 바꾸면 여기도 같이 바꾼다.
MARKERS=(
  '예시: 두 문서 대조|src/pages/demo-viewer/App.tsx'
  '가짜 5,000행|src/pages/demo-table/TablePage.tsx'
  'no-session|src/pages/demo-api/ApiPage.tsx'
  '폴더 더하기 작게|src/pages/demo-parts/PartsPage.tsx'
)

mode=check
case "${1:-}" in
  '') ;;
  --self-check) mode=self ;;
  --no-build) mode=nobuild ;;
  *) echo "모르는 인자: $1"; exit 2 ;;
esac

for entry in "${MARKERS[@]}"; do
  marker="${entry%%|*}" file="${entry#*|}"
  if ! grep -qF -- "$marker" "$file"; then
    echo "표식 「${marker}」 이 ${file} 에 없다(표식을 고친다)"
    exit 2
  fi
done

case "$mode" in
  self) VITE_DEMOS=1 pnpm build > /dev/null || exit 2 ;;
  check) env -u VITE_DEMOS pnpm build > /dev/null || exit 2 ;;
  nobuild) ;;
esac

if [ ! -d dist/assets ]; then
  echo "dist/assets 가 없다(빌드가 없다)"
  exit 2
fi

bad=0
for entry in "${MARKERS[@]}"; do
  marker="${entry%%|*}" file="${entry#*|}"
  code=0
  found=$(grep -rlF -- "$marker" dist/assets) || code=$?
  case "$code" in
    0) hits=$(printf '%s\n' "$found" | wc -l | tr -d ' ') ;;
    1) hits=0 ;;
    *) echo "grep 오류(코드 ${code}): 「${marker}」"; exit 2 ;;
  esac
  echo "「${marker}」(${file}): dist/assets 파일 ${hits}개"
  if [ "$mode" = self ]; then
    [ "$hits" -gt 0 ] || bad=1
  else
    [ "$hits" -eq 0 ] || bad=1
  fi
done

if [ "$mode" = self ]; then
  if [ "$bad" -eq 0 ]; then echo "자기 확인: VITE_DEMOS=1 빌드에 표식 넷이 다 있다"; else echo "자기 확인 실패: 표식이 데모 빌드에도 없다"; fi
else
  if [ "$bad" -eq 0 ]; then echo "데모 표식 0건: 프로덕션 빌드에 데모가 없다"; else echo "데모가 프로덕션 빌드에 들었다"; fi
fi
exit "$bad"
