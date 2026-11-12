"""흐름 scope3.colab@157 의 끼움(core/flows/binding.py 의 RunBinding + RunFactsBinding — 밴드 S3K1). apps.py 의
ready() 가 REGISTRY 곁에 `BINDINGS.register(FLOW_ID, Scope3ColabBinding(factor_book=…, runs_enabled=…))` 로 단다.

    check_options(options)      옵션은 {reportYear: int} 하나. 어기면 RunOptionsRejected(<해요체 한 문장 — 열쇠 이름만,
                                값은 싣지 않는다>). 계수 책 포트가 「없음」이면 그것도 거절(배포 누락 — 행 0)
    versions(options)           {"engine": "colab_157", "flow": FLOW_ID, "route": ROUTE}
    versions_with(options, *, company_id)
                                versions 그대로(회사별 판 없음 — 회사 꼬리표를 받으려고 둘째 꼴을 갖춘다)
    inputs_with(document, options, *, company_id, versions)
                                ColabInputs(template=문서 바이트, report_year=options.reportYear, route=ROUTE,
                                tags=(회사 id 글자, inventory.scope3)) — 데이터 검증 끼움의 꼬리표 꼴
    inputs(document, options)   막아 둠(NotImplementedError) — 회사 없이는 호출 기록의 꼬리표를 지을 수 없다. 포트 꼴을
                                맞추려고 있을 뿐이고 실행기는 늘 inputs_with 를 부른다
    adapters(ctx)               ColabAdapters(llm=ctx.llm(), factor_book=<포트 바이트 → read_workbook>,
                                geocoder=NoGeocoder()). 책이 없거나 못 읽으면 FactorBookUnreadable(실행 error_code
                                internal — 표 runs/calc/errors.py 에 없는 예외. 글은 워커 로그에만)

받기 차례와 문장(어기는 첫 것 하나):
    스위치 꺼짐                    「Scope 3 실행은 아직 열려 있지 않아요. 운영자에게 알려 주세요」(MARC-ISSUE-499)
    모르는 열쇠                    「알 수 없는 옵션이에요: <열쇠, 쉼표로>」
    reportYear 빠짐·int 아님·참거짓·1990 앞·올해(Asia/Seoul) 뒤
                                   「옵션 reportYear의 값이 맞지 않아요」
    계수 책 없음                   「Scope 3 배출계수 책이 배포에 없어요. 운영자에게 알려 주세요」

셈의 연도 정본은 options.reportYear 다. 문서(템플릿)의 연도 칸은 견주지 않는다(발주서 Q1).
지오코더는 NoGeocoder(「늘 못 찾음」 — 실제 공급원 MARC-ENT-167 held). 코랩대로 AI 직선거리 갈래로 간다.

이 파일은 순수다(django 0, 파일·경로 0). 계수 책 바이트는 apps.py 가 꽂은 포트(service/utils/scope3_files.py)로만 본다.
"""

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import UTC, date, datetime
from typing import Final, Protocol
from zoneinfo import ZoneInfo

from esgapi.core.flows.binding import DocumentInput, RunContext, RunOptionsRejected
from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.colab_157.ports import NoGeocoder
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

ENGINE: Final = "colab_157"
FLOW_ID: Final = colab.FLOW.id
MODULE: Final = colab.FLOW.module
ROUTE: Final = "standard-openai-41"
"""LLM 경로(core/llm/data/models.json). 코랩 원본은 Claude 였다 — 서버 키는 OpenAI 라 가장 가까운 형제(데이터 검증
colab_156)와 같은 경로를 쓴다(S3K1 C0 ★F)."""
YEAR_FIRST: Final = 1990
"""고를 수 있는 첫 해(인덱스 선택 service/utils/index_selection.YEAR_FIRST 와 같은 값 — 흐름은 service 를 모른다)."""
SEOUL: Final = ZoneInfo("Asia/Seoul")
OPTION_KEYS: Final = frozenset({"reportYear"})


def clock() -> datetime:
    """지금(UTC). 「올해」의 원천 하나 — 시험은 이 모듈 속성을 갈아 끼운다."""
    return datetime.now(UTC)


def today() -> date:
    """지금의 Asia/Seoul 날짜."""
    return clock().astimezone(SEOUL).date()


@dataclass(frozen=True, slots=True)
class FileMissing:
    """포트가 그 파일을 찾지 못했다(배포 누락). 예외로 숨기지 않는 갈래다."""

    name: str


class PackagedFile(Protocol):
    """패키지에 실린 파일 하나의 바이트 포트(순수). 구현은 service/utils/scope3_files.py."""

    def read(self) -> bytes | FileMissing: ...


class FactorBookUnreadable(Exception):
    """실행이 돌 때 계수 책이 없거나 읽히지 않는다(배포 결함). 실행은 실패한다 — error_code internal(S3K1 C0 ★J)."""


def accept_options(options: Mapping[str, object]) -> int:
    """옵션을 받아 셈 연도를 돌려준다. 어기면 RunOptionsRejected(머리말의 차례·문장)."""
    unknown = sorted(str(key) for key in options if key not in OPTION_KEYS)
    if unknown:
        raise RunOptionsRejected(f"알 수 없는 옵션이에요: {', '.join(unknown)}")
    year = options.get("reportYear")
    if not isinstance(year, int) or isinstance(year, bool) or not YEAR_FIRST <= year <= today().year:
        raise RunOptionsRejected("옵션 reportYear의 값이 맞지 않아요")
    return year


class Scope3ColabBinding:
    """scope3.colab@157 의 끼움(머리말)."""

    def __init__(self, *, factor_book: PackagedFile, runs_enabled: Callable[[], bool]) -> None:
        self.factor_book = factor_book
        self.runs_enabled = runs_enabled

    def check_options(self, options: Mapping[str, object]) -> None:
        if not self.runs_enabled():
            raise RunOptionsRejected("Scope 3 실행은 아직 열려 있지 않아요. 운영자에게 알려 주세요")
        accept_options(options)
        if isinstance(self.factor_book.read(), FileMissing):
            raise RunOptionsRejected("Scope 3 배출계수 책이 배포에 없어요. 운영자에게 알려 주세요")

    def versions(self, options: Mapping[str, object]) -> dict[str, object]:
        return {"engine": ENGINE, "flow": FLOW_ID, "route": ROUTE}

    def versions_with(self, options: Mapping[str, object], *, company_id: int) -> dict[str, object]:
        return self.versions(options)

    def inputs(self, document: DocumentInput, options: Mapping[str, object]) -> colab.ColabInputs:
        raise NotImplementedError("회사 꼬리표가 필요하다 — inputs_with 로 부른다")

    def inputs_with(
        self, document: DocumentInput, options: Mapping[str, object], *, company_id: int, versions: Mapping[str, object]
    ) -> colab.ColabInputs:
        return colab.ColabInputs(
            template=document.content,
            report_year=accept_options(options),
            route=ROUTE,
            tags=Tags(tenant=str(company_id), module=MODULE),
        )

    def adapters(self, ctx: RunContext) -> colab.ColabAdapters:
        content = self.factor_book.read()
        if isinstance(content, FileMissing):
            raise FactorBookUnreadable(f"계수 책 {content.name} 이 없다")
        book = read_workbook(content)
        if isinstance(book, ReaderProblem):
            raise FactorBookUnreadable(f"계수 책을 읽지 못했다: {book.kind} {book.where}")
        return colab.ColabAdapters(llm=ctx.llm(), factor_book=book, geocoder=NoGeocoder())
