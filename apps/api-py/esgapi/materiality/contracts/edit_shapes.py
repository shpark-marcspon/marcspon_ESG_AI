"""고침 꼴 — 끝난 중대성평가 IRO 실행의 결과(materiality.result@2) 글 칸 고치기(밴드 IRS3, 결정 MARC-ENT-561).

받는 꼴(POST /materiality/runs/{run_id}/result/edits 의 본문 — 경로 쪽 Schema 가 이 꼴의 고침 하나를 싣는다)과 내는 꼴
materiality.result-edits@1(GET·POST …/result/edits 의 응답)과 상한 상수다. **이 파일에 로직은 없다**(주소 검사·바른
주소·값 검사·덮기 — outputs/edits.py, 저장 — service/actions/edits.py).
- 칸 주소는 JSON Pointer(RFC 6901)다 — result@2 본문 안 자리. 허용 꼴은 POINTER_PATTERN 하나(글 칸만 — 분류 값·가치사슬
  활동·토픽/서브토픽 이름은 고치지 않는다). 숫자는 0부터, 앞 0 없음.
- 맥락 항목(title·summary·url) 고침은 같은 토픽·같은 쪽(regulations·controversies)·같은 원본 url 의 항목 전부와 그 재무
  항목의 Pathway 사본에 퍼진다. 저장·응답의 주소는 그 묶음의 첫 자리(바른 주소)다.
- 상한(코드포인트)은 **어림**이다(근거 없는 수 — 정의·①②③·summary 4,000 · title 1,000 · url 2,048). 마이그레이션
  CHECK 는 값을 문면에 굳힌다(models.py) — 바꾸면 새 마이그레이션.
- 시각은 +09:00 ISO 8601 글자다(짓기가 core.schemas.to_seoul_iso). 계약은 ninja·core.schemas 를 import 하지 않는다.
- 이름은 전부 `MaterialityResultEdit` 로 시작하고 contracts/shapes.py 의 이름과 겹치지 않는다(generated/ 의 schema
  이름 — 같은 이름이면 하나로 합쳐진다).
칸마다 아래의 docstring 이 JSON 스키마의 description 이 된다.
"""

from typing import Annotated, Final, Literal, TypedDict

from pydantic import ConfigDict, Field, with_config

from esgapi.materiality.contracts.shapes import FORBID

EDITS_SHAPE: Final = "materiality.result-edits@1"
STRICT_FORBID: Final = ConfigDict(extra="forbid", use_attribute_docstrings=True, strict=True)

TEXT_MAX_CHARS: Final = 4000
"""영향 정의·①②③·맥락 summary 의 상한(코드포인트, 어림)."""
TITLE_MAX_CHARS: Final = 1000
"""맥락 title 의 상한(코드포인트, 어림)."""
URL_MAX_CHARS: Final = 2048
"""맥락 url 의 상한(코드포인트, 어림)."""
VALUE_MAX_OCTETS: Final = 16384
"""고침 행 value 의 바이트 상한(마이그레이션 CHECK — 마지막 그물. 4,000자 × 4 바이트보다 넓다, 어림)."""
POINTER_MAX_CHARS: Final = 200
CHANGES_MIN: Final = 1
CHANGES_MAX: Final = 200
"""한 저장의 고침 수(어림)."""

_N = "(0|[1-9][0-9]{0,5})"
POINTER_PATTERN: Final = (
    f"^/part2/topics/{_N}/subtopics/{_N}/("
    f"(impact|pathway)/rows/{_N}/impactDefinition"
    f"|pathway/rows/{_N}/(impactDriver|businessImpact|financialImpact)"
    f"|(impact|financial|pathway)/rows/{_N}/context/(regulations|controversies)/{_N}/(title|summary|url)"
    ")$"
)
"""고칠 수 있는 칸 주소의 꼴(받기·마이그레이션 CHECK 가 같은 글). 숫자 칸은 여섯 자리까지."""


@with_config(STRICT_FORBID)
class MaterialityResultEditChange(TypedDict):
    """고침 하나(본문). value 가 공백만·빈 글이면 null(화면 「–」)로 저장한다. 원문과 같은 값 = 되돌림."""

    pointer: Annotated[str, Field(min_length=1, max_length=POINTER_MAX_CHARS)]
    """고칠 칸의 JSON Pointer(예: /part2/topics/0/subtopics/0/impact/rows/0/impactDefinition)."""
    value: str | None
    """새 글(null = 빈 칸). url 은 null 이거나 http:// · https:// 로 시작한다(앞뒤 공백을 뗀 글로 견줌)."""


@with_config(FORBID)
class MaterialityResultEditor(TypedDict):
    """고친 사람(응답 전용 — 사람은 세션에서 온다)."""

    name: Annotated[str, Field(min_length=1)]
    """화면에 보일 이름(못 풀면 「알 수 없는 사용자」)."""


@with_config(FORBID)
class MaterialityResultEdit(TypedDict):
    """지금 원문과 다른 칸 하나(바른 주소)."""

    pointer: str
    """칸의 바른 주소(맥락 항목은 퍼짐 묶음의 첫 자리)."""
    value: str | None
    """지금 값(가장 큰 revision 의 값)."""
    original: str | None
    """AI 가 쓴 원문(결과 본문의 그 자리 값)."""
    editedAt: str
    """지금 값을 저장한 때(+09:00 ISO 8601)."""
    editedBy: MaterialityResultEditor


@with_config(FORBID)
class MaterialityResultEdits(TypedDict):
    """materiality.result-edits@1 — 한 실행의 결과 고침. revision 은 실행 하나의 저장 번호(고침이 없으면 0)이고 다음
    저장의 baseRevision 이 된다."""

    schemaVersion: Literal["materiality.result-edits@1"]
    revision: Annotated[int, Field(ge=0)]
    edits: list[MaterialityResultEdit]
    """지금 값이 원문과 다른 칸만, 본문 차례(토픽 → 서브토픽 → impact → financial → pathway → 줄 → 칸)."""
