"""문서·일감의 순수 규칙(core/calc/documents.py): 전이표 둘, 저장소 키, 파일 이름, 올릴 수 있는 역할. 순수 층.

상태 튜플과 DB 의 CHECK(모델의 제약)가 같은지는 test_documents_models.py 가 견준다.
"""

import uuid
from itertools import product
from typing import cast

import pytest

from esgapi.core.calc import documents as calc
from esgapi.core.calc.documents import BadTenantId, StorageKey

KEY_ID = "0b0e7c1e-0000-4000-8000-000000000001"  # 키의 UUID(문서 id 가 아니다)
COMPANY = 7  # 순수 층의 회사 id(DB 가 없다)

# ── 전이표 ────────────────────────────────────────────────────────────


def test_document_transitions_are_exactly_the_one_written_here() -> None:
    assert calc.DOCUMENT_STATUSES == ("awaiting_upload", "uploaded")
    allowed = {(a, b) for a, b in product(calc.DOCUMENT_STATUSES, repeat=2) if calc.can_transition_document(a, b)}
    assert allowed == {("awaiting_upload", "uploaded")}
    assert set(calc.DOCUMENT_TRANSITIONS) == set(calc.DOCUMENT_STATUSES)


def test_job_transitions_are_exactly_the_four_written_here() -> None:
    assert calc.JOB_STATUSES == ("queued", "processing", "done", "failed")
    allowed = {(a, b) for a, b in product(calc.JOB_STATUSES, repeat=2) if calc.can_transition_job(a, b)}
    assert allowed == {
        ("queued", "processing"),
        ("processing", "processing"),  # 재시도·이어받기
        ("processing", "done"),
        ("processing", "failed"),
    }
    assert set(calc.JOB_TRANSITIONS) == set(calc.JOB_STATUSES)


def test_nothing_leaves_a_finished_state() -> None:
    assert [s for s in calc.DOCUMENT_STATUSES if calc.is_document_finished(s)] == ["uploaded"]
    assert [s for s in calc.JOB_STATUSES if calc.is_job_finished(s)] == ["done", "failed"]
    for done in ("uploaded",):
        assert [to for to in calc.DOCUMENT_STATUSES if calc.can_transition_document(done, to)] == []
    for finished in ("done", "failed"):
        assert [to for to in calc.JOB_STATUSES if calc.can_transition_job(finished, to)] == []


def test_job_kinds_is_parse_alone_for_now() -> None:
    assert calc.JOB_KINDS == ("parse",)


def test_status_guards() -> None:
    assert calc.is_document_status("uploaded") and not calc.is_document_status("queued")
    assert calc.is_job_status("queued") and not calc.is_job_status("uploaded")
    assert not calc.is_job_status(None)


# ── 저장소 키 ─────────────────────────────────────────────────────────


# 사본에서 뜻이 없다: mutmut 의 트램펄린이 함수를 감싸 __code__.co_varnames 가 () 로 보인다(scripts/weekly.sh ②)
@pytest.mark.not_under_mutmut
def test_the_key_is_tenant_then_document_and_takes_no_file_name() -> None:
    """키는 회사 id(숫자) 다음 키의 UUID 다. 서브도메인 글자가 아니다(나3)."""
    assert calc.storage_key(COMPANY, KEY_ID) == StorageKey(f"companies/{COMPANY}/documents/{KEY_ID}/original")
    # 파일 이름을 받는 인자가 없다: 사용자가 적은 글자가 키에 들어갈 길이 없다.
    assert calc.storage_key.__code__.co_varnames[: calc.storage_key.__code__.co_argcount] == (
        "company_id",
        "key_id",
    )
    made = calc.storage_key(1, str(uuid.uuid4()))
    assert isinstance(made, StorageKey)
    assert made.key.count("/") == 4
    assert made.key.startswith("companies/1/documents/")
    assert "tenant" not in made.key


@pytest.mark.parametrize(
    "company_id",
    [
        0,
        -1,
        -7,
        True,  # bool 은 int 의 하위 타입이다
        False,
        "7",  # 숫자 글자도 아니다(정수만)
        "tenant-a",  # 서브도메인 글자
        7.0,
        None,
    ],
    ids=repr,
)
def test_a_tenant_id_that_cannot_be_a_key_segment_is_a_branch_not_a_key(company_id: object) -> None:
    assert calc.storage_key(cast("int", company_id), KEY_ID) == BadTenantId()  # 타입 검사기를 지나도 갈래다


def test_tenant_id_length_boundary() -> None:
    assert isinstance(calc.storage_key(1, KEY_ID), StorageKey)
    assert isinstance(calc.storage_key(2**63 - 1, KEY_ID), StorageKey)  # BigInt 의 끝(19자리)
    assert calc.storage_key(2**63 - 1, KEY_ID) == StorageKey(f"companies/{2**63 - 1}/documents/{KEY_ID}/original")


@pytest.mark.parametrize("document_id", ["", "not-a-uuid", KEY_ID.upper(), KEY_ID.replace("-", ""), f"{KEY_ID}/x"])
def test_a_document_id_that_is_not_our_uuid_is_a_programming_error(document_id: str) -> None:
    with pytest.raises(ValueError, match="UUID"):
        calc.storage_key(COMPANY, document_id)


# ── 파일 이름 ─────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("name", "valid"),
    [
        ("", False),
        ("a", True),
        ("보고서 2025 (최종).pdf", True),
        ("../../etc/passwd", True),  # 표시용 글자일 뿐이다(키에 안 들어간다)
        ("a" * 255, True),
        ("a" * 256, False),
        ("a\x00b", False),  # NUL: PostgreSQL 의 글자 칸에 못 들어간다
        ("a\nb", False),
        ("a\tb", False),
        ("a\x7fb", False),
        ("a\x1fb", False),
        ("a\x20b", True),  # 빈칸은 제어 글자가 아니다
    ],
)
def test_file_name_rule(name: str, valid: bool) -> None:
    assert calc.is_valid_file_name(name) is valid
