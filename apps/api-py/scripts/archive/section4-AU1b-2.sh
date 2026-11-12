#!/usr/bin/env bash
# 밴드 AU1b-2 의 §4 자기검증(발주서 band-handoffs/AU1b-2-order.md §4, 개정 1·2). 줄마다 [n] … EXIT= 를 찍고 끝에
# SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-AU1b-2.sh --with-containers                                  전부(경계 2 = 커밋 ② 뒤)
#   apps/api-py/scripts/section4-AU1b-2.sh --boundary 1 --step 1,2,3,4,5,6,7,8,9,10,11,12 --with-containers  커밋 ① 의 단계
#   --with-containers   8 의 심은 파손에서 업무·보안 층의 것도 심는다(없으면 「안 돌림」 줄이 생겨 8 이 실패한다)
#
# 환경 변수:
#   AU1B2_BASE   기준 커밋(기본: 워크트리를 만든 main 0b076a7 = merge band/AU1b-1)
#   AU1B2_OUT    산출물 자리(기본: 워크트리 곁의 AU1b-2.out). collect-base.txt·collect-security-base.txt·
#                lint-imports-base.txt 가 여기 있어야 한다(커밋 ① 전에 BASE 에서 뜬 것)
#   AU1B2_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(12 가 BASE..HEAD 의 메시지와 함께 본다)
# 2·8 은 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${AU1B2_BASE:-0b076a7b3649bb56921d73cec726dfa26ab4608f}"
OUT="${AU1B2_OUT:-$SIDE/AU1b-2.out}"
S4="$OUT/section4"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

STEPS="all"
BOUNDARY=2
WITH_CONTAINERS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --boundary) BOUNDARY="${2:?--boundary 뒤에 1·2}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS="--with-containers"; shift ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
case "$BOUNDARY" in 1|2) ;; *) echo "--boundary 는 1·2"; exit 2 ;; esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD) BOUNDARY=$BOUNDARY"

HELPER="$S4/au1b2_helper.py"
cat > "$HELPER" <<'PY'
import ast
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
BOUNDARY = int(sys.argv[3])
CMD = sys.argv[4]
ARGS = sys.argv[5:]
API = "apps/api-py/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def at_base(path: str) -> str:
    return git("show", f"{BASE}:{path}")


def now(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def changed_files() -> set[str]:
    return set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())


# ── 3: openapi 의 바뀐 자리 ──────────────────────────────────────────

def leaves(node, prefix=""):
    """JSON 을 (포인터 → 값) 으로 편다. 사전·목록 모두 펼친다(목록은 parameters 의 name 으로 열쇠를 삼는다)."""
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


def ptr_escape(key: str) -> str:
    return key.replace("~", "~0").replace("/", "~1")


def leaves_doc(doc):
    out = {}
    for path, item in doc.get("paths", {}).items():
        out.update(leaves(item, f"/paths/{ptr_escape(path)}"))
    for k, v in doc.items():
        if k != "paths":
            out.update(leaves(v, f"/{k}"))
    return out


NEW_SCHEMAS = ["RunLogOut", "RunLogPageOut", "RunMetricsOut"]  # 개정 1 m5 — components 더함은 이 셋뿐
# 새로 생겨도 되는 잎(기존 잎은 하나도 바뀌지 않는다 — 더하기만)
ADDED_OK = [r"/paths/~1run-logs/.*", r"/paths/~1run-logs~1metrics/.*"] + [
    rf"/components/schemas/{name}/.*" for name in NEW_SCHEMAS
]

if CMD == "openapi-diff":
    base_doc = json.loads(at_base(API + "generated/openapi.json"))
    head_doc = json.loads(now(API + "generated/openapi.json"))
    b, h = leaves_doc(base_doc), leaves_doc(head_doc)
    changed = sorted(k for k in set(b) | set(h) if b.get(k, "<없음>") != h.get(k, "<없음>"))
    added_ok = [re.compile(p) for p in ADDED_OK]
    outside = [k for k in changed if k in b or not any(a.fullmatch(k) for a in added_ok)]
    print(f"  바뀐 잎 {len(changed)}(기존 잎이 바뀌거나 빠진 것과 목록 밖 더함 {len(outside)}: {outside[:20]})")
    paths = sorted(set(head_doc["paths"]) - set(base_doc["paths"]))
    gone_paths = sorted(set(base_doc["paths"]) - set(head_doc["paths"]))
    added_schemas = sorted(set(head_doc["components"]["schemas"]) - set(base_doc["components"]["schemas"]))
    gone_schemas = sorted(set(base_doc["components"]["schemas"]) - set(head_doc["components"]["schemas"]))
    print(f"  더한 경로 {paths} · 빠진 경로 {gone_paths}")
    print(f"  더한 components {added_schemas} · 빠진 components {gone_schemas}")
    ops = {
        (path, method): op.get("operationId")
        for path in paths
        for method, op in head_doc["paths"][path].items()
    }
    print(f"  더한 동작 {ops}")
    for (path, method) in sorted(ops):
        op = head_doc["paths"][path][method]
        names = [p.get("name") for p in op.get("parameters", [])]
        print(f"  {method.upper()} {path} 쿼리 {names} · 응답 {sorted(op['responses'])} · security {op.get('security')}")
    want_ops = {("/run-logs", "get"): "user_run_log_list", ("/run-logs/metrics", "get"): "user_run_log_metrics"}
    ok = (
        not outside
        and changed
        and ops == want_ops
        and not gone_paths
        and not gone_schemas
        and added_schemas == sorted(NEW_SCHEMAS)
    )
    raise SystemExit(0 if ok else 1)

if CMD == "sha":
    text = (ROOT / API / "generated/openapi.json").read_bytes()
    want = (ROOT / API / "generated/api.d.ts.source-sha256").read_text().strip()
    got = hashlib.sha256(text).hexdigest()
    print(f"  openapi sha256 {got} · 적힌 값 {want}")
    raise SystemExit(0 if got == want else 1)

# ── 4·10: 0줄 경로와 허용 경로(발주서 머리) ─────────────────────────────

P = r"^apps/api-py/"
E = P + r"esgapi/"
ZERO_PATHS = [
    r"^apps/web/", r"^packages/",
    P + r"\.importlinter$", E + r"config/(api|apps_list)\.py$", E + r"config/settings/",
    P + r"scripts/planted-breaks\.sh$",
    E + r"runs/models\.py$", E + r"runs/migrations/", E + r"runs/tasks\.py$", E + r"runs/context\.py$",
    E + r"runs/calc/", E + r"runs/management/", E + r"runs/service/(actions|apis|schemas|services)/",
    E + r"runs/service/selectors/(runs|jobs)\.py$",
    E + r"core/models\.py$", E + r"core/migrations/", E + r"core/llm/", E + r"core/flows/", E + r"core/service/services/",
    E + r"core/service/selectors/(audit|documents)\.py$", E + r"core/isolation/", E + r"core/observability/",
    E + r"user/models\.py$", E + r"user/migrations/", E + r"user/management/", E + r"user/service/(services|actions)/",
    E + r"user/service/selectors/user\.py$", E + r"user/service/apis/(audit|users|user|login)\.py$",
    E + r"(greenwash|inventory|reconcile|reference|organization|dataverify|translation)/",
    P + r"tests/security/(test_owner|test_migrations|test_runs|test_audit)\.py$", P + r"tests_integration/",
    P + r"(pyproject\.toml|uv\.lock)$", r"^compose\.yaml$", r"^README\.md$", r"^docs/",
]

ALLOWED_PATHS = [
    E + r"runs/service/selectors/operator\.py$",
    E + r"core/service/selectors/llm_usage\.py$",
    E + r"core/calc/run_metrics\.py$",
    E + r"core/permissions\.py$",
    E + r"user/service/apis/run_logs\.py$",
    E + r"user/service/schemas/run_logs\.py$",
    E + r"user/api\.py$",
    E + r"runs/tests/service/selectors/(__init__|test_operator)\.py$",
    E + r"core/tests/service/selectors/test_llm_usage\.py$",
    E + r"core/tests/calc/test_run_metrics\.py$",
    E + r"user/tests/service/apis/test_run_logs\.py$",
    E + r"core/tests/(test_permissions|test_permissions_wiring|test_selector_scope)\.py$",
    E + r"core/tests/isolation/test_static_rules\.py$",
    E + r"config/tests/(test_api_contract|test_api_errors|test_api_times)\.py$",
    P + r"generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$",
    P + r"tests/security/(test_run_logs|test_tenant_paths|test_login)\.py$",
    P + r"scripts/(section4|planted-breaks)-AU1b-2\.sh$",
]
# 경계 ① 에 바뀌면 안 되는 것(커밋 ② 의 몫 — 개정 1 m1: core/permissions.py 도)
ONLY_AFTER_1 = [
    E + r"core/permissions\.py$", E + r"core/tests/test_permissions(_wiring)?\.py$",
    E + r"user/service/apis/run_logs\.py$", E + r"user/service/schemas/run_logs\.py$", E + r"user/api\.py$",
    E + r"user/tests/service/apis/test_run_logs\.py$",
    E + r"config/tests/(test_api_contract|test_api_errors|test_api_times)\.py$",
    P + r"generated/", P + r"tests/security/",
]


def hits(paths: set[str], patterns: list[str]) -> list[str]:
    return sorted(p for p in paths if any(re.search(a, p) for a in patterns))


if CMD == "zero":
    changed = changed_files()
    bad = hits(changed, ZERO_PATHS)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)} · 0줄 경로와 교집합 {bad}")
    # 양성 대조: 0줄 경로 하나를 가짜로 더하면 잡힌다
    planted = "apps/api-py/esgapi/runs/migrations/0099_planted.py"
    positive = hits(changed | {planted}, ZERO_PATHS)
    print(f"  양성 대조(가짜 runs/migrations/0099_planted.py) → {positive}")
    raise SystemExit(1 if bad or not changed or positive != [planted] else 0)

if CMD == "allowed":
    changed = changed_files()
    outside = sorted(p for p in changed if not any(re.search(a, p) for a in ALLOWED_PATHS))
    early = hits(changed, ONLY_AFTER_1) if BOUNDARY < 2 else []
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)}:")
    for p in sorted(changed):
        print(f"    {p}")
    print(f"  허용 밖: {outside}")
    print(f"  경계 ① 에 커밋 ② 몫이 바뀜: {early}")
    planted = "apps/api-py/esgapi/runs/service/selectors/runs.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 runs/service/selectors/runs.py) 허용 밖 → {positive}")
    raise SystemExit(1 if outside or early or not changed or not positive else 0)

# ── 6: 시험 수·이름 ────────────────────────────────────────────────────

SECURITY_ADDED = {
    1: set(),
    2: {
        "tests/security/test_run_logs.py::test_a_customer_bearer_is_refused_on_both_paths",
        "tests/security/test_run_logs.py::test_choosing_b_shows_no_run_or_llm_line_of_a",
        "tests/security/test_run_logs.py::test_metrics_for_b_do_not_count_the_runs_of_a",
        "tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /run-logs]",
        "tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /run-logs/metrics]",
    },
}


def nodes(p: Path) -> set[str]:
    return {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}


if CMD == "collect":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed, added = sorted(before - after), sorted(after - before)
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)} · 더함 {len(added)}")
    for n in removed:
        print(f"    - {n}")
    for n in added:
        print(f"    + {n}")
    raise SystemExit(1 if removed or len(after) <= len(before) else 0)

if CMD == "collect-security":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed, added = sorted(before - after), set(after - before)
    print(f"  보안 층 BASE {len(before)} · 지금 {len(after)} · 빠짐 {removed}")
    for n in sorted(added):
        print(f"    + {n}")
    want = SECURITY_ADDED[BOUNDARY]
    print(f"  기대한 더함과 같은가: {added == want} (기대 밖 {sorted(added - want)} · 빠진 기대 {sorted(want - added)})")
    raise SystemExit(0 if not removed and added == want else 1)

# ── 7: 약화 대조(값은 BASE 재측 + n) ──────────────────────────────────

# (파일 끝부분, 지운 줄의 글자, 경계, 짝으로 더한 줄의 글자, 항목). 지운 줄 가운데 assert·==·len( 을 품은 것이 전부
# 여기 있어야 하고, 그 짝(더한 줄)도 그 파일에 있어야 한다.
CONTRACT = "esgapi/config/tests/test_api_contract.py"
ERRORS = "esgapi/config/tests/test_api_errors.py"
TIMES = "esgapi/config/tests/test_api_times.py"
PERM = "esgapi/core/tests/test_permissions.py"
LOGIN = "tests/security/test_login.py"
TENANT = "tests/security/test_tenant_paths.py"
MINUS = [
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert opened == 36", 1, "assert opened == 38",
     "§2-2 ① test_static_rules.py for_company( BASE 36 → 38(+2)"),
    ("esgapi/core/tests/test_selector_scope.py",
     "assert sorted(files) == [  # 분모: Selector 파일 일곱. 늘면 여기가 빨개져 새 파일의 조회를 보게 한다", 1,
     "assert sorted(files) == [  # 분모: Selector 파일 아홉(AU1b-2 +2). 늘면 여기가 빨개져 새 파일의 조회를 보게 한다",
     "§2-2 ① test_selector_scope.py selector 파일 BASE 7 → 9(+2)"),
    (CONTRACT, "assert len(found) == 40", 2, "assert len(found) == 42", "§2-2 ② operationId BASE 40 → 42"),
    (CONTRACT, "assert len(set(found.values())) == 40", 2, "assert len(set(found.values())) == 42",
     "§2-2 ② 고유 operationId BASE 40 → 42"),
    (CONTRACT, "assert (len(operations), len(with_body)) == (40, 17)", 2,
     "assert (len(operations), len(with_body)) == (42, 17)", "§2-2 ② (동작, 본문) BASE (40,17) → (42,17)"),
    (CONTRACT, "assert len(with_444) == 34", 2, "assert len(with_444) == 36", "§2-2 ② 444 선언 BASE 34 → 36"),
    (CONTRACT, "assert len(USER_ADMIN_OPERATIONS) == 6", 2, "assert len(USER_ADMIN_OPERATIONS) == 8",
     "§2-2 ② USER_ADMIN_OPERATIONS BASE 6 → 8(「17」 그대로)"),
    (ERRORS, "assert with_errors == 37  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1", 2,
     "assert with_errors == 39  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1",
     "§2-2 ② test_api_errors.py:67 BASE 37 → 39"),
    (ERRORS, "assert len(takers) == 34  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1", 2,
     "assert len(takers) == 36  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1",
     "§2-2 ② test_api_errors.py:82 BASE 34 → 36"),
    (TIMES, "assert len(names) == 18  # 분모(E2 바닥에서 셈): 스키마 9 의 시각 칸 · UA1 +1: CustomerUserOut.createdAt", 2,
     "assert len(names) == 21  # 분모(E2 바닥에서 셈): 스키마 9 의 시각 칸 · UA1 +1: CustomerUserOut.createdAt",
     "§2-2 ② test_api_times.py:73 BASE 18 → 21(+3: RunLogOut 의 시각 칸 셋)"),
    (PERM, "assert len(everything) == 40  # 분모: 공개 7 · 인증 33", 2,
     "assert len(everything) == 42  # 분모: 공개 7 · 인증 35", "§2-2 ② test_permissions.py:128 BASE 40 → 42"),
    (PERM, "assert len(NEEDS) == 33  # 분모: 회사 25 · 자기 2 · 운영 관리자 6(K2c·UA1·AU1a·AU1b-1)", 2,
     "assert len(NEEDS) == 35  # 분모: 회사 25 · 자기 2 · 운영 관리자 8(K2c·UA1·AU1a·AU1b-1·AU1b-2)",
     "§2-2 ② test_permissions.py:136 BASE 33 → 35"),
    (PERM, "assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 31  # 분모: 막힌 수", 2,
     "assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 33  # 분모: 막힌 수",
     "§2-2 ② test_permissions.py:207 BASE 31 → 33"),
    (LOGIN, "assert len(authenticated) == 33  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})", 2,
     "assert len(authenticated) == 35  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})",
     "§2-2 ② tests/security/test_login.py:281 BASE 33 → 35"),
    (LOGIN, "assert len(closed) == 31  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1", 2,
     "assert len(closed) == 33  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1",
     "§2-2 ② tests/security/test_login.py:303 BASE 31 → 33"),
    (TENANT, "assert (len(OPERATIONS), len(AUTHENTICATED)) == (40, 33)", 2,
     "assert (len(OPERATIONS), len(AUTHENTICATED)) == (42, 35)",
     "§2-2 ② tests/security/test_tenant_paths.py:273 BASE (40,33) → (42,35)"),
]

if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "*/tests/*", "apps/api-py/tests")
    current = None
    rows = []
    plus: dict[str, set[str]] = {}
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            current = line[6:]
        elif line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("-") and not line.startswith("---") and re.search(r"assert|==|len\(", line):
            rows.append((current, line[1:].strip()))
        elif line.startswith("+") and not line.startswith("+++"):
            plus.setdefault(current or "", set()).add(line[1:].strip())
    bad = 0
    for path, text in rows:
        hit = next(
            (
                (item, pair)
                for f, t, b, pair, item in MINUS
                if b <= BOUNDARY and path and path.endswith(f) and t == text
            ),
            None,
        )
        paired = hit is not None and hit[1] in plus.get(path or "", set())
        print(f"  - {path}: {text}\n      → {hit[0] if hit else '<항목 없음>'} · 짝 {'있음' if paired else '없음'}")
        bad += 0 if paired else 1
    print(f"  - 줄(assert·==·len() {len(rows)} · 항목·짝 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 11: 기록 지점(record_event 부르는 자리)이 BASE 와 같다 ─────────────


def sites(read_file, paths) -> set[tuple[str, str]]:
    found = set()
    for rel in paths:
        parts = rel.split("/")
        if not rel.endswith(".py") or "tests" in parts or "migrations" in parts:
            continue
        tree = ast.parse(read_file(rel))
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                for n in ast.walk(fn):
                    if isinstance(n, ast.Call):
                        name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else None
                        if name == "record_event":
                            found.add((rel, fn.name))
    return found


if CMD == "sites":
    base_paths = git("ls-tree", "-r", "--name-only", BASE, "--", API + "esgapi").split()
    head_paths = [p.relative_to(ROOT).as_posix() for p in (ROOT / API / "esgapi").rglob("*.py")]
    base = sites(at_base, base_paths)
    head = sites(now, head_paths)
    print(f"  BASE {sorted(base)}")
    print(f"  지금 {sorted(head)}")
    planted = ast.parse("def f():\n    audit.record_event(at=1)\n")
    positive = any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "record_event" for n in ast.walk(planted))
    raise SystemExit(0 if base == head and base and positive else 1)

# ── 12: 키 꼴 0 ───────────────────────────────────────────────────────

if CMD == "keys":
    pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    added = [l for l in git("diff", BASE).splitlines() if l.startswith("+")]
    for path in git("ls-files", "--others", "--exclude-standard").split():
        added += (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    messages = git("log", "--format=%B", f"{BASE}..HEAD")
    if ARGS and ARGS[0]:
        messages += Path(ARGS[0]).read_text(encoding="utf-8")
    found = [l for l in added if pattern.search(l)] + [l for l in messages.splitlines() if pattern.search(l)]
    positive = bool(pattern.search("sk-" + "A" * 24))
    print(f"  더한 줄 {len(added)} · 메시지 {len(messages.splitlines())}줄 · 키 꼴 {len(found)} · 양성 대조 {positive}")
    raise SystemExit(1 if found or not added or not positive else 0)

raise SystemExit(f"모르는 명령 {CMD}")
PY
helper() { api python "$HELPER" "$ROOT" "$BASE" "$BOUNDARY" "$@"; }

if want 1; then
  api pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$S4/1-pure.txt" 2>&1
  rc=$?
  tail -1 "$S4/1-pure.txt"
  report 1 "순수 층 초록" "$rc"
fi

if want 2; then
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider -n 2 \
    esgapi/core esgapi/runs esgapi/user esgapi/config) > "$S4/2-business.txt" 2>&1
  rc_b=$?
  tail -1 "$S4/2-business.txt"
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider) > "$S4/2-security.txt" 2>&1
  rc_s=$?
  tail -1 "$S4/2-security.txt"
  rc=0; [ "$rc_b" = "0" ] && [ "$rc_s" = "0" ] || rc=1
  echo "  통합 층(tests_integration): 안 돌림 — 이 밴드가 닿지 않는다(§1-12)"
  report 2 "업무·보안 층 초록(업무 ${rc_b} 보안 ${rc_s})" "$rc"
fi

if want 3; then
  if [ "$BOUNDARY" = "1" ]; then
    git -C "$ROOT" diff --quiet "$BASE" -- apps/api-py/generated
    rc_g=$?
    untracked="$(git -C "$ROOT" ls-files --others --exclude-standard -- apps/api-py/generated)"
    echo "  generated 의 BASE 와 차이: ${rc_g} · 추적 안 된 새 파일: ${untracked:-<없음>}"
    rc=0; [ "$rc_g" = "0" ] && [ -z "$untracked" ] || rc=1
    report 3 "계약(경계 ① generated 0바이트)" "$rc"
  else
    (cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business env -u OPENAI_API_KEY \
      uv run --frozen python manage.py export_openapi) > "$S4/3-openapi-now.json" 2> "$S4/3-openapi-now.err"
    rc_e=$?
    cmp -s "$S4/3-openapi-now.json" "$API_PY/generated/openapi.json"
    rc_cmp=$?
    helper sha > "$S4/3-sha.txt" 2>&1
    rc_sha=$?
    cat "$S4/3-sha.txt"
    api pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$S4/3-contract.txt" 2>&1
    rc_c=$?
    tail -1 "$S4/3-contract.txt"
    helper openapi-diff > "$S4/3-openapi-diff.txt" 2>&1
    rc_d=$?
    cat "$S4/3-openapi-diff.txt"
    rc=0
    for x in "$rc_e" "$rc_cmp" "$rc_sha" "$rc_c" "$rc_d"; do [ "$x" = "0" ] || rc=1; done
    report 3 "계약(뽑기 ${rc_e} cmp ${rc_cmp} sha ${rc_sha} 계약 시험 ${rc_c} 바뀐 자리 ${rc_d})" "$rc"
  fi
fi

if want 4; then
  helper zero > "$S4/4-zero.txt" 2>&1
  rc=$?
  cat "$S4/4-zero.txt"
  report 4 "0줄 경로(추적 안 된 새 파일 포함, 양성 대조)" "$rc"
fi

if want 5; then
  api lint-imports > "$S4/5-lint-imports.txt" 2>&1
  rc_l=$?
  last="$(grep -E '^Contracts:' "$S4/5-lint-imports.txt" | tail -1)"
  base_last="$(grep -E '^Contracts:' "$OUT/lint-imports-base.txt" 2>/dev/null | tail -1)"
  echo "  지금: $last · BASE: ${base_last:-<없음>}"
  # 계약 「나」: user 의 시험이 esgapi.runs.models 를 import 하지 않는다(lint-imports 는 user.** 를 보지만 글자로 한 번 더)
  # 계약 「다」: core.calc.run_metrics 가 django·runs·core.service 를 import 하지 않는다
  (cd "$ROOT" && git grep --untracked -n -E "^[[:space:]]*(from|import)[[:space:]]+esgapi\.runs\.models|^[[:space:]]*from[[:space:]]+esgapi\.runs[[:space:]]+import[[:space:]].*models|(import_module|__import__)\([^)]*esgapi\.runs\.models" -- apps/api-py/esgapi/user) > "$S4/5-user-runs-models.txt" 2>&1
  rc_u=$?
  n_u=$(wc -l < "$S4/5-user-runs-models.txt" | tr -d ' ')
  (cd "$ROOT" && git grep --untracked -n -E "^(from|import) (django|ninja|psycopg|esgapi\.runs|esgapi\.core\.service)" -- \
    apps/api-py/esgapi/core/calc/run_metrics.py) > "$S4/5-calc-imports.txt" 2>&1
  rc_k=$?
  n_k=$(wc -l < "$S4/5-calc-imports.txt" | tr -d ' ')
  # 양성 대조: 같은 꼴이 실제로 맞는 자리(runs 의 selector 가 runs.models 를 import 한다)
  (cd "$ROOT" && git grep --untracked -n -E "^from esgapi\.runs\.models" -- apps/api-py/esgapi/runs/service/selectors/operator.py) \
    > "$S4/5-positive.txt" 2>&1
  rc_p=$?
  echo "  user 의 esgapi.runs.models ${n_u}줄(git grep ${rc_u}) · run_metrics 의 금지 import ${n_k}줄(git grep ${rc_k}) · 양성 대조 git grep ${rc_p}"
  rc=0
  [ "$rc_l" = "0" ] && [ -n "$base_last" ] && [ "$last" = "$base_last" ] || rc=1
  [ "$rc_u" = "1" ] && [ "$n_u" = "0" ] || rc=1
  [ "$rc_k" = "1" ] && [ "$n_k" = "0" ] || rc=1
  [ "$rc_p" = "0" ] || rc=1
  report 5 "import 계약(BASE 와 같음, 「나」·「다」 글자)" "$rc"
fi

if want 6; then
  if [ ! -s "$OUT/collect-base.txt" ] || [ ! -s "$OUT/collect-security-base.txt" ]; then
    echo "  $OUT/collect-base.txt·collect-security-base.txt 가 없다(커밋 ① 전에 BASE 에서 떠 둘 것)"
    report 6 "시험 수·이름" 1
  else
    api pytest --collect-only -q -p no:cacheprovider esgapi tests > "$S4/6-collect-now.txt" 2>&1
    rc_c=$?
    helper collect "$OUT/collect-base.txt" "$S4/6-collect-now.txt" > "$S4/6-collect.txt" 2>&1
    rc_n=$?
    cat "$S4/6-collect.txt"
    api pytest --collect-only -q -p no:cacheprovider -m security tests > "$S4/6-collect-security-now.txt" 2>&1
    rc_s=$?
    helper collect-security "$OUT/collect-security-base.txt" "$S4/6-collect-security-now.txt" > "$S4/6-collect-security.txt" 2>&1
    rc_ss=$?
    cat "$S4/6-collect-security.txt"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] && [ "$rc_s" = "0" ] && [ "$rc_ss" = "0" ] || rc=1
    report 6 "시험 수·이름(사라진 id 0, 보안 층 차이 = 기대)" "$rc"
  fi
fi

if want 7; then
  helper weaken > "$S4/7-weaken.txt" 2>&1
  rc=$?
  cat "$S4/7-weaken.txt"
  report 7 "약화 대조(- 줄마다 §2-2 항목과 BASE+n 짝)" "$rc"
fi

if want 8; then
  "$API_PY/scripts/planted-breaks-AU1b-2.sh" --boundary "$BOUNDARY" $WITH_CONTAINERS > "$S4/8-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9]+ =>|P[0-9]+/|P0|PLANTED=|FINGERPRINT=)' "$S4/8-planted.txt"
  expect="PLANTED=9/9"; [ "$BOUNDARY" = "2" ] && expect="PLANTED=13/13"
  got="$(grep -E '^PLANTED=' "$S4/8-planted.txt" | tail -1)"
  skipped="$(grep -c '안 돌림' "$S4/8-planted.txt")"
  fp="$(grep -E '^FINGERPRINT=' "$S4/8-planted.txt" | tail -1)"
  echo "  기대 ${expect} · 받음 ${got} · 「안 돌림」 ${skipped}줄 · ${fp}"
  rc=0; [ "$rc_p" = "0" ] && [ "$got" = "$expect" ] && [ "$skipped" = "0" ] && [ "$fp" = "FINGERPRINT=same" ] || rc=1
  report 8 "심은 파손(${expect} 정확히)" "$rc"
fi

if want 9; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/9-verify-fast.txt" 2>&1
  rc=$?
  last="$(tail -1 "$S4/9-verify-fast.txt")"
  echo "  $last"
  [ "$last" = "VERIFY_FAST=PASS" ] || rc=1
  report 9 "게이트 verify.sh --fast" "$rc"
fi

if want 10; then
  helper allowed > "$S4/10-allowed.txt" 2>&1
  rc=$?
  cat "$S4/10-allowed.txt"
  report 10 "허용 경로(추적 안 된 새 파일 포함, 양성 대조)" "$rc"
fi

if want 11; then
  helper sites > "$S4/11-sites.txt" 2>&1
  rc=$?
  cat "$S4/11-sites.txt"
  report 11 "기록 지점 BASE 와 같음(record_event 부르는 자리)" "$rc"
fi

if want 12; then
  helper keys "${AU1B2_COMMIT_MSG_FILE:-}" > "$S4/12-keys.txt" 2>&1
  rc=$?
  cat "$S4/12-keys.txt"
  report 12 "키 꼴 0" "$rc"
fi

if want 13; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 13 "작업 트리 깨끗" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
