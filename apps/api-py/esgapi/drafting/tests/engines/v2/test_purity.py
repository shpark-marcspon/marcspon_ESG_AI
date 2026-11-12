"""`engines/v2/` 는 순수한가(RP2b B12, 발주서 1-4 ④): v1 순수 시험(tests/engines/v1/test_purity.py)과 같은 금지 목록에,
esgapi 는 자기 폴더와 `esgapi.drafting.engines.v1`(S2 몫·이스케이프·경고 꼴) 하나만 허락한다 — core·tools·계약·흐름 0
(core 뷰는 덕 타이핑, 표 행 줄은 tools/blocks_text 의 규칙 복사)."""

import ast
from pathlib import Path

import esgapi.drafting.engines.v2 as package
from esgapi.drafting.tests.engines.v1.test_purity import is_forbidden, modules_in

FOLDER = Path(package.__file__).parent
OWN = "esgapi.drafting.engines.v2"
ALLOWED = "esgapi.drafting.engines.v1"
EXPECTED_FILES = {
    "__init__.py",
    "sentences.py",
    "material.py",
    "answers.py",
    "checks.py",
    "places.py",
    "texts.py",
    "prompts.py",
}


def imported(path: Path) -> set[str]:
    return modules_in(path.read_text(encoding="utf-8"), OWN)


def inside(module: str, root: str) -> bool:
    return module == root or module.startswith(f"{root}.")


def test_the_folder_is_the_files_we_think_it_is() -> None:
    assert {path.name for path in FOLDER.glob("*.py")} == EXPECTED_FILES


def test_no_module_imports_files_clocks_network_django_or_pydantic() -> None:
    for path in sorted(FOLDER.glob("*.py")):
        offending = sorted(module for module in imported(path) if is_forbidden(module))
        assert offending == [], f"{path.name}: {offending}"


def test_esgapi_imports_are_v2_itself_or_engines_v1_only() -> None:
    for path in sorted(FOLDER.glob("*.py")):
        outside = sorted(
            module
            for module in imported(path)
            if module.split(".")[0] == "esgapi" and not inside(module, OWN) and not inside(module, ALLOWED)
        )
        assert outside == [], f"{path.name}: {outside}"


def test_the_checker_catches_core_and_tools() -> None:
    planted = "from esgapi.core.documents.view import Block\nfrom ...tools import blocks_text\n"
    assert {m for m in modules_in(planted, OWN) if not inside(m, OWN) and not inside(m, ALLOWED)} == {
        "esgapi.core.documents.view",
        "esgapi.drafting.tools",
    }


def test_no_module_calls_open_or_print() -> None:
    for path in FOLDER.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert not calls & {"open", "print", "exec", "eval"}, path.name
