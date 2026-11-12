"""사업장 경로의 요청과 응답의 꼴(JSON). 여기 적힌 것이 OpenAPI 문서와 프론트의 타입(generated/api.d.ts)이 된다.

필드 이름은 camelCase 다. SiteOut.id 는 글자 그대로다(값이 UUID 글자에서 숫자 id 의 십진 글자로 — K1u-a).
"""

from ninja import Schema
from pydantic import Field

from esgapi.core.schemas import Strict


class SiteOut(Schema):
    id: str
    name: str
    externalId: str | None


class SitesOut(Schema):
    sites: list[SiteOut]


class SiteIn(Strict):
    name: str = Field(min_length=1, max_length=200)
    externalId: str | None = Field(default=None, min_length=1, max_length=200)


class SiteCreatedOut(Schema):
    site: SiteOut
