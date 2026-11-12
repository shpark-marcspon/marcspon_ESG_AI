"""용어집 엑셀 두 경로의 몸(POST /translation/glossary/read · GET /translation/glossary/template — 밴드 TR3a ②).

상태가 없다: DB·저장소·디스크에 쓰지 않고 감사 줄도 남기지 않는다. 테넌트 행을 읽지 않으므로 회사 id 를 받지 않는다
(그린워싱 기본 단어 목록과 같은 꼴 — 운영 관리자도 같은 결과). 읽기·양식 짓기는 도구(tools/glossary_xlsx.py)가 하고,
여기서는 도구의 갈래를 응답 꼴(contracts/glossary_shapes.py)로 옮길 뿐이다. 칸의 값은 로그에 싣지 않는다.
"""

from typing import Final

from esgapi.translation.contracts.glossary_shapes import (
    TranslationGlossaryReadOk,
    TranslationGlossaryReadRejected,
)
from esgapi.translation.tools import glossary_xlsx

FILE_NAME: Final = "translation-glossary-template.xlsx"
MEDIA_TYPE: Final = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def read(data: bytes) -> TranslationGlossaryReadOk | TranslationGlossaryReadRejected:
    """xlsx 바이트 → 짝 목록(ok true) 또는 거절 갈래(ok false). 어떤 바이트도 예외 대신 갈래다."""
    match glossary_xlsx.read_glossary(data):
        case glossary_xlsx.GlossaryRead(pairs=pairs):
            return {"ok": True, "pairs": [{"ko": ko, "en": en} for ko, en in pairs], "rowCount": len(pairs)}
        case glossary_xlsx.GlossaryRejected(kind=kind, row=row, message=message):
            return {"ok": False, "kind": kind, "row": row, "message": message}


def template() -> bytes:
    """빈 양식 xlsx(매번 같은 바이트)."""
    return glossary_xlsx.template()
