"""관측 폴더의 층 규칙. 순수 층.

context.py 와 jsonlog.py 는 순수다: 표준 라이브러리와 (jsonlog 는) context 만 들인다.
middleware.py 는 django 를 알지만 esgapi 에서는 context 만 들인다. gunicorn.conf.py 는 jsonlog 만 들인다.
`.importlinter` 의 순수 계약에 이 둘의 줄이 서기 전까지는 이 테스트가 그 사이를 지킨다.
"""

import ast
import sys
from pathlib import Path

import pytest

ESGAPI = Path(__file__).resolve().parents[2]
OBSERVABILITY = ESGAPI / "core" / "observability"
CONTEXT = "esgapi.core.observability.context"


def imports_of(path: Path) -> set[str]:
    """그 파일이 들이는 모듈의 이름 전부(함수 안에서 들이는 것도 센다)."""
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0, f"{path.name}: 상대 import 는 쓰지 않는다(이 테스트가 못 읽는다)"
            assert node.module is not None
            names.add(node.module)
    return names


def outside_the_standard_library(names: set[str]) -> set[str]:
    return {name for name in names if name.split(".")[0] not in sys.stdlib_module_names}


def test_the_package_init_imports_nothing() -> None:
    assert imports_of(OBSERVABILITY / "__init__.py") == set()


def test_context_imports_only_the_standard_library() -> None:
    names = imports_of(OBSERVABILITY / "context.py")
    assert names  # 파일을 못 읽어 빈 집합끼리 같다고 하는 일을 막는다
    assert outside_the_standard_library(names) == set()


def test_jsonlog_imports_only_the_standard_library_and_context() -> None:
    names = imports_of(OBSERVABILITY / "jsonlog.py")
    assert CONTEXT in names
    assert outside_the_standard_library(names) == {CONTEXT}


@pytest.mark.parametrize("name", ["context.py", "jsonlog.py"])
def test_the_pure_two_know_no_framework(name: str) -> None:
    tops = {module.split(".")[0] for module in imports_of(OBSERVABILITY / name)}
    assert tops.isdisjoint({"django", "ninja", "psycopg", "celery", "kombu", "gunicorn"})


def esgapi_imports_of(path: Path) -> set[str]:
    return {name for name in imports_of(path) if name.split(".")[0] == "esgapi"}


def test_the_middleware_imports_only_context_from_esgapi() -> None:
    """테넌트·세션·설정을 모른다(그래서 맨 앞에 설 수 있다). celery 도 들이지 않는다."""
    path = OBSERVABILITY / "middleware.py"
    assert esgapi_imports_of(path) == {CONTEXT}
    assert {name.split(".")[0] for name in imports_of(path)}.isdisjoint({"celery", "kombu", "psycopg", "ninja"})


def test_the_gunicorn_config_imports_only_jsonlog_from_esgapi() -> None:
    """gunicorn 의 주 프로세스가 설정을 읽을 때 Django 가 뜨지 않는다."""
    path = ESGAPI.parent / "gunicorn.conf.py"
    assert esgapi_imports_of(path) == {"esgapi.core.observability.jsonlog"}
    assert outside_the_standard_library(imports_of(path)) == {"esgapi.core.observability.jsonlog"}


def test_nothing_in_the_folder_imports_celery() -> None:
    for path in sorted(OBSERVABILITY.glob("*.py")):
        assert {name.split(".")[0] for name in imports_of(path)}.isdisjoint({"celery", "kombu"}), path.name
