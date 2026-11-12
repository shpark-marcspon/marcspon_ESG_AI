"""운영 관리자 실행 기록 엑셀(AD-04 「엑셀 내보내기」 — AD4S ②). 순수하다(`.importlinter` 계약 다의 service/utils —
django·ninja 를 import 하지 않는다. esgapi.core.schemas 도 안 부른다: 시각은 경로가 글자로 지어 넘긴다).

시트 하나 「실행 기록」 — 머리 한 줄 + 실행 한 줄씩(경로가 넘긴 차례 그대로: 새 것 먼저).
열(감독 판단 Q6, 글은 웹 entities/run-log/config/text.ts 와 같은 글 — 디자인 확정 전):
  시각 · 모듈(한국어, 모르는 id 는 그대로) · 문서 · 흐름(flowId) · AI 설정 버전(판 이름, 기본 판은 「기본 설정」) ·
  담당자(이름, 없으면 아이디, 둘 다 없으면 「알 수 없는 사람」) · 처리 시간(초) · 토큰 · 비용(추정, USD) · 상태 ·
  검토 · 시험용
값 없음: 수 칸 셋은 글자 「–」(U+2013 — 웹 runFigures 와 같다: queued 줄은 셋 다, 그 밖 줄은 처리 시간이 null 일
때). 글 칸(AI 설정 버전·검토·시험용)은 빈칸. 셀에 datetime 0(시각은 KST ISO 글자).
글자 칸은 두 가지만 다듬는다(greenwash/outputs/xlsx.py 와 같은 꼴): xlsx 가 담지 못하는 제어 문자
(ILLEGAL_CHARACTERS_RE)를 지우고, `=` 로 시작해 수식이 된 칸(data_type "f")을 글자 칸("s")으로 되돌린다(문서
이름은 사람이 올린 글이다). `'` 접두는 붙이지 않는다(값이 바뀐다 — 발주서 m4).
openpyxl 의 xlsx 는 만든 시각이 들어가 바이트가 실행마다 다르다 — 시험은 읽어 들인 칸 값을 견준다.
"""

import io
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Final

from openpyxl import Workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE

from esgapi.core.calc.run_metrics import KST

MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
SHEET: Final = "실행 기록"
HEADER: Final = (
    "시각",
    "모듈",
    "문서",
    "흐름",
    "AI 설정 버전",
    "담당자",
    "처리 시간(초)",
    "토큰",
    "비용(추정, USD)",
    "상태",
    "검토",
    "시험용",
)
MODULES: Final = {
    "greenwash": "그린워싱",
    "inventory.scope3": "온실가스 Scope 3",
    "dataverify": "데이터 검증",
    "translation": "영문번역",
    "materiality": "중대성평가 IRO",
}
STATUSES: Final = {"queued": "대기", "processing": "처리 중", "done": "완료", "failed": "실패"}
REVIEWS: Final = {"pending": "미검토", "in_review": "검토 중", "confirmed": "확정"}
UNKNOWN_UPLOADER: Final = "알 수 없는 사람"
EMPTY: Final = "–"  # en dash U+2013
TEST: Final = "예"
DEFAULT_SETTING: Final = "기본 설정"  # 기본 판(id 없음) — 웹 run.ts aiSettingText 와 같은 글


@dataclass(frozen=True, slots=True)
class RunLogLine:
    """엑셀 한 줄의 재료 — 경로가 GET /run-logs 의 줄(run_out)과 같은 값으로 짓는다. 칸은 글자·수·None 뿐."""

    created_at: str  # KST ISO 글자(경로의 to_seoul_iso)
    module: str
    document_name: str | None  # 문서 없는 흐름의 실행이면 None → 빈칸(ND1)
    flow_id: str
    ai_setting: str | None  # 판 이름, 기본 판은 「기본 설정」
    created_by_name: str | None
    created_by_username: str | None
    duration_sec: int | None
    tokens: int
    cost_usd: float
    status: str
    review: str | None
    is_test: bool


def file_name(at: datetime) -> str:
    """「실행기록_YYYY-MM-DD_HHMM.xlsx」(KST). 시각이 naive 면 ValueError(어느 시간대인지 모른다)."""
    if at.tzinfo is None or at.utcoffset() is None:
        raise ValueError("시각에 시간대가 없다")
    return f"실행기록_{at.astimezone(KST):%Y-%m-%d_%H%M}.xlsx"


def _row(line: RunLogLine) -> list[object]:
    queued = line.status == "queued"
    return [
        line.created_at,
        MODULES.get(line.module, line.module),
        line.document_name,
        line.flow_id,
        line.ai_setting,
        line.created_by_name or line.created_by_username or UNKNOWN_UPLOADER,
        EMPTY if queued or line.duration_sec is None else line.duration_sec,
        EMPTY if queued else line.tokens,
        EMPTY if queued else line.cost_usd,
        STATUSES.get(line.status, line.status),
        None if line.review is None else REVIEWS.get(line.review, line.review),
        TEST if line.is_test else None,
    ]


def workbook(lines: Sequence[RunLogLine]) -> bytes:
    """줄 → xlsx 바이트(시트 하나, 머리 한 줄 + 줄)."""
    book = Workbook()
    sheet = book.active
    assert sheet is not None  # noqa: S101 — 새 Workbook 은 시트 하나를 갖고 시작한다
    sheet.title = SHEET
    sheet.append(list(HEADER))
    for line in lines:
        sheet.append([ILLEGAL_CHARACTERS_RE.sub("", v) if isinstance(v, str) else v for v in _row(line)])
        for cell in sheet[sheet.max_row]:
            if cell.data_type == "f":  # `=` 로 시작하는 글 — 수식이 아니라 글자로
                cell.data_type = "s"
    out = io.BytesIO()
    book.save(out)
    return out.getvalue()
