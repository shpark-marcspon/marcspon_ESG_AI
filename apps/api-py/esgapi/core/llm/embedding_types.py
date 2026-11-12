"""임베딩 공급사와 주고받는 중립 낱말 셋: 요청(묶음 하나), 답(벡터), 답의 갈래.

잎 모듈이다(esgapi.core.llm.types 만 import 한다). 공급사 포트(core/resources/ports/llm.py)와 어댑터
(providers/mock.py·providers/openai.py)는 낱말을 여기서만 가져오고 embedding.py 를 import 하지 않는다:
embedding.py 는 client.py 를, client.py 는 공급사 포트를 import 하므로 포트가 embedding.py 를 부르면 고리가 되어
`import esgapi.core.llm.client` 만으로 채팅 길까지 죽는다.
"""

from dataclasses import dataclass
from typing import Literal

from esgapi.core.llm.types import ProviderError, ProviderTimeout


@dataclass(frozen=True)
class EmbeddingProviderRequest:
    """공급사에 넘기는 중립 요청(묶음 하나).

    dimensions  모델 설정의 차원. 모의 공급사는 이 길이로 짓고, OpenAI 어댑터는 보내지 않는다(모델의 기본값과 같다).
    """

    api_model_id: str
    inputs: tuple[str, ...]
    dimensions: int

    def to_json(self) -> dict[str, object]:
        """요청 해시에 쓰는 꼴. 기록에는 해시만 실리고 이 본문(입력 글자)은 실리지 않는다."""
        return {"apiModelId": self.api_model_id, "inputs": list(self.inputs), "dimensions": self.dimensions}


@dataclass(frozen=True)
class EmbeddingVectors:
    """공급사의 답(성공). 벡터는 입력 차례다.

    input_tokens  공급사가 보고한 입력 토큰. None = 보고하지 않음(비용을 지어내지 않는다).
    """

    vectors: tuple[tuple[float, ...], ...]
    input_tokens: int | None
    model_id: str | None = None
    # 클라이언트 결과의 Embedded("embedded")와 이름을 가른다.
    kind: Literal["vectors"] = "vectors"


# 뒤 둘은 채팅과 같은 갈래(types.py)다.
type EmbeddingProviderResponse = EmbeddingVectors | ProviderError | ProviderTimeout
