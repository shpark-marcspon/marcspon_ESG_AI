"""EDK 인벤토리 엑셀 읽기의 응답 꼴(POST /dataverify/edk/read — 밴드 DVX1, MARC-ENT-505 §2.1 ③).

읽은 것도, 읽지 못한 까닭도 200 이다 — 판별 칸 `ok`. 웹은 `ok: true` 의 `data` 를 JSON 파일을 올린 것과 같은 길(미리
읽기·크기 셈)에 넣고, 실행 입력 `options.input.data`(dataverify.input@1 — 이 꼴은 바꾸지 않는다)에 싣는다. 읽기
경로는 상태가 없다. `data` 에는 검증 대상 테마(지금 「환경」)만 싣고 나머지 테마는 수(`skipped`)만 낸다. `ok: false` 의
`kind` 는 tools/edk_xlsx.py 의 RejectionKind 와 같은 열이다(tests/contracts/test_edk_read_shapes.py 가 견준다 — 계약은
도구를 import 하지 않는다). 거절 글에는 칸의 값이 없다.

칸마다 아래의 docstring 이 OpenAPI 의 description 이 된다. 이름은 `Dataverify` 로 시작한다(generated/ 의 schema
이름 — 다른 모듈의 것과 겹치지 않게).
"""

from typing import Annotated, Literal, TypedDict

from pydantic import Field, with_config

from esgapi.dataverify.contracts.shapes import FORBID, Count, EdkItem, Year

DataverifyEdkRejectionKind = Literal[
    "too_large",
    "not_xlsx",
    "unsafe_xlsx",
    "bad_header",
    "bad_cell",
    "no_theme",
    "too_many_rows",
    "too_many_scanned_rows",
    "no_rows",
    "no_target_theme",
    "long_cell",
    "converted_too_large",
]


@with_config(FORBID)
class DataverifyEdkReadSkipped(TypedDict):
    """검증 대상이 아니라 싣지 않은 테마(이름은 내지 않는다)."""

    themes: Count
    """뺀 테마 수."""
    items: Count
    """그 테마들의 항목 수."""


@with_config(FORBID)
class DataverifyEdkReadOk(TypedDict):
    """읽었다 — `data` 는 input@1 의 data 꼴(테마 → 항목, 항목 열쇠 열하나). 항목은 파일의 행 차례다."""

    ok: Literal[True]
    data: dict[str, list[EdkItem]]
    """검증 대상 테마 → 항목. 수 칸의 정수인 소수(90001.0)는 정수로, 글자는 받은 그대로, 빈 칸은 null. values 의
    열쇠는 머리 「YYYY년」에서 「년」을 뗀 연도다."""
    itemCount: Count
    """data 에 실린 항목 수."""
    skipped: DataverifyEdkReadSkipped
    years: list[Year]
    """머리의 연도(오름차순)."""
    skippedEmptyRows: Count
    """건너뛴 빈 행 수."""
    ignoredColumns: Count
    """읽지 않은 머리 칸 수(「공시」 등 — 빈 머리 칸은 세지 않는다)."""


@with_config(FORBID)
class DataverifyEdkReadRejected(TypedDict):
    """읽지 못했다 — 파일을 고쳐 다시 올린다."""

    ok: Literal[False]
    kind: DataverifyEdkRejectionKind
    """too_large(바이트 상한) · not_xlsx(xlsx 가 아님 — 빈 본문 포함) · unsafe_xlsx(열 수 없는 꼴 — 압축·XML 방어) ·
    bad_header(1행에서 열 이름을 찾지 못함·겹침) · bad_cell(날짜·참/거짓 칸) · no_theme(테마 칸 빔) ·
    too_many_rows(항목 상한) · too_many_scanned_rows(훑은 행 상한 — 빈 행이 너무 많음) · no_rows(항목이 없음) ·
    no_target_theme(검증 대상 테마의 항목이 없음) · long_cell(칸 글자 수 상한) · converted_too_large(실을 글자·수 합이
    실행 옵션 상한을 넘음)."""
    row: Annotated[int, Field(ge=1)] | None
    """엑셀의 행 번호(머리가 1). 파일 전체의 까닭이면 null."""
    column: Annotated[int, Field(ge=1)] | None
    """엑셀의 열 번호(A 가 1). 칸의 까닭이 아니면 null."""
    message: str
    """해요체 한 문장(행·열 번호는 있고 칸의 값은 없다). 화면은 이 글이 아니라 kind 로 글을 고른다."""


DataverifyEdkRead = DataverifyEdkReadOk | DataverifyEdkReadRejected
"""판별 칸은 `ok`(true | false)다. pydantic 의 `discriminator` 는 걸지 않는다(materiality/contracts/
value_chain_shapes.py 와 같은 까닭 — bool 판별 값이 OpenAPI mapping 에 글자로 적힌다). 두 갈래의 `ok` 가 Literal
이라 검사는 하나로 갈린다."""
