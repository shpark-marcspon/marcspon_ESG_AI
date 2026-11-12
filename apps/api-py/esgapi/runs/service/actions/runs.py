"""실행 만들기: 실행 행과 그 단계 행(두 표)을 한 트랜잭션에 쓰고, 커밋 뒤 큐에 쪽지 하나를 건다 → `@transaction.atomic`
함수(E1b 의 규칙). core 의 문서(selector)와 흐름·끼움 등록부(core.flows)를 읽어 조립하므로 Action 이다(Service·Selector
는 남의 도메인을 import 하지 않는다 — `.importlinter` 계약 바).

    create_run(...)   검사 차례(X1b-2b 처분 ⑫ — 바꾸면 tests/security/test_tenant_paths.py 의 NOT_PASSED 가 빨개진다):
                      [Idempotency-Key 있음(IK1): 그 사람의 그 열쇠로 만든 실행 → 같은 본문 RunReplayed · 다른 본문
                      KeyReused — 쓰기 0] →
                      documentId 있음: 문서(없음·남의 것 → DocumentNotFound, `uploaded` 아님 → DocumentNotUploaded)
                      → 흐름(UnknownFlow) → 문서 없는 흐름이면 DocumentNotAccepted → 끼움(FlowNotRunnable)
                      documentId 없음(ND1): 흐름(UnknownFlow) → 문서 없는 흐름이면 계속, 끼움 없음 FlowNotRunnable,
                      문서 흐름이면 DocumentRequired
                      → [resume_from 있음: 앞 실행 잠금(없음·남의 것 →
                      ResumeNotFound) → 문서·흐름·단계 이름·옵션 다름 → ResumeMismatch → 앞이 failed 아님 →
                      ResumeNotFailed → 앞을 이어 받은 실행이 queued·processing·done → ResumeAlready → 앞 실행과 같은
                      launchKey → LaunchKeyReused(LK1); 옵션·versions 는 앞 것] → 옵션(OptionsRejected — 흐름의 크기
                      상한(BINDINGS.options_limit)·끼움의 check_options) → 판 묶음(VersionsRejected — 끼움의
                      versions_with 가 못 지음, 이어 돌기는 앞 것이라 0) → 실행 행 + 단계 행(흐름이 선언한 차례 —
                      이어 돌면 앞에서부터 이어진 끝난 단계는 done 으로 옮기고 나머지 pending) + 옮긴 단계의 파일
                      행(새 키) → on_commit(큐)
                      → 감사 줄(마지막 문장)
                      [retry 있음(RM1c — 고른 구획만 다시, done 실행만): Idempotency → 문서(위와 같은 code) →
                      resume_from 도 있음 → RetryMismatch → 앞 실행 잠금(없음·남의 것 → RetryNotFound) → 꼴(모듈·
                      흐름·문서·옵션이 앞과 다름 — 빈 options·없는 flowId 는 앞 것) → RetryMismatch → 앞이 done 아님
                      → RetryNotDone(꼴 어긋남이 상태 앞 — 이어 돌기와 같다) → 흐름(앞 flow_id — UnknownFlow, 단계
                      이름 다름 → RetryMismatch)·끼움(DocumentNotAccepted·FlowNotRunnable·DocumentRequired) → 고른
                      단계가 펼침 밖·열쇠 빔·겹침·앞 그 단계 행 밖 → RetrySegmentsUnknown → 앞과 같은 launchKey →
                      LaunchKeyReused → 고른 단계 앞 단계가 done·data 아님(방어) → RetryMismatch →
                      옵션(앞 것 — OptionsRejected) → 판(지금 끼움이 앞 옵션으로 짓는 판 ≠ 앞
                      versions → RetryVersionChanged, 못 지으면 VersionsRejected) → 실행 행(resumed_from = 앞, versions
                      ·options 앞 것) + 단계 행(고른 단계 앞은 done 으로 옮기고 그 단계부터 pending) + 옮긴 단계의 파일
                      행 + 구획 행(아래) → on_commit → 감사 줄 run_created]

★ 거절은 값으로 돌려준다(블록 안에서 던지지 않는다). 거절은 전부 쓰기 앞이라 행 0 이다.
★ 문서 없는 흐름(ND1 — BINDINGS.documentless 가 끼움을 줌)의 실행은 문서 칸이 NULL 이고 감사 줄의 target_label 도
  None 이다. 갈래는 어느 사전에 달렸는가로 가른다(RunFactsBinding isinstance 를 문서 없는 끼움에 쓰지 않는다).
★ 큐에 넣기는 블록 안에서 `transaction.on_commit(<꾸밈 없는 안쪽 함수>, robust=True)` 로 건다(confirm_upload 의
  _sending 꼴 — partial 금지 까닭도 같다). 블록이 되돌려지면 같이 버려지고, 갈고리가 던져도 요청은 201 이다(쪽지를
  잃은 실행은 requeue_runs 가 메운다).
★ 이어 돌기(X1b-2b ⑬·⑬b): 옮긴 단계의 파일 행은 새 실행 id 로 지은 키로 블록 안에서 쓴다. 바이트는 실행기 `_plan` 이
  옮긴다(RC1 — 새 키가 비었으면 앞 실행(사슬)의 키에서. 요청 스레드의 저장소 호출 0 — 옮김 몸은 services 의 resume
  모듈의 carry).
  ★ versions 는 앞 실행의 것을 물려받는다 — 끼움이 RunFactsBinding 이 아니면 지금 코드와 어긋날 수 있다.
★ 구획 옮김(RM1c — 635-4, 판정은 runs/calc/segments.carried_segments): 펼침이 있는 흐름의 이어 돌기·고른 다시만 앞
  실행의 구획을 읽어(selectors.segments_to_carry, 문 하나) 새 실행 id 로 한 번에 쓴다(bulk_create — 장벽 흐름·새 실행은
  구획 쿼리 0). 옮긴(done) 펼침 단계는 행 전부 그대로, 시작 단계는 이어 돌기면 done 만 done·나머지 pending, 고른
  다시면 고른 것 pending·나머지 그대로(안 고른 failed 는 모음에 failed). 옮겨 온 구획 = attempts 0 인 done·failed(이
  실행에서 끝난 행은 ≥1), 임대 NULL, 시각은 앞 것 그대로(firstStartedAt < 새 createdAt 일 수 있다). 직렬 done 의 빈
  data_octets 는 다시 센다(병렬 합 검사가 옮긴 몫도 센다). 실행기는 0줄: 첫 시도 segments_planned 가 저장 계획과 같으면
  0행이고 ended_segments 가 옮긴 끝난 구획을 넘긴다.
  ★ 무효 조건: 앞 실행이 segments_mismatch 로 끝났으면 이어 돌기는 시작 단계 구획을 옮기지 않는다(처음부터 — RM1c 앞
  동작). 파서 판만 바뀐 배포 뒤의 이어 돌기·고른 다시는 옮긴 열쇠(parserVersion 이 든다)가 새 계획과 달라 첫 시도
  segments_mismatch 로 끝난다(versions 에 파서 판이 없어 고른 다시도 409 가 아니다) — 다시 이어 돌면 처음부터다.
  ★ resumed_from_run_id 는 고른 다시도 적는다(D2 — 앞 상태가 done 이면 고른 다시, failed 면 이어 돌기). 넣은
  실행(idempotency_key 가 묶음 열쇠)도 고른 다시 대상이다. 같은 done 실행을 여러 번 고른 다시 해도 된다(D4).
★ 감사 줄(MARC-ENT-295 — action "run")은 이 블록의 **마지막 문장**이다: 세이브포인트로 들어 실행 행과 같이 커밋되고,
  record_event 는 던지지 않으므로(DB 오류도 값) 감사가 실패해도 실행은 만들어진다(AU1a 처분 ⑨⑱).
  actor_user_id 는 키워드 필수다(빠뜨려 조용히 command 로 적히지 않게 — sid:MARC-ISSUE-192 의 4).
★ Idempotency-Key(IK1 — idempotency=(열쇠, 본문 sha256)): 열쇠 찾기가 **첫 문장**이다(검사 앞 — 이어 돌기 재시도가
  ResumeAlready 로 막히지 않게). 찾으면 쓰기·on_commit·감사 0 으로 돌려준다(RunReplayed 의 실행은 지금 값 — 상태가
  첫 응답과 다를 수 있다). 거절(404·409·422)은 행을 남기지 않으므로 열쇠도 남지 않는다 — 고쳐 다시 보내면 새로 판정.
  동시 두 요청은 둘 다 「없음」을 읽고 INSERT 한다: 실행 행 INSERT 를 세이브포인트로 감싸 뒤의 것이 유일 제약
  IDEMPOTENCY_UNIQUE 의 IntegrityError(앞의 것이 커밋할 때까지 기다린 뒤)를 받으면 그 세이브포인트만 되돌리고
  (그 안에 걸린 것 0 — on_commit·감사는 INSERT 뒤) 같은 트랜잭션에서 열쇠로 다시 읽어 같은 판정을 한다(READ
  COMMITTED 라 앞의 것이 보인다). 다른 제약·이름 모름은 다시 던진다(greenwash/service/services/review.py 의 _broken 꼴).
  같은 열쇠의 동시 이어 돌기는 뒤의 것이 lock_run 에서 기다렸다 ResumeAlready 에 닿는다 — 거기서 열쇠로 한 번 더
  판정한다(앞 실행이 보이면 같은 판정, 없으면 ResumeAlready 그대로). 열쇠 없는 요청은 세이브포인트도 0 — 차례·쿼리
  그대로다.
  ★ 무효 조건: 열쇠는 만료되지 않는다(며칠 뒤 같은 열쇠 = 그 옛 실행). 범위는 (세션 회사, 사람)이다 — 운영 관리자는
  작업 회사마다 따로다.
★ launchKey(LK1 — launch_key, 선택): 같이 시작한 실행(사람 동작 한 번)의 묶음 열쇠를 행에 적기만 한다(유일 아님 —
  묶음 셈은 읽을 때 runs/service/selectors/operator.py). 묶음의 범위는 (회사, 만든 사람, 열쇠)다. 다시 하기는 새 열쇠라
  이어 돌기에 앞 실행과 같은 열쇠가 오면 LaunchKeyReused(쓰기 0 — 이어 돌기 검사의 끝, 앞 행은 이미 잠가 읽었다).
  ★ 무효 조건: 이어 돌기가 아닌 새 POST 로 하는 다시 실행·[이 파트만 다시]는 서버가 「같이 시작」과 가르지 못한다 —
  새 열쇠를 짓는 것은 웹의 의무다. 앞의 앞(사슬)의 열쇠는 보지 않는다. 열쇠 없는 요청은 LK1 앞 그대로다.
★ 테스트가 바꿔 끼우는 틈(전부 「부를 때 모듈 속성으로 읽는다」):
    actions.REGISTRY · actions.BINDINGS     흐름과 끼움의 등록부(시험 안의 가짜 흐름을 단다)
    hooks.enqueue_run                       큐 갈고리(core/resources/queue.py)
"""

import contextlib
import json
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, cast, overload

from django.db import IntegrityError, models, transaction

from esgapi.core.auth.principal import Kind
from esgapi.core.flows import binding as flow_ports  # G2c2: 둘째 꼴 RunFactsBinding(isinstance 갈래)
from esgapi.core.flows.binding import BINDINGS, DocumentlessBinding, NoBinding, RunBinding, RunOptionsRejected
from esgapi.core.flows.registry import REGISTRY
from esgapi.core.flows.types import Flow, FlowRegistryError
from esgapi.core.resources import queue as hooks
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.selectors.documents import Document
from esgapi.core.service.services.audit import record_event
from esgapi.runs.calc.keys import file_key
from esgapi.runs.calc.segments import SegmentCarry, carried_segments
from esgapi.runs.models import RunFileRow, RunRow, RunSegmentRow, RunStepRow
from esgapi.runs.service.selectors import runs as selectors
from esgapi.runs.service.selectors.runs import Keyed, Run, RunFile, RunStep

# 큐에 넣는 함수의 꼴: enqueue(company_id=…, run_id=…)
Enqueue = Callable[..., None]
IDEMPOTENCY_UNIQUE = "run_runs_idempotency_uniq"  # migrations/0003_run_idempotency_key.py


@dataclass(frozen=True, slots=True)
class RunCreated:
    run: Run


@dataclass(frozen=True, slots=True)
class RunReplayed:
    """같은 사람이 같은 Idempotency-Key·같은 본문으로 다시 보냈다 — 앞 실행(지금 값). 쓰기 0(IK1)."""

    run: Run


@dataclass(frozen=True, slots=True)
class KeyReused:
    """같은 Idempotency-Key 로 다른 본문을 보냈다(IK1). 쓰기 0."""


@dataclass(frozen=True, slots=True)
class DocumentNotFound:
    """그런 문서가 없다. 다른 회사의 문서도 이 갈래다."""


@dataclass(frozen=True, slots=True)
class DocumentNotUploaded:
    """문서가 아직 `uploaded` 가 아니다(올림 확인 전)."""


@dataclass(frozen=True, slots=True)
class UnknownFlow:
    """모르는 모듈·흐름이거나, 그 흐름이 요청한 모듈의 것이 아니다."""


@dataclass(frozen=True, slots=True)
class FlowNotRunnable:
    """흐름은 있으나 실행기에 끼울 끼움이 없다."""

    flow_id: str


@dataclass(frozen=True, slots=True)
class DocumentRequired:
    """이 흐름은 문서가 있어야 한다(documentId 없음 — ND1)."""


@dataclass(frozen=True, slots=True)
class DocumentNotAccepted:
    """문서 없는 흐름에 documentId 를 주었다(입력은 options — ND1). 남의·없는 문서는 그 앞에서 DocumentNotFound."""


@dataclass(frozen=True, slots=True)
class OptionsRejected:
    message: str  # 사람에게 보일 한 문장(끼움의 글 그대로)


@dataclass(frozen=True, slots=True)
class VersionsRejected:
    message: str  # 사람에게 보일 한 문장(끼움의 글 그대로)


@dataclass(frozen=True, slots=True)
class ResumeNotFound:
    """이어 돌릴 앞 실행이 없다. 다른 회사의 실행도 이 갈래다."""


@dataclass(frozen=True, slots=True)
class ResumeMismatch:
    """앞 실행과 문서·흐름·단계 이름·옵션이 다르다."""

    message: str  # 어긋난 칸(사람에게 보일 한 문장)


@dataclass(frozen=True, slots=True)
class ResumeNotFailed:
    """앞 실행이 failed 가 아니다(실패한 실행만 이어 돈다)."""


@dataclass(frozen=True, slots=True)
class ResumeAlready:
    """앞 실행을 이어 받은 실행이 이미 있다(queued·processing·done)."""


@dataclass(frozen=True, slots=True)
class LaunchKeyReused:
    """이어 돌기에 앞 실행과 같은 launchKey 가 왔다(다시 하기는 새 열쇠 — LK1)."""


@dataclass(frozen=True, slots=True)
class SegmentRetry:
    """done 실행에서 고른 구획만 다시(RM1c). keys = 그 펼침 단계의 구획 열쇠 sha(보낸 차례)."""

    from_run_id: int
    step: str
    keys: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class RetryNotFound:
    """고른 구획을 다시 돌 앞 실행이 없다. 다른 회사의 실행도 이 갈래다."""


@dataclass(frozen=True, slots=True)
class RetryMismatch:
    """앞 실행과 모듈·흐름·문서·옵션·단계 이름이 다르다(또는 resume_from 과 같이 왔다)."""

    message: str


@dataclass(frozen=True, slots=True)
class RetryNotDone:
    """앞 실행이 done 이 아니다(고른 구획 다시는 done 실행만 — 실패한 실행은 이어 돌기)."""


@dataclass(frozen=True, slots=True)
class RetrySegmentsUnknown:
    """고른 단계가 펼침이 아니거나, 고른 열쇠가 비었거나 겹치거나 앞 실행의 그 단계에 없다."""

    message: str


@dataclass(frozen=True, slots=True)
class RetryVersionChanged:
    """지금 끼움이 앞 옵션으로 짓는 판(AI 설정·흐름)이 앞 실행의 판과 다르다 — 처음부터 새 실행으로."""


type CreateResult = (
    RunCreated
    | RunReplayed
    | KeyReused
    | DocumentNotFound
    | DocumentNotUploaded
    | UnknownFlow
    | FlowNotRunnable
    | DocumentRequired
    | DocumentNotAccepted
    | OptionsRejected
    | VersionsRejected
    | ResumeNotFound
    | ResumeMismatch
    | ResumeNotFailed
    | ResumeAlready
    | LaunchKeyReused
)

type RetryRefused = RetryNotFound | RetryMismatch | RetryNotDone | RetrySegmentsUnknown | RetryVersionChanged
"""고른 구획 다시(retry 를 줄 때)만 나는 거절(RM1c)."""

# 검사 갈래가 돌려주는 거절(쓰기 0)
type Refusal = (
    DocumentNotAccepted
    | FlowNotRunnable
    | DocumentRequired
    | UnknownFlow
    | ResumeNotFound
    | ResumeMismatch
    | ResumeNotFailed
    | ResumeAlready
    | LaunchKeyReused
    | RetryRefused
)


def options_too_large(limit: int) -> str:
    """옵션 크기 거절의 글(그 흐름의 상한 — BINDINGS.options_limit)."""
    return f"옵션이 너무 크다(JSON 으로 {limit}바이트까지)"


def options_unencodable() -> str:
    """옵션 글에 짝 없는 서로게이트(JSON 의 \\ud800 따위)가 있어 UTF-8 로 적을 수 없을 때의 거절 글(MARC-ISSUE-340)."""
    return "옵션에 UTF-8 로 적을 수 없는 글자(짝 없는 서로게이트)가 있다"


def _sending(send: Enqueue, *, company_id: int, run_id: int) -> Callable[[], None]:
    """커밋 뒤에 `send(…)` 를 부를 것 하나. 값은 여기서 묶는다(partial 을 쓰지 않는 까닭은 confirm_upload 의 것)."""

    def send_run() -> None:
        send(company_id=company_id, run_id=run_id)

    return send_run


def _broken(err: IntegrityError) -> str | None:
    """IntegrityError 가 어긴 제약의 이름(psycopg 의 diag). 모르면 None."""
    diag = getattr(err.__cause__, "diag", None)
    name = getattr(diag, "constraint_name", None)
    return name if isinstance(name, str) else None


def _replayed(*, company_id: int, actor_user_id: int, idempotency: tuple[str, str]) -> RunReplayed | KeyReused | None:
    """그 사람이 그 열쇠로 만든 실행이 있으면 본문 sha 로 가른다(같음 RunReplayed · 다름 KeyReused). 없으면 None."""
    key, sha = idempotency
    found: Keyed | None = selectors.run_by_key(company_id=company_id, created_by_user_id=actor_user_id, key=key)
    if found is None:
        return None
    return RunReplayed(found.run) if found.body_sha256 == sha else KeyReused()


def _flow(module: str, flow_id: str | None) -> Flow | None:
    """요청의 모듈·흐름 → 흐름. flow_id 가 없으면 그 모듈의 기본 흐름. 없거나 남의 모듈의 것이면 None."""
    try:
        flow = REGISTRY.default_of(module) if flow_id is None else REGISTRY.get(flow_id)
    except FlowRegistryError:
        return None
    return flow if flow.module == module else None


def _carried(steps: Sequence[RunStep]) -> tuple[RunStep, ...]:
    """앞에서부터 이어진 끝난 단계(실행기 _plan 이 carried 로 읽는 것과 같은 판정 — done 이고 data 가 있음)."""
    carried: list[RunStep] = []
    for step in steps:
        if step.status != "done" or step.data is None:
            break
        carried.append(step)
    return tuple(carried)


def _resume_mismatch(
    previous: RunRow, steps: Sequence[RunStep], *, document_id: int | None, flow: Flow, options: Mapping[str, object]
) -> str | None:
    """앞 실행과 어긋난 칸의 글. 같으면 None. 요청 옵션이 비어 있으면 앞 것을 쓰므로 견주지 않는다."""
    if previous.document_id != document_id:
        return "앞 실행과 문서가 다르다"
    if previous.flow_id != flow.id:
        return "앞 실행과 흐름이 다르다"
    if tuple(s.name for s in steps) != flow.steps:
        return "앞 실행의 단계가 지금 흐름의 단계와 다르다"
    if options and dict(options) != previous.options:
        return "앞 실행과 옵션이 다르다(이어 돌기는 앞 실행의 옵션을 쓴다)"
    return None


def _options_too_large(options: Mapping[str, object], limit: int) -> bool:
    """jsonb 를 글로 적은 크기의 어림(json 의 기본 구분자 — finish_run 의 결과 크기와 같은 셈)이 그 흐름의 상한을
    넘는가. 넘으면 400 으로 돌려준다(DB 의 CHECK 는 감싼 꼴의 여유를 둔 그 위의 잠금이다 — runs/models.py).
    짝 없는 서로게이트가 있으면 UnicodeEncodeError 를 그대로 올린다 — 부르는 쪽이 400 으로 거절한다(LH1 — 340)."""
    return len(json.dumps(options, ensure_ascii=False).encode("utf-8")) > limit


def _versions(
    binding: RunBinding | DocumentlessBinding, *, bare: bool, options: Mapping[str, object], company_id: int
) -> dict[str, object]:
    """끼움의 판 몫. 갈래(문서 없는가)는 부르는 쪽이 사전으로 가른 것이다 — 둘째 꼴 isinstance 는 그 갈래 안에서만."""
    if bare:
        if isinstance(binding, flow_ports.DocumentlessFactsBinding):
            return binding.versions_with(options, company_id=company_id)
        return binding.versions(options)
    if isinstance(binding, flow_ports.RunFactsBinding):
        return binding.versions_with(options, company_id=company_id)
    return binding.versions(options)


@dataclass(frozen=True, slots=True)
class _Source:
    """검사를 지난 실행의 자리: 흐름·끼움·옵션과, 앞 실행이 있으면(이어 돌기·고른 다시) 옮길 것."""

    flow: Flow
    binding: RunBinding | DocumentlessBinding
    bare: bool
    options: Mapping[str, object]
    carried: tuple[RunStep, ...] = ()
    previous_files: tuple[RunFile, ...] = ()
    previous_versions: dict[str, object] | None = None
    previous_error: str | None = None
    retry_keys: frozenset[str] | None = None
    segments: tuple[SegmentCarry, ...] | None = None  # 고른 다시가 검사에서 이미 읽은 앞 실행의 구획(None = 안 읽음)


def _bound(flow: Flow, document: Document | None) -> tuple[RunBinding | DocumentlessBinding, bool] | Refusal:
    """흐름 → 끼움과 「문서 없는 흐름인가」. 갈래는 어느 사전에 달렸는가로(머리말 ★ ND1)."""
    bare = BINDINGS.documentless(flow.id)
    if bare is not None:
        if document is not None:
            return DocumentNotAccepted()
        return bare, True
    found = BINDINGS.get(flow.id)
    if isinstance(found, NoBinding):
        return FlowNotRunnable(flow.id)
    if document is None:
        return DocumentRequired()
    return found, False


def _fresh_source(
    *,
    company_id: int,
    actor_user_id: int,
    module: str,
    flow_id: str | None,
    document: Document | None,
    options: Mapping[str, object],
    resume_from: int | None,
    idempotency: tuple[str, str] | None,
    launch_key: str | None,
) -> _Source | Refusal | RunReplayed | KeyReused:
    """새 실행·이어 돌기의 검사(머리말 차례 — RM1c 앞과 같은 문·같은 차례)."""
    flow = _flow(module, flow_id)
    if flow is None:
        return UnknownFlow()
    bound = _bound(flow, document)
    if not isinstance(bound, tuple):
        return bound
    binding, bare = bound
    if resume_from is None:
        return _Source(flow=flow, binding=binding, bare=bare, options=options)
    # 잠금이 경합을 줄 세운다: 같은 앞 실행을 둘이 이어 돌리면 뒤의 것은 앞의 것이 커밋한 뒤 ResumeAlready 다
    previous = selectors.lock_run(company_id=company_id, run_id=resume_from)
    if previous is None:
        return ResumeNotFound()
    previous_steps = selectors.step_rows(company_id=company_id, run_id=previous.pk)
    mismatch = _resume_mismatch(
        previous,
        previous_steps,
        document_id=None if document is None else document.id,
        flow=flow,
        options=options,
    )
    if mismatch is not None:
        return ResumeMismatch(mismatch)
    if previous.status != "failed":
        return ResumeNotFailed()
    if selectors.resumed_alive(company_id=company_id, run_id=previous.pk):
        # 같은 열쇠의 동시 이어 돌기: 앞 요청이 잠금을 쥐고 커밋한 뒤라 그 실행이 보인다(머리말 — 같은 판정)
        replayed = (
            None
            if idempotency is None
            else _replayed(company_id=company_id, actor_user_id=actor_user_id, idempotency=idempotency)
        )
        return ResumeAlready() if replayed is None else replayed
    if launch_key is not None and previous.launch_key == launch_key:
        return LaunchKeyReused()  # 다시 하기가 원 묶음에 섞이지 않게(머리말 — 쓰기 0)
    return _Source(
        flow=flow,
        binding=binding,
        bare=bare,
        options=dict(previous.options),
        carried=_carried(previous_steps),
        previous_files=selectors.run_files(company_id=company_id, run_id=previous.pk),
        previous_versions=dict(previous.versions),
        previous_error=previous.error_code,
    )


def _retry_mismatch(
    previous: RunRow, *, module: str, flow_id: str | None, document_id: int | None, options: Mapping[str, object]
) -> str | None:
    """고른 다시의 꼴: 앞 실행과 어긋난 칸의 글. 같으면 None. 빈 options·없는 flowId 는 앞 것이다."""
    if previous.module != module:
        return "앞 실행과 모듈이 다르다"
    if flow_id is not None and previous.flow_id != flow_id:
        return "앞 실행과 흐름이 다르다"
    if previous.document_id != document_id:
        return "앞 실행과 문서가 다르다"
    if options and dict(options) != previous.options:
        return "앞 실행과 옵션이 다르다(고른 구획 다시는 앞 실행의 옵션을 쓴다)"
    return None


def _retry_source(
    *,
    company_id: int,
    module: str,
    flow_id: str | None,
    document: Document | None,
    options: Mapping[str, object],
    resume_from: int | None,
    launch_key: str | None,
    retry: SegmentRetry,
) -> _Source | Refusal:
    """고른 구획 다시의 검사(머리말 차례): resume_from 과 같이 → 앞 잠금 → 꼴 → done → 흐름·끼움 → 고른 구획 →
    launchKey. 옵션·판은 부르는 쪽(새 실행과 같은 문)."""
    if resume_from is not None:
        return RetryMismatch("이어 돌기(resumeFromRunId)와 고른 구획 다시(retrySegments)는 같이 줄 수 없다")
    previous = selectors.lock_run(company_id=company_id, run_id=retry.from_run_id)
    if previous is None:
        return RetryNotFound()
    mismatch = _retry_mismatch(
        previous,
        module=module,
        flow_id=flow_id,
        document_id=None if document is None else document.id,
        options=options,
    )
    if mismatch is not None:
        return RetryMismatch(mismatch)
    if previous.status != "done":
        return RetryNotDone()
    flow = _flow(module, previous.flow_id)
    if flow is None:
        return UnknownFlow()
    previous_steps = selectors.step_rows(company_id=company_id, run_id=previous.pk)
    if tuple(s.name for s in previous_steps) != flow.steps:
        return RetryMismatch("앞 실행의 단계가 지금 흐름의 단계와 다르다")
    bound = _bound(flow, document)
    if not isinstance(bound, tuple):
        return bound
    binding, bare = bound
    if retry.step not in flow.fanouts:
        return RetrySegmentsUnknown(f"단계 {retry.step} 은 이 흐름의 펼침 단계가 아니다")
    keys = frozenset(retry.keys)
    if not retry.keys:
        return RetrySegmentsUnknown("다시 돌 구획을 하나 이상 골라야 한다")
    if len(keys) != len(retry.keys):
        return RetrySegmentsUnknown("고른 구획에 같은 열쇠가 둘 이상 있다")
    segments = selectors.segments_to_carry(company_id=company_id, run_id=previous.pk)
    if not keys <= {row.key_sha256 for row in segments if row.step == retry.step}:
        return RetrySegmentsUnknown("앞 실행의 그 단계에 없는 구획을 골랐다")
    if launch_key is not None and previous.launch_key == launch_key:
        return LaunchKeyReused()
    target = flow.steps.index(retry.step)
    carried = tuple(step for step in _carried(previous_steps) if step.position < target)
    if len(carried) != target:  # done 실행인데 고른 단계 앞에 data 없는 단계가 있다(방어 — 검증 1 권고 3)
        return RetryMismatch("앞 실행의 고른 단계 앞 단계가 끝난 꼴이 아니다")
    return _Source(
        flow=flow,
        binding=binding,
        bare=bare,
        options=dict(previous.options),
        carried=carried,
        previous_files=selectors.run_files(company_id=company_id, run_id=previous.pk),
        previous_versions=dict(previous.versions),
        retry_keys=keys,
        segments=segments,
    )


@overload
def create_run(
    *,
    company_id: int,
    actor_kind: Kind,
    actor_user_id: int,
    module: str,
    flow_id: str | None,
    document_id: int | None,
    options: Mapping[str, object],
    resume_from: int | None,
    now: datetime,
    idempotency: tuple[str, str] | None = None,
    launch_key: str | None = None,
    retry: None = None,
) -> CreateResult: ...


@overload
def create_run(
    *,
    company_id: int,
    actor_kind: Kind,
    actor_user_id: int,
    module: str,
    flow_id: str | None,
    document_id: int | None,
    options: Mapping[str, object],
    resume_from: int | None,
    now: datetime,
    idempotency: tuple[str, str] | None = None,
    launch_key: str | None = None,
    retry: SegmentRetry | None,
) -> CreateResult | RetryRefused: ...


@transaction.atomic
def create_run(
    *,
    company_id: int,
    actor_kind: Kind,
    actor_user_id: int,
    module: str,
    flow_id: str | None,
    document_id: int | None,
    options: Mapping[str, object],
    resume_from: int | None,
    now: datetime,
    idempotency: tuple[str, str] | None = None,
    launch_key: str | None = None,
    retry: SegmentRetry | None = None,
) -> CreateResult | RetryRefused:
    """실행 하나(`queued`)와 그 단계 행(흐름이 선언한 차례 전부 `pending`)을 만들고 커밋 뒤 큐에 넣는다.
    차례는 머리말 그대로다. 문서·실행의 회사는 인자(세션의 회사)다 — 남의 문서·실행 id 는 「없음」이다.
    `idempotency` 는 (Idempotency-Key, 본문 sha256 — runs/calc/idempotency.py). None 이면 열쇠 없는 요청(IK1 앞과
    같다). `launch_key` 는 같이 시작한 묶음의 열쇠(LK1). None 이면 묶음 없음(LK1 앞과 같다).
    `retry` 는 done 실행에서 고른 구획만 다시(RM1c). None 이면 RM1c 앞과 같은 문·같은 차례다."""
    if idempotency is not None:
        replayed = _replayed(company_id=company_id, actor_user_id=actor_user_id, idempotency=idempotency)
        if replayed is not None:
            return replayed
    document = None
    if document_id is not None:
        document = document_selectors.find_document(company_id=company_id, document_id=document_id)
        if document is None:
            return DocumentNotFound()
        if document.status != "uploaded":
            return DocumentNotUploaded()
    source = (
        _fresh_source(
            company_id=company_id,
            actor_user_id=actor_user_id,
            module=module,
            flow_id=flow_id,
            document=document,
            options=options,
            resume_from=resume_from,
            idempotency=idempotency,
            launch_key=launch_key,
        )
        if retry is None
        else _retry_source(
            company_id=company_id,
            module=module,
            flow_id=flow_id,
            document=document,
            options=options,
            resume_from=resume_from,
            launch_key=launch_key,
            retry=retry,
        )
    )
    if not isinstance(source, _Source):
        return source
    flow, binding, options = source.flow, source.binding, source.options
    limit = BINDINGS.options_limit(flow.id)
    try:
        too_large = _options_too_large(options, limit)
    except UnicodeEncodeError:
        return OptionsRejected(options_unencodable())
    if too_large:
        return OptionsRejected(options_too_large(limit))
    try:
        binding.check_options(options)
    except RunOptionsRejected as rejected:
        return OptionsRejected(rejected.message)
    # 판 묶음(처분 ⑬): 끼움의 몫 위에 흐름 id@판. 「flow」 열쇠는 늘 실행한 흐름이다(끼움이 덮지 못한다).
    # 이어 돌기는 앞 실행의 판 묶음 그대로다(X1b-2b ⑫v — 남은 단계가 앞과 같은 판으로 돈다).
    # 고른 다시(RM1c)는 지금 끼움이 앞 옵션으로 짓는 판이 앞 판과 같을 때만 앞 판으로(다르면 RetryVersionChanged)
    versions: dict[str, object]
    if source.previous_versions is not None and retry is None:
        versions = source.previous_versions
    else:
        try:
            versions = {
                **_versions(binding, bare=source.bare, options=options, company_id=company_id),
                "flow": flow.id,
            }
        except flow_ports.RunVersionsRejected as refused:
            return VersionsRejected(refused.message)
        # 645-1: 견줌·저장 전에 jsonb 가 돌려줄 꼴로(tuple → list 등 — 앞 판은 jsonb 왕복 값). 인코더는 그 칸의 것
        field = cast("models.JSONField[Any]", RunRow._meta.get_field("versions"))
        versions = json.loads(json.dumps(versions, cls=field.encoder))
        if source.previous_versions is not None:
            if versions != source.previous_versions:
                return RetryVersionChanged()
            versions = source.previous_versions

    previous_run = resume_from if retry is None else retry.from_run_id
    key, sha = (None, None) if idempotency is None else idempotency
    try:
        # 세이브포인트는 열쇠가 있을 때만: 겹친 요청의 23505 는 이것만 되돌린다(머리말). 열쇠 없으면 IK1 앞 그대로
        with transaction.atomic() if idempotency is not None else contextlib.nullcontext():
            row = RunRow.for_company(company_id).create(
                company_id=company_id,
                document_id=None if document is None else document.id,
                module=flow.module,
                flow_id=flow.id,
                options=dict(options),
                versions=versions,
                status="queued",
                attempts=0,
                created_by_user_id=actor_user_id,
                resumed_from_run_id=previous_run,
                idempotency_key=key,
                idempotency_sha256=sha,
                launch_key=launch_key,
            )
    except IntegrityError as err:
        if idempotency is None or _broken(err) != IDEMPOTENCY_UNIQUE:
            raise
        # 겹친 요청이 같은 열쇠로 먼저 커밋했다 — 그 실행으로 같은 판정(머리말)
        replayed = _replayed(company_id=company_id, actor_user_id=actor_user_id, idempotency=idempotency)
        if replayed is None:
            raise RuntimeError("Idempotency-Key 의 유일 제약을 어겼는데 그 열쇠의 실행이 없다") from err
        return replayed
    done = {s.name: s for s in source.carried}
    for position, name in enumerate(flow.steps):
        step = done.get(name)
        RunStepRow.for_company(company_id).create(
            company_id=company_id,
            run_id=row.pk,
            name=name,
            position=position,
            status="pending" if step is None else "done",
            done=None if step is None else step.done,
            total=None if step is None else step.total,
            data=None if step is None else step.data,
            started_at=None if step is None else step.started_at,
            finished_at=None if step is None else step.finished_at,
        )
    # 옮긴 단계의 파일 행: 이름·꼴·크기·sha256 그대로, 키는 새 실행 id 로(바이트는 실행기 _plan 이 옮긴다 — RC1)
    for file in source.previous_files:
        if file.step is None or file.step not in done:
            continue
        key = file_key(company_id=company_id, run_id=row.pk, step=file.step, name=file.name)
        RunFileRow.for_company(company_id).create(
            company_id=company_id,
            run_id=row.pk,
            step=file.step,
            name=file.name,
            media_type=file.media_type,
            storage_key=key,
            size_bytes=file.size_bytes,
            sha256=file.sha256,
        )
    # 옮긴 구획(RM1c — 머리말): 펼침이 있는 흐름의 이어 돌기·고른 다시만(장벽 흐름·새 실행은 쿼리 0)
    if previous_run is not None and flow.fanouts:
        start = next((name for name in flow.steps if name not in done), None)
        rows = carried_segments(
            selectors.segments_to_carry(company_id=company_id, run_id=previous_run)
            if source.segments is None
            else source.segments,
            carried_steps=frozenset(done),
            start_step=start,
            previous_error=source.previous_error,
            retry_keys=source.retry_keys,
        )
        if rows:
            # INSERT 한 번. 행의 회사는 이 실행의 회사(7a 허락 — test_static_rules 의 CONSTRUCTOR_ALLOWED, RM1c)
            RunSegmentRow.for_company(company_id).bulk_create(
                [
                    RunSegmentRow(
                        company_id=company_id,
                        run_id=row.pk,
                        step=segment.step,
                        position=segment.position,
                        kind=segment.kind,
                        key=dict(segment.key),
                        key_sha256=segment.key_sha256,
                        status=segment.status,
                        attempts=0,
                        data=None if segment.data is None else dict(segment.data),
                        data_octets=segment.data_octets,
                        error_code=segment.error_code,
                        started_at=segment.started_at,
                        finished_at=segment.finished_at,
                    )
                    for segment in rows
                ]
            )
    created = selectors.find_run(company_id=company_id, run_id=row.pk)
    if created is None:
        raise RuntimeError("방금 만든 run_runs 의 행이 없다")
    # robust=True: 갈고리가 던져도 커밋은 이미 끝났고 요청은 201 이다(core/resources/queue.py 의 머리말)
    transaction.on_commit(
        _sending(hooks.enqueue_run, company_id=company_id, run_id=row.pk),
        robust=True,
    )
    record_event(
        at=now,
        company_id=company_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action="run",
        event="run_created",
        result="success",
        target_kind="run",
        target_id=row.pk,
        target_label=None if document is None else document.file_name,  # 「그때의 이름」 — 문서 없는 실행은 없음
    )
    return RunCreated(created)
