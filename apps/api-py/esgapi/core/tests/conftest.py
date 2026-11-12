"""core 의 테스트가 같이 쓰는 고정물.

소켓을 막는 고정물(blocked_network)과 NetworkBlockedError 는 뿌리 conftest(apps/api-py/conftest.py)로 올라갔다
(밴드 PY3b. 이제 core 만이 아니라 순수 층 전부에 걸린다). 이 폴더의 테스트는 그것을 인자 이름으로 그대로 받는다.
"""

from pathlib import Path

import pytest


@pytest.fixture
def prompt_root(tmp_path: Path) -> Path:
    """테스트용 템플릿 넷(t/plain@1·@2, t/cached-short@1, t/cached-long@1)이 든 폴더."""
    from esgapi.core.tests.llm_support import write_prompts

    return write_prompts(tmp_path / "prompts")
