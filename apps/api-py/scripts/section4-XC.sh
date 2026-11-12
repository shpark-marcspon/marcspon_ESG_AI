#!/usr/bin/env bash
# 밴드 XC(MARC-TICK-94: 실행·문서 HTTP 경로의 계약 먼저 — 응답 꼴만 openapi 에 싣고 몸은 501)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-XC.sh --step <0~2>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-XC.sh --pure            --step 2 전부 + 심은 파손의 순수 몫
#         apps/api-py/scripts/section4-XC.sh --containers      업무·보안 층 한 번 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-XC.sh --after-commit    --step 2 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 와 rehearsal.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 통합 층은 돌리지 않는다: 이 밴드에는 저장소·큐에 닿는 몸이 없다(발주서 §1-1).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다.
# AI 공급사 호출 0. 네트워크는 uv·docker·pnpm 의 설치뿐이다. bash 전용이다(${PIPESTATUS[0]}).
#
# ★ 컨테이너 층에 들어가는 문은 gate() 다(감독 공지 2026-10-15: 자기 밖 esg-app* 프로젝트 ≤ 2, 빌드 중 0,
#   free ≥ 20%, 1분 부하 < 24). 60초 간격, 최대 30분. 넘기면 띄우지 않는다.
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 「더하기만」(다): 기준의 openapi 의 모든 (자리, 값)이 지금에도 같다. 더해진 열쇠는 이미 있던 자리 안에서는
#   ADDED_INSIDE 의 목록뿐이다(새 경로·새 스키마는 통째로 새 자리라 목록 밖). required·enum 은 기준 ⊆ 지금.
set -u
cd "$(dirname "$0")/../../.."
B=5b85a9a   # 기준 커밋(감독 처분 덧붙임: main 5b85a9a. 발주서의 d128608 뒤에 T1c 병합)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
export LC_ALL=C
MODE="${1:-}"
STEP=2
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-2]) ;; *) echo "사용: $0 --step <0~2>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~2> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다)
ROOT="$(pwd)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
E="$A/esgapi"
TEST_DS=esgapi.config.settings.test_business
# 순수 층의 수: 기준 1,823(5b85a9a 에서 -m "not django_db and not security" 로 셈) + 커밋 ① 의 새 순수 노드.
NEW_PURE_1=2   # test_api_contract.py 의 새 테스트 둘(계약 한 장, 더하기만)
PURE=1823; [ "$STEP" -ge 1 ] && PURE=$((PURE + NEW_PURE_1))
export PURE

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
# 기준에서 바뀐 파일(작업 트리 + 추적 안 된 새 파일 + 지운 파일). 커밋 전에도 뒤에도 같은 답을 낸다.
changed() { { git diff --no-renames --name-only "$B"; git ls-files --others --exclude-standard; } | sort -u; }
# 허용 경로(발주서 §1-2 의 닫힌 목록) 밖에서 바뀐 파일.
outside() {
  changed | grep -v -E \
    -e '^apps/api-py/esgapi/core/service/apis/(runs|documents)\.py$' \
    -e '^apps/api-py/esgapi/core/service/schemas/(runs|documents)\.py$' \
    -e '^apps/api-py/esgapi/core/permissions\.py$' \
    -e '^apps/api-py/esgapi/config/api\.py$' \
    -e '^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$' \
    -e '^apps/api-py/esgapi/config/tests/(test_api_contract|test_request_schemas_reject_bool)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/(test_permissions|test_permissions_wiring|test_documents_api)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/service/(__init__|apis/__init__|apis/test_runs)\.py$' \
    -e '^apps/api-py/tests/security/test_tenant_paths\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-XC\.sh$'
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다. 규칙은 감독 공지(사용자 승인, sid:MARC-TICK-11 노트 14:09):
#   (1) 자기 밖 esg-app* compose 프로젝트가 둘 이하 (2) 빌드 중인 것 없음(build 는 기계 전체 하나)
#   (3) memory_pressure free ≥ 20% · 1분 부하 < 24. 60초마다, 최대 30분. 넘기면 감독에게 「XC 컨테이너 대기」.
gate() {
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d " ")"
    building="$(pgrep -fl "compose.*build|buildx|docker build" | grep -v -c pgrep)"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" -le 2 ] && [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 자기 밖 esg-app* 프로젝트 $others · 빌드 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: 자기 밖 프로젝트 $others · 빌드 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 30분 기다림 — 감독에게 「XC 컨테이너 대기」)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

# config/api.py 의 diff: 더한 줄은 import·add_router 둘, 그 밖의 +/- 줄은 머리 docstring(기준·지금 모두) 안에만.
api_diff_ok() {
  git show "$B:$E/config/api.py" > "$T/api-base.py"
  python3 - "$T/api-base.py" "$E/config/api.py" <<'PY'
import difflib, sys
base = open(sys.argv[1], encoding="utf-8").read().splitlines()
now = open(sys.argv[2], encoding="utf-8").read().splitlines()
ALLOWED = {
    "from esgapi.core.service.apis.runs import router as runs_router",
    'api.add_router("/runs", runs_router, auth=session_cookie)',
}
def doc_end(lines):
    return next(i for i in range(1, len(lines)) if lines[i].rstrip().endswith('"""'))
be, ne = doc_end(base), doc_end(now)
bad, added = [], []
for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=base, b=now, autojunk=False).get_opcodes():
    if tag == "equal":
        continue
    for i in range(i1, i2):
        if i > be:
            bad.append("-" + base[i])
    for j in range(j1, j2):
        if now[j] in ALLOWED:
            added.append(now[j])
        elif j > ne:
            bad.append("+" + now[j])
print(f"  더한 import·add_router {len(added)} (기대 2) · 머리 글 밖의 다른 줄 {len(bad)}")
for b in bad:
    print("  ★", b)
sys.exit(0 if sorted(added) == sorted(ALLOWED) and not bad else 1)
PY
}

echo "── 밴드 XC §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트, 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음), 계약 여섯 kept"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "$PURE passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'

  echo; echo "── 다. 생성물: 코드에서 다시 뽑은 openapi = generated/openapi.json, sha256 적힌 값, 더하기만, apps/web 0줄"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'
  run 'test "$(sha "$A/generated/openapi.json")" = "$(cat "$A/generated/api.d.ts.source-sha256")"; code=$?; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3 && exit $code; exit 1'
  if [ "$STEP" -lt 1 ]; then
    run 'git diff --quiet "$B" -- "$A/generated"'
  else
    run 'git show "$B:$A/generated/openapi.json" > "$T/openapi-base.json" && (cd "$A" && uv run --frozen python - "$T/openapi-base.json" generated/openapi.json <<"PY"
import json, sys
base = json.load(open(sys.argv[1], encoding="utf-8"))
now = json.load(open(sys.argv[2], encoding="utf-8"))
# 이미 있던 자리 안에 더해져도 되는 열쇠(발주서 §0-5 + 감독 처분의 GET /documents. uploadedBy 는 새 스키마
# DocumentListItemOut 에만 있어 여기 없다).
ADDED_INSIDE = {
    "paths./documents.get",
    "paths./documents.post.responses.501",
    "components.schemas.DocumentIn.properties.reportYear",
    "components.schemas.DocumentIn.properties.previousDocumentId",
    "components.schemas.DocumentOut.properties.reportYear",
    "components.schemas.DocumentOut.properties.previousDocumentId",
    "components.schemas.DocumentOut.properties.pageCount",
}
SET_LISTS = {"required", "enum"}
changed, removed, added = [], [], []
def walk(b, n, where):
    if isinstance(b, dict):
        if not isinstance(n, dict):
            changed.append(where); return
        for key, value in b.items():
            if key not in n:
                removed.append(f"{where}.{key}")
            else:
                walk(value, n[key], f"{where}.{key}" if where else key)
        for key in n:
            if key not in b:
                added.append(f"{where}.{key}" if where else key)
    elif isinstance(b, list) and where.rsplit(".", 1)[-1] in SET_LISTS:
        if not isinstance(n, list) or not set(map(json.dumps, b)) <= set(map(json.dumps, n)):
            changed.append(where)
    elif b != n:
        changed.append(where)
walk(base, now, "")
inside = [a for a in added if not (a.startswith("paths.") and a.count(".") == 1) and not (a.startswith("components.schemas.") and a.count(".") == 2)]
new_paths = sum(1 for a in added if a.startswith("paths.") and a.count(".") == 1)
new_schemas = sum(1 for a in added if a.startswith("components.schemas.") and a.count(".") == 2)
print(f"  바뀐 값 {len(changed)} · 지운 열쇠 {len(removed)} · 새 경로 {new_paths} · 새 스키마 {new_schemas} · 있던 자리 안에 더한 열쇠 {len(inside)}")
for x in changed: print("  ★ 바뀜:", x)
for x in removed: print("  ★ 지움:", x)
for x in sorted(inside): print("  더함:", x, "" if x in ADDED_INSIDE else "★ 목록 밖")
grown = [w for w in ("components.schemas.DocumentOut.required",) if len(now["components"]["schemas"]["DocumentOut"].get("required", [])) != len(base["components"]["schemas"]["DocumentOut"].get("required", []))]
print("  required 가 늘어난 자리:", grown)
sys.exit(0 if not changed and not removed and set(inside) <= ADDED_INSIDE else 1)
PY
)'
  fi
  run 'git diff --quiet "$B" -- apps/web'

  echo; echo "── 라. 마이그레이션(makemigrations 가 낼 것 없음, 마이그레이션 파일 diff 0)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'n="$(changed | grep -c "/migrations/")"; echo "  바뀐·새 마이그레이션 파일: $n"; [ "$n" = 0 ]'

  echo; echo "── 마. 경계(닫힌 목록, 지운 파일 0, config/api.py·permissions.py 의 diff 꼴)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'n="$(git diff --no-renames --name-only --diff-filter=D "$B" | wc -l | tr -d " ")"; echo "  지운 파일: $n"; [ "$n" = 0 ]'
  if [ "$STEP" -ge 1 ]; then run 'api_diff_ok'; fi
  run 'n="$(git diff -U0 "$B" -- "$E/core/permissions.py" | grep -c -E "^-[^-]")"; echo "  permissions.py 의 지운 줄 $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- "$E/core/exceptions.py" "$E/core/schemas.py" "$E/core/models.py" "$E/core/tenancy" "$E/core/service/services" "$E/core/service/selectors" "$E/greenwash" "$A/tests/support" "$A/tests_integration" "$A/pyproject.toml" "$A/uv.lock" "$A/.importlinter" scripts compose.yaml && test ! -e "$E/runs"'

  echo; echo "── 나. 수집: 사라진 노드 0, 새 노드는 EXPECTED_NEW 와 글자로 같다(기준의 노드 ID 는 git archive 사본에서)"
  mkdir -p "$T/base"
  git archive "$B" "$A" compose.yaml | tar -x -C "$T/base"
  ln -s "$ROOT/.env" "$T/base/.env"
  (cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt")
  (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt")
  comm -23 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/gone.txt"; comm -13 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/new.txt"
  expected_new | sort > "$T/new-expected.txt"
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · 사라짐 $(wc -l < "$T/gone.txt" | tr -d " ") · 새로 $(wc -l < "$T/new.txt" | tr -d " ")"; sed "s/^/  사라짐: /" "$T/gone.txt"; [ "$b" = 2258 ] && [ ! -s "$T/gone.txt" ] && diff "$T/new-expected.txt" "$T/new.txt"'
  run 'for m in "not django_db and not security" "django_db and not security" "security"; do (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "$m" 2> /dev/null | tail -1 | sed "s/^/  [$m] /"); done'

  if [ "$STEP" -ge 1 ]; then
    echo; echo "── 바. 셈(AST): apis/runs.py 의 error_response(501 은 4 곳, selectors·services·models import 0, 새 operationId 의 꼴"
    run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, json, re, sys
src = open("esgapi/core/service/apis/runs.py", encoding="utf-8").read()
tree = ast.parse(src)
calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Name) and n.func.id == "error_response"
         and n.args and isinstance(n.args[0], ast.Constant) and n.args[0].value == 501]
imports = [n.module if isinstance(n, ast.ImportFrom) else a.name for n in ast.walk(tree) if isinstance(n, ast.Import | ast.ImportFrom) for a in n.names]
bad_imports = [m for m in imports if m and re.search(r"(^|\.)(selectors|services|models)(\.|$)", m)]
doc = json.load(open("generated/openapi.json", encoding="utf-8"))
ops = {op["operationId"] for item in doc["paths"].values() for op in item.values()}
new = {"runs_create", "runs_list", "runs_get", "runs_file_get", "core_documents_versions", "core_documents_list"}
shape = [o for o in new if re.fullmatch(r"(runs|core_documents)_[a-z_]+", o) is None]
print(f"  error_response(501 {len(calls)} 곳 · selectors·services·models import {bad_imports} · 새 operationId 여섯이 openapi 에 {len(new & ops)} · 꼴 어김 {shape} · 동작 수 {len(ops)}")
sys.exit(0 if (len(calls), bad_imports, len(new & ops), shape, len(ops)) == (4, [], 6, [], 23) else 1)
PY
)'
    run 'n="$(git grep -c -E "error_response\(501" -- "$E/core/service/apis/documents.py" | cut -d: -f2)"; echo "  apis/documents.py 의 error_response(501: ${n:-0} 곳 (기대 3: 만들기의 갈래·목록·versions)"; [ "${n:-0}" = 3 ]'
  fi

  echo; echo "── 사. 테스트 자리(check_test_layout.py) 와 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다)"
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; exit $code)'
  if [ "$STEP" -ge 2 ]; then
    run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py --list 2>&1 | grep "service/apis/test_runs" | sed "s/^/  /"; uv run --frozen python scripts/check_test_layout.py --list 2>&1 | grep "service/apis/test_runs" | grep -q "core/service/apis/runs.py")'
  fi
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$B" -- . ":!$A/scripts/section4-XC.sh" ":!$A/scripts/planted-breaks-XC.sh" ":!$A/generated" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-XC\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+.*($marks)" "$T/all.diff")"; echo "  더한 줄 $plus"; grep -E "^\+.*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" = 0 ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫(P1~P6)"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-XC.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=6/6" && exit $code; exit 1'
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
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  if [ "$code" -ne 0 ]; then
    grep -E "^(FAILED|ERROR)" "$T/layer.txt" | head -30
    memory_pressure | grep percentage
  fi
}

# 층마다 기대하는 「<n> passed」: 기준 5b85a9a 의 수집(업무 354 · 보안 81) + 이 밴드의 새 노드(EXPECTED_NEW 의 층별 셈).
NEW_BUSINESS=29   # service/apis/test_runs 19 + test_documents_api 4 + test_permissions_wiring 의 새 매개변수 6
NEW_SECURITY=12   # test_tenant_paths: contract_only 의 501 여섯 + 401 의 새 매개변수 여섯
BUSINESS=$((354 + NEW_BUSINESS))
SECURITY=$((81 + NEW_SECURITY))

containers_part() {
  echo; echo "── 아. 컨테이너 (업무·보안 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh XC 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  local PROJECT; PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test -n "$PROJECT" && test "$PROJECT" != esg-app'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  layer "업무 층" "$BUSINESS" "$A/scripts/test-business.sh" -n 2
  layer "보안 층" "$SECURITY" "$A/scripts/test-security.sh"
  echo; echo "── 아(덧). 심은 파손의 컨테이너 몫(P7·P8)"
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-XC.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=2/2" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 자. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 3'
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-94" "Derives-from: MARC-TICK-74"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
}

# 이 밴드가 더하는 노드(발주서 §3-2 의 이름 + 있는 매개변수 테스트의 새 매개변수). 커밋마다 늘어난다.
expected_new() {
  [ "$STEP" -ge 1 ] || return 0
  cat <<'NEW'
esgapi/config/tests/test_api_contract.py::test_existing_operations_only_gained
esgapi/config/tests/test_api_contract.py::test_the_run_and_version_operations_are_the_contract_sheet
NEW
  [ "$STEP" -ge 2 ] || return 0
  cat <<'NEW'
esgapi/core/tests/service/apis/test_runs.py::test_a_bad_run_body_is_400[body0]
esgapi/core/tests/service/apis/test_runs.py::test_a_bad_run_body_is_400[body1]
esgapi/core/tests/service/apis/test_runs.py::test_a_bad_run_body_is_400[body2]
esgapi/core/tests/service/apis/test_runs.py::test_a_bad_run_body_is_400[body3]
esgapi/core/tests/service/apis/test_runs.py::test_a_bad_run_body_is_400[body4]
esgapi/core/tests/service/apis/test_runs.py::test_a_viewer_cannot_create_a_run
esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[core_documents_list]
esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[core_documents_versions]
esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_create]
esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_file_get]
esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_get]
esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_list]
esgapi/core/tests/service/apis/test_runs.py::test_the_document_id_types_are_checked_per_route
esgapi/core/tests/service/apis/test_runs.py::test_without_a_session_it_is_401[core_documents_list]
esgapi/core/tests/service/apis/test_runs.py::test_without_a_session_it_is_401[core_documents_versions]
esgapi/core/tests/service/apis/test_runs.py::test_without_a_session_it_is_401[runs_create]
esgapi/core/tests/service/apis/test_runs.py::test_without_a_session_it_is_401[runs_file_get]
esgapi/core/tests/service/apis/test_runs.py::test_without_a_session_it_is_401[runs_get]
esgapi/core/tests/service/apis/test_runs.py::test_without_a_session_it_is_401[runs_list]
esgapi/core/tests/test_documents_api.py::test_a_create_with_nulls_is_the_same_201
esgapi/core/tests/test_documents_api.py::test_a_create_with_report_year_or_previous_is_501_and_writes_nothing[previousDocumentId]
esgapi/core/tests/test_documents_api.py::test_a_create_with_report_year_or_previous_is_501_and_writes_nothing[reportYear]
esgapi/core/tests/test_documents_api.py::test_the_new_document_fields_are_null
esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden[core_documents_list]
esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden[core_documents_versions]
esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden[runs_create]
esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden[runs_file_get]
esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden[runs_get]
esgapi/core/tests/test_permissions_wiring.py::test_raising_the_cell_makes_that_route_forbidden[runs_list]
tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /documents]
tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /documents/{document_id}/versions]
tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /runs]
tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /runs/{run_id}]
tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /runs/{run_id}/files/{name}]
tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[POST /runs]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /documents]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /documents/{document_id}/versions]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /runs]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /runs/{run_id}]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /runs/{run_id}/files/{name}]
tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[POST /runs]
NEW
}
export -f sha changed outside gate env_value expected_new api_diff_ok 2> /dev/null
export T A E B TEST_DS STEP
case "$MODE" in
  --step) step_part ;;
  --pure) step_part; pure_extra_part ;;
  --containers) containers_part ;;
  --after-commit) step_part; after_commit_part ;;
esac
echo
echo "── 바뀐 파일 수 (기준 $B 대비, 새 파일 포함): $(changed | wc -l | tr -d " ")"
echo "0 이 아닌 EXIT: $FAILS"
[ "$FAILS" = 0 ]
