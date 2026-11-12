"""기본 단어 목록의 응답 꼴(GET /greenwash/terms/default)과 AI 설정 판의 대상 단어 꼴 둘(밴드 G2d — 저장 본문의
GreenwashTermIn, 판 응답의 GreenwashTerm). TypedDict(모르는 키 금지) → JSON 스키마.

고정 파일은 tests/data/flow-shapes/terms/greenwash.terms-default.schema.json. 클래스 이름이 openapi 의 구성요소 이름이
되므로 `Greenwash` 로 시작한다. 값은 engines/e0/wordcount.GREEN_TERMS 를 차례 그대로 담는다(경로
service/apis/greenwash.py 가 flows/colab_e0.DEFAULT_TERMS 로 import 해서 돌려준다 — 복사하지 않는다). 이 파일은
등록 길(apps.py 의 ready)에서 들이지 않는다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, TypedDict

from pydantic import ConfigDict, Field, TypeAdapter, with_config

from esgapi.greenwash.contracts.shapes import FORBID

SHAPE: Final = "greenwash.terms-default"
STRICT_FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True, strict=True)
"""입력 꼴 — 모르는 키 금지 + 타입을 바꿔 받지 않음(core contracts/ai_setting_shapes 의 STRICT_FORBID 와 같은 값)."""

TERMS_SENT_MAX: Final = 1000
"""저장 본문 terms 의 목록 길이 꼴 상한(넘으면 422). 느슨한 그물이다 — 실제 상한 100 은 받기(flows/terms_e0)가 400
TERMS_COUNT 로 막는다(선례 binding_e0.EXTRA_TERMS_SENT_MAX)."""
TERM_SENT_CHARS: Final = 200
"""낱말 글의 꼴 상한(넘으면 422). 실제 규칙 1~30자는 받기의 400 TERMS_TEXT."""


@with_config(FORBID)
class GreenwashDefaultTerms(TypedDict):
    """기본 단어 목록(의심 낱말). 노트북 목록을 글자·차례 그대로 싣는다 — 흠을 고치지 않는다.

    노트북에서 쉼표가 빠져 두 낱말이 붙은 것(예: 「eco프리」)도 그대로다.
    화면이 사용자가 더하는 단어와 견줄 때의 키: `normalize_term(t).replace(" ", "")` — 소문자로 바꾸고 `- _ / · • ∙` 를
    공백으로 바꾼 뒤 공백을 접고 모두 지운다(calc/wordcount.normalize_term, G1c 의 「추가 단어」 규칙. 「탄소 중립」 =
    「탄소중립」).
    """

    terms: list[str]
    """기본 단어(노트북의 차례)."""


TERMS_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashDefaultTerms]]] = {SHAPE: TypeAdapter(GreenwashDefaultTerms)}
"""꼴 id → 검사기. json_schema() 로 고정 파일을 뽑는다."""


@with_config(STRICT_FORBID)
class GreenwashTermIn(TypedDict):
    """판 대상 단어 하나의 입력(저장 본문 GreenwashAiSettingCreate.terms 의 칸). 두 칸 다 필수. 글 규칙(1~30자·괄호·
    따옴표·보이지 않는 글자 0·비교 키 겹침 0)·개수(100)·켠 것 ≥ 1 은 받기(flows/terms_e0.accept_terms — 400 TERMS_*)가
    본다."""

    text: Annotated[str, Field(max_length=TERM_SENT_CHARS)]
    """낱말(앞뒤 공백을 뺀 값이 정규형)."""
    enabled: bool
    """사용 — 끄면 셈에서 빠진다(판에는 남는다)."""


@with_config(FORBID)
class GreenwashTerm(TypedDict):
    """판의 대상 단어 하나(받기를 거친 정규형 — 받은 차례 그대로). 빈도 목록(의심 낱말)만 바꾼다 — 판정할 문장을 고르는
    환경 신호는 코드 고정(MARC-ENT-394)."""

    text: str
    """낱말(앞뒤 공백을 뺀 1~30자)."""
    enabled: bool
    """사용. 켠 낱말만 판 차례대로 센다."""
