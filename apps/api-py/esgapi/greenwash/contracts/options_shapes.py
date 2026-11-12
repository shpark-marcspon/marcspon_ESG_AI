"""실행 옵션 꼴 greenwash.options@1 — `POST /runs {module: "greenwash", options}` 의 options.
TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/options/greenwash.options@1.schema.json.

웹 RunRequest 의 parts·extraTerms 를 그대로 받는다(밴드 G1b). openapi 에는 오르지 않는다(RunIn.options 는
dict[str, object] 그대로) — 프론트는 이 고정 파일을 읽는다. 클래스 이름은 `Greenwash` 로 시작한다.

**이 파일에 로직은 없다.** 받기(검사 차례와 사람에게 보일 문장)는 끼움 flows/binding_e0.GreenwashBinding.check_options
가 한다 — 상한(쪽 1~300, 추가 단어 100개)은 그 파일의 상수와 같아야 한다(tests/contracts/test_options_shapes.py 가
견준다). reportYear·previousDocumentId 는 실행 옵션이 아니라 문서의 칸이다. criteria(판정 기준표)는 G2c-2 전까지
모르는 열쇠로 거절된다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, NotRequired, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.greenwash.contracts.shapes import FORBID

SHAPE: Final = "greenwash.options@1"

OptionPage = Annotated[int, Field(ge=1, le=300)]
"""쪽 번호. 1부터, 300까지(웹 MAX_PAGE_COUNT 와 같은 어림 — 문서의 쪽 수는 만들 때 모른다)."""


@with_config(FORBID)
class GreenwashOptionParts(TypedDict):
    """파트 셋의 점검 쪽. 셋 다 있어야 하고(빈 목록 = 그 파트 없음), 셋의 합집합이 한 쪽 이상이어야 한다. 한 쪽이
    두 파트에 들어도 된다(노트북 동작 — 셈에서 두 번)."""

    ceo: list[OptionPage]
    """CEO 메시지의 쪽."""
    company: list[OptionPage]
    """회사소개의 쪽."""
    climate: list[OptionPage]
    """기후/환경 토픽의 쪽."""


@with_config(FORBID)
class GreenwashOptions(TypedDict):
    """greenwash.options@1 — 그린워싱 실행의 옵션."""

    parts: GreenwashOptionParts
    """파트별 점검 쪽."""
    extraTerms: NotRequired[Annotated[list[str], Field(max_length=100)]]
    """추가 단어(없으면 없음). 보낼 수 있는 것은 100개까지이고, 앞뒤 공백·빈 것·겹친 것을 거른 뒤 한 단어 1~30자,
    30개까지여야 한다(괄호·따옴표 금지, 글자나 숫자 하나 이상 — flows/colab_e0.accept_extra_terms)."""


OPTIONS_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashOptions]]] = {SHAPE: TypeAdapter(GreenwashOptions)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
