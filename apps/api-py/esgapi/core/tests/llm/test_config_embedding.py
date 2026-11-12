"""임베딩 설정: load_config 가 임베딩 모델·경로를 싣고, 채팅 모델과 같은 규칙으로 거절한다.

실제 모델의 수치(차원·한도·단가)는 여기에 적지 않는다. data/models.json 을 읽어 견준다.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.llm.config import default_config_sources, load_config, resolve_embedding_route
from esgapi.core.llm.errors import LlmConfigError

# 1. 실제 설정


def test_the_real_embedding_route_resolves_to_the_model_of_the_data_file() -> None:
    (real,) = default_config_sources(synthetic=False)
    body = json.loads(real.read_text(encoding="utf-8"))
    config = load_config((real,))

    model = resolve_embedding_route(config, "light-openai")

    key = body["embeddingRoutes"]["light-openai"]
    entry = body["embeddingModels"][key]
    assert model.key == key
    assert model.provider == entry["provider"]
    assert model.api_model_id == entry["apiModelId"]
    assert model.dimensions == entry["dimensions"]
    assert model.max_inputs_per_request == entry["maxInputsPerRequest"]
    assert model.pricing.input == entry["pricing"]["input"]
    assert set(config.embedding_models) == set(body["embeddingModels"])
    assert dict(config.embedding_routes) == body["embeddingRoutes"]
    assert all(model.entry.synthetic is None for model in config.embedding_models.values())


# 2. 가상 설정


def test_the_synthetic_embedding_route_is_in_its_own_file_and_adds_no_chat_model() -> None:
    real, chat_synthetic, embedding_synthetic = default_config_sources(synthetic=True)
    assert embedding_synthetic.name == "models.embedding.synthetic.json"
    config = load_config((real, chat_synthetic, embedding_synthetic))
    chat_only = load_config((real, chat_synthetic))

    model = resolve_embedding_route(config, "mock-gw1")

    assert model.key == "mock-embedding-gw1-synthetic"
    assert model.provider == "mock"
    assert model.entry.synthetic is True
    assert dict(config.models) == dict(chat_only.models)
    assert dict(config.routes) == dict(chat_only.routes)
    assert config.token_estimate == chat_only.token_estimate
    # 가상 파일을 더해도 실제 임베딩 경로는 그대로다.
    assert resolve_embedding_route(config, "light-openai") == resolve_embedding_route(chat_only, "light-openai")


# 3. 거절 여섯 (임시 파일. 꼴은 test_llm_cost.py 의 FILE·MODEL 과 같게 여기에 따로 둔다)

EMBEDDING: dict[str, Any] = {
    "provider": "p",
    "apiModelId": "e",
    "label": "e",
    "pricing": {"input": 1},
    "dimensions": 4,
    "maxInputTokens": 10,
    "maxInputsPerRequest": 10,
    "maxTokensPerRequest": 100,
    "multilingual": None,
    "sourceRefs": [],
    "notes": [],
}
SOURCED = {**EMBEDDING, "sourceRefs": ["a"]}
TOKEN_ESTIMATE = {"note": "", "latinCharsPerToken": 4, "latinBasis": "", "cjkCharsPerToken": 1, "cjkBasis": ""}
FILE: dict[str, Any] = {
    "checkedOn": "2026-10-15",
    "note": "",
    "sources": {"a": "https://example.com/a"},
    "tokenEstimate": TOKEN_ESTIMATE,
    "models": {},
    "routes": {},
}


@pytest.mark.parametrize(
    ("name", "body", "message"),
    [
        ("no-source.json", {**FILE, "embeddingModels": {"e": EMBEDDING}}, "임베딩 모델 e 에 출처가 없다"),
        (
            "bad-ref.json",
            {**FILE, "embeddingModels": {"e": {**EMBEDDING, "sourceRefs": ["zzz"]}}},
            "임베딩 모델 e 의 출처 zzz 가 sources 에 없다",
        ),
        (
            "marked-in-real.json",
            {**FILE, "embeddingModels": {"e": {**SOURCED, "synthetic": True}}},
            "가상 임베딩 모델 e 는 synthetic 파일에 둬야",
        ),
        (
            "unmarked.synthetic.json",
            {**FILE, "synthetic": True, "embeddingModels": {"e": EMBEDDING}},
            "가상 파일의 임베딩 모델 e 에 synthetic 표시가 없다",
        ),
        (
            "bad-route.json",
            {**FILE, "embeddingModels": {"e": SOURCED}, "embeddingRoutes": {"r": "nope"}},
            "임베딩 경로 r 이 없는 모델 nope",
        ),
    ],
)
def test_bad_embedding_entries_are_rejected(tmp_path: Path, name: str, body: dict[str, Any], message: str) -> None:
    path = tmp_path / name
    path.write_text(json.dumps(body), encoding="utf-8")
    with pytest.raises(LlmConfigError, match=message):
        load_config([path])


def test_the_same_embedding_key_in_two_files_is_rejected_and_a_good_file_loads(tmp_path: Path) -> None:
    """여섯째(두 파일에 같은 키). 위의 거절이 「파일이 통째로 틀려서」가 아님도 같이 보인다:
    같은 뼈대의 옳은 파일은 읽힌다.
    """
    good = tmp_path / "good.json"
    good.write_text(
        json.dumps({**FILE, "embeddingModels": {"e": SOURCED}, "embeddingRoutes": {"r": "e"}}), encoding="utf-8"
    )
    other = tmp_path / "other.json"
    other.write_text(json.dumps({**FILE, "embeddingModels": {"e": SOURCED}}), encoding="utf-8")

    config = load_config([good])

    assert list(config.embedding_models) == ["e"]
    assert dict(config.embedding_routes) == {"r": "e"}
    with pytest.raises(LlmConfigError, match="임베딩 모델 e 가 중복"):
        load_config([good, other])


# 4. 경로 풀기


def test_an_unknown_embedding_route_is_rejected_and_chat_routes_are_a_separate_namespace() -> None:
    config = load_config(default_config_sources(synthetic=True))
    with pytest.raises(LlmConfigError, match="임베딩 경로 nope 가 설정에 없다"):
        resolve_embedding_route(config, "nope")
    assert "light" in config.routes
    with pytest.raises(LlmConfigError, match="임베딩 경로 light 가 설정에 없다"):
        resolve_embedding_route(config, "light")
