"""밴드 IR2b §4-7·§4-8: 1부 → 2부 한 실행(flows/iro_155)의 요청 대조와 기간 사례 표(모의 공급사만 — 네트워크·키 0).

    사용(apps/api-py 에서): uv run --frozen python -I scripts/materiality_compare_ir2b.py compare|window <출력 자리>

compare(§4-7) — 같은 입력·같은 모의 답으로:
    ① 새 흐름의 1부 요청 다섯 = colab_155.FLOW 단독 요청 다섯(요청 몸 바이트 — openai 공급사의 SDK kwargs JSON)
    ② 창이 다 덮을 때 새 흐름의 2부 요청 아홉 = 시험 흐름 PART2_FLOW(씨앗 = 같은 1부 결과)의 요청 아홉
    ③ 창을 좁힌 사례(컨트로버시 항목 하나가 기간 밖): 새 흐름의 2부 요청 = PART2_FLOW 에 손으로 거른 1부 결과를 씨앗으로
       넣은 요청. 손 거름은 이 스크립트가 따로 짓는다(contracts/wire 의 기간 함수 재사용 0).
    끝 줄 PART1_SAME=<다른 수> PART2_SAME=<다른 수>(②+③), 종료 코드는 둘 다 0 일 때만 0.
window(§4-8) — tests/contracts/test_wire_window.py 의 사례 표(S1 문법·항목 날짜)와 아래 S2 한 항목 표를 돌려
    <출력 자리>/window-cases.tsv(입력·기대·실제·맞음)에 적고, 끝 줄 WINDOW_CASES=<맞음>/<전체>.
출력 자리 밖에는 쓰지 않는다. 결과 글은 지어낸 「가상…」 뿐이다.
"""

import copy
import json
import sys
from datetime import date
from pathlib import Path
from typing import Any, cast

from esgapi.core.flows.run import run_flow
from esgapi.core.llm.providers.mock import MockProvider
from esgapi.core.llm.providers.openai import OpenAIProvider
from esgapi.core.llm.types import ProviderRequest
from esgapi.materiality.contracts import wire
from esgapi.materiality.flows import colab_155
from esgapi.materiality.tests.contracts import test_wire_window as cases
from esgapi.materiality.tests.flows import support

NARROW_OUT = "2024-12-31"
"""창(2025-01-01~2025-06-30) 하루 밖 — 컨트로버시 항목 둘째의 날짜."""


def body(request: ProviderRequest) -> bytes:
    return json.dumps(OpenAIProvider().build_request(request), ensure_ascii=False, sort_keys=True).encode()


def iro_requests(received: dict[str, Any], days: tuple[str | None, ...]) -> list[ProviderRequest]:
    mock = MockProvider("openai")
    support.script_iro(mock, received, controversy_days=days)
    support.run_iro(support.iro_inputs(received), support.spy2(mock))
    return mock.calls


def part1_alone(received: dict[str, Any], days: tuple[str | None, ...]) -> tuple[list[ProviderRequest], dict[str, Any]]:
    mock = MockProvider("openai")
    support.script_part1_dated(mock, received, controversy_days=days)
    done = run_flow(
        colab_155.FLOW,
        colab_155.MaterialityInputs(
            received=received, tags=support.TAGS, max_cost_usd=support.COST, **support.PART1_CODE
        ),
        colab_155.MaterialityAdapters(llm=support.spy2(mock)),
    )
    return mock.calls, dict(support.result(done))


def part2_alone(received: dict[str, Any], part1: dict[str, Any]) -> list[ProviderRequest]:
    mock = MockProvider("openai")
    support.script_part2(mock)
    support.run2(support.inputs2(received, part1=part1), support.spy2(mock))
    return mock.calls


def hand_filtered(part1: dict[str, Any], out_day: str) -> dict[str, Any]:
    """손 거름: 지어낸 답의 꼴(컨트로버시 results.items)에서 날짜가 out_day 인 항목만 뺀 사본."""
    out = copy.deepcopy(part1)
    for t in out["part1"]["topics"]:
        items = t["controversy"]["parsed"]["results"]["items"]
        t["controversy"]["parsed"]["results"]["items"] = [i for i in items if i["date"] != out_day]
    return out


def diff(name: str, ours: list[ProviderRequest], theirs: list[ProviderRequest]) -> int:
    a, b = [body(r) for r in ours], [body(r) for r in theirs]
    n = abs(len(a) - len(b)) + sum(1 for x, y in zip(a, b, strict=False) if x != y)
    print(f"  {name}: 새 흐름 {len(a)} · 견줄 것 {len(b)} · 다름 {n}")
    return n


def compare() -> int:
    received = support.received2()
    wide = (support.IN_RANGE,)
    ours = iro_requests(received, wide)
    alone, part1 = part1_alone(received, wide)
    part1_same = diff("① 1부 요청", ours[:5], alone)
    part2_same = diff("② 2부 요청(창이 다 덮음)", ours[5:], part2_alone(received, part1))
    narrow = (support.IN_RANGE, NARROW_OUT)
    ours = iro_requests(received, narrow)
    alone, part1 = part1_alone(received, narrow)
    part1_same += diff("① 1부 요청(창을 좁힘)", ours[:5], alone)
    part2_same += diff(
        "③ 2부 요청(창을 좁힘 — 손 거름 씨앗)", ours[5:], part2_alone(received, hand_filtered(part1, NARROW_OUT))
    )
    leaked = sum(1 for r in ours[5:] if "가상 사건 2" in body(r).decode())
    print(f"  ③ 2부 요청에 남은 기간 밖 항목 {leaked}")
    part2_same += leaked
    print(f"PART1_SAME={part1_same} PART2_SAME={part2_same}")
    return int(part1_same != 0 or part2_same != 0)


ONE_ITEM: list[tuple[str, dict[str, Any], bool, str | None]] = [
    ("regulation", {"publish_date": "2025-01-01"}, True, None),
    ("regulation", {"publish_date": "2024-12-31"}, False, "items_out_of_range"),
    ("regulation", {"publish_date": "2025-06-30"}, True, None),
    ("regulation", {"publish_date": "2025-07-01"}, False, "items_out_of_range"),
    ("regulation", {"publish_date": "2024-06-01", "event_date": "2025-03-01"}, False, "items_out_of_range"),
    ("regulation", {"publish_date": None, "event_date": "2025-03-01"}, True, None),
    ("regulation", {"publish_date": None, "event_date": None}, True, "item_date_unreadable"),
    ("regulation", {"publish_date": "2024-03"}, True, "item_date_unreadable"),
    ("controversy", {"date": "2025-03-01"}, True, None),
    ("controversy", {"date": "2020-01-01"}, False, "items_out_of_range"),
    ("controversy", {"date": "2025"}, True, "item_date_unreadable"),
    ("controversy", {"date": None}, True, "item_date_unreadable"),
]
"""S2 한 항목 표: (쪽, 날짜 칸, 남는가, 경고 코드) — 창 2025-01-01~2025-06-30."""


def one_item(side: str, dates: dict[str, Any]) -> tuple[bool, str | None]:
    item = {"title": "가상 항목", **dates}
    done: dict[str, Any] = {"status": "done", "parsed": {}, "items": [], "selfCheck": None, "topicNameMismatch": False}
    not_run: dict[str, Any] = {"status": "not_run", "message": "가상"}
    reg: dict[str, Any]
    con: dict[str, Any]
    if side == "regulation":
        reg, con = {**done, "parsed": {"results": {"KR": [item]}}}, not_run
    else:
        reg, con = not_run, {**done, "parsed": {"results": {"items": [item]}}}
    topic = {"topic": "가상", "description": "가상", "keywordStr": "가상", "regulation": reg, "controversy": con}
    result: dict[str, Any] = {"schemaVersion": "materiality.result@1", "part1": {"topics": [topic]}, "warnings": []}
    got, warnings = wire.part1_in_window(result, date(2025, 1, 1), date(2025, 6, 30))
    parsed = got["part1"]["topics"][0][side]["parsed"]
    kept = (parsed["results"]["KR"] if side == "regulation" else parsed["results"]["items"]) != []
    return kept, (warnings[0]["code"] if warnings else None)


def window(out: Path) -> int:
    rows = ["무엇\t입력\t기대\t실제\t맞음"]
    right = total = 0
    for text, expected in cases.WINDOW_RANGE_CASES:
        got = wire.parse_date_range(text, cases.TODAY)
        rows.append(f"dateRange\t{text!r}\t{expected}\t{got}\t{got == expected}")
        right, total = right + (got == expected), total + 1
    for value, expected_day in cases.WINDOW_ITEM_CASES:
        got_day = wire.item_date(value)
        rows.append(f"항목 날짜\t{value!r}\t{expected_day}\t{got_day}\t{got_day == expected_day}")
        right, total = right + (got_day == expected_day), total + 1
    for side, dates, kept, code in ONE_ITEM:
        got_item = one_item(side, dates)
        ok = got_item == (kept, code)
        rows.append(f"거르기 {side}\t{json.dumps(dates, ensure_ascii=False)}\t{(kept, code)}\t{got_item}\t{ok}")
        right, total = right + ok, total + 1
    (out / "window-cases.tsv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"  표 {out / 'window-cases.tsv'}")
    print(f"WINDOW_CASES={right}/{total}")
    return int(right != total)


if __name__ == "__main__":
    mode, out_dir = sys.argv[1], Path(sys.argv[2])
    out_dir.mkdir(parents=True, exist_ok=True)
    sys.exit(compare() if mode == "compare" else window(out_dir) if mode == "window" else cast("int", 2))
