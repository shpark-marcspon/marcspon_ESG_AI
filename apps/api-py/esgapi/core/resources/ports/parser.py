"""포트: 문서 파서. 「PDF 바이트 → (문서 모델, 글자 자리[, 도표 라벨])」.

구현은 core/resources/parser.py 의 make(name) 이 고른다(http). 시험의 가짜는 core/tests/resource_fakes.py.
포트는 **JSON 값만** 넘긴다(dict). core 는 업무 모듈을 모른다: 꼴 검증은 받는 쪽(reconcile/calc 의 document·places)이
한다.
원본을 어디서 읽어 오는지(저장소)는 부르는 쪽의 일이다. 포트는 주소가 아니라 바이트를 받는다.

실패는 던지지 않고 갈래로 돌려준다:
  rejected          이 입력은 다시 해도 안 된다(파서의 4xx: PDF 가 아니다, 암호가 걸렸다 …)
  unavailable       잠깐의 문제일 수 있다(파서의 5xx, 연결 실패, 시간 초과). 다시 해 볼 수 있다
  invalid_response  파서가 200 을 냈는데 약속한 꼴이 아니다(JSON 이 아니다, 봉투가 틀리다, 글자 자리가 없다, 너무 크다)
"""

from dataclasses import dataclass
from typing import Any, Literal, Protocol

ParseFailureKind = Literal["rejected", "unavailable", "invalid_response"]
PARSE_FAILURE_KINDS: tuple[ParseFailureKind, ...] = ("rejected", "unavailable", "invalid_response")


@dataclass(frozen=True, slots=True)
class Parsed:
    document: dict[str, Any]  # 문서 모델 0.1 (document.json 의 꼴)
    # 글자 자리 0.1 (char-places.json 의 꼴). http 어댑터는 늘 채운다(없으면 invalid_response 다).
    # None 은 글자 자리 없이 분해한 산출을 그대로 돌려주는 가짜 어댑터에서만 나온다.
    char_places: dict[str, Any] | None
    warnings: tuple[str, ...] = ()
    # 도표 라벨 0.1 (chart-labels.json 의 꼴, 밴드 CHL1). `charts=True` 로 부른 판 2 에서만 온다(http 어댑터는 그때
    # 늘 채운다 — 없으면 invalid_response). None = 부르지 않음(저장하면 칸 NULL).
    chart_labels: dict[str, Any] | None = None
    ok: Literal[True] = True


@dataclass(frozen=True, slots=True)
class ParseFailureDetail:
    status: int | None  # 파서가 낸 HTTP 상태 코드. 응답을 받지 못했으면 None
    code: (
        str | None
        # 파서의 오류 본문 {"detail": {"code", "message"}} 의 code (`password_protected`, `not_a_pdf` …). 그 꼴이 아니면
        # None
    )
    message: str


@dataclass(frozen=True, slots=True)
class ParseFailed:
    kind: ParseFailureKind
    detail: ParseFailureDetail
    ok: Literal[False] = False


ParseResult = Parsed | ParseFailed


class DocumentParser(Protocol):
    def parse(self, pdf: bytes, *, file_name: str, layout: int = 1, charts: bool = False) -> ParseResult:
        """PDF 하나를 분해한다. 실패를 던지지 않고 `ParseFailed` 의 갈래로 돌려준다.

        layout: 파서의 분해 판(1 = 기본 — 그린워싱·대조가 쓰는 판, 2 = 번역 판 — 밴드 TRD2). 모르는 판은 파서가
        422 `bad_layout`(rejected)으로 거절한다.
        charts: 도표 라벨도 받는다(판 2 에만 — 밴드 CHL1). 판 2 가 아니면 파서가 422 `bad_charts`(rejected).
        """
        ...
