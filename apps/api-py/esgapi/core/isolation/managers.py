"""회사 범위 표의 기본 매니저(격리의 받침 ②). 회사를 정하지 않은 조회는 DB 로 가기 전에 던진다.

범위 값은 회사의 숫자 id(양의 정수)다: 0·음수·bool·글자·None 은 거절한다. 회사 범위 모델은 여섯이다 —
뿌리 Company(organization), 회사 칸 표 User(user)·Site(organization)·DocumentRow·LlmCallLogRow(core)·JobRow(runs).

  회사 칸 표: CompanyScopedModel 을 잇고 칸 선언 뒤에 두 줄 —
      objects = CompanyScopedManager["<Model>"]()   # 첫 매니저 = 기본 매니저. for_company(<회사 id>) 로만 열린다
      unscoped = models.Manager["<Model>"]()        # 회사를 가로지르는 일(운영·테스트). 제품 코드는 쓰지 않는다
  뿌리(company): 범위 칸이 자기 id 다. CompanyRootManager — for_company(id) 는 그 행 하나의 범위, 이름 붙은 입구 둘
      (by_subdomain: 찾기, register: 만들기)은 행을 돌려줄 뿐 QuerySet 을 내주지 않는다. 입구를 부르는 자리는
      허용 목록으로 지킨다(core/tests/isolation/test_static_rules.py).

여는 길은 하나다: <Model>.for_company(company_id). 그 뒤 filter·order_by·select_for_update 를 이어도 범위가 남는다
(QuerySet 의 hints 에 실어 두면 Django 가 사본마다 물려준다). 범위 안의 create·bulk_create·update 는 다른 회사로
쓰지 못한다(CrossCompanyWriteError). <Model>.objects.all()·filter()·create()·count() … 와 역방향 관계 매니저
(document.jobs)는 UnscopedQueryError 다.

★ 이것이 막지 못하는 것(무효 조건):
  - _base_manager: 정방향 외래 키 읽기(job.document), save()·refresh_from_db()·delete() 의 수집은 Django 가 보통
    Manager 로 연다. 그래서 남의 회사 행을 가리키는 외래 키는 여기서 안 막힌다 → DB 의 같은 회사 외래 키
    (core/isolation/foreign_keys.py, 받침 ⑤)가 막는다. 생성자 <Model>(…) + save() 도 이 검사를 비껴간다 → 제품에서는
    허용 목록 밖에 0(core/tests/isolation/test_static_rules.py, 받침 ④).
  - update_or_create(defaults={"company_id": …}) 의 갱신 갈래는 save() 라 update() 검사를 안 지난다.
  - unscoped·raw SQL·psql 로 앱 역할에 붙는 것. 제품 코드의 것은 받침 ④ 가 글자로 막는다.
"""

from typing import Any, Self, TypeVar

from django.db import models
from django.db.models.sql.query import Query

from esgapi.core.calc.ids import is_company_id

_M = TypeVar("_M", bound=models.Model)


class UnscopedQueryError(RuntimeError):
    """회사를 정하지 않고 회사 범위 표를 열려 했다."""


COMPANY_FIELD = "company_id"


class CrossCompanyWriteError(RuntimeError):
    """범위의 회사와 다른 회사로 쓰려 했다(또는 회사 칸을 고치려 했다)."""


class CompanyScopedQuerySet(models.QuerySet[_M]):
    # Django 는 filter·order_by 마다 사본을 만들며 hints 를 __init__ 에 다시 넘긴다(QuerySet._clone).
    def __init__(
        self,
        model: type[models.Model] | None = None,
        query: Query | None = None,
        using: str | None = None,
        hints: dict[str, models.Model] | None = None,
    ) -> None:
        super().__init__(model=model, query=query, using=using, hints=hints)
        company: object = (hints or {}).get(COMPANY_FIELD)
        self.scoped_company_id: int | None = company if is_company_id(company) else None

    @property
    def scoped_company(self) -> int:
        if self.scoped_company_id is None:
            raise UnscopedQueryError(f"{self.model.__name__}: 범위의 회사가 없다")
        return self.scoped_company_id

    def _same_company(self, values: dict[str, Any]) -> None:
        if "company" in values:
            raise CrossCompanyWriteError("company= 가 아니라 company_id= 로 넘긴다")
        if values.setdefault(COMPANY_FIELD, self.scoped_company) != self.scoped_company:
            raise CrossCompanyWriteError("범위의 회사와 다른 회사로 쓰려 했다")

    def create(self, **kwargs: Any) -> _M:
        self._same_company(kwargs)
        return super().create(**kwargs)

    def bulk_create(self, objs: Any, *args: Any, **kwargs: Any) -> list[_M]:
        rows: list[_M] = list(objs)
        for row in rows:
            company: object = getattr(row, COMPANY_FIELD, None)
            if company is None:  # 칸을 안 채운 행
                setattr(row, COMPANY_FIELD, self.scoped_company)
            elif company != self.scoped_company:
                raise CrossCompanyWriteError("범위의 회사와 다른 회사로 쓰려 했다")
        return super().bulk_create(rows, *args, **kwargs)

    def update(self, **kwargs: Any) -> int:
        if COMPANY_FIELD in kwargs or "company" in kwargs:
            raise CrossCompanyWriteError("회사 칸은 고치지 않는다")
        return super().update(**kwargs)


def _checked(company_id: object) -> int:
    if not is_company_id(company_id):
        raise UnscopedQueryError(f"회사 id 는 양의 정수다: {company_id!r}")
    return company_id


class CompanyScopedManager(models.Manager[_M]):
    def get_queryset(self) -> CompanyScopedQuerySet[_M]:
        raise UnscopedQueryError(f"{self.model.__name__}.objects 는 for_company(<회사 id>) 로만 연다")

    def for_company(self, company_id: int) -> CompanyScopedQuerySet[_M]:
        checked = _checked(company_id)
        hints: dict[str, Any] = {COMPANY_FIELD: checked}
        queryset = CompanyScopedQuerySet[_M](model=self.model, using=self._db, hints=hints)
        return queryset.filter(**{COMPANY_FIELD: checked})


class CompanyScopedModel(models.Model):
    """회사 칸 표의 추상 바닥. 칸이 없다(마이그레이션에 안 실린다). 여는 길: <Model>.for_company(company_id).

    django-types 는 Model.objects 를 ClassVar[BaseManager[Self]] 로 못 박는다. 모델에 CompanyScopedManager 를 달아도
    타입 검사기는 <Model>.objects 를 BaseManager 로 본다(for_company 를 모른다). 그래서 여는 길을 classmethod 로 둔다.
    """

    class Meta:
        abstract = True

    @classmethod
    def for_company(cls, company_id: int) -> CompanyScopedQuerySet[Self]:
        manager = cls.objects
        if not isinstance(manager, CompanyScopedManager):
            raise UnscopedQueryError(f"{cls.__name__}.objects 가 CompanyScopedManager 가 아니다")
        return manager.for_company(company_id)


class CompanyRootManager(models.Manager[_M]):
    """뿌리 표(company)의 기본 매니저. 범위 칸이 자기 pk 다. 조건 없는 조회는 거절한다.

    이름 붙은 입구 둘(by_subdomain·register)은 행 하나를 돌려준다. QuerySet 을 내주지 않는다.
    """

    def get_queryset(self) -> models.QuerySet[_M]:
        raise UnscopedQueryError(f"{self.model.__name__}.objects 는 for_company(<회사 id>)·이름 붙은 입구로만 연다")

    def _entrance(self) -> models.QuerySet[_M]:
        return models.QuerySet[_M](model=self.model, using=self._db)

    def for_company(self, company_id: int) -> models.QuerySet[_M]:
        return self._entrance().filter(pk=_checked(company_id))

    def by_subdomain(self, subdomain: str) -> _M | None:
        """서브도메인으로 회사 하나(활성이든 아니든). 없으면 None. is_active 는 부르는 쪽이 본다."""
        if not subdomain:
            raise UnscopedQueryError("빈 서브도메인으로는 찾지 않는다")
        return self._entrance().filter(subdomain=subdomain).first()

    def register(self, **fields: Any) -> _M:
        """회사를 만드는 유일한 입구. 칸의 이름·검사는 모델의 register 가 정한다."""
        return self._entrance().create(**fields)


class CompanyRootModel(models.Model):
    """뿌리 표(company)의 추상 바닥. 여는 길: <Model>.for_company(id), 그리고 모델이 정한 이름 붙은 입구."""

    class Meta:
        abstract = True

    @classmethod
    def root_manager(cls) -> CompanyRootManager[Self]:
        manager = cls.objects
        if not isinstance(manager, CompanyRootManager):
            raise UnscopedQueryError(f"{cls.__name__}.objects 가 CompanyRootManager 가 아니다")
        return manager

    @classmethod
    def for_company(cls, company_id: int) -> models.QuerySet[Self]:
        return cls.root_manager().for_company(company_id)
