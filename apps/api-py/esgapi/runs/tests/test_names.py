"""runs 는 업무 모듈을 글자로도 부르지 않는다(AST — X1b-2b ㉖, X1a 보고의 n3). .importlinter 계약 차 가 못 보는 길을
막는다: import_module("esgapi.<업무 모듈>…")·__import__(…) 는 import 문이 아니라 계약에 걸리지 않는다.
core 의 같은 검사(core/tests/test_flows_core_names.py)와 같은 꼴이다.

대상: esgapi/runs 아래의 .py 에서 tests/·migrations/ 를 뺀 것. 재는 것: 글자 상수·f-문자열의 글자 조각에
`esgapi.<업무 모듈>` 0, import_module·__import__ 부름 0. 순수 층(돌리지 않는다).
알려진 구멍: 이어 붙인 글자("esgapi." + "inv" + …), getattr(importlib, "import_module")·sys.modules[...] 는 못 본다.
목록 = `.importlinter` 계약 차(runs-knows-no-module)의 금지 목록(MARC-ISSUE-247 — core 의 검사와 한 자리. 여기에
목록을 다시 적지 않는다).
"""

import ast
import configparser
import re
from pathlib import Path

RUNS = Path(__file__).resolve().parents[1]
CONTRACTS = RUNS.parents[1] / ".importlinter"


def forbidden(contract: str) -> tuple[str, ...]:
    """`.importlinter` 계약의 금지 목록(`esgapi.` 를 뗀 이름, 파일 차례). 글로 읽는다(import-linter 를 안 부름)."""
    parser = configparser.ConfigParser()
    parser.read(CONTRACTS, encoding="utf-8")
    names = parser[f"importlinter:contract:{contract}"]["forbidden_modules"].split()
    return tuple(name.removeprefix("esgapi.") for name in names)


BUSINESS = forbidden("runs-knows-no-module")
MODULE_NAME = re.compile(rf"\besgapi\.({'|'.join(BUSINESS)})\b")
DYNAMIC = {"import_module", "__import__"}


def sources() -> list[Path]:
    return sorted(p for p in RUNS.rglob("*.py") if not {"tests", "migrations"} & set(p.relative_to(RUNS).parts))


def literal_text(node: ast.expr) -> str | None:
    """문자열 상수, 또는 f-문자열의 글자 조각을 이은 것. 그 밖은 None."""
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        return "".join(v.value for v in node.values if isinstance(v, ast.Constant) and isinstance(v.value, str))
    return None


def spelled(source: str) -> list[str]:
    """그 소스에서 업무 모듈 이름을 품은 글자(줄과 글)."""
    hits: list[str] = []
    for node in ast.walk(ast.parse(source)):
        text = literal_text(node) if isinstance(node, ast.expr) else None
        if text is not None and MODULE_NAME.search(text):
            hits.append(f"{getattr(node, 'lineno', '?')} {text!r}")
    return hits


def dynamic(source: str) -> list[int]:
    """import_module(…)·importlib.import_module(…)·__import__(…) 의 줄."""
    found: list[int] = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Call):
            func = node.func
            name = func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None
            if name in DYNAMIC:
                found.append(node.lineno)
    return found


def test_runs_spells_no_business_module() -> None:
    files = sources()
    hits = [f"{p.relative_to(RUNS)}:{hit}" for p in files for hit in spelled(p.read_text(encoding="utf-8"))]
    assert hits == []
    assert len(files) > 10  # 분모: 제품 파일을 실제로 읽었다(models·tasks·service 들)
    assert RUNS / "tasks.py" in files and not any("tests" in p.parts for p in files)


def test_runs_imports_nothing_dynamically() -> None:
    hits = [f"{p.relative_to(RUNS)}:{line}" for p in sources() for line in dynamic(p.read_text(encoding="utf-8"))]
    assert hits == []


def test_the_checks_catch_what_they_should() -> None:
    """양성 대조: 지어낸 소스의 글자 상수·f-문자열·동적 import 를 문다(분모: 업무 모듈 밖 이름은 지나간다)."""
    assert spelled('NAME = "esgapi.greenwash"') == ["1 'esgapi.greenwash'"]
    assert spelled('OTHER = f"esgapi.translation.{x}"') != []  # f-문자열(그 안의 글자 조각도 따로 걸린다)
    assert spelled('OK = "esgapi.runs.tasks"\nCORE = "esgapi.core"') == []
    assert dynamic("import importlib\nimportlib.import_module(name)\n__import__(n)") == [2, 3]


def test_the_list_is_the_import_contracts() -> None:
    """MARC-ISSUE-247: 목록은 계약 차 그대로 — 계약 가(core 의 금지 목록)에서 runs 자신을 뺀 것."""
    assert len(BUSINESS) == len(set(BUSINESS)) > 0
    assert "runs" not in BUSINESS
    assert set(BUSINESS) == set(forbidden("core-knows-no-module")) - {"runs"}
    assert "dataverify" in BUSINESS


def test_the_check_catches_each_listed_module() -> None:
    """양성 대조: 목록의 이름마다 지어낸 글을 문다."""
    assert [name for name in BUSINESS if spelled(f'NAME = "esgapi.{name}.x"') != [f"1 'esgapi.{name}.x'"]] == []
