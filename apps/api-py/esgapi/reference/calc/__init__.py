"""계수 조립 규칙(한국 배출권거래제 지침). 순수 모듈: Django·DB·파일·시계를 모른다(`.importlinter` 계약 다).

원본은 esg-lab 의 `ts/factor-assembly/src/domain/` 이다. 동작을 옮겼고 파일을 베끼지 않았다.

    types.py        조립이 받는 값(계수 낱줄, 대응표)과 내놓는 값(성공 / 실패 갈래)
    value_raw.py    낱줄의 `value_raw` 글자 → 엔진이 받는 십진 문자열
    policy.py       어느 산정등급을 쓰는가
    sector.py       사업장의 업종 → CH4·N2O 계수의 부문
    assemble.py     고정연소 계수 한 건
    electricity.py  구매 전력 계수 한 건
    parse.py        대응표 JSON → `AssemblyMapping`

★ 수치는 여기 없다. 값은 전부 낱줄의 `value_raw` 에서 온다. 여기 적힌 글자는 지침의 자리(조문 위치)와 표기 규칙이다.
★ 조립 결과의 `factor` 는 계산 엔진(`inventory.engines`)의 `CombustionFactor`·`PurchasedEnergyFactor` 와 같은
  JSON 꼴의 dict 다(camelCase). 엔진을 import 하지 않는다: 두 모듈은 이 JSON 꼴로만 만난다.
"""

from esgapi.reference.calc.assemble import SOURCE_IDS, assemble_combustion_factor, national_calorific_fuels
from esgapi.reference.calc.electricity import (
    GIR_EDITIONS,
    TABLE69,
    assemble_purchased_electricity_factor,
    electricity_options,
)
from esgapi.reference.calc.parse import MappingShapeError, mapping_from_json
from esgapi.reference.calc.policy import RULES, resolve_tiers
from esgapi.reference.calc.sector import resolve_sector
from esgapi.reference.calc.types import (
    FAILURE_KINDS,
    Assembled,
    AssemblyMapping,
    AssemblyResult,
    FactorRecord,
    Failed,
    Failure,
    FailureKind,
    Ok,
    SourceRef,
)
from esgapi.reference.calc.value_raw import read_value_raw

__all__ = [
    "FAILURE_KINDS",
    "GIR_EDITIONS",
    "RULES",
    "SOURCE_IDS",
    "TABLE69",
    "Assembled",
    "AssemblyMapping",
    "AssemblyResult",
    "FactorRecord",
    "Failed",
    "Failure",
    "FailureKind",
    "MappingShapeError",
    "Ok",
    "SourceRef",
    "assemble_combustion_factor",
    "assemble_purchased_electricity_factor",
    "electricity_options",
    "mapping_from_json",
    "national_calorific_fuels",
    "read_value_raw",
    "resolve_sector",
    "resolve_tiers",
]
