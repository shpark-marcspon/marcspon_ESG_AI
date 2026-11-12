"""실행의 파일을 저장소의 어느 키에 두는가. 키는 서버가 짓는다(사용자가 고른 글자는 파일 이름 한 마디뿐이다).

    runs/<회사 id>/<실행 id>/out/<이름>              흐름의 출력 파일(run_files.step NULL)
    runs/<회사 id>/<실행 id>/steps/<단계>/<이름>     단계의 산출 파일(run_files.step = 단계 이름)

문서의 키(core/calc/documents.py — companies/…)와 접두가 다르다. 단계 이름은 흐름 레지스트리의 꼴([a-z][a-z0-9_]*)이라
「out」과 「steps」의 마디가 겹치지 않는다.
★ 키에 시도 번호를 넣지 않는다: 같은 파일을 다시 쓰면(시도가 바뀌어 다시 돈 단계·출력) 같은 키를 덮어쓴다. 행은 쓰기가
  끝난 뒤 한 번 적히고(run_files 의 UNIQUE (run, step, name)·storage_key) 지우지 않는다. 저장소 쓰기 뒤 행 쓰기 전에
  죽으면 키 하나가 행 없이 남는다(고아 — 다음 시도가 같은 키를 덮어쓰므로 늘지 않는다).
"""

import re
from typing import Final

# runs/models.py 의 RUN_FILE_NAME 과 같아야 한다(테스트가 견준다. calc 는 모델을 import 하지 못한다 — 계약 다).
FILE_NAME: Final = re.compile(r"^[A-Za-z0-9._-]{1,100}$")
STEP_NAME: Final = re.compile(r"^[a-z][a-z0-9_]*$")


def file_key(*, company_id: int, run_id: int, step: str | None, name: str) -> str:
    """파일 하나의 키. 이름·단계의 꼴이 틀리면 ValueError(흐름이 낸 이름이 표의 CHECK 를 지나지 못한다)."""
    if FILE_NAME.fullmatch(name) is None or name in {".", ".."}:
        raise ValueError(f"실행의 파일 이름 꼴이 틀렸다: {name!r}")
    if company_id <= 0 or run_id <= 0:
        raise ValueError("회사·실행 id 는 양의 정수다")
    if step is None:
        return f"runs/{company_id}/{run_id}/out/{name}"
    if STEP_NAME.fullmatch(step) is None:
        raise ValueError(f"단계 이름 꼴이 틀렸다: {step!r}")
    return f"runs/{company_id}/{run_id}/steps/{step}/{name}"
