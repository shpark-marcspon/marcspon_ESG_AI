#!/usr/bin/env bash
# 밴드 GP1(MARC-TICK-69: 인증 있는 동작 13 의 권한 검증, 권한 표 하나, 도메인을 넘는 조립의 Action)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-GP1.sh --step <1~4>     그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-GP1.sh --pure           --step 4 전부 + 심은 파손
#         apps/api-py/scripts/section4-GP1.sh --containers     컨테이너 층 한 번(postgres 만 띄운다 → 업무 → 보안 → 권한 표에 심는 파손 열하나 → 내리기)
#         apps/api-py/scripts/section4-GP1.sh --hand-planted   권한 표에 심는 파손 열하나의 순수 층 쪽만(DB 없이)
#         apps/api-py/scripts/section4-GP1.sh --after-commit   --pure 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 와 통합 층은 돌리지 않는다(감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨은 이 저장소의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# AI 공급사 호출 0. 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 커밋마다 달라지는 기대: 계약 수(①~③ 다섯, ④ 여섯), 없어지는 노드 ID(①② 하나, ③ 부터 둘), Action(③ 부터).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 권한 표에 심는 파손 열하나(발주서 §3-3 의 둘째 표)는 계약이 아니라 테스트가 빨개지는지를 본다. 한 번에 하나씩,
#   심기 전의 파일을 저장소 밖에 베껴 두었다가 되돌린다(git 을 쓰지 않는다). 하나는 남의 파일
#   (accounts/service/selectors/accounts.py)에 잠깐 심는다. 업무 층 쪽은 postgres 가 떠 있을 때(--containers)만 잰다.
# ★ 기준의 노드 ID 는 git archive 로 푼 사본(저장소 밖)에서 이 워크트리의 .venv 로 뜬다(1,891건).
set -u
cd "$(dirname "$0")/../../.."
B=aae8afa   # 기준 커밋(발주서 §1-1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
MODE="${1:-}"
STEP=4
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [1-4]) ;; *) echo "사용: $0 --step <1~4>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --hand-planted | --after-commit) ;;
  *) echo "사용: $0 --step <1~4> | --pure | --containers | --hand-planted | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
ROOT="$PWD"
A=apps/api-py
TEST_DS=esgapi.config.settings.test_business
PURE=1519       # 순수 층: 기준 1,508 − 1(test_editor_and_up_can_upload) + 12(core 아홉 · accounts 셋)
BUSINESS=336    # 업무 층: 기준 316 + 14(연결) + 3(분류의 거부) + 3(Action)
SECURITY=67     # 보안 층: 기준 그대로
env_value() { sed -n "s/^$1=//p" .env | tail -1; }

FAILS=0
run() {
  echo
  echo "▶ $*"
  ( eval "$*" )
  local code=$?
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
sha() { shasum -a 256 "$1" | cut -d' ' -f1; }
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1-2 의 닫힌 목록) 밖에서 바뀐 파일. 줄마다 저장소 뿌리에서 시작하는 꼴이다.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/permissions\.py$' \
    -e '^apps/api-py/esgapi/core/calc/documents\.py$' \
    -e '^apps/api-py/esgapi/core/service/apis/documents\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_permissions|test_permissions_wiring|test_documents_calc)\.py$' \
    -e '^apps/api-py/esgapi/accounts/service/permissions/accounts\.py$' \
    -e '^apps/api-py/esgapi/accounts/service/apis/(auth|accounts)\.py$' \
    -e '^apps/api-py/esgapi/accounts/tests/test_permissions\.py$' \
    -e '^apps/api-py/esgapi/inventory/service/apis/inventory\.py$' \
    -e '^apps/api-py/esgapi/inventory/service/services/inventory\.py$' \
    -e '^apps/api-py/esgapi/inventory/service/actions/(__init__|scope3_shortlist)\.py$' \
    -e '^apps/api-py/esgapi/inventory/__init__\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/(test_scope3_api|test_api)\.py$' \
    -e '^apps/api-py/esgapi/reference/service/apis/reference\.py$' \
    -e '^apps/api-py/esgapi/reconcile/tests/test_tasks_registered\.py$' \
    -e '^apps/api-py/esgapi/__init__\.py$' \
    -e '^apps/api-py/\.importlinter$' \
    -e '^apps/api-py/scripts/(planted-breaks|section4-GP1)\.sh$'
}
# 지난 밴드의 기록 스크립트와 rehearsal.sh (0줄이어야 한다).
records() {
  git ls-files "$A/scripts/section4*.sh" "$A/scripts/planted-breaks-*.sh" "$A/esgapi/*/tests/planted-breaks-*.sh" \
    | grep -v -x "$A/scripts/section4-GP1.sh"
  echo "$A/scripts/rehearsal.sh"
}
# 노드 ID: 기준에만 있는 줄(diff 의 <)의 기대. 그 커밋까지의 것.
expected_gone() {
  echo "< esgapi/core/tests/test_documents_calc.py::test_editor_and_up_can_upload"
  [ "$STEP" -ge 3 ] && echo "< esgapi/inventory/tests/test_scope3_api.py::test_the_service_catalog_keeps_that_order"
  return 0
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다. 먼저 다른 esg-app* 컨테이너가 0 이 될 때까지(60초마다, 최대 30분),
# 그 뒤 verify.lock 없음 · 메모리 free 20% 이상 · 1분 부하 12 미만(30초마다, 최대 10분).
gate() {
  local tries=0 others free load lock
  while :; do
    others="$(docker ps --format '{{.Names}}' | grep -c '^esg-app')"
    [ "$others" = 0 ] && break
    [ "$tries" -ge 30 ] && { echo "  (다른 esg-app* 컨테이너가 30분 뒤에도 $others 개 떠 있다)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
  echo "  (다른 esg-app* 컨테이너 0 · 기다린 횟수 $tries × 60초)"
  tries=0
  lock="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
  while :; do
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ ! -e "$lock" ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: verify.lock 없음 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 30초)"
      return 0
    fi
    [ "$tries" -ge 20 ] && { echo "  (문이 안 열렸다: verify.lock $([ -e "$lock" ] && echo 있음 || echo 없음) · free ${free:-?}% · 1분 부하 ${load:-?} · 10분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 30
  done
}

echo "── 밴드 GP1 §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local kept=5; [ "$STEP" -ge 4 ] && kept=6
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것·경고 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "'"$PURE"' passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'

  echo; echo "── 나. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일"
  run 'git diff --quiet "$B" -- "$A/generated"'
  run 'for f in openapi.json api.d.ts api.d.ts.source-sha256; do now="$(sha "$A/generated/$f")"; echo "  $now  $f"; test "$now" = "$(git show "$B:$A/generated/$f" | shasum -a 256 | cut -d" " -f1)" || { echo "★ 다르다: $f"; exit 1; }; done; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 다. 경로 함수의 docstring 0줄(바뀐 삼중 따옴표 줄은 새 함수 둘의 것뿐)"
  run 'git diff -U0 "$B" -- "$A/esgapi/*/service/apis/*.py" | grep -E "^[+-][^+-]" | grep -F "\"\"\"" > "$T/doc.txt"; cat "$T/doc.txt"; test "$(grep -c -v -x -F "+    \"\"\"세션을 꺼내고 그 동작의 권한을 본다(권한 표: core/permissions.py). 역할이 모자라면 403 forbidden.\"\"\"" "$T/doc.txt")" = 0 && test "$(wc -l < "$T/doc.txt" | tr -d " ")" = 2'

  echo; echo "── 라. 계약 $kept KEPT"
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; grep -E "^[가나다라마바]\. " "$T/lint.txt"; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: '"$kept"' kept, 0 broken." && test "$(grep -c -E "^[가나다라마바]\. .* KEPT" "$T/lint.txt")" = '"$kept"' && exit $code; exit 1)'
  run 'n="$(grep -c "importlinter:contract:" "$A/.importlinter")"; echo "  .importlinter 의 계약 수: $n"; [ "$n" = '"$kept"' ]'

  echo; echo "── 마. 표와 호출(글자)"
  run '(cd "$A" && n="$(git grep -I -c "can_upload" -- esgapi | wc -l | tr -d " ")"; u="$(git grep -I -c "_uploader" -- esgapi | wc -l | tr -d " ")"; echo "  can_upload 가 든 파일 $n · _uploader 가 든 파일 $u"; [ "$n$u" = 00 ])'
  run '(cd "$A" && n="$(git grep -c "session_of(" -- esgapi/inventory/service/apis esgapi/reference/service/apis | wc -l | tr -d " ")"; m="$(git grep -c "session_of(request)" -- esgapi/accounts/service/apis/accounts.py | cut -d: -f2)"; echo "  inventory·reference 의 경로에 남은 session_of( 파일 $n · accounts 의 경로의 session_of(request) ${m}줄(사업장 둘)"; [ "$n" = 0 ] && [ "$m" = 2 ])'
  run '(cd "$A" && git grep -hoE "(permitted_session|_permitted)\(request, \"[a-z0-9_]+\"\)" -- "esgapi/*/service/apis/*.py" | sed -E "s/.*\"([a-z0-9_]+)\".*/\1/" | sort > "$T/called.txt"; n="$(wc -l < "$T/called.txt" | tr -d " ")"; u="$(sort -u "$T/called.txt" | wc -l | tr -d " ")"; echo "  경로가 글자로 부른 것 ${n}번 · 서로 다른 이름 $u (11 = 13 − 사업장 둘)"; { cat "$T/called.txt"; echo accounts_sites_list; echo accounts_sites_create; } | sort > "$T/called-all.txt"; uv run --frozen python -c "from esgapi.core.permissions import OPERATION_POLICY; print(*sorted(OPERATION_POLICY), sep=chr(10))" > "$T/table.txt"; diff "$T/table.txt" "$T/called-all.txt" && [ "$n" = 11 ] && [ "$u" = 11 ])'

  if [ "$STEP" -ge 3 ]; then
    echo; echo "── 바. Action: 하나이고, actions/ 의 파일마다 도메인 둘 이상을 부른다. inventory 의 Service·Selector 는 남의 도메인을 모른다"
    run '(cd "$A" && { git ls-files esgapi; git ls-files --others --exclude-standard esgapi; } | sort -u | grep "/actions/" | grep -v "__init__" > "$T/actions.txt"; cat "$T/actions.txt"; echo esgapi/inventory/service/actions/scope3_shortlist.py | diff - "$T/actions.txt")'
    run '(cd "$A" && uv run --frozen python - <<PY
import ast, sys
from pathlib import Path
bad = 0
files = [p for p in Path("esgapi").glob("*/service/actions/*.py") if p.name != "__init__.py"]
for path in files:
    domains = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        names = [node.module or ""] if isinstance(node, ast.ImportFrom) else [a.name for a in node.names] if isinstance(node, ast.Import) else []
        for name in names:
            parts = name.split(".")
            if parts[0] == "esgapi" and len(parts) > 1 and parts[1] not in ("core", "config"):
                domains.add(parts[1])
    print(" ", path, sorted(domains))
    bad += len(domains) < 2
sys.exit(1 if bad or not files else 0)
PY
)'
    run '(cd "$A" && n="$(git grep -nE "^(from|import) esgapi\.(accounts|reference|reconcile)" -- esgapi/inventory/service/services esgapi/inventory/service/selectors | wc -l | tr -d " ")"; echo "  inventory 의 Service·Selector 가 남의 도메인을 들인 줄: $n"; [ "$n" = 0 ])'
  fi

  echo; echo "── 사. 노드 ID: 기준(1,891)에서 없어진 것이 발주서 §3-1 의 것뿐이고, 새로 생긴 것이 전부 이 밴드의 테스트 파일 넷의 것이다"
  run 'mkdir -p "$T/base" && git archive "$B" "$A" | tar -x -C "$T/base" && (cd "$T/base/$A" && "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> "$T/base-collect.err" | grep "::" | LC_ALL=C sort > "$T/base-nodeids.txt"); n="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; h="$(sha "$T/base-nodeids.txt" | cut -c1-16)"; echo "  기준 ${n}건 · $h"; test "$n" = 1891 && test "$h" = ddb8fb529ece4a69'
  run '(cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | LC_ALL=C sort > "$T/nodeids.txt"); n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; diff "$T/base-nodeids.txt" "$T/nodeids.txt" | grep "^[<>]" > "$T/node-diff.txt"; gone="$(grep -c "^<" "$T/node-diff.txt")"; new="$(grep -c "^>" "$T/node-diff.txt")"; echo "  지금 ${n}건 · 없어진 것 $gone · 새로 생긴 것 $new"; grep "^<" "$T/node-diff.txt"; grep "^>" "$T/node-diff.txt" | sed -E "s/^> ([^:]+)::.*/\1/" | sort | uniq -c; expected_gone | LC_ALL=C sort | diff - <(grep "^<" "$T/node-diff.txt" | LC_ALL=C sort) && test "$(grep "^>" "$T/node-diff.txt" | grep -c -v -E "^> esgapi/(core/tests/test_permissions(_wiring)?\.py|accounts/tests/test_permissions\.py|inventory/tests/test_scope3_api\.py)::")" = 0 && test "$n" = "$((1891 - gone + new))"'

  echo; echo "── 아. 경계"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- compose.yaml scripts docker infra apps/web services README.md "$A/pyproject.toml" "$A/uv.lock" "$A/tests" "$A/tests_integration" "$A/conftest.py" "$A/esgapi/config"'
  run 'git diff --quiet "$B" -- "$A/esgapi/*/service/selectors" "$A/esgapi/accounts/service/services" "$A/esgapi/reference/service/services" "$A/esgapi/core/service/services" "$A/esgapi/reconcile/tasks.py" "$A/esgapi/*/migrations" && test "$(changed | grep -c -E "/migrations/|/service/selectors/|^$A/esgapi/(accounts|reference|core)/service/services/")" = 0'
  run 'n="$(records | wc -l | tr -d " ")"; echo "  기록 스크립트와 rehearsal.sh: ${n}파일"; git diff --quiet "$B" -- $(records)'
  run 'n="$(git diff "$B" -- "$A/esgapi/core/calc/documents.py" | grep -c "^+[^+]")"; echo "  core/calc/documents.py 에 더한 줄: $n (지우기만 한다)"; [ "$n" = 0 ]'

  echo; echo "── 자. accounts 의 권한 파일의 이름 셋이 그대로"
  run '(cd "$A" && uv run --frozen python -c "from esgapi.accounts.service.permissions.accounts import Forbidden, can_view_sites, can_create_site")'
  run 'n="$(git diff "$B" -- "$A/esgapi/accounts/service/permissions/accounts.py" | grep -c -E "^-def |^-class |^-    needed")"; echo "  지운 def·class·needed 줄: $n"; [ "$n" = 0 ]'

  echo; echo "── 차. 깎지 않았다(건너뛰기·경고 예외·무시 표시를 더하지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; plus="$({ git diff "$B" -- . ":!$A/scripts/section4-GP1.sh"; for f in $(git ls-files --others --exclude-standard | grep -v -x "$A/scripts/section4-GP1.sh"); do sed "s/^/+/" "$f"; done; } | grep -c -E "^\+.*($marks)")"; echo "  더한 줄 $plus (이 스크립트는 뺀다: 무늬를 글자로 적은 줄이 있다)"; [ "$plus" = 0 ]'

  echo; echo "── 카. 휠"
  run '"$A/scripts/check-wheel.sh" 2>&1 | tail -4; exit ${PIPESTATUS[0]}'
}

pure_extra_part() {
  echo; echo "── 심은 파손 27"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks.sh" > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=27/27" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
}

# 한 층을 돌리고 EXIT 를 찍는다. 끝 줄이 「<건수> passed」로 시작해야 한다. 다시 돌리지 않는다.
layer() { # <이름> <건수> <명령…>
  local name="$1" want="$2" code started=$SECONDS last
  shift 2
  echo; echo "▶ $*"
  "$@" > "$T/layer.txt" 2>&1; code=$?
  tail -3 "$T/layer.txt"
  last="$(tail -1 "$T/layer.txt")"
  case "$last" in "$want passed"*) ;; *) echo "★ 끝 줄이 「$want passed」로 시작하지 않는다"; code=1 ;; esac
  echo "$last" | grep -q -E "failed|error" && { echo "★ 끝 줄에 failed·error 가 있다"; code=1; }
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  if [ "$code" -ne 0 ]; then
    grep -E "^(FAILED|ERROR)" "$T/layer.txt" | head -40
    cp "$T/layer.txt" "$T/layer-$want.txt"; echo "  (전문: $T/layer-$want.txt)"
    memory_pressure | grep percentage
  fi
}

# 권한 표에 심는 파손 열하나. 줄마다 <심은 것> → 순수 층에서 빨개진 것 / 업무 층에서 빨개진 것, 기대와 같은가.
# WITH_DB=1 이면 업무 층도 잰다(postgres 가 떠 있어야 한다). 끝나면 작업 트리가 처음과 같아야 한다.
hand_planted() {
  (cd "$A" && WITH_DB="${WITH_DB:-0}" KEEP="$T/hand" uv run --frozen python - <<'PY'
import os, shutil, subprocess, sys
from pathlib import Path

KEEP = Path(os.environ["KEEP"]); KEEP.mkdir(parents=True, exist_ok=True)
WITH_DB = os.environ["WITH_DB"] == "1"
CORE = "esgapi/core/tests/test_permissions.py::"
ACC = "esgapi/accounts/tests/test_permissions.py::"
WIRE = "esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden"
S3 = "esgapi/inventory/tests/test_scope3_api.py::"
CELLS, PROPOSED, FIRST = CORE + "test_the_table_is_these_thirty_nine_cells", CORE + "test_only_the_llm_route_is_proposed", CORE + "test_each_route_checks_its_own_operation_id_first"
TABLE = "esgapi/core/permissions.py"
AUTH = "esgapi/accounts/service/apis/auth.py"
REF = "esgapi/reference/service/apis/reference.py"
INV = "esgapi/inventory/service/apis/inventory.py"
DOC = "esgapi/core/service/apis/documents.py"
CHECK = '        raise ApplicationError("forbidden", "forbidden", permissions.forbidden_message(operation_id))\n'
EIGHT = ["accounts_me", "inventory_calc", "inventory_scope3_classify", "inventory_scope3_shortlist",
         "reference_assemble", "reference_assemble_electricity", "reference_factors", "reference_sources"]
# (이름, [(파일, 옛 글자, 새 글자)], 순수 층에서 빨개질 것, 업무 층에서 빨개질 것, 업무 층에서 같이 돌려 초록이어야 할 것)
PLANTS = [
    ("1. 표에서 reference_factors 줄을 지운다",
     [(TABLE, '    "reference_factors": Policy("viewer"),\n', "")],
     [CORE + "test_every_authenticated_operation_is_in_the_table"], [], []),
    ("2. 표의 inventory_scope3_classify 를 Policy(\"viewer\") 로 되돌린다",
     [(TABLE, 'Policy("editor", proposed=True)', 'Policy("viewer")')],
     [CELLS, PROPOSED],
     [S3 + "test_a_viewer_cannot_classify_and_nothing_is_called", S3 + "test_the_role_is_checked_before_the_row_limit"], []),
    ("3. 표의 inventory_calc 를 Policy(\"editor\") 로 올린다",
     [(TABLE, '"inventory_calc": Policy("viewer")', '"inventory_calc": Policy("editor")')],
     [CELLS], ["esgapi/inventory/tests/test_api.py::test_a_viewer_can_calculate"], []),
    ("4. reference 의 factors 가 permitted_session 대신 session_of(request) 를 부른다",
     [(REF, "import permitted_session, session_cookie\n", "import permitted_session, session_cookie, session_of\n"),
      (REF, 'permitted_session(request, "reference_factors")', "session_of(request)")],
     [FIRST], [WIRE + "[reference_factors]"], []),
    ("5. inventory 의 calc 가 남의 이름(inventory_scope3_shortlist)으로 읽는다",
     [(INV, 'permitted_session(request, "inventory_calc")', 'permitted_session(request, "inventory_scope3_shortlist")')],
     [FIRST], [WIRE + "[inventory_calc]"], []),
    ("6. documents_confirm 의 _permitted 줄을 _storage() 뒤로 옮긴다",
     [(DOC, '    session = _permitted(request, "core_documents_confirm")\n',
       '    storage = _storage()\n    session = _permitted(request, "core_documents_confirm")\n')],
     [FIRST], [], []),
    ("7. can_create_site 의 몸을 role in (admin, editor) 로 되돌린다",
     [("esgapi/accounts/service/permissions/accounts.py", 'return is_allowed("accounts_sites_create", role)', 'return role in ("admin", "editor")')],
     [ACC + "test_both_read_the_table"], [WIRE + "[accounts_sites_create]"], []),
    ("8. scope3_classify 에서 권한 줄을 행 수 검사 뒤로 옮긴다",
     [(INV, '    session = permitted_session(request, "inventory_scope3_classify")\n', ""),
      (INV, "    rows = [row.model_dump(exclude_unset=True) for row in body.rows]\n    result = services.scope3_classify_output(",
       '    session = permitted_session(request, "inventory_scope3_classify")\n'
       "    rows = [row.model_dump(exclude_unset=True) for row in body.rows]\n    result = services.scope3_classify_output(")],
     [FIRST], [S3 + "test_the_role_is_checked_before_the_row_limit"], []),
    ("9. permitted_session 이 판정을 건너뛰고 늘 세션을 돌려준다",
     [(AUTH, "    if not permissions.is_allowed(operation_id, session.role):\n" + CHECK, "")],
     [ACC + "test_permitted_session_returns_the_session_or_raises_forbidden"],
     [WIRE + f"[{op}]" for op in EIGHT],
     [WIRE + f"[{op}]" for op in ("accounts_sites_create", "accounts_sites_list", "core_documents_confirm", "core_documents_create", "core_documents_get")]),
    ("10. (남의 파일) list_sites 의 권한 줄을 if False: 로",
     [("esgapi/accounts/service/selectors/accounts.py", "    if not can_view_sites(session.role):\n", "    if False:\n")],
     [CORE + "test_the_two_site_routes_reach_the_table_inside_their_selector_and_service"], [WIRE + "[accounts_sites_list]"], []),
    ("11. is_allowed 의 >= 를 > 로",
     [(TABLE, "return _RANK[role] >= _RANK[needed_role(operation_id)]", "return _RANK[role] > _RANK[needed_role(operation_id)]")],
     [CELLS, ACC + "test_the_values_are_what_they_were", ACC + "test_both_read_the_table"], [], []),
]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True, check=True).stdout


def outcome(command: list[str], ids: list[str]) -> tuple[set[str], set[str]]:
    """그 테스트들을 돌려 (빨개진 것, 초록인 것)을 낸다. -rA 의 짧은 요약 줄에서 읽는다."""
    out = subprocess.run([*command, "-q", "-p", "no:cacheprovider", "-rA", *ids], capture_output=True, text=True).stdout
    failed = {line.split(" ")[1] for line in out.splitlines() if line.startswith(("FAILED ", "ERROR "))}
    passed = {line.split(" ")[1] for line in out.splitlines() if line.startswith("PASSED ")}
    return failed & set(ids), passed & set(ids)


before = status()
bad = 0
for name, edits, pure, business, stay_green in PLANTS:
    files = sorted({path for path, _, _ in edits})
    for path in files:
        shutil.copy2(path, KEEP / path.replace("/", "_"))
    try:
        for path, old, new in edits:
            text = Path(path).read_text(encoding="utf-8")
            assert text.count(old) == 1, (name, path, old)
            Path(path).write_text(text.replace(old, new), encoding="utf-8")
        red, _ = outcome(["python", "-m", "pytest", "-m", "not django_db and not security"], pure)
        line = f"순수 {len(red)}/{len(pure)}"
        ok = red == set(pure)
        if WITH_DB and (business or stay_green):
            red_b, green_b = outcome(["scripts/test-business.sh"], business + stay_green)
            line += f" · 업무 {len(red_b & set(business))}/{len(business)}"
            ok = ok and red_b == set(business)
            if stay_green:
                line += f" · 같이 돌려 초록 {len(green_b & set(stay_green))}/{len(stay_green)}"
                ok = ok and green_b >= set(stay_green)
        elif business:
            line += f" · 업무 안 잼(0/{len(business)}. postgres 없음)"
    finally:
        for path in files:
            shutil.copy2(KEEP / path.replace("/", "_"), path)
    same = status() == before
    print(f"  {name} → 빨개진 것: {line} · 되돌린 뒤 git status {'같음' if same else '★ 다름'} · {'맞음' if ok and same else '★ 다름'}")
    bad += not (ok and same)
print(f"  HAND_PLANTED={len(PLANTS) - bad}/{len(PLANTS)}" + ("" if WITH_DB else " (순수 층 쪽만)"))
sys.exit(1 if bad else 0)
PY
  )
}

containers_part() {
  echo; echo "── 컨테이너 (업무·보안 층. postgres 만 띄운다. 통합 층과 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. scripts/worktree-env.sh GP1 으로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  local PROJECT; PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|POSTGRES_PORT)=' .env
  run 'test -n "$PROJECT" && test "$PROJECT" != esg-app'
  run '! lsof -nP -iTCP:"$(env_value POSTGRES_PORT)" -sTCP:LISTEN > /dev/null 2>&1'   # 포트가 비어 있다
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  run 'docker compose up -d --wait postgres 2>&1 | tail -3; exit ${PIPESTATUS[0]}'
  run 'docker compose ps --status running --format "{{.Service}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | tr "\n" " ")" = "postgres "'
  layer "업무 층" "$BUSINESS" "$A/scripts/test-business.sh" -p no:cacheprovider -n 2
  layer "보안 층" "$SECURITY" "$A/scripts/test-security.sh" -p no:cacheprovider
  echo; echo "── 권한 표에 심는 파손 열하나(순수 + 업무. 한 번에 하나, 저장소 밖 사본으로 되돌린다)"
  git status --porcelain > "$T/before-hand.txt"
  run 'WITH_DB=1 hand_planted'
  run 'git status --porcelain | diff - "$T/before-hand.txt"'
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
}

after_commit_part() {
  echo; echo "── 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 4'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do git log -1 --format=%B "$c" | grep -q -x "Ticket: MARC-TICK-69" || { echo "★ 트레일러가 없다: $c"; bad=1; }; done; [ "$bad" = 0 ]'
}

case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --containers) containers_part ;;
  --hand-planted) git status --porcelain > "$T/before-hand.txt"; run 'WITH_DB=0 hand_planted'; run 'git status --porcelain | diff - "$T/before-hand.txt"' ;;
  --after-commit) step_part; pure_extra_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
