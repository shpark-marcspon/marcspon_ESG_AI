"""셋째 결과 꼴 translation.layout@1 — PDF 입력 흐름(translation.pdf@158, 밴드 TRD2·결정 MARC-ENT-471)의 블록·좌표 결과.

흐름(flows/pdf_158.py report)이 result@1·digest@1 곁에 셋째 결과로 남긴다. 화면은 원본 PDF 쪽 위에
`units[].members[].bbox`(pt, 쪽 왼쪽 위 원점 — 쪽마다 `pages[].width·height` 로 나눠 비율로)의 상자를 그리고, 누르면
`source` 와 문체별 번역(`variants[].units[]` — 같은 차례)을 짝으로 보인다. 표는 칸 상자(`cells[].bbox`)·칸 번역,
group·table 은 묶음 상자 하나, missing·unplaced·skipped.imageOnlyPages 는 「번역 안 됨」. 머리글·꼬리말은 번역하지
않는다(level source_only).
워드 흐름(translation.colab@158)은 이 꼴을 내지 않는다. result@1·digest@1 은 바이트 그대로다.

칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다. 이름은 `TranslationLayout` 으로 시작한다
(generated/ 의 schema 이름 — 다른 모듈의 같은 이름과 겹치지 않게, 밴드 TRS3). 고정 파일은
tests/data/flow-shapes/translation.layout@1.schema.json. 칸을 더하는 것은 @1 안, 빼거나 바꾸면 @2 다.
"""

from collections.abc import Mapping
from typing import Annotated, Any, Final, Literal, NotRequired, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.translation.contracts.shapes import FORBID, Count, PageNum, VariantLabel

LAYOUT_SHAPE: Final = "translation.layout@1"

Points = Annotated[float, Field(ge=0)]
Box = Annotated[list[float], Field(min_length=4, max_length=4)]
"""[x0, y0, x1, y1] — pt, 쪽 왼쪽 위 원점(파서 docparse 의 상자 그대로)."""
Tag = Annotated[str, Field(pattern=r"^(BLOCK|VISUAL|TABLE) [1-9][0-9]*$")]


@with_config(FORBID)
class TranslationLayoutParser(TypedDict):
    name: str
    version: str
    layout: Literal[2]
    """파서의 분해 판(번역 판 2만 받는다)."""


@with_config(FORBID)
class TranslationLayoutSource(TypedDict):
    """원본 PDF 와 그것을 읽은 판."""

    pdfSha256: str
    """실행 문서 바이트의 sha256(PDF 가 아니어도)."""
    pageCount: Count | None
    """PDF 의 쪽 수. 파서 앞에서 거절했으면 null."""
    parser: TranslationLayoutParser | None
    """파서 앞에서 거절했으면 null."""
    adapter: str
    """어댑터 판(`pdf_tags@1`)."""


@with_config(FORBID)
class TranslationLayoutPage(TypedDict):
    """쪽 범위 안의 쪽."""

    page: PageNum
    width: Points
    height: Points
    textLayer: Literal["present", "none"]
    """none = 글자 층이 없는 쪽(그림·스캔 — 번역하지 않음)."""


@with_config(FORBID)
class TranslationLayoutMember(TypedDict):
    """단위를 이룬 파서 블록(표 단위면 표 하나)."""

    id: str
    """파서의 위치 id(`p3-b5`, 표는 `p3-t1`)."""
    key: str | None
    """파서의 내용 해시 키(쪽 범위·상자 흔들림에 같다)."""
    kind: Literal["heading", "paragraph", "table"]
    bbox: Box
    source: str
    """원문(표는 엔진에 넣은 pipe 표 글)."""


@with_config(FORBID)
class TranslationLayoutCell(TypedDict):
    """표 단위의 비지 않은 칸."""

    row: Count
    """원 표의 행 번호(빈 행을 뺀 pipe 행 번호가 아니다)."""
    col: Count
    id: str
    """`<표 id>:r<행>c<열>`."""
    bbox: Box | None
    """칸 글자의 상자. 글자 자리를 잇지 못했으면 null."""
    source: str
    """칸 글 + 그 칸의 각주 표시."""


@with_config(FORBID)
class TranslationLayoutUnit(TypedDict):
    """번역 단위 하나(엔진의 태그 하나) — 지도 차례(쪽, 읽는 차례)."""

    tag: Tag | None
    """쪽 안의 태그(`BLOCK 2`). 머리글·꼬리말은 null(태그 글 밖 — 번역하지 않음)."""
    page: PageNum
    kind: Literal["block", "visual", "table", "header", "footer"]
    """block = 제목과 이어지는 문단 묶음, visual = 도표 라벨 묶음(글자 층만), table, header·footer = 머리글·꼬리말."""
    members: list[TranslationLayoutMember]
    cells: NotRequired[list[TranslationLayoutCell]]
    """표 단위만."""
    rows: NotRequired[list[Count]]
    """표 단위만: pipe 표의 행(머리 행 = 0) → 원 표 행 번호."""


@with_config(FORBID)
class TranslationLayoutPlacedCell(TypedDict):
    row: Count
    """원 표의 행 번호."""
    col: Count
    text: str


@with_config(FORBID)
class TranslationLayoutPlacedUnit(TypedDict):
    """문체 하나에서 단위 하나의 번역 — `units` 와 같은 차례."""

    tag: Tag | None
    page: PageNum
    level: Literal["block", "group", "cell", "table", "source_only", "missing"]
    """block = 멤버마다 번역(translations 가 멤버 차례), group = 묶음 번역 하나(문단 수가 바뀜 — 상자는 멤버 전부),
    cell = 칸마다(cells), table = 표 번역 하나(행·열 모양이 바뀜), source_only = 번역하지 않음(머리글·꼬리말),
    missing = 번역에서 이 태그를 찾지 못함(글은 unplaced 에 있을 수 있다)."""
    translations: list[str] | None
    cells: NotRequired[list[TranslationLayoutPlacedCell]]
    """level cell 만."""


@with_config(FORBID)
class TranslationLayoutUnplaced(TypedDict):
    """단위에 붙이지 못한 번역 글(버리지 않는다)."""

    page: PageNum
    text: str


@with_config(FORBID)
class TranslationLayoutVariant(TypedDict):
    """문체 하나(result@1 의 문체 차례)."""

    label: VariantLabel
    stage: Literal["autofix", "translated"]
    """쓴 글: 자동수정이 done 이면 autofix.translatedText, 아니면 translatedText."""
    units: list[TranslationLayoutPlacedUnit]
    unplaced: list[TranslationLayoutUnplaced]


@with_config(FORBID)
class TranslationLayoutSkipped(TypedDict):
    emptyTables: list[str]
    """칸이 다 빈 표(파서 표 id) — 번역 단위가 아니다."""
    imageOnlyPages: list[PageNum]
    """글자 층이 없는 쪽."""


@with_config(FORBID)
class TranslationLayoutWarning(TypedDict):
    code: Literal["image_only_page", "tag_missing", "tag_extra", "tag_shift", "page_missing", "length_ratio"]
    page: PageNum | None
    tag: str | None
    variant: VariantLabel | None
    """문체(되붙임 경고). 어댑터의 경고(image_only_page)는 null."""


@with_config(FORBID)
class TranslationLayout(TypedDict):
    """translation.layout@1 — PDF 영문번역 한 건의 블록·좌표 결과."""

    schemaVersion: Literal["translation.layout@1"]
    status: Literal["done", "rejected"]
    """결과 translation.result@1 의 status."""
    sourceSha256: str
    """엔진에 넣은 태그 글의 sha256(result@1 document.sourceSha256 과 같다)."""
    source: TranslationLayoutSource
    pages: list[TranslationLayoutPage]
    units: list[TranslationLayoutUnit]
    variants: list[TranslationLayoutVariant]
    """rejected 면 빈 목록."""
    skipped: TranslationLayoutSkipped
    warnings: list[TranslationLayoutWarning]


LAYOUT_SHAPES: Final[Mapping[str, TypeAdapter[Any]]] = {
    LAYOUT_SHAPE: TypeAdapter[TranslationLayout](
        Annotated[TranslationLayout, Field(title=LAYOUT_SHAPE, description="PDF 영문번역 한 건의 블록·좌표 결과.")]
    )
}
"""꼴 id → 검사기. validate_python(결과, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
