#!/usr/bin/env bash
# 밴드 GC1 의 심은 파손 열넷(발주서 band-handoffs/GC1-order.md §4-7). 하나씩 심고 테스트를 돌린 뒤 원본 바이트로 되쓴다.
#
#   apps/api-py/scripts/planted-breaks-GC1.sh            전부
#   apps/api-py/scripts/planted-breaks-GC1.sh 3 12       그 번호만(0번 = 심지 않은 기준은 늘 돈다)
#
# 되쓰기는 이 스크립트가 시작 때 읽어 둔 바이트로 한다(git checkout·restore·stash 를 쓰지 않는다).
# 끝에 손댄 파일 전부의 sha256 을 시작과 견준다. 끝 줄 PLANTED=<잡은 수>/<심은 수>.
# 산출물(파손마다의 pytest 출력)은 $GC1_OUT/planted/ 아래(기본: 워크트리 곁의 GC1.out).
set -u

API_PY="$(cd "$(dirname "$0")/.." && pwd)"
ROOT="$(cd "$API_PY/../.." && pwd)"
OUT="${GC1_OUT:-$(cd "$ROOT/.." && pwd)/GC1.out}"
mkdir -p "$OUT/planted"
cd "$API_PY" || exit 2

uv run --frozen python - "$OUT/planted" "$@" <<'PY'
import copy
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
COMPARE = GW / "flows/compare_shapes.py"
ROUTES = GW / "service/apis/greenwash.py"
NORMAL = GW / "tests/data/contract-examples/compare/compare-normal.json"
IN_REVIEW = GW / "tests/data/contract-examples/review/review-in-review.json"
T = "esgapi/greenwash/tests/test_contracts_gc1.py::"
C = "esgapi/config/tests/test_api_contract.py::"
TESTS = ["esgapi/greenwash", "esgapi/config/tests/test_api_contract.py", "esgapi/core/tests/test_permissions.py"]

FILES = [COMPARE, ROUTES, NORMAL, IN_REVIEW]
original = {path: path.read_bytes() for path in FILES}
sha_before = {path: hashlib.sha256(data).hexdigest() for path, data in original.items()}


def text_edit(path: Path, old: str, new: str) -> Callable[[], None]:
    def apply() -> None:
        text = original[path].decode("utf-8")
        assert text.count(old) >= 1, f"{path}: 심을 자리 없음: {old!r}"
        path.write_text(text.replace(old, new, 1), encoding="utf-8")

    return apply


def json_edit(path: Path, change: Callable[[dict[str, Any]], dict[str, Any] | None]) -> Callable[[], None]:
    def apply() -> None:
        value = json.loads(original[path])
        changed = change(value)  # 제자리에서 바꾸거나(None) 새 값을 돌려준다
        result = value if changed is None else changed
        path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return apply


def pair_of(value: dict[str, Any], outcome: str) -> dict[str, Any]:
    return next(p for p in value["pairs"] if p["outcome"] == outcome)


def fill_target(v: dict[str, Any]) -> None:
    pair_of(v, "resolved_deleted")["target"] = copy.deepcopy(pair_of(v, "remaining")["target"])


def out_of_range(v: dict[str, Any]) -> None:
    v["marks"][-1]["item_index"] = 9


def adopted_with_reason(v: dict[str, Any]) -> None:
    next(m for m in v["marks"] if m["decision"] == "adopted")["exclude_reason"] = "사유"


def second_key(v: dict[str, Any]) -> dict[str, Any]:
    return {"base": v["base"], **{k: x for k, x in v.items() if k != "base"}}


def same_level(v: dict[str, Any]) -> None:
    pair = pair_of(v, "level_changed")
    pair["target"]["level"] = pair["base"]["level"]


def bump_count(v: dict[str, Any]) -> None:
    v["counts"]["remaining"] += 1


def one_letter(v: dict[str, Any]) -> None:
    ref = pair_of(v, "remaining")["target"]
    ref["sentence"] = ref["sentence"][:-1] + "!"


EXTRA_ROUTE = '''

@router.get("/extra", operation_id="greenwash_extra")
def extra(request: HttpRequest) -> HttpResponse:
    return _not_implemented()
'''

BREAKS: list[tuple[int, str, Callable[[], None], list[str]]] = [
    (1, "compare 꼴에서 outcome 하나를 뺌", text_edit(COMPARE, '    "out_of_scope",\n]', "]"),
     [T + "test_the_json_schema_is_pinned_byte_for_byte", T + "test_a_compare_example_fits"]),
    (2, "ItemRef 에 id 칸", text_edit(COMPARE, '    """그 실행의 결과 items 의 차례(0부터)."""\n',
                                     '    """그 실행의 결과 items 의 차례(0부터)."""\n    id: int\n'),
     [T + "test_the_json_schema_is_pinned_byte_for_byte"]),
    (3, "compare-normal 의 ItemRef 문장 한 글자", json_edit(NORMAL, one_letter),
     [T + "test_compare_refs_match_the_result_items"]),
    (4, "compare-normal 의 counts 하나 +1", json_edit(NORMAL, bump_count),
     [T + "test_compare_outcome_rules_and_counts"]),
    (5, "resolved_deleted 쌍에 target 채움", json_edit(NORMAL, fill_target),
     [T + "test_compare_outcome_rules_and_counts"]),
    (6, "review 예시 item_index 를 범위 밖으로", json_edit(IN_REVIEW, out_of_range),
     [T + "test_review_marks_point_into_result_normal"]),
    (7, "adopted 표시에 사유", json_edit(IN_REVIEW, adopted_with_reason),
     [T + "test_review_marks_point_into_result_normal"]),
    (8, "schemaVersion 을 둘째 키로", json_edit(NORMAL, second_key),
     [T + "test_a_compare_example_fits"]),
    (9, "경로 하나의 operation_id 바꿈",
     text_edit(ROUTES, 'operation_id="greenwash_compare_get"', 'operation_id="greenwash_compare_read"'),
     [C + "test_operation_ids_are_the_hand_written_table"]),
    (10, "openapi.json 을 다시 뽑지 않고 경로 하나 더함",
     lambda: ROUTES.write_text(original[ROUTES].decode("utf-8") + EXTRA_ROUTE, encoding="utf-8"),
     [C + "test_committed_openapi_matches_the_code"]),
    (11, "PUT 의 413 선언 뺌",
     text_edit(ROUTES, "**NOT_FOUND_AND_501, **BODY_ERROR_RESPONSES}", "**NOT_FOUND_AND_501, **ERROR_RESPONSES}"),
     [C + "test_an_operation_declares_413_exactly_when_it_takes_a_body"]),
    (12, "GreenwashReviewUpdate 에 user_id 칸",
     text_edit(ROUTES, "    marks: list[GreenwashReviewMark]\n",
               "    marks: list[GreenwashReviewMark]\n    user_id: int | None = None\n"),
     [T + "test_the_review_update_body_is_strict_and_has_no_tenant_or_user_field"]),
    (13, "GreenwashReviewUpdate 의 Greenwash 접두를 뺌",
     lambda: ROUTES.write_text(
         original[ROUTES].decode("utf-8").replace("GreenwashReviewUpdate", "ReviewUpdate"), encoding="utf-8"),
     [T + "test_gc1_component_names_have_the_prefix_and_result_names_do_not_collide"]),
    (14, "level_changed 쌍의 두 등급을 같게", json_edit(NORMAL, same_level),
     [T + "test_compare_outcome_rules_and_counts"]),
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
