"""조직의 표: 회사(company)와 사업장(sites), 자산/시설 코드 목록(공통)·사업장별 자산/시설(K1b-1).
EDK 리뉴얼 꼴(원문의 Company)에서 1차에 쓰는 칸만 둔다(K1u-a).

회사는 격리의 뿌리다: 범위 칸이 자기 id 다(core/isolation/managers.py 의 CompanyRootManager). 기본 매니저는 조건 없는
조회를 거절하고, 여는 길은 넷뿐이다 — Company.for_company(<회사 id>), 이름 붙은 입구 셋:
  Company.by_subdomain(…)     찾기. 부르는 자리는 service/selectors/organization.py 하나
                              (교환과 seed_company 가 그 함수를 쓴다)
  Company.register(…)         만들기. 부르는 자리는 management/commands/seed_company.py 하나
  Company.sole_candidates()   「하나뿐인 회사」(K2c — 사용자 결정 「시드로하자」). 회사 표의 앞 두 행까지만 읽는다.
                              부르는 자리는 service/selectors/organization.py 의 find_sole_company 하나
(core/tests/isolation/test_static_rules.py 가 호출 자리를 허용 목록으로 지킨다.)

나머지 EDK 칸(plan·기간·언어·담당자·주소 등)은 뜻이 정해지면(질문 9) 더함 마이그레이션으로 넣는다.
앱 역할(esg_app)에는 SELECT 만 준다(migrations/0001_initial.py) — 요청을 처리하는 프로세스는 회사를 만들지 못한다.
"""

from collections.abc import Collection
from typing import Final

from django.db import models
from django.db.models.functions import Now

from esgapi.core.isolation.managers import (
    CompanyRootManager,
    CompanyRootModel,
    CompanyScopedManager,
    CompanyScopedModel,
)
from esgapi.core.models import BaseModel

# 서브도메인의 꼴. EDK 토큰의 tenant_id 주장과 같은 규칙이다(소문자·숫자·하이픈, 1~63자).
# 교환은 이 값으로 회사를 찾는다.
SUBDOMAIN_PATTERN: Final = r"^[a-z0-9][a-z0-9-]{0,62}$"


class CompanyManager(CompanyRootManager["Company"]):
    """company 의 기본 매니저. 바닥(CompanyRootManager)의 거절·입구 둘에 「하나뿐인 회사」의 입구 하나를 더한다
    (user 의 CompanyScopedUserManager 와 같은 꼴 — 바닥 managers.py 는 그대로).
    마이그레이션에 싣지 않는다(바닥과 같이 use_in_migrations 거짓)."""

    def sole_candidates(self) -> list["Company"]:
        """회사 표의 앞 두 행(id 오름)까지만. 0·1·2 를 가르는 데 쓴다 — 행을 다 세지 않는다(회사가 늘어도 같은 비용).
        ★ 의도한 회사를 넘는 읽기다: 운영 관리자 경로와 서브도메인 없는 로그인에서만, 부르는 쪽이 칸 셋
        (id·subdomain·is_active)만 밖으로 낸다."""
        return list(self._entrance().order_by("id")[:2])


class Company(BaseModel, CompanyRootModel):
    name = models.CharField(max_length=100)
    business_licence_number = models.CharField(max_length=18, unique=True)
    subdomain = models.CharField(max_length=100, unique=True)
    # 새 회사는 쓸 수 없는 채로 선다(원문의 기본값). seed_company 가 쓸 수 있게 만든다.
    is_active = models.BooleanField(default=False)

    objects = CompanyManager()
    unscoped = models.Manager["Company"]()

    class Meta(BaseModel.Meta, CompanyRootModel.Meta):
        db_table = "company"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(subdomain__regex=SUBDOMAIN_PATTERN), name="company_subdomain_format"
            ),
        )

    def __str__(self) -> str:
        return self.subdomain

    @classmethod
    def by_subdomain(cls, subdomain: str) -> "Company | None":
        """서브도메인으로 회사 하나(활성이든 아니든). 없으면 None. 활성인지는 부르는 쪽(selectors)이 본다."""
        return cls.root_manager().by_subdomain(subdomain)

    @classmethod
    def sole_candidates(cls) -> list["Company"]:
        """「하나뿐인 회사」의 입구: 회사 표의 앞 두 행까지만. 하나인지는 부르는 쪽(selectors)이 본다."""
        manager = cls.root_manager()
        if not isinstance(manager, CompanyManager):
            raise TypeError("Company.objects 가 CompanyManager 가 아니다")
        return manager.sole_candidates()

    @classmethod
    def register(cls, *, name: str, business_licence_number: str, subdomain: str) -> "Company":
        """회사를 만드는 유일한 입구. 쓸 수 있는 회사(is_active)로 만든다. 겹치면 IntegrityError."""
        return cls.root_manager().register(
            name=name, business_licence_number=business_licence_number, subdomain=subdomain, is_active=True
        )


class Site(CompanyScopedModel):
    """사업장(EDK 꼴의 Branch — 표·모델 이름은 그대로 sites·Site). 옛 accounts 의 SiteRow 꼴에 K1b-1 이 칸 넷을 더했다
    (더하기만 — 기존 칸의 이름·꼴·제약 0 바뀜). 경로는 /branches(옛 /sites 둘은 계약 그대로, deprecated).

    회사마다 본사가 정확히 하나다(시드·데이터 이전 0003). 본사는 지울 수 없고 인벤토리 사용이 늘 켜져 있다 —
    아래 제약 둘과 services 둘 다로 막는다. 지우기는 삭제 표시(deleted_at)다: 앱 역할에 DELETE 가 없다.
    이름은 같은 회사의 삭제 안 된 것끼리 겹치지 않는다(지운 이름은 다시 쓴다). 회사 밖(그룹·상위 회사)을 가리키는 칸 0
    (MARC-ENT-469 — 나중에 상위 회사 칸을 더해도 옮길 것 0).
    회사 칸 표라 기본 매니저가 회사를 정하지 않은 조회를 거절한다(Site.for_company(…) 로만).
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    company_id: int  # Django 가 외래 키마다 만들어 주는 칸. 타입 검사기가 알도록 적어 둔다
    # EDK 가 준 사업장 ID. 우리 쪽에서 만든 사업장이면 비어 있다(NULL).
    external_id = models.CharField(max_length=200, null=True)  # noqa: DJ001  NULL 과 "" 를 가른다: NULL 만 「EDK 쪽 ID 없음」
    name = models.CharField(max_length=200)
    created_at = models.DateTimeField(auto_now_add=True)
    # K1b-1: 더한 칸 넷. 기존 행은 기본값으로 채운다(본사 아님·인벤토리 켬·삭제 안 됨). 기본값을 DB 에도 둔다
    # (db_default) — 칸 넷을 모르는 INSERT(옛 코드·보안 층의 SQL 씨앗)도 그대로 선다.
    is_headquarters = models.BooleanField(default=False, db_default=False)
    inventory_enabled = models.BooleanField(default=True, db_default=True)
    deleted_at = models.DateTimeField(null=True)
    updated_at = models.DateTimeField(auto_now=True, db_default=Now())

    objects = CompanyScopedManager["Site"]()
    unscoped = models.Manager["Site"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "sites"
        constraints = (
            models.UniqueConstraint(
                fields=("company",), condition=models.Q(is_headquarters=True), name="sites_one_headquarters_per_company"
            ),
            models.UniqueConstraint(
                fields=("company", "name"), condition=models.Q(deleted_at__isnull=True), name="sites_name_unique_alive"
            ),
            models.CheckConstraint(
                condition=~models.Q(is_headquarters=True, deleted_at__isnull=False), name="sites_headquarters_alive"
            ),
            models.CheckConstraint(
                condition=models.Q(is_headquarters=False) | models.Q(inventory_enabled=True),
                name="sites_headquarters_inventory_on",
            ),
        )

    def __str__(self) -> str:
        return self.name


class FacilityCode(BaseModel):
    """자산/시설 코드 목록 — **모든 고객사 공통 하나**(MARC-ENT-469 3). 회사 칸이 없어 회사 범위 모델이 아니다
    (core/tests/test_selector_scope.py 의 GLOBAL_TABLES). 회사 데이터 0, 쓰기는 운영 관리자만(core/permissions.py).

    code 는 만들 때 F0001 꼴로 자동(같은 트랜잭션의 INSERT 뒤 UPDATE)이고 이름을 고쳐도 그대로다. 지우기는 삭제 표시:
    새 선택 목록에서만 빠지고, 이미 쓰는 site_facilities 행은 그대로 코드 글자·이름이 보인다
    (FK PROTECT — 하드 지우기 0).
    여는 자리는 organization 의 selectors·services 뿐이다.
    """

    # 만드는 문(INSERT)에서는 비어 있고 같은 트랜잭션의 UPDATE 가 F<id 네 자리> 로 채운다(services 의 한 블록).
    code = models.CharField(max_length=10, unique=True, null=True)  # noqa: DJ001  NULL = 그 블록 안의 잠깐뿐
    name = models.CharField(max_length=100)
    sort_order = models.IntegerField(default=0)  # 기본 = 만든 차례(services 가 id 로 채운다)
    deleted_at = models.DateTimeField(null=True)

    class Meta(BaseModel.Meta):
        db_table = "organization_facility_codes"
        constraints = (
            models.UniqueConstraint(
                fields=("name",), condition=models.Q(deleted_at__isnull=True), name="facility_codes_name_unique_alive"
            ),
        )

    def __str__(self) -> str:
        return self.code or self.name


class SiteFacility(BaseModel, CompanyScopedModel):
    """사업장별 자산/시설(사업장 하나 × 코드 하나 × 세부시설명). 회사 칸 표 — 사업장과 같은 회사여야 한다:
    (company_id, site_id) → sites (company_id, id) 같은 회사 외래 키를 0002 가 건다(남의 회사 사업장을 가리키면 23503).
    facility_code 는 공통 표라 짝이 없다. 사업장 안 (코드, 세부시설명)은 삭제 안 된 것끼리 겹치지 않는다.
    지우기는 삭제 표시(앱 역할에 DELETE 없음).
    """

    company = models.ForeignKey(Company, on_delete=models.PROTECT)
    company_id: int
    site = models.ForeignKey(Site, on_delete=models.PROTECT)
    site_id: int
    facility_code = models.ForeignKey(FacilityCode, on_delete=models.PROTECT)
    facility_code_id: int
    detail_name = models.CharField(max_length=200)
    deleted_at = models.DateTimeField(null=True)

    objects = CompanyScopedManager["SiteFacility"]()
    unscoped = models.Manager["SiteFacility"]()

    # ── 회사 넘는 존재 읽기의 이름 붙은 입구 하나(S12S1 Q9 — 7a 허락) ──
    # inventory CompanyIndexSelection.used_node_ids 꼴.
    # 운영 관리자가 공통 코드 목록의 옛 씨앗 코드를 지울 때 「어느 회사의 사업장이든 쓰는가」 만 묻는다. 돌려주는 것은
    # 코드 id 집합뿐이다(회사 id·행 내용 0). 부르는 자리는 organization/service/selectors/facility_codes.py 하나다
    # (core/tests/isolation/test_static_rules.py 의 MODEL_ENTRANCES). 삭제 표시한 행은 쓰는 것이 아니다(숨김 칸은 없다).

    @classmethod
    def used_code_ids(cls, ids: Collection[int]) -> frozenset[int]:
        """ids 가운데 어느 회사의 삭제 안 된 사업장 자산/시설이 가리키는 공통 코드 id."""
        rows = models.QuerySet["SiteFacility"](model=cls).filter(
            deleted_at__isnull=True, facility_code_id__in=list(ids)
        )
        return frozenset(rows.values_list("facility_code_id", flat=True))

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "site_facilities"
        constraints = (
            models.UniqueConstraint(
                fields=("site", "facility_code", "detail_name"),
                condition=models.Q(deleted_at__isnull=True),
                name="site_facilities_unique_alive",
            ),
        )

    def __str__(self) -> str:
        return self.detail_name
