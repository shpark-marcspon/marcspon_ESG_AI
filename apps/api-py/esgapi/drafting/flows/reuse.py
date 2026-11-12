"""앞 실행 이어 받기의 계획(밴드 RP2c, 결정 MARC-ENT-514 3번·512 — 순수: django 0, contracts 만). 「같으면 옮김, 다르면
처음부터」 — 열쇠가 어긋나면 섞지 않는다(전부 다시 + 경고 base_not_reused).

    matched(base, extract, settings)             어긋난 까닭(없으면 None). 차례: base_rejected(앞 결과가 거절로 끝남) →
                                                 versions(FACT_KEYS 뺀 판이 다름) → document(분해 artifactId·
                                                 pagesSha256 이 다름 — 둘 중 하나라도 null 이면 다름) → settings(경로·
                                                 프롬프트가 다름 — mock↔live 섞임 0)
    changes(base, nodes)                         contracts/wire.outline_changes(앞 목차 → 지금 목차)
    s2_keys(base, leaves, changes, rebuild, reason)   S2 목차 줄에 실을 잎. 어긋남·앞 failedBatches → 잎 전부 / 아니면
                                                 changed·added·rebuild
    kept_pages(base, changes, rebuild, reason)   S2 를 다시 하지 않는 잎 → 앞 결과의 쪽(same ∧ rebuild 아님)
    reusable(base, key, pages, changes, rebuild, reason, document_id)
                                                 same ∧ rebuild 아님 ∧ 쪽 같음 ∧ 앞 outcome done → 옮길 (outcome, 잎
                                                 경고,
                                                 origin). outcome 은 바이트 그대로이고 출처 documentId 만 이 실행의
                                                 문서로
                                                 (처분 ⑧ — 분해가 같으면 블록·상자가 같다)

origin = 그 잎을 실제로 지은 실행(앞 잎의 reusedFrom 이 있으면 그것 — 사슬, 없으면 앞 실행).
규칙을 바꾸면 끼움 versions 의 reuse 판(REUSE_VERSION)을 올린다.
"""

import copy
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast

from esgapi.drafting.contracts import wire
from esgapi.drafting.contracts.wire import LeafChange

REUSE_VERSION: Final = "drafting-reuse@1"
MOVED_CODES: Final = frozenset(
    {
        "material_truncated",
        "source_not_given",
        "source_block_missing",
        "sentence_out_of_range",
        "unsupported_bullet",
        "number_not_in_source",
        "bullets_capped",
    }
)
"""옮기는 잎 경고(S3 몫). 쪽·S2 몫(page_truncated·mapping_incomplete·unknown_key·page_out_of_batch)은 이 실행이 다시
낸다."""


@dataclass(frozen=True, slots=True, kw_only=True)
class Base:
    """이어 받을 앞 실행(끼움이 만들 때 대 보고 돌 때 다시 읽은 것)."""

    run_id: int
    outline_id: int
    nodes: Sequence[Mapping[str, Any]]
    """앞 실행이 읽은 목차 판의 마디."""
    versions_same: bool
    """두 실행의 versions 에서 FACT_KEYS(목차·문서 판)를 뺀 나머지가 같은가."""
    result: Mapping[str, Any]
    """앞 실행의 결과(drafting.bullets@3)."""


def matched(base: Base, extract: Mapping[str, Any], settings: Mapping[str, Any]) -> str | None:
    if base.result["status"]["status"] != "done":
        return "base_rejected"
    if not base.versions_same:
        return "versions"
    basis = cast("Mapping[str, Any] | None", base.result["basis"])
    if (
        basis is None
        or basis["pagesSha256"] is None
        or extract["pagesSha256"] is None
        or basis["artifactId"] != extract["artifactId"]
        or basis["pagesSha256"] != extract["pagesSha256"]
    ):
        return "document"
    if base.result["settings"] != settings:
        return "settings"
    return None


def changes(base: Base, nodes: Sequence[Mapping[str, Any]]) -> dict[str, LeafChange]:
    return wire.outline_changes(base.nodes, nodes)[0]


def _failed_batches(base: Base) -> bool:
    return bool(base.result["mapping"]["failedBatches"])


def _kept(key: str, changes: Mapping[str, LeafChange], rebuild: Collection[str]) -> bool:
    return changes.get(key) == "same" and key not in rebuild


def s2_keys(
    base: Base | None,
    leaves: Sequence[str],
    changes: Mapping[str, LeafChange],
    rebuild: Collection[str],
    reason: str | None,
) -> list[str]:
    if base is None or reason is not None or _failed_batches(base):
        return list(leaves)
    return [key for key in leaves if not _kept(key, changes, rebuild)]


def _base_leaves(base: Base) -> dict[str, Mapping[str, Any]]:
    return {leaf["key"]: leaf for leaf in cast("list[Mapping[str, Any]]", base.result["leaves"])}


def kept_pages(
    base: Base | None, changes: Mapping[str, LeafChange], rebuild: Collection[str], reason: str | None
) -> dict[str, list[int]]:
    if base is None or reason is not None or _failed_batches(base):
        return {}
    found = _base_leaves(base)
    return {key: list(found[key]["pages"]) for key in changes if _kept(key, changes, rebuild) and key in found}


def reusable(
    base: Base | None,
    key: str,
    pages: Sequence[int],
    changes: Mapping[str, LeafChange],
    rebuild: Collection[str],
    reason: str | None,
    document_id: int,
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, int]] | None:
    if base is None or reason is not None or not _kept(key, changes, rebuild):
        return None
    leaf = _base_leaves(base).get(key)
    if leaf is None or list(leaf["pages"]) != list(pages) or leaf["outcome"]["status"] != "done":
        return None
    outcome = cast("dict[str, Any]", copy.deepcopy(leaf["outcome"]))
    for bullet in outcome["bullets"]:
        for source in bullet["sources"]:
            source["documentId"] = document_id
    warnings = [
        dict(w)
        for w in cast("list[Mapping[str, Any]]", base.result["warnings"])
        if w["key"] == key and w["code"] in MOVED_CODES
    ]
    origin = leaf["reusedFrom"] or {"runId": base.run_id, "outlineId": base.outline_id}
    return outcome, warnings, dict(origin)
