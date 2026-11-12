"""비용 계산과 토큰 어림. 단가는 설정 파일에서 온다(코드에 수치가 없다)."""

import math
import re
from typing import Protocol

from esgapi.core.llm.config import HostedToolPricing, Pricing, TokenEstimate
from esgapi.core.llm.types import Usage

_PER_MTOK = 1_000_000


def round_usd(value: float) -> float:
    """1e-8 달러에서 반올림해 부동소수 오차를 지운다.

    esg-lab 의 `Math.round(v * 1e8) / 1e8` 과 같은 값이 나오게 반올림은 「절반은 위로」다
    (파이썬의 round 는 절반을 짝수 쪽으로 보낸다).
    """
    return math.floor(value * 1e8 + 0.5) / 1e8


def compute_cost_usd(
    usage: Usage, pricing: Pricing, hosted_calls: int = 0, hosted: HostedToolPricing | None = None
) -> float:
    """사용량과 단가로 비용(USD)을 계산한다. 단가는 100만 토큰당 값이다.

    장문 구간이 있는 모델은 입력 합계(캐시 포함)가 기준을 넘으면 요청 전체에 장문 단가를 적용한다.
    공급사가 보고하지 않은(None) 캐시 토큰은 0 으로 계산한다. 호출 쪽이 경고로 따로 알린다.
    `hosted_calls` 는 공급사가 실행한 도구(web_search) 호출 수다. 건당 요금(`hosted`)을 곱해 더한다. 0 이면(기본)
    지금까지와 같은 값이다. 건당 요금이 없는 모델에 그 도구를 싣는 것은 호출 층이 미리 막는다.
    """
    cache_read = usage.cache_read_tokens or 0
    cache_write = usage.cache_write_tokens or 0
    total_input = usage.input_tokens + cache_read + cache_write
    long = pricing.long_context
    rates = long if long is not None and total_input > long.above_input_tokens else pricing
    micro = (
        usage.input_tokens * rates.input
        + usage.output_tokens * rates.output
        + cache_read * rates.cache_read
        + cache_write * rates.cache_write
    )
    if hosted_calls == 0 or hosted is None:
        return round_usd(micro / _PER_MTOK)
    return round_usd(micro / _PER_MTOK + hosted_calls * hosted.web_search_per_call)


class TokenEstimator(Protocol):
    def estimate(self, text: str) -> int: ...


# 한글 자모·가나·호환 자모·한자(확장 A, 통합)·한글 음절. esg-lab 의 정규식과 같은 여섯 구간이다.
_CJK = re.compile("[ᄀ-ᇿ぀-ヿ㄰-㆏㐀-䶿一-鿿가-힯]")


class HeuristicTokenEstimator:
    """글자 수로 토큰 수를 어림한다. 과금 근거가 아니라 사전 경고와 dry-run 용이다.

    글자 수는 esg-lab(JS 의 `text.length`)과 같게 UTF-16 단위로 센다: 그림 글자처럼 BMP 밖의 글자는 둘로 센다.
    """

    def __init__(self, config: TokenEstimate) -> None:
        self._config = config

    def estimate(self, text: str) -> int:
        cjk = len(_CJK.findall(text))
        other = len(text.encode("utf-16-le")) // 2 - cjk
        return math.ceil(cjk / self._config.cjk_chars_per_token + other / self._config.latin_chars_per_token)
