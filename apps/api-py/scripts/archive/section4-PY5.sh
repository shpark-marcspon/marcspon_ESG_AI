#!/usr/bin/env bash
# 밴드 PY5(MARC-TICK-51, 기준정보)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-PY5.sh            전체(컨테이너를 띄우고 내린다). 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-PY5.sh planted    심은 파손 일곱(Postgres 만 띄우고 내린다). 마지막 줄 PLANTED=
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# esg-lab 은 읽기만 한다(전체 계수 표를 읽기 전용으로 컨테이너에 붙인다). 경로가 다르면 ESG_LAB 로 준다.
set -u
cd "$(dirname "$0")/../../.."
BASE=7366123
ESG_LAB="${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 와 gen-ts-types.sh 가 Node 22 를 쓴다

env_value() { sed -n "s/^$1=//p" .env | tail -1; }
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
OWNER="$(env_value POSTGRES_OWNER_USER)"
DB="$(env_value POSTGRES_DB)_py"
API="http://127.0.0.1:$(env_value API_PY_PORT)"

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}
# 주인 역할로 한 값을 묻는다(분모를 세는 데만 쓴다).
sql() { docker compose exec -T postgres psql -U "$OWNER" -d "$DB" -At -c "$1"; }
# 값을 찍고 기대와 견준다.
expect() { # <설명> <얻은 값> <기대>
  if [ "$2" = "$3" ]; then echo "  맞음  $1 = $2"; else echo "  ★ 다름  $1 = $2 (기대 $3)"; return 1; fi
}

# ════════════════════════════════════════════════════════════════════
if [ "${1:-}" = "planted" ]; then
  # 심은 파손: 규칙을 하나씩 망가뜨리고, 그것을 잡아야 할 테스트가 빨개지는지 본다.
  # 심기 전의 파일을 임시 폴더에 베껴 두었다가 되돌린다(git 을 쓰지 않는다). 끝나면 작업 트리가 처음과 같아야 한다.
  cd apps/api-py
  backup="$(mktemp -d)"
  log="$(mktemp)"
  before="$( { git status --porcelain; git diff; } | shasum | cut -d' ' -f1)"
  touched=""
  restore() { [ -n "$touched" ] && cp "$backup/file" "$touched"; touched=""; }
  trap 'restore; rm -rf "$backup" "$log"; (cd ../.. && docker compose down -v >/dev/null 2>&1)' EXIT

  plant() { # <파일> <바꿀 글> <바꾼 글>   글이 정확히 한 번 있어야 한다
    cp "$1" "$backup/file"; touched="$1"
    python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"심지 못함: {path} 에 바꿀 글이 {text.count(old)}번 있다")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
  }
  total=0; caught=0
  verdict() { # <설명> <잡아야 할 테스트 이름(또는 계약)의 조각>   $log 에 방금 돌린 출력이 있다
    total=$((total + 1))
    local summary; summary="$(grep -E '^[0-9]+ (passed|failed)|^(FAILED|ERROR) |BROKEN|^Contracts:' "$log" | tail -1)"
    if grep -E '^(FAILED|ERROR) |BROKEN' "$log" | grep -q -- "$2"; then
      caught=$((caught + 1)); echo "잡힘    $1"
    else
      echo "★ 못 잡음  $1"
    fi
    echo "          잡은 것: $2"
    echo "          빨간 것 $(grep -c -E '^(FAILED|ERROR) |BROKEN$' "$log") 개 / 요약: $summary"
    restore
  }
  pure() { uv run --frozen pytest -q -m "not django_db and not security" esgapi/reference >"$log" 2>&1; }

  (cd ../.. && docker compose up -d --wait postgres >/dev/null 2>&1) || { echo "Postgres 를 띄우지 못했다"; exit 2; }
  echo "── 심지 않음: 순수·업무(reference)·보안 층이 초록인가"
  pure; tail -1 "$log"
  scripts/test-business.sh esgapi/reference >"$log" 2>&1; tail -1 "$log"
  scripts/test-security.sh >"$log" 2>&1; tail -1 "$log"
  echo

  plant esgapi/reference/licenses.py \
    'DEFAULT_LICENSES_TEXT: Final = "ok,unverified"' 'DEFAULT_LICENSES_TEXT: Final = "ok,unverified,disputed"'
  scripts/test-business.sh esgapi/reference/tests/test_import.py >"$log" 2>&1
  verdict "1. 가져오기의 기본(--include-license)에 disputed 를 넣음" "test_disputed_rows_are_left_out_by_default"

  plant esgapi/reference/calc/assemble.py \
    '    if len(found) > 1:
        return fail("record_ambiguous", parameter=parameter, criteria=criteria, recordIds=[r.id for r in found])
    record = found[0]' '    record = found[0]'
  pure
  verdict "2. 낱줄이 둘일 때 첫 것을 고름(고정연소)" "test_two_rows_for_the_same_condition_are_ambiguous"

  plant esgapi/reference/calc/value_raw.py \
    '_DECIMAL = re.compile(r"-?[0-9]+(\.[0-9]+)?")' '_DECIMAL = re.compile(r"-?[0-9]+(\.[0-9]+)?([eE][-+]?[0-9]+)?")'
  pure
  verdict "3. value_raw 에서 지수 표기를 받음" "test_odd_notation_fails\[7.32e4\]"

  plant esgapi/reference/calc/policy.py 'if chosen["co2"] != chosen["oxidation"]:' 'if False:'
  pure
  verdict "4. 산화계수 등급을 CO2 등급과 다르게 허용함" "test_tier_combinations_the_guideline_forbids"

  plant esgapi/reference/calc/assemble.py 'from collections.abc import Callable, Mapping, Sequence' \
    'import django  # noqa: F401
from collections.abc import Callable, Mapping, Sequence'
  COLUMNS=400 uv run --frozen lint-imports >"$log" 2>&1
  verdict "5. calc/assemble.py 에 import django" "다\. 순수 모듈"

  plant esgapi/reference/migrations/0001_reference.py '        grant(TABLES, "SELECT"),
' ''
  scripts/test-security.sh >"$log" 2>&1
  verdict "6. 마이그레이션에서 앱 역할의 SELECT grant 를 뺌 → 보안 층" "test_app_role_may_select_and_nothing_else"
  # 같은 파손을 업무 층은 못 잡는다(주인 역할로 붙어 권한에 걸리지 않는다). 그래서 보안 층에 테스트가 있다.
  plant esgapi/reference/migrations/0001_reference.py '        grant(TABLES, "SELECT"),
' ''
  scripts/test-business.sh esgapi/reference >"$log" 2>&1
  echo "          (같은 파손, 업무 층: $(tail -1 "$log") — 초록이어야 「업무 층은 못 잡는다」가 맞다)"
  restore

  plant esgapi/reference/api.py 'licenses = DEFAULT_LICENSES if query.license is None' \
    'licenses = frozenset({"ok", "unverified", "disputed"}) if query.license is None'
  scripts/test-business.sh esgapi/reference/tests/test_api.py >"$log" 2>&1
  verdict "7. 조회의 license 기본값에서 disputed 를 허용함" "test_disputed_rows_are_hidden_unless_the_license_is_named"

  after="$( { git status --porcelain; git diff; } | shasum | cut -d' ' -f1)"
  echo
  [ "$before" = "$after" ] && echo "되돌림: 작업 트리가 심기 전과 같다" || echo "★ 되돌림 실패: 작업 트리가 달라졌다"
  echo "PLANTED=$caught/$total"
  [ "$caught" = "$total" ] && [ "$before" = "$after" ]
  exit $?
fi

# ════════════════════════════════════════════════════════════════════
echo "── 부하와 포트 (.env)"
uptime
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; fi
done

# ── 컨테이너 없이 도는 것 ──
run 'cd apps/api-py && uv sync --frozen'
run 'cd apps/api-py && uv run ruff check . && uv run ruff format --check .'
run 'cd apps/api-py && uv run pyright'
run 'cd apps/api-py && uv run lint-imports'
run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security"'            # 순수 층 전체
run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security" esgapi/reference'   # 그 가운데 이 밴드
run 'apps/api-py/scripts/check-wheel.sh'                                                  # wheel 에 tests 폴더가 없는가

# generated/openapi.json 이 기준($BASE) 것에 더하기만 했는가: 기준의 경로 여섯·operationId 일곱·스키마가 글자까지 그대로고
# 새 경로 넷은 전부 /reference/ 아래다. (diff 의 줄 수로는 알 수 없다: 키를 가나다순으로 찍어 줄이 밀린다.)
additive() {
  local old; old="$(mktemp)"
  git show "$BASE:apps/api-py/generated/openapi.json" > "$old"
  jq -n --slurpfile old "$old" --slurpfile new apps/api-py/generated/openapi.json '
    ($old[0]) as $o | ($new[0]) as $n
    | ([$o.paths[][] | .operationId]) as $old_ids | ([$n.paths[][] | .operationId]) as $new_ids
    | {
        old_paths: ($o.paths | length),
        old_paths_kept_verbatim: ([$o.paths | keys[] | select($n.paths[.] == $o.paths[.])] | length),
        old_schemas: ($o.components.schemas | length),
        old_schemas_kept_verbatim:
          ([$o.components.schemas | keys[] | select($n.components.schemas[.] == $o.components.schemas[.])] | length),
        old_operation_ids: ($old_ids | length),
        old_operation_ids_kept: ($old_ids - ($old_ids - $new_ids) | length),
        added_paths: (($n.paths | keys) - ($o.paths | keys)),
        added_operation_ids: ($new_ids - $old_ids | sort)
      }' | tee "$old.out"
  jq -e '.old_paths == .old_paths_kept_verbatim and .old_schemas == .old_schemas_kept_verbatim
         and .old_operation_ids == .old_operation_ids_kept
         and .added_paths == ["/reference/assemble", "/reference/assemble-electricity", "/reference/factors", "/reference/sources"]
         and .added_operation_ids == ["reference_assemble", "reference_assemble_electricity", "reference_factors", "reference_sources"]' \
    "$old.out" >/dev/null
  local status=$?; rm -f "$old" "$old.out"; return $status
}
run 'additive'

# 통합 테스트와 아래 curl 이 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다).
EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
export EDK_JWT_PUBLIC_KEY

# ── 컨테이너가 있어야 도는 것 ──
run 'docker compose up -d --build --wait'
run 'apps/api-py/scripts/test-business.sh -n 2'      # 업무 층: 주인 역할, 테스트마다 롤백
run 'apps/api-py/scripts/test-security.sh'           # 보안 층: 앱 역할(esg_app), 진짜 커밋, 직렬
run 'apps/api-py/scripts/test-integration.sh'        # 통합 6: 떠 있는 api-py 에 교환 → /me → /sites

# 이미지 안: 자료 사본 둘이 실렸고 tests 폴더는 없다.
IMAGE="$PROJECT/api-py:local"
export IMAGE
run 'docker run --rm "$IMAGE" sh -c "cd /app/.venv/lib/python3.13/site-packages/esgapi/reference && ls -l data && test -s data/factors.kr.jsonl && test -s data/mappings.kr-ets.json && ! find /app/.venv/lib -path \"*/site-packages/esgapi/*\" -name tests -type d | grep ."'

by_source="SELECT string_agg(source_id || ' ' || n, ', ' ORDER BY source_id) FROM (SELECT source_id, count(*) AS n FROM reference_factor_records GROUP BY 1) t"
by_license="SELECT string_agg(license_status || ' ' || n, ', ' ORDER BY license_status) FROM (SELECT s.license_status, count(*) AS n FROM reference_factor_records r JOIN reference_sources s ON s.id = r.source_id GROUP BY 1) t"
export by_source by_license

# (1) 인자 없이: 패키지에 실린 사본 600건. 컨테이너 안에서는 사본이 site-packages 아래에 있다.
run 'docker compose run --rm migrate-py python manage.py import_factors'
check_600() {
  expect "낱줄" "$(sql 'SELECT count(*) FROM reference_factor_records')" 600 &&
  expect "출처별" "$(sql "$by_source")" "gir-2024 8, gir-2025 32, kr-ets-byl06 12, kr-ets-byl10 385, kr-ets-byl11 55, kr-ets-byl12 108" &&
  expect "출처 행(낱줄 있는 여섯 + kr-ets-byl05)" "$(sql 'SELECT count(*) FROM reference_sources')" 7 &&
  expect "대응표" "$(sql 'SELECT count(*) FROM reference_mappings')" 1
}
run 'check_600'
# 멱등: 한 번 더 돌려도 행 수가 그대로다.
run 'docker compose run --rm migrate-py python manage.py import_factors | tail -3 && check_600'

# (2) esg-lab 의 전체 계수 표(10,754줄)를 기본으로: disputed(KEITI 398)가 빠져 10,356.
run 'docker compose run --rm -v "$ESG_LAB/data/factors:/data:ro" migrate-py python manage.py import_factors /data/factors.jsonl --mapping /data/mappings.kr-ets.json'
check_default() {
  expect "원본의 줄 수(분모)" "$(wc -l < "$ESG_LAB/data/factors/factors.jsonl" | tr -d ' ')" 10754 &&
  expect "낱줄" "$(sql 'SELECT count(*) FROM reference_factor_records')" 10356 &&
  expect "keiti-epd 의 낱줄" "$(sql "SELECT count(*) FROM reference_factor_records WHERE source_id = 'keiti-epd'")" 0 &&
  expect "keiti-epd 의 출처 행" "$(sql "SELECT count(*) FROM reference_sources WHERE id = 'keiti-epd'")" 0 &&
  expect "license_status 별" "$(sql "$by_license")" "ok 9756, unverified 600" &&
  expect "범주 연결(SUMMARY 의 12,271 에서 keiti 480 을 뺀 것)" "$(sql 'SELECT count(*) FROM reference_factor_scope3_categories')" 11791 &&
  expect "DEFRA 의 값 없는 행(value 가 NULL 이고 value_status 가 남았다)" "$(sql "SELECT count(*) || ' ' || string_agg(DISTINCT value_status, ',') FROM reference_factor_records WHERE source_id = 'defra-2026' AND value IS NULL")" "1705 not_available_in_source"
}
run 'check_default'

# (3) disputed 를 명시하면 10,754. (--mapping 을 주지 않아 대응표는 건드리지 않는다.)
run 'docker compose run --rm -v "$ESG_LAB/data/factors:/data:ro" migrate-py python manage.py import_factors /data/factors.jsonl --include-license ok,unverified,disputed'
check_all() {
  expect "낱줄" "$(sql 'SELECT count(*) FROM reference_factor_records')" 10754 &&
  expect "출처별" "$(sql "$by_source")" "defra-2026 8740, epa-seef-v1.3 1016, gir-2024 8, gir-2025 32, keiti-epd 398, kr-ets-byl06 12, kr-ets-byl10 385, kr-ets-byl11 55, kr-ets-byl12 108" &&
  expect "license_status 별" "$(sql "$by_license")" "disputed 398, ok 9756, unverified 600" &&
  expect "범주 연결(SUMMARY 의 표 「카테고리 × 계수 유형」의 계를 더한 것)" "$(sql 'SELECT count(*) FROM reference_factor_scope3_categories')" 12271 &&
  expect "범주별" "$(sql "SELECT string_agg(category || ':' || n, ' ' ORDER BY category) FROM (SELECT category, count(*) AS n FROM reference_factor_scope3_categories GROUP BY 1) t")" "1:1384 2:1382 3:486 4:1700 5:328 6:1350 7:1143 8:1236 9:1700 12:326 13:1236"
}
run 'check_all'

# 앱 설정(앱 역할)으로 부르면 not_owner 로 멈춘다(api-py 컨테이너는 앱 역할의 주소만 안다). 종료 코드가 0 이 아니어야 한다.
run 'docker compose exec -T api-py python manage.py import_factors; code=$?; echo "  (명령의 종료 코드 $code)"; test $code -ne 0 && test "$(sql "SELECT count(*) FROM reference_factor_records")" = 10754'

# (4) 떠 있는 api-py 에 요청: 교환 → 낱줄 찾기 → 조립. disputed 가 든 DB 에서 기본 조회가 KEITI 를 내지 않는가.
requests() {
  local jar; jar="$(mktemp)"
  sql "INSERT INTO tenants (id, name, created_at) VALUES ('s4-py5', '검증 회사', now()) ON CONFLICT DO NOTHING" >/dev/null
  local token; token="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py token --tenant s4-py5 --sub s4-viewer --role viewer)"
  expect "세션 없이 GET /reference/factors" "$(curl -s -o /dev/null -w '%{http_code}' "$API/reference/factors")" 401 || return 1
  expect "교환(viewer)" "$(curl -s -o /dev/null -w '%{http_code}' -c "$jar" -X POST "$API/auth/exchange" -H 'content-type: application/json' -d "{\"token\":\"$token\"}")" 200 || return 1
  get() { curl -s -b "$jar" "$API$1"; }
  post() { curl -s -b "$jar" -X POST "$API$1" -H 'content-type: application/json' -d "$2"; }
  local all='license=ok,unverified,disputed'
  expect "GET /reference/factors?source=kr-ets-byl12 → total" "$(get '/reference/factors?source=kr-ets-byl12' | jq -r .total)" 108 &&
  expect "GET /reference/factors?source=keiti-epd (기본 license) → total" "$(get '/reference/factors?source=keiti-epd' | jq -c '[.total, .licenses]')" '[0,["ok","unverified"]]' &&
  expect "GET /reference/factors?source=keiti-epd&$all → total, 첫 줄의 상태" "$(get "/reference/factors?source=keiti-epd&$all" | jq -c '[.total, .items[0].licenseStatus, (.items[0].licenseNote != null)]')" '[398,"disputed",true]' &&
  expect "GET /reference/factors (기본) → total" "$(get '/reference/factors?limit=1' | jq -r .total)" 10356 &&
  expect "GET /reference/factors?$all → total" "$(get "/reference/factors?limit=1&$all" | jq -r .total)" 10754 &&
  expect "GET /reference/sources → 출처 수, keiti-epd 의 상태" "$(get '/reference/sources' | jq -c '[(.sources | length), (.sources[] | select(.id == "keiti-epd") | .licenseStatus)]')" '[10,"disputed"]' &&
  expect "POST /reference/assemble 경유 제조업 Tier 2 → ok, 발열량·CO2·산화계수" \
    "$(post /reference/assemble '{"fuel":"경유","combustionType":"stationary","industry":{"sector":"manufacturing_construction"},"tiers":{"kind":"explicit","calorific":2,"co2":2,"oxidation":2}}' | jq -c '[.ok, .value.factor.calorific.value, .value.factor.emissionFactors[0].value, .value.factor.oxidationFactor]')" \
    '[true,"35.2","73200","0.99"]' &&
  expect "POST /reference/assemble 에 LPG → 실패 갈래" \
    "$(post /reference/assemble '{"fuel":"LPG","fuelState":"기체","combustionType":"stationary","industry":{"sector":"manufacturing_construction"},"tiers":{"kind":"explicit","calorific":2,"co2":2,"oxidation":2}}' | jq -c '[.ok, .failure.kind, .failure.parameter]')" \
    '[false,"record_not_found","calorific"]' &&
  expect "POST /reference/assemble-electricity 표-69 → ok, CO2" \
    "$(post /reference/assemble-electricity '{"energyType":"electricity","source":"guideline_table69","gasForm":"per_gas"}' | jq -c '[.ok, .value.factor.emissionFactors[0].value]')" \
    '[true,"0.4567"]'
  local status=$?; rm -f "$jar"; return $status
}
run 'requests'

run 'docker compose down -v'
run 'scripts/verify.sh'
# 이 워크트리의 이미지를 지운다(바탕 이미지와 다른 워크트리의 것은 건드리지 않는다).
run 'docker image ls --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/.*:local$" | xargs -r docker image rm >/dev/null; ! docker image ls --format "{{.Repository}}" | grep -q "^$PROJECT/"'

# 허용 경로 밖의 변경이 없는가(발주서 §4 의 마지막 줄 그대로).
run 'test -z "$(git status --porcelain | grep -v -E '"'"'^.. (apps/api-py/esgapi/reference/|apps/api-py/tests/security/test_reference.py|apps/api-py/generated/|apps/api-py/scripts/section4-PY5.sh|apps/api-py/(pyproject.toml|uv.lock)|README\.md)'"'"')"'
echo
echo "▶ git status --porcelain | wc -l"
git status --porcelain | wc -l
echo "▶ esg-lab 을 건드리지 않았는가: (cd $ESG_LAB && git status --porcelain | wc -l)"
(cd "$ESG_LAB" && git status --porcelain | wc -l)
