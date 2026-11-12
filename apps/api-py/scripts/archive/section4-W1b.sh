#!/usr/bin/env bash
# 밴드 W1b(MARC-TICK-62, Celery 워커: 앱 정의 · 워커 서비스 · 파서 태스크 · 테넌트 도우미 · 표의 임대로 중복 막기 · 커밋 뒤 큐 넣기)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-W1b.sh                  전체(--pure 뒤에 --containers). 줄마다 EXIT=<종료 코드>
#         apps/api-py/scripts/section4-W1b.sh --pure           컨테이너 없이 도는 것만(반복해 돌려도 된다)
#         apps/api-py/scripts/section4-W1b.sh --containers     컨테이너 층 한 번(띄우기 → 워커·큐의 단언 → 업무 → 보안 → 통합 → 심은 파손 10~19 → 내리기 → 이미지 치우기)
#         apps/api-py/scripts/section4-W1b.sh --after-commit   README 대조 둘(코드를 HEAD 의 트리에서 읽으므로 커밋 ④ 뒤에만 뜻이 있다)
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다
#   (바탕 이미지 softwaremill/elasticmq-native 는 지우지 않는다).
# AI 공급사 호출 0. ★ AWS 로 나가는 호출 0: 브로커는 compose 의 queue(SQS 흉내)뿐이고, 호스트 없는 sqs:// 로
#   Celery 를 돌리는 줄이 이 스크립트에 없다. 네트워크는 uv·docker 의 설치뿐이다.
# bash 전용이다(${PIPESTATUS[0]}). 임시 파일은 지우지 않는다(mktemp 의 것이라 운영체제가 치운다).
set -u
cd "$(dirname "$0")/../../.."
B=08051a1   # 기준 커밋(발주서 §1-1)
N=7         # pyproject.toml 에 직접 고정한 줄 수
NAMES='amqp billiard celery click-didyoumean click-plugins click-repl kombu prompt-toolkit pycurl tzlocal vine wcwidth '   # 잠금의 새 이름 열둘(끝 빈칸까지)
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
  run '(cd apps/api-py && uv run --frozen pytest -q -m "not django_db and not security" | tail -1)'   # 순수 층 전부의 건수
  run '(cd apps/api-py && uv run --frozen lint-imports)'                    # 계약 넷
  run 'git diff --numstat "$B" -- apps/api-py/.importlinter ; test "$(git diff --numstat "$B" -- apps/api-py/.importlinter | awk "{print (\$1 <= 4 && \$2 <= 3)}")" = 1 && grep -q "^    esgapi\.\*\.tasks$" apps/api-py/.importlinter'
  # 0줄로 두기로 한 것
  run 'git diff --quiet "$B" -- apps/api-py/generated apps/api-py/esgapi/config/__init__.py apps/api-py/esgapi/config/api.py apps/api-py/esgapi/config/apps_list.py apps/api-py/esgapi/config/settings apps/api-py/esgapi/core/api.py apps/api-py/esgapi/core/models.py apps/api-py/esgapi/core/migrations apps/api-py/esgapi/core/ports apps/api-py/esgapi/core/adapters apps/api-py/esgapi/core/calc/documents.py apps/api-py/esgapi/core/documents/services.py apps/api-py/esgapi/core/documents/selectors.py apps/api-py/esgapi/core/documents/schemas.py apps/api-py/esgapi/core/tenancy/db.py apps/api-py/esgapi/core/tenancy/middleware.py apps/api-py/esgapi/core/tenancy/rls.py apps/api-py/esgapi/reconcile/services apps/api-py/esgapi/reconcile/api.py apps/api-py/esgapi/accounts apps/api-py/esgapi/inventory apps/api-py/esgapi/reference apps/api-py/conftest.py apps/api-py/tests/support apps/api-py/tests/security/conftest.py apps/api-py/tests/security/test_documents.py apps/api-py/tests/security/test_owner.py apps/api-py/tests_integration/conftest.py apps/api-py/tests_integration/test_flow.py apps/api-py/tests_integration/test_parser_flow.py apps/api-py/gunicorn.conf.py docker/api-py.Dockerfile scripts apps/web apps/server packages services infra'
  run 'test "$(jq -r "[.paths[][] | .operationId] | length" apps/api-py/generated/openapi.json)" = 17'          # 새 경로 0
  run 'test -z "$({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | grep "/migrations/")"'   # 새·고친 마이그레이션 0
  echo; echo "── 의존성: 직접 고정한 일곱 줄, 잠금의 새 이름 열둘, 있던 판이 안 움직임"
  run 'test "$(git diff "$B" -- apps/api-py/pyproject.toml | grep -c -E "^\+ *\"(celery==5\.6\.3|kombu==5\.6\.2|billiard==4\.2\.4|amqp==5\.3\.1|click-repl==0\.3\.0|wcwidth==0\.8\.5|pycurl==7\.48\.0)\"")" = "$N" && test "$(git diff "$B" -- apps/api-py/pyproject.toml | grep -c "^-[^-]")" = 0'
  run 'git diff --numstat "$B" -- apps/api-py/uv.lock ; test "$(git diff --numstat "$B" -- apps/api-py/uv.lock | cut -f2)" = 0'   # 잠금의 지운 줄 0
  run 'git diff -U0 "$B" -- apps/api-py/uv.lock | sed -n "s/^+name = \"\(.*\)\"$/\1/p" | sort | tr "\n" " " > "$T/lock-names.txt" ; cat "$T/lock-names.txt"; echo ; test "$(cat "$T/lock-names.txt")" = "$NAMES"'
  run '(cd apps/api-py && uv run --frozen python -W error -c "import celery, kombu, billiard, amqp, pycurl; assert (celery.__version__, kombu.__version__, billiard.__version__, amqp.__version__) == (\"5.6.3\", \"5.6.2\", \"4.2.4\", \"5.3.1\") and pycurl.version.startswith(\"PycURL/7.48.0\")")'
  run 'test -z "$(grep -n -i "celery-types\|celery\[sqs\]\"" apps/api-py/pyproject.toml apps/api-py/uv.lock | grep -v "^apps/api-py/pyproject.toml:[0-9]*: *#")"'   # 타입 스텁·덧붙임을 들이지 않았다
  echo; echo "── 브로커 주소: compose 의 값이 호스트를 가진 글자이고, 호스트 없는 sqs:// 를 값으로 주는 줄이 없다"
  # 둘째 줄은 약하다: `KEY=sqs://`·`KEY: sqs://` 로 끝나는 줄만 잡는다(파이썬 dict 의 꼴은 못 잡는다. 그쪽은 순수 층의 소켓 막기가 지킨다).
  run 'grep -q "^      CELERY_BROKER_URL: sqs://queue:9324$" compose.yaml && grep -q "^      CELERY_QUEUE_URL: http://queue:9324/000000000000/esg-jobs$" compose.yaml && grep -q "^      CELERY_BROKER_SECURE: \"false\"$" compose.yaml'
  run 'test -z "$(grep -rnE "CELERY_BROKER_URL[=:] *\"?sqs://\"?[[:space:]]*$" compose.yaml .env.example apps/api-py --include="*.yaml" --include="*.example" --include="*.sh" --include="*.py" --include="*.ini" --include="*.toml" --exclude-dir=.venv)"'
  echo; echo "── 공유 파일: compose 는 api-py 덩어리 안의 고침과 정해 둔 두 자리의 추가뿐"
  run 'git diff -U0 "$B" -- compose.yaml | grep "^@@" ; test -z "$(git diff -U0 "$B" -- compose.yaml | sed -n "s/^@@ -\([0-9]*\)\(,\([0-9]*\)\)\{0,1\} .*/\1 \3/p" | awk "{n = (\$2 == \"\" ? 1 : \$2); inside = (\$1 >= 107 && \$1 <= 159)} (n > 0 && !inside) || (n == 0 && !(inside || \$1 == 171 || \$1 == 172 || \$1 == 228 || \$1 == 229))")" && test "$(git diff "$B" -- compose.yaml | grep -c "^-[^-]")" -le 3'
  run 'test "$(git diff "$B" -- .env.example | grep -c "^-[^-]")" = 0 && test -z "$(git diff "$B" -- .env.example | grep -E "^\+[A-Z_]+=.+")"'   # 새 키는 빈 값뿐(필수 키 0)
  run 'test "$(git diff "$B" -- apps/api-py/esgapi/config/env.py | grep -c "^-[^-]")" = 0'    # 설정은 더하기만
  run '(cd apps/api-py && uv run --frozen python - <<"PY"
import pathlib, re
text = pathlib.Path("../../compose.yaml").read_text()
block = re.search(r"\n  worker-py:\n(.*?)(?=\n  [a-z-]+:\n|\nvolumes:)", text, re.S).group(1)
assert "*api-py-env" in block and "DATABASE_URL_PY_OWNER" not in block and "ports:" not in block and "celery" in block
PY
)'
  run 'test -z "$(git diff -U0 "$B" -- README.md | sed -n "s/^@@ -\([0-9]*\).*/\1/p" | awk "\$1 < 1169")"'   # README 는 Python 절(1169행부터) 안에서만
  # 있던 통합 테스트(test_upload_flow.py)에는 고정물과 머리말뿐: 단언 줄을 더하지도 지우지도 않았다
  run 'test -z "$(git diff "$B" -- apps/api-py/tests_integration/test_upload_flow.py | grep -E "^[-+][^-+].*\bassert\b")"'
  run 'apps/api-py/scripts/check-wheel.sh'                                 # wheel 에 tests 없음
  run 'n="$(cd apps/api-py && uv run --frozen pytest -q -c tests_integration/pytest.ini tests_integration --collect-only | grep -c "::test_")"; echo "  통합 테스트 $n 건이 모인다(돌리지는 않는다)"; test "$n" -ge 14'   # 9 + 새 다섯
  echo; echo "── 심은 파손 (순수 열)"
  git status --porcelain > "$T/before.txt"
  run 'apps/api-py/scripts/planted-breaks-W1b.sh --pure'                    # PLANTED=9/9
  run 'git status --porcelain | diff - "$T/before.txt"'                     # 스크립트 밖에서 따로 잰다: 작업 트리 그대로
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
    [ "$name" = "통합 층" ] && docker compose logs --no-color --tail 80 worker-py queue api-py parser
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
  # api-py·worker-py 가 postgres·migrate-py·storage·queue 를 끌고 뜬다. TS 의 api·worker·redis 는 띄우지 않는다.
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6 && test -z "$(docker compose ps --format "{{.Service}}" | grep -E "^(api|worker|redis)$")"'
  echo; echo "── 워커: 앱 역할의 주소뿐, 같은 이미지·다른 명령, 끝점이 로컬 흉내"
  run 'test "$(docker compose exec -T worker-py env | grep -c "^DATABASE_URL_PY=")" = 1 && test "$(docker compose exec -T worker-py env | grep -c "OWNER")" = 0'
  run 'docker inspect --format "{{.Image}} {{.Path}} {{index .Args 0}}" $(docker compose ps -q api-py worker-py) | sed "s/^sha256:\(.\{12\}\)[0-9a-f]*/\1…/" ; test "$(docker inspect --format "{{.Image}}" $(docker compose ps -q api-py worker-py) | sort -u | wc -l | tr -d " ")" = 1 && test "$(docker inspect --format "{{.Path}}" $(docker compose ps -q api-py worker-py) | sort -u | wc -l | tr -d " ")" = 2'
  run 'docker compose exec -T worker-py python -c "from urllib.parse import urlsplit; from esgapi.config.celery import app; c = app.conf; assert c.task_ignore_result and c.task_acks_late and c.worker_prefetch_multiplier == 1; assert c.result_backend is None and c.get(\"CELERY_DB_REUSE_MAX\") is None; assert urlsplit(c.broker_url).hostname == \"queue\" and \"amazonaws\" not in str(c.broker_transport_options)"'
  run 'docker compose exec -T api-py python -c "from urllib.parse import urlsplit; from esgapi.config.celery import app; assert urlsplit(app.conf.broker_url).hostname == \"queue\""'
  run 'docker compose logs --no-color worker-py | grep -E "jobs\.parse|ready\.|Connected to" | head -5 ; docker compose logs --no-color worker-py | grep -q "jobs.parse" && test -z "$(docker compose logs --no-color worker-py queue api-py | grep -i "amazonaws")"'   # 태스크가 등록됐고, 기록 어디에도 AWS 의 주소가 없다
  # 브로커 설정 없이 띄운 워커는 이름 있는 오류로 끝난다(SystemExit). 브로커를 **비워서** 본다(호스트 없는 sqs:// 가 아니다).
  run 'docker compose run --rm --no-deps -T -e CELERY_BROKER_URL= worker-py > "$T/no-broker.txt" 2>&1; code=$?; tail -3 "$T/no-broker.txt"; echo "  (브로커 없이 띄운 워커의 종료 코드 $code)"; test "$code" != 0 && grep -q "CELERY_BROKER_URL 이 없다" "$T/no-broker.txt"'
  layer "업무 층" apps/api-py/scripts/test-business.sh -n 2
  layer "보안 층" apps/api-py/scripts/test-security.sh
  layer "통합 층" apps/api-py/scripts/test-integration.sh -s
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'   # 통합이 멈추고 죽인 것을 다 되돌렸다
  run 'test -z "$(docker compose logs --no-color worker-py queue api-py | grep -i "amazonaws")"'
  git status --porcelain > "$T/before-c.txt"
  run 'apps/api-py/scripts/planted-breaks-W1b.sh --containers'             # PLANTED=10/10
  run 'git status --porcelain | diff - "$T/before-c.txt"'
  run 'git diff --quiet "$B" -- apps/api-py/esgapi/core/documents/services.py'   # 15·16 을 심었던 파일이 0줄로 돌아왔다
  run 'docker compose down -v 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'test -z "$(docker ps -a --format "{{.Names}}" | grep "^$PROJECT-")"'              # 자기 컨테이너 0
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; test -z "$(docker images --format "{{.Repository}}" | grep "^$PROJECT/")"'
}

boundary_part() {
  # 허용 경로 밖 0 (기준 $B 와 견준다. 커밋 전에도 뒤에도 같은 답을 낸다: 작업 트리 + 새 파일)
  run 'test -z "$({ git diff --name-only "$B"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E "^(apps/api-py/esgapi/config/(celery|env)\.py$|apps/api-py/esgapi/config/tests/test_env\.py$|apps/api-py/esgapi/core/(calc/jobs|tenancy/tasks|documents/(jobs|hooks|__init__)|__init__|management/commands/requeue_jobs)\.py$|apps/api-py/esgapi/core/tests/test_(jobs|celery)_[a-z0-9_]+\.py$|apps/api-py/esgapi/core/tests/test_documents_(services|models|api)\.py$|apps/api-py/esgapi/reconcile/(tasks|calc/job_summary)\.py$|apps/api-py/esgapi/reconcile/tests/test_(tasks_[a-z0-9_]+|job_summary)\.py$|apps/api-py/tests/security/test_(jobs|documents_race)\.py$|apps/api-py/tests_integration/test_(worker|upload)_flow\.py$|apps/api-py/scripts/(section4|planted-breaks)-W1b\.sh$|apps/api-py/(pyproject\.toml|uv\.lock|\.importlinter)$|docker/elasticmq\.conf$|compose\.yaml$|\.env\.example$|README\.md$)")"'
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
