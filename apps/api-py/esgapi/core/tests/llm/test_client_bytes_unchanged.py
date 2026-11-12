"""도구 칸이 빈 요청의 바이트 불변(밴드 TL1 `MARC-TICK-180` 의 T1). 순수 층.

도구 칸(tools·tool_choice·parallel_tool_calls·max_hosted_calls·system_placement·turns)과
`Completed` 의 새 칸이 생긴 뒤에도,
도구를 쓰지 않는 요청의 중립 본문·해시, OpenAI·모의 어댑터가 조립한 본문, 호출 기록 한 줄, dry-run 보고는 기준 커밋과
글자째 같아야 한다. 기준 값은 기준 커밋 ccd3194(도구 칸이 생기기 전)에서 같은 셈으로 잰 sha256 이다
(잰 스크립트는 band-reports/TL1.md 의 「T1 BASE 값」). 기록 줄은 `callId`(uuid4)·`ts` 를 빼고 견준다.
dry-run 보고는 LH1(MARC-ISSUE-167)이 estimate 끝에 더한 열쇠 셋(`LH1_ESTIMATE_KEYS`)을 빼고 견주고, 그 셋이 끝에
있음은 따로 잰다.

실제 공급사로 가는 호출은 없다. 토큰 수와 본문은 전부 가상(synthetic) 값이다.
"""

import json
from pathlib import Path
from typing import Any, cast

from pydantic import BaseModel

from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.log import sha256_json, sha256_text
from esgapi.core.llm.prompts import FilePromptStore
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.sinks.memory import MemorySink
from esgapi.core.llm.types import JsonSchemaSpec, PdfPart, ProviderRequest, SystemSegment, TextPart
from esgapi.core.tests.llm_support import LONG_GUIDE, TAGS, synthetic_config

LH1_ESTIMATE_KEYS = ["schemaTokens", "maxAttempts", "worstCaseUsd"]

SCHEMA: dict[str, object] = {"type": "object", "properties": {}, "additionalProperties": False}

# 대표 요청 다섯: 글만·스키마·PDF·temperature·system 캐시.
REQUESTS = {
    "text": ProviderRequest(api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10),
    "schema": ProviderRequest(
        api_model_id="m",
        system=(SystemSegment(text="지침", cache=False),),
        user=(TextPart(text="q"),),
        max_output_tokens=10,
        json_schema=JsonSchemaSpec(name="out", schema=SCHEMA),
    ),
    "pdf": ProviderRequest(
        api_model_id="m",
        system=(SystemSegment(text="지침", cache=False),),
        user=(PdfPart(base64="UERG", filename="r.pdf"), TextPart(text="표")),
        max_output_tokens=2000,
    ),
    "temperature": ProviderRequest(
        api_model_id="m", system=(), user=(TextPart(text="q"),), max_output_tokens=10, temperature=0.1
    ),
    "cache": ProviderRequest(
        api_model_id="m",
        system=(SystemSegment(text=LONG_GUIDE, cache=True), SystemSegment(text="메모", cache=False)),
        user=(TextPart(text="q"),),
        max_output_tokens=10,
    ),
}


class Out(BaseModel):
    ok: bool


CALLS: dict[str, CallRequest[Any]] = {
    "plain": CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="mock", tags=TAGS),
    "schema": CallRequest(prompt="t/plain@1", vars={"question": "q"}, route="mock", tags=TAGS, schema=Out),
    "cached": CallRequest(prompt="t/cached-long@1", vars={"question": "q"}, route="mock", tags=TAGS, temperature=0.1),
}

# 기준 커밋 ccd3194 에서 잰 값. `*.ordered` 는 열쇠 차례까지(정렬 없이 JSON 으로 낸 글자의 sha256).
BASELINE = {
    "cache.mock": "427763f6733eeaadd377dee12245577d9ba58f3c5a1a1dde942b98c2bfb485b5",
    "cache.openai": "5d46d5fe4f807e1974d92732d175f6aeb3665d6ece44f20717f430873d904ec4",
    "cache.openai.ordered": "6e9f05aec0d47aa055ae174b25a7b206f12f5a4ef1b9d41d07165b88f9e0aee4",
    "cache.to_json": "89e0f29e3c59dc2b6351f13522bb1f1bfda95b3144e3f0637955d8708a1b7f4e",
    "cache.to_json.ordered": "ea9dab6524ea617e83191958c6b34ed5143398d481d7c407f0ab5b925832f615",
    "call.cached.store0.record": "314143a0dc594475c270ffc8ce8db6ce821ad4f8c836990c68701708ecafde70",
    "call.cached.store1.record": "13f945ab988818be83b1a9c8e8f199b26951dbf67ed27b7c1c2dc5f3262857a8",
    "call.plain.store0.record": "0ba30d1d34746726e5e35b0868e89cbb558b45faec692f003a11c2cc8a7d775a",
    "call.plain.store1.record": "02d570cbae858056ce560316361136dda6a7a9f8790b14b3df7274c9141ab9dc",
    "call.schema.store0.record": "652ca121393d5ba80e041292283a322927084b52128e9d00a7e40504c70dcd9c",
    "call.schema.store1.record": "1f6f8d63c590e3de7f90a09fca701bbd0c5be5632b04323d14a6512ba65fce4d",
    # LH3 Q8(MARC-ISSUE-417): 캐시 지정 몫을 쓰기 단가(가상 1.25 > 입력 1.0)로 — 위끝 0.010301 → 0.010876. 나머지 그대로
    "dry_run.cached": "39b28a17373b865d19260a8b17240faffcf04cafeef1acd577ddeb7285cf1031",
    "dry_run.plain": "8bbf8c414d186eee1fe39315b1f7d439fd4e5b2edcd12416ba8afe775941ec06",
    "dry_run.schema": "3faac0ec681f68ad4795302cbae97753bf8a2b6ee22381f3679d1d35477209f5",
    "pdf.mock": "b27575a1bf03eada18552f9199b18aa27c625998aa6d326b8deb567a7f9825bd",
    "pdf.openai": "ac19d0fa3841ca0057d971756cdeb606b9ef29886458d0286db629abdb2b3882",
    "pdf.openai.ordered": "4e07bca9f7c35490e3a98d6d58f89e566262f80d7aa2b514425de72bb936a7bb",
    "pdf.to_json": "414f94623c34a49101d927ef483a97b9dbee4078dc2b304b202f33f4b66aa193",
    "pdf.to_json.ordered": "7edc6da7a8b778c19c2c75c247b85726cc2348d797895ecff906ea2af14a0ed7",
    "schema.mock": "d99c9433bf01d237ec64424f6240cecce167d42aeb23fa394bdd70a74edab6b2",
    "schema.openai": "3f03a8d29ad9fbce7dba0b23b632ecad1273bd3aa248f170438693a8f9d5d24f",
    "schema.openai.ordered": "998f3bfb22e8ca769359ac726e1640203fb32bf6a901664919c19e6a43b04418",
    "schema.to_json": "2c56c51d27c4abe7b2a05198d8ecee3bfb496746bececfe8854e047dd3390d80",
    "schema.to_json.ordered": "39224a1dcf4651696ca97297056854d349b4278e80eca32d542b8bd1436777cb",
    "temperature.mock": "22db180cc413368b5b4aed6ce7c38f7ed169361dfc80b61c562c3195536dc56e",
    "temperature.openai": "c7509dd810ab683238610401ca2b5c2ccdd25b288c90bc67fe48e4fa7a699089",
    "temperature.openai.ordered": "fc6525429102251a31410e32a7830d40ea3304e50f7e7cca4ed922538de811aa",
    "temperature.to_json": "4c0428f30b9a1944bc48fdbabae93d327839f58fc43a2f0b22f0da83cda68431",
    "temperature.to_json.ordered": "2f457c5f3110fa9ec1baf0f8d6bd81f5d7015302d0b8d989b9f2be72e7091303",
    "text.mock": "e101072c5962fe36c15966050388a69cd04a46e21751c935474f42a416abb2ca",
    "text.openai": "c28eaa8b1cd0b1613bf13d5d3b19325463a639621997b13fb718c1683e14f86b",
    "text.openai.ordered": "53a798de6c82e633bceb25195b570303e1c3aa897ff020762adf7d5795d4735e",
    "text.to_json": "47a0165c0c12a7332310d9de172dbc1437a05d841b908be7458df27ca686baf1",
    "text.to_json.ordered": "7807d64890d52f652b9137a6876585ea04f17cc9a4a6daab90d3c587d5628fcc",
}


def measure(prompt_root: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for name, request in REQUESTS.items():
        out[f"{name}.to_json"] = sha256_json(request.to_json())
        out[f"{name}.to_json.ordered"] = sha256_text(json.dumps(request.to_json(), ensure_ascii=False))
        out[f"{name}.openai"] = sha256_json(OpenAIProvider().build_request(request))
        out[f"{name}.openai.ordered"] = sha256_text(
            json.dumps(OpenAIProvider().build_request(request), ensure_ascii=False)
        )
        out[f"{name}.mock"] = sha256_json(MockProvider().build_request(request))
    for store in (False, True):
        for name, call in CALLS.items():
            mock = MockProvider()
            log = MemorySink()
            client = LlmClient(
                config=synthetic_config(),
                providers={"mock": mock, "mock-b": MockProvider("mock-b")},
                prompts=FilePromptStore(prompt_root),
                log=log,
                store_bodies=store,
                now=lambda: 0.0,
            )
            mock.enqueue_text('{"ok":true}')
            client.call(call)
            record = log.records[0].to_json()
            record.pop("callId")
            record.pop("ts")
            out[f"call.{name}.store{int(store)}.record"] = sha256_json(record)
            out[f"dry_run.{name}"] = sha256_json(without_lh1_keys(client.dry_run(call).to_json()))
    return out


def without_lh1_keys(report: dict[str, Any]) -> dict[str, Any]:
    """dry-run 보고에서 LH1 이 estimate 끝에 더한 열쇠 셋을 뺀 것(나머지 열쇠 차례 그대로)."""
    estimate = {key: value for key, value in report["estimate"].items() if key not in LH1_ESTIMATE_KEYS}
    return report | {"estimate": estimate}


def test_requests_records_and_dry_runs_without_tools_match_the_baseline_commit(prompt_root: Path) -> None:
    assert measure(prompt_root) == BASELINE


def test_lh1_estimate_keys_come_last_in_every_dry_run_report(prompt_root: Path) -> None:
    client = LlmClient(
        config=synthetic_config(),
        providers={"mock": MockProvider(), "mock-b": MockProvider("mock-b")},
        prompts=FilePromptStore(prompt_root),
        log=MemorySink(),
    )
    for call in CALLS.values():
        estimate = cast("dict[str, object]", client.dry_run(call).to_json()["estimate"])
        assert list(estimate)[-3:] == LH1_ESTIMATE_KEYS


def test_default_tool_fields_add_no_keys_to_the_neutral_body_or_the_openai_body() -> None:
    for request in REQUESTS.values():
        assert request.uses_tools is False
        body = request.to_json()
        for key in ("tools", "toolChoice", "parallelToolCalls", "maxHostedCalls", "systemPlacement", "turns"):
            assert key not in body
        params = OpenAIProvider().build_request(request)
        assert set(params) <= {"model", "max_output_tokens", "input", "store", "instructions", "text", "temperature"}
        assert params["store"] is False
