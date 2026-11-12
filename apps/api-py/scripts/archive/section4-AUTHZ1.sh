#!/usr/bin/env bash
# 밴드 AUTHZ1 의 §4 자기검증(발주서 band-handoffs/AUTHZ1-order.md §4, 개정 2). 줄마다 [n] … EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-AUTHZ1.sh                                  전부(경계 2 = 커밋 ② 뒤)
#   apps/api-py/scripts/section4-AUTHZ1.sh --boundary 1 --step 1,3,4,5,6,7,9,10   커밋 ① 의 단계
#   --with-containers   7 의 심은 파손에서 컨테이너가 필요한 것(P2 의 업무·보안 층, P6)도 심는다
#
# 환경 변수:
#   AUTHZ1_BASE   기준 커밋(기본: 워크트리를 만든 main d72ade2 = WK1 병합)
#   AUTHZ1_OUT    산출물 자리(기본: 워크트리 곁의 AUTHZ1.out). collect-base.txt 가 여기 있어야 한다
#   AUTHZ1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(11 이 BASE..HEAD 의 메시지와 함께 본다)
# 2·8 은 Postgres 가 떠 있어야 한다(scripts/worktree-env.sh AUTHZ1 → docker compose up -d --wait postgres). 컨테이너를 띄우지 않는다.
# 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS 의 /bin/bash 3.2 에서 돈다.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${AUTHZ1_BASE:-d72ade2e71a6c548759967766e43ee480f4373a7}"
OUT="${AUTHZ1_OUT:-$SIDE/AUTHZ1.out}"
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

HELPER="$S4/authz1_helper.py"
cat > "$HELPER" <<'PY'
import ast
import io
import json
import re
import subprocess
import sys
import tokenize
from pathlib import Path

ROOT = Path(sys.argv[1])
BASE = sys.argv[2]
CMD = sys.argv[3]
ARGS = sys.argv[4:]
API = "apps/api-py/"


def git(*a: str) -> str:
    return subprocess.run(["git", "-C", str(ROOT), *a], check=True, capture_output=True, text=True).stdout


def at_base(path: str) -> str:
    return git("show", f"{BASE}:{path}")


def now(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def docstring_starts(text: str, module_only: bool) -> set[tuple[int, int]]:
    """docstring 문자열 토큰의 시작 (줄, 칸). module_only 면 모듈 docstring 만."""
    tree = ast.parse(text)
    holders: list[ast.AST] = [tree]
    if not module_only:
        holders += [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef)]
    starts = set()
    for holder in holders:
        body = getattr(holder, "body", [])
        if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) and isinstance(body[0].value.value, str):
            starts.add((body[0].value.lineno, body[0].value.col_offset))
    return starts


def code_tokens(text: str, module_only: bool) -> list[tuple[int, str]]:
    skip = docstring_starts(text, module_only)
    out = []
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type in (tokenize.COMMENT, tokenize.NL):
            continue
        if tok.type == tokenize.STRING and tok.start in skip:
            out.append((tok.type, "<docstring>"))
            continue
        out.append((tok.type, tok.string))
    return out


def counts(read) -> tuple[int, int, int, int, int, int]:
    doc = json.loads(read(API + "generated/openapi.json"))
    ops = [o for ms in doc["paths"].values() for o in ms.values() if isinstance(o, dict)]
    public = [o for o in ops if not o.get("security")]
    authed = [o for o in ops if o.get("security")]
    table = ast.parse(read(API + "esgapi/core/permissions.py"))
    rows = 0
    for node in ast.walk(table):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "OPERATION_POLICY":
            assert isinstance(node.value, ast.Dict)
            rows = len(node.value.keys)
    tests = ast.parse(read(API + "esgapi/core/tests/test_permissions.py"))
    inside = 0
    for node in ast.walk(tests):
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == "INSIDE":
            assert isinstance(node.value, ast.Dict)
            inside = len(node.value.keys)
    return len(ops), len(public), len(authed), rows, 0, inside


def first_statements(rev: str | None) -> int:
    """경로 파일(esgapi/*/service/apis/*.py)에서 permitted(request, "…") 꼴 줄 수. git grep 종료 ≥2 는 실패."""
    cmd = ["git", "-C", str(ROOT), "grep", "-n", "-E", r'permitted(_session)?\(request, "']
    if rev:
        cmd.append(rev)
    cmd += ["--", "apps/api-py/esgapi/*/service/apis/*.py"]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode >= 2:
        print(r.stderr)
        raise SystemExit(2)
    return len([line for line in r.stdout.splitlines() if line])


if CMD == "tokens":
    # (파일, 모듈 docstring 만 바뀌어도 되는가)
    files = [
        ("apps/api-py/esgapi/core/service/apis/documents.py", True),
        ("apps/api-py/esgapi/inventory/tests/test_api.py", False),
        ("apps/api-py/esgapi/inventory/tests/test_scope3_api.py", False),
    ]
    bad = 0
    for path, module_only in files:
        before, after = at_base(path), now(path)
        same_code = code_tokens(before, module_only) == code_tokens(after, module_only)
        changed = before != after
        print(f"  {path}: 바뀜={'예' if changed else '아니오'} 코드토큰같음={'예' if same_code else '아니오'}")
        bad += 0 if same_code else 1
    raise SystemExit(1 if bad else 0)

if CMD == "counts":
    head = counts(now)
    base = counts(at_base)
    fh, fb = first_statements(None), first_statements(BASE)
    fmt = lambda c, f: f"{c[0]} {c[1]} {c[2]} {c[3]} {f}+{c[5]}"
    print(f"  HEAD(작업 트리): {fmt(head, fh)}")
    print(f"  BASE(양성 대조): {fmt(base, fb)}")
    want = "37 7 30 30 28+2"
    ok = fmt(head, fh) == want and fmt(base, fb) == want and fb > 0
    print(f"  기대: {want}")
    raise SystemExit(0 if ok else 1)

if CMD == "collect":
    base_file, now_file, boundary = Path(ARGS[0]), Path(ARGS[1]), ARGS[2]
    node = lambda p: {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}
    before, after = node(base_file), node(now_file)
    P = "esgapi/core/tests/test_permissions.py::"
    removed_expected = {P + "test_only_the_llm_route_is_proposed"}  # 개정 2 B1: 「proposed 칸 0」 으로 이름째 바꿈
    added_expected = {P + "test_the_public_operations_are_these_seven", P + "test_no_cell_is_proposed"}
    removed, added = before - after, after - before
    added_security = {n for n in added if n.startswith("tests/security/test_tenant_paths.py::")}
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {sorted(removed)} · 더함 {sorted(added)}")
    ok = removed == removed_expected and added - added_security == added_expected
    if boundary == "1":
        ok = ok and not added_security and len(after) == len(before) + 1
    else:
        ok = ok and len(added_security) == 1 and len(after) == len(before) + 2
    raise SystemExit(0 if ok else 1)

if CMD == "permissions-lines":
    # 개정 2 B1: core/permissions.py 의 바뀐 줄은 proposed 자리뿐(바뀐 줄마다 proposed·가안·MARC-ENT-276 중 하나가 있거나,
    # 분류 칸이 CUSTOMER 가 된 줄이다 — 칸의 needs 가 BASE 와 같은지는 순수 층 test_the_table_is_these_needs 가 잰다).
    diff = git("diff", "-U0", BASE, "--", API + "esgapi/core/permissions.py")
    lines = [l for l in diff.splitlines() if l[:1] in "+-" and not l.startswith(("+++", "---"))]
    for l in lines:
        print("  " + l)
    allowed = re.compile(r"proposed|MARC-ENT-276|가안|\"inventory_scope3_classify\": CUSTOMER,$")
    ok = all(allowed.search(l) for l in lines if l.strip() not in ("+", "-"))
    raise SystemExit(0 if ok else 1)

if CMD == "allowed":
    allow = {
        "apps/api-py/esgapi/core/tests/test_permissions.py",
        "apps/api-py/esgapi/core/permissions.py",  # 개정 2 B1(proposed 자리만 — 3b 가 잰다)
        "apps/api-py/tests/security/test_tenant_paths.py",
        "apps/api-py/esgapi/inventory/tests/test_scope3_api.py",
        "apps/api-py/esgapi/inventory/tests/test_api.py",
        "apps/api-py/esgapi/core/service/apis/documents.py",
        "apps/api-py/scripts/section4-AUTHZ1.sh",
        "apps/api-py/scripts/planted-breaks-AUTHZ1.sh",
    }
    changed = set(git("diff", "--name-only", BASE).split()) | set(git("ls-files", "--others", "--exclude-standard").split())
    outside = sorted(changed - allow)
    print(f"  바뀐 파일 {len(changed)}: {sorted(changed)}")
    print(f"  허용 밖: {outside}")
    raise SystemExit(1 if outside or not changed else 0)

if CMD == "keys":
    pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    added = [l for l in git("diff", BASE).splitlines() if l.startswith("+")]
    added += [l for l in git("diff", "--cached", BASE).splitlines() if l.startswith("+")]
    for path in git("ls-files", "--others", "--exclude-standard").split():
        added += (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    messages = git("log", "--format=%B", f"{BASE}..HEAD")
    if ARGS and ARGS[0]:
        messages += Path(ARGS[0]).read_text(encoding="utf-8")
    hits = [l for l in added if pattern.search(l)] + [l for l in messages.splitlines() if pattern.search(l)]
    print(f"  더한 줄 {len(added)} · 메시지 {len(messages.splitlines())}줄 · 키 꼴 {len(hits)}")
    raise SystemExit(1 if hits or not added else 0)

raise SystemExit(f"모르는 명령 {CMD}")
PY
helper() { api python "$HELPER" "$ROOT" "$BASE" "$@"; }

if want 1; then
  api pytest -q -p no:cacheprovider -m "not django_db and not security" esgapi > "$S4/1-pure.txt" 2>&1
  rc=$?
  tail -1 "$S4/1-pure.txt"
  report 1 "순수 층 초록" "$rc"
fi

if want 2; then
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-business.sh -p no:cacheprovider esgapi/core/tests/test_permissions_wiring.py \
    esgapi/core/tests/test_documents_api.py esgapi/inventory/tests/test_api.py esgapi/inventory/tests/test_scope3_api.py \
    esgapi/user/tests) > "$S4/2-business.txt" 2>&1
  rc_b=$?
  tail -1 "$S4/2-business.txt"
  (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider tests/security/test_tenant_paths.py \
    tests/security/test_login.py tests/security/test_user_admin.py) > "$S4/2-security.txt" 2>&1
  rc_s=$?
  tail -1 "$S4/2-security.txt"
  rc=0; [ "$rc_b" = "0" ] && [ "$rc_s" = "0" ] || rc=1
  report 2 "업무·보안 층 초록(업무 ${rc_b} 보안 ${rc_s})" "$rc"
fi

if want 3; then
  git -C "$ROOT" diff --quiet "$BASE" -- apps/api-py/generated apps/web apps/api-py/esgapi/greenwash \
    apps/api-py/esgapi/core/auth apps/api-py/esgapi/core/tenancy apps/api-py/esgapi/core/service/apis/runs.py
  rc_d=$?
  helper permissions-lines > "$S4/3-permissions.txt" 2>&1
  rc_p=$?
  cat "$S4/3-permissions.txt"
  api pytest -q -p no:cacheprovider esgapi/config/tests/test_api_contract.py > "$S4/3-contract.txt" 2>&1
  rc_c=$?
  tail -1 "$S4/3-contract.txt"
  rc=0; [ "$rc_d" = "0" ] && [ "$rc_p" = "0" ] && [ "$rc_c" = "0" ] || rc=1
  report 3 "계약·동작 바이트 0(diff ${rc_d} permissions 자리 ${rc_p} 계약 시험 ${rc_c})" "$rc"
fi

if want 4; then
  helper tokens > "$S4/4-tokens.txt" 2>&1
  rc=$?
  cat "$S4/4-tokens.txt"
  report 4 "바뀐 줄의 종류(주석·docstring 밖 토큰 0)" "$rc"
fi

if want 5; then
  helper counts > "$S4/5-counts.txt" 2>&1
  rc=$?
  cat "$S4/5-counts.txt"
  report 5 "셈 37 7 30 30 28+2(BASE 양성 대조)" "$rc"
fi

if want 6; then
  if [ ! -s "$OUT/collect-base.txt" ]; then
    echo "  $OUT/collect-base.txt 가 없다(커밋 ① 전에 BASE 에서 떠 둘 것)"
    report 6 "시험 수·이름" 1
  else
    api pytest --collect-only -q -p no:cacheprovider esgapi tests/security > "$S4/6-collect-now.txt" 2>&1
    rc_c=$?
    helper collect "$OUT/collect-base.txt" "$S4/6-collect-now.txt" "$BOUNDARY" > "$S4/6-collect.txt" 2>&1
    rc_n=$?
    cat "$S4/6-collect.txt"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] || rc=1
    report 6 "시험 수·이름(BASE + ${BOUNDARY})" "$rc"
  fi
fi

if want 7; then
  "$API_PY/scripts/planted-breaks-AUTHZ1.sh" --boundary "$BOUNDARY" $WITH_CONTAINERS > "$S4/7-planted.txt" 2>&1
  rc=$?
  grep -E '^(P[0-9]|PLANTED=|FINGERPRINT=)' "$S4/7-planted.txt"
  report 7 "심은 파손" "$rc"
fi

if want 8; then
  if [ "$BOUNDARY" = "1" ]; then
    echo "  경계 1: ② 의 새 시험이 아직 없다 — 안 돌림"
    report 8 "보안 층 쌍의 분모(안 돌림)" 1
  else
    (cd "$API_PY" && env -u OPENAI_API_KEY scripts/test-security.sh -p no:cacheprovider -s \
      "tests/security/test_tenant_paths.py::test_a_customer_bearer_passes_auth_and_permission_on_every_company_operation") \
      > "$S4/8-denominator.txt" 2>&1
    rc=$?
    grep -E '^AUTHZ1 ' "$S4/8-denominator.txt"
    report 8 "보안 층 쌍의 분모" "$rc"
  fi
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
  report 10 "허용 경로" "$rc"
fi

if want 11; then
  helper keys "${AUTHZ1_COMMIT_MSG_FILE:-}" > "$S4/11-keys.txt" 2>&1
  rc=$?
  cat "$S4/11-keys.txt"
  report 11 "키 꼴 0" "$rc"
fi

if want 12; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 12 "작업 트리 깨끗" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
