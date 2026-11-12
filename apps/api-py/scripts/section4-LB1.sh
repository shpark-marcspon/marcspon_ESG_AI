#!/usr/bin/env bash
# 밴드 LB1(MARC-TICK-613 — LLM 한도 초과·과부하 이름 가름 + 대기 예산 재시도 + ToolLoopFailed hosted_calls)의 §4 자기검증
# (발주서 band-handoffs/LB1-order.md §4).
#   사용: apps/api-py/scripts/section4-LB1.sh [--with-containers]
#   --with-containers 면 업무 층(이 워크트리의 compose postgres — runs/tests/test_context_live.py·core 의 sink_db)과
#   verify --fast 도 돈다. 안 주면 그 둘은 「안 돌림」(실패로 셈).
# 단계마다 「[이름] EXIT=<n> <초>s」, 끝 줄 「SECTION4_FAIL=<n>」. 기준 B = 발주서 BASE 78827ffb(S4_BASE 로 바꿈).
# .git/verify.lock(디렉터리)이 있으면 시험을 하나도 돌리지 않고 종료 2(러너 공통 §5).
# macOS /bin/bash 3.2. LLM·네트워크 0(실호출 0 — 공급사는 모의·진짜 SDK + 가짜 HTTP).
set -u
cd "$(dirname "$0")/.."
MAIN="$(git rev-parse --path-format=absolute --git-common-dir)"
B="${S4_BASE:-78827ffb}"
CONTAINERS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --with-containers) CONTAINERS=1; shift ;;
    *) echo "모르는 인자: $1" >&2; exit 2 ;;
  esac
done
FAIL=0
locked() { [ -e "$MAIN/verify.lock" ]; }
step() {  # step <이름> <명령…>
  local name="$1"; shift
  if locked; then echo "[$name] lock 있음 — 멈춤"; exit 2; fi
  local start=$SECONDS
  "$@"
  local code=$?
  echo "[$name] EXIT=$code $((SECONDS - start))s"
  [ "$code" -eq 0 ] || FAIL=$((FAIL + 1))
}

echo "BASE $B · HEAD $(git rev-parse --short HEAD)"
if locked; then echo "lock 있음 — 시험 0"; exit 2; fi
echo "lock 없음 확인 $(date +%H:%M:%S)"

# §4-1 표적: core 의 llm 시험(순수 층) — 고른 식은 디렉터리와 이름 둘.
target() {
  uv run --frozen pytest -q -p no:cacheprovider -n 2 -m "not django_db and not security" esgapi/core/tests/llm \
    esgapi/core/tests/test_llm_adapters.py esgapi/core/tests/test_llm_gemini.py esgapi/core/tests/test_llm_retry.py \
    esgapi/core/tests/test_llm_command.py esgapi/core/tests/test_llm_client.py
}
# §4-2 core 밖 의존(경계 0-2 목록) — 이 밴드 뒤에도 초록, 0줄.
outside() {
  uv run --frozen pytest -q -p no:cacheprovider -n 2 -m "not django_db and not security" \
    esgapi/translation/tests/tools esgapi/translation/tests/engines esgapi/translation/tests/flows \
    esgapi/inventory/tests/test_scope3_prompts.py esgapi/inventory/tests/flows \
    esgapi/dataverify/tests esgapi/materiality/tests esgapi/greenwash/tests/flows/test_rewrite_r1.py \
    esgapi/drafting/tests esgapi/runs/tests/test_tasks_shape.py
}
zero_land() {  # 0줄 구역(§1) — runs 는 test_context_live.py 의 단언만(Q4)
  local n bad
  n=$(git diff "$B" --name-only -- esgapi/greenwash esgapi/drafting esgapi/translation esgapi/materiality esgapi/dataverify \
      esgapi/inventory generated esgapi/config tests/security tests_integration conftest.py scripts/verify.sh \
      scripts/planted-breaks.sh scripts/test-business.sh pyproject.toml uv.lock ../web ../../deploy \
      esgapi/core/llm/data esgapi/core/llm/throttle.py esgapi/core/models.py esgapi/core/migrations | wc -l | tr -d ' ')
  bad=$(git diff "$B" --name-only -- esgapi/runs | grep -v '^apps/api-py/esgapi/runs/tests/test_context_live.py$')
  echo "0줄 구역 바뀐 파일 $n · runs 허락 밖: ${bad:-0}"
  [ "$n" -eq 0 ] && [ -z "$bad" ]
}
allowed_land() {  # 수정 허용 닫힌 목록(§1) 밖이 없나
  local bad
  bad=$(git diff "$B" --name-only -- . | grep -vE '^apps/api-py/(esgapi/core/llm/(retry|types|client|embedding|embedding_types|log|__init__|sink_db)\.py|esgapi/core/llm/providers/(anthropic|openai|gemini|mock)\.py|esgapi/core/tests/.*|scripts/(section4|planted-breaks)-LB1\.sh|esgapi/runs/tests/test_context_live\.py)$')
  echo "허락 밖 파일: ${bad:-0}"; [ -z "$bad" ]
}
sha16() {  # 보고의 sha16(§6)
  echo "sha16 $(git diff "$B" HEAD -- esgapi/core esgapi/config generated tests/security esgapi/runs | shasum -a 256 | cut -c1-16)"
}
count_asserts() {  # 셈 대조(보고에) — 종료는 늘 0
  git diff "$B" -U0 -- esgapi/core/tests esgapi/runs/tests | grep -E '^[-+].*(== *\[?[0-9]|max_retries|attempts|_lines|FAILED_429)' \
    | grep -vE '^(\+\+\+|---)' | head -60
  return 0
}

step target target
step outside outside
step importlinter uv run --frozen lint-imports
step test-layout uv run --frozen python scripts/check_test_layout.py
step pyright uv run --frozen pyright esgapi/core/llm esgapi/core/tests/llm esgapi/runs/tests/test_context_live.py
step zero-land zero_land
step allowed-land allowed_land
step sha16 sha16
step count-asserts count_asserts
if [ "$CONTAINERS" -eq 1 ]; then
  step test-business ./scripts/test-business.sh -q -n 2 esgapi/runs/tests/test_context_live.py esgapi/core/tests/test_llm_sink_db.py
  step verify-fast bash -c 'cd ../.. && scripts/verify.sh --fast'
else
  echo "[test-business] 안 돌림(--with-containers 없음)"; FAIL=$((FAIL + 1))
  echo "[verify-fast] 안 돌림(--with-containers 없음)"; FAIL=$((FAIL + 1))
fi
echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" -eq 0 ]
