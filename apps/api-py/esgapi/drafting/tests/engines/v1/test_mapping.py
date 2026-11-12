# pyright: reportUnknownVariableType=false, reportUnknownArgumentType=false
"""S2 답 → 쪽↔잎(engines/v1/mapping.py — RP1 §3 S4). 순수 층."""

from esgapi.drafting.engines.v1 import mapping


def test_unknown_keys_pages_out_of_batch_and_duplicates() -> None:
    answer = {
        "pages": [
            {"page": 2, "keys": ["a", "a", "zz", "b"]},
            {"page": 9, "keys": ["a"]},
            {"page": 3, "keys": []},
        ]
    }
    found, warnings = mapping.map_batch(answer, batch_pages=[2, 3], leaves=["a", "b"])
    assert found == {2: ["a", "b"]}  # 빈 keys 쪽은 열쇠가 없다
    assert [(w["code"], w["page"]) for w in warnings] == [("unknown_key", 2), ("page_out_of_batch", None)]
    assert mapping.leaf_pages({3: ["b"], 2: ["a", "b"]}, ["a", "b", "c"]) == {"a": [2], "b": [2, 3], "c": []}


def test_an_empty_answer_maps_nothing() -> None:
    assert mapping.map_batch({"pages": []}, batch_pages=[1], leaves=["a"]) == ({}, [])


def test_warning_pages_are_at_least_one_or_none() -> None:
    assert mapping.warning("x", "m", page=0)["page"] is None
    assert mapping.warning("x", "m", page=-3)["page"] is None
    assert mapping.warning("x", "m", page=1)["page"] == 1
