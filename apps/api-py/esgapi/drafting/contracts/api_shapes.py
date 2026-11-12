"""경로의 몸 꼴 중 요청과 목차 넣기의 답(밴드 RP1 ③). 요청은 pydantic 모델(모르는 칸 거절·타입을 바꿔 받지 않음 —
core.schemas.StrictIn 과 같은 설정. 계약 층은 ninja·django 를 모르므로 그 클래스를 잇지 않고 설정만 같게 둔다), 답은
TypedDict 다.

칸 이름은 camelCase. 시각 칸이 있는 응답(프로젝트·문서·목록)은 service/schemas/projects.py 의 ninja Schema + KstDateTime
이다(RP2d 가 옮김 — 이 층은 core 를 모른다). 오류는 core 의 꼴 그대로(`{error: {code, message, fields}}`) — 원고작성이
더하는 code 는 DOCUMENT_NO_TEXT_LAYER 하나다(contracts/wire.py).

openapi 는 이름이 같은 컴포넌트를 하나로 합치므로 이름마다 Drafting 머리를 단다.
"""

from typing import Annotated, TypedDict

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, with_config

from esgapi.drafting.contracts.shapes import FORBID, DraftingOutlineNode

STRICT_IN = ConfigDict(extra="forbid", strict=True, use_attribute_docstrings=True)

# ── 요청 ──


class DraftingProjectCreateIn(BaseModel):
    """`POST /drafting/projects` 의 본문."""

    model_config = STRICT_IN

    year: Annotated[int, Field(ge=2000, le=2100)]
    """보고서 연도(2000~2100)."""
    name: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=80)]
    """프로젝트 이름(앞뒤 공백을 뺀 1~80자)."""


class DraftingDocumentPutIn(BaseModel):
    """`PUT /drafting/projects/{project_id}/document` 의 본문."""

    model_config = STRICT_IN

    documentId: Annotated[int, Field(ge=1)]
    """같은 회사의 올림이 끝난 문서 id(POST /documents → confirm). 글자 층이 없으면(hasText false) 422."""


class DraftingOutlinePutIn(BaseModel):
    """`PUT /drafting/projects/{project_id}/outline` 의 본문 — drafting.outline@1 통째. 트리 규칙은
    contracts/wire.accept_outline 이 본다(어기면 422 VALIDATION_ERROR, fields.nodes 에 한 문장)."""

    model_config = STRICT_IN

    nodes: list[DraftingOutlineNode]
    """마디 1~300(잎 1~150), 앞차례(부모가 먼저)."""


# ── 응답 ──


@with_config(FORBID)
class DraftingOutlinePut(TypedDict):
    """`PUT …/outline` 의 답. 같은 sha 를 다시 넣으면 지금 판 그대로(멱등)."""

    outlineId: int
    revision: int
    sha256: str
