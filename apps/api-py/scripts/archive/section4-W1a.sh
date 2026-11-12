#!/usr/bin/env bash
# 밴드 W1a(MARC-TICK-61, 문서 올리기와 상태 표: 저장소 포트와 boto3 어댑터 · core 의 표 둘과 RLS · 경로 셋)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-W1a.sh                  전체(--pure 뒤에 --containers). 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-W1a.sh --pure           컨테이너 없이 도는 것만(반복해 돌려도 된다)
#         apps/api-py/scripts/section4-W1a.sh --containers     컨테이너 층 한 번(띄우기 → 업무 → 보안 → 통합 → curl 한 줄기 → 심은 파손 10~16 → 내리기 → 이미지 치우기)
#         apps/api-py/scripts/section4-W1a.sh --after-commit   README 대조 둘(코드를 HEAD 의 트리에서 읽으므로 커밋 ③ 뒤에만 뜻이 있다)
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# AI 공급사 호출 0. 저장소의 접근 키는 .env 의 로컬 가짜 값이고 값을 찍지 않는다. 네트워크는 uv·docker 의 설치뿐이다.
# bash 전용이다(${PIPESTATUS[0]}). 임시 파일은 지우지 않는다(mktemp 의 것이라 운영체제가 치운다).
set -u
cd "$(dirname "$0")/../../.."
B=ca9ce87   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-all}"
case "$MODE" in all | --pure | --containers | --after-commit) ;; *) echo "사용: $0 [--pure|--containers|--after-commit]" >&2; exit 2 ;; esac

T="$(mktemp -d)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
test -n "$PROJECT" || { echo ".env 에 COMPOSE_PROJECT_NAME 이 없다" >&2; exit 2; }

run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다: 메모리 free 20% 이상, 1분 부하 12 미만. 30초마다, 최대 10분(그 뒤엔 그냥 돈다).
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

pure_part() {
  local started=$SECONDS
  run 'scripts/verify.sh --fast'                                           # 끝 줄 VERIFY_FAST=PASS
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd apps/api-py && uv run --frozen pytest -q -m "not django_db and not security" esgapi/core esgapi/config)'
  run '(cd apps/api-py && uv run --frozen pytest -q -m "not django_db and not security" | tail -1)'   # 순수 층 전부의 건수(기준 1,167 + 새 건수)
  run '(cd apps/api-py && uv run --frozen lint-imports)'                    # 계약 넷, .importlinter 0줄인 채
  # 0줄로 두기로 한 것
  run 'git diff --quiet "$B" -- apps/api-py/.importlinter apps/api-py/esgapi/config/apps_list.py apps/api-py/esgapi/config/settings apps/api-py/esgapi/config/urls.py apps/api-py/esgapi/core/tenancy apps/api-py/esgapi/core/exceptions.py apps/api-py/esgapi/core/schemas.py apps/api-py/esgapi/core/registry.py apps/api-py/esgapi/core/conf.py apps/api-py/esgapi/core/llm apps/api-py/esgapi/core/ports/llm.py apps/api-py/esgapi/core/ports/parser.py apps/api-py/esgapi/core/adapters/llm.py apps/api-py/esgapi/core/adapters/parser.py apps/api-py/esgapi/core/migrations/0001_llm_call_log.py apps/api-py/esgapi/accounts apps/api-py/esgapi/reconcile apps/api-py/esgapi/inventory apps/api-py/esgapi/reference apps/api-py/esgapi/materiality apps/api-py/esgapi/drafting apps/api-py/esgapi/greenwashing apps/api-py/esgapi/translation apps/api-py/conftest.py apps/api-py/tests/support apps/api-py/tests/security/conftest.py apps/api-py/tests/security/test_owner.py apps/api-py/tests/security/test_rls.py apps/api-py/tests_integration/conftest.py apps/api-py/tests_integration/pytest.ini apps/api-py/tests_integration/test_flow.py apps/api-py/tests_integration/test_parser_flow.py apps/api-py/tests_integration/data apps/web apps/server packages services docker infra scripts .dockerignore'
  # 워커·브로커·내려받기 주소 없음: 낱말이 아니라 들이는 줄과 정의를 본다
  run 'test ! -e apps/api-py/esgapi/reconcile/tasks.py && test -z "$(grep -rnE "^[[:space:]]*(import|from)[[:space:]]+celery|def presign_download|\"celery" apps/api-py/esgapi apps/api-py/pyproject.toml --include="*.py" --include="*.toml")"'
  echo; echo "── 의존성: 더한 것이 그 둘뿐, 고정된 판, 잠금의 새 이름이 여섯, 있던 판이 안 움직임"
  run 'test "$(git diff "$B" -- apps/api-py/pyproject.toml | grep -c "^+ *\"boto\(3\|core\)==1\.43\.101\"")" = 2 && test "$(git diff "$B" -- apps/api-py/pyproject.toml | grep -c "^-[^-]")" = 0'
  run 'git diff --numstat "$B" -- apps/api-py/uv.lock ; test "$(git diff --numstat "$B" -- apps/api-py/uv.lock | cut -f2)" = 0'   # 잠금의 지운 줄 0
  run 'git diff -U0 "$B" -- apps/api-py/uv.lock | sed -n "s/^+name = \"\(.*\)\"$/\1/p" | sort | tr "\n" " " | tee "$T/lock-names.txt" ; echo ; test "$(cat "$T/lock-names.txt")" = "boto3 botocore jmespath python-dateutil s3transfer six "'
  run '(cd apps/api-py && uv run --frozen python -c "import boto3, botocore; assert (boto3.__version__, botocore.__version__) == (\"1.43.101\", \"1.43.101\")")'
  run 'grep -A1 "^name = \"urllib3\"" apps/api-py/uv.lock | tail -1 ; grep -A1 "^name = \"urllib3\"" apps/api-py/uv.lock | grep -q "^version = \"2.8.0\"$"'   # 이미 있던 꾸러미의 판 그대로
  run 'test -z "$(grep -n -i "boto3-stubs\|types-boto3\|botocore-stubs" apps/api-py/pyproject.toml apps/api-py/uv.lock)"'   # 타입 스텁을 들이지 않았다
  echo; echo "── 공유 파일은 추가만"
  run 'git diff --numstat "$B" -- apps/api-py/esgapi/config/api.py ; test "$(git diff --numstat "$B" -- apps/api-py/esgapi/config/api.py | awk "{print (\$1 <= 6 && \$2 <= 2)}")" = 1'
  run 'test "$(git diff "$B" -- apps/api-py/esgapi/core/models.py | grep -c "^-[^-]")" = 0'   # 있는 모델의 줄은 0줄 고침
  run 'test "$(git diff "$B" -- apps/api-py/esgapi/config/env.py | grep -c "^-[^-]")" = 0'    # 설정도 더하기만
  # compose 는 줄 번호로: 기준 트리에서 `api-py:` 107행, `migrate-py:` 147행. 덩어리가 전부 그 사이여야 한다
  run 'git diff -U0 "$B" -- compose.yaml | grep "^@@" ; test -z "$(git diff -U0 "$B" -- compose.yaml | sed -n "s/^@@ -\([0-9]*\).*/\1/p" | awk "\$1 < 107 || \$1 > 145")"'
  run 'test "$(git diff "$B" -- compose.yaml .env.example | grep -c "^-[^-]")" = 0'            # 지운 줄 0
  run 'test -z "$(git diff -U0 "$B" -- README.md | sed -n "s/^@@ -\([0-9]*\).*/\1/p" | awk "\$1 < 1169")"'   # README 는 Python 절(1169행부터) 안에서만
  run 'grep -q "개발 단계에 실제 고객 문서를 올리지 않는다" README.md && grep -q "개발 단계에 실제 고객 문서를 올리지 않는다" .env.example'
  # .env.example 에 새로 든 키는 값이 빈 선택 키 둘뿐이다(필수 키를 새로 만들지 않았다)
  run 'git diff -U0 "$B" -- .env.example | sed -n "s/^+\([A-Z][A-Z0-9_]*\)=\(.*\)$/\1=[\2]/p" | tr "\n" " " | tee "$T/env-keys.txt" ; echo ; test "$(cat "$T/env-keys.txt")" = "UPLOAD_URL_TTL_SECONDS=[] MAX_UPLOAD_BYTES=[] "'
  echo; echo "── 계약"
  run 'test "$(jq -r "[.paths[][] | .operationId] | length" apps/api-py/generated/openapi.json)" = 17 && test "$(jq -r "[.paths[][] | .operationId | select(startswith(\"core_documents_\"))] | length" apps/api-py/generated/openapi.json)" = 3'
  run 'test "$(shasum -a 256 apps/api-py/generated/openapi.json | cut -d" " -f1)" = "$(cat apps/api-py/generated/api.d.ts.source-sha256)"'
  run 'apps/api-py/scripts/check-wheel.sh'                                 # wheel 에 tests 없음
  run 'n="$(cd apps/api-py && uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration --collect-only | grep -c "::test_")"; echo "  통합 테스트 $n 건이 모인다(돌리지는 않는다)"; test "$n" = 9'   # 7 + 새 2
  echo; echo "── 심은 파손 (순수 열)"
  git status --porcelain > "$T/before.txt"
  run 'apps/api-py/scripts/planted-breaks-W1a.sh --pure'                    # PLANTED=10/10
  run 'git status --porcelain | diff - "$T/before.txt"'                     # 스크립트 밖에서 따로 잰다: 작업 트리 그대로
}

# 손으로 따라가는 길(README 의 「문서 올리기와 상태 표」)을 curl 로 한 번. 테넌트 하나를 주인 역할로 등록하고 끝에서 지운다.
curl_walk() {
  local api="http://localhost:$(env_value API_PY_PORT)" db owner tenant="w1a-curl" jar="$T/cookies.txt" pdf=apps/api-py/tests_integration/data/ruled-table.pdf
  db="$(env_value POSTGRES_DB)_py"; owner="$(env_value POSTGRES_OWNER_USER)"
  psql() { docker compose exec -T postgres psql -U "$owner" -d "$db" -v ON_ERROR_STOP=1 -qAt -c "$1"; }
  psql "INSERT INTO tenants (id, name, created_at) VALUES ('$tenant', 'curl 한 줄기', now())" || return 1
  local token size doc url code status jobs rc=0
  token="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py token --tenant "$tenant" --sub w1a-curl-user --role editor --name 손으로)"
  size="$(wc -c < "$pdf" | tr -d ' ')"
  code="$(curl -s -o /dev/null -w '%{http_code}' -c "$jar" -X POST "$api/auth/exchange" -H 'content-type: application/json' -d "{\"token\":\"$token\"}")"
  echo "  교환 $code"; [ "$code" = 200 ] || rc=1
  code="$(curl -s -o "$T/doc.json" -w '%{http_code}' -b "$jar" -X POST "$api/documents" -H 'content-type: application/json' -d "{\"fileName\": \"ruled-table.pdf\", \"sizeBytes\": $size}")"
  echo "  만들기 $code (sizeBytes $size)"; [ "$code" = 201 ] || rc=1
  doc="$(jq -r .document.id "$T/doc.json")"; url="$(jq -r .upload.url "$T/doc.json")"
  echo "  올리기 주소의 호스트: $(printf '%s' "$url" | sed -E 's#^(https?://[^/]+)/.*#\1#')"
  code="$(curl -s -o /dev/null -w '%{http_code}' -X PUT --data-binary @"$pdf" "$url")"
  echo "  저장소에 PUT $code"; [ "$code" = 200 ] || rc=1
  code="$(curl -s -o "$T/confirm.json" -w '%{http_code}' -b "$jar" -X POST "$api/documents/$doc/confirm")"
  status="$(jq -r .document.status "$T/confirm.json")"; jobs="$(jq -c '[.jobs[] | [.kind, .status]]' "$T/confirm.json")"
  echo "  올림 확인 $code · 문서 $status · 일감 $jobs"; [ "$code" = 200 ] && [ "$status" = uploaded ] && [ "$jobs" = '[["parse","queued"]]' ] || rc=1
  code="$(curl -s -o "$T/get.json" -w '%{http_code}' -b "$jar" "$api/documents/$doc")"
  echo "  상태 보기 $code"; [ "$code" = 200 ] && diff <(jq -S . "$T/confirm.json") <(jq -S . "$T/get.json") > /dev/null || rc=1
  psql "DELETE FROM core_jobs WHERE tenant_id = '$tenant'; DELETE FROM core_documents WHERE tenant_id = '$tenant'; DELETE FROM users WHERE tenant_id = '$tenant'; DELETE FROM tenants WHERE id = '$tenant'" || rc=1
  return "$rc"
}

# 한 층을 돌리고 EXIT 를 찍는다. 빨가면 원문과 부하를 남기고 **그 층만** 한 번 더(이미지를 다시 짓지 않는다).
layer() { # <이름> <명령…>
  local name="$1" code
  shift
  local started=$SECONDS
  echo; echo "▶ $*"
  "$@"; code=$?
  echo "EXIT=$code"
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  if [ "$code" -ne 0 ]; then
    uptime; memory_pressure | grep percentage
    [ "$name" = "통합 층" ] && docker compose logs --no-color --tail 60 api-py storage
    echo; echo "▶ $* (한 번 더)"
    "$@"; echo "EXIT=$?"
  fi
}

containers_part() {
  echo; echo "── 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  run 'test ! -e "$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"'   # 감독의 전량이 도는 중이 아니다
  local port
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다. 띄우지 않는다"; echo "EXIT=1"; return 1; fi
  done
  echo "  (포트 넷이 비어 있다)"
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  gate
  local started=$SECONDS
  # api-py 가 postgres·migrate-py·storage 를 끌고 뜬다. parser 는 있던 통합 1건이 쓴다. TS 의 api·worker·redis 는 띄우지 않는다.
  run 'docker compose up -d --build --wait api-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo'
  # 저장소 키 아홉이 컨테이너에 있다(값은 찍지 않는다)
  run 'test "$(docker compose exec -T api-py env | grep -c -E "^(S3_BUCKET|S3_REGION|S3_ENDPOINT|S3_PUBLIC_ENDPOINT|S3_FORCE_PATH_STYLE|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|UPLOAD_URL_TTL_SECONDS|MAX_UPLOAD_BYTES)=")" = 9'
  layer "업무 층" apps/api-py/scripts/test-business.sh -n 2               # 기준 207 + 새 건수
  layer "보안 층" apps/api-py/scripts/test-security.sh                    # 기준 37 + 새 건수
  layer "통합 층" apps/api-py/scripts/test-integration.sh                 # 기준 7 + 새 2
  run 'curl_walk'                                                          # README 의 한 줄기를 curl 로
  git status --porcelain > "$T/before-c.txt"
  run 'apps/api-py/scripts/planted-breaks-W1a.sh --containers'             # PLANTED=7/7
  run 'git status --porcelain | diff - "$T/before-c.txt"'
  run 'docker compose down -v 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'test -z "$(docker ps -a --format "{{.Names}}" | grep "^$PROJECT-")"'              # 자기 컨테이너 0
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; test -z "$(docker images --format "{{.Repository}}" | grep "^$PROJECT/")"'
}

boundary_part() {
  # 허용 경로 밖 0 (기준 $B 와 견준다. 커밋 전에도 뒤에도 같은 답을 낸다: 작업 트리 + 새 파일)
  run 'test -z "$({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E "^(apps/api-py/esgapi/core/(calc/documents\.py|ports/storage\.py|adapters/storage\.py|models\.py|__init__\.py|api\.py)$|apps/api-py/esgapi/core/migrations/000[2-9]_[a-z0-9_]+\.py$|apps/api-py/esgapi/core/documents/|apps/api-py/esgapi/core/tests/test_(documents|storage)_[a-z0-9_]+\.py$|apps/api-py/esgapi/config/(api|env)\.py$|apps/api-py/esgapi/config/tests/test_(api_contract|env|request_schemas_reject_bool)\.py$|apps/api-py/tests/security/test_documents\.py$|apps/api-py/tests_integration/test_upload_flow\.py$|apps/api-py/generated/|apps/api-py/scripts/(section4|planted-breaks)-W1a\.sh$|apps/api-py/(pyproject\.toml|uv\.lock)$|compose\.yaml$|\.env\.example$|README\.md$)")"'
  echo
  echo "── 바뀐 파일 (기준 $B 대비, 새 파일 포함)"
  { git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u
}

after_commit_part() {
  echo; echo "── 커밋 뒤: README 의 Python 절과 HEAD 의 코드"
  run '(cd apps/api-py && uv run --frozen python scripts/readme_audit.py paths --rev HEAD | tail -1 ; test "${PIPESTATUS[0]}" = 0)'
  run '(cd apps/api-py && uv run --frozen python scripts/readme_audit.py forward --rev HEAD | tail -1 ; test "${PIPESTATUS[0]}" = 0)'
}

case "$MODE" in
  --pure) pure_part; boundary_part ;;
  --containers) containers_part; boundary_part ;;
  --after-commit) after_commit_part; boundary_part ;;
  all) pure_part; containers_part; boundary_part ;;
esac
