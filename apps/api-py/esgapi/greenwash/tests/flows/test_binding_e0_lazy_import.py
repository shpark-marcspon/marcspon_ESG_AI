"""끼움의 좌표 import 는 늦다(밴드 G1b-2b ① — 검증 처분 R1): 새 하위 프로세스에서 flows/binding_e0 만 import 하면
pypdfium2 가 sys.modules 에 없다(API 프로세스에 pdfium 을 올리지 않는다). 분모: 같은 프로세스에서 tools/coordinates 를
import 하면 올라온다. 순수 층(DB 없음).
"""

import subprocess
import sys

PROBE = """
import sys
import {module}
print("pypdfium2" in sys.modules)
"""


def loaded_after(module: str) -> bool:
    done = subprocess.run(
        [sys.executable, "-c", PROBE.format(module=module)], capture_output=True, text=True, check=True, timeout=60
    )
    return done.stdout.strip().splitlines()[-1] == "True"


def test_importing_the_binding_does_not_load_pdfium() -> None:
    assert loaded_after("esgapi.greenwash.flows.binding_e0") is False


def test_importing_the_coordinates_loads_pdfium() -> None:
    assert loaded_after("esgapi.greenwash.tools.coordinates") is True  # 분모: 시험이 헛돌지 않음
