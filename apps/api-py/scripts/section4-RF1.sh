#!/usr/bin/env bash
# 밴드 RF1 의 §4 자기검증(발주서 band-handoffs/RF1-order.md §4 — AD4D 의 section4-AD4D.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝에 SECTION4_FAIL=<n>. 경계는 하나다.
# 사용(어디서든):
#   apps/api-py/scripts/section4-RF1.sh --with-containers                 전부
#   apps/api-py/scripts/section4-RF1.sh --step 1,2,3 --with-containers    고른 단계만
#   --with-containers   9 의 심은 파손에서 업무·보안 층의 것도 심는다(없으면 「안 돌림」 줄이 생겨 9 가 실패한다)
#
# 단계(§4): 1 순수 · 2 업무(core·runs·user·config)·보안 · 3 계약(generated 다시 뽑아 cmp·sha·계약 시험·바뀐 자리 —
#   경로 하나·동작 하나·component 0·runs_file_get 0) · 4 0줄 경로 · 5 lint-imports kept = BASE + runs 이름 검사 ·
#   6 makemigrations --check(0) · 7 수집(사라진 id 0, 수 BASE 이상) · 8 약화 대조 · 9 심은 파손 13/13 ·
#   10 verify.sh --fast · 11 바뀐 경로 ⊆ 허용 · 12 제품 record_event 자리 = BASE + 1 · 13 키 꼴 0 · 웹 typecheck ·
#   15 git status --porcelain 0(커밋 뒤에만 — 커밋 전에는 --step 으로 뺀다). 14(마이그레이션 왕복)는 없다 — 마이그레이션 0.
#
# 환경 변수:
#   RF1_BASE   기준 커밋(기본: 워크트리를 만든 main 1a45b1b = merge band/DV1d)
#   RF1_OUT    산출물 자리(기본: 워크트리 곁의 RF1.out). collect-base.txt·collect-security-base.txt·
#              lint-imports-base.txt 가 여기 있어야 한다(구현 전에 BASE 에서 뜬 것)
#   RF1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(13 이 BASE..HEAD 의 메시지와 함께 본다)
# 2·6·9 는 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${RF1_BASE:-1a45b1b}"
OUT="${RF1_OUT:-$SIDE/RF1.out}"
S4="$OUT/section4"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

STEPS="all"
BOUNDARY=1
WITH_CONTAINERS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --with-containers) WITH_CONTAINERS="--with-containers"; shift ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD)"

HELPER="$S4/rf1_helper.py"
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


# ── 3: openapi 의 바뀐 자리(§4-3 — 그 밖 = 멈춤) ──────────────────────────────

def leaves(node, prefix=""):
    """JSON 을 (포인터 → 값) 으로 편다. 목록은 parameters 의 name 으로 열쇠를 삼는다."""
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


# 바뀌어도 되는 잎: 새 경로 /run-logs/{run_id}/files/{name} 전부(component 0 · 다른 경로 0 — runs_file_get 포함)
CHANGED_OK = {1: [r"/paths/~1run-logs~1\{run_id\}~1files~1\{name\}(/.*)?"]}
NEW_SCHEMAS = {1: []}
NEW_OPS = {1: {("/run-logs/{run_id}/files/{name}", "get"): "user_run_log_file_get"}}
RUNS_FILE = "/runs/{run_id}/files/{name}"

if CMD == "openapi-diff":
    base_doc = json.loads(at_base(API + "generated/openapi.json"))
    head_doc = json.loads(now(API + "generated/openapi.json"))
    b, h = leaves_doc(base_doc), leaves_doc(head_doc)
    changed = sorted(k for k in set(b) | set(h) if b.get(k, "<없음>") != h.get(k, "<없음>"))
    ok_patterns = [re.compile(p) for n in range(1, BOUNDARY + 1) for p in CHANGED_OK[n]]
    outside = [k for k in changed if not any(a.fullmatch(k) for a in ok_patterns)]
    print(f"  바뀐 잎 {len(changed)} · 허용 밖 {len(outside)}: {outside[:20]}")
    for k in changed:
        print(f"    {k}: {json.dumps(b.get(k, '<없음>'), ensure_ascii=False)[:100]} → {json.dumps(h.get(k, '<없음>'), ensure_ascii=False)[:160]}")
    paths = sorted(set(head_doc["paths"]) - set(base_doc["paths"]))
    gone_paths = sorted(set(base_doc["paths"]) - set(head_doc["paths"]))
    added_schemas = sorted(set(head_doc["components"]["schemas"]) - set(base_doc["components"]["schemas"]))
    gone_schemas = sorted(set(base_doc["components"]["schemas"]) - set(head_doc["components"]["schemas"]))
    print(f"  더한 경로 {paths} · 빠진 경로 {gone_paths}")
    print(f"  더한 components {added_schemas} · 빠진 components {gone_schemas}")
    ops = {(path, method): op.get("operationId") for path in paths for method, op in head_doc["paths"][path].items()}
    print(f"  더한 동작 {ops}")
    print(f"  runs_file_get 동작 JSON 같음: {base_doc['paths'].get(RUNS_FILE) == head_doc['paths'].get(RUNS_FILE)}")
    ok = (
        not outside
        and bool(changed)
        and base_doc["paths"].get(RUNS_FILE) == head_doc["paths"].get(RUNS_FILE) is not None
        and ops == NEW_OPS[BOUNDARY]
        and not gone_paths
        and not gone_schemas
        and added_schemas == NEW_SCHEMAS[BOUNDARY]
    )
    raise SystemExit(0 if ok else 1)

if CMD == "sha":
    text = (ROOT / API / "generated/openapi.json").read_bytes()
    want = (ROOT / API / "generated/api.d.ts.source-sha256").read_text().strip()
    got = hashlib.sha256(text).hexdigest()
    print(f"  openapi sha256 {got} · 적힌 값 {want}")
    raise SystemExit(0 if got == want else 1)

# ── 4·11: 0줄 경로(§1-3)와 허용 경로(§1-2 ∪ §1-4) ─────────────────────────────

P = r"^apps/api-py/"
E = P + r"esgapi/"
W = r"^apps/web/"
ALLOWED_PATHS = {
    # §1-2 이 감독의 땅
    E + r"core/permissions\.py$": 1,
    E + r"runs/service/services/files\.py$": 1,
    E + r"runs/service/apis/runs\.py$": 1,
    E + r"runs/service/selectors/operator\.py$": 1,
    E + r"user/service/apis/run_logs\.py$": 1,
    E + r"runs/tests/service/services/test_files\.py$": 1,
    E + r"runs/tests/service/selectors/test_operator\.py$": 1,
    E + r"runs/tests/service/apis/(test_runs|test_runs_operator)\.py$": 1,
    E + r"user/tests/service/apis/test_run_logs\.py$": 1,
    E + r"core/tests/(test_permissions|test_permissions_wiring|test_transaction_rules|isolation/test_static_rules)\.py$": 1,
    E + r"config/tests/test_api_(contract|errors|times)\.py$": 1,
    P + r"generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$": 1,
    # §1-4 9f(보안·스크립트) — MARC-TICK-241 노트(test_login.py:313 은 덧 허락)
    P + r"scripts/(section4|planted-breaks)-RF1\.sh$": 1,
    P + r"tests/security/(test_run_logs|test_tenant_paths|test_login|test_operator_company)\.py$": 1,
}
ZERO_PATHS = [
    P + r"\.importlinter$", P + r"(pyproject\.toml|uv\.lock)$", E + r"[^/]+/migrations/",
    E + r"runs/models\.py$", E + r"runs/service/selectors/runs\.py$", E + r"runs/(tasks|context)\.py$",
    E + r"(greenwash|translation|dataverify|inventory)/", E + r"core/service/services/(audit|documents)\.py$",
    E + r"user/service/schemas/", P + r"tests_integration/", r"conftest\.py$", P + r"tests/support/", r"^apps/web/",
    P + r"scripts/(planted-breaks|verify|section4)\.sh$",
]
# §1-3 의 그 밖(tests/security 의 허락 밖 파일)은 11 의 허용 목록이 잰다.


def hits(paths: set[str], patterns: list[str]) -> list[str]:
    return sorted(p for p in paths if any(re.search(a, p) for a in patterns))


if CMD == "zero":
    changed = changed_files()
    bad = hits(changed, ZERO_PATHS)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)} · 0줄 경로와 교집합 {bad}")
    planted = "apps/api-py/esgapi/runs/migrations/0099_planted.py"
    positive = hits(changed | {planted}, ZERO_PATHS)
    print(f"  양성 대조(가짜 runs/migrations/0099_planted.py) → {positive}")
    raise SystemExit(1 if bad or not changed or positive != [planted] else 0)

if CMD == "allowed":
    changed = changed_files()
    outside, early = [], []
    for p in sorted(changed):
        found = [b for pattern, b in ALLOWED_PATHS.items() if re.search(pattern, p)]
        if not found:
            outside.append(p)
        elif min(found) > BOUNDARY:
            early.append(p)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)}:")
    for p in sorted(changed):
        print(f"    {p}")
    print(f"  허용 밖: {outside}")
    print(f"  뒤 경계 몫이 미리 바뀜: {early}")
    planted = "apps/api-py/esgapi/runs/models.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 runs/models.py) 허용 밖 → {positive}")
    raise SystemExit(1 if outside or early or not changed or not positive else 0)

# ── 7: 시험 수·이름 ────────────────────────────────────────────────────

SRUN = "tests/security/test_run_logs.py"
SECURITY_ADDED = {
    1: {
        SRUN + "::test_choosing_b_gets_404_on_a_file_of_a_run_of_a_like_a_missing_id",
        SRUN + "::test_a_customer_bearer_gets_no_run_file",
        "tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /run-logs/{run_id}/files/{name}]",
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

# ── 8: 약화 대조(- 줄의 assert·==·len( 이 §2-4·§1-4 짝) ──────────────────────

# (파일 끝부분, 지운 줄, 경계, 짝으로 더한 줄, 항목)
# (파일 끝부분, 지운 줄, 경계, 짝으로 더한 줄, 항목)
MINUS = [
    ("esgapi/config/tests/test_api_contract.py",
     "assert len(found) == 55  # TR2 +1 · AD4S +1 · AD4D +1", 1,
     "assert len(found) == 56  # TR2 +1 · AD4S +1 · AD4D +1 · RF1 +1",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/config/tests/test_api_contract.py",
     "assert len(set(found.values())) == 55  # TR2 +1 · AD4S +1 · AD4D +1", 1,
     "assert len(set(found.values())) == 56  # TR2 +1 · AD4S +1 · AD4D +1 · RF1 +1",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/config/tests/test_api_contract.py",
     "assert (len(operations), len(with_body)) == (55, 20)  # TR2 +1: GET /translation/runs/{run_id}/result · AD4S +1", 1,
     "assert (len(operations), len(with_body)) == (56, 20)  # TR2 +1: GET /translation/runs/{run_id}/result · AD4S +1",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/config/tests/test_api_contract.py",
     "assert len(with_444) == 49  # G1b-1 +1: GET /greenwash/checks · G2c2 +5: AI 설정 판 · AS2a +2: prompt-model 둘", 1,
     "assert len(with_444) == 50  # G1b-1 +1: GET /greenwash/checks · G2c2 +5: AI 설정 판 · AS2a +2: prompt-model 둘",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/config/tests/test_api_contract.py",
     "assert len(USER_ADMIN_OPERATIONS) == 10  # AD4S +1 · AD4D +1", 1,
     "assert len(USER_ADMIN_OPERATIONS) == 11  # AD4S +1 · AD4D +1 · RF1 +1",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/config/tests/test_api_errors.py",
     "assert with_errors == 52  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1", 1,
     "assert with_errors == 53  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/config/tests/test_api_errors.py",
     "assert len(takers) == 49  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1", 1,
     "assert len(takers) == 50  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1",
     "§2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/core/tests/test_permissions.py",
     "assert len(everything) == 55  # 분모: 공개 7 · 인증 48(G2c2 +5 · AS2a +2 · TR2 +1 · AD4S +1 · AD4D +1)", 1,
     "assert len(everything) == 56  # 분모: 공개 7 · 인증 49(G2c2 +5 · AS2a +2 · TR2 +1 · AD4S +1 · AD4D +1 · RF1 +1)",
     "감독 22 덧 허락 — §2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/core/tests/test_permissions.py",
     "assert len(NEEDS) == 48  # 분모: 고객사 10 · 회사 업무 19 · 자기 2 · 운영 관리자 17", 1,
     "assert len(NEEDS) == 49  # 분모: 고객사 10 · 회사 업무 19 · 자기 2 · 운영 관리자 18(RF1 +1)",
     "감독 22 덧 허락 — §2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/core/tests/test_permissions.py",
     "len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 46", 1,
     "len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 47",
     "감독 22 덧 허락 — §2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("esgapi/core/tests/test_transaction_rules.py",
     "assert len(files) == 24, [", 1,
     "assert len(files) == 25, [",
     "§2-1 services 파일 +1(runs 의 services/files.py — 쓰기 0)"),
    ("tests/security/test_login.py",
     "assert len(authenticated) == 48  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})", 1,
     "assert len(authenticated) == 49  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})",
     "9f 허락 — §2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("tests/security/test_login.py",
     "assert len(closed) == 46  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1", 1,
     "assert len(closed) == 47  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1",
     "9f 덧 허락(241 노트) — §2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
    ("tests/security/test_operator_company.py",
     "assert len(OPERATOR_OPERATIONS) == 17  # 분모(AD4S +1: user_run_log_export · AD4D +1: user_run_log_get)", 1,
     "assert len(OPERATOR_OPERATIONS) == 18  # 분모(AD4S +1: user_run_log_export · AD4D +1: user_run_log_get)",
     "9f 허락 — 운영 관리자 칸 17 → 18"),
    ("tests/security/test_tenant_paths.py",
     "assert (len(OPERATIONS), len(AUTHENTICATED)) == (55, 48)", 1,
     "assert (len(OPERATIONS), len(AUTHENTICATED)) == (56, 49)",
     "9f 허락 — §2-4 셈 +1(RF1 GET /run-logs/{run_id}/files/{name})"),
]

if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "*/tests/*", "apps/api-py/tests", "apps/web/src")
    current = None
    rows = []
    plus: dict[str, set[str]] = {}
    for line in diff.splitlines():
        if line.startswith("--- a/") or line.startswith("+++ b/"):
            current = line[6:]
        elif line.startswith("-") and not line.startswith("---") and re.search(r"assert|==|len\(|expect", line):
            rows.append((current, line[1:].strip()))
        elif line.startswith("+") and not line.startswith("+++"):
            plus.setdefault(current or "", set()).add(line[1:].strip())
    bad = 0
    for path, text in rows:
        hit = next(
            ((item, pair) for f, t, b, pair, item in MINUS if b <= BOUNDARY and path and path.endswith(f) and t == text),
            None,
        )
        paired = hit is not None and hit[1] in plus.get(path or "", set())
        print(f"  - {path}: {text}\n      → {hit[0] if hit else '<항목 없음>'} · 짝 {'있음' if paired else '없음'}")
        bad += 0 if paired else 1
    print(f"  - 줄(assert·==·len(·expect) {len(rows)} · 항목·짝 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 12: 제품의 record_event 부르는 자리(①② = BASE) ───────


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
    want = base | {("apps/api-py/esgapi/user/service/apis/run_logs.py", "run_log_file_get")}  # RF1 +1(감사 download)
    print(f"  BASE {len(base)} · 지금 {len(head)} · 더함 {sorted(head - base)} · 빠짐 {sorted(base - head)}")
    planted = ast.parse("def f():\n    audit.record_event(at=1)\n")
    positive = any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "record_event" for n in ast.walk(planted))
    raise SystemExit(0 if head == want and base and positive else 1)

# ── 13: 키 꼴 0 ───────────────────────────────────────────────────────

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
  echo "  통합 층(tests_integration): 안 돌림 — 이 밴드가 닿지 않는다(§4-2)"
  report 2 "업무·보안 층 초록(업무 ${rc_b} 보안 ${rc_s})" "$rc"
fi

if want 3; then
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
  api pytest -q -p no:cacheprovider esgapi/runs/tests/test_names.py > "$S4/5-names.txt" 2>&1
  rc_n=$?
  tail -1 "$S4/5-names.txt"
  rc=0
  [ "$rc_l" = "0" ] && [ -n "$base_last" ] && [ "$last" = "$base_last" ] && [ "$rc_n" = "0" ] || rc=1
  report 5 "import 계약 kept = BASE · runs 이름 검사" "$rc"
fi

if want 6; then
  (cd "$API_PY" && DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business env -u OPENAI_API_KEY \
    uv run --frozen python manage.py makemigrations --check --dry-run) > "$S4/6-makemigrations.txt" 2>&1
  rc=$?
  cat "$S4/6-makemigrations.txt"
  report 6 "makemigrations --check --dry-run" "$rc"
fi

if want 7; then
  if [ ! -s "$OUT/collect-base.txt" ] || [ ! -s "$OUT/collect-security-base.txt" ]; then
    echo "  $OUT/collect-base.txt·collect-security-base.txt 가 없다(경계 ① 전에 BASE 에서 떠 둘 것)"
    report 7 "시험 수·이름" 1
  else
    api pytest --collect-only -q -p no:cacheprovider esgapi tests > "$S4/7-collect-now.txt" 2>&1
    rc_c=$?
    helper collect "$OUT/collect-base.txt" "$S4/7-collect-now.txt" > "$S4/7-collect.txt" 2>&1
    rc_n=$?
    grep -v '^    +' "$S4/7-collect.txt"
    api pytest --collect-only -q -p no:cacheprovider -m security tests > "$S4/7-collect-security-now.txt" 2>&1
    rc_s=$?
    helper collect-security "$OUT/collect-security-base.txt" "$S4/7-collect-security-now.txt" > "$S4/7-collect-security.txt" 2>&1
    rc_ss=$?
    cat "$S4/7-collect-security.txt"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] && [ "$rc_s" = "0" ] && [ "$rc_ss" = "0" ] || rc=1
    report 7 "시험 수·이름(사라진 id 0, 보안 층 차이 = 기대)" "$rc"
  fi
fi

if want 8; then
  helper weaken > "$S4/8-weaken.txt" 2>&1
  rc=$?
  cat "$S4/8-weaken.txt"
  report 8 "약화 대조(- 줄마다 항목과 짝)" "$rc"
fi

if want 9; then
  "$API_PY/scripts/planted-breaks-RF1.sh" $WITH_CONTAINERS > "$S4/9-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9a-z]+ =>|P0=|PLANTED=|FINGERPRINT=)' "$S4/9-planted.txt"
  expect="PLANTED=13/13"  # 발주서 §3 의 P1~P12(P7 은 a·b 둘)
  got="$(grep -E '^PLANTED=' "$S4/9-planted.txt" | tail -1)"
  skipped="$(grep -c '안 돌림' "$S4/9-planted.txt")"
  fp="$(grep -E '^FINGERPRINT=' "$S4/9-planted.txt" | tail -1)"
  echo "  기대 ${expect} · 받음 ${got} · 「안 돌림」 ${skipped}줄 · ${fp}"
  rc=0; [ "$rc_p" = "0" ] && [ "$got" = "$expect" ] && [ "$skipped" = "0" ] && [ "$fp" = "FINGERPRINT=same" ] || rc=1
  report 9 "심은 파손(${expect} 정확히)" "$rc"
fi

if want 10; then
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" scripts/verify.sh --fast) > "$S4/10-verify-fast.txt" 2>&1
  rc=$?
  last="$(tail -1 "$S4/10-verify-fast.txt")"
  echo "  $last"
  [ "$last" = "VERIFY_FAST=PASS" ] || rc=1
  report 10 "게이트 verify.sh --fast" "$rc"
fi

if want 11; then
  helper allowed > "$S4/11-allowed.txt" 2>&1
  rc=$?
  cat "$S4/11-allowed.txt"
  report 11 "허용 경로(추적 안 된 새 파일 포함, 양성 대조)" "$rc"
fi

if want 12; then
  helper sites > "$S4/12-sites.txt" 2>&1
  rc=$?
  cat "$S4/12-sites.txt"
  report 12 "제품 record_event 자리(BASE + 1)" "$rc"
fi

if want 13; then
  helper keys "${RF1_COMMIT_MSG_FILE:-}" > "$S4/13-keys.txt" 2>&1
  rc_k=$?
  cat "$S4/13-keys.txt"
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" pnpm --dir apps/web typecheck) > "$S4/13-web-typecheck.txt" 2>&1
  rc_w=$?
  echo "  pnpm --dir apps/web typecheck EXIT=${rc_w}"
  rc=0; [ "$rc_k" = "0" ] && [ "$rc_w" = "0" ] || rc=1
  report 13 "키 꼴 0 · 웹 typecheck" "$rc"
fi

if want 15; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 15 "작업 트리 깨끗(커밋 뒤)" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
