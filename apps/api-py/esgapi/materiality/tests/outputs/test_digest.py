"""outputs/digest.digest(밴드 IR3c §3-1-1): 지어낸 결과 materiality.result@2 넷마다 두 수가 손값과 같고, 최종 엑셀
(final_xlsx.build_final)의 「2-1」·「2-2」 시트 데이터 줄 수와 같다. 2부를 돌리지 않았으면 둘 다 null(시트는 머리뿐)."""

import copy
import io
import json
from pathlib import Path
from typing import Any, cast

import pytest
from openpyxl import load_workbook
from openpyxl.worksheet.worksheet import Worksheet

from esgapi.materiality.contracts import shapes
from esgapi.materiality.contracts.digest_shapes import DIGEST_SHAPE, DIGEST_SHAPES
from esgapi.materiality.outputs import final_xlsx
from esgapi.materiality.outputs.digest import digest

EXAMPLE = Path(__file__).resolve().parents[1] / "data" / "examples" / "result2-sample.json"
FAILED: dict[str, Any] = {
    "status": "failed",
    "raw": None,
    "parseError": None,
    "failure": {"kind": "timeout", "message": "timeout"},
}
FIRST_DATA_ROW = 6  # 두 시트 다 머리가 5행, 데이터는 6행부터(final_xlsx.build_final)


def example() -> dict[str, Any]:
    return cast("dict[str, Any]", json.loads(EXAMPLE.read_text(encoding="utf-8")))


def part2_not_run() -> dict[str, Any]:
    result = example()
    result["part2"] = {"status": "not_run", "message": "가상"}
    return result


def all_done() -> dict[str, Any]:
    """토픽 셋의 서브토픽 모두 첫 서브토픽(impact 1·financial 2·pathway 2 줄, 모두 done)의 사본."""
    result = example()
    first = result["part2"]["topics"][0]["subtopics"][0]
    for topic in result["part2"]["topics"]:
        topic["subtopics"] = [copy.deepcopy(first)]
    return result


def mixed() -> dict[str, Any]:
    """견본 그대로: 토픽 둘은 impact failed·pathway not_run, 토픽 셋은 impact done 0줄·재무 rows 0 이라
    pathway not_run."""
    return example()


def pathway_failed() -> dict[str, Any]:
    """토픽 하나에 서브토픽 둘 — 둘째는 첫째의 사본인데 pathway failed. 토픽 둘·셋은 견본 그대로."""
    result = example()
    subs = result["part2"]["topics"][0]["subtopics"]
    second = copy.deepcopy(subs[0])
    second["name"] = "가상 서브토픽 나"
    second["pathway"] = copy.deepcopy(FAILED)
    subs.append(second)
    return result


CASES = [
    pytest.param(part2_not_run, None, None, id="part2-not-run"),
    pytest.param(all_done, 3, 6, id="all-done"),
    pytest.param(mixed, 1, 2, id="impact-failed-pathway-not-run"),
    pytest.param(pathway_failed, 2, 2, id="pathway-failed-two-subtopics"),
]


def data_rows(sheet: Worksheet) -> int:
    return sum(1 for r in range(FIRST_DATA_ROW, sheet.max_row + 1) if sheet[f"D{r}"].value is not None)


@pytest.mark.parametrize(("make", "impact", "pathway"), CASES)
def test_the_two_counts_are_the_hand_values(make: Any, impact: int | None, pathway: int | None) -> None:
    result = make()
    shapes.RESULT_SHAPES[shapes.RESULT_SHAPE_V2].validate_python(result, strict=True)  # 지어낸 결과도 꼴 안
    got = digest(result)
    DIGEST_SHAPES[DIGEST_SHAPE].validate_python(got, strict=True)
    assert got == {"schemaVersion": "materiality.digest@1", "impactRows": impact, "pathwayRows": pathway}


@pytest.mark.parametrize(("make", "impact", "pathway"), CASES)
def test_the_counts_are_the_final_workbook_rows(make: Any, impact: int | None, pathway: int | None) -> None:
    result = make()
    content, _ = final_xlsx.build_final(result)
    book = load_workbook(io.BytesIO(content))
    soc = cast("Worksheet", book[final_xlsx.SOC_SHEET])
    fin = cast("Worksheet", book[final_xlsx.FIN_SHEET])
    got = digest(result)
    assert (data_rows(soc), data_rows(fin)) == (impact or 0, pathway or 0)
    assert (got["impactRows"], got["pathwayRows"]) == (impact, pathway)


def test_the_result_is_not_touched() -> None:
    result = pathway_failed()
    before = json.dumps(result, ensure_ascii=False, sort_keys=True)
    digest(result)
    assert json.dumps(result, ensure_ascii=False, sort_keys=True) == before
