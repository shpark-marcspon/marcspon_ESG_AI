"""패키지에 실린 기준정보 표(esgapi/inventory/data/*.json)를 읽는다. 파일을 읽는 것은 여기뿐이다(calc 는 값만 받는다).

실린 것: 단위 환산(정의값), GWP 세트 둘, 표본 계수 셋. 한국 지침의 계수 전량은 여기 없다(reference 모듈의 일이다).
"""

import json
from functools import cache
from importlib import resources

from esgapi.inventory.engines.scope12.engine_1.tables import TablesInvalid, merge_tables, validate_tables
from esgapi.inventory.engines.scope12.engine_1.types import ReferenceTables

# 이어 붙이는 순서. esg-lab 의 테스트 준비물(ts/ghg-calc/test/fixtures.ts 의 loadTables)과 같다.
DATA_FILES = ("unit-conversions.json", "gwp-sets.json", "factors.kr-ets-sample.json")


def read_data(name: str) -> dict[str, object]:
    """자료 파일 하나를 JSON 그대로 읽는다(검사 전)."""
    text = resources.files("esgapi.inventory").joinpath("data", name).read_text(encoding="utf-8")
    loaded: dict[str, object] = json.loads(text)
    return loaded


@cache
def default_tables() -> ReferenceTables:
    """요청이 표를 싣지 않았을 때 쓰는 표. 프로세스에서 한 번 읽는다(불변 dataclass 라 같이 써도 된다)."""
    validated = validate_tables(merge_tables(*(read_data(name) for name in DATA_FILES)))
    if isinstance(validated, TablesInvalid):
        problems = "; ".join(f"{p.where}: {p.problem}" for p in validated.problems)
        raise RuntimeError(f"패키지에 실린 기준정보 표가 검사를 통과하지 못했다: {problems}")
    return validated.tables
