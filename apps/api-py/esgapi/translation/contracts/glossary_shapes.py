"""용어집 엑셀 읽기의 응답 꼴(POST /translation/glossary/read — 밴드 TR3a, MARC-ENT-392).

읽은 짝도, 읽지 못한 까닭도 200 이다 — 판별 칸 `ok`. 웹은 `ok: true` 의 `pairs` 를 실행 옵션
`options.glossary.base|final` 에 그대로 싣는다(실행이 자기 입력을 다 가진다 — 다시 하기 재현). `ok: false` 의 `kind` 는
tools/glossary_xlsx.py 의 RejectionKind 와 같은 열 개다(tests/contracts/test_glossary_shapes.py 가 견준다 — 계약은
도구를 import 하지 않는다, tests/test_axes.py). 거절 글에는 칸의 값이 없다.

칸마다 아래의 docstring 이 OpenAPI 의 description 이 된다. 이름은 `Translation` 으로 시작한다(generated/ 의
schema 이름).
"""

from typing import Annotated, Literal, TypedDict

from pydantic import Field, with_config

from esgapi.translation.contracts.shapes import FORBID, Count

GlossaryRejectionKind = Literal[
    "too_large",
    "not_xlsx",
    "unsafe_xlsx",
    "bad_header",
    "empty_cell",
    "not_text",
    "too_long",
    "duplicate_ko",
    "too_many_rows",
    "no_rows",
]


@with_config(FORBID)
class TranslationGlossaryPair(TypedDict):
    """용어집 한 짝 — 엑셀 한 행의 A 칸(한국어)과 B 칸(영문), 앞뒤 공백을 뗀 글."""

    ko: Annotated[str, Field(min_length=1)]
    en: Annotated[str, Field(min_length=1)]


@with_config(FORBID)
class TranslationGlossaryReadOk(TypedDict):
    """읽었다 — 짝은 파일의 행 차례(빈 행은 건너뜀)."""

    ok: Literal[True]
    pairs: Annotated[list[TranslationGlossaryPair], Field(min_length=1, max_length=500)]
    rowCount: Count
    """짝 수(= pairs 길이)."""


@with_config(FORBID)
class TranslationGlossaryReadRejected(TypedDict):
    """읽지 못했다 — 파일을 고쳐 다시 올린다."""

    ok: Literal[False]
    kind: GlossaryRejectionKind
    """too_large(바이트 상한) · not_xlsx(xlsx 가 아님 — 빈 본문 포함) · unsafe_xlsx(열 수 없는 꼴 — 압축·XML 방어) ·
    bad_header(1행이 「한국어」「영문」이 아님) · empty_cell(한 칸만 빔) · not_text(수·날짜 칸) · too_long(글자 수) ·
    duplicate_ko(같은 한국어 두 번) · too_many_rows(행·짝 수 상한) · no_rows(짝이 없음)."""
    row: Annotated[int, Field(ge=1)] | None
    """엑셀의 행 번호(1부터). 파일 전체의 까닭이면 null."""
    message: str
    """화면에 그대로 보일 해요체 한 문장(행 번호는 있고 칸의 값은 없다)."""


TranslationGlossaryRead = TranslationGlossaryReadOk | TranslationGlossaryReadRejected
"""판별 칸은 `ok`(true | false)다. pydantic 의 `discriminator` 는 걸지 않는다: bool 판별 값을 OpenAPI mapping 에 글자
"True"·"False" 로 적어(JSON 의 true·false 가 아님) 생성 타입이 어긋날 수 있다. 두 갈래의 `ok` 가 Literal 이라 검사는
그대로 하나로 갈린다."""
