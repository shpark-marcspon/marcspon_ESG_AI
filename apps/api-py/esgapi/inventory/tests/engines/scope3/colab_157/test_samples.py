"""표본 지킴이: 이 판 시험의 지어낸 시트에서 이름 칸(국가·사업장·품목·자산·거래처)은 전부 `가상` 으로 시작한다.

받은 자료·실제 기업 이름을 시험에 넣지 않는다(발주서 §1-3, `test_s3sheets_samples.py` 꼴). 머리글 줄에서 이름 칸을 찾고
그 아래 글 칸을 본다. 수는 지어낸 것(`9` 로 시작)만 쓴다.
표본은 `test_frames.CASES`(템플릿 시험의 `C1_ROWS` 포함)·`test_factor_book.SAMPLES`·`test_purchase.SAMPLES`(S1 — 시트
갈래 시험 test_pipeline 도 이 줄을 쓴다)·`support.ACTIVITY_SAMPLES`(S3C-b1 ② 지출·폐기물 시트 넷과 계수 시트 셋 —
test_pipeline·결과 꼴 시험이 쓴다)다.
"""

from esgapi.inventory.engines.scope3.colab_157.frames import read_frame
from esgapi.inventory.tests.engines.scope3.colab_157 import test_factor_book, test_frames, test_purchase
from esgapi.inventory.tests.engines.scope3.colab_157.support import ACTIVITY_SAMPLES
from esgapi.inventory.tools.scope3_sheets.grid import NumberCell, Sheet

NAME_HEADERS = ("국가", "사업장", "품목명", "자산명", "거래처명")


def name_values(sheet: Sheet) -> list[str]:
    frame = read_frame(sheet, header=None)
    values: list[str] = []
    for i in range(len(frame)):
        row = [str(v).lstrip("*") for v in frame.iloc[i].tolist()]
        columns = [j for j, v in enumerate(row) if any(h in v for h in NAME_HEADERS)]
        if not columns:
            continue
        for k in range(i + 1, len(frame)):
            cells = frame.iloc[k].tolist()
            values += [str(cells[j]) for j in columns if isinstance(cells[j], str)]
        break
    return values


def samples() -> list[Sheet]:
    return [*test_frames.CASES.values(), *test_factor_book.SAMPLES, *test_purchase.SAMPLES, *ACTIVITY_SAMPLES]


def test_every_name_cell_starts_with_gasang() -> None:
    names = [value for sheet in samples() for value in name_values(sheet)]
    assert len(names) >= 5  # 분모: 이름 칸을 실제로 본다
    assert [v for v in names if not v.startswith("가상")] == []


def test_every_number_starts_with_nine() -> None:
    numbers = [
        cell.xml_text.lstrip("-")
        for sheet in samples()
        for cell in sheet.cells.values()
        if isinstance(cell, NumberCell)
    ]
    assert len(numbers) >= 5
    assert [n for n in numbers if not n.startswith(("9", "0.9"))] == []
