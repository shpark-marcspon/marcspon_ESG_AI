#!/usr/bin/env bash
# 통합 테스트: compose 로 떠 있는 api-py 에 호스트에서 요청을 보낸다.   사용: apps/api-py/scripts/test-integration.sh
# 컨테이너가 떠 있어야 하고, 그 컨테이너의 EDK_JWT_PUBLIC_KEY 가 .dev-keys 의 공개키여야 한다
# (scripts/verify.sh 와 section4.sh 는  export EDK_JWT_PUBLIC_KEY="$(… dev_edk.py public-key)"  뒤에 띄운다).
set -euo pipefail
cd "$(dirname "$0")/.."
# -c: 통합 테스트만의 설정을 쓴다(Django 를 띄우지 않는다. 떠 있는 서버를 밖에서 부른다).
exec uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration "$@"
