"""모델 설정 파일을 읽어 하나로 합친다. 모델 ID, 단가, 한도, 경로는 이 파일들에만 있다(코드에 수치가 없다).

파일은 `data/models.json`(실제 모델. 수치마다 출처)과 `data/models.synthetic.json`(테스트·모의 공급사 전용 가상
모델), `data/models.embedding.synthetic.json`(가상 임베딩 모델)이다.
출처 없는 실제 모델, 가상 표시 없는 가상 모델, 모르는 열쇠는 거부한다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Annotated

from pydantic import AnyUrl, BaseModel, ConfigDict, Field, ValidationError
from pydantic.alias_generators import to_camel

from esgapi.core.llm.errors import LlmConfigError

type ConfigSource = Path | Traversable

Rate = Annotated[float, Field(ge=0)]
PositiveInt = Annotated[int, Field(gt=0)]


class _Strict(BaseModel):
    """파일의 열쇠는 camelCase, 파이썬의 이름은 snake_case. 모르는 열쇠는 거부하고 타입을 바꿔 읽지 않는다."""

    model_config = ConfigDict(extra="forbid", strict=True, frozen=True, alias_generator=to_camel, populate_by_name=True)


class LongContextPricing(_Strict):
    above_input_tokens: PositiveInt
    input: Rate
    output: Rate
    cache_write: Rate
    cache_read: Rate


class Pricing(_Strict):
    """단가. USD / 100만 토큰."""

    input: Rate
    output: Rate
    cache_write: Rate
    cache_write_1h: Annotated[Rate | None, Field(alias="cacheWrite1h")] = None
    cache_read: Rate
    long_context: LongContextPricing | None = None


class HostedToolPricing(_Strict):
    """공급사가 실행하는 도구의 건당 요금. USD / 호출 1건(토큰 단가와 단위가 다르다)."""

    web_search_per_call: Rate


class PdfLimits(_Strict):
    max_pages_per_request: PositiveInt | None
    max_request_mb: Annotated[float, Field(gt=0)]


class Lifecycle(_Strict):
    status: str
    retirement: str | None
    note: str


class ModelEntry(_Strict):
    """설정 파일의 모델 하나.

    `reasoning_output_reserve_tokens` 는 추론 토큰이 출력 상한을 같이 쓰는 모델의 여유분이다. 호출 층이 요청의
    `max_output_tokens`(답의 상한)에 이만큼 더해 보낸다. 추론 토큰이 없거나 상한을 같이 쓰지 않는 모델에는 두지 않는다.
    `hosted_tool_pricing` 은 공급사가 실행하는 도구(web_search)를 실을 모델에만 둔다. 없는 모델에 그 도구를 실으면
    호출 층이 공급사를 부르기 전에 거부한다(client.py 의 `call_tools`).
    """

    provider: Annotated[str, Field(min_length=1)]
    api_model_id: Annotated[str, Field(min_length=1)]
    label: str
    synthetic: bool | None = None
    pricing: Pricing
    hosted_tool_pricing: HostedToolPricing | None = None
    context_window_tokens: PositiveInt
    max_input_tokens: PositiveInt | None = None
    max_output_tokens: PositiveInt
    reasoning_output_reserve_tokens: PositiveInt | None = None
    min_cache_tokens: PositiveInt
    pdf: PdfLimits
    structured_output: bool
    lifecycle: Lifecycle
    source_refs: tuple[str, ...]
    notes: tuple[str, ...]


class EmbeddingPricing(_Strict):
    input: Rate


class EmbeddingModelEntry(_Strict):
    """임베딩 모델. 임베딩 호출 길(embedding.py 의 EmbeddingClient)이 경로(`embeddingRoutes`)로 찾아 쓴다."""

    provider: Annotated[str, Field(min_length=1)]
    api_model_id: Annotated[str, Field(min_length=1)]
    label: str
    synthetic: bool | None = None
    pricing: EmbeddingPricing
    dimensions: PositiveInt
    max_input_tokens: PositiveInt
    max_inputs_per_request: PositiveInt
    max_tokens_per_request: PositiveInt
    multilingual: bool | None
    source_refs: tuple[str, ...]
    notes: tuple[str, ...]


class TokenEstimate(_Strict):
    note: str
    latin_chars_per_token: Annotated[float, Field(gt=0)]
    latin_basis: str
    cjk_chars_per_token: Annotated[float, Field(gt=0)]
    cjk_basis: str


class _File(_Strict):
    checked_on: Annotated[str, Field(pattern=r"^\d{4}-\d{2}-\d{2}$")]
    synthetic: bool | None = None
    note: str
    sources: dict[str, AnyUrl]
    token_estimate: TokenEstimate | None = None
    models: dict[str, ModelEntry]
    routes: dict[str, Annotated[tuple[str, ...], Field(min_length=1)]]
    embedding_models: dict[str, EmbeddingModelEntry] | None = None
    embedding_routes: dict[str, str] | None = None


@dataclass(frozen=True)
class ModelConfig:
    """경로가 가리키는 모델 하나. `key` 는 설정 파일에서의 이름이고 기록의 `model` 칸에 남는다."""

    key: str
    entry: ModelEntry

    @property
    def provider(self) -> str:
        return self.entry.provider

    @property
    def api_model_id(self) -> str:
        return self.entry.api_model_id

    @property
    def pricing(self) -> Pricing:
        return self.entry.pricing

    @property
    def max_output_tokens(self) -> int:
        return self.entry.max_output_tokens

    @property
    def hosted_tool_pricing(self) -> HostedToolPricing | None:
        return self.entry.hosted_tool_pricing

    @property
    def min_cache_tokens(self) -> int:
        return self.entry.min_cache_tokens

    @property
    def structured_output(self) -> bool:
        return self.entry.structured_output

    @property
    def reasoning_output_reserve_tokens(self) -> int | None:
        return self.entry.reasoning_output_reserve_tokens


@dataclass(frozen=True)
class EmbeddingModelConfig:
    """임베딩 경로가 가리키는 모델 하나. `key` 는 설정 파일에서의 이름이고 기록의 `model` 칸에 남는다."""

    key: str
    entry: EmbeddingModelEntry

    @property
    def provider(self) -> str:
        return self.entry.provider

    @property
    def api_model_id(self) -> str:
        return self.entry.api_model_id

    @property
    def dimensions(self) -> int:
        return self.entry.dimensions

    @property
    def max_inputs_per_request(self) -> int:
        return self.entry.max_inputs_per_request

    @property
    def pricing(self) -> EmbeddingPricing:
        return self.entry.pricing


@dataclass(frozen=True)
class LlmConfig:
    """`embedding_routes` 는 경로 이름 → 모델 키 하나다(대체 모델이 없다: 벡터 공간이 달라 섞을 수 없다)."""

    models: Mapping[str, ModelConfig]
    routes: Mapping[str, tuple[str, ...]]
    token_estimate: TokenEstimate
    embedding_models: Mapping[str, EmbeddingModelConfig] = field(default_factory=dict[str, EmbeddingModelConfig])
    embedding_routes: Mapping[str, str] = field(default_factory=dict[str, str])


def _issues(error: ValidationError) -> str:
    return "; ".join(f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}" for issue in error.errors())


def load_config(sources: Sequence[ConfigSource]) -> LlmConfig:
    models: dict[str, ModelConfig] = {}
    routes: dict[str, tuple[str, ...]] = {}
    embedding_models: dict[str, EmbeddingModelConfig] = {}
    embedding_routes: dict[str, str] = {}
    token_estimate: TokenEstimate | None = None

    for source in sources:
        try:
            # JSON 으로 바로 읽는다(strict 이지만 JSON 의 배열은 tuple 로, 정수는 실수 칸으로 받는다).
            file = _File.model_validate_json(source.read_text(encoding="utf-8"))
        except OSError as err:
            raise LlmConfigError(f"{source}: 읽을 수 없다: {err}") from err
        except ValidationError as err:
            raise LlmConfigError(f"{source}: {_issues(err)}") from err

        for key, entry in file.models.items():
            if key in models:
                raise LlmConfigError(f"{source}: 모델 {key} 가 중복 정의됐다")
            if file.synthetic:
                if not entry.synthetic:
                    raise LlmConfigError(f"{source}: 가상 파일의 모델 {key} 에 synthetic 표시가 없다")
            else:
                if entry.synthetic:
                    raise LlmConfigError(f"{source}: 가상 모델 {key} 는 synthetic 파일에 둬야 한다")
                if not entry.source_refs:
                    raise LlmConfigError(f"{source}: 모델 {key} 에 출처가 없다")
                for ref in entry.source_refs:
                    if ref not in file.sources:
                        raise LlmConfigError(f"{source}: 모델 {key} 의 출처 {ref} 가 sources 에 없다")
            models[key] = ModelConfig(key=key, entry=entry)
        for name, keys in file.routes.items():
            if name in routes:
                raise LlmConfigError(f"{source}: 경로 {name} 이 중복 정의됐다")
            routes[name] = keys
        # 임베딩 모델은 채팅 모델과 같은 규칙으로 쌓는다(중복·가상 표시·출처).
        for key, embedding in (file.embedding_models or {}).items():
            if key in embedding_models:
                raise LlmConfigError(f"{source}: 임베딩 모델 {key} 가 중복 정의됐다")
            if file.synthetic:
                if not embedding.synthetic:
                    raise LlmConfigError(f"{source}: 가상 파일의 임베딩 모델 {key} 에 synthetic 표시가 없다")
            else:
                if embedding.synthetic:
                    raise LlmConfigError(f"{source}: 가상 임베딩 모델 {key} 는 synthetic 파일에 둬야 한다")
                if not embedding.source_refs:
                    raise LlmConfigError(f"{source}: 임베딩 모델 {key} 에 출처가 없다")
                for ref in embedding.source_refs:
                    if ref not in file.sources:
                        raise LlmConfigError(f"{source}: 임베딩 모델 {key} 의 출처 {ref} 가 sources 에 없다")
            embedding_models[key] = EmbeddingModelConfig(key=key, entry=embedding)
        for name, key in (file.embedding_routes or {}).items():
            if name in embedding_routes:
                raise LlmConfigError(f"{source}: 임베딩 경로 {name} 이 중복 정의됐다")
            embedding_routes[name] = key
        if file.token_estimate is not None:
            token_estimate = file.token_estimate

    for name, keys in routes.items():
        for key in keys:
            if key not in models:
                raise LlmConfigError(f"경로 {name} 이 없는 모델 {key} 를 가리킨다")
    for name, key in embedding_routes.items():
        if key not in embedding_models:
            raise LlmConfigError(f"임베딩 경로 {name} 이 없는 모델 {key} 를 가리킨다")
    if token_estimate is None:
        raise LlmConfigError("tokenEstimate 설정이 어느 파일에도 없다")
    return LlmConfig(
        models=models,
        routes=routes,
        token_estimate=token_estimate,
        embedding_models=embedding_models,
        embedding_routes=embedding_routes,
    )


def resolve_route(config: LlmConfig, route: str) -> tuple[ModelConfig, ...]:
    """경로의 모델들. 첫 모델이 주, 나머지가 대체 순서다."""
    keys = config.routes.get(route)
    if keys is None:
        raise LlmConfigError(f"경로 {route} 가 설정에 없다")
    return tuple(config.models[key] for key in keys)


def resolve_embedding_route(config: LlmConfig, route: str) -> EmbeddingModelConfig:
    """임베딩 경로의 모델 하나. 채팅의 경로와 이름 칸이 따로다."""
    key = config.embedding_routes.get(route)
    if key is None:
        raise LlmConfigError(f"임베딩 경로 {route} 가 설정에 없다")
    return config.embedding_models[key]


def default_config_sources(*, synthetic: bool) -> tuple[ConfigSource, ...]:
    """패키지에 실린 설정 파일. 가상 모델 파일(둘)은 `synthetic` 을 켰을 때만 넣는다.

    `models.json` 은 이 저장소가 정본이고, `models.synthetic.json` 은 esg-lab 의 사본,
    셋째 파일(`models.embedding.synthetic.json`)은 이 저장소의 가상 파일이다(data/README.md).
    """
    data = resources.files("esgapi.core.llm").joinpath("data")
    sources: list[ConfigSource] = [data.joinpath("models.json")]
    if synthetic:
        sources.append(data.joinpath("models.synthetic.json"))
        sources.append(data.joinpath("models.embedding.synthetic.json"))
    return tuple(sources)
