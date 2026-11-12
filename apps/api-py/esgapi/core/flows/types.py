"""흐름의 값. 레지스트리(registry.py)와 실행(run.py)이 각각 여기에 기댄다.

흐름 = 이름 붙은 단계의 차례. 단계 함수는 순수하다: (입력, 어댑터, 앞 단계들의 산출물, 문맥) → 산출물.
파일·DB·LLM·큐는 어댑터로만 닿는다. 단계의 산출물(StepOutput)은 체크포인트의 단위라 data 가 JSON 으로 왕복해야 한다.

단계는 두 종류다(RM1a — sid:MARC-ENT-618):
  장벽(FlowStep)   지금까지의 단계. 단계 하나가 한 번에 산출물 하나를 낸다. 모음 단계도 장벽이다(펼침 뒤에 놓인 것).
  펼침(FanoutStep) 앞 장벽들의 산출물에서 구획(Segment) 목록을 짓고(plan) 구획마다 run 을 부른다. 구획의 경계와 뜻은
                   모듈이 정한다 — core 는 구획 열쇠(SegmentKey)를 불투명한 위치 표지로만 다룬다. 산출물은
                   {"segments": [구획마다 열쇠·status·data|errorCode]} 이고 뒤 모음 단계가 carried 로 받는다.
★ 모듈이 지킬 계약(펼침 — 무효 조건: 이것을 어기면 이어 돌기·RM1b 병렬이 다른 값을 낸다):
  - plan 은 결정적이다. 같은 입력·carried → 같은 구획 목록·차례(LLM·시계·난수 0). 이어 도는 시도가 다시 셈한다.
  - 구획 run 은 다른 구획의 산출·차례·공유 상태에 기대지 않는다(입력은 inputs·어댑터·carried·그 구획 하나).
  - 구획 열쇠의 span 에는 문서의 글을 싣지 않는다 — 쪽·블록 번호 같은 위치 표지만(열쇠는 DB 와 기록에 남는다).
"""

import hashlib
import json
import re
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from typing import Any, Final, Literal, NoReturn, Protocol, cast


class FlowRegistryError(Exception):
    """선언이나 등록이 틀렸다(이름 꼴, 겹침, dataclass 아님, 같은 흐름 두 번, 남의 모듈의 기본값)."""


class FlowInputError(Exception):
    """입력·어댑터의 꼴이 틀렸거나, 넘겨받은 산출물이 모자라거나, 없는 단계다. 어떤 단계도 부르기 전에 난다."""


class SegmentsFailed(Exception):
    """on_failure="fail_run" 인 펼침 단계에서 구획이 영구 실패했다(첫 실패에서 남은 구획을 부르지 않고 멈춘다).

    밖으로는 FlowStepFailed 의 __cause__ 로 나온다(실행기의 code segments_failed)."""


class SegmentsEmpty(Exception):
    """allow_empty=False 인 펼침 단계의 계획이 구획 0개다. FlowStepFailed 의 __cause__(code segments_empty)."""


class SegmentPlanMismatch(Exception):
    """이어 도는 시도의 계획이 저장된 계획과 다르다(plan 이 결정적이지 않거나 입력이 바뀌었다).

    사건 받는 쪽(실행기의 segments_planned)이 던지고 run_flow 는 그대로 올린다(FlowStepFailed 로 감싸지 않는다 —
    실행기의 code segments_mismatch, 실패 단계 없음). 넘겨받은 segments_done 에 계획 밖 열쇠가 있어도
    run_flow 가 던진다."""


class SegmentFatal(Exception):
    """구획 실패가 「이 실행 전체가 성립하지 않음」이다(RM1b 635-1 — 실행기의 치명 표). segment_failed 받는 쪽이 던진다.

    run_flow 는 이것을 받는 쪽의 예외로 그대로 올리지 않고 단계 실패로 접는다: step_failed 뒤 FlowStepFailed(펼침 단계)
    의 __cause__ = cause(원래 예외 — 실행기가 그 클래스로 code 를 짓는다)."""

    def __init__(self, cause: Exception) -> None:
        super().__init__(f"구획의 치명 실패: {type(cause).__name__}")
        self.cause = cause


class FlowOutputError(Exception):
    """단계의 산출물이 규칙을 어겼다(JSON 왕복이 안 됨, 파일 이름 겹침, 끝 산출물의 결과·파일 규칙).

    밖으로는 FlowStepFailed 의 __cause__ 로만 나온다.
    """


class NoTextLayer(Exception):
    """문서의 모든 쪽에 글이 없다(글자 층 없는 스캔 PDF).

    실행기의 고정 표(runs/calc/errors.py)가 no_text_layer 로 접는다.
    """


@dataclass(frozen=True, slots=True, kw_only=True)
class OutputFile:
    """단계가 낸 파일. 마지막 단계의 것은 흐름이 선언한 output_files 가운데 하나의 이름이다."""

    name: str
    media_type: str
    content: bytes


@dataclass(frozen=True, slots=True, kw_only=True)
class StepOutput:
    """단계의 산출물 = 체크포인트의 단위. data 는 json.dumps 로 직렬화되어야 한다. 큰 이진 산출물은 files 로."""

    data: dict[str, object]
    files: tuple[OutputFile, ...] = ()


type Carried = Mapping[str, StepOutput]
"""단계 이름 → 그 단계의 산출물(앞 단계들의 것)."""


def _discard(partial: Mapping[str, object], done: int, total: int) -> None:
    return None


@dataclass(frozen=True, slots=True, kw_only=True)
class StepContext:
    """단계 함수의 넷째 인자. 긴 단계가 단계 안에서 이어 돌 때 쓴다(지금 inventory 의 흐름 둘은 쓰지 않는다).

    resume        이 단계가 앞 실행에서 남긴 부분 산출물(없으면 None). run_flow 의 resume 이 start_at 의 단계에만 온다.
    checkpoint()  부분 산출물을 남긴다. run_flow 가 JSON 왕복한 값을 step_progress 로 내고, 실패하면
                  FlowStepFailed.partial 에 싣는다. 왕복이 안 되면 FlowOutputError(단계 실패).
    """

    resume: Mapping[str, object] | None
    on_checkpoint: Callable[[Mapping[str, object], int, int], None] = field(default=_discard, repr=False, compare=False)
    """run_flow 가 단다. 단계는 이것 대신 checkpoint() 를 부른다. 기본값은 버린다 —
    StepContext(resume=…) 로 단계 함수 하나를 run_flow 없이 부를 수 있게."""

    def checkpoint(self, partial: Mapping[str, object], *, done: int, total: int) -> None:
        self.on_checkpoint(partial, done, total)


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowStep[I, A]:
    """이름 붙은 단계 하나. I·A 는 그 흐름의 입력·어댑터 dataclass 다."""

    name: str
    run: Callable[[I, A, Carried, StepContext], StepOutput]


SEGMENT_KIND: Final = re.compile(r"[a-z][a-z0-9_]{0,31}")
"""구획 열쇠 kind 의 꼴(1~32자 — 실행기의 run_segments.kind varchar(32)). 꼴만 본다(뜻은 모듈의 것)."""
SEGMENT_SPAN_MAX_CHARS: Final = 200
SEGMENT_DOCUMENT_SHA256: Final = re.compile(r"[0-9a-f]{64}")
"""구획 열쇠 document_sha256 의 꼴(16진 소문자 64자)."""
SEGMENT_PARSER_VERSION: Final = re.compile(r"[A-Za-z0-9._-]{1,64}")
"""구획 열쇠 parser_version 의 꼴(1~64자)."""
SEGMENT_DATA_MAX_OCTETS: Final = 512 * 1024
"""구획 산출 data 의 앱 상한(json 기본 구분자로 적은 UTF-8 바이트). 실행기의 구획 DB CHECK(1 MiB)의 절반 — 감싼 꼴
(OrderedJSONField)은 최악 두 배라서. 어림이다(잰 값이 아니다). runs 시험이 마이그레이션 CHECK 값과 견준다."""
FANOUT_DATA_MAX_OCTETS: Final = 8 * 1024 * 1024
"""펼침 단계 data 전체(구획 산출 합)의 앱 상한. 실행기의 단계 data DB 상한(16 MiB)의 절반 — 이유는 위와 같다. 어림."""
MAX_SEGMENTS_CEILING: Final = 10_000


@dataclass(frozen=True, slots=True, kw_only=True)
class SegmentKey:
    """구획 하나의 열쇠. kind·span 은 모듈이 정하는 불투명한 표지다(core·runs 는 뜻을 모른다).

    kind             구획의 종류(SEGMENT_KIND 꼴)
    span             그 문서 안의 범위 표지(1~200자 — 쪽·블록 번호 같은 위치만. 문서의 글 0)
    document_sha256  범위가 가리키는 문서의 바이트 해시(문서 없는 흐름이면 None)
    parser_version   범위를 지은 파서의 판(없으면 None)
    """

    kind: str
    span: str
    document_sha256: str | None
    parser_version: str | None


def segment_key_fields(key: SegmentKey) -> dict[str, object]:
    """열쇠의 정규화 칸(JSON 이름). None 도 null 로 싣는다."""
    return {
        "kind": key.kind,
        "span": key.span,
        "documentSha256": key.document_sha256,
        "parserVersion": key.parser_version,
    }


def segment_key_text(fields: Mapping[str, object]) -> str:
    """정규화 칸의 글(열쇠 차례 고정 = 정렬, ensure_ascii=False, 구분자 (",",":")). DB 의 jsonb 는 열쇠 차례를 바꿔
    돌려주므로 그 값에서 다시 셈해도 같은 글이 나와야 한다."""
    return json.dumps(dict(fields), sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def segment_key_sha256(key: SegmentKey) -> str:
    """구획 열쇠의 해시(16진 64자). 실행 안에서 구획을 가리키는 값이다."""
    return hashlib.sha256(segment_key_text(segment_key_fields(key)).encode("utf-8")).hexdigest()


def segment_key_of(fields: Mapping[str, object]) -> SegmentKey:
    """정규화 칸 → 열쇠(저장소에서 꺼낸 값). 칸이 다르거나 꼴이 틀리면 ValueError."""
    if set(fields) != {"kind", "span", "documentSha256", "parserVersion"}:
        raise ValueError(f"구획 열쇠의 칸이 틀렸다: {sorted(fields)}")
    kind, span = fields["kind"], fields["span"]
    sha, parser = fields["documentSha256"], fields["parserVersion"]
    if not isinstance(kind, str) or not isinstance(span, str):
        raise ValueError("구획 열쇠의 kind·span 이 글이 아니다")
    if not (sha is None or isinstance(sha, str)) or not (parser is None or isinstance(parser, str)):
        raise ValueError("구획 열쇠의 documentSha256·parserVersion 이 글이나 null 이 아니다")
    return SegmentKey(kind=kind, span=span, document_sha256=sha, parser_version=parser)


def segment_key_problem(key: object) -> str | None:
    """열쇠의 꼴 검사. 맞으면 None, 틀리면 까닭(kind 는 꼴만 — Q6)."""
    if not isinstance(key, SegmentKey):
        return f"구획 열쇠가 SegmentKey 가 아니다: {type(key).__name__}"
    # 칸의 꼴은 선언이 str 이어도 모듈이 다른 값을 실을 수 있다(dataclass 는 꼴을 보지 않는다) — object 로 본다
    kind = cast("object", key.kind)
    span = cast("object", key.span)
    if not isinstance(kind, str) or SEGMENT_KIND.fullmatch(kind) is None:
        return f"구획 kind 의 꼴이 틀렸다: {kind!r}"
    if not isinstance(span, str) or not 1 <= len(span) <= SEGMENT_SPAN_MAX_CHARS:
        return f"구획 span 은 1~{SEGMENT_SPAN_MAX_CHARS}자 글이어야 한다"
    optional = (
        ("document_sha256", cast("object", key.document_sha256), SEGMENT_DOCUMENT_SHA256),
        ("parser_version", cast("object", key.parser_version), SEGMENT_PARSER_VERSION),
    )
    for name, value, pattern in optional:
        if value is not None and (not isinstance(value, str) or pattern.fullmatch(value) is None):
            return f"구획 {name} 은 None 이나 꼴({pattern.pattern})에 맞는 글이어야 한다"
    return None


@dataclass(frozen=True, slots=True, kw_only=True)
class Segment:
    """계획의 구획 하나: 열쇠와 그 구획의 입력(JSON 왕복 — run_flow 가 왕복한 값을 run 에 준다)."""

    key: SegmentKey
    input: dict[str, object]


@dataclass(frozen=True, slots=True, kw_only=True)
class SegmentOutput:
    """구획 하나의 산출(파일 없음). data 는 JSON 으로 왕복해야 하고 SEGMENT_DATA_MAX_OCTETS 안이다."""

    data: dict[str, object]


@dataclass(frozen=True, slots=True, kw_only=True)
class SegmentFailure:
    """그 실행 안에서 영구 실패로 끝난 구획(error_code 는 실행기가 지은 code)."""

    error_code: str


type SegmentEnded = SegmentOutput | SegmentFailure
"""그 실행 안에서 끝난 구획(done·failed). 이어 도는 시도는 이것을 다시 부르지 않는다."""

type SegmentFailurePolicy = Literal["fail_run", "pass_to_gather"]


@dataclass(frozen=True, slots=True, kw_only=True)
class FanoutStep[I, A]:
    """펼침 단계. 칸 넷(on_failure·allow_empty·max_segments 와 이름·함수)에 기본값이 없다 — 흐름이 꼭 밝힌다.

    plan          (입력, 앞 단계들의 산출물) → 구획 목록(차례가 모음의 차례). 결정적이어야 한다(머리말 ★)
    run           (입력, 어댑터, 앞 단계들의 산출물, 그 구획, 문맥) → 그 구획의 산출. 문맥의 resume 은 None,
                  checkpoint() 는 FlowOutputError(구획 안 체크포인트 없음 — 그 구획의 실패)
    on_failure    fail_run = 첫 영구 실패에서 남은 구획을 부르지 않고 단계 실패(SegmentsFailed) ·
                  pass_to_gather = 다 돌고 모음에 status failed 로
    allow_empty   계획 0개일 때: True 면 모음에 빈 목록, False 면 단계 실패(SegmentsEmpty)
    max_segments  계획의 구획 수 상한(1~10,000). 넘으면 단계 실패(FlowOutputError)
    """

    name: str
    plan: Callable[[I, Carried], tuple[Segment, ...]]
    run: Callable[[I, A, Carried, Segment, StepContext], SegmentOutput]
    on_failure: SegmentFailurePolicy
    allow_empty: bool
    max_segments: int


type StepKind = Literal["barrier", "fanout"]

type ResultCheck = Callable[[tuple[dict[str, object], ...]], None]
"""끝 결과 검사 훅(자리 — RM1a 에서 쓰는 흐름 0). 던지면 마지막 단계의 실패(FlowOutputError 로 감싼다)."""


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowOutput:
    """흐름의 끝 산출물: 결과(꼴 여럿일 수 있다. 각각 첫 키가 schemaVersion)와 출력 파일."""

    results: tuple[dict[str, object], ...]
    files: tuple[OutputFile, ...]


@dataclass(frozen=True, slots=True, kw_only=True)
class FlowRun:
    """run_flow 가 돌려주는 것. steps 는 넘겨받은 산출물 + 이번에 지은 산출물(단계의 차례대로)."""

    steps: dict[str, StepOutput]
    output: FlowOutput


@dataclass(frozen=True, slots=True, kw_only=True)
class Flow:
    """등록되는 흐름. make_flow(registry.py)가 짓는다 — 손으로 짓지 않는다(이름 검사를 지나지 않는다).

    adapter_names      어댑터 dataclass 의 칸 이름(칸 차례) = 어댑터 이름표
    optional_adapters  그 가운데 기본값이 None 인 칸(선택 어댑터 — 없으면 흐름이 그 일을 건너뛴다)
    steps              단계 이름(차례대로)
    step_kinds         단계마다 barrier·fanout(steps 와 같은 차례). 지금 등록된 흐름은 전부 barrier
    result_checks      끝 결과 검사 훅(기본 () — 자리만)
    run_step           장벽 단계 하나를 부른다. 입력·어댑터가 선언한 꼴이 아니면 FlowInputError(펼침 이름도)
    fanouts            펼침 단계 이름 → 그 선언(plan·run 은 입력·어댑터 검사로 감싼 것). 장벽 흐름은 빈 사전
    """

    module: str
    id: str
    input_shape: str
    result_shapes: tuple[str, ...]
    output_files: tuple[str, ...]
    inputs: type[object]
    adapters: type[object]
    adapter_names: tuple[str, ...]
    optional_adapters: tuple[str, ...]
    steps: tuple[str, ...]
    step_kinds: tuple[StepKind, ...]
    result_checks: tuple[ResultCheck, ...] = ()
    run_step: Callable[[str, object, object, Carried, StepContext], StepOutput] = field(repr=False, compare=False)
    fanouts: Mapping[str, "FanoutStep[Any, Any]"] = field(
        default_factory=dict[str, "FanoutStep[Any, Any]"], repr=False, compare=False
    )


class FlowEvents(Protocol):
    """실행기가 단계 진행을 받는 포트. 받는 쪽이 예외를 내면 run_flow 는 그대로 올린다."""

    def step_started(self, flow_id: str, step: str) -> None: ...

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        """output 은 그 단계의 산출물(JSON 왕복한 data) — 실행기가 체크포인트로 남긴다."""
        ...

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        """reason = "<예외 클래스>: <글>"."""
        ...

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        """단계 안 진행. partial 은 ctx.checkpoint 에 준 부분 산출물(JSON 왕복한 값)."""
        ...


class NoEvents:
    """사건을 받지 않는다."""

    def step_started(self, flow_id: str, step: str) -> None:
        return None

    def step_finished(self, flow_id: str, step: str, output: StepOutput) -> None:
        return None

    def step_failed(self, flow_id: str, step: str, reason: str) -> None:
        return None

    def step_progress(self, flow_id: str, step: str, done: int, total: int, partial: Mapping[str, object]) -> None:
        return None


NO_EVENTS: Final = NoEvents()


class SegmentEvents(Protocol):
    """실행기가 펼침 단계의 구획 진행을 받는 포트(FlowEvents 와 따로 — 이미 있는 구현을 넓히지 않는다).

    받는 쪽이 예외를 내면 run_flow 는 그대로 올린다(FlowStepFailed 로 감싸지 않는다). keys·key 는 계획의 열쇠다.
    """

    def segments_planned(self, flow_id: str, step: str, keys: tuple[SegmentKey, ...]) -> None:
        """계획을 받는다(시도마다 한 번). 저장된 계획과 다르면 SegmentPlanMismatch 를 던진다."""
        ...

    def segment_started(self, flow_id: str, step: str, key: SegmentKey) -> None: ...

    def segment_finished(self, flow_id: str, step: str, key: SegmentKey, output: SegmentOutput) -> None:
        """output 은 JSON 왕복한 산출."""
        ...

    def segment_failed(self, flow_id: str, step: str, key: SegmentKey, err: Exception) -> str:
        """구획의 run 이 낸 예외나 산출 검사의 FlowOutputError. 그 구획의 error_code 를 돌려준다(code 표는 실행기의
        것). 잠깐 오류면 받는 쪽이 err 를 다시 던진다(그 구획은 끝나지 않고 다음 시도가 다시 부른다)."""
        ...


class SegmentDispatch(Protocol):
    """펼침 단계의 구획을 직접 돌지 않고 밖(실행기의 구획 쪽지 — RM1b)에 맡기는 포트. run_flow(dispatch=…)로만 단다.

    pending 은 그 실행 안에서 아직 끝나지 않은 구획의 열쇠(계획 차례). 받는 쪽은 돌아오지 않는다 — BaseException 으로
    나간다(실행기의 RunParked). 돌아오면 run_flow 가 단계 실패(FlowOutputError)로 접는다. Exception 을 던지면 사건
    받는 쪽의 예외와 같이 그대로 올린다.
    """

    def dispatch(self, flow_id: str, step: str, pending: tuple[SegmentKey, ...]) -> NoReturn: ...


class NoSegmentEvents:
    """구획 사건을 받지 않는다. 실패 구획의 code 는 step_error."""

    def segments_planned(self, flow_id: str, step: str, keys: tuple[SegmentKey, ...]) -> None:
        return None

    def segment_started(self, flow_id: str, step: str, key: SegmentKey) -> None:
        return None

    def segment_finished(self, flow_id: str, step: str, key: SegmentKey, output: SegmentOutput) -> None:
        return None

    def segment_failed(self, flow_id: str, step: str, key: SegmentKey, err: Exception) -> str:
        return "step_error"


NO_SEGMENT_EVENTS: Final = NoSegmentEvents()


class FlowStepFailed(Exception):
    """단계가 실패했다(단계의 예외, 또는 산출물 검사의 FlowOutputError — 원래 예외는 __cause__).

    step       실패한 단계
    completed  그때까지 끝난 단계의 산출물(넘겨받은 것 포함). 실행기는 이것으로 start_at=step 부터 이어 간다
    partial    실패한 단계가 마지막으로 checkpoint 에 남긴 부분 산출물(한 번도 안 남겼으면 None)
    """

    def __init__(self, step: str, *, completed: dict[str, StepOutput], partial: Mapping[str, object] | None) -> None:
        super().__init__(f"단계 {step} 이 실패했다")
        self.step = step
        self.completed = completed
        self.partial = partial
