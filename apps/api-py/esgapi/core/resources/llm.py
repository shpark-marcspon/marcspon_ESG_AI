"""포트 `llm`(core/resources/ports/llm.py 의 Provider)의 구현을 고른다.

    make("mock")                          모의 공급사(키 없음)
    make("openai", api_key=키)            실제 공급사. 키는 부르는 쪽(core/llm/setup.py)이 **명시로** 넘긴다
    make("openai", assemble_only=True)    SDK 객체 없이 요청 조립만 하는 어댑터(dry-run 용). 부르면 오류 갈래를 돌려준다

    make_embedding("mock")                임베딩 포트(EmbeddingProvider)의 모의. 이름은 make 의 모의와 같다
    make_embedding("openai", api_key=키)  실제 임베딩 공급사. 임베딩 어댑터가 있는 것은 openai 뿐이다

실제 공급사에 키가 없으면(None·빈 값) SDK 객체를 만들지 않고 LiveSetupError 를 던진다.
SDK 는 고를 때에야 import 한다(안 쓰는 공급사의 SDK 를 읽어 들이지 않는다).
"""

from esgapi.core.llm.errors import LiveSetupError
from esgapi.core.llm.providers.mock import MockEmbeddingProvider, MockProvider
from esgapi.core.resources.ports.llm import EmbeddingProvider, Provider

MOCK_PROVIDERS: tuple[str, ...] = ("mock", "mock-b")
# 실제 호출을 지원하는 공급사.
LIVE_PROVIDERS: tuple[str, ...] = ("openai", "anthropic", "gemini")
# 실제 임베딩 호출을 지원하는 공급사.
EMBEDDING_LIVE_PROVIDERS: tuple[str, ...] = ("openai",)


def make(name: str, *, api_key: str | None = None, assemble_only: bool = False) -> Provider:
    if name in MOCK_PROVIDERS:
        return MockProvider(name)
    if name not in LIVE_PROVIDERS:
        known = ", ".join((*MOCK_PROVIDERS, *LIVE_PROVIDERS))
        raise LiveSetupError(f"공급사 {name} 의 어댑터가 없다. 있는 것: {known}")
    if not assemble_only and (api_key is None or api_key.strip() == ""):
        raise LiveSetupError(
            f"공급사 {name} 의 키가 없다. 실제 공급사는 키 없이 부를 수 없다(모의 공급사와 dry-run 은 키가 필요 없다)"
        )
    key = None if assemble_only else api_key

    if name == "openai":
        from esgapi.core.llm.providers.openai import OpenAIProvider, create_openai_client

        return OpenAIProvider(None if key is None else create_openai_client(key))
    if name == "anthropic":
        from esgapi.core.llm.providers.anthropic import AnthropicProvider, create_anthropic_client

        return AnthropicProvider(None if key is None else create_anthropic_client(key))
    from esgapi.core.llm.providers.gemini import GeminiProvider, create_gemini_client

    return GeminiProvider(None if key is None else create_gemini_client(key))


def make_embedding(name: str, *, api_key: str | None = None, assemble_only: bool = False) -> EmbeddingProvider:
    if name in MOCK_PROVIDERS:
        return MockEmbeddingProvider(name)
    if name not in EMBEDDING_LIVE_PROVIDERS:
        known = ", ".join((*MOCK_PROVIDERS, *EMBEDDING_LIVE_PROVIDERS))
        raise LiveSetupError(f"공급사 {name} 의 임베딩 어댑터가 없다. 있는 것: {known}")
    if not assemble_only and (api_key is None or api_key.strip() == ""):
        raise LiveSetupError(
            f"공급사 {name} 의 키가 없다. 실제 공급사는 키 없이 부를 수 없다(모의 공급사와 dry-run 은 키가 필요 없다)"
        )
    from esgapi.core.llm.providers.openai import OpenAIEmbeddingProvider, create_openai_embedding_client

    return OpenAIEmbeddingProvider(
        None if assemble_only or api_key is None else create_openai_embedding_client(api_key)
    )
