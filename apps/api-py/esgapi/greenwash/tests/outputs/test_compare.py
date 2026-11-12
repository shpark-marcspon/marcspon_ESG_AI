"""수정본 짝 계산 compare_runs(밴드 GR1, 발주서 band-handoffs/GR1-order.md §3 (a)~(j)). 순수 층(DB·AI·pdfium 없음).

쪽 글은 전부 지은 것이다 — 지어낸 회사 「가상전자」의 지어낸 문장(GC1 의 계약 예시와 같은 이름). 결과 항목의 꼴은
계약 예시 result-normal.json 의 항목을 본으로 쓰고 sentence·page·parts·level 만 바꾼다.
"""

import copy
import json
import subprocess
import sys
from collections import Counter
from collections.abc import Sequence
from pathlib import Path
from typing import Any, Final, cast

import pytest

from esgapi.greenwash.contracts import compare_shapes
from esgapi.greenwash.contracts.compare_shapes import GreenwashCompareResult
from esgapi.greenwash.outputs.compare import OUTCOMES, RunSide, compare_runs

EXAMPLES: Final = Path(__file__).resolve().parents[1] / "data" / "contract-examples"
API_PY: Final = Path(__file__).resolve().parents[4]

CEO, COMPANY, CLIMATE = "CEO 메시지", "회사소개", "기후/환경 토픽"
FILL: Final = "이 쪽은 가상전자의 지배구조와 이사회 운영을 설명합니다."
S1: Final = "가상전자는 2035년까지 사업장 전력을 모두 재생에너지로 바꾸겠습니다."
S2: Final = "가상전자의 포장재는 전부 친환경 소재입니다."
S3: Final = "가상전자는 지난해 물 사용량을 크게 줄였습니다."


def load(*parts: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLES.joinpath(*parts).read_text(encoding="utf-8")))


TEMPLATE: Final = load("result-normal.json")


def item(sentence: str, page: int = 1, parts: Sequence[str] = (CLIMATE,), level: str = "Mid") -> dict[str, Any]:
    out = copy.deepcopy(cast("dict[str, Any]", TEMPLATE["items"][2]))
    out.update(sentence=sentence, page=page, parts=list(parts), level=level, position=None)
    return out


def result(items: Sequence[dict[str, Any]], page_count: int, scanned: Sequence[int]) -> dict[str, Any]:
    """result-normal.json 을 본으로 items·쪽 수·점검 쪽을 바꾼 result@1(counts 는 items 를 다시 센다)."""
    out = copy.deepcopy(TEMPLATE)
    names = [p["name"] for p in out["parts"]]
    out["source"]["pageCount"] = page_count
    out["parts"] = [{"name": name, "pages": list(scanned) if name == CLIMATE else []} for name in names]
    out["pages"] = list(scanned)
    out["items"] = [copy.deepcopy(i) for i in items]
    out["candidateStats"]["failedPages"] = []
    by_level = Counter(cast("str", i["level"]) for i in items)
    out["counts"] = {
        "total": len(items),
        "byLevel": {lv: by_level[lv] for lv in ("High", "Mid", "Low")},
        "byPart": {
            name: {
                lv: sum(1 for i in items if name in i["parts"] and i["level"] == lv) for lv in ("High", "Mid", "Low")
            }
            for name in names
        },
    }
    return out


def run(
    items: Sequence[dict[str, Any]],
    pages: Sequence[str],
    scanned: Sequence[int] | None = None,
    *,
    adopted: frozenset[int] | None = None,
    run_id: int = 1,
) -> RunSide:
    """작은 사례의 한 판. 점검 쪽은 주지 않으면 쪽 전부."""
    seen = list(range(1, len(pages) + 1)) if scanned is None else scanned
    side: compare_shapes.GreenwashCompareSide = {
        "documentId": run_id,
        "runId": run_id,
        "versionLabel": f"v{run_id}",
        "unconfirmed": adopted is None,
    }
    return RunSide(side=side, result=result(items, len(pages), seen), page_texts=list(pages), adopted=adopted)


def checked(out: GreenwashCompareResult) -> GreenwashCompareResult:
    """(j) 모든 출력: 첫 키, strict 검사, counts = pairs 를 다시 센 값(일곱 키, 0 포함)."""
    assert next(iter(out)) == "schemaVersion"
    compare_shapes.COMPARE_SHAPES[compare_shapes.SHAPE].validate_python(out, strict=True)
    recount = Counter(p["outcome"] for p in out["pairs"])
    assert dict(out["counts"]) == {o: recount[o] for o in OUTCOMES}
    return out


def outcomes(out: GreenwashCompareResult) -> list[tuple[str, int | None, int | None]]:
    """짝마다 (분류, base item_index, target item_index)."""
    return [
        (
            p["outcome"],
            p["base"]["itemIndex"] if p["base"] else None,
            p["target"]["itemIndex"] if p["target"] else None,
        )
        for p in checked(out)["pairs"]
    ]


def refs_match(out: GreenwashCompareResult, base: RunSide, target: RunSide) -> GreenwashCompareResult:
    """ItemRef 는 결과 항목의 sentence·level·parts·page 를 그대로(꼬리 「 ...」 포함) 옮긴다. side 는 복사한다."""
    fields = ("sentence", "level", "parts", "page")
    for pair in out["pairs"]:
        for ref, run_side in ((pair["base"], base), (pair["target"], target)):
            if ref is not None:
                source = run_side.result["items"][ref["itemIndex"]]
                assert {k: source[k] for k in fields} == {k: ref[k] for k in fields}
                assert ref["parts"] is not source["parts"]
    assert out["base"] == base.side and out["base"] is not base.side
    assert out["target"] == target.side and out["target"] is not target.side
    return out


def one(base: RunSide, target: RunSide) -> list[tuple[str, int | None, int | None]]:
    return outcomes(refs_match(compare_runs(base, target), base, target))


# ── (a) 계약 예시 재현 ──────────────────────────────────────────────────────────────

BASE_ITEMS: Final = load("compare", "compare-normal.base-result.json")["items"]
TARGET_ITEMS: Final = TEMPLATE["items"]


def sentence_of(items: Any, index: int) -> str:
    return cast("str", items[index]["sentence"])


def example_pages() -> tuple[list[str], list[str]]:
    """예시가 정한 분류에 맞춘 합성 쪽 글(base 8쪽·target 8쪽). base 2 는 base 3쪽에만, base 3 은 target 점검 쪽
    (3쪽)에, base 4 는 어디에도 없음, base 5 는 target 7쪽(점검 밖)에만, target 2 는 base 4쪽(점검 밖)에만,
    target 3 은 base 글에 없음."""
    b, t = BASE_ITEMS, TARGET_ITEMS
    base = [FILL] * 8
    base[1] = sentence_of(b, 0) + "\n" + sentence_of(b, 1)
    base[2] = sentence_of(b, 2) + " " + sentence_of(b, 3)
    base[3] = "공장 소개.\n" + sentence_of(t, 2)
    base[6] = sentence_of(b, 5)
    target = [FILL] * 8
    target[1] = sentence_of(t, 0) + "\n" + sentence_of(t, 1)
    target[2] = "물류 현황.\n" + sentence_of(b, 3)
    target[3] = sentence_of(t, 2)
    target[4] = sentence_of(t, 3)
    target[6] = sentence_of(b, 5)
    return base, target


def side_of(example: dict[str, Any], which: str) -> compare_shapes.GreenwashCompareSide:
    return cast("compare_shapes.GreenwashCompareSide", dict(example[which]))


def review_adopted() -> frozenset[int]:
    marks = load("review", "review-confirmed.json")["marks"]
    return frozenset(m["itemIndex"] for m in marks if m["decision"] == "adopted")


@pytest.mark.parametrize("name", ["compare-normal.json", "compare-unconfirmed.json"])
def test_the_contract_examples_are_reproduced(name: str) -> None:
    example = load("compare", name)
    base_pages, target_pages = example_pages()
    base_result = load("compare", "compare-normal.base-result.json")
    target_side = side_of(example, "target")
    base = RunSide(side_of(example, "base"), base_result, base_pages, frozenset(range(len(base_result["items"]))))
    target_adopted = None if target_side["unconfirmed"] else review_adopted()
    target = RunSide(target_side, load("result-normal.json"), target_pages, target_adopted)
    out = refs_match(checked(compare_runs(base, target)), base, target)
    assert out == example
    assert json.dumps(out, ensure_ascii=False) == json.dumps(example, ensure_ascii=False)  # 키·짝 차례까지


def emptied(value: dict[str, Any]) -> dict[str, Any]:
    out = copy.deepcopy(value)
    out["items"] = []
    zero = {"High": 0, "Mid": 0, "Low": 0}
    out["counts"] = {"total": 0, "byLevel": dict(zero), "byPart": {p["name"]: dict(zero) for p in out["parts"]}}
    return out


def test_compare_empty_is_reproduced() -> None:
    example = load("compare", "compare-empty.json")
    base = RunSide(
        side_of(example, "base"), emptied(load("compare", "compare-normal.base-result.json")), [FILL] * 8, frozenset()
    )
    target = RunSide(side_of(example, "target"), emptied(load("result-normal.json")), [FILL] * 8, frozenset())
    assert checked(compare_runs(base, target)) == example


# ── (b) 분류 일곱 ──────────────────────────────────────────────────────────────────


def test_remaining() -> None:
    assert one(run([item(S1, level="High")], [S1]), run([item(S1, level="High")], [S1], run_id=2)) == [
        ("remaining", 0, 0)
    ]


def test_level_changed() -> None:
    assert one(run([item(S1, level="High")], [S1]), run([item(S1, level="Mid")], [S1], run_id=2)) == [
        ("level_changed", 0, 0)
    ]


def test_resolved_deleted() -> None:
    assert one(run([item(S2)], [S2]), run([], [FILL], run_id=2)) == [("resolved_deleted", 0, None)]


def test_resolved_not_flagged() -> None:
    assert one(run([item(S2)], [S2]), run([], [S2], run_id=2)) == [("resolved_not_flagged", 0, None)]


def test_resolved_undetermined() -> None:
    """AI 문장이 base 글에도 없다(원문과 달라 가를 수 없음)."""
    assert one(run([item(S2)], [FILL]), run([], [FILL], run_id=2)) == [("resolved_undetermined", 0, None)]


def test_new() -> None:
    assert one(run([], [FILL]), run([item(S3)], [S3], run_id=2)) == [("new", None, 0)]


def test_new_when_the_base_had_it_on_a_scanned_page() -> None:
    assert one(run([], [S3]), run([item(S3)], [S3], run_id=2)) == [("new", None, 0)]


def test_out_of_scope_on_the_base_side() -> None:
    """base 에만 있는 문장이 target 글의 점검 쪽 밖(2쪽)에만 있다."""
    assert one(run([item(S2)], [S2, FILL]), run([], [FILL, S2], [1], run_id=2)) == [("out_of_scope", 0, None)]


def test_out_of_scope_on_the_target_side() -> None:
    """target 에만 있는 문장이 base 글의 점검 쪽 밖(2쪽)에만 있다."""
    assert one(run([], [FILL, S3], [1]), run([item(S3)], [S3, FILL], run_id=2)) == [("out_of_scope", None, 0)]


# ── (c) 확정본 거르기 ────────────────────────────────────────────────────────────────


def test_a_confirmed_side_compares_only_its_adopted_sentences() -> None:
    target = run([item(S1), item(S2)], [S1 + S2], adopted=frozenset({0}), run_id=2)
    assert one(run([item(S1)], [S1 + S2]), target) == [("remaining", 0, 0)]


def test_a_sentence_the_confirmed_base_excluded_is_new_when_the_unconfirmed_target_flags_it() -> None:
    """머리말 ★ 비대칭: base 확정본이 제외한 문장이 target(미확정)에 그대로 걸리면 짝이 없어 new 다."""
    base = run([item(S1), item(S2)], [S1 + S2], adopted=frozenset({0}))
    target = run([item(S1), item(S2)], [S1 + S2], run_id=2)
    assert one(base, target) == [("remaining", 0, 0), ("new", None, 1)]


# ── (d) 같은 열쇠 여럿 ───────────────────────────────────────────────────────────────


def test_the_same_key_twice_pairs_in_item_order_and_the_rest_is_one_sided() -> None:
    base = run([item(S1, page=1), item(S1, page=2)], [S1, S1])
    target = run([item(S1, page=1)], [S1, FILL], run_id=2)
    assert one(base, target) == [("remaining", 0, 0), ("resolved_not_flagged", 1, None)]


def test_the_same_key_on_both_sides_pairs_first_with_first() -> None:
    """같은 열쇠가 양쪽에 둘씩: item_index 차례로 첫째끼리, 둘째끼리(등급이 엇갈려 차례가 결과를 바꾼다)."""
    base = run([item(S1, level="High"), item(S1, level="Mid")], [S1])
    target = run([item(S1, level="Mid"), item(S1, level="High")], [S1], run_id=2)
    assert one(base, target) == [("level_changed", 0, 0), ("level_changed", 1, 1)]


# ── (e) 쪽이 밀린 판, 파트 ───────────────────────────────────────────────────────────


def test_the_same_sentence_on_a_shifted_page_is_a_pair() -> None:
    base = run([item(S1, page=3, parts=[COMPANY])], [FILL, FILL, S1, FILL, FILL])
    target = run([item(S1, page=5, parts=[COMPANY])], [FILL, FILL, FILL, FILL, S1], run_id=2)
    assert one(base, target) == [("remaining", 0, 0)]


def test_the_same_sentence_with_other_parts_is_not_a_pair() -> None:
    """열쇠에 parts 가 든다(감독이 정할 물음 — 지금 규칙의 결과를 적어 둔다): base 쪽은 target 점검 쪽 글에 있어
    not_flagged, target 쪽은 base 점검 쪽 글에 있어 new 로 둘이 된다."""
    base = run([item(S1, parts=[COMPANY])], [S1])
    target = run([item(S1, parts=[COMPANY, CLIMATE])], [S1], run_id=2)
    assert one(base, target) == [("resolved_not_flagged", 0, None), ("new", None, 0)]


# ── (f) 정규화 ───────────────────────────────────────────────────────────────────


def test_spacing_width_case_quotes_dashes_and_the_tail_are_the_same_key() -> None:
    plain = "가상전자는 'Net-Zero' 목표를 세웠습니다."
    varied = "가상전자는　“ＮＥＴ–zero”  목표를\n세웠습니다. ..."
    assert one(run([item(plain)], [plain]), run([item(varied)], [varied], run_id=2)) == [("remaining", 0, 0)]


def test_a_truncated_sentence_is_found_in_the_page_text() -> None:
    """노트북이 자른 문장(꼬리 「 ...」)은 꼬리를 떼고 찾는다. 쪽 글의 줄바꿈·띄어쓰기 차이도 찾는다."""
    cut = "가상전자의 포장재는 전부 ..."
    assert one(run([item(cut)], [S2]), run([], ["가상전자의\n포장재는  전부 친환경 소재입니다."], run_id=2)) == [
        ("resolved_not_flagged", 0, None)
    ]


def test_a_missing_period_and_a_middle_dot_for_a_comma_are_the_same_key_only_at_tier_two() -> None:
    base_s = "가상전자는 재생에너지·수소 설비를 늘렸습니다."
    target_s = "가상전자는 재생에너지, 수소 설비를 늘렸습니다"
    assert one(run([item(base_s)], [base_s]), run([item(target_s)], [target_s], run_id=2)) == [("remaining", 0, 0)]


# ── (g) 여러 쪽에서 찾음 ─────────────────────────────────────────────────────────────


def test_found_on_several_target_pages_one_of_them_scanned_is_not_flagged() -> None:
    target = run([], [FILL, S2, FILL, S2], [1, 2], run_id=2)
    assert one(run([item(S2)], [S2]), target) == [("resolved_not_flagged", 0, None)]


def test_found_on_several_base_pages_one_of_them_scanned_is_new() -> None:
    base = run([], [S3, FILL, S3], [1, 2])
    assert one(base, run([item(S3)], [S3], run_id=2)) == [("new", None, 0)]


# ── (h) 입력 검사, 빈 정규화 문장 ──────────────────────────────────────────────────────


def dry_run_side() -> RunSide:
    value = load("result-dry-run.json")
    side: compare_shapes.GreenwashCompareSide = {
        "documentId": 1,
        "runId": 1,
        "versionLabel": "v1",
        "unconfirmed": True,
    }
    return RunSide(side, value, [FILL] * value["source"]["pageCount"], None)


def loose_page_side() -> RunSide:
    """strict 가 아니면 「1」을 1 로 받아 줄 값."""
    good = run([item(S1)], [S1])
    value = copy.deepcopy(dict(good.result))
    value["items"][0]["page"] = "1"
    return RunSide(good.side, value, good.page_texts, good.adopted)


def unknown_key_side() -> RunSide:
    good = run([item(S1)], [S1])
    return RunSide(good.side, {**good.result, "surprise": 1}, good.page_texts, good.adopted)


@pytest.mark.parametrize(
    ("make", "match"),
    [
        (dry_run_side, "dry-run"),
        (lambda: RunSide(run([item(S1)], [S1]).side, run([item(S1)], [S1]).result, [S1, FILL], None), "쪽 글 수"),
        (
            lambda: RunSide(
                {**run([item(S1)], [S1]).side, "unconfirmed": True}, run([item(S1)], [S1]).result, [S1], frozenset({0})
            ),
            "어긋난다",
        ),
        (
            lambda: RunSide(
                {**run([item(S1)], [S1]).side, "unconfirmed": False}, run([item(S1)], [S1]).result, [S1], None
            ),
            "어긋난다",
        ),
        (lambda: run([item(S1)], [S1], adopted=frozenset({1})), "범위"),
        (lambda: run([item(S1)], [S1], adopted=frozenset({-1})), "범위"),
        (unknown_key_side, "꼴이 아니다"),
        (loose_page_side, "꼴이 아니다"),
    ],
    ids=[
        "dry-run",
        "page-count",
        "unconfirmed-with-adopted",
        "confirmed-without-adopted",
        "adopted-over",
        "adopted-under",
        "strict",
        "strict-coercion",
    ],
)
def test_bad_inputs_raise(make: Any, match: str) -> None:
    good = run([item(S1)], [S1], run_id=2)
    bad = cast("RunSide", make())
    with pytest.raises(ValueError, match=match):
        compare_runs(bad, good)
    with pytest.raises(ValueError, match=match):
        compare_runs(good, bad)


def test_an_empty_normalized_sentence_is_not_an_error() -> None:
    """정규화하면 빈 글인 문장: 짝짓지 않고 다른 판 글에서 찾지 않는다 — base 에만이면 undetermined, target 에만이면
    new. 양쪽에 있어도 짝이 아니다."""
    dots = "..."
    assert one(run([item(dots)], [S1]), run([], [S1], run_id=2)) == [("resolved_undetermined", 0, None)]
    assert one(run([], [S1]), run([item(dots)], [S1], run_id=2)) == [("new", None, 0)]
    assert one(run([item(dots)], [S1]), run([item(dots)], [S1], run_id=2)) == [
        ("resolved_undetermined", 0, None),
        ("new", None, 0),
    ]
    # base 의 점검 쪽이 비어도(어느 쪽 글도 점검 밖) 빈 글은 찾지 않으므로 out_of_scope 가 아니라 new 다
    assert one(run([], [S1], []), run([item(dots)], [S1], run_id=2)) == [("new", None, 0)]


# ── (i) 순수 ─────────────────────────────────────────────────────────────────────


def test_importing_compare_pulls_in_no_pdfium_django_or_ninja() -> None:
    code = (
        "import sys, esgapi.greenwash.outputs.compare\n"
        "names = ('pypdfium2', 'django', 'ninja', 'esgapi.greenwash.tools.pdfium_locate')\n"
        "print(sorted(m for m in names if m in sys.modules))"
    )
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True, cwd=API_PY)
    assert done.stdout.strip() == "[]"


def test_the_inputs_are_not_changed_and_the_output_is_the_same_twice() -> None:
    base_pages, target_pages = example_pages()
    base = RunSide(
        side_of(load("compare", "compare-normal.json"), "base"),
        load("compare", "compare-normal.base-result.json"),
        base_pages,
        frozenset(range(6)),
    )
    target = RunSide(
        side_of(load("compare", "compare-normal.json"), "target"),
        load("result-normal.json"),
        target_pages,
        review_adopted(),
    )
    before = copy.deepcopy((base, target))
    first, second = compare_runs(base, target), compare_runs(base, target)
    assert first == second
    assert (base, target) == before
    ref = first["pairs"][0]["base"]
    assert ref is not None
    ref["parts"].append("바뀜")  # 출력은 입력과 목록을 나누지 않는다
    assert (base, target) == before
