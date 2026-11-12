#!/usr/bin/env bash
# 빌드 잠금(<git 공통 폴더>/build.lock — 기계 전체에서 build 는 하나)을 잡고 명령 하나를 돌린 뒤 놓는다.
#   사용: scripts/with-build-lock.sh <명령…>      예: scripts/with-build-lock.sh docker compose build
# 잠금은 scripts/verify.sh 의 전량과 같은 것이다(scripts/lib/lock.sh). 끝나는 꼴:
#   명령의 종료 코드 그대로 · 75 기다림 상한(BUILD_LOCK_WAIT_S, 기본 1800초. 간격 BUILD_LOCK_POLL_S, 기본 5초)
#   · 2 인자 없음, 또는 잠금 자리를 계산하지 못함(이 스크립트가 git 저장소 밖에 있다 — 사본의 것을 부르지 않는다)
#     이나 만들 수 없음(부모 폴더가 없다)
#   · 130·143 Ctrl-C·SIGTERM — 명령이 끝난 뒤에(명령은 앞에서 돈다. 잠금은 명령이 도는 동안 늘 쥐어져 있다)
# 조상이 이미 잡았으면(BUILD_LOCK_HELD_BY 가 잠금의 pid 이고 살아 있다) 기다리지 않고 돌리며, 놓는 것도 그 조상이 한다.
# 이 잠금이 못 막는 것은 scripts/verify.sh 의 머리 주석(빌드 잠금 절)에 있다.
set -u
here="$(cd "$(dirname "$0")" && pwd)"

usage() { echo "사용: scripts/with-build-lock.sh <명령…>" >&2; }
[ "$#" -ge 1 ] || { usage; exit 2; }

. "$here/lib/lock.sh"

if [ -n "${BUILD_LOCK_DIR:-}" ]; then
  dir="$BUILD_LOCK_DIR"
else
  common="$(git -C "$here/.." rev-parse --path-format=absolute --git-common-dir 2>/dev/null)"
  if [ -z "$common" ]; then
    echo "빌드 잠금 자리를 계산하지 못했다(git 저장소 밖): $here/.." >&2
    usage
    exit 2
  fi
  dir="$common/build.lock"
fi

trap 'lock_release "$dir"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM

lock_acquire "$dir" "${BUILD_LOCK_WAIT_S:-1800}" "${BUILD_LOCK_POLL_S:-5}" "빌드 잠금이 잡혀 있다" "$*" "${BUILD_LOCK_HELD_BY:-}"
code=$?
[ "$code" -eq 0 ] || exit "$code"   # 75 상한 · 2 잠금 자리를 만들 수 없음
if [ "$LOCK_ACQUIRED" = held ]; then
  echo "빌드 잠금은 이미 조상(pid $BUILD_LOCK_HELD_BY)이 쥐었다: $dir (기다림 0)"
else
  export BUILD_LOCK_HELD_BY=$$
  echo "빌드 잠금을 잡았다: $dir (${LOCK_WAITED}초 기다림)"
fi

# exec 하지 않는다: 명령이 끝나야 EXIT 의 trap 이 잠금을 놓는다.
"$@"
exit $?
