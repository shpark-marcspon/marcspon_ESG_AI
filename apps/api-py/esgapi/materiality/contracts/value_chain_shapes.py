"""가치사슬 표 엑셀 읽기의 응답 꼴(POST /materiality/value-chain/read — 밴드 IRW2, MARC-ENT-464·421).

읽은 행도, 읽지 못한 까닭도 200 이다 — 판별 칸 `ok`. 웹은 `ok: true` 의 `rows` 를 화면 표에 넣고(밸류체인 값 검사·
바꿈은 웹 model/valueChain.ts), 사용자가 고친 표를 실행 입력 `input.valueChain`(materiality.input@1 — 이 꼴은 바꾸지
않는다)에 싣는다. 읽기 경로는 상태가 없다. `ok: false` 의 `kind` 는 tools/value_chain_xlsx.py 의 RejectionKind 와 같은
아홉이다(tests/contracts/test_value_chain_shapes.py 가 견준다 — 계약은 도구를 import 하지 않는다, tests/test_axes.py).
거절 글에는 칸의 값이 없다.

칸마다 아래의 docstring 이 OpenAPI 의 description 이 된다. 이름은 `Materiality` 로 시작한다(generated/ 의 schema
이름).
"""

from typing import Annotated, Literal, TypedDict

from pydantic import Field, with_config

from esgapi.materiality.contracts.shapes import FORBID, Count

ValueChainRejectionKind = Literal[
    "too_large",
    "not_xlsx",
    "unsafe_xlsx",
    "bad_header",
    "not_text",
    "too_long",
    "too_many_rows",
    "too_many_scanned_rows",
    "no_rows",
]


@with_config(FORBID)
class MaterialityValueChainReadRow(TypedDict):
    """가치사슬 표 한 행 — 열 이름 아래 데이터 행 하나(앞뒤 공백을 뗀 글, 빈 칸은 ""). 열쇠는 input@1 의
    valueChain 원소(MaterialityValueChainRow)와 같다. 밸류체인 값은 파일의 글 그대로다."""

    business_unit: str
    """사업 부문. 빈 칸이면 바로 위 행의 것을 물려받는다(사업 내용도 비었으면 그것도)."""
    business_unit_description: str
    """사업 내용."""
    value_chain_stage: str
    """밸류체인(파일의 글 그대로 — 업스트림·자체운영·다운스트림 꼴의 검사는 웹)."""
    stakeholder: str
    """이해관계자."""
    business_activity: str
    """관련 비즈니스 활동."""


@with_config(FORBID)
class MaterialityValueChainReadOk(TypedDict):
    """읽었다 — 행은 파일의 차례(밸류체인·이해관계자·관련 비즈니스 활동이 다 빈 행은 건너뜀)."""

    ok: Literal[True]
    rows: Annotated[list[MaterialityValueChainReadRow], Field(min_length=1, max_length=100)]
    rowCount: Count
    """행 수(= rows 길이)."""


@with_config(FORBID)
class MaterialityValueChainReadRejected(TypedDict):
    """읽지 못했다 — 파일을 고쳐 다시 올린다."""

    ok: Literal[False]
    kind: ValueChainRejectionKind
    """too_large(바이트 상한) · not_xlsx(xlsx 가 아님 — 빈 본문 포함) · unsafe_xlsx(열 수 없는 꼴 — 압축·XML 방어) ·
    bad_header(열 이름 다섯을 찾지 못함) · not_text(수·날짜 칸) · too_long(글자 수) · too_many_rows(데이터 행 상한) ·
    too_many_scanned_rows(훑은 행 상한 — 빈 행이 너무 많음) · no_rows(데이터 행이 없음)."""
    row: Annotated[int, Field(ge=1)] | None
    """데이터 행 번호(열 이름 다음부터 1, 건너뛴 행은 세지 않음 — 화면 표의 행 번호). 파일 전체의 까닭이면 null."""
    column: Annotated[int, Field(ge=0, le=4)] | None
    """칸(0 사업 부문 · 1 사업 내용 · 2 밸류체인 · 3 이해관계자 · 4 관련 비즈니스 활동). 칸의 까닭이 아니면 null."""
    message: str
    """해요체 한 문장(행 번호는 있고 칸의 값은 없다). 화면은 이 글이 아니라 kind 로 글을 고른다."""


MaterialityValueChainRead = MaterialityValueChainReadOk | MaterialityValueChainReadRejected
"""판별 칸은 `ok`(true | false)다. pydantic 의 `discriminator` 는 걸지 않는다(translation/contracts/glossary_shapes.py
와 같은 까닭 — bool 판별 값이 OpenAPI mapping 에 글자로 적힌다). 두 갈래의 `ok` 가 Literal 이라 검사는 하나로 갈린다."""
