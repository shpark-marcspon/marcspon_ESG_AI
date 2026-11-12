# pyright: reportUnknownMemberType=false, reportUnknownVariableType=false, reportUnknownArgumentType=false
"""운영 관리자가 작업 회사로 한 그린워싱 업무의 이름(결정 MARC-ENT-374, 밴드 OP1 §2-3 — 37 허락). 업무 층.

목록 줄(checks)·검토 상태(review)의 사람 이름은 user 의 people_of 로 푼다: 그 회사의 고객사 사용자 먼저, 못 푼 id 는
운영 관리자. 문서를 올리고 검토를 확정한 사람이 운영 관리자면 그 이름이 나온다. 남의 회사 고객사 사용자의 id 는 풀지
않는다(「알 수 없는 사용자」). 점검 목록의 companyName 은 회사 id 로 읽는다(세션 사용자를 거치지 않는다 — Q7).
★ 실행·결과 행은 seed(apps.get_model)로 심는다 — runs.models 를 import 하지 않는다(계약 나). 문서·이름은 지어낸 것이다.
"""

from typing import Any

import pytest

from esgapi.core.conf import now
from esgapi.greenwash.service.actions import checks as check_actions
from esgapi.greenwash.service.actions import review as review_actions
from esgapi.greenwash.tests.service import seed
from esgapi.user.service.services.user import create_customer_user, create_operator
from esgapi.user.service.utils.login import UserCreated

pytestmark = pytest.mark.django_db

NORMAL = seed.example("result-normal")
UNKNOWN = "알 수 없는 사용자"
PASSWORD = "Blue-Harbor-7310"


def operator() -> int:
    created = create_operator(username="ops", name="운영자 한빛", password=PASSWORD)
    assert isinstance(created, UserCreated), created
    return created.user_id


def customer(company_id: int, username: str, name: str) -> int:
    created = create_customer_user(
        actor_kind="admin", company_id=company_id, username=username, name=name, password=PASSWORD
    )
    assert isinstance(created, UserCreated), created
    return created.user_id


def confirmed_by_operator(company_id: int, admin: int, *, uploaded_by: int) -> int:
    run_id = seed.run(company_id, result=NORMAL, document_id=seed.document(company_id, uploaded_by=str(uploaded_by)))
    state = review_actions.put_review(
        company_id=company_id, actor_kind="admin", actor_user_id=admin, run_id=run_id, confirm=True, marks=[], now=now()
    )
    assert isinstance(state, dict), state
    return run_id


def test_the_operator_who_uploaded_and_confirmed_is_named(companies: tuple[int, int]) -> None:
    a, _ = companies
    admin = operator()
    run_id = confirmed_by_operator(a, admin, uploaded_by=admin)
    state: Any = review_actions.review_state(company_id=a, run_id=run_id)
    assert state["confirmedBy"] == {"id": admin, "name": "운영자 한빛"}
    body: Any = check_actions.checks(company_id=a, user_id=admin)
    (document,) = body["documents"]
    assert document["uploadedBy"] == {"userId": admin, "name": "운영자 한빛"}
    (line,) = body["runs"]
    assert line["review"]["confirmedBy"] == {"id": admin, "name": "운영자 한빛"}
    assert body["companyName"] == "가 회사"  # 운영 관리자에게는 회사 행이 없다 — 회사 id 로 읽는다
    assert body["currentUserId"] == admin


def test_a_customer_of_another_company_is_not_named(companies: tuple[int, int]) -> None:
    """올린 사람 칸에 남의 회사(B) 고객사 사용자의 id 가 있어도 풀지 않는다. 분모: 같은 회사(A) 고객사 사용자는 푼다."""
    a, b = companies
    admin = operator()
    stranger = customer(b, "b-kim", "남의 김")
    mine = customer(a, "a-lee", "우리 이")
    confirmed_by_operator(a, admin, uploaded_by=stranger)
    confirmed_by_operator(a, admin, uploaded_by=mine)
    body: Any = check_actions.checks(company_id=a, user_id=mine)
    names = sorted(d["uploadedBy"]["name"] for d in body["documents"])
    assert names == sorted([UNKNOWN, "우리 이"])
    assert {line["review"]["confirmedBy"]["name"] for line in body["runs"]} == {"운영자 한빛"}
