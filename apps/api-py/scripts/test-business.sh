#!/usr/bin/env bash
# 업무 층(@pytest.mark.django_db)을 compose 로 떠 있는 Postgres 에 붙여 돌린다.
#   사용: apps/api-py/scripts/test-business.sh [pytest 인자…]
#     -n 2         워커 둘로 나눠 돌린다(pytest-xdist). 워커마다 테스트 DB 가 따로 생긴다: test_<DB>_gw0, test_<DB>_gw1
#     --reuse-db   끝나도 테스트 DB 를 지우지 않고 다음에 다시 쓴다(마이그레이션을 건너뛴다).
#                  ★ 마이그레이션을 고친 뒤에는 --create-db 로 한 번 다시 만든다(남은 DB 는 옛 꼴이다).
# 주소는 저장소 맨 위의 .env 에서 읽는다(포트·비밀번호가 여기 박히지 않게). 컨테이너가 떠 있어야 한다.
#
# Django 는 주인 역할로 붙는다. pytest-django 가 그 연결로 test_${POSTGRES_DB}_py 를 만들고 마이그레이션하고,
# 테스트마다 트랜잭션으로 감싸 되돌린다. 떠 있는 서버의 자료(${POSTGRES_DB}_py)는 건드리지 않는다.
set -euo pipefail
cd "$(dirname "$0")/.."

# shellcheck source=db-env.sh
. scripts/db-env.sh
export TEST_DATABASE_URL_PY_OWNER="$OWNER_DATABASE_URL"

exec uv run --frozen pytest -q -m django_db "$@"
