"""engines/e0/ 의 사본 열 파일이 GW1 의 같은 파일과 구문 나무(AST)가 같다 — esg-lab 없이 도는 판.

GW1 쪽 정규화 AST 의 sha256 을 tests/data/gw1-ast-sha256.txt 에 박아 두었다(뽑은 명령은 그 파일 머리).
정규화는 scripts/g1a_compare.py 의 것과 같다: import 의 모듈 이름 esgapi.greenwash.engines.e0(.x) → greenwash(.x).
주석·서식·AST 가 같은 이스케이프 정리는 AST 밖이다.
"""

import ast
import hashlib
from pathlib import Path

import pytest

CALC = Path(__file__).resolve().parents[1] / "engines" / "e0"
PINNED = Path(__file__).resolve().parent / "data" / "gw1-ast-sha256.txt"
OURS = "esgapi.greenwash.engines.e0"
E0_NOT_COPIES = frozenset({"checker.py", "result.py", "gw1.py"})
"""engines/e0/ 에서 고정 밖의 이름: 풀린 사본 checker.py 와 사본이 아닌 두 파일(GW1 결과 조립 result.py,
꼴 있는 겉 gw1.py)."""


class _Normalize(ast.NodeTransformer):
    def visit_ImportFrom(self, node: ast.ImportFrom) -> ast.ImportFrom:
        if node.module == OURS:
            node.module = "greenwash"
        elif node.module is not None and node.module.startswith(OURS + "."):
            node.module = "greenwash." + node.module.removeprefix(OURS + ".")
        return node

    def visit_Import(self, node: ast.Import) -> ast.Import:
        for alias in node.names:
            if alias.name == OURS or alias.name.startswith(OURS + "."):
                alias.name = "greenwash" + alias.name.removeprefix(OURS)
        return node


def normalized_sha256(path: Path) -> str:
    tree = _Normalize().visit(ast.parse(path.read_text(encoding="utf-8"), filename=str(path)))
    return hashlib.sha256(ast.dump(tree, include_attributes=False).encode("utf-8")).hexdigest()


def pinned() -> dict[str, str]:
    lines = [line.split() for line in PINNED.read_text(encoding="utf-8").splitlines() if not line.startswith("#")]
    return {name: digest for name, digest in lines}


def test_nine_files_are_pinned_and_checker_is_released() -> None:
    """고정 아홉 + E0_NOT_COPIES(풀린 checker.py — GL1 에서 이어 돌기 꼭지를 달았고 GW1 동등성은 tests/flows 의 대조가
    맡는다 — 와 사본 아닌 result.py·gw1.py)."""
    copies = {p.name for p in CALC.glob("*.py") if p.name != "__init__.py"}
    assert copies == set(pinned()) | E0_NOT_COPIES
    assert len(pinned()) == 9
    assert "checker.py" not in pinned()


@pytest.mark.parametrize("name", sorted(pinned()))
def test_a_copy_has_the_gw1_ast(name: str) -> None:
    assert normalized_sha256(CALC / name) == pinned()[name]


def test_the_copies_compile_without_warnings() -> None:
    """잘못된 이스케이프(SyntaxWarning)가 없다 — filterwarnings = error 아래에서 import 가 깨지지 않게."""
    for path in CALC.glob("*.py"):
        compile(path.read_text(encoding="utf-8"), str(path), "exec")
