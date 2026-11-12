#!/usr/bin/env bash
# 밴드 AU1a 의 §4 자기검증(발주서 band-handoffs/AU1a-order.md §4, 개정 1·2). 줄마다 [n] … EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-AU1a.sh                                         전부(경계 3 = 커밋 ③ 뒤)
#   apps/api-py/scripts/section4-AU1a.sh --boundary 1 --step 1,2,3,4,5,6,7,8,9,10,12   커밋 ① 의 단계
#   --with-containers   8 의 심은 파손에서 업무·보안 층의 것도 심는다
#
# 환경 변수:
#   AU1A_BASE   기준 커밋(기본: 워크트리를 만든 main 90c2f6d = merge band/UA1, 그 앞 2f999c6 merge band/X1a)
#   AU1A_OUT    산출물 자리(기본: 워크트리 곁의 AU1a.out). collect-base.txt·lint-imports-base.txt 가 여기 있어야 한다
#   AU1A_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(12 가 BASE..HEAD 의 메시지와 함께 본다)
# 2·8(--with-containers) 은 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${AU1A_BASE:-90c2f6df372c3a3823c6511892850fd11dd2ccd0}"
OUT="${AU1A_OUT:-$SIDE/AU1a.out}"
S4="$OUT/section4"
NODE_PATH_DIR="$HOME/.nvm/versions/node/v22.23.1/bin"
mkdir -p "$S4"
api() { (cd "$API_PY" && env -u OPENAI_API_KEY uv run --frozen "$@"); }

STEPS="all"
BOUNDARY=3
WITH_CONTAINERS=""
while [ $# -gt 0 ]; do
  case "$1" in
    --step) STEPS=",${2:?--step 뒤에 번호},"; shift 2 ;;
    --boundary) BOUNDARY="${2:?--boundary 뒤에 1·2·3}"; shift 2 ;;
    --with-containers) WITH_CONTAINERS="--with-containers"; shift ;;
    *) echo "모르는 인자: $1"; exit 2 ;;
  esac
done
case "$BOUNDARY" in 1|2|3) ;; *) echo "--boundary 는 1·2·3"; exit 2 ;; esac
want() { [ "$STEPS" = "all" ] || case "$STEPS" in *",$1,"*) return 0 ;; *) return 1 ;; esac; }

FAIL=0
report() { # report <번호> <이름> <exit>
  echo "[$1] $2 EXIT=$3"
  [ "$3" = "0" ] || FAIL=$((FAIL + 1))
}

echo "BASE=$BASE HEAD=$(git -C "$ROOT" rev-parse HEAD) BOUNDARY=$BOUNDARY"

HELPER="$S4/au1a_helper.py"
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


# 경계 3 에서 허용하는 바뀐 자리(§4-3): 경로 하나·동작 하나(user_audit_list)와 그 응답 꼴 둘. 목록 밖이면 실패(§5 멈춤 6).
ALLOWED_OPENAPI = [
    r"^/paths/~1audit-logs(/|$)",
    r"^/components/schemas/AuditEventOut(/|$)",
    r"^/components/schemas/AuditPageOut(/|$)",
]


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


if CMD == "openapi-diff":
    base_doc = json.loads(at_base(API + "generated/openapi.json"))
    head_doc = json.loads(now(API + "generated/openapi.json"))
    b, h = leaves_doc(base_doc), leaves_doc(head_doc)
    changed = sorted(k for k in set(b) | set(h) if b.get(k, "<없음>") != h.get(k, "<없음>"))
    allowed = [re.compile(p) for p in ALLOWED_OPENAPI]
    outside = [k for k in changed if not any(a.search(k) for a in allowed)]
    removed = [k for k in changed if k in b]  # 기존 잎이 바뀌거나 빠짐(기존 바이트 그대로여야 한다)
    groups = sorted({"/".join(k.split("/")[:6]) for k in changed})
    print(f"  바뀐 잎 {len(changed)} · 묶음 {len(groups)} · 기존 잎이 바뀜 {len(removed)}")
    for g in groups:
        print(f"    {g}")
    params = sorted(p.get("name") for p in head_doc["paths"].get("/audit-logs", {}).get("get", {}).get("parameters", []))
    print(f"  쿼리 인자 {params}")
    print(f"  목록 밖 {len(outside)}: {outside[:20]}")
    want = sorted(["companyId", "action", "actorUserId", "dateFrom", "dateTo", "limit", "offset"])
    raise SystemExit(1 if outside or removed or not changed or params != want else 0)

if CMD == "sha":
    text = (ROOT / API / "generated/openapi.json").read_bytes()
    want = (ROOT / API / "generated/api.d.ts.source-sha256").read_text().strip()
    got = hashlib.sha256(text).hexdigest()
    print(f"  openapi sha256 {got} · 적힌 값 {want}")
    raise SystemExit(0 if got == want else 1)

# ── 6: 시험 수·이름 ────────────────────────────────────────────────────

if CMD == "collect":
    base_file, now_file = Path(ARGS[0]), Path(ARGS[1])
    node = lambda p: {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}
    before, after = node(base_file), node(now_file)
    removed, added = sorted(before - after), sorted(after - before)
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)} · 더함 {len(added)}")
    for n in removed:
        print(f"    - {n}")
    for n in added:
        print(f"    + {n}")
    raise SystemExit(1 if removed or len(after) <= len(before) else 0)

# ── 7: 약화 대조 ─────────────────────────────────────────────────────

# (파일 끝부분, 지운 줄의 글자, 경계) → 항목. 지운 줄 가운데 assert·==·len( 을 품은 것이 전부 여기 있어야 한다.
MINUS = [
    ("esgapi/core/tests/isolation/test_managers.py",
     'assert len([names for names in fields if "company_id" in names]) == 5  # 분모', 1,
     "§2-2 ① test_managers.py:44 5→6(새 회사 칸 표 하나)"),
    ("esgapi/core/tests/isolation/test_managers.py",
     'assert [m.__name__ for m in COMPANY_SCOPED] == ["Company", "DocumentRow", "JobRow", "LlmCallLogRow", "Site", "User"]', 1,
     "감독 처분 2026-10-19(marcspon-93) test_managers.py:134 회사 모델 이름 목록 +AuditEventRow(조이는 꼴)"),
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert len(company_models()) == 6  # 분모", 1,
     "§2-2 ① test_static_rules.py:175 6→7"),
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert opened == 19", 1,
     "§2-2 ① test_static_rules.py:229 for_company( 19→21"),
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert opened == 21", 3,
     "§2-2 ③ test_static_rules.py:229 for_company( 21→22(names_of)"),
    ("esgapi/core/tests/test_selector_scope.py",
     "assert with_company == COMPANY_TABLES and len(COMPANY_TABLES) == 5  # 분모", 1,
     "§2-2 ① test_selector_scope.py:214 5→6"),
    ("esgapi/core/tests/test_selector_scope.py",
     "assert sorted(files) == [  # 분모: Selector 파일 다섯. 늘면 여기가 빨개져 새 파일의 조회를 보게 한다", 1,
     "§2-2 ① test_selector_scope.py:220 selector 파일 5→6(주석 수 글자)"),
    ("esgapi/core/tests/test_selector_scope.py",
     'assert opened == {"documents": 3, "jobs": 3}  # 분모: 쓰는 문의 수(create 둘·update 넷)', 1,
     "§2-2 ① test_selector_scope.py:249 짝 audit 더함 + \"audit\": 1"),
    ("esgapi/core/tests/test_transaction_rules.py", "assert len(files) == 12, [", 1,
     "§2-2 ① test_transaction_rules.py:298 12→13"),
    ("esgapi/core/tests/test_documents_api.py",
     'assert [statements[i].split()[0] for i in order[1:]] == ["UPDATE", "INSERT"]', 2,
     "§2-2 ② 처분 ⑰ test_documents_api.py:560 업무 표 문만 거른 순서 그대로 + 감사 INSERT 하나·그 뒤(조이는 꼴)"),
    ("esgapi/core/tests/test_documents_services.py",
     'assert services.confirm_upload.__kwdefaults__ == {"enqueue": None}', 2,
     "감독 처분 2026-10-19(marcspon-93) test_documents_services.py:212 기본값 사전 +actor_user_id(정확 일치 그대로)"),
    ("esgapi/config/tests/test_api_contract.py",
     'assert len(found) == 38', 3,
     "§2-2 ③ test_api_contract.py:170 operationId 38→39"),
    ("esgapi/config/tests/test_api_contract.py",
     'assert len(set(found.values())) == 38', 3,
     "§2-2 ③ test_api_contract.py:171 고유 operationId 38→39"),
    ("esgapi/config/tests/test_api_contract.py",
     'assert (len(operations), len(with_body)) == (38, 17)', 3,
     "§2-2 ③ test_api_contract.py:186 (38,17)→(39,17)(GET — 본문 0)"),
    ("esgapi/config/tests/test_api_contract.py",
     'assert len(with_444) == 32', 3,
     "§2-2 ③ test_api_contract.py:214 444 선언 32→33"),
    ("esgapi/config/tests/test_api_contract.py",
     'assert len(USER_ADMIN_OPERATIONS) == 4', 3,
     "§2-2 ③ test_api_contract.py:456 USER_ADMIN_OPERATIONS 4→5(「17」 그대로)"),
    ("esgapi/config/tests/test_api_errors.py",
     'assert with_errors == 35  # UA1: 수정(PATCH /users/{user_id}) +1', 3,
     "§2-2 ③ test_api_errors.py:67 35→36"),
    ("esgapi/config/tests/test_api_errors.py",
     'assert len(takers) == 32  # UA1: 수정(PATCH /users/{user_id}) +1', 3,
     "§2-2 ③ test_api_errors.py:82 32→33"),
    ("esgapi/config/tests/test_api_times.py",
     'assert len(names) == 17  # 분모(E2 바닥에서 셈): 스키마 9 의 시각 칸 · UA1 +1: CustomerUserOut.createdAt', 3,
     "§2-2 ③ test_api_times.py:73 17→18(AuditEventOut.at)"),
    ("esgapi/core/tests/test_permissions.py",
     'assert len(everything) == 38  # 분모: 공개 7 · 인증 31', 3,
     "§2-2 ③ test_permissions.py:118 38→39(인증 32)"),
    ("esgapi/core/tests/test_permissions.py",
     'assert len(NEEDS) == 31  # 분모: 회사 25 · 자기 2 · 운영 관리자 4(K2c·UA1)', 3,
     "§2-2 ③ test_permissions.py:126 31→32(운영 관리자 5)"),
    ("esgapi/core/tests/test_permissions.py",
     'assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 29  # 분모: 막힌 수', 3,
     "§2-2 ③ test_permissions.py:197 29→30"),
    ("tests/security/test_login.py",
     'assert len(authenticated) == 31  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})', 3,
     "§2-2 ③ tests/security/test_login.py:281 31→32"),
    ("tests/security/test_login.py",
     'assert len(closed) == 29  # UA1 +1: PATCH /users/{user_id}', 3,
     "§2-2 ③ tests/security/test_login.py:302 29→30"),
    ("tests/security/test_tenant_paths.py",
     'assert (len(OPERATIONS), len(AUTHENTICATED)) == (38, 31)  # UA1 +1: PATCH /users/{user_id}', 3,
     "§2-2 ③ tests/security/test_tenant_paths.py:262 (38,31)→(39,32)"),
]

if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "*/tests/*", "apps/api-py/tests")
    current = None
    rows = []
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            current = line[6:]
        elif line.startswith("-") and not line.startswith("---") and re.search(r"assert|==|len\(", line):
            rows.append((current, line[1:].strip()))
    bad = 0
    for path, text in rows:
        hit = next((item for f, t, b, item in MINUS if b <= BOUNDARY and path and path.endswith(f) and t == text), None)
        print(f"  - {path}: {text}\n      → {hit or '<항목 없음>'}")
        bad += 0 if hit else 1
    print(f"  - 줄(assert·==·len() {len(rows)} · 항목 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 10: 허용 경로(§4-10) ─────────────────────────────────────────────

ALLOWED_PATHS = [
    r"^apps/api-py/esgapi/core/(models|permissions)\.py$",
    r"^apps/api-py/esgapi/core/migrations/0001_initial\.py$",
    r"^apps/api-py/esgapi/core/calc/audit\.py$",
    r"^apps/api-py/esgapi/core/service/services/(audit|documents)\.py$",
    r"^apps/api-py/esgapi/core/service/selectors/audit\.py$",
    r"^apps/api-py/esgapi/core/service/apis/documents\.py$",
    r"^apps/api-py/esgapi/core/tests/",
    r"^apps/api-py/esgapi/user/service/",
    r"^apps/api-py/esgapi/user/api\.py$",
    r"^apps/api-py/esgapi/user/tests/",
    r"^apps/api-py/esgapi/config/tests/(test_api_contract|test_api_errors|test_api_times)\.py$",
    r"^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$",
    r"^apps/api-py/tests/security/(test_audit|test_owner|test_tenant_paths|test_login)\.py$",
    r"^apps/api-py/scripts/(section4|planted-breaks)-AU1a\.sh$",
]

if CMD == "allowed":
    changed = changed_files()
    outside = sorted(p for p in changed if not any(re.search(a, p) for a in ALLOWED_PATHS))
    print(f"  바뀐 파일 {len(changed)}:")
    for p in sorted(changed):
        print(f"    {p}")
    print(f"  허용 밖: {outside}")
    if BOUNDARY < 3 and any(p.startswith(API + "generated/") for p in changed):
        print("  경계 1·2 에 generated 가 바뀜 — 실패")
        raise SystemExit(1)
    raise SystemExit(1 if outside or not changed else 0)

# ── 11: 기록 지점 표 대조(경계 ② 부터 — 감독 메모) ─────────────────────
# 제품 코드에서 record_event( 를 부르는 자리(파일, 감싼 함수). 뒤 밴드(AU1b·그 몸 밴드)가 지점을 더할 때 이 목록을 늘린다.
RECORD_SITES = {("esgapi/user/service/services/login.py", "note"), ("esgapi/core/service/services/documents.py", "confirm_upload")}

if CMD == "sites":
    found = set()
    pkg = ROOT / API / "esgapi"
    for path in sorted(pkg.rglob("*.py")):
        rel = path.relative_to(ROOT / API).as_posix()
        if {"tests", "migrations"} & set(path.relative_to(pkg).parts[:-1]):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for fn in ast.walk(tree):
            if isinstance(fn, ast.FunctionDef | ast.AsyncFunctionDef):
                for n in ast.walk(fn):
                    if isinstance(n, ast.Call):
                        name = n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id if isinstance(n.func, ast.Name) else None
                        if name == "record_event":
                            found.add((rel, fn.name))
    print(f"  부르는 자리 {sorted(found)}")
    print(f"  기대 {sorted(RECORD_SITES)}")
    # 양성 대조: 이 걷기가 지어낸 소스의 부름을 잡는다
    planted = ast.parse("def f():\n    audit.record_event(at=1)\n")
    positive = any(isinstance(n, ast.Call) and getattr(n.func, "attr", None) == "record_event" for n in ast.walk(planted))
    raise SystemExit(0 if found == RECORD_SITES and positive else 1)

# ── 12: 키 꼴 0 ───────────────────────────────────────────────────────

if CMD == "keys":
    pattern = re.compile(r"sk-[A-Za-z0-9_-]{20,}")
    added = [l for l in git("diff", BASE).splitlines() if l.startswith("+")]
    for path in git("ls-files", "--others", "--exclude-standard").split():
        added += (ROOT / path).read_text(encoding="utf-8", errors="replace").splitlines()
    messages = git("log", "--format=%B", f"{BASE}..HEAD")
    if ARGS and ARGS[0]:
        messages += Path(ARGS[0]).read_text(encoding="utf-8")
    hits = [l for l in added if pattern.search(l)] + [l for l in messages.splitlines() if pattern.search(l)]
    positive = bool(pattern.search("sk-" + "A" * 24))
    print(f"  더한 줄 {len(added)} · 메시지 {len(messages.splitlines())}줄 · 키 꼴 {len(hits)} · 양성 대조 {positive}")
    raise SystemExit(1 if hits or not added or not positive else 0)

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
    esgapi/core esgapi/user esgapi/config) > "$S4/2-business.txt" 2>&1
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
  if [ "$BOUNDARY" != "3" ]; then
    git -C "$ROOT" diff --quiet "$BASE" -- apps/api-py/generated
    rc=$?
    report 3 "계약 바이트 0(generated diff)" "$rc"
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
  git -C "$ROOT" diff --quiet "$BASE" -- apps/web packages apps/api-py/.importlinter \
    apps/api-py/esgapi/config/apps_list.py apps/api-py/esgapi/config/api.py apps/api-py/esgapi/config/settings \
    apps/api-py/scripts/planted-breaks.sh apps/api-py/esgapi/runs apps/api-py/esgapi/reconcile \
    apps/api-py/esgapi/greenwash apps/api-py/esgapi/inventory apps/api-py/esgapi/reference \
    apps/api-py/esgapi/organization apps/api-py/esgapi/user/models.py apps/api-py/esgapi/user/migrations \
    apps/api-py/esgapi/user/management apps/api-py/esgapi/core/observability apps/api-py/tests/security/test_migrations.py \
    apps/api-py/pyproject.toml apps/api-py/uv.lock compose.yaml README.md docs
  rc_z=$?
  # 새 마이그레이션 파일 0(처분 ⑤ (가)) — 추적 밖의 새 파일까지
  extra="$(git -C "$ROOT" ls-files --others --exclude-standard -- 'apps/api-py/esgapi/*/migrations/*')"
  added="$(git -C "$ROOT" diff --name-only --diff-filter=A "$BASE" -- 'apps/api-py/esgapi/*/migrations/*')"
  echo "  새 마이그레이션 파일: [${extra}${added}]"
  rc=0; [ "$rc_z" = "0" ] && [ -z "$extra" ] && [ -z "$added" ] || rc=1
  report 4 "0줄(diff ${rc_z}, 새 마이그레이션 0)" "$rc"
fi

if want 5; then
  api lint-imports > "$S4/5-lint-imports.txt" 2>&1
  rc_l=$?
  last="$(grep -E '^Contracts:' "$S4/5-lint-imports.txt" | tail -1)"
  base_last="$(grep -E '^Contracts:' "$OUT/lint-imports-base.txt" 2>/dev/null | tail -1)"
  echo "  지금: $last · BASE: ${base_last:-<없음>}"
  rc=0; [ "$rc_l" = "0" ] && [ -n "$base_last" ] && [ "$last" = "$base_last" ] || rc=1
  report 5 "import 계약(BASE 와 같음)" "$rc"
fi

if want 6; then
  if [ ! -s "$OUT/collect-base.txt" ]; then
    echo "  $OUT/collect-base.txt 가 없다(커밋 ① 전에 BASE 에서 떠 둘 것)"
    report 6 "시험 수·이름" 1
  else
    api pytest --collect-only -q -p no:cacheprovider esgapi tests > "$S4/6-collect-now.txt" 2>&1
    rc_c=$?
    helper collect "$OUT/collect-base.txt" "$S4/6-collect-now.txt" > "$S4/6-collect.txt" 2>&1
    rc_n=$?
    cat "$S4/6-collect.txt" | head -5
    api pytest --collect-only -q -p no:cacheprovider -m security tests > "$S4/6-collect-security-now.txt" 2>&1
    rc_s=$?
    echo "  보안 층 수집: BASE $(tail -1 "$OUT/collect-security-base.txt") · 지금 $(tail -1 "$S4/6-collect-security-now.txt") · EXIT=${rc_s}"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] && [ "$rc_s" = "0" ] || rc=1
    report 6 "시험 수·이름(사라진 id 0)" "$rc"
  fi
fi

if want 7; then
  helper weaken > "$S4/7-weaken.txt" 2>&1
  rc=$?
  cat "$S4/7-weaken.txt"
  report 7 "약화 대조(- 줄마다 §2-2 항목)" "$rc"
fi

if want 8; then
  "$API_PY/scripts/planted-breaks-AU1a.sh" --boundary "$BOUNDARY" $WITH_CONTAINERS > "$S4/8-planted.txt" 2>&1
  rc=$?
  grep -E '^(P[0-9]|PLANTED=|FINGERPRINT=)' "$S4/8-planted.txt"
  report 8 "심은 파손" "$rc"
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
  if [ "$BOUNDARY" = "1" ]; then
    echo "  경계 1: 안 돌림(감독 메모 — 단계 11 은 커밋 ② 경계부터)"
  else
    helper sites > "$S4/11-sites.txt" 2>&1
    rc=$?
    cat "$S4/11-sites.txt"
    report 11 "기록 지점 표 대조(record_event 부르는 자리)" "$rc"
  fi
fi

if want 12; then
  helper keys "${AU1A_COMMIT_MSG_FILE:-}" > "$S4/12-keys.txt" 2>&1
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
