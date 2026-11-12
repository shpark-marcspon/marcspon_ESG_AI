"""수정본 짝 계산 — 한 문서의 두 판(base·target)의 실행 결과와 쪽 글 → greenwash.compare@1(밴드 GR1, MARC-TICK-106).

순수 함수 `compare_runs` 하나다. DB·경로·실행 틀·AI·pdfium 없음 — 들이는 것은 꼴(shapes·compare_shapes)과 pdfium 없는
정규화(textnorm)뿐이다. 대표 실행 고르기·판 이름 짓기·검토(review@1) 읽기는 부르는 쪽(G1b) 몫이다.

규칙(뜻의 정본은 compare_shapes 의 머리말):
    견주는 문장  확정본(adopted 있음)은 adopted 에 든 item_index 만, 미확정은 items 전부. item_index 차례.
    짝 열쇠      (2단 정규화한 문장, parts). 쪽·등급은 열쇠 밖. 같은 열쇠 여럿은 양쪽을 item_index 차례로 하나씩.
                 정규화한 문장이 빈 글이면 열쇠가 없다(짝짓지 않고 한쪽 문장. 다른 판 글에서도 찾지 않는다).
    짝 있음      level 이 같으면 remaining, 다르면 level_changed.
    base 에만    target 쪽 글에서 찾아, 찾은 쪽 가운데 하나라도 target 점검 쪽이면 resolved_not_flagged, 모두 밖이면
                 out_of_scope. 못 찾으면 base 쪽 글에서 찾아 있으면 resolved_deleted, 없으면 resolved_undetermined.
    target 에만  base 쪽 글에서 찾아, 찾았는데 모두 base 점검 쪽 밖이면 out_of_scope, 그 밖은 new.
    「점검 쪽」 = result@1 의 pages. 쪽 번호를 판끼리 견주지 않는다(판마다 쪽이 밀린다).
    pairs 차례   ① 짝 있는 것(base 차례) ② base 에만(base 차례) ③ target 에만(target 차례).
쪽 글은 쪽마다 한 번만 정규화한다. 입력을 바꾸지 않는다. 출력은 돌려주기 전에 compare@1 로 strict 검사한다.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, cast, get_args

from pydantic import ValidationError

from esgapi.greenwash.contracts import shapes
from esgapi.greenwash.contracts.compare_shapes import (
    COMPARE_SHAPES,
    SHAPE,
    GreenwashCompareCounts,
    GreenwashCompareOutcome,
    GreenwashComparePair,
    GreenwashCompareResult,
    GreenwashCompareSide,
    GreenwashItemRef,
)
from esgapi.greenwash.tools.textnorm import norm_str, strip_tail

TIER: Final = 2
"""정규화 단(pdfium_locate 의 2단: NFKC → 공백·보이지 않는 글자 제거 → casefold → 글자·숫자만)."""

OUTCOMES: Final = cast("tuple[GreenwashCompareOutcome, ...]", get_args(GreenwashCompareOutcome))

Key = tuple[str, tuple[str, ...]]


@dataclass(frozen=True)
class RunSide:
    """견줄 한 판의 대표 실행."""

    side: GreenwashCompareSide
    """출력의 base·target 칸 그대로(documentId·runId·versionLabel·unconfirmed). 부르는 쪽이 짓는다."""
    result: Mapping[str, Any]
    """그 실행의 greenwash.result@1(dry-run 아님)."""
    page_texts: Sequence[str]
    """그 실행의 extract 단계 산출 data["pages"] 그대로(0번 = 1쪽)."""
    adopted: frozenset[int] | None
    """확정본이면 review@1 에서 adopted 인 item_index 의 집합, 미확정이면 None."""


@dataclass(frozen=True)
class _Prepared:
    items: list[tuple[int, Mapping[str, Any]]]
    """견주는 문장(item_index, 항목), item_index 차례."""
    norm_pages: list[str]
    """쪽 글을 정규화한 것(0번 = 1쪽)."""
    scanned: frozenset[int]
    """점검 쪽(result.pages, 1부터)."""


def _check(name: str, run: RunSide) -> None:
    try:
        shapes.RESULT_SHAPES[shapes.SHAPE].validate_python(run.result, strict=True)
    except ValidationError as exc:
        raise ValueError(f"{name} 결과가 {shapes.SHAPE} 꼴이 아니다({exc.error_count()}곳 어긋남)") from exc
    if run.result["dryRun"] is not None:
        raise ValueError(f"{name} 결과가 dry-run 이다 — 판정 문장이 없어 견줄 수 없다")
    page_count = run.result["source"]["pageCount"]
    if len(run.page_texts) != page_count:
        raise ValueError(f"{name} 쪽 글 수({len(run.page_texts)})가 결과의 pageCount({page_count})와 다르다")
    if run.side["unconfirmed"] != (run.adopted is None):
        raise ValueError(f"{name} 의 unconfirmed 와 adopted 가 어긋난다(미확정이면 None, 확정본이면 집합)")
    count = len(run.result["items"])
    if run.adopted is not None and any(not 0 <= i < count for i in run.adopted):
        raise ValueError(f"{name} 의 adopted 에 items 범위(0~{count - 1}) 밖의 번호가 있다")


def _prepare(run: RunSide) -> _Prepared:
    items = cast("list[Mapping[str, Any]]", run.result["items"])
    return _Prepared(
        items=[(i, item) for i, item in enumerate(items) if run.adopted is None or i in run.adopted],
        norm_pages=[norm_str(text, TIER) for text in run.page_texts],
        scanned=frozenset(cast("list[int]", run.result["pages"])),
    )


def _norm(item: Mapping[str, Any]) -> str:
    return norm_str(strip_tail(cast("str", item["sentence"])), TIER)


def _key(item: Mapping[str, Any]) -> Key | None:
    text = _norm(item)
    if not text:
        return None  # 빈 글은 어디에나 있다 — 짝짓지 않는다
    return (text, tuple(cast("list[str]", item["parts"])))


def _found(needle: str, norm_pages: Sequence[str]) -> list[int]:
    """needle 이 든 쪽(1부터)."""
    return [page for page, text in enumerate(norm_pages, start=1) if needle in text]


def _in_scope(found: Sequence[int], scanned: frozenset[int]) -> bool:
    return any(page in scanned for page in found)


def _base_only(item: Mapping[str, Any], base: _Prepared, target: _Prepared) -> GreenwashCompareOutcome:
    if _key(item) is None:
        return "resolved_undetermined"
    needle = _norm(item)
    found = _found(needle, target.norm_pages)
    if found:
        return "resolved_not_flagged" if _in_scope(found, target.scanned) else "out_of_scope"
    return "resolved_deleted" if _found(needle, base.norm_pages) else "resolved_undetermined"


def _target_only(item: Mapping[str, Any], base: _Prepared) -> GreenwashCompareOutcome:
    if _key(item) is None:
        return "new"
    found = _found(_norm(item), base.norm_pages)
    if found and not _in_scope(found, base.scanned):
        return "out_of_scope"
    return "new"


def _ref(index: int, item: Mapping[str, Any]) -> GreenwashItemRef:
    return {
        "itemIndex": index,
        "sentence": cast("str", item["sentence"]),
        "level": item["level"],
        "parts": list(cast("list[str]", item["parts"])),
        "page": cast("int", item["page"]),
    }


def _counts(pairs: Sequence[GreenwashComparePair]) -> GreenwashCompareCounts:
    return cast("GreenwashCompareCounts", {o: sum(1 for p in pairs if p["outcome"] == o) for o in OUTCOMES})


def compare_runs(base: RunSide, target: RunSide) -> GreenwashCompareResult:
    """두 판의 대표 실행 → greenwash.compare@1. 입력이 규칙에 어긋나면 ValueError(한국어 한 줄)."""
    _check("base", base)
    _check("target", target)
    b, t = _prepare(base), _prepare(target)

    waiting: dict[Key, list[tuple[int, Mapping[str, Any]]]] = {}
    for index, item in t.items:
        key = _key(item)
        if key is not None:
            waiting.setdefault(key, []).append((index, item))

    matched: list[GreenwashComparePair] = []
    base_only: list[GreenwashComparePair] = []
    paired: set[int] = set()
    for index, item in b.items:
        key = _key(item)
        queue = waiting.get(key) if key is not None else None
        if queue:
            t_index, t_item = queue.pop(0)
            paired.add(t_index)
            outcome: GreenwashCompareOutcome = "remaining" if item["level"] == t_item["level"] else "level_changed"
            matched.append({"outcome": outcome, "base": _ref(index, item), "target": _ref(t_index, t_item)})
        else:
            base_only.append({"outcome": _base_only(item, b, t), "base": _ref(index, item), "target": None})
    target_only: list[GreenwashComparePair] = [
        {"outcome": _target_only(item, b), "base": None, "target": _ref(index, item)}
        for index, item in t.items
        if index not in paired
    ]

    pairs = matched + base_only + target_only
    out: GreenwashCompareResult = {
        "schemaVersion": SHAPE,
        "base": {**base.side},
        "target": {**target.side},
        "pairs": pairs,
        "counts": _counts(pairs),
    }
    COMPARE_SHAPES[SHAPE].validate_python(out, strict=True)
    return out
