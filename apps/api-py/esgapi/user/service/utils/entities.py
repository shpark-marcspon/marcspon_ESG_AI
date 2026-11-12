"""교환의 낱말: 테넌트(= 회사), 사용자. 순수하다(표준 라이브러리만).

DB 의 표(user.models.User, organization 의 Company)와 갈라 둔 까닭: 교환의 갈래(utils/exchange.py)와 유스케이스
(services/user.py 의 exchange)가 Django 없이 테스트된다. services 와 apis 의 작은 함수가 행을 이것으로 바꿔 내보낸다.
"""

from dataclasses import dataclass

from esgapi.core.tenancy.session import Role


@dataclass(frozen=True)
class Tenant:
    """고객사 하나 = 회사. id 는 회사의 subdomain(EDK 토큰의 tenant_id 주장과 같은 글자), company_id 는 회사의 숫자 id.
    마크스폰 관리자가 미리 등록한 쓸 수 있는 회사만 있다(교환이 만들지 않는다)."""

    id: str
    name: str
    company_id: int


@dataclass(frozen=True)
class User:
    """교환으로 받은 사용자. 표의 행(users)은 (회사, username = 토큰의 sub) 로 정해진다.

    issuer·external_id·role 은 주장에서 온다(표에는 username 과 level 로 들어간다. role 은 세션에만 실린다).
    """

    id: str
    company_id: int
    tenant_id: str
    issuer: str
    external_id: str
    name: str
    role: Role
