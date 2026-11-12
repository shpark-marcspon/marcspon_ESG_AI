#!/usr/bin/env bash
# 시각 비교의 기준 그림을 다시 찍는다(밴드 VS1 — 결정 sid:MARC-ENT-326).   사용: apps/web/scripts/visual-update.sh [--all]
# 기준 그림은 git 밖 한 자리(main 체크아웃의 형제 esg-app.visual-baseline/ — e2e/visual-baseline.ts). 갱신은 병합 뒤 main 에서 감독만 한다.
# 거절(한 줄 + EXIT=2): main 워크트리가 아님 · 가지가 main 이 아님 · .git/verify.lock 있음 · apps/web 에 커밋 안 한 바뀜(기준은 병합된 커밋의 그림이어야).
# 통과면 바뀐 장만(--all 이면 전부) 다시 찍고 <기준 폴더>/BASELINE.txt 에 커밋 해시·날짜·장 수를 덮어쓴다. 포트는 WEB_TEST_PORT 를 물려받는다.
set -u
cd "$(dirname "$0")/.."

mode=changed
case "${1:-}" in
  '') ;;
  --all) mode=all ;;
  *) echo "모르는 인자: $1 (쓸 수 있는 것: --all)"; exit 2 ;;
esac

top=$(git rev-parse --show-toplevel)
main=$(dirname "$(git rev-parse --path-format=absolute --git-common-dir)")
if [ "$top" != "$main" ]; then
  echo "거절: main 워크트리가 아니다($top) — 기준 갱신은 $main 에서만"; exit 2
fi
branch=$(git branch --show-current)
if [ "$branch" != main ]; then
  echo "거절: 가지가 main 이 아니다($branch)"; exit 2
fi
if [ -e "$main/.git/verify.lock" ]; then
  echo "거절: $main/.git/verify.lock 이 있다 — 전량 verify 가 끝난 뒤에"; exit 2
fi
if [ -n "$(git status --porcelain -- .)" ]; then
  echo "거절: apps/web 에 커밋 안 한 바뀜이 있다 — 기준은 병합된 커밋의 그림이어야 한다"; exit 2
fi

dir="$(dirname "$main")/$(basename "$main").visual-baseline"
mkdir -p "$dir"
env -u VISUAL_BASELINE_DIR VISUAL_UPDATE_MAIN=1 pnpm exec playwright test e2e/visual.spec.ts --update-snapshots="$mode"
code=$?
if [ "$code" -ne 0 ]; then
  echo "갱신 실패 EXIT=$code — BASELINE.txt 는 그대로"; exit "$code"
fi
count=$(find "$dir" -name '*.png' | wc -l | tr -d ' ')
printf 'commit %s\ndate %s\nshots %s\nmode %s\n' "$(git rev-parse HEAD)" "$(date '+%Y-%m-%d %H:%M:%S %z')" "$count" "$mode" > "$dir/BASELINE.txt"
echo "기준 갱신 끝: $dir ($count 장, $mode)"
