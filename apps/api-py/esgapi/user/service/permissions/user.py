"""고객사 사용자 관리(K2c·UA1 — 목록·만들기·비밀번호 초기화·수정)의 권한 규칙.
순수하다(표준 라이브러리와 core 의 권한 표·주체만).

그 앱의 동작은 그 앱이 지킨다(사업장 권한 모듈 organization/service/permissions 와 같은 꼴): 사용자 관리의
selectors·services·actions 가 첫 줄에서 여기를 부른다. 값은 core/permissions.py 의 표 하나에 있다 — 여기는 그 표를
읽는 얇은 함수뿐이다(사본 표 0). 1차는 운영 관리자만 한다(사용자 결정 2026-10-15 14:46). 고객사 관리자의 사용자 관리는
2차다 — 그때 표의 칸과 is_resettable 의 대상 규칙을 바꾼다.
"""

from dataclasses import dataclass
from typing import Final

from esgapi.core.auth.principal import Kind
from esgapi.core.permissions import forbidden_message, is_allowed

# 고객사 사용자 관리의 동작 넷. 넷이 같은 칸이다(core/tests/test_permissions.py 가 단언한다).
USER_ADMIN_OPERATIONS: Final = ("user_list", "user_create", "user_password_reset", "user_update")


def can_manage_customer_users(kind: Kind) -> bool:
    """고객사 사용자를 보고·만들고·초기화하고·고칠 수 있는가. 넷의 칸을 다 읽는다(하나라도 막히면 막힌다)."""
    return all(is_allowed(operation_id, kind=kind) for operation_id in USER_ADMIN_OPERATIONS)


def is_resettable(target_kind: str) -> bool:
    """HTTP 초기화의 대상인가: 고객사 사용자(service)만. 운영 관리자의 초기화는 부트스트랩 명령으로만 한다."""
    return target_kind == "service"


@dataclass(frozen=True)
class Forbidden:
    """그 동작을 할 수 없는 주체다. selectors·services·actions 가 「했다」 대신 돌려주는 갈래다."""

    operation_id: str

    @property
    def message(self) -> str:
        """403 의 문장(누가 하는 일인가 — core/permissions.py 의 forbidden_message)."""
        return forbidden_message(self.operation_id)
