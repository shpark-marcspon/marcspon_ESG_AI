"""축: 계약(contracts)과 출력(outputs)은 엔진(engines)을 모르고, 엔진·계약·출력은 흐름(flows)을 모른다(DV1a 발주서
§3 S11 — 처분 ③ 가의 축 계약 대용, AST. 흐름 줄은 DV1b 처분 ⑥).

엔진 → 계약·출력은 tests/engines/colab_156/test_purity.py 가 본다. 계약 → 출력도 금지다(출력은 계약의 꼴을 읽는 쪽).
상대 import 는 그 파일의 꾸러미 기준으로 풀어 같은 검사에 넣는다(ISSUE-195).
무효 조건: 직접 import 만 본다. importlib·__import__ 로 이름을 글자로 부르면 못 잡는다(엔진은 importlib 금지).
"""

import ast
from pathlib import Path

import esgapi.dataverify as package

ROOT = Path(package.__file__).parent
FORBIDDEN = {
    "engines": ("esgapi.dataverify.flows",),
    "contracts": ("esgapi.dataverify.engines", "esgapi.dataverify.outputs", "esgapi.dataverify.flows"),
    "outputs": ("esgapi.dataverify.engines", "esgapi.dataverify.flows"),
}


OWN = "esgapi.dataverify"


def package_of(path: Path) -> str:
    """그 파일의 꾸러미(`__init__.py` 면 그 자신, 아니면 담은 폴더)."""
    return ".".join([OWN, *path.parent.relative_to(ROOT).parts])


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(translation
    tests/engines/colab_158/test_purity.py 의 판별 복사 — ISSUE-195)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def imported_modules(path: Path) -> set[str]:
    return modules_in(path.read_text(encoding="utf-8"), package_of(path))


def modules_in(source: str, package: str) -> set[str]:
    """절대·상대 import 둘 다(상대는 그 파일의 꾸러미 기준으로 풀어 같은 검사에 넣는다). from 꼴은 모듈과
    `<모듈>.<이름>` 둘 다."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolve(node, package)
            names.add(module)
            names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다(ISSUE-195): 계약 파일 자리에서 `from ..engines.colab_156 import tools` 는 엔진이다."""
    contracts = package_of(ROOT / "contracts" / "wire.py")
    assert contracts == "esgapi.dataverify.contracts"
    assert package_of(ROOT / "contracts" / "__init__.py") == contracts
    assert modules_in("from ..engines.colab_156 import tools\n", contracts) == {
        "esgapi.dataverify.engines.colab_156",
        "esgapi.dataverify.engines.colab_156.tools",
    }
    assert modules_in("from .. import outputs\n", contracts) == {"esgapi.dataverify", "esgapi.dataverify.outputs"}
    assert modules_in("from .shapes import CHECK\n", contracts) == {
        "esgapi.dataverify.contracts.shapes",
        "esgapi.dataverify.contracts.shapes.CHECK",
    }


def test_the_layers_do_not_import_what_they_must_not_know() -> None:
    seen = 0
    for layer, forbidden in FORBIDDEN.items():
        for path in sorted((ROOT / layer).glob("**/*.py")) if (ROOT / layer).is_dir() else []:
            seen += 1
            bad = sorted(m for m in imported_modules(path) if any(m == f or m.startswith(f"{f}.") for f in forbidden))
            assert bad == [], f"{path.relative_to(ROOT)}: {bad}"
    assert seen >= 2  # contracts 의 __init__·shapes 가 적어도 있다(빈 집합으로 통과하지 않게)
