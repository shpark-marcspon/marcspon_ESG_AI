#!/usr/bin/env bash
# 밴드 AUTHZ1 의 심은 파손(발주서 band-handoffs/AUTHZ1-order.md §3). 하나씩 심고 겨눈 시험만 돌린 뒤 손으로 되돌린다(원본
# 바이트를 들고 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(어디서든):
#   apps/api-py/scripts/planted-breaks-AUTHZ1.sh [--boundary 1|2] [--with-containers] [--only P1,P4]
#
# 판정: 0번(아무것도 안 심음)은 겨눈 시험이 전부 초록. 「잡음」= 심은 뒤 그 층의 pytest 가 0 아닌 종료이고, 빨개져야 할
# 시험 노드가 전부 FAILED 로 찍힘(그 밖에 더 빨개진 것은 적기만 한다).
# 경계 1(커밋 ① 앞)에는 ② 의 보안 시험이 없어 그것을 겨눈 단계(P2 의 보안 층, P6)는 심지 않는다. 컨테이너가 필요한 단계
# (P2 의 업무·보안 층, P6)는 --with-containers 일 때만 — 아니면 「안 돌림」으로 찍고 잡은 수·심은 수에 넣지 않는다.
# 심을 때마다 파일이 실제로 바뀌었는지 먼저 본다. 끝에 심은 파일의 sha256 이 시작과 같은지, git status 가 시작과 같은지
# 본다(FINGERPRINT=same|DIFF). 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물: AUTHZ1_OUT(기본: 워크트리 곁의 AUTHZ1.out)/planted/. 공급사를 부르지 않는다. macOS bash 3.2.
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${AUTHZ1_OUT:-$(cd "$ROOT/.." && pwd)/AUTHZ1.out}"
mkdir -p "$OUT/planted"
exec env -u OPENAI_API_KEY uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import os
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

LOGS = Path(sys.argv[1])
args = sys.argv[2:]
BOUNDARY = "2"
CONTAINERS = False
ONLY = None
while args:
    if args[0] == "--boundary" and len(args) > 1 and args[1] in ("1", "2"):
        BOUNDARY, args = args[1], args[2:]
    elif args[0] == "--with-containers":
        CONTAINERS, args = True, args[1:]
    elif args[0] == "--only" and len(args) > 1:
        ONLY, args = set(args[1].split(",")), args[2:]
    else:
        sys.exit(f"모르는 인자: {args}")


def swap(old: str, new: str) -> Callable[[str], str | None]:
    def plant(text: str) -> str | None:
        return text.replace(old, new, 1) if text.count(old) == 1 else None

    return plant


def drop_security(operation_id: str) -> Callable[[str], str | None]:
    """openapi.json 에서 그 동작의 security 칸 줄들을 지운다(글자로 — 나머지 바이트는 그대로)."""

    def plant(text: str) -> str | None:
        at = text.find(f'"operationId": "{operation_id}"')
        if at < 0:
            return None
        start = text.find('"security": [', at)
        nxt = text.find('"operationId":', at + 1)
        if start < 0 or (0 <= nxt < start):
            return None
        depth, end = 0, start + len('"security": ')
        for end in range(end, len(text)):  # 짝 맞는 ] 까지(안에 "CompanyScopedAuth": [] 가 있다)
            depth += {"[": 1, "]": -1}.get(text[end], 0)
            if depth == 0:
                break
        end += 1
        # 앞의 쉼표까지 지운다: ...,\n      "security": [ ... ]
        comma = text.rfind(",", 0, start)
        return text[:comma] + text[end:]

    return plant


def add_public_operation(text: str) -> str | None:
    anchor = '  "paths": {\n'
    if text.count(anchor) != 1:
        return None
    extra = (
        '    "/planted-public": {\n      "get": {\n        "operationId": "planted_public",\n'
        '        "summary": "planted",\n        "responses": {"200": {"description": "OK"}}\n      }\n    },\n'
    )
    return text.replace(anchor, anchor + extra, 1)


PERM = Path("esgapi/core/permissions.py")
OPENAPI = Path("generated/openapi.json")
INV_API = Path("esgapi/inventory/service/apis/inventory.py")
ORG_SVC = Path("esgapi/organization/service/services/organization.py")
SEC = Path("tests/security/test_tenant_paths.py")
TP = "esgapi/core/tests/test_permissions.py::"
PURE_TARGET = ["esgapi/core/tests/test_permissions.py"]
WIRING = "esgapi/core/tests/test_permissions_wiring.py"
SEC_TEST = "tests/security/test_tenant_paths.py::test_a_customer_bearer_passes_auth_and_permission_on_every_company_operation"
PUBLIC = TP + "test_the_public_operations_are_these_seven"

# 층: (이름, 명령 앞부분, 겨눔, 컨테이너가 필요한가)
PURE = ("순수", ["uv", "run", "--frozen", "pytest", "-q", "-rf", "-p", "no:cacheprovider", "-m", "not django_db and not security"], PURE_TARGET, False)
BUSINESS = ("업무", ["scripts/test-business.sh", "-rf", "-p", "no:cacheprovider"], [WIRING], True)
SECURITY = ("보안", ["scripts/test-security.sh", "-rf", "-p", "no:cacheprovider"], [SEC_TEST], True)

# (번호, 설명, [(파일, 심는 함수)], [(층, 빨개져야 할 노드 묶음, 이 경계에 있는가)])
PLANTS = [
    ("P1", "표에서 inventory_scope3_classify 줄을 지움",
     [(PERM, swap('    "inventory_scope3_classify": CUSTOMER,\n', ""))],
     [(PURE, {TP + n for n in ("test_every_authenticated_operation_is_in_the_table", "test_the_table_is_these_needs",
                                "test_the_cells_are_partitioned", "test_an_operator_is_refused_every_customer_cell",
                                "test_no_cell_is_proposed", "test_each_route_checks_its_own_operation_id_first",
                                "test_the_public_operations_are_these_seven")}, True)]),
    ("P2", "inventory_calc 칸을 OPERATOR 로",
     [(PERM, swap('    "inventory_calc": CUSTOMER,\n', '    "inventory_calc": OPERATOR,\n'))],
     [(PURE, {TP + n for n in ("test_the_table_is_these_needs", "test_the_cells_are_partitioned",
                                "test_an_operator_is_refused_every_customer_cell")}, True),
      (BUSINESS, None, True),
      (SECURITY, {SEC_TEST}, BOUNDARY == "2")]),
    ("P3", "분류 경로의 permitted(…) 를 principal_of(request) 로",
     [(INV_API, swap('principal = permitted(request, "inventory_scope3_classify")', "principal = principal_of(request)"))],
     [(PURE, {TP + "test_each_route_checks_its_own_operation_id_first"}, True)]),
    ("P4", "openapi.json 에 security 없는 동작 하나를 더함",
     [(OPENAPI, add_public_operation)],
     [(PURE, {PUBLIC}, True)]),
    ("P5", "openapi.json 에서 inventory_scope3_classify 의 security 를 지움",
     [(OPENAPI, drop_security("inventory_scope3_classify"))],
     [(PURE, {TP + "test_every_authenticated_operation_is_in_the_table", PUBLIC}, True)]),
    ("P6", "보안 시험 ② 의 본문 표에서 inventory_calc 의 본문을 {} 로",
     [(SEC, swap('    "inventory_calc": ("", CALC_BODY),\n', '    "inventory_calc": ("", {}),\n'))],
     [(SECURITY, {SEC_TEST}, BOUNDARY == "2")]),
    ("P7", "organization.py 의 can_create_site(...) 를 True 로",
     [(ORG_SVC, swap("if not can_create_site(principal.kind) or", "if not True or"))],
     [(PURE, {TP + "test_the_two_site_routes_reach_the_table_inside_their_selector_and_service"}, True)]),
]
if ONLY:
    PLANTS = [p for p in PLANTS if p[0] in ONLY]


def status() -> str:
    return subprocess.run(["git", "status", "--porcelain", "--untracked-files=all"], capture_output=True, text=True,
                          check=True).stdout


def runnable(layer) -> bool:
    return CONTAINERS or not layer[3]


def run(layer, log: Path) -> tuple[int, set[str], str]:
    name, cmd, targets, _ = layer
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache")}
    env.pop("OPENAI_API_KEY", None)
    done = subprocess.run([*cmd, *targets], capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    failed = set(re.findall(r"^FAILED (\S+?)(?: - .*)?$", text, flags=re.M))
    last = text.strip().splitlines()[-1] if text.strip() else ""
    return done.returncode, failed, last


files = sorted({f for p in PLANTS for f, _ in p[2]})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
status_before = status()

# 0번: 아무것도 안 심음 — 쓰는 층이 초록
layers_used = []
for p in PLANTS:
    for layer, _, here in p[3]:
        if here and runnable(layer) and layer not in layers_used:
            layers_used.append(layer)
zero_ok = True
for layer in layers_used:
    code, failed, last = run(layer, LOGS / f"P0-{layer[0]}.log")
    print(f"P0 {layer[0]} 초록: EXIT={code} {last}")
    zero_ok = zero_ok and code == 0

caught = planted = 0
for number, what, edits, checks in PLANTS:
    if not any(here for _, _, here in checks):
        print(f"{number} 안 돌림(경계 {BOUNDARY}: 겨눈 시험이 아직 없다) — {what}")
        continue
    originals = {f: f.read_bytes() for f, _ in edits}
    try:
        ok_plant = True
        for f, plant in edits:
            text = f.read_text(encoding="utf-8")
            new = plant(text)
            if new is None or new == text:
                ok_plant = False
                break
            f.write_text(new, encoding="utf-8")
        if not ok_plant:
            print(f"{number} 심기 실패(파일이 바뀌지 않음) — {what}")
            planted += 1
            continue
        for layer, expected, here in checks:
            label = f"{number}/{layer[0]}"
            if not here:
                print(f"{label} 안 돌림(경계 {BOUNDARY}: 겨눈 시험이 아직 없다) — {what}")
                continue
            if not runnable(layer):
                print(f"{label} 안 돌림(컨테이너 — --with-containers 없음) — {what}")
                continue
            planted += 1
            code, failed, last = run(layer, LOGS / f"{number}-{layer[0]}.log")
            if expected is None:
                hit = code != 0 and bool(failed)
            else:
                hit = code != 0 and expected <= failed
            caught += 1 if hit else 0
            missing = sorted((expected or set()) - failed)
            print(f"{label} {'잡음' if hit else '못 잡음'} EXIT={code} 빨강 {len(failed)} 빠진 기대 {missing} — {what}")
            for node in sorted(failed):
                print(f"    FAILED {node}")
    finally:
        for f, data in originals.items():
            f.write_bytes(data)

same = all(hashlib.sha256(f.read_bytes()).hexdigest() == h for f, h in start.items()) and status() == status_before
print(f"P0={'green' if zero_ok else 'RED'}")
print(f"FINGERPRINT={'same' if same else 'DIFF'}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if zero_ok and same and caught == planted and planted > 0 else 1)
PY
