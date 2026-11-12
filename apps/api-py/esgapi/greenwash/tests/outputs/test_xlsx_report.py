"""엑셀의 확정본(xlsx.build 의 adopted — 밴드 G1b-2a §2-1, MARC-ENT-356). 순수 층(DB 없음).

잰다: adopted 기본값이면 지금 build 와 같은 칸 값 · 확정본 「문장」 줄 수 = 채택 수(차례 그대로) · 「요약」 다시 셈(빈
파트 0 줄 포함, 두 파트에 든 문장은 둘 다) · 「설정」 끝의 판 줄 · 채택 0 이면 「문장」은 머리만 · 점검 페이지·실패한
페이지·단어 빈도는 결과 그대로. 결과는 계약 예시(지어낸 것)다.
"""

import io
import json
from pathlib import Path
from typing import Any

from openpyxl import load_workbook

from esgapi.greenwash.flows.colab_e0 import frequency_extras
from esgapi.greenwash.outputs import xlsx

EXAMPLES = Path(__file__).resolve().parents[1] / "data" / "contract-examples"


def example(name: str) -> dict[str, Any]:
    body: dict[str, Any] = json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))
    return body


def read(content: bytes) -> dict[str, list[tuple[Any, ...]]]:
    book = load_workbook(io.BytesIO(content), read_only=True)
    return {name: [tuple(row) for row in book[name].iter_rows(values_only=True)] for name in book.sheetnames}


def build(result: dict[str, Any], adopted: set[int] | None = None) -> dict[str, list[tuple[Any, ...]]]:
    return read(xlsx.build(result, added_terms=frequency_extras(result["extraTerms"]), adopted=adopted))


def test_the_default_is_the_flow_workbook() -> None:
    result = example("result-normal")
    default = read(xlsx.build(result, added_terms=frequency_extras(result["extraTerms"])))
    assert build(result, None) == default
    assert len(default["문장"]) - 1 == len(result["items"]) == 4
    assert all(row[0] != "판" for row in default["설정"])  # 판 줄은 확정본만


def test_the_confirmed_workbook_holds_only_the_adopted_sentences() -> None:
    result = example("result-normal")
    full = build(result)
    confirmed = build(result, {3, 0})
    assert confirmed["문장"][0] == xlsx.SENTENCE_HEADER
    assert confirmed["문장"][1:] == [full["문장"][1], full["문장"][4]]  # itemIndex 0·3, 결과 차례 그대로
    assert confirmed["단어 빈도"] == full["단어 빈도"]
    assert confirmed["설정"][:-1] == full["설정"]
    assert confirmed["설정"][-1] == ("판", "확정본 — 채택 2 / 전체 4")


def test_the_confirmed_summary_is_recounted_over_every_part() -> None:
    """result-normal: 0 CEO High · 1 CEO Mid · 2 회사소개+기후 Mid · 3 기후 Low.
    채택 {2} 면 CEO 메시지는 빈 파트로 0 줄."""
    result = example("result-normal")
    summary = dict(build(result, {2})["요약"][1:])
    assert (summary["등급 High"], summary["등급 Mid"], summary["등급 Low"]) == (0, 1, 0)
    assert [summary[f"CEO 메시지 · {level}"] for level in xlsx.LEVELS] == [0, 0, 0]  # 빈 파트도 줄이 있다
    assert [summary[f"회사소개 · {level}"] for level in xlsx.LEVELS] == [0, 1, 0]
    assert [summary[f"기후/환경 토픽 · {level}"] for level in xlsx.LEVELS] == [0, 1, 0]  # 두 파트 문장은 둘 다
    assert summary["전체 문장 수"] == 1
    full = dict(build(result)["요약"][1:])
    assert (summary["점검 페이지 수"], summary["인식 실패 페이지 수"]) == (
        full["점검 페이지 수"],
        full["인식 실패 페이지 수"],
    )


def test_the_summary_part_rows_follow_the_result_parts() -> None:
    result = example("result-normal")
    names = [p["name"] for p in result["parts"]]
    rows = [name for name, _ in build(result, {0, 1, 2, 3})["요약"][1:] if " · " in name]
    assert list(dict.fromkeys(row.split(" · ")[0] for row in rows)) == names


def test_all_adopted_is_the_full_count() -> None:
    result = example("result-many")
    every = set(range(len(result["items"])))
    full, confirmed = build(result), build(result, every)
    assert confirmed["문장"] == full["문장"]
    assert confirmed["요약"] == full["요약"]


def test_nothing_adopted_leaves_the_header_only() -> None:
    result = example("result-normal")
    confirmed = build(result, set())
    assert confirmed["문장"] == [xlsx.SENTENCE_HEADER]
    summary = dict(confirmed["요약"][1:])
    assert summary["전체 문장 수"] == 0
    assert confirmed["설정"][-1] == ("판", "확정본 — 채택 0 / 전체 4")
