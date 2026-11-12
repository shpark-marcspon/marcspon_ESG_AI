"""엔진의 바깥 하나: LLM 대화 호출(포트). 엔진은 core.llm 을 모른다 — 다리(tools/llm_bridge.py)가 이 꼴을 채운다.

코랩의 `client.messages.create` 는 잘림·거절에 예외를 내지 않고 응답을 돌려준다(R/2147-2153·6389-6396 —
그 글로 계속한다).
그래서 포트도 잘림·거절을 글로 돌려주고 `ending` 에 갈래를 남긴다(엔진이 결과 warnings 에 llm_truncated·llm_refused).
SDK 가 예외를 내던 자리(공급사 오류·시간 초과·예산)는 예외 하나 `LlmCallFailed` — 코랩의 같은 except 에 잡힌다(W7 갈래).
포트는 글을 strip 하지 않는다 — 코랩의 strip 은 자리마다 엔진이 한다.
"""

from dataclasses import dataclass
from typing import Literal, Protocol

from esgapi.translation.engines.colab_158.prompts import Site

type Role = Literal["translate", "review"]
"""역할: translate = 번역·윤문·게이트·자동수정(코랩 TRANSLATION_MODEL), review = 검수(코랩 haiku 고정 — W3)."""


class LlmCallFailed(Exception):  # 코랩의 SDK 예외 자리
    """LLM 호출이 실패했다(공급사 오류·시간 초과·예산 상한). 메시지는 다리가 결과의 kind 를 싣는다."""


@dataclass(frozen=True)
class GatewayText:
    """호출 하나의 답 글. ending: complete = 끝까지, truncated = 출력 상한에서 잘림(잘린 글),
    refused = 거절(거절 글)."""

    text: str
    ending: Literal["complete", "truncated", "refused"]


class LlmGateway(Protocol):
    def complete(self, site: Site, role: Role, system: str, user: str, max_tokens: int) -> GatewayText:
        """한 번 부른다. 실패면 LlmCallFailed."""
        ...
