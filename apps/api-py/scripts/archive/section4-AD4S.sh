#!/usr/bin/env bash
# 밴드 AD4S 의 §4 자기검증(발주서 band-handoffs/AD4S-order.md §4, 개정 3). 줄마다 [n] … EXIT= 를 찍고 끝에
# SECTION4_FAIL=<n>.
# 사용(어디서든):
#   apps/api-py/scripts/section4-AD4S.sh --boundary 1|2|3 --with-containers                 전부
#   apps/api-py/scripts/section4-AD4S.sh --boundary 1 --step 1,2,3 --with-containers         고른 단계만
#   --with-containers   9 의 심은 파손에서 업무·보안 층의 것도 심는다(없으면 「안 돌림」 줄이 생겨 9 가 실패한다)
#
# 단계(§4): 1 순수 · 2 업무·보안 · 3 계약(generated 다시 뽑아 cmp·sha·계약 시험·바뀐 자리) · 4 0줄 경로 ·
#   5 lint-imports kept = BASE + runs 이름 검사 · 6 makemigrations --check · 7 수집(사라진 id 0) · 8 약화 대조 ·
#   9 심은 파손 · 10 verify.sh --fast · 11 바뀐 경로 ⊆ 허용 · 12 제품 record_event 자리 · 13 키 꼴 0 · 웹 typecheck ·
#   14 git status --porcelain 0(커밋 뒤에만 — 커밋 전에는 --step 으로 뺀다).
#
# 환경 변수:
#   AD4S_BASE   기준 커밋(기본: 워크트리를 만든 main b4d7955 = merge band/CO1)
#   AD4S_OUT    산출물 자리(기본: 워크트리 곁의 AD4S.out). collect-base.txt·collect-security-base.txt·
#               lint-imports-base.txt 가 여기 있어야 한다(경계 ① 전에 BASE 에서 뜬 것)
#   AD4S_COMMIT_MSG_FILE  커밋 전에 볼 커밋 메시지 초안(13 이 BASE..HEAD 의 메시지와 함께 본다)
# 2·6·9 는 Postgres 가 떠 있어야 한다(.env 의 COMPOSE_PROJECT_NAME → docker compose up -d --wait postgres).
# 컨테이너를 띄우지 않는다. 공급사를 부르지 않는다. 전량 scripts/verify.sh 는 돌리지 않는다(--fast 만). 통합 층은 안 돌림.
# macOS /bin/bash 3.2: 명령 치환 뒤의 $? 는 다음 줄에서 받는다. 한글이 바로 뒤에 오는 변수는 ${n} 꼴.
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
SIDE="$(cd "$ROOT/.." && pwd)"
BASE="${AD4S_BASE:-b4d7955}"
OUT="${AD4S_OUT:-$SIDE/AD4S.out}"
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

HELPER="$S4/ad4s_helper.py"
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


# 경계마다 바뀌어도 되는 잎(쌓인다). ① RunLogOut 칸 둘·RunAiSettingOut·질의 review·/run-logs GET description
# ② /run-logs/export 경로 전부 ③ AuditEventOut.module
CHANGED_OK = {
    1: [
        r"/paths/~1run-logs/get/description",
        r"/paths/~1run-logs/get/parameters/review(/.*)?",
        r"/components/schemas/RunLogOut/properties/(review|aiSetting)(/.*)?",
        r"/components/schemas/RunLogOut/required/\d+",
        r"/components/schemas/RunAiSettingOut(/.*)?",
    ],
    2: [r"/paths/~1run-logs~1export(/.*)?"],
    3: [
        r"/components/schemas/AuditEventOut/properties/module(/.*)?",
        r"/components/schemas/AuditEventOut/required/\d+",
    ],
}
NEW_SCHEMAS = ["RunAiSettingOut"]
NEW_OPS = {1: {}, 2: {("/run-logs/export", "get"): "user_run_log_export"}}
NEW_OPS[3] = NEW_OPS[2]

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
        and changed
        and ops == NEW_OPS[BOUNDARY]
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

# ── 4·11: 0줄 경로(§1-3)와 허용 경로(§1-2 ∪ §1-4) ─────────────────────────────

P = r"^apps/api-py/"
E = P + r"esgapi/"
W = r"^apps/web/"
ALLOWED_PATHS = {
    # §1-2 이 감독의 땅
    E + r"runs/extras\.py$": 1,
    E + r"runs/service/selectors/operator\.py$": 1,
    E + r"runs/tests/(test_extras|service/selectors/test_operator)\.py$": 1,
    E + r"user/service/(apis|schemas)/run_logs\.py$": 1,
    E + r"user/service/(apis|schemas)/audit\.py$": 3,
    E + r"user/service/utils/run_log_xlsx\.py$": 2,
    E + r"user/tests/service/apis/test_run_logs\.py$": 1,
    E + r"user/tests/service/utils/test_run_log_xlsx\.py$": 2,
    E + r"user/tests/service/apis/test_audit\.py$": 3,
    E + r"core/permissions\.py$": 2,
    E + r"core/calc/audit\.py$": 2,
    E + r"core/service/(services|selectors)/audit\.py$": 3,
    E + r"core/models\.py$": 3,
    E + r"core/tests/(calc|service/services)/test_audit\.py$": 2,
    E + r"core/tests/(test_permissions|test_permissions_wiring)\.py$": 2,
    E + r"core/tests/(test_selector_scope|isolation/test_static_rules)\.py$": 1,
    E + r"config/tests/test_api_(contract|errors)\.py$": 2,
    P + r"generated/(openapi\.json|api\.d\.ts|api\.d\.ts\.source-sha256)$": 1,
    P + r"scripts/(section4|planted-breaks)-AD4S\.sh$": 1,
    # §1-4 82(그린워싱)
    E + r"greenwash/service/selectors/run_extras\.py$": 1,
    E + r"greenwash/service/actions/checks\.py$": 1,
    E + r"greenwash/apps\.py$": 1,
    E + r"greenwash/tests/service/selectors/test_run_extras\.py$": 1,
    E + r"greenwash/service/actions/ai_settings\.py$": 3,
    E + r"greenwash/tests/service/apis/test_ai_settings(_model)?\.py$": 3,
    # §1-4 9f(보안)
    P + r"tests/security/test_run_logs\.py$": 1,
    P + r"tests/security/(test_tenant_paths|test_login)\.py$": 2,
    P + r"tests/security/test_operator_company\.py$": 2,  # 9f 허락(230 노트) — :223 분모 15→16
    # §1-4 46(웹) + 230 노트 46 허락(run.test.ts:177)
    W + r"src/entities/run-log/api/testing\.ts$": 1,
    W + r"src/entities/run-log/model/run\.test\.ts$": 1,
    W + r"src/entities/audit-log/api/testing\.ts$": 3,
    W + r"src/entities/audit-log/model/audit\.test\.ts$": 3,
}
ZERO_PATHS = [
    P + r"\.importlinter$", P + r"(pyproject\.toml|uv\.lock)$", r"/migrations/",
    E + r"runs/models\.py$", E + r"runs/service/selectors/runs\.py$", E + r"core/flows/",
    P + r"tests_integration/", r"conftest\.py$", P + r"tests/support/",
    P + r"scripts/(planted-breaks|verify)\.sh$", E + r"config/(api|apps_list)\.py$", E + r"config/settings/",
]
# §1-3 의 「중 §1-4 밖」(greenwash·tests/security·W) 은 11 의 허용 목록이 잰다.


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
    planted = "apps/api-py/esgapi/runs/service/selectors/runs.py"
    positive = [p for p in [planted] if not any(re.search(a, p) for a in ALLOWED_PATHS)]
    print(f"  양성 대조(가짜 runs/service/selectors/runs.py) 허용 밖 → {positive}")
    raise SystemExit(1 if outside or early or not changed or not positive else 0)

# ── 7: 시험 수·이름 ────────────────────────────────────────────────────

SRUN = "tests/security/test_run_logs.py"
SECURITY_ADDED = {
    1: {SRUN + "::test_a_review_row_of_a_does_not_reach_the_runs_of_b"},
}
SECURITY_ADDED[2] = SECURITY_ADDED[1] | {
    SRUN + "::test_a_customer_bearer_gets_no_export",
    SRUN + "::test_the_export_for_b_holds_no_name_of_a",
    "tests/security/test_tenant_paths.py::test_without_a_session_it_is_401[GET /run-logs/export]",
}
SECURITY_ADDED[3] = SECURITY_ADDED[2]


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
MINUS = [
    ("esgapi/core/tests/isolation/test_static_rules.py", "assert opened == 61", 1, "assert opened == 62",
     "§2-4 ① opened 61 → 62"),
    ("esgapi/runs/tests/service/selectors/test_operator.py",
     "with django_assert_num_queries(2):  # 셈 1 + 읽기 1(문서 이름은 같은 쿼리의 join)", 1,
     "with django_assert_num_queries(3):", "감독 f8 허락(물음 1) test_operator 쪽 쿼리 2 → 3"),
    ("esgapi/user/tests/service/apis/test_run_logs.py",
     "assert (len(body_queries(empty_list)), len(body_queries(full_list))) == (3, 5)", 1,
     "assert (len(body_queries(empty_list)), len(body_queries(full_list))) == (3, 7)", "§3 M1 쿼리 수 (3,5) → (3,7)"),
    ("esgapi/greenwash/tests/service/apis/test_ai_settings_model.py",
     'assert lines(a) == [("ai_setting_created", v1, {"changed_fields": ["criteria", "memo", "model_settings"]})]', 3,
     '("ai_setting_created", v1, {"changed_fields": ["criteria", "memo", "model_settings"], "module": "greenwash"})',
     "§1-4 82 :360 module 더함(ruff format 이 줄을 나눔 — 짝은 안쪽 튜플 줄)"),
    ("tests/security/test_operator_company.py", "assert len(OPERATOR_OPERATIONS) == 15  # 분모", 2,
     "assert len(OPERATOR_OPERATIONS) == 16  # 분모(AD4S +1: user_run_log_export)", "9f 허락 운영 관리자 칸 15 → 16"),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(found) == 53  # TR2 +1', 2,
     'assert len(found) == 54  # TR2 +1 · AD4S +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(set(found.values())) == 53  # TR2 +1', 2,
     'assert len(set(found.values())) == 54  # TR2 +1 · AD4S +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/config/tests/test_api_contract.py',
     'assert (len(operations), len(with_body)) == (53, 20)  # TR2 +1: GET /translation/runs/{run_id}/result', 2,
     'assert (len(operations), len(with_body)) == (54, 20)  # TR2 +1: GET /translation/runs/{run_id}/result · AD4S +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(with_444) == 47  # G1b-1 +1: GET /greenwash/checks · G2c2 +5: AI 설정 판 · AS2a +2: prompt-model 둘', 2,
     'assert len(with_444) == 48  # G1b-1 +1: GET /greenwash/checks · G2c2 +5: AI 설정 판 · AS2a +2: prompt-model 둘', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/config/tests/test_api_contract.py',
     'assert len(USER_ADMIN_OPERATIONS) == 8', 2,
     'assert len(USER_ADMIN_OPERATIONS) == 9  # AD4S +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/config/tests/test_api_errors.py',
     'assert with_errors == 50  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1', 2,
     'assert with_errors == 51  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/config/tests/test_api_errors.py',
     'assert len(takers) == 47  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1', 2,
     'assert len(takers) == 48  # UA1: 수정(PATCH /users/{user_id}) +1 · AU1a: GET /audit-logs +1 · AU1b-1 +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/core/tests/calc/test_audit.py',
     'assert TARGET_KINDS == ("user", "document", "run", "report", "greenwash_item", "ai_setting")', 2,
     'assert TARGET_KINDS == ("user", "document", "run", "report", "greenwash_item", "ai_setting", "run_log_export")', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/core/tests/test_permissions.py',
     'assert len(everything) == 53  # 분모: 공개 7 · 인증 46(G2c2 +5 · AS2a +2 · TR2 +1)', 2,
     'assert len(everything) == 54  # 분모: 공개 7 · 인증 47(G2c2 +5 · AS2a +2 · TR2 +1 · AD4S +1)', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/core/tests/test_permissions.py',
     'assert len(NEEDS) == 46  # 분모: 고객사 10 · 회사 업무 19 · 자기 2 · 운영 관리자 15', 2,
     'assert len(NEEDS) == 47  # 분모: 고객사 10 · 회사 업무 19 · 자기 2 · 운영 관리자 16', "§2-4 ② 셈 +1(AD4S export)"),
    ('esgapi/core/tests/test_permissions.py',
     'len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 44', 2,
     'len(authenticated - INITIAL_ALLOWED) == len(authenticated) - 2 == 45', "§2-4 ② 셈 +1(AD4S export)"),
    ('tests/security/test_login.py',
     'assert len(authenticated) == 46  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})', 2,
     'assert len(authenticated) == 47  # 분모: test_tenant_paths 의 표와 같은 수(UA1 +1: PATCH /users/{user_id})', "§2-4 ② 셈 +1(AD4S export)"),
    ('tests/security/test_login.py',
     'assert len(closed) == 44  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1', 2,
     'assert len(closed) == 45  # UA1 +1: PATCH /users/{user_id} · AU1a +1: GET /audit-logs · AU1b-1 +1', "§2-4 ② 셈 +1(AD4S export)"),
    ('tests/security/test_tenant_paths.py',
     'assert (len(OPERATIONS), len(AUTHENTICATED)) == (53, 46)', 2,
     'assert (len(OPERATIONS), len(AUTHENTICATED)) == (54, 47)', "§2-4 ② 셈 +1(AD4S export)"),
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

# ── 12: 제품의 record_event 부르는 자리(① = BASE, ②③ = BASE + 내보내기 하나) ───────


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
    want = base if BOUNDARY == 1 else base | {(API + "esgapi/user/service/apis/run_logs.py", "run_log_export")}
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
  "$API_PY/scripts/planted-breaks-AD4S.sh" --boundary "$BOUNDARY" $WITH_CONTAINERS > "$S4/9-planted.txt" 2>&1
  rc_p=$?
  grep -E '^(P[0-9a-z]+ =>|P0=|PLANTED=|FINGERPRINT=)' "$S4/9-planted.txt"
  expect="PLANTED=10/10"
  [ "$BOUNDARY" = "2" ] && expect="PLANTED=24/24"  # 발주서 22 + HB(감독 f8) + P9b(9f 조건 (사))
  [ "$BOUNDARY" = "3" ] && expect="PLANTED=28/28"
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
  report 12 "제품 record_event 자리(① BASE · ②③ BASE+1)" "$rc"
fi

if want 13; then
  helper keys "${AD4S_COMMIT_MSG_FILE:-}" > "$S4/13-keys.txt" 2>&1
  rc_k=$?
  cat "$S4/13-keys.txt"
  (cd "$ROOT" && PATH="$NODE_PATH_DIR:$PATH" pnpm --dir apps/web typecheck) > "$S4/13-web-typecheck.txt" 2>&1
  rc_w=$?
  echo "  pnpm --dir apps/web typecheck EXIT=${rc_w}"
  rc=0; [ "$rc_k" = "0" ] && [ "$rc_w" = "0" ] || rc=1
  report 13 "키 꼴 0 · 웹 typecheck" "$rc"
fi

if want 14; then
  porcelain="$(git -C "$ROOT" status --porcelain)"
  n=0; [ -z "$porcelain" ] || n=$(printf '%s\n' "$porcelain" | wc -l | tr -d ' ')
  echo "  git status --porcelain ${n}줄"
  rc=0; [ "$n" = "0" ] || rc=1
  report 14 "작업 트리 깨끗(커밋 뒤)" "$rc"
fi

echo "SECTION4_FAIL=$FAIL"
[ "$FAIL" = "0" ]
