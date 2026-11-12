"""분해 일감의 요약과 문제의 code(esgapi/reconcile/calc/job_summary.py). 순수 층.

★ 문서와 숫자는 전부 지어낸 것이다(synthetic).
"""

import ast
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from esgapi.core.resources.ports.parser import Parsed
from esgapi.core.tests.resource_fakes import FakeParser
from esgapi.reconcile.calc.job_summary import MAX_MESSAGE_CHARS, SUMMARY_KEYS, parse_summary, problem_code
from esgapi.reconcile.service.services.parse import PARSE_PROBLEM_KINDS, ParsedInput, ParseProblem, parse_and_extract
from esgapi.reconcile.tests.support import TableSpec, synthetic_document

SYNTHETIC = Path(__file__).resolve().parent / "golden" / "synthetic"
PDF = b"%PDF-1.7 (synthetic bytes, not a real pdf)"
SUMMARY_MAX_OCTETS = 4096  # core/migrations/0002 의 CHECK


def load(name: str) -> Any:
    return json.loads((SYNTHETIC / name).read_text(encoding="utf-8"))


def parsed(*, places: bool = True, warnings: tuple[str, ...] = ()) -> ParsedInput:
    result = Parsed(load("document.json"), load("char-places.json") if places else None, warnings)
    parser = FakeParser({hashlib.sha256(PDF).hexdigest(): result})
    found = parse_and_extract(PDF, file_name="reconcile-doc.synthetic.pdf", parser=parser, doc_id="doc")
    assert isinstance(found, ParsedInput)
    return found


def big() -> ParsedInput:
    """큰 가짜 문서: 표 200개 × 30행 × 6열. 요약의 크기가 문서의 크기를 따라 자라지 않는다는 것을 본다."""
    from esgapi.reconcile.calc.facts import extract_document

    marker = "표식-글자-" * 50
    tables = [
        TableSpec(
            id=f"t{index}",
            cells=[["항목", "2023", "2024", "2025", "단위", marker]]
            + [[f"행 {row}", "1,234.5", "2,345.6", "3,456.7", "tCO2e", marker] for row in range(30)],
            page=1 + index % 400,
        )
        for index in range(200)
    ]
    document = synthetic_document("big.synthetic.pdf", tables, pages=400)
    return ParsedInput(
        document, extract_document(document, "big"), None, tuple(f"경고 {n} {marker}" for n in range(50))
    )


def test_the_summary_of_the_synthetic_document() -> None:
    assert parse_summary(parsed()) == {"pages": 3, "tables": 5, "facts": 99, "has_places": True, "warnings": 0}
    assert parse_summary(parsed(places=False, warnings=("느리다", "글자 층이 없는 쪽이 있다"))) == {
        "pages": 3,
        "tables": 5,
        "facts": 99,
        "has_places": False,
        "warnings": 2,
    }


@pytest.mark.parametrize("make", [parsed, big])
def test_the_summary_has_exactly_the_fixed_keys_and_only_numbers_and_booleans(make: Any) -> None:
    summary = parse_summary(make())
    assert tuple(summary) == SUMMARY_KEYS == ("pages", "tables", "facts", "has_places", "warnings")
    # 글자가 없다(문서의 글이 요약으로 새는 길이 없다). bool 은 int 의 아래 타입이라 타입을 글자로 견준다.
    assert {key: type(value).__name__ for key, value in summary.items()} == {
        "pages": "int",
        "tables": "int",
        "facts": "int",
        "has_places": "bool",
        "warnings": "int",
    }
    encoded = json.dumps(summary, ensure_ascii=False).encode()
    assert len(encoded) < SUMMARY_MAX_OCTETS / 10, len(encoded)  # 분모: 지은 문서 하나와 큰 가짜 문서 하나
    assert "표식" not in encoded.decode()


def test_the_big_document_is_big_and_its_summary_is_not() -> None:
    document = big()
    summary = parse_summary(document)
    assert (summary["pages"], summary["tables"], summary["warnings"]) == (400, 200, 50)
    assert summary["facts"] > 10_000
    assert len(json.dumps(summary).encode()) < 100


@pytest.mark.parametrize("kind", PARSE_PROBLEM_KINDS)
def test_a_problem_without_a_parser_code_is_named_by_its_branch(kind: Any) -> None:
    assert problem_code(ParseProblem(kind, "무슨 일인지")) == (kind, "무슨 일인지")


def test_a_parser_code_wins_over_the_branch_name_and_the_message_is_cut() -> None:
    problem = ParseProblem("rejected", "가" * 800, code="not_a_pdf", status=422)
    code, message = problem_code(problem)
    assert code == "not_a_pdf"
    assert message == "가" * MAX_MESSAGE_CHARS and MAX_MESSAGE_CHARS == 500
    # 빈 code 는 없는 것이다
    assert problem_code(ParseProblem("rejected", "x", code=""))[0] == "rejected"


def _resolve(node: ast.ImportFrom, package: str) -> str:
    """`from <점들><이름> import …` 의 절대 이름. 점 하나 = 그 파일의 꾸러미, 둘 = 그 위(dataverify
    tests/engines/colab_156/test_purity.py 의 판별 복사 — ISSUE-207)."""
    if node.level == 0:
        return node.module or ""
    parts = package.split(".")
    base = parts[: len(parts) - (node.level - 1)]
    return ".".join([*base, node.module] if node.module else base)


# 사본에서 뜻이 없다: mutmut 이 심은 트램펄린(mutmut.mutation.trampoline import)을 소스에서 읽는다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_the_summary_rules_import_neither_celery_nor_django() -> None:
    """뿌리가 아니라 **풀린 전체 이름**을 허용 목록에 견준다(MARC-ISSUE-436 N1 — 뿌리만 보면 `esgapi.config` 의
    celery 가 지나간다): 표준 라이브러리는 typing 하나, esgapi 는 esgapi.reconcile.calc 와 그 아래만. 늘리려면 까닭을
    적는다(test_calc_is_pure.py 도 calc/*.py 전부를 허용 목록으로 본다)."""
    path = Path(__file__).resolve().parents[1] / "calc" / "job_summary.py"
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(_resolve(node, "esgapi.reconcile.calc"))  # 상대 꼴은 그 꾸러미 기준으로 푼다

    def allowed(name: str) -> bool:
        return name == "typing" or name == "esgapi.reconcile.calc" or name.startswith("esgapi.reconcile.calc.")

    outside = sorted(name for name in names if not allowed(name))
    assert outside == [], f"calc/job_summary.py 가 허용 목록 밖을 import 한다: {outside}"
    assert "typing" in names and any(name.startswith("esgapi.reconcile.calc") for name in names)
