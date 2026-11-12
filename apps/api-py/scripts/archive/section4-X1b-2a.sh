#!/usr/bin/env bash
# 밴드 X1b-2a(MARC-TICK-192: 문서 쪽 계약의 몸 — 목록·판 사슬·PATCH·원본·pageCount·hasText·고객사 GET /runs 의
# documentName)의 §4 자기검증(발주서 band-handoffs/X1b-2-order.md §4, 개정 1·2 — 2a 몫).
#   사용: apps/api-py/scripts/section4-X1b-2a.sh --commit <1|2|3|4> [--with-containers] [--after-commit] [--step <n>]
#   단계 1·2·3·4·5·6·7·9·10·11·13·14·15 는 커밋마다, 8(스키마 대조)은 커밋 ① 만(12 는 2b 몫 — 없음).
#   --with-containers 가 없으면 컨테이너 단계(2·8·15 의 업무·보안 층)는 「안 돌림」으로 찍고 실패로 센다(조용한 초록 금지).
#   --after-commit 이면 13 이 「작업 트리 0줄」을 본다(아니면 「스테이징 밖의 바뀜·새 파일 0」 — 커밋 전).
# 환경 변수: X1B2A_MSG(쓸 커밋 메시지 파일 — 13 이 키 꼴을 본다).
# 단계마다 「[n] <설명> EXIT=<n>」, 끝 줄 「SECTION4_FAIL=<n>」. 하나라도 0 이 아니면 1 로 끝난다.
# 전량 scripts/verify.sh 는 돌리지 않는다(감독 몫). AI 공급사 호출 0, 시험은 env -u OPENAI_API_KEY.
# 컨테이너는 이 워크트리의 compose 프로젝트(.env 의 COMPOSE_PROJECT_NAME)의 것만 띄운다. build 는
#   scripts/with-build-lock.sh 로만(기계 전체 하나). 띄운 벌은 내리지 않는다(러너가 끝에 내린다).
# 셸 규칙(bash 3.2): 명령 치환의 종료 코드는 다음 줄에서 받는다. 변수 바로 뒤에 한글이 오면 ${var}.
#   git grep 의 종료 ≥2 와 양성 대조 0 은 실패로 센다. git grep -E 에 \s 를 쓰지 않는다.
set -u
cd "$(dirname "$0")/../../.."
ROOT="$(pwd)"
BASE=181a483745404fb49f916c8642743961668156e8   # 워크트리를 세운 main(merge band/AU1b-2)
OUT="$ROOT/../X1b-2a.out"                        # 워크트리 밖. collect-base.txt·lint-imports-base.txt 가 여기 있다
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
    *) echo "사용: $0 --commit <1|2|3|4> [--step <n>] [--with-containers] [--after-commit]" >&2; exit 2 ;;
  esac
done
case "$COMMIT" in 1 | 2 | 3 | 4) ;; *) echo "--commit <1|2|3|4> 이 필요하다" >&2; exit 2 ;; esac

T="$(mktemp -d /private/tmp/x1b2.XXXXXX)"
case "$T" in /private/tmp/x1b2.*) ;; *) exit 99 ;; esac
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


def product_sources(read, paths):
    for rel in paths:
        parts = rel.split("/")
        if not rel.endswith(".py") or "tests" in parts or "migrations" in parts:
            continue
        yield rel, ast.parse(read(rel))


def head_paths() -> list[str]:
    return [p.relative_to(ROOT).as_posix() for p in sorted(PKG.rglob("*.py"))]


def base_paths() -> list[str]:
    return git("ls-tree", "-r", "--name-only", BASE, "--", API + "esgapi").split()


def at_base(rel: str) -> str:
    return git("show", f"{BASE}:{rel}")


def now(rel: str) -> str:
    return (ROOT / rel).read_text(encoding="utf-8")


def call_name(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return None


def call_sites(read, paths, name: str) -> set[tuple[str, str]]:
    found = set()
    for rel, tree in product_sources(read, paths):
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                for n in ast.walk(fn):
                    if isinstance(n, ast.Call) and call_name(n) == name:
                        found.add((rel.removeprefix(API), fn.name))
    return found


# ── 14: 기록 지점 ──
DOWNLOAD_SITE = {("esgapi/core/service/apis/documents.py", "documents_file_get")}

if CMD == "sites":
    base = call_sites(at_base, base_paths(), "record_event")
    head = call_sites(now, head_paths(), "record_event")
    want = base | (DOWNLOAD_SITE if COMMIT >= 2 else set())
    planted = ast.parse("def f():\n    audit.record_event(at=1)\n")
    positive = any(isinstance(n, ast.Call) and call_name(n) == "record_event" for n in ast.walk(planted))
    print(f"  BASE {len(base)} {sorted(base)}")
    print(f"  지금 {len(head)} {sorted(head)}")
    print(f"  기대 {len(want)}(커밋 ② 부터 원본 내려받기 하나 더) · 양성 대조 {positive}")
    raise SystemExit(0 if head == want and len(base) == 4 and positive else 1)

# ── 9: PDF 를 여는 자리 ──
if CMD == "pdf":
    def importers(read, paths) -> set[str]:
        hit = set()
        for rel, tree in product_sources(read, paths):
            for n in ast.walk(tree):
                names = [a.name for a in n.names] if isinstance(n, ast.Import) else [n.module or ""] if isinstance(n, ast.ImportFrom) else []
                if any(x == "pypdfium2" or x.startswith("pypdfium2.") for x in names):
                    hit.add(rel.removeprefix(API))
        return hit

    base, head = importers(at_base, base_paths()), importers(now, head_paths())
    print(f"  pypdfium2 를 import 하는 제품 파일: BASE {sorted(base)} · 지금 {sorted(head)}")
    adapter = API + "esgapi/core/resources/pdf.py"
    tree = ast.parse(now(adapter))
    child = next(
        (n.value.value for n in tree.body if isinstance(n, ast.AnnAssign | ast.Assign)
         and any(isinstance(t, ast.Name) and t.id == "_CHILD" for t in ([n.target] if isinstance(n, ast.AnnAssign) else n.targets))
         and isinstance(n.value, ast.Constant)),
        "",
    )
    runs = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr == "run"
            and isinstance(n.func.value, ast.Name) and n.func.value.id == "subprocess"]
    keywords = [sorted(k.arg for k in r.keywords if k.arg) for r in runs]
    print(f"  어댑터 부모의 pypdfium2 import: {'있음' if adapter.removeprefix(API) in head else '0'} · 자식 글에 「import pypdfium2」: "
          f"{'import pypdfium2' in child} · subprocess.run 부름 {len(runs)} · 키워드 {keywords}")
    ok = (
        base == head == {"esgapi/greenwash/tools/pdfium_locate.py"}
        and "import pypdfium2" in child
        and len(runs) == 1
        # ④(가지 리뷰 fix): capture_output 대신 stdout·stderr 를 임시 파일로(부모가 상한까지만 읽음), env={}
        and (({"timeout", "preexec_fn", "input", "stdout", "stderr", "env"} <= set(keywords[0])
              and "capture_output" not in keywords[0]) if COMMIT >= 4
             else {"timeout", "preexec_fn", "input", "capture_output"} <= set(keywords[0]))
    )
    raise SystemExit(0 if ok else 1)

# ── 6: 시험 수·이름 ──
DOC501 = {
    "esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[core_documents_list]",
    "esgapi/core/tests/service/apis/test_runs.py::test_each_run_operation_is_501_after_auth[core_documents_versions]",
    "esgapi/core/tests/test_documents_api.py::test_a_create_with_report_year_or_previous_is_501_and_writes_nothing[reportYear]",
    "esgapi/core/tests/test_documents_api.py::test_a_create_with_report_year_or_previous_is_501_and_writes_nothing[previousDocumentId]",
    "tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /documents]",
    "tests/security/test_tenant_paths.py::test_a_contract_only_route_is_501_and_writes_nothing[GET /documents/{document_id}/versions]",
}
GONE_OK = {1: set(), 2: DOC501, 3: DOC501, 4: DOC501}  # ④ = 가지 리뷰 fix(노드 빠짐 0)


def nodes(p: Path) -> set[str]:
    return {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}


if CMD == "collect":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed, added = sorted(before - after), sorted(after - before)
    allowed = GONE_OK[COMMIT]
    bad = [n for n in removed if n not in allowed]
    missing_allowed = sorted(allowed - set(removed))
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)}(허용 밖 {len(bad)}) · 더함 {len(added)}")
    for layer in ("esgapi/", "tests/security/"):
        print(f"    {layer} 앞 {sum(n.startswith(layer) for n in before)} · 뒤 {sum(n.startswith(layer) for n in after)}")
    for n in removed:
        print(f"    - {n}{'' if n in allowed else '   ★ 허용 밖'}")
    for n in added:
        print(f"    + {n}")
    if missing_allowed:
        print(f"  ★ 빠져야 하는데 남은 것 {missing_allowed}")
    raise SystemExit(1 if bad or missing_allowed or len(after) <= len(before) else 0)

if CMD == "collect-security":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed = sorted(before - after)
    allowed = {n for n in GONE_OK[COMMIT] if n.startswith("tests/security/")}
    bad = [n for n in removed if n not in allowed]
    print(f"  보안 층 BASE {len(before)} · 지금 {len(after)} · 빠짐 {removed}(허용 밖 {bad}) · 더함 {len(after - before)}")
    for n in sorted(after - before):
        print(f"    + {n}")
    # 보안 수집 수는 늘기만(§3-1 조건 2) — 커밋 ① 은 보안 층 0줄이라 같음
    grows = len(after) >= len(before) if COMMIT == 1 else len(after) > len(before)
    raise SystemExit(0 if not bad and grows else 1)

# ── 7: 약화 대조 ──
# (파일 끝부분, 지운 줄의 글자, 커밋, 짝으로 더한 줄의 글자, 항목). 지운 줄 가운데 assert·==·len(·parametrize 를 품은
# 것이 전부 여기 있어야 하고, 그 짝(더한 줄)도 그 파일에 있어야 한다.
MINUS = [
    ("esgapi/core/tests/test_documents_models.py", "assert len(DOCUMENT_COLUMNS) == 15  # X1b-1 +3", 1,
     "assert len(DOCUMENT_COLUMNS) == 16  # X1b-1 +3 · X1b-2a +1(has_text)",
     "§2-5 ① test_documents_models.py:76 DOCUMENT_COLUMNS 15 → 16(has_text)"),
    ("esgapi/core/tests/test_selector_scope.py",
     'assert opened == {"documents": 3, "jobs": 3, "audit": 1, "runs": 6}', 1,
     'assert opened == {"documents": 4, "jobs": 3, "audit": 1, "runs": 6}',
     "§2-5 ① test_selector_scope.py:272 쓰는 문 documents 3 → 4(PATCH 의 update)"),
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert opened == 38", 1, "assert opened == 39",
     "§2-5 ① test_static_rules.py:249 for_company( 38 → 38+k, k=1(update_document)"),
    ('esgapi/config/tests/test_api_contract.py', 'assert len(found) == 42', 2,
     'assert len(found) == 44',
     '§2-5 ② test_api_contract.py:182 동작 수 42 → 44'),
    ('esgapi/config/tests/test_api_contract.py', 'assert len(set(found.values())) == 42', 2,
     'assert len(set(found.values())) == 44',
     '§2-5 ② test_api_contract.py:183 42 → 44'),
    ('esgapi/config/tests/test_api_contract.py', 'assert (len(operations), len(with_body)) == (42, 17)', 2,
     'assert (len(operations), len(with_body)) == (44, 18)',
     '§2-5 ② :198 (42, 17) → (44, 18)'),
    ('esgapi/config/tests/test_api_contract.py', 'assert len(company) == 24  # 분모: 쿠키 인증이던 회사 동작 25 에서 GET /me 하나를 뺀 것', 2,
     'assert len(company) == 26  # 분모: 쿠키 인증이던 회사 동작 25 에서 GET /me 하나를 뺀 것 + X1b-2a 문서 둘(PATCH·원본)',
     '§2-5 ② :230 회사 동작 24 → 26'),
    ('esgapi/config/tests/test_api_contract.py', 'assert len(with_444) == 36', 2,
     'assert len(with_444) == 38',
     '§2-5 ② :235 with_444 36 → 38'),
    ('esgapi/config/tests/test_api_contract.py', 'assert len(keys) == 5', 2,
     'assert len(keys) == 7',
     '§2-5 ② :250 core_documents_ 동작 5 → 7'),
    ('esgapi/config/tests/test_api_contract.py', 'assert [key for key in keys if "requestBody" in operations[key]] == [("post", "/documents")]', 2,
     'assert [key for key in keys if "requestBody" in operations[key]] == [',
     '§2-5 ② :256 본문 있는 문서 동작 + PATCH'),
    ('esgapi/config/tests/test_api_contract.py', 'assert with_501 == (', 2,
     'assert with_501 == STILL_501 | (GREENWASH_CONTRACT_OPERATIONS - {("get", "/greenwash/terms/default")})',
     '§2-5 ② :470-488 with_501 의 문서 만들기 줄 빠짐'),
    ('esgapi/config/tests/test_api_errors.py', 'assert with_errors == 39  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1', 2,
     'assert with_errors == 41  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1',
     '§2-5 ② test_api_errors.py:67 with_errors 39 → 41'),
    ('esgapi/config/tests/test_api_errors.py', 'assert len(takers) == 36  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1', 2,
     'assert len(takers) == 38  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1',
     '§2-5 ② test_api_errors.py:83 takers 36 → 38'),
    ('esgapi/core/tests/service/apis/test_runs.py', 'assert error_of(client.get("/api/documents/7/versions")) == (501, "NOT_IMPLEMENTED")', 2,
     'assert error_of(client.get("/api/documents/7/versions")) == (404, "NOT_FOUND")  # X1b-2a, 감독 c1 허락',
     '표 밖 — 감독 c1 허락: test_runs.py:119 versions 501 → 404(몸이 섬)'),
    ('esgapi/core/tests/test_documents_api.py', '@pytest.mark.parametrize("field", ["reportYear", "previousDocumentId"])', 2,
     '# (X1b-2a: 두 칸의 501 시험은 몸 시험으로 갈음 — core/tests/service/apis/test_documents.py 의',
     '§2-5 ② test_documents_api.py:636-662 501 시험 → 몸 시험(짝 노드는 service/apis/test_documents.py)'),
    ('esgapi/core/tests/test_documents_api.py', 'body = {"fileName": "보고서 2025.pdf", "sizeBytes": len(PDF), field: 2025}', 2,
     '# (X1b-2a: 두 칸의 501 시험은 몸 시험으로 갈음 — core/tests/service/apis/test_documents.py 의',
     '§2-5 ② test_documents_api.py:636-662 501 시험 → 몸 시험(짝 노드는 service/apis/test_documents.py)'),
    ('esgapi/core/tests/test_documents_api.py', 'assert error_of(create(client, body)) == (501, "NOT_IMPLEMENTED")', 2,
     '# (X1b-2a: 두 칸의 501 시험은 몸 시험으로 갈음 — core/tests/service/apis/test_documents.py 의',
     '§2-5 ② test_documents_api.py:636-662 501 시험 → 몸 시험(짝 노드는 service/apis/test_documents.py)'),
    ('esgapi/core/tests/test_documents_api.py', 'assert (DocumentRow.unscoped.count(), JobRow.unscoped.count(), fake.presigned) == (0, 0, [])', 2,
     '# (X1b-2a: 두 칸의 501 시험은 몸 시험으로 갈음 — core/tests/service/apis/test_documents.py 의',
     '§2-5 ② test_documents_api.py:636-662 501 시험 → 몸 시험(짝 노드는 service/apis/test_documents.py)'),
    ('esgapi/core/tests/test_permissions.py', 'assert len(everything) == 42  # 분모: 공개 7 · 인증 35', 2,
     'assert len(everything) == 44  # 분모: 공개 7 · 인증 37',
     '§2-5 ② test_permissions.py:133 42 → 44'),
    ('esgapi/core/tests/test_permissions.py', 'assert len(NEEDS) == 35  # 분모: 회사 25 · 자기 2 · 운영 관리자 8(K2c·UA1·AU1a·AU1b-1·AU1b-2)', 2,
     'assert len(NEEDS) == 37  # 분모: 회사 27 · 자기 2 · 운영 관리자 8(K2c·UA1·AU1a·AU1b-1·AU1b-2)',
     '§2-5 ② test_permissions.py:141 35 → 37'),
    ('esgapi/core/tests/test_permissions.py', 'assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 33  # 분모: 막힌 수', 2,
     'len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 35',
     '표 밖 — 감독 c1 허락: test_permissions.py:214 막힌 수 33 → 35'),
    ('tests/security/test_login.py', 'assert len(authenticated) == 35  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})', 2,
     'assert len(authenticated) == 37  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})',
     '§2-5 ② test_login.py:281 35 → 37'),
    ('tests/security/test_login.py', 'assert len(closed) == 33  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1', 2,
     'assert len(closed) == 35  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1',
     '§2-5 ② test_login.py:303 33 → 35'),
    ('tests/security/test_tenant_paths.py', 'assert (len(OPERATIONS), len(AUTHENTICATED)) == (42, 35)', 2,
     'assert (len(OPERATIONS), len(AUTHENTICATED)) == (44, 37)',
     '§2-5 ② test_tenant_paths.py:276 (42, 35) → (44, 37)'),
    ('tests/security/test_tenant_paths.py', 'assert len(targets) == 24  # 분모: 쿠키 인증이던 회사 동작 25 에서 GET /me 를 뺀 것', 2,
     'assert len(targets) == 26  # 분모: 쿠키 인증이던 회사 동작 25 에서 GET /me 를 뺀 것 + X1b-2a 문서 둘',
     '§2-5 ② test_tenant_paths.py:315 24 → 26'),
    ('tests/security/test_tenant_paths.py', 'assert len(company_operations()) == 24  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다', 2,
     'assert len(company_operations()) == 26  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다',
     '§2-5 ② test_tenant_paths.py:344 24 → 26'),
    ('tests/security/test_tenant_paths.py', 'assert len(targets) == 24  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다', 2,
     'assert len(targets) == 26  # 분모: 대상이 비면 아래 고리가 아무것도 재지 않는다',
     '§2-5 ② test_tenant_paths.py:396 24 → 26'),
    ('esgapi/runs/tests/service/apis/test_runs.py',
     'assert set(item) == {"id", "module", "flowId", "documentId", "status", "createdAt", "finishedAt"}', 3,
     'assert set(item) == {"id", "module", "flowId", "documentId", "documentName", "status", "createdAt", "finishedAt"}',
     '§2-3 ③ runs test_runs.py 목록 줄 칸 +documentName'),
    ('esgapi/runs/tests/service/apis/test_runs.py',
     'assert [r["id"] for r in other.get("/api/runs").json()["results"]] == [theirs]', 3,
     'assert [(r["id"], r["documentName"]) for r in other.get("/api/runs").json()["results"]] == [',
     '§2-3 ③ runs test_runs.py 분모(B 의 세션) — 줄에 documentName 을 더 단언(넓힘)'),
]

if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "*/tests/*", "apps/api-py/tests", "apps/api-py/tests_integration")
    current = None
    rows = []
    plus: dict[str, set[str]] = {}
    for line in diff.splitlines():
        if line.startswith("--- "):
            current = line[6:] if line.startswith("--- a/") else None
        elif line.startswith("+++ "):
            current = line[6:] if line.startswith("+++ b/") else current
        elif line.startswith("-") and re.search(r"assert|==|len\(|parametrize", line):
            rows.append((current, line[1:].strip()))
        elif line.startswith("+"):
            plus.setdefault(current or "", set()).add(line[1:].strip())
    bad = 0
    for path, text in rows:
        hit = next(((item, pair) for f, t, c, pair, item in MINUS if c <= COMMIT and path and path.endswith(f) and t == text), None)
        paired = hit is not None and hit[1] in plus.get(path or "", set())
        print(f"  - {path}: {text}\n      → {hit[0] if hit else '<항목 없음>'} · 짝 {'있음' if paired else '없음'}")
        bad += 0 if paired else 1
    print(f"  - 줄(assert·==·len(·parametrize) {len(rows)} · 항목·짝 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 8: 스키마 대조(pg_dump 를 문장으로 나눠 견준다) ──
NEW_INDEX = re.compile(
    r"^CREATE UNIQUE INDEX core_documents_previous_uniq ON public\.core_documents USING btree "
    r"\(company_id, previous_document_id\) WHERE \(previous_document_id IS NOT NULL\)$"
)


def statements(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    return [s.strip() for s in text.split(";\n") if s.strip()]


if CMD == "schema":
    base, head = statements(Path(ARGS[0])), statements(Path(ARGS[1]))
    gone, new = sorted(set(base) - set(head)), sorted(set(head) - set(base))
    bad = []
    by_first = {s.splitlines()[0]: s for s in base}
    for s in new:
        flat = " ".join(s.split())
        if NEW_INDEX.match(flat):
            print(f"  + {flat}")
            continue
        first = s.splitlines()[0]
        old = by_first.get(first)
        if first.startswith("CREATE TABLE public.core_documents ") and old is not None:
            extra = [l for l in s.splitlines() if l not in old.splitlines() and l.rstrip(",") not in old.splitlines()]
            lost = [l for l in old.splitlines() if l not in s.splitlines() and l + "," not in s.splitlines()]
            if [l.strip().rstrip(",") for l in extra] == ["has_text boolean"] and not lost:
                print(f"  ~ {first} : 더한 줄 {[l.strip() for l in extra]}")
                continue
        bad.append(s)
    replaced = {s.splitlines()[0] for s in new}
    gone_bad = [s for s in gone if not (s.startswith("CREATE TABLE public.core_documents ") and s.splitlines()[0] in replaced)]
    print(f"  문장 BASE {len(base)} · HEAD {len(head)} · 새 {len(new)} · 빠짐 {len(gone)}(바뀐 것 밖 {len(gone_bad)}) · 허용 밖 {len(bad)}")
    for s in bad + gone_bad:
        print(f"  ★ 허용 밖: {' '.join(s.split())[:200]}")
    raise SystemExit(1 if bad or gone_bad or len(new) != 2 else 0)

if CMD == "grants":
    base = set(Path(ARGS[0]).read_text().splitlines())
    head = set(Path(ARGS[1]).read_text().splitlines())
    print(f"  권한 행 BASE {len(base)} · HEAD {len(head)} · 더함 {sorted(head - base)} · 빠짐 {sorted(base - head)}")
    raise SystemExit(0 if base == head and base else 1)

# ── 3: openapi 의 바뀐 자리(②③) ──
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


# 처분 ⑱ 의 차이 목록(커밋마다). 잎의 경로 꼴: /paths/<~1 로 바꾼 경로>/<메서드>/… 와 /components/…
DOC = r"^/paths/~1documents"
ONE = r"^/paths/~1documents~1\{document_id\}"
SCH = r"^/components/schemas/"
ALLOWED_OPENAPI: dict[int, list[str]] = {
    2: [
        # ① 목록·versions·만들기의 501 빠짐
        DOC + r"/(get|post)/responses/501/",
        ONE + r"~1versions/get/responses/501/",
        # ② 새 동작 둘(PATCH core_documents_update·원본 core_documents_file_get)과 꼴 DocumentPatchIn
        ONE + r"/patch/",
        ONE + r"~1file/",
        SCH + r"DocumentPatchIn/",
        # ③ DocumentOut.hasText(필수 칸 — null 허용), DocumentListItemOut 이 이어받음(required 의 자리가 밀림)
        SCH + r"Document(Out|ListItemOut)/properties/hasText/",
        SCH + r"DocumentOut/required/10$",
        SCH + r"DocumentListItemOut/required/1[01]$",
        # ④ 목록 쿼리 uploadedBy·latestOnly, q 의 NUL 막는 pattern
        SCH + r"DocumentListQuery/properties/(uploadedBy|latestOnly)/",
        DOC + r"/get/parameters/(uploadedBy|latestOnly)/",
        SCH + r"DocumentListQuery/properties/q/anyOf/0/pattern$",
        DOC + r"/get/parameters/q/schema/anyOf/0/pattern$",
        # ⑤ reportYear 범위(만들기·목록 — PATCH 는 ② 의 새 꼴 안)
        SCH + r"Document(In|ListQuery)/properties/reportYear/anyOf/0/(minimum|maximum)$",
        DOC + r"/get/parameters/reportYear/schema/anyOf/0/(minimum|maximum)$",
        # ⑥ docstring 「세 역할 모두」 → 「고객사 사용자」(목록·단건·versions)
        DOC + r"/get/description$",
        ONE + r"/get/description$",
        ONE + r"~1versions/get/description$",
    ],
    3: [
        # ⑧ RunSummaryOut.documentName(필수 — required 에 documentId 뒤로 끼어 뒤 셋의 자리가 밀림)
        SCH + r"RunSummaryOut/properties/documentName/",
        SCH + r"RunSummaryOut/required/[4-7]$",
        # ⑨ RunIn.options 의 default {}(Field(default={}) — 동작 0)
        SCH + r"RunIn/properties/options/default",
    ],
    4: [],  # ④ 가지 리뷰 fix(pdf.py 출력 상한·빈 환경) — 계약 0바이트
}

if CMD == "openapi-diff":
    base_doc = json.loads(at_base(API + "generated/openapi.json"))
    head_doc = json.loads(now(API + "generated/openapi.json"))
    b, h = leaves_doc(base_doc), leaves_doc(head_doc)
    changed = sorted(k for k in set(b) | set(h) if b.get(k, "<없음>") != h.get(k, "<없음>"))
    allowed = [re.compile(p) for c in range(2, COMMIT + 1) for p in ALLOWED_OPENAPI[c]]
    outside = [k for k in changed if not any(a.search(k) for a in allowed)]
    print(f"  바뀐 잎 {len(changed)} · 목록 밖 {len(outside)}")
    for k in changed:
        print(f"    {'+' if k not in b else '-' if k not in h else '~'} {k}{'   ★ 목록 밖' if k in outside else ''}")
    raise SystemExit(1 if outside or not changed else 0)

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
    *:1 | *:2 | *:3 | *:4 | *:5 | *:6 | *:7 | *:9 | *:10 | *:11 | *:13 | *:14 | *:15) return 0 ;;
    1:8) return 0 ;;
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
gate() { # 기계 문: 자기 밖 esg-app* 프로젝트 ≤ 2, 빌드 중 0, free ≥ 20%, 1분 부하 < 24. 60초 간격, 최대 30분.
  local tries=0 free load others building me
  me="$(env_value COMPOSE_PROJECT_NAME)"
  while :; do
    others="$(docker ps --format '{{.Label "com.docker.compose.project"}}' | grep '^esg-app' | grep -v -x -F "$me" | sort -u | wc -l | tr -d " ")"
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
export -f env_value changed helper gate
export ROOT BASE OUT A E T COMMIT

echo "── 밴드 X1b-2a §4 · 커밋 $COMMIT · BASE ${BASE:0:7} · HEAD $(git rev-parse --short HEAD) · 기록 $T · $(uptime | sed 's/.*load/load/')"

# ── 1. 순수 층 ──
if wanted 1; then
  step 1 "순수 층 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$T/pure.txt" 2>&1; code=$?; tail -1 "$T/pure.txt"; exit $code)'
fi

# ── 3. 계약 ──
if wanted 3; then
  if [ "$COMMIT" = 1 ]; then
    step 3 "generated 0바이트(커밋 ①)" 'git diff --quiet "$BASE" -- "$A/generated"; code=$?; new="$(git ls-files --others --exclude-standard -- "$A/generated" | wc -l | tr -d " ")"; echo "  git diff EXIT=$code · 새 파일 $new"; [ "$code" = 0 ] && [ "$new" = 0 ]'
  else
    step 3 "다시 뽑은 openapi 와 generated/openapi.json 의 cmp" '(cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business uv run --frozen python manage.py export_openapi > "$T/openapi.json" 2> "$T/export.err"; code=$?; [ "$code" = 0 ] || { tail -3 "$T/export.err"; exit $code; }; cmp "$T/openapi.json" generated/openapi.json)'
    step 3 "api.d.ts.source-sha256 = openapi 의 sha256" 'helper sha'
    step 3 "config/tests/test_api_contract.py 초록" '(cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$T/contract.txt" 2>&1; code=$?; tail -1 "$T/contract.txt"; exit $code)'
    step 3 "openapi 의 바뀐 자리 = 처분 ⑱ 의 그 커밋까지 몫" 'helper openapi-diff'
  fi
fi

# ── 4. 0줄 ──
if wanted 4; then
  step 4 "0줄 경로(§1-9·§4-4)" '
    P="packages $E/greenwash $E/inventory $E/reconcile $E/reference $E/organization $E/user $E/dataverify $E/translation $E/runs/tasks.py $E/runs/context.py $E/runs/calc $E/runs/service/services $E/runs/service/selectors/operator.py $E/runs/service/actions $E/runs/models.py $E/runs/migrations $E/runs/management $E/core/auth $E/core/tenancy $E/core/flows $E/core/llm $E/core/isolation $E/core/service/services/audit.py $E/core/service/selectors/audit.py $E/core/calc/audit.py $E/config/api.py $E/config/apps_list.py $E/config/settings $A/.importlinter $A/scripts/planted-breaks.sh $A/scripts/test-layout-allow.txt $A/pyproject.toml $A/uv.lock compose.yaml infra docker README.md docs $A/tests/security/test_migrations.py $A/tests/security/test_same_company_foreign_keys.py $A/tests/security/test_owner.py $A/tests/security/test_audit.py $A/tests/security/test_run_logs.py $A/tests/security/test_runs.py $A/tests/security/conftest.py"
    git diff --quiet "$BASE" -- $P; code=$?
    new="$(git ls-files --others --exclude-standard -- $P | wc -l | tr -d " ")"
    echo "  git diff EXIT=$code · 추적 안 된 새 파일 $new"
    # apps/web 은 커밋 ③ 의 fixtures.ts 한 파일(6·0) 밖 0줄
    web="$(git diff --name-only "$BASE" -- apps/web; git ls-files --others --exclude-standard -- apps/web)"
    webbad="$(printf "%s\n" "$web" | grep -v -x -F "apps/web/src/entities/run-log/api/mock/fixtures.ts" | grep -c .)"
    [ "$COMMIT" -ge 3 ] || webbad="$(printf "%s\n" "$web" | grep -c .)"
    echo "  apps/web 바뀐 파일: [$(printf "%s " $web)] · 허용 밖 $webbad"
    # tests/support·tests_integration 은 새 파일만(기존 파일 0줄)
    git diff --quiet --diff-filter=MDR "$BASE" -- "$A/tests/support" "$A/tests_integration"; sup=$?
    echo "  tests/support·tests_integration 기존 파일 고침 EXIT=$sup"
    # 새 마이그레이션 파일 0(처분 ④ (가) — core 0001 다시 쓰기)
    extra="$(git ls-files --others --exclude-standard -- "$E/*/migrations/*")$(git diff --name-only --diff-filter=A "$BASE" -- "$E/*/migrations/*")"
    echo "  새 마이그레이션 파일: [${extra}]"
    [ "$code" = 0 ] && [ "$new" = 0 ] && [ "$webbad" = 0 ] && [ "$sup" = 0 ] && [ -z "$extra" ]'
fi

# ── 5. import 계약 ──
if wanted 5; then
  step 5 "lint-imports 의 Contracts 줄 = BASE(lint-imports-base.txt)" '(cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint.txt" 2>&1; code=$?; now="$(grep -E "^Contracts:" "$T/lint.txt" | tail -1)"; base="$(grep -E "^Contracts:" "$OUT/lint-imports-base.txt" | tail -1)"; echo "  지금: $now · BASE: ${base:-<없음>}"; [ "$code" = 0 ] && [ -n "$base" ] && [ "$now" = "$base" ])'
  step 5 "양성 대조: 새 파일을 계약 가·다 가 문다(심고 되돌림)" '
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
    plant "$E/core/resources/pdf.py" "import esgapi.greenwash  # noqa" "가\\..*" || exit 1
    plant "$E/core/calc/versions.py" "import django  # noqa" "다\\..*" || exit 1
    (cd "$A" && COLUMNS=400 uv run --frozen lint-imports --no-cache > "$T/lint-after.txt" 2>&1); c=$?
    echo "  되돌린 뒤: $(grep -E "^Contracts:" "$T/lint-after.txt" | tail -1) EXIT=$c"; exit $c'
fi

# ── 6. 시험 수·이름 ──
if wanted 6; then
  step 6 "수집한 노드 id: 사라진 것 = §3-1 조건 3 의 목록뿐, 수는 늚" '
    test -s "$OUT/collect-base.txt" || { echo "  collect-base.txt 가 없다"; exit 1; }
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider esgapi tests/security > "$T/collect-now.txt" 2>&1); code=$?
    tail -1 "$OUT/collect-base.txt" | sed "s/^/  앞: /"; tail -1 "$T/collect-now.txt" | sed "s/^/  뒤: /"
    helper collect "$OUT/collect-base.txt" "$T/collect-now.txt" > "$T/collect.txt" 2>&1; c=$?
    cat "$T/collect.txt"
    (cd "$A" && env -u OPENAI_API_KEY uv run --frozen pytest --collect-only -q -p no:cacheprovider -m security tests > "$T/collect-security.txt" 2>&1); s=$?
    helper collect-security "$OUT/collect-security-base.txt" "$T/collect-security.txt" > "$T/collect-security-diff.txt" 2>&1; sd=$?
    cat "$T/collect-security-diff.txt"
    n_int="$(git grep -h -c -E "^(async )?def test_" -- "$A/tests_integration/*.py" | paste -sd+ - | bc)"
    echo "  통합 층 시험 함수(def test_ 셈): 앞 26(BASE grep) · 뒤 ${n_int}"
    [ "$code" = 0 ] && [ "$c" = 0 ] && [ "$s" = 0 ] && [ "$sd" = 0 ]'
fi

# ── 7. 약화 대조 ──
if wanted 7; then
  step 7 "시험 diff 의 - 줄(assert·==·len(·parametrize)마다 §2-5 항목과 짝" 'helper weaken'
fi

# ── 2·8. 컨테이너 ──
PROJECT="$(env_value COMPOSE_PROJECT_NAME)"
OWNER="$(env_value POSTGRES_OWNER_USER)"
export PROJECT OWNER

if [ "$CONTAINERS" = 1 ] && { wanted 2 || wanted 8; }; then
  step "2·8" "Postgres 한 벌($PROJECT)" '
    test -n "$PROJECT" && test "$PROJECT" != esg-app || exit 1
    gate || exit 1
    docker compose up -d --wait postgres 2>&1 | tail -2; exit "${PIPESTATUS[0]}"'
fi

if wanted 2; then
  if [ "$CONTAINERS" = 1 ]; then
    step 2 "업무 층(core·runs·config·reconcile·user)" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider --create-db esgapi/core esgapi/runs esgapi/config esgapi/reconcile esgapi/user > "$T/business.txt" 2>&1; code=$?; tail -1 "$T/business.txt"; exit $code)'
    step 2 "보안 층 전부" '(cd "$A" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider > "$T/security.txt" 2>&1; code=$?; tail -1 "$T/security.txt"; exit $code)'
    step 2 "통합 층(이미지는 with-build-lock.sh 로 짓고 compose 전부를 띄운다)" '
      gate || exit 1
      EDK_JWT_PUBLIC_KEY="$(cd "$A" && uv run --frozen python scripts/dev_edk.py public-key)" || exit 1
      export EDK_JWT_PUBLIC_KEY CELERY_WAIT_TIME_SECONDS=2 JOB_RETRY_DELAY_SECONDS=1
      scripts/with-build-lock.sh docker compose build > "$T/build.txt" 2>&1; code=$?; tail -2 "$T/build.txt"; [ "$code" = 0 ] || exit $code
      docker compose up -d --wait > "$T/up.txt" 2>&1; code=$?; tail -3 "$T/up.txt"; [ "$code" = 0 ] || exit $code
      start=$(date +%s)
      (cd "$A" && scripts/test-integration.sh -p no:cacheprovider > "$T/integration.txt" 2>&1); code=$?
      tail -1 "$T/integration.txt"
      echo "  통합 층 $(( $(date +%s) - start ))초"; exit $code'
  else
    not_run 2 "업무·보안·통합 층" "--with-containers 없음"
  fi
fi

if wanted 8; then
  if [ "$CONTAINERS" = 1 ]; then
    step 8 "스키마 대조: BASE 트리와 지금 트리로 빈 DB 둘에 migrate → pg_dump --schema-only(db 컨테이너 안) 견줌" '
      set -e
      D="$T/base-tree"; mkdir -p "$D"
      case "$D" in /private/tmp/x1b2.*) ;; *) exit 99 ;; esac
      git archive "$BASE" "$A" | tar -x -C "$D"
      PY="$ROOT/$A/.venv/bin/python"
      host="127.0.0.1:$(env_value POSTGRES_PORT)"
      pw="$(env_value POSTGRES_OWNER_PASSWORD)"
      URL_BASE="postgres://$OWNER:$pw@$host/x1b2a_schema_base"; URL_HEAD="postgres://$OWNER:$pw@$host/x1b2a_schema_head"
      for db in x1b2a_schema_base x1b2a_schema_head; do
        docker compose exec -T postgres psql -q -U "$OWNER" -d postgres -c "DROP DATABASE IF EXISTS $db" -c "CREATE DATABASE $db" > /dev/null
      done
      set +e
      (cd "$D/$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_BASE" "$PY" manage.py migrate --no-input > "$T/migrate-base.txt" 2>&1); c1=$?
      (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_HEAD" "$PY" manage.py migrate --no-input > "$T/migrate-head.txt" 2>&1); c2=$?
      echo "  migrate BASE EXIT=$c1 · HEAD EXIT=$c2"
      [ "$c1" = 0 ] && [ "$c2" = 0 ] || { tail -5 "$T/migrate-base.txt" "$T/migrate-head.txt"; exit 1; }
      for side in base head; do
        docker compose exec -T postgres pg_dump -U "$OWNER" --schema-only --no-owner "x1b2a_schema_$side" | grep -v -E "^(--|SET |SELECT pg_catalog.set_config|\\\\(un)?restrict )" > "$T/dump-$side.sql"
        docker compose exec -T postgres psql -At -U "$OWNER" -d "x1b2a_schema_$side" -f - < "$T/grants.sql" > "$T/grants-$side.txt"
      done
      wc -l "$T/dump-base.sql" "$T/dump-head.sql" | sed "s/^/  /"
      helper schema "$T/dump-base.sql" "$T/dump-head.sql"; d1=$?
      helper grants "$T/grants-base.txt" "$T/grants-head.txt"; d2=$?
      (cd "$A" && env -u OPENAI_API_KEY DJANGO_SETTINGS_MODULE=esgapi.config.settings.migrate DATABASE_URL_PY_OWNER="$URL_HEAD" "$PY" manage.py makemigrations --check --dry-run > "$T/makemigrations.txt" 2>&1); c3=$?
      grep -v -E "RuntimeWarning|warnings.warn" "$T/makemigrations.txt" | sed "s/^/  makemigrations: /"
      for db in x1b2a_schema_base x1b2a_schema_head; do
        docker compose exec -T postgres psql -q -U "$OWNER" -d postgres -c "DROP DATABASE IF EXISTS $db" > /dev/null
      done
      [ "$d1" = 0 ] && [ "$d2" = 0 ] && [ "$c3" = 0 ] && [ -s "$T/dump-base.sql" ] && [ -s "$T/grants-base.txt" ]'
  else
    not_run 8 "스키마 대조" "--with-containers 없음"
  fi
fi

# ── 9. PDF 를 여는 자리 ──
if wanted 9; then
  step 9 "pypdfium2 를 import 하는 제품 파일 = greenwash/tools/pdfium_locate.py 하나(BASE 와 같음) · 어댑터는 자식 글에만 · subprocess.run 에 timeout=" 'helper pdf'
fi

# ── 10. 빠른 게이트 ──
if wanted 10; then
  step 10 "scripts/verify.sh --fast 끝 줄 VERIFY_FAST=PASS" 'start=$(date +%s); scripts/verify.sh --fast > "$T/fast.log" 2>&1; code=$?; tail -1 "$T/fast.log"; echo "  $(( $(date +%s) - start ))초"; grep -q "^VERIFY_FAST=PASS$" "$T/fast.log" && exit $code; exit 1'
fi

# ── 11. 허용 경로 ──
if wanted 11; then
  # config/tests/test_request_schemas_reject_bool.py: 커밋 ② 의 표 밖 셈(BODY_OPERATIONS 등) — 감독 c1 허락(2026-10-19 밤)
  # tests/security/test_jobs.py: 테스트 감독 39 허락(sid:MARC-TICK-71 노트, 2026-10-19 밤) — uploaded() 의 D6 읽기 못 박고 비우기
  step 11 "BASE 대비 바뀐 파일이 §4-11 허용 목록 안(커밋까지의 몫)" '
    changed > "$T/changed.txt"
    grep -v -E \
      -e "^$E/core/(models|calc/documents|calc/versions|resources/ports/pdf|resources/pdf)\.py$" \
      -e "^$E/core/migrations/0001_initial\.py$" \
      -e "^$E/core/service/(selectors|services)/documents\.py$" \
      -e "^$E/core/tests/" \
      -e "^$A/scripts/(section4|planted-breaks)-X1b-2a\.sh$" \
      -e "^$A/tests/security/test_jobs\.py$" \
      "$T/changed.txt" > "$T/outside.txt"
    if [ "$COMMIT" -ge 2 ]; then
      grep -v -E \
        -e "^$E/core/permissions\.py$" -e "^$E/core/service/(apis|schemas)/documents\.py$" \
        -e "^$E/config/tests/(test_api_contract|test_api_errors)\.py$" \
        -e "^$E/config/tests/test_request_schemas_reject_bool\.py$" \
        -e "^$A/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$" \
        -e "^$A/tests/security/(test_tenant_paths|test_login|test_documents_chain)\.py$" \
        -e "^$A/tests_integration/test_document_file\.py$" \
        "$T/outside.txt" > "$T/outside2.txt"; mv "$T/outside2.txt" "$T/outside.txt"
    fi
    if [ "$COMMIT" -ge 3 ]; then
      grep -v -E \
        -e "^$E/runs/service/(apis|schemas|selectors)/runs\.py$" \
        -e "^$E/runs/tests/service/apis/test_runs\.py$" \
        -e "^apps/web/src/entities/run-log/api/mock/fixtures\.ts$" \
        "$T/outside.txt" > "$T/outside2.txt"; mv "$T/outside2.txt" "$T/outside.txt"
    fi
    echo "  바뀐 파일 $(wc -l < "$T/changed.txt" | tr -d " ")개 · 허용 밖 $(wc -l < "$T/outside.txt" | tr -d " ")개"
    sed "s/^/    /" "$T/changed.txt"
    sed "s/^/  ★ /" "$T/outside.txt"
    [ -s "$T/changed.txt" ] && [ ! -s "$T/outside.txt" ]'
fi

# ── 13. 키 꼴 0 · 작업 트리 ──
if wanted 13; then
  step 13 "diff 의 더한 줄·새 파일과 커밋 메시지에 sk- 키 꼴 0(양성 대조 1)" '
    pat="sk-[A-Za-z0-9_-]{20,}"
    a="$(git diff "$BASE" | grep "^+" | grep -c -E "$pat")"
    u=0; for f in $(git ls-files --others --exclude-standard); do u=$((u + $(grep -c -E "$pat" "$f"))); done
    b="$(git log --format=%B "$BASE"..HEAD | grep -c -E "$pat")"
    c=0; [ -n "${X1B2A_MSG:-}" ] && c="$(grep -c -E "$pat" "$X1B2A_MSG")"
    p="$(printf "sk-%s\n" AAAAAAAAAAAAAAAAAAAAAAAA | grep -c -E "$pat")"
    echo "  diff ${a}줄 · 새 파일 ${u}줄 · 커밋 메시지 ${b}줄 · 쓸 메시지(${X1B2A_MSG:-없음}) ${c}줄 · 양성 대조 ${p}"
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

# ── 14. 기록 지점 ──
if wanted 14; then
  step 14 "제품 코드의 record_event( 부르는 자리 = BASE 넷(커밋 ② 부터 + 원본 내려받기 = 다섯)" 'helper sites'
fi

# ── 15. 심은 파손 ──
if wanted 15; then
  if [ "$CONTAINERS" = 1 ]; then
    step 15 "심은 파손(커밋 ${COMMIT} 까지의 P) PLANTED=n/n · FINGERPRINT=same" '
      "$A/scripts/planted-breaks-X1b-2a.sh" --commit "$COMMIT" --with-containers > "$T/planted.txt" 2>&1; code=$?
      grep -E "^(P[0-9]+/|P[0-9]+ |P0|PLANTED=|FINGERPRINT=)" "$T/planted.txt"
      grep -q "안 돌림" "$T/planted.txt" && { echo "  ★ 안 돌린 경우가 있다"; exit 1; }
      exit $code'
  else
    not_run 15 "심은 파손" "--with-containers 없음"
  fi
fi

echo
echo "── 기록: $T"
echo "SECTION4_FAIL=$FAILS"
[ "$FAILS" = 0 ]
