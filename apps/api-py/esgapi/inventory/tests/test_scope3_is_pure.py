"""`engines/scope3/llm_first_1/` 는 순수한가: 파일·시계·난수·네트워크·Django·reference·LLM 조립을 import 하지 않는다.

`.importlinter` 의 계약 (다)가 django·ninja·psycopg 를 문다. 여기는 그 밖의 것까지 폴더의 소스에서 직접 본다
(esg-lab `ports.test.ts` 의 「domain 은 파일·네트워크 모듈과 adapters·eval 을 import 하지 않는다」의 옮김).
"""

import ast
from pathlib import Path

import esgapi.inventory.engines.scope3.llm_first_1 as package

FOLDER = Path(package.__file__).parent
OWN = package.__name__
ROOT = FOLDER.parents[len(OWN.split(".")) - 1]  # esgapi 를 담은 폴더

# 순수 층이 import 하면 안 되는 것(앞머리 일치). `esgapi.core.llm` 은 순수 조각(client·types·cost)만 된다.
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
    "esgapi.reference",
    "esgapi.organization",
    "esgapi.user",
    "esgapi.config",
    "esgapi.core.llm.setup",
    "esgapi.core.llm.providers",
    "esgapi.core.llm.sinks",
    "esgapi.core.resources",
    "esgapi.core.conf",
    "esgapi.inventory.service",
    "esgapi.inventory.api",
    "esgapi.inventory.data_loader",
    "esgapi.inventory.tests",
)
ALLOWED_LLM = {"esgapi.core.llm.client", "esgapi.core.llm.types", "esgapi.core.llm.cost"}
# core 의 순수 규칙(십진 커널, 불리언 거름). 밴드 PY8a 가 inventory/calc 에서 core/calc 로 옮겼다.
ALLOWED_CORE_CALC = {"esgapi.core.calc.decimal", "esgapi.core.calc.guards"}
EXPECTED_FILES = {
    "__init__.py",
    "calc.py",
    "catalog.py",
    "lexical_v1.py",
    "llm_steps.py",
    "memory.py",
    "normalize.py",
    "pipeline.py",
    "ports.py",
    "ranking.py",
    "review.py",
    "serialize.py",
    "shortlister.py",
    "types.py",
    "units.py",
}


def package_of(path: Path) -> str:
    """그 파일의 꾸러미(담은 폴더의 점 이름 — `__init__.py` 면 그 자신). ROOT 밖 파일이면 ValueError."""
    return ".".join(path.parent.relative_to(ROOT).parts)


def resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def modules_in(source: str, package: str) -> set[str]:
    """절대·상대 import 둘 다(상대는 그 파일의 꾸러미 기준으로 풀어 같은 검사에 넣는다). `from . import x` 는 그
    꾸러미와 `<꾸러미>.x` 둘 다."""
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


def imported_modules(path: Path) -> set[str]:
    return modules_in(path.read_text(encoding="utf-8"), package_of(path))


def is_forbidden(module: str) -> bool:
    return any(module == name or module.startswith(f"{name}.") for name in FORBIDDEN)


def test_the_folder_is_the_fifteen_files_we_think_it_is() -> None:
    assert {path.name for path in FOLDER.glob("*.py")} == EXPECTED_FILES


def test_no_module_imports_files_clocks_randomness_network_django_or_reference() -> None:
    for path in sorted(FOLDER.glob("*.py")):
        offending = sorted(module for module in imported_modules(path) if is_forbidden(module))
        assert offending == [], f"{path.name}: {offending}"


def test_only_the_pure_pieces_of_core_llm_are_imported() -> None:
    used: set[str] = set()
    for path in FOLDER.glob("*.py"):
        used |= {module for module in imported_modules(path) if module.startswith("esgapi.core")}
    assert used <= ALLOWED_LLM | ALLOWED_CORE_CALC
    assert used & ALLOWED_LLM  # 분류·추천 요청을 조립하므로 하나는 쓴다(이 검사가 빈 집합으로 통과하지 않게).


def test_no_module_calls_open_or_uses_floats_for_money() -> None:
    """파일을 여는 호출이 없고, 계산(`calc.py`)에는 float 리터럴과 float() 호출이 없다."""
    for path in FOLDER.glob("*.py"):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert "open" not in calls, path.name
    calc = ast.parse((FOLDER / "calc.py").read_text(encoding="utf-8"))
    floats = [node for node in ast.walk(calc) if isinstance(node, ast.Constant) and isinstance(node.value, float)]
    assert floats == []
    names = {node.id for node in ast.walk(calc) if isinstance(node, ast.Name)}
    assert "float" not in names
    assert "ranking" not in " ".join(imported_modules(FOLDER / "calc.py"))


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다(ISSUE-207 — 옛 검사는 `ImportFrom.level` 을 버려 상대 꼴을 지나쳤다)."""
    tree = ast.parse("from . import x\nfrom ..y import z\nfrom ... import w\nimport json\n")
    froms = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert [resolve(node, OWN) for node in froms] == [
        "esgapi.inventory.engines.scope3.llm_first_1",
        "esgapi.inventory.engines.scope3.y",
        "esgapi.inventory.engines",
    ]
    assert modules_in("from . import x\nfrom ..y import z\nimport json\n", OWN) == {
        "esgapi.inventory.engines.scope3.llm_first_1",
        "esgapi.inventory.engines.scope3.llm_first_1.x",
        "esgapi.inventory.engines.scope3.y",
        "json",
    }
    assert modules_in("from os import path\n", OWN) == {"os"}
    assert package_of(FOLDER / "calc.py") == OWN
    assert package_of(FOLDER / "sub" / "a.py") == "esgapi.inventory.engines.scope3.llm_first_1.sub"
