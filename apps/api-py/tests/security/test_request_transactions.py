"""요청마다의 트랜잭션이 없다는 것(EDK 리뉴얼 꼴)을 앱 역할의 진짜 커밋으로 잰다. 보안 층.

여기서 재는 것(업무 층은 테스트의 트랜잭션 안이라 「밖」과 진짜 커밋을 못 잰다):
  - 오류로 답한 요청에서도 그 요청이 쓴 호출 기록 줄이 남는다(싱크가 줄마다 스스로 커밋한다)
  - 경로가 부르는 LLM 호출은 트랜잭션 밖에서 돈다(바깥 호출 동안 트랜잭션·잠금을 쥐지 않는다)

Django 의 연결은 앱 역할(esg_app)이고 진짜로 커밋한다. `owner` 는 주인 역할의 연결이다(분모를 센다).
남는다·안 남는다는 늘 주인 역할의 실제 행 수와 함께 단언한다. 상태 코드만 단언한다(오류 code 글자는 E2 가 바꾼다).

무효 조건: 미들웨어를 직접 돌리는 테스트는 경로 함수를 지어낸다(django-ninja 를 거치지 않는다). LLM 은 모의 공급사다.
"""

import json
from typing import Any

import psycopg
import pytest
from django.db import connection
from django.http import HttpRequest, HttpResponse
from django.test import Client, RequestFactory

from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.prompts import PackagePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sink_db import DbSink, Written
from esgapi.core.llm.types import InvokeOptions, ProviderRequest, ProviderResponse
from esgapi.core.tenancy.middleware import TenantMiddleware
from esgapi.inventory.service.services import inventory as inventory_services
from tests.security.conftest import count
from tests.security.test_llm_log import record_of
from tests.support.http import login

pytestmark = pytest.mark.security

Owner = psycopg.Connection[tuple[Any, ...]]
TABLE = "core_llm_call_logs"


def test_a_log_line_survives_an_error_response(owner: Owner, companies: tuple[int, int]) -> None:
    """경로가 기록을 쓴 뒤 500 으로 답해도 그 줄은 남는다(전에는 미들웨어가 되돌려 사라졌다)."""
    sink = DbSink()

    def record_then_fail(request: HttpRequest) -> HttpResponse:
        sink.record(record_of(companies[0]))
        return HttpResponse(status=500)

    assert count(owner, TABLE) == 0  # 분모: 쓰기 전
    assert TenantMiddleware(record_then_fail)(RequestFactory().post("/inventory/scope3/classify")).status_code == 500
    assert sink.outcomes == (Written(),)
    assert count(owner, TABLE) == 1


class RecordingProvider(MockProvider):
    """부른 순간의 `connection.in_atomic_block` 을 적어 두는 모의 공급사."""

    def __init__(self) -> None:
        super().__init__()
        self.in_atomic: list[bool] = []

    def invoke(self, request: ProviderRequest, options: InvokeOptions) -> ProviderResponse:
        self.in_atomic.append(connection.in_atomic_block)
        return super().invoke(request, options)


def test_the_llm_call_runs_outside_a_transaction(
    client: Client, owner: Owner, companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scope 3 분류(HTTP, 미들웨어를 거침)의 LLM 호출이 트랜잭션 밖에서 돈다. 기록 줄은 호출마다 커밋된다."""
    provider = RecordingProvider()
    reply = {"category": 1, "keywords_en": ["steel"], "confidence": "medium", "reason": "테스트 응답 (synthetic)"}
    provider.enqueue_text(json.dumps(reply, ensure_ascii=False))
    llm = LlmClient(
        config=load_config(default_config_sources(synthetic=True)),
        providers={"mock": provider},
        prompts=PackagePromptStore(),
        log=DbSink(),
    )
    monkeypatch.setattr(inventory_services, "scope3_gateway", lambda: llm)
    login(client, tenant_id="tenant-a")
    assert count(owner, TABLE) == 0  # 분모: 부르기 전
    response = client.post(
        "/api/inventory/scope3/classify",
        data=json.dumps({"rows": [{"rowId": "a", "itemName": "합성 강판", "unit": "kg"}]}),
        content_type="application/json",
    )
    assert response.status_code == 200, response.content.decode()
    assert provider.in_atomic == [False]  # 분모: 호출 1 번
    assert count(owner, TABLE) == 1  # 그 호출의 줄이 커밋됐다
    assert owner.execute(f"SELECT company_id FROM {TABLE}").fetchall() == [(companies[0],)]  # 세션의 회사로
