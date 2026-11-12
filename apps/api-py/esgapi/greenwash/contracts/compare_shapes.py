"""비교 꼴 greenwash.compare@1 의 정의 — 한 문서의 두 판(base·target)의 판정 문장을 짝지은 결과. **초안 판 — 굳힘 전.**

초안 판의 뜻: 프론트가 비교 화면·엑셀 「앞 판 비교」 시트를 이 꼴로 한 번 지은 뒤 굳힌다. 굳히기 전에는 `@1` 안에서
감독 승인으로 칸을 고칠 수 있다. 굳힌 뒤에 꼴을 바꾸면 새 판(@2)이다.

TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/compare/greenwash.compare@1.schema.json.
칸의 docstring 이 JSON 스키마의 description 이 된다(use_attribute_docstrings). 클래스 이름이 openapi 의 구성요소 이름이
되므로 전부 `Greenwash` 로 시작한다(ninja 는 같은 이름의 구성요소를 조용히 덮는다).
`level`·`page`·`parts` 의 타입과 뜻은 greenwash.result@1(contracts/shapes.py)의 항목과 같다 — 그 타입을 들여 쓴다.

**이 파일에 로직은 없다.** 아래 규칙은 짝을 짓는 뒤 밴드(수정본 밴드)와 화면이 같은 뜻을 읽도록 적어 둔 것이다.

대표 실행: 판(문서)마다 확정본(검토 greenwash.review@2 의 state = confirmed)이 대표이고, 없으면 그 판의 마지막 실행이
    대표이며 `unconfirmed: true` 다. 서버가 고른다(경로는 문서 id 만 받는다).
견주는 문장: 확정본은 채택(adopted)한 문장만, 미확정은 전부.
    ★ 비대칭에 주의: base 확정본에서 제외한 문장이 target(미확정)에 그대로 걸리면 짝이 없어 `new` 로 보일 수 있다.
짝 열쇠: 정규화한 문장 글 + `parts`(쪽 번호는 뺀다 — 판마다 쪽이 밀린다). 같은 열쇠의 문장이 둘 이상이면 나온 차례로
    하나씩 짝짓는다. 비슷한 글 짝짓기는 2차다: 고쳐 쓴 문장은 `resolved_*` 하나 + `new` 하나로 보일 수 있다.
분류 일곱(화면 글자는 디자인이 정한다):
    remaining              짝이 있고 등급이 같다                       base·target 둘 다
    level_changed          짝이 있고 등급이 다르다                     base·target 둘 다
    resolved_deleted       base 에만 있고 target 판 글에서 그 문장을 못 찾음(문장을 지움)   base 만
    resolved_not_flagged   base 에만 있고 target 판 글의 점검 쪽에 그 문장이 그대로 있음(더는 지적 안 됨)  base 만
    resolved_undetermined  base 에만 있고 base 판 글에서도 그 문장을 못 찾음(가를 수 없음)    base 만
    new                    target 에만 있다                            target 만
    out_of_scope           한쪽에만 있고 다른 판 글에서 찾은 쪽이 모두 그 판의 점검 쪽 밖   base 나 target 의 한쪽
해소 가르기: target 실행의 extract 단계가 남긴 쪽 글(쪽마다 정규화)에서 정규화한 base 문장을 찾는다. 찾은 쪽 가운데
    하나라도 target 의 점검 쪽(result@1 의 pages)이면 not_flagged, 찾았는데 모두 점검 쪽 밖이면 out_of_scope, 못 찾으면
    base 실행의 쪽 글에서 찾아 있으면 deleted, 거기서도 못 찾으면 undetermined.
target 에만 있는 문장: base 실행의 쪽 글에서 찾아, 찾았는데 그 쪽이 모두 base 의 점검 쪽 밖이면 out_of_scope, 그 밖(못
    찾음, 또는 점검 쪽에서 찾음)은 new. 쪽 번호를 판끼리 견주지 않는다 — 문장이 다른 판의 어느 쪽에 있는지를 그 판의
    글에서 찾아 그 판의 점검 쪽과 견준다. 정규화하면 빈 글인 문장은 짝짓지 않고 찾지 않는다(base 에만 → undetermined,
    target 에만 → new).
pairs 의 차례: 짝 있는 것(remaining·level_changed)을 base itemIndex 차례로 → base 에만 있는 것을 base itemIndex
    차례로 → target 에만 있는 것을 target itemIndex 차례로.
열린 물음: `versionLabel` 을 어떻게 짓는가(아래 칸).
엑셀 「앞 판 비교」 시트: `pairs` 한 줄에 한 줄 —
    결과, 앞 문장·등급, 이번 문장·등급, 앞 파트, 이번 파트, 앞 쪽, 이번 쪽.

이 파일은 등록 길(apps.py 의 ready)에서 들이지 않는다.
"""

from collections.abc import Mapping
from typing import Final, Literal, TypedDict

from pydantic import TypeAdapter, with_config

from esgapi.greenwash.contracts.shapes import FORBID, Count, Level, Page

SHAPE: Final = "greenwash.compare@1"

GreenwashCompareOutcome = Literal[
    "resolved_deleted",
    "resolved_not_flagged",
    "resolved_undetermined",
    "remaining",
    "level_changed",
    "new",
    "out_of_scope",
]
"""짝 하나의 분류. 뜻은 이 파일 머리말의 표."""


@with_config(FORBID)
class GreenwashCompareSide(TypedDict):
    """견준 한 판(문서)과 그 대표 실행."""

    documentId: int
    """판(올린 문서)의 id."""
    runId: int
    """이 판의 대표 실행 id. 확정본이 있으면 그것, 없으면 마지막 실행."""
    versionLabel: str
    """화면에 보일 판 이름(예: 「v2」). 서버가 짓는다(문서의 reportYear·판 차례에서). 짓는 법은 열린 물음이다."""
    unconfirmed: bool
    """대표 실행이 확정본이 아니면 true(마지막 실행을 대신 썼다). 미확정이면 모든 문장을 견준다."""


@with_config(FORBID)
class GreenwashItemRef(TypedDict):
    """한 판의 결과(greenwash.result@1)의 문장 하나를 가리킨다. 열쇠는 (그 판의 runId, itemIndex).

    `position`(쪽 위 자리)은 싣지 않는다: 화면은 하이라이트를 그릴 때 그 실행의 결과를 따로 받아 itemIndex 로 찾는다.
    sentence·level·parts·page 는 그 결과 항목의 값을 그대로 옮긴 것이다(목록과 엑셀을 결과 없이 그리기 위해).
    """

    itemIndex: Count
    """그 실행의 결과 items 의 차례(0부터)."""
    sentence: str
    """그 항목의 sentence."""
    level: Level
    """그 항목의 level."""
    parts: list[str]
    """그 항목의 parts."""
    page: Page
    """그 항목의 page(1부터)."""


@with_config(FORBID)
class GreenwashComparePair(TypedDict):
    """짝 하나. 분류마다 base·target 의 있음은 머리말의 표대로다(꼴은 둘 다 null 을 받지만 그런 짝은 없다)."""

    outcome: GreenwashCompareOutcome
    """분류."""
    base: GreenwashItemRef | None
    """base 판의 문장. 없으면 null."""
    target: GreenwashItemRef | None
    """target 판의 문장. 없으면 null."""


@with_config(FORBID)
class GreenwashCompareCounts(TypedDict):
    """분류별 짝의 수. 일곱 키가 늘 있다(0 포함). pairs 를 다시 센 값이다."""

    resolved_deleted: Count
    resolved_not_flagged: Count
    resolved_undetermined: Count
    remaining: Count
    level_changed: Count
    new: Count
    out_of_scope: Count


@with_config(FORBID)
class GreenwashCompareResult(TypedDict):
    """greenwash.compare@1 — 두 판의 비교. schemaVersion 이 첫 키다."""

    schemaVersion: Literal["greenwash.compare@1"]
    base: GreenwashCompareSide
    """앞 판."""
    target: GreenwashCompareSide
    """이번 판."""
    pairs: list[GreenwashComparePair]
    """짝 목록. 차례는 수정본 밴드가 정한다(엑셀 시트의 줄 차례와 같다)."""
    counts: GreenwashCompareCounts
    """분류별 수."""


COMPARE_SHAPES: Final[Mapping[str, TypeAdapter[GreenwashCompareResult]]] = {SHAPE: TypeAdapter(GreenwashCompareResult)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
