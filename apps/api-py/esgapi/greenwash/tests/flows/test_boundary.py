"""경계: flows/·tools/·outputs/·contracts/ 의 모듈(흐름·어댑터·도구·엑셀·비교·꼴·등록), engines/e0 의 사본 아닌 둘과
apps.py 가 SDK 클라이언트를 짓지 않고 설정·환경 변수·파일·소켓에 닿지 않는다.

AST 로 센다: import 의 모듈 이름(openai·anthropic·google.genai·boto3·socket·os), os.environ·getenv 의 이름,
open(…) 부르기.
흐름은 어댑터로만 바깥에 닿는다(X2 「흐름 인터페이스 한 장」 개정 3). 결과 꼴 검사는 pydantic 이고
jsonschema·rpds 를 들이지 않는다(D0 가 알린 rpds-py 판 차이가 대조에 닿지 않게 — 둘째 테스트가 engines/ 까지
넓혀 센다).
"""

import ast
from pathlib import Path

GREENWASH = Path(__file__).resolve().parents[2]
FORBIDDEN_MODULES = ("openai", "anthropic", "google.genai", "boto3", "socket", "os", "importlib", "jsonschema", "rpds")
FORBIDDEN_NAMES = ("environ", "getenv", "putenv", "__import__", "read_text", "read_bytes", "write_text", "write_bytes")


def imported(tree: ast.AST) -> list[str]:
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module is not None:
            names.append(node.module)
    return names


def hits(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = [
        f"import {name}"
        for name in imported(tree)
        if any(name == m or name.startswith(m + ".") for m in FORBIDDEN_MODULES)
    ]
    for node in ast.walk(tree):
        if isinstance(node, ast.Name | ast.Attribute):
            name = node.id if isinstance(node, ast.Name) else node.attr
            if name in FORBIDDEN_NAMES:
                found.append(f"name {name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "open":
            found.append("open(...)")
    return found


def test_flow_modules_touch_nothing_outside_their_adapters() -> None:
    folders = ("flows", "tools", "outputs", "contracts", "engines/g1")
    # engines/ 의 사본은 이 검사 밖이다. 사본 아닌 둘(GW1 결과 조립·꼴 있는 겉)은 이름으로 훑는다.
    not_copies = [GREENWASH / "engines" / "e0" / "result.py", GREENWASH / "engines" / "e0" / "gw1.py"]
    modules = [*(p for d in folders for p in sorted((GREENWASH / d).glob("*.py"))), *not_copies, GREENWASH / "apps.py"]
    names = {p.name for p in modules}
    assert names >= {
        "colab_e0.py",
        "registration.py",
        "xlsx.py",
        "shapes.py",
        "llm_bridge.py",
        "coordinates.py",
        "result.py",
        "apps.py",
    }
    assert {str(p.relative_to(GREENWASH)): hits(p) for p in modules} == {
        str(p.relative_to(GREENWASH)): [] for p in modules
    }


def test_the_copies_and_flows_do_not_import_jsonschema_or_rpds() -> None:
    paths = sorted((GREENWASH / "engines").rglob("*.py")) + [
        p for d in ("flows", "tools", "outputs", "contracts") for p in sorted((GREENWASH / d).glob("*.py"))
    ]
    bad = [
        f"{p.relative_to(GREENWASH)}: {name}"
        for p in paths
        for name in imported(ast.parse(p.read_text(encoding="utf-8")))
        if name.split(".")[0] in ("jsonschema", "rpds")
    ]
    assert bad == []


def test_the_scan_catches_what_it_should(tmp_path: Path) -> None:
    planted = tmp_path / "planted.py"
    planted.write_text(
        "import openai\nimport os\nx = os.environ['K']\nopen('k')\nfrom os import getenv\n"
        "import importlib\nm = __import__('socket')\nfrom pathlib import Path\nPath('k').read_text()\n",
        encoding="utf-8",
    )
    want = ["import openai", "import os", "import os", "name environ", "open(...)", "import importlib"]
    want += ["name __import__", "name read_text"]
    assert sorted(hits(planted)) == sorted(want)
