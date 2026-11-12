#!/usr/bin/env bash
# 밴드 PY3b(MARC-TICK-57, 호출 기록의 DB 싱크)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-PY3b.sh            전체(컨테이너를 띄우고 내린다). 줄마다 EXIT=<종료 코드>. 전부 0 이어야 한다
#         apps/api-py/scripts/section4-PY3b.sh planted    심은 파손 여덟(Postgres 만 띄우고 내린다). 마지막 줄 PLANTED=8/8 이어야 한다
# 다루는 컨테이너·볼륨은 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# AI 공급사는 부르지 않는다(모의 공급사뿐. 키를 읽지 않는다).
set -u
cd "$(dirname "$0")/../../.."
BASE=6aaa84e
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 가 Node 22 를 쓴다

env_value() { sed -n "s/^$1=//p" .env | tail -1; }
OWNER="$(env_value POSTGRES_OWNER_USER)"
DB="$(env_value POSTGRES_DB)_py"

PURE='not django_db and not security'
# 순수 층이 모은 테스트 수와, 소켓 막는 고정물(blocked_network)이 세워지는 테스트 수.
# ★ 무효 조건: --setup-plan 은 고정물의 몸통을 돌리지 않는다. 「세워짐」만 잰다(몸통의 건너뛰는 조건이 틀려도 같은 수다).
#   실제로 막는지는 test_llm_layers.py::test_socket_connections_are_blocked_in_these_tests 와 gemini 의 문지기가 잰다.
collected() { (cd apps/api-py && uv run --frozen pytest -m "$PURE" --collect-only -q | grep -c '::'); }
blocked() { (cd apps/api-py && uv run --frozen pytest -m "$PURE" --setup-plan | grep -c 'SETUP    F blocked_network'); }

# ════════════════════════════════════════════════════════════════════
if [ "${1:-}" = "planted" ]; then
  # 심은 파손: 규칙을 하나씩 망가뜨리고, 그것을 잡아야 할 테스트가 빨개지는지 본다.
  # 심기 전의 파일을 임시 폴더에 베껴 두었다가 되돌린다(git 을 쓰지 않는다). 끝나면 파일이 처음과 같아야 한다.
  SINK=apps/api-py/esgapi/core/llm/sink_db.py
  MIGRATION=apps/api-py/esgapi/core/migrations/0001_llm_call_log.py
  ROOT_CONFTEST=apps/api-py/conftest.py
  CORE_CONFTEST=apps/api-py/esgapi/core/tests/conftest.py
  FILES="$SINK $MIGRATION $ROOT_CONFTEST $CORE_CONFTEST"
  backup="$(mktemp -d)"
  log="$(mktemp)"
  before="$(shasum -a 256 $FILES)"
  touched=""
  restore() {
    local file
    for file in $touched; do cp "$backup/$(printf '%s' "$file" | tr / _)" "$file"; done
    touched=""
  }
  trap 'restore; rm -rf "$backup" "$log"; docker compose down -v >/dev/null 2>&1' EXIT

  plant() { # <파일> <바꿀 글> <바꾼 글>   글이 정확히 한 번 있어야 한다
    case " $touched " in *" $1 "*) ;; *) cp "$1" "$backup/$(printf '%s' "$1" | tr / _)"; touched="$touched $1" ;; esac
    python3 - "$1" "$2" "$3" <<'PY'
import sys
path, old, new = sys.argv[1:4]
text = open(path, encoding="utf-8").read()
if text.count(old) != 1:
    sys.exit(f"★ 심지 못함: {path} 에 바꿀 글이 {text.count(old)}번 있다")
open(path, "w", encoding="utf-8").write(text.replace(old, new))
PY
  }

  # 업무 층은 이 밴드의 테스트 파일만, 보안 층은 전부(test_owner.py 의 카탈로그 검사가 새 표를 무는지까지).
  # --create-db: 마이그레이션을 망가뜨린 것(3·4)이 업무 층의 테스트 DB 에도 들어가게 매번 새로 만든다.
  business() { apps/api-py/scripts/test-business.sh -p no:cacheprovider --create-db esgapi/core/tests/test_llm_sink_db.py; }
  security() { apps/api-py/scripts/test-security.sh -p no:cacheprovider; }
  reds() { sed -nE 's/^(FAILED|ERROR) ([^ ]*).*/\2/p' "$log" | sed 's/\[.*//' | sort -u; }

  total=0; caught=0
  verdict() { # <설명> <빨개져야 하는 테스트 이름(::뒤)…>   $log 에 방금 돌린 출력이 있다
    local title="$1"; shift
    total=$((total + 1))
    local names; names="$(reds)"
    local missing="" want
    for want in "$@"; do
      printf '%s\n' "$names" | grep -q -- "::$want\$" || missing="$missing $want"
    done
    echo
    echo "▶ $title"
    echo "  기대: $*"
    if [ -z "$missing" ] && [ "$#" -gt 0 ]; then caught=$((caught + 1)); echo "  잡힘  (빨개진 테스트 $(printf '%s' "$names" | grep -c . || true)개)"
    else echo "  ★ 안 잡힘 — 빨개지지 않은 것:$missing"; fi
    printf '%s\n' "$names" | sed '/^$/d; s/^/    /'
    grep -E '^[0-9]+ (passed|failed)|^=+ .*(passed|failed|error)' "$log" | sed 's/^/    · /'
    restore
  }
  both() { { business; security; } >"$log" 2>&1; }

  docker compose up -d --wait postgres >/dev/null 2>&1 || { echo "★ Postgres 가 뜨지 않았다"; exit 1; }

  # 0. 심지 않음: 두 층이 다 초록이어야 아래의 「빨개졌다」가 뜻이 있다.
  both
  echo "▶ 0. 심지 않음"
  grep -E '^[0-9]+ (passed|failed)' "$log" | sed 's/^/    · /'
  if [ -z "$(reds)" ] && [ "$(grep -cE '^[0-9]+ passed' "$log")" = 2 ]; then echo "BASELINE_CLEAN=yes"; else echo "BASELINE_CLEAN=no"; reds; fi

  plant "$SINK" "            with transaction.atomic():
                session = session_tenant()" "            if True:
                session = session_tenant()"
  both
  verdict "1. record 의 세이브포인트(안쪽 atomic)를 뺀다" \
    test_a_failed_log_insert_does_not_take_the_request_down_with_it \
    test_a_rejected_insert_is_reported_and_the_next_record_is_still_written

  plant "$SINK" "rows = LlmCallLogRow.objects.filter(tenant_id=scope.tenant)" "rows = LlmCallLogRow.objects.all()"
  both
  verdict "2. spent 의 tenant_id WHERE 를 뺀다 (보안 층은 RLS 가 가려 초록일 수 있다: 아래 목록에 보안 층의 이름이 있는지 본다)" \
    test_the_tenant_sum_reads_only_that_tenant_and_that_module_from_the_table

  plant "$MIGRATION" "        *isolate(TABLE),
" ""
  both
  verdict "3. 마이그레이션에서 isolate 를 뺀다" \
    test_every_tenant_table_has_rls_enabled_and_forced \
    test_policy_text_compares_the_transaction_setting \
    test_a_line_is_seen_only_inside_its_own_tenant

  plant "$MIGRATION" '"SELECT, INSERT"),' '"SELECT, INSERT, UPDATE, DELETE"),'
  both
  verdict "4. grant 에 UPDATE, DELETE 를 더한다" \
    test_app_role_may_only_read_and_append \
    test_app_role_cannot_change_or_remove_a_log_line \
    test_app_role_reads_every_tenant_table_and_deletes_none

  plant "$SINK" "row_from_record(record, tenant_id=session).save(force_insert=True)" \
    "row_from_record(record, tenant_id=record.tenant).save(force_insert=True)"
  both
  verdict "5. 행의 tenant_id 를 세션이 아니라 꼬리표로 쓴다" \
    test_a_wrong_tag_is_stored_under_the_session_tenant \
    test_a_wrong_tag_is_written_under_the_session_tenant_and_reported

  plant "$SINK" "            if record.cost_usd is not None:" \
    "            if record.cost_usd is not None and not isinstance(outcome, NoTenant | WriteFailed):"
  both
  verdict "6. 쓰지 못한 줄(NoTenant·WriteFailed)을 메모리 누계에 넣지 않는다 (보안 층의 롤백 테스트는 초록 그대로여야 한다)" \
    test_unwritten_lines_still_count_towards_spent
  # 6 이 7 과 갈리는가: 보안 층의 롤백 테스트는 6 에서 빨개지지 않는다.

  plant "$SINK" "            if record.cost_usd is not None:" \
    "            if record.cost_usd is not None and not isinstance(outcome, Written):"
  both
  verdict "7. 쓰인 줄(Written)을 메모리 누계에 넣지 않는다" \
    test_a_rolled_back_request_loses_its_log_line_but_the_object_remembers_the_cost

  # 8. 뿌리 고정물을 끈다. ★ 고정물을 끈 채로는 지목한 테스트 둘만 돌린다. 순수 층 전체를 돌리지 않는다
  #    (PY3 의 사고: 고정물이 꺼진 채 진짜 SDK 클라이언트가 불려 가상 키의 요청이 나갔다. 둘째 테스트의 문지기가 그것을 막는다).
  plant "$ROOT_CONFTEST" \
    'if node.get_closest_marker("django_db") is not None or node.get_closest_marker("security") is not None:' \
    'if True:'
  (cd apps/api-py && uv run --frozen pytest -q -p no:cacheprovider \
    "esgapi/core/tests/test_llm_layers.py::test_socket_connections_are_blocked_in_these_tests" \
    "esgapi/core/tests/test_llm_gemini.py::test_sdk_client_uses_the_given_key_and_real_client_is_stopped_at_the_socket") >"$log" 2>&1
  verdict "8. 뿌리 conftest 의 소켓 고정물을 끈다 (지목한 둘만 돌렸다)" \
    test_socket_connections_are_blocked_in_these_tests \
    test_sdk_client_uses_the_given_key_and_real_client_is_stopped_at_the_socket

  # 8-나. 고정물의 범위를 core/tests 로 되돌린다(뿌리에서는 autouse 를 끄고, core/tests 에서만 autouse 로 다시 건다).
  #       고정물은 core/tests 에서 켜진 채다. 테스트의 몸통은 돌리지 않는다(모으기와 --setup-plan 뿐).
  #       §4 의 「걸린 수 = 모은 수」 줄이 0 이 아니어야 한다. PLANTED 의 분모에는 넣지 않는다(8 의 곁가지).
  plant "$ROOT_CONFTEST" "@pytest.fixture(autouse=True)
def blocked_network(" "@pytest.fixture
def blocked_network("
  plant "$CORE_CONFTEST" "@pytest.fixture
def prompt_root(" "@pytest.fixture(autouse=True)
def _core_only_block(blocked_network: list[object]) -> None:
    pass


@pytest.fixture
def prompt_root("
  got_collected="$(collected)"; got_blocked="$(blocked)"
  test "$got_collected" = "$got_blocked"; scope_exit=$?
  restore
  echo
  echo "▶ 8-나. 고정물의 범위를 core/tests 로 되돌린다"
  echo "  모은 수 $got_collected, 걸린 수 $got_blocked → 「걸린 수 = 모은 수」 줄의 EXIT=$scope_exit (0 이 아니어야 한다)"
  echo "SCOPE_LINE_CATCHES=$([ "$scope_exit" != 0 ] && [ "$got_blocked" -gt 0 ] && echo yes || echo no)"

  echo
  echo "PLANTED=$caught/$total"
  echo "TREE_SAME_AFTER_RESTORE=$([ "$before" = "$(shasum -a 256 $FILES)" ] && echo yes || echo no)"
  exit 0
fi

# ════════════════════════════════════════════════════════════════════
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}
sql() { docker compose exec -T postgres psql -U "$OWNER" -d "$DB" -At -c "$1"; }

echo "── 포트가 다른 워크트리와 겹치지 않는가 (.env)"
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; fi
done
echo "── 부하"; uptime; memory_pressure 2>/dev/null | grep percentage

# ── 컨테이너 없이 도는 것 ──
run 'cd apps/api-py && uv sync --frozen'
run 'cd apps/api-py && uv run ruff check . && uv run ruff format --check .'
run 'cd apps/api-py && uv run pyright'
run 'cd apps/api-py && uv run lint-imports'
run 'cd apps/api-py && uv run lint-imports --config esgapi/core/llm/purity.importlinter'
run "cd apps/api-py && uv run pytest -q -m '$PURE'"     # 순수 층

# 걸린 수 = 모은 수 (머리의 무효 조건). 두 수를 찍는다.
echo
echo "▶ 소켓 막는 고정물: 걸린 수 = 모은 수 (순수 층)"
COLLECTED="$(collected)"; BLOCKED="$(blocked)"
echo "  모은 수 $COLLECTED / 걸린 수 $BLOCKED"
test "$COLLECTED" = "$BLOCKED" && test "$COLLECTED" -gt 0
echo "EXIT=$?"

# 통합 테스트는 뿌리 conftest 를 읽지 않는다(그래서 고정물의 조건에 tests_integration 을 넣지 않았다). 0 이어야 한다.
echo
echo "▶ 통합 테스트의 고정물 목록에 뿌리 conftest 의 tenants 가 없다"
INTEGRATION_SEES_ROOT="$(cd apps/api-py && uv run --frozen pytest -c tests_integration/pytest.ini tests_integration --fixtures -q 2>/dev/null | grep -c '^tenants')"
echo "  grep -c '^tenants' = $INTEGRATION_SEES_ROOT"
test "$INTEGRATION_SEES_ROOT" = 0
echo "EXIT=$?"

# 통합 테스트가 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다). section4-PY3.sh 와 같다.
EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
export EDK_JWT_PUBLIC_KEY

# ── 컨테이너가 있어야 도는 것 ──
run 'docker compose up -d --build --wait'
run 'apps/api-py/scripts/test-business.sh -n 2 --create-db'   # --create-db: 앞선 실행이 --reuse-db 로 남긴 옛 꼴의 DB 를 쓰지 않는다
run 'apps/api-py/scripts/test-security.sh'
run 'apps/api-py/scripts/test-integration.sh'

# 관리 명령을 **컨테이너 안에서**, 앱 역할로 돌린다: 이미지에 마이그레이션이 실렸고 migrate-py 가 표를 만들었는지까지 잰다.
CALL="docker compose exec -T -e LLM_LOG_SINK=db api-py python manage.py llm_call --prompt core/hello@1 --var name=x --route mock --mock-text '{\"ok\":true}'"
run "$CALL --tenant tenant-s4 --module s4"
# 주인이 센 분모: 한 줄, 세션의 테넌트로, 꼬리표도 같고, 성공.
echo
echo "▶ 주인 역할이 본 그 줄 (count|tenant_id|tag_tenant|result_kind)"
ROW="$(sql "SELECT count(*), min(tenant_id), min(tag_tenant), min(result_kind) FROM core_llm_call_logs WHERE module='s4'")"
echo "  $ROW"
test "$ROW" = "1|tenant-s4|tenant-s4|success"
echo "EXIT=$?"
run "$CALL ; test \$? = 2"                                        # --tenant 없이 → 2
run "$CALL --tenant tenant-s4 --store-bodies ; test \$? = 2"      # 본문 + db → 2
# 거절된 두 번은 줄을 남기지 않았다: 표 전체가 여전히 1줄.
echo
echo "▶ 거절된 두 실행은 줄을 남기지 않았다 (표 전체의 행 수)"
ALL_ROWS="$(sql "SELECT count(*) FROM core_llm_call_logs")"
echo "  $ALL_ROWS"
test "$ALL_ROWS" = 1
echo "EXIT=$?"
run 'docker compose down -v'
run 'scripts/verify.sh'

# 허용 경로 밖의 변경이 없어야 한다(0). 앞 줄은 아직 커밋 안 한 것, 뒷줄은 커밋한 것(커밋 경계가 셋이다).
ALLOWED='apps/api-py/esgapi/core/(llm/sink_db\.py|llm/setup\.py|models\.py|migrations/|management/commands/llm_call\.py|tests/)|apps/api-py/tests/security/test_llm_log\.py|apps/api-py/conftest\.py|apps/api-py/scripts/section4-PY3b\.sh|apps/api-py/esgapi/config/(env\.py|tests/test_env\.py)|\.env\.example|README\.md'
run "test -z \"\$(git status --porcelain --untracked-files=all | grep -v -E '^.. ($ALLOWED)')\""
run "test -z \"\$(git diff --name-only $BASE..HEAD | grep -v -E '^($ALLOWED)')\""
echo
echo "── 허용 경로 밖의 변경(없어야 한다)"
git status --porcelain --untracked-files=all | grep -v -E "^.. ($ALLOWED)"
git diff --name-only "$BASE..HEAD" | grep -v -E "^($ALLOWED)"
echo "OUTSIDE_STATUS=$(git status --porcelain --untracked-files=all | grep -v -E "^.. ($ALLOWED)" | wc -l | tr -d ' ')"
echo "OUTSIDE_COMMITTED=$(git diff --name-only "$BASE..HEAD" | grep -v -E "^($ALLOWED)" | wc -l | tr -d ' ')"
echo "── 부하"; uptime
