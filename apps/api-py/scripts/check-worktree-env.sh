#!/usr/bin/env bash
# scripts/worktree-env.sh 가 빈 폴더에서 API_PY_PORT 까지 채운 .env 를 만드는가.   사용: apps/api-py/scripts/check-worktree-env.sh
# 방법: 임시 폴더에 빈 git 저장소를 만들고 worktree-env.sh 와 .env.example 만 베껴 돌린다. 이 저장소의 .env 는 건드리지 않는다.
set -euo pipefail
cd "$(dirname "$0")/../../.."

dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
mkdir "$dir/scripts"
cp scripts/worktree-env.sh "$dir/scripts/"
cp .env.example "$dir/"
git -C "$dir" init -q

"$dir/scripts/worktree-env.sh" check-py2 >/dev/null
ports="$(grep -E '^(API|POSTGRES|STORAGE|API_PY)_PORT=' "$dir/.env")"
echo "$ports" | tr '\n' ' '; echo
base="$(echo "$ports" | sed -n 's/^API_PORT=//p')"
# 포트 넷이 base, base+1, base+2, base+3 이고 20000 대(워크트리의 범위)인가.
[ "$base" -ge 20000 ]
[ "$(echo "$ports" | sed -n 's/^POSTGRES_PORT=//p')" -eq $((base + 1)) ]
[ "$(echo "$ports" | sed -n 's/^STORAGE_PORT=//p')" -eq $((base + 2)) ]
[ "$(echo "$ports" | sed -n 's/^API_PY_PORT=//p')" -eq $((base + 3)) ]
[ "$(echo "$ports" | wc -l | tr -d ' ')" -eq 4 ]
# 웹 개발 서버의 포트는 base+4 다(저장소의 CORS 허락 출처가 이 값을 쓴다. 위 넷의 무늬에는 들지 않는다).
[ "$(sed -n 's/^WEB_PORT=//p' "$dir/.env")" -eq $((base + 4)) ]
