#!/usr/bin/env bash
# 연습용 개인키(apps/api-py/.dev-keys)가 docker 의 빌드 컨텍스트로 넘어가지 않는가.   사용: apps/api-py/scripts/check-build-context.sh
# 방법: apps/api-py 를 통째로 COPY 하는 한 줄짜리 이미지를 빌드해, 그 안에 .dev-keys 가 없음을 본다
#       (.dockerignore 가 막은 것은 COPY 로도 들어가지 못한다). 키 쌍이 아직 없으면 먼저 만든다. 만든 이미지는 지운다.
set -euo pipefail
cd "$(dirname "$0")/../../.."

(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key >/dev/null)
[ -f apps/api-py/.dev-keys/edk-private.pem ] || { echo "키 쌍이 없다: 이 검사는 아무것도 재지 못한다" >&2; exit 2; }

dockerfile="$(mktemp)"
trap 'rm -f "$dockerfile"' EXIT
cat > "$dockerfile" <<'DOCKERFILE'
FROM python:3.13.9-slim-bookworm@sha256:b685a4fa58bb19d1814d78a1ec0f0208f351452724f78b20212c984d6e124a34
COPY apps/api-py /ctx
# pyproject.toml 은 있어야 한다(컨텍스트가 통째로 비어 통과하는 일을 막는다). .dev-keys 는 없어야 한다.
RUN test -e /ctx/pyproject.toml && test ! -e /ctx/.dev-keys
DOCKERFILE

if image="$(docker build --no-cache -q -f "$dockerfile" . 2>/dev/null)"; then
  docker rmi "$image" >/dev/null
  echo "빌드 컨텍스트에 apps/api-py/.dev-keys 가 없다"
else
  echo "빌드 컨텍스트에 apps/api-py/.dev-keys 가 들어갔다(.dockerignore 를 본다)" >&2
  exit 1
fi
