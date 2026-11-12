"""올림 확인의 감사 줄 행위자 kind(밴드 OP1 §2-3 — 결정 MARC-ENT-374). 업무 층.

회사 업무라 경로가 주체의 kind 를 넘긴다: 작업 회사로 일하는 운영 관리자의 올림 확인은 actor_kind admin·회사 id = 작업
회사. 넘기지 않은 옛 부름은 service, 사용자 id 도 없으면 command(그대로).
"""

import pytest

from esgapi.core.models import AuditEventRow
from esgapi.core.service.services import documents as services
from esgapi.core.tests.resource_fakes import FakeStorage
from esgapi.core.tests.service.services.test_documents import NOW, created, no_queue

pytestmark = pytest.mark.django_db
CONTENT = b"not a pdf (synthetic)"


def upload_line(company_id: int, **actor: object) -> tuple[object, ...]:
    storage = FakeStorage()
    document_id = created(storage, company_id, CONTENT)
    result = services.confirm_upload(
        company_id=company_id,
        document_id=document_id,
        storage=storage,
        now=NOW,
        enqueue=no_queue,
        **actor,  # pyright: ignore[reportArgumentType]
    )
    assert isinstance(result, services.UploadConfirmed), result
    (line,) = AuditEventRow.for_company(company_id).filter(action="upload", target_id=document_id)
    return line.actor_kind, line.actor_user_id, line.company_id


@pytest.mark.parametrize(
    ("actor", "expected_kind", "expected_user"),
    [
        ({"actor_user_id": 9001, "actor_kind": "admin"}, "admin", 9001),
        ({"actor_user_id": 7, "actor_kind": "service"}, "service", 7),
        ({"actor_user_id": 7}, "service", 7),  # 옛 부름(actor_kind 없음)
        ({}, "command", None),
    ],
    ids=["admin", "service", "old-call", "command"],
)
def test_the_upload_line_names_the_actor_kind(
    companies: tuple[int, int], actor: dict[str, object], expected_kind: str, expected_user: int | None
) -> None:
    a, _ = companies
    assert upload_line(a, **actor) == (expected_kind, expected_user, a)
