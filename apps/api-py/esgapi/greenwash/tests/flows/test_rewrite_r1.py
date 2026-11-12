"""흐름 greenwash.rewrite@R1(밴드 RW1 `MARC-TICK-163`): 끝난 실행의 결과에 High·Mid 문장의 exampleSentence 를 채운다.

공급사는 모의(MockProvider, 합성 설정의 경로 mock) — 실제 네트워크·키 0. 입력 결과는
tests/data/contract-examples/result-normal.json(High·Mid·Mid·Low, 지은 문장)을 읽기만 하고, 문장 수는 시험 안에서 그
항목을 베껴 늘린다. 지은 결과는 입력·출력 둘 다 결과 꼴 greenwash.result@1 을 strict 로 지난다.
T1~T13 은 RW1 발주서 §3 의 표 번호다. 밴드 RW2(`MARC-TICK-165`)가 프롬프트를 판 2 로, 답 꼴을 구조화 출력(schema
RewriteAnswer)으로 바꿨다(MARC-ENT-279) — 모의 답은 schema 꼴 JSON 이고, 꼴이 틀린 답은 호출 층이 한 번 더 부르므로
(MAX_SCHEMA_RETRIES 1) 대본을 두 번 심는다. 밴드 RW3(`MARC-TICK-174`)가 프롬프트를 판 3 으로 바꾸고 뒤 검사 둘(평가어
null·어미 경고)을 더했다(MARC-ENT-288, T14·T15). 밴드 RW4(`MARC-TICK-182`)가 프롬프트를 판 4 로 바꾸고 빈칸 밖 숫자
경고를 더했다(MARC-ENT-309, T16) — 대본 답(rewritten)도 판 4 를 지켜 원문의 숫자를 빈칸 안에 넣는다. RW4 ② 가 모델을
gpt-6-luna(경로 light-openai, temperature 없음)로 바꿨다(MARC-ENT-314, T17 — 정본 설정에 openai 자리의 모의 공급사).
"""

import copy
import dataclasses
import hashlib
import io
import json
import re
from collections.abc import Callable, Sequence
from importlib import resources
from pathlib import Path
from typing import Any, cast

import pytest
from openpyxl import load_workbook

from esgapi.core.flows.run import run_flow
from esgapi.core.flows.types import FlowRun, FlowStepFailed
from esgapi.core.llm.client import TEMPERATURE_UNSUPPORTED_MODELS, CallRequest, LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.errors import LlmConfigError
from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id
from esgapi.core.llm.providers.mock import SYNTHETIC_USAGE, MockProvider, MockReply
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import (
    BudgetExceeded,
    CallMeta,
    Completed,
    LlmResult,
    ProviderError,
    ProviderFailed,
    ProviderRequest,
    ProviderResponse,
    Refusal,
    SchemaMismatch,
    Scope,
    SystemSegment,
    Tags,
    TextPart,
    TimedOut,
    Truncated,
)
from esgapi.greenwash.contracts import shapes
from esgapi.greenwash.flows import colab_e0
from esgapi.greenwash.flows import rewrite_r1 as rw

TAGS = Tags(tenant="tenant-synthetic", module="greenwash")
EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "contract-examples"
PROMPT_SHA256 = "b5fb9c945c3f97bd3c8be94e7474fe245a10a75f662d864da69c4ca378ee6f97"
"""prompts/rewrite/4.md 의 sha256(RW4 커밋 직전 파일에서 떴다). 글은 초안 4 그대로다(MARC-ENT-309). 초안 파일은 저장소
밖이라 시험은 sha256 으로 고정한다(초안과의 글자 대조는 밴드 보고)."""
PROMPT_3_SHA256 = "799869694f5e9d48f82929da2867261fd5691c006cc1206b1481879166124f69"
"""prompts/rewrite/3.md 의 sha256(RW3). 판 기록이라 바뀌지 않는다(MARC-ENT-288)."""
PROMPT_2_SHA256 = "79c67a93d97e56594b57cc35d7add8f1c8331d406f5d8a5d8ff05de2c8d962cd"
"""prompts/rewrite/2.md 의 sha256(RW2). 판 기록이라 바뀌지 않는다(MARC-ENT-279)."""
PROMPT_1_SHA256 = "6e21bdb1e569e6fa9230610e1455f201913f4625640a520e958995eb72aaad87"
"""prompts/rewrite/1.md 의 sha256(RW1). 판 기록이라 바뀌지 않는다(MARC-ENT-278)."""
RULES_ADDED_IN_2 = (
    "- 연도·목표연도·기간도 빈칸 꼴로만 씁니다. 「20__년」처럼 숫자 일부만 비우지 않습니다. (예: [____: 목표연도]까지)",
    "- 원문에 없는 이행·검증·관리 사실(검증을 받았다, 관리하고 있다, 절차를 마련했다 등)을 사실로 단정하지 않습니다. "
    '그런 내용은 빈칸으로 두거나 "~할 계획입니다" 꼴로만 씁니다.',
    '- 지적·평가·설명("~이 필요함", "~으로 추정되나")이 아니라, '
    "보고서 본문에 그대로 넣을 수 있는 고쳐 쓴 문장만 씁니다.",
)
"""초안 2 가 판 1 에 더한 세 줄(MARC-ENT-279 의 1~3). 판 1 의 「원문에 이미 있는 수치와 고유명사는 그대로 씁니다.」
다음에 든다. 초안 파일은 저장소 밖이라 시험은 판 1 과의 차이와 sha256 으로 고정한다(초안과의 글자 대조는 밴드 보고)."""
META = CallMeta(call_id="c", prompt_id=rw.PROMPT_ID, attempts=(), total_cost_usd=0.0, warnings=())
DRAFT_EXAMPLE = (
    "당사는 [____: 기준연도] 대비 [____: 적용 범위(Scope 1·2 등)] 배출량을 2030년까지 [____: 감축률(%)] 감축하고, "
    "남는 배출량은 [____: 상쇄 수단]으로 상쇄해 탄소중립을 달성할 계획입니다."
)
"""초안 「예」의 예시 문장(지어낸 문장)."""
BLOCK = re.compile(r"\[문장 i=(\d+)\]\n원문: (.*)\n")
DIGITS = re.compile(r"[0-9]+")


# ── 도우미 ───────────────────────────────────────────────────────────────────


def normal() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / "result-normal.json").read_text(encoding="utf-8")))


def with_levels(levels: Sequence[str]) -> dict[str, Any]:
    """result-normal 의 항목을 level 마다 베껴(High ← 0번, Mid ← 1번, Low ← 3번) 문장을 늘린 결과.
    문장은 번호로 가른다."""
    result = normal()
    source = {"High": result["items"][0], "Mid": result["items"][1], "Low": result["items"][3]}
    items: list[dict[str, Any]] = []
    for n, level in enumerate(levels):
        item = copy.deepcopy(source[level])
        item["sentence"] = f"지은 문장 {n}: {item['sentence']}"
        items.append(item)
    result["items"] = items
    by_level = {level: sum(1 for x in levels if x == level) for level in rw.LEVELS}
    result["counts"] = {**result["counts"], "total": len(items), "byLevel": by_level}
    return result


def interleaved(targets: int) -> list[str]:
    """대상 targets 개(High·Mid 번갈아)와 그 사이사이 Low(대상 셋마다 하나, 앞뒤에도 하나)."""
    levels = ["Low"]
    for n in range(targets):
        levels.append("High" if n % 2 == 0 else "Mid")
        if n % 3 == 2:
            levels.append("Low")
    levels.append("Low")
    return levels


def strict(result: dict[str, Any]) -> None:
    shapes.RESULT_SHAPES["greenwash.result@1"].validate_python(result, strict=True)


def rewritten(sentence: str) -> str:
    """판 4 를 지킨 대본 답: 원문의 숫자는 빈칸 안으로 넣는다(`2030년` → `[____: 값 2030]년`, 판 4 「값은 모두 빈칸」,
    MARC-ENT-309). 숫자를 항목명에 남겨 문장끼리 가른다 — 빈칸 안 숫자는 value_outside_blank 가 세지 않는다."""
    blanked = DIGITS.sub(lambda m: f"[____: 값 {m.group()}]", sentence.strip())
    return f"[____: 기준연도] 대비 {blanked}"


def user_of(request: ProviderRequest) -> str:
    return "".join(part.text for part in request.user if isinstance(part, TextPart))


def echo(request: ProviderRequest) -> ProviderResponse:
    """받은 덩이마다 `[____: 기준연도] 대비 <원문>` 을 돌려주는 대본 답."""
    items = [{"i": int(i), "example_sentence": rewritten(s)} for i, s in BLOCK.findall(user_of(request))]
    return Completed(text=json.dumps({"items": items}, ensure_ascii=False), usage=SYNTHETIC_USAGE)


def reversed_echo(request: ProviderRequest) -> ProviderResponse:
    items = [{"i": int(i), "example_sentence": rewritten(s)} for i, s in BLOCK.findall(user_of(request))]
    return Completed(text=json.dumps({"items": items[::-1]}, ensure_ascii=False), usage=SYNTHETIC_USAGE)


def client(mock: MockProvider, sink: MemorySink | None = None) -> LlmClient:
    return LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": mock},
        prompts=PackagePromptStore(),
        log=sink or MemorySink(),
    )


def bridge(mock: MockProvider, sink: MemorySink | None = None) -> rw.RewriteBridge:
    return rw.RewriteBridge(client(mock, sink), route="mock", tags=TAGS)


def run(result: dict[str, Any], llm: rw.RewriteBridge, *, dry_run: bool = False) -> FlowRun:
    return run_flow(rw.FLOW, rw.RewriteInputs(result=result, dry_run=dry_run), rw.RewriteAdapters(llm=llm))


def out(flow_run: FlowRun) -> dict[str, Any]:
    (result,) = flow_run.output.results
    return cast("dict[str, Any]", result)


def data(flow_run: FlowRun) -> dict[str, Any]:
    return cast("dict[str, Any]", flow_run.steps["rewrite"].data)


def examples_of(result: dict[str, Any]) -> list[str | None]:
    return [item["exampleSentence"] for item in result["items"]]


def expected(result: dict[str, Any]) -> list[str | None]:
    return [rewritten(i["sentence"]) if i["level"] in ("High", "Mid") else None for i in result["items"]]


def warnings(**given: int) -> dict[str, int]:
    return {name: given.get(name, 0) for name in rw.WARNINGS}


def sheet_examples(flow_run: FlowRun) -> list[object]:
    (book,) = flow_run.output.files
    rows = list(load_workbook(io.BytesIO(book.content), read_only=True)["문장"].iter_rows(values_only=True))
    return [row[-1] for row in rows[1:]]


def twice(mock: MockProvider, reply: MockReply) -> MockProvider:
    """꼴이 틀린 답이면 호출 층이 한 번 더 부른다(MAX_SCHEMA_RETRIES) — 같은 대본을 두 번 심는다."""
    return mock.enqueue(reply).enqueue(reply)


class Canned(rw.RewriteBridge):
    """공급사 없이 정한 결과 갈래를 돌려주는 다리(모의 공급사로는 지을 수 없는 갈래 — 예산 초과. 공급사 오류·시간 초과도
    같은 꼴로 맞댄다)."""

    def __init__(self, make: Callable[[], LlmResult[rw.RewriteAnswer]]) -> None:
        super().__init__(client(MockProvider()), route="mock", tags=TAGS)
        self.make = make
        self.asked = 0

    def ask(self, sentences: str) -> LlmResult[rw.RewriteAnswer]:
        self.asked += 1
        return self.make()


# ── T1 선언 · T2 템플릿 ──────────────────────────────────────────────────────


def test_t1_declaration() -> None:
    flow = rw.FLOW
    assert (flow.module, flow.id, flow.input_shape) == ("greenwash", "greenwash.rewrite@R1", "greenwash.result@1")
    assert flow.result_shapes == ("greenwash.result@1",)
    assert flow.output_files == ("greenwash-report.xlsx",)
    assert flow.steps == ("rewrite", "report")
    assert flow.adapter_names == ("llm",)
    assert (rw.CHAT_ROUTE, colab_e0.CHAT_ROUTE) == ("light-openai", "light-openai-41")
    assert not hasattr(rw, "TEMPERATURE")
    assert (rw.BATCH_SIZE, rw.TARGET_LEVELS, rw.MAX_CHARS) == (10, ("High", "Mid"), 200)


def test_t2_template() -> None:
    assert rw.PROMPT_ID == "greenwash/rewrite@4"
    template = PackagePromptStore().get(parse_prompt_id(rw.PROMPT_ID))
    assert len(template.system) == 1
    assert template.system[0].cache is False
    assert "{{" not in template.system[0].text
    assert template.user == "{{sentences}}"
    body = resources.files("esgapi.greenwash").joinpath("prompts", "rewrite", "4.md").read_bytes()
    assert hashlib.sha256(body).hexdigest() == PROMPT_SHA256
    assert body.startswith(b"=== system ===\n") and body.endswith(b"\n=== user ===\n{{sentences}}\n")


def test_t2_versions_1_and_2_are_kept() -> None:
    two = resources.files("esgapi.greenwash").joinpath("prompts", "rewrite", "2.md").read_bytes()
    assert hashlib.sha256(two).hexdigest() == PROMPT_2_SHA256
    third = PackagePromptStore().get(parse_prompt_id("greenwash/rewrite@3"))
    assert third.user == PackagePromptStore().get(parse_prompt_id("greenwash/rewrite@2")).user


def test_t2_version_3_is_kept() -> None:
    three = resources.files("esgapi.greenwash").joinpath("prompts", "rewrite", "3.md").read_bytes()
    assert hashlib.sha256(three).hexdigest() == PROMPT_3_SHA256
    fourth = PackagePromptStore().get(parse_prompt_id(rw.PROMPT_ID))
    assert fourth.user == PackagePromptStore().get(parse_prompt_id("greenwash/rewrite@3")).user


def test_t2_the_prompt_forbids_the_words_the_flow_checks() -> None:
    """판 4 의 평가어 줄이 흐름의 COMMENTARY_WORDS 와 같은 다섯을 같은 차례로 든다(한쪽만 바뀌지 않게)."""
    text = PackagePromptStore().get(parse_prompt_id(rw.PROMPT_ID)).system[0].text
    (line,) = [line for line in text.split("\n") if "같은 평가어를 쓰지 않습니다" in line]
    assert tuple(re.findall(r'"([^"]+)"', line)) == rw.COMMENTARY_WORDS


def test_t2_version_2_is_version_1_plus_three_rules() -> None:
    one = resources.files("esgapi.greenwash").joinpath("prompts", "rewrite", "1.md").read_bytes()
    assert hashlib.sha256(one).hexdigest() == PROMPT_1_SHA256
    first = PackagePromptStore().get(parse_prompt_id("greenwash/rewrite@1"))
    second = PackagePromptStore().get(parse_prompt_id("greenwash/rewrite@2"))
    lines = first.system[0].text.split("\n")
    at = lines.index("- 원문에 이미 있는 수치와 고유명사는 그대로 씁니다.") + 1
    assert second.system[0].text.split("\n") == [*lines[:at], *RULES_ADDED_IN_2, *lines[at:]]
    assert second.user == first.user


# ── T3 정상 · T4 차례·칸 불변 ─────────────────────────────────────────────────


def test_t3_normal_fills_high_and_mid_and_leaves_low_null() -> None:
    given = normal()
    strict(given)
    mock = MockProvider().enqueue(echo)
    flow_run = run(given, bridge(mock))
    result = out(flow_run)
    assert len(mock.calls) == 1
    assert examples_of(result) == expected(given)
    assert [i["level"] for i in result["items"]] == ["High", "Mid", "Mid", "Low"]
    assert examples_of(result)[3] is None
    strict(result)
    assert sheet_examples(flow_run) == [*expected(given)[:3], None]
    step = data(flow_run)
    assert (step["targets"], step["batches"], step["nulled"]) == (3, 1, 0)
    assert step["warnings"] == warnings()
    assert step["dry_run"] is None
    assert [(c["batch"], c["promptId"]) for c in step["calls"]] == [(0, rw.PROMPT_ID)]


def test_t4_order_and_other_fields_are_unchanged() -> None:
    given = with_levels(interleaved(11))
    # 앞뒤 공백·줄바꿈이 든 칸도 그대로 간다(사본은 칸을 손질하지 않는다)
    given["items"][1]["sentence"] = "  " + given["items"][1]["sentence"] + "\n"
    given["items"][1]["fixParagraph"] = "\n " + given["items"][1]["fixParagraph"] + "  \n"
    strict(given)
    before = copy.deepcopy(given)
    result = out(run(given, bridge(MockProvider().enqueue(echo).enqueue(echo))))
    assert given == before  # 들어온 dict 를 제자리에서 고치지 않는다
    assert list(result) == list(given)
    assert {k: v for k, v in result.items() if k != "items"} == {k: v for k, v in given.items() if k != "items"}
    assert len(result["items"]) == len(given["items"])
    for got, was in zip(result["items"], given["items"], strict=True):
        assert list(got) == list(was)
        assert {k: v for k, v in got.items() if k != "exampleSentence"} == {
            k: v for k, v in was.items() if k != "exampleSentence"
        }
    assert examples_of(result) == expected(given)


# ── T5 묶음 경계 · T6 짝짓기 ──────────────────────────────────────────────────


@pytest.mark.parametrize(("targets", "calls"), [(0, 0), (1, 1), (10, 1), (11, 2), (22, 3)])
def test_t5_batch_boundaries(targets: int, calls: int) -> None:
    given = with_levels(interleaved(targets))
    mock = MockProvider()
    for _ in range(4):
        mock.enqueue(echo)
    flow_run = run(given, bridge(mock))
    assert len(mock.calls) == calls
    assert mock.pending == 4 - calls
    left = targets
    for request in mock.calls:
        sent = [int(i) for i, _ in BLOCK.findall(user_of(request))]
        assert sent == list(range(min(rw.BATCH_SIZE, left)))
        left -= len(sent)
    assert left == 0
    assert examples_of(out(flow_run)) == expected(given)
    assert (data(flow_run)["targets"], data(flow_run)["batches"]) == (targets, calls)
    strict(out(flow_run))


def test_t6_answers_are_paired_by_i_not_by_order() -> None:
    given = with_levels(interleaved(7))
    result = out(run(given, bridge(MockProvider().enqueue(reversed_echo))))
    assert examples_of(result) == expected(given)


@pytest.mark.parametrize(
    "wrap",
    ["```json\n{0}\n```", "```\n{0}\n```", "  \n```json {0}```\n "],
    ids=["json-fence", "bare-fence", "fence-one-line"],
)
def test_t6_a_fenced_answer_is_a_schema_mismatch(wrap: str) -> None:
    """판 2 는 울타리를 벗기지 않는다 — 구조화 출력 아래 울타리 친 답은 꼴이 틀린 답이다(다시 부르기 뒤에도)."""
    given, ok = three_sentences()
    mock = twice(MockProvider(), Completed(text=wrap.format(answer((0, ok[0]))), usage=SYNTHETIC_USAGE))
    flow_run = run(given, bridge(mock))
    assert len(mock.calls) == 2
    assert examples_of(out(flow_run)) == [None] * 4
    assert data(flow_run)["warnings"] == warnings(schema_mismatch=3)


# ── T7 망가진 답 ─────────────────────────────────────────────────────────────


def answer(*pairs: tuple[object, object]) -> str:
    return json.dumps({"items": [{"i": i, "example_sentence": t} for i, t in pairs]}, ensure_ascii=False)


def three_sentences() -> tuple[dict[str, Any], list[str]]:
    given = normal()
    return given, [rewritten(i["sentence"]) for i in given["items"][:3]]


BROKEN: list[tuple[str, Callable[[list[str]], ProviderResponse], list[int], dict[str, int]]] = [
    # (이름, 답 짓기(정상 글 셋 → 공급사 답), 채워지는 대상 차례, 경고)
    ("refused", lambda ok: Refusal(text="거절", category=None, usage=SYNTHETIC_USAGE), [], {"refused": 3}),
    ("truncated", lambda ok: Truncated(text='{"items": [', usage=SYNTHETIC_USAGE), [], {"truncated": 3}),
    # 판 2: JSON 이 아니거나 꼴이 틀린 답은 호출 층의 schema 검증·다시 부르기 뒤 SchemaMismatch(not_json 은 오지 않는다)
    ("not-json-text", lambda ok: Completed(text="그냥 글", usage=SYNTHETIC_USAGE), [], {"schema_mismatch": 3}),
    ("not-json-shape", lambda ok: Completed(text='{"items": "x"}', usage=SYNTHETIC_USAGE), [], {"schema_mismatch": 3}),
    ("not-json-list", lambda ok: Completed(text='[{"i": 0}]', usage=SYNTHETIC_USAGE), [], {"schema_mismatch": 3}),
    (
        "i-not-integer",
        lambda ok: Completed(text=answer((0, ok[0]), ("1", ok[1]), (2, ok[2])), usage=SYNTHETIC_USAGE),
        [],
        {"schema_mismatch": 3},
    ),
    (
        "extra-key",
        lambda ok: Completed(
            text=json.dumps({"items": [{"i": 0, "example_sentence": ok[0], "note": "x"}]}, ensure_ascii=False),
            usage=SYNTHETIC_USAGE,
        ),
        [],
        {"schema_mismatch": 3},
    ),
    (
        "missing-i",
        lambda ok: Completed(text=answer((0, ok[0]), (1, ok[1])), usage=SYNTHETIC_USAGE),
        [0, 1],
        {"missing_i": 1},
    ),
    (
        "duplicate-i",
        lambda ok: Completed(text=answer((0, ok[0]), (1, ok[1]), (1, ok[1]), (2, ok[2])), usage=SYNTHETIC_USAGE),
        [0, 2],
        {"duplicate_i": 1},
    ),
    (
        "unknown-i",
        lambda ok: Completed(
            text=answer((0, ok[0]), (1, ok[1]), (2, ok[2]), (7, "x"), (-1, "x")), usage=SYNTHETIC_USAGE
        ),
        [0, 1, 2],
        {"unknown_i": 2},
    ),
    (
        "not-text",
        lambda ok: Completed(text=answer((0, "   "), (1, ""), (2, ok[2])), usage=SYNTHETIC_USAGE),
        [2],
        {"not_text": 2},
    ),
    (
        "blank-malformed",
        lambda ok: Completed(
            text=answer((0, ok[0]), (1, "[___: 기준연도] 대비 감축"), (2, ok[2])), usage=SYNTHETIC_USAGE
        ),
        [0, 2],
        {"blank_malformed": 1},
    ),
    (
        "blank-year-digits",
        lambda ok: Completed(
            text=answer((0, "당사는 20__년까지 [____: 감축률(%)] 감축할 계획입니다."), (1, ok[1]), (2, ok[2])),
            usage=SYNTHETIC_USAGE,
        ),
        [1, 2],
        {"blank_malformed": 1},
    ),
]


@pytest.mark.parametrize(("name", "reply", "filled", "counted"), BROKEN, ids=[b[0] for b in BROKEN])
def test_t7_a_broken_answer_nulls_only_its_sentences(
    name: str, reply: Callable[[list[str]], ProviderResponse], filled: list[int], counted: dict[str, int]
) -> None:
    given, ok = three_sentences()
    mock = twice(MockProvider(), reply(ok))
    flow_run = run(given, bridge(mock))
    result = out(flow_run)
    assert examples_of(result) == [ok[n] if n in filled else None for n in range(3)] + [None]
    step = data(flow_run)
    assert step["warnings"] == warnings(**counted)
    assert step["nulled"] == 3 - len(filled)
    assert len(step["calls"]) == 1
    # 꼴이 틀린 답만 호출 층이 한 번 더 부른다(MAX_SCHEMA_RETRIES 1)
    assert len(mock.calls) == (2 if "schema_mismatch" in counted else 1)
    strict(result)


def test_t7_schema_mismatch_nulls_the_batch() -> None:
    given = with_levels(interleaved(11))
    bad = Completed(text='{"items": [{"i": 0}]}', usage=SYNTHETIC_USAGE)
    mock = twice(MockProvider(), bad).enqueue(echo)
    flow_run = run(given, bridge(mock))
    assert len(mock.calls) == 3
    want: list[str | None] = [None] * len(given["items"])
    targets = [n for n, i in enumerate(given["items"]) if i["level"] != "Low"]
    want[targets[10]] = rewritten(given["items"][targets[10]]["sentence"])
    assert examples_of(out(flow_run)) == want
    assert data(flow_run)["warnings"] == warnings(schema_mismatch=10)
    result = bridge(twice(MockProvider(), bad)).ask("x")
    assert isinstance(result, SchemaMismatch)
    assert result.issues and len(result.meta.attempts) == 2


def test_t7_a_schema_mismatch_then_a_good_answer_is_used() -> None:
    given, _ = three_sentences()
    mock = MockProvider().enqueue_text('{"items": "x"}').enqueue(echo)
    flow_run = run(given, bridge(mock))
    assert len(mock.calls) == 2
    assert examples_of(out(flow_run)) == expected(given)
    assert data(flow_run)["warnings"] == warnings()


def repeated_items(request: ProviderRequest) -> ProviderResponse:
    """실호출 RWL1(MARC-ISSUE-164)에서 본 꼴: "items" 키가 문장마다 되풀이된 글."""
    found = BLOCK.findall(user_of(request))
    parts = [
        '"items": ' + json.dumps([{"i": int(i), "example_sentence": rewritten(s)}], ensure_ascii=False)
        for i, s in found
    ]
    return Completed(text="{" + ", ".join(parts) + "}", usage=SYNTHETIC_USAGE)


def test_t7_repeated_items_keys_are_a_schema_mismatch_not_the_last_one() -> None:
    """되풀이된 키는 호출 층의 JSON 읽기가 마지막 하나로 접어 schema 를 지난다 — 흐름이 다시 보고 그 묶음을 null 로
    둔다. 조용히 마지막 문장 하나만 채우지 않고, 실행은 끝까지 간다(다음 묶음은 채운다)."""
    given = with_levels(interleaved(11))
    mock = MockProvider().enqueue(repeated_items).enqueue(echo)
    flow_run = run(given, bridge(mock))
    assert (len(mock.calls), mock.pending) == (2, 0)  # schema 를 지나므로 호출 층의 다시 부르기는 없다
    targets = [n for n, i in enumerate(given["items"]) if i["level"] != "Low"]
    want: list[str | None] = [None] * len(given["items"])
    want[targets[10]] = rewritten(given["items"][targets[10]]["sentence"])
    assert examples_of(out(flow_run)) == want
    step = data(flow_run)
    assert step["warnings"] == warnings(schema_mismatch=10)
    assert (step["nulled"], len(step["calls"])) == (10, 2)
    strict(out(flow_run))


@pytest.mark.parametrize(
    ("text", "repeated"),
    [
        ('{"items": [], "items": []}', True),
        ('{"items": [{"i": 0, "i": 1, "example_sentence": "가"}]}', True),
        ('{"items": [{"i": 0, "example_sentence": "가"}, {"i": 0, "example_sentence": "가"}]}', False),
        ('{"items": []}', False),
        ("그냥 글", False),
    ],
    ids=["top", "nested", "same-values-not-keys", "plain", "not-json"],
)
def test_t7_repeated_keys(text: str, repeated: bool) -> None:
    assert rw.repeated_keys(text) is repeated


def test_t7_over_length_is_kept_and_counted() -> None:
    given, ok = three_sentences()
    long = "가" * (rw.MAX_CHARS + 1)
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, f"  {long}\n"), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [long, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(over_length=1)
    assert data(flow_run)["nulled"] == 0


# ── T14 평가어 · T15 어미 (판 3 의 뒤 검사, MARC-ENT-288) ──────────────────────


@pytest.mark.parametrize("word", rw.COMMENTARY_WORDS)
def test_t14_a_commentary_word_nulls_the_sentence(word: str) -> None:
    given, ok = three_sentences()
    said = f"[____: 기준연도] 대비 감축 목표를 {word} 수준으로 정하겠습니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [None, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(commentary=1)
    assert data(flow_run)["nulled"] == 1
    strict(out(flow_run))


@pytest.mark.parametrize("word", rw.COMMENTARY_WORDS)
def test_t14_a_word_already_in_the_sentence_is_kept(word: str) -> None:
    given, _ = three_sentences()
    given["items"][0]["sentence"] = f"가상 문장의 감축은 {word} 수준으로 정하겠습니다."
    said = f"[____: 기준연도] 대비 감축은 {word} 수준으로 정하겠습니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said)))))
    assert examples_of(out(flow_run))[0] == said
    assert data(flow_run)["warnings"] == warnings(missing_i=2)


def test_t14_an_inflected_word_is_caught() -> None:
    given, ok = three_sentences()
    said = "[____: 기준연도] 대비 감축 목표를 밝히는 것이 필요한 상황입니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, ok[0]), (1, said), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [ok[0], None, ok[2], None]
    assert data(flow_run)["warnings"] == warnings(commentary=1)


def test_t14_commentary_comes_before_over_length() -> None:
    """평가어와 200자 넘김이 같이 있으면 null 쪽(commentary)만 센다 — 검사 차례가 고정이다."""
    given, ok = three_sentences()
    said = "추정 " + "가" * rw.MAX_CHARS + "입니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [None, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(commentary=1)


@pytest.mark.parametrize(
    ("text", "sentence", "found"),
    [
        ("감축이 필요성 있게 정해진다.", "감축을 정한다.", True),
        ("불필요한 배출을 줄인다.", "배출을 줄인다.", True),  # 한계: 부분 글자 일치라 「불필요」도 걸린다
        ("배출을 줄인다.", "배출을 줄이는 것이 바람직하다.", False),
        ("[____: 기준연도] 대비 배출을 줄인다.", "배출을 줄인다.", False),
    ],
    ids=["inflected", "false-positive-limit", "no-word", "blank-only"],
)
def test_t14_commentary(text: str, sentence: str, found: bool) -> None:
    assert rw.commentary(text, sentence) is found


def test_t15_an_other_ending_is_kept_and_counted() -> None:
    given, ok = three_sentences()
    said = "[____: 기준연도] 대비 모든 사업장에서 탄소중립을 달성한다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [said, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(ending_mismatch=1)
    assert data(flow_run)["nulled"] == 0


def test_t15_the_same_ending_is_not_counted() -> None:
    given, ok = three_sentences()
    said = "[____: 기준연도] 대비 모든 사업장에서 탄소중립을 달성할 계획입니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [said, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings()


@pytest.mark.parametrize(
    "sentence",
    ["가상 사업장의 재생에너지, 폐기물 감축 등", "가상 사업장의 배출을 줄였다(주1)."],
    ids=["ends-with-deung", "footnote-in-parens"],
)
def test_t15_an_undecided_sentence_is_not_counted(sentence: str) -> None:
    given, _ = three_sentences()
    given["items"][0]["sentence"] = sentence
    said = "[____: 기준연도] 대비 가상 사업장의 배출을 줄였습니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said)))))
    assert examples_of(out(flow_run))[0] == said
    assert data(flow_run)["warnings"] == warnings(missing_i=2)


@pytest.mark.parametrize(
    ("text", "kind"),
    [
        ("달성하겠습니다.", rw.HAPSYO),
        ("친환경 기업입니다 ", rw.HAPSYO),
        ("달성한다.", rw.HAERA),
        ("달성할 계획이다).", rw.HAERA),
        ("감축 등", None),
        ("줄였다(주1).", None),
        ("[____: 기준연도]", None),
    ],
    ids=["hapsyo", "hapsyo-no-period", "haera", "haera-close-paren", "deung", "footnote", "blank-end"],
)
def test_t15_ending(text: str, kind: str | None) -> None:
    assert rw.ending(text) == kind


# ── T16 빈칸 밖 숫자 (판 4 의 뒤 검사, MARC-ENT-309) ─────────────────────────────


def test_t16_a_value_outside_the_blanks_is_kept_and_counted() -> None:
    given, ok = three_sentences()
    said = "당사는 [____: 기준연도] 대비 2030년까지 모든 사업장에서 탄소중립을 달성할 계획입니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [said, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(value_outside_blank=1)
    assert data(flow_run)["nulled"] == 0
    strict(out(flow_run))


@pytest.mark.parametrize(
    "said",
    [
        "당사는 [____: 기준연도] 대비 [____: 감축률(%)] 감축할 계획입니다.",
        "당사는 [____: 2차 목표연도]까지 [____: 적용 범위(Scope 1·2 등)] 배출량을 줄일 계획입니다.",
        "당사는 [____: 목표연도]까지 Scope 1·2 배출량을 줄일 계획입니다.",
        "당사는 [____: 목표연도]까지 Scope 1, 2 및 3 배출량을 줄일 계획입니다.",
        "당사는 [____: 목표연도]까지 ISO 14001 인증을 받을 계획입니다.",
        "당사는 [____: 목표연도]까지 ISO 14064-1 에 따라 배출량을 산정할 계획입니다.",
    ],
    ids=["number-free-blank", "number-in-blank", "scope-dot", "scope-comma-and", "iso", "iso-part"],
)
def test_t16_numbers_in_blanks_and_names_are_not_counted(said: str) -> None:
    given, ok = three_sentences()
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [said, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings()


def test_t16_a_name_and_a_value_together_are_counted() -> None:
    given, ok = three_sentences()
    said = "당사는 [____: 목표연도]까지 Scope 1 배출량 30%를 줄일 계획입니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [said, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(value_outside_blank=1)


def test_t16_a_nulled_sentence_is_not_counted() -> None:
    """평가어로 null 된 문장은 숫자 경고를 세지 않는다 — 검사 차례가 고정이다(숫자 검사는 채움이 확정된 문장에만)."""
    given, ok = three_sentences()
    said = "2030년까지 탄소중립을 달성할 것으로 추정됩니다."
    flow_run = run(given, bridge(MockProvider().enqueue_text(answer((0, said), (1, ok[1]), (2, ok[2])))))
    assert examples_of(out(flow_run)) == [None, ok[1], ok[2], None]
    assert data(flow_run)["warnings"] == warnings(commentary=1)


def test_t16_the_prompt_names_are_not_values() -> None:
    """판 4 가 값이 아니라고 든 이름(「Scope 1·2」「ISO 14001」)을 흐름도 값으로 세지 않는다(한쪽만 바뀌지 않게)."""
    text = PackagePromptStore().get(parse_prompt_id(rw.PROMPT_ID)).system[0].text
    (line,) = [line for line in text.split("\n") if "이름에 든 숫자는 값이 아니니" in line]
    names = re.findall(r"「([^」]+)」", line)
    assert names == ["Scope 1·2", "ISO 14001"]
    assert not any(rw.value_outside_blank(name) for name in names)


@pytest.mark.parametrize(
    ("text", "found"),
    [
        ("2030년까지 줄인다.", True),
        ("[____: 목표연도]까지 줄인다.", False),
        ("[____: 감축률(%)]만큼 30% 줄인다.", True),
        ("Scope1·2·3 배출량", False),
        ("Scope 1 · 2 배출량", False),
        ("Scope 3 배출량", False),
        ("Scope 1 및 2 배출량", False),
        ("ISO14001 인증", False),
        ("ISO 14001:2015 인증", True),  # 한계: 판 연도는 두 꼴 밖이라 값으로 센다
        ("２０３０년까지 줄인다.", True),
        ("이천삼십년까지 줄인다.", False),  # 한계: 한글로 쓴 수는 세지 못한다
    ],
    ids=[
        "year",
        "blank-only",
        "blank-and-value",
        "scope-no-space",
        "scope-spaced-dot",
        "scope-one",
        "scope-and",
        "iso-no-space",
        "iso-year-limit",
        "full-width",
        "hangul-number-limit",
    ],
)
def test_t16_value_outside_blank(text: str, found: bool) -> None:
    assert rw.value_outside_blank(text) is found


@pytest.mark.parametrize(
    "make",
    [
        lambda: ProviderFailed(status=500, retryable=True, message="모의 장애", meta=META),
        lambda: TimedOut(message="모의 시간 초과", meta=META),
        lambda: BudgetExceeded(limit_usd=1.0, spent_usd=1.0, scope=Scope(), meta=META),
    ],
    ids=["provider_error", "timeout", "budget_exceeded"],
)
def test_t7_provider_side_failures_fail_the_step(make: Callable[[], LlmResult[rw.RewriteAnswer]]) -> None:
    given, _ = three_sentences()
    kind = make().kind
    with pytest.raises(FlowStepFailed) as failed:
        run(given, Canned(make))
    assert failed.value.step == "rewrite"
    assert isinstance(failed.value.__cause__, RuntimeError)
    assert str(failed.value.__cause__).endswith(f": {kind}")


# ── T8 빈칸 정규식 ────────────────────────────────────────────────────────────


@pytest.mark.parametrize("blank", ["[____: 기준연도]", "[____: 적용 범위(Scope 1·2 등)]", "[____: 감축률(%)]"])
def test_t8_the_blank_form_matches(blank: str) -> None:
    assert rw.BLANK.fullmatch(blank) is not None
    assert not rw.blank_malformed(f"앞 {blank} 뒤")


@pytest.mark.parametrize("bad", ["[___: 기준연도]", "[____:기준연도]", "[____: ]", "[____]", "____ 대비"])
def test_t8_other_blank_forms_break_the_rule(bad: str) -> None:
    assert rw.BLANK.fullmatch(bad) is None
    assert rw.blank_malformed(f"앞 {bad} 뒤")


def test_t8_the_draft_example_keeps_the_rule() -> None:
    assert len(rw.BLANK.findall(DRAFT_EXAMPLE)) == 4
    assert not rw.blank_malformed(DRAFT_EXAMPLE)


# ── T9 부르기 실패와 이어 돌기 ─────────────────────────────────────────────────


def test_t9_refused_and_truncated_null_their_batch_only() -> None:
    given = with_levels(interleaved(22))
    mock = (
        MockProvider()
        .enqueue(Refusal(text="거절", category="policy", usage=SYNTHETIC_USAGE))
        .enqueue(Truncated(text="{", usage=SYNTHETIC_USAGE))
        .enqueue(echo)
    )
    flow_run = run(given, bridge(mock))
    targets = [n for n, i in enumerate(given["items"]) if i["level"] != "Low"]
    want: list[str | None] = [None] * len(given["items"])
    for n in targets[20:]:
        want[n] = rewritten(given["items"][n]["sentence"])
    assert examples_of(out(flow_run)) == want
    assert data(flow_run)["warnings"] == warnings(refused=10, truncated=10)
    assert data(flow_run)["nulled"] == 20


def test_t9_a_provider_error_fails_the_step_and_resume_calls_only_the_rest() -> None:
    given = with_levels(interleaved(22))
    whole = MockProvider().enqueue(echo).enqueue(echo).enqueue(echo)
    once = run(given, bridge(whole))

    broken = MockProvider().enqueue(echo).enqueue(ProviderError(status=500, retryable=True, message="모의 장애"))
    with pytest.raises(FlowStepFailed) as failed:
        run(given, bridge(broken))
    assert failed.value.step == "rewrite"
    assert str(failed.value.__cause__).endswith(": provider_error")
    assert len(broken.calls) == 2
    partial = failed.value.partial
    assert partial is not None and partial["done"] == 1

    rest = MockProvider().enqueue(echo).enqueue(echo)
    resumed = run_flow(
        rw.FLOW,
        rw.RewriteInputs(result=given),
        rw.RewriteAdapters(llm=bridge(rest)),
        start_at="rewrite",
        resume=partial,
    )
    assert len(rest.calls) == 2
    assert [user_of(r) for r in rest.calls] == [user_of(r) for r in whole.calls[1:]]
    assert out(resumed) == out(once)
    assert data(resumed)["examples"] == data(once)["examples"]
    assert data(resumed)["warnings"] == data(once)["warnings"]
    assert [c["batch"] for c in data(resumed)["calls"]] == [0, 1, 2]


# ── T10 dry-run · T11 요청 꼴 · T12 입력 거절 · T13 user 덩이 ──────────────────


def test_t10_dry_run_calls_no_provider() -> None:
    given = with_levels(interleaved(22))
    mock = MockProvider()
    flow_run = run(given, bridge(mock), dry_run=True)
    assert mock.calls == []
    step = data(flow_run)
    dry = step["dry_run"]
    assert dry["requests"] == step["batches"] == 3
    assert dry["model"] == "mock-synthetic"
    assert dry["input_tokens"] > 0
    assert dry["max_output_tokens"] == 3 * rw.MAX_OUTPUT_TOKENS
    assert dry["cost_upper_bound_usd"] > 0
    assert step["warnings"] is None
    assert step["nulled"] is None
    assert step["calls"] == []
    result = out(flow_run)
    assert examples_of(result) == [None] * len(given["items"])
    strict(result)
    assert [f.name for f in flow_run.output.files] == [rw.REPORT_FILE]


def test_t10_estimate_counts_the_same_request_as_ask() -> None:
    used = bridge(MockProvider())
    sentences = rw.user_text(normal()["items"][:3])
    request: CallRequest[rw.RewriteAnswer] = used.request(sentences)
    assert (request.prompt, request.route, request.vars) == (rw.PROMPT_ID, "mock", {"sentences": sentences})
    assert (request.schema, request.schema_name, request.max_schema_retries) == (rw.RewriteAnswer, "rewrite", 1)
    report = used.estimate(sentences)
    sent = cast("dict[str, Any]", report.request)
    assert sent["user"] == [{"type": "text", "text": sentences}]
    assert cast("dict[str, Any]", sent["jsonSchema"])["name"] == "rewrite"


def test_t11_the_request_shape() -> None:
    given = normal()
    mock = MockProvider().enqueue(echo)
    run(given, bridge(mock))
    (sent,) = mock.calls
    template = PackagePromptStore().get(parse_prompt_id(rw.PROMPT_ID))
    assert sent.temperature is None
    assert sent.max_output_tokens == rw.MAX_OUTPUT_TOKENS
    assert sent.system == (SystemSegment(text=template.system[0].text, cache=False),)
    assert sent.json_schema is not None
    assert sent.json_schema.name == "rewrite"
    schema = sent.json_schema.schema
    assert (schema["type"], schema["required"], schema["additionalProperties"]) == ("object", ["items"], False)
    items = cast("dict[str, Any]", schema["properties"])["items"]
    assert items["type"] == "array"
    item = cast("dict[str, Any]", schema["$defs"])["RewriteAnswerItem"]
    assert item["required"] == ["i", "example_sentence"] and item["additionalProperties"] is False
    assert items["items"] == {"$ref": "#/$defs/RewriteAnswerItem"}
    assert user_of(sent) == rw.user_text(given["items"][:3])


# ── T17 모델 (MARC-ENT-314: 대체표현은 gpt-6-luna, temperature 없음 — E0 는 gpt-4.1-mini 그대로) ─────────


def real_bridge(mock: MockProvider, sink: MemorySink | None = None) -> rw.RewriteBridge:
    """저장소 정본 models.json(가상 모델 없음)과 openai 자리의 모의 공급사, 기본 경로 — 실제 네트워크·키 0."""
    used = LlmClient(
        config=load_config(default_config_sources(synthetic=False)),
        providers={"openai": mock},
        prompts=PackagePromptStore(),
        log=sink or MemorySink(),
    )
    return rw.RewriteBridge(used, tags=TAGS)


def test_t17_the_route_is_gpt6_luna_alone_and_e0_keeps_gpt41_mini() -> None:
    config = load_config(default_config_sources(synthetic=False))
    assert config.routes[rw.CHAT_ROUTE] == ("gpt-6-luna",)
    assert config.routes[colab_e0.CHAT_ROUTE] == ("gpt-4.1-mini",)
    assert "gpt-6-luna" in TEMPERATURE_UNSUPPORTED_MODELS
    assert real_bridge(MockProvider("openai")).request("x").temperature is None


def test_t17_the_default_bridge_sends_no_temperature_to_gpt6_luna() -> None:
    given = normal()
    mock = MockProvider("openai").enqueue(echo)
    flow_run = run(given, real_bridge(mock))
    (sent,) = mock.calls
    assert (sent.api_model_id, sent.temperature) == ("gpt-6-luna", None)
    assert examples_of(out(flow_run)) == expected(given)


def test_t17_dry_run_estimates_gpt6_luna() -> None:
    mock = MockProvider("openai")
    flow_run = run(with_levels(interleaved(22)), real_bridge(mock), dry_run=True)
    assert mock.calls == []
    dry = data(flow_run)["dry_run"]
    assert (dry["requests"], dry["model"]) == (3, "gpt-6-luna")
    assert dry["cost_upper_bound_usd"] > 0


def test_t17_a_temperature_on_the_route_fails_before_the_provider() -> None:
    """luna 경로에 temperature 를 실으면 공급사를 부르기 전에 LlmConfigError(흐름이 싣지 않는 까닭)."""
    mock = MockProvider("openai").enqueue(echo)
    used = real_bridge(mock)
    with pytest.raises(LlmConfigError, match="temperature"):
        used.client.call(dataclasses.replace(used.request("x"), temperature=0.0))
    assert mock.calls == []


def _dry_run_result(r: dict[str, Any]) -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads((EXAMPLES / "result-dry-run.json").read_text(encoding="utf-8")))


def _first_item(r: dict[str, Any], **changed: object) -> dict[str, Any]:
    item = {
        k: v for k, v in cast("dict[str, Any]", r["items"][0]).items() if k not in changed or changed[k] is not None
    }
    item.update({k: v for k, v in changed.items() if v is not None})
    return {**r, "items": [item]}


SPOILS: list[tuple[str, Callable[[dict[str, Any]], dict[str, Any]]]] = [
    ("dry-run-result", _dry_run_result),
    ("other-version", lambda r: {**r, "schemaVersion": "greenwash.result@2"}),
    ("items-not-list", lambda r: {**r, "items": "x"}),
    ("missing-field", lambda r: _first_item(r, fixParagraph=None)),
    ("unknown-level", lambda r: _first_item(r, level="Top")),
    ("tags-not-list", lambda r: _first_item(r, riskTags="근거 부족")),
]


@pytest.mark.parametrize("spoil", [s[1] for s in SPOILS], ids=[s[0] for s in SPOILS])
def test_t12_inputs_are_refused(spoil: Callable[[dict[str, Any]], dict[str, Any]]) -> None:
    mock = MockProvider().enqueue(echo)
    with pytest.raises(ValueError):
        run(spoil(normal()), bridge(mock))
    assert mock.calls == []


def test_t13_user_block_bytes() -> None:
    item = {
        "sentence": "당사는 2030년 탄소중립을 달성할 것입니다.",
        "level": "High",
        "riskTags": ["근거 부족", "과장"],
        "confirmedInEvidence": [],
        "missingFields": ["기준연도", "적용 범위"],
        "fixParagraph": "기준연도와 적용 범위를 함께 밝히는 보완이 필요합니다.",
    }
    assert rw.user_block(0, item) == (
        "[문장 i=0]\n"
        "원문: 당사는 2030년 탄소중립을 달성할 것입니다.\n"
        "리스크 등급: High\n"
        "위험 유형: 근거 부족, 과장\n"
        "근거에서 확인된 사실: 없음\n"
        "빠진 항목:\n"
        "- 기준연도\n"
        "- 적용 범위\n"
        "수정 방향: 기준연도와 적용 범위를 함께 밝히는 보완이 필요합니다."
    )
    second = {**item, "sentence": "{중괄호} {{변수}} 문장", "level": "Mid", "confirmedInEvidence": ["계약 체결"]}
    assert rw.user_text([item, second]) == rw.user_block(0, item) + "\n\n" + rw.user_block(1, second)
    assert rw.user_block(1, second).startswith("[문장 i=1]\n원문: {중괄호} {{변수}} 문장\n리스크 등급: Mid\n")
    assert "근거에서 확인된 사실:\n- 계약 체결\n빠진 항목:" in rw.user_block(1, second)
