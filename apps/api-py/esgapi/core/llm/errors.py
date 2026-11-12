"""호출 층이 던지는 예외 셋. 결과의 갈래(LlmResult)와 다르다: 이것들은 설정이나 부르는 쪽의 잘못이다.

공급사가 실패한 것(오류·시간 초과·거부·잘림·스키마 불일치·상한)은 예외가 아니라 결과의 갈래로 돌아온다.
예외 하나: Celery 의 소프트 시간 제한은 갈래로 삼키지 않고 다시 던진다(soft_deadline_in — LH2).
"""


class LlmConfigError(Exception):
    """모델 설정 파일이 틀렸거나, 없는 경로·등록 안 된 공급사·모델 상한을 넘는 출력 토큰을 요청했다."""


class PromptError(Exception):
    """프롬프트 id 의 꼴이 틀렸거나, 템플릿이 없거나, 템플릿의 꼴이 틀렸거나, 변수가 모자라거나 남는다."""


class LiveSetupError(Exception):
    """실제 공급사 호출을 조립할 수 없다(키 없음, 지원하지 않는 공급사, 상한 없음). 부르기 전에 난다."""


# Celery 의 소프트 시간 제한 예외 이름(celery.exceptions 의 것은 billiard.exceptions 의 것과 같은 클래스다 — LH2 ★d).
_SOFT_DEADLINE = "SoftTimeLimitExceeded"
# 사슬(__cause__·__context__)을 따라가는 깊이 상한. SDK 는 한 겹(anthropic 의 APIConnectionError from err)만 싼다.
_CHAIN_DEPTH = 8


def soft_deadline_in(error: BaseException) -> BaseException | None:
    """예외와 그 `__cause__`·`__context__` 사슬에서 Celery 의 소프트 시간 제한(SoftTimeLimitExceeded)을 찾는다.
    없으면 None.

    호출 층(어댑터·_invoke·도구 실행 자리)은 이것이 있으면 공급사 오류 값으로 삼키지 않고 그 예외를 다시 던진다
    (LH2, MARC-ISSUE-411 S3) — 실행기의 outcome_of 가 RunDeferred 로 끝낸다(runs/tasks.py).
    celery·billiard 를 import 하지 않는다: 조상 클래스의 **이름**으로 가른다(providers/gemini.py 의 _ancestor_names 꼴).
    깊이 상한(_CHAIN_DEPTH)과 본 예외 모음으로 고리를 막는다.
    """
    seen: set[int] = set()
    current: BaseException | None = error
    for _ in range(_CHAIN_DEPTH):
        if current is None or id(current) in seen:
            return None
        seen.add(id(current))
        if any(cls.__name__ == _SOFT_DEADLINE for cls in type(current).__mro__):
            return current
        current = current.__cause__ or current.__context__
    return None
