#!/usr/bin/env bash
# 밴드 PY7(MARC-TICK-54, Scope 3 의 순수 규칙과 경로 둘)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-PY7.sh            전체(컨테이너를 띄우고 내린다). 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-PY7.sh --pure     컨테이너 없이 도는 것만(순수 층, 골든, 재생, 경계 검사)
#         apps/api-py/scripts/section4-PY7.sh --curl     컨테이너를 띄워 계수 표를 들이고 curl 로 묻는 것만
# 심은 파손은 따로다: apps/api-py/esgapi/inventory/tests/planted-breaks-PY7.sh
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# esg-lab 은 읽기만 한다(TS CLI 를 돌리되 산출물은 임시 폴더로, 계수 표는 읽기 전용으로 컨테이너에 붙인다).
# AI 공급사 호출 0. 임시 파일은 지우지 않는다(mktemp 의 것이라 운영체제가 치운다).
set -u
cd "$(dirname "$0")/../../.."
B=6aaa84e   # 기준 커밋(발주서 §1-1)
ESG_LAB="${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
export ESG_LAB
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh·gen-ts-types.sh·esg-lab 의 CLI 가 Node 22 를 쓴다
MODE="${1:-all}"

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
sql() { docker compose exec -T postgres psql -U "$OWNER" -d "$DB" -At -c "$1"; }
expect() { # <설명> <얻은 값> <기대>
  if [ "$2" = "$3" ]; then echo "  맞음  $1 = $2"; else echo "  ★ 다름  $1 = $2 (기대 $3)"; return 1; fi
}
# 기계가 바쁠 때 빌드·verify 앞에서 기다린다: 메모리 free 20% 이상, 1분 부하 12 미만. 최대 10분(그 뒤엔 그냥 돈다).
gate() {
  local tries=0 free load
  while [ "$tries" -lt 20 ]; do
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then break; fi
    tries=$((tries + 1)); sleep 30
  done
  echo "  (문: free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 30초)"
}

echo "── 부하와 포트 (.env)"
uptime
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
echo "esg-lab: HEAD $(git -C "$ESG_LAB" rev-parse --short HEAD), 돌리기 전의 변경 $(git -C "$ESG_LAB" status --porcelain | wc -l | tr -d ' ') 건"

# ════════════════════════════════════════════════════════════════════
pure_part() {
  run 'cd apps/api-py && uv sync --frozen'
  run 'cd apps/api-py && uv run ruff check . && uv run ruff format --check .'
  run 'cd apps/api-py && uv run pyright'
  run 'cd apps/api-py && uv run lint-imports'
  run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security"'                    # 순수 층 전체
  run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security" esgapi/inventory'   # 그 가운데 inventory
  # G1 을 esg-lab 의 TS CLI 로 다시 만들어 저장소의 골든과 diff 0 (esg-lab 파일 변경 0).
  run 'cd apps/api-py && esgapi/inventory/tests/data/scope3/make-golden.sh --check'
  # G2 전체 일치 · G3 105·107·109/113 (다듬은 사본으로) · G4 의 수. 자료가 없으면 건너뛰지 않고 실패한다.
  run 'cd apps/api-py && uv run python -m esgapi.inventory.tests.scope3_replay "$ESG_LAB"'
  run 'test -z "$(git -C "$ESG_LAB" status --porcelain)"'                                         # esg-lab 변경 0
  # 새 의존성 0: regex 패키지를 들이지 않았다.
  run 'cd apps/api-py && test "$(uv export --frozen --no-dev --no-emit-project --no-hashes 2>/dev/null | grep -c -i -E "^regex==")" = 0'
  run 'test -z "$(git diff --name-only "$B" -- apps/api-py/pyproject.toml apps/api-py/uv.lock)"'  # 의존성 파일 0줄
  run 'apps/api-py/scripts/check-wheel.sh'                                                        # wheel 에 tests 폴더가 없는가
  run 'wheel_prompts'
  run 'additive'
}

# wheel 에 프롬프트 템플릿(`prompts/<이름>/<판>.md`)이 둘 실렸는가. 곁의 README.md 는 따로 센다.
wheel_prompts() {
  local out; out="$(mktemp -d)"
  (cd apps/api-py && uv build --wheel -o "$out" >/dev/null 2>&1) || return 1
  local names; names="$(unzip -Z1 "$out"/*.whl)"
  expect "wheel 의 inventory 템플릿(prompts/*/*.md)" "$(printf '%s\n' "$names" | grep -c -E '^esgapi/inventory/prompts/[^/]+/[0-9]+\.md$')" 2 &&
  expect "wheel 의 inventory/prompts/README.md" "$(printf '%s\n' "$names" | grep -c -x 'esgapi/inventory/prompts/README.md')" 1 &&
  expect "wheel 의 tests 폴더 아래 파일" "$(printf '%s\n' "$names" | grep -c '/tests/')" 0 &&
  expect "wheel 의 calc/scope3 파일" "$(printf '%s\n' "$names" | grep -c -E '^esgapi/inventory/calc/scope3/[a-z0-9_]+\.py$')" 15
}

# generated/openapi.json 이 기준($B)에 더하기만 했는가: 기준의 경로·operationId 열둘·스키마가 글자까지 그대로고
# 새 경로 둘은 /inventory/scope3/ 아래다.
additive() {
  local old; old="$(mktemp)"
  git show "$B:apps/api-py/generated/openapi.json" > "$old"
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
        added_operation_ids: ($new_ids - $old_ids | sort),
        added_schemas: (($n.components.schemas | keys) - ($o.components.schemas | keys) | length)
      }' | tee "$old.out"
  jq -e '.old_paths == .old_paths_kept_verbatim and .old_schemas == .old_schemas_kept_verbatim
         and .old_operation_ids == 12 and .old_operation_ids_kept == 12
         and .added_paths == ["/inventory/scope3/classify", "/inventory/scope3/shortlist"]
         and .added_operation_ids == ["inventory_scope3_classify", "inventory_scope3_shortlist"]' "$old.out" >/dev/null
}

# ════════════════════════════════════════════════════════════════════
# 떠 있는 api-py 에 묻는다. 계수 표를 세 번 들인다: 패키지 사본 600 → 전체(기본) 10,356 → disputed 까지 10,754.
shortlist() { curl -s -b "$JAR" -X POST "$API/inventory/scope3/shortlist" -H 'content-type: application/json' -d "$1"; }
timed() { curl -s -o /dev/null -w '%{time_total}' -b "$JAR" -X POST "$API/inventory/scope3/shortlist" -H 'content-type: application/json' -d "$1"; }
status_of() { curl -s -o /dev/null -w '%{http_code}' "$@"; }

STEEL_KG='{"row":{"itemName":"스테인리스 강판","unit":"kg"},"category":1,"basis":"physical"}'
LAPTOP='{"row":{"itemName":"노트북 구매","unit":"대"},"category":1}'
TRUCK='{"row":{"itemName":"원자재 운송","transport":{"mode":"트럭","weightKg":"21000"}},"category":4}'
export STEEL_KG LAPTOP TRUCK

login_viewer() {
  JAR="$(mktemp)"; export JAR
  sql "INSERT INTO tenants (id, name, created_at) VALUES ('s4-py7', '검증 회사', now()) ON CONFLICT DO NOTHING" >/dev/null
  local token; token="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py token --tenant s4-py7 --sub s4-viewer --role viewer)"
  expect "교환(viewer)" "$(status_of -c "$JAR" -X POST "$API/auth/exchange" -H 'content-type: application/json' -d "{\"token\":\"$token\"}")" 200
}

ask_package_copy() {
  login_viewer || return 1
  expect "세션 없이 POST /inventory/scope3/shortlist" "$(status_of -X POST "$API/inventory/scope3/shortlist" -H 'content-type: application/json' -d "$STEEL_KG")" 401 &&
  expect "낱줄(패키지 사본)" "$(sql 'SELECT count(*) FROM reference_factor_records')" 600 &&
  expect "그 가운데 Scope 3 범주가 붙은 낱줄" "$(sql 'SELECT count(DISTINCT record_id) FROM reference_factor_scope3_categories')" 0 &&
  expect "shortlist {범주 1, kg} → status, physical" "$(shortlist '{"row":{"itemName":"스테인리스 강판","unit":"kg"},"category":1}' | jq -c '[.status, .physical, .catalog.rejectedTotal]')" '["no_candidates","no_activity_candidates",0]'
}

ask_default_table() {
  login_viewer || return 1
  expect "낱줄(전체, 기본 이용 조건)" "$(sql 'SELECT count(*) FROM reference_factor_records')" 10356 &&
  expect "keiti-epd 의 낱줄" "$(sql "SELECT count(*) FROM reference_factor_records WHERE source_id = 'keiti-epd'")" 0 &&
  expect "shortlist {범주 1, 단위 대} → basis, fallbackReason, total, shown, rejectedTotal" \
    "$(shortlist "$LAPTOP" | jq -c '[.status, .basis, .fallbackReason, .total, .shown, .catalog.rejectedTotal]')" '["shortlisted","spend","unit_mismatch",1016,25,0]' || return 1
  echo "  shortlist {범주 4, 운송 행(무게 있음)} → $(shortlist "$TRUCK" | jq -c '{status, basis, fallbackReason, total, shown, lexicalMatches, first: .candidates[0].id, per: ([.candidates[].per] | unique)}')"
  echo "  shortlist {범주 1, kg, basis physical} → $(shortlist "$STEEL_KG" | jq -c '{status, basis, total, shown, lexicalMatches, first: .candidates[0].id, licenses: ([.candidates[].licenseStatus] | unique)}')"
  expect "범주 4 운송 행 → basis" "$(shortlist "$TRUCK" | jq -r .basis)" physical &&
  expect "범주 1 kg physical → 후보의 이용 조건" "$(shortlist "$STEEL_KG" | jq -c '[.candidates[].licenseStatus] | unique')" '["ok"]' || return 1
  KG_TOTAL_DEFAULT="$(shortlist "$STEEL_KG" | jq -r .total)"; echo "$KG_TOTAL_DEFAULT" > "$TOTALS"
  echo "  응답 시간(초, curl time_total. 한 번씩): 대→지출 $(timed "$LAPTOP") · 운송 $(timed "$TRUCK") · kg 활동 $(timed "$STEEL_KG")"
  echo "  응답 시간(초, 두 번째): 대→지출 $(timed "$LAPTOP") · 운송 $(timed "$TRUCK") · kg 활동 $(timed "$STEEL_KG")"
}

# ★ 마·차: 새 selector 한 번의 시간·쿼리 수·행 수와, DB 의 정렬(collation)이 코드 포인트 순과 갈리는 자리.
selector_facts() {
  echo "  DB 의 datcollate|datctype: $(sql 'SELECT datcollate, datctype FROM pg_database WHERE datname = current_database()')"
  docker compose exec -T api-py python manage.py shell -c '
import time
from django.db import connection
from django.test.utils import CaptureQueriesContext
from esgapi.reference import selectors
from esgapi.reference.models import FactorRecordRow
for licenses in (frozenset({"ok", "unverified"}), frozenset({"ok", "unverified", "disputed"})):
    times = []
    for _ in range(3):
        with CaptureQueriesContext(connection) as queries:
            started = time.perf_counter()
            views = selectors.scope3_candidate_records(licenses=licenses)
            times.append(round((time.perf_counter() - started) * 1000))
    ids = [view.id for view in views]
    by_db = list(FactorRecordRow.objects.filter(id__in=ids).order_by("id").values_list("id", flat=True))
    moved = sum(1 for a, b in zip(by_db, ids) if a != b)
    inverted = sum(1 for a, b in zip(by_db, by_db[1:]) if a > b)
    print(f"  selector({sorted(licenses)}): 행 {len(ids)}, 쿼리 {len(queries)}, 시간(ms) {times}")
    print(f"    DB 의 ORDER BY id 와 코드 포인트 순이 다른 자리 {moved} / {len(ids)}, 이웃한 쌍 가운데 뒤집힌 것 {inverted}")
'
}

ask_all_licenses() {
  login_viewer || return 1
  local before; before="$(cat "$TOTALS")"
  local all='{"row":{"itemName":"스테인리스 강판","unit":"kg"},"category":1,"basis":"physical","license":"ok,unverified,disputed"}'
  expect "낱줄(disputed 까지)" "$(sql 'SELECT count(*) FROM reference_factor_records')" 10754 &&
  expect "범주 1 kg physical, 기본 license → total(disputed 를 들이기 전과 같다)" "$(shortlist "$STEEL_KG" | jq -r .total)" "$before" &&
  expect "같은 요청, 기본 license → 후보의 이용 조건" "$(shortlist "$STEEL_KG" | jq -c '[.candidates[].licenseStatus] | unique')" '["ok"]' || return 1
  echo "  같은 요청 + license=ok,unverified,disputed → $(shortlist "$all" | jq -c '{total, shown, licenses: ([.candidates[].licenseStatus] | unique)}')"
  local more; more="$(shortlist "$all" | jq -r .total)"
  [ "$more" -gt "$before" ] && echo "  맞음  disputed 를 명시하면 total 이 는다 ($before → $more)" || { echo "  ★ 다름  total 이 늘지 않았다 ($before → $more)"; return 1; }
  expect "disputed 가 섞여 나온다" "$(shortlist "$all" | jq -c '[.candidates[].licenseStatus] | unique | index("disputed") != null')" true &&
  expect "범주 1 의 활동 기반 후보(단위로 거르기 전. disputed 포함)" "$(sql "SELECT count(*) FROM reference_factor_records r JOIN reference_factor_scope3_categories c ON c.record_id = r.id WHERE c.category = 1 AND r.record_type = 'emission_factor' AND r.gas = 'CO2e' AND r.value IS NOT NULL AND r.factor_type <> 'spend'")" 271
}

ask_classify() {
  login_viewer || return 1
  local body='{"rows":[{"rowId":"r1","itemName":"스테인리스 강판","unit":"kg","quantity":"12000","amount":"21600000","currency":"KRW"}]}'
  local out; out="$(mktemp)"
  expect "세션 없이 POST /inventory/scope3/classify" "$(status_of -X POST "$API/inventory/scope3/classify" -H 'content-type: application/json' -d "$body")" 401 &&
  expect "POST /inventory/scope3/classify (떠 있는 서버) → 상태 코드" "$(curl -s -o "$out" -w '%{http_code}' -b "$JAR" -X POST "$API/inventory/scope3/classify" -H 'content-type: application/json' -d "$body")" 503 &&
  expect "그 본문" "$(jq -c . "$out")" '{"error":{"code":"llm_not_configured","message":"생성 모델 경로 mock 가 이 서버에 준비되어 있지 않다"}}' &&
  expect "묶음 21 → 413 (공급사에 닿기 전에 걸린다)" "$(status_of -b "$JAR" -X POST "$API/inventory/scope3/classify" -H 'content-type: application/json' -d "$(jq -nc '{rows: [range(21) | {rowId: "r\(.)", itemName: "품목 \(.)"}]}')")" 413
}

container_part() {
  # 통합 테스트와 아래 curl 이 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다).
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  TOTALS="$(mktemp)"; export TOTALS
  for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "  (포트 $port 는 이미 열려 있다: $(lsof -nP -iTCP:"$port" -sTCP:LISTEN | tail -1 | cut -c1-40))"; fi
  done
  gate
  run 'docker compose up -d --build --wait'
  if [ "$MODE" != "--curl" ]; then
    run 'apps/api-py/scripts/test-business.sh -n 2'      # 업무 층: 주인 역할, 테스트마다 롤백
    run 'apps/api-py/scripts/test-security.sh'           # 보안 층: 앱 역할(esg_app), 진짜 커밋, 직렬
    run 'apps/api-py/scripts/test-integration.sh'        # 통합 6: 떠 있는 api-py 에 교환 → /me → /sites
  fi
  # 이미지 안: 템플릿 둘이 실렸고 tests 폴더는 없다.
  IMAGE="$PROJECT/api-py:local"; export IMAGE
  run 'docker run --rm "$IMAGE" sh -c "cd /app/.venv/lib/python3.13/site-packages/esgapi/inventory && ls prompts/*/1.md && test \$(ls prompts/*/1.md | wc -l) = 2 && ! find /app/.venv/lib -path \"*/site-packages/esgapi/*\" -name tests -type d | grep -q ."'

  run 'docker compose run --rm migrate-py python manage.py import_factors | tail -2'                 # 패키지 사본 600
  run 'ask_package_copy'
  run 'docker compose run --rm -v "$ESG_LAB/data/factors:/data:ro" migrate-py python manage.py import_factors /data/factors.jsonl | tail -2'   # 10,356
  run 'ask_default_table'
  run 'selector_facts'
  run 'docker compose run --rm -v "$ESG_LAB/data/factors:/data:ro" migrate-py python manage.py import_factors /data/factors.jsonl --include-license ok,unverified,disputed | tail -2'   # 10,754
  run 'ask_all_licenses'
  run 'selector_facts'
  run 'ask_classify'
  run 'docker compose down -v'
}

boundary_part() {
  # 아래 여섯은 기준 커밋 $B 와 견준다. 커밋 전에도 뒤에도 같은 답을 낸다(작업 트리 + 새 파일).
  changed() { { git diff --name-only "$B" -- "$@"; git ls-files --others --exclude-standard -- "$@"; } | sort -u; }
  run 'test -z "$(changed . | grep -v -E "^(apps/api-py/esgapi/inventory/|apps/api-py/esgapi/reference/selectors\.py$|apps/api-py/generated/|apps/api-py/scripts/section4-PY7\.sh$|apps/api-py/(pyproject\.toml|uv\.lock)$|README\.md$)")"'   # 허용 경로 밖 0
  run 'test -z "$(changed apps/api-py/esgapi/inventory | grep -v -E "^apps/api-py/esgapi/inventory/(calc/scope3/|prompts/|tests/|api\.py$|schemas\.py$|services\.py$|__init__\.py$)")"'   # Scope 1·2 의 파일 0줄
  run 'test -z "$(git diff --diff-filter=MDR --name-only "$B" -- apps/api-py/esgapi/inventory/tests)"'   # 기존 테스트 파일은 고치지 않았다
  run 'test "$(git diff --numstat "$B" -- apps/api-py/esgapi/reference/selectors.py | cut -f2)" = 0'        # selectors.py 는 추가만
  run 'test -z "$(changed apps/api-py/esgapi/reference | grep -v -E "^apps/api-py/esgapi/reference/selectors\.py$")"'   # reference 의 나머지 0줄
  run 'test -z "$(git diff -U0 "$B" -- apps/api-py/esgapi/inventory/api.py apps/api-py/esgapi/inventory/schemas.py apps/api-py/esgapi/inventory/services.py | grep -E "^-[^-]" | grep -v -E "^-(from|import) |^-    [A-Za-z_]+,$|^-\)$")"'   # 지운 줄은 import 줄뿐
  echo
  echo "  (참고) 바뀐 파일 $(changed . | wc -l | tr -d ' ') 개, git status --porcelain $(git status --porcelain | wc -l | tr -d ' ') 줄"
  echo "  (참고) 기존 세 파일에서 지운 줄:"; git diff -U0 "$B" -- apps/api-py/esgapi/inventory/api.py apps/api-py/esgapi/inventory/schemas.py apps/api-py/esgapi/inventory/services.py | grep -E '^-[^-]' | sed 's/^/    /'
  echo "  (참고) inventory/__init__.py 에서 지운 줄:"; git diff -U0 "$B" -- apps/api-py/esgapi/inventory/__init__.py | grep -E '^-[^-]' | sed 's/^/    /'
}

case "$MODE" in
  --pure) pure_part; boundary_part ;;
  --curl) container_part ;;
  *)
    pure_part
    container_part
    gate
    run 'scripts/verify.sh'
    # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
    run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3; test -z "$(docker images --format "{{.Repository}}" | grep "^$PROJECT/")"'
    boundary_part
    ;;
esac
