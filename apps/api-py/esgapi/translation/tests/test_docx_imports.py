"""python-docx 를 만지는 자리(발주서 §1-8): 제품 코드(esgapi 아래, tests 폴더 밖)에서 `import docx`·`from docx` 는 아래
다섯뿐이고 `lxml` 은 0(python-docx 를 거쳐서만). 시험은 Word 를 코드로 지어야 하므로 tests 폴더는 세지 않는다.
"""

import ast
from pathlib import Path

import esgapi

ESGAPI = Path(esgapi.__file__).parent
ALLOWED = {
    "translation/tools/docx_reader.py",
    "translation/outputs/docx_bilingual.py",
    "translation/outputs/docx_qa.py",
    "translation/outputs/readback.py",
    "drafting/outputs/docx.py",  # RP2d 결과 docx(MARC-ENT-504)
}


def top_names(source: str) -> set[str]:
    """그 글이 import 하는 꾸러미의 맨 앞 이름(상대 import 는 esgapi 안이라 뺀다)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module.split(".")[0])
    return names


def product_files() -> list[Path]:
    return sorted(p for p in ESGAPI.rglob("*.py") if "tests" not in p.relative_to(ESGAPI).parts)


def test_the_finder_sees_both_forms() -> None:
    assert top_names("import docx\n") == {"docx"}
    assert top_names("from docx.table import Table\n") == {"docx"}
    assert top_names("import lxml.etree as etree\n") == {"lxml"}
    assert top_names("from . import docx\n") == set()
    assert top_names("import docxtpl\n") == {"docxtpl"}


def test_python_docx_is_imported_only_by_the_allowed_files_and_lxml_by_none() -> None:
    files = product_files()
    assert len(files) > 100
    importing_docx: set[str] = set()
    importing_lxml: set[str] = set()
    for path in files:
        names = top_names(path.read_text(encoding="utf-8"))
        rel = path.relative_to(ESGAPI).as_posix()
        if "docx" in names:
            importing_docx.add(rel)
        if "lxml" in names:
            importing_lxml.add(rel)
    assert importing_docx - ALLOWED == set()
    assert "translation/tools/docx_reader.py" in importing_docx  # 양성 대조: 읽개는 python-docx 를 쓴다
    assert importing_lxml == set()


def test_only_word_dump_imports_the_unguarded_readback() -> None:
    """readback 은 방어 없이 Document(BytesIO) 를 연다 — 우리가 지은 바이트만. 올린 파일은 docx_reader(가지 리뷰 M1)."""
    importing: set[str] = set()
    for path in product_files():
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom) and node.module is not None:
                names = {node.module, *(f"{node.module}.{alias.name}" for alias in node.names)}
            elif isinstance(node, ast.Import):
                names = {alias.name for alias in node.names}
            else:
                continue
            if "esgapi.translation.outputs.readback" in names or (node_level_relative_readback(node)):
                importing.add(path.relative_to(ESGAPI).as_posix())
    assert importing == {"translation/outputs/word_dump.py"}


def node_level_relative_readback(node: ast.AST) -> bool:
    """`from . import readback`·`from .readback import …` 꼴(상대 import)도 센다."""
    if not isinstance(node, ast.ImportFrom) or node.level == 0:
        return False
    return node.module == "readback" or any(alias.name == "readback" for alias in node.names)
