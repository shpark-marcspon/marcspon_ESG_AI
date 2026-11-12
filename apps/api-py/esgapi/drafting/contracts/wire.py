"""목차 받기·sha·잎 셈, 그리고 경로의 오류 code(밴드 RP1 ① — C0 계약). 엔진을 import 하지 않는다(dict 만 — 축 시험).

    accept_outline(received)      drafting.outline@1 꼴 + 트리 규칙 → 정규형(title strip). 아니면 OutlineRejected
    outline_sha256(outline)       정규형의 sha256(json.dumps sort_keys·ensure_ascii False·쉼표·쌍점 붙임)
    leaf_keys(nodes)              잎(자식 없는 마디)의 key — 목록 차례
    title_paths(nodes)            key → 대 → 그 마디 제목 경로
    leaf_digests(nodes)           잎 key → 잎 내용 sha256(제목 경로 + 요구 내용 — 밴드 RP2c, 처분 ④)
    outline_changes(base, nodes)  앞 목차 → 지금 목차의 잎 차이(지금 잎마다 same·changed·added, 지운 잎 key)

트리 규칙(발주서 §2-1): key `^[a-z0-9][a-z0-9-]{0,39}$`·겹침 0 · 첫 마디 depth 1·parentKey null · 부모가 앞에 ·
depth = 부모 + 1(1~4) · 마디 1~300·잎 1~150 · title strip 1~200 · requirement ≤ 2,000.
"""

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from typing import Any, Final, Literal, cast

from pydantic import ValidationError

from esgapi.drafting.contracts.shapes import (
    DEPTH_MAX,
    KEY_PATTERN,
    LEAVES_MAX,
    NODES_MAX,
    OUTLINE_SHAPE,
    OUTLINE_SHAPES,
    REQUIREMENT_MAX_CHARS,
    TITLE_MAX_CHARS,
    DraftingOutline,
    DraftingOutlineNode,
)

DOCUMENT_NO_TEXT_LAYER: Final = "DOCUMENT_NO_TEXT_LAYER"
"""PUT /drafting/projects/{id}/document 의 422 — 문서에 글자 층이 없다(has_text false. null = 아직 모름은 받는다).
원고작성이 더하는 오류 code 는 이것 하나다(그 밖은 core 의 NOT_FOUND·VALIDATION_ERROR·RUN_NOT_DONE 그대로)."""

_KEY: Final = re.compile(KEY_PATTERN)


class OutlineRejected(ValueError):
    """목차가 꼴·트리 규칙에 맞지 않는다. str(e) 가 사람에게 보일 한 문장이다."""


def accept_outline(received: object) -> DraftingOutline:
    """drafting.outline@1 받기. 지나면 정규형(새 dict — title 은 앞뒤 공백을 뺌, 그 밖은 받은 값 그대로)."""
    try:
        OUTLINE_SHAPES[OUTLINE_SHAPE].validate_python(received, strict=True)
    except ValidationError as error:
        raise OutlineRejected("목차가 drafting.outline@1 꼴이 아니다(모르는 칸·빠진 칸·값의 타입).") from error
    nodes: Sequence[Mapping[str, Any]] = cast("Mapping[str, Any]", received)["nodes"]
    if not 1 <= len(nodes) <= NODES_MAX:
        raise OutlineRejected(f"목차 마디는 1~{NODES_MAX}개다(받은 수 {len(nodes)}).")
    depth_of: dict[str, int] = {}
    with_children: set[str] = set()
    accepted: list[DraftingOutlineNode] = []
    for index, node in enumerate(nodes, start=1):
        key, parent, depth = node["key"], node["parentKey"], node["depth"]
        if not _KEY.fullmatch(key):
            raise OutlineRejected(f"{index}번째 마디의 key 가 꼴(영 소문자·숫자·하이픈 1~40자)이 아니다.")
        if key in depth_of:
            raise OutlineRejected(f"{index}번째 마디의 key 「{key}」가 앞 마디와 겹친다.")
        if index == 1 and parent is not None:
            raise OutlineRejected("첫 마디는 depth 1·parentKey null 이어야 한다.")
        if parent is None:
            if depth != 1:
                raise OutlineRejected(f"{index}번째 마디는 부모가 없으니 depth 가 1 이어야 한다.")
        elif parent not in depth_of:
            raise OutlineRejected(f"{index}번째 마디의 부모 「{parent}」가 앞에 없다(부모가 먼저 온다).")
        elif depth != depth_of[parent] + 1:
            raise OutlineRejected(f"{index}번째 마디의 depth 는 부모 depth + 1 이어야 한다.")
        if not 1 <= depth <= DEPTH_MAX:
            raise OutlineRejected(f"{index}번째 마디의 depth 는 1~{DEPTH_MAX} 다.")
        title = node["title"].strip()
        if not 1 <= len(title) <= TITLE_MAX_CHARS:
            raise OutlineRejected(f"{index}번째 마디의 제목은 앞뒤 공백을 빼고 1~{TITLE_MAX_CHARS}자다.")
        if len(node["requirement"]) > REQUIREMENT_MAX_CHARS:
            raise OutlineRejected(f"{index}번째 마디의 요구 내용은 {REQUIREMENT_MAX_CHARS}자까지다.")
        depth_of[key] = depth
        if parent is not None:
            with_children.add(parent)
        accepted.append(
            {"key": key, "parentKey": parent, "depth": depth, "title": title, "requirement": node["requirement"]}
        )
    leaves = len(accepted) - len(with_children)
    if not 1 <= leaves <= LEAVES_MAX:
        raise OutlineRejected(f"목차 잎(자식 없는 마디)은 1~{LEAVES_MAX}개다(받은 수 {leaves}).")
    return {"nodes": accepted}


def outline_sha256(outline: Mapping[str, Any]) -> str:
    """정규형의 sha256(16진 64자). 같은 목차는 같은 값 — PUT 의 멱등·실행의 판 대조가 이것을 쓴다."""
    text = json.dumps(outline, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def leaf_keys(nodes: Sequence[Mapping[str, Any]]) -> tuple[str, ...]:
    """잎(자식 없는 마디)의 key, 목록 차례."""
    parents = {node["parentKey"] for node in nodes if node["parentKey"] is not None}
    return tuple(node["key"] for node in nodes if node["key"] not in parents)


def title_paths(nodes: Sequence[Mapping[str, Any]]) -> dict[str, tuple[str, ...]]:
    """key → 대 → 그 마디의 제목 경로(부모가 앞에 온다는 받기 규칙에 기댄다)."""
    paths: dict[str, tuple[str, ...]] = {}
    for node in nodes:
        parent = node["parentKey"]
        paths[node["key"]] = (*(() if parent is None else paths[parent]), node["title"])
    return paths


LeafChange = Literal["same", "changed", "added"]


def leaf_digests(nodes: Sequence[Mapping[str, Any]]) -> dict[str, str]:
    """잎 key → sha256(json.dumps([제목 경로, 요구 내용]) — ensure_ascii False·쉼표·쌍점 붙임), 잎 차례. 조상 제목이
    바뀌어도 바뀐다(S3 요청이 제목 경로를 싣는다). 형제 차례·잎 아닌 마디의 요구 내용은 들지 않는다."""
    paths = title_paths(nodes)
    requirement = {node["key"]: node["requirement"] for node in nodes}
    found: dict[str, str] = {}
    for key in leaf_keys(nodes):
        text = json.dumps([list(paths[key]), requirement[key]], ensure_ascii=False, separators=(",", ":"))
        found[key] = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return found


def outline_changes(
    base_nodes: Sequence[Mapping[str, Any]], nodes: Sequence[Mapping[str, Any]]
) -> tuple[dict[str, LeafChange], tuple[str, ...]]:
    """(지금 잎 key → same·changed·added — 지금 잎 차례, 지운 잎 key — 앞 목차 잎 차례). 잎이 가지가 되면 지움이다."""
    before, after = leaf_digests(base_nodes), leaf_digests(nodes)
    changes: dict[str, LeafChange] = {}
    for key, digest in after.items():
        changes[key] = "added" if key not in before else "same" if before[key] == digest else "changed"
    return changes, tuple(key for key in before if key not in after)
