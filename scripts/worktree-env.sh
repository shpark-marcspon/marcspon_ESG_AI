#!/usr/bin/env bash
# git 워크트리 하나를 위한 .env 를 만든다.   사용(워크트리 안에서): scripts/worktree-env.sh <이름>
#
# 같은 저장소를 여러 벌(main 과 워크트리들) 동시에 띄워도 겹치지 않게, .env.example 에서 두 가지만 바꾼다:
#   COMPOSE_PROJECT_NAME = esg-app-<이름>   → 컨테이너·볼륨·네트워크·이미지 이름이 갈린다
#   API_PORT, POSTGRES_PORT, STORAGE_PORT, API_PY_PORT, WEB_PORT   → 이름에서 정해지는 값(같은 이름이면 늘 같은 포트)
# 이미 .env 가 있으면 건드리지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."

name="${1:-}"
case "$name" in
  "" | *[!A-Za-z0-9_-]*) echo "사용: scripts/worktree-env.sh <이름(영문·숫자·-·_)>" >&2; exit 2 ;;
esac
if [ -f .env ]; then
  echo ".env 가 이미 있어 그대로 둔다: $(pwd)/.env"
  exit 0
fi

# compose 프로젝트 이름은 소문자만 받는다.
project="esg-app-$(printf '%s' "$name" | tr '[:upper:]' '[:lower:]')"

# 포트가 쓰이고 있는가: 지금 듣고 있는 프로세스가 있거나, 다른 워크트리의 .env 가 이미 잡아 두었거나.
taken_by_others="$(git worktree list --porcelain | sed -n 's/^worktree //p' \
  | while read -r dir; do [ -f "$dir/.env" ] && grep -E '^(API|POSTGRES|STORAGE|API_PY|WEB)_PORT=' "$dir/.env" || true; done \
  | cut -d= -f2)"
in_use() {
  lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1 && return 0
  printf '%s\n' "$taken_by_others" | grep -qx "$1"
}

# 이름 → 0~399 의 칸 번호(cksum 은 같은 글자에 늘 같은 수를 준다). 칸 하나가 포트 열 개다: 20000, 20010, ...
# main 이 쓰는 18080·18081·15432·19000 과는 범위가 달라 겹치지 않는다. 칸이 쓰이고 있으면 다음 칸으로 간다.
slot=$(( $(printf '%s' "$name" | cksum | cut -d' ' -f1) % 400 ))
for _ in $(seq 400); do
  base=$(( 20000 + slot * 10 ))
  if ! in_use "$base" && ! in_use $(( base + 1 )) && ! in_use $(( base + 2 )) && ! in_use $(( base + 3 )) && ! in_use $(( base + 4 )); then break; fi
  slot=$(( (slot + 1) % 400 ))
  base=""
done
[ -n "$base" ] || { echo "빈 포트 칸을 찾지 못했다" >&2; exit 1; }

sed -e "s/^COMPOSE_PROJECT_NAME=.*/COMPOSE_PROJECT_NAME=$project/" \
    -e "s/^API_PORT=.*/API_PORT=$base/" \
    -e "s/^POSTGRES_PORT=.*/POSTGRES_PORT=$(( base + 1 ))/" \
    -e "s/^STORAGE_PORT=.*/STORAGE_PORT=$(( base + 2 ))/" \
    -e "s/^API_PY_PORT=.*/API_PY_PORT=$(( base + 3 ))/" \
    -e "s/^WEB_PORT=.*/WEB_PORT=$(( base + 4 ))/" \
    .env.example > .env

echo "만들었다: $(pwd)/.env"
echo "  COMPOSE_PROJECT_NAME=$project  API_PORT=$base  POSTGRES_PORT=$(( base + 1 ))  STORAGE_PORT=$(( base + 2 ))  API_PY_PORT=$(( base + 3 ))  WEB_PORT=$(( base + 4 ))"
