"""분해 일감의 끝을 표(run_jobs)에 적을 꼴로 줄인다: 분해 결과 → 작은 숫자 몇 개, 분해의 문제 → (code, message).

순수하다(django·ninja·psycopg·celery 를 모른다. `.importlinter` 계약 다).

★ 요약에는 **정수와 불리언뿐**이다. 글자를 싣지 않는다: 문서의 글(쪽의 글, 표의 칸, 파일 이름)이 표로 새는 길이 없다.
  분해 결과의 본문은 저장하지 않는다(일감의 `summary` 는 「작은 요약」이고 DB 가 4,096바이트로 막는다).
  키의 집합은 SUMMARY_KEYS 로 굳혔다. 더하려면 여기와 테스트를 같이 고친다.
"""

from typing import Final, Protocol

from esgapi.reconcile.calc.types import DocModel, Extraction, PlaceIndex


class ParsedLike(Protocol):
    """분해 결과의 꼴(reconcile/services/parse.py 의 ParsedInput 이 이 꼴이다).

    calc 는 services 를 import 하지 않는다(순수 층의 import 허용 목록: tests/test_calc_is_pure.py). 꼴로만 받는다.
    """

    @property
    def document(self) -> DocModel: ...
    @property
    def extraction(self) -> Extraction: ...
    @property
    def place_index(self) -> PlaceIndex | None: ...
    @property
    def warnings(self) -> tuple[str, ...]: ...


class ProblemLike(Protocol):
    """분해의 문제의 꼴(같은 파일의 ParseProblem)."""

    @property
    def kind(self) -> str: ...
    @property
    def detail(self) -> str: ...
    @property
    def code(self) -> str | None: ...


SUMMARY_KEYS: Final[tuple[str, ...]] = ("pages", "tables", "facts", "has_places", "warnings")
MAX_MESSAGE_CHARS: Final = 500  # 표의 칸 길이(run_jobs.error_message)


def parse_summary(parsed: ParsedLike) -> dict[str, int | bool]:
    return {
        "pages": parsed.document.source.page_count,  # 쪽 수(파서가 센 것)
        "tables": len(parsed.document.tables),  # 표 수
        "facts": len(parsed.extraction.facts),  # 값 후보 수
        "has_places": parsed.place_index is not None,  # 글자 자리가 같이 왔는가
        "warnings": len(parsed.warnings),  # 파서가 붙인 경고의 수(글은 싣지 않는다)
    }


def problem_code(problem: ProblemLike) -> tuple[str, str]:
    """분해의 문제 → (code, message). code 는 파서가 준 것(`not_a_pdf` …)이 있으면 그것, 없으면 갈래 이름이다.

    message 는 500자에서 자른다.
    """
    return problem.code or problem.kind, problem.detail[:MAX_MESSAGE_CHARS]
