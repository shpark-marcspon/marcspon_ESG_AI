#!/usr/bin/env bash
# 업무 층이 만든 테스트 DB 의 이름을 낸다(pytest-django 가 만든 test_… 들).   사용: apps/api-py/scripts/list-test-dbs.sh
# `test-business.sh -n 2 --reuse-db` 뒤에 부르면 워커마다 하나씩 보인다: test_<DB>_gw0, test_<DB>_gw1
# 하나도 없으면 실패한다(잴 것이 없었다는 뜻이다).
set -euo pipefail
cd "$(dirname "$0")/../../.."
owner="$(sed -n 's/^POSTGRES_OWNER_USER=//p' .env)"
names="$(docker compose exec -T postgres psql -U "$owner" -d postgres -Atc \
  "SELECT datname FROM pg_database WHERE datname LIKE 'test\_%' ORDER BY datname")"
echo "$(printf '%s' "$names" | grep -c . || true) 개: $(printf '%s' "$names" | tr '\n' ' ')"
[ -n "$names" ]
