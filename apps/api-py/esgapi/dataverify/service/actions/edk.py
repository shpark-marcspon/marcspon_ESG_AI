"""EDK 인벤토리 엑셀 두 경로의 몸(POST /dataverify/edk/read · GET /dataverify/edk/template — 밴드 DVX1 ①).

상태가 없다: DB·저장소·디스크에 쓰지 않고 감사 줄도 남기지 않는다. 테넌트 행을 읽지 않으므로 회사 id 를 받지 않는다
(영문번역 용어집·중대성평가 가치사슬 읽기와 같은 꼴 — 운영 관리자도 같은 결과). 읽기·양식 짓기는 도구
(tools/edk_xlsx.py)가 하고, 여기서는 도구의 갈래를 응답 꼴(contracts/edk_read_shapes.py)로 옮길 뿐이다. 원본 파일은
저장하지 않는다 — 실행은 화면이 받은 data 로 POST /runs 를 만든다. 칸의 값은 로그에 싣지 않는다.
"""

from typing import Any, Final

from esgapi.core.conf import now
from esgapi.dataverify.contracts.edk_read_shapes import DataverifyEdkReadOk, DataverifyEdkReadRejected
from esgapi.dataverify.tools import edk_xlsx

FILE_NAME: Final = "EDK-인벤토리-양식.xlsx"
MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def read(data: bytes) -> DataverifyEdkReadOk | DataverifyEdkReadRejected:
    """xlsx 바이트 → data(ok true) 또는 거절 갈래(ok false). 어떤 바이트도 예외 대신 갈래다."""
    match edk_xlsx.read_edk(data):
        case edk_xlsx.EdkRead() as read:
            items: Any = read.data  # 도구의 dict 는 EdkItem 꼴 그대로(계약 시험이 TypeAdapter 로 잰다)
            return {
                "ok": True,
                "data": items,
                "itemCount": read.item_count,
                "skipped": {"themes": read.skipped_themes, "items": read.skipped_items},
                "years": list(read.years),
                "skippedEmptyRows": read.skipped_empty_rows,
                "ignoredColumns": read.ignored_columns,
            }
        case edk_xlsx.EdkRejected(kind=kind, row=row, column=column, message=message):
            return {"ok": False, "kind": kind, "row": row, "column": column, "message": message}


def template(year: int | None) -> bytes:
    """양식 xlsx(연도 열 year−2·year−1·year, 가상 예시 한 줄 — 같은 year 면 매번 같은 바이트). year 가 없으면 서버
    오늘(UTC)의 해 − 1(보고연도는 지난해가 보통이다)."""
    return edk_xlsx.template(now().year - 1 if year is None else year)
