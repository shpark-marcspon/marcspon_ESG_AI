"""실행 옵션 꼴 dataverify.options@1 — `POST /runs {module: "dataverify", options}` 의 options(밴드 DV1d·DV1f).
TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/options/dataverify.options@1.schema.json.

칸은 input(필수)과 source(선택). input 은 입력 꼴 dataverify.input@1(shapes.DataverifyInput)을 그대로 가져다
쓴다(두 번째 정본 0). 감싸 두는 것은 뒤에 칸(AI 설정 판 등)이 붙어도 input@1 을 @2 로 올리지 않으려고다. 문서는
없다 — 데이터 검증은 문서 없는 흐름이다(ND1 — 실행의 documentId 를 받지 않는다).
- openapi 에는 오르지 않는다(RunIn.options 는 dict[str, object] 그대로) — 프론트는 이 고정 파일을 읽는다. 목록
  응답(밴드 DV1g)이 DataverifySource 를 다시 써 그 꼴만 openapi 에 오른다 — 이름과 꼴은 이 판으로 굳힌다.
- 크기 상한은 256KiB 다(core.flows.binding.DOCUMENTLESS_OPTIONS_MAX_OCTETS — apps.py 가 등록 인자로 넘긴다. 다른 흐름의
  16KiB 가 아니다). EDK 입력 한 건이 16KiB 를 넘는다(「환경」 42항목 어림 약 13KB~50KB).
- web_search 칸이 없다 — 인사이트는 늘 web_search 를 싣는다(MARC-ENT-372). 비용 상한 칸도 없다 — 끼움의 코드 상수다
  (flows/binding_156.STAGE_COSTS). 둘 다 주면 모르는 열쇠로 거절한다.
- source(밴드 DV1f, MARC-ENT-420)는 입력의 출처 — 올린 파일 {kind: "file", name} 이나 붙여 넣기 {kind: "paste"}. 표시
  전용이다: 닿는 곳은 실행 행의 options(GET /runs/{id})와 목록(DV1g)뿐이고 흐름·프롬프트·결과·엑셀·로그에는 넘기지
  않는다(끼움의 inputs 는 input 만). 판을 올리지 않는다 — 더하기만이라 옛 본문 {input} 이 그대로 맞다(TR3a batchId 꼴).
  name 은 1~255자(글자 수), `/`·`\\`·제어 글자(C0·DEL·C1)·양방향 제어 글자를 받지 않고 확장자는 보지 않는다. 서버는
  고치지 않는다(받은 그대로 저장 — 경로 떼기는 웹 몫). 크기 몫은 많아야 약 1.1KB 라 그만큼 input 이 쓸 몫이 준다
  (상한은 그대로).

**이 파일에 로직은 없다.** 받기(사람에게 보일 문장)는 끼움 flows/binding_156.DataverifyBinding.check_options 가 한다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, Literal, NotRequired, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.dataverify.contracts.shapes import FORBID, DataverifyInput

SHAPE: Final = "dataverify.options@1"
SOURCE_NAME_MAX: Final = 255
SOURCE_NAME_PATTERN: Final = r"^[^/\\\u0000-\u001f\u007f-\u009f\u061c\u200e\u200f\u202a-\u202e\u2066-\u2069]+$"
r"""거절하는 글자 — `/`·`\`·C0(U+0000~001F)·DEL·C1(U+0080~009F)·양방향 제어(U+061C·200E·200F·202A~202E·
2066~2069). 이스케이프는 `\uXXXX` 꼴만 쓴다 — pydantic(Rust regex)과 웹(ECMAScript `new RegExp(p, "u")`)에서
같은 뜻이다(`\x{…}` 는 JS 에서 다르다)."""

SourceName = Annotated[str, Field(min_length=1, max_length=SOURCE_NAME_MAX, pattern=SOURCE_NAME_PATTERN)]


@with_config(FORBID)
class DataverifyFileSource(TypedDict):
    """올린 파일에서 읽은 입력."""

    kind: Literal["file"]
    name: SourceName
    """파일 이름(경로 없이 — 웹이 뗀다). 표시 전용, 받은 그대로 둔다."""


@with_config(FORBID)
class DataverifyPasteSource(TypedDict):
    """붙여 넣은 입력. 이름이 없다(주면 모르는 열쇠로 거절)."""

    kind: Literal["paste"]


DataverifySource = Annotated[DataverifyFileSource | DataverifyPasteSource, Field(discriminator="kind")]


@with_config(FORBID)
class DataverifyOptions(TypedDict):
    """dataverify.options@1 — 데이터 검증 실행의 옵션."""

    input: DataverifyInput
    """검증할 입력(dataverify.input@1 — 받은 그대로 흐름에 넘긴다)."""
    source: NotRequired[DataverifySource]
    """입력의 출처(표시 전용 — 흐름에 넘기지 않는다). 없으면 알 수 없음(옛 본문)."""


OPTIONS_SHAPES: Final[Mapping[str, TypeAdapter[DataverifyOptions]]] = {SHAPE: TypeAdapter(DataverifyOptions)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
