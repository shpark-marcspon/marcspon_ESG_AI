#!/usr/bin/env bash
# 밴드 PY6(MARC-TICK-53, 데이터 검증의 규칙)의 §4 자기검증. 줄마다 "EXIT=<종료 코드>" 를 낸다. 전부 0 이어야 한다.
#   사용: apps/api-py/scripts/section4-PY6.sh          전체(컨테이너를 띄우고 내린다)
#         apps/api-py/scripts/section4-PY6.sh pure     커밋 경계 ① 뒤의 것: 순수 층·골든·허용 경로 줄만(컨테이너 없음)
# 심은 파손은 따로다: apps/api-py/esgapi/reconcile/tests/planted-breaks-PY6.sh (마지막 줄 PLANTED=21/21)
# 다루는 컨테이너·볼륨·이미지는 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# esg-lab 은 읽고 실행만 한다(골든의 TS 덤프). 경로가 다르면 ESG_LAB 로 준다.
set -u
cd "$(dirname "$0")/../../.."
MODE="${1:-all}"
BASE=6aaa84e
ESG_LAB="${ESG_LAB:?ESG_LAB=<esg-lab 저장소의 경로> 를 준다}"
export ESG_LAB BASE
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 와 골든의 tsx 가 Node 22 를 쓴다

env_value() { sed -n "s/^$1=//p" .env | tail -1; }
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  echo "EXIT=$?"
}

echo "── $(date '+%Y-%m-%d %H:%M:%S') · 모드 $MODE · 부하와 포트 (.env)"
uptime
memory_pressure 2>/dev/null | grep percentage
grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
for port in $(grep -E '^(API|API_PY|POSTGRES|STORAGE)_PORT=' .env | cut -d= -f2); do
  if lsof -nP -iTCP:"$port" -sTCP:LISTEN >/dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; fi
done

# ── 컨테이너 없이 도는 것 ──
run 'cd apps/api-py && uv sync --frozen'
if [ "$MODE" != pure ]; then
  run 'cd apps/api-py && uv run ruff check . && uv run ruff format --check .'
  run 'cd apps/api-py && uv run pyright'
  run 'cd apps/api-py && uv run lint-imports'
fi
run 'cd apps/api-py && uv run pytest -q -m "not django_db and not security"'                 # 순수 층(지은 문서 골든 포함)
if [ "$MODE" = pure ]; then
  run 'cd apps/api-py && uv run pytest -q esgapi/reconcile --durations=5'                     # 이 밴드의 것(① 까지)
else
  run 'cd apps/api-py && uv run pytest -q esgapi/reconcile esgapi/core/tests/test_parser_port.py --durations=5'   # 이 밴드의 것만, 건수
fi

# 골든: esg-lab 의 TS 덤프 → 파이썬과 값으로 견준다. esg-lab 은 앞뒤로 달라지지 않아야 한다.
run 'mkdir -p apps/api-py/.lab-golden && git -C "$ESG_LAB" status --porcelain > apps/api-py/.lab-golden/lab-before.txt; git -C "$ESG_LAB" rev-parse --short HEAD'
run 'apps/api-py/esgapi/reconcile/tests/golden/make-golden.sh'
run 'cd apps/api-py && uv run python -m esgapi.reconcile.tests.golden.check_lab'              # 네 문서 × 구획: 건수 + 값 전체 일치 + digest
run 'git -C "$ESG_LAB" status --porcelain | diff - apps/api-py/.lab-golden/lab-before.txt'    # esg-lab 변경 0

run 'git diff --quiet "$BASE" -- apps/api-py/pyproject.toml apps/api-py/uv.lock'              # 새 의존성 0
# 공유 파일 셋은 추가만: numstat 의 지운 줄 합 0
run 'test "$(git diff --numstat "$BASE" -- apps/api-py/esgapi/config/env.py .env.example compose.yaml | awk '"'"'{s+=$2} END{print s+0}'"'"')" = 0'
run 'git diff --quiet "$BASE" -- apps/api-py/esgapi/reconcile/api.py apps/api-py/esgapi/reconcile/apps.py apps/api-py/generated'   # api.py·apps.py·generated 0줄

if [ "$MODE" != pure ]; then
  run 'apps/api-py/scripts/check-wheel.sh'                                                    # wheel 에 tests(골든 도구 포함) 없음

  # 통합 테스트가 EDK 인 척 토큰을 서명할 키 쌍. 공개키만 컨테이너에 준다(.env 의 값보다 앞선다).
  EDK_JWT_PUBLIC_KEY="$(cd apps/api-py && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY

  # ── 컨테이너가 있어야 도는 것 ──
  run 'docker compose up -d --build --wait'
  run 'apps/api-py/scripts/test-business.sh -n 2'      # 업무 층(이 밴드는 더하지 않는다 — 수 그대로)
  run 'apps/api-py/scripts/test-security.sh'           # 보안 층(수 그대로)
  run 'apps/api-py/scripts/test-integration.sh'        # 통합 6

  # 이미지 안: calc 로 지은 표 하나에서 값 후보를 뽑는다. tests 폴더는 없다.
  IMAGE="$PROJECT/api-py:local"
  export IMAGE
  in_image() {
    docker run --rm "$IMAGE" python -c '
import importlib.util
from esgapi.reconcile.calc.facts import extract_document
from esgapi.reconcile.calc.document import validate_document
raw = {"schema_version": "0.1", "source": {"file_name": "s.synthetic.pdf", "sha256": "0" * 64, "page_count": 1},
       "pages": [{"page": 1, "height": 800, "text_layer": "present"}],
       "blocks": [{"id": "p1-b1", "kind": "table", "page": 1, "bbox": [0, 0, 1, 1], "order": 1, "table_id": "p1-t1"}],
       "tables": [{"id": "p1-t1", "page": 1, "cells": [["구분", "값"], ["가", "1,234"]],
                   "header": {"rows": [0], "cols": [0], "basis": "rows_before_first_numeric_row"},
                   "method": "lines", "status": "ok", "footnote_marks": []}]}
facts = extract_document(validate_document(raw).document, "s").facts
print([(fact.id, fact.value) for fact in facts])
assert [(fact.id, fact.value) for fact in facts] == [("p1-t1:r1c1", "1234")]
assert importlib.util.find_spec("esgapi.reconcile.tests") is None, "이미지에 tests 가 실렸다"
print("이미지 안: 값 후보 1, esgapi.reconcile.tests 없음")
'
  }
  run 'in_image'
  # 떠 있는 api-py 의 환경에 파서의 주소와 시간 제한이 있다.
  run 'docker compose exec -T api-py env | grep -E "^PARSER_(URL|TIMEOUT_MS)=" | sort | tee /dev/stderr | tr "\n" " " | grep -q "PARSER_TIMEOUT_MS=30000 PARSER_URL=http://parser:8000"'

  run 'docker compose down -v'
  run 'scripts/verify.sh'
  # 이 워크트리의 이미지를 지운다(바탕 이미지와 다른 워크트리의 것은 건드리지 않는다).
  run 'docker image ls --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/.*:local$" | xargs -r docker image rm >/dev/null; ! docker image ls --format "{{.Repository}}" | grep -q "^$PROJECT/"'
fi

# 허용 경로 밖 0 — 기준 커밋과의 차이(커밋 ① 포함) + 안 올린 새 파일을 같이 본다(발주서 §4 의 마지막 줄 그대로).
run 'test -z "$({ git diff --name-only "$BASE"; git ls-files -o --exclude-standard; } | sort -u | grep -v -E '"'"'^(apps/api-py/esgapi/reconcile/|apps/api-py/esgapi/core/(ports|adapters)/parser\.py$|apps/api-py/esgapi/core/tests/test_parser_port\.py$|apps/api-py/scripts/section4-PY6\.sh$|apps/api-py/(pyproject\.toml|uv\.lock|\.gitignore)$|apps/api-py/esgapi/config/env\.py$|\.env\.example$|compose\.yaml$|README\.md$)'"'"')"'
echo
echo "▶ git status --porcelain | wc -l"
git status --porcelain | wc -l
echo "▶ esg-lab 을 건드리지 않았는가: git -C $ESG_LAB status --porcelain | wc -l"
git -C "$ESG_LAB" status --porcelain | wc -l
