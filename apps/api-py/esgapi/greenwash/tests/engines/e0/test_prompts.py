"""노트북 프롬프트 넷(engines/e0/prompts.py): 종류 넷의 id(core.llm 템플릿 `greenwash/<종류>@1`)와 글 안의 `{` 수.

공급사·키 0 — 글만 본다.
"""

from esgapi.greenwash.engines.e0.ports import prompt_kind
from esgapi.greenwash.engines.e0.prompts import PROMPT_VERSION, default_prompts
from esgapi.greenwash.flows.colab_e0 import PROMPT_IDS


def test_the_four_kinds_map_to_four_prompt_files() -> None:
    pack = default_prompts(PROMPT_VERSION)
    texts = {
        "detect": pack.detect_system_prompt,
        "eval": pack.eval_system_prompt,
        "repair": pack.repair_fix_prompt,
        "low_only": pack.low_only_prompt,
    }
    assert {prompt_kind(text, pack) for text in texts.values()} == set(PROMPT_IDS)
    assert PROMPT_IDS == {
        "detect": "greenwash/detect@1",
        "eval": "greenwash/eval@1",
        "repair": "greenwash/repair@1",
        "low_only": "greenwash/low-only@1",
    }
    # 노트북 글의 값에는 `{` 가 하나씩 있다(소스의 `{{` 는 f-string 이스케이프). 쪽 글(user)에는 무엇이든 들 수 있어
    # 글은 템플릿이 아니라 변수로 넘긴다 — 넣은 값은 다시 훑지 않는다(위 렌더 테스트).
    assert [text.count("{") for text in texts.values()] == [1, 1, 1, 1]
