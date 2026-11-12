"""실행 옵션 꼴 translation.options@1 — `POST /runs {module: "translation", options}` 의 options(밴드 TR2).
TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/options/translation.options@1.schema.json.

칸 꼴은 입력 꼴(shapes.py — translation.input@1)의 TypedDict 를 그대로 가져다 쓴다(두 번째 정본 0). 입력 꼴과 다른 것:
- document 가 없다 — 문서는 실행의 documentId 로 온다(흐름이 바이트를 읽어 판정 — docx·글).
- 고를 수 있는 칸(실행 옵션 256KiB 상한 — apps.py 가 흐름에 등록한 core DOCUMENTLESS_OPTIONS_MAX_OCTETS, 밴드 TR3a):
  batchId(묶음 id — 밴드 TR3a), glossary(없으면 빈 용어집, 있으면 base·
  final 각각 없으면 빈 목록 — 저장소에 기본 용어집은 없다), peerGroupStyle(없거나 null 이면 싣지 않음), autofix(없으면
  true — 코랩 값), retry(실패 쪽만 다시 — 코랩 셀 50).
openapi 에는 오르지 않는다(RunIn.options 는 dict[str, object] 그대로) — 프론트는 이 고정 파일을 읽는다.

**이 파일에 로직은 없다.** 받기(사람에게 보일 문장)는 끼움 flows/binding_158.TranslationBinding.check_options 가 한다 —
retry.pages 의 겹침 거절도 거기다(JSON 스키마의 uniqueItems 로 싣지 않는다).
"""

from collections.abc import Mapping
from typing import Annotated, Final, NotRequired, TypedDict

from pydantic import Field, TypeAdapter, with_config

from esgapi.translation.contracts.shapes import (
    FORBID,
    Company,
    GlossaryPair,
    PageRange,
    Part,
    PeerGroupStyle,
    Style,
)

SHAPE: Final = "translation.options@1"
RETRY_PAGES_MAX: Final = 300
"""retry.pages 의 길이 상한(그린워싱 옵션의 쪽 상한과 같은 어림)."""
GLOSSARY_PAIRS_MAX: Final = 500
"""용어집 base·final 각각의 짝 수 상한(용어집 엑셀 파일당 데이터 행 상한과 같다 — tools/glossary_xlsx.py, 추정). 글자 수
상한은 옵션에 걸지 않는다(짝 꼴은 입력 꼴 그대로) — 마지막 잠금은 옵션 바이트 상한이다."""
BATCH_ID_PATTERN: Final = r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$"

RetryPage = Annotated[int, Field(ge=1)]


@with_config(FORBID)
class TranslationOptionGlossary(TypedDict):
    """용어집(입력 꼴 Glossary 의 칸 둘 — 각각 고를 수 있다)."""

    base: NotRequired[Annotated[list[GlossaryPair], Field(max_length=GLOSSARY_PAIRS_MAX)]]
    """평가 용어집(코랩 GLOSSARY). 없으면 빈 목록. 많아야 500짝."""
    final: NotRequired[Annotated[list[GlossaryPair], Field(max_length=GLOSSARY_PAIRS_MAX)]]
    """최종 용어집(코랩 FINAL_GLOSSARY). 없으면 빈 목록. 많아야 500짝."""


@with_config(FORBID)
class TranslationRetryOption(TypedDict):
    """실패 쪽만 다시(코랩 셀 50 RETRY_PAGES). 앞 실행의 번역 글(자동수정 전)에 고른 쪽만 다시 번역해 끼우고, 검수·
    자동수정은 **전 쪽** 다시 돈다. 앞 실행은 같은 회사·영문번역·끝남·결과가 거절이 아님이어야 하고(아니면 결과
    rejected `retry_source_not_found`), 원문 sha256 과 문체 묶음, AI 설정 판(실행 versions 의 판 열쇠 — 열쇠 없는 옛
    실행도 다른 판으로 본다)이 같아야 한다(아니면 `retry_source_mismatch`)."""

    fromRunId: Annotated[int, Field(ge=1)]
    """번역 글을 가져올 앞 실행."""
    pages: Annotated[list[RetryPage], Field(min_length=1, max_length=RETRY_PAGES_MAX)]
    """다시 번역할 쪽 번호(1부터, 겹침 금지). 원문에 없는 쪽은 건너뛴다(경고 retry_page_missing)."""


@with_config(FORBID)
class TranslationOptions(TypedDict):
    """translation.options@1 — 영문번역 실행의 옵션."""

    batchId: NotRequired[Annotated[str, Field(pattern=BATCH_ID_PATTERN)]]
    """묶음 id(소문자 uuid — 웹이 짓는다). [번역 시작] 한 번이 묶음 하나이고, 그 묶음의 파트 실행마다 같은 값이다.
    [이 파트만 다시]는 같은 옵션·같은 batchId 다. 없으면 묶음에 들지 않은 실행. 흐름의 입력에는 싣지 않는다."""
    company: Company
    part: Part
    """번역할 파트(코랩 셀 38 CURRENT_PART). ceo_message 면 번역 모델이 경로 standard(Sonnet)다."""
    style: Style
    pages: PageRange
    ceoPageLimit: Annotated[int, Field(ge=0)] | None
    """ceo_message 파트의 쪽 조각 수 상한(코랩 셀 49 CEO_PAGE_LIMIT, 코랩 값 6). null = 제한 없음."""
    glossary: NotRequired[TranslationOptionGlossary]
    """용어집. 없으면 빈 용어집(저장소에 기본 용어집은 없다 — 코랩의 용어집은 한 고객사의 것)."""
    peerGroupStyle: NotRequired[PeerGroupStyle | None]
    """peer group 문체 글. 없거나 null 이면 싣지 않는다."""
    autofix: NotRequired[bool]
    """검수 이슈 기반 자동수정(코랩 셀 67). 없으면 true."""
    retry: NotRequired[TranslationRetryOption]
    """실패 쪽만 다시. 없으면 처음부터 번역."""


OPTIONS_SHAPES: Final[Mapping[str, TypeAdapter[TranslationOptions]]] = {SHAPE: TypeAdapter(TranslationOptions)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
