"""쌍둥이: 가치사슬 엑셀 읽개(materiality/tools/value_chain_xlsx.py)의 zip·XML 방어는 영문번역 용어집 읽개
(translation/tools/glossary_xlsx.py — 밴드 TR3a)를 옮겨 적은 것이다(발주서 IRW2 Q1·§1-3 — 모듈끼리 import 0). 한쪽만
고치면 여기서 빨갛다: 두 소스를 `Path.read_text` 로 읽어(어느 쪽도 import 하지 않는다) 아래 이름들의 AST 를 견준다.

- 함수: 몸 전체를 `ast.dump` 로. 거절 글·kind 이름은 바꿔도 되므로 str 상수와 f-글은 정규화하고, 결과 이름 둘
  (GlossaryRead → ValueChainRead · _pairs → _table)만 같은 것으로 본다.
- 상수·예외 묶음: 글자 그대로(str·bytes 값까지) 견준다 — 상한 값 하나만 달라도 빨강.
"""

import ast
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[3]
"""esgapi/."""
GLOSSARY: Final = ROOT / "translation" / "tools" / "glossary_xlsx.py"
VALUE_CHAIN: Final = ROOT / "materiality" / "tools" / "value_chain_xlsx.py"

FUNCTIONS: Final = (
    "_read",
    "_declared_sizes",
    "_read_entry",
    "_check_entries",
    "_looks_like_xml",
    "_parser",
    "_feed",
    "_scan",
    "_content_types_root",
)
CONSTANTS: Final = (
    "MAX_BYTES",
    "MAX_ENTRIES",
    "MAX_ENTRY_BYTES",
    "MAX_DECLARED_BYTES",
    "MAX_SCANNED_ROWS",
    "MAX_XML_DEPTH",
    "MAX_XML_ELEMENTS",
    "MAX_XML_SPAN",
    "_CHUNK",
    "_CONTENT_TYPES",
    "_CT_NS",
    "_ZIP_ERRORS",
    "_WORKBOOK_ERRORS",
    "_XML_SIGNATURES",
    "_SPACE_THEN_LT",
)
RENAMED: Final = {"GlossaryRead": "ValueChainRead", "_pairs": "_table"}
"""옮기며 바꾼 이름(결과 꼴·뒷단 함수). 그 밖의 이름은 같아야 한다."""


class _Normalized(ast.NodeTransformer):
    """str 상수(거절 글·kind)와 f-글을 빈 글로, 바꾼 이름을 새 이름으로."""

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        return ast.Constant(value="") if isinstance(node.value, str) else node

    def visit_JoinedStr(self, node: ast.JoinedStr) -> ast.AST:
        return ast.Constant(value="")

    def visit_Name(self, node: ast.Name) -> ast.AST:
        return ast.Name(id=RENAMED.get(node.id, node.id), ctx=node.ctx)


def definitions(path: Path) -> dict[str, ast.AST]:
    return definitions_of(ast.parse(path.read_text(encoding="utf-8")))


def definitions_of(module: ast.Module) -> dict[str, ast.AST]:
    """모듈 맨 위의 함수·대입(주석 달린 대입 포함)을 이름으로."""
    found: dict[str, ast.AST] = {}
    for node in module.body:
        if isinstance(node, ast.FunctionDef):
            found[node.name] = node
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            found[node.target.id] = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            found[node.targets[0].id] = node.value
    return found


def function_dump(node: ast.AST) -> str:
    return ast.dump(_Normalized().visit(ast.parse(ast.unparse(node))))


@pytest.mark.parametrize("name", FUNCTIONS)
def test_the_copied_defence_functions_have_the_same_body(name: str) -> None:
    glossary, value_chain = definitions(GLOSSARY), definitions(VALUE_CHAIN)
    assert function_dump(value_chain[name]) == function_dump(glossary[name])


@pytest.mark.parametrize("name", CONSTANTS)
def test_the_copied_limits_and_tables_have_the_same_value(name: str) -> None:
    glossary, value_chain = definitions(GLOSSARY), definitions(VALUE_CHAIN)
    assert ast.dump(value_chain[name]) == ast.dump(glossary[name])


def test_the_comparison_is_not_empty_and_is_not_blind_to_a_changed_limit() -> None:
    """분모: 견줄 것이 다 있고, 정규화가 숫자까지 지우지 않는다(상수 하나를 바꾼 소스는 다르게 나온다)."""
    glossary = definitions(GLOSSARY)
    assert set(FUNCTIONS) | set(CONSTANTS) <= set(glossary) & set(definitions(VALUE_CHAIN))
    changed = ast.parse(
        GLOSSARY.read_text(encoding="utf-8").replace("MAX_XML_DEPTH: Final = 64", "MAX_XML_DEPTH: Final = 65")
    )
    assert ast.dump(definitions_of(changed)["MAX_XML_DEPTH"]) != ast.dump(glossary["MAX_XML_DEPTH"])
    edited = GLOSSARY.read_text(encoding="utf-8").replace("if entry.filename in sizes:", "if False:")
    assert function_dump(definitions_of(ast.parse(edited))["_declared_sizes"]) != function_dump(
        glossary["_declared_sizes"]
    )


def test_the_value_chain_reader_does_not_import_translation() -> None:
    source = VALUE_CHAIN.read_text(encoding="utf-8")
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert imported and not {m for m in imported if m and "translation" in m}
