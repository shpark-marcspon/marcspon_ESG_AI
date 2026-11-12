"""고친 판 최종 엑셀 내려받기(GET /materiality/runs/{run_id}/report — 밴드 IRS3 ③, 결정 MARC-ENT-561, 처분 Q1·Q8 가).
runs(실행·결과)·core(감사)를 엮어 조립하므로 Action 이다(greenwash service/actions/report.py 꼴).

    report(company_id, actor_kind, actor_user_id, run_id, now)   엑셀 바이트 | NotFound | RunNotDone

규칙:
  1. 결과 = actions/result.run_result(지금 고침을 덮은 고친 판 — 갈래 NotFound·RunNotDone 그대로)
  2. 열쇠 차례 되살림: run_results.body 는 jsonb 라 열쇠 차례가 DB 왕복에서 바뀐다(part1 이 앞으로). result@2 를
     strict 로 **검사한 값**(꼴 차례로 다시 지은 dict)을 덤프한다 — 흐름의 dump_v2 는 받은 dict 를 덤프해 jsonb 차례가
     그대로 나간다(검증 ③ B2). parsed(모델 원문 dict — JsonValue)의 안쪽 차례는 jsonb 차례 그대로다
  3. 바이트 = outputs/final_xlsx.build_final(고친 판) — 시트 넷, RAW_JSON 도 고친 판(Q8 가). 저장된 출력 파일
     (run_files)은 읽지 않는다. 자른 칸 목록(cuts)은 버린다(경고는 실행 끝의 결과에 이미 있다 — 내려받기는 결과를 고치지
     않는다)
  4. 감사 download 한 줄: 바이트를 지은 뒤·응답 앞(greenwash report 규칙 7). target_kind = report(다시 지은 보고서 —
     저장 파일 내려받기의 run 과 갈린다), target_label = 파일 이름. 거절·예외는 줄 0
"""

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Final, cast

from esgapi.core.auth.principal import Kind
from esgapi.core.service.services.audit import record_event
from esgapi.materiality.contracts import shapes
from esgapi.materiality.outputs import final_xlsx
from esgapi.materiality.service.actions.result import NotFound, RunNotDone, run_result

FILE_NAME: Final = final_xlsx.FILENAME  # "materiality-final-report.xlsx"


def in_shape_order(result: dict[str, Any]) -> dict[str, Any]:
    """규칙 2. strict 검사한 값(꼴 차례)의 JSON 판. 꼴이 아니면 pydantic ValidationError(결함 — 500)."""
    adapter = shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2]
    return cast("dict[str, Any]", json.loads(adapter.dump_json(adapter.validate_python(result, strict=True))))


@dataclass(frozen=True, slots=True)
class Report:
    content: bytes


type Refusal = NotFound | RunNotDone


def report(*, company_id: int, actor_kind: Kind, actor_user_id: int, run_id: int, now: datetime) -> Report | Refusal:
    """고친 판 최종 엑셀. 차례는 머리말 그대로다. 거절은 감사 앞이라 줄 0 이다."""
    result = run_result(company_id=company_id, run_id=run_id)
    if isinstance(result, NotFound | RunNotDone):
        return result
    content, _cuts = final_xlsx.build_final(in_shape_order(result))
    record_event(
        at=now,
        company_id=company_id,
        actor_kind=actor_kind,
        actor_user_id=actor_user_id,
        action="download",
        event="materiality_report_downloaded",
        result="success",
        target_kind="report",
        target_id=run_id,
        target_label=FILE_NAME,
    )
    return Report(content=content)
