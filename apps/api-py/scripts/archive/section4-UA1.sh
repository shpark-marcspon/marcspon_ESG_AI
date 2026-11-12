#!/usr/bin/env bash
# 밴드 UA1 의 §4 자기검증(발주서 band-handoffs/UA1-order.md §4, 개정 1·2). 줄마다 [n] … EXIT= 를 찍고 끝에 SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-UA1.sh                                    전부(경계 3 = 커밋 ③ 뒤)
#   apps/api-py/scripts/section4-UA1.sh --boundary 1 --step 1,3,5,6,8,9,10   커밋 ① 의 단계
#   --with-containers   8 의 심은 파손에서 업무·보안 층의 것도 심는다
#
# 환경 변수:
#   UA1_BASE   기준 커밋(기본: 워크트리를 만든 main 7444685 = merge band/AD1)
#   UA1_OUT    산출물 자리(기본: 워크트리 곁의 UA1.out). collect-base.txt 가 여기 있어야 한다
#   UA1_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(12 가 BASE..HEAD 의 메시지와 함께 본다)
# 2·8(--with-containers) 은 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). macOS /bin/bash 3.2.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${UA1_BASE:-7444685bb02db4771acef3a6ae6d29e5d4978ef1}"
OUT="${UA1_OUT:-$SIDE/UA1.out}"
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

HELPER="$S4/ua1_helper.py"
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


# 경계마다 허용하는 바뀐 자리(포인터의 앞부분 정규식). 목록 밖이면 실패(§4-3·§5 멈춤 7).
ALLOWED_OPENAPI = {
    2: [
        r"^/paths/~1users~1\{user_id\}/patch(/|$)",                     # 경로 하나·동작 하나(user_update)
        r"^/paths/~1users/get/parameters/(q|status)(/|$)",             # user_list 인자 둘
        r"^/paths/~1users/get/description$",                           # 동작 description user_list(개정 2 B4)
        r"^/components/schemas/CustomerUserOut/properties/(createdAt|companyName)(/|$)",
        r"^/components/schemas/CustomerUserOut/required/\d+$",         # 칸 둘이 required 에 더해짐
        r"^/components/schemas/UserUpdateIn(/|$)",
        r"^/components/schemas/UserCreateIn/properties/username/pattern$",
    ],
    3: [
        r"^/components/schemas/LoginIn/properties/companySubdomain/description$",
        r"^/paths/~1auth~1login/post/description$",                    # 동작 description user_auth_login(개정 2 B4)
    ],
}


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
    allowed = [re.compile(p) for n, ps in ALLOWED_OPENAPI.items() if n <= BOUNDARY for p in ps]
    outside = [k for k in changed if not any(a.search(k) for a in allowed)]
    # 묶어 보이기: 포인터의 앞 다섯 마디
    groups = sorted({"/".join(k.split("/")[:6]) for k in changed})
    print(f"  바뀐 잎 {len(changed)} · 묶음 {len(groups)}")
    for g in groups:
        print(f"    {g}")
    print(f"  목록 밖 {len(outside)}: {outside[:20]}")
    if BOUNDARY >= 2 and not changed:
        print("  경계 ≥2 인데 바뀐 자리 0 — 실패")
        raise SystemExit(1)
    raise SystemExit(1 if outside else 0)

if CMD == "sha":
    text = (ROOT / API / "generated/openapi.json").read_bytes()
    want = (ROOT / API / "generated/api.d.ts.source-sha256").read_text().strip()
    got = hashlib.sha256(text).hexdigest()
    print(f"  openapi sha256 {got} · 적힌 값 {want}")
    raise SystemExit(0 if got == want else 1)

# ── 4: 0줄 경로와 웹 두 파일(더하기만) ─────────────────────────────────

WEB_ALLOWED = {"apps/web/src/entities/account/api/testing.ts", "apps/web/src/app/admin/router.test.tsx"}

if CMD == "web":
    web = set(git("diff", "--name-only", BASE, "--", "apps/web").split())
    web |= {p for p in git("ls-files", "--others", "--exclude-standard", "--", "apps/web").split()}
    outside = sorted(web - WEB_ALLOWED)
    diff = git("diff", "-U0", BASE, "--", *sorted(WEB_ALLOWED))
    minus = [l for l in diff.splitlines() if l.startswith("-") and not l.startswith("---")]
    plus = [l for l in diff.splitlines() if l.startswith("+") and not l.startswith("+++")]
    bad_plus = [l for l in plus if not re.match(r"^\+\s*(createdAt|companyName):", l)]
    print(f"  apps/web 바뀐 파일 {sorted(web)} · 허용 밖 {outside} · - 줄 {len(minus)} · + 줄 {len(plus)} · 칸 둘 밖 + 줄 {bad_plus}")
    if BOUNDARY == 1 and web:
        raise SystemExit(1)
    raise SystemExit(1 if outside or minus or bad_plus else 0)

# ── 6: 시험 수·이름 ────────────────────────────────────────────────────

TU = "esgapi/user/tests/service/services/test_user.py::"
TP = "esgapi/user/tests/service/actions/test_password.py::"
# 뒤집은 경우: 옛 id → 새 id(§3). 옛 id 가 사라지는 것은 이것뿐이어야 한다.
RENAMED = {
    TU + "test_password_problems_refuse_without_echoing_the_password[numeric]":
        TU + "test_password_problems_now_pass_what_the_removed_validators_refused[numeric]",
    TU + "test_password_problems_refuse_without_echoing_the_password[common]":
        TU + "test_password_problems_now_pass_what_the_removed_validators_refused[common]",
    TU + "test_password_problems_refuse_a_password_like_the_username":
        TU + "test_password_problems_now_pass_what_the_removed_validators_refused[like-the-username]",
    TP + "test_a_new_password_the_validators_refuse_changes_nothing[common]":
        TP + "test_a_new_password_the_removed_validators_refused_is_now_accepted[common]",
    TP + "test_a_new_password_the_validators_refuse_changes_nothing[numeric]":
        TP + "test_a_new_password_the_removed_validators_refused_is_now_accepted[numeric]",
}

if CMD == "collect":
    base_file, now_file = Path(ARGS[0]), Path(ARGS[1])
    node = lambda p: {line.strip() for line in p.read_text(encoding="utf-8").splitlines() if "::" in line}
    before, after = node(base_file), node(now_file)
    removed, added = sorted(before - after), sorted(after - before)
    print(f"  BASE {len(before)} · 지금 {len(after)} · 빠짐 {len(removed)} · 더함 {len(added)}")
    for n in removed:
        print(f"    - {n} → {RENAMED.get(n, '<짝 없음>')}")
    for n in added:
        print(f"    + {n}")
    unpaired = [n for n in removed if RENAMED.get(n) not in after]
    print(f"  짝 없는 빠짐 {len(unpaired)}")
    raise SystemExit(1 if unpaired or len(after) <= len(before) else 0)

# ── 7: 약화 대조 ─────────────────────────────────────────────────────

# (파일 끝부분, 지운 줄의 글자) → 항목. 지운 assert 줄이 전부 여기 있어야 한다.
MINUS_ASSERTS = [
    ("esgapi/user/tests/service/services/test_user.py",
     'rejected = password_problems(password, username="kim", name="김담당")', "§2-1 함수 꼴(username·name 인자 지움)"),
    ("esgapi/user/tests/service/services/test_user.py",
     "assert isinstance(rejected, PasswordRejected), rejected",
     "§1-7·§2-1 뒤집기 — 옛 test_password_problems_refuse_a_password_like_the_username 의 단언(비슷함 거절)이 "
     "test_password_problems_now_pass_what_the_removed_validators_refused[like-the-username] 로"),
    ("esgapi/user/tests/service/services/test_user.py",
     'assert password_problems(PASSWORD, username="kim", name="김담당") is None',"§2-1 함수 꼴(username·name 인자 지움) — 같은 단언"),
    ("esgapi/user/tests/service/services/test_user.py",
     'assert isinstance(create_operator(username="ops", name="운영자", password="password123"), PasswordRejected)',
     "§2-1·개정 2 B3 꼴 — 7자 거절로 바꾸고 흔함 받음은 test_a_common_password_now_creates_the_user"),
    ("esgapi/user/tests/service/apis/test_login.py",
     'assert status_code(change(client, access, PASSWORD, "12345678")) == (400, "PASSWORD_REJECTED")',
     "§2-1 apis/test_login.py:240 — 7자 400 + 8자 200"),
    ("esgapi/user/tests/management/commands/test_create_user.py",
     'assert "12345678" not in str(caught.value)', "개정 2 B3 test_create_user.py:75-78 — 7자 거절 + 8자 받음"),
    ("esgapi/user/tests/service/services/test_user.py",
     "assert isinstance(",
     "§2-5 B10·§1-7 (가) — test_user.py:341 고객사 같은 username(운영 관리자와 겹침)이 이제 UsernameTaken(감독 8a 받음)"),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(found) == 37',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) :168'),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(set(found.values())) == 37',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) :169'),
    ('esgapi/config/tests/test_api_contract.py',
     'assert (len(operations), len(with_body)) == (37, 16)',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) :184'),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(with_444) == 31',
     '개정 1-4 444 셈 31→32(새 엔드포인트 하나)'),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(USER_ADMIN_OPERATIONS) == 3',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) :453'),
    ('esgapi/config/tests/test_api_errors.py',
     'assert with_errors == 34',
     '개정 3 ④(감독 허락) :67'),
    ('esgapi/config/tests/test_api_errors.py',
     'assert len(takers) == 31',
     '개정 3 ④(감독 허락) :82'),
    ('esgapi/config/tests/test_api_times.py',
     'assert len(names) == 16  # 분모(E2 바닥에서 셈): 스키마 9 의 시각 칸',
     '개정 3 ⑤(감독 허락) — CustomerUserOut.createdAt'),
    ('esgapi/core/tests/test_permissions.py',
     'assert len(everything) == 37  # 분모: 공개 7 · 인증 30',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) test_permissions.py:116'),
    ('esgapi/core/tests/test_permissions.py',
     'assert len(NEEDS) == 30  # 분모: 회사 25 · 자기 2 · 운영 관리자 3(K2c)',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) :124'),
    ('esgapi/core/tests/test_permissions.py',
     'assert len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 28  # 분모: 막힌 수',
     '개정 2 B2 — 새 동작 user_update 하나로 셈 +1(이제 더 큰 수로 단언) :195'),
    ('esgapi/core/tests/test_transaction_rules.py',
     'assert len(files) == 11, [',
     '개정 3 (1)(감독 허락, X1a 파일) — 새 actions/account.py'),
    ('esgapi/user/tests/service/permissions/test_user.py',
     'assert set(USER_ADMIN_OPERATIONS) == {"user_list", "user_create", "user_password_reset"}',
     '개정 3 ⑨(감독 허락) — 넷째 user_update'),
    ('tests/security/test_login.py',
     'assert len(authenticated) == 30  # 분모: test_tenant_paths 의 표와 같은 수',
     '개정 3 ⑦(테스트 감독 허락) :278'),
    ('tests/security/test_login.py',
     'assert len(closed) == 28',
     "개정 3 ⑦'(테스트 감독 marcspon-39 허락) :299"),
    ('tests/security/test_tenant_paths.py',
     'assert (len(OPERATIONS), len(AUTHENTICATED)) == (37, 30)',
     "개정 3 ②'(테스트 감독 marcspon-39 허락) :260"),
]

if CMD == "weaken":
    diff = git("diff", "-U0", BASE, "--", "*/tests/*", "apps/api-py/tests")
    current = None
    rows = []
    for line in diff.splitlines():
        if line.startswith("--- a/"):
            current = line[6:]
        elif line.startswith("-") and not line.startswith("---") and "assert" in line:
            rows.append((current, line[1:].strip()))
    bad = 0
    for path, text in rows:
        hit = next((item for f, t, item in MINUS_ASSERTS if path and path.endswith(f) and t == text), None)
        print(f"  - {path}: {text}\n      → {hit or '<항목 없음>'}")
        bad += 0 if hit else 1
    print(f"  -assert 줄 {len(rows)} · 항목 없음 {bad}")
    raise SystemExit(1 if bad else 0)

# ── 10: 허용 경로 ────────────────────────────────────────────────────

ALLOWED_PATHS = [
    r"^apps/api-py/esgapi/user/service/",
    r"^apps/api-py/esgapi/user/tests/",
    r"^apps/api-py/esgapi/core/permissions\.py$",
    r"^apps/api-py/esgapi/core/tests/test_permissions\.py$",
    r"^apps/api-py/esgapi/core/tests/test_permissions_wiring\.py$",
    r"^apps/api-py/esgapi/core/tests/isolation/test_static_rules\.py$",
    r"^apps/api-py/esgapi/config/tests/test_api_contract\.py$",
    # 개정 3(감독 marcspon-fe·8a, 테스트 감독 f9·39 — 같은 새 동작 하나 때문의 셈 +1·표 한 줄)
    r"^apps/api-py/esgapi/config/tests/(test_api_errors|test_api_times|test_request_schemas_reject_bool)\.py$",
    r"^apps/api-py/esgapi/core/tests/test_transaction_rules\.py$",
    r"^apps/api-py/tests/security/test_tenant_paths\.py$",
    r"^apps/api-py/tests/security/test_refresh\.py$",  # 커밋 ③ 준비 차례(테스트 감독 39 허락)
    r"^apps/api-py/esgapi/organization/models\.py$",
    r"^apps/api-py/esgapi/organization/service/selectors/organization\.py$",
    r"^apps/api-py/generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$",
    r"^apps/api-py/tests/security/(test_user_admin|test_login)\.py$",
    r"^apps/api-py/scripts/(section4|planted-breaks)-UA1\.sh$",
    r"^apps/web/src/entities/account/api/testing\.ts$",
    r"^apps/web/src/app/admin/router\.test\.tsx$",
]

if CMD == "allowed":
    changed = changed_files()
    outside = sorted(p for p in changed if not any(re.search(a, p) for a in ALLOWED_PATHS))
    print(f"  바뀐 파일 {len(changed)}:")
    for p in sorted(changed):
        print(f"    {p}")
    print(f"  허용 밖: {outside}")
    if BOUNDARY == 1 and any(p.startswith(("apps/api-py/generated/", "apps/web/")) for p in changed):
        print("  경계 1 에 generated·apps/web 이 바뀜 — 실패")
        raise SystemExit(1)
    raise SystemExit(1 if outside or not changed else 0)

# ── 11: organization 은 docstring 만 ───────────────────────────────────

def strip_docstrings(text: str) -> str:
    tree = ast.parse(text)
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                body[0].value.value = "<docstring>"
    return ast.dump(tree)


if CMD == "org":
    files = [API + "esgapi/organization/models.py", API + "esgapi/organization/service/selectors/organization.py"]
    other = sorted(p for p in changed_files() if p.startswith(API + "esgapi/organization/") and p not in files)
    bad = len(other)
    for f in files:
        b = at_base(f)
        positive = strip_docstrings(b) == strip_docstrings(b)  # 양성 대조: BASE 끼리 같다
        same = strip_docstrings(b) == strip_docstrings(now(f))
        print(f"  {f}: 바뀜={'예' if b != now(f) else '아니오'} docstring 밖 같음={'예' if same else '아니오'} 양성 대조={positive}")
        bad += 0 if (same and positive) else 1
    print(f"  그 밖의 organization 파일 바뀜: {other}")
    raise SystemExit(1 if bad else 0)

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
    # 양성 대조: 무늬가 키 꼴을 잡는다
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
    esgapi/user esgapi/core esgapi/config esgapi/organization) > "$S4/2-business.txt" 2>&1
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
  if [ "$BOUNDARY" = "1" ]; then
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
  git -C "$ROOT" diff --quiet "$BASE" -- packages apps/api-py/.importlinter apps/api-py/esgapi/config/apps_list.py \
    apps/api-py/esgapi/config/api.py apps/api-py/esgapi/config/settings apps/api-py/scripts/planted-breaks.sh \
    apps/api-py/esgapi/core/tests/test_selector_scope.py \
    apps/api-py/esgapi/core/tests/test_flows_core_names.py apps/api-py/esgapi/user/migrations \
    apps/api-py/esgapi/user/models.py apps/api-py/pyproject.toml apps/api-py/uv.lock compose.yaml README.md \
    apps/api-py/scripts/rehearsal.sh
  rc_z=$?
  helper web > "$S4/4-web.txt" 2>&1
  rc_w=$?
  cat "$S4/4-web.txt"
  rc=0; [ "$rc_z" = "0" ] && [ "$rc_w" = "0" ] || rc=1
  report 4 "0줄(diff ${rc_z} 웹 두 파일 더하기만 ${rc_w})" "$rc"
fi

if want 5; then
  api lint-imports > "$S4/5-lint-imports.txt" 2>&1
  rc_l=$?
  last="$(grep -E '^Contracts:' "$S4/5-lint-imports.txt" | tail -1)"
  base_last="$(grep -E '^Contracts:' "$OUT/lint-imports-base.txt" 2>/dev/null | tail -1)"
  echo "  지금: $last · BASE: ${base_last:-<없음>}"
  rc=0; [ "$rc_l" = "0" ] && [ -n "$base_last" ] && [ "$last" = "$base_last" ] && [ "$last" = "Contracts: 15 kept, 0 broken." ] || rc=1
  report 5 "import 계약(15 kept, BASE 와 같음)" "$rc"
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
    cat "$S4/6-collect.txt"
    rc=0; [ "$rc_c" = "0" ] && [ "$rc_n" = "0" ] || rc=1
    report 6 "시험 수·이름(사라진 id 는 짝 목록뿐)" "$rc"
  fi
fi

if want 7; then
  helper weaken > "$S4/7-weaken.txt" 2>&1
  rc=$?
  cat "$S4/7-weaken.txt"
  report 7 "약화 대조(-assert 줄마다 항목)" "$rc"
fi

if want 8; then
  "$API_PY/scripts/planted-breaks-UA1.sh" --boundary "$BOUNDARY" $WITH_CONTAINERS > "$S4/8-planted.txt" 2>&1
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
  helper org > "$S4/11-org.txt" 2>&1
  rc=$?
  cat "$S4/11-org.txt"
  report 11 "organization 은 docstring 만" "$rc"
fi

if want 12; then
  helper keys "${UA1_COMMIT_MSG_FILE:-}" > "$S4/12-keys.txt" 2>&1
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
