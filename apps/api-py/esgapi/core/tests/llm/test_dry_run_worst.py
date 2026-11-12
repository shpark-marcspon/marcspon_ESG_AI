"""dry-run 어림의 최악 칸 셋(밴드 LH1 S8 — MARC-ISSUE-167). 순수 층.

`schema_tokens`(공급사에 실린 schema 의 어림) · `max_attempts`(1 + max_schema_retries, schema 없으면 1) ·
`worst_case_usd`(입력 + schema 토큰·출력 상한을 다 쓴 한 번 × max_attempts). 옛 칸 `input_tokens`·
`cost_upper_bound_usd` 는 BASE(1b7484bc)와 같은 값이다 — 아래 수는 BASE 트리에서 같은 요청으로 잰 것
(band-reports/LH1.md 「S8 BASE 값」). 공급사 호출 0(모의 공급사는 부르지 않는다). 단가는 models.json 의 것.
"""

from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from pydantic import BaseModel

from esgapi.core.llm.client import CallRequest
from esgapi.core.llm.cost import round_usd
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import DryRunEstimate
from esgapi.core.tests.llm_support import TAGS, Harness, harness


class Answer(BaseModel):
    category: str
    confidence: float


PLAIN = CallRequest(prompt="t/plain@1", vars={"question": "분류해 줘"}, route="light-openai", tags=TAGS)
SCHEMA = replace(PLAIN, schema=Answer)
# BASE 에서 잰 값(input_tokens, max_output_tokens, cost_upper_bound_usd) — light-openai(gpt-6-luna)
BASE_VALUES = (10, 6096, 0.003049)


def rig(prompt_root: Path) -> Harness:
    return harness(prompt_root, providers={"openai": MockProvider("openai"), "mock": MockProvider()})


def estimate[T](h: Harness, request: CallRequest[T]) -> DryRunEstimate:
    return h.client.dry_run(request).estimate


@pytest.mark.parametrize(
    "request_", [PLAIN, SCHEMA, replace(SCHEMA, max_schema_retries=0)], ids=["plain", "schema", "r0"]
)
def test_old_fields_keep_their_base_values(prompt_root: Path, request_: CallRequest[Any]) -> None:
    got = estimate(rig(prompt_root), request_)
    assert (got.input_tokens, got.max_output_tokens, got.cost_upper_bound_usd) == BASE_VALUES


def test_a_schema_request_counts_schema_tokens_and_three_attempts(prompt_root: Path) -> None:
    h = rig(prompt_root)
    got = estimate(h, SCHEMA)
    assert got.schema_tokens > 0
    assert got.max_attempts == 3
    once = estimate(h, replace(SCHEMA, max_schema_retries=0))
    assert (once.schema_tokens, once.max_attempts) == (got.schema_tokens, 1)
    assert once.worst_case_usd > got.cost_upper_bound_usd  # schema 토큰이 입력에 든다
    assert got.worst_case_usd == round_usd(once.worst_case_usd * 3)
    assert (got.worst_case_usd, once.worst_case_usd, got.schema_tokens) == (0.0091632, 0.0030544, 54)


def test_without_a_schema_the_worst_case_is_the_old_upper_bound(prompt_root: Path) -> None:
    got = estimate(rig(prompt_root), PLAIN)
    assert (got.schema_tokens, got.max_attempts, got.worst_case_usd) == (0, 1, got.cost_upper_bound_usd)


def test_the_new_keys_are_in_the_json(prompt_root: Path) -> None:
    got = rig(prompt_root).client.dry_run(SCHEMA).to_json()["estimate"]
    assert isinstance(got, dict)
    assert (got["schemaTokens"], got["maxAttempts"], got["worstCaseUsd"]) == (54, 3, 0.0091632)
