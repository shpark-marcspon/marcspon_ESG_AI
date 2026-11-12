"""협조 마감: 시도가 소프트 시간 제한에 닿기 전에 스스로 접는 때와 그 신호.

마감 = 시도 시작(monotonic) + 소프트 제한 − 여유. 실행기의 사건 받는 쪽(단계 시작·단계 안 체크포인트)이 자기 쓰기 블록을
닫은 뒤 마감을 지났으면 RunYield 를 낸다. 실행기는 그 시도를 접고(부분 산출은 체크포인트가 이미 저장했다) 실행을 다시
넣는다. 소프트 제한은 뒷받침이다 — LLM 호출 한가운데서 나면 공급사 오류 값으로 삼켜진다(core/llm/client.py 의 _invoke).

★ RunYield 는 BaseException 의 자식이다(Exception 이 아니다): 흐름(core/flows/run.py 의 except Exception)·단계·LLM 층의
  `except Exception` 이 잡지 못해 step_failed 가 불리지 않고 run_flow 밖으로 바로 나온다(P19 가 문다).
★ 무효 조건: 체크포인트 사이 한 칸이 여유(60초)보다 길면 소프트 제한이 먼저 난다.
"""

from typing import Final

DEADLINE_MARGIN_S: Final = 60  # 어림(잰 값이 아니다)


class RunYield(BaseException):
    """이 시도를 접는다(마감을 지났거나, 내 시도가 더는 이 실행의 주인이 아니다). 실행기만 잡는다."""


def deadline_of(*, started: float, soft_limit_s: int) -> float:
    """시도 시작(monotonic 초)과 소프트 제한(초) → 마감(monotonic 초)."""
    return started + soft_limit_s - DEADLINE_MARGIN_S
