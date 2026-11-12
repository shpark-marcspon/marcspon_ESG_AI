"""실행 옵션 꼴 materiality.options@1 — `POST /runs {module: "materiality", options}` 의 options(밴드 IR3a).
TypedDict(모르는 키 금지) → JSON 스키마. 고정 파일은 tests/data/flow-shapes/options/materiality.options@1.schema.json.

칸은 input(필수) 하나. input 은 입력 꼴 materiality.input@1(shapes.MaterialityInput)을 그대로 가져다 쓴다(두 번째 정본
0). 감싸 두는 것은 뒤에 칸(AI 설정 판 등 — IR4)이 붙어도 input@1 을 @2 로 올리지 않으려고다. 문서는 없다 — 중대성평가
IRO 는 문서 없는 흐름이다(ND1 — 실행의 documentId 를 받지 않는다).
- openapi 에는 오르지 않는다(RunIn.options 는 dict[str, object] 그대로) — 프론트는 이 고정 파일을 읽는다.
- 크기 상한은 256KiB 다(core.flows.binding.DOCUMENTLESS_OPTIONS_MAX_OCTETS — apps.py 가 등록 인자로 넘긴다. 다른 흐름의
  16KiB 가 아니다). 토픽·서브토픽 설명과 가치사슬이 한글(3바이트)이라 코랩 크기의 입력이 16KiB 근처에 닿는다.
- today 칸이 없다 — 「오늘」은 끼움이 실행 시각의 Asia/Seoul 날짜로 넣는다(flows/binding_155.today — 브라우저 시계를
  믿지 않는다). 비용 상한 칸·web_search 칸도 없다 — 비용 상한은 끼움의 코드 상수(flows/binding_155.RUN_MAX_COST_USD),
  웹 검색은 코랩대로 흐름이 정한다. 셋 다 주면 모르는 열쇠로 거절한다.

**이 파일에 로직은 없다.** 받기(사람에게 보일 문장)는 끼움 flows/binding_155.MaterialityBinding.check_options 가 한다.
"""

from collections.abc import Mapping
from typing import Final, TypedDict

from pydantic import TypeAdapter, with_config

from esgapi.materiality.contracts.shapes import FORBID, MaterialityInput

SHAPE: Final = "materiality.options@1"


@with_config(FORBID)
class MaterialityOptions(TypedDict):
    """materiality.options@1 — 중대성평가 IRO 실행의 옵션."""

    input: MaterialityInput
    """조사할 입력(materiality.input@1 — 받은 그대로 흐름에 넘긴다)."""


OPTIONS_SHAPES: Final[Mapping[str, TypeAdapter[MaterialityOptions]]] = {SHAPE: TypeAdapter(MaterialityOptions)}
"""꼴 id → 검사기. validate_python(값, strict=True) 로 검사하고 json_schema() 로 고정 파일을 뽑는다."""
