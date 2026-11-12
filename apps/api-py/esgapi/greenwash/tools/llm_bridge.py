"""core.llm 의 대화 호출 하나: 프롬프트 id + system·user 글 → 글. 판(엔진)의 타입·프롬프트 표를 모른다.

어느 프롬프트 id 를 쓸지, system 글이 그 판의 프롬프트인지는 부르는 쪽(판의 흐름 — flows/colab_e0.LlmChatBridge)이
정한다.
temperature 는 받은 값을 넘기기만 한다(기본값 없음 — 원천은 판의 엔진). None 이면 싣지 않는다(판의 모델 설정 — AS2b).
"""

from esgapi.core.llm.client import CallRequest, LlmClient
from esgapi.core.llm.types import Success, Tags


class LlmTextCall:
    """글 둘을 변수 `system`·`user` 로 core.llm 템플릿에 넘겨 한 번 부른다. Success 가 아니면 RuntimeError."""

    def __init__(
        self, client: LlmClient, *, route: str, tags: Tags, temperature: float | None, max_output_tokens: int
    ) -> None:
        self.client = client
        self.route = route
        self.tags = tags
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens

    def complete(self, prompt_id: str, system: str, user: str) -> str:
        request = CallRequest[str](
            prompt=prompt_id,
            route=self.route,
            tags=self.tags,
            vars={"system": system, "user": user},
            max_output_tokens=self.max_output_tokens,
            temperature=self.temperature,
        )
        result = self.client.call(request)
        if not isinstance(result, Success):
            raise RuntimeError(f"대화 호출이 성공하지 못했다: {result.kind}")
        return result.text
