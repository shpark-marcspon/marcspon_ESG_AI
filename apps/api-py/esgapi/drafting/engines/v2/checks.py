"""출처 검사 — 근거 판정은 이 코드다(모델이 댄 블록·문장 번호를 그대로 믿지 않는다, 결정 MARC-ENT-514 2번).

출처마다 ⓐ 이 잎의 재료에 실은 블록인가(아니면 출처를 버리고 source_not_given) ⓑ 문장(표는 행) 번호가 그 블록에 실은
번호인가(아니면 그 출처는 sentence 없이 — index None + sentence_out_of_range. 제목 블록은 번호가 없어 s 는 null 이어야)
ⓒ 남은 출처가 0 이면 unsupported(+unsupported_bullet) ⓓ bullet 의 숫자(쉼표를 뺀 정수·소수, % 는 떼고 견줌)가
숫자 몫에 없으면 unsupported(+number_not_in_source). 숫자 몫 = 남은 출처 블록 글의 합 ∪ 남은 출처 중 짧은 블록
(제목, 또는 SHORT_MAX 자 안의 문단 — 표는 짧아도 아님)마다 그 넓힘 몫: 이 잎 재료(given)의 같은 쪽 표 전부와,
같은 쪽 원래 차례(order)의 앞뒤 NEIGHBOURS 블록(쪽을 넘지 않고, given 에 없는 자리에서 멈춤). 넓힘으로 본 표는
머리 행까지 행 전부를 본다. 쪽 전체는 보지 않는다 — 표 머리·쪽 머리 연도가 틀린 연도를 통과시킴(562). 넓힘은 판정에만
쓰고 sources 에 더하지 않는다(RPS2). 날짜 「2025.05.22」(구분자 . - / 같음, 셋 조각)는 연·월·일 수 셋으로, 정수
조각은 앞 0 을 뗀다(「05」→「5」). 같은 (블록, 번호) 는 하나로, 차례는 (쪽, order, 번호 — None 먼저). 근거 없는
bullet 은 지우지 않고 표시한다.

출처 dict = {documentId, blockId, page, index}(상자는 report 가 places 로 단다).
"""

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from esgapi.drafting.engines.v1.mapping import Warning, warning

from .material import HEADING, TABLE, GivenBlock

NUMBER: Final = re.compile(r"\d[\d,]*(?:\.\d+)?")
DATE: Final = re.compile(r"(?<!\d)(?<!\d\.)(\d{4})([./-])(\d{1,2})\2(\d{1,2})(?!\.?\d)")
"""연·월·일 셋 꼴(구분자 같음). 앞뒤가 숫자·「.숫자」로 이어지면(「1.2.3.4」 꼴 판 번호) 날짜 아님.
두 조각 「2025.05」 는 소수 그대로(「2025.12톤」 꼴과 못 가름)."""

SHORT_MAX: Final = 60
"""짧은 문단의 글자 수 상한(이하면 넓힘). SHORT_MAX 60 · k 1 — RPS2 run 30 다시 검사로 고름(band-reports/RPS2.md §1:
80·k 2 는 표 머리 연도로 지나는 덫 꼴이 들어옴)."""
NEIGHBOURS: Final = 1
"""넓힘 이웃 k — 쪽 안 원래 차례의 앞뒤 k 블록(SHORT_MAX 와 같은 쓸기에서 고름)."""


def _whole_number(piece: str) -> str:
    return piece if "." in piece else piece.lstrip("0") or "0"


def numbers(text: str, *, source: bool = False) -> set[str]:
    """글 안의 수(「1,200」→「1200」, 「3.5」 그대로, 끝 쉼표는 문장 부호로 뗌, 날짜는 연·월·일 셋, 정수 앞 0 뗌).
    source 면(출처 쪽) 점 날짜의 「연.월」 토막(쓴 그대로 — 「2025.12.31」→「2025.12」)도 낸다: bullet 「2025.12」 는
    두 조각이라 소수로 읽히므로 날짜 규칙 앞(BASE)처럼 지나게."""
    found = {_whole_number(part) for match in DATE.finditer(text) for part in match.group(1, 3, 4)}
    if source:
        found |= {f"{m.group(1)}.{m.group(3)}" for m in DATE.finditer(text) if m.group(2) == "."}
    rest = DATE.sub(" ", text)
    return found | {_whole_number(m.group(0).rstrip(",").replace(",", "")) for m in NUMBER.finditer(rest)}


def _short(block: GivenBlock) -> bool:
    return block.kind == HEADING or (block.kind != TABLE and len(block.text) <= SHORT_MAX)


def _widened(block: GivenBlock, given: Mapping[str, GivenBlock]) -> list[GivenBlock]:
    """짧은 블록의 넓힘 몫 — 같은 쪽 given 의 표 전부 + 쪽 안 원래 차례(order)의 앞뒤 NEIGHBOURS. 차례에서 given 에 없는
    자리(재료에서 잘림·빈 블록)를 만나면 그쪽은 거기서 멈춘다(빠진 자리를 건너 넓히지 않음)."""
    page = [b for b in given.values() if b.page == block.page]
    by_order = {b.order: b for b in page}
    near: list[GivenBlock] = []
    for step in (-1, 1):
        for distance in range(1, NEIGHBOURS + 1):
            found = by_order.get(block.order + step * distance)
            if found is None:
                break
            near.append(found)
    return [*(b for b in page if b.kind == TABLE), *near]


def check(
    bullets: Sequence[Mapping[str, Any]],
    *,
    key: str,
    given: Mapping[str, GivenBlock],
    document_id: int,
) -> tuple[list[dict[str, Any]], list[Warning]]:
    checked: list[dict[str, Any]] = []
    warnings: list[Warning] = []
    for bullet in bullets:
        kept: dict[tuple[str, int | None], GivenBlock] = {}
        for source in bullet["sources"]:
            block = given.get(source["block"])
            if block is None:
                warnings.append(warning("source_not_given", "이 잎에 주지 않은 블록을 근거로 댔다(뺌).", key=key))
                continue
            index: int | None = source["s"]
            if index is not None and index not in block.units:
                warnings.append(
                    warning(
                        "sentence_out_of_range",
                        "근거 블록에 없는 문장 번호를 댔다(블록만 남김).",
                        key=key,
                        page=block.page,
                    )
                )
                index = None
            kept[(block.id, index)] = block
        order = sorted(kept, key=lambda at: (kept[at].page, kept[at].order, -1 if at[1] is None else at[1]))
        unsupported = not order
        if unsupported:
            warnings.append(warning("unsupported_bullet", "근거 블록이 남지 않은 bullet 이다.", key=key))
        else:
            found: set[str] = set()
            for block in {at[0]: kept[at] for at in order}.values():
                found |= numbers(block.text, source=True)
                if _short(block):
                    for near in _widened(block, given):
                        found |= numbers(near.text, source=True)
            if not numbers(bullet["text"]) <= found:
                unsupported = True
                warnings.append(warning("number_not_in_source", "bullet 의 숫자가 출처 블록에 없다.", key=key))
        checked.append(
            {
                "text": bullet["text"],
                "sources": [
                    {
                        "documentId": document_id,
                        "blockId": block_id,
                        "page": kept[(block_id, index)].page,
                        "index": index,
                    }
                    for block_id, index in order
                ],
                "unsupported": unsupported,
            }
        )
    return checked, warnings
