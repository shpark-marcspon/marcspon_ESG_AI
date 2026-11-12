"""`engines/colab_158/` 는 순수한가: 파일·시계·난수·네트워크·Django·pydantic·core·계약·도구·출력을 import 하지 않고,
print·open 을 부르지 않는다(발주서 §1-9·§3 S6). `dataverify/tests/engines/colab_156/test_purity.py` 의 판별 복사.

`.importlinter` 의 계약 (다)가 django·ninja·psycopg 를 문다. 여기는 그 밖의 것까지 폴더의 소스에서 직접 본다.
"""

import ast
from pathlib import Path

import esgapi.translation.engines.colab_158 as package

FOLDER = Path(package.__file__).parent
OWN = "esgapi.translation.engines.colab_158"

FORBIDDEN = (
    "django",
    "ninja",
    "psycopg",
    "os",
    "io",
    "pathlib",
    "shutil",
    "tempfile",
    "glob",
    "importlib",
    "time",
    "datetime",
    "random",
    "secrets",
    "uuid",
    "socket",
    "ssl",
    "http",
    "urllib",
    "httpx",
    "requests",
    "subprocess",
    "threading",
    "asyncio",
    "openai",
    "anthropic",
    "google",
    "docx",
    "lxml",
    "pydantic",
)
EXPECTED_FILES = {
    "__init__.py",
    "structured.py",
    "glossary.py",
    "pages.py",
    "tables.py",
    "gates.py",
    "bilingual.py",
    "review_rules.py",
    "prompts.py",
    "ports.py",
    "records.py",
    "translate.py",
    "review.py",
    "autofix.py",
    "pipeline.py",
    "plan.py",
    "texts.py",
}


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미(엔진 파일은 OWN 안), 둘 = 그 위."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def imported_modules(path: Path) -> set[str]:
    """절대·상대 import 둘 다(상대는 OWN 기준으로 풀어 같은 검사에 넣는다 — 검증 B1). `from . import x` 는 그 꾸러미와
    `<꾸러미>.x` 둘 다."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = resolve(node, OWN)
            names.add(module)
            if node.module is None:
                names.update(f"{module}.{alias.name}" for alias in node.names)
    return names


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다: 엔진 파일 자리에서 `from ...contracts import shapes` 는 esgapi.translation.contracts."""
    tree = ast.parse("from ...contracts import shapes\nfrom . import pages\nfrom ....core.llm import types\n")
    froms = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert [resolve(node, OWN) for node in froms] == [
        "esgapi.translation.contracts",
        OWN,
        "esgapi.core.llm",
    ]


def is_forbidden(module: str) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in FORBIDDEN)


def test_the_folder_is_the_files_we_think_it_is() -> None:
    assert {path.name for path in FOLDER.glob("*.py")} == EXPECTED_FILES


def test_no_module_imports_files_clocks_network_django_or_pydantic() -> None:
    for path in sorted(FOLDER.glob("*.py")):
        offending = sorted(module for module in imported_modules(path) if is_forbidden(module))
        assert offending == [], f"{path.name}: {offending}"


def test_no_module_imports_esgapi_outside_its_own_folder() -> None:
    """core·계약(contracts)·도구(tools)·출력(outputs)·다른 모듈을 모른다 — 엔진은 계약을 모른다(처분 ⑭ 의 축 대용)."""
    for path in sorted(FOLDER.glob("*.py")):
        outside = sorted(
            module
            for module in imported_modules(path)
            if module.split(".")[0] == "esgapi" and module != OWN and not module.startswith(f"{OWN}.")
        )
        assert outside == [], f"{path.name}: {outside}"


def test_no_module_calls_open_or_print() -> None:
    for path in FOLDER.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert not calls & {"open", "print", "exec", "eval"}, path.name
