#!/usr/bin/env bash
# 밴드 E2 의 심은 파손(발주서 band-handoffs/E2-order.md §3 의 여섯 + 검증 뒤 고침 B1·R1·R3 의 셋). 하나씩 심고 돌린 뒤 손으로 되돌린다(원본 바이트를 들고
# 있다가 되쓴다 — git checkout·restore·stash 를 쓰지 않는다). 사용(apps/api-py 에서): scripts/planted-breaks-E2.sh
#
# 판정(GR1 꼴): 0번(아무것도 안 심음)은 전부 초록. 「잡음」= 종료 코드 ≠ 0 이고, 그 줄의 「빨개져야 하는 것」이
# 출력의 FAILED·ERROR 줄에 있다. 끝 줄 PLANTED=<잡은 수>/<심은 수>. 순수 층만 돈다(DB 없음).
# 끝에 심은 파일의 sha256 이 시작과 같은지 본다(FINGERPRINT=same|DIFF).
# 산출물: E2_OUT(기본: 워크트리 곁의 E2.out)/planted/
set -u
cd "$(dirname "$0")/.."
ROOT="$(cd ../.. && pwd)"
OUT="${E2_OUT:-$(cd "$ROOT/.." && pwd)/E2.out}"
mkdir -p "$OUT/planted"
exec uv run --frozen python - "$OUT/planted" <<'PY'
import hashlib
import os
import subprocess
import sys
from pathlib import Path

LOGS = Path(sys.argv[1])
X = Path("esgapi/core/exceptions.py")
A = Path("esgapi/config/api.py")
S = Path("esgapi/core/schemas.py")
M = Path("esgapi/core/observability/middleware.py")
U = Path("esgapi/config/urls.py")
I = Path("esgapi/inventory/service/schemas/inventory.py")
TESTS = [
    "esgapi/core/tests/test_exceptions.py",
    "esgapi/core/tests/test_schemas.py",
    "esgapi/config/tests/test_api_errors.py",
    "esgapi/config/tests/test_api_times.py",
    "esgapi/config/tests/test_api_contract.py",
    "esgapi/config/tests/test_request_schemas_reject_bool.py",
]
CMD = ["uv", "run", "--frozen", "pytest", "-q", "-rfE", "-p", "no:cacheprovider", "-m", "not django_db and not security", *TESTS]

# (번호, 심는 것, 파일, [(옛 글, 새 글), …], 빨개져야 하는 것(FAILED/ERROR 줄에 들어야 하는 글 — 하나라도))
PLANTS = [
    (1, "본문에서 fields 를 뺌", X,
     [('    return JsonResponse({"error": detail.model_dump()}, status=status)',
       '    return JsonResponse({"error": detail.model_dump(exclude={"fields"})}, status=status)')],
     ["test_error_response_carries_all_four_keys", "test_a_malformed_login_body_is_422"]),
    (2, "legacyCode 를 싣지 않음", X,
     [("                self.legacyCode = self.code", "                pass")],
     ["test_error_response_carries_all_four_keys", "test_a_detail_built_in_lowercase_goes_out_in_uppercase_once"]),
    (3, "요청 꼴 틀림을 400 으로 되돌림", A,
     [('    "validation": 422,', '    "validation": 400,')],
     ["test_a_malformed_login_body_is_422"]),
    (4, "500 본문에 예외 글자를 실음", A,
     [('    log.exception("unhandled error: %s %s", request.method, request.path, exc_info=exc)\n'
       '    return error_response(500, "INTERNAL_SERVER_ERROR", INTERNAL_MESSAGE)',
       '    log.exception("unhandled error: %s %s", request.method, request.path, exc_info=exc)\n'
       '    return error_response(500, "INTERNAL_SERVER_ERROR", f"{INTERNAL_MESSAGE}: {exc!r}")')],
     ["test_an_unexpected_exception_is_500_with_no_detail_and_is_logged"]),
    (5, "+09:00 을 UTC 그대로로", S,
     [("    return value.astimezone(SEOUL).isoformat()", "    return value.isoformat()")],
     ["test_utc_near_midnight_moves_to_the_next_seoul_day", "test_the_types_serialise_in_python_and_json_modes"]),
    (6, "444 선언을 뺌(공통 표 TOKEN_ERROR_RESPONSES — 그것을 펼친 동작마다 하나씩 빠짐)", S,
     [("TOKEN_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**ERROR_RESPONSES, 444: ErrorBody}",
       "TOKEN_ERROR_RESPONSES: dict[int, type[ErrorBody]] = {**ERROR_RESPONSES}")],
     ["test_444_is_declared_exactly_by_the_operations_that_take_a_token"]),
    # 검증 뒤 고침(B1·R1)
    (7, "405 를 오류 꼴로 바꾸지 않음(ninja 의 text/html 그대로)", M,
     [("            if isinstance(response, HttpResponseNotAllowed):\n                response = method_not_allowed(response)\n", "")],
     ["test_a_method_the_path_does_not_have_is_405_in_the_one_shape_and_keeps_allow"]),
    (8, "handler500 을 걷음(Django 의 HTML 500)", U,
     [("handler500 = server_error\n", "")],
     ["test_an_exception_outside_ninja_is_500_in_the_one_shape", "test_the_urls_hand_404_and_500_to_the_one_shape"]),
    (9, "TierIn 에서 IntOnly 를 뺌(1.0 을 등급 1 로 받음)", I,
     [("TierIn = Annotated[Tier, NotBool, IntOnly]", "TierIn = Annotated[Tier, NotBool]")],
     ["test_each_tier_takes_1_and_refuses_1_point_0_and_the_text_1", "test_every_integer_field_of_every_request_body_rejects_true"]),
]

files = sorted({p[2] for p in PLANTS})
start = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}


def run(cmd: list[str], log: Path) -> tuple[int, str]:
    # 바이트코드 격리: 심은 글과 되돌린 글이 같은 크기·같은 초면 __pycache__ 의 낡은 .pyc 가 쓰일 수 있다.
    env = {**os.environ, "PYTHONPYCACHEPREFIX": str(LOGS / "pycache" / log.stem)}
    done = subprocess.run(cmd, capture_output=True, text=True, check=False, env=env)
    text = done.stdout + done.stderr
    log.write_text(text, encoding="utf-8")
    return done.returncode, text


def red_lines(text: str) -> list[str]:
    return [line for line in text.splitlines() if line.startswith(("FAILED", "ERROR"))]


code, _ = run(CMD, LOGS / "00.log")
zero_ok = code == 0
print(f"[0] 아무것도 안 심음: {'전부 초록' if zero_ok else '빨강이 있다'}")

caught = 0
for num, what, path, edits, want in PLANTS:
    original = path.read_bytes()
    text = original.decode("utf-8")
    counts = [text.count(old) for old, _ in edits]
    if counts != [1] * len(edits):
        print(f"[{num}] {what}: 심을 자리를 못 찾음(옛 글이 {counts} 번) — 못 잡은 것으로 센다")
        continue
    for old, new in edits:
        text = text.replace(old, new, 1)
    try:
        path.write_text(text, encoding="utf-8")
        code, out = run(CMD, LOGS / f"{num:02d}.log")
    finally:
        path.write_bytes(original)  # 손으로 되돌림
    reds = red_lines(out)
    hit = [w for w in want if any(w in line for line in reds)]
    ok = code != 0 and bool(hit)
    caught += ok
    print(f"[{num}] {what}: {'잡음' if ok else '못 잡음'} (종료 {code}, 빨간 줄 {len(reds)}, 기대한 것 {hit or want})")

end = {f: hashlib.sha256(f.read_bytes()).hexdigest() for f in files}
same = end == start
print(f"FINGERPRINT={'same' if same else 'DIFF'} ({len(files)} 파일)")
print(f"PLANTED={caught}/{len(PLANTS)}")
sys.exit(0 if zero_ok and same and caught == len(PLANTS) else 1)
PY
