#!/usr/bin/env bash
# 발주서(MARC-TICK-50, band-handoffs/PY4-order.md) §4 의 자기검증을 한 번에 돌린다.   사용: apps/api-py/scripts/section4-PY4.sh
# 줄마다 "EXIT=<종료 코드>" 를 낸다. 전부 0 이어야 한다.
# 다루는 컨테이너·볼륨은 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# 심은 파손은 따로다: apps/api-py/esgapi/inventory/tests/planted-breaks-PY4.sh
# verify.sh 가 node 22 를 쓴다:  PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH" apps/api-py/scripts/section4-PY4.sh
set -u
cd "$(dirname "$0")/../../.."

# ── --curl: 떠 있는 컨테이너에 요청을 보내는 조각(아래의 run 줄 하나가 이것을 부른다) ──
if [ "${1:-}" = "--curl" ]; then
  set -euo pipefail
  base="http://127.0.0.1:$(sed -n 's/^API_PY_PORT=//p' .env)"
  # shellcheck source=db-env.sh
  cd apps/api-py && . scripts/db-env.sh
  tenant="s4-py4-$$"
  jar="$(mktemp)"
  psql() { docker compose exec -T postgres psql -v ON_ERROR_STOP=1 -q -U "$(env_value POSTGRES_OWNER_USER)" -d "$(env_value POSTGRES_DB)_py" "$@"; }
  cleanup() { psql -c "DELETE FROM users WHERE tenant_id = '$tenant'; DELETE FROM tenants WHERE id = '$tenant';" >/dev/null; rm -f "$jar"; }
  trap cleanup EXIT
  # 테넌트 등록은 관리자가 하는 일이다(앱에는 이 길이 없다). 주인 역할로 심고 끝나면 지운다.
  psql -c "INSERT INTO tenants (id, name, created_at) VALUES ('$tenant', 'section4 PY4', now());"
  token="$(uv run --frozen python scripts/dev_edk.py token --tenant "$tenant" --sub s4-viewer --role viewer --name 검증)"
  curl -sS -f -c "$jar" -H 'content-type: application/json' "$base/auth/exchange" -d "{\"token\": \"$token\"}" >/dev/null
  body='{"gwpSetId": "kr-ets-decree-annex2", "rows": [{"id": "H01", "orgUnit": "synthetic-site", "period": "2025",
    "sourceType": "stationary_combustion", "fuel": "diesel", "sector": "manufacturing_construction",
    "parameterTiers": {"calorific": 2, "co2": 2, "nonCo2": 1, "oxidation": 2}, "amount": "1000", "unit": "L"}]}'
  answer="$(curl -sS -f -b "$jar" -H 'content-type: application/json' "$base/inventory/calc" -d "$body")"
  total="$(printf '%s' "$answer" | python3 -c 'import json,sys; print(json.load(sys.stdin)["aggregation"]["total"]["co2e"])')"
  echo "POST $base/inventory/calc (viewer 세션, tables 없음) → aggregation.total.co2e = $total   (손계산 H01: 2.5596384)"
  [ "$total" = "2.5596384" ]
  # 세션 없이는 401
  code="$(curl -sS -o /dev/null -w '%{http_code}' -H 'content-type: application/json' "$base/inventory/calc" -d "$body")"
  echo "세션 없이 → $code"
  [ "$code" = "401" ]
  # 본문이 Django 의 기본 상한(2.5MB)을 넘으면: 잰 값을 적는다(계산 결과 200 이 아니어야 한다).
  big="$(mktemp)"
  python3 -c 'import sys; sys.stdout.write("{\"rows\": [], \"gwpSetId\": \"" + "x" * (3 * 1024 * 1024) + "\"}")' > "$big"
  code="$(curl -sS -o /dev/null -w '%{http_code}' -b "$jar" -H 'content-type: application/json' "$base/inventory/calc" --data-binary "@$big")"
  rm -f "$big"
  echo "본문 3MB → $code"
  [ "$code" != "200" ]
  exit 0
fi

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}

echo "── 포트가 비어 있는가 (.env)   $(date '+%Y-%m-%d %H:%M:%S')   $(uptime | sed 's/.*load/load/')"
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
run 'cd apps/api-py && uv run pytest -q esgapi/inventory/tests/test_property.py --durations=5'   # 속성 다섯의 시간
# hypothesis(MPL-2.0)는 dev 에만: 런타임 의존성 목록(uv export --no-dev)에 없어야 한다.
run 'cd apps/api-py && test "$(uv export --frozen --no-dev --no-emit-project --no-hashes 2>/dev/null | grep -c -i -E "^(hypothesis|sortedcontainers)==")" = 0'
run 'apps/api-py/scripts/check-wheel.sh'             # wheel 안에 tests 폴더가 없는가
# wheel 에 패키지 자료 셋이 실리는가.
run 'cd apps/api-py && out="$(mktemp -d)" && uv build --wheel -o "$out" >/dev/null 2>&1 && test "$(unzip -Z1 "$out"/*.whl | grep -c "^esgapi/inventory/data/.*\.json$")" = 3; s=$?; rm -rf "$out"; exit $s'

# 통합 테스트가 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다).
EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
export EDK_JWT_PUBLIC_KEY

# ── 컨테이너가 있어야 도는 것 ──
run 'docker compose up -d --build --wait'
run 'apps/api-py/scripts/test-business.sh -n 2'      # 업무 층 (= pytest -q -m django_db -n 2)
run 'apps/api-py/scripts/test-security.sh'           # 보안 층 (= pytest -q --ds=esgapi.config.settings.test_security -m security)
run 'apps/api-py/scripts/test-integration.sh'        # 통합 6
# 이미지 안: hypothesis 가 없고, 패키지 자료 셋이 있고, tests 폴더가 없다.
IMAGE="$(sed -n 's/^COMPOSE_PROJECT_NAME=//p' .env)/api-py:local"
export IMAGE
run 'docker run --rm "$IMAGE" python -c "
import importlib.util, importlib.resources as r
assert importlib.util.find_spec(\"hypothesis\") is None, \"hypothesis 가 이미지에 있다\"
assert importlib.util.find_spec(\"sortedcontainers\") is None
data = sorted(p.name for p in r.files(\"esgapi.inventory\").joinpath(\"data\").iterdir() if p.name.endswith(\".json\"))
assert data == [\"factors.kr-ets-sample.json\", \"gwp-sets.json\", \"unit-conversions.json\"], data
assert not r.files(\"esgapi.inventory\").joinpath(\"tests\").is_dir(), \"tests 가 이미지에 있다\"
print(\"image ok:\", data)
"'
# 떠 있는 api-py 에 curl: 교환 → POST /inventory/calc (표를 싣지 않는다 = 이미지에 실린 표) → 합계가 손계산 값(H01).
run 'apps/api-py/scripts/section4-PY4.sh --curl'
run 'docker compose down -v'
run 'scripts/verify.sh'

# 허용 경로 밖의 변경: 없어야 한다.
run "test -z \"\$(git status --porcelain | grep -v -E '^.. (apps/api-py/esgapi/inventory/|apps/api-py/generated/|apps/api-py/scripts/section4-PY4.sh|apps/api-py/(pyproject.toml|uv.lock|\\.gitignore)|README\\.md)')\""
echo
echo "── 끝   $(date '+%Y-%m-%d %H:%M:%S')   $(uptime | sed 's/.*load/load/')"
