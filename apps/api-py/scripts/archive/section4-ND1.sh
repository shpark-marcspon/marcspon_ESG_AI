#!/usr/bin/env bash
# 밴드 ND1 의 §4 자기검증(발주서 band-handoffs/ND1-order.md §4, 개정 2 — AD4D §4 의 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-ND1.sh --boundary 1|2 --with-containers                 전부
#   apps/api-py/scripts/section4-ND1.sh --boundary 1 --step 1,2,3 --with-containers       고른 단계만
#   --with-containers   9 의 심은 파손에서 업무·보안 층의 것도 심는다(없으면 「안 돌림」 줄이 생겨 9 가 실패한다)
#
# 단계(§4 — AD4D §4 에서 바꿈): 1 순수 · 2 업무(core·runs·user·config·greenwash)·보안 · 3 계약(generated 다시 뽑아
#   cmp·sha·계약 시험·바뀐 자리 — ① RunIn·RunSummaryOut·RunOut 의 문서 칸 꼴만(required 하나 줄음·nullable) / ②
#   + RunLogOut·RunLogDetailOut(물려받음) 두 칸, 새 경로·동작·component 0) · 4 0줄 경로 · 5 lint-imports kept = BASE
#   + runs 이름 검사 · 6 makemigrations --check(0002 가 있다) · 7 수집(사라진 id = 9f 가 허락한 이름 바꿈 하나) ·
#   8 약화 대조 · 9 심은 파손 · 10 verify.sh --fast · 11 바뀐 경로 ⊆ 허용 · 12 제품 record_event 자리 = BASE ·
#   13 키 꼴 0 · 14 마이그레이션 왕복(0001 만 올린 빈 DB 에서 runs 0002 ⇄ 0001 + 보안 test_migrations) ·
#   15 sqlmigrate runs 0002 원문이 다섯 문(0001 이 선 DB 에 붙어야 한다 — 빈 DB 면 FK 문 둘이 빠진다) + 되돌림 ·
#   16 업무 모듈 diff = §1-4 74 표 세 자리(그린워싱 diff 해시를 찍는다) · 17 W/ 0줄 + 웹 typecheck(generated 바뀜) ·
#   18 git status --porcelain 0(커밋 뒤에만 — 커밋 전에는 --step 으로 뺀다).
# 환경 변수:
#   ND1_BASE    기준 커밋(기본: 워크트리를 만든 main 6ded424 = merge band/AD4X, AD4D 병합 뒤)
#   ND1_OUT     산출물 자리(기본: 워크트리 곁의 ND1.out). collect-base.txt·collect-security-base.txt·
#               lint-imports-base.txt 가 여기 있어야 한다(경계 ① 전에 BASE 에서 뜬 것)
#   ND1_COMMIT_MSG_FILE   커밋 전에 볼 커밋 메시지 초안(13 이 BASE..HEAD 의 메시지와 함께 본다)
# 2·6·9·14·15 는 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${ND1_BASE:-6ded424}"
OUT="${ND1_OUT:-$SIDE/ND1.out}"
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

HELPER="$S4/nd1_helper.py"
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



# 경계마다 바뀌어도 되는 잎(쌓인다). ① 실행 꼴 셋의 문서 칸 ② + RunLogOut 의 두 칸
DOC = r"/properties/documentId/(type|anyOf/[01]/type|description)"
NAME = r"/properties/documentName/(type|anyOf/[01]/type|description)"
CHANGED_OK = {
    1: [
        r"/components/schemas/RunIn/description",
        r"/components/schemas/RunIn" + DOC,
        r"/components/schemas/RunIn/required/1",
        r"/components/schemas/(RunOut|RunSummaryOut)" + DOC,
        r"/components/schemas/RunSummaryOut" + NAME,
    ],
    2: [
        r"/components/schemas/RunLogOut" + DOC,  # RunLogDetailOut(RunLogOut) 은 칸을 물려받아 같이
        r"/components/schemas/RunLogOut" + NAME,
        r"/components/schemas/RunLogDetailOut" + DOC,
        r"/components/schemas/RunLogDetailOut" + NAME,
    ],
}
NEW_SCHEMAS = {1: [], 2: []}
NEW_OPS = {1: {}, 2: {}}

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
    ok = (
        not outside
        and bool(changed)
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
    E + r"core/flows/binding\.py$": 1,
    E + r"runs/models\.py$": 1,
    E + r"runs/migrations/0002_run_document_optional\.py$": 1,
    E + r"runs/migrations/0001_initial\.py$": 1,  # 머리말 한 줄만
    E + r"runs/tasks\.py$": 1,
    E + r"runs/service/actions/runs\.py$": 1,
    E + r"runs/service/selectors/runs\.py$": 1,
    E + r"runs/service/(apis|schemas)/runs\.py$": 1,
    E + r"runs/tests/(test_binding|test_executor)\.py$": 1,
    E + r"runs/tests/(test_models|test_models_values)\.py$": 1,
    E + r"runs/tests/service/apis/test_runs(|_versions|_operator)\.py$": 1,
    E + r"runs/tests/service/apis/test_runs_session\.py$": 1,
    E + r"runs/tests/service/selectors/test_runs\.py$": 1,
    E + r"config/tests/test_api_(contract|errors)\.py$": 1,
    P + r"generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$": 1,
    E + r"runs/service/selectors/operator\.py$": 2,
    E + r"user/service/(apis|schemas)/run_logs\.py$": 2,
    E + r"user/service/utils/run_log_xlsx\.py$": 2,
    E + r"user/tests/service/(apis/test_run_logs|utils/test_run_log_xlsx)\.py$": 2,
    E + r"runs/tests/service/selectors/test_operator\.py$": 2,
    P + r"scripts/(section4|planted-breaks)-ND1\.sh$": 1,
    # §1-4 9f(보안) — MARC-TICK-236 노트 08:31
    P + r"tests/security/(test_migrations|test_runs|test_tenant_paths)\.py$": 1,
    P + r"tests/security/test_run_logs\.py$": 2,
    # §1-4 74(그린워싱 a2) — 타입 가드 세 자리만(16 이 줄을 잰다)
    # 플랫폼-웹 d9 허락(236 노트) — RunsScreen.tsx:536 title 한 줄(17 이 −1/+1 을 잰다)
    W + r"src/pages/admin-runs/ui/RunsScreen\.tsx$": 2,
    E + r"greenwash/service/actions/(checks|review)\.py$": 1,
}
ZERO_PATHS = [
    P + r"\.importlinter$", P + r"(pyproject\.toml|uv\.lock)$", E + r"(?!runs/)[^/]+/migrations/",
    E + r"core/flows/(run|types|registry)\.py$", E + r"(?!core/)[^/]+/flows/", E + r"core/models\.py$",
    E + r"core/isolation/foreign_keys\.py$", E + r"runs/service/(services|selectors)/jobs\.py$",
    E + r"runs/calc/errors\.py$", E + r"config/settings/",
    E + r"(translation|dataverify|inventory)/", E + r"greenwash/(?!service/actions/(checks|review)\.py$)",
    P + r"tests_integration/", r"conftest\.py$", P + r"tests/support/", r"^apps/web/(?!src/pages/admin-runs/ui/RunsScreen\.tsx$)",
    P + r"scripts/(planted-breaks|verify)\.sh$",
]
# §1-3 의 그 밖(tests/security 의 허락 밖 파일)은 11 의 허용 목록이 잰다.


def hits(paths: set[str], patterns: list[str]) -> list[str]:
    return sorted(p for p in paths if any(re.search(a, p) for a in patterns))


if CMD == "zero":
    changed = changed_files()
    bad = hits(changed, ZERO_PATHS)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)} · 0줄 경로와 교집합 {bad}")
    planted = "apps/api-py/esgapi/core/migrations/0099_planted.py"
    positive = hits(changed | {planted}, ZERO_PATHS)
    print(f"  양성 대조(가짜 core/migrations/0099_planted.py) → {positive}")
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
    planted = "apps/api-py/esgapi/core/models.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 core/models.py) 허용 밖 → {positive}")
    raise SystemExit(1 if outside or early or not changed or not positive else 0)

# ── 7: 시험 수·이름 ────────────────────────────────────────────────────

SRUNS = "tests/security/test_runs.py"
SLOGS = "tests/security/test_run_logs.py"
RENAMED = {SRUNS + "::test_run_options_over_the_limit_are_refused": SRUNS + "::test_run_options_over_the_db_ceiling_are_refused"}
SECURITY_ADDED = {
    1: {
        *RENAMED.values(),
        SRUNS + "::test_a_documentless_run_stays_inside_its_company[session]",
        SRUNS + "::test_a_documentless_run_stays_inside_its_company[bearer]",
        SRUNS + "::test_another_companys_document_id_on_a_documentless_flow_is_not_found[session]",
        SRUNS + "::test_another_companys_document_id_on_a_documentless_flow_is_not_found[bearer]",
        SRUNS + "::test_a_null_document_does_not_open_the_child_rows_to_another_company",
    },
}
SECURITY_ADDED[2] = SECURITY_ADDED[1] | {
    SLOGS + "::test_a_documentless_run_of_a_is_not_in_bs_list_or_workbook",
}


def nodes(p: Path) -> set[str]:
    return {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}


if CMD == "collect":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed, added = sorted(before - after), sorted(after - before)
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)} · 더함 {len(added)}")
    for n in removed:
        print(f"    - {n}{' (9f 허락 이름 바꿈)' if n in RENAMED else ''}")
    for n in added:
        print(f"    + {n}")
    raise SystemExit(1 if set(removed) != set(RENAMED) or len(after) <= len(before) else 0)

if CMD == "collect-security":
    before, after = nodes(Path(ARGS[0])), nodes(Path(ARGS[1]))
    removed, added = set(before - after), set(after - before)
    print(f"  보안 층 BASE {len(before)} · 지금 {len(after)} · 빠짐 {sorted(removed)}")
    for n in sorted(added):
        print(f"    + {n}")
    want = SECURITY_ADDED[BOUNDARY]
    print(f"  기대한 더함과 같은가: {added == want} (기대 밖 {sorted(added - want)} · 빠진 기대 {sorted(want - added)})")
    raise SystemExit(0 if removed == set(RENAMED) and added == want else 1)

# ── 8: 약화 대조(- 줄의 assert·==·len( 이 §2-1·§1-4 짝) ──────────────────────

# (파일 끝부분, 지운 줄, 경계, 짝으로 더한 줄, 항목)
MINUS = [
    ("esgapi/runs/tests/service/apis/test_runs_session.py",
     'assert client.post("/api/runs", data={"module": "greenwash"}, content_type="application/json").status_code == 422', 1,
     'assert client.post("/api/runs", data=body, content_type="application/json").status_code == 422',
     "§2-1 땅 시험(B1) :100 — documentId 타입을 틀려 같은 422"),
    ("esgapi/runs/tests/test_models.py",
     'assert refused(lambda: run(a, doc.pk, options={"x": "가" * 6000})) == "run_runs_options_size_check"', 1,
     'assert refused(lambda: run(a, doc.pk, options={"x": "가" * (RUN_OPTIONS_CEILING_OCTETS // 3 + 1)})) == (',
     "§2-1 땅 시험 :87 — DB 상한이 CEILING 으로(ruff format 이 나눔 — 짝은 머리 줄)"),
    ("esgapi/runs/tests/test_models.py", "assert plain_again.options == SHUFFLED", 1,
     "assert plain_again.versions == SHUFFLED", "§2-1 땅 시험 :193-197 — 분모를 맨 JSONField(versions)로"),
    ("esgapi/runs/tests/test_models.py", "assert keys_deep(plain_again.options) != keys_deep(SHUFFLED)", 1,
     "assert keys_deep(plain_again.versions) != keys_deep(SHUFFLED)", "§2-1 땅 시험 :193-197"),
    ("esgapi/runs/tests/test_models.py",
     'assert keys_deep(plain_again.options) == [("ceo", []), ("climate", []), ("company", [("a", []), ("zz", [])])]', 1,
     'assert keys_deep(plain_again.versions) == [("ceo", []), ("climate", []), ("company", [("a", []), ("zz", [])])]',
     "§2-1 땅 시험 :193-197"),
    ("tests/security/test_migrations.py", ") == (1, [(1,)])", 1, ") == (2, [(2,)])",
     "9f 허락 ① runs 마이그레이션 수 1 → 2(파일·적용 기록)"),
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

# ── 12: 제품의 record_event 부르는 자리(①② = BASE — ND1 은 감사 줄을 더하지 않는다, target_label 만 None) ───────


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
    want = base  # ND1 은 감사 줄을 더하지 않는다(① ② 다 BASE)
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

# ── 16: 업무 모듈 diff = §1-4 74 표 세 자리(그린워싱 a2 허락 — 236 노트 08:31) ───────────────

GREENWASH = "apps/api-py/esgapi/greenwash"
GREENWASH_LINES = {
    "apps/api-py/esgapi/greenwash/service/actions/checks.py": (
        [
            "    wanted_documents = list(dict.fromkeys(r.document_id for r in runs))  # 처음 본 차례(새 실행 먼저)",
        ],
        [
            "        if run.document_id is None:  # 문서 없는 실행은 그린워싱에 없다(ND1)",
            "            continue",
            "    wanted_documents = list(",
            "        dict.fromkeys(r.document_id for r in runs if r.document_id is not None)",
            "    )  # 처음 본 차례(새 실행 먼저)",
        ],
    ),
    "apps/api-py/esgapi/greenwash/service/actions/review.py": (
        [
            "    document = document_selectors.find_document(company_id=company_id, document_id=found.run.document_id)",
        ],
        [
            "    document = (",
            "        None",
            "        if found.run.document_id is None",
            "        else document_selectors.find_document(company_id=company_id, document_id=found.run.document_id)",
            "    )",
        ],
    ),
}

if CMD == "greenwash":
    diff = git("diff", "-U0", BASE, "--", GREENWASH)
    got: dict[str, tuple[list[str], list[str]]] = {}
    current = ""
    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            current = line[6:]
            got.setdefault(current, ([], []))
        elif line.startswith("--- "):
            continue
        elif line.startswith("-"):
            got.setdefault(current, ([], []))[0].append(line[1:])
        elif line.startswith("+"):
            got.setdefault(current, ([], []))[1].append(line[1:])
    untracked = [p for p in git("ls-files", "--others", "--exclude-standard", "--", GREENWASH).split() if p]
    print(f"  그린워싱 바뀐 파일 {sorted(got)} · 추적 안 된 새 파일 {untracked}")
    for path, (minus, plus) in sorted(got.items()):
        print(f"    {path}: -{len(minus)} +{len(plus)}")
    digest = hashlib.sha256(git("diff", f"{BASE}", "--", GREENWASH).encode()).hexdigest()
    print(f"  git diff {BASE} -- {GREENWASH} sha256 {digest}")
    planted = {**GREENWASH_LINES, "x": ([], ["y"])}
    positive = planted != GREENWASH_LINES
    raise SystemExit(0 if got == {k: (list(a), list(b)) for k, (a, b) in GREENWASH_LINES.items()} and not untracked and positive else 1)

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
    esgapi/core esgapi/runs esgapi/user esgapi/config esgapi/greenwash) > "$S4/2-business.txt" 2>&1
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
  "$API_PY/scripts/planted-breaks-ND1.sh" --boundary "$BOUNDARY" $WITH_CONTAINERS > "$S4/9-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9a-z]+ =>|P0=|PLANTED=|FINGERPRINT=)' "$S4/9-planted.txt"
  expect="PLANTED=22/22"  # 발주서 §3 ① (9f 조건 (사)의 P23·P24·P25 포함)
  [ "$BOUNDARY" = "2" ] && expect="PLANTED=26/26"  # + ② P12~P14 · 9f (사)의 P26
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
  report 12 "제품 record_event 자리(①② BASE)" "$rc"
fi

if want 13; then
  helper keys "${ND1_COMMIT_MSG_FILE:-}" > "$S4/13-keys.txt" 2>&1
  rc=$?
  cat "$S4/13-keys.txt"
  report 13 "키 꼴 0" "$rc"
fi

# 14·15 는 0001 까지만 올린 새 DB 하나(nd1_s4_migrate)에 붙는다 — sqlmigrate 는 DB 의 FK 이름을 읽어 문을 짓는다.
OWNER_USER="$(sed -n 's/^POSTGRES_OWNER_USER=//p' "$ROOT/.env" | tail -1)"
scratch_psql() { (cd "$ROOT" && docker compose exec -T postgres psql -U "$OWNER_USER" -d postgres -v ON_ERROR_STOP=1 -tA "$@"); }
scratch_manage() {
  (cd "$API_PY" && . scripts/db-env.sh && TEST_DATABASE_URL_PY_OWNER="${OWNER_DATABASE_URL%/*}/nd1_s4_migrate" \
    DJANGO_SETTINGS_MODULE=esgapi.config.settings.test_business env -u OPENAI_API_KEY \
    uv run --frozen python manage.py "$@")
}
scratch_fresh() {
  scratch_psql -c "DROP DATABASE IF EXISTS nd1_s4_migrate" -c "CREATE DATABASE nd1_s4_migrate" > /dev/null &&
    scratch_manage migrate runs 0001 > "$S4/14-migrate-0001.txt" 2>&1
}

if want 14; then
  scratch_fresh
  rc_f=$?
  {
    scratch_manage migrate runs 0002 && scratch_manage migrate runs 0001 && scratch_manage migrate runs 0002
  } > "$S4/14-round-trip-scratch.txt" 2>&1
  rc_m=$?
  tail -4 "$S4/14-round-trip-scratch.txt"
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider tests/security/test_migrations.py) \
    > "$S4/14-round-trip.txt" 2>&1
  rc_t=$?
  tail -1 "$S4/14-round-trip.txt"
  rc=0; [ "$rc_f" = "0" ] && [ "$rc_m" = "0" ] && [ "$rc_t" = "0" ] || rc=1
  report 14 "마이그레이션 왕복(runs 0001 ⇄ 0002 · 보안 test_migrations)" "$rc"
fi

if want 15; then
  scratch_fresh
  rc_f=$?
  scratch_manage sqlmigrate runs 0002 > "$S4/15-sqlmigrate.txt" 2>&1
  rc_s=$?
  scratch_manage migrate runs 0002 > /dev/null 2>&1 && scratch_manage sqlmigrate --backwards runs 0002 \
    > "$S4/15-sqlmigrate-backwards.txt" 2>&1
  rc_b=$?
  cat "$S4/15-sqlmigrate.txt" "$S4/15-sqlmigrate-backwards.txt"
  # 문 = 주석·BEGIN·COMMIT 밖의 줄을 ; 로 나눈 것(SET CONSTRAINTS … IMMEDIATE; ALTER … DROP CONSTRAINT 는 한 줄 둘)
  statements="$(grep -v -e '^--' -e '^BEGIN;' -e '^COMMIT;' "$S4/15-sqlmigrate.txt" | tr ';' '\n' | sed 's/^ *//' | grep -v '^$')"
  printf '%s\n' "$statements" > "$S4/15-statements.txt"
  want_re='^SET CONSTRAINTS "run_runs_document_id_[0-9a-f]*_fk_core_documents_id" IMMEDIATE$
^ALTER TABLE "run_runs" DROP CONSTRAINT "run_runs_document_id_[0-9a-f]*_fk_core_documents_id"$
^ALTER TABLE "run_runs" ALTER COLUMN "document_id" DROP NOT NULL$
^ALTER TABLE "run_runs" ADD CONSTRAINT "run_runs_document_id_[0-9a-f]*_fk_core_documents_id" FOREIGN KEY \("document_id"\) REFERENCES "core_documents" \("id"\) DEFERRABLE INITIALLY DEFERRED$
^ALTER TABLE "run_runs" DROP CONSTRAINT "run_runs_options_size_check"$
^ALTER TABLE "run_runs" ADD CONSTRAINT "run_runs_options_size_check" CHECK \(octet_length\(options::text\) <= 524352\)$'
  n=0; bad=0
  while IFS= read -r line; do
    n=$((n + 1))
    pattern="$(printf '%s\n' "$want_re" | sed -n "${n}p")"
    printf '%s\n' "$line" | grep -Eq "$pattern" || { bad=$((bad + 1)); echo "  기대 밖 문 $n: $line"; }
  done < "$S4/15-statements.txt"
  echo "  문 ${n}개(SET CONSTRAINTS 는 DROP 의 앞머리 — 다섯 문 = FK DROP · DROP NOT NULL · FK ADD · CHECK DROP · CHECK ADD) · 기대 밖 ${bad}"
  grep -q 'same_company_fk' "$S4/15-sqlmigrate.txt" && { echo "  두 칸 같은 회사 FK 가 걸렸다"; bad=$((bad + 1)); }
  grep -q 'CHECK (octet_length(options::text) <= 16384)' "$S4/15-sqlmigrate-backwards.txt" || bad=$((bad + 1))
  grep -q 'ALTER COLUMN "document_id" SET NOT NULL' "$S4/15-sqlmigrate-backwards.txt" || bad=$((bad + 1))
  scratch_psql -c "DROP DATABASE IF EXISTS nd1_s4_migrate" > /dev/null
  rc=0; [ "$rc_f" = "0" ] && [ "$rc_s" = "0" ] && [ "$rc_b" = "0" ] && [ "$n" = "6" ] && [ "$bad" = "0" ] || rc=1
  report 15 "sqlmigrate runs 0002 다섯 문(+ 되돌림 16384·SET NOT NULL)" "$rc"
fi

if want 16; then
  helper greenwash > "$S4/16-greenwash.txt" 2>&1
  rc=$?
  cat "$S4/16-greenwash.txt"
  report 16 "업무 모듈 diff = §1-4 74 표 세 자리" "$rc"
fi

if want 17; then
  # ② 는 d9 허락 한 줄만: RunsScreen.tsx 의 title={row.documentName} → ?? undefined(−1/+1). 그 밖 W/ 0줄
  screen="apps/web/src/pages/admin-runs/ui/RunsScreen.tsx"
  web="$(git -C "$ROOT" diff --name-only "$BASE" -- apps/web ":!$screen"; git -C "$ROOT" ls-files --others --exclude-standard -- apps/web)"
  echo "  W/ 바뀐 파일(허락 한 줄 밖): ${web:-0}"
  lines="$(git -C "$ROOT" diff -U0 "$BASE" -- "$screen" | grep -E '^[-+] ' )"
  printf '%s\n' "$lines" | sed 's/^/    /'
  if [ "$BOUNDARY" = "2" ] && [ -n "$lines" ]; then
    want_lines='-                            title={row.documentName}
+                            title={row.documentName ?? undefined}'
    [ "$lines" = "$want_lines" ] || web="${web} ${screen}(허락 밖 줄)"
  elif [ -n "$lines" ]; then
    web="${web} ${screen}(① 에 0줄)"
  fi
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" pnpm --dir apps/web typecheck) > "$S4/17-web-typecheck.txt" 2>&1
  rc_w=$?
  echo "  pnpm --dir apps/web typecheck EXIT=${rc_w}"
  rc=0; [ -z "$web" ] && [ "$rc_w" = "0" ] || rc=1
  report 17 "W/ 0줄 · 웹 typecheck(generated 바뀜)" "$rc"
fi

if want 18; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 18 "작업 트리 깨끗(커밋 뒤)" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
