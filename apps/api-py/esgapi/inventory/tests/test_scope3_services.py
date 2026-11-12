"""Scope 3 분류의 쓰임새(`services.scope3_classify`)를 DB 없이, 소켓 문지기 아래에서 잰다.

분류는 DB 를 읽지 않는다. 그래서 `django_db` 표시 없이 부를 수 있고, 그러면 문지기(tests/conftest.py)가 걸린다:
이름 풀이나 연결을 시도하면 테스트가 깨지고 시도한 주소가 `blocked_network` 에 남는다.
(업무 층의 경로 테스트 test_scope3_api.py 에는 문지기가 걸리지 않는다. DB 연결도 소켓이라서다.)

「실호출의 길이 없다」를 말하는 것은 셋이다: 경로 상수(`SCOPE3_ROUTE = "mock"`), 부르기 전의 경로 검사(모의 공급사의
경로가 아니면 503 `llm_not_configured`), 이 파일의 막힌 시도 0.
"""

from dataclasses import replace

import pytest

from esgapi.config.env import LlmSettings
from esgapi.core.exceptions import ApplicationError
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.setup import build_client, llm_client
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.inventory.engines.scope3.llm_first_1.llm_steps import CLASSIFY_PROMPT
from esgapi.inventory.service.services import inventory as services
from esgapi.inventory.tests.scope3_llm_support import classification, mock_client, user_texts
from esgapi.inventory.tests.scope3_support import row

COMPANY = 7  # 순수 층의 회사 id(DB 가 없다). 경로는 세션의 company_id 를 넘긴다


def use(monkeypatch: pytest.MonkeyPatch, client: LlmClient) -> None:
    """이음매(`scope3_gateway`)를 그 클라이언트로 바꾼다."""
    monkeypatch.setattr(services, "scope3_gateway", lambda: client)


def not_configured(error: pytest.ExceptionInfo[ApplicationError]) -> None:
    assert (error.value.kind, error.value.code) == ("unavailable", "llm_not_configured")
    assert error.value.message == "생성 모델 경로 mock 가 이 서버에 준비되어 있지 않다"


def test_the_route_is_the_mock_route_and_is_one_constant() -> None:
    assert services.SCOPE3_ROUTE == "mock"
    assert services.SCOPE3_PROVIDER == "mock"
    assert services.SCOPE3_MAX_GROUPS == 20
    assert frozenset({"ok", "unverified"}) == services.SCOPE3_DEFAULT_LICENSES


def test_classify_goes_through_the_mock_provider_with_no_network(
    monkeypatch: pytest.MonkeyPatch, blocked_network: list[object]
) -> None:
    mock = MockProvider()
    log = MemorySink()
    use(monkeypatch, mock_client(mock, log))
    mock.enqueue_text(classification(1, ["steel", "sheet"])).enqueue_text(classification("other"))
    rows = [
        row("합성 강판", row_id="a", quantity="13579", amount="24680000"),
        row("합성강판", row_id="b"),
        row("폐기물 처리", row_id="c"),
    ]
    result = services.scope3_classify(rows=rows, company_id=COMPANY)
    assert isinstance(result, services.Scope3Classified)
    first, second = result.groups
    assert isinstance(first, services.Scope3GroupClassified)
    assert (first.key, first.row_ids) == ("합성강판|kg|", ("a", "b"))
    assert (first.classification.category, first.classification.keywords) == (1, ("steel", "sheet"))
    assert isinstance(second, services.Scope3GroupClassified)
    assert second.classification.category == "other"
    # 묶음마다 한 번: 세 행, 두 묶음, 두 호출.
    assert len(mock.calls) == 2
    assert (result.usage.calls, result.usage.attempts) == (2, 2)
    assert set(result.usage.by_prompt) == {CLASSIFY_PROMPT}
    # 꼬리표는 세션의 회사 id(의 글자)와 모듈 이름이다. 불린 것은 모의 공급사의 가상 모델뿐이다.
    assert {(record.tenant, record.module, record.provider, record.model) for record in log.records} == {
        (str(COMPANY), "inventory", "mock", "mock-synthetic")
    }
    # 숫자는 프롬프트에 가지 않는다.
    sent = "\n".join(user_texts(mock))
    assert "13579" not in sent
    assert "24680000" not in sent
    assert blocked_network == []


def test_a_failed_group_is_kept_as_a_failure_and_the_next_group_is_still_asked(
    monkeypatch: pytest.MonkeyPatch, blocked_network: list[object]
) -> None:
    mock = MockProvider()
    use(monkeypatch, mock_client(mock))
    for _ in range(3):
        mock.enqueue_text(classification(5))
    mock.enqueue_text(classification(6))
    result = services.scope3_classify(rows=[row("x1", row_id="a"), row("출장", row_id="b")], company_id=COMPANY)
    assert isinstance(result, services.Scope3Classified)
    failed, ok = result.groups
    assert isinstance(failed, services.Scope3GroupFailed)
    assert failed.llm.kind == "schema_mismatch"
    assert isinstance(ok, services.Scope3GroupClassified)
    assert (result.usage.calls, result.usage.attempts) == (2, 4)
    assert blocked_network == []


def test_the_server_client_has_no_mock_route_so_classify_is_llm_not_configured(
    monkeypatch: pytest.MonkeyPatch, blocked_network: list[object]
) -> None:
    """★ 바: 떠 있는 서버의 클라이언트(`build_client(mock=False)`)에는 경로 `mock` 이 없다. 키가 있어도 그렇다."""
    with_keys = LlmSettings(openai_api_key="sk-synthetic-not-a-key", anthropic_api_key="x", gemini_api_key="y")
    use(monkeypatch, build_client(with_keys))
    with pytest.raises(ApplicationError) as error:
        services.scope3_classify(rows=[row("합성 강판")], company_id=COMPANY)
    not_configured(error)
    for secret in ("sk-synthetic", "models", "LLM_", "key"):
        assert secret not in error.value.message
    assert blocked_network == []


def test_the_default_seam_is_the_process_client_and_it_is_not_configured(blocked_network: list[object]) -> None:
    """이음매를 바꾸지 않으면 `llm_client()` 가 나온다. 그 클라이언트로는 분류가 되지 않는다."""
    assert services.scope3_gateway() is llm_client()
    with pytest.raises(ApplicationError) as error:
        services.scope3_classify(rows=[row("합성 강판")], company_id=COMPANY)
    not_configured(error)
    assert blocked_network == []


def rerouted(routes: dict[str, tuple[str, ...]], providers: dict[str, MockProvider]) -> LlmClient:
    config = load_config(default_config_sources(synthetic=True))
    return LlmClient(
        config=replace(config, routes=routes), providers=providers, prompts=PackagePromptStore(), log=MemorySink()
    )


def test_a_route_named_mock_that_points_at_another_provider_is_refused_before_any_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """설정 파일(`LLM_MODELS_FILE`)이 `mock` 이라는 경로를 다른 공급사의 모델에 걸어 두어도 부르지 않는다(★ 바)."""
    other = MockProvider("mock-b")  # 「모의가 아닌 공급사」의 대역이다: 이름이 `mock` 이 아니다.
    use(monkeypatch, rerouted({"mock": ("mock-b-synthetic",)}, {"mock-b": other}))
    with pytest.raises(ApplicationError) as error:
        services.scope3_classify(rows=[row("합성 강판")], company_id=COMPANY)
    not_configured(error)
    assert other.calls == []


def test_a_mock_route_with_a_fallback_model_is_refused_too(monkeypatch: pytest.MonkeyPatch) -> None:
    """대체 모델의 공급사는 부르기 전에 알 수 없다. 그래서 대체가 걸린 경로는 통째로 거절한다."""
    mock, other = MockProvider(), MockProvider("mock-b")
    routes = {"mock": ("mock-synthetic", "mock-b-synthetic")}
    use(monkeypatch, rerouted(routes, {"mock": mock, "mock-b": other}))
    mock.enqueue_text(classification(1))
    with pytest.raises(ApplicationError) as error:
        services.scope3_classify(rows=[row("합성 강판")], company_id=COMPANY)
    not_configured(error)
    assert (mock.calls, other.calls) == ([], [])


def test_duplicates_too_many_groups_and_empty_input_never_reach_the_gateway(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom() -> LlmClient:
        raise AssertionError("이음매를 불렀다")

    monkeypatch.setattr(services, "scope3_gateway", boom)
    duplicate = services.scope3_classify(rows=[row("a"), row("b")], company_id=COMPANY)
    assert duplicate == services.Scope3DuplicateRowId("r1")
    many = [row(f"품목 {index}", row_id=str(index)) for index in range(21)]
    assert services.scope3_classify(rows=many, company_id=COMPANY) == services.Scope3TooManyGroups(21)
    empty = services.scope3_classify(rows=[], company_id=COMPANY)
    assert isinstance(empty, services.Scope3Classified)
    assert empty.groups == ()


def test_request_rows_become_pure_rows_with_absent_keys_as_none() -> None:
    full = services.scope3_row(
        {
            "rowId": "r9",
            "itemName": "원자재 운송",
            "quantity": "1",
            "unit": "kg",
            "amount": "2",
            "currency": "KRW",
            "date": "2026-01-05",
            "orgUnit": "본사",
            "transport": {"mode": "트럭", "origin": "부산", "destination": "평택", "weightKg": "3", "distanceKm": "4"},
        }
    )
    assert full == row(
        "원자재 운송",
        row_id="r9",
        quantity="1",
        amount="2",
        transport=services.TransportInfo("부산", "평택", "트럭", "3", "4"),
    )
    bare = services.scope3_row({"itemName": "x", "transport": {"mode": "철도"}})
    assert (bare.row_id, bare.quantity, bare.unit, bare.amount, bare.currency) == ("", None, None, None, None)
    assert bare.transport == services.TransportInfo("", "", "철도", None, None)
    assert services.scope3_row({"itemName": "x"}).transport is None


def test_license_text_is_parsed_strictly() -> None:
    assert services.scope3_licenses(None) == frozenset({"ok", "unverified"})
    assert services.scope3_licenses("ok, unverified ,disputed") == frozenset({"ok", "unverified", "disputed"})
    assert services.scope3_licenses("disputed") == frozenset({"disputed"})
    for bad in ("ok,bogus", "ok,ok", "", "ok,", "OK"):
        with pytest.raises(ApplicationError) as error:
            services.scope3_licenses(bad)
        assert (error.value.kind, error.value.code) == ("invalid_input", "invalid_license")
