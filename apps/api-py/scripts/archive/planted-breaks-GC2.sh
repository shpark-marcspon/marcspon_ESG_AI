#!/usr/bin/env bash
# 밴드 GC2 의 심은 파손 열하나(발주서 band-handoffs/GC2-order.md §3). 하나씩 심고 테스트를 돌린 뒤 원본 바이트로 되쓴다.
#
#   apps/api-py/scripts/planted-breaks-GC2.sh            전부
#   apps/api-py/scripts/planted-breaks-GC2.sh 3 9        그 번호만(0번 = 심지 않은 기준은 늘 돈다)
#
# 되쓰기는 이 스크립트가 시작 때 읽어 둔 바이트로 한다(git checkout·restore·stash 를 쓰지 않는다).
# 끝에 손댄 파일 전부의 sha256 을 시작과 견준다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물(파손마다의 pytest 출력)은 $GC2_OUT/planted/ 아래(기본: 워크트리 곁의 GC2.out).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
OUT="${GC2_OUT:-$(cd "$ROOT/.." && pwd)/GC2.out}"
mkdir -p "$OUT/planted"
cd "$API_PY" || exit 2

uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

out = Path(sys.argv[1])
only = {int(a) for a in sys.argv[2:]}

GW = Path("esgapi/greenwash")
REVIEW = GW / "flows/review_shapes.py"
RESULT = GW / "flows/shapes.py"
TERMS_SHAPE = GW / "flows/terms_shapes.py"
ROUTES = GW / "service/apis/greenwash.py"
CONFIRMED = GW / "tests/data/contract-examples/review/review-confirmed.json"
PERMISSIONS = Path("esgapi/core/permissions.py")
T = "esgapi/greenwash/tests/test_contracts_gc2.py::"
S = "esgapi/greenwash/tests/flows/test_shapes.py::"
P = "esgapi/core/tests/test_permissions.py::"
TESTS = ["esgapi/greenwash", "esgapi/config/tests/test_api_contract.py", "esgapi/core/tests/test_permissions.py"]

FILES = [REVIEW, RESULT, TERMS_SHAPE, ROUTES, CONFIRMED, PERMISSIONS]
original = {path: path.read_bytes() for path in FILES}
sha_before = {path: hashlib.sha256(data).hexdigest() for path, data in original.items()}


def text_edit(path: Path, old: str, new: str) -> Callable[[], None]:
    def apply() -> None:
        text = original[path].decode("utf-8")
        assert text.count(old) == 1, f"{path}: 심을 자리가 하나가 아님: {old!r}"
        path.write_text(text.replace(old, new), encoding="utf-8")

    return apply


def text_edits(path: Path, pairs: list[tuple[str, str]]) -> Callable[[], None]:
    def apply() -> None:
        text = original[path].decode("utf-8")
        for old, new in pairs:
            assert text.count(old) >= 1, f"{path}: 심을 자리 없음: {old!r}"
            text = text.replace(old, new)
        path.write_text(text, encoding="utf-8")

    return apply


def json_edit(path: Path, change: Callable[[dict[str, Any]], None]) -> Callable[[], None]:
    def apply() -> None:
        value = json.loads(original[path])
        change(value)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return apply


def nobody(v: dict[str, Any]) -> None:
    v["confirmed_by"] = None


BREAKS: list[tuple[int, str, Callable[[], None], list[str]]] = [
    (1, "review@1 에서 confirmed_by 칸을 뺌",
     text_edit(REVIEW, "    confirmed_by: GreenwashReviewer | None\n", ""),
     [T + "test_confirmed_by_comes_right_after_confirmed_at_and_takes_null",
      T + "test_the_review_schema_is_pinned_with_confirmed_by"]),
    (2, "PUT 본문 state 를 세 상태로 되돌림",
     text_edit(ROUTES, '    state: Literal["confirmed"] | None = None\n',
               '    state: Literal["pending", "in_review", "confirmed"] | None = None\n'),
     [T + "test_the_body_refuses_any_other_state", T + "test_openapi_says_the_body_state_is_the_const_confirmed"]),
    (3, "기본 단어에서 마지막 낱말 하나를 뺌",
     text_edit(ROUTES, 'return {"terms": list(GREEN_TERMS)}', 'return {"terms": list(GREEN_TERMS)[:-1]}'),
     [T + "test_the_default_terms_are_green_terms_in_order"]),
    (4, "기본 단어를 정렬해서 냄",
     text_edit(ROUTES, 'return {"terms": list(GREEN_TERMS)}', 'return {"terms": sorted(GREEN_TERMS)}'),
     [T + "test_the_default_terms_are_green_terms_in_order"]),
    (5, "report 의 compareBase 를 snake 로",
     text_edit(ROUTES, "    compareBase: int | None = Query(", "    compare_base: int | None = Query("),
     [T + "test_the_report_route_is_declared"]),
    (6, "report 200 의 content type 을 octet-stream 으로",
     text_edit(ROUTES, '"content": {XLSX: {', '"content": {"application/octet-stream": {'),
     [T + "test_the_report_route_is_declared"]),
    (7, "report 의 권한 문장을 뺌",
     text_edit(ROUTES, '    permitted_session(request, "greenwash_report_get")\n', ""),
     [T + "test_the_routes_read_their_own_cell"]),
    (8, "새 꼴 이름에서 Greenwash 접두를 뺌(GreenwashDefaultTerms → DefaultTerms)",
     lambda: (text_edits(TERMS_SHAPE, [("GreenwashDefaultTerms", "DefaultTerms")])(),
              text_edits(ROUTES, [("GreenwashDefaultTerms", "DefaultTerms")])()),
     [T + "test_the_new_component_names_have_the_prefix_and_stay_in_greenwash"]),
    (9, "result@1 에 칸 하나를 더함",
     text_edit(RESULT, '    """판정 문장. 쪽 차례, 쪽 안에서는 노트북이 낸 차례. 실행마다',
               '    extra_note: str\n    """판정 문장. 쪽 차례, 쪽 안에서는 노트북이 낸 차례. 실행마다'),
     [S + "test_the_json_schema_is_pinned", T + "test_the_result_schema_is_pinned_and_says_the_key_is_fixed"]),
    (10, "review-confirmed.json 의 confirmed_by 를 null 로", json_edit(CONFIRMED, nobody),
     [T + "test_only_the_confirmed_example_names_who_confirmed"]),
    (11, "권한 표에서 terms 를 뺌",
     text_edit(PERMISSIONS, '    "greenwash_terms_default": CUSTOMER,\n', ""),
     [P + "test_every_authenticated_operation_is_in_the_table", T + "test_the_routes_read_their_own_cell"]),
]


def restore() -> None:
    for path, data in original.items():
        path.write_bytes(data)


def run(tag: str) -> tuple[int, str]:
    proc = subprocess.run(
        ["uv", "run", "--frozen", "pytest", "-q", "-p", "no:cacheprovider", "-rf", *TESTS],
        capture_output=True, text=True, check=False,
    )
    (out / f"{tag}.log").write_text(proc.stdout + proc.stderr, encoding="utf-8")
    return proc.returncode, proc.stdout


def failed(stdout: str, test: str) -> bool:
    return any(line.startswith("FAILED " + test) for line in stdout.splitlines())


code, stdout = run("break-00")
base_ok = code == 0
print(f"[0] 심지 않음: {'초록' if base_ok else '빨강'} EXIT={0 if base_ok else 1}  ({stdout.strip().splitlines()[-1]})")

caught = planted = 0
try:
    for number, name, plant, expected in BREAKS:
        if only and number not in only:
            continue
        planted += 1
        try:
            plant()
            code, stdout = run(f"break-{number:02d}")
        finally:
            restore()
        hit = code != 0 and all(failed(stdout, test) for test in expected)
        caught += hit
        red = sorted({line.split("::")[-1].split(" ")[0] for line in stdout.splitlines() if line.startswith("FAILED ")})
        print(f"[{number}] {name}: {'잡음' if hit else '못 잡음'} EXIT={0 if hit else 1}")
        print(f"     기대: {', '.join(t.split('::')[-1] for t in expected)}")
        print(f"     빨간 것: {', '.join(red) if red else '없음'}")
finally:
    restore()

sha_after = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in FILES}
same = sha_after == sha_before
for path in FILES:
    print(f"     sha256 {sha_before[path][:16]}… → {sha_after[path][:16]}… {path}")
print(f"원본 바이트 그대로: {'예' if same else '아니오'} EXIT={0 if same else 1}")
print(f"PLANTED={caught}/{planted}")
sys.exit(0 if base_ok and same and caught == planted else 1)
PY
