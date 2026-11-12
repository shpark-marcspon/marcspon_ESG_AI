"""흐름 scope3.colab@157: 받은 Scope 3 코랩(MARC-ENT-157)을 옮긴 엔진 판 colab_157 의 `run` 을 감싼다.

단계는 열다섯이다(밴드 S3R1, 사용자 결정 MARC-ENT-527 — MARC-ISSUE-499): 카테고리 단계 `c1`…`c9`·`c11`…`c15`(C10
없음, 카테고리 번호 차례)와 `assemble`. 엔진은 0줄이다(MARC-ENT-442).
- 카테고리 단계 k: 템플릿을 거른 판(처리기 없는 시트 — 기업정보·회사별 매핑 등 — 는 다 두고, c-시트는 단계 1..k 의
  카테고리만, 시트 차례 그대로)으로 엔진 `run` 을 부르고 결과는 버린다. 단계 data = 그 단계가 새로 부른 칸의 호출 일지
  (`scope3_journal_157`). 앞 단계 일지는 되감는다(공급사 0). 단계 k 의 시트가 없으면 엔진을 부르지 않는다(빈 일지).
  단계 안에서는 실제 호출 BATCH_CALLS 번·20초마다 체크포인트(partial = 머리 + done + 이 단계 일지) — 협조 마감으로
  끊겨도 다음 시도가 그 자리에서 잇는다(되감기 계산은 c1..k 를 다시 함 — O(k²), 지어낸 1,984행 판 단계 하나 3초 안,
  보고 C0-4).
- assemble: 거르지 않은 템플릿으로 엔진을 한 번(`assemble_run`), 일지 = 앞 단계 data 합. 실제 호출 0 이 정상이다.
  결과 = 지금까지의 `calculate` 꼴 그대로(읽개 거절 포함). partial 은 마감 확인용 `{"v":1,"step":"assemble","done":0,
  "journal":[]}` 이고 이어 돌 때 무시한다(처음부터 다시 되감음).

지금은 C1·C2 와 C4-2·C9-2·C6-2·C5(S3C-b1), C4-1·C9-1(거리 — S3C-b2a), C6-1·C7(출장·통근 거리 — S3C-b2b),
C3·C8 셋·C13 셋(에너지 — S3C-c1a), C12·C15(판매제품 폐기·투자 — S3C-c1b-1), C11·C14(판매제품 사용·프랜차이즈 —
S3C-c1b-2)까지 21키를 다 셈한다(「아직 지원 안 함」 시트는 남지 않는다).
지오코더 어댑터는 실행기가 준다(실제 공급원은 `MARC-ENT-167` held — 아직 잇지 않았다. 일지 밖이다).
그래서 기본 흐름은 그대로 scope3.llm-first@1 이다 —
기본을 이 흐름으로 바꾸는 것은 S3C-c(registration.py 의 DEFAULTS 한 줄).
템플릿 바이트는 여기서 `tools.xlsx_reader.read_workbook` 으로 읽는다(xlsx 를 여는 것은 그 파일뿐 — 처분 ⑤). 받은
바이트 상한은 온실가스 올리기 상한 `GHG_UPLOAD_MAX_BYTES`(20MB — MARC-ENT-593, 계수 책은 읽개 기본값 그대로).
못 읽으면 거절 결과 하나(assemble — 카테고리 단계는 빈 일지). 계수 책은 읽힌 `Workbook` 을 어댑터로 받는다.
엔진이 출력 파일 둘(「진단 파일」·「채운 템플릿」)의 내용을 짓고(`ColabRun.outputs` — S3C-c2), 바이트로 쓰는 것은 아직
시험 덤프뿐이다 — 흐름 파일은 S3C-c3.
실행을 멈추는 것(밴드 S3K3 — MARC-ISSUE-521): 설정 결함·공급사 거절(401·403·404·429 크레딧 소진)·실행 비용 상한은 일지
게이트웨이가 엔진 밖으로 빼내 단계 실패가 된다(scope3_journal_157 머리말 (d)~(f)). 데이터 탓 시트 예외·그 밖의 공급사
오류는 코랩대로 done 이고 결과의 시트 status·llmCalls 에 남는다 — assemble 이 그 수를 경고 한 줄로 낸다.
"""

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import Final

from esgapi.core.flows.registry import make_flow
from esgapi.core.flows.types import Carried, Flow, FlowStep, StepContext, StepOutput
from esgapi.core.llm.errors import soft_deadline_in
from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.colab_157.pipeline import ColabRejected, ColabRun, FailedSheet, run
from esgapi.inventory.engines.scope3.colab_157.ports import Geocoder, LlmGateway
from esgapi.inventory.engines.scope3.colab_157.serialize import rejected_to_dict, result_to_dict
from esgapi.inventory.engines.scope3.colab_157.template import match_sheet_processor
from esgapi.inventory.flows.scope3_journal_157 import (
    JOURNAL_VERSION,
    Entry,
    JournalGateway,
    read_entries,
    read_resume,
    unescaped,
)
from esgapi.inventory.tools.scope3_sheets.grid import Workbook
from esgapi.inventory.tools.xlsx_reader import GHG_UPLOAD_MAX_BYTES, ReaderProblem, read_workbook

logger = logging.getLogger(__name__)

RESULT_SHAPE: Final = "scope3.colab.result@1"
CATEGORY_STEPS: Final = ("c1", "c2", "c3", "c4", "c5", "c6", "c7", "c8", "c9", "c11", "c12", "c13", "c14", "c15")
"""카테고리 단계(카테고리 번호 차례 — engines/…/template.py 의 처리기 category, C10 없음)."""
ASSEMBLE: Final = "assemble"


@dataclass(frozen=True, slots=True, kw_only=True)
class ColabInputs:
    template: bytes
    report_year: int
    route: str
    tags: Tags


@dataclass(frozen=True, slots=True, kw_only=True)
class ColabAdapters:
    llm: LlmGateway
    factor_book: Workbook
    geocoder: Geocoder


def _soft_deadline(error: BaseException) -> bool:
    """엔진의 넓은 except 자리에 주입하는 「다시 던질지」 판별 — Celery soft limit 이 사슬에 있으면 참(MARC-ISSUE-414,
    밴드 S3L1. 엔진은 core.llm.errors 를 모른다). 참이면 그 예외는 시트 실패로 남지 않고 실행기가 미룬다."""
    return soft_deadline_in(error) is not None


def category_step(sheet_name: str) -> str | None:
    """시트가 속한 카테고리 단계(엔진과 같은 `match_sheet_processor`). 처리기가 없으면 None."""
    processor = match_sheet_processor(sheet_name)
    return None if processor is None else "c" + processor.category.removeprefix("Category")


def filtered(template: Workbook, step: str) -> Workbook:
    """단계 1..step 의 c-시트와 처리기 없는 시트(차례 그대로). defined_names 는 그대로(엔진이 읽는 곳 0)."""
    allowed = set(CATEGORY_STEPS[: CATEGORY_STEPS.index(step) + 1])
    kept = tuple(s for s in template.sheets if (c := category_step(s.name)) is None or c in allowed)
    return Workbook(kept, template.defined_names)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def book_sha256(book: Workbook) -> str:
    """읽힌 계수 책의 지문(repr — 같은 바이트를 같은 읽개로 읽으면 같다). 바뀌면 경고만 한다(read_resume)."""
    return _sha256(repr(book).encode("utf-8"))


def _carried_journal(carried: Carried, steps: Iterable[str]) -> list[Entry]:
    out: list[Entry] = []
    for name in steps:
        entries = read_entries(carried[name].data.get("journal"))
        if entries is None:
            raise ValueError(f"단계 {name} 의 일지 꼴이 틀렸다")
        out.extend(entries)
    return out


def _engine(
    template: Workbook, inputs: ColabInputs, adapters: ColabAdapters, llm: LlmGateway
) -> ColabRun | ColabRejected:
    return run(
        template,
        adapters.factor_book,
        inputs.report_year,
        llm,
        adapters.geocoder,
        inputs.tags,
        inputs.route,
        reraise=_soft_deadline,
    )


def _category(step: str) -> Callable[[ColabInputs, ColabAdapters, Carried, StepContext], StepOutput]:
    before = CATEGORY_STEPS[: CATEGORY_STEPS.index(step)]

    def run_step(inputs: ColabInputs, adapters: ColabAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
        template = read_workbook(inputs.template, max_bytes=GHG_UPLOAD_MAX_BYTES)
        if isinstance(template, ReaderProblem) or all(category_step(s.name) != step for s in template.sheets):
            return StepOutput(data={"journal": []})  # 읽개 거절은 assemble 이 결과로 낸다
        template_sha = _sha256(inputs.template)
        book_sha = book_sha256(adapters.factor_book)
        resumed = read_resume(ctx.resume, template_sha256=template_sha, factor_book_sha256=book_sha, step=step)
        gateway = JournalGateway(
            adapters.llm,
            replay=[*_carried_journal(carried, before), *resumed.entries],
            carried=resumed.entries,
            base_done=resumed.done,
            head={"v": JOURNAL_VERSION, "templateSha256": template_sha, "factorBookSha256": book_sha, "step": step},
            checkpoint=ctx.checkpoint,
        )
        unescaped(lambda: _engine(filtered(template, step), inputs, adapters, gateway))
        return StepOutput(data={"journal": gateway.journal()})

    return run_step


def assemble_run(
    inputs: ColabInputs,
    adapters: ColabAdapters,
    journal: Iterable[Entry],
    checkpoint: Callable[..., None] | None = None,
) -> ColabRun | ColabRejected | ReaderProblem:
    """거르지 않은 템플릿으로 엔진을 한 번, 일지를 되감아(assemble 단계와 대조 덤프가 같이 쓴다).
    읽개가 못 읽으면 그 값."""
    template = read_workbook(inputs.template, max_bytes=GHG_UPLOAD_MAX_BYTES)
    if isinstance(template, ReaderProblem):
        return template
    gateway = JournalGateway(
        adapters.llm,
        replay=journal,
        head={"v": JOURNAL_VERSION, "step": ASSEMBLE},
        checkpoint=checkpoint if checkpoint is not None else _discard,
        record=False,
    )
    result = unescaped(lambda: _engine(template, inputs, adapters, gateway))
    if gateway.real_calls:
        logger.warning("scope3_journal_assemble_real_calls calls=%s", gateway.real_calls)
    return result


def _discard(partial: object, *, done: int, total: int) -> None:
    return None


def _assemble(inputs: ColabInputs, adapters: ColabAdapters, carried: Carried, ctx: StepContext) -> StepOutput:
    result = assemble_run(inputs, adapters, _carried_journal(carried, CATEGORY_STEPS), ctx.checkpoint)
    if isinstance(result, ReaderProblem):
        detail = f"{result.kind} {result.where}: {result.detail}"
        return StepOutput(data={"results": [rejected_to_dict(RESULT_SHAPE, "reader_problem", detail)]})
    if isinstance(result, ColabRun):
        _log_problems(result)
    return StepOutput(data={"results": [result_to_dict(result, RESULT_SHAPE)]})


def _log_problems(result: ColabRun) -> None:
    """done 인 실행 안의 시트 실패·LLM 실패 수를 운영자 로그 한 줄로(밴드 S3K3 — 수만, 시트 이름·오류 글·기업 원문 0).
    결과 dict 는 그대로다."""
    failed_sheets = sum(1 for outcome in result.sheets if isinstance(outcome, FailedSheet))
    llm_failed = sum(
        n for counts in result.llm_calls.by_prompt.values() for via, n in counts.items() if via.startswith("failed:")
    )
    if failed_sheets or llm_failed:
        logger.warning("scope3_result_problems failed_sheets=%s llm_failed=%s", failed_sheets, llm_failed)


FLOW: Final[Flow] = make_flow(
    module="inventory.scope3",
    id="scope3.colab@157",
    input_shape="scope3.colab.input@1",
    inputs=ColabInputs,
    adapters=ColabAdapters,
    result_shapes=(RESULT_SHAPE,),
    steps=(
        *(FlowStep(name=step, run=_category(step)) for step in CATEGORY_STEPS),
        FlowStep(name=ASSEMBLE, run=_assemble),
    ),
)
