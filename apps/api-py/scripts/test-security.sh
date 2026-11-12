#!/usr/bin/env bash
# 보안 층(tests/security)을 compose 로 떠 있는 Postgres 에 붙여 돌린다.   사용: apps/api-py/scripts/test-security.sh [pytest 인자…]
# 주소는 저장소 맨 위의 .env 에서 읽는다. 컨테이너가 떠 있어야 한다. 직렬로만 돈다(-n 을 주면 첫 고정물이 멈춘다).
#
# 테스트는 ${POSTGRES_DB}_py_test 라는 별도 DB 를 만들어 쓰고 끝나면 지운다. 떠 있는 서버의 자료는 건드리지 않는다.
#   TEST_DATABASE_URL_PY        앱 역할(esg_app): 테스트하려는 코드가 붙는다. RLS 가 걸린다.
#   TEST_DATABASE_URL_PY_OWNER  주인 역할: 테스트 DB 를 만들고 마이그레이션하고 자료를 심는다.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=db-env.sh
. scripts/db-env.sh
export TEST_DATABASE_URL_PY="$APP_DATABASE_URL"
export TEST_DATABASE_URL_PY_OWNER="$OWNER_DATABASE_URL"

# --ds: Django 설정을 보안 층 것으로 바꾼다(앱 역할로 붙는다). pytest 설정은 순수·업무 층과 같은 pyproject.toml 이다.
# -m security: 보안 층의 테스트만. 두 층은 Django 가 붙는 역할이 달라 한 프로세스에 섞이지 않는다.
exec uv run --frozen pytest -q --ds=esgapi.config.settings.test_security -m security "$@"
