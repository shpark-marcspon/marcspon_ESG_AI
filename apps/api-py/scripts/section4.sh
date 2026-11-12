#!/usr/bin/env bash
# 발주서(MARC-TICK-48) §4 의 자기검증을 한 번에 돌린다.   사용: apps/api-py/scripts/section4.sh
# 줄마다 "EXIT=<종료 코드>" 를 낸다. 전부 0 이어야 하고, 마지막 줄(허용 경로 밖의 변경)은 OUTSIDE_CHANGES=0 이어야 한다.
# 다루는 컨테이너·볼륨은 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# 심은 파손(계약 넷)과 예행은 따로다: apps/api-py/scripts/planted-breaks.sh, rehearsal.sh(컨테이너가 떠 있어야 한다)
set -u
cd "$(dirname "$0")/../../.."
BASE=42d9fbe

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}

echo "── 포트가 다른 워크트리와 겹치지 않는가 (.env)"
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; fi
done

# ── 컨테이너 없이 도는 것 ──
run 'cd apps/api-py && uv sync --frozen'
run 'cd apps/api-py && uv run ruff check . && uv run ruff format --check .'
run 'cd apps/api-py && uv run pyright'
run 'cd apps/api-py && uv run lint-imports'
run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security"'     # 순수 층
run 'apps/api-py/scripts/check-worktree-env.sh'      # worktree-env.sh 가 API_PY_PORT 를 채우는가(MARC-ISSUE-41 의 2번)
run 'apps/api-py/scripts/check-build-context.sh'     # 빌드 컨텍스트에 .dev-keys 가 없는가(MARC-ISSUE-41 의 1번)
run 'apps/api-py/scripts/check-wheel.sh'             # wheel 안에 tests 폴더가 없는가

# 통합 테스트가 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다).
EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
export EDK_JWT_PUBLIC_KEY

# ── 컨테이너가 있어야 도는 것 ──
run 'docker compose up -d --build --wait'
# 업무 층: 주인 역할, pytest-django 의 테스트 DB, 테스트마다 롤백. 직렬과 워커 둘의 통과 수가 같아야 한다.
run 'apps/api-py/scripts/test-business.sh'
# --reuse-db: 끝난 뒤에도 워커마다의 테스트 DB 를 남겨, 바로 아래 줄에서 이름을 볼 수 있게 한다.
run 'apps/api-py/scripts/test-business.sh -n 2 --reuse-db'
run 'apps/api-py/scripts/list-test-dbs.sh'
# 보안 층: 앱 역할(esg_app), 진짜 커밋, 직렬.  (= pytest --ds=esgapi.config.settings.test_security -m security)
run 'apps/api-py/scripts/test-security.sh'
# 통합 한 줄기: 떠 있는 api-py 에 호스트에서 교환 → /me → /sites.
run 'apps/api-py/scripts/test-integration.sh'
# 이미지에 설치된 esgapi 안에 tests 폴더가 없는가.
IMAGE="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env)/api-py:local"
export IMAGE
run 'test -z "$(docker run --rm "$IMAGE" find /app/.venv/lib -path "*/site-packages/esgapi" -prune -o -path "*/site-packages/esgapi/*" -name tests -type d -print)"'
run 'docker compose down -v'
run 'scripts/verify.sh'

# 허용 경로 밖의 변경: 추적되는 파일의 diff 와, 추적되지 않는 새 파일. 둘 다 없어야 한다(0).
ALLOWED=(':!apps/api-py' ':!scripts/worktree-env.sh' ':!.dockerignore' ':!docker/api-py.Dockerfile' ':!compose.yaml' ':!scripts/verify.sh' ':!README.md')
echo
echo "▶ git diff --stat $BASE -- . ${ALLOWED[*]} | tail -1"
git diff --stat "$BASE" -- . "${ALLOWED[@]}" | tail -1
echo "OUTSIDE_CHANGES=$( { git diff --name-only "$BASE" -- . "${ALLOWED[@]}"; git ls-files --others --exclude-standard -- . "${ALLOWED[@]}"; } | wc -l | tr -d ' ')"
echo
echo "▶ git status --porcelain | grep -v -E '^.. (허용 경로)' | wc -l"
echo "OUTSIDE_STATUS=$(git status --porcelain | grep -v -E '^.. (apps/api-py/|scripts/worktree-env.sh|\.dockerignore|docker/api-py.Dockerfile|compose.yaml|scripts/verify.sh|README.md)' | wc -l | tr -d ' ')"
