# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""결과 글 칸 고침의 쓰기(services/edits.py)·읽기(selectors/edits.py)와 표의 제약(밴드 IRS3 ① §2-4·§4). 업무 층: 진짜
DB(주인 역할 — 앱 역할의 GRANT 는 보안 층 tests/security/test_owner.py 가 잰다).

    머리   처음 만들기 revision 0 · 다시 만들기(겹친 저장) = 행 하나 · 다른 제약 위반은 다시 던짐
    올림   base 가 맞으면 1 행 · 낡은 base 0 행(revision 그대로) · 남의 회사 0 행
    고침   지금 값 = 주소마다 가장 큰 revision · 회사 범위 · 머리 없는 고침은 복합 FK 로 거절 · CHECK(주소 꼴·revision·
           값 바이트) · unique (회사, 실행, revision, 주소)
run_id 는 외래 키가 아니다 — 실행 행 없이 숫자로 심는다. 값은 지어낸 것이다.
"""

from datetime import UTC, datetime

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from esgapi.materiality.models import MaterialityResultEditHeadRow, MaterialityResultEditRow
from esgapi.materiality.service.selectors import edits as selectors
from esgapi.materiality.service.services import edits as services

pytestmark = pytest.mark.django_db

NOW = datetime(2026, 11, 3, 1, 0, tzinfo=UTC)
RUN = 7001
USER = 41
P = "/part2/topics/0/subtopics/0/impact/rows/0/impactDefinition"
Q = "/part2/topics/0/subtopics/0/impact/rows/0/context/regulations/0/title"


def heads(company_id: int) -> list[tuple[int, int]]:
    return list(MaterialityResultEditHeadRow.for_company(company_id).order_by("id").values_list("run_id", "revision"))


def test_create_head_starts_at_revision_0_and_a_second_create_is_absorbed(companies: tuple[int, int]) -> None:
    a, b = companies
    assert selectors.head_revision(company_id=a, run_id=RUN) is None
    services.create_head(company_id=a, run_id=RUN)
    services.create_head(company_id=a, run_id=RUN)  # 겹친 저장이 먼저 만든 것 — unique 위반만 삼킨다
    assert heads(a) == [(RUN, 0)]
    assert selectors.head_revision(company_id=a, run_id=RUN) == 0
    assert selectors.head_revision(company_id=b, run_id=RUN) is None  # 회사 범위
    services.create_head(company_id=b, run_id=RUN)  # 같은 run_id 라도 회사마다
    assert heads(b) == [(RUN, 0)]


def test_create_head_rethrows_other_integrity_errors(
    companies: tuple[int, int], monkeypatch: pytest.MonkeyPatch
) -> None:
    a, _ = companies
    monkeypatch.setattr(services, "HEAD_UNIQUE", "다른_제약_이름")
    services.create_head(company_id=a, run_id=RUN)
    with pytest.raises(IntegrityError):
        services.create_head(company_id=a, run_id=RUN)


def test_bump_head_moves_only_from_the_base(companies: tuple[int, int]) -> None:
    a, b = companies
    services.create_head(company_id=a, run_id=RUN)
    assert services.bump_head(company_id=a, run_id=RUN, base_revision=0, now=NOW) == 1
    assert services.bump_head(company_id=a, run_id=RUN, base_revision=0, now=NOW) == 0  # 낡은 base
    assert services.bump_head(company_id=b, run_id=RUN, base_revision=1, now=NOW) == 0  # 남의 회사
    assert selectors.head_revision(company_id=a, run_id=RUN) == 1
    assert services.bump_head(company_id=a, run_id=RUN, base_revision=1, now=NOW) == 1
    assert heads(a) == [(RUN, 2)]
    head = MaterialityResultEditHeadRow.for_company(a).get(run_id=RUN)
    assert head.updated_at == NOW


def test_the_current_value_is_the_largest_revision(companies: tuple[int, int]) -> None:
    """P6: 두 번 고친 칸 = 둘째 값. 주소마다 한 행, 주소 차례."""
    a, b = companies
    services.create_head(company_id=a, run_id=RUN)
    services.insert_edits(company_id=a, run_id=RUN, revision=1, user_id=USER, changes=[(Q, "가상 첫 제목"), (P, "첫")])
    services.insert_edits(company_id=a, run_id=RUN, revision=2, user_id=USER + 1, changes=[(P, "가상 둘째 정의")])
    services.insert_edits(company_id=a, run_id=RUN, revision=3, user_id=USER + 2, changes=[(Q, None)])
    found = selectors.current_edits(company_id=a, run_id=RUN)
    assert [(e.pointer, e.value, e.revision, e.edited_by_user_id) for e in found] == [
        (Q, None, 3, USER + 2),  # 주소 차례(…/context… < …/impactDefinition)
        (P, "가상 둘째 정의", 2, USER + 1),
    ]
    assert selectors.current_edits(company_id=a, run_id=RUN + 1) == []
    assert selectors.current_edits(company_id=b, run_id=RUN) == []  # 회사 범위
    assert MaterialityResultEditRow.for_company(a).count() == 4  # 불변 행 — 저장 = 새 행


def test_an_edit_without_a_head_breaks_the_same_company_key(companies: tuple[int, int]) -> None:
    a, b = companies
    services.create_head(company_id=b, run_id=RUN)  # 남의 회사의 머리로는 서지 못한다
    with pytest.raises(IntegrityError, match="materiality_result_edits_run_id_same_company_fk"), transaction.atomic():
        services.insert_edits(company_id=a, run_id=RUN, revision=1, user_id=USER, changes=[(P, "가상")])


@pytest.mark.parametrize(
    ("revision", "pointer", "value", "constraint"),
    [
        (1, "/part2/topics/0/subtopics/0/impact/rows/0/impactType", "가상", "materiality_result_edits_pointer_check"),
        (1, "/part1/0/regulation", "가상", "materiality_result_edits_pointer_check"),
        (0, P, "가상", "materiality_result_edits_revision_check"),
        (1, P, "가" * 5462, "materiality_result_edits_value_size_check"),  # 16,386 바이트
    ],
)
def test_the_edit_checks_are_the_last_net(
    companies: tuple[int, int], revision: int, pointer: str, value: str, constraint: str
) -> None:
    a, _ = companies
    services.create_head(company_id=a, run_id=RUN)
    with pytest.raises(IntegrityError, match=constraint), transaction.atomic():
        services.insert_edits(company_id=a, run_id=RUN, revision=revision, user_id=USER, changes=[(pointer, value)])
    services.insert_edits(company_id=a, run_id=RUN, revision=1, user_id=USER, changes=[(P, "가" * 5461)])  # 16,383


def test_one_pointer_once_per_revision(companies: tuple[int, int]) -> None:
    a, _ = companies
    services.create_head(company_id=a, run_id=RUN)
    with pytest.raises(IntegrityError, match="materiality_result_edits_company_run_rev_uniq"), transaction.atomic():
        services.insert_edits(company_id=a, run_id=RUN, revision=1, user_id=USER, changes=[(P, "가"), (P, "나")])


def test_the_head_revision_check(companies: tuple[int, int]) -> None:
    a, _ = companies
    services.create_head(company_id=a, run_id=RUN)
    with pytest.raises(IntegrityError, match="materiality_result_edit_heads_revision_check"), transaction.atomic():
        MaterialityResultEditHeadRow.for_company(a).filter(run_id=RUN).update(revision=-1)


def _tables() -> set[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT tablename FROM pg_tables WHERE schemaname = 'public' AND tablename LIKE 'materiality%%'")
        return {str(row[0]) for row in cursor.fetchall()}


def _migrate(*targets: tuple[str, str]) -> None:
    executor = MigrationExecutor(connection)
    executor.migrate(list(targets) or executor.loader.graph.leaf_nodes())


@pytest.mark.django_db(transaction=True)
def test_the_0002_migration_goes_up_down_and_up_again() -> None:
    """내림(0002 → 0001)은 고침 표 둘만 지운다(판 표는 남음) · 다시 올리면 제약·복합 FK 가 다시 선다."""
    new = {"materiality_result_edit_heads", "materiality_result_edits"}
    assert _tables() >= new
    try:
        _migrate(("materiality", "0001_ai_settings"))
        assert _tables() == {"materiality_ai_settings"}
    finally:
        _migrate()
    assert _tables() == {"materiality_ai_settings", *new}
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT conname FROM pg_constraint WHERE conrelid IN "
            "('materiality_result_edit_heads'::regclass, 'materiality_result_edits'::regclass) "
            "AND contype IN ('c', 'u', 'f') AND conname NOT LIKE '%%company_id%%' "
            "UNION SELECT indexname FROM pg_indexes WHERE tablename IN ('materiality_result_edit_heads', "
            "'materiality_result_edits') AND indexname LIKE '%%_uniq'"
        )
        names = sorted(str(row[0]) for row in cursor.fetchall())
    assert names == sorted(
        [
            "materiality_result_edit_heads_company_run_uniq",
            "materiality_result_edit_heads_revision_check",
            "materiality_result_edits_company_run_rev_uniq",
            "materiality_result_edits_revision_check",
            "materiality_result_edits_pointer_check",
            "materiality_result_edits_value_size_check",
            "materiality_result_edits_run_id_same_company_fk",
        ]
    )
