"""축(발주서 §3 S6): 계약(contracts)은 엔진(engines)·도구(tools)·Word 쓰개(outputs — TR1b)를 import 하지 않고, 도구는
계약·Word 쓰개를 import 하지 않는다. Word 쓰개는 도구·흐름(flows)을 import 하지 않고, 엔진에서는
`engines.colab_158.review_rules` 하나만 안다(TR1b 처분 ⑦ — 셀 62 가 부르는 strip_korean_bilingual_annotations).
엔진 쪽(엔진은 계약·도구·core 를 모름)은 tests/engines/colab_158/test_purity.py.
상대 import 도 그 파일의 꾸러미 기준으로 풀어 본다(검증 ② B1 — `from ..engines import x` 꼴을 놓치지 않게).
"""

import ast
from pathlib import Path

import pytest

import esgapi.translation as translation

ROOT = Path(translation.__file__).parent
PACKAGE = "esgapi.translation"

# 꾸러미 → 그 안의 파일이 import 하면 안 되는 꾸러미
AXES = {
    "contracts": ("esgapi.translation.engines", "esgapi.translation.tools", "esgapi.translation.outputs"),
    "tools": ("esgapi.translation.contracts", "esgapi.translation.outputs"),
    "outputs": ("esgapi.translation.tools", "esgapi.translation.flows"),
}
# outputs 가 아는 엔진 모듈은 이것 하나뿐(AXES 는 금지 목록이라 「하나만 허용」은 따로 잰다)
OUTPUTS_ENGINE_ALLOWED = "esgapi.translation.engines.colab_158.review_rules"


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def imported_modules(source: str, package: str) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolve(node, package)
            names.add(module)
            if node.module is None:
                names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def crosses(module: str, forbidden: tuple[str, ...]) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in forbidden)


def test_relative_and_absolute_forms_are_both_caught() -> None:
    contracts = f"{PACKAGE}.contracts"
    for source, expected in [
        ("from ..engines.colab_158 import pipeline\n", "esgapi.translation.engines.colab_158"),
        ("from .. import tools\n", "esgapi.translation.tools"),
        ("from ..tools.llm_bridge import route_for\n", "esgapi.translation.tools.llm_bridge"),
        ("import esgapi.translation.engines\n", "esgapi.translation.engines"),
    ]:
        found = sorted(m for m in imported_modules(source, contracts) if crosses(m, AXES["contracts"]))
        assert found == [expected], source
    assert imported_modules("from .shapes import RESULT_SHAPE\n", contracts) == {"esgapi.translation.contracts.shapes"}
    assert not crosses("esgapi.translation.toolsmith", AXES["contracts"])


@pytest.mark.parametrize("folder", sorted(AXES))
def test_the_folder_does_not_cross_its_axis(folder: str) -> None:
    files = sorted((ROOT / folder).glob("*.py"))
    assert files, folder
    package = f"{PACKAGE}.{folder}"
    for path in files:
        offending = sorted(
            m for m in imported_modules(path.read_text(encoding="utf-8"), package) if crosses(m, AXES[folder])
        )
        assert offending == [], f"{folder}/{path.name}: {offending}"


def engine_modules(source: str, package: str) -> set[str]:
    return {m for m in imported_modules(source, package) if crosses(m, ("esgapi.translation.engines",))}


def test_outputs_knows_only_review_rules_of_the_engines() -> None:
    files = sorted((ROOT / "outputs").glob("*.py"))
    assert files
    package = f"{PACKAGE}.outputs"
    for path in files:
        reaching = engine_modules(path.read_text(encoding="utf-8"), package)
        assert reaching <= {OUTPUTS_ENGINE_ALLOWED}, f"outputs/{path.name}: {sorted(reaching)}"


def test_the_engine_allowance_is_narrow() -> None:
    """`from …colab_158 import review_rules` 꼴은 꾸러미(colab_158)로 잡혀 허용 밖이다 — 모듈 이름까지 적은 꼴만
    지난다."""
    package = f"{PACKAGE}.outputs"
    for source, ok in [
        ("from esgapi.translation.engines.colab_158.review_rules import strip_korean_bilingual_annotations\n", True),
        ("from ..engines.colab_158.review_rules import strip_korean_bilingual_annotations\n", True),
        ("from esgapi.translation.engines.colab_158 import review_rules\n", False),
        ("from esgapi.translation.engines.colab_158 import structured\n", False),
        ("from esgapi.translation.engines.colab_158.pipeline import source_and_pages\n", False),
        ("import esgapi.translation.engines\n", False),
    ]:
        assert (engine_modules(source, package) <= {OUTPUTS_ENGINE_ALLOWED}) is ok, source
