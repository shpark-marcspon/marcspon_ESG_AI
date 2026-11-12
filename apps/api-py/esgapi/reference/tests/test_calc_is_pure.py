"""`reference/calc/` 는 파일·네트워크·시계·난수·Django 를 쓰지 않는다. 순수 층.

TS 원본 `files.test.ts` 의 「조립 함수(domain)는 파일·네트워크·시계를 쓰지 않는다」(74~78행)의 뜻을 옮겼다.
Django·ninja·psycopg 는 `.importlinter` 의 계약 (다)도 막는다. 여기서는 import 한 이름을 직접 읽어 나머지도 본다.
"""

import ast
from pathlib import Path

import pytest

CALC = Path(__file__).resolve().parents[1] / "calc"
PACKAGE = "esgapi.reference.calc"  # CALC 의 꾸러미(상대 import 를 풀 기준 — ISSUE-207)

# 순수 모듈이 import 해도 되는 것. 여기 없는 것이 들어오면 빨개진다(목록을 늘릴 때 까닭을 적는다).
ALLOWED = {
    "collections.abc",
    "dataclasses",
    "json",  # 실패에 싣는 「받은 값」을 글자로 적는 데만 쓴다(dumps)
    "re",
    "typing",
    "pydantic",  # 대응표 JSON 의 꼴 검사(parse.py)
    "esgapi.reference.calc",
}
FORBIDDEN_NAMES = {"open", "float", "eval", "exec", "__import__"}


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def _imports(tree: ast.AST, package: str = PACKAGE) -> set[str]:
    """절대·상대 import 둘 다(상대는 calc 꾸러미 기준 — 폴더가 납작해 파일마다 같다). `from . import x` 는 그
    꾸러미와 `<꾸러미>.x` 둘 다."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolve(node, package)
            found.add(module)
            if node.module is None:
                found.update(f"{module}.{alias.name}" for alias in node.names)
    return found


# 사본에서 뜻이 없다: mutmut 이 심은 트램펄린(mutmut.mutation.trampoline import)을 소스에서 읽는다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_calc_imports_only_the_allowed_modules() -> None:
    files = sorted(CALC.glob("*.py"))
    assert len(files) >= 7  # 빈 폴더를 재고 통과하는 일을 막는다
    for file in files:
        for name in _imports(ast.parse(file.read_text(encoding="utf-8"))):
            allowed = name in ALLOWED or name.startswith("esgapi.reference.calc.")
            assert allowed, f"{file.name} 이 {name} 을 import 한다"


def test_calc_never_opens_files_or_makes_floats() -> None:
    """파일을 열지 않고, 값을 float 로 바꾸지 않는다(값은 글자로만 다닌다)."""
    for file in sorted(CALC.glob("*.py")):
        tree = ast.parse(file.read_text(encoding="utf-8"))
        called = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert not called & FORBIDDEN_NAMES, f"{file.name}: {called & FORBIDDEN_NAMES}"


def test_calc_does_not_read_the_engine() -> None:
    """`inventory.engines`(계산 엔진)를 import 하지 않는다. 두 모듈은 JSON 꼴로만 만난다."""
    for file in sorted(CALC.glob("*.py")):
        assert "esgapi.inventory" not in file.read_text(encoding="utf-8"), file.name


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다(ISSUE-207 — 옛 `_imports` 는 `ImportFrom.level` 을 버려 `from . import x` 를 빈 이름으로
    적었다)."""
    tree = ast.parse("from . import parse\nfrom ..service import x\nfrom ...inventory import y\nimport json\n")
    froms = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert [resolve(node, PACKAGE) for node in froms] == [
        "esgapi.reference.calc",
        "esgapi.reference.service",
        "esgapi.inventory",
    ]
    # `from . import x` 는 calc 안이라 허용 목록을 지나고, 위로 오르는 상대 꼴은 빨개진다
    assert _imports(ast.parse("from . import parse\nimport json\n")) == {
        "esgapi.reference.calc",
        "esgapi.reference.calc.parse",
        "json",
    }
    assert _imports(ast.parse("from ..service import x\n")) == {"esgapi.reference.service"}
