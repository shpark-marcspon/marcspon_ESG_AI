"""도구 호출 한 번(이름·인자·도구 출력 dict) → 결과 꼴 dataverify.result@2 의 검사 기록 `Check` 하나(밴드 DV1a).

엔진(engines/colab_156)을 import 하지 않는다 — dict 만 받는다(엔진은 계약을 모르고 계약은 엔진을 모른다). 새 셈은 없다:
- 수(value·diff·tolerance)는 repr(float) 글자로 옮긴다(코랩 출력은 float — 「코랩과 다른 자리」, 값은 같다).
- 「N/A」는 value null + na true, 도구의 {"error": …} 는 kind error, 계산하지 못한 해는 note 를 그대로 둔다 — 셋을
  한 값으로 접지 않는다.
- 이름형 도구(*_by_name·*_by_names)의 항목은 items.byName, 단건 도구(sum_check·sum_n_check·ratio_check)의 인자는
  items.raw 에 받은 그대로.
- 모델이 준 인자를 비추는 칸은 받은 그대로(JsonValue)라 도구가 낸 결과는 늘 제 갈래로 남는다. 지은 기록이 꼴을
  지나지 못하는 것은 도구 출력이 어긋난 엔진 결함뿐이고, 그때만 kind error 「shape mismatch: <까닭>」(짧은 글)이다.
- 허용 오차는 도구가 비교에 쓴 값이다(bool 은 1·0). 수가 아니면 null — 도구가 쓰지 않은 경우뿐이다.
"""

import collections.abc
import re
from collections.abc import Mapping
from typing import Any, Final, cast

from pydantic import ValidationError

from esgapi.dataverify.contracts import shapes
from esgapi.dataverify.contracts.shapes import CHECK, ErrorCheck, RuleCheck, SearchCheck, ValueCheck

Check = ValueCheck | RuleCheck | SearchCheck | ErrorCheck

RULES: Final = {
    "sum_check": "sum",
    "sum_check_by_name": "sum",
    "sum_n_check": "sum_n",
    "sum_n_check_by_names": "sum_n",
    "ratio_check": "ratio",
    "ratio_check_by_name": "ratio",
}
"""검사 도구 → 규칙."""
BY_NAME: Final = {
    "sum_check_by_name": ("total", "a", "b"),
    "sum_n_check_by_names": ("addends", "target"),
    "ratio_check_by_name": ("numerator", "denominator", "expected"),
}
"""이름형 도구 → 항목 인자의 열쇠."""
RAW: Final = {"sum_check": ("a", "b", "c"), "sum_n_check": ("addends", "target"), "ratio_check": ("d", "e", "f")}
"""단건 도구 → 값 인자의 열쇠."""
QUAD: Final = ("대분류", "중분류", "소분류", "단위")
FILTER: Final = ("대분류", "중분류", "소분류_contains")


def _tolerance(value: Any) -> str | None:
    """도구가 비교에 쓴 허용 오차(실행 값 — 밴드 DV16 부터 늘 prompts.TOLERANCE = 0.0)의 repr(float) 글자.
    수가 아니면 None(실행 값은 늘 수라 생기지 않는다 — 옛 꼴을 지키는 방어)."""
    if not isinstance(value, bool | int | float):
        return None
    try:
        return repr(float(value))
    except OverflowError:  # float 로 담지 못하는 큰 정수 — 도구는 정수 그대로 견줬다
        return repr(value)


def _year_result(year: Any, out: Mapping[str, Any]) -> dict[str, Any]:
    diff = out["diff"]
    return {
        "year": year,
        "ok": out["ok"],
        "status": out["status"],
        "diff": None if diff is None else repr(float(diff)),
        "note": out.get("note"),
        "explanation": out["explanation"],
    }


def _build(seq: int, name: str, args: Any, output: Mapping[str, Any], tolerance: float) -> dict[str, Any]:
    head: dict[str, Any] = {"seq": seq, "tool": name}
    if "error" in output:
        return {**head, "kind": "error", "message": output["error"], "args": args}
    # 오류가 아니면 도구가 args.get 을 불렀다 — args 는 객체다
    args = cast("dict[str, Any]", args)
    if name == "value_of_by_name":
        value = output["value"]
        na = value == "N/A"
        return {
            **head,
            "kind": "value",
            "item": [args.get(key) for key in QUAD],
            "year": args.get("year"),
            "value": None if na else repr(float(value)),
            "na": na,
        }
    if name == "search_items":
        return {
            **head,
            "kind": "search",
            "filter": {key: args[key] for key in FILTER if key in args},
            "total": output["total"],
            "limit": output["limit"],
            "offset": output["offset"],
            "returned": len(output["items"]),
        }
    if name in RULES:
        by_name = name in BY_NAME
        if by_name:
            items = {"byName": {key: args[key] for key in BY_NAME[name] if key in args}, "raw": None}
            years = [_year_result(row["year"], row) for row in output["results"]]
        else:
            items = {"byName": None, "raw": {key: args[key] for key in RAW[name] if key in args}}
            years = [_year_result(None, output)]
        return {
            **head,
            "kind": "check",
            "rule": RULES[name],
            "items": items,
            "tolerance": _tolerance(tolerance),
            "years": years,
        }
    raise ValueError(f"모르는 도구의 출력이다: {name}")


def _mismatch(error: Exception) -> str:
    """꼴이 어긋난 까닭을 짧게(pydantic 의 안내 글·URL 은 싣지 않는다 — 엑셀로 나간다)."""
    if isinstance(error, ValidationError):
        first = error.errors(include_url=False, include_input=False)[0]
        where = ".".join(str(part) for part in first["loc"])
        return f"shape mismatch: {first['type']} at {where} ({error.error_count()} errors)"
    return f"shape mismatch: {type(error).__name__}"


def to_check(seq: int, name: str, args: Any, output: Mapping[str, Any], *, tolerance: float) -> Check:
    """도구 호출 한 번의 기록. `tolerance` 는 실행의 판정 허용 오차 — 도구가 실제로 견준 값이다(밴드 DV16: 분배기가
    모델이 인자로 준 값을 무시하므로 기록도 모델 값을 싣지 않는다).

    모델이 준 인자를 비추는 칸(item·year·byName·raw·filter·limit·offset·args)은 받은 그대로라, 도구가 낸 결과는 늘
    그 갈래(value·check·search·error)로 남는다. 「shape mismatch」 error 는 도구 출력 자체가 꼴과 어긋날 때(엔진의
    결함)뿐이다."""
    try:
        record = _build(seq, name, args, output, tolerance)
        CHECK.validate_python(record, strict=True)
    except (ValidationError, KeyError, TypeError, ValueError, AttributeError) as error:
        record = {"seq": seq, "tool": name, "kind": "error", "message": _mismatch(error), "args": args}
    return cast("Check", record)


# ── 인사이트 리포트 → 표 줄·출처(밴드 DV1b) ──
# 코랩 밖 규칙이다(코랩은 리포트 글을 그대로 docx 로 옮긴다 — 「다른 자리」).

INSIGHT_COLUMNS: Final = ("area", "indicator", "observation", "risk", "interpretation")
"""인사이트 표의 다섯 열(코랩 셀 18 출력 형식의 차례)."""
_SEPARATOR: Final = re.compile(r"^\|?\s*:?-+:?\s*(\|\s*:?-+:?\s*)*\|?$")


def _cells(line: str) -> list[str]:
    """마크다운 표 한 줄의 칸 글(strip 만). 앞뒤의 「|」 하나씩은 칸 경계라 뗀다."""
    body = line.strip()
    if body.startswith("|"):
        body = body[1:]
    if body.endswith("|"):
        body = body[:-1]
    return [cell.strip() for cell in body.split("|")]


def to_insight_rows(text: str) -> tuple[list[shapes.InsightRow], shapes.RowsParsed]:
    """리포트 글의 마크다운 표(머리줄 다음 줄이 구분선 `|---|` 꼴인 것)를 전부 찾아 데이터 줄을 다섯 열로 읽는다.

    글이 비면 ([], "none"). 표가 없거나, 머리줄·데이터 줄 가운데 칸이 다섯이 아닌 줄이 하나라도 있거나, 데이터 줄이
    0 이면 ([], "unparsed") — 원문은 report 에 남는다. 표는 빈 줄이나 「|」 없는 줄에서 끝난다."""
    if not text.strip():
        return [], "none"
    lines = text.splitlines()
    rows: list[shapes.InsightRow] = []
    tables = 0
    index = 0
    while index < len(lines) - 1:
        head, separator = lines[index], lines[index + 1].strip()
        if "|" not in head or "|" not in separator or _SEPARATOR.match(separator) is None:
            index += 1
            continue
        tables += 1
        if len(_cells(head)) != len(INSIGHT_COLUMNS):
            return [], "unparsed"
        index += 2
        while index < len(lines) and lines[index].strip() and "|" in lines[index]:
            cells = _cells(lines[index])
            if len(cells) != len(INSIGHT_COLUMNS):
                return [], "unparsed"
            rows.append(cast("shapes.InsightRow", dict(zip(INSIGHT_COLUMNS, cells, strict=True))))
            index += 1
    if tables == 0 or not rows:
        return [], "unparsed"
    return rows, "parsed"


def to_sources(citations: collections.abc.Sequence[Mapping[str, Any]]) -> list[shapes.WebSource]:
    """웹 검색 출처(url_citation 의 url·title) — url 의 첫 등장만, 차례 그대로. title 은 받은 그대로."""
    seen: set[str] = set()
    sources: list[shapes.WebSource] = []
    for citation in citations:
        url = citation["url"]
        if url in seen:
            continue
        seen.add(url)
        sources.append({"title": citation.get("title"), "url": url})
    return sources
