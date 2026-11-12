"""두 벌인 낱말: 계약(contracts/shapes.py)의 Literal 24개가 엔진의 것과 값·차례까지 같은가(밴드 EN1 ④). 순수 층.

계약은 엔진을 import 하지 않으므로(.importlinter inventory-contracts-not-engines) 엔진의 Literal 을 다시 적었다.
흐름이 두 축을 잇는 자리라 이 시험도 tests/flows/ 에 둔다. 엔진의 낱말이 바뀌면 계약도 같이 바꾸고(결과 꼴이 바뀌면
새 판 @n), 그렇지 않으면 여기가 빨개진다.
"""

from typing import get_args

import pytest

from esgapi.inventory.contracts import shapes
from esgapi.inventory.engines.scope3.colab_157 import activity as colab_activity
from esgapi.inventory.engines.scope3.colab_157 import energy as colab_energy
from esgapi.inventory.engines.scope3.colab_157 import factor_book as colab_factor_book
from esgapi.inventory.engines.scope3.colab_157 import purchase as colab_purchase
from esgapi.inventory.engines.scope3.llm_first_1 import calc as s3_calc
from esgapi.inventory.engines.scope3.llm_first_1 import llm_steps, shortlister
from esgapi.inventory.engines.scope3.llm_first_1 import types as s3_types
from esgapi.inventory.engines.scope12.engine_1 import aggregate
from esgapi.inventory.engines.scope12.engine_1 import types as s12_types

PAIRS = [
    ("Gas", s12_types),
    ("FactorGas", s12_types),
    ("CalorificBasis", s12_types),
    ("FacilityUse", s12_types),
    ("FactorKind", s12_types),
    ("SourceType", s12_types),
    ("Scope", s12_types),
    ("GroupKey", aggregate),
    ("SupportedCategory", s3_types),
    ("Confidence", s3_types),
    ("Basis", s3_types),
    ("CandidateBasis", s3_types),
    ("FallbackReason", s3_types),
    ("LicenseStatus", s3_types),
    ("NumberField", s3_calc),
    ("FailureKind", llm_steps),
    ("ShortlistMethod", shortlister),
    ("ColabOrigin", colab_purchase),
    ("ColabStep", colab_purchase),
    ("ColabMissing", colab_purchase),
    ("ColabActivityKind", colab_activity),
    ("ColabActivityStep", colab_activity),
    ("FactorSheetHow", colab_factor_book),
    ("ColabEnergyKind", colab_energy),
]


@pytest.mark.parametrize(("name", "engine"), PAIRS, ids=[name for name, _ in PAIRS])
def test_contract_literal_matches_engine(name: str, engine: object) -> None:
    contract_values = get_args(getattr(shapes, name))
    assert contract_values  # 빈 튜플끼리 같음으로 지나가지 않게
    assert contract_values == get_args(getattr(engine, name))
