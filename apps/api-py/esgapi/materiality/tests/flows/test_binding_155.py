"""끼움 MaterialityBinding(밴드 IR3a §3-1, 순수): options@1 strict 받기와 문장(열쇠 길만 — 값 0), input 판정이
shapes.check_input 과 같음, dateRange 를 「오늘」로 읽어 만들기에서 막음, 「오늘」= clock 의 Asia/Seoul 날짜,
입력(받은 dict 그대로·회사 꼬리표·비용 상한 5 USD), 판 묶음, 포트 꼴, 축(순수·시계 한 곳). 옵션은 지어낸 값이다.
기대값은 손으로 적었다(상수를 불러 붙이지 않는다). clock 은 monkeypatch 로 고정한다(실제 날짜와 다른 값).
"""

import ast
import copy
import inspect
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pytest
from pydantic import ValidationError

from esgapi.core.flows.binding import DocumentlessBinding, DocumentlessFactsBinding, RunOptionsRejected
from esgapi.core.flows.types import FlowInputError
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.embedding import EmbeddingClient
from esgapi.core.llm.types import Tags
from esgapi.materiality.contracts import shapes
from esgapi.materiality.flows import binding_155, colab_155, iro_155, part2_155
from esgapi.materiality.flows.binding_155 import MaterialityBinding, accept_options
from esgapi.materiality.tests.flows.support import binding, options, received2, reordered2

SECRET = "가상비밀값-9q2w"
"""거절 문장에 실리면 안 되는 지어낸 값."""
NOON_UTC = datetime(2025, 6, 30, 3, 0, tzinfo=UTC)
"""clock 의 기본 고정값 — 서울 2025-06-30 12:00."""
REAL_CLOCK = binding_155.clock
"""갈아 끼우기 전의 clock(모듈을 읽을 때 잡아 둔다)."""


@pytest.fixture(autouse=True)
def fixed_clock(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    monkeypatch.setattr(binding_155, "clock", lambda: NOON_UTC)
    yield


def at(monkeypatch: pytest.MonkeyPatch, when: datetime) -> None:
    monkeypatch.setattr(binding_155, "clock", lambda: when)


def refused(given: Any) -> str:
    with pytest.raises(RunOptionsRejected) as caught:
        binding().check_options(given)
    return caught.value.message


def changed(change: Callable[[dict[str, Any]], None]) -> dict[str, Any]:
    """지은 input 을 고친 것."""
    given = received2()
    change(given)
    return given


def first_topic(given: dict[str, Any]) -> dict[str, Any]:
    topic: dict[str, Any] = given["topics"][0]
    return topic


# ── 3-1-1 옵션 받기 표 ──


def test_synthetic_options_are_accepted() -> None:
    binding().check_options(options())


@pytest.mark.parametrize(
    ("given", "message"),
    [
        ({}, "옵션 input이(가) 없어요"),
        (options(today="2025-06-30"), "알 수 없는 옵션이에요: today"),
        (options(maxCostUsd=1.0), "알 수 없는 옵션이에요: maxCostUsd"),
        (options(webSearch=True), "알 수 없는 옵션이에요: webSearch"),
        (options(webSearch=True, today=SECRET), "알 수 없는 옵션이에요: today, webSearch"),
        ({"input": changed(lambda x: x.update(extra=SECRET))}, "알 수 없는 옵션이에요: input.extra"),
        ({"input": changed(lambda x: x["company"].update(ceo=SECRET))}, "알 수 없는 옵션이에요: input.company.ceo"),
        ({"input": changed(lambda x: x.pop("company"))}, "옵션 input.company이(가) 없어요"),
        ({"input": changed(lambda x: first_topic(x).pop("description"))}, "옵션 input.topics.description이(가) 없어요"),
        (
            {"input": changed(lambda x: x.update(schemaVersion="materiality.input@2"))},
            "옵션 input.schemaVersion의 값이 맞지 않아요",
        ),
        ({"input": changed(lambda x: x.update(userLocation=SECRET))}, "옵션 input.userLocation의 값이 맞지 않아요"),
        ({"input": changed(lambda x: x.update(userLocation="kr"))}, "옵션 input.userLocation의 값이 맞지 않아요"),
        ({"input": changed(lambda x: x.update(topics=[]))}, "옵션 input.topics의 값이 맞지 않아요"),
        (
            {"input": changed(lambda x: x["topics"].append(dict(x["topics"][0])))},
            "옵션 input.topics의 값이 맞지 않아요",
        ),
        (
            {"input": changed(lambda x: x.update(latestEventMode="false"))},
            "옵션 input.latestEventMode의 값이 맞지 않아요",
        ),
        ({"input": SECRET}, "옵션 input의 값이 맞지 않아요"),
        ([SECRET], "옵션 전체의 값이 맞지 않아요"),
    ],
    ids=[
        "empty",
        "today",
        "maxCostUsd",
        "webSearch",
        "two-unknown",
        "input-extra",
        "company-extra",
        "company-missing",
        "topic-description-missing",
        "schemaVersion",
        "userLocation-secret",
        "userLocation-lower",
        "topics-empty",
        "topics-duplicate",
        "latestEventMode-text",
        "input-text",
        "not-object",
    ],
)
def test_refused_options_say_one_sentence_with_key_paths_only(given: Any, message: str) -> None:
    said = refused(given)
    assert said == message
    assert SECRET not in said and "9q2w" not in said


def test_a_duplicate_topic_name_does_not_reach_the_sentence() -> None:
    def twice(x: dict[str, Any]) -> None:
        first_topic(x)["topic"] = SECRET
        x["topics"].append({"topic": SECRET, "description": "가상 설명"})

    said = refused({"input": changed(twice)})
    assert said == "옵션 input.topics의 값이 맞지 않아요"
    assert SECRET not in said and "9q2w" not in said


def test_a_value_planted_in_a_wrong_field_does_not_reach_the_sentence() -> None:
    said = refused({"input": changed(lambda x: x["company"].update(name=[SECRET]))})
    assert said == "옵션 input.company.name의 값이 맞지 않아요"
    assert SECRET not in said and "9q2w" not in said


# ── 3-1-2 같은 판정(colab_155.check_received) ──

SAME_TABLE: list[Callable[[dict[str, Any]], None]] = [
    lambda x: None,
    lambda x: x.update(subtopicsByTopic=None, valueChain=None),
    lambda x: x.update(extra=1),
    lambda x: x.pop("topics"),
    lambda x: x.update(schemaVersion="materiality.input@2"),
    lambda x: x.update(sector="가상 섹터"),
    lambda x: x.update(userLocation="KOR"),
    lambda x: x.update(industries=[]),
    lambda x: x["topics"].append(dict(x["topics"][0])),
    lambda x: x.update(latestEventMode=1),
    lambda x: x["valueChain"][0].pop("stakeholder"),
    lambda x: x.update(sector="financial"),
]


def _passes(call: Callable[[], object], error: type[Exception]) -> bool:
    try:
        call()
    except error:
        return False
    return True


@pytest.mark.parametrize("change", SAME_TABLE, ids=[str(n) for n in range(len(SAME_TABLE))])
def test_the_input_verdict_is_the_same_as_check_received(change: Callable[[dict[str, Any]], None]) -> None:
    given = changed(change)
    by_binding = _passes(lambda: accept_options({"input": copy.deepcopy(given)}), RunOptionsRejected)
    by_flow = _passes(lambda: colab_155.check_received(copy.deepcopy(given)), FlowInputError)
    by_shapes = _passes(lambda: shapes.check_input(copy.deepcopy(given)), ValidationError)
    assert by_binding == by_flow == by_shapes


def test_the_same_table_has_both_verdicts() -> None:
    verdicts = {_passes(lambda c=c: shapes.check_input(changed(c)), ValidationError) for c in SAME_TABLE}
    assert verdicts == {True, False}


# ── 3-1-3 dateRange(처분 ⑤ 가) ──


def with_range(text: object) -> dict[str, Any]:
    return options(changed(lambda x: x.update(dateRange=text)))


@pytest.mark.parametrize(
    "text", ["2024-01-01~오늘까지", "2025-06-30~오늘까지", "2024-01-01~2024-12-31", "2026-01-01~2026-12-31"]
)
def test_a_date_range_read_with_the_seoul_today_is_accepted(text: str) -> None:
    binding().check_options(with_range(text))


@pytest.mark.parametrize(
    "text",
    [
        "2025-07-01~오늘까지",  # 시작이 서울 오늘(2025-06-30) 뒤
        "최근 1년",
        "2024-13-01~오늘까지",
        "2024-02-30~2024-03-01",
        "2024-12-31~2024-01-01",
        f"{SECRET}~오늘까지",
        "",
    ],
    ids=["after-today", "words", "month-13", "feb-30", "start-after-end", "secret", "empty"],
)
def test_a_date_range_that_cannot_be_read_is_refused_at_create(text: str) -> None:
    said = refused(with_range(text))
    assert said == "옵션 input.dateRange의 값이 맞지 않아요"
    assert text == "" or text not in said
    assert SECRET not in said


def test_a_date_range_that_is_not_text_is_the_shape_sentence() -> None:
    assert refused(with_range(20240101)) == "옵션 input.dateRange의 값이 맞지 않아요"


def test_the_date_range_is_read_with_the_seoul_date_not_the_utc_date(monkeypatch: pytest.MonkeyPatch) -> None:
    given = with_range("2025-07-01~오늘까지")
    at(monkeypatch, datetime(2025, 6, 30, 14, 59, 59, tzinfo=UTC))  # 서울 6-30 23:59:59
    refused(given)
    at(monkeypatch, datetime(2025, 6, 30, 15, 0, 0, tzinfo=UTC))  # 서울 7-1 00:00 — UTC 로는 아직 6-30
    binding().check_options(given)


# ── 3-1-4 today 경계(처분 ④ 가) ──


@pytest.mark.parametrize(
    ("when", "seoul"),
    [
        (datetime(2025, 6, 30, 14, 59, 59, tzinfo=UTC), date(2025, 6, 30)),
        (datetime(2025, 6, 30, 15, 0, 0, tzinfo=UTC), date(2025, 7, 1)),
        (datetime(2025, 6, 30, 0, 30, tzinfo=timezone(timedelta(hours=9))), date(2025, 6, 30)),
        (datetime(2024, 12, 31, 15, 0, tzinfo=UTC), date(2025, 1, 1)),
    ],
    ids=["before-seoul-midnight", "seoul-midnight", "given-in-seoul", "new-year"],
)
def test_today_is_the_seoul_date_of_the_clock(monkeypatch: pytest.MonkeyPatch, when: datetime, seoul: date) -> None:
    at(monkeypatch, when)
    made = binding().inputs(options(), company_id=42)
    assert made.today == seoul
    assert type(made.today) is date
    assert binding_155.today() == seoul


def test_the_clock_is_read_when_called(monkeypatch: pytest.MonkeyPatch) -> None:
    first = binding().inputs(options(), company_id=1).today
    at(monkeypatch, NOON_UTC + timedelta(days=1))
    assert (first, binding().inputs(options(), company_id=1).today) == (date(2025, 6, 30), date(2025, 7, 1))


def test_the_real_clock_is_aware_utc() -> None:
    got = REAL_CLOCK()
    assert got.tzinfo is UTC
    assert got.astimezone(binding_155.SEOUL).utcoffset() == timedelta(hours=9)


# ── 3-1-5 inputs ──


def test_inputs_pass_the_received_input_as_is_with_the_company_tags_and_the_cost_cap() -> None:
    given = options()
    made = binding().inputs(given, company_id=42)
    assert made.received is given["input"]
    assert list(made.received) == list(received2())
    assert made.tags == Tags(tenant="42", module="materiality")
    assert made.max_cost_usd == 5.0
    assert (made.route1, made.route2) == ("standard-openai-4o", "standard-openai-41")
    assert iro_155.check_today(made.today) == date(2025, 6, 30)


def test_inputs_keep_the_key_order_of_the_received_input() -> None:
    made = binding().inputs({"input": reordered2()}, company_id=7)
    assert next(iter(made.received)) == "topics"
    assert list(made.received["topics"][0]) == ["description", "topic"]
    assert list(made.received["valueChain"][0])[:2] == ["business_activity", "stakeholder"]
    assert list(made.received["industries"][0]) == ["description", "industryName", "standard"]


def test_inputs_refuse_options_that_do_not_fit() -> None:
    with pytest.raises(RunOptionsRejected):
        binding().inputs({}, company_id=1)
    with pytest.raises(RunOptionsRejected):
        binding().inputs(with_range("2025-07-01~오늘까지"), company_id=1)


def test_the_run_cost_cap_is_five_usd() -> None:
    assert binding_155.RUN_MAX_COST_USD == 5.0
    assert colab_155.check_cost(binding_155.RUN_MAX_COST_USD) == 5.0  # 흐름의 상한 검사를 지난다


# ── 3-1-6 versions·상한·포트 ──


def test_versions_are_engine_flow_and_the_six_prompt_ids() -> None:
    assert binding().versions(options()) == {
        "engine": "colab_155",
        "flow": "materiality.iro@155",
        "promptIds": {
            "regulation": "materiality/regulation@1",
            "keywords": "materiality/keywords@1",
            "controversy": "materiality/controversy@1",
            "impact": "materiality/impact@1",
            "financial": "materiality/financial@1",
            "pathway": "materiality/pathway@1",
        },
    }


def test_the_binding_has_the_facts_branch() -> None:
    assert isinstance(binding(), DocumentlessFactsBinding)  # IR4 ③ — 판 열쇠를 박고 판으로 입력을 짓는 길


def _parameters(owner: object, name: str) -> list[tuple[str, Any]]:
    signature = inspect.signature(getattr(owner, name))
    return [(p.name, p.kind) for p in signature.parameters.values() if p.name != "self"]


@pytest.mark.parametrize("name", ["check_options", "inputs", "adapters", "versions"])
def test_the_binding_has_the_documentless_port_shape(name: str) -> None:
    assert _parameters(MaterialityBinding, name) == _parameters(DocumentlessBinding, name)
    assert "document" not in dict(_parameters(MaterialityBinding, name))


def test_inputs_take_the_company_as_a_keyword_only_argument() -> None:
    assert dict(_parameters(MaterialityBinding, "inputs"))["company_id"] is inspect.Parameter.KEYWORD_ONLY


@dataclass
class FakeContext:
    """RunContext 꼴의 가짜. llm() 은 미리 지은 표시 객체를 돌려준다."""

    marker: object = field(default_factory=object)
    company_id: int = 9
    run_id: int = 1
    module: str = "materiality"
    flow_id: str = "materiality.iro@155"
    attempt: int = 1
    dry_run: bool = False
    asked: int = 0

    def llm(self) -> LlmClient:
        self.asked += 1
        return self.marker  # pyright: ignore[reportReturnType]

    def embedding(self) -> EmbeddingClient:
        raise AssertionError("중대성평가는 임베딩을 쓰지 않는다")


def test_adapters_use_the_run_client() -> None:
    ctx = FakeContext()
    made = binding().adapters(ctx)
    assert isinstance(made, iro_155.IroAdapters)
    assert made.llm is ctx.marker
    assert ctx.asked == 1


def test_the_prompt_ids_cover_the_six_calling_steps() -> None:
    called = {*colab_155.PROMPT_IDS, *part2_155.PROMPT_IDS2}
    assert called == set(binding().versions(options())["promptIds"])  # pyright: ignore[reportArgumentType]
    assert called <= set(iro_155.FLOW.steps)


# ── 3-1-9 축 ──

BINDING_FILE = Path(binding_155.__file__)
CLOCK_WORDS = ("datetime.now", "datetime.today", "datetime.utcnow", "date.today", "time.time", "time.monotonic")


def imported(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.update(f"{node.module}.{alias.name}" for alias in node.names)
    return names


def test_the_binding_imports_no_django_settings_engines_or_sdk() -> None:
    bad = [
        n
        for n in imported(BINDING_FILE)
        if n.split(".")[0] in {"django", "ninja", "openai", "anthropic", "os", "time"}
        or n.startswith(("esgapi.config", "esgapi.materiality.engines", "esgapi.runs"))
    ]
    assert bad == []
    assert "environ" not in BINDING_FILE.read_text(encoding="utf-8")


def _clock_reads(tree: ast.AST) -> list[ast.AST]:
    found: list[ast.AST] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Attribute)
            and isinstance(node.value, ast.Name)
            and f"{node.value.id}.{node.attr}" in CLOCK_WORDS
        ):
            found.append(node)
    return found


def test_the_clock_is_read_in_one_place_inside_clock() -> None:
    tree = ast.parse(BINDING_FILE.read_text(encoding="utf-8"))
    (clock_def,) = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "clock"]
    everywhere = _clock_reads(tree)
    inside = _clock_reads(clock_def)
    assert len(everywhere) == 1
    assert everywhere == inside
    assert "date.today" not in BINDING_FILE.read_text(encoding="utf-8")


# ── MARC-ISSUE-367 의 1: 사용자가 지은 dict 열쇠(토픽 이름)는 거절 문장의 열쇠 길에 실리지 않는다(IR3b) ──

MARKER = "ZZ-토픽-표지"
"""subtopicsByTopic 의 열쇠로 심는 지어낸 토픽 이름 — 어느 문장에도 0."""


def with_subtopics(subtopics: Any, *, key: Any = MARKER) -> dict[str, Any]:
    given = received2()
    given["subtopicsByTopic"] = {**given["subtopicsByTopic"], key: subtopics}
    return {"input": given}


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (
            with_subtopics([{"name": "가상 서브 라", "description": "가상 설명", "bogus": 1}]),
            "알 수 없는 옵션이에요: input.subtopicsByTopic.*.bogus",
        ),
        (
            with_subtopics([{"name": 7, "description": "가상 설명"}]),
            "옵션 input.subtopicsByTopic.*.name의 값이 맞지 않아요",
        ),
        (
            with_subtopics([{"name": "가상 서브 라"}]),
            "옵션 input.subtopicsByTopic.*.description이(가) 없어요",
        ),
        (with_subtopics(MARKER), "옵션 input.subtopicsByTopic.*의 값이 맞지 않아요"),
    ],
    ids=["unknown-key", "wrong-shape", "missing", "not-a-list"],
)
def test_a_topic_name_key_is_masked_in_the_sentence(given: Any, message: str) -> None:
    said = refused(given)
    assert said == message
    assert MARKER not in said and "표지" not in said


def test_a_key_that_is_not_text_is_masked_without_the_key_mark() -> None:
    said = refused(with_subtopics([{"name": "가상 서브 라", "description": "가상 설명"}], key=5))
    assert said == "옵션 input.subtopicsByTopic.*의 값이 맞지 않아요"
    assert "[key]" not in said and "5" not in said


def test_the_path_masks_only_the_part_under_a_dict_key_field() -> None:
    path = binding_155._path  # pyright: ignore[reportPrivateUsage]
    assert path(("input", "subtopicsByTopic", MARKER, 0, "bogus")) == "input.subtopicsByTopic.*.bogus"
    assert path(("input", "subtopicsByTopic", 5, "[key]")) == "input.subtopicsByTopic.*"
    assert path(("input", "subtopicsByTopic", 5, 0, "bogus")) == "input.subtopicsByTopic.*.bogus"  # int 열쇠도 가림
    assert path(("input", "topics", 0, "description")) == "input.topics.description"  # 분모: 목록 칸은 그대로
    assert path(("input", "company", "ceo")) == "input.company.ceo"
    fields = binding_155._DICT_KEY_FIELDS  # pyright: ignore[reportPrivateUsage]
    assert frozenset({"subtopicsByTopic"}) == fields


# ── MARC-ISSUE-367 의 2: inputs 는 「오늘」을 한 번 읽는다(검사와 입력이 자정 경계에서 갈리지 않는다, IR3b) ──


def test_inputs_read_the_clock_once_across_the_seoul_midnight(monkeypatch: pytest.MonkeyPatch) -> None:
    reads = [datetime(2025, 6, 30, 14, 59, 59, tzinfo=UTC), datetime(2025, 6, 30, 15, 0, 0, tzinfo=UTC)]
    calls: list[datetime] = []

    def counting() -> datetime:
        when = reads[min(len(calls), 1)]  # 둘째부터 서울 자정을 넘는다
        calls.append(when)
        return when

    monkeypatch.setattr(binding_155, "clock", counting)
    made = binding().inputs(options(), company_id=3)
    assert len(calls) == 1
    assert made.today == date(2025, 6, 30)  # 첫 값(서울 23:59:59)의 날짜


def test_the_run_cost_cap_is_the_flow_constant_re_exported() -> None:
    """상한은 흐름 colab_155 한 자리에 정의되고 binding_155 는 같은 값을 다시 내보낸다(MARC-ISSUE-412 ①, 밴드 IRS1)."""
    assert binding_155.RUN_MAX_COST_USD is colab_155.RUN_MAX_COST_USD
    assert "RUN_MAX_COST_USD: Final" not in BINDING_FILE.read_text(encoding="utf-8")
