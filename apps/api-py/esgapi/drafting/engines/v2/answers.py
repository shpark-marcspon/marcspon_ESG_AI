"""S3 답 `{bullets: [{text, sources: [{block, s}]}]}` 다듬기(v1 bullets.trim 의 꼴 — 처분 ⑨).

trim(answer, key)   글 strip·빈 글 버림·200자에서 자름 · 15 줄 넘으면 버리고 bullets_capped. 출처 중 꼴 어긋난 것
                    (글 아닌 block · bool·정수 아닌 s · 음수 s)은 버린다(s 는 null 이면 블록만 — 답 꼴 ⑨)
"""

from collections.abc import Mapping
from typing import Any, Final, cast

from esgapi.drafting.engines.v1.mapping import Warning, warning

BULLETS_MAX: Final = 15
BULLET_MAX_CHARS: Final = 200


def _source(item: object) -> dict[str, Any] | None:
    if not isinstance(item, Mapping):
        return None
    found = cast("Mapping[str, Any]", item)
    block, s = found.get("block"), found.get("s")
    if not isinstance(block, str) or not block:
        return None
    if s is not None and (isinstance(s, bool) or not isinstance(s, int) or s < 0):
        return None
    return {"block": block, "s": s}


def trim(answer: Mapping[str, Any], key: str) -> tuple[list[dict[str, Any]], list[Warning]]:
    kept: list[dict[str, Any]] = []
    for item in answer.get("bullets", []):
        text = str(item.get("text", "")).strip()[:BULLET_MAX_CHARS].strip()
        if text:
            sources = [found for found in map(_source, item.get("sources", [])) if found is not None]
            kept.append({"text": text, "sources": sources})
    if len(kept) > BULLETS_MAX:
        message = f"bullet 이 {BULLETS_MAX} 줄을 넘어 뒤를 버렸다."
        return kept[:BULLETS_MAX], [warning("bullets_capped", message, key=key)]
    return kept, []
