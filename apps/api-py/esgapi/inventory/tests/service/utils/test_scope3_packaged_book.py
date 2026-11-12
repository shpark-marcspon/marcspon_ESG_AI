"""패키지 계수 책(data/scope3/scope3-factor-book.xlsx — 받은 책 v1.1 의 Scope 3 열, 밴드 S3V1 · MARC-ENT-641)의 꼴.

책 값은 견본으로 단언하지 않는다 — 꼴·집합·같음만(시트 이름 집합 · 사람 칸 빔 · 원화 칸이 수 · 엔진 읽기 표 · 저장 값).
Q9: 책 v1.1 의 새 「탄소기원구분」 열은 엔진이 읽지 않는다(MARC-ENT-442 — 엔진은 코랩 규칙으로 나눈다).
그 열과 엔진 규칙이 갈리는 줄은 알려진 목록뿐이어야 한다(늘면 빨강). 목록의 낱말은 책의 공개 분류어다.
"""

import io
import re
import zipfile
from functools import cache

import pandas as pd

from esgapi.inventory.engines.scope3.colab_157 import factor_book as fb
from esgapi.inventory.engines.scope3.colab_157.constants import BIOGENIC_WASTE_FCF
from esgapi.inventory.engines.scope3.colab_157.product import biogenic_group_from_code
from esgapi.inventory.engines.scope3.colab_157.waste import (
    biogenic_group_from_name,
    lookup_waste_ef,
    normalize_treatment,
)
from esgapi.inventory.flows.binding_157 import FileMissing
from esgapi.inventory.service.utils import scope3_files
from esgapi.inventory.tools.scope3_sheets.grid import FormulaCell, NumberCell, Workbook
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

SHEETS = (
    "에너지",
    "에너지_C3",
    "운송",
    "출장_통근",
    "폐기물_C5",
    "폐기물_C12",
    "구매_USEPA",
    "운송_Spend",
    "출장_Spend",
    "전력_국가별",
)
"""Scope 3 열 10시트(받은 책의 Scope 1·2 열 — 환율_참조·이동연소 … — 은 걷음, 옛 책의 「목록」 없음)."""

ENGINE_READS = {
    "에너지": ("reloaded", 3),
    "에너지_C3": ("initial", 2),
    "운송": ("reloaded", 1),
    "출장_통근": ("initial", 1),
    "폐기물_C5": ("reloaded", 2),
    "폐기물_C12": ("reloaded", 1),
    "운송_Spend": ("reloaded", 2),
    "출장_Spend": ("reloaded", 2),
}
"""엔진 읽개의 (how, 머리 줄) — 옛 책(밴드 S3K1)과 같다(S3V1 ★E)."""

ORIGIN_WORD = "탄소기원구분"
FCF_WORD = "FCF"
BIOGENIC = "생물"
KNOWN_C5_DIFFERENCES = frozenset({("폐지류", "기타"), ("폐목재류", "기타")})
"""책은 「생물」, 엔진은 소각만 나눔(waste.py — 처리방법 「기타」 는 나누지 않음). S3V1 Q9 — 이슈로 올림."""


def packaged() -> bytes:
    content = scope3_files.FACTOR_BOOK.read()
    assert not isinstance(content, FileMissing)
    return content


@cache
def book() -> Workbook:
    found = read_workbook(packaged())
    assert not isinstance(found, ReaderProblem)
    return found


def part(name: str) -> str:
    with zipfile.ZipFile(io.BytesIO(packaged())) as archive:
        return archive.read(name).decode()


def first_line_columns(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    out.columns = pd.Index([str(c).splitlines()[0].strip() for c in frame.columns])
    return out


def test_the_book_has_the_scope3_sheets_only() -> None:
    assert tuple(s.name for s in book().sheets) == SHEETS
    assert book().defined_names == ()


def test_the_person_cells_are_empty() -> None:
    """MARC-ENT-521 꼴: 문서 속성 lastModifiedBy 와 workbook absPath url 은 빈 글자(요소는 남김)."""
    assert re.findall(r"<cp:lastModifiedBy>([^<]*)</cp:lastModifiedBy>", part("docProps/core.xml")) == [""]
    assert re.findall(r'<x15ac:absPath url="([^"]*)"', part("xl/workbook.xml")) == [""]


def test_the_other_name_parts_hold_no_person() -> None:
    """이름이 실리는 다른 부품: app.xml 제목은 시트 이름뿐, 메모 작성자는 받은 그대로의 「Unknown Author」 뿐,
    문서 속성은 openpyxl 이 적은 creator 와 받은 그대로의 요소뿐(제목·키워드 같은 칸 없음)."""
    titles = re.findall(r"<vt:lpstr>([^<]*)</vt:lpstr>", part("docProps/app.xml"))
    assert titles == ["워크시트", *SHEETS]
    with zipfile.ZipFile(io.BytesIO(packaged())) as archive:
        comments = [n for n in archive.namelist() if n.startswith("xl/comments")]
    assert len(comments) > 0
    authors = {a for n in comments for a in re.findall(r"<author>([^<]*)</author>", part(n))}
    assert authors == {"Unknown Author"}
    core = part("docProps/core.xml")
    assert re.findall(r"<dc:creator>([^<]*)</dc:creator>", core) == ["openpyxl"]
    inner = core[core.index("<cp:coreProperties") :]
    tags = set(re.findall(r"<((?:cp|dc|dcterms):\w+)", inner)) - {"cp:coreProperties"}
    assert tags == {
        "dc:creator",
        "cp:lastModifiedBy",
        "cp:revision",
        "dcterms:created",
        "dcterms:modified",
        "dc:language",
    }


def test_the_c3_sheet_keeps_the_city_gas_nm3_row() -> None:
    """결정 MARC-ENT-654(감독 — 마크스폰 답 MARC-ENT-649 전까지 임시): v1.1 은 「도시가스(LNG)」 Nm³ 줄을 뺐지만
    앱 책은 v1.0 의 그 한 줄을 남긴다 — 빼면 Nm³ 입력이 kg 계수에 발열량 다리 없이 걸린다(단위 어긋남).
    남은 줄의 이름은 모두 다르다."""
    frame = first_line_columns(fb.read_energy_c3_sheet(book()).frame)
    names = [str(n).strip() for n in frame["활동유형"]]
    assert len(names) == len(set(names))
    row = frame[frame["활동유형"].astype(str).str.strip() == "도시가스(LNG)"]
    assert len(row) == 1
    assert str(row.iloc[0]["기준단위"]).strip() == "Nm³"


def test_the_krw_columns_of_the_spend_sheets_are_numbers() -> None:
    """책 v1.1 의 운송_Spend·출장_Spend 원화 열(H~J)은 수식이 아니라 수다 — 줄마다 셋 다."""
    for name in ("운송_Spend", "출장_Spend"):
        sheet = next(s for s in book().sheets if s.name == name)
        rows = fb.read_factor_sheet(book(), name).frame
        assert len(rows) > 0
        for row in range(4, 4 + len(rows)):
            cells = [sheet.cells.get(f"{col}{row}") for col in "HIJ"]
            assert all(isinstance(c, NumberCell) for c in cells), (name, row)


def test_the_purchase_sheet_keeps_its_saved_values() -> None:
    """구매_USEPA 원화 열은 수식 칸이고 엑셀 저장 값이 있다(다시 저장하면 사라짐 — S3V1 Q1).
    엔진이 연도마다 줄 전부에서 계수를 읽는다."""
    sheet = next(s for s in book().sheets if s.name == "구매_USEPA")
    formulas = [c for c in sheet.cells.values() if isinstance(c, FormulaCell)]
    assert len(formulas) > 0
    assert all(isinstance(c.cached, NumberCell) for c in formulas)
    counts: set[int] = set()
    for year in (2023, 2024, 2025):
        db = fb.load_purchase_usepa_as_krw_spend_db(book(), year)
        assert db.frame["ef"].notna().all()
        counts.add(len(db.frame))
    assert len(counts) == 1


def test_the_engine_reads_the_sheets_as_before() -> None:
    reads = {
        "에너지": fb.read_energy_sheet(book()),
        "에너지_C3": fb.read_energy_c3_sheet(book()),
        "폐기물_C12": fb.read_waste_c12_sheet(book()),
        **{name: fb.read_factor_sheet(book(), name) for name in fb.AUTO_HEADER_WORDS},
        "출장_통근": fb.read_initial_factor_sheet(book(), "출장_통근"),
    }
    assert {name: (r.how, r.header) for name, r in reads.items()} == ENGINE_READS
    assert all(len(r.frame) > 0 for r in reads.values())


def test_the_waste_factor_columns_are_the_first_factor_columns() -> None:
    """새 열(생물·화석 계수)은 뒤에 붙었다 — 엔진이 고르는 첫 「배출계수」(C5)·「매립 EF」(C12) 열이 그 앞이다."""
    c5 = list(fb.read_factor_sheet(book(), "폐기물_C5").frame.columns)
    c12 = list(fb.read_waste_c12_sheet(book()).frame.columns)
    origin_c5 = next(i for i, c in enumerate(c5) if ORIGIN_WORD in c)
    origin_c12 = next(i for i, c in enumerate(c12) if ORIGIN_WORD in c)
    assert next(i for i, c in enumerate(c5) if "배출계수" in c) < origin_c5
    assert next(i for i, c in enumerate(c12) if "매립 EF" in c) < origin_c12


def test_the_c5_lookup_takes_the_first_factor_column() -> None:
    """엔진 C5 찾기(waste.py)는 첫 「배출계수」 열(F)을 쓴다 — v1.1 은 그 뒤에 「생물기원 CO2 배출계수」·
    「화석기원 CO2eq 배출계수」 열을 더했다. 줄마다 (종류, 처리방법) 의 첫 줄 F 값과 같고,
    뒤 열 값과 갈리는 줄이 있다(고름이 재짐)."""
    frame = fb.read_factor_sheet(book(), "폐기물_C5").frame
    columns = [c for c in frame.columns if "배출계수" in c]
    first, later = columns[0], columns[1:]
    assert len(later) == 2
    seen: set[tuple[str, str]] = set()
    differs = 0
    for _, row in frame.iterrows():
        key = (str(row[frame.columns[0]]).strip(), str(row[frame.columns[1]]).strip())
        if key in seen:
            continue
        seen.add(key)
        found = lookup_waste_ef(frame, *key)
        assert (found.via, found.value) == ("exact", float(row[first])), key
        differs += any(float(row[c]) != float(row[first]) for c in later)
    assert len(seen) > 0
    assert differs > 0


def c5_differences() -> set[tuple[str, str]]:
    frame = first_line_columns(fb.read_factor_sheet(book(), "폐기물_C5").frame)
    assert len(frame) > 0
    out: set[tuple[str, str]] = set()
    for _, row in frame.iterrows():
        name, treatment = str(row["폐기물 종류"]).strip(), str(row["처리방법"]).strip()
        group = biogenic_group_from_name(name) if normalize_treatment(treatment) == "소각" else None
        book_bio = str(row[ORIGIN_WORD]).strip() == BIOGENIC
        if (group is not None) != book_bio:
            out.add((name, treatment))
        elif group is not None:
            assert float(row[FCF_WORD]) == BIOGENIC_WASTE_FCF[group] * 100, (name, treatment)
    return out


def test_the_c5_origin_column_matches_the_engine_rule_but_the_known_rows() -> None:
    assert c5_differences() == KNOWN_C5_DIFFERENCES


def test_the_c12_origin_column_matches_the_engine_rule() -> None:
    """C12 엔진은 코드(소분류 → 중분류) 접두로 나눈다(product.py). 책 열과 줄마다 같고, 생물 줄의 FCF(%) 도 같다."""
    frame = first_line_columns(fb.read_waste_c12_sheet(book()).frame)
    assert len(frame) > 0
    bio_rows = 0
    for _, row in frame.iterrows():
        sub, mid = (str(row[k]).strip() if pd.notna(row[k]) else "" for k in ("소분류", "중분류"))
        group = biogenic_group_from_code(sub or mid) if (sub or mid) else None
        book_bio = str(row[ORIGIN_WORD]).strip() == BIOGENIC
        assert (group is not None) == book_bio, (sub, mid)
        if group is not None:
            bio_rows += 1
            assert float(row[FCF_WORD]) == BIOGENIC_WASTE_FCF[group] * 100, (sub, mid)
    assert bio_rows > 0
