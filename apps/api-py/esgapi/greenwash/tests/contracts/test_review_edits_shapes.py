"""그린워싱 계약 — 검토 review@3(@2 에 근거 고침·재판단을 더한 판, GRJ1)의 고침(edits, 밴드 G1b-3 ①). 순수 층(DB 없음).

본문 GreenwashReviewEditIn 이 strict(모르는 칸·snake·true/1.0/"1"·소문자 등급 거절)
응답 꼴 GreenwashReviewEdit·칸 꼴 셋이 모르는 칸을 거절하고 칸 null 을 받음
예시 넷(review-pending·in-review·confirmed·edited)이 @3 을 지나고 첫 키가 schemaVersion, edited 의 고침이 결과를 가리킴
표 상수 EDIT_LEVELS 가 계약 Level 과 같음(import 0 — 마이그레이션이 값을 문면에 굳힌다)
"""

import copy
import json
from datetime import datetime
from pathlib import Path
from typing import Any, cast, get_args

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.greenwash.contracts import review_shapes, shapes
from esgapi.greenwash.models import EDIT_LEVELS
from esgapi.greenwash.service.apis import greenwash as routes

DATA = Path(__file__).resolve().parents[1] / "data"
EXAMPLES = DATA / "contract-examples"
PINNED = DATA / "flow-shapes" / "review"
NAMES = ["review-pending.json", "review-in-review.json", "review-confirmed.json", "review-edited.json"]
STATE = review_shapes.REVIEW_SHAPES[review_shapes.SHAPE]


def load(*parts: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLES.joinpath(*parts).read_text(encoding="utf-8")))


def edit_in(**kw: object) -> dict[str, object]:
    return {"itemIndex": 1, "level": None, "reasonBullets": None, "fixParagraph": None, **kw}


def body(*edits: dict[str, object]) -> str:
    return json.dumps({"marks": [], "edits": list(edits)})


def test_the_shape_is_review_at_3_and_the_only_pinned_file() -> None:
    assert review_shapes.SHAPE == "greenwash.review@3"
    assert list(review_shapes.REVIEW_SHAPES) == ["greenwash.review@3"]  # 앞 판 읽기 없음(검토 JSON 은 저장 안 됨)
    assert [p.name for p in PINNED.iterdir()] == ["greenwash.review@3.schema.json"]


def test_the_edit_levels_are_the_contract_levels() -> None:
    assert get_args(shapes.Level) == EDIT_LEVELS


@pytest.mark.parametrize("name", NAMES)
def test_an_example_fits_review_at_3(name: str) -> None:
    value = load("review", name)
    assert next(iter(value)) == "schemaVersion"
    STATE.validate_python(value, strict=True)


def test_the_edited_example_points_into_result_normal_and_differs_from_the_ai() -> None:
    edited = load("review", "review-edited.json")
    items = load("result-normal.json")["items"]
    indexes = [edit["itemIndex"] for edit in edited["edits"]]
    assert indexes == sorted(set(indexes)) and all(0 <= i < len(items) for i in indexes)
    ai_key = {"level": "level", "reasonBullets": "reasonBullets", "fixParagraph": "fixParagraph"}
    for edit in edited["edits"]:
        values = [edit[k] for k in ai_key]
        assert any(v is not None for v in values)  # 칸 셋 중 하나 이상
        for key, field in ai_key.items():
            if edit[key] is not None:
                assert edit[key]["value"] != items[edit["itemIndex"]][field]  # AI 와 같은 값은 null 로 접힌다
                assert (
                    datetime.fromisoformat(edit[key]["editedAt"]).utcoffset()
                    == datetime.fromisoformat("2026-01-01T00:00:00+09:00").utcoffset()
                )
    # 제외한 문장도 고칠 수 있다
    excluded = {m["itemIndex"] for m in edited["marks"] if m["decision"] == "excluded"}
    assert excluded & set(indexes)
    assert [load("review", review)["edits"] for review in NAMES[:3]] == [[], [], []]


def test_the_state_rejects_unknown_or_bad_edit_keys() -> None:
    edited = load("review", "review-edited.json")
    rejected: list[dict[str, Any]] = []
    no_edits = {k: v for k, v in edited.items() if k != "edits"}
    rejected.append(no_edits)
    extra = copy.deepcopy(edited)
    extra["edits"][0]["ai"] = {}
    rejected.append(extra)
    level = copy.deepcopy(edited)
    level["edits"][0]["level"]["value"] = "high"
    rejected.append(level)
    flat = copy.deepcopy(edited)
    flat["edits"][0]["level"] = "Low"  # 응답은 {value, editedAt, editedBy}
    rejected.append(flat)
    who = copy.deepcopy(edited)
    who["edits"][1]["fixParagraph"]["editedBy"]["name"] = ""
    rejected.append(who)
    old = {**edited, "schemaVersion": "greenwash.review@1"}
    rejected.append(old)
    for value in rejected:
        with pytest.raises(ValidationError):
            STATE.validate_python(value, strict=True)


@pytest.mark.parametrize(
    "bad",
    [
        edit_in(extra=1),
        {"item_index": 1, "level": "Low", "reasonBullets": None, "fixParagraph": None},
        edit_in(itemIndex=True),
        edit_in(itemIndex=1.0),
        edit_in(itemIndex="1"),
        edit_in(itemIndex=-1),
        edit_in(level="high"),
        edit_in(level=1),
        edit_in(reasonBullets="한 줄"),
        edit_in(reasonBullets=[1]),
        edit_in(fixParagraph=["글"]),
        {"itemIndex": 1, "level": "Low"},  # 칸을 빼지 않는다(null 로 보낸다)
    ],
    ids=[
        "unknown",
        "snake",
        "true",
        "float",
        "text-index",
        "negative",
        "lowercase-level",
        "number-level",
        "text-bullets",
        "number-bullet",
        "list-fix",
        "missing-keys",
    ],
)
def test_the_edit_body_is_strict(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        routes.GreenwashReviewUpdate.model_validate_json(body(bad))


def test_the_edit_body_accepts_flat_values_and_null_or_missing_edits() -> None:
    parsed = routes.GreenwashReviewUpdate.model_validate_json(
        body(edit_in(level="Low", reasonBullets=["가", "나"], fixParagraph="고친 글"))
    )
    assert parsed.edits == [{"itemIndex": 1, "level": "Low", "reasonBullets": ["가", "나"], "fixParagraph": "고친 글"}]
    assert routes.GreenwashReviewUpdate.model_validate_json('{"marks": []}').edits is None  # 생략 = 고침 그대로
    assert routes.GreenwashReviewUpdate.model_validate_json('{"marks": [], "edits": null}').edits is None
    assert routes.GreenwashReviewUpdate.model_validate_json('{"marks": [], "edits": []}').edits == []


def test_the_edit_in_shape_is_strict_on_its_own() -> None:
    """중첩 TypedDict 에 바깥 strict 가 안 내려간다(review_shapes.py 의 STRICT_FORBID 주석) — 꼴 하나로도 잰다."""
    adapter = TypeAdapter(review_shapes.GreenwashReviewEditIn)
    with pytest.raises(ValidationError):
        adapter.validate_python(edit_in(itemIndex=True))
    adapter.validate_python(edit_in(itemIndex=2))
