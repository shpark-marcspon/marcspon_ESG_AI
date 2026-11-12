"""지은 문서 골든: 저장소에 둔 TS 덤프(`golden/synthetic/ts-dump.json`)와 파이썬의 덤프가 **값 전체 일치**하는가.

컨테이너도 esg-lab 도 없이 돈다. main 의 `verify.sh` 가 되재는 골든은 이것뿐이다.
★ 무효 조건: 네 보고서(값 후보 8,773)의 일치는 `check_lab.py` 를 돌린 그날 esg-lab 의 git 밖 산출에 대해서만 잰 것이고
  여기서는 되재지 않는다. 네 보고서에는 언어 차이를 드러낼 글자가 0 이라 그쪽의 「같다」는 이 지은 문서 하나에 기댄다.
  문서와 숫자는 전부 지어낸 것이다(synthetic).

구획: facts · nonValues · grids · failed · kinds · count · masks + dec · notation. 여덟째 `places`(상자)는
`test_places.py`.
"""

import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.reconcile.tests.golden import dump

GOLDEN = Path(__file__).resolve().parent / "golden"
SYNTHETIC = GOLDEN / "synthetic"
Json = Any


def load(path: Path) -> Json:
    return json.loads(path.read_text(encoding="utf-8"))


TS = load(SYNTHETIC / "ts-dump.json")


def python_dump() -> dict[str, Json]:
    """파이썬의 덤프. 모듈을 읽을 때가 아니라 테스트 안에서 낸다(규칙이 망가져도 다른 파일의 수집을 막지 않게).
    부를 때마다 새로 낸다 — 캐시하면 mutmut 이 변이를 켜기 전에 한 번 굳어 어느 변이에서도 원본을 본다(MARC-ISSUE-154).
    """
    return {
        **dump.dump_document(load(SYNTHETIC / "document.json"), "synthetic"),
        **dump.dump_cases(load(SYNTHETIC / "cases.json")),
    }


SECTIONS = (*dump.SECTIONS, *dump.CASE_SECTIONS)


@pytest.mark.parametrize("section", SECTIONS)
def test_python_equals_the_committed_ts_dump(section: str) -> None:
    assert dump.first_difference(TS[section], python_dump()[section], section) is None


def test_the_sections_are_not_empty_and_match_the_digest() -> None:
    py = python_dump()
    sizes = {section: dump.size(section, py[section]) for section in SECTIONS}
    assert sizes == {
        "facts": 99,
        "nonValues": 62,
        "grids": 4,
        "failed": 2,
        "kinds": 99,
        "count": 99,
        "masks": 128,
        "dec": 34,
        "notation": 400,
    }
    digest = load(GOLDEN / "lab-digest.json")["synthetic"]["sections"]
    assert digest == {s: {"count": sizes[s], "sha256": dump.digest(py[s])} for s in SECTIONS}
    assert digest == {s: {"count": sizes[s], "sha256": dump.digest(TS[s])} for s in SECTIONS}


def test_the_language_difference_examples_are_in_the_document() -> None:
    """발주서의 「언어 차이 본보기」 ①~⑧ 이 지은 문서에 실제로 들어 있다(누가 빼면 여기서 빨개진다)."""
    document = load(SYNTHETIC / "document.json")
    text = "\n".join(block.get("text", "") for block in document["blocks"])
    cells = [cell for table in document["tables"] for row in table["cells"] for cell in row]
    everything = text + "\n" + "\n".join(cells)
    for needle in ("3위 ", "3위A", "2기 ", "2기B", "4종"):  # ①
        assert needle in everything
    assert "١٢٣" in everything  # ② 아랍-인도 숫자
    assert "１２３" in everything  # ② 전각 숫자
    for point in ("﻿", "\u0085", "\u001c", " ", " "):  # ③ ⑤
        assert point in everything
    assert any(cell.endswith("\n") for cell in cells)  # ④ 칸 글 끝의 줄바꿈
    assert ".\n7" in text  # ④ 종류 규칙이 보는 블록 원문
    assert any(ord(ch) > 0xFFFF for ch in everything)  # ⑥ 보충 평면 글자
    assert {"N/A", "Ｎ／Ａ", "n/a"} <= set(cells)  # ⑦
    lefts = [block["bbox"][0] for block in document["blocks"] if block["id"] in ("p1-b10", "p1-b11", "p1-b12")]
    assert lefts == [101.0, 102.0, 102.4]  # ⑧ 101.0 / 2 = 50.5


def test_what_the_examples_come_out_as() -> None:
    """본보기가 TS 에서 무엇으로 나왔는지 적어 둔다(뜻을 읽을 수 있게. 값은 TS 덤프의 것이다)."""
    kinds = TS["kinds"]
    # ⑧ 세로줄: 셋이 한 줄이라 눈금이다.
    assert [kinds["p1-b10#n1"], kinds["p1-b11#n1"], kinds["p1-b12#n1"]] == ["scale", "scale", "scale"]
    # ④ `.\n` 뒤의 숫자는 「글 끝에 홀로 붙은 쪽 번호」가 아니다. `. ` 뒤는 그렇다.
    assert (kinds["p1-b6#n1"], kinds["p1-b7#n1"]) == ("value", "identifier")
    by_block: dict[str, list[tuple[str, str]]] = {}
    for item in TS["nonValues"]:
        by_block.setdefault(item["where"]["blockId"] or "", []).append((item["raw"], item["class"]))
    # ① `3위A`·`2기B` 만 순번이다.
    assert ("3", "ordinal") in by_block["p1-b2"]
    assert by_block["p1-b2"].count(("2", "ordinal")) == 2  # `2단계` 와 `2기B`
    # ⑥ 이모지 뒤의 숫자: 자리는 UTF-16.
    first = next(fact for fact in TS["facts"] if fact["id"] == "p1-b5#n1")
    assert (first["raw"], first["where"]["span"]["start"], first["where"]["span"]["end"]) == ("+7.5%", 6, 11)
    # ② 글 속의 아랍-인도 숫자·전각 숫자는 숫자 덩어리가 아니다.
    assert [fact["raw"] for fact in TS["facts"] if fact["where"]["blockId"] == "p1-b3"] == ["45", "7", "8"]
