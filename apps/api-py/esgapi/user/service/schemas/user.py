"""교환·세션 경로의 요청과 응답의 꼴(JSON). 여기 적힌 것이 OpenAPI 문서(/api/openapi.json)와 프론트의 타입
(generated/api.d.ts)이 된다. 필드 이름은 camelCase 다(TS 뼈대의 응답과 같게).

id 칸은 글자 그대로다(값이 UUID 글자에서 숫자 id 의 십진 글자로 바뀌었다 — 프론트의 타입은 그대로, K1u-a).
"""

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import KstDateTime, Strict
from esgapi.core.tenancy.session import Role


class ExchangeIn(Strict):
    token: str = Field(min_length=1, max_length=8192, description="EDK 가 서명한 토큰(JWT)")


class UserOut(Schema):
    id: str
    name: str
    issuer: str
    externalId: str


class TenantOut(Schema):
    id: str
    name: str


class ExchangeOut(Schema):
    user: UserOut
    tenant: TenantOut
    role: Role
    expiresAt: KstDateTime


class MeOut(Schema):
    userId: str
    tenantId: str
    role: Role
    expiresAt: KstDateTime
    companyId: int
