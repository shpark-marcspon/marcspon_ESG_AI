"""꼴 translation.input@1·translation.result@1(contracts/shapes.py): 고정 스키마 파일과 글자까지 같고, 지은 예시가 결과
꼴에 맞으며, 결과 꼴은 모르는 키·빠진 키·갈래 섞임을 거부하고, 입력 꼴은 받은 dict 를 고치지 않는다(발주서 §3 S3).

예시(tests/data/examples/result-sample.json)는 로직보다 먼저 손으로 지은 것이다(회사·용어·글은 전부 지어낸 것).
프론트가 화면을 짓는 데 쓴다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest
from pydantic import ValidationError

from esgapi.translation.contracts import shapes

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes"
EXAMPLE = DATA / "examples" / "result-sample.json"
ALL_SHAPES = {**shapes.INPUT_SHAPES, **shapes.RESULT_SHAPES}


def pinned_text(shape: str) -> str:
    return json.dumps(ALL_SHAPES[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"


def load_example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLE.read_text(encoding="utf-8")))


def check_result(result: dict[str, Any]) -> None:
    assert next(iter(result)) == "schemaVersion"
    shapes.RESULT_SHAPES[result["schemaVersion"]].validate_python(result, strict=True)


def rejects_result(result: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)


def an_input() -> dict[str, Any]:
    return {
        "schemaVersion": "translation.input@1",
        "document": {"kind": "structuredText", "text": "[PAGE 1]\n[BLOCK 1]\n가상 제목\n가상 본문입니다."},
        "company": {
            "name": "ABC Corp",
            "preferredSubject": "virtual manufacturing, energy efficiency",
            "industryStandards": "GRI Standards 2021, ISSB (IFRS S1 and IFRS S2)",
        },
        "glossary": {
            "base": [{"ko": "가상사업장", "en": "Virtual Site"}, {"ko": "가상", "en": "Virtual"}],
            "final": [{"ko": "가상사업장", "en": "Virtual Business Site"}],
        },
        "part": "general",
        "style": {"compareAb": False, "single": "B"},
        "peerGroupStyle": None,
        "pages": {"start": None, "end": None},
        "ceoPageLimit": 6,
        "autofix": True,
    }


@pytest.mark.parametrize("shape", sorted(ALL_SHAPES))
def test_the_json_schema_is_pinned(shape: str) -> None:
    assert pinned_text(shape) == (PINNED / f"{shape}.schema.json").read_text(encoding="utf-8")


def test_every_shape_is_pinned() -> None:
    files = {p.name.removesuffix(".schema.json") for p in PINNED.glob("*.schema.json")}
    # translation.digest@1(둘째 결과 — 밴드 TR3a)은 tests/contracts/test_digest_shapes.py 가 못 박는다
    # translation.layout@1(셋째 결과 — 밴드 TRD2)은 tests/contracts/test_layout_shapes.py 가 못 박는다
    assert (
        set(ALL_SHAPES)
        == files - {"translation.digest@1", "translation.layout@1"}
        == {"translation.input@1", "translation.result@1"}
    )


def test_the_example_fits_the_result_shape() -> None:
    result = load_example()
    check_result(result)
    (variant,) = result["variants"]
    assert {f["status"] for f in variant["fragments"]} == {"translated", "error"}  # 프론트가 W7 갈래를 본다
    assert {p["review"]["status"] for p in variant["pages"]} == {"reviewed", "parse_failed"}
    assert {i["source"] for p in variant["pages"] for i in p["review"]["issues"]} == {"model", "glossary_rule"}
    assert variant["autofix"]["status"] == "done"


def test_a_missing_or_extra_key_is_rejected_by_the_result_shape() -> None:
    base = load_example()
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "unknown": 1})
    broken.append({**base, "usage": {"calls": 3}})  # 사용량은 싣지 않는다
    broken.append({**base, "schemaVersion": "translation.result@2"})
    broken.append({**base, "variants": []})  # done 은 문체가 적어도 하나
    for path in (("settings",), ("document",), ("variants", 0), ("variants", 0, "fragments", 0)):
        nested = copy.deepcopy(base)
        target: Any = nested
        for step in path:
            target = target[step]
        target["extra"] = 1
        broken.append(nested)
    no_default = copy.deepcopy(base)
    del no_default["variants"][0]["fragments"][0]["editorialQa"]["scoreDefaulted"]
    broken.append(no_default)
    bad_reason = copy.deepcopy(base)
    bad_reason["variants"][0]["fragments"][0]["editorialQa"]["reason"] = "skipped"
    broken.append(bad_reason)
    bad_source = copy.deepcopy(base)
    bad_source["variants"][0]["pages"][0]["review"]["issues"][0]["source"] = "python"
    broken.append(bad_source)
    one_dup = copy.deepcopy(base)
    one_dup["document"]["duplicatePages"] = {"3": 1}  # 합친 쪽은 두 번 이상 나온 쪽
    broken.append(one_dup)
    negative = copy.deepcopy(base)
    negative["variants"][0]["pages"][0]["review"]["counts"]["high"] = -1
    broken.append(negative)
    bad_engine = copy.deepcopy(base)
    bad_engine["settings"]["engine"] = "colab_157"
    broken.append(bad_engine)
    for result in broken:
        rejects_result(result)


def test_a_branch_cannot_mix_with_another() -> None:
    base = load_example()
    variant = base["variants"][0]
    autofix = variant["autofix"]
    stop: dict[str, Any] = {
        "kind": "remaining_korean",
        "pageNum": 3,
        "remainingKorean": ["가상"],
        "message": "가상 멈춤",
    }
    stopped: dict[str, Any] = {
        **autofix,
        "status": "stopped",
        "pages": [],
        "translatedText": None,
        "bilingualText": None,
        "stop": stop,
    }
    not_run: dict[str, Any] = {**stopped, "status": "not_run", "stop": None, "notRunReason": "disabled"}
    review_stop: dict[str, Any] = {
        "status": "call_failed",
        "issues": [],
        "counts": {"high": 0, "medium": 0, "low": 0},
        "message": "x",
    }
    rejection: dict[str, Any] = {"kind": "no_pages", "message": "가상", "pageCount": None, "limit": None}

    def with_variant(**changes: Any) -> dict[str, Any]:
        return {**base, "variants": [{**variant, **changes}]}

    def with_page_review(review: dict[str, Any]) -> dict[str, Any]:
        return with_variant(pages=[{**variant["pages"][0], "review": review}])

    mixed: list[dict[str, Any]] = [
        {**base, "rejection": rejection},  # done 에 rejection
        {**base, "status": "rejected"},  # rejected 에 rejection 없음·문체 있음
        {**base, "status": "rejected", "rejection": rejection},  # rejected 에 문체
        with_variant(autofix={**autofix, "stop": stop}),  # done 에 stop
        with_variant(autofix={**stopped, "pages": autofix["pages"]}),  # stopped 에 쪽(버린다)
        with_variant(autofix={**stopped, "translatedText": "x"}),  # stopped 에 글
        with_variant(autofix={**stopped, "stop": None}),  # stopped 에 stop 없음
        with_variant(autofix={**not_run, "notRunReason": None}),  # not_run 에 까닭 없음
        with_variant(autofix={**not_run, "notRunReason": "skipped"}),
        with_page_review({**review_stop, "issues": variant["pages"][0]["review"]["issues"]}),  # 멈춘 검수에 이슈
        with_page_review({**variant["pages"][0]["review"], "message": "x"}),  # 돈 검수에 message
        with_page_review({**review_stop, "status": "skipped"}),
    ]
    for result in mixed:
        rejects_result(result)
    check_result(with_variant(autofix=stopped))
    check_result(with_variant(autofix=not_run))
    check_result(with_page_review(review_stop))
    check_result(with_page_review({**review_stop, "status": "not_run", "message": None}))
    limit: dict[str, Any] = {"kind": "ceo_page_limit", "message": "가상", "pageCount": 7, "limit": 6}
    check_result({**base, "status": "rejected", "rejection": limit, "variants": []})


def test_schema_version_must_be_the_first_key() -> None:
    base = load_example()
    moved = {"status": base["status"], **{k: v for k, v in base.items() if k != "status"}}
    with pytest.raises(AssertionError):
        check_result(moved)


def test_check_input_returns_the_received_dict_itself() -> None:
    received = an_input()
    before = json.dumps(received, ensure_ascii=False)
    assert shapes.check_input(received) is received
    assert json.dumps(received, ensure_ascii=False) == before  # 키 차례(용어집 짝의 차례 포함)가 그대로다
    with_peer = {**received, "peerGroupStyle": {"prompt": "가상 peer 문체 글"}, "part": "ceo_message"}
    assert shapes.check_input(with_peer) is with_peer
    open_range = {**received, "pages": {"start": 2, "end": None}, "ceoPageLimit": None}
    assert shapes.check_input(open_range) is open_range


def test_the_input_shape_rejects_what_is_not_the_shape() -> None:
    base = an_input()
    broken: list[dict[str, Any]] = [{k: v for k, v in base.items() if k != key} for key in base]
    broken.append({**base, "model": "claude-sonnet-4-6"})  # 엔진 상수는 칸이 아니다(처분 ⑤)
    broken.append({**base, "document": {"kind": "docx", "text": "x"}})  # docx 갈래는 TR1b
    broken.append({**base, "glossary": {"base": {"가상": "Virtual"}, "final": []}})  # 용어집은 짝의 목록(처분 ⑥)
    broken.append({**base, "glossary": {"base": [{"ko": "가상", "en": "Virtual", "note": "x"}], "final": []}})
    broken.append({**base, "part": "appendix"})
    broken.append({**base, "style": {"compareAb": False, "single": "C"}})
    broken.append({**base, "peerGroupStyle": "가상 글"})
    broken.append({**base, "pages": {"start": "1", "end": None}})
    broken.append({**base, "ceoPageLimit": -1})
    broken.append({**base, "autofix": "true"})
    broken.append({**base, "company": {**base["company"], "homepage": "x"}})
    for received in broken:
        with pytest.raises(ValidationError):
            shapes.check_input(received)
