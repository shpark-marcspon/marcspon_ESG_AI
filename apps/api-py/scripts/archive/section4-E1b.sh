#!/usr/bin/env bash
# 밴드 E1b(MARC-TICK-90: 요청 단위 트랜잭션을 걷고 EDK 리뉴얼 꼴 — 쓰기는 service 안 atomic, 여러 표는 actions 의
# @transaction.atomic, 큐·외부 호출은 on_commit 또는 트랜잭션 밖)의 §4 자기검증.
#   사용: apps/api-py/scripts/section4-E1b.sh --step <0~4>      그 커밋까지의 부분(커밋마다 돌린다)
#         apps/api-py/scripts/section4-E1b.sh --pure            --step 4 전부 + 심은 파손의 순수 몫
#         apps/api-py/scripts/section4-E1b.sh --containers      업무·보안·통합 층 한 번 + 심은 파손의 컨테이너 몫 + 내리기
#         apps/api-py/scripts/section4-E1b.sh --after-commit    --step 4 전부 + 커밋된 모습(작업 트리 0줄, 커밋 수, 트레일러)
# 전부 EXIT=0 이어야 한다. 끝 줄 「0 이 아닌 EXIT: <n>」, 하나라도 아니면 스크립트가 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(전량은 감독이 병합 뒤 main 에서).
# 다루는 컨테이너·볼륨·이미지는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것뿐이다(바탕 이미지는 지우지 않는다).
# AI 공급사 호출 0. 브로커는 compose 의 queue(sqs://queue:9324)뿐이다. 네트워크는 uv·docker·pnpm 의 설치뿐이다.
# bash 전용이다(${PIPESTATUS[0]}). git grep -E 에 \s 를 쓰지 않는다([[:space:]]).
#
# ★ 컨테이너 층은 기계 전체에서 한 번에 하나다: 다른 esg-app* 컨테이너가 0 이 될 때까지 기다린다(60초 간격, 최대 30분).
# ★ makemigrations --check 는 호스트에서 test_business 설정으로 돈다(DB 없이. 닿지 않는 주소라 RuntimeWarning 한 줄이 난다. 기대다).
# ★ openapi 는 코드에서 다시 뽑아(표준 출력) generated/openapi.json 과 바이트로 견준다. 저장소에 쓰지 않는다.
# ★ 코드의 셈은 AST 로 한다(글자 셈은 docstring 을 문다 — 발주서 개정 1 의 B3).
set -u
cd "$(dirname "$0")/../../.."
B=efc5e3b   # 기준 커밋(발주서 §1-1, 개정 1)
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"   # verify.sh 의 pnpm 이 Node 22 를 쓴다
export LC_ALL=C   # sort 와 diff 가 같은 차례를 쓴다
MODE="${1:-}"
STEP=4
case "$MODE" in
  --step) STEP="${2:-}"; case "$STEP" in [0-4]) ;; *) echo "사용: $0 --step <0~4>" >&2; exit 2 ;; esac ;;
  --pure | --containers | --after-commit) ;;
  *) echo "사용: $0 --step <0~4> | --pure | --containers | --after-commit" >&2; exit 2 ;;
esac

T="$(mktemp -d)"   # 저장소 밖. 기록을 둔다(지우지 않는다. 운영체제가 치운다)
ROOT="$(pwd)"
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
A=apps/api-py
E="$A/esgapi"
TEST_DS=esgapi.config.settings.test_business
FLOW_FN=test_readyz_is_503_while_the_db_is_down_and_recovers
export A E B T TEST_DS FLOW_FN STEP

# 층마다의 수(기준 efc5e3b 의 수집: 순수 1,799 · 업무 354 · 보안 81 · 통합 17).
NEW_PURE_3=3   # core/tests/tenancy/test_middleware.py(커밋 ③)
NEW_PURE_4=14  # core/tests/test_transaction_rules.py(커밋 ④: 파일마다 8 + 규칙 다섯 + 자기 시험 하나)
PURE=1799; [ "$STEP" -ge 3 ] && PURE=$((PURE + NEW_PURE_3)); [ "$STEP" -ge 4 ] && PURE=$((PURE + NEW_PURE_4))
BUSINESS=355     # 354 − 사라짐 3 + 새 이름 3 + 새 1(test_a_confirm_that_fails_midway_leaves_nothing)
SECURITY=85      # 81 − 사라짐 4 + 새 이름 4 + 새 4(head 밖 · 되돌린 블록의 갈고리 · 오류 응답의 기록 줄 · LLM 밖)
INTEGRATION=17   # 이름 그대로(함수 하나의 몸만 고친다)
PURE_PLANTED="8/8"; CONTAINER_PLANTED="7/7"   # planted-breaks-E1b.sh 의 순수 몫 P1~P4·P6~P9, 컨테이너 몫 P1b·P2·P3·P4·P5·P8 업무·P8 보안
export PURE_PLANTED CONTAINER_PLANTED
C1_SUBJECT='feat(core): 호출 기록이 트랜잭션 밖이면 스스로 짧은 트랜잭션을 열어 쓴다'

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
    -e '^apps/api-py/esgapi/core/tenancy/middleware\.py$' \
    -e '^apps/api-py/esgapi/core/tenancy/__init__\.py$' \
    -e '^apps/api-py/esgapi/core/__init__\.py$' \
    -e '^apps/api-py/esgapi/config/settings/base\.py$' \
    -e '^apps/api-py/esgapi/core/llm/sink_db\.py$' \
    -e '^apps/api-py/esgapi/core/llm/setup\.py$' \
    -e '^apps/api-py/esgapi/core/management/commands/llm_call\.py$' \
    -e '^apps/api-py/esgapi/core/service/services/documents\.py$' \
    -e '^apps/api-py/esgapi/accounts/service/services/accounts\.py$' \
    -e '^apps/api-py/esgapi/core/resources/queue\.py$' \
    -e '^apps/api-py/esgapi/core/resources/storage\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_transaction_rules\.py$' \
    -e '^apps/api-py/esgapi/core/tests/tenancy/(__init__|test_middleware)\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_llm_sink_db\.py$' \
    -e '^apps/api-py/esgapi/core/tests/test_documents_services\.py$' \
    -e '^apps/api-py/tests/security/(test_tenant_boundary|test_documents|test_llm_log)\.py$' \
    -e '^apps/api-py/tests/security/test_request_transactions\.py$' \
    -e '^apps/api-py/tests_integration/test_flow\.py$' \
    -e '^apps/api-py/esgapi/inventory/tests/test_api\.py$' \
    -e '^apps/api-py/scripts/(section4|planted-breaks)-E1b\.sh$'
}
# 기계가 바쁠 때 컨테이너 앞에서 기다린다: 다른 esg-app* 컨테이너 0, verify.lock 없음, 메모리 free 20% 이상, 1분 부하 12 미만.
# 60초마다, 최대 30분. verify.lock 은 main 작업 트리의 것(워크트리가 같이 쓰는 git 공통 폴더).
gate() {
  local tries=0 free load lock others
  lock="$(git rev-parse --path-format=absolute --git-common-dir)/verify.lock"
  while :; do
    others="$(docker ps --format '{{.Names}}' | grep -c '^esg-app')"
    free="$(memory_pressure 2>/dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(uptime | sed -n 's/.*load averages*: *\([0-9.]*\).*/\1/p')"
    if [ "$others" = 0 ] && [ ! -e "$lock" ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 12 ]; then
      echo "  (문: esg-app* 컨테이너 0 · verify.lock 없음 · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: esg-app* 컨테이너 $others · verify.lock $([ -e "$lock" ] && echo 있음 || echo 없음) · free ${free:-?}% · 1분 부하 ${load:-?} · 30분 기다림)"; return 1; }
    tries=$((tries + 1)); sleep 60
  done
}

echo "── 밴드 E1b §4 · $MODE${2:+ $2} · 기준 $B · HEAD $(git rev-parse --short HEAD) · $(uptime | sed 's/.*load/load/')"

step_part() {
  local started=$SECONDS
  echo; echo "── 가. 빠른 게이트와 순수 층의 끝 줄($PURE passed, 건너뛴 것 없음)"
  run 'scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; grep -E "passed|failed|error|kept|broken" "$T/fast.log" | tail -12; tail -1 "$T/fast.log"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
  echo "  (--fast 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run '(cd "$A" && uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" > "$T/pure.txt" 2>&1; code=$?; last="$(tail -1 "$T/pure.txt")"; echo "  $last"; case "$last" in "'"$PURE"' passed"*) ;; *) exit 1 ;; esac; echo "$last" | grep -q -E "skipped|xfailed|xpassed|warning" && exit 1; exit $code)'
  run '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; tail -1 "$T/lint.txt"; test "$(tail -1 "$T/lint.txt")" = "Contracts: 6 kept, 0 broken." && exit $code; exit 1)'
  run '(cd "$A" && uv run --frozen python scripts/check_test_layout.py > "$T/layout.txt" 2>&1; code=$?; tail -2 "$T/layout.txt"; exit $code)'

  echo; echo "── 다. generated/ 3파일이 바이트 동일, 코드에서 다시 뽑은 openapi 도 그 파일과 바이트 동일, apps/web 0줄"
  run 'git diff --quiet "$B" -- "$A/generated" apps/web && test -z "$(git ls-files --others --exclude-standard -- "$A/generated" apps/web)"'
  run 'for f in openapi.json api.d.ts api.d.ts.source-sha256; do test "$(sha "$A/generated/$f")" = "$(git show "$B:$A/generated/$f" | shasum -a 256 | cut -d" " -f1)" || { echo "★ 다르다: $f"; exit 1; }; done; test "$(git ls-files "$A/generated" | wc -l | tr -d " ")" = 3'
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py export_openapi 2> "$T/export.err" > "$T/openapi.json"; code=$?; tail -2 "$T/export.err"; cmp "$T/openapi.json" generated/openapi.json && exit $code; exit 1)'

  echo; echo "── 라. 마이그레이션(makemigrations 가 낼 것 없음, 새·바뀐 마이그레이션 0)"
  run '(cd "$A" && DJANGO_SETTINGS_MODULE=$TEST_DS uv run --frozen python manage.py makemigrations --check --dry-run > "$T/mm.txt" 2>&1; code=$?; echo "  RuntimeWarning 줄 $(grep -c "RuntimeWarning" "$T/mm.txt")"; tail -1 "$T/mm.txt"; test "$(tail -1 "$T/mm.txt")" = "No changes detected" && exit $code; exit 1)'
  run 'n="$(changed | grep -c "/migrations/")"; echo "  바뀐·새 마이그레이션 파일: $n (기대 0)"; [ "$n" = 0 ]'

  echo; echo "── 마. 경계(닫힌 목록, 지운 파일 0, X1·E2·T1c 의 파일 0줄, 통합 test_flow.py 는 함수 하나의 몸만)"
  run 'n="$(outside | wc -l | tr -d " ")"; outside; echo "  허용 경로 밖에서 바뀐 파일: $n"; [ "$n" = 0 ]'
  run 'n="$(git diff --no-renames --name-only --diff-filter=D "$B" | wc -l | tr -d " ")"; echo "  지운 파일: $n"; [ "$n" = 0 ]'
  run 'git diff --quiet "$B" -- "$E/core/service/services/jobs.py" "$E/core/service/selectors" "$E/reconcile" "$E/core/management/commands/requeue_jobs.py" "$E/core/exceptions.py" "$E/core/schemas.py" "$E/config/api.py" "$E/core/observability" "$A/tests/support" "$E/greenwash" "$E/core/isolation" "$E/core/models.py" "$E/config/celery.py" "$E/config/env.py" "$A/pyproject.toml" "$A/uv.lock" "$A/.importlinter" compose.yaml .env.example README.md scripts docker infra || exit 1; n="$(changed | grep -c -E "/service/(apis|actions)/|/runs/")"; echo "  */service/apis·actions, runs 의 바뀐·새 파일: $n"; [ "$n" = 0 ]'
  run '(cd "$A" && git diff -U0 "$B" -- tests_integration/test_flow.py > "$T/flow.diff"; git show "$B:$A/tests_integration/test_flow.py" > "$T/flow-base.py"; uv run --frozen python - "$T/flow-base.py" tests_integration/test_flow.py "$T/flow.diff" <<"PY"
import ast, os, re, sys
name = os.environ["FLOW_FN"]
def span(path):
    tree = ast.parse(open(path, encoding="utf-8").read())
    fns = [n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name]
    assert len(fns) == 1, path
    fn = fns[0]
    sig = ast.dump(fn.args) + ast.dump(ast.List(fn.decorator_list))
    head = max(n.end_lineno or 0 for n in [*fn.args.args, *([fn.returns] if fn.returns else [])])
    return head + 1, fn.end_lineno, sig  # 몸 = 정의 줄 다음 줄부터(몸 첫머리의 주석 포함)
b0, b1, bsig = span(sys.argv[1]); n0, n1, nsig = span(sys.argv[2])
bad = 0; hunks = 0
for line in open(sys.argv[3], encoding="utf-8"):
    m = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
    if not m:
        continue
    hunks += 1
    os_, oc, ns, nc = int(m[1]), int(m[2] or 1), int(m[3]), int(m[4] or 1)
    old_ok = oc == 0 or (b0 <= os_ and os_ + oc - 1 <= b1)
    new_ok = nc == 0 or (n0 <= ns and ns + nc - 1 <= n1)
    if not (old_ok and new_ok):
        print("  ★ 함수 몸 밖의 덩어리:", line.strip()); bad = 1
same = "그대로" if bsig == nsig else "★ 다르다"
print(f"  test_flow.py 의 덩어리 {hunks} · 함수 몸 기준 {b0}-{b1} → 지금 {n0}-{n1} · 정의 줄(인자·꾸밈) {same}")
want = int(os.environ["STEP"]) >= 3
sys.exit(0 if not bad and bsig == nsig and (hunks > 0) == want else 1)
PY
)'

  echo; echo "── 나. 수집: 사라진 노드는 이름 바꿈 목록과 글자로 같고, 새 노드는 정해진 이름뿐(기준의 노드 ID 는 git archive 사본에서)"
  mkdir -p "$T/base"
  git archive "$B" "$A" | tar -x -C "$T/base"
  (cd "$T/base/$A" && PYTHONPATH=. "$ROOT/$A/.venv/bin/python" -m pytest --collect-only -q -p no:cacheprovider 2> /dev/null | grep "::" | sort > "$T/base-nodeids.txt")
  (cd "$A" && uv run --frozen pytest --collect-only -q -p no:cacheprovider 2> "$T/collect.err" | grep "::" | sort > "$T/nodeids.txt")
  comm -23 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/gone.txt"; comm -13 "$T/base-nodeids.txt" "$T/nodeids.txt" > "$T/new.txt"
  expected_gone | sort > "$T/gone-expected.txt"; expected_new | sort > "$T/new-expected.txt"
  run 'b="$(wc -l < "$T/base-nodeids.txt" | tr -d " ")"; n="$(wc -l < "$T/nodeids.txt" | tr -d " ")"; echo "  기준 $b · 지금 $n · 사라진 것 $(wc -l < "$T/gone.txt" | tr -d " ") · 새 것 $(wc -l < "$T/new.txt" | tr -d " ")"; sed "s/^/  사라짐: /" "$T/gone.txt"; [ "$b" = 2234 ] && diff "$T/gone-expected.txt" "$T/gone.txt"'
  run 'sed "s/^/  새로: /" "$T/new.txt"; diff "$T/new-expected.txt" "$T/new.txt"'
  run '(cd "$A" && for m in "not django_db and not security" django_db security; do printf "  %-32s %s\n" "$m" "$(uv run --frozen pytest --collect-only -q -p no:cacheprovider -m "$m" 2> /dev/null | grep -c "::")"; done) | tee "$T/layers.txt"; b="$(sed -n "2p" "$T/layers.txt" | awk "{print \$NF}")"; s="$(sed -n "3p" "$T/layers.txt" | awk "{print \$NF}")"; want_b=354; want_s=81; [ "$STEP" -ge 1 ] && want_s=81; [ "$STEP" -ge 2 ] && want_b=355; [ "$STEP" -ge 3 ] && want_s='"$SECURITY"'; echo "  기대: 업무 $want_b · 보안 $want_s"; [ "$b" = "$want_b" ] && [ "$s" = "$want_s" ]'

  echo; echo "── 바. 셈(제품 = esgapi 의 tests·migrations 밖, AST)"
  run '(cd "$A" && uv run --frozen python - <<"PY"
import ast, os, pathlib, subprocess, sys
step = int(os.environ["STEP"])
base = os.environ["B"]

def tree_of(src):
    return ast.parse(src)

def blocks(tree):
    """with 항목의 transaction.atomic(…) 과 @transaction.atomic(…) 꾸밈의 수."""
    def is_atomic(node):
        f = node.func if isinstance(node, ast.Call) else node
        return isinstance(f, ast.Attribute) and f.attr == "atomic" and isinstance(f.value, ast.Name) and f.value.id == "transaction"
    n = 0
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            n += sum(is_atomic(item.context_expr) for item in node.items)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            n += sum(is_atomic(d) for d in node.decorator_list)
    return n

def product():
    for path in sorted(pathlib.Path("esgapi").rglob("*.py")):
        if "tests" in path.parts or "migrations" in path.parts:
            continue
        yield path

on_commit = durable = 0
counts = {}
for path in product():
    tree = tree_of(path.read_text(encoding="utf-8"))
    counts[str(path)] = blocks(tree)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr == "on_commit":
            on_commit += 1
        if isinstance(node, ast.keyword) and node.arg == "durable" and isinstance(node.value, ast.Constant) and node.value.value is True:
            durable += 1
base_counts = {}
for path in counts:
    try:
        src = subprocess.run(["git", "show", f"{base}:apps/api-py/{path}"], capture_output=True, text=True, check=True).stdout
    except subprocess.CalledProcessError:
        src = ""
    base_counts[path] = blocks(tree_of(src)) if src else 0

want = {
    "esgapi/core/service/services/documents.py": 2 if step >= 2 else 0,
    "esgapi/accounts/service/services/accounts.py": 2 if step >= 2 else 1,
    "esgapi/core/tenancy/middleware.py": 0 if step >= 3 else 1,
    "esgapi/core/management/commands/llm_call.py": 0 if step >= 1 else 1,
}
bad = 0
for path in sorted(set(counts) | set(base_counts)):
    b, n = base_counts.get(path, 0), counts.get(path, 0)
    if b or n:
        expect = want.get(path, b)
        mark = "" if n == expect else "  ★ 기대 %d" % expect
        print(f"  {path}: 블록 {b} → {n}{mark}")
        bad |= n != expect
print(f"  transaction.on_commit 호출 {on_commit} (기대 1) · durable=True {durable} (기대 3)")
bad |= on_commit != 1 or durable != 3

def names(path):
    tree = tree_of(pathlib.Path(path).read_text(encoding="utf-8"))
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            out.add(node.id)
        elif isinstance(node, ast.Attribute):
            out.add(node.attr)
        elif isinstance(node, ast.alias):
            out.add(node.asname or node.name.split(".")[-1])
        elif isinstance(node, (ast.Import, ast.ImportFrom)) and isinstance(node, ast.ImportFrom) and node.module:
            out.update(node.module.split("."))
    return out

if step >= 1:
    s = {"in_atomic_block"} & names("esgapi/core/llm/sink_db.py")
    l = {"atomic", "transaction"} & names("esgapi/core/management/commands/llm_call.py")
    print(f"  sink_db.py 의 in_atomic_block {sorted(s)} · llm_call.py 의 atomic·transaction {sorted(l)} (기대 둘 다 [])")
    bad |= bool(s or l)
if step >= 3:
    m = {"transaction", "atomic", "set_rollback", "DatabaseError", "unavailable"} & names("esgapi/core/tenancy/middleware.py")
    t = [str(p) for p in product() if "TENANT_TX_EXEMPT_PATHS" in p.read_text(encoding="utf-8")]
    print(f"  middleware.py 코드의 transaction·atomic·set_rollback·DatabaseError·unavailable {sorted(m)} · TENANT_TX_EXEMPT_PATHS 글자 {t} (기대 둘 다 [])")
    bad |= bool(m or t)
sys.exit(1 if bad else 0)
PY
)'

  echo; echo "── 사(덧). 깎은 것 0(건너뛰기·경고 예외·무시 표시가 늘지 않았다)"
  run 'marks="xfail|mark\.skip|skipif|filterwarnings|noqa|type: ignore|pyright: ignore"; git diff "$B" -- . ":!$A/scripts/section4-E1b.sh" ":!$A/scripts/planted-breaks-E1b.sh" > "$T/all.diff"; for f in $(git ls-files --others --exclude-standard | grep -v -E "scripts/(section4|planted-breaks)-E1b\.sh$"); do sed "s/^/+/" "$f"; done >> "$T/all.diff"; plus="$(grep -c -E "^\+.*($marks)" "$T/all.diff")"; echo "  더한 줄 $plus (이 밴드의 스크립트 둘은 뺀다: 무늬를 글자로 적은 줄이 있다)"; grep -E "^\+.*($marks)" "$T/all.diff" | cut -c1-200; [ "$plus" = 0 ]'
}

pure_extra_part() {
  echo; echo "── 자(순수). 심은 파손의 순수 몫"
  if [ ! -x "$A/scripts/planted-breaks-E1b.sh" ]; then echo "★ planted-breaks-E1b.sh 가 없다(커밋 ⑤ 의 것)"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return; fi
  git status --porcelain > "$T/before-planted.txt"
  run '"$A/scripts/planted-breaks-E1b.sh" --pure > "$T/planted.txt" 2>&1; code=$?; cat "$T/planted.txt"; test "$(tail -1 "$T/planted.txt")" = "PLANTED=$PURE_PLANTED" && exit $code; exit 1'
  run 'git status --porcelain | diff - "$T/before-planted.txt"'
}

# 한 층을 돌리고 EXIT 를 찍는다. 끝 줄이 「<건수> passed」로 시작해야 한다. 다시 돌리지 않는다.
layer() { # <이름> <건수> <명령…>
  local name="$1" want="$2" code started=$SECONDS last
  shift 2
  echo; echo "▶ $*"
  "$@" > "$T/layer.txt" 2>&1; code=$?
  cp "$T/layer.txt" "$T/layer-$name.txt"
  tail -3 "$T/layer.txt"
  last="$(tail -1 "$T/layer.txt")"
  case "$last" in "$want passed"*) ;; *) echo "★ 끝 줄이 「$want passed」로 시작하지 않는다"; code=1 ;; esac
  echo "EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
  echo "  ($name 에 걸린 시간 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/') · 기록 $T/layer-$name.txt)"
  if [ "$code" -ne 0 ]; then
    grep -E "^(FAILED|ERROR)" "$T/layer.txt" | head -30
    memory_pressure | grep percentage
    [ "$name" = "통합" ] && docker compose logs --no-color --tail 80 api-py migrate-py worker-py queue parser
  fi
}

containers_part() {
  echo; echo "── 아. 컨테이너 (업무·보안·통합 층. 전량 verify.sh 가 아니다)"
  test -f .env || { echo "★ .env 가 없다. ~/scripts/worktree-env.sh E1b 로 만든다"; echo "EXIT=1"; FAILS=$((FAILS + 1)); return 1; }
  local PROJECT; PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
  export PROJECT
  grep -E '^(COMPOSE_PROJECT_NAME|API_PORT|API_PY_PORT|POSTGRES_PORT|STORAGE_PORT)=' .env
  run 'test "$PROJECT" = esg-app-e1b'
  local port busy=0
  for port in $(env_value API_PORT) $(env_value API_PY_PORT) $(env_value POSTGRES_PORT) $(env_value STORAGE_PORT); do
    if lsof -nP -iTCP:"$port" -sTCP:LISTEN > /dev/null 2>&1; then echo "★ 포트 $port 를 누가 쓰고 있다"; busy=1; fi
  done
  run '[ "'"$busy"'" = 0 ]'                                                                # 포트 넷이 비어 있다
  run 'gate'
  [ "$FAILS" = 0 ] || { echo "★ 띄우지 않는다(위 줄이 0 이 아니다)"; return 1; }
  EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)"
  export EDK_JWT_PUBLIC_KEY
  local started=$SECONDS
  # api-py·worker-py 가 postgres·migrate-py·storage·queue 를 끌고 뜬다. TS 의 api·worker·redis 는 띄우지 않는다.
  run 'docker compose up -d --build --wait api-py worker-py parser 2>&1 | tail -5 ; test "${PIPESTATUS[0]}" = 0'
  echo "  (짓고 띄우는 데 $((SECONDS - started))초 · $(uptime | sed 's/.*load/load/'))"
  run 'docker compose ps --format "{{.Service}} {{.State}}" | sort | tr "\n" ";"; echo; test "$(docker compose ps --status running --format "{{.Service}}" | grep -c -E "^(api-py|worker-py|parser|postgres|storage|queue)$")" = 6'
  run 'docker compose exec -T worker-py python -c "from urllib.parse import urlsplit; from esgapi.config.celery import app; print(app.conf.broker_url.split(\":\")[0]); assert urlsplit(app.conf.broker_url).hostname == \"queue\""'   # 브로커는 로컬 흉내
  layer "업무" "$BUSINESS" "$A/scripts/test-business.sh" -n 2
  layer "보안" "$SECURITY" "$A/scripts/test-security.sh"
  layer "통합" "$INTEGRATION" "$A/scripts/test-integration.sh" -s
  run 'n="$(docker compose logs --no-color worker-py queue api-py | grep -c -i "amazonaws")"; echo "  기록의 amazonaws 줄: $n"; [ "$n" = 0 ]'
  if [ -x "$A/scripts/planted-breaks-E1b.sh" ]; then
    echo; echo "── 아(덧). 심은 파손의 컨테이너 몫"
    git status --porcelain > "$T/before-planted.txt"
    run '"$A/scripts/planted-breaks-E1b.sh" --containers > "$T/planted-c.txt" 2>&1; code=$?; cat "$T/planted-c.txt"; test "$(tail -1 "$T/planted-c.txt")" = "PLANTED=$CONTAINER_PLANTED" && exit $code; exit 1'
    run 'git status --porcelain | diff - "$T/before-planted.txt"'
  fi
  run 'docker compose down -v --remove-orphans 2>&1 | tail -3 ; test "${PIPESTATUS[0]}" = 0'
  run 'n="$(docker ps -aq --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; v="$(docker volume ls -q --filter "label=com.docker.compose.project=$PROJECT" | wc -l | tr -d " ")"; echo "  남은 컨테이너 $n · 볼륨 $v"; [ "$n$v" = 00 ]'
  # 이 워크트리의 이미지를 치운다(다른 워크트리의 것과 바탕 이미지는 건드리지 않는다).
  run 'docker images --format "{{.Repository}}:{{.Tag}}" | grep "^$PROJECT/" | xargs -n 20 docker image rm 2>&1 | tail -3 ; i="$(docker images --format "{{.Repository}}" | grep -c "^$PROJECT/")"; echo "  남은 이미지 $i"; [ "$i" = 0 ]'
}

after_commit_part() {
  echo; echo "── 자. 커밋된 모습"
  run 'test "$(git status --porcelain | wc -l | tr -d " ")" = 0'
  run 'git log --format="%h %s" "$B"..HEAD; n="$(git log --format=%s "$B"..HEAD | wc -l | tr -d " ")"; fixes="$(git log --format=%s "$B"..HEAD | grep -c "^fix")"; echo "  커밋 $n (fix: $fixes)"; test "$((n - fixes))" = 6'   # ⓪~⑤ 여섯 + fix: 몇 개든
  run 'bad=0; for c in $(git rev-list "$B"..HEAD); do for t in "Ticket: MARC-TICK-90" "Derives-from: MARC-ENT-137"; do git log -1 --format=%B "$c" | grep -q -x "$t" || { echo "★ 트레일러가 없다: $c $t"; bad=1; }; done; done; [ "$bad" = 0 ]'
  local c1; c1="$(git log --format=%H --grep "^$C1_SUBJECT" "$B"..HEAD | tail -1)"
  export c1
  run 'echo "  커밋 ①: ${c1:-<없다>}"; test -n "$c1" && git log -1 --format=%B "$c1" | grep -q -x "Concerns: MARC-ISSUE-48"'
}

# 사라지는 노드(발주서 §3-1 의 일곱. 커밋마다 늘어난다).
expected_gone() {
  [ "$STEP" -ge 1 ] && cat <<'GONE'
esgapi/core/tests/test_llm_sink_db.py::test_outside_a_transaction_the_table_is_not_asked
esgapi/core/tests/test_llm_sink_db.py::test_without_a_tenant_nothing_is_written_and_the_line_goes_to_the_log
tests/security/test_llm_log.py::test_a_rolled_back_request_loses_its_log_line_but_the_object_remembers_the_cost
tests/security/test_llm_log.py::test_without_a_tenant_the_app_role_writes_nothing
GONE
  [ "$STEP" -ge 2 ] && cat <<'GONE'
esgapi/core/tests/test_documents_services.py::test_a_failed_signing_raises_so_the_request_rolls_back
GONE
  [ "$STEP" -ge 3 ] && cat <<'GONE'
tests/security/test_documents.py::test_a_callback_registered_before_a_4xx_is_dropped_by_the_middleware
tests/security/test_tenant_boundary.py::test_error_response_rolls_back_the_request_transaction
GONE
  return 0
}
# 새 노드(발주서 §3-1 의 새 이름 · 3-2 · 3-3, 감독 처분의 R6 하나).
expected_new() {
  [ "$STEP" -ge 1 ] && cat <<'NEW'
esgapi/core/tests/test_llm_sink_db.py::test_a_bad_tag_writes_nothing_and_the_line_goes_to_the_log
esgapi/core/tests/test_llm_sink_db.py::test_an_empty_tenant_scope_does_not_ask_the_table
tests/security/test_llm_log.py::test_a_bad_tag_writes_nothing_and_outside_a_transaction_the_sink_commits
tests/security/test_llm_log.py::test_a_line_in_a_block_that_rolls_back_is_lost_but_the_object_remembers_the_cost
NEW
  [ "$STEP" -ge 2 ] && cat <<'NEW'
esgapi/core/tests/test_documents_services.py::test_a_confirm_that_fails_midway_leaves_nothing
esgapi/core/tests/test_documents_services.py::test_a_failed_signing_leaves_no_row
NEW
  [ "$STEP" -ge 3 ] && cat <<'NEW'
esgapi/core/tests/tenancy/test_middleware.py::test_an_error_response_is_passed_through
esgapi/core/tests/tenancy/test_middleware.py::test_the_middleware_reaches_no_database
esgapi/core/tests/tenancy/test_middleware.py::test_the_session_is_attached_before_the_route_runs
tests/security/test_documents.py::test_a_callback_registered_in_a_block_that_rolls_back_is_dropped
tests/security/test_documents.py::test_a_hook_registered_in_a_block_that_rolls_back_is_never_called
tests/security/test_documents.py::test_the_storage_head_runs_outside_a_transaction
tests/security/test_request_transactions.py::test_a_log_line_survives_an_error_response
tests/security/test_request_transactions.py::test_the_llm_call_runs_outside_a_transaction
tests/security/test_tenant_boundary.py::test_the_middleware_opens_no_transaction
NEW
  [ "$STEP" -ge 4 ] && cat <<'NEW'
esgapi/core/tests/test_transaction_rules.py::test_a_function_that_writes_two_tables_is_named
esgapi/core/tests/test_transaction_rules.py::test_actions_that_write_open_one_transaction
esgapi/core/tests/test_transaction_rules.py::test_after_commit_work_is_registered_inside_a_block
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[accounts/service/services/accounts.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[core/service/services/documents.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[core/service/services/jobs.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[inventory/service/actions/scope3_shortlist.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[inventory/service/services/inventory.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[reconcile/service/services/parse.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[reference/admin/services/importer.py]
esgapi/core/tests/test_transaction_rules.py::test_every_write_sits_inside_a_block[reference/service/services/reference.py]
esgapi/core/tests/test_transaction_rules.py::test_no_outside_call_inside_a_block
esgapi/core/tests/test_transaction_rules.py::test_no_request_wide_transaction
esgapi/core/tests/test_transaction_rules.py::test_the_checker_catches_what_it_should
NEW
  return 0
}
export -f sha changed outside gate env_value expected_gone expected_new 2> /dev/null
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
