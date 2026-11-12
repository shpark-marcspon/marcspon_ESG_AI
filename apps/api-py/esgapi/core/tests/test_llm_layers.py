"""core/llm 의 층 규칙과, 순수 층의 테스트가 네트워크로 나가지 못한다는 것. 순수 층."""

import ast
import configparser
import socket
from pathlib import Path

import pytest

from conftest import NetworkBlockedError

CORE = Path(__file__).resolve().parents[1]
LLM = CORE / "llm"
# Django 를 아는 파일 둘. 순수성 계약에 들지 않는다. sink_db 는 DB 싱크다(sinks/ 아래가 아니라 여기 있는 까닭:
# 계약이 sinks 를 폴더째 문다).
DJANGO_AWARE = {"esgapi.core.llm.setup", "esgapi.core.llm.sink_db"}


def contract_sources() -> set[str]:
    parser = configparser.ConfigParser()
    parser.read(LLM / "purity.importlinter", encoding="utf-8")
    return set(parser["importlinter:contract:llm-pure"]["source_modules"].split())


def test_purity_contract_lists_every_module_of_the_call_layer() -> None:
    """core/llm 에 모듈을 더하고 계약에 안 적으면 그 모듈은 지켜지지 않는다. 폴더와 목록을 견준다."""
    top = {f"esgapi.core.llm.{path.stem}" for path in LLM.glob("*.py") if path.stem != "__init__"}
    packages = {f"esgapi.core.llm.{path.parent.name}" for path in LLM.glob("*/__init__.py")}
    expected = (top - DJANGO_AWARE) | packages | {"esgapi.core.resources.ports.llm", "esgapi.core.resources.llm"}
    assert len(top) >= 12  # 폴더를 못 읽어 빈 목록끼리 같다고 하는 일을 막는다
    assert contract_sources() == expected


def test_package_init_imports_nothing() -> None:
    """__init__.py 는 계약에 적을 수 없어(적으면 setup 까지 걸린다) 여기서 잰다: 아무것도 import 하지 않는다."""
    for init in (LLM / "__init__.py", LLM / "providers" / "__init__.py", LLM / "sinks" / "__init__.py"):
        tree = ast.parse(init.read_text(encoding="utf-8"))
        imports = [node for node in ast.walk(tree) if isinstance(node, ast.Import | ast.ImportFrom)]
        assert imports == [], init


def test_only_setup_imports_django_inside_the_call_layer() -> None:
    """계약(import-linter)과 따로, 소스를 직접 읽어 한 번 더 잰다: django 를 아는 것은 setup.py(core.conf 에 닿는다)와
    sink_db.py(DB 싱크) 둘뿐이다.
    """
    aware: set[str] = set()
    files = [*LLM.rglob("*.py"), CORE / "resources" / "ports" / "llm.py", CORE / "resources" / "llm.py"]
    assert len(files) >= 20
    for path in files:
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [alias.name for alias in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            if any(
                name.split(".")[0] in {"django", "ninja", "psycopg"} or name == "esgapi.core.conf" for name in names
            ):
                aware.add(path.name)
    assert aware == {"setup.py", "sink_db.py"}


# 사본에서 뜻이 없다: mutmut 이 한 프로세스에서 pytest 를 거듭 불러 conftest 가 두 벌이 되어
# NetworkBlockedError 가 다른 클래스다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_socket_connections_are_blocked_in_these_tests(blocked_network: list[object]) -> None:
    """고정물(뿌리 conftest.py 의 blocked_network)이 꺼지면 이 테스트가 빨개진다: 막힌 것이 아니라 그냥 거절당한다."""
    with pytest.raises(NetworkBlockedError):
        socket.create_connection(("127.0.0.1", 9), timeout=0.2)
    with pytest.raises(NetworkBlockedError):
        socket.getaddrinfo("provider.invalid", 443)
    with pytest.raises(NetworkBlockedError), socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw:
        raw.connect(("127.0.0.1", 9))
    assert blocked_network == ["127.0.0.1", "provider.invalid", ("127.0.0.1", 9)]
