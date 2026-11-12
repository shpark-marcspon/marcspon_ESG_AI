# pyright: reportArgumentType=false
"""앞 실행 이어 받기의 계획(flows/reuse.py — 밴드 RP2c B4): 어긋난 까닭 넷과 그 차례, S2 다시 할 잎, 옮길 쪽, 옮길 잎의
갈래(rebuild·쪽 다름·앞 failed·앞 no_material), origin 사슬, 옮기는 경고 code 거름. 순수 층. 값은 지어낸 것이다."""

import copy
from typing import Any

import pytest

from esgapi.drafting.flows import reuse
from esgapi.drafting.tests.flows.support import OUTLINE, base_result

PAGES_SHA = "c" * 64
SETTINGS: dict[str, Any] = {
    "routes": {"map": "light-openai-41", "draft": "light-openai-41"},
    "promptIds": {"map": "drafting/map@1", "draft": "drafting/draft@2"},
}
EXTRACT: dict[str, Any] = {"artifactId": 41, "pagesSha256": PAGES_SHA}
LEAVES = ["ghg", "energy", "safety"]
DONE: dict[str, Any] = {
    "status": "done",
    "bullets": [
        {
            "text": "배출량 1,200 tCO2eq",
            "sources": [
                {"documentId": 30, "blockId": "p2-b1", "page": 2, "blockBox": [1.0, 2.0, 3.0, 4.0], "sentence": None}
            ],
            "unsupported": False,
        }
    ],
}


def result(**leaves: dict[str, Any]) -> dict[str, Any]:
    found = base_result(50, 11)
    found["basis"] = {
        "artifactId": 41,
        "parser": {"name": "docparse", "version": "0.1.0", "layout": 2},
        "epoch": 1,
        "pagesSha256": PAGES_SHA,
    }
    for leaf in found["leaves"]:
        leaf.update(leaves.get(leaf["key"], {}))
    return found


def base(found: dict[str, Any] | None = None, *, versions_same: bool = True) -> reuse.Base:
    return reuse.Base(
        run_id=50,
        outline_id=11,
        nodes=list(OUTLINE["nodes"]),
        versions_same=versions_same,
        result=found or result(),
    )


ALL_SAME = {"ghg": "same", "energy": "same", "safety": "same"}


# ── matched ──


def test_b4_matched_is_none_when_everything_is_the_same() -> None:
    assert reuse.matched(base(), EXTRACT, SETTINGS) is None


def test_b4_matched_reasons_in_their_order() -> None:
    rejected = result()
    rejected["status"] = {"status": "rejected", "code": "over_budget", "stage": "before_map", "message": "x"}
    rejected["settings"]["routes"]["map"] = "mock"
    assert reuse.matched(base(rejected, versions_same=False), {"artifactId": 9, "pagesSha256": None}, SETTINGS) == (
        "base_rejected"
    )
    other = {"artifactId": 9, "pagesSha256": PAGES_SHA}
    assert reuse.matched(base(versions_same=False), other, {}) == "versions"
    assert reuse.matched(base(), other, {}) == "document"
    assert reuse.matched(base(), {"artifactId": 41, "pagesSha256": "d" * 64}, SETTINGS) == "document"
    assert reuse.matched(base(), EXTRACT, {**SETTINGS, "routes": {"map": "mock", "draft": "mock"}}) == "settings"


@pytest.mark.parametrize("side", ["base", "now", "both"])
def test_b4_a_null_pages_sha_never_matches_even_null_with_null(side: str) -> None:
    """감독 9c 10-30: pagesSha256 null(too_large 행)은 null 끼리도 불일치 — reason document."""
    found = result()
    extract = dict(EXTRACT)
    if side in ("base", "both"):
        found["basis"]["pagesSha256"] = None
    if side in ("now", "both"):
        extract["pagesSha256"] = None
    assert reuse.matched(base(found), extract, SETTINGS) == "document"


def test_b4_a_null_basis_never_matches() -> None:
    found = result()
    found["basis"] = None
    assert reuse.matched(base(found), EXTRACT, SETTINGS) == "document"


# ── s2_keys · kept_pages ──


def test_b4_s2_keys_are_all_leaves_without_a_base_or_on_a_mismatch_or_failed_batches() -> None:
    changes = {**ALL_SAME, "ghg": "changed"}
    assert reuse.s2_keys(None, LEAVES, changes, (), None) == LEAVES
    assert reuse.s2_keys(base(), LEAVES, changes, (), "document") == LEAVES
    failed = result()
    failed["mapping"]["failedBatches"] = [
        {"firstPage": 1, "lastPage": 2, "failure": {"kind": "timeout", "message": "x"}}
    ]
    assert reuse.s2_keys(base(failed), LEAVES, changes, (), None) == LEAVES
    assert reuse.kept_pages(base(failed), changes, (), None) == {}


def test_b4_s2_keys_are_changed_added_and_rebuild_when_matched() -> None:
    changes = {"ghg": "changed", "energy": "same", "safety": "same", "new": "added"}
    assert reuse.s2_keys(base(), [*LEAVES, "new"], changes, {"safety"}, None) == ["ghg", "safety", "new"]
    assert reuse.s2_keys(base(), LEAVES, ALL_SAME, (), None) == []


def test_b4_kept_pages_are_the_base_pages_of_same_leaves_not_rebuilt() -> None:
    found = result(ghg={"pages": [2, 5]}, energy={"pages": [4]})
    changes = {**ALL_SAME, "safety": "changed"}
    assert reuse.kept_pages(base(found), changes, {"energy"}, None) == {"ghg": [2, 5]}
    assert reuse.kept_pages(base(found), changes, (), "versions") == {}
    assert reuse.kept_pages(None, changes, (), None) == {}


# ── reusable ──


def test_b4_reusable_moves_a_done_leaf_and_rewrites_only_the_document_id() -> None:
    found = result(ghg={"pages": [2], "outcome": copy.deepcopy(DONE)})
    moved = reuse.reusable(base(found), "ghg", [2], ALL_SAME, (), None, 31)
    assert moved is not None
    outcome, warnings, origin = moved
    expected = copy.deepcopy(DONE)
    expected["bullets"][0]["sources"][0]["documentId"] = 31
    assert outcome == expected and warnings == [] and origin == {"runId": 50, "outlineId": 11}
    assert found["leaves"][0]["outcome"] == DONE  # 앞 결과는 그대로


@pytest.mark.parametrize("case", ["rebuild", "pages", "failed", "no_material", "changed", "mismatch", "no_base"])
def test_b4_reusable_refuses(case: str) -> None:
    outcome: dict[str, Any] = copy.deepcopy(DONE)
    if case == "failed":
        outcome = {"status": "failed", "failure": {"kind": "timeout", "message": "x"}}
    elif case == "no_material":
        outcome = {"status": "no_material"}
    found = base(result(ghg={"pages": [2], "outcome": outcome}))
    rebuild = {"ghg"} if case == "rebuild" else set[str]()
    pages = [2, 3] if case == "pages" else [2]
    changes = {**ALL_SAME, "ghg": "changed"} if case == "changed" else ALL_SAME
    reason = "settings" if case == "mismatch" else None
    chosen = None if case == "no_base" else found
    assert reuse.reusable(chosen, "ghg", pages, changes, rebuild, reason, 31) is None


def test_b4_origin_follows_the_chain() -> None:
    found = result(ghg={"pages": [2], "outcome": copy.deepcopy(DONE), "reusedFrom": {"runId": 40, "outlineId": 9}})
    moved = reuse.reusable(base(found), "ghg", [2], ALL_SAME, (), None, 31)
    assert moved is not None and moved[2] == {"runId": 40, "outlineId": 9}


def test_b4_only_the_s3_warnings_of_that_leaf_move() -> None:
    found = result(ghg={"pages": [2], "outcome": copy.deepcopy(DONE)})

    def warn(code: str, key: str | None) -> dict[str, Any]:
        return {"code": code, "message": "x", "key": key, "page": None}

    moved_codes = sorted(reuse.MOVED_CODES)
    found["warnings"] = [
        *(warn(code, "ghg") for code in moved_codes),
        warn("unsupported_bullet", "energy"),
        warn("mapping_incomplete", "ghg"),
        warn("page_truncated", None),
        warn("base_not_reused", None),
    ]
    moved = reuse.reusable(base(found), "ghg", [2], ALL_SAME, (), None, 31)
    assert moved is not None
    assert [w["code"] for w in moved[1]] == moved_codes
    assert {
        "material_truncated",
        "source_not_given",
        "source_block_missing",
        "sentence_out_of_range",
        "unsupported_bullet",
        "number_not_in_source",
        "bullets_capped",
    } == reuse.MOVED_CODES
