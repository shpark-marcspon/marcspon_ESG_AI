"""실행이 failed 로 끝날 때 run_runs.error_code 에 적히는 값과 사람에게 보일 글(고정 표 — 예외의 원문은 로그에만).

실행기(esgapi/runs/tasks.py)가 정한 것과, 단계가 낸 예외의 클래스를 모듈 경로까지 붙인 이름(<모듈>.<qualname> —
다른 모듈의 같은 이름 예외가 섞이지 않게)으로 고정 표에 접은 것이다. 표에 없는 클래스는 step_error 다(이어받은
하위 클래스도 접지 않는다. 그 클래스 이름도 글도 표에 싣지 않는다 — 문서 글이 섞일 수 있다).
"""

from typing import Final

RUN_ERROR_MESSAGES: Final[dict[str, str]] = {
    # 실행기가 정한 것(failed_step 은 NULL)
    "flow_not_runnable": "이 흐름은 지금 실행할 수 없다(흐름이나 끼움이 등록되어 있지 않다)",
    "document_missing": "실행의 문서가 이 회사에 없다",
    "object_missing": "저장소에 문서 원본이 없다",
    "object_changed": "저장소의 문서 원본이 올림 확인 때의 것과 다르다",
    "object_too_large": "문서 원본이 상한보다 크다",
    "storage_denied": "저장소가 거절했다",
    "storage_unconfigured": "이 프로세스에 저장소 설정이 없다",
    "attempts_exhausted": "진행 없이 끝난 시도가 상한에 닿았다",
    "result_too_large": "결과가 저장 상한보다 크다",
    "versions_mismatch": "실행을 만들 때의 판정 기준을 지금 다시 지을 수 없다(새 실행으로 다시 돌려야 한다)",
    "internal": "실행 중 예상 밖 오류가 났다(워커 로그)",
    "segments_mismatch": "이어 도는 시도의 구획 계획이 앞 시도와 다르다(새 실행으로 다시 돌려야 한다)",  # RM1a
    # 단계가 실패했다(failed_step 은 그 단계)
    "options_rejected": "실행의 옵션이 이 흐름에 맞지 않는다",
    "flow_input_invalid": "흐름의 입력이 맞지 않는다",
    "step_output_invalid": "단계의 산출물이 규칙에 맞지 않는다",
    "embedding_failed": "임베딩 호출이 실패했다",
    "no_text_layer": "문서에 글자 층이 없다(스캔 PDF — 모든 쪽의 글이 비었다)",
    "setup_error": "AI 호출 설정이 없어 실행하지 못했다(운영 관리자 확인)",
    "step_error": "단계가 실패했다(워커 로그)",
    "segments_failed": "구획이 실패해 단계가 실패했다(워커 로그)",  # RM1a — 펼침 단계 fail_run
    "segments_empty": "펼침 단계의 구획이 0개다(이 흐름은 빈 계획을 받지 않는다)",  # RM1a — allow_empty=False
}

# 단계의 예외 클래스의 모듈 경로까지 붙인 이름(<모듈>.<qualname> — 다른 모듈의 같은 이름 예외가 섞이지 않게)
# → error_code(표 밖은 step_error). 열쇠는 문자열이다(runs/calc 는 다른 모듈을 import 하지 않는다 —
# test_calc 가 import 로 견준다).
STEP_ERROR_CODES: Final[dict[str, str]] = {
    "esgapi.core.flows.binding.RunOptionsRejected": "options_rejected",
    "esgapi.core.flows.types.FlowInputError": "flow_input_invalid",
    "esgapi.core.flows.types.FlowOutputError": "step_output_invalid",
    "esgapi.core.llm.embedding.EmbeddingFailed": "embedding_failed",
    "esgapi.core.flows.types.NoTextLayer": "no_text_layer",
    "esgapi.core.flows.binding.RunVersionsMismatch": "versions_mismatch",
    "esgapi.core.llm.errors.LiveSetupError": "setup_error",
    "esgapi.core.llm.errors.LlmConfigError": "setup_error",  # 영문번역 prepare 의 dry-run(TR2)
    "esgapi.core.llm.errors.PromptError": "step_error",  # 봉투 빠짐 = 배포 결함(TR2 — 명시)
    # RM1a 펼침 단계: 앞 둘은 FlowStepFailed 의 __cause__(failed_step = 펼침), 셋째는 run_flow 밖(failed_step NULL)
    "esgapi.core.flows.types.SegmentsFailed": "segments_failed",
    "esgapi.core.flows.types.SegmentsEmpty": "segments_empty",
    "esgapi.core.flows.types.SegmentPlanMismatch": "segments_mismatch",
}


# 실행 치명(RM1b 635-1 — 감독 답 Q2): 구획 run 이 이 클래스로 실패하면 그 구획의 실패가 아니라 「이 실행 전체가 성립하지
# 않음」이다. 정책(fail_run·pass_to_gather)과 상관없이 실행 failed·failed_step = 펼침 단계·code 는 STEP_ERROR_CODES 의
# 값(PromptError 는 step_error). 직렬(RowEvents.segment_failed)과 구획 쪽지가 같은 집합. 정확 일치(하위 클래스 0).
RUN_FATAL_ERRORS: Final[frozenset[str]] = frozenset(
    {
        "esgapi.core.llm.errors.LiveSetupError",
        "esgapi.core.llm.errors.LlmConfigError",
        "esgapi.core.llm.errors.PromptError",
        "esgapi.core.flows.binding.RunVersionsMismatch",
        "esgapi.core.flows.binding.RunOptionsRejected",
        "esgapi.core.flows.types.FlowInputError",
    }
)


def run_fatal(err_type: type[BaseException]) -> bool:
    """구획 실패가 실행의 치명인가(RUN_FATAL_ERRORS — 정확 일치)."""
    return f"{err_type.__module__}.{err_type.__qualname__}" in RUN_FATAL_ERRORS


def step_error_code(err_type: type[BaseException], *, default: str = "step_error") -> str:
    """예외 클래스 → error_code(정확 일치 — 하위 클래스는 접지 않는다). 표 밖이면 default(단계 안이면 step_error,
    실행기 쪽이면 internal)."""
    return STEP_ERROR_CODES.get(f"{err_type.__module__}.{err_type.__qualname__}", default)
