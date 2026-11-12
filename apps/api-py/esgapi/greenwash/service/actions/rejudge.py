"""재판단 만들기(밴드 GRJ1 — 결정 MARC-ENT-617, 화면 GW-05 r4). 검토 화면의 [재판단]이 부른다.

    create_rejudge(company_id, actor_*, run_id, item_index, now)
        POST /greenwash/runs/{runId}/items/{itemIndex}/rejudge → 재판단 실행 하나(queued, greenwash.rejudge@E0)

★ runs 의 create_run 을 부르는 그린워싱 자리는 이 파일 하나다(71 허락 조건 (1) — runs 땅 0줄).
★ 옵션은 서버가 굳힌다(웹이 POST /runs 로 바로 만들지 못한다 — flows/rejudge_e0.py 의 문, 감독 R2):
  {fromRunId, itemIndex, sentence, lowOnly, kept(남긴 AI 칩), added(더한 조각), maxCharsPerChunk,
  maxCharsEvidenceTotal, promptVersion(원 실행 config 로 셈한 판 글자 — GRS1)}.
  판은 원 실행의 versions 그대로(Q2). 만든 실행 id 는 그 문장 행의 rejudge_run_ids 끝에 붙인다.

규칙(차례대로 — 앞이 이긴다. 쓰기 전 거절은 행 0):
  1·2·3  review.py 와 같다 — 실행 없음·남의 회사·그린워싱 아님·결과 없음 404 · done 아님 409 RUN_NOT_DONE · dry-run 409
         NO_REVIEW. 원 실행 흐름이 greenwash.colab@E0 이 아니면 404(재판단 실행의 재판단은 없다)
  4      itemIndex 가 결과 items 밖 → 404(그런 문장이 없다)
  5      검토 행을 FOR UPDATE 로 잡는다(검토 PUT·다른 재판단과 줄 선다). 확정됨 → 409 REVIEW_LOCKED
  6      그 문장의 가장 늦은 재판단이 대기·진행 중 → 409 REJUDGE_RUNNING(두 번 누름이 돈 드는 실행 둘이 되지 않게 —
         71 조건 (4), 감독 권장 「진행 중이면 409」)
  7      지금 근거가 기준 판단에 보낸 것과 같음(지운 칩 0·더한 조각 같음) → 409 NOTHING_TO_REJUDGE(감독 R4)
  8      create_run 의 거절은 POST /runs 와 같은 kind·code 로(경로가 바꾼다 — 71 조건 (3))
감사: 실행 만들기의 run_created 한 줄(create_run 이 쓴다) + 이 문장의 action=run · event=greenwash_item_rejudged 한 줄
(감독 R1 — 새 action 0, core 0줄). 업무 블록의 마지막 문장이다.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final

from django.db import transaction
from pydantic.alias_generators import to_snake

from esgapi.core.auth.principal import Kind
from esgapi.core.service.selectors import documents as document_selectors
from esgapi.core.service.services.audit import record_event
from esgapi.greenwash.flows import colab_e0, rejudge_e0
from esgapi.greenwash.service.actions import review
from esgapi.greenwash.service.selectors import review as selectors
from esgapi.greenwash.service.services import review as services
from esgapi.runs.service.actions import runs as run_actions


@dataclass(frozen=True, slots=True)
class ItemNotFound:
    """그 실행의 결과에 그런 문장이 없다."""


@dataclass(frozen=True, slots=True)
class NothingToRejudge:
    """근거가 기준 판단에 보낸 것과 같다."""


@dataclass(frozen=True, slots=True)
class CreateRefused:
    """runs 의 create_run 이 거절했다(경로가 POST /runs 와 같은 kind·code 로 바꾼다)."""

    refusal: run_actions.CreateResult


@dataclass(frozen=True, slots=True)
class RejudgeCreated:
    rejudge_run_id: int


type Refusal = (
    review.NotFound
    | review.RunNotDone
    | review.NoReview
    | review.ReviewLocked
    | ItemNotFound
    | review.RejudgeRunning
    | NothingToRejudge
    | CreateRefused
)

EVENT: Final = "greenwash_item_rejudged"


def _checker(result: dict[str, object]) -> dict[str, Any]:
    config = result.get("config")
    checker = config.get("checker") if isinstance(config, dict) else None  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    if not isinstance(checker, dict):
        raise RuntimeError("끝난 그린워싱 결과에 config.checker 가 없다")
    return checker  # pyright: ignore[reportUnknownVariableType]


def prompt_version(checker: Mapping[str, Any]) -> str:
    """원 실행이 판정에 쓴 프롬프트 판 글자 — 결과 config.checker(GWConfig 를 camel 로 실은 것)를 snake 로 되돌려
    judge 와 같은 길(colab_e0.judged_prompt_version)로 셈한다(GRS1 — MARC-ISSUE-632: 지금 코드의 SCAN_CONFIG 가
    아니라 원 실행의 config)."""
    return colab_e0.judged_prompt_version({to_snake(key): value for key, value in checker.items()})


@transaction.atomic
def create_rejudge(
    *, company_id: int, actor_kind: Kind, actor_user_id: int, run_id: int, item_index: int, now: datetime
) -> RejudgeCreated | Refusal:
    found = review.reviewable(company_id, run_id)
    if not isinstance(found, review.Done):
        return found
    if found.run.flow_id != colab_e0.FLOW_ID:
        return review.NotFound()
    items = review.item_list(found.result)
    if not 0 <= item_index < len(items):
        return ItemNotFound()
    locked = selectors.lock_review(company_id=company_id, run_id=run_id)
    if locked is not None and locked.state == "confirmed":
        return review.ReviewLocked()
    rows = selectors.mark_rows(company_id=company_id, run_id=run_id)
    bases, lines = review.judgments(company_id, run_id, items, rows)
    line = lines.get(item_index)
    if line is not None and line.status == "running":
        return review.RejudgeRunning()
    basis = bases[item_index]
    removed, added = review.evidence_now(rows.get(item_index), basis)
    if review.nothing_to_rejudge(removed, added, basis):
        return NothingToRejudge()
    item = items[item_index]
    chips = list(basis.item.get("confirmedInEvidence") or [])
    checker = _checker(found.result)
    options: dict[str, object] = {
        "fromRunId": run_id,
        "itemIndex": item_index,
        "sentence": item["sentence"],
        "lowOnly": item["level"] == "Low",  # 원 항목의 갈래(선언적 문장 — 엔진 is_low_declarative 가 정한 것)
        "kept": [chip for position, chip in enumerate(chips) if position not in set(removed)],
        "added": [dict(piece) for piece in added],
        "maxCharsPerChunk": checker["maxCharsPerChunk"],
        "maxCharsEvidenceTotal": checker["maxCharsEvidenceTotal"],
        "promptVersion": prompt_version(checker),
    }
    with rejudge_e0.creating(options, found.run.versions):
        created = run_actions.create_run(
            company_id=company_id,
            actor_kind=actor_kind,
            actor_user_id=actor_user_id,
            module=colab_e0.FLOW.module,
            flow_id=rejudge_e0.FLOW_ID,
            document_id=None,
            options=options,
            resume_from=None,
            now=now,
        )
    if not isinstance(created, run_actions.RunCreated):
        return CreateRefused(created)
    services.append_rejudge(company_id=company_id, run_id=run_id, item_index=item_index, rejudge_run_id=created.run.id)
    document = (
        None
        if found.run.document_id is None
        else document_selectors.find_document(company_id=company_id, document_id=found.run.document_id)
    )
    file_name = document.file_name if document is not None else f"문서 {found.run.document_id}"
    record_event(  # 업무 블록의 마지막 문장(review.py 머리말과 같은 꼴)
        at=now,
        company_id=company_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action="run",
        event=EVENT,
        result="success",
        target_kind="greenwash_item",
        target_id=run_id,
        target_label=review.label(file_name, item_index),
    )
    return RejudgeCreated(rejudge_run_id=created.run.id)
