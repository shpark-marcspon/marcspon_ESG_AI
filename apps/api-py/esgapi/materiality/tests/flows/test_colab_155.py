"""흐름 materiality.colab@155 를 끝까지(발주서 §3 S2·S3·S7·S9·S11·S13·S14): 코랩 셀 차례·수, 요청의 칸, 실제로 보내는 글
(IR1a 엔진 글과 바이트 같음), 결과 꼴·1부 엑셀, 호출 기록의 손셈, NaN 답, 순수. 공급사는 모의만(실호출 0)."""

import ast
import io
import json
import math
import re
from pathlib import Path
from typing import Any, cast

import pytest
from openpyxl import load_workbook

import esgapi.materiality.flows as flows_package
from esgapi.core.flows.types import FlowInputError
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import ApproximateLocation, ProviderRequest, TextPart, WebSearchTool
from esgapi.materiality.contracts import shapes, wire
from esgapi.materiality.engines.colab_155 import constants, prompts, whitelists
from esgapi.materiality.engines.colab_155.inputs import industry_text
from esgapi.materiality.flows import colab_155
from esgapi.materiality.outputs import xlsx
from esgapi.materiality.tests.flows import support
from esgapi.materiality.tests.flows.support import CALL_USD, SEARCH_USD, USAGE


def run_all(given: dict[str, Any], *, hosted: int = 1) -> tuple[MockProvider, support.Spy, Any]:
    mock = MockProvider("openai")
    support.script_all(mock, given, hosted=hosted)
    llm = support.spy(mock)
    done = support.run(support.inputs(received=given), llm)
    assert mock.pending == 0
    return mock, llm, done


def user_text(request: ProviderRequest) -> str:
    (part,) = request.user
    assert isinstance(part, TextPart)
    return part.text


def system_text(request: ProviderRequest) -> str:
    (segment,) = request.system
    assert segment.cache is False
    return segment.text


def expected_messages(given: dict[str, Any]) -> list[tuple[str, str]]:
    """IR1a 엔진이 낸 (system, user = 접두 + JOIN + 가변) — 코랩 셀 17 → 20 → 22 차례."""
    industry = wire.engine_industry(given)
    topics = wire.engine_topics(given)
    _, raw = whitelists.whitelist_for(given["sector"])
    join = colab_155.USER_JOIN
    out = [
        (
            prompts.regulation_system(raw),
            prompts.REGULATION_USER_PREFIX
            + join
            + prompts.regulation_user(
                t["topic"], t["description"], industry_text(industry), given["geoScope"], given["mainLanguage"]
            ),
        )
        for t in topics
    ]
    out.append(
        (
            prompts.KEYWORDS_SYSTEM,
            prompts.KEYWORDS_USER_PREFIX
            + join
            + prompts.keywords_user(industry, given["dateRange"], given["mainLanguage"], topics),
        )
    )
    out += [
        (
            prompts.CONTROVERSY_SYSTEM,
            prompts.CONTROVERSY_USER_PREFIX
            + join
            + prompts.controversy_user(
                t["topic"],
                t["description"],
                industry,
                given["geoScope"],
                given["mainLanguage"],
                f"{t['topic']} 키워드 1, {t['topic']} 키워드 2",
            ),
        )
        for t in topics
    ]
    return out


# ── S2 끝까지(토픽 3) ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("industries", [1, 3])
def test_seven_calls_in_colab_order_with_the_engine_text_byte_for_byte(industries: int) -> None:
    given = support.received(industries=industries)
    mock, llm, _ = run_all(given)
    assert len(mock.calls) == 7  # 1 + 2 × 토픽
    assert [r.prompt for r in llm.tool_requests] == [
        *["materiality/regulation@1"] * 3,
        "materiality/keywords@1",
        *["materiality/controversy@1"] * 3,
    ]
    sent = [(system_text(call), user_text(call)) for call in mock.calls]
    assert sent == expected_messages(given)
    # 비금융권 → 셀 73 판이 규제 system 의 [8] 에 낀다.
    assert sent[0][0] == prompts.regulation_system(whitelists.WHITELIST_CELL73)
    assert prompts.REGULATION_USER_PREFIX + "\n\n" in sent[0][1]


def test_every_request_carries_the_colab_body_fields() -> None:
    mock, llm, _ = run_all(support.received())
    location = WebSearchTool(search_context_size="low", user_location=ApproximateLocation(country="KR"))
    for call in mock.calls:
        assert call.api_model_id == "gpt-4o"
        assert call.temperature == 0.1
        assert call.tool_choice == "auto"
        assert call.system_placement == "input_message"
        assert call.max_output_tokens == 16_384
        assert call.tools == (location,)
        assert call.max_hosted_calls is None
        assert call.parallel_tool_calls is None
        assert call.turns == ()
    for request in llm.tool_requests:
        assert request.route == "standard-openai-4o"
        assert request.max_steps == 1
        assert request.max_cost_usd is None
        assert request.max_hosted_calls is None
        assert request.timeout_ms == 600_000
        assert request.tags == support.TAGS
        assert request.tools == (location,)  # 키워드로 지은 user_location
    assert colab_155.USER_JOIN == "\n\n"
    assert constants.SEARCH_CONTEXT_SIZE == "low"


def test_the_result_shape_settings_and_excel() -> None:
    given = support.received()
    _, _, done = run_all(given)
    result = support.result(done)
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE].validate_python(result, strict=True)
    assert result["settings"] == {
        "model": "gpt-4o",
        "temperature": "0.1",
        "searchContextSize": "low",
        "promptIds": {
            "regulation": "materiality/regulation@1",
            "keywords": "materiality/keywords@1",
            "controversy": "materiality/controversy@1",
        },
    }
    assert result["scope"]["whitelist"] == "cell73"
    topics = cast("list[dict[str, Any]]", result["part1"]["topics"])
    assert [(t["regulation"]["status"], t["controversy"]["status"]) for t in topics] == [("done", "done")] * 3
    assert topics[0]["regulation"]["items"][0]["primary_url"] == "https://example.com/r"  # utm 지움(엔진)
    assert topics[0]["regulation"]["items"][0]["region"] == "KR"
    assert topics[2]["keywordStr"] == "가상토픽 셋 키워드 1, 가상토픽 셋 키워드 2"
    assert result["part1"]["keywords"]["status"] == "done"
    assert [w["code"] for w in result["warnings"]] == ["subtopic_autofilled", "subtopic_autofilled"]

    (report,) = done.output.files
    assert (report.name, report.media_type) == (xlsx.FILENAME, xlsx.MEDIA_TYPE)
    book = load_workbook(io.BytesIO(report.content))
    assert book.sheetnames == [xlsx.SHORTLIST, xlsx.RAW_JSON]
    sheet = book[xlsx.SHORTLIST]
    assert [sheet[f"C{r}"].value for r in (4, 5, 6)] == sorted(support.topic_names(given))  # 코랩 셀 33: 이름 차례
    raw = "".join(str(row[0].value) for row in book[xlsx.RAW_JSON].iter_rows())
    assert json.loads(raw) == wire.websearch_payload(result)


def test_the_call_records_and_the_running_total_by_hand() -> None:
    _, _, done = run_all(support.received(), hosted=2)
    calls = [call for phase in colab_155.PHASES for call in done.steps[phase].data["calls"]]
    per_call = round(CALL_USD + 2 * SEARCH_USD, 6)  # 0.045 + 0.02 = 0.065
    assert [(c["phase"], c["ending"], c["hostedCalls"], c["costUsd"], c["model"], c["attempts"]) for c in calls] == [
        *[("regulation", "done", 2, per_call, "gpt-4o", 1)] * 3,
        ("keywords", "done", 2, per_call, "gpt-4o", 1),
        *[("controversy", "done", 2, per_call, "gpt-4o", 1)] * 3,
    ]
    names = support.topic_names(support.received())
    assert [c["topic"] for c in calls] == [*names, None, *names]
    assert done.steps["regulation"].data["spentUsd"] == pytest.approx(3 * per_call)
    assert done.steps["keywords"].data["spentUsd"] == pytest.approx(4 * per_call)
    assert done.steps["controversy"].data["spentUsd"] == pytest.approx(7 * per_call)
    assert set(done.steps["report"].data) == {"results"}


def test_the_financial_sector_picks_cell_71() -> None:
    mock, _, done = run_all(support.received(sector="financial"))
    assert system_text(mock.calls[0]) == prompts.regulation_system(whitelists.WHITELIST_CELL71)
    assert support.result(done)["scope"]["whitelist"] == "cell71"


# ── S3 토픽 15 ─────────────────────────────────────────────────────────────────────────────


def test_fifteen_topics_make_thirty_one_calls_and_each_topic_gets_its_keywords() -> None:
    given = support.received(topics=15)
    mock, _, done = run_all(given)
    assert len(mock.calls) == 31
    names = support.topic_names(given)
    controversy_users = [user_text(call) for call in mock.calls[16:]]
    for name, text in zip(names, controversy_users, strict=True):
        assert f"keyword: {name} 키워드 1, {name} 키워드 2\n" in text
        assert f"topic_name: {name}\n" in text
    result = support.result(done)
    assert [t["topic"] for t in result["part1"]["topics"]] == names
    # 경고 차례: load(서브토픽, 토픽 차례) — 서브토픽이 있는 것은 「가상토픽 하나」뿐.
    assert [(w["code"], w["topic"]) for w in result["warnings"]] == [("subtopic_autofilled", n) for n in names[1:]]


# ── S7 검색 0회 ────────────────────────────────────────────────────────────────────────────


def test_no_search_is_still_done_without_warnings_and_costs_tokens_only() -> None:
    _, _, done = run_all(support.received(), hosted=0)
    calls = done.steps["regulation"].data["calls"]
    assert [(c["ending"], c["hostedCalls"], c["costUsd"]) for c in calls] == [("done", 0, CALL_USD)] * 3
    result = support.result(done)
    assert {t["regulation"]["status"] for t in result["part1"]["topics"]} == {"done"}
    assert [w["code"] for w in result["warnings"]] == ["subtopic_autofilled", "subtopic_autofilled"]


# ── S9 NaN ─────────────────────────────────────────────────────────────────────────────────


def test_a_nan_answer_finishes_and_comes_out_as_null() -> None:
    """json.loads 가 받는 NaN·Infinity 가 모델 JSON 에 있어도 단계 왕복(allow_nan=False)이 깨지지 않는다 — 결과는
    dump_json 판이라 null(감독 10-23, MARC-ISSUE-345 1)."""
    given = support.received(topics=1)
    mock = MockProvider("openai")
    nan_answer = '{"topic_name": "가상토픽 하나", "results": {"KR": [{"title": "가상", "score": NaN}]}, "n": Infinity}'
    mock.enqueue_text(nan_answer, USAGE)
    mock.enqueue_text(support.keywords_answer(["가상토픽 하나"]), USAGE)
    mock.enqueue_text(support.controversy_answer("가상토픽 하나"), USAGE)
    done = support.run(support.inputs(received=given), support.spy(mock))
    result = support.result(done)
    regulation = result["part1"]["topics"][0]["regulation"]
    assert regulation["status"] == "done"
    assert regulation["parsed"]["results"]["KR"][0]["score"] is None
    assert regulation["parsed"]["n"] is None
    (report,) = done.output.files
    raw = "".join(str(row[0].value) for row in load_workbook(io.BytesIO(report.content))[xlsx.RAW_JSON].iter_rows())
    assert "NaN" not in raw and "Infinity" not in raw
    assert not any(isinstance(v, float) and not math.isfinite(v) for v in _floats(result))


def _floats(value: Any) -> list[Any]:
    if isinstance(value, dict):
        return [x for v in cast("dict[str, Any]", value).values() for x in _floats(v)]
    if isinstance(value, list):
        return [x for v in cast("list[Any]", value) for x in _floats(v)]
    return [value]


# ── S13 순수 · S14 이름·키 ─────────────────────────────────────────────────────────────────


FLOWS = Path(flows_package.__file__).parent


def test_the_flow_reads_no_settings_env_or_sdk() -> None:
    for path in sorted(FLOWS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        names = {alias.name for node in ast.walk(tree) if isinstance(node, ast.Import) for alias in node.names}
        names |= {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
        # IR4 ②: prompt_model_155 는 칸 기본값을 LlmConfig 에서 읽는다 — 설정 파일 읽기가 아니라 형 하나(발주서 1-2 B1)
        names -= {"esgapi.core.llm.config"} if path.name == "prompt_model_155.py" else set()
        bad = sorted(n for n in names if n.split(".")[0] in {"os", "openai", "django", "anthropic"} or ".config" in n)
        assert bad == [], f"{path.name}: {bad}"
        assert "environ" not in path.read_text(encoding="utf-8")


def test_made_up_inputs_and_answers_carry_no_key_shapes() -> None:
    given = support.received(topics=15)
    texts = [
        json.dumps(given, ensure_ascii=False),
        support.keywords_answer(support.topic_names(given)),
        *(support.regulation_answer(n) for n in support.topic_names(given)),
        *(support.controversy_answer(n) for n in support.topic_names(given)),
        Path(support.__file__).read_text(encoding="utf-8"),
    ]
    for text in texts:
        assert re.search(r"sk-[A-Za-z0-9_-]{16,}", text) is None
    assert all(n.startswith("가상") for n in support.topic_names(given))
    assert given["company"]["name"].startswith("가상")


# ── S11 dry-run 위끝 ───────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(("topics", "assumed"), [(2, 1), (3, 2)])
def test_the_estimate_calls_no_provider_and_its_upper_bounds_add_up_by_hand(topics: int, assumed: int) -> None:
    mock = MockProvider("openai")
    llm = support.spy(mock)
    given = support.inputs(received=support.received(topics=topics))
    got = colab_155.estimate(given, llm, assumed_searches_per_call=assumed)
    assert mock.calls == []
    calls = 1 + 2 * topics
    assert len(llm.dry_runs) == calls
    assert all(r.max_hosted_calls == assumed for r in llm.dry_runs)  # 위끝 셈에만 건수를 둔다
    assert got["maxProviderCalls"] == 2 * calls
    assert {p: v["calls"] for p, v in got["perPhase"].items()} == {
        "regulation": topics,
        "keywords": 1,
        "controversy": topics,
    }
    # 손셈: 호출 하나 = 입력 어림 × 2.5/1M + 출력 상한 16,384 × 10/1M + 건수 × 0.01(걸음 1)
    bounds: list[float] = []
    for request in llm.dry_runs:
        report = llm.client.dry_run_tools(request)
        assert report.estimate.max_output_tokens == 16_384
        bounds.append(report.estimate.input_tokens * 2.5 / 1e6 + 16_384 * 10 / 1e6 + assumed * SEARCH_USD)
    assert got["totalUpperBoundUsd"]["withoutRetry"] == pytest.approx(sum(bounds), abs=1e-6)
    assert got["totalUpperBoundUsd"]["withRetry"] == pytest.approx(2 * sum(bounds), abs=1e-6)
    assert got["unestimated"] == ["tool_outputs", "web_search_content", "controversy_keywords"]
    assert len(got["assumptions"]) == 5


def test_the_estimate_uses_no_keywords_for_controversy_and_rejects_bad_inputs() -> None:
    mock = MockProvider("openai")
    llm = support.spy(mock)
    colab_155.estimate(support.inputs(received=support.received(topics=1)), llm)
    assert "keyword: (키워드 없음)\n" in llm.dry_runs[-1].vars["user"]
    for bad in (0, -1, True, 1.5):
        with pytest.raises(FlowInputError):
            colab_155.estimate(support.inputs(), llm, assumed_searches_per_call=bad)  # type: ignore[arg-type]
    with pytest.raises(FlowInputError):
        colab_155.estimate(support.inputs(max_cost_usd=0.0), llm)
    assert mock.calls == []
