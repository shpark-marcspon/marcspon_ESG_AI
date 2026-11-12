"""쌍둥이: EDK 인벤토리 엑셀 읽개(dataverify/tools/edk_xlsx.py)의 zip·XML 방어는 영문번역 용어집 읽개
(translation/tools/glossary_xlsx.py — 밴드 TR3a)를 옮겨 적은 것이다(발주서 DVX1 Q3·§1-2 — 모듈끼리 import 0). 한쪽만
고치면 여기서 빨갛다: 두 소스를 `Path.read_text` 로 읽어(어느 쪽도 import 하지 않는다) 아래 이름들의 AST 를 견준다
(materiality/tests/tools/test_value_chain_xlsx_twin.py 꼴).

- 함수: 몸 전체를 `ast.dump` 로. 거절 글은 바꿔도 되므로 문장 꼴 str 상수와 f-글은 정규화하고(kind 이름처럼 소문자·
  밑줄뿐인 글은 그대로 — 갈래를 맞바꾸면 빨강, 가지 리뷰 N4), 결과 이름 둘
  (GlossaryRead → EdkRead · _pairs → _items)만 같은 것으로 본다.
- 상수·예외 묶음: 글자 그대로(str·bytes 값까지) 견준다 — 상한 값 하나만 달라도 빨강. 다름 허락은 DIFFERENT 하나
  (MAX_XML_ELEMENTS — 이름과 두 값을 적는다. 값이 둘 중 하나라도 바뀌면 빨강).
"""

import ast
import re
from pathlib import Path
from typing import Final

import pytest

ROOT: Final = Path(__file__).resolve().parents[3]
"""esgapi/."""
GLOSSARY: Final = ROOT / "translation" / "tools" / "glossary_xlsx.py"
EDK: Final = ROOT / "dataverify" / "tools" / "edk_xlsx.py"

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
    "MAX_XML_SPAN",
    "_CHUNK",
    "_CONTENT_TYPES",
    "_CT_NS",
    "_ZIP_ERRORS",
    "_WORKBOOK_ERRORS",
    "_XML_SIGNATURES",
    "_SPACE_THEN_LT",
)
DIFFERENT: Final = {"MAX_XML_ELEMENTS": (100_000, 500_000)}
"""옮긴 상수 가운데 값이 다른 것 — (glossary 값, edk 값). 견본 하나가 glossary 예산으로 unsafe_xlsx(발주서 Q4·★D)."""
RENAMED: Final = {"GlossaryRead": "EdkRead", "_pairs": "_items"}
"""옮기며 바꾼 이름(결과 꼴·뒷단 함수). 그 밖의 이름은 같아야 한다."""


KIND_LIKE: Final = re.compile(r"[a-z_]+")
"""정규화하지 않는 글(kind 이름 꼴 — fullmatch)."""


class _Normalized(ast.NodeTransformer):
    """문장 꼴 str 상수(거절 글)와 f-글을 빈 글로(kind 이름 꼴은 그대로), 바꾼 이름을 새 이름으로."""

    def visit_Constant(self, node: ast.Constant) -> ast.AST:
        if isinstance(node.value, str) and not KIND_LIKE.fullmatch(node.value):
            return ast.Constant(value="")
        return node

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
    glossary, edk = definitions(GLOSSARY), definitions(EDK)
    assert function_dump(edk[name]) == function_dump(glossary[name])


@pytest.mark.parametrize("name", CONSTANTS)
def test_the_copied_limits_and_tables_have_the_same_value(name: str) -> None:
    glossary, edk = definitions(GLOSSARY), definitions(EDK)
    assert ast.dump(edk[name]) == ast.dump(glossary[name])


@pytest.mark.parametrize("name", sorted(DIFFERENT))
def test_the_one_allowed_difference_has_exactly_the_two_listed_values(name: str) -> None:
    glossary, edk = definitions(GLOSSARY), definitions(EDK)
    assert (ast.literal_eval(glossary[name]), ast.literal_eval(edk[name])) == DIFFERENT[name]
    assert not set(DIFFERENT) & set(CONSTANTS)


def test_the_comparison_is_not_empty_and_is_not_blind_to_a_changed_limit() -> None:
    """분모: 견줄 것이 다 있고, 정규화가 숫자까지 지우지 않는다(상수 하나를 바꾼 소스는 다르게 나온다)."""
    glossary = definitions(GLOSSARY)
    assert set(FUNCTIONS) | set(CONSTANTS) | set(DIFFERENT) <= set(glossary) & set(definitions(EDK))
    changed = ast.parse(
        GLOSSARY.read_text(encoding="utf-8").replace("MAX_XML_DEPTH: Final = 64", "MAX_XML_DEPTH: Final = 65")
    )
    assert ast.dump(definitions_of(changed)["MAX_XML_DEPTH"]) != ast.dump(glossary["MAX_XML_DEPTH"])
    edited = GLOSSARY.read_text(encoding="utf-8").replace("if entry.filename in sizes:", "if False:")
    assert function_dump(definitions_of(ast.parse(edited))["_declared_sizes"]) != function_dump(
        glossary["_declared_sizes"]
    )


def test_the_comparison_keeps_kind_names_so_a_swapped_kind_is_red() -> None:
    """kind 이름은 지우지 않는다(가지 리뷰 N4): 옮긴 방어 함수에서 갈래 하나를 맞바꾼 소스는 다르게 나온다."""
    source = EDK.read_text(encoding="utf-8")
    kinds = [name for name in FUNCTIONS if "'unsafe_xlsx'" in ast.unparse(definitions(EDK)[name])]
    assert kinds, "옮긴 방어 함수에 unsafe_xlsx 가 없다 — 이 시험의 분모가 비었다"
    name = kinds[0]
    swapped = ast.unparse(definitions(EDK)[name]).replace("'unsafe_xlsx'", "'not_xlsx'", 1)
    assert function_dump(ast.parse(swapped).body[0]) != function_dump(definitions(EDK)[name])
    assert source.count('"unsafe_xlsx"') >= 1


def test_the_edk_reader_does_not_import_translation_or_materiality() -> None:
    source = EDK.read_text(encoding="utf-8")
    imported = {
        node.module if isinstance(node, ast.ImportFrom) else alias.name
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Import | ast.ImportFrom)
        for alias in node.names
    }
    assert imported and not {m for m in imported if m and ("translation" in m or "materiality" in m)}
