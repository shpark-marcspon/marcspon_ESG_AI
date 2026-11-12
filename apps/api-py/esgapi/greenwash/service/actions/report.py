"""엑셀 보고서 내려받기(GET /greenwash/runs/{run_id}/report — 밴드 G1b-2a, MARC-ENT-356). runs(실행·결과)·core(감사)를
엮어 조립하므로 Action 이다(Service·Selector 는 남의 도메인을 import 하지 않는다 — `.importlinter` 계약 바).

    report(company_id, actor_*, run_id, confirmed, now)   규칙 1~8 → 엑셀 바이트와 감사 대상 이름, 또는 거절 갈래

규칙(발주서 G1b-2a §2-2):
  1. 실행이 없거나 남의 회사, module != greenwash, flow_id != E0_FLOW, 결과 본문 없음 → NotFound(404)
  2. status != done → RunNotDone(409 RUN_NOT_DONE)
  3. 결과 본문이 dry-run(dryRun 칸이 값) → NoReport(409 NO_REPORT) — 엑셀이 없다
  4. confirmed 인데 검토가 confirmed 가 아님 → NotConfirmed(409 NOT_CONFIRMED). 확정이면 adopted = 채택한 itemIndex,
     edits = 고친 문장 itemIndex → (등급, 사유, 수정 방향)(mark_rows — 고침 0 이면 빈 dict, G1b-3), bases·notes = 기준
     판단(재판단)과 「근거 고침」·「재판단」 칸 글(review.judgments — 검토 GET 과 한 벌, GRJ1). 미확정은 넷 다 None
     (첫 AI 판단 그대로 — 재판단 반영은 검토 반영 엑셀에만)
  5. 결과 사본의 counts.byPart 를 parts[].name 차례로 다시 놓는다(값 그대로) — run_results.body 는 jsonb 라 열쇠 차례가
     DB 왕복에서 바뀐다(발주서 B3). 엑셀 「요약」의 파트 차례 = 결과 parts 차례
  6. 바이트 = outputs/xlsx.build(결과, added_terms=frequency_extras(extraTerms), adopted=…, edits=…) — 저장된 출력
     파일은 읽지 않고 결과에서 늘 다시 짓는다(확정본이 같은 길)
     extraTerms 칸이 없는 옛 꼴(G1c 앞) 결과는 추가 단어 없음으로 — 사본의 extraTerms = [](G1b-2b, MARC-ISSUE-255)
  7. 감사 download 한 줄: 바이트를 지은 뒤·응답 앞(MARC-ENT-295). 거절·build 예외는 줄 0. record_event 는 던지지 않는다
  8. 응답(경로): xlsx 바이트, Content-Disposition attachment; filename="greenwash-report.xlsx"
★ 표면은 엔진을 직접 들이지 않는다 — frequency_extras·FLOW_ID 는 흐름 flows.colab_e0 의 이름으로 받는다.
★ 부재는 갈래로: NotFound·RunNotDone 은 actions/review.py 의 것을 다시 쓰고, NoReport·NotConfirmed 는 여기 것이다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from esgapi.core.auth.principal import Kind
from esgapi.core.schemas import to_seoul_iso
from esgapi.core.service.services.audit import record_event
from esgapi.greenwash.contracts.shapes import SHAPE as RESULT_SHAPE
from esgapi.greenwash.flows import colab_e0
from esgapi.greenwash.flows.colab_e0 import frequency_extras
from esgapi.greenwash.outputs import xlsx
from esgapi.greenwash.service.actions import review
from esgapi.greenwash.service.actions.review import NotFound, RunNotDone
from esgapi.greenwash.service.selectors import review as selectors
from esgapi.runs.service.selectors import runs as run_selectors
from esgapi.user.service.selectors.user import people_of

MODULE: Final = "greenwash"
E0_FLOW: Final = colab_e0.FLOW_ID  # 보고서를 내는 흐름(다음 밴드도 이 상수로 거른다 — 발주서 R8·critic R4)
FILE_NAME: Final = colab_e0.REPORT_FILE  # "greenwash-report.xlsx"
CONFIRMED_LABEL: Final = f"{FILE_NAME} · 확정본"


@dataclass(frozen=True, slots=True)
class NoReport:
    """dry-run 실행이라 엑셀이 없다."""


@dataclass(frozen=True, slots=True)
class NotConfirmed:
    """확정본을 청했는데 검토가 확정 전이다."""


@dataclass(frozen=True, slots=True)
class Report:
    content: bytes
    label: str  # 감사 target_label


type Refusal = NotFound | RunNotDone | NoReport | NotConfirmed


def _result(company_id: int, run_id: int) -> dict[str, Any] | NotFound | RunNotDone:
    """규칙 1·2. 끝난 E0 그린워싱 실행의 결과 본문."""
    run = run_selectors.find_run(company_id=company_id, run_id=run_id)
    if run is None or run.module != MODULE or run.flow_id != E0_FLOW:
        return NotFound()
    if run.status != "done":
        return RunNotDone(run.status)
    results = run_selectors.run_results(company_id=company_id, run_id=run_id)
    body = next((r.body for r in results if r.schema_version == RESULT_SHAPE), None)
    if not isinstance(body, dict):  # 끝난 그린워싱 실행에는 늘 있다 — 없으면 없는 실행으로(review._done_run 과 같음)
        return NotFound()
    return cast("dict[str, Any]", body)


def _adopted(company_id: int, run_id: int) -> set[int] | NotConfirmed:
    """규칙 4. 확정된 검토의 채택한 itemIndex."""
    review = selectors.find_review(company_id=company_id, run_id=run_id)
    if review is None or review.state != "confirmed":
        return NotConfirmed()
    marks = selectors.decided_marks(company_id=company_id, run_id=run_id)
    return {m.item_index for m in marks if m.decision == "adopted"}


def _edits(rows: Mapping[int, selectors.MarkRow]) -> dict[int, xlsx.Edit]:
    """규칙 4. 확정된 검토의 고침(고친 칸이 하나 이상인 표시 행만)."""
    edits = {
        index: (row.edited_level, row.edited_reason_bullets, row.edited_fix_paragraph) for index, row in rows.items()
    }
    return {index: edit for index, edit in edits.items() if any(v is not None for v in edit)}


def _minute(at: datetime) -> str:
    """「YYYY-MM-DD HH:MM」(서울 시각)."""
    return to_seoul_iso(at)[:16].replace("T", " ")


def _rejudged(
    company_id: int, run_id: int, items: Sequence[Mapping[str, Any]], rows: Mapping[int, selectors.MarkRow]
) -> tuple[dict[int, dict[str, Any]], dict[int, xlsx.Note]]:
    """규칙 4(GRJ1). 기준 판단(review.judgments — 검토 GET 과 한 벌)이 재판단인 문장의 판정 칸, 그리고 문장마다
    「근거 고침」(지움 n · 더함 n — 지금 유효한 고침, 없으면 빈 칸)·「재판단」(n회 · 때 · 이름 — 기준이 된 재판단이
    있을 때만) 칸 글."""
    bases, lines = review.judgments(company_id, run_id, items, rows)
    wanted = {basis.judged_by for basis in bases if basis.run_id is not None and basis.judged_by is not None}
    found = people_of(company_id, wanted) if wanted else {}
    judged = {i: dict(basis.item) for i, basis in enumerate(bases) if basis.run_id is not None}
    notes: dict[int, xlsx.Note] = {}
    for index in range(len(items)):
        removed, added = review.evidence_now(rows.get(index), bases[index])
        evidence = f"지움 {len(removed)} · 더함 {len(added)}" if removed or added else ""
        basis = bases[index]
        line = lines.get(index)
        rejudge = ""
        if basis.run_id is not None and basis.judged_at is not None and line is not None:
            person = found.get(basis.judged_by) if basis.judged_by is not None else None
            name = person[1] if person is not None and person[1].strip() else review.UNKNOWN_USER
            rejudge = f"{line.count}회 · {_minute(basis.judged_at)} · {name}"
        if evidence or rejudge:
            notes[index] = (evidence, rejudge)
    return judged, notes


def in_part_order(result: dict[str, Any]) -> dict[str, Any]:
    """규칙 5. counts.byPart 를 parts[].name 차례로 다시 놓은 사본(값 그대로, parts 에 없는 열쇠는 뒤에 그 차례로)."""
    counts = result.get("counts")
    if not isinstance(counts, dict):
        return result
    by_part = cast("dict[str, Any]", counts).get("byPart")
    if not isinstance(by_part, dict):
        return result
    by_part = cast("dict[str, Any]", by_part)
    names = [cast("dict[str, Any]", p)["name"] for p in cast("list[Any]", result["parts"])]
    first = {name: by_part[name] for name in names if name in by_part}
    ordered = first | {name: value for name, value in by_part.items() if name not in first}
    return {**result, "counts": {**cast("dict[str, Any]", counts), "byPart": ordered}}


def report(
    *, company_id: int, actor_kind: Kind, actor_user_id: int, run_id: int, confirmed: bool, now: datetime
) -> Report | Refusal:
    """엑셀 보고서. 차례는 머리말 그대로다. 거절은 감사 앞이라 줄 0 이다."""
    result = _result(company_id, run_id)
    if not isinstance(result, dict):
        return result
    if result.get("dryRun") is not None:
        return NoReport()
    adopted: set[int] | None = None
    edits: dict[int, xlsx.Edit] | None = None
    bases: dict[int, dict[str, Any]] | None = None
    notes: dict[int, xlsx.Note] | None = None
    if confirmed:
        found = _adopted(company_id, run_id)
        if isinstance(found, NotConfirmed):
            return found
        adopted = found
        rows = selectors.mark_rows(company_id=company_id, run_id=run_id)
        edits = _edits(rows)
        bases, notes = _rejudged(company_id, run_id, cast("list[dict[str, Any]]", result["items"]), rows)
    filled: dict[str, Any] = {**result, "extraTerms": result.get("extraTerms") or []}  # 규칙 6 — xlsx 도 읽어 사본으로
    content = xlsx.build(
        in_part_order(filled),
        added_terms=frequency_extras(filled["extraTerms"]),
        adopted=adopted,
        edits=edits,
        bases=bases,
        notes=notes,
    )
    label = CONFIRMED_LABEL if confirmed else FILE_NAME
    # 감사 줄: 바이트를 지은 뒤·응답 앞(머리말 7)
    record_event(
        at=now,
        company_id=company_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action="download",
        event="greenwash_report_downloaded",
        result="success",
        target_kind="report",
        target_id=run_id,
        target_label=label,
    )
    return Report(content=content, label=label)
