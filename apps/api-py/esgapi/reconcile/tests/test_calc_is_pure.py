"""`reconcile/calc/` 는 순수 층이다. TS `boundaries.test.ts` 2건의 뜻을 옮겼다.

  1. domain 은 adapters·파일 시스템·SDK 를 import 하지 않는다 → 여기서는 import **허용 목록**으로 본다.
  2. 값을 다루는 코드는 parseFloat·Number() 로 원문 숫자를 읽지 않는다 → `float(`·`int(` 호출이 없다.
Django·ninja·psycopg 는 `.importlinter` 의 계약 (다)도 막는다(`esgapi.*.calc`).
"""

import ast
from pathlib import Path

import pytest

CALC = Path(__file__).resolve().parents[1] / "calc"
PACKAGE = "esgapi.reconcile.calc"  # CALC 의 꾸러미(상대 import 를 풀 기준)

# 순수 모듈이 import 해도 되는 것. 여기 없는 것이 들어오면 빨개진다(목록을 늘릴 때 까닭을 적는다).
ALLOWED = {
    "collections.abc",
    "dataclasses",
    "math",  # floor·trunc·inf·isfinite (좌표와 「정수인 실수」)
    "re",
    "typing",
    "unicodedata",  # NFKC
}
# reconcile 밖의 esgapi 를 import 하는 자리는 dec.py 하나고, 그것은 core 의 십진 커널이다(다른 업무 모듈은 0).
ALLOWED_PER_FILE = {"dec.py": {"esgapi.core.calc.decimal"}}
# 파일·시계·난수·동적 실행, 그리고 원문 숫자를 수로 읽는 것(값은 끝까지 십진 문자열이다).
FORBIDDEN_NAMES = {"open", "float", "int", "eval", "exec", "__import__", "print", "input"}


def _resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def _imports(tree: ast.AST, package: str = PACKAGE) -> set[str]:
    """절대·상대 import 둘 다(상대는 `package` 기준으로 풀어 같은 검사에 넣는다)."""
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            found.add(_resolve(node, package))
    return found


def _files() -> list[Path]:
    files = sorted(CALC.glob("*.py"))
    assert len(files) >= 11  # 빈 폴더를 재고 통과하는 일을 막는다
    return files


# 사본에서 뜻이 없다: mutmut 이 심은 트램펄린(mutmut.mutation.trampoline import)을 소스에서 읽는다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_calc_imports_only_the_allowed_modules() -> None:
    for file in _files():
        for name in _imports(ast.parse(file.read_text(encoding="utf-8"))):
            allowed = (
                name in ALLOWED
                or name == "esgapi.reconcile.calc"
                or name.startswith("esgapi.reconcile.calc.")
                or name in ALLOWED_PER_FILE.get(file.name, set())
            )
            assert allowed, f"{file.name} 이 {name} 을 import 한다"


def test_calc_never_reads_source_numbers_into_floats_or_ints() -> None:
    """원문 숫자를 `float(`·`int(` 로 읽지 않는다. 파일을 열지 않는다. 표준 라이브러리의 `decimal` 도 쓰지 않는다."""
    for file in _files():
        tree = ast.parse(file.read_text(encoding="utf-8"))
        called = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert not called & FORBIDDEN_NAMES, f"{file.name}: {called & FORBIDDEN_NAMES}"
        assert "decimal" not in _imports(tree), file.name
