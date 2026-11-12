"""EDK 인벤토리 엑셀 읽개(tools/edk_xlsx.py)의 순수성(밴드 DVX1 — materiality/tests/tools/
test_value_chain_xlsx_purity.py 를 옮겨 적음): 남이 준 xlsx 를 여는 제품 파일이라 디스크에 풀거나 쓰지 않는다 —
extractall·extract·파일 open·tempfile·os·shutil·pathlib 0 을 AST 로 단언(inventory/tests/test_s3sheets_is_pure.py 가
xlsx_reader 에 거는 단언과 같은 꼴). 상태 없음은 업무 시험이 DB·저장소 수로도 잰다. `archive.open(이름)` 은 zip 항목을
메모리로 푸는 것이라 받는다 — 맨 `open(…)` 만 막는다."""

import ast
from pathlib import Path

from esgapi.dataverify.tools import edk_xlsx

PATH = Path(edk_xlsx.__file__)
FORBIDDEN_MODULES = {"os", "shutil", "tempfile", "pathlib", "io.open", "builtins"}
FORBIDDEN_NAMES = {"open", "mkstemp", "NamedTemporaryFile"}
FORBIDDEN_METHODS = {"extractall", "extract", "write_bytes", "write_text", "mkstemp", "NamedTemporaryFile"}


def tree() -> ast.Module:
    return ast.parse(PATH.read_text(encoding="utf-8"))


def imported(module: ast.Module) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module)
    return names


def called(module: ast.Module) -> tuple[set[str], set[str]]:
    """(맨 이름으로 부른 것, 속성으로 부른 것)."""
    names: set[str] = set()
    methods: set[str] = set()
    for node in ast.walk(module):
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                names.add(node.func.id)
            elif isinstance(node.func, ast.Attribute):
                methods.add(node.func.attr)
    return names, methods


def test_the_reader_imports_no_file_system_module() -> None:
    modules = imported(tree())
    assert {"zipfile", "xml.parsers.expat", "openpyxl"} <= modules  # 빈 집합으로 통과하지 않게
    assert not {m for m in modules if m.split(".")[0] in FORBIDDEN_MODULES or m in FORBIDDEN_MODULES}


def test_the_reader_never_extracts_or_opens_a_file() -> None:
    names, methods = called(tree())
    assert "load_workbook" in names and "ZipFile" in methods  # 이 검사가 빈 집합으로 통과하지 않게
    assert names & FORBIDDEN_NAMES == set()
    assert methods & FORBIDDEN_METHODS == set()
    source = PATH.read_text(encoding="utf-8")
    assert "extractall" not in source and ".extract(" not in source


def test_the_reader_opens_the_workbook_read_only_with_values() -> None:
    """load_workbook 부름은 하나이고 read_only=True·data_only=True 다(read_only=False 면 트리를 다 짓는다)."""
    calls = [
        node
        for node in ast.walk(tree())
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "load_workbook"
    ]
    assert len(calls) == 1
    flags = {k.arg: k.value.value for k in calls[0].keywords if isinstance(k.value, ast.Constant)}
    assert flags == {"read_only": True, "data_only": True}
