"""실행 옵션 꼴 drafting.options@2 — `POST /runs {module: "drafting", options}` 의 options(밴드 RP1 ①, @2 는 밴드 RP2c —
@1 을 갈음, @1 의 몸 {projectId} 는 그대로 지난다). TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은
tests/data/flow-shapes/options/drafting.options@2.schema.json.

칸은 projectId(필수)와 base(선택) 둘이다. 목차 판·문서는 옵션으로 받지 않는다 — 끼움(flows/binding_v2)이 만들 때 그
프로젝트의 지금 목차 판·지금 문서를 versions 에 박는다(큐 중에 목차를 고쳐도 만들 때의 판). 원고작성은 문서 없는
흐름이다(실행의 documentId 를 받지 않는다 — 주면 422). 비용 상한 칸도 없다(환경 DRAFTING_RUN_MAX_USD).
base 는 목차를 고친 뒤 이어 받을 앞 실행(같은 회사·프로젝트의 끝난 원고작성 실행)과 다시 만들 잎 key 들이다.
- openapi 에는 오르지 않는다(RunIn.options 는 dict[str, object] 그대로) — 프론트는 이 고정 파일을 읽는다.

**이 파일에 로직은 없다.** 받기(사람에게 보일 문장)는 끼움 flows/binding_v2.DraftingBinding.check_options 가 한다.
"""

from collections.abc import Mapping
from typing import Annotated, Final, NotRequired, TypedDict

from pydantic import Field, StrictInt, TypeAdapter, with_config

from esgapi.drafting.contracts.shapes import FORBID, KEY_PATTERN, LEAVES_MAX

SHAPE: Final = "drafting.options@2"


@with_config(FORBID)
class DraftingOptionsBase(TypedDict):
    """이어 받을 앞 실행과 다시 만들 잎."""

    runId: Annotated[StrictInt, Field(ge=1)]
    """앞 실행 id(같은 회사·같은 프로젝트의 끝난 원고작성 실행 — 아니면 만들기 409)."""
    rebuild: Annotated[list[Annotated[str, Field(pattern=KEY_PATTERN)]], Field(max_length=LEAVES_MAX)]
    """안 바뀌었어도 다시 만들 목차 잎 key(0~150, 겹침 없음 — 지금 목차의 잎이어야)."""


@with_config(FORBID)
class DraftingOptions(TypedDict):
    """drafting.options@2 — 원고작성 실행의 옵션."""

    projectId: Annotated[int, Field(ge=1)]
    """원고작성 프로젝트 id(같은 회사의 것 — 남의 회사 id 는 「없음」과 같다)."""
    base: NotRequired[DraftingOptionsBase]
    """목차를 고친 뒤 이어 받을 앞 실행. 없으면 처음부터 짓는다."""


OPTIONS_SHAPES: Final[Mapping[str, TypeAdapter[DraftingOptions]]] = {SHAPE: TypeAdapter(DraftingOptions)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
