"""C6 — 구조 관계(structure.py)를 손셈과 견주고, 순수 세 파일(contract·view·structure)의 import 를 본다. 순수 층."""

import ast
import sys
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.documents.contract import RELATIONS
from esgapi.core.documents.structure import Structure
from esgapi.core.tests.artifact_fakes import block, fake_document, section, table

DOCUMENTS = Path(__file__).resolve().parents[2] / "documents"
PURE = ("contract", "view", "structure")
SHA = "c" * 64


def sample() -> dict[str, Any]:
    """두 쪽: 1쪽 머리글·제목·문단·표·꼬리말, 2쪽 문단 둘(목록 차례를 일부러 섞음)."""
    return fake_document(
        SHA,
        page_count=2,
        sections=[
            section("s1", "가상 환경", level=1),
            section("s2", "가상 물 관리", level=2),
            section("s3", "가상 사회", level=1, page_start=2, page_end=2),
        ],
        blocks=[
            block("p2-b2", "둘째 쪽 끝", page=2, order=2, section_id="s3"),
            block("p1-h", "가상 머리글", order=1, region="header"),
            block("p1-b1", "물 사용 현황", order=2, kind="heading", section_id="s2"),
            block("p1-b2", "가상 사업장은 물을 줄였다.", order=3, section_id="s2"),
            block("p1-b3", order=4, kind="table", table_id="p1-t1", section_id="s2"),
            block("p1-f", "- 1 -", order=5, region="footer"),
            block("p2-b1", "둘째 쪽 처음", page=2, order=1, section_id="s3"),
        ],
        tables=[table("p1-t1", [["구분", "2024", "2025"], ["사용량", "1,200", "1,100"]])],
    )


def test_relation_names_are_the_contract_list() -> None:
    assert RELATIONS == (
        "section_contains",
        "table_contains",
        "cell_row_header",
        "cell_col_header",
        "next_block",
        "title_path",
        "on_page",
    )
    with pytest.raises(ValueError):
        Structure(sample()).relations("near", "p1-b1")


def test_relations_by_hand() -> None:
    s = Structure(sample())
    assert s.relations("section_contains", "s2") == ("p1-b1", "p1-b2", "p1-b3")
    assert s.relations("section_contains", "s3") == ("p2-b1", "p2-b2")
    assert s.relations("table_contains", "p1-t1") == tuple(f"p1-t1:r{r}c{c}" for r in range(2) for c in range(3))
    assert s.relations("cell_row_header", "p1-t1:r1c2") == ("p1-t1:r1c0",)
    assert s.relations("cell_col_header", "p1-t1:r1c2") == ("p1-t1:r0c2",)
    assert s.relations("cell_row_header", "p1-t1:r0c0") == ()  # 자기 자신은 빼다
    # 읽는 차례: 쪽 오름 → order 오름, 본문만(머리글·꼬리말 건너뜀), 쪽을 넘는다
    assert [s.relations("next_block", b) for b in ("p1-b1", "p1-b2", "p1-b3", "p2-b1", "p2-b2", "p1-h")] == [
        ("p1-b2",),
        ("p1-b3",),
        ("p2-b1",),
        ("p2-b2",),
        (),
        (),
    ]
    assert s.relations("title_path", "p1-b2") == ("가상 환경", "가상 물 관리", "물 사용 현황")
    assert s.title_path("p1-b1") == ("가상 환경", "가상 물 관리")  # 제목 자신은 앞 heading 이 아니다
    assert s.title_path("p2-b2") == ("가상 사회",)  # level 1 이 앞 level 1·2 를 닫는다
    assert s.title_path("p1-h") == ()  # 섹션 밖
    assert s.relations("on_page", "p2-b1") == ("2",)
    assert s.relations("on_page", "p1-t1:r0c1") == ("1",)
    assert s.relations("on_page", "없는-id") == ()


def _imports(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text())):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


@pytest.mark.parametrize("name", PURE)
def test_the_pure_files_import_only_the_standard_library(name: str) -> None:
    allowed = {f"esgapi.core.documents.{other}" for other in PURE}
    outside = {
        module
        for module in _imports(DOCUMENTS / f"{name}.py")
        if module not in allowed and module.split(".")[0] not in sys.stdlib_module_names
    }
    assert outside == set()


def test_the_import_check_catches_django(tmp_path: Path) -> None:
    probe = tmp_path / "x.py"
    probe.write_text("from django.db import models\nimport json\n")
    assert {m for m in _imports(probe) if m.split(".")[0] not in sys.stdlib_module_names} == {"django.db"}
