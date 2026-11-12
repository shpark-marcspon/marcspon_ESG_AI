"""쓰기. 유스케이스 하나: 사업장 만들기. HTTP 를 모른다(요청·응답·상태 코드가 없다).

결과는 예외가 아니라 갈래로 돌려준다(permissions/organization.py 의 Forbidden). service/apis/organization.py 가 갈래를
응답으로 바꾼다. 유스케이스(create_site)는 바깥(DB)을 **함수 인자**로 받는다. 기본값이 이 파일의 진짜 구현이다.
"""

from collections.abc import Callable
from dataclasses import dataclass

from esgapi.core.auth.principal import Principal
from esgapi.organization.service.permissions.organization import Forbidden, can_create_site
from esgapi.organization.service.services import branches
from esgapi.organization.service.services.branches import NameTaken
from esgapi.organization.service.utils.entities import Site as SiteInfo


def insert_site(company_id: int, name: str, external_id: str | None) -> SiteInfo | NameTaken:
    # /branches 와 같은 안쪽 함수(branches.insert_site_row — 감독 판단 1·N3)를 부른다. 행의 회사는 인자의 것이다.
    # 같은 회사의 삭제 안 된 사업장에 같은 이름이 있으면 NameTaken(K1b-1 의 sites_name_unique_alive).
    made = branches.insert_site_row(company_id, name=name, external_id=external_id)
    if isinstance(made, NameTaken):
        return made
    return SiteInfo(id=str(made.id), company_id=made.company_id, external_id=made.external_id, name=made.name)


@dataclass(frozen=True)
class SiteCreated:
    site: SiteInfo


def create_site(
    principal: Principal,
    *,
    name: str,
    external_id: str | None,
    insert_site: Callable[[int, str, str | None], SiteInfo | NameTaken] = insert_site,
) -> SiteCreated | Forbidden | NameTaken:
    """사업장 만들기. 권한은 여기서 본다."""
    # 경로의 첫 문장 permitted(core/auth/bearer.py)를 이 동작에서는 여기서 대신한다: 같은 표(is_allowed)를 읽는다.
    # company_id is None 은 permitted 에 없는 겹 확인이다 — 회사 없는 주체를 막는 깊은 방어라 남긴다
    # (밴드 CU1, 감독 처분 ②).
    if not can_create_site(principal.kind) or principal.company_id is None:  # 회사 없는 주체는 고객사 사용자가 아니다
        return Forbidden("accounts_sites_create")
    # 회사는 주체(세션·토큰)에서만 온다. 요청 본문에는 그 칸이 없다.
    made = insert_site(principal.company_id, name, external_id)
    return made if isinstance(made, NameTaken) else SiteCreated(made)
