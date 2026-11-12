"""`tools/scope3_sheets/` 는 순수한가, 그리고 xlsx 를 여는 `tools/xlsx_reader.py` 는 허용한 것만 import 하는가.

`.importlinter` 의 계약 (다)가 `esgapi.inventory.tools` 아래의 django·ninja·psycopg 를 문다. 여기는 그 밖의 것
(파일·zip·XML)까지 폴더의 소스에서 직접 본다. `tools/xlsx_reader.py` 는 zip·XML 을 열어야 해서 금지 목록이 아니라
허용 목록으로 지킨다.
"""

import ast
from pathlib import Path

import pytest

import esgapi.inventory.tools.scope3_sheets as package
from esgapi.inventory.tools import xlsx_reader

FOLDER = Path(package.__file__).parent
OWN = package.__name__
ROOT = FOLDER.parents[len(OWN.split(".")) - 1]  # esgapi 를 담은 폴더
EXPECTED_FILES = {"__init__.py", "grid.py", "factor_layout.py", "factors.py", "dropdowns.py", "crosscheck.py"}
FORBIDDEN = (
    "zipfile",
    "xml",
    "io",
    "os",
    "pathlib",
    "shutil",
    "tempfile",
    "glob",
    "time",
    "datetime",
    "random",
    "socket",
    "urllib",
    "http",
    "subprocess",
    "django",
    "ninja",
    "psycopg",
    "esgapi.reference",
    "esgapi.inventory.tools.xlsx_reader",
    "esgapi.inventory.data_loader",
    "esgapi.inventory.service",
    "esgapi.inventory.api",
    "esgapi.inventory.tests",
)
# 그 폴더가 import 해도 되는 것 전부(앞머리 일치가 아니라 이름까지).
ALLOWED_IN_FOLDER = {
    "re",
    "unicodedata",
    "dataclasses",
    "typing",
    "collections.abc",
    "esgapi.inventory.tools.scope3_sheets.grid",
    "esgapi.inventory.tools.scope3_sheets.factor_layout",
    "esgapi.inventory.tools.scope3_sheets.factors",
    "esgapi.inventory.tools.scope3_sheets.dropdowns",
}
# tools/xlsx_reader.py 의 허용 목록. 발주서 §1-2 의 것(zipfile · xml.etree.ElementTree · decimal · re · dataclasses ·
# typing · grid · esgapi.core.calc.decimal)에 셋을 더했다: io(메모리의 바이트를 zipfile 에 건네는 BytesIO —
# 파일을 열지 않는다), zlib·struct(망가진 zip 이 내는 예외의 이름을 적으려고).
ALLOWED_IN_READER = {
    "zipfile",
    "xml.etree.ElementTree",
    "decimal",
    "re",
    "dataclasses",
    "typing",
    "io",
    "zlib",
    "struct",
    "esgapi.inventory.tools.scope3_sheets.grid",
    "esgapi.core.calc.decimal",
}


def every_node(tree: ast.AST) -> list[ast.AST]:
    """나무의 모든 마디(뿌리 포함)."""
    found: list[ast.AST] = []
    waiting: list[ast.AST] = [tree]
    while waiting:
        node = waiting.pop()
        found.append(node)
        waiting.extend(ast.iter_child_nodes(node))
    return found


def package_of(path: Path) -> str:
    """그 파일의 꾸러미(담은 폴더의 점 이름 — `__init__.py` 면 그 자신). ROOT 밖 파일이면 ValueError."""
    return ".".join(path.parent.relative_to(ROOT).parts)


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def modules_in(source: str, package: str) -> set[str]:
    """절대·상대 import 둘 다(상대는 그 파일의 꾸러미 기준으로 풀어 같은 검사에 넣는다). `from . import x` 는 그
    꾸러미와 `<꾸러미>.x` 둘 다."""
    names: set[str] = set()
    for node in every_node(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolve(node, package)
            names.add(module)
            if node.module is None:
                names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def imported_modules(path: Path) -> set[str]:
    return modules_in(path.read_text(encoding="utf-8"), package_of(path))


def called_names(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    return {node.func.id for node in every_node(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}


def is_forbidden(module: str) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in FORBIDDEN)


def test_the_folder_is_the_six_files_we_think_it_is() -> None:
    assert {path.name for path in FOLDER.glob("*.py")} == EXPECTED_FILES
    assert [path.name for path in FOLDER.iterdir() if path.is_dir() and path.name != "__pycache__"] == []


# 사본에서 뜻이 없다: mutmut 이 심은 트램펄린(mutmut.mutation.trampoline import)을 소스에서 읽는다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_no_module_in_the_folder_imports_files_zip_xml_network_django_or_the_reader() -> None:
    for path in sorted(FOLDER.glob("*.py")):
        modules = imported_modules(path)
        assert sorted(module for module in modules if is_forbidden(module)) == [], path.name
        assert modules <= ALLOWED_IN_FOLDER, f"{path.name}: {sorted(modules - ALLOWED_IN_FOLDER)}"
        assert "open" not in called_names(path), path.name


def test_the_folder_does_not_use_floats() -> None:
    """수는 십진 문자열로만 다닌다. float 는 읽개가 표기를 풀 때 한 번뿐이다(그 파일은 이 폴더 밖이다)."""
    for path in sorted(FOLDER.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        assert [n for n in every_node(tree) if isinstance(n, ast.Constant) and isinstance(n.value, float)] == [], (
            path.name
        )
        assert "float" not in {node.id for node in every_node(tree) if isinstance(node, ast.Name)}, path.name


# 사본에서 뜻이 없다: mutmut 이 심은 트램펄린(mutmut.mutation.trampoline import)을 소스에서 읽는다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_the_reader_imports_only_what_is_on_its_list() -> None:
    path = Path(xlsx_reader.__file__)
    modules = imported_modules(path)
    assert modules <= ALLOWED_IN_READER, sorted(modules - ALLOWED_IN_READER)
    assert {"zipfile", "xml.etree.ElementTree"} <= modules  # 이 검사가 빈 집합으로 통과하지 않게
    assert "open" not in called_names(path)
    source = path.read_text(encoding="utf-8")
    assert "extractall" not in source and ".extract(" not in source


def test_the_reader_is_the_only_product_file_that_imports_zipfile_or_xml() -> None:
    root = Path(xlsx_reader.__file__).parents[2]  # esgapi/
    opening = [
        path.relative_to(root).as_posix()
        for path in sorted(root.rglob("*.py"))
        if "tests" not in path.parts
        and any(m == "zipfile" or m == "xml" or m.startswith("xml.") for m in imported_modules(path))
    ]
    assert opening == [
        "dataverify/tools/edk_xlsx.py",
        "inventory/tools/scope12_xlsx.py",  # S12b-1: 같은 바이트(zip 다시 묶기 — 발주서 2-5)
        "inventory/tools/scope3_xlsx.py",  # S3D1: 같은 바이트(zip 다시 묶기 — scope12_xlsx 꼴)
        "inventory/tools/xlsx_reader.py",
        "materiality/tools/value_chain_xlsx.py",
        "runbundle/service/actions/export.py",
        "runbundle/service/actions/import_.py",
        "translation/service/actions/archive.py",
        "translation/tools/docx_reader.py",
        "translation/tools/glossary_xlsx.py",
        "translation/tools/page_tags.py",
    ]


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다(ISSUE-207 — 옛 검사는 `ImportFrom.level` 을 버려 상대 꼴을 지나쳤다)."""
    tree = ast.parse("from . import x\nfrom ..y import z\nfrom ... import w\nimport json\n")
    froms = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert [resolve(node, OWN) for node in froms] == [
        "esgapi.inventory.tools.scope3_sheets",
        "esgapi.inventory.tools.y",
        "esgapi.inventory",
    ]
    assert modules_in("from . import x\nfrom ..y import z\nimport json\n", OWN) == {
        "esgapi.inventory.tools.scope3_sheets",
        "esgapi.inventory.tools.scope3_sheets.x",
        "esgapi.inventory.tools.y",
        "json",
    }
    assert modules_in("from os import path\n", OWN) == {"os"}
    assert package_of(FOLDER / "grid.py") == OWN
    assert package_of(FOLDER / "sub" / "a.py") == "esgapi.inventory.tools.scope3_sheets.sub"
