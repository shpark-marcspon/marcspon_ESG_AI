# pyright: reportMissingTypeStubs=false, reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""태스크의 등록과 얇음(esgapi/reconcile/tasks.py). 순수 층: 등록된 이름과 import 목록만 본다(돌리지 않는다)."""

import ast
import configparser
from pathlib import Path

from esgapi.config.celery import app
from esgapi.core.calc.documents import JOB_KINDS
from esgapi.core.calc.jobs import task_name
from esgapi.reconcile import tasks

API_PY = Path(__file__).resolve().parents[3]


def test_the_parse_task_is_registered_under_the_name_the_hook_sends() -> None:
    assert tasks.parse_job.name == "jobs.parse" == task_name("parse")
    assert app.tasks["jobs.parse"].name == tasks.parse_job.name
    assert app.tasks["jobs.parse"].run.__func__ is tasks.run_parse_job
    # 일감의 종류마다 그 이름의 태스크가 있다(종류를 더하고 태스크를 안 만들면 여기서 빨개진다).
    ours = sorted(name for name in app.tasks if name.startswith("jobs."))
    assert ours == sorted(task_name(kind) for kind in JOB_KINDS)


def test_the_task_takes_the_two_ids_by_keyword_only() -> None:
    import inspect

    parameters = inspect.signature(tasks.run_parse_job).parameters
    assert list(parameters) == ["self", "company_id", "job_id"]
    assert [parameters[name].kind for name in ("company_id", "job_id")] == [inspect.Parameter.KEYWORD_ONLY] * 2


def _resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


def test_the_task_file_does_not_import_models_directly() -> None:
    imported: set[str] = set()
    for node in ast.walk(ast.parse((API_PY / "esgapi" / "reconcile" / "tasks.py").read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            imported.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            module = _resolve(node, "esgapi.reconcile")  # 상대 꼴은 tasks.py 의 꾸러미 기준으로 푼다
            imported.update({module, *(f"{module}.{alias.name}" for alias in node.names)})
    assert not [name for name in imported if name.endswith(".models") or ".models." in name]


def test_contract_ra_covers_task_files() -> None:
    """`.importlinter` 계약 (라)가 `esgapi.*.tasks` 를 문다(이름에도 tasks 가 있다). 계약은 모두 열아홉이다."""
    parser = configparser.ConfigParser()
    parser.read(API_PY / ".importlinter", encoding="utf-8")
    contract = parser["importlinter:contract:api-knows-no-models"]
    assert contract["source_modules"].split() == ["esgapi.*.api", "esgapi.*.service.apis", "esgapi.*.tasks"]
    assert contract["forbidden_modules"].split() == ["esgapi.*.models"]
    assert "tasks" in contract["name"]
    assert len([name for name in parser.sections() if name.startswith("importlinter:contract:")]) == 19
