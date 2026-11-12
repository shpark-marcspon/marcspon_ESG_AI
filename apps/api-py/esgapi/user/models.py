"""사용자 표(users). EDK 리뉴얼 꼴(원문의 User)에서 1차에 쓰는 칸과 제약이다(K1u-a). 표와 제약뿐 — 로그인(비밀번호 검사·
JWT·잠금)과 level 의 권한은 K2 가 단다. 사업장(branch)·역할(role) 칸은 넣지 않는다(K1b·2차).

  kind     admin(운영팀 — 회사 없음) · service(고객사 사용자 — 회사 있음). 짝은 CHECK 가 지킨다
  username 로그인 아이디. 운영팀은 전역 unique, 고객사는 회사 안 unique(조건부 UNIQUE 둘 — 결정 02:56).
           그래서 USERNAME_FIELD 가 unique 가 아니고 auth.W004 를 끈다(config/apps_list.py, 결정 6)
  level    99 관리자 · 89 · 79 일반(CHECK). 1차는 99·79 둘만 쓴다(사용자 결정 「역할은 관리자·일반 둘」)

격리: 회사 칸 표다(CompanyScopedModel). 기본 매니저가 회사를 정하지 않은 조회를 거절한다 —
AbstractUser 의 UserManager 를 덮는다(createsuperuser 는 안 된다. 운영팀 계정의 입구는 K2).
여는 길: User.for_company(<회사 id>).
표 이름이 users 인 까닭: user 는 PostgreSQL 의 예약어다. AbstractUser 의 M2M 표 둘
(users_groups·users_user_permissions)은 앱이 읽지 않아 앱 역할의 권한이 없다(migrations/0001_initial.py).
"""

from datetime import datetime
from typing import Final
from uuid import UUID

from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models

from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel

KINDS: Final = ("admin", "service")
LEVELS: Final = (99, 89, 79)


class CompanyScopedUserManager(CompanyScopedManager["User"], UserManager["User"]):
    """users 의 기본 매니저. 조회는 회사 범위 바닥의 것(get_queryset 이 거절, for_company 로만)이고, UserManager 를
    같이 잇는 것은 AbstractUser 의 objects 타입(UserManager)과 맞추려는 것뿐이다. create_user·create_superuser 는
    쓰지 않는다(kind·level 을 모르므로 CHECK 가 막는다 — 운영팀 계정의 입구는 K2).
    마이그레이션에 싣지 않는다(UserManager 의 기본은 싣는다 — 마이그레이션이 이 파일에 기대지 않게).
    """

    use_in_migrations = False

    # ── 운영 관리자(kind admin, 회사 없음)의 이름 붙은 입구(K2a). 회사 바닥 밖으로 여는 유일한 길이다 ──
    # 몸에 kind="admin"·company IS NULL 조건이 있다(고객사 사용자의 행을 볼 수 없다). 부르는 자리는
    # core/tests/isolation/test_static_rules.py 의 USER_ENTRANCES 가 허용 목록으로 지킨다. QuerySet 을 돌려주는 까닭:
    # 행 잠금(select_for_update)은 Selector 에만 둔다(core/tests/test_selector_scope.py) — 입구는 거른 것만 낸다.

    def _admins(self) -> models.QuerySet["User"]:
        return models.QuerySet["User"](model=self.model, using=self._db).filter(kind="admin", company__isnull=True)

    def admin_by_username(self, username: str) -> models.QuerySet["User"]:
        """그 username 의 운영 관리자(전역 unique — 많아야 한 행)."""
        return self._admins().filter(username=username)

    def admin_by_id(self, user_id: int) -> models.QuerySet["User"]:
        """그 id 의 운영 관리자(많아야 한 행). 고객사 사용자의 id 면 빈 것이다."""
        return self._admins().filter(pk=user_id)

    def register_admin(self, *, username: str, name: str, password: str) -> "User":
        """운영 관리자를 만드는 유일한 입구. level 99·is_initial(개정 3 처분). 겹치면 IntegrityError(전역 unique)."""
        return self._admins().create(
            kind="admin", company=None, username=username, name=name, level=99, is_initial=True, password=password
        )


class User(CompanyScopedModel, AbstractUser):
    kind = models.CharField(max_length=10)
    username = models.CharField(max_length=150)
    name = models.CharField(max_length=20)
    level = models.PositiveSmallIntegerField()
    # 글자로 가리킨다: 남의 models 를 import 하지 않는다(.importlinter 계약 나)
    company = models.ForeignKey("organization.Company", on_delete=models.CASCADE, null=True)
    company_id: int | None  # Django 가 외래 키마다 만들어 주는 칸. 타입 검사기가 알도록 적어 둔다
    tel = models.CharField(max_length=20, blank=True, default="")
    department = models.CharField(max_length=100, blank=True, default="")
    is_initial = models.BooleanField(default=True)
    login_failed_count = models.PositiveSmallIntegerField(default=0)
    login_expiry_at = models.DateTimeField(null=True)

    objects = CompanyScopedUserManager()  # 기본 매니저(AbstractUser 의 UserManager 를 덮는다)
    unscoped = models.Manager["User"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "users"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(kind="admin", company__isnull=True)
                | models.Q(kind="service", company__isnull=False),
                name="users_kind_company_check",
            ),
            models.CheckConstraint(condition=models.Q(level__in=LEVELS), name="users_level_values_check"),
            models.UniqueConstraint(
                fields=["username"], condition=models.Q(kind="admin"), name="users_admin_username_uniq"
            ),
            models.UniqueConstraint(
                fields=["company", "username"], condition=models.Q(kind="service"), name="users_company_username_uniq"
            ),
        )

    def __str__(self) -> str:
        return f"{self.company_id}:{self.username}"

    @classmethod
    def _manager(cls) -> CompanyScopedUserManager:
        manager = cls.objects
        if not isinstance(manager, CompanyScopedUserManager):
            raise TypeError("User.objects 가 CompanyScopedUserManager 가 아니다")
        return manager

    @classmethod
    def admin_by_username(cls, username: str) -> models.QuerySet["User"]:
        """운영 관리자 입구(찾기). 부르는 자리는 user/service/selectors/user.py 하나."""
        return cls._manager().admin_by_username(username)

    @classmethod
    def admin_by_id(cls, user_id: int) -> models.QuerySet["User"]:
        """운영 관리자 입구(id 로). 부르는 자리는 user/service/selectors/user.py 하나."""
        return cls._manager().admin_by_id(user_id)

    @classmethod
    def register_admin(cls, *, username: str, name: str, password: str) -> "User":
        """운영 관리자 입구(만들기). 부르는 자리는 user/service/services/user.py 의 create_operator 하나."""
        return cls._manager().register_admin(username=username, name=name, password=password)


class RefreshToken(models.Model):
    """refresh 토큰의 행(K2a). 토큰 글자는 저장하지 않는다 — jti(그 토큰)와 family(로그인 한 번에서 이어진 계보)만.

    rotate: refresh 를 한 번 쓰면 used_at 을 적고 같은 family 로 새 행을 넣는다.
    쓴 행을 다시 내면(재사용) 그 family 전부에 revoked_at 을 적는다(처분 B3).
    회사 칸이 없다(운영 관리자의 행은 회사가 없다) — 사용자에 딸린 표다.
    여는 길은 이름 붙은 입구뿐이다(by_jti·of_family·of_user·issue). 부르는 자리는 test_static_rules 의 USER_ENTRANCES.
    ★ user FK 를 따라 사용자를 읽지 않는다(K-B3): 사용자는 refresh 주장의 company_id 로 User.for_company 에서 읽는다.
    지난 행을 지우는 일은 2차다(앱 역할에 DELETE 를 주지 않는다 — migrations/0002_refresh_tokens.py).
    """

    jti = models.UUIDField(unique=True)
    family = models.UUIDField(db_index=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="+")
    user_id: int  # Django 가 외래 키마다 만들어 주는 칸
    issued_at = models.DateTimeField()
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True)
    revoked_at = models.DateTimeField(null=True)

    class Meta:
        db_table = "user_refresh_tokens"

    def __str__(self) -> str:
        return str(self.jti)

    @classmethod
    def _rows(cls) -> models.QuerySet["RefreshToken"]:
        return models.QuerySet["RefreshToken"](model=cls)

    @classmethod
    def by_jti(cls, jti: UUID) -> models.QuerySet["RefreshToken"]:
        """그 토큰의 행(많아야 하나)."""
        return cls._rows().filter(jti=jti)

    @classmethod
    def of_family(cls, family: UUID) -> models.QuerySet["RefreshToken"]:
        """그 계보의 행 전부."""
        return cls._rows().filter(family=family)

    @classmethod
    def of_user(cls, user_id: int) -> models.QuerySet["RefreshToken"]:
        """그 사용자의 행 전부(비밀번호 바꾸기·초기화가 끊는다)."""
        return cls._rows().filter(user_id=user_id)

    @classmethod
    def issue(
        cls, *, jti: UUID, family: UUID, user_id: int, issued_at: datetime, expires_at: datetime
    ) -> "RefreshToken":
        return cls._rows().create(jti=jti, family=family, user_id=user_id, issued_at=issued_at, expires_at=expires_at)
