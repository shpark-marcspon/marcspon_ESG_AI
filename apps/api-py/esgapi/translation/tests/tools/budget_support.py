"""금액 바닥 안전 시험의 모의 공급사 꼴(밴드 TRE1 — 실호출 0, 글은 지어낸 것).

최악 사용량: 출력 = 그 요청의 출력 상한을 다 씀, 입력 = 그 요청의 dry_run 어림 입력 토큰 × 2.0(GUARD_FACTOR 의 뜻 —
어림 토큰 대비 실토큰 비율. 「글자 수 × 2」는 영문에서 어림의 8배라 쓰지 않는다 — 발주서 critic B2). 그래서 한 호출의
실비 ≤ 머리 여유(위끝 × 2)다(gpt-4.1·mini `p_out = 4·p_in`).
"""

from collections.abc import Callable
from dataclasses import replace

from esgapi.core.llm.config import default_config_sources, load_config
from esgapi.core.llm.cost import HeuristicTokenEstimator
from esgapi.core.llm.types import Completed, ProviderRequest, ProviderResponse, Usage

ESTIMATOR = HeuristicTokenEstimator(load_config(default_config_sources(synthetic=False)).token_estimate)
INPUT_FACTOR = 2.0

type Reply = Callable[[ProviderRequest], ProviderResponse]


def estimated_input(request: ProviderRequest) -> int:
    """`LlmClient.dry_run` 의 입력 어림과 같은 셈(system 조각들과 user 글을 줄바꿈으로 이음)."""
    user = "".join(getattr(part, "text", "") for part in request.user)
    return ESTIMATOR.estimate("\n".join([*(segment.text for segment in request.system), user]))


def worst_usage(request: ProviderRequest) -> Usage:
    return Usage(
        input_tokens=int(estimated_input(request) * INPUT_FACTOR),
        output_tokens=request.max_output_tokens,
        cache_read_tokens=0,
        cache_write_tokens=0,
    )


def worst(reply: Reply) -> Reply:
    """reply 의 글은 그대로, 성공 답의 사용량만 최악으로."""

    def answer(request: ProviderRequest) -> ProviderResponse:
        got = reply(request)
        return replace(got, usage=worst_usage(request)) if isinstance(got, Completed) else got

    return answer
