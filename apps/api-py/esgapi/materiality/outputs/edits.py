"""결과 글 칸 고침의 순수 규칙(밴드 IRS3, 결정 MARC-ENT-561) — 틀도 DB 도 모른다. 꼴·상한은 contracts/edit_shapes.py.

    parse(pointer)                       허용 꼴(POINTER_PATTERN)의 주소 → Address, 아니면 None
    groups(body)                         맥락 항목의 퍼짐 묶음(원본 본문에서 — 고친 url 로 다시 묶지 않는다)
    check(body, current, changes)        한 저장의 고침들 → (바른 주소, 정규 값) 목록, 또는 Invalid(첫 어긋난 차례 n)
    apply(body, current)                 고친 판(새 dict — 원본은 그대로). current 가 비면 본문 그대로(같은 객체)
    listing(body, current)               지금 값이 원문과 다른 칸만 본문 차례로 (주소, 지금 값, 원문)

칸(Q5 가 — 글 칸만): 2-1 영향 정의 `T/impact/rows/{r}/impactDefinition` · 2-2 영향 정의·①②③
`T/pathway/rows/{r}/(impactDefinition|impactDriver|businessImpact|financialImpact)` · 맥락 항목
`T/(impact|financial|pathway)/rows/{r}/context/(regulations|controversies)/{k}/(title|summary|url)`
(T = /part2/topics/{t}/subtopics/{s}). 그 자리의 갈래가 done 이고 원본 본문에 그 칸이 있어야 한다.

퍼짐 묶음(Q4 가): 같은 토픽·같은 쪽에서, 원본 url(strip)이 빈 글·null 이 아니면 impact·financial·pathway rows 의
context 항목 중 원본 url 이 같은 것 전부. url 이 비면 그 항목 하나 + 그 재무 항목을 사본으로 가진 Pathway 항목(i 로
이음 — contracts/wire.py 의 pathway_view 는 i 번째 재무 row 의 context 를 잇는다). 묶음의 **첫 자리**(바른 주소) = 그
토픽 안 모든 서브토픽의 impact rows 를 다 훑은 뒤 모든 서브토픽의 financial rows 차례의 첫 것(outputs/final_xlsx.py 의
shortlist_rows → merged_items 와 같은 차례). Pathway 주소는 i 로 재무 rows[i-1] 의 같은 k 로 옮긴 뒤 같은 규칙(i 가
null·범위 밖이면 거절).

값(Q6 가): 빈 글·공백만 → null. 짝 없는 서로게이트·C0 제어 문자(\\t·\\n·\\r 밖, NUL 포함) 거절. 상한(코드포인트, 어림)
정의·①②③·summary 4,000 · title 1,000 · url 2,048. url 은 null 이거나 앞뒤 공백을 뗀 글이 http:// · https:// 로 시작
(웹 ResultScreen 의 SAFE_URL 과 같은 규칙).
url 규칙: 고친 판에서 같은 토픽·쪽의 다른 묶음과 url(strip)이 같아지면 거절(Q9 가). url 을 비우는데(→ null) 그 묶음의
impact+financial 항목이 둘 이상이면 거절(합쳐 보이던 하나가 여럿으로 갈라진다).
덮기(결정적): 바른 주소마다 지금 값(가장 큰 revision)을 묶음 전체(Pathway 사본 포함)에 쓴다 — 원문과 같은 값도 쓴다.
`parsed`·`raw`·`warnings`·`settings`·`part1` 은 건드리지 않는다.
"""

import copy
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final, NamedTuple, cast

from esgapi.materiality.contracts.edit_shapes import (
    POINTER_PATTERN,
    TEXT_MAX_CHARS,
    TITLE_MAX_CHARS,
    URL_MAX_CHARS,
)

PHASES: Final = ("impact", "financial", "pathway")
SIDES: Final = ("regulations", "controversies")
ROW_FIELDS: Final = ("impactDefinition", "impactDriver", "businessImpact", "financialImpact")
ITEM_FIELDS: Final = ("title", "summary", "url")
LIMITS: Final[Mapping[str, int]] = {
    "impactDefinition": TEXT_MAX_CHARS,
    "impactDriver": TEXT_MAX_CHARS,
    "businessImpact": TEXT_MAX_CHARS,
    "financialImpact": TEXT_MAX_CHARS,
    "summary": TEXT_MAX_CHARS,
    "title": TITLE_MAX_CHARS,
    "url": URL_MAX_CHARS,
}
_POINTER: Final = re.compile(POINTER_PATTERN)
_SAFE_URL: Final = re.compile(r"https?://")


class Address(NamedTuple):
    """칸 하나의 자리. side·item 은 맥락 항목 칸일 때만 값이다."""

    topic: int
    subtopic: int
    phase: str
    row: int
    side: str | None
    item: int | None
    field: str


ItemKey = tuple[int, int, str, int, str, int]
"""맥락 항목 하나(topic, subtopic, phase, row, side, item)."""


@dataclass(frozen=True, slots=True)
class Invalid:
    """한 저장의 고침이 규칙에 어긋났다(경로 400 INVALID_EDIT). message 는 한국어 한 문장."""

    message: str


@dataclass(frozen=True, slots=True)
class Groups:
    """맥락 항목의 퍼짐 묶음. of = 항목 → 묶음의 첫 자리, members = 첫 자리 → 묶음 전부(impact·financial·pathway)."""

    of: Mapping[ItemKey, ItemKey]
    members: Mapping[ItemKey, Sequence[ItemKey]]


def parse(pointer: str) -> Address | None:
    """허용 꼴의 주소 → Address. 꼴 밖이면 None."""
    if _POINTER.fullmatch(pointer) is None:
        return None
    parts = pointer.split("/")  # ['', 'part2', 'topics', t, 'subtopics', s, phase, 'rows', r, …]
    topic, subtopic, phase, row = int(parts[3]), int(parts[5]), parts[6], int(parts[8])
    if parts[9] == "context":
        return Address(topic, subtopic, phase, row, parts[10], int(parts[11]), parts[12])
    return Address(topic, subtopic, phase, row, None, None, parts[9])


def pointer(address: Address) -> str:
    """Address → JSON Pointer."""
    head = f"/part2/topics/{address.topic}/subtopics/{address.subtopic}/{address.phase}/rows/{address.row}"
    if address.side is None:
        return f"{head}/{address.field}"
    return f"{head}/context/{address.side}/{address.item}/{address.field}"


def _order(address: Address) -> tuple[int, ...]:
    """본문 차례(토픽 → 서브토픽 → impact → financial → pathway → 줄 → 칸)."""
    if address.side is None:
        inner = (0, ROW_FIELDS.index(address.field), 0, 0)
    else:
        inner = (1, SIDES.index(address.side), cast("int", address.item), ITEM_FIELDS.index(address.field))
    return (address.topic, address.subtopic, PHASES.index(address.phase), address.row, *inner)


def _topics(body: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    part2 = body["part2"]
    return list(part2["topics"]) if part2["status"] == "done" else []


def _rows(sub: Mapping[str, Any], phase: str) -> list[dict[str, Any]]:
    outcome = sub[phase]
    return list(outcome["rows"]) if outcome["status"] == "done" else []


def _row(body: Mapping[str, Any], topic: int, subtopic: int, phase: str, row: int) -> dict[str, Any] | None:
    topics = _topics(body)
    if topic >= len(topics):
        return None
    subs = topics[topic]["subtopics"]
    if subtopic >= len(subs):
        return None
    rows = _rows(subs[subtopic], phase)
    return rows[row] if row < len(rows) else None


def _item(body: Mapping[str, Any], key: ItemKey) -> dict[str, Any] | None:
    topic, subtopic, phase, row, side, item = key
    found = _row(body, topic, subtopic, phase, row)
    if found is None:
        return None
    items = found["context"][side]
    return items[item] if item < len(items) else None


def _url(item: Mapping[str, Any]) -> str | None:
    given = item.get("url")
    return given.strip() if isinstance(given, str) and given.strip() else None


def _fin_of(pathway_row: Mapping[str, Any], fin_rows: Sequence[Mapping[str, Any]]) -> int | None:
    """Pathway 줄의 i(1부터) → 재무 rows 의 차례(0부터). 잇지 못하면 None."""
    i = pathway_row.get("i")
    return i - 1 if isinstance(i, int) and not isinstance(i, bool) and 1 <= i <= len(fin_rows) else None


def _side_items(subs: Sequence[Mapping[str, Any]], topic: int, phase: str, side: str) -> Iterator[ItemKey]:
    for s, sub in enumerate(subs):
        for r, row in enumerate(_rows(sub, phase)):
            for k in range(len(row["context"][side])):
                yield (topic, s, phase, r, side, k)


def groups(body: Mapping[str, Any]) -> Groups:
    """원본 본문의 퍼짐 묶음(머리말)."""
    of: dict[ItemKey, ItemKey] = {}
    members: dict[ItemKey, list[ItemKey]] = {}
    for t, topic in enumerate(_topics(body)):
        subs = topic["subtopics"]
        for side in SIDES:
            by_url: dict[str, ItemKey] = {}
            for phase in ("impact", "financial"):  # 모든 서브토픽의 impact 다음 모든 서브토픽의 financial
                for key in _side_items(subs, t, phase, side):
                    url = _url(cast("Mapping[str, Any]", _item(body, key)))
                    first = by_url.setdefault(url, key) if url is not None else key
                    of[key] = first
                    members.setdefault(first, []).append(key)
            for s, sub in enumerate(subs):
                fin_rows = _rows(sub, "financial")
                for r, row in enumerate(_rows(sub, "pathway")):
                    fin = _fin_of(row, fin_rows)
                    for k, item in enumerate(row["context"][side]):
                        url = _url(item)
                        if url is not None:
                            first = by_url.get(url)
                        else:
                            twin: ItemKey = (t, s, "financial", fin if fin is not None else -1, side, k)
                            first = of.get(twin) if fin is not None and _url(_item(body, twin) or {}) is None else None
                        if first is not None:
                            key = (t, s, "pathway", r, side, k)
                            of[key] = first
                            members[first].append(key)
    return Groups(of=of, members=members)


def _canonical(body: Mapping[str, Any], found: Groups, address: Address) -> Address | str:
    """주소 → 바른 주소, 아니면 까닭(글)."""
    row = _row(body, address.topic, address.subtopic, address.phase, address.row)
    if row is None:
        return "그 자리의 줄이 결과에 없다"
    if address.side is None:
        if address.field not in row or not isinstance(row[address.field], str | None):
            return "그 칸은 고칠 수 없다"
        return address
    item = cast("int", address.item)
    if item >= len(row["context"][address.side]):
        return "그 자리의 맥락 항목이 결과에 없다"
    key: ItemKey = (address.topic, address.subtopic, address.phase, address.row, address.side, item)
    if address.phase == "pathway":
        sub = _topics(body)[address.topic]["subtopics"][address.subtopic]
        fin = _fin_of(row, _rows(sub, "financial"))
        if fin is None:
            return "그 Pathway 줄은 재무 영향 줄과 이어지지 않아 맥락 항목을 고칠 수 없다"
        key = (address.topic, address.subtopic, "financial", fin, address.side, item)
        if _item(body, key) is None:
            return "그 Pathway 맥락 항목의 재무 영향 항목이 결과에 없다"
    first = found.of[key]
    return Address(*first, address.field)


def _value(field: str, value: str | None) -> str | Invalid | None:
    """값 규칙(머리말) → 정규 값, 아니면 Invalid(까닭만 — 차례는 부르는 쪽이 붙인다)."""
    if value is None or value.strip() == "":
        return None
    if any(0xD800 <= ord(c) <= 0xDFFF for c in value):
        return Invalid("짝 없는 서로게이트 글자는 받지 않는다")
    if any(ord(c) < 0x20 and c not in "\t\n\r" for c in value):
        return Invalid("제어 문자(탭·줄바꿈 밖)는 받지 않는다")
    if len(value) > LIMITS[field]:
        return Invalid(f"글이 {LIMITS[field]:,}자를 넘는다")
    if field == "url" and _SAFE_URL.match(value.strip()) is None:
        return Invalid("출처는 http:// 나 https:// 로 시작해야 한다")
    return value


def _url_pointer(first: ItemKey) -> str:
    return pointer(Address(*first, "url"))


def check(
    body: Mapping[str, Any], current: Mapping[str, str | None], changes: Sequence[tuple[str, str | None]]
) -> list[tuple[str, str | None]] | Invalid:
    """한 저장의 고침들(차례대로) → (바른 주소, 정규 값). current = 지금 고침(바른 주소 → 지금 값)."""
    found = groups(body)
    out: list[tuple[str, str | None]] = []
    seen: set[str] = set()
    for n, (given, value) in enumerate(changes, 1):
        address = parse(given)
        if address is None:
            return Invalid(f"{n}번째 고침의 자리({given[:80]})는 고칠 수 있는 칸이 아니다")
        canonical = _canonical(body, found, address)
        if isinstance(canonical, str):
            return Invalid(f"{n}번째 고침: {canonical}")
        normal = _value(address.field, value)
        if isinstance(normal, Invalid):
            return Invalid(f"{n}번째 고침: {normal.message}")
        target = pointer(canonical)
        if target in seen:
            return Invalid(f"{n}번째 고침은 앞 고침과 같은 칸(같은 묶음)이다")
        seen.add(target)
        if canonical.field == "url" and normal is None:
            first = cast("ItemKey", tuple(canonical[:6]))
            if sum(1 for m in found.members[first] if m[2] != "pathway") >= 2:
                return Invalid(f"{n}번째 고침: 여러 항목이 합쳐 보이는 출처는 비울 수 없다")
        out.append((target, normal))
    clash = _url_clash(body, found, {**current, **dict(out)})
    if clash is not None:
        n = next((i for i, (target, _) in enumerate(out, 1) if target in clash), 1)
        return Invalid(f"{n}번째 고침: 같은 토픽의 다른 항목과 출처(url)가 같아진다")
    return out


def _url_clash(body: Mapping[str, Any], found: Groups, merged: Mapping[str, str | None]) -> set[str] | None:
    """고친 판에서 같은 토픽·쪽의 두 묶음의 url(strip)이 같으면 그 둘의 url 주소. 없으면 None."""
    seen: dict[tuple[int, str, str], str] = {}
    for first in found.members:
        target = _url_pointer(first)
        original = cast("Mapping[str, Any]", _item(body, first))
        effective = merged[target] if target in merged else original.get("url")
        url = effective.strip() if isinstance(effective, str) and effective.strip() else None
        if url is None:
            continue
        slot = (first[0], first[4], url)
        if slot in seen:
            return {seen[slot], target}
        seen[slot] = target
    return None


def apply(body: dict[str, Any], current: Mapping[str, str | None]) -> dict[str, Any]:
    """고친 판(머리말 「덮기」). current 는 바른 주소 → 지금 값. 비면 body 그대로(같은 객체)."""
    if not current:
        return body
    found = groups(body)
    out = copy.deepcopy(body)
    for target, value in current.items():
        address = parse(target)
        if address is None:
            raise LookupError(target)  # 저장한 주소는 받기를 지난 바른 주소다 — 여기 오면 결함
        if address.side is None:
            row = _row(out, address.topic, address.subtopic, address.phase, address.row)
            if row is None:
                raise LookupError(target)
            row[address.field] = value
            continue
        first: ItemKey = cast("ItemKey", tuple(address[:6]))
        for key in found.members[first]:
            cast("dict[str, Any]", _item(out, key))[address.field] = value
    return out


def original_value(body: Mapping[str, Any], target: str) -> str | None:
    """바른 주소의 원문(결과 본문의 그 자리 값)."""
    address = parse(target)
    if address is None:
        raise LookupError(target)
    if address.side is None:
        row = _row(body, address.topic, address.subtopic, address.phase, address.row)
        if row is None:
            raise LookupError(target)
        return cast("str | None", row[address.field])
    item = _item(body, cast("ItemKey", tuple(address[:6])))
    if item is None:
        raise LookupError(target)
    return cast("str | None", item[address.field])


def listing(body: Mapping[str, Any], current: Mapping[str, str | None]) -> list[tuple[str, str | None, str | None]]:
    """지금 값이 원문과 다른 칸만 본문 차례로 (바른 주소, 지금 값, 원문)."""
    out: list[tuple[Address, str | None, str | None]] = []
    for target, value in current.items():
        original = original_value(body, target)
        if value != original:
            out.append((cast("Address", parse(target)), value, original))
    out.sort(key=lambda entry: _order(entry[0]))
    return [(pointer(address), value, original) for address, value, original in out]
