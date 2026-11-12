"""`engines/scope3/colab_157/` 는 순수한가(처분 ⑫ (가) — `test_scope3_is_pure.py` 를 이 판에 맞게 판별 복사).

파일·시계·난수·네트워크·Django·reference 를 import 하지 않고, xlsx 를 열지 않는다(처분 ⑤ — 여는 것은
`tools/xlsx_reader.py` 뿐). 개정 1 B5: import 만 보면 엔진이 `pd.read_excel`·`ExcelFile`·`to_excel` 로 파일을 열 수
있어, 속성 이름(`read_*` 전부·쓰기 꼴)과 이름 `open` 의 부름을 AST 로 막는다. `pandas` 자체는
된다(`pandas.io`·`openpyxl` 은 안 된다).
"""

import ast
from pathlib import Path

import esgapi.inventory.engines.scope3.colab_157 as package

FOLDER = Path(package.__file__).parent
OWN = package.__name__
ROOT = FOLDER.parents[len(OWN.split(".")) - 1]  # esgapi 를 담은 폴더

EXPECTED_FILES = {
    "__init__.py",
    "activity.py",
    "company_mapping.py",
    "constants.py",
    "distance.py",
    "energy.py",
    "factor_book.py",
    "frames.py",
    "llm.py",
    "output_files.py",
    "pdcompat.py",
    "pipeline.py",
    "ports.py",
    "product.py",
    "purchase.py",
    "serialize.py",
    "spend.py",
    "template.py",
    "transport.py",
    "travel.py",
    "travel_mode.py",
    "units.py",
    "waste.py",
}

# 순수 층이 import 하면 안 되는 것(앞머리 일치).
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
    "geopy",
    "openpyxl",
    "pandas.io",
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
    "esgapi.inventory.tools.xlsx_reader",
    "esgapi.inventory.engines.scope3.llm_first_1",
)
ALLOWED_LLM = {"esgapi.core.llm.client", "esgapi.core.llm.types"}
# 파일을 열거나 쓰는 pandas 꼴(속성 이름). `read_` 로 시작하는 것은 전부 막는다.
FORBIDDEN_ATTRIBUTES = {
    "ExcelFile",
    "ExcelWriter",
    "to_excel",
    "to_csv",
    "to_pickle",
    "to_parquet",
    "to_feather",
    "to_hdf",
    "to_sql",
    "to_clipboard",
    "to_stata",
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


def test_the_folder_is_the_files_we_think_it_is() -> None:
    assert {path.name for path in FOLDER.glob("*.py")} == EXPECTED_FILES


def test_no_module_imports_files_clocks_randomness_network_django_or_the_other_version() -> None:
    for path in sorted(FOLDER.glob("*.py")):
        offending = sorted(module for module in imported_modules(path) if is_forbidden(module))
        assert offending == [], f"{path.name}: {offending}"


def test_only_the_pure_pieces_of_core_llm_are_imported() -> None:
    used: set[str] = set()
    for path in FOLDER.glob("*.py"):
        used |= {module for module in imported_modules(path) if module.startswith("esgapi.core")}
    assert used <= ALLOWED_LLM
    assert used & ALLOWED_LLM  # 생성 모델을 부르므로 하나는 쓴다(빈 집합으로 통과하지 않게).


def test_no_module_opens_files_through_open_or_pandas() -> None:
    seen = 0
    for path in sorted(FOLDER.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        calls = {
            node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        seen += len(attributes)
        assert "open" not in calls, path.name
        assert sorted(a for a in attributes if a.startswith("read_") or a in FORBIDDEN_ATTRIBUTES) == [], path.name
    assert seen > 0  # 속성을 하나도 못 보면(빈 폴더 등) 이 검사가 빈 채로 통과하지 않게


def test_the_attribute_rule_bites_on_a_planted_line() -> None:
    """양성 대조: 같은 규칙이 `pd.read_excel(data)` 와 `df.to_excel(x)` 를 잡는다."""
    tree = ast.parse("import pandas as pd\npd.read_excel(data)\ndf.to_excel(x)\n")
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert sorted(a for a in attributes if a.startswith("read_") or a in FORBIDDEN_ATTRIBUTES) == [
        "read_excel",
        "to_excel",
    ]


def test_relative_imports_are_resolved() -> None:
    """상대 꼴도 잡는다(ISSUE-207 — 옛 검사는 `ImportFrom.level` 을 버려 상대 꼴을 지나쳤다)."""
    tree = ast.parse("from . import x\nfrom ..y import z\nfrom ... import w\nimport json\n")
    froms = [node for node in tree.body if isinstance(node, ast.ImportFrom)]
    assert [resolve(node, OWN) for node in froms] == [
        "esgapi.inventory.engines.scope3.colab_157",
        "esgapi.inventory.engines.scope3.y",
        "esgapi.inventory.engines",
    ]
    assert modules_in("from . import x\nfrom ..y import z\nimport json\n", OWN) == {
        "esgapi.inventory.engines.scope3.colab_157",
        "esgapi.inventory.engines.scope3.colab_157.x",
        "esgapi.inventory.engines.scope3.y",
        "json",
    }
    assert modules_in("from os import path\n", OWN) == {"os"}
    assert package_of(FOLDER / "distance.py") == OWN
    assert package_of(FOLDER / "sub" / "a.py") == "esgapi.inventory.engines.scope3.colab_157.sub"
