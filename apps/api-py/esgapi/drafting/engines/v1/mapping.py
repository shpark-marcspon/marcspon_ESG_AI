"""S2 답 `{pages: [{page, keys}]}` → 쪽 → 잎 key, 그리고 잎 → 쪽 역표(처분 ⑩).

모르는 key·잎 아닌 key 는 버리고 unknown_key, 묶음 밖 쪽은 버리고 page_out_of_batch. 같은 쪽·같은 key 가 겹치면 하나로.
경고는 결과 꼴의 warning dict 다(code·message·key·page — page 는 늘 1 이상이거나 None).
"""

from collections.abc import Iterable, Mapping, Sequence
from typing import Any

Warning = dict[str, Any]


def warning(code: str, message: str, *, key: str | None = None, page: int | None = None) -> Warning:
    return {"code": code, "message": message, "key": key, "page": page if page is None or page >= 1 else None}


def map_batch(
    answer: Mapping[str, Any], *, batch_pages: Iterable[int], leaves: Iterable[str]
) -> tuple[dict[int, list[str]], list[Warning]]:
    inside, known = set(batch_pages), set(leaves)
    found: dict[int, list[str]] = {}
    warnings: list[Warning] = []
    for item in answer.get("pages", []):
        page = item.get("page")
        if not isinstance(page, int) or page not in inside:
            warnings.append(warning("page_out_of_batch", "모델이 이 묶음에 없는 쪽을 답했다(버림)."))
            continue
        for key in item.get("keys", []):
            if key not in known:
                warnings.append(warning("unknown_key", "모델이 목차 잎이 아닌 key 를 답했다(버림).", page=page))
            elif key not in found.setdefault(page, []):
                found[page].append(key)
    return found, warnings


def leaf_pages(page_keys: Mapping[int, Sequence[str]], leaves: Sequence[str]) -> dict[str, list[int]]:
    """잎 → 그 잎을 단 쪽(쪽 차례). 목차 잎 차례 그대로 모든 잎이 열쇠다."""
    found: dict[str, list[int]] = {key: [] for key in leaves}
    for page in sorted(page_keys):
        for key in page_keys[page]:
            if key in found and page not in found[key]:
                found[key].append(page)
    return found
