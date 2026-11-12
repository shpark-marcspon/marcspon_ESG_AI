"""목차 받기·sha·잎 셈·잎 지문·차이(contracts/wire.py — 밴드 RP1 §3 S1, RP2c B3): 트리 규칙의 갈래마다 한 문장으로
거절하고, 정규형은 title 만
strip 하며, sha256 은 손셈(정규 JSON 글자의 sha256)과 같다. 순수 층."""

import copy
import hashlib
from typing import Any

import pytest

from esgapi.drafting.contracts import wire


def node(key: str, parent: str | None, depth: int, title: str = "제목", requirement: str = "") -> dict[str, Any]:
    return {"key": key, "parentKey": parent, "depth": depth, "title": title, "requirement": requirement}


def outline(*nodes: dict[str, Any]) -> dict[str, Any]:
    return {"nodes": list(nodes)}


DEEP = (node("a", None, 1), node("b", "a", 2), node("c", "b", 3), node("d", "c", 4))
SAMPLE = outline(node("a", None, 1, " 환경 "), node("a-1", "a", 2, "기후", "배출량"), node("b", None, 1, "사회"))


def rejected(received: object, needle: str) -> None:
    with pytest.raises(wire.OutlineRejected) as caught:
        wire.accept_outline(received)
    assert needle in str(caught.value)


def test_a_good_outline_is_accepted_with_titles_stripped_only() -> None:
    before = copy.deepcopy(SAMPLE)
    accepted = wire.accept_outline(SAMPLE)
    assert before == SAMPLE  # 받은 dict 를 고치지 않는다
    assert [n["title"] for n in accepted["nodes"]] == ["환경", "기후", "사회"]
    assert accepted["nodes"][1]["requirement"] == "배출량"
    assert wire.leaf_keys(accepted["nodes"]) == ("a-1", "b")
    assert wire.title_paths(accepted["nodes"])["a-1"] == ("환경", "기후")


def test_the_sha256_is_the_hand_computed_one() -> None:
    small = outline(node("a", None, 1, "가"))
    text = '{"nodes":[{"depth":1,"key":"a","parentKey":null,"requirement":"","title":"가"}]}'
    assert wire.outline_sha256(small) == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert wire.outline_sha256(wire.accept_outline(SAMPLE)) != wire.outline_sha256(SAMPLE)  # strip 뒤가 정규형


@pytest.mark.parametrize(
    ("received", "needle"),
    [
        ({"nodes": []}, "1~300"),
        ({"nodes": [node("a", None, 1)], "extra": 1}, "꼴이 아니다"),
        ({"nodes": [{**node("a", None, 1), "id": 3}]}, "꼴이 아니다"),
        ({"nodes": [{**node("a", None, 1), "depth": "1"}]}, "꼴이 아니다"),
        (outline(node("A", None, 1)), "key 가 꼴"),
        (outline(node("-a", None, 1)), "key 가 꼴"),
        (outline(node("a" * 41, None, 1)), "key 가 꼴"),
        (outline(node("a", None, 1), node("a", None, 1)), "겹친다"),
        (outline(node("a", None, 2)), "depth 가 1"),
        (outline(node("b", "a", 2), node("a", None, 1)), "첫 마디"),
        (outline(node("a", None, 1), node("c", "b", 2)), "앞에 없다"),
        (outline(node("a", None, 1), node("b", "a", 3)), "부모 depth + 1"),
        (outline(*DEEP, node("e", "d", 5)), "1~4"),
        (outline(node("a", None, 1, "   ")), "제목"),
        (outline(node("a", None, 1, "가" * 201)), "제목"),
        (outline(node("a", None, 1, requirement="가" * 2001)), "요구 내용"),
    ],
)
def test_each_tree_rule_refuses_with_one_sentence(received: object, needle: str) -> None:
    rejected(received, needle)


def test_the_limits_at_the_edge() -> None:
    wire.accept_outline(outline(node("a", None, 1, "가" * 200, "나" * 2000)))
    leaves_150 = outline(*(node(f"k{i}", None, 1) for i in range(150)))
    assert len(wire.leaf_keys(wire.accept_outline(leaves_150)["nodes"])) == 150
    rejected(outline(*(node(f"k{i}", None, 1) for i in range(151))), "잎")
    # 마디 300(잎 150 + 부모 150) 은 받고 301 은 거절
    pairs = [n for i in range(150) for n in (node(f"p{i}", None, 1), node(f"c{i}", f"p{i}", 2))]
    assert len(wire.accept_outline(outline(*pairs))["nodes"]) == 300
    rejected(outline(*pairs, node("x", None, 1)), "1~300")


def test_the_error_code_of_the_document_route() -> None:
    assert wire.DOCUMENT_NO_TEXT_LAYER == "DOCUMENT_NO_TEXT_LAYER"


# ── RP2c B3: 잎 지문·목차 차이 ──

BASE = (
    node("env", None, 1, "환경"),
    node("ghg", "env", 2, "온실가스", "배출량"),
    node("energy", "env", 2, "에너지", "사용량"),
    node("safety", None, 1, "안전", "재해율"),
)


def test_b3_the_leaf_digest_is_the_hand_computed_one() -> None:
    text = '[["환경","온실가스"],"배출량"]'
    assert wire.leaf_digests(BASE)["ghg"] == hashlib.sha256(text.encode("utf-8")).hexdigest()
    assert list(wire.leaf_digests(BASE)) == ["ghg", "energy", "safety"]


def changed(*nodes: dict[str, Any]) -> tuple[dict[str, str], tuple[str, ...]]:
    found, removed = wire.outline_changes(BASE, nodes)
    return dict(found), removed


def test_b3_the_same_outline_is_all_same() -> None:
    assert changed(*copy.deepcopy(BASE)) == ({"ghg": "same", "energy": "same", "safety": "same"}, ())


def test_b3_an_ancestor_title_changes_every_leaf_under_it() -> None:
    nodes = copy.deepcopy(BASE)
    nodes[0]["title"] = "환경 경영"
    assert changed(*nodes) == ({"ghg": "changed", "energy": "changed", "safety": "same"}, ())


def test_b3_a_requirement_change_is_changed() -> None:
    nodes = copy.deepcopy(BASE)
    nodes[2]["requirement"] = "사용량과 절감"
    assert changed(*nodes)[0]["energy"] == "changed"


def test_b3_only_the_sibling_order_changes_nothing() -> None:
    nodes = copy.deepcopy(BASE)
    assert changed(nodes[0], nodes[2], nodes[1], nodes[3]) == (
        {"energy": "same", "ghg": "same", "safety": "same"},
        (),
    )


def test_b3_a_renamed_key_is_removed_and_added() -> None:
    nodes = copy.deepcopy(BASE)
    nodes[1]["key"] = "ghg-2"
    assert changed(*nodes) == ({"ghg-2": "added", "energy": "same", "safety": "same"}, ("ghg",))


def test_b3_a_leaf_that_became_a_branch_is_removed_and_its_child_added() -> None:
    nodes = [*copy.deepcopy(BASE), node("safety-1", "safety", 2, "산업재해", "재해율")]
    assert changed(*nodes) == ({"ghg": "same", "energy": "same", "safety-1": "added"}, ("safety",))
