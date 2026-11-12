"""생성 모델 부름의 갈래(코랩이 본 꼴로 내림)와 글 해석, 프롬프트 파일.

글 해석 = 코랩 `safe_json_loads`·`_extract_json_object`.
"""

import hashlib
import json
from pathlib import Path

import pytest

from esgapi.core.llm.prompts import PackagePromptStore, parse_prompt_id
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.colab_157.llm import (
    LlmCalls,
    LlmContext,
    LlmFailed,
    LlmText,
    call_text,
    extract_json_object,
    safe_json_loads,
)
from esgapi.inventory.tests.scope3_llm_support import ROUTE, mock_client, user_text

PROMPTS = Path(__file__).resolve().parents[4] / "prompts"
TAGS = Tags(tenant="가상회사", module="inventory")


def test_success_and_failure_fall_to_text_or_failed() -> None:
    mock = MockProvider().enqueue_text("IT장비")
    context = LlmContext(mock_client(mock), ROUTE, TAGS, LlmCalls())
    got = call_text(context, "inventory/scope3-colab-group-name@1", {"product_text": "가상 노트북"}, 20)
    assert got == LlmText("IT장비", "success")
    assert "가상 노트북" in user_text(mock.calls[0])
    failed = call_text(context, "inventory/scope3-colab-group-name@1", {"product_text": "가상 의자"}, 20)
    assert isinstance(failed, LlmFailed)  # 심은 답이 없으면 모의 공급사가 실패한다
    assert context.calls.by_prompt["inventory/scope3-colab-group-name@1"]["success"] == 1


def test_safe_json_loads_strips_fences_like_the_colab() -> None:
    assert safe_json_loads('```json\n{"a": 1}\n```') == {"a": 1}
    with pytest.raises(json.JSONDecodeError):
        safe_json_loads("가상 답")
    assert extract_json_object('앞 글 {"a": 9} 뒤 글') == {"a": 9}
    assert extract_json_object("") is None


@pytest.mark.parametrize(
    "name",
    [
        "scope3-colab-group-name",
        "scope3-colab-naics-pick",
        "scope3-colab-unit-factor",
        "scope3-colab-unit-factor-simple",
        "scope3-colab-travel-mode",
        "scope3-colab-city-name",
        "scope3-colab-distance-straight",
        "scope3-colab-distance-road",
        "scope3-colab-airport",
        "scope3-colab-transport-mode",
    ],
)
def test_the_prompt_files_parse(name: str) -> None:
    template = PackagePromptStore().get(parse_prompt_id(f"inventory/{name}@1"))
    assert template.user
    assert hashlib.sha256((PROMPTS / name / "1.md").read_bytes()).hexdigest() == template.hash
