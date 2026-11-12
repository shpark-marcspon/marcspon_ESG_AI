#!/usr/bin/env bash
# 발주서(MARC-TICK-49, 밴드 PY3) §4 의 자기검증을 한 번에 돌린다.
#   사용: apps/api-py/scripts/section4-PY3.sh            §4 의 명령을 차례로. 줄마다 "EXIT=<종료 코드>". 전부 0 이어야 한다
#         apps/api-py/scripts/section4-PY3.sh planted    심은 파손 일곱(컨테이너 없이 돈다). 마지막 줄 PLANTED=7/7 이어야 한다
# 다루는 컨테이너·볼륨은 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# AI 공급사는 부르지 않는다(모의 공급사와 dry-run 뿐. 키를 읽지 않는다).
set -u
cd "$(dirname "$0")/../../.."

# ── 심은 파손 ─────────────────────────────────────────────────────────
# 코드 한 줄을 망가뜨리고 순수 층(core·config 의 테스트)과 순수성 계약을 돌려, 기대한 테스트가 빨개지는지 본다.
# 고치기 전의 파일을 임시 폴더에 베껴 두었다가 되돌린다(git 을 쓰지 않는다). 끝나면 작업 트리가 처음과 같아야 한다.
planted() {
  cd apps/api-py
  # 둘 다 함수 밖에서도 보여야 한다(끝날 때의 trap 이 읽는다).
  backup="$(mktemp -d)"
  touched=""
  restore() { if [ -n "$touched" ]; then cp "$backup/file" "$touched"; touched=""; fi; }
  trap 'restore; rm -rf "$backup"' EXIT

  break_line() { # <파일> <있어야 하는 글(고정 문자열)> <바꿀 글>
    grep -qF -- "$2" "$1" || { echo "★ 심을 자리가 없다: $1 에 「$2」 가 없다"; return 1; }
    cp "$1" "$backup/file"; touched="$1"
    OLD="$2" NEW="$3" python3 - "$1" <<'PY'
import os, sys
path = sys.argv[1]
text = open(path, encoding="utf-8").read()
open(path, "w", encoding="utf-8").write(text.replace(os.environ["OLD"], os.environ["NEW"], 1))
PY
  }
  failed_tests() { # 빨개진 테스트의 이름(파일::함수)을 한 줄에 하나씩
    uv run --frozen pytest -q -m "not django_db and not security" -p no:cacheprovider esgapi/core esgapi/config 2>&1 \
      | sed -n 's/^FAILED \([^ ]*\).*/\1/p' | sed 's/\[.*//' | sort -u
  }
  purity() { # 순수성 계약이 깨졌으면 BROKEN, 아니면 KEPT
    if uv run --frozen lint-imports --config esgapi/core/llm/purity.importlinter >/dev/null 2>&1; then echo KEPT; else echo BROKEN; fi
  }

  # 심기 전의 다섯 파일의 지문. 끝난 뒤의 것과 같아야 한다(새 파일이라 git status 로는 안 보인다).
  local planted_files="esgapi/core/llm/client.py esgapi/core/llm/schema.py esgapi/core/llm/prompts.py esgapi/core/llm/providers/redact.py esgapi/core/tests/conftest.py"
  local before; before="$(shasum -a 256 $planted_files)"

  local total=0 ok=0
  check() { # <번호와 설명> <빨개져야 하는 테스트(파일::함수)> [기대하는 계약 상태]
    local reds; reds="$(failed_tests)"
    local count; count="$(printf '%s' "$reds" | grep -c . || true)"
    local contract; contract="$(purity)"
    local want_contract="${3:-KEPT}"
    total=$((total + 1))
    local mark="★ 다름"
    if [ "$2" = "없음" ]; then
      [ "$count" = 0 ] && [ "$contract" = "$want_contract" ] && mark="맞음"
    elif printf '%s\n' "$reds" | grep -qxF -- "$2" && [ "$contract" = "$want_contract" ]; then
      mark="맞음"
    fi
    [ "$mark" = "맞음" ] && ok=$((ok + 1))
    echo
    echo "▶ $1"
    echo "  기대: $2 가 빨개진다 / 순수성 계약 $want_contract"
    echo "  결과: 빨개진 테스트 $count 개, 순수성 계약 $contract  → $mark"
    printf '%s\n' "$reds" | sed '/^$/d; s/^/    /'
    restore
  }

  check "0. 심지 않음" "없음"

  break_line esgapi/core/llm/client.py "exhausted = self.budget.check(request.tags)" "exhausted = None" \
    && check "1. 예산 check 를 뺀다 (client.py)" \
      "esgapi/core/tests/test_llm_client.py::test_budget_blocks_before_calling_provider_once_limit_is_reached"

  break_line esgapi/core/llm/client.py "for _round in range(schema_retries + 1):" "for _round in range(1):" \
    && check "2. 스키마 재시도를 0 으로 (client.py)" \
      "esgapi/core/tests/test_llm_client.py::test_default_is_two_schema_retries_then_schema_mismatch"

  break_line esgapi/core/llm/schema.py 'out["additionalProperties"] = False' 'pass' \
    && check "3. additionalProperties: false 를 넣지 않는다 (schema.py)" \
      "esgapi/core/tests/test_llm_schema.py::test_every_object_is_closed_and_every_property_is_required"

  break_line esgapi/core/llm/providers/redact.py 'return _AIZA.sub("AIza[가림]", _SK.sub("sk-[가림]", text))' 'return text' \
    && check "4. 키 가리기(redact)를 뺀다. 오류 문장에 키가 든 SDK 예외를 테스트가 던진다 (providers/redact.py)" \
      "esgapi/core/tests/test_llm_adapters.py::test_key_in_sdk_error_message_never_reaches_the_result"

  break_line esgapi/core/llm/client.py "import json" "import django  # noqa: F401
import json" \
    && check "5. client.py 에 import django" \
      "esgapi/core/tests/test_llm_layers.py::test_only_setup_imports_django_inside_the_call_layer" BROKEN

  break_line esgapi/core/llm/prompts.py "    if unused:" "    if unused and False:" \
    && check "6. 템플릿의 남는 변수 검사를 뺀다 (prompts.py)" \
      "esgapi/core/tests/test_llm_prompts.py::test_extra_variable_is_an_error"

  break_line esgapi/core/tests/conftest.py 'if node.get_closest_marker("django_db") is not None:' 'if True:' \
    && check "7. 소켓을 막는 고정물을 끈다 (core/tests/conftest.py)" \
      "esgapi/core/tests/test_llm_layers.py::test_socket_connections_are_blocked_in_these_tests"

  echo
  echo "PLANTED=$((ok - 1))/$((total - 1))   (0번 「심지 않음」은 빼고 센다. 0번이 맞음이 아니면 아래 줄이 다르다)"
  echo "BASELINE_CLEAN=$([ "$ok" -ge 1 ] && echo yes || echo no)"
  echo "TREE_SAME_AFTER_RESTORE=$([ "$before" = "$(shasum -a 256 $planted_files)" ] && echo yes || echo no)"
}

if [ "${1:-}" = "planted" ]; then planted; exit 0; fi

# ── §4 ────────────────────────────────────────────────────────────────
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}

# verify.sh 는 Node 22 를 쓴다.
PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"; export PATH

echo "── 포트가 다른 워크트리와 겹치지 않는가 (.env)"
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; fi
done
echo "── 부하"; uptime

# ── 컨테이너 없이 도는 것 ──
run 'cd apps/api-py && uv sync --frozen'
run 'cd apps/api-py && uv run ruff check . && uv run ruff format --check .'
run 'cd apps/api-py && uv run pyright'
run 'cd apps/api-py && uv run lint-imports'
run 'cd apps/api-py && uv run lint-imports --config esgapi/core/llm/purity.importlinter'
run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security"'     # 순수 층

# 통합 테스트가 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다). section4.sh 와 같다.
EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
export EDK_JWT_PUBLIC_KEY

# ── 컨테이너가 있어야 도는 것 ──
run 'docker compose up -d --build --wait'
run 'apps/api-py/scripts/test-business.sh -n 2'
run 'apps/api-py/scripts/test-security.sh'
run 'apps/api-py/scripts/test-integration.sh'
# 관리 명령을 **컨테이너 안에서** 돌린다: 이미지에 data/*.json 과 prompts/*.md 가 실렸는지까지 잰다.
run "docker compose exec -T api-py python manage.py llm_call --prompt core/hello@1 --var name=x --route mock --mock-text '{\"ok\":true}' --dry-run"
# jsonl 은 /tmp 아래(/app 은 앱 사용자가 쓰지 못한다). mock 이 답하고 JSONL 한 줄이 남는다.
run "docker compose exec -T -e LLM_LOG_SINK=jsonl -e LLM_JSONL_PATH=/tmp/llm.jsonl api-py python manage.py llm_call --prompt core/hello@1 --var name=x --route mock --mock-text '{\"ok\":true}' && test \"\$(docker compose exec -T api-py sh -c 'wc -l < /tmp/llm.jsonl' | tr -d ' ')\" = 1"
# 그 한 줄의 칸 목록(CallRecord 의 늘 있는 칸 스물하나)을 눈으로 볼 수 있게 낸다.
run "docker compose exec -T api-py python -c \"import json; print(sorted(json.loads(open('/tmp/llm.jsonl').readline())))\""
run 'docker compose down -v'
run 'scripts/verify.sh'

# 허용 경로 밖의 변경이 없어야 한다(0).
ALLOWED='^.. (apps/api-py/esgapi/core/(llm/|ports/llm.py|adapters/llm.py|prompts/|tests/|management/commands/llm_)|apps/api-py/esgapi/config/tests/test_env.py|apps/api-py/scripts/section4-PY3.sh|apps/api-py/(pyproject.toml|uv.lock|\.gitignore|esgapi/config/env.py)|\.env\.example|compose\.yaml|README\.md)'
run "test -z \"\$(git status --porcelain --untracked-files=all | grep -v -E '$ALLOWED')\""
echo
echo "── 허용 경로 밖의 변경(없어야 한다)"
git status --porcelain --untracked-files=all | grep -v -E "$ALLOWED"
echo "OUTSIDE_STATUS=$(git status --porcelain --untracked-files=all | grep -v -E "$ALLOWED" | wc -l | tr -d ' ')"
echo "── 부하"; uptime
