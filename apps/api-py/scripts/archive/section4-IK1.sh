#!/usr/bin/env bash
# 밴드 IK1 의 §4 자기검증(발주서 band-handoffs/IK1-order.md §4 — RF1 의 section4-RF1.sh 꼴). 줄마다 [n] … EXIT= 를 찍고
# 끝에 SECTION4_FAIL=<n>. 경계는 하나다.
# 사용(어디서든):
#   apps/api-py/scripts/section4-IK1.sh --with-containers                 전부
#   apps/api-py/scripts/section4-IK1.sh --step 1,2,3 --with-containers    고른 단계만
#   --with-containers   9 의 심은 파손에서 업무·보안 층의 것도 심는다(없으면 「안 돌림」 줄이 생겨 9 가 실패한다)
#
# 단계(§4): 1 순수 · 2 업무(runs·core·config + 모듈의 POST /runs 시험 — 0 바뀜 증거)·보안(test_runs·test_migrations
#   (왕복 — runs 0003 포함)·test_tenant_paths) · 3 계약(generated 다시 뽑아 cmp·sha·계약 시험·바뀐 자리 — runs_create 의
#   머리 매개변수 하나와 그 설명만·component 0·다른 동작 0) · 4 0줄 경로 · 5 lint-imports kept = BASE + runs 이름 검사 ·
#   6 makemigrations --check(0) · 7 수집(사라진 id 0, 수 BASE 이상) · 8 약화 대조 · 9 심은 파손 16/16 ·
#   10 verify.sh --fast · 11 바뀐 경로 ⊆ 허용 · 12 create_run( 부르는 자리 = BASE · 13 키 꼴 0 · 웹 typecheck ·
#   15 git status --porcelain 0(커밋 뒤에만 — 커밋 전에는 --step 으로 뺀다). 14(마이그레이션 왕복)는 2 의 보안 층
#   tests/security/test_migrations.py 가 잰다.
#
# 환경 변수:
#   IK1_BASE   기준 커밋(기본: 워크트리를 만든 main 4e28a54 = merge band/RC1)
#   IK1_OUT    산출물 자리(기본: 워크트리 곁의 IK1.out). collect-base.txt·collect-security-base.txt·
#              lint-imports-base.txt 가 여기 있어야 한다(구현 전에 BASE 에서 뜬 것)
#   IK1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(13 이 BASE..HEAD 의 메시지와 함께 본다)
# 2·6·9 는 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${IK1_BASE:-4e28a54}"
OUT="${IK1_OUT:-$SIDE/IK1.out}"
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

HELPER="$S4/ik1_helper.py"
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


# 바뀌어도 되는 잎: runs_create 의 머리 매개변수 Idempotency-Key 하나(그 잎 전부)와 docstring 설명 한 줄
# (component 0 · 경로 0 · 다른 동작 0)
CHANGED_OK = {1: [r"/paths/~1runs/post/parameters(/Idempotency-Key(/.*)?)?", r"/paths/~1runs/post/description"]}
RUNS = "/runs"

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
    paths = sorted(set(head_doc["paths"]) ^ set(base_doc["paths"]))
    schemas = sorted(set(head_doc["components"]["schemas"]) ^ set(base_doc["components"]["schemas"]))
    same_schemas = head_doc["components"] == base_doc["components"]
    others = {
        (path, method)
        for path, item in head_doc["paths"].items()
        for method, op in item.items()
        if (path, method) != (RUNS, "post") and base_doc["paths"].get(path, {}).get(method) != op
    }
    params = [p for p in head_doc["paths"][RUNS]["post"].get("parameters", []) if p["in"] == "header"]
    print(f"  더하거나 빠진 경로 {paths} · components 차이 {schemas} · components 같음 {same_schemas}")
    print(f"  runs_create 밖 바뀐 동작 {sorted(others)}")
    print(f"  runs_create 머리 매개변수 원문: {json.dumps(params, ensure_ascii=False)}")
    ok = (
        not outside
        and bool(changed)
        and not paths
        and same_schemas
        and not others
        and [(p["name"], p["required"]) for p in params] == [("Idempotency-Key", False)]
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
    E + r"runs/models\.py$": 1,
    E + r"runs/migrations/0003_run_idempotency_key\.py$": 1,
    E + r"runs/calc/idempotency\.py$": 1,
    E + r"runs/service/selectors/runs\.py$": 1,
    E + r"runs/service/actions/runs\.py$": 1,
    E + r"runs/service/apis/runs\.py$": 1,
    E + r"runs/tests/.*\.py$": 1,
    E + r"core/tests/(test_transaction_rules|isolation/test_static_rules|test_selector_scope)\.py$": 1,
    E + r"config/tests/test_api_(contract|errors|times)\.py$": 1,
    P + r"generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$": 1,
    # §1-4 73(보안·스크립트) — MARC-TICK-253 노트
    P + r"scripts/(section4|planted-breaks)-IK1\.sh$": 1,
    P + r"tests/security/(test_migrations|test_runs)\.py$": 1,
}
ZERO_PATHS = [
    P + r"\.importlinter$", P + r"(pyproject\.toml|uv\.lock)$", E + r"(?!runs/)[^/]+/migrations/",
    E + r"runs/migrations/(?!0003_run_idempotency_key\.py$)", E + r"runs/service/schemas/", E + r"core/permissions\.py$",
    E + r"runs/(tasks|context)\.py$", E + r"runs/executor", E + r"runs/calc/keys\.py$",
    E + r"core/(?!tests/)", E + r"(greenwash|translation|dataverify|inventory)/", E + r"user/",
    P + r"tests_integration/", r"conftest\.py$", P + r"tests/support/", r"^apps/web/",
    P + r"tests/security/test_tenant_paths\.py$",
    P + r"scripts/(planted-breaks|verify|section4)\.sh$",
]
# §1-3 의 그 밖(tests/security 의 허락 밖 파일)은 11 의 허용 목록이 잰다.


def hits(paths: set[str], patterns: list[str]) -> list[str]:
    return sorted(p for p in paths if any(re.search(a, p) for a in patterns))


if CMD == "zero":
    changed = changed_files()
    bad = hits(changed, ZERO_PATHS)
    print(f"  바뀐 파일(추적 안 된 새 파일 포함) {len(changed)} · 0줄 경로와 교집합 {bad}")
    planted = "apps/api-py/esgapi/runs/service/schemas/runs.py"
    positive = hits(changed | {planted}, ZERO_PATHS)
    print(f"  양성 대조(가짜 runs/service/schemas/runs.py) → {positive}")
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
    planted = "apps/api-py/esgapi/runs/tasks.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 runs/tasks.py) 허용 밖 → {positive}")
    raise SystemExit(1 if outside or early or not changed or not positive else 0)

# ── 7: 시험 수·이름 ────────────────────────────────────────────────────

SRUN = "tests/security/test_runs.py"
SECURITY_ADDED = {
    1: {
        SRUN + "::test_the_same_key_in_two_companies_or_two_people_makes_separate_runs",
        SRUN + "::test_the_app_role_cannot_write_a_second_row_for_the_same_key_or_a_key_without_its_sha",
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
    ("tests/security/test_migrations.py",
     ") == (2, [(2,)])", 1,
     ") == (3, [(3,)])",
     "73 허락 ① — runs 마이그레이션 수 2 → 3(IK1 0003)"),
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

# ── 12: create_run( 부르는 자리(= BASE — 기본값 None 이라 부르는 쪽 0줄) ─────────


def call_sites(read_file, paths) -> list[tuple[str, int]]:
    found = []
    for rel in paths:
        if not rel.endswith(".py"):
            continue
        tree = ast.parse(read_file(rel))
        for n in ast.walk(tree):
            if isinstance(n, ast.Call):
                name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else None
                if name == "create_run":
                    found.append((rel, n.lineno))
    return found


if CMD == "calls":
    base_paths = git("ls-tree", "-r", "--name-only", BASE, "--", API + "esgapi", API + "tests").split()
    head_paths = [p.relative_to(ROOT).as_posix() for d in ("esgapi", "tests") for p in (ROOT / API / d).rglob("*.py")]
    base = call_sites(at_base, base_paths)
    head = call_sites(now, head_paths)
    base_files = sorted({f for f, _ in base})
    new_tests = {API + "esgapi/runs/tests/service/actions/test_create_run_race.py"}  # 이 밴드의 새 시험(동시 10~12)
    head_old = [(f, n) for f, n in head if f not in new_tests]
    print(f"  BASE {len(base)} 자리 {base_files}")
    print(f"  지금 {len(head)} 자리(새 시험 파일 몫 {len(head) - len(head_old)}) · 새 시험 밖 {len(head_old)}")
    planted = ast.parse("def f():\n    actions.create_run(company_id=1)\n")
    positive = any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "create_run" for n in ast.walk(planted))
    raise SystemExit(0 if len(head_old) == len(base) and sorted({f for f, _ in head_old}) == base_files and base and positive else 1)

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
    esgapi/core esgapi/runs esgapi/config \
    esgapi/greenwash/tests/service/apis/test_ai_settings_model.py esgapi/greenwash/tests/flows/test_binding_e0_runs.py \
    esgapi/translation/tests/flows/test_runs_translation.py \
    esgapi/dataverify/tests/service/apis/test_dataverify_operator.py esgapi/dataverify/tests/flows/test_runs_dataverify.py \
    ) > "$S4/2-business.txt" 2>&1
  rc_b=$?
  tail -1 "$S4/2-business.txt"
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider \
    tests/security/test_runs.py tests/security/test_migrations.py tests/security/test_tenant_paths.py) \
    > "$S4/2-security.txt" 2>&1
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
  "$API_PY/scripts/planted-breaks-IK1.sh" $WITH_CONTAINERS > "$S4/9-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9a-z]+ =>|P0=|PLANTED=|FINGERPRINT=)' "$S4/9-planted.txt"
  expect="PLANTED=16/16"  # 발주서 §3 의 P1~P15 + 73 조건 (다)의 P16
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
  helper calls > "$S4/12-sites.txt" 2>&1
  rc=$?
  cat "$S4/12-sites.txt"
  report 12 "create_run( 부르는 자리 = BASE" "$rc"
fi

if want 13; then
  helper keys "${IK1_COMMIT_MSG_FILE:-}" > "$S4/13-keys.txt" 2>&1
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
