#!/usr/bin/env bash
# 밴드 X1b-1(MARC-TICK-179: 실행 틀 — 실행·단계·결과·출력 파일 표, 실행기 runs.execute, 실행 경로 넷의 몸)의 §4 자기검증
# (발주서 band-handoffs/X1b-order.md §4, 개정 5).
#   사용: apps/api-py/scripts/section4-X1b-1.sh --commit <1|2|3> [--with-containers] [--after-commit] [--step <n>]
#   --commit 1 은 단계 1·2·3·4·5·6·7·8·9·10·11·13, 2 는 그에 12, 3 은 전부(14·통합 층 포함).
#   --with-containers 가 없으면 컨테이너 단계(2·8)는 「안 돌림」으로 찍고 실패로 센다(조용한 초록 금지).
#   --after-commit 이면 13 이 「작업 트리 0줄」을 본다(아니면 「스테이징 밖의 바뀜·새 파일 0」 — 커밋 전).
# 환경 변수: X1B1_C1(커밋 ① 의 해시 — ②③ 에서 단계 4 가 표·마이그레이션 0줄을 그 해시와 견준다),
#   X1B1_MSG(쓸 커밋 메시지 파일 — 13 이 키 꼴을 본다).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독 몫). AI 공급사 호출 0, 시험은 env -u OPENAI_API_KEY.
# 컨테이너는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것만 띄운다. build 는
#   scripts/with-build-lock.sh 로만(기계 전체 하나). 띄운 벌은 내리지 않는다(러너가 끝에 내린다).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
#   git grep 의 종료 ≥2 와 양성 대조 0 은 실패로 센다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=da0fa43443f0030449d9c8dde8a94d764366fe30   # 워크트리를 세운 main(merge band/AU1a)
OUT="$ROOT/../X1b-1.out"                         # 워크트리 밖. collect-base.txt·lint-imports-base.txt 가 여기 있다
A=apps/api-py
E="$A/esgapi"
export PATH="$HOME/.nvm/versions/node/v22.23.1/bin:$PATH"
export LC_ALL=C

COMMIT=""; ONLY=""; CONTAINERS=0; AFTER=0
while [ $# -gt 0 ]; do
  case "$1" in
    --commit) COMMIT="${2:-}"; shift 2 ;;
    --step) ONLY="${2:-}"; shift 2 ;;
    --with-containers) CONTAINERS=1; shift ;;
    --after-commit) AFTER=1; shift ;;
    *) echo "사용: $0 --commit <1|2|3> [--step <n>] [--with-containers] [--after-commit]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3) ;; *) echo "--commit <1|2|3> 이 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/x1b1.XXXXXX)"
case "$T" in /private/tmp/x1b1.*) ;; *) exit 99 ;; esac
FAILS=0

# ── 단계 안의 파이썬(파일로 둔다 — 단계의 셸 글이 홑따옴표 안이다) ──
cat > "$T/helper.py" <<'PY'
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
COMMIT = int(sys.argv[3])
CMD = sys.argv[4]
ARGS = sys.argv[5:]
API = "apps/api-py/"
PKG = ROOT / API / "esgapi"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def product_files():
    for path in sorted(PKG.rglob("*.py")):
        parts = set(path.relative_to(PKG).parts[:-1])
        if {"tests", "migrations"} & parts:
            continue
        yield path.relative_to(ROOT / API).as_posix(), ast.parse(path.read_text(encoding="utf-8"))


def call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def call_sites(name: str, attr_of: str | None = None) -> set[tuple[str, str]]:
    """제품 코드에서 <name>( 를 부르는 (파일, 감싼 함수). attr_of 면 <attr_of>.<name>( 만."""
    found = set()
    for rel, tree in product_files():
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                for n in ast.walk(fn):
                    if isinstance(n, ast.Call) and call_name(n) == name:
                        if attr_of is not None and not (
                            isinstance(n.func, ast.Attribute) and isinstance(n.func.value, ast.Name) and n.func.value.id == attr_of
                        ):
                            continue
                        found.add((rel, fn.name))
    return found


# ── 4: JobRow 클래스 몸의 AST 가 BASE 와 같다 ──
if CMD == "jobrow":
    def jobrow(source: str) -> str:
        tree = ast.parse(source)
        (node,) = [n for n in tree.body if isinstance(n, ast.ClassDef) and n.name == "JobRow"]
        return ast.dump(node, include_attributes=False)

    base = jobrow(git("show", f"{BASE}:{API}esgapi/runs/models.py"))
    now = jobrow((PKG / "runs/models.py").read_text(encoding="utf-8"))
    print(f"  JobRow AST 같음: {base == now} (길이 {len(base)})")
    raise SystemExit(0 if base == now and base else 1)

# ── 6: 시험 수·이름 ──
# 사라져도 되는 노드(§3-1 조건 3 — 커밋 ③): 짝은 보고의 표.
GONE_OK = {
    3: {
        "esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_file_get]",
        "esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_get]",
        "esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[runs_list]",
        "tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[POST /runs]",
        "tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /runs]",
        "tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /runs/{run_id}]",
        "tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /runs/{run_id}/files/{name}]",
    },
}

if CMD == "collect":
    base_file, now_file = Path(ARGS[0]), Path(ARGS[1])
    node = lambda p: {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}
    before, after = node(base_file), node(now_file)
    removed, added = sorted(before - after), sorted(after - before)
    allowed = GONE_OK.get(COMMIT, set())
    bad = [n for n in removed if n not in allowed]
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)}(허용 밖 {len(bad)}) · 더함 {len(added)}")
    for layer in ("esgapi/", "tests/security/", "tests_integration/"):
        print(f"    {layer} 앞 {sum(n.startswith(layer) for n in before)} · 뒤 {sum(n.startswith(layer) for n in after)}")
    for n in removed:
        print(f"    - {n}{'' if n in allowed else '   ★ 허용 밖'}")
    for n in added:
        print(f"    + {n}")
    missing_allowed = sorted(allowed - set(removed))
    if missing_allowed:
        print(f"  ★ 빠져야 하는데 남은 것 {missing_allowed}")
    raise SystemExit(1 if bad or missing_allowed or len(after) <= len(before) else 0)

# ── 7: 약화 대조 ──
# (파일 끝부분, 지운 줄의 글자, 커밋) → §2-5 의 항목(또는 감독 처분). 지운 줄 가운데 assert·==·len(·parametrize 를 품은
# 것이 전부 여기 있어야 한다.
MINUS = [
    ("esgapi/core/tests/isolation/test_managers.py",
     'assert len([names for names in fields if "company_id" in names]) == 6  # 분모(AU1a +1: AuditEventRow)', 1,
     "§2-5 ① test_managers.py:45 6→10(새 회사 칸 표 넷)"),
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert len(company_models()) == 7  # 분모(AU1a +1: AuditEventRow)", 1,
     "§2-5 ① test_static_rules.py:185 7→11"),
    ("esgapi/core/tests/test_selector_scope.py",
     "assert with_company == COMPANY_TABLES and len(COMPANY_TABLES) == 6  # 분모(AU1a +1: AuditEventRow)", 1,
     "§2-5 ① test_selector_scope.py:216 6→10"),
    ("esgapi/core/tests/test_documents_models.py", "assert len(DOCUMENT_COLUMNS) == 12", 1,
     "§2-5 ① test_documents_models.py:72 DocumentRow 칸 12→15(처분 ④ (가) — 감독 처분 2026-10-19)"),
    ("esgapi/core/tests/test_documents_models.py",
     'assert [name for name in sorted(doc) if doc[name].null] == ["etag", "sha256", "uploaded_at"]', 1,
     "§2-5 ① test_documents_models.py NULL 칸 목록 +3(감독 처분 2026-10-19 — 더하기만, 정확 일치 그대로)"),
    ("esgapi/core/tests/test_documents_models.py",
     'assert [name for name, field in doc.items() if field.is_relation] == ["company"]', 1,
     "§2-5 ① test_documents_models.py 관계 칸 +previous_document(감독 처분 2026-10-19)"),
    # ── 커밋 ② ──
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert opened == 22", 2,
     "§2-5 ② test_static_rules.py:242 for_company( 수 22→34(X1b-1 +12: runs selectors 여섯·services 여섯)"),
    ("esgapi/core/tests/test_jobs_hook.py", 'assert direct == {"config/celery.py", "reconcile/tasks.py"}', 2,
     "감독 처분 sid:MARC-TICK-179(2026-10-19) — celery 를 들이는 제품 파일에 runs/tasks.py 더함(정확 일치 그대로)"),
    ("esgapi/core/tests/test_jobs_hook.py", 'assert through_app == {"core/resources/queue.py", "reconcile/tasks.py"}', 2,
     "감독 처분 sid:MARC-TICK-179(2026-10-19) — 앱을 거쳐 celery 를 들이는 파일에 runs/tasks.py 더함"),
    ("esgapi/core/tests/test_observability_context.py", 'assert list(parameters) == ["task_id", "task_name", "job_id"]', 2,
     "§2-5 ② test_observability_context.py 칸 목록 +run_id(처분 ⑯)"),
    ("esgapi/core/tests/test_observability_context.py",
     "assert [parameter.kind for parameter in parameters.values()] == [inspect.Parameter.KEYWORD_ONLY] * 3", 2,
     "§2-5 ② test_observability_context.py 이름으로만 받는 인자 3→4(처분 ⑯)"),
    ("esgapi/core/tests/test_observability_jsonlog.py", "assert len(set(FIELDS)) == 21  # E2 +1: 접근 줄의 code", 2,
     "§2-5 ② test_observability_jsonlog.py:78 칸 수 21→22(처분 ⑯ run_id)"),
    ("esgapi/core/tests/test_selector_scope.py",
     "assert sorted(files) == [  # 분모: Selector 파일 여섯. 늘면 여기가 빨개져 새 파일의 조회를 보게 한다", 2,
     "§2-5 ② test_selector_scope.py:232-239 Selector 파일 여섯→일곱(runs/service/selectors/runs.py)"),
    ("esgapi/core/tests/test_selector_scope.py", 'assert opened == {"documents": 3, "jobs": 3, "audit": 1}', 2,
     "§2-5 ② test_selector_scope.py:257 쓰는 문 + \"runs\": 6"),
    ("esgapi/core/tests/test_storage_adapter.py", 'assert methods == {"presign_upload", "head", "get"}', 2,
     "감독 처분 sid:MARC-TICK-179(2026-10-19) — 처분 ⑳ (가) ObjectStorage.put: 포트 메서드 셋→넷(정확 일치 그대로)"),
    ("esgapi/core/tests/test_transaction_rules.py", "assert len(files) == 13, [", 2,
     "§2-5 ② test_transaction_rules.py:299 target_files() 13→14(runs/service/services/runs.py)"),
    ("esgapi/core/tests/test_transaction_rules.py",
     'assert durable == {"reconcile/tasks.py": 2, "runs/management/commands/requeue_jobs.py": 1}  # 셈 3', 2,
     "§2-5 ② test_transaction_rules.py:376 durable 셈 3→9(k=6: runs/tasks.py 5 · requeue_runs.py 1)"),
    # ── 커밋 ③ ──
    ("esgapi/config/tests/test_api_contract.py", 'assert {success, "501"} <= set(responses), key', 3,
     "§2-5 ③ test_api_contract.py:389 「{success, 501} ⊆」→ 성공 ⊆ · 501 은 STILL_501(runs_create·문서 둘)에만(개정 4 N1)"),
    ("esgapi/config/tests/test_api_contract.py",
     'assert responses["501"]["content"]["application/json"]["schema"]["$ref"].endswith("/ErrorBody"), key', 3,
     "§2-5 ③ test_api_contract.py:391 responses[\"501\"] 꼴 단언을 501 이 있는 것에만(개정 4 N1 — 줄은 if 안으로 옮김)"),
    ("esgapi/core/tests/service/apis/test_runs.py", '@pytest.mark.parametrize("operation_id", sorted(CONTRACT_ONLY))', 3,
     "§2-5 ③ core test_runs.py:81-82 401 표는 여섯 그대로 — 새 상수 SESSION_REQUIRED 로(노드 id 그대로, 개정 4 B7)"),
    ("esgapi/core/tests/service/apis/test_runs.py",
     'assert error_of(send(client, *CONTRACT_ONLY[operation_id])) == (401, "NO_SESSION")', 3,
     "§2-5 ③ core test_runs.py:81-82 같은 줄 — CONTRACT_ONLY → SESSION_REQUIRED(여섯, 개정 4 B7)"),
    ("esgapi/core/tests/test_transaction_rules.py",
     "assert sum(total for total, _ in counted.values()) == 1  # 분모: 올림 확인의 하나", 3,
     "§2-5 ③ test_transaction_rules.py:324 on_commit 셈 1→2 + runs/service/actions/runs.py 1 단언(개정 4 B2)"),
]

if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "*/tests/*", "apps/api-py/tests", "apps/api-py/tests_integration")
    current = None
    rows = []
    for line in diff.splitlines():
        if line.startswith("--- "):
            current = line[6:] if line.startswith("--- a/") else None
        elif line.startswith("-") and not line.startswith("---") and re.search(r"assert|==|len\(|parametrize", line):
            rows.append((current, line[1:].strip()))
    bad = 0
    for path, text in rows:
        hit = next((item for f, t, c, item in MINUS if c <= COMMIT and path and path.endswith(f) and t == text), None)
        print(f"  - {path}: {text}\n      → {hit or '<항목 없음>'}")
        bad += 0 if hit else 1
    print(f"  - 줄(assert·==·len(·parametrize) {len(rows)} · 항목 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 8: 스키마 대조(pg_dump 를 문장으로 나눠 견준다) ──
ALLOWED_TABLES = ("run_runs", "run_steps", "run_results", "run_files")
OWN_TABLE = re.compile(
    r"^(CREATE TABLE|ALTER TABLE( ONLY)?|CREATE (UNIQUE )?INDEX \S+ ON|CREATE SEQUENCE|ALTER SEQUENCE"
    r"|GRANT [A-Z,]+ ON TABLE)"  # 권한의 열 줄은 아래 grants 가 처분 ⑤ 와 견준다
    r" public\.(" + "|".join(ALLOWED_TABLES) + r")(_[a-z0-9_]+_seq)?( |$)"
)
# 기존 표 안에서 더해도 되는 것(문장의 줄 단위)
ALLOWED_LINES = {
    "core_llm_call_logs": re.compile(r"\brun_id\b|core_llm_logs_company_run"),
    "core_documents": re.compile(r"\b(report_year|previous_document_id|page_count)\b|core_documents_(report_year|page_count)_check|previous_document"),
}


def statements(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [s.strip() for s in text.split(";\n") if s.strip()]


if CMD == "schema":
    base, head = statements(Path(ARGS[0])), statements(Path(ARGS[1]))
    bset, hset = set(base), set(head)
    gone = sorted(bset - hset)
    new = sorted(hset - bset)
    bad = []
    by_first = {s.splitlines()[0]: s for s in base}
    for s in new:
        # 새 표 넷의 문장만(그 표를 머리에 둔 CREATE·ALTER·색인·시퀀스). 다른 표에서 run_* 로 향하는 FK 는 여기서
        # 빠져 아래에서 허용 밖이 된다(검증 ① n3 — 「글자가 들어 있기만 하면」을 좁힘).
        if OWN_TABLE.match(" ".join(s.split())):
            continue
        first = s.splitlines()[0]
        old = by_first.get(first)
        table = next((t for t in ALLOWED_LINES if re.search(rf"\b{t}\b", s)), None)
        if table is not None and not first.startswith("CREATE TABLE ") and ALLOWED_LINES[table].search(s):
            print(f"  + {' '.join(s.split())[:150]}")
            continue  # 새 칸의 제약·색인(ALTER TABLE … ADD CONSTRAINT·CREATE INDEX)
        if table is not None and old is not None:
            extra = [l for l in s.splitlines() if l not in old.splitlines()]
            lost = [l for l in old.splitlines() if l not in s.splitlines()]
            # 마지막 칸 줄 뒤의 쉼표는 칸이 늘면 생긴다 — 쉼표만 다른 줄은 같은 줄로 친다
            lost = [l for l in lost if l + "," not in s.splitlines()]
            if all(ALLOWED_LINES[table].search(l) or l.rstrip(",") in old.splitlines() for l in extra) and not lost:
                print(f"  ~ {first[:90]} : 더한 줄 {[l.strip() for l in extra if ALLOWED_LINES[table].search(l)]}")
                continue
        if table is not None and old is None and ALLOWED_LINES[table].search(s):
            continue
        bad.append(s)
    replaced = {s.splitlines()[0] for s in new}
    # 빠져도 되는 것은 칸이 늘어 다시 적힌 CREATE TABLE 뿐(같은 첫 줄의 새 문장이 있다)
    gone_bad = [s for s in gone if not (s.startswith("CREATE TABLE ") and s.splitlines()[0] in replaced)]
    print(f"  문장 BASE {len(base)} · HEAD {len(head)} · 새 {len(new)} · 빠짐 {len(gone)}(바뀐 것 밖 {len(gone_bad)}) · 허용 밖 {len(bad)}")
    runs_create = next((s for s in head if s.startswith("CREATE TABLE public.run_runs ")), "")
    for column in ("stalled_attempts", "progress_attempt"):
        line = next((l.strip() for l in runs_create.splitlines() if l.strip().startswith(column + " ")), "<없음>")
        print(f"  run_runs 칸 {column}: {line}")
    check = next((l.strip() for l in runs_create.splitlines() if "run_runs_progress_attempt_check" in l), "<없음>")
    print(f"  progress_attempt CHECK: {check}")
    for s in bad + gone_bad:
        print(f"  ★ 허용 밖: {' '.join(s.split())[:200]}")
    raise SystemExit(1 if bad or gone_bad or not new else 0)

if CMD == "grants":
    base = set(Path(ARGS[0]).read_text().splitlines())
    head = set(Path(ARGS[1]).read_text().splitlines())
    want = {f"esg_app|{t}|{p}" for t in ("run_runs", "run_steps") for p in ("SELECT", "INSERT", "UPDATE")}
    want |= {f"esg_app|{t}|{p}" for t in ("run_results", "run_files") for p in ("SELECT", "INSERT")}
    added, removed = head - base, base - head
    print(f"  권한 행 BASE {len(base)} · HEAD {len(head)} · 더함 {len(added)} · 빠짐 {len(removed)} · 기대 {len(want)}")
    for line in sorted(added | removed):
        print(f"    {'+' if line in added else '-'} {line}")
    raise SystemExit(0 if added == want and not removed and base else 1)

# ── 12: 실행기 대조(② 부터) ──
if CMD == "runner":
    flow = call_sites("run_flow")
    bindings = call_sites("get", attr_of="BINDINGS")
    clients = call_sites("build_client")
    runs_clients = {site for site in clients if site[0].startswith("esgapi/runs/")}
    print(f"  run_flow( 부르는 자리 {sorted(flow)}")
    print(f"  BINDINGS.get( 부르는 자리 {sorted(bindings)}")
    print(f"  runs 의 build_client( 자리 {sorted(runs_clients)}")
    mock_ok = False
    for rel, tree in product_files():
        if not rel.startswith("esgapi/runs/"):
            continue
        for n in ast.walk(tree):
            if isinstance(n, ast.Call) and call_name(n) == "build_client":
                mock_ok = any(k.arg == "mock" and isinstance(k.value, ast.Constant) and k.value.value is True for k in n.keywords)
    print(f"  mock=True: {mock_ok}")
    want_flow = {("esgapi/runs/tasks.py", "execute_run")}
    want_bind = {("esgapi/runs/tasks.py", "execute_run")} | ({("esgapi/runs/service/actions/runs.py", "create_run")} if COMMIT >= 3 else set())
    ok = flow == want_flow and bindings == want_bind and len(runs_clients) == 1 and next(iter(runs_clients))[1] == "llm" and mock_ok
    raise SystemExit(0 if ok else 1)

# ── 14: 기록 지점(③ 부터) ──
RECORD_SITES = {
    ("esgapi/user/service/services/login.py", "note"),
    ("esgapi/core/service/services/documents.py", "confirm_upload"),
    ("esgapi/runs/service/actions/runs.py", "create_run"),
    ("esgapi/runs/service/apis/runs.py", "runs_file_get"),
}

if CMD == "sites":
    found = call_sites("record_event")
    planted = ast.parse("def f():\n    audit.record_event(at=1)\n")
    positive = any(isinstance(n, ast.Call) and call_name(n) == "record_event" for n in ast.walk(planted))
    print(f"  부르는 자리 {sorted(found)}")
    print(f"  기대 {sorted(RECORD_SITES)} · 양성 대조 {positive}")
    raise SystemExit(0 if found == RECORD_SITES and positive else 1)

# ── 3: openapi 의 바뀐 자리(③) ──
def leaves(node, prefix=""):
    out = {}
    if isinstance(node, dict):
        if not node:
            out[prefix] = {}
        for k, v in node.items():
            out.update(leaves(v, f"{prefix}/{k}"))
    elif isinstance(node, list):
        if not node:
            out[prefix] = []
        for i, v in enumerate(node):
            key = v.get("name") if isinstance(v, dict) and "name" in v and "in" in v else str(i)
            out.update(leaves(v, f"{prefix}/{key}"))
    else:
        out[prefix] = node
    return out


def esc(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def leaves_doc(doc):
    out = {}
    for path, item in doc.get("paths", {}).items():
        out.update(leaves(item, f"/paths/{esc(path)}"))
    for k, v in doc.items():
        if k != "paths":
            out.update(leaves(v, f"/{k}"))
    return out


# §0-2: 셋의 501 빠짐 · runs_create 의 404 더함
ALLOWED_OPENAPI = [
    r"^/paths/~1runs/get/responses/501(/|$)",
    r"^/paths/~1runs~1\{run_id\}/get/responses/501(/|$)",
    r"^/paths/~1runs~1\{run_id\}~1files~1\{name\}/get/responses/501(/|$)",
    r"^/paths/~1runs/post/responses/404(/|$)",
]

if CMD == "openapi-diff":
    base_doc = json.loads(git("show", f"{BASE}:{API}generated/openapi.json"))
    head_doc = json.loads((ROOT / API / "generated/openapi.json").read_text(encoding="utf-8"))
    b, h = leaves_doc(base_doc), leaves_doc(head_doc)
    changed = sorted(k for k in set(b) | set(h) if b.get(k, "<없음>") != h.get(k, "<없음>"))
    allowed = [re.compile(p) for p in ALLOWED_OPENAPI]
    outside = [k for k in changed if not any(a.search(k) for a in allowed)]
    groups = sorted({re.sub(r"/responses/(\d+)/.*", r"/responses/\1", k) for k in changed})
    print(f"  바뀐 잎 {len(changed)} · 묶음 {len(groups)}")
    for g in groups:
        print(f"    {'+' if g.replace('/', '', 0) and any(k.startswith(g) and k in h and k not in b for k in changed) else '-'} {g}")
    print(f"  목록 밖 {len(outside)}: {outside[:20]}")
    seen = {re.sub(r"/responses/(\d+)/.*", r"/responses/\1", k) for k in changed}
    need = {"/paths/~1runs/get/responses/501", "/paths/~1runs~1{run_id}/get/responses/501",
            "/paths/~1runs~1{run_id}~1files~1{name}/get/responses/501", "/paths/~1runs/post/responses/404"}
    raise SystemExit(1 if outside or seen != need else 0)

if CMD == "sha":
    text = (ROOT / API / "generated/openapi.json").read_bytes()
    want = (ROOT / API / "generated/api.d.ts.source-sha256").read_text().strip()
    got = hashlib.sha256(text).hexdigest()
    print(f"  openapi sha256 {got} · 적힌 값 {want}")
    raise SystemExit(0 if got == want else 1)

raise SystemExit(f"모르는 명령 {CMD}")
PY

cat > "$T/grants.sql" <<'SQL'
SELECT grantee || '|' || table_name || '|' || privilege_type FROM information_schema.role_table_grants
WHERE grantee = 'esg_app' ORDER BY 1;
SQL

wanted() { # <단계> — 이 커밋에서 도는 단계인가
  [ -z "$ONLY" ] || [ "$ONLY" = "$1" ] || return 1
  case "$COMMIT:$1" in
    *:1 | *:2 | *:3 | *:4 | *:5 | *:6 | *:7 | *:8 | *:9 | *:10 | *:11 | *:13) return 0 ;;
    2:12 | 3:12 | 3:14) return 0 ;;
    *) return 1 ;;
  esac
}
step() { # <n> <설명> <셸 글>
  local n="$1" desc="$2" code
  shift 2
  echo
  echo "[$n] $desc"
  (eval "$*")
  code=$?
  echo "[$n] $desc EXIT=$code"
  [ "$code" = 0 ] || FAILS=$((FAILS + 1))
}
not_run() { # <n> <설명> <까닭>
  echo
  echo "[$1] $2 — 안 돌림($3) EXIT=1"
  FAILS=$((FAILS + 1))
}
env_value() { sed -n "s/^$1=//p" .env | tail -1; }
changed() { { git diff --no-renames --name-only "$BASE"; git ls-files --others --exclude-standard; } | sort -u; }
helper() { (cd "$A" && uv run --frozen python "$T/helper.py" "$ROOT" "$BASE" "$COMMIT" "$@"); }
export -f env_value changed helper
export ROOT BASE OUT A E T COMMIT

echo "── 밴드 X1b-1 §4 · 커밋 $COMMIT · BASE ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"

# ── 1. 순수 층 ──
if wanted 1; then
  step 1 "순수 층 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$T/pure.txt" 2>&1; code=$?; tail -1 "$T/pure.txt"; exit $code)'
fi

# ── 3. 계약 ──
if wanted 3; then
  if [ "$COMMIT" -lt 3 ]; then
    step 3 "generated 0바이트(커밋 ①②)" 'git diff --quiet "$BASE" -- "$A/generated"; code=$?; new="$(git ls-files --others --exclude-standard -- "$A/generated" | wc -l | tr -d " ")"; echo "  git diff EXIT=$code · 새 파일 $new"; [ "$code" = 0 ] && [ "$new" = 0 ]'
  else
    step 3 "다시 뽑은 openapi 와 generated/openapi.json 의 cmp" '(cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi > "$T/openapi.json" 2> "$T/export.err"; code=$?; [ "$code" = 0 ] || { tail -3 "$T/export.err"; exit $code; }; cmp "$T/openapi.json" generated/openapi.json)'
    step 3 "api.d.ts.source-sha256 = openapi 의 sha256" 'helper sha'
    step 3 "config/tests/test_api_contract.py 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$T/contract.txt" 2>&1; code=$?; tail -1 "$T/contract.txt"; exit $code)'
    step 3 "openapi 의 바뀐 자리 = §0-2(셋의 501 빠짐 · runs_create 의 404)" 'helper openapi-diff'
  fi
fi

# ── 4. 0줄 ──
if wanted 4; then
  step 4 "0줄 경로(§4-4)" '
    P="apps/web packages $E/greenwash $E/inventory $E/reconcile $E/reference $E/organization $E/user $E/core/permissions.py $E/core/auth $E/core/tenancy $E/core/service $E/core/calc/audit.py $E/runs/service/selectors/jobs.py $E/runs/service/services/jobs.py $E/runs/management/commands/requeue_jobs.py $E/config/api.py $E/config/apps_list.py $A/.importlinter $A/scripts/planted-breaks.sh $A/scripts/rehearsal.sh $A/pyproject.toml $A/uv.lock compose.yaml infra README.md docs $A/tests_integration/test_worker_flow.py $A/tests_integration/test_upload_flow.py $A/tests/security/test_llm_log.py $A/tests/security/test_audit.py $A/tests/security/conftest.py"
    git diff --quiet "$BASE" -- $P; code=$?
    new="$(git ls-files --others --exclude-standard -- $P | wc -l | tr -d " ")"
    echo "  git diff EXIT=$code · 추적 안 된 새 파일 $new"
    # tests/support 는 새 파일만(기존 파일 0줄)
    git diff --quiet --diff-filter=MDR "$BASE" -- "$A/tests/support"; sup=$?
    echo "  tests/support 기존 파일 고침 EXIT=$sup"
    # 새 마이그레이션 파일 0(처분 ④ (가) — 다시 쓰기)
    extra="$(git ls-files --others --exclude-standard -- "$E/*/migrations/*")$(git diff --name-only --diff-filter=A "$BASE" -- "$E/*/migrations/*")"
    echo "  새 마이그레이션 파일: [${extra}]"
    [ "$code" = 0 ] && [ "$new" = 0 ] && [ "$sup" = 0 ] && [ -z "$extra" ]'
  step 4 "runs/models.py 의 JobRow 클래스 AST = BASE" 'helper jobrow'
  if [ "$COMMIT" -ge 2 ]; then
    step 4 "②③: runs/models.py·runs/migrations·core/models.py·core/migrations 0줄(커밋 ① 기준 — §2-1 ★)" '
      test -n "${X1B1_C1:-}" || { echo "  X1B1_C1(커밋 ① 의 해시)이 없다"; exit 1; }
      git diff --quiet "$X1B1_C1" -- "$E/runs/models.py" "$E/runs/migrations" "$E/core/models.py" "$E/core/migrations"; code=$?
      echo "  기준 ${X1B1_C1:0:7} · git diff EXIT=$code"; exit $code'
  fi
fi

# ── 5. import 계약 ──
if wanted 5; then
  step 5 "lint-imports 의 Contracts 줄 = BASE(lint-imports-base.txt)" '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; now="$(grep -E "^Contracts:" "$T/lint.txt" | tail -1)"; base="$(grep -E "^Contracts:" "$OUT/lint-imports-base.txt" | tail -1)"; echo "  지금: $now · BASE: ${base:-<없음>}"; [ "$code" = 0 ] && [ -n "$base" ] && [ "$now" = "$base" ])'
  step 5 "양성 대조: runs 의 새 파일을 와일드카드 계약이 문다(심고 되돌림)" '
    plant() { # <파일> <심을 줄> <깨져야 할 계약 이름>
      f="$1"; keep="$T/keep.$(basename "$f")"
      [ -f "$f" ] || { echo "  $f 없음 — 안 심음"; return 1; }
      cp "$f" "$keep"
      printf "%s\n" "$2" >> "$f"
      (cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint-plant.txt" 2>&1); c=$?
      cp "$keep" "$f"
      cmp -s "$keep" "$f" || { echo "  되돌림 실패 $f"; return 1; }
      hit="$(grep -c -E "^$3 BROKEN" "$T/lint-plant.txt")"
      echo "  $f + 「$2」 → lint-imports EXIT=$c · 「$(grep -E "^$3 BROKEN" "$T/lint-plant.txt" | head -1)」"
      [ "$c" != 0 ] && [ "$hit" -ge 1 ]
    }
    plant "$E/runs/service/apis/runs.py" "from esgapi.runs.models import RunRow  # noqa" "라\\..*" || exit 1
    if [ "$COMMIT" -ge 2 ]; then
      plant "$E/runs/tasks.py" "from esgapi.runs.models import RunRow  # noqa" "라\\..*" || exit 1
      plant "$E/core/flows/binding.py" "import django  # noqa" "다\\..*" || exit 1
    else
      echo "  runs/tasks.py·core/flows/binding.py 는 커밋 ② 부터(지금 없음)"
    fi
    (cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint-after.txt" 2>&1); c=$?
    echo "  되돌린 뒤: $(grep -E "^Contracts:" "$T/lint-after.txt" | tail -1) EXIT=$c"; exit $c'
fi

# ── 6. 시험 수·이름 ──
if wanted 6; then
  step 6 "수집한 노드 id: 사라진 것 = §3-1 조건 3 의 목록뿐, 수는 늚" '
    test -s "$OUT/collect-base.txt" || { echo "  collect-base.txt 가 없다"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests tests_integration > "$T/collect-now.txt" 2>&1); code=$?
    tail -1 "$OUT/collect-base.txt" | sed "s/^/  앞: /"; tail -1 "$T/collect-now.txt" | sed "s/^/  뒤: /"
    helper collect "$OUT/collect-base.txt" "$T/collect-now.txt" > "$T/collect.txt" 2>&1; c=$?
    cat "$T/collect.txt"
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider -m security tests > "$T/collect-security.txt" 2>&1); s=$?
    echo "  보안 층 수집: 앞 $(tail -1 "$OUT/collect-security-base.txt") · 뒤 $(tail -1 "$T/collect-security.txt") EXIT=$s"
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider tests_integration > "$T/collect-integration.txt" 2>&1)
    echo "  통합 층 수집: 앞 $(tail -1 "$OUT/collect-integration-base.txt") · 뒤 $(tail -1 "$T/collect-integration.txt")"
    [ "$code" = 0 ] && [ "$c" = 0 ] && [ "$s" = 0 ]'
fi

# ── 7. 약화 대조 ──
if wanted 7; then
  step 7 "시험 diff 의 - 줄(assert·==·len(·parametrize)마다 §2-5 항목" 'helper weaken'
fi

# ── 2·8. 컨테이너 ──
gate() { # 기계 문: 자기 밖 esg-app* 프로젝트 ≤ 2, 빌드 중 0, free ≥ 20%, 1분 부하 < 24. 60초 간격, 최대 30분.
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d " ")"
    # 첫 낱말이 docker·docker-compose 인 build 명령만 센다(Docker Desktop 의 com.docker.build 데몬·다른 세션의 글은 아니다)
    building="$(ps -axo command | grep -E "^[^ ]*/?(docker|docker-compose)( .*)? (build|buildx)( |$)" | grep -v -c grep)"
    free="$(memory_pressure 2> /dev/null | sed -n 's/.*free percentage: \([0-9]*\)%.*/\1/p')"
    load="$(sysctl -n vm.loadavg | awk '{print $2}')"
    if [ "$others" -le 2 ] && [ "$building" = 0 ] && [ "${free:-0}" -ge 20 ] && [ "$(printf '%.0f' "${load:-99}")" -lt 24 ]; then
      echo "  (문: 자기 밖 esg-app* 프로젝트 $others · 빌드 중 $building · free ${free:-?}% · 1분 부하 ${load:-?} · 기다린 횟수 $tries × 60초)"
      return 0
    fi
    [ "$tries" -ge 30 ] && { echo "  (문이 안 열렸다: 자기 밖 $others · 빌드 중 $building · free ${free:-?}% · 부하 ${load:-?})"; return 1; }
    tries=$((tries + 1))
    sleep 60
  done
}
export -f gate
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
OWNER="$(env_value POSTGRES_OWNER_USER)"
export PROJECT OWNER

if [ "$CONTAINERS" = 1 ] && { wanted 2 || wanted 8; }; then
  step "2·8" "Postgres 한 벌($PROJECT)" '
    test -n "$PROJECT" && test "$PROJECT" != esg-app || exit 1
    grep -q "^SESSION_SECRET=." .env || { echo "  .env 에 SESSION_SECRET 이 없다"; exit 1; }
    gate || exit 1
    docker compose up -d --wait postgres 2>&1 | tail -2; exit "${PIPESTATUS[0]}"'
fi

if wanted 2; then
  if [ "$CONTAINERS" = 1 ]; then
    step 2 "업무 층(core·runs·config·reconcile)" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/core esgapi/runs esgapi/config esgapi/reconcile > "$T/business.txt" 2>&1; code=$?; tail -1 "$T/business.txt"; exit $code)'
    step 2 "보안 층 전부" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider > "$T/security.txt" 2>&1; code=$?; tail -1 "$T/security.txt"; exit $code)'
  else
    not_run 2 "업무·보안 층" "--with-containers 없음"
  fi
fi

if wanted 8; then
  if [ "$CONTAINERS" = 1 ]; then
    step 8 "스키마 대조: BASE 트리와 지금 트리로 빈 DB 둘에 migrate → pg_dump --schema-only(db 컨테이너 안) 견줌" '
      set -e
      D="$T/base-tree"; mkdir -p "$D"
      case "$D" in /private/tmp/x1b1.*) ;; *) exit 99 ;; esac
      git archive "$BASE" "$A" | tar -x -C "$D"
      PY="$ROOT/$A/.venv/bin/python"
      host="127.0.0.1:$(env_value POSTGRES_PORT)"
      pw="$(env_value POSTGRES_OWNER_PASSWORD)"
      URL_BASE="postgres://$OWNER:$pw@$host/x1b1_schema_base"; URL_HEAD="postgres://$OWNER:$pw@$host/x1b1_schema_head"
      for db in x1b1_schema_base x1b1_schema_head; do
        docker compose exec -T postgres psql -q -U "$OWNER" -d postgres -c "DROP DATABASE IF EXISTS $db" -c "CREATE DATABASE $db" > /dev/null
      done
      set +e
      (cd "$D/$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_BASE" "$PY" manage.py migrate --no-input > "$T/migrate-base.txt" 2>&1); c1=$?
      (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_HEAD" "$PY" manage.py migrate --no-input > "$T/migrate-head.txt" 2>&1); c2=$?
      echo "  migrate BASE EXIT=$c1 · HEAD EXIT=$c2"
      [ "$c1" = 0 ] && [ "$c2" = 0 ] || { tail -5 "$T/migrate-base.txt" "$T/migrate-head.txt"; exit 1; }
      for side in base head; do
        docker compose exec -T postgres pg_dump -U "$OWNER" --schema-only --no-owner "x1b1_schema_$side" | grep -v -E "^(--|SET |SELECT pg_catalog.set_config|\\\\(un)?restrict )" > "$T/dump-$side.sql"
        docker compose exec -T postgres psql -At -U "$OWNER" -d "x1b1_schema_$side" -f - < "$T/grants.sql" > "$T/grants-$side.txt"
      done
      wc -l "$T/dump-base.sql" "$T/dump-head.sql" | sed "s/^/  /"
      helper schema "$T/dump-base.sql" "$T/dump-head.sql"; d1=$?
      helper grants "$T/grants-base.txt" "$T/grants-head.txt"; d2=$?
      (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_HEAD" "$PY" manage.py makemigrations --check --dry-run > "$T/makemigrations.txt" 2>&1); c3=$?
      grep -v -E "RuntimeWarning|warnings.warn" "$T/makemigrations.txt" | sed "s/^/  makemigrations: /"
      for db in x1b1_schema_base x1b1_schema_head; do
        docker compose exec -T postgres psql -q -U "$OWNER" -d postgres -c "DROP DATABASE IF EXISTS $db" > /dev/null
      done
      [ "$d1" = 0 ] && [ "$d2" = 0 ] && [ "$c3" = 0 ] && [ -s "$T/dump-base.sql" ] && [ -s "$T/grants-base.txt" ]'
  else
    not_run 8 "스키마 대조" "--with-containers 없음"
  fi
fi

if [ "$COMMIT" = 3 ] && wanted 2; then
  if [ "$CONTAINERS" = 1 ]; then
    step 2 "통합 층(이미지는 with-build-lock.sh 로 짓고 compose 전부를 띄운다)" '
      gate || exit 1
      EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || exit 1
      export EDK_JWT_PUBLIC_KEY CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
      scripts/with-build-lock.sh docker compose build > "$T/build.txt" 2>&1; code=$?; tail -2 "$T/build.txt"; [ "$code" = 0 ] || exit $code
      docker compose up -d --wait > "$T/up.txt" 2>&1; code=$?; tail -3 "$T/up.txt"; [ "$code" = 0 ] || exit $code
      start=$(date +%s)
      (cd "$A" && scripts/test-integration.sh -p no:cacheprovider > "$T/integration.txt" 2>&1); code=$?
      tail -1 "$T/integration.txt"
      grep -E "test_run_flow" "$T/integration.txt" | head -5
      echo "  통합 층 $(( $(date +%s) - start ))초"; exit $code'
  else
    not_run 2 "통합 층" "--with-containers 없음"
  fi
fi

# ── 9. runs 로 향하는 의존 0 ──
if wanted 9; then
  step 9 "다른 앱의 마이그레이션·모델이 runs 를 가리키지 않는다(양성 대조 먼저)" '
    pos="$(git grep -n -E "\(\"core\", \"0001_initial\"\)" -- "$E/runs/migrations/*.py")"; c=$?
    posf="$(git grep -n -F "to=\"core.documentrow\"" -- "$E/runs/migrations/*.py")"; cf=$?
    echo "  양성(의존): ${pos:-없음} (git grep EXIT=$c)"; echo "  양성(FK 글자): $(printf "%s\n" "$posf" | wc -l | tr -d " ")줄 (git grep EXIT=$cf)"
    [ "$c" = 0 ] && [ "$cf" = 0 ] || exit 1
    neg="$(git grep -n -E "\(\"runs\"," -- "$E/*/migrations/*.py" ":!$E/runs/**")"; n=$?
    negf="$(git grep -n -E "\"runs\.[A-Za-z]" -- "$E/*/models.py" "$E/*/models/*.py" "$E/*/migrations/*.py" ":!$E/runs/**")"; nf=$?
    echo "  runs 밖의 (\"runs\", 의존: ${neg:-0줄} (EXIT=$n) · \"runs. 모델 글자: ${negf:-0줄} (EXIT=$nf)"
    [ "$n" = 1 ] && [ "$nf" = 1 ]'
fi

# ── 10. 빠른 게이트 ──
if wanted 10; then
  step 10 "scripts/verify.sh --fast 끝 줄 VERIFY_FAST=PASS" 'start=$(date +%s); scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; tail -1 "$T/fast.log"; echo "  $(( $(date +%s) - start ))초"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
fi

# ── 11. 허용 경로 ──
if wanted 11; then
  step 11 "BASE 대비 바뀐 파일이 §4-11 허용 목록 안" '
    changed > "$T/changed.txt"
    grep -v -E \
      -e "^$E/runs/" \
      -e "^$E/core/(models|flows/__init__|flows/binding|calc/jobs|resources/ports/storage|resources/storage|resources/queue|observability/context|observability/jsonlog)\.py$" \
      -e "^$E/core/migrations/0001_initial\.py$" \
      -e "^$E/core/llm/(types|log|sink_db)\.py$" \
      -e "^$E/config/celery\.py$" \
      -e "^$E/core/tests/" \
      -e "^$E/config/tests/test_api_contract\.py$" \
      -e "^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$" \
      -e "^$A/tests/security/(test_runs|test_owner|test_same_company_foreign_keys|test_migrations|test_tenant_paths)\.py$" \
      -e "^$A/tests_integration/test_run_flow\.py$" \
      -e "^$A/tests/support/" \
      -e "^$A/scripts/(section4|planted-breaks)-X1b-1\.sh$" \
      "$T/changed.txt" > "$T/outside.txt"
    # runs/ 안의 jobs 셋은 0줄(§4-4 가 따로 본다), generated 는 ③ 에서만
    if [ "$COMMIT" -lt 3 ]; then grep -E "^$A/generated/" "$T/changed.txt" >> "$T/outside.txt"; fi
    echo "  바뀐 파일 $(wc -l < "$T/changed.txt" | tr -d " ")개 · 허용 밖 $(wc -l < "$T/outside.txt" | tr -d " ")개"
    sed "s/^/    /" "$T/changed.txt"
    sed "s/^/  ★ /" "$T/outside.txt"
    [ -s "$T/changed.txt" ] && [ ! -s "$T/outside.txt" ]'
fi

# ── 12. 실행기 대조(② 부터) ──
if wanted 12; then
  step 12 "run_flow( 는 runs/tasks.py 하나 · BINDINGS.get( 은 태스크(와 ③ 의 action) · runs 의 build_client 는 RunContext.llm 하나(mock=True)" 'helper runner'
fi

# ── 13. 키 꼴 0 · 작업 트리 ──
if wanted 13; then
  step 13 "diff 의 더한 줄·새 파일과 커밋 메시지에 sk- 키 꼴 0(양성 대조 1)" '
    pat="sk-[A-Za-z0-9_-]{20,}"
    a="$(git diff "$BASE" | grep "^+" | grep -c -E "$pat")"
    u=0; for f in $(git ls-files --others --exclude-standard); do u=$((u + $(grep -c -E "$pat" "$f"))); done
    b="$(git log --format=%B "$BASE"..HEAD | grep -c -E "$pat")"
    c=0; [ -n "${X1B1_MSG:-}" ] && c="$(grep -c -E "$pat" "$X1B1_MSG")"
    p="$(printf "sk-%s\n" AAAAAAAAAAAAAAAAAAAAAAAA | grep -c -E "$pat")"
    echo "  diff ${a}줄 · 새 파일 ${u}줄 · 커밋 메시지 ${b}줄 · 쓸 메시지(${X1B1_MSG:-없음}) ${c}줄 · 양성 대조 ${p}"
    [ "$a$u$b$c" = 0000 ] && [ "$p" = 1 ]'
  if [ "$AFTER" = 1 ]; then
    step 13 "git status --porcelain 0줄" 'n="$(git status --porcelain | wc -l | tr -d " ")"; echo "  ${n}줄"; [ "$n" = 0 ]'
  else
    step 13 "커밋 전: 스테이징 밖의 바뀜·새 파일 0(스테이징 줄 수는 적기만)" '
      s="$(git diff --cached --name-only | wc -l | tr -d " ")"
      w="$(git status --porcelain | grep -c -v -E "^[MADR] ")"
      echo "  스테이징 ${s}파일 · 스테이징 밖 ${w}줄"; git status --porcelain | grep -v -E "^[MADR] " | sed "s/^/  ★ /"
      [ "$w" = 0 ]'
  fi
fi

# ── 14. 기록 지점(③ 부터) ──
if wanted 14; then
  step 14 "제품 코드의 record_event( 부르는 자리 = 넷(note·confirm_upload·create_run·runs_file_get)" 'helper sites'
fi

echo
echo "── 기록: $T"
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
