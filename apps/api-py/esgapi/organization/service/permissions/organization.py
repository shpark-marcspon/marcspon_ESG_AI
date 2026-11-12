"""사업장(sites) 동작의 권한 규칙. 순수하다(표준 라이브러리와 core 의 권한 표·주체만).

그 앱의 동작은 그 앱이 지킨다(감독 처분 ㉠, K1u-a): 사업장의 selectors·services 가 여기를 부른다.
값은 core/permissions.py 의 표 하나에 있다 — 여기는 그 표를 읽는 얇은 함수뿐이다(사본 표 0).
1차 역할은 운영 관리자·고객사 사용자 둘이고(사용자 결정 2026-10-15 14:46) 사업장 동작은 고객사 사용자의 일이다.
사용자 관리 경로의 권한은 user 에 따로 둔다(K2c).
"""

from dataclasses import dataclass

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import forbidden_message, is_allowed


def can_view_sites(kind: Kind) -> bool:
    """사업장 목록을 볼 수 있는가. 값은 core/permissions.py 의 표에 있다."""
    return is_allowed("accounts_sites_list", kind=kind)


def can_create_site(kind: Kind) -> bool:
    """사업장을 만들 수 있는가. 값은 core/permissions.py 의 표에 있다."""
    return is_allowed("accounts_sites_create", kind=kind)


@dataclass(frozen=True)
class Forbidden:
    """그 동작을 할 수 없는 주체다. services·selectors 가 「했다」 대신 돌려주는 갈래다."""

    operation_id: str

    @property
    def message(self) -> str:
        """403 의 문장(누가 하는 일인가 — core/permissions.py 의 forbidden_message)."""
        return forbidden_message(self.operation_id)
