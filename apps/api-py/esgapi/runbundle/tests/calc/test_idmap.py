"""지도의 순수 몫(runbundle/calc/idmap.py) — S3: 넣는 차례(앞 판 먼저·옛 id 오름), 열쇠 짓기(m2), aiSettingId 다시 쓰기,
지도 밖은 UnknownId. ★ 값은 전부 지어낸 것이다(synthetic).
"""

import uuid

import pytest

from esgapi.core.flows.carriers import IdMap, UnknownId
from esgapi.runbundle.calc.bundle import Refused
from esgapi.runbundle.calc.idmap import (
    RX1_NS,
    document_order,
    idempotency_key,
    launch_key,
    rewrite_versions,
    run_order,
)

BUNDLE = "0b9a7c3e-6f1d-4c2b-9a8e-1d2c3b4a5f60"
OTHER = "5d1c2b3a-4f5e-4a6b-8c7d-9e0f1a2b3c4d"


def test_runs_go_in_old_id_ascending() -> None:
    assert run_order([{"oldId": 9}, {"oldId": 3}, {"oldId": 5}]) == [3, 5, 9]


def test_documents_go_in_previous_first() -> None:
    rows = [
        {"oldId": 2, "previousOldId": 8},  # 앞 판이 더 큰 id 여도 먼저
        {"oldId": 8, "previousOldId": None},
        {"oldId": 5, "previousOldId": 4},  # 앞 판 4 는 묶음 밖 — 묶지 않음
        {"oldId": 1, "previousOldId": None},
    ]
    assert document_order(rows) == [1, 8, 2, 5]
    with pytest.raises(Refused):
        document_order([{"oldId": 1, "previousOldId": 2}, {"oldId": 2, "previousOldId": 1}])


def test_keys_are_derived_from_the_bundle() -> None:
    key = idempotency_key(BUNDLE, 7)
    assert key == str(uuid.uuid5(RX1_NS, f"{BUNDLE}:7")) and key != idempotency_key(OTHER, 7)
    assert idempotency_key(BUNDLE, 7) != idempotency_key(BUNDLE, 8)
    old = "11111111-1111-4111-8111-111111111111"
    assert launch_key(BUNDLE, old) == launch_key(BUNDLE, old) != launch_key(OTHER, old)  # 묶음 안 무리는 남고 둘은 갈림
    assert launch_key(BUNDLE, None) is None


def test_ai_setting_ids_follow_the_map() -> None:
    ids = IdMap(run={}, document={}, ai_setting={7: 70})
    assert rewrite_versions({"flow": "f", "aiSettingId": 7, "x": 1}, ids) == {"flow": "f", "aiSettingId": 70, "x": 1}
    assert rewrite_versions({"aiSettingId": None}, ids) == {"aiSettingId": None}
    assert rewrite_versions({"flow": "f"}, ids) == {"flow": "f"}
    with pytest.raises(UnknownId):
        rewrite_versions({"aiSettingId": 8}, ids)
    with pytest.raises(Refused):
        rewrite_versions({"aiSettingId": "7"}, ids)
