#!/usr/bin/env bash
# 밴드 PY8a(MARC-TICK-56, 마무리의 코드 쪽: 게이트 두 단 · 십진 커널과 bool 거름을 core/calc 로 · operationId·413·행 상한)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-PY8a.sh               전체. 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-PY8a.sh --pure        컨테이너 없이 도는 것만(반복해 돌려도 된다)
#         apps/api-py/scripts/section4-PY8a.sh --containers  전량 verify.sh 한 번 + 떠 있어야 재는 것(3MB curl, 심은 파손 11·12)
# 전량 verify.sh 는 이 밴드에서 한 번만 돈다(게이트 자체를 고쳤고, ②③ 의 업무 층을 그 한 번이 겸한다).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# AI 공급사 호출 0. esg-lab 을 쓰지 않는다. 임시 파일은 지우지 않는다(mktemp 의 것이라 운영체제가 치운다).
set -u
cd "$(dirname "$0")/../../.."
B=c53201d   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh·gen-ts-types.sh 가 Node 22 를 쓴다
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers) ;; *) echo "사용: $0 [--pure|--containers]" >&2; exit 2 ;; esac

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
expect() { # <설명> <얻은 값> <기대>
  if [ "$2" = "$3" ]; then echo "  맞음  $1 = $2"; else echo "  ★ 다름  $1 = $2 (기대 $3)"; return 1; fi
}
# 기계가 바쁠 때 전량 앞에서 기다린다: 메모리 free 20% 이상, 1분 부하 12 미만. 30초마다, 최대 10분(그 뒤엔 그냥 돈다).
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

# 기준 $B 의 verify.sh 의 step 18줄이 지금의 전량 계획 안에 그 순서로 있는가(글자 대조. 따옴표만 벗긴다).
baseline_steps_are_kept() {
  local old new; old="$(mktemp)"; new="$(mktemp)"
  git show "$B:scripts/verify.sh" | grep -E '(^|[ !])step ' | sed -E 's/^(if ! )?step //; s/; then$//' | tr -d '"' > "$old"
  scripts/verify.sh --plan | grep '^step: ' | sed 's/^step: //' > "$new"
  expect "기준의 step 줄" "$(wc -l < "$old" | tr -d ' ')" 18 || return 1
  echo "  지금의 전량 계획 $(wc -l < "$new" | tr -d ' ')줄. 기준에 없던 줄:"
  awk 'NR == FNR { old[$0] = 1; next } !($0 in old) { print "    + " $0 }' "$old" "$new"
  awk 'NR == FNR { want[++n] = $0; next } i < n && $0 == want[i + 1] { i++ } END { exit !(i == n) }' "$old" "$new"
}
# pre-commit 의 모드. 커밋 전에는 추적되지 않는 파일이라 `git ls-files -s` 가 비어 있다: 그때는 임시 색인에 올려 본다.
hook_mode() {
  local mode; mode="$(git ls-files -s scripts/git-hooks/pre-commit | cut -c1-6)"
  if [ -z "$mode" ]; then
    local index; index="$(mktemp -u)"
    GIT_INDEX_FILE="$index" git read-tree HEAD
    GIT_INDEX_FILE="$index" git update-index --add scripts/git-hooks/pre-commit
    mode="$(GIT_INDEX_FILE="$index" git ls-files -s scripts/git-hooks/pre-commit | cut -c1-6)"
    echo "  (아직 커밋 전이다. 임시 색인에 올려 본 모드)"
  fi
  test -x scripts/git-hooks/pre-commit && expect "pre-commit 의 모드" "$mode" 100755
}

# ════════════════════════════════════════════════════════════════════
pure_part() {
  run 'scripts/check-gates.sh'
  run 'scripts/verify.sh --fast'                                           # 끝 줄 VERIFY_FAST=PASS. 단계마다 걸린 시간
  run 'diff <(git show "$B:scripts/verify.sh" | grep -c -E "(^|[ !])step ") <(echo 18) && scripts/verify.sh --plan'
  run 'baseline_steps_are_kept'
  run 'hook_mode'
  run 'git diff --quiet "$B" -- services/parser/docparse services/parser/schemas scripts/git-hooks/post-commit scripts/git-hooks/semantic-trailers-post-commit.sh'
  run 'test ! -e apps/api-py/esgapi/inventory/calc/decimal.py && test -z "$(grep -rn "inventory\.calc\.decimal\|def _not_a_bool" apps/api-py/esgapi --include="*.py")"'
  # 이 밴드가 닿은 모듈의 순수 층(건수)
  run 'cd apps/api-py && uv run --frozen pytest -q -m "not django_db and not security" esgapi/core esgapi/config esgapi/inventory esgapi/reconcile esgapi/accounts esgapi/reference'
  # 커널 테스트의 건수: 옮기기 전 44(파일 하나) = 옮긴 뒤 core 43 + inventory 에 남긴 1
  run 'cd apps/api-py && expect "커널 테스트(core) + 출처 테스트(inventory)" "$(uv run --frozen pytest -q -m "not django_db and not security" esgapi/core/tests/test_calc_decimal.py esgapi/inventory/tests/test_provenance.py | tail -1 | cut -d" " -f1)" 44'
  run 'test "$(jq -r "[.paths[][] | .operationId] | length" apps/api-py/generated/openapi.json)" = 14 && test "$(jq -r "[.paths[][] | .operationId | select(startswith(\"esgapi_\"))] | length" apps/api-py/generated/openapi.json)" = 0'
  run 'test "$(shasum -a 256 apps/api-py/generated/openapi.json | cut -d" " -f1)" = "$(cat apps/api-py/generated/api.d.ts.source-sha256)"'
  # 0줄로 두기로 한 것
  run 'git diff --quiet "$B" -- README.md apps/web apps/api-py/.importlinter apps/api-py/tests_integration apps/api-py/esgapi/reconcile/tests/golden apps/api-py/esgapi/reference/tests compose.yaml .dockerignore .env.example scripts/worktree-env.sh docker infra'
  # reference/api.py 에서 바뀐 줄은 import 와 response 줄뿐
  run 'test -z "$(git diff -U0 "$B" -- apps/api-py/esgapi/reference/api.py | grep -E "^[-+][^-+]" | grep -v -E "ERROR_RESPONSES")"'
  run 'contract_facts'
  run 'apps/api-py/scripts/check-wheel.sh'
  run 'apps/api-py/scripts/planted-breaks-PY8a.sh --pure'                  # 심은 파손 1~10·13·14
}

# 계약(generated/openapi.json)의 수: 경로·동작·스키마 이름이 기준과 같고, 바뀐 것은 operationId 일곱과 413 선언뿐이다.
contract_facts() {
  local old; old="$(mktemp)"
  git show "$B:apps/api-py/generated/openapi.json" > "$old"
  jq -n --slurpfile old "$old" --slurpfile new apps/api-py/generated/openapi.json '
    ($old[0]) as $o | ($new[0]) as $n
    | def ops(d): [d.paths | to_entries[] | .key as $p | .value | to_entries[] | {key: "\(.key) \($p)", value: .value}] | from_entries;
      (ops($o)) as $oo | (ops($n)) as $no
    | {
        paths: [($o.paths | length), ($n.paths | length)],
        operations: [($oo | length), ($no | length)],
        same_operation_keys: (($oo | keys) == ($no | keys)),
        schema_names_same: (($o.components.schemas | keys) == ($n.components.schemas | keys)),
        schemas_changed: [$o.components.schemas | keys[] | select($n.components.schemas[.] != $o.components.schemas[.])],
        renamed: [$oo | to_entries[] | select(.value.operationId != $no[.key].operationId) | "\(.key): \(.value.operationId) → \($no[.key].operationId)"],
        with_body: [$no | to_entries[] | select(.value.requestBody) | .key] | length,
        with_413: [$no | to_entries[] | select(.value.responses["413"]) | .key] | length,
        gained_413: [$no | to_entries[] | select(.value.responses["413"] and ($oo[.key].responses["413"] | not)) | .key]
      }' | tee "$old.out"
  jq -e '.paths == [13, 13] and .operations == [14, 14] and .same_operation_keys and .schema_names_same
         and (.renamed | length) == 7 and .with_body == 7 and .with_413 == 7 and (.gained_413 | length) == 5
         and .schemas_changed == ["Scope3ClassifyIn"]' "$old.out" > /dev/null
}

# ════════════════════════════════════════════════════════════════════
# 떠 있는 api-py 에 3MB 본문을 보낸다(gunicorn 을 거친다). 413 이 아니면 본 값을 그대로 적는다.
big_body_through_gunicorn() {
  local jar body out code token
  jar="$(mktemp)"; body="$(mktemp)"; out="$(mktemp)"
  docker compose exec -T postgres psql -U "$OWNER" -d "$DB" -At -c "INSERT INTO tenants (id, name, created_at) VALUES ('s4-py8a', '검증 회사', now()) ON CONFLICT DO NOTHING" > /dev/null
  token="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py token --tenant s4-py8a --sub s4-viewer --role viewer)"
  expect "교환(viewer)" "$(curl -s -o /dev/null -w '%{http_code}' -c "$jar" -X POST "$API/auth/exchange" -H 'content-type: application/json' -d "{\"token\":\"$token\"}")" 200 || return 1
  { printf '{"rows":[],"gwpSetId":"'; head -c 3145728 /dev/zero | tr '\0' 'x'; printf '"}'; } > "$body"
  echo "  본문 $(wc -c < "$body" | tr -d ' ') 바이트"
  code="$(curl -s -o "$out" -w '%{http_code}' -b "$jar" -X POST "$API/inventory/calc" -H 'content-type: application/json' --data-binary "@$body")"
  echo "  curl 종료 코드 $? · 응답 본문: $(head -c 300 "$out")"
  expect "3MB 본문 → POST /inventory/calc 의 상태 코드" "$code" 413 &&
    expect "그 본문의 code" "$(jq -r .error.code "$out" 2>/dev/null)" body_too_large &&
    expect "세션 없이 3MB → POST /auth/exchange" "$(curl -s -o "$out" -w '%{http_code}' -X POST "$API/auth/exchange" -H 'content-type: application/json' --data-binary "@$body")" 413
}

container_part() {
  for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "  (포트 $port 는 이미 열려 있다: $(lsof -nP -iTCP:"$port" -sTCP:LISTEN | tail -1 | cut -c1-40))"; fi
  done
  gate
  local started=$SECONDS
  run 'scripts/verify.sh'                                                  # 전량 한 번 = 컨테이너 층 한 번. VERIFY=PASS, 통합 6
  echo "  (전량에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'test ! -e "$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"'
  # 전량은 끝에서 내린다. 떠 있어야 재는 것은 따로 한 번 띄운다(이미지는 전량이 지은 것을 쓴다. 다시 짓지 않는다).
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  gate
  run 'docker compose up -d --wait'
  run 'big_body_through_gunicorn'
  run 'apps/api-py/scripts/planted-breaks-PY8a.sh --containers'            # 심은 파손 11·12
  run 'docker compose down -v'
  run 'test -z "$(docker ps -a --format "{{.Names}}" | grep "^$PROJECT-")"'   # 자기 컨테이너 0
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3; test -z "$(docker images --format "{{.Repository}}" | grep "^$PROJECT/")"'
}

boundary_part() {
  # 허용 경로 밖 0 (기준 $B 와 견준다. 커밋 전에도 뒤에도 같은 답을 낸다: 작업 트리 + 새 파일)
  run 'test -z "$({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E "^(scripts/verify\.sh$|scripts/check-gates\.sh$|scripts/git-hooks/pre-commit$|services/parser/(pyproject\.toml|uv\.lock|app\.py|test_app\.py)$|services/parser/(scripts|tests)/|apps/api-py/esgapi/core/(calc|tests)/|apps/api-py/esgapi/core/(__init__|schemas)\.py$|apps/api-py/esgapi/inventory/|apps/api-py/esgapi/reconcile/calc/dec\.py$|apps/api-py/esgapi/reconcile/tests/test_calc_is_pure\.py$|apps/api-py/esgapi/config/(api\.py$|settings/base\.py$|tests/)|apps/api-py/esgapi/accounts/(api\.py$|tests/)|apps/api-py/esgapi/reference/api\.py$|apps/api-py/generated/|apps/api-py/scripts/(gen-ts-types|section4-PY8a|planted-breaks-PY8a)\.sh$|apps/api-py/(pyproject\.toml|uv\.lock|\.gitignore)$)")"'
  echo
  echo "  (참고) 바뀐 파일 $({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u | wc -l | tr -d ' ') 개, git status --porcelain $(git status --porcelain | wc -l | tr -d ' ') 줄"
}

case "$MODE" in
  --pure) pure_part; boundary_part ;;
  --containers) container_part; boundary_part ;;
  *) pure_part; container_part; boundary_part ;;
esac
