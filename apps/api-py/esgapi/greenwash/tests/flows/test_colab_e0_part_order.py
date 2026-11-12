"""결과의 파트 차례(밴드 G1b): 실행기가 이어 돌 때 extract 의 data 는 jsonb 를 거쳐 열쇠 차례가 바뀌어 온다. assemble 은
section_pages 를 노트북 차례(engines/e0/parts.build_section_pages 의 열쇠 차례)로 다시 지어 parts·counts 가 같다.
순수 층. 글은 표본(synthetic)이다.
"""

from typing import Any, cast

from esgapi.core.flows.types import StepOutput
from esgapi.greenwash.engines.e0.parts import build_section_pages
from esgapi.greenwash.flows import colab_e0 as colab
from esgapi.greenwash.tests.flows import support as s


def test_the_part_order_is_the_notebook_functions() -> None:
    assert tuple(build_section_pages("1", "2", "3", 5)[0]) == colab.PART_ORDER
    assert len(colab.PART_ORDER) == 3


def test_notebook_order_puts_the_known_parts_first_and_keeps_the_rest() -> None:
    a, b, c = colab.PART_ORDER
    assert list(colab.notebook_order({c: [3], "기타": [9], a: [1], b: [2]})) == [a, b, c, "기타"]
    assert colab.notebook_order({b: [2]}) == {b: [2]}


def test_a_result_from_reordered_extract_data_is_the_same() -> None:
    """jsonb 처럼 열쇠를 길이 차례로 늘어세운 extract 를 넣어도 결과가 바이트까지 같다."""
    flow_run = s.run(s.inputs(), s.adapters())
    whole = s.result_of(flow_run)
    carried = dict(flow_run.steps)
    ext = dict(carried["extract"].data)
    sections = cast("dict[str, Any]", ext["section_pages"])
    ext["section_pages"] = {k: sections[k] for k in sorted(sections, key=lambda k: (len(k.encode()), k))}
    assert list(ext["section_pages"]) != list(colab.PART_ORDER)  # 분모: 차례가 실제로 바뀌었다
    carried["extract"] = StepOutput(data=ext, files=carried["extract"].files)
    assert colab.assemble(s.inputs(), carried) == whole
