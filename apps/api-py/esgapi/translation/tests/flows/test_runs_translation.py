# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""영문번역을 진짜 DB 의 실행 만들기·실행기로 잰다(밴드 TR2 §3-2, 업무 층). 저장소는 가짜, 태스크는 함수를 직접 부른다
(greenwash/tests/flows/test_binding_e0_runs.py 꼴). 전역 REGISTRY·BINDINGS 의 끼움(apps.py 가 단 것 — 앞 실행 저장소는
진짜 runs selectors)을 그대로 쓴다.

    3-2-1  작은 지어낸 txt → POST /runs {module: translation} 201·판 묶음 → 실행기 끝(모의) → done·결과·Word ·
           결과 경로 GET /translation/runs/{id}/result 200(꼴 strict — done·rejected 둘 다)
    3-2-2  옵션 거절 400 INVALID_OPTIONS(끼움 문장) · 256KiB 넘는 옵션 400(16KiB 넘는 것은 201 — TR3a) · 결과 경로의
           다른 모듈·남의 회사·없는 실행 404 NOT_FOUND · 안 끝남 409 RUN_NOT_DONE
    3-2-3  retry: 같은 문서 앞 실행 → done·settings.retry · 남의 회사·그린워싱·안 끝남 → retry_source_not_found ·
           원문 다름 → retry_source_mismatch
    3-2-4  서버 그대로(mock) → 경로 mock 으로 done(TRR1 T2 — 앞에는 키 없음 LiveSetupError) · 설정 오류 →
           failed·setup_error·prepare(출력 상한 LlmConfigError) · 봉투 빠짐 → failed·step_error·prepare
★ 공급사: context.build_client 의 make 를 갈아 openai 에 대본 심은 MockProvider(실제 공급사·키·네트워크 0 — 경로 셋 다
  openai, MARC-ENT-402)·끼움의 mock 끔(scripted). 갈지 않으면 서버 그대로 — 경로 mock(3-2-4 의 첫 줄).
★ 실행·결과 행은 runs 의 selectors 로 읽는다(runs.models 를 import 하지 않는다 — 계약 나). 문서는 전부 지어낸 것이다.
"""

import contextlib
import json
from collections.abc import Mapping
from dataclasses import dataclass, field
from functools import partial
from types import MappingProxyType
from typing import Any

import pytest
from django.test import Client

from esgapi.config.env import JobSettings
from esgapi.core.flows.binding import BINDINGS
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.models import DocumentRow
from esgapi.core.resources import llm as llm_adapters
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.runs import context, tasks
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.translation.contracts.digest_shapes import DIGEST_SHAPE
from esgapi.translation.contracts.shapes import RESULT_SHAPE, RESULT_SHAPES
from esgapi.translation.engines.colab_158 import prompts
from esgapi.translation.flows import colab_158 as colab
from esgapi.translation.flows.binding_158 import TranslationBinding
from esgapi.translation.tests.engines.colab_158.support import ok
from esgapi.translation.tests.flows.support import SIMPLE, SIMPLE_EN, options
from esgapi.translation.tests.flows.test_binding_158 import synthetic_glossary
from esgapi.translation.tests.tools import glossary_support
from esgapi.translation.tools import llm_bridge
from tests.support.http import login
from tests.support.patches import plug_storage

pytestmark = pytest.mark.django_db

SETTINGS = JobSettings(lease_s=90, max_attempts=3, retry_delay_s=5)
OPTIONS_LIMIT = 256 * 1024
"""영문번역의 옵션 상한(apps.py 가 등록한 core DOCUMENTLESS_OPTIONS_MAX_OCTETS — 밴드 TR3a)."""
NO_ISSUES = ok("[]")
XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


class RetryAsked(Exception):
    """가짜 retry 가 돌려주는 것."""


@dataclass
class World:
    storage: FakeStorage
    company_a: int
    company_b: int
    mock: MockProvider = field(default_factory=lambda: MockProvider("openai"))
    sink: MemorySink = field(default_factory=MemorySink)
    retries: list[dict[str, Any]] = field(default_factory=lambda: [])

    def retry(self, **kwargs: Any) -> RetryAsked:
        self.retries.append(kwargs)
        return RetryAsked()


@pytest.fixture
def world(monkeypatch: pytest.MonkeyPatch, companies: tuple[int, int]) -> World:
    storage = plug_storage(monkeypatch, FakeStorage(), max_upload_bytes=1_000_000)
    made = World(storage, *companies)
    monkeypatch.setattr(tasks, "job_settings", lambda: SETTINGS)
    monkeypatch.setattr(tasks, "monotonic", lambda: 0.0)
    monkeypatch.setattr(tasks, "soft_limit_s", lambda: 240)
    monkeypatch.setattr(context, "call_sink", lambda: made.sink)
    return made


def scripted(monkeypatch: pytest.MonkeyPatch, world: World) -> None:
    """실행기의 클라이언트가 anthropic·openai 를 모의로 짓게 하고 끼움의 mock 을 끈다(live 길의 경로 셋 그대로 —
    openai 는 대본 심은 world.mock). mock 을 끄지 않으면 흐름이 경로 `mock` 을 부른다(MARC-ISSUE-331, 3-2-4 첫 줄)."""
    monkeypatch.setattr(BINDINGS.get(colab.FLOW_ID), "mock", lambda: False)

    def make(name: str, **kwargs: Any) -> Any:
        if name == "openai":
            return world.mock
        if name == "anthropic":
            return MockProvider("anthropic")
        return llm_adapters.make(name, **kwargs)

    monkeypatch.setattr(context, "build_client", partial(context.build_client, make=make))


def document(world: World, company: int, content: bytes = SIMPLE.encode(), name: str = "synthetic.txt") -> int:
    key = f"companies/{company}/documents/tr2-{len(world.storage.objects)}/original"
    etag = world.storage.put(key, content)
    row = DocumentRow.for_company(company).create(
        company_id=company,
        uploaded_by="1",
        file_name=name,
        storage_key=key,
        size_bytes=len(content),
        etag=etag,
        status="uploaded",
    )
    return row.pk


def create(client: Client, module: str, document_id: int, given: Mapping[str, object]) -> Any:
    body = {"module": module, "documentId": document_id, "options": given}
    return client.post("/api/runs", data=body, content_type="application/json")


def new_run(client: Client, world: World, given: Mapping[str, object], **doc: Any) -> int:
    login(client)
    response = create(client, "translation", document(world, world.company_a, **doc), given)
    assert response.status_code == 201, response.content.decode()
    run_id: int = response.json()["id"]
    return run_id


def execute(world: World, run_id: int, company: int | None = None) -> None:
    with contextlib.suppress(RetryAsked):
        tasks.execute_run(world, company_id=str(company or world.company_a), run_id=str(run_id))


def run_of(world: World, run_id: int, company: int | None = None) -> run_selectors.Run:
    found = run_selectors.find_run(company_id=company or world.company_a, run_id=run_id)
    assert found is not None
    return found


def result_body(world: World, run_id: int, shape: str = RESULT_SHAPE) -> dict[str, Any]:
    """그 꼴의 결과 행 본문(결과는 둘 — result@1 과 digest@1, 밴드 TR3a. schemaVersion 으로 고른다)."""
    rows = run_selectors.run_results(company_id=world.company_a, run_id=run_id)
    assert sorted(r.schema_version for r in rows) == [DIGEST_SHAPE, RESULT_SHAPE]
    (found,) = [r for r in rows if r.schema_version == shape]
    assert isinstance(found.body, dict)
    return found.body  # pyright: ignore[reportReturnType]


def done_run(client: Client, world: World, monkeypatch: pytest.MonkeyPatch, given: Mapping[str, object]) -> int:
    scripted(monkeypatch, world)
    world.mock.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    run_id = new_run(client, world, given)
    execute(world, run_id)
    assert world.mock.pending == 0
    return run_id


# ── 3-2-1 ──


def test_post_runs_translation_is_201_with_the_versions_and_three_steps(client: Client, world: World) -> None:
    run_id = new_run(client, world, options())
    run = run_of(world, run_id)
    assert (run.module, run.flow_id, run.status) == ("translation", colab.FLOW_ID, "queued")
    assert run.versions == {
        "engine": "colab_158",
        "flow": colab.FLOW_ID,
        "promptIds": llm_bridge.prompt_ids(),
        "aiSetting": "기본 설정",  # TR4 ③ 기본 판 — 판 열쇠의 값은 test_binding_158_settings.py 가 잰다
        "aiSettingId": None,
        "modelSettingsSha256": run.versions["modelSettingsSha256"],
    }
    steps = run_selectors.step_rows(company_id=world.company_a, run_id=run_id)
    assert [s.name for s in steps] == ["prepare", "translate", "report"]


def test_the_executor_runs_a_small_text_document_to_done(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    run = run_of(world, run_id)
    assert (run.status, run.error_code, run.failed_step, run.attempts) == ("done", None, None, 1)
    body = result_body(world, run_id)
    RESULT_SHAPES[RESULT_SHAPE].validate_python(body, strict=True)
    assert body["status"] == "done" and body["settings"]["retry"] is None
    outputs = [f.name for f in run_selectors.run_files(company_id=world.company_a, run_id=run_id) if f.step is None]
    assert "translation-bilingual-single.docx" in outputs and set(outputs) <= set(colab.OUTPUT_FILES)
    assert {r.run_id for r in world.sink.records} == {str(run_id)}
    assert {r.tenant for r in world.sink.records} == {str(world.company_a)}
    assert len(world.mock.calls) == 2
    response = client.get(f"/api/runs/{run_id}")
    assert (response.status_code, response.json()["status"]) == (200, "done")


def result_of(client: Client, run_id: int) -> Any:
    return client.get(f"/api/translation/runs/{run_id}/result")


def test_the_result_path_returns_the_result_body_in_its_shape(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    run_id = done_run(client, world, monkeypatch, options())
    response = result_of(client, run_id)
    assert response.status_code == 200, response.content.decode()
    body = response.json()
    RESULT_SHAPES[RESULT_SHAPE].validate_python(body, strict=True)
    assert body == result_body(world, run_id)
    assert body["status"] == "done" and SIMPLE_EN.splitlines()[1] in body["variants"][0]["translatedText"]


def test_the_result_path_returns_a_rejected_result_too(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """시작 전에 막힌 실행(over_budget)도 실행은 done 이라 결과 경로가 200 rejected 를 준다(호출 0)."""
    scripted(monkeypatch, world)
    monkeypatch.setattr(BINDINGS.get(colab.FLOW_ID), "max_usd", lambda: 0.0001)
    run_id = new_run(client, world, options())
    execute(world, run_id)
    response = result_of(client, run_id)
    assert response.status_code == 200, response.content.decode()
    RESULT_SHAPES[RESULT_SHAPE].validate_python(response.json(), strict=True)
    assert (response.json()["status"], response.json()["rejection"]["kind"]) == ("rejected", "over_budget")
    assert world.mock.calls == []


# ── 3-2-2 ──


def test_the_result_path_of_another_module_or_company_or_no_run_is_404(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    mine = done_run(client, world, monkeypatch, options())
    green = create(
        client,
        "greenwash",
        document(world, world.company_a, name="g.pdf"),
        {"parts": {"ceo": [1], "company": [], "climate": []}},
    )
    assert green.status_code == 201, green.content.decode()
    for run_id in (green.json()["id"], mine + 1000):
        response = result_of(client, run_id)
        assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")
        assert response.json()["error"]["message"] == "그런 실행이 없다"
    other = Client()
    login(other, tenant_id="tenant-b")
    response = result_of(other, mine)
    assert (response.status_code, response.json()["error"]["code"]) == (404, "NOT_FOUND")
    assert result_of(client, mine).status_code == 200  # 분모: 제 회사로는 보인다


def test_the_result_path_of_an_unfinished_run_is_409(client: Client, world: World) -> None:
    run_id = new_run(client, world, options())
    response = result_of(client, run_id)
    assert (response.status_code, response.json()["error"]["code"]) == (409, "RUN_NOT_DONE")
    assert response.json()["error"]["message"] == "실행이 아직 끝나지 않았다"


@pytest.mark.parametrize(
    ("given", "message"),
    [
        (options(criteria={}), "알 수 없는 옵션이에요: criteria"),
        (options(retry={"fromRunId": 1, "pages": [2, 2]}), "다시 번역할 쪽 번호가 겹쳐요"),
    ],
)
def test_refused_options_are_400_with_the_bindings_sentence(
    client: Client, world: World, given: dict[str, Any], message: str
) -> None:
    login(client)
    response = create(client, "translation", document(world, world.company_a), given)
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert response.json()["error"]["message"] == message


def test_options_over_16kib_are_accepted_now_that_the_flow_registers_256kib(client: Client, world: World) -> None:
    """B2 의 지어낸 164 + 164 짝 용어집(16KiB 넘음)은 영문번역의 등록 상한 256KiB(apps.py — 밴드 TR3a) 안이라 201."""
    given = options(glossary={"base": synthetic_glossary(164), "final": synthetic_glossary(164)})
    assert len(json.dumps(given, ensure_ascii=False).encode()) > 16 * 1024
    login(client)
    response = create(client, "translation", document(world, world.company_a), given)
    assert response.status_code == 201, response.content.decode()


def padded(target: int) -> dict[str, Any]:
    """옵션 바이트(runs 의 셈 — json.dumps 기본 구분자, UTF-8)가 꼭 target 이 되게 peer 글을 채운 옵션."""
    given = options(peerGroupStyle={"prompt": ""})
    given["peerGroupStyle"]["prompt"] = "x" * (target - len(json.dumps(given, ensure_ascii=False).encode()))
    assert len(json.dumps(given, ensure_ascii=False).encode()) == target
    return given


def test_options_over_256kib_are_refused_at_creation_and_256kib_is_accepted(client: Client, world: World) -> None:
    """상한은 바이트 그대로다: 262,144 바이트는 201, 하나 더 넘으면 400 INVALID_OPTIONS(글에 상한) — 실행 0."""
    login(client)
    response = create(client, "translation", document(world, world.company_a), padded(OPTIONS_LIMIT + 1))
    assert (response.status_code, response.json()["error"]["code"]) == (400, "INVALID_OPTIONS")
    assert "262144" in response.json()["error"]["message"].replace(",", "")
    page = run_selectors.run_page(
        company_id=world.company_a, module=None, status=None, document_id=None, limit=10, offset=0
    )
    assert page.count == 0
    accepted = create(client, "translation", document(world, world.company_a), padded(OPTIONS_LIMIT))
    assert accepted.status_code == 201, accepted.content.decode()


def test_a_500_plus_500_glossary_read_from_excel_with_an_8000_char_peer_text_runs_to_done(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """MARC-ISSUE-269 닫는 조건(밴드 TR3a §2-5): 지어낸 500짝(국 10·영 30자) 엑셀 둘을 용어집 읽기 경로로 읽어 그 짝을
    그대로 base·final 에 싣고 peer 글 8,000자를 더한 옵션 → 201 → 실행기(모의) done → 결과 경로 200 · digest 결과 행.
    (final 은 같은 짝의 거꾸로 차례.) 옵션 바이트는 runs 의 셈(json.dumps 기본 구분자, UTF-8)으로 재어 상한 안임을
    단언한다(실측값은 보고)."""
    login(client)
    read = [
        client.post("/api/translation/glossary/read", glossary_support.glossary(pairs), content_type=XLSX)
        for pairs in (glossary_support.synthetic_pairs(500), glossary_support.synthetic_pairs(500)[::-1])
    ]
    assert [(r.status_code, r.json()["ok"], r.json()["rowCount"]) for r in read] == [(200, True, 500)] * 2
    given = options(
        glossary={"base": read[0].json()["pairs"], "final": read[1].json()["pairs"]},
        peerGroupStyle={"prompt": "가" * 8_000},
    )
    size = len(json.dumps(given, ensure_ascii=False).encode())
    assert 16 * 1024 < size < OPTIONS_LIMIT, size
    run_id = done_run(client, world, monkeypatch, given)
    run = run_of(world, run_id)
    assert (run.status, run.error_code) == ("done", None)
    assert run.options["glossary"] == {"base": read[0].json()["pairs"], "final": read[1].json()["pairs"]}  # 자기 입력
    response = result_of(client, run_id)
    assert response.status_code == 200, response.content.decode()
    assert response.json() == result_body(world, run_id)
    digest = result_body(world, run_id, DIGEST_SHAPE)
    assert (digest["status"], digest["outcome"]) == ("done", "done")


# ── 3-2-3 ──


def retry_body(world: World, client: Client, from_run_id: int, *, content: bytes = SIMPLE.encode()) -> dict[str, Any]:
    run_id = new_run(client, world, options(retry={"fromRunId": from_run_id, "pages": [1]}), content=content)
    execute(world, run_id)
    assert run_of(world, run_id).status == "done"
    return result_body(world, run_id)


def test_retry_of_a_done_run_of_the_same_document_is_done_with_the_retry_settings(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = done_run(client, world, monkeypatch, options())
    world.mock.enqueue(ok("[BLOCK 1]\nVirtual Title\nVirtual body again.")).enqueue(NO_ISSUES)
    body = retry_body(world, client, first)
    assert body["status"] == "done"
    assert body["settings"]["retry"] == {"fromRunId": first, "pages": [1], "skippedPages": []}
    assert "Virtual body again." in body["variants"][0]["translatedText"]
    assert world.mock.pending == 0


def test_retry_of_another_companys_run_is_not_found(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    login(client, tenant_id="tenant-b")
    response = create(client, "translation", document(world, world.company_b), options())
    other = response.json()["id"]
    world.mock.enqueue(ok(SIMPLE_EN)).enqueue(NO_ISSUES)
    execute(world, other, world.company_b)
    assert run_of(world, other, world.company_b).status == "done"
    body = retry_body(world, Client(), other)  # 회사 A 의 새 클라이언트
    assert body["rejection"]["kind"] == "retry_source_not_found"
    assert json.dumps(body).count("Virtual Title") == 0  # 그 회사 글이 결과에 0


def test_retry_of_a_greenwash_or_unfinished_run_is_not_found(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    login(client)
    green = create(
        client,
        "greenwash",
        document(world, world.company_a, name="g.pdf"),
        {"parts": {"ceo": [1], "company": [], "climate": []}},
    )
    assert green.status_code == 201, green.content.decode()
    queued = new_run(client, world, options())
    for source in (green.json()["id"], queued):
        assert retry_body(world, client, source)["rejection"]["kind"] == "retry_source_not_found"
    assert world.mock.calls == []


def test_retry_of_a_run_of_another_text_is_a_mismatch(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    first = done_run(client, world, monkeypatch, options())
    other = (SIMPLE + "\n가상 덧붙임").encode()
    assert retry_body(world, client, first, content=other)["rejection"]["kind"] == "retry_source_mismatch"
    assert world.mock.pending == 0 and len(world.mock.calls) == 2


def test_retry_of_a_rejected_run_of_the_same_document_is_not_found(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """앞 실행이 done 이어도 결과가 거절(over_budget)이면 다시 돌릴 번역 글이 없다 — retry_source_not_found, 호출 0."""
    scripted(monkeypatch, world)
    binding = BINDINGS.get(colab.FLOW_ID)
    monkeypatch.setattr(binding, "max_usd", lambda: 0.0001)
    first = new_run(client, world, options())
    execute(world, first)
    assert run_of(world, first).status == "done"
    assert result_body(world, first)["rejection"]["kind"] == "over_budget"
    monkeypatch.setattr(binding, "max_usd", lambda: 5.0)
    assert retry_body(world, client, first)["rejection"]["kind"] == "retry_source_not_found"
    assert world.mock.calls == []


# ── 3-2-4 ──


def failed(world: World, run_id: int) -> tuple[str, str | None, str | None]:
    run = run_of(world, run_id)
    return run.status, run.error_code, run.failed_step


def test_the_server_without_keys_fails_in_prepare_with_setup_error(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    """live 길(끼움 mock 끔)에 키가 없으면: 공급사를 지을 때 LiveSetupError — failed·setup_error·prepare, 공급사 호출 0
    (TRR1 앞의 시험을 가지 리뷰 L5 로 되살림 — 지금 서버 그대로는 mock 이라 아래 시험이 잰다)."""
    monkeypatch.setattr(BINDINGS.get(colab.FLOW_ID), "mock", lambda: False)
    run_id = new_run(client, world, options())
    execute(world, run_id)
    assert failed(world, run_id) == ("failed", "setup_error", "prepare")
    assert world.sink.records == []


def test_the_server_as_is_in_mock_mode_runs_to_done_on_the_mock_route(client: Client, world: World) -> None:
    """T2(MARC-ISSUE-331): 갈지 않은 서버 그대로(make 이음매 0 — 진짜 context.build_client, LLM_RUN_MODE 빔 = mock).
    앞(TRR1 전)에는 prepare 의 dry_run 이 openai 경로에서 LiveSetupError → setup_error 였다. 이제 경로 `mock` 으로
    부른다: 심은 답이 없어 호출마다 공급사 오류 → 쪽마다 [TRANSLATION_ERROR] 인 채 done, 결과 routes `mock`."""
    binding = BINDINGS.get(colab.FLOW_ID)
    assert isinstance(binding, TranslationBinding) and binding.mock() is True  # 분모: 시험 설정은 mock(run_mode)
    run_id = new_run(client, world, options())
    execute(world, run_id)
    assert failed(world, run_id) == ("done", None, None)
    body = result_body(world, run_id)
    RESULT_SHAPES[RESULT_SHAPE].validate_python(body, strict=True)
    assert body["status"] == "done"
    assert body["settings"]["routes"] == {"translate": "mock", "review": "mock"}
    # 입력·versions 는 그대로(TRR1 검증 R2): 판 열쇠·모델 sha 가 live 길(끼움 mock 끔)로 만든 실행과 같다
    run = run_of(world, run_id)
    assert run.versions["aiSettingId"] is None
    assert (
        run.versions["modelSettingsSha256"]
        == binding.versions_with(options(), company_id=world.company_a)["modelSettingsSha256"]
    )
    assert "[TRANSLATION_ERROR page=1]" in body["variants"][0]["translatedText"]
    assert {r.model for r in world.sink.records} == {"mock-synthetic"}  # 경로 mock 의 모델(가상)
    assert world.mock.calls == []  # openai 경로는 부르지 않는다
    outputs = [f.name for f in run_selectors.run_files(company_id=world.company_a, run_id=run_id) if f.step is None]
    assert "translation-bilingual-single.docx" in outputs


def test_an_output_cap_over_the_model_limit_fails_in_prepare_with_setup_error(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    monkeypatch.setitem(prompts.MAX_TOKENS, "section", 10**7)
    huge = llm_bridge.CallModel(llm_bridge.TRANSLATE_ROUTE, 10**7)  # R4 min — 칸 위끝도 넘게(TR4, 감독 10-23 허락)
    monkeypatch.setattr(
        "esgapi.translation.flows.binding_158.DEFAULT_MODELS", llm_bridge.TranslationModels(huge, huge, huge)
    )
    run_id = new_run(client, world, options())
    execute(world, run_id)
    assert failed(world, run_id) == ("failed", "setup_error", "prepare")
    assert world.mock.calls == []


def test_a_missing_envelope_fails_in_prepare_with_step_error(
    client: Client, world: World, monkeypatch: pytest.MonkeyPatch
) -> None:
    scripted(monkeypatch, world)
    versions = {**llm_bridge.PROMPT_VERSIONS, "section": 99}
    monkeypatch.setattr(llm_bridge, "PROMPT_VERSIONS", MappingProxyType(versions))
    run_id = new_run(client, world, options())
    execute(world, run_id)
    assert failed(world, run_id) == ("failed", "step_error", "prepare")
    assert world.mock.calls == []
