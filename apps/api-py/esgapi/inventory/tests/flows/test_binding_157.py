"""S3K1 ① 끼움 scope3.colab@157(flows/binding_157.py): 옵션 받기 표, 입력·어댑터·판, 계수 책 포트, 등록·기본 흐름.

순수 층: DB 0. 템플릿·계수 책은 지어낸 것(s3sheets_support·colab_157 support). 저장소의 xlsx 둘은 읽히는지만 본다.
"""

import hashlib
import inspect
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from esgapi.core.flows.binding import BINDINGS, DocumentInput, RunBinding, RunFactsBinding, RunOptionsRejected
from esgapi.core.flows.carriers import CARRIERS, NO_ROWS
from esgapi.core.flows.registry import REGISTRY
from esgapi.core.llm.client import LlmClient
from esgapi.core.llm.embedding import EmbeddingClient
from esgapi.core.llm.types import Tags
from esgapi.inventory.engines.scope3.colab_157.ports import NoGeocoder
from esgapi.inventory.flows import binding_157
from esgapi.inventory.flows import scope3_colab_157 as colab
from esgapi.inventory.flows.binding_157 import (
    FactorBookUnreadable,
    FileMissing,
    Scope3ColabBinding,
    accept_options,
)
from esgapi.inventory.service.utils import scope3_files
from esgapi.inventory.tests.engines.scope3.colab_157.support import xlsx_bytes
from esgapi.inventory.tests.s3sheets_support import MiB, padded, sample_factor_book, sample_template
from esgapi.inventory.tools.xlsx_reader import ReaderProblem, read_workbook

BOOK_BYTES = xlsx_bytes(sample_factor_book())
TEMPLATE_BYTES = xlsx_bytes(sample_template())
SHA256 = {
    "scope3-template-v2.2.xlsx": "c51abfd6e023424b3194892afc2878b8a101ea355ce7c301874296301bbec42e",
    "scope3-factor-book.xlsx": "2b76427c174a90d3f43ff7a5cc6032795924d9bd90eeda8ad5571874b59a036b",
}
"""data/scope3 의 두 파일(받은 원본에서 지은 사본 — 짓는 법과 받은 sha 는 data/README.md 의 표)."""


@dataclass
class FakeFile:
    """PackagedFile 의 가짜. 읽은 수를 센다."""

    content: bytes | FileMissing
    reads: int = 0

    def read(self) -> bytes | FileMissing:
        self.reads += 1
        return self.content


@dataclass
class FakeContext:
    """RunContext 꼴의 가짜. llm() 은 미리 지은 표시 객체를 돌려준다."""

    marker: object = field(default_factory=object)
    company_id: int = 9
    run_id: int = 1
    module: str = "inventory.scope3"
    flow_id: str = "scope3.colab@157"
    attempt: int = 1
    asked: int = 0

    def llm(self) -> LlmClient:
        self.asked += 1
        return self.marker  # pyright: ignore[reportReturnType]

    def embedding(self) -> EmbeddingClient:
        raise AssertionError("Scope 3 코랩 흐름은 임베딩을 쓰지 않는다")


def binding(content: bytes | FileMissing = BOOK_BYTES) -> Scope3ColabBinding:
    return Scope3ColabBinding(factor_book=FakeFile(content), runs_enabled=lambda: True)


def document(content: bytes = TEMPLATE_BYTES) -> DocumentInput:
    # 실행기는 문서를 늘 PDF 꼴로 넘긴다(runs/tasks.py DOCUMENT_MEDIA_TYPE) — 끼움은 content 만 본다
    return DocumentInput(content=content, media_type="application/pdf", file_name="가상-scope3.xlsx")


@pytest.fixture
def at(monkeypatch: pytest.MonkeyPatch) -> Callable[[datetime], None]:
    def set_clock(now: datetime) -> None:
        monkeypatch.setattr(binding_157, "clock", lambda: now)

    return set_clock


# ── 옵션 받기 표 ──


@pytest.mark.parametrize("year", [1990, 2025, 2026])
def test_a_year_from_1990_to_this_year_is_accepted(at: Callable[[datetime], None], year: int) -> None:
    at(datetime(2026, 6, 1, tzinfo=UTC))
    assert accept_options({"reportYear": year}) == year
    binding().check_options({"reportYear": year})


@pytest.mark.parametrize(
    "options",
    [
        {},
        {"reportYear": None},
        {"reportYear": "2025"},
        {"reportYear": 2025.0},
        {"reportYear": True},
        {"reportYear": 1989},
        {"reportYear": 2027},
    ],
    ids=["missing", "null", "text", "float", "bool", "before-1990", "after-this-year"],
)
def test_a_bad_year_is_rejected_by_key_name_only(at: Callable[[datetime], None], options: dict[str, object]) -> None:
    at(datetime(2026, 6, 1, tzinfo=UTC))
    with pytest.raises(RunOptionsRejected) as caught:
        binding().check_options(options)
    assert caught.value.message == "옵션 reportYear의 값이 맞지 않아요"


def test_this_year_is_the_seoul_year(at: Callable[[datetime], None]) -> None:
    """UTC 12-31 15:30 은 서울 1-1 이다 — 새해가 고를 수 있는 해가 된다."""
    at(datetime(2026, 12, 31, 15, 30, tzinfo=UTC))
    assert accept_options({"reportYear": 2027}) == 2027
    at(datetime(2026, 12, 31, 14, 59, tzinfo=UTC))
    with pytest.raises(RunOptionsRejected):
        accept_options({"reportYear": 2027})


def test_unknown_keys_are_named_sorted_before_the_year() -> None:
    with pytest.raises(RunOptionsRejected) as caught:
        binding().check_options({"zeta": 1, "reportYear": "x", "alpha": 2})
    assert caught.value.message == "알 수 없는 옵션이에요: alpha, zeta"


def test_a_missing_factor_book_is_rejected_after_the_year() -> None:
    missing = binding(FileMissing("scope3-factor-book.xlsx"))
    with pytest.raises(RunOptionsRejected) as caught:
        missing.check_options({"reportYear": 2025})
    assert caught.value.message == "Scope 3 배출계수 책이 배포에 없어요. 운영자에게 알려 주세요"
    with pytest.raises(RunOptionsRejected, match="reportYear"):
        missing.check_options({})


def test_a_switched_off_binding_refuses_first_without_reading_the_book() -> None:
    """스위치가 꺼지면 옵션을 보기 전에 거절한다 — 기존 RunOptionsRejected(400 invalid_options), 책은 읽지 않는다."""
    port = FakeFile(BOOK_BYTES)
    off = Scope3ColabBinding(factor_book=port, runs_enabled=lambda: False)
    for options in ({"reportYear": 2025}, {}):
        with pytest.raises(RunOptionsRejected) as caught:
            off.check_options(options)
        assert caught.value.message == "Scope 3 실행은 아직 열려 있지 않아요. 운영자에게 알려 주세요"
    assert port.reads == 0


# ── 판·입력·어댑터 ──


def test_versions_carry_engine_flow_and_route() -> None:
    expected = {"engine": "colab_157", "flow": "scope3.colab@157", "route": "standard-openai-41"}
    assert binding().versions({"reportYear": 2025}) == expected
    assert binding().versions_with({"reportYear": 2025}, company_id=9) == expected


def test_inputs_with_take_the_document_bytes_the_year_and_the_company_tag() -> None:
    made = binding().inputs_with(document(), {"reportYear": 2025}, company_id=9, versions={})
    assert made == colab.ColabInputs(
        template=TEMPLATE_BYTES,
        report_year=2025,
        route="standard-openai-41",
        tags=Tags(tenant="9", module="inventory.scope3"),
    )
    assert binding().inputs_with(document(), {"reportYear": 2019}, company_id=9, versions={}).report_year == 2019


def test_inputs_without_a_company_are_refused() -> None:
    """회사 없는 꼴은 막혔다 — 빈 꼬리표로 도는 실행이 생기지 않게. 실행기는 inputs_with 만 부른다."""
    with pytest.raises(NotImplementedError, match="inputs_with"):
        binding().inputs(document(), {"reportYear": 2025})


def test_inputs_reject_bad_options_too() -> None:
    """만들 때 받은 옵션이라도 실행기가 부를 때 다시 받는다(행을 고쳐 넣은 경우)."""
    with pytest.raises(RunOptionsRejected):
        binding().inputs_with(document(), {"reportYear": True}, company_id=9, versions={})


def test_adapters_read_the_book_through_the_port_with_no_geocoder() -> None:
    port = FakeFile(BOOK_BYTES)
    ctx = FakeContext()
    made = Scope3ColabBinding(factor_book=port, runs_enabled=lambda: True).adapters(ctx)
    assert made.llm is ctx.marker
    assert ctx.asked == 1
    assert made.factor_book == read_workbook(BOOK_BYTES)
    assert type(made.geocoder) is NoGeocoder
    assert port.reads == 1


@pytest.mark.parametrize(
    ("content", "says"),
    [(FileMissing("scope3-factor-book.xlsx"), "이 없다"), (b"not a zip", "읽지 못했다")],
    ids=["missing", "unreadable"],
)
def test_adapters_fail_the_run_when_the_book_is_gone_or_unreadable(content: bytes | FileMissing, says: str) -> None:
    with pytest.raises(FactorBookUnreadable, match=says):
        binding(content).adapters(FakeContext())


def test_the_book_keeps_the_default_ten_mib_limit() -> None:
    """계수 책은 올린 파일이 아니다: 읽개 기본 상한(10MiB) 그대로 — 올리기 상한 20MB(MARC-ENT-593)를 넘기지 않는다."""
    with pytest.raises(FactorBookUnreadable, match="too_many_bytes"):
        binding(padded(BOOK_BYTES, 10 * MiB + 1)).adapters(FakeContext())
    assert binding(padded(BOOK_BYTES, 10 * MiB)).adapters(FakeContext()).factor_book is not None


def test_the_book_exception_has_no_error_code_of_its_own() -> None:
    """★J: 표(runs/calc/errors.py)에 없는 예외 — 실행 error_code 는 internal."""
    from esgapi.runs.calc.errors import STEP_ERROR_CODES

    name = f"{FactorBookUnreadable.__module__}.{FactorBookUnreadable.__qualname__}"
    assert name not in STEP_ERROR_CODES


@pytest.mark.parametrize("name", ["check_options", "inputs", "adapters", "versions"])
def test_the_binding_has_the_document_port_shape(name: str) -> None:
    ours = inspect.signature(getattr(Scope3ColabBinding, name)).parameters
    port = inspect.signature(getattr(RunBinding, name)).parameters
    assert list(ours) == list(port)


def test_the_binding_is_a_facts_binding() -> None:
    """실행기가 회사 꼬리표를 넘기는 둘째 꼴(inputs_with)로 부른다(runs/tasks.py)."""
    assert isinstance(binding(), RunFactsBinding)


# ── 저장소의 xlsx 둘 ──


@pytest.mark.parametrize("port", [scope3_files.TEMPLATE, scope3_files.FACTOR_BOOK], ids=lambda p: p.name)
def test_the_packaged_files_are_the_recorded_bytes_and_read(port: scope3_files.PackagedXlsx) -> None:
    content = port.read()
    assert isinstance(content, bytes)
    assert hashlib.sha256(content).hexdigest() == SHA256[port.name]
    assert not isinstance(read_workbook(content), ReaderProblem)


def test_each_port_reads_its_own_file() -> None:
    assert (scope3_files.TEMPLATE.name, scope3_files.FACTOR_BOOK.name) == (
        "scope3-template-v2.2.xlsx",
        "scope3-factor-book.xlsx",
    )


def test_a_file_not_in_the_package_is_missing_not_an_exception() -> None:
    assert scope3_files.PackagedXlsx("없는-파일.xlsx").read() == FileMissing("없는-파일.xlsx")


# ── 등록·기본 흐름 ──


def test_ready_registered_the_binding_with_the_packaged_book_and_no_rows_carrier() -> None:
    found = BINDINGS.get("scope3.colab@157")
    assert isinstance(found, Scope3ColabBinding)
    assert found.factor_book is scope3_files.FACTOR_BOOK
    assert BINDINGS.options_limit("scope3.colab@157") == 16 * 1024
    assert BINDINGS.flow_ids().count("scope3.colab@157") == 1
    assert "scope3.llm-first@1" not in BINDINGS.flow_ids()
    assert CARRIERS.get("inventory.scope3") is NO_ROWS


def test_the_default_scope3_flow_is_the_colab_flow() -> None:
    assert REGISTRY.default_of("inventory.scope3") is colab.FLOW
    assert REGISTRY.defaults()["inventory.scope3"] == "scope3.colab@157"
