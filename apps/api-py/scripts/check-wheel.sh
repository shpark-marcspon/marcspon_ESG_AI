#!/usr/bin/env bash
# wheel(설치되는 패키지)에 테스트 폴더가 실리지 않는가.   사용: apps/api-py/scripts/check-wheel.sh
# 방법: 임시 폴더에 wheel 을 만들어 안의 파일 이름을 본다(pyproject.toml 의 exclude = ["esgapi/**/tests"]).
set -euo pipefail
cd "$(dirname "$0")/.."
out="$(mktemp -d)"
trap 'rm -rf "$out"' EXIT
uv build --wheel -o "$out" >/dev/null 2>&1
names="$(unzip -Z1 "$out"/*.whl)"
echo "wheel 안의 파일 $(printf '%s\n' "$names" | wc -l | tr -d ' ') 개, 그 가운데 tests 폴더 아래 $(printf '%s\n' "$names" | grep -c '/tests/' || true) 개"
# esgapi/__init__.py 는 있어야 한다(wheel 이 통째로 비어 통과하는 일을 막는다).
printf '%s\n' "$names" | grep -qx 'esgapi/__init__.py'
! printf '%s\n' "$names" | grep -q '/tests/'
