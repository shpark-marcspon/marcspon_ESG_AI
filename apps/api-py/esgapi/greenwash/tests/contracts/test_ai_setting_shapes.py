# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
# pyright: reportUnknownLambdaType=false
"""AI 설정 판 꼴 셋(contracts/ai_setting_shapes.py — 밴드 G2c2)과 기준표 꼴의 받기 수 표기(Q7). 순수 층.

    고정 스키마 셋이 바이트까지 같고, 예시 넷이 strict 로 지나며, 모르는 칸·틀린 값은 거절되고, 새 클래스 이름이
    `GreenwashAiSetting` 으로 시작해 다른 꼴과 겹치지 않는다.
    Q7(§3-1-5): criteria@1 스키마의 표기 수가 받기 상수와 같고, 경계 앞뒤 입력의 받기 결과·거절 code 가 표기 전과 같다.

예시의 이름·글·메모는 지은 것이다.
"""

import copy
import json
from pathlib import Path
from typing import Any, cast, is_typeddict

import pytest
from pydantic import TypeAdapter, ValidationError

from esgapi.greenwash.contracts import (
    ai_setting_shapes,
    checks_shapes,
    compare_shapes,
    criteria_shapes,
    options_shapes,
    review_shapes,
    shapes,
    terms_shapes,
)
from esgapi.greenwash.flows import colab_e0, criteria_e0
from esgapi.greenwash.flows.criteria_e0 import CriteriaRejected, accept_criteria, default_criteria

DATA = Path(__file__).resolve().parents[1] / "data"
PINNED = DATA / "flow-shapes" / "ai-setting"
EXAMPLES = DATA / "contract-examples" / "ai-setting"
ADAPTERS: dict[str, TypeAdapter[Any]] = {
    ai_setting_shapes.LIST_SHAPE: ai_setting_shapes.LIST_SHAPES[ai_setting_shapes.LIST_SHAPE],
    ai_setting_shapes.SETTING_SHAPE: ai_setting_shapes.SETTING_SHAPES[ai_setting_shapes.SETTING_SHAPE],
    ai_setting_shapes.DEFAULT_SHAPE: ai_setting_shapes.DEFAULT_SHAPES[ai_setting_shapes.DEFAULT_SHAPE],
}
EXAMPLE_SHAPES = {
    "ai-setting-default.json": ai_setting_shapes.DEFAULT_SHAPE,
    "ai-setting.json": ai_setting_shapes.SETTING_SHAPE,
    "ai-settings-empty.json": ai_setting_shapes.LIST_SHAPE,
    "ai-settings-saved.json": ai_setting_shapes.LIST_SHAPE,
}


def load(name: str) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / name).read_text(encoding="utf-8")))


@pytest.mark.parametrize("shape", sorted(ADAPTERS))
def test_the_json_schema_is_pinned_byte_for_byte(shape: str) -> None:
    pinned = PINNED / f"{shape}.schema.json"
    text = json.dumps(ADAPTERS[shape].json_schema(), ensure_ascii=False, indent=2) + "\n"
    assert pinned.read_bytes() == text.encode("utf-8")
    schema = json.loads(text)
    assert schema["required"][0] == "schemaVersion"
    assert schema["additionalProperties"] is False
    assert all(d.get("additionalProperties") is False for d in schema["$defs"].values() if d.get("type") == "object")


def test_the_pinned_files_are_the_three() -> None:
    assert sorted(p.name for p in PINNED.iterdir()) == sorted(f"{shape}.schema.json" for shape in ADAPTERS)


def test_the_examples_are_the_four() -> None:
    assert sorted(p.name for p in EXAMPLES.iterdir()) == sorted(EXAMPLE_SHAPES)


@pytest.mark.parametrize("name", sorted(EXAMPLE_SHAPES))
def test_an_example_fits_its_shape(name: str) -> None:
    body = load(name)
    assert body["schemaVersion"] == EXAMPLE_SHAPES[name]
    ADAPTERS[EXAMPLE_SHAPES[name]].validate_python(body, strict=True)


def test_the_examples_carry_real_shas_and_names() -> None:
    """예시의 sha 는 그 기준표로 지은 값이고 판 이름은 criteria.version 과 같다(웹이 예시를 믿고 짓는다)."""
    default = load("ai-setting-default.json")
    assert default["criteria"] == default_criteria()
    assert default["evalPromptSha256"] == colab_e0.run_versions(None)["evalPromptSha256"]
    one = load("ai-setting.json")
    assert one["criteria"]["version"] == one["name"]
    assert one["evalPromptSha256"] == colab_e0.run_versions(one["criteria"])["evalPromptSha256"]
    saved = load("ai-settings-saved.json")
    assert saved["applied"] == {"kind": "saved", "id": one["id"]}
    assert [item["status"] for item in saved["items"]] == ["applied", "past"]
    assert saved["default"] == {
        "name": default["name"],
        "title": default["title"],
        "evalPromptSha256": default["evalPromptSha256"],
    }
    # @2(AS3a-2): 기본 판·목록 default 의 이름은 서버 글 DEFAULT_TITLE, 저장 판은 받은 이름(옛 판 null)
    assert default["title"] == ai_setting_shapes.DEFAULT_TITLE == "기본 설정"
    assert [item["title"] for item in saved["items"]] == [one["title"], None]


def _broken(name: str, path: tuple[str | int, ...], value: object) -> dict[str, Any]:
    body = copy.deepcopy(load(name))
    target: Any = body
    for key in path[:-1]:
        target = target[key]
    if value is KeyError:
        del target[path[-1]]
    else:
        target[path[-1]] = value
    return body


@pytest.mark.parametrize(
    ("name", "path", "value"),
    [
        pytest.param("ai-settings-saved.json", ("extra",), 1, id="list-unknown-key"),
        pytest.param("ai-settings-saved.json", ("applied", "kind"), "none", id="applied-kind"),
        pytest.param("ai-settings-saved.json", ("applied", "id"), KeyError, id="saved-without-id"),
        pytest.param("ai-settings-empty.json", ("applied", "id"), 3, id="default-with-id"),
        pytest.param("ai-settings-saved.json", ("items", 0, "status"), "draft", id="status"),
        pytest.param("ai-settings-saved.json", ("items", 0, "id"), "12", id="id-text"),
        pytest.param("ai-settings-saved.json", ("total",), -1, id="total-negative"),
        pytest.param("ai-setting.json", ("criteria", "rows", 0, "extra"), 1, id="criteria-unknown-key"),
        pytest.param("ai-setting.json", ("createdBy", "id"), KeyError, id="author-without-id"),
        pytest.param("ai-setting-default.json", ("schemaVersion",), "greenwash.ai-setting@1", id="default-shape"),
        pytest.param("ai-setting-default.json", ("schemaVersion",), "greenwash.ai-setting-default@1", id="default-v1"),
        pytest.param("ai-setting-default.json", ("title",), None, id="default-title-null"),
        pytest.param("ai-setting.json", ("title",), KeyError, id="setting-without-title"),
        pytest.param("ai-setting.json", ("title",), 3, id="setting-title-number"),
        pytest.param("ai-settings-saved.json", ("items", 0, "title"), KeyError, id="summary-without-title"),
        pytest.param("ai-settings-saved.json", ("default", "title"), KeyError, id="list-default-without-title"),
    ],
)
def test_a_broken_body_is_refused(name: str, path: tuple[str | int, ...], value: object) -> None:
    with pytest.raises(ValidationError):
        ADAPTERS[EXAMPLE_SHAPES[name]].validate_python(_broken(name, path, value), strict=True)


def test_the_memo_bound_is_the_table_column() -> None:
    """저장 본문의 메모 상한(계약)이 표의 칸(varchar(200))과 같다 — 201자가 DB 의 DataError 가 아니라 422 로 끝난다."""
    from esgapi.greenwash.models import AI_SETTING_MEMO_MAX_CHARS, GreenwashAiSettingRow

    assert ai_setting_shapes.MEMO_MAX_CHARS == AI_SETTING_MEMO_MAX_CHARS == 200
    assert GreenwashAiSettingRow._meta.get_field("memo").max_length == AI_SETTING_MEMO_MAX_CHARS


def test_the_title_and_prompt_bounds_are_the_table_constants() -> None:
    """판 이름 상한(본문 꼴)과 프롬프트 글 크기 상한(core 받기)이 표의 칸·CHECK 상수와 같다(AS3a-2 — 받기가 먼저 막아
    CHECK 가 500 으로 끝나지 않는다)."""
    from esgapi.core.contracts.ai_setting_shapes import PROMPTS_MAX_OCTETS
    from esgapi.greenwash.models import (
        AI_SETTING_PROMPTS_MAX_OCTETS,
        AI_SETTING_TITLE_MAX_CHARS,
        GreenwashAiSettingRow,
    )

    assert ai_setting_shapes.TITLE_MAX_CHARS == AI_SETTING_TITLE_MAX_CHARS == 40
    assert GreenwashAiSettingRow._meta.get_field("title").max_length == AI_SETTING_TITLE_MAX_CHARS
    assert PROMPTS_MAX_OCTETS == AI_SETTING_PROMPTS_MAX_OCTETS


def test_the_class_names_are_new_and_prefixed() -> None:
    found = {n for n, v in vars(ai_setting_shapes).items() if isinstance(v, type) and is_typeddict(v)}
    mine = found - {"GreenwashCriteria", "GreenwashTerm"}  # 들인 기준표 꼴·판 단어 꼴(G2d — terms_shapes)
    assert mine and all(n.startswith("GreenwashAiSetting") for n in mine), mine
    others = (shapes, review_shapes, compare_shapes, criteria_shapes, terms_shapes, checks_shapes, options_shapes)
    taken = {n for module in others for n, v in vars(module).items() if isinstance(v, type) and is_typeddict(v)}
    assert not mine & taken


# ── Q7 표기(§3-1-5) ──


def _criteria_schema() -> dict[str, Any]:
    return criteria_shapes.CRITERIA_SHAPES[criteria_shapes.SHAPE].json_schema()


def test_the_marked_counts_are_the_acceptance_constants() -> None:
    schema = _criteria_schema()
    row = schema["$defs"]["GreenwashCriterionRow"]["properties"]
    guideline = schema["$defs"]["GreenwashCriterionGuideline"]["properties"]
    terms = row["terms"]["anyOf"][0]
    one_line = "^[^\r\n]*$"
    table = {
        "text": (row["text"]["minLength"], row["text"]["maxLength"], row["text"]["pattern"]),
        "term": (terms["items"]["minLength"], terms["items"]["maxLength"], terms["items"]["pattern"]),
        "terms": (terms["minItems"], terms["maxItems"]),
        "guideline": (guideline["text"]["minLength"], guideline["text"]["maxLength"], guideline["text"]["pattern"]),
        "version": (schema["properties"]["version"]["minLength"], schema["properties"]["version"]["maxLength"]),
        "rows": (schema["properties"]["rows"]["minItems"], schema["properties"]["rows"]["maxItems"]),
    }
    assert table == {
        "text": (1, criteria_e0.TEXT_CHARS, one_line),
        "term": (1, criteria_e0.TERM_CHARS, one_line),
        "terms": (1, criteria_e0.TERMS_MAX),
        "guideline": (1, criteria_e0.GUIDELINE_CHARS, one_line),
        "version": (1, criteria_e0.VERSION_CHARS),
        "rows": (criteria_e0.ROW_COUNT, criteria_e0.ROW_COUNT),
    }
    assert schema["properties"]["version"]["pattern"] == "^" + criteria_e0.VERSION_NAME.pattern + "$"


def _with(edit: Any) -> dict[str, Any]:
    criteria = cast("dict[str, Any]", copy.deepcopy(default_criteria()))
    edit(criteria)
    return criteria


def _code(criteria: object) -> str:
    try:
        accept_criteria(criteria)
    except CriteriaRejected as refused:
        return refused.code
    return "accepted"


def _set_terms(n: int) -> Any:
    return lambda c: c["rows"][0].update(terms=[f"낱말{i}" for i in range(n)])


def _set(row: int, key: str, value: object) -> Any:
    return lambda c: c["rows"][row].update({key: value})


# 경계 앞뒤의 받기 결과(표기 전 BASE 의 accept_criteria 와 같은 값 — 검증 길은 0 변화). 표기 밖의 받기(앞뒤 공백을 지운
# 뒤 잼, 보이지 않는 글자)도 같이 묶는다: 표기가 검증에 걸렸다면 여기서 code 가 CRITERIA_SHAPE 로 바뀐다.
BOUNDARY = [
    ("text-300", _set(9, "text", "가" * 300), "accepted"),
    ("text-301", _set(9, "text", "가" * 301), "CRITERIA_TEXT_LENGTH"),
    ("text-0", _set(9, "text", ""), "CRITERIA_TEXT_LENGTH"),
    ("text-301-with-spaces", _set(9, "text", " " + "가" * 299 + " "), "accepted"),
    ("text-newline", _set(9, "text", "한 줄\n두 줄"), "CRITERIA_TEXT_MULTILINE"),
    ("terms-30", _set_terms(30), "accepted"),
    ("terms-31", _set_terms(31), "CRITERIA_TERMS_COUNT"),
    ("terms-0", _set_terms(0), "CRITERIA_TERMS_COUNT"),
    ("term-30", _set(0, "terms", ["가" * 30]), "accepted"),
    ("term-31", _set(0, "terms", ["가" * 31]), "CRITERIA_TERM_LENGTH"),
    ("term-0", _set(0, "terms", [""]), "CRITERIA_TERM_LENGTH"),
    ("guideline-200", _set(2, "guideline", {"text": "가" * 200, "status": "draft"}), "accepted"),
    ("guideline-201", _set(2, "guideline", {"text": "가" * 201, "status": "draft"}), "CRITERIA_GUIDELINE_LENGTH"),
    ("version-64", lambda c: c.update(version="v" * 64), "accepted"),
    ("version-65", lambda c: c.update(version="v" * 65), "CRITERIA_VERSION"),
    ("version-0", lambda c: c.update(version=""), "CRITERIA_VERSION"),
    ("rows-14", lambda c: c.update(rows=c["rows"][:14]), "CRITERIA_ROWS_FIXED"),
    ("rows-16", lambda c: c.update(rows=[*c["rows"], c["rows"][-1]]), "CRITERIA_ROWS_FIXED"),
]


@pytest.mark.parametrize(("edit", "code"), [pytest.param(e, c, id=n) for n, e, c in BOUNDARY])
def test_the_acceptance_at_the_bounds_is_unchanged(edit: Any, code: str) -> None:
    assert _code(_with(edit)) == code
