"""core 는 업무 모듈을 글자로도 부르지 않는다(AST). .importlinter 계약 가가 못 보는 길을 막는다:
import_module("esgapi.<업무 모듈>…")·__import__(…) 는 import 문이 아니라 계약에 걸리지 않는다.

대상: esgapi/core 아래의 .py 전부에서 core/tests/ 를 뺀 것(흐름만이 아니다 — core 의 어느 파일이든).
알려진 구멍: 이어 붙인 글자("esgapi." + "inv" + …)는 3번(글자 아닌 인자)으로만 잡히고,
getattr(importlib, "import_module")·importlib.util.find_spec·sys.modules[...] 처럼 이름을 감추는 길은 못 본다.
목록 = `.importlinter` 계약 가(core-knows-no-module)의 금지 목록(MARC-ISSUE-247 — runs 의 검사와 한 자리. 여기에
목록을 다시 적지 않는다).
"""

import ast
import configparser
import re
from pathlib import Path

CORE = Path(__file__).resolve().parents[1]
APPS_LIST = CORE.parent / "config" / "apps_list.py"
CONTRACTS = CORE.parents[1] / ".importlinter"


def forbidden(contract: str) -> tuple[str, ...]:
    """`.importlinter` 계약의 금지 목록(`esgapi.` 를 뗀 이름, 파일 차례). 글로 읽는다(import-linter 를 안 부름)."""
    parser = configparser.ConfigParser()
    parser.read(CONTRACTS, encoding="utf-8")
    names = parser[f"importlinter:contract:{contract}"]["forbidden_modules"].split()
    return tuple(name.removeprefix("esgapi.") for name in names)


BUSINESS = forbidden("core-knows-no-module")
MODULE_NAME = re.compile(rf"\besgapi\.({'|'.join(BUSINESS)})\b")
DYNAMIC = {"import_module", "__import__"}
# 글자가 아닌 첫 인자로 허용하는 것: (core 안의 파일, 인자의 글)
ALLOWED_NON_LITERAL = {("management/commands/export_openapi.py", "settings.ROOT_URLCONF")}


def sources() -> list[Path]:
    return sorted(p for p in CORE.rglob("*.py") if p.relative_to(CORE).parts[0] != "tests")


def literal_text(node: ast.expr) -> str | None:
    """문자열 상수, 또는 f-문자열의 글자 조각을 이은 것. 그 밖은 None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def dynamic_imports() -> list[tuple[str, int, ast.expr]]:
    """(core 안의 파일, 줄, 첫 인자) — import_module(…)·importlib.import_module(…)·__import__(…)."""
    found: list[tuple[str, int, ast.expr]] = []
    for path in sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.Call) or not node.args:
                continue
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name in DYNAMIC:
                found.append((str(path.relative_to(CORE)), node.lineno, node.args[0]))
    return found


def test_core_spells_no_business_module() -> None:
    hits: list[str] = []
    for path in sources():
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            text = literal_text(node) if isinstance(node, ast.expr) else None
            if text is not None and MODULE_NAME.search(text):
                hits.append(f"{path.relative_to(CORE)}:{getattr(node, 'lineno', '?')} {text!r}")
    assert hits == []


def test_the_business_module_list_is_complete() -> None:
    """config/apps_list.py 를 글로 읽는다(import 하지 않는다). 새 업무 앱이 생기면 위의 목록에 더한다."""
    tree = ast.parse(APPS_LIST.read_text(encoding="utf-8"))
    apps = {
        node.value.removeprefix("esgapi.")
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.startswith("esgapi.")
    }
    assert "core" in apps
    assert apps - {"core"}
    assert apps - {"core"} <= set(BUSINESS)


def test_core_imports_dynamically_only_inside_core() -> None:
    hits: list[str] = []
    seen: list[tuple[str, str]] = []
    for rel, line, arg in dynamic_imports():
        text = literal_text(arg)
        seen.append((rel, ast.unparse(arg)))
        if text is None:
            if (rel, ast.unparse(arg)) not in ALLOWED_NON_LITERAL:
                hits.append(f"{rel}:{line} {ast.unparse(arg)}")
        elif not text.startswith("esgapi.core."):
            hits.append(f"{rel}:{line} {text!r}")
    # 비지 않음: 검사가 실제로 무언가를 본다
    assert ("management/commands/export_openapi.py", "settings.ROOT_URLCONF") in seen
    assert hits == []


def test_the_list_is_the_import_contracts() -> None:
    """MARC-ISSUE-247: 목록은 계약 가 그대로 — 계약 차(runs 의 금지 목록)에 runs 를 더한 것. 빠졌던 dataverify 포함."""
    assert len(BUSINESS) == len(set(BUSINESS)) > 0
    assert set(BUSINESS) == set(forbidden("runs-knows-no-module")) | {"runs"}
    assert "dataverify" in BUSINESS


def test_the_check_catches_each_listed_module() -> None:
    """양성 대조: 목록의 이름마다 지어낸 글을 문다(분모: core 자신은 지나간다)."""
    assert [name for name in BUSINESS if not MODULE_NAME.search(f'"esgapi.{name}.x"')] == []
    assert not MODULE_NAME.search('"esgapi.core.flows"')
