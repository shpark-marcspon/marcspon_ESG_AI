"""모델 설정 받기·sha 의 원천 selectors.RunModelSource(밴드 AS2b §2-2 N1). 순수 층(DB 0).

    LLM_MODELS_FILE(설정 llm.models_file)이 있으면 그 파일 — 실행 클라이언트(core/llm/setup.py 비모의 갈래)와 같은 셈.
    없으면 패키지 models.json. 명세는 prompt_model_e0.STEPS 그 자체.

설정 파일은 패키지 파일의 임시 사본에서 모델 하나의 apiModelId 만 바꾼 것이다. 실제 AI 호출 0.
"""

import dataclasses
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from django.conf import LazySettings

from esgapi.core.calc.ai_settings import defaults, model_settings_sha256
from esgapi.core.llm.config import default_config_sources, load_config, resolve_route
from esgapi.greenwash.flows import prompt_model_e0
from esgapi.greenwash.service.selectors import ai_settings as selectors

PACKAGE = Path(load_config.__code__.co_filename).parent / "data" / "models.json"


@pytest.fixture
def fresh_cache() -> Iterator[None]:
    """model_config 는 한 번 읽어 쥔다(functools.cache) — 앞뒤로 비운다."""
    selectors.model_config.cache_clear()
    yield
    selectors.model_config.cache_clear()


def test_the_source_reads_the_models_file_like_the_run_client(
    settings: LazySettings, tmp_path: Path, fresh_cache: None
) -> None:
    source = selectors.RunModelSource()
    assert source.steps() is prompt_model_e0.STEPS
    packaged = source.config()
    assert packaged == load_config(default_config_sources(synthetic=False))  # 분모: 파일이 없으면 패키지 파일
    before = model_settings_sha256(defaults(packaged, source.steps()))

    raw = json.loads(PACKAGE.read_text(encoding="utf-8"))
    raw["models"]["gpt-4.1-mini"]["apiModelId"] = "gpt-4.1-mini-moved"  # 기본 경로(light-openai-41)의 모델
    copied = tmp_path / "models.json"
    copied.write_text(json.dumps(raw, ensure_ascii=False), encoding="utf-8")
    config = settings.ESG_CONFIG
    settings.ESG_CONFIG = dataclasses.replace(config, llm=dataclasses.replace(config.llm, models_file=str(copied)))
    selectors.model_config.cache_clear()

    moved = source.config()
    assert [m.api_model_id for m in resolve_route(moved, "light-openai-41")] == ["gpt-4.1-mini-moved"]
    assert model_settings_sha256(defaults(moved, source.steps())) != before
