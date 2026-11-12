"""inventory 의 모델: 온실가스 인덱스 풀(GhgIndexNode)과 시설별 배출계수 풀(GhgFactor·GhgFactorVersion·GhgFactorGas).
밴드 K1b-2a(결정 MARC-ENT-463·469 3, 화면 S19·S20).

**모든 고객사 공통 하나**(MARC-ENT-469 3): 네 표 다 회사 칸이 없어 회사 범위 모델이 아니다
(core/tests/test_selector_scope.py 의 GLOBAL_TABLES). 회사 데이터 0, 쓰기는 운영 관리자만(core/permissions.py 의
inventory_admin_ghg_* — MARC-ENT-478). 여는 자리는 inventory 의 selectors·services 뿐이다.

  ghg_index_nodes        4단 나무: 배출범위(scope) → 배출원 유형(source_type) → 배출활동(activity) →
                         자산/시설(facility). 잎만 시설 코드·1차 단위·툴팁을 가진다. 지우기는 삭제 표시.
  ghg_factors            계수의 정체(잎 하나에 여럿, 삭제 안 된 것 중 기본 정확히 하나). 지우기는 삭제 표시.
  ghg_factor_versions    계수의 판. **넣고 나면 고치지 않는다**(앱 역할 SELECT·INSERT 만) — 고치기는 새 판.
  ghg_factor_gases       판마다 가스 일곱 줄(고정 차례). 판과 같이 고치지 않는다.

회사 선택(K1b-2b)은 GhgFactorVersion 을 잡는다 — 풀에서 계수를 고쳐도 회사가 잡은 옛 판은 글자 그대로 남는다.

**회사 범위 표 둘**(K1b-2b — 결정 MARC-ENT-469 3·4, 화면 S17): 기본 매니저가 거절하고 for_company(<회사 id>) 로만 연다.
  inventory_years             회사의 인벤토리 해(회사·해 하나씩). 소수점 자릿수(decimals)를 가진다
  inventory_index_selections  그 해에 고른 풀 잎과 **잡은 판**(factor_version). 해와 같은 회사 외래 키(0002)
풀 표를 가리키는 외래 키 둘(잎·판)은 공통 표라 같은 회사 짝이 없다.

**회사 범위 표 셋 더**(S12a — 결정 MARC-ENT-463·469, 화면 S2·S3·S12):
  inventory_entry_rows     (선택 × 사업장 자산/시설) 입력 행 하나 — 행 단위·N/A·셈한 배출량(tCO2-eq). 지우기는 삭제 표시
  inventory_entry_values   행의 월 칸 값(`YYYY-MM`)·추정 표시. 행과 같이 남는다(지워도 값 그대로)
  inventory_entry_history  값·N/A 바뀜의 기록. **넣고 나면 고치지 않는다**(앱 역할 SELECT·INSERT 만 — updated_at 없음)
셋 다 같은 회사 외래 키(0003): 행 → 선택·자산/시설, 값·히스토리 → 행(남의 회사 것을 가리키면 그 문에서 23503).
선택 행의 칸 셋(memo·locked_at·locked_by_user_id)은 인덱스 메모·잠금이다(새 표 0 — 감독 판단 3).

**회사 범위 표 둘 더**(S12a-2 — 결정 MARC-ENT-517, 화면 S7·S9·S11·S12):
  inventory_entry_periods   (선택 × 사업장) 블록의 입력주기(month·quarter·year). 행이 없는 블록은 month(데이터 이전 0).
                            주기를 바꿔도 옛 주기 칸 값은 지우지 않는다(숨김 — 판단 E)
  inventory_custom_factors  행 전용 직접입력 계수(판 표 칸 꼴 + 가스 JSON — 판단 B). **넣고 나면 고치지 않는다**
                            (앱 역할 SELECT·INSERT 만 — updated_at 없음)
행은 계수 덮어쓰기 칸 둘(풀 판·직접입력 — 많아야 하나, 둘 다 없으면 선택의 잡은 판 · 판단 C), 히스토리는 사유와 계수
줄의 앞뒤 참조 넷을 더한다. 같은 회사 외래 키 다섯(0004): 주기 → 선택·사업장, 행·히스토리 앞뒤 → 직접입력.
reference 를 가리키는 외래 키는 없다(K1r 이 와도 0줄): 씨앗의 근거 낱줄 id 는 판의 seed_record_ids(JSON 글자)에만.

**회사 범위 표 하나 더**(S3K2a — 결정 MARC-ENT-559·469 2, 기획 RPT-21 §3.3):
  inventory_scope3_categories  (회사, 해, 카테고리) 하나의 잠금 — 잠근 때·사람·핀 실행 id(셋이 다 있거나 다 없음).
      「지금 결과」는 저장하지 않는다(읽을 때 셈 — service/utils/scope3_state.py). 빈 행 = 안 잠김.
      pinned_run_id 는 runs 로 외래 키가 아닌 정수 칸이다(MARC-ENT-210 — 다른 앱은 runs 로 FK 0).
      inventory_years 로 FK 0(해는 실행의 options.reportYear 에서 온다). 지우지 않는다(DELETE 0).
      실행 묶음(runbundle)에 싣지 않는다 — 핀은 실행 id 를 가리키는 확정 상태라 옮기면 id 가 어긋난다.
"""

from collections.abc import Collection

from django.db import models
from django.db.models.functions import Length, Trim
from django.db.models.lookups import GreaterThanOrEqual

from esgapi.core.isolation.managers import CompanyScopedManager, CompanyScopedModel
from esgapi.core.models import BaseModel
from esgapi.inventory.service.utils.entries import HISTORY_KINDS, PERIODS, REASON_MAX, SLOT_PATTERN
from esgapi.inventory.service.utils.ghg_pool import GASES, LEVELS
from esgapi.inventory.service.utils.index_selection import DECIMALS_RANGE, DEFAULT_DECIMALS, YEAR_FIRST, YEAR_LAST
from esgapi.inventory.service.utils.scope3_edits import EDIT_KINDS, ROW_ID_MAX, SCOPE3_REASON_MAX
from esgapi.inventory.service.utils.scope3_factors import (
    FACTOR_CHOICE_MAX,
    FACTOR_CHOICES,
    FACTOR_NUMBER_MAX,
    FACTOR_RANK_FIRST,
    FACTOR_RANK_LAST,
    FACTOR_TITLE_MAX,
    FACTOR_UNIT_MAX,
    SCOPE3_FACTOR_TEXT_MAX,
)
from esgapi.inventory.service.utils.scope3_state import CATEGORIES


class GhgIndexNode(BaseModel):
    """인덱스 풀의 노드 하나. 뿌리는 배출범위뿐이고(부모 없음), 「부모 단 = 자기 단 − 1」 은 services 가 지킨다.

    잎(facility)의 name 은 빈 글자다 — 응답은 시설 코드 이름을 select_related 로 읽는다(코드 이름 고침이 따라온다).
    facility_code 는 organization 의 공통 코드 목록(글자 참조 — 계약 나). 쓰이는 코드는 지울 수 없다(PROTECT).
    """

    level = models.CharField(max_length=20)
    parent = models.ForeignKey("self", on_delete=models.PROTECT, null=True, related_name="children")
    parent_id: int | None
    name = models.CharField(max_length=100, blank=True)
    sort_order = models.IntegerField(default=0)  # 기본 = 만든 차례(services 가 id 로 채운다)
    facility_code = models.ForeignKey(
        "organization.FacilityCode", on_delete=models.PROTECT, null=True, related_name="+"
    )
    facility_code_id: int | None
    unit_kind = models.CharField(max_length=20, null=True)  # noqa: DJ001  NULL = 잎이 아니다
    unit = models.CharField(max_length=20, null=True)  # noqa: DJ001  NULL = 잎이 아니다
    tooltip = models.CharField(max_length=1000, blank=True, default="")
    seed_key = models.CharField(max_length=300, null=True)  # noqa: DJ001  NULL = 씨앗 명령이 만든 행이 아니다
    deleted_at = models.DateTimeField(null=True)

    class Meta(BaseModel.Meta):
        db_table = "ghg_index_nodes"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(level__in=LEVELS),
                name="ghg_nodes_level_check",
            ),
            models.CheckConstraint(
                condition=models.Q(parent__isnull=True, level="scope")
                | models.Q(parent__isnull=False, level__in=LEVELS[1:]),
                name="ghg_nodes_root_is_scope",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    level="facility", facility_code__isnull=False, unit_kind__isnull=False, unit__isnull=False
                )
                | (
                    ~models.Q(level="facility")
                    & models.Q(facility_code__isnull=True, unit_kind__isnull=True, unit__isnull=True)
                ),
                name="ghg_nodes_leaf_fields",
            ),
            models.UniqueConstraint(
                fields=("parent", "name"),
                condition=models.Q(deleted_at__isnull=True) & ~models.Q(level="facility"),
                name="ghg_nodes_name_unique_alive",
            ),
            models.UniqueConstraint(
                fields=("name",),
                condition=models.Q(parent__isnull=True, deleted_at__isnull=True),
                name="ghg_nodes_root_name_unique_alive",
            ),
            models.UniqueConstraint(
                fields=("parent", "facility_code"),
                condition=models.Q(deleted_at__isnull=True),
                name="ghg_nodes_code_unique_alive",
            ),
            models.UniqueConstraint(
                fields=("seed_key",),
                condition=models.Q(seed_key__isnull=False),
                name="ghg_nodes_seed_key_unique",
            ),
        )

    def __str__(self) -> str:
        return self.name or f"{self.level} {self.pk}"


class GhgFactor(BaseModel):
    """계수의 정체. 값은 판(GhgFactorVersion)에 있고, current_version 이 지금 판의 번호다
    (고치기 = 정체 잠금 → +1 → 새 판).

    「삭제 안 된 계수가 있으면 기본이 정확히 하나」 중 「많아야 하나」 는 DB(부분 unique)가, 「적어도 하나」 는
    services 가 지킨다(첫 계수가 기본, 기본을 지우면 남은 첫 행이 잇는다).
    """

    facility_node = models.ForeignKey(GhgIndexNode, on_delete=models.PROTECT, related_name="factors")
    facility_node_id: int
    is_default = models.BooleanField(default=False)
    sort_order = models.IntegerField(default=0)
    current_version = models.IntegerField(default=1)
    seed_key = models.CharField(max_length=300, null=True)  # noqa: DJ001  NULL = 씨앗 명령이 만든 행이 아니다
    deleted_at = models.DateTimeField(null=True)

    class Meta(BaseModel.Meta):
        db_table = "ghg_factors"
        constraints = (
            models.UniqueConstraint(
                fields=("facility_node",),
                condition=models.Q(is_default=True, deleted_at__isnull=True),
                name="ghg_factors_one_default_alive",
            ),
            models.CheckConstraint(
                condition=~models.Q(is_default=True, deleted_at__isnull=False),
                name="ghg_factors_default_alive",
            ),
            models.CheckConstraint(
                condition=models.Q(current_version__gte=1),
                name="ghg_factors_version_positive",
            ),
            models.UniqueConstraint(
                fields=("seed_key",),
                condition=models.Q(seed_key__isnull=False),
                name="ghg_factors_seed_key_unique",
            ),
        )

    def __str__(self) -> str:
        return f"factor {self.pk} v{self.current_version}"


class GhgFactorVersion(models.Model):
    """계수의 판 하나. **고치지 않는다** — 앱 역할에 UPDATE·DELETE 가 없다(0001 의 grant). updated_at 이 없는 까닭.

    Decimal 칸(ncv)은 max_digits=30, decimal_places=12 — 주고받을 때는 글자다(지수 표기 0, utils 의 decimal_text).
    factor_unit 은 가스 계수의 단위(MARC-ENT-474 권장안 기본값: 순발열량 켬 kg/TJ, 끔 kg/<투입 단위>).
    """

    factor = models.ForeignKey(GhgFactor, on_delete=models.PROTECT, related_name="versions")
    factor_id: int
    version = models.IntegerField()
    name = models.CharField(max_length=100)
    source = models.CharField(max_length=200)
    base_year = models.SmallIntegerField()
    tier = models.SmallIntegerField()
    country_code = models.CharField(max_length=20)
    industry_code = models.CharField(max_length=40)
    input_unit_kind = models.CharField(max_length=20)
    input_unit = models.CharField(max_length=20)
    emission_unit_kind = models.CharField(max_length=20, default="mass")
    emission_unit = models.CharField(max_length=20, default="tCO2-eq")
    ncv_enabled = models.BooleanField(default=False)
    ncv = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    ncv_unit_kind = models.CharField(max_length=20, null=True)  # noqa: DJ001  NULL = 순발열량 끔
    ncv_unit = models.CharField(max_length=20, null=True)  # noqa: DJ001  NULL = 순발열량 끔
    factor_unit = models.CharField(max_length=30)
    note = models.CharField(max_length=1000, blank=True, default="")
    seed_record_ids: "models.JSONField[list[str]]" = models.JSONField(default=list)
    seed_gwp_set_id = models.CharField(max_length=63, null=True)  # noqa: DJ001  NULL = 씨앗이 아니다
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ghg_factor_versions"
        constraints = (
            models.UniqueConstraint(fields=("factor", "version"), name="ghg_factor_versions_unique"),
            models.CheckConstraint(condition=models.Q(version__gte=1), name="ghg_factor_versions_version_positive"),
            models.CheckConstraint(condition=models.Q(tier__in=(1, 2, 3)), name="ghg_factor_versions_tier_check"),
            models.CheckConstraint(
                condition=models.Q(base_year__gte=1990, base_year__lte=2100),
                name="ghg_factor_versions_base_year_range",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    ncv_enabled=True, ncv__isnull=False, ncv_unit_kind__isnull=False, ncv_unit__isnull=False
                )
                | models.Q(ncv_enabled=False, ncv__isnull=True, ncv_unit_kind__isnull=True, ncv_unit__isnull=True),
                name="ghg_factor_versions_ncv_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(ncv__isnull=True) | models.Q(ncv__gt=0),
                name="ghg_factor_versions_ncv_positive",
            ),
        )

    def __str__(self) -> str:
        return f"{self.name} v{self.version}"


class GhgFactorGas(models.Model):
    """판의 가스 한 줄. 판마다 늘 일곱 줄(「일곱 줄」·「켠 가스 ≥1」 은 services). 판과 같이 고치지 않는다."""

    factor_version = models.ForeignKey(GhgFactorVersion, on_delete=models.PROTECT, related_name="gases")
    factor_version_id: int
    gas = models.CharField(max_length=10)
    enabled = models.BooleanField(default=False)
    factor = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    gwp = models.DecimalField(max_digits=30, decimal_places=12, null=True)

    class Meta:
        db_table = "ghg_factor_gases"
        constraints = (
            models.UniqueConstraint(fields=("factor_version", "gas"), name="ghg_factor_gases_unique"),
            models.CheckConstraint(condition=models.Q(gas__in=GASES), name="ghg_factor_gases_gas_check"),
            models.CheckConstraint(
                # NULL 은 CHECK 를 지나간다 — 켠 줄은 값이 있음을 따로 적는다.
                condition=models.Q(enabled=False)
                | models.Q(factor__isnull=False, gwp__isnull=False, factor__gt=0, gwp__gt=0),
                name="ghg_factor_gases_enabled_values",
            ),
        )

    def __str__(self) -> str:
        return self.gas


class InventoryYear(BaseModel, CompanyScopedModel):
    """회사의 인벤토리 해 하나(회사 범위 — MARC-ENT-469 4). 첫 선택 저장이 만든다(GET 은 만들지 않는다).

    decimals 는 그 해 입력값의 소수점 자릿수(기본 DEFAULT_DECIMALS — 바꾸는 경로는 S12a). 지우지 않는다.
    """

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    year = models.SmallIntegerField()
    decimals = models.SmallIntegerField(default=DEFAULT_DECIMALS)

    objects = CompanyScopedManager["InventoryYear"]()
    unscoped = models.Manager["InventoryYear"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "inventory_years"
        constraints = (
            models.UniqueConstraint(fields=("company", "year"), name="inventory_years_company_year_unique"),
            models.CheckConstraint(
                condition=models.Q(decimals__gte=DECIMALS_RANGE[0], decimals__lte=DECIMALS_RANGE[1]),
                name="inventory_years_decimals_range",
            ),
            models.CheckConstraint(
                condition=models.Q(year__gte=YEAR_FIRST, year__lte=YEAR_LAST),
                name="inventory_years_year_range",
            ),
        )

    def __str__(self) -> str:
        return str(self.year)


class CompanyIndexSelection(BaseModel, CompanyScopedModel):
    """그 해에 회사가 고른 풀 잎 하나(회사 범위). 인덱스 풀은 모든 고객사 공통이다(MARC-ENT-469 3).

    factor_version 은 **잡은 판**이다: 고를 때 그 잎의 기본 계수의 지금 판을 잡고, 다시 저장하거나 풀에서 계수를
    고쳐도(새 판) 바꾸지 않는다. 「그 판이 그 잎의 계수」 는 services 가 지킨다(DB 로 못 건다).
    뺀 잎은 데이터가 없으면 삭제 표시(deleted_at), 있으면 숨김(hidden — 행·판 그대로, 다시 고르면 숨김을 푼다).
    지운 행은 숨기지 않는다(CHECK). 해와 같은 회사여야 한다(0002 의 같은 회사 외래 키 — 어기면 23503).
    """

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    inventory_year = models.ForeignKey(InventoryYear, on_delete=models.PROTECT, related_name="selections")
    inventory_year_id: int
    facility_node = models.ForeignKey(GhgIndexNode, on_delete=models.PROTECT, related_name="+")
    facility_node_id: int
    factor_version = models.ForeignKey(GhgFactorVersion, on_delete=models.PROTECT, related_name="+")
    factor_version_id: int
    hidden = models.BooleanField(default=False)
    deleted_at = models.DateTimeField(null=True)
    # S12a 인덱스 메모·잠금(감독 판단 3 — 선택 행의 칸). 잠근 사람은 users.pk(외래 키 아님 — 감사 행 꼴).
    memo = models.TextField(db_default="")
    locked_at = models.DateTimeField(null=True)
    locked_by_user_id = models.BigIntegerField(null=True)

    objects = CompanyScopedManager["CompanyIndexSelection"]()
    unscoped = models.Manager["CompanyIndexSelection"]()

    # ── 회사 넘는 존재 읽기의 이름 붙은 입구 둘(K1b-2b ④ — 결정 MARC-ENT-487, 이슈 MARC-ISSUE-432) ──
    # 운영 관리자가 공통 풀의 잎·계수를 지우거나 고칠 때 「어느 회사든 쓰는가」 만 묻는다. 돌려주는 것은 풀 id
    # 집합뿐이다(회사 id·행 내용 0). 부르는 자리는 selectors/index_selection.py 하나다
    # (core/tests/isolation/test_static_rules.py 의 MODEL_ENTRANCES). 숨긴 행도 쓰는 것이다(잡은 판이 남는다) · 삭제
    # 표시한 행은 아니다.

    @classmethod
    def used_node_ids(cls, ids: Collection[int]) -> frozenset[int]:
        """ids 가운데 어느 회사의 삭제 안 된 선택이 가리키는 풀 잎 id."""
        rows = models.QuerySet["CompanyIndexSelection"](model=cls).filter(
            deleted_at__isnull=True, facility_node_id__in=list(ids)
        )
        return frozenset(rows.values_list("facility_node_id", flat=True))

    @classmethod
    def used_factor_ids(cls, ids: Collection[int]) -> frozenset[int]:
        """ids 가운데 어느 회사의 삭제 안 된 선택이 판을 잡은 풀 계수 id."""
        rows = models.QuerySet["CompanyIndexSelection"](model=cls).filter(
            deleted_at__isnull=True, factor_version__factor_id__in=list(ids)
        )
        return frozenset(rows.values_list("factor_version__factor_id", flat=True))

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "inventory_index_selections"
        constraints = (
            models.UniqueConstraint(
                fields=("inventory_year", "facility_node"),
                condition=models.Q(deleted_at__isnull=True),
                name="inventory_selections_node_unique_alive",
            ),
            models.CheckConstraint(
                condition=~models.Q(hidden=True, deleted_at__isnull=False),
                name="inventory_selections_hidden_alive",
            ),
            models.CheckConstraint(  # S12a: 잠근 때와 잠근 사람은 같이 있거나 같이 없다
                condition=models.Q(locked_at__isnull=True, locked_by_user_id__isnull=True)
                | models.Q(locked_at__isnull=False, locked_by_user_id__isnull=False),
                name="inventory_selections_lock_pair",
            ),
        )

    def __str__(self) -> str:
        return f"selection {self.pk}"


class InventoryEntryPeriod(BaseModel, CompanyScopedModel):
    """블록(선택 × 사업장) 하나의 입력주기(S7). 행이 없으면 month. 선택·사업장과 같은 회사(0004 의 같은 회사 외래
    키 둘)."""

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    selection = models.ForeignKey(CompanyIndexSelection, on_delete=models.PROTECT, related_name="+")
    selection_id: int
    site: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Site", on_delete=models.PROTECT, related_name="+"
    )
    site_id: int
    period = models.CharField(max_length=8)

    objects = CompanyScopedManager["InventoryEntryPeriod"]()
    unscoped = models.Manager["InventoryEntryPeriod"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "inventory_entry_periods"
        constraints = (
            models.UniqueConstraint(fields=("selection", "site"), name="inventory_entry_periods_unique"),
            models.CheckConstraint(condition=models.Q(period__in=PERIODS), name="inventory_entry_periods_period_check"),
        )

    def __str__(self) -> str:
        return self.period


class InventoryCustomFactor(CompanyScopedModel):
    """행 전용 직접입력 계수 하나(S9·S11). **고치지 않는다**(앱 역할 SELECT·INSERT 만 — updated_at 없음). 칸은 판 표
    (GhgFactorVersion) 꼴이고 씨앗 칸·배출량 단위 칸은 없다(배출량은 tCO2-eq 하나 — 발주서 2-3 ⓛ). 가스는 JSON 한 칸
    (판단 B): 고정 차례 일곱 줄 `{gas, enabled, factor 글자|null, gwp 글자|null}`. 행위자는 감사 행 꼴(외래 키 아님)."""

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    name = models.CharField(max_length=100)
    source = models.CharField(max_length=200)
    base_year = models.SmallIntegerField()
    tier = models.SmallIntegerField()
    country_code = models.CharField(max_length=20)
    industry_code = models.CharField(max_length=40)
    input_unit_kind = models.CharField(max_length=20)
    input_unit = models.CharField(max_length=20)
    ncv_enabled = models.BooleanField(default=False)
    ncv = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    ncv_unit_kind = models.CharField(max_length=20, null=True)  # noqa: DJ001  NULL = 순발열량 끔
    ncv_unit = models.CharField(max_length=20, null=True)  # noqa: DJ001  NULL = 순발열량 끔
    factor_unit = models.CharField(max_length=30)
    note = models.CharField(max_length=1000, blank=True, default="")
    gases: "models.JSONField[list[dict[str, object]]]" = models.JSONField(default=list)
    actor_kind = models.CharField(max_length=16)
    actor_user_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    objects = CompanyScopedManager["InventoryCustomFactor"]()
    unscoped = models.Manager["InventoryCustomFactor"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "inventory_custom_factors"
        constraints = (  # 판 표(ghg_factor_versions)의 CHECK 넷과 같은 꼴
            models.CheckConstraint(condition=models.Q(tier__in=(1, 2, 3)), name="inventory_custom_factors_tier_check"),
            models.CheckConstraint(
                condition=models.Q(base_year__gte=1990, base_year__lte=2100),
                name="inventory_custom_factors_base_year_range",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    ncv_enabled=True, ncv__isnull=False, ncv_unit_kind__isnull=False, ncv_unit__isnull=False
                )
                | models.Q(ncv_enabled=False, ncv__isnull=True, ncv_unit_kind__isnull=True, ncv_unit__isnull=True),
                name="inventory_custom_factors_ncv_consistent",
            ),
            models.CheckConstraint(
                condition=models.Q(ncv__isnull=True) | models.Q(ncv__gt=0),
                name="inventory_custom_factors_ncv_positive",
            ),
        )

    def __str__(self) -> str:
        return self.name


class InventoryEntryRow(BaseModel, CompanyScopedModel):
    """입력 행 하나: 그 해 고른 잎(selection) × 사업장의 자산/시설(site_facility). 회사 범위.

    unit 은 행 단위(잎 단위이거나 환산 쌍이 있는 같은 종류 — services 가 지킨다). emission 은 잡은 판으로 셈한 tCO2-eq
    (빈 행·N/A 는 NULL), 셈할 수 없으면 emission_problem 에 까닭 글자. 지우기는 삭제 표시(값·히스토리 그대로).
    선택·자산/시설과 같은 회사여야 한다(0003 의 같은 회사 외래 키 둘).
    """

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    selection = models.ForeignKey(CompanyIndexSelection, on_delete=models.PROTECT, related_name="entry_rows")
    selection_id: int
    site_facility: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.SiteFacility", on_delete=models.PROTECT, related_name="+"
    )
    site_facility_id: int
    unit = models.CharField(max_length=20)
    na = models.BooleanField(default=False)
    emission = models.DecimalField(max_digits=30, decimal_places=12, null=True)
    emission_problem = models.CharField(max_length=40, null=True)  # noqa: DJ001  NULL = 셈했거나 셈할 것이 없다
    deleted_at = models.DateTimeField(null=True)
    # S12a-2 계수 덮어쓰기(S9·S11 — 판단 C): 많아야 하나. 둘 다 NULL = 선택의 잡은 판. 판은 계수의 지금 판을 잡는다.
    factor_version = models.ForeignKey(GhgFactorVersion, on_delete=models.PROTECT, null=True, related_name="+")
    factor_version_id: int | None
    custom_factor = models.ForeignKey(InventoryCustomFactor, on_delete=models.PROTECT, null=True, related_name="+")
    custom_factor_id: int | None

    objects = CompanyScopedManager["InventoryEntryRow"]()
    unscoped = models.Manager["InventoryEntryRow"]()

    # 회사 넘는 사용 중 읽기의 이름 붙은 입구(S12a-2 — 결정 MARC-ENT-487 꼴, 플랫폼-서버 e7 허락 H14): 운영 관리자가 풀
    # 계수를 지울 때 「어느 회사든 행이 덮어쓴 계수인가」만 묻는다. 풀 id 집합뿐(회사 id·행 내용 0). 부르는 자리는
    # selectors/index_selection.py 의 factors_in_use 하나. 히스토리 줄은 막지 않는다(지운 계수 줄은 복구 409 — 길 i).

    @classmethod
    def used_factor_ids(cls, ids: Collection[int]) -> frozenset[int]:
        """ids 가운데 어느 회사의 살아 있는 입력 행이 판을 잡은 풀 계수 id."""
        rows = models.QuerySet["InventoryEntryRow"](model=cls).filter(
            deleted_at__isnull=True, factor_version__factor_id__in=list(ids)
        )
        return frozenset(rows.values_list("factor_version__factor_id", flat=True))

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "inventory_entry_rows"
        constraints = (
            models.UniqueConstraint(
                fields=("selection", "site_facility"),
                condition=models.Q(deleted_at__isnull=True),
                name="inventory_entry_rows_unique_alive",
            ),
            models.CheckConstraint(  # S12a-2: 풀 판과 직접입력을 같이 잡지 않는다
                condition=models.Q(factor_version__isnull=True) | models.Q(custom_factor__isnull=True),
                name="inventory_entry_rows_one_factor",
            ),
        )

    def __str__(self) -> str:
        return f"entry row {self.pk}"


class InventoryEntryValue(BaseModel, CompanyScopedModel):
    """행의 칸 값 하나(slot 월 `YYYY-MM` · 분기 `YYYY-Qn` · 연 `YYYY` — S12a-2). amount NULL = 빈 칸. estimated = 추정값
    표시. 행과 같은 회사. 블록 주기 밖 칸의 값은 지우지 않고 남는다(상세·셈에서 빠짐 — 판단 E)."""

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    row = models.ForeignKey(InventoryEntryRow, on_delete=models.PROTECT, related_name="values")
    row_id: int
    slot = models.CharField(max_length=7)
    amount = models.DecimalField(max_digits=24, decimal_places=6, null=True)
    estimated = models.BooleanField(default=False)

    objects = CompanyScopedManager["InventoryEntryValue"]()
    unscoped = models.Manager["InventoryEntryValue"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "inventory_entry_values"
        constraints = (
            models.UniqueConstraint(fields=("row", "slot"), name="inventory_entry_values_unique"),
            models.CheckConstraint(
                condition=models.Q(amount__isnull=True) | models.Q(amount__gte=0),
                name="inventory_entry_values_amount_nonneg",
            ),
            models.CheckConstraint(
                condition=models.Q(slot__regex=SLOT_PATTERN), name="inventory_entry_values_slot_format"
            ),
        )

    def __str__(self) -> str:
        return self.slot


class InventoryEntryHistory(CompanyScopedModel):
    """값·N/A·단위·주기·계수 바뀜 한 줄. **고치지 않는다**(앱 역할 SELECT·INSERT 만 — 판 표 꼴이라 updated_at 이 없다).

    before·after 는 value 면 Decimal 글자(빈 칸 NULL), unit 이면 단위, period 면 주기 글자, factor 면 NULL(앞뒤는 참조
    칸 넷 — 판 또는 직접입력 정확히 하나씩). 복구(S12)도 같은 종류의 새 줄이다. reason 은 계수 바꿈·복구의 사유.
    행위자는 actor_kind(service·admin)와 users.pk(외래 키 아님 — 감사 행 꼴).
    """

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    row = models.ForeignKey(InventoryEntryRow, on_delete=models.PROTECT, related_name="history")
    row_id: int
    kind = models.CharField(max_length=10)
    slot = models.CharField(max_length=7, null=True)  # noqa: DJ001  NULL = 행 하나의 바뀜(N/A)
    before = models.CharField(max_length=40, null=True)  # noqa: DJ001  NULL = 빈 칸
    after = models.CharField(max_length=40, null=True)  # noqa: DJ001  NULL = 빈 칸
    unit = models.CharField(max_length=20)
    actor_kind = models.CharField(max_length=16)
    actor_user_id = models.BigIntegerField(null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    reason = models.CharField(max_length=REASON_MAX, null=True)  # noqa: DJ001  NULL = 사유 없는 줄
    before_version = models.ForeignKey(GhgFactorVersion, on_delete=models.PROTECT, null=True, related_name="+")
    before_version_id: int | None
    after_version = models.ForeignKey(GhgFactorVersion, on_delete=models.PROTECT, null=True, related_name="+")
    after_version_id: int | None
    before_custom = models.ForeignKey(InventoryCustomFactor, on_delete=models.PROTECT, null=True, related_name="+")
    before_custom_id: int | None
    after_custom = models.ForeignKey(InventoryCustomFactor, on_delete=models.PROTECT, null=True, related_name="+")
    after_custom_id: int | None

    objects = CompanyScopedManager["InventoryEntryHistory"]()
    unscoped = models.Manager["InventoryEntryHistory"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "inventory_entry_history"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(kind__in=HISTORY_KINDS), name="inventory_entry_history_kind_check"
            ),
            models.CheckConstraint(  # S12a-2: 계수 줄만 앞뒤 참조를 가지고, 앞·뒤 각각 판 또는 직접입력 정확히 하나
                condition=(
                    ~models.Q(kind="factor")
                    & models.Q(
                        before_version__isnull=True,
                        after_version__isnull=True,
                        before_custom__isnull=True,
                        after_custom__isnull=True,
                    )
                )
                | (
                    models.Q(kind="factor")
                    & (
                        models.Q(before_version__isnull=False, before_custom__isnull=True)
                        | models.Q(before_version__isnull=True, before_custom__isnull=False)
                    )
                    & (
                        models.Q(after_version__isnull=False, after_custom__isnull=True)
                        | models.Q(after_version__isnull=True, after_custom__isnull=False)
                    )
                ),
                name="inventory_entry_history_factor_refs",
            ),
        )

    def __str__(self) -> str:
        return f"{self.kind} {self.slot or ''}".strip()


class Scope3CategoryState(BaseModel, CompanyScopedModel):
    """(회사, 해, 카테고리) 하나의 Scope 3 잠금(회사 범위 — S3K2a Q7). 행은 첫 잠금이 만든다(GET 은 만들지 않는다).

    잠금 셋(locked_at·locked_by_user_id·pinned_run_id)은 같이 있거나 같이 없다(CHECK — selections 의 lock_pair 꼴).
    잠근 사람은 users.pk(외래 키 아님 — 감사 행 꼴), 핀은 run_runs.pk(외래 키 아님 — MARC-ENT-210). 풀면 셋 다 NULL.
    """

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    year = models.SmallIntegerField()
    category = models.CharField(max_length=3)
    locked_at = models.DateTimeField(null=True)
    locked_by_user_id = models.BigIntegerField(null=True)
    pinned_run_id = models.BigIntegerField(null=True)

    objects = CompanyScopedManager["Scope3CategoryState"]()
    unscoped = models.Manager["Scope3CategoryState"]()

    class Meta(BaseModel.Meta, CompanyScopedModel.Meta):
        db_table = "inventory_scope3_categories"
        constraints = (
            models.UniqueConstraint(fields=("company", "year", "category"), name="inventory_scope3_categories_unique"),
            models.CheckConstraint(
                condition=models.Q(year__gte=YEAR_FIRST, year__lte=YEAR_LAST),
                name="inventory_scope3_categories_year_range",
            ),
            models.CheckConstraint(
                condition=models.Q(category__in=CATEGORIES), name="inventory_scope3_categories_category_check"
            ),
            models.CheckConstraint(
                condition=models.Q(locked_at__isnull=True, locked_by_user_id__isnull=True, pinned_run_id__isnull=True)
                | models.Q(locked_at__isnull=False, locked_by_user_id__isnull=False, pinned_run_id__isnull=False),
                name="inventory_scope3_categories_lock_triple",
            ),
        )

    def __str__(self) -> str:
        return f"{self.year} {self.category}"


class Scope3RowEdit(CompanyScopedModel):
    """Scope 3 결과 줄의 편집 한 번(표 inventory_scope3_row_edits — S3K2b-1, 결정 MARC-ENT-570). **고치지 않는다**.

    ★ 불변 행이다(앱 역할 SELECT·INSERT 만 — updated_at 이 없다): 지금 상태 = 그 (실행, rowId) 의 가장 큰 id 사건,
      히스토리 = 그 사건들. 복구도 새 사건이다. 새 실행에 옮겨 붙이지 않는다(570).
    ★ run_id 는 run_runs.pk 이고 외래 키가 아니다(MARC-ENT-210). actor_user_id 도 외래 키가 아니다(감사 행 꼴).
    batch_id 는 한 요청의 사건을 묶는다(요청마다 uuid4 — UPDATE 권한이 없어 첫 사건 id 로는 못 묶는다).
    ★ kind factor(S3K2b-2): 고른 계수·그때 센 배출량과 사건 때 뜬 AI 원안(537)을 칸에 남긴다 — 수는 `repr(float)` 글자.
      결과 본문은 덮지 않는다. 다른 kind 면 이 칸들은 전부 null 이다(모양 CHECK).
    """

    company: "models.ForeignKey[models.Model]" = models.ForeignKey(
        "organization.Company", on_delete=models.PROTECT, related_name="+"
    )
    company_id: int
    run_id = models.BigIntegerField()
    category = models.CharField(max_length=3)
    row_id = models.CharField(max_length=ROW_ID_MAX)
    kind = models.CharField(max_length=10)
    reason = models.CharField(max_length=SCOPE3_REASON_MAX)
    actor_kind = models.CharField(max_length=16)
    actor_user_id = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    batch_id = models.UUIDField(null=True)
    factor_choice = models.CharField(max_length=FACTOR_CHOICE_MAX, null=True)  # noqa: DJ001 — 없음과 빈 글이 다르다
    factor_rank = models.SmallIntegerField(null=True)
    factor_title = models.CharField(max_length=FACTOR_TITLE_MAX, null=True)  # noqa: DJ001
    factor_value = models.CharField(max_length=FACTOR_NUMBER_MAX, null=True)  # noqa: DJ001
    factor_source = models.CharField(max_length=SCOPE3_FACTOR_TEXT_MAX, null=True)  # noqa: DJ001
    factor_unit = models.CharField(max_length=FACTOR_UNIT_MAX, null=True)  # noqa: DJ001
    co2e = models.CharField(max_length=FACTOR_NUMBER_MAX, null=True)  # noqa: DJ001
    biogenic_co2e = models.CharField(max_length=FACTOR_NUMBER_MAX, null=True)  # noqa: DJ001
    ai_factor_title = models.CharField(max_length=FACTOR_TITLE_MAX, null=True)  # noqa: DJ001
    ai_factor_value = models.CharField(max_length=FACTOR_NUMBER_MAX, null=True)  # noqa: DJ001
    ai_factor_source = models.CharField(max_length=SCOPE3_FACTOR_TEXT_MAX, null=True)  # noqa: DJ001
    ai_co2e = models.CharField(max_length=FACTOR_NUMBER_MAX, null=True)  # noqa: DJ001

    objects = CompanyScopedManager["Scope3RowEdit"]()
    unscoped = models.Manager["Scope3RowEdit"]()

    class Meta(CompanyScopedModel.Meta):
        db_table = "inventory_scope3_row_edits"
        indexes = (
            models.Index(fields=("company", "run_id", "row_id", "id"), name="inv_s3_edits_run_row_idx"),
            models.Index(fields=("company", "run_id", "category"), name="inv_s3_edits_run_cat_idx"),
            models.Index(fields=("company", "run_id", "batch_id"), name="inv_s3_edits_run_batch_idx"),
        )
        constraints = (
            models.CheckConstraint(
                condition=models.Q(category__in=CATEGORIES), name="inventory_scope3_row_edits_category_check"
            ),
            models.CheckConstraint(
                condition=models.Q(kind__in=EDIT_KINDS), name="inventory_scope3_row_edits_kind_check"
            ),
            models.CheckConstraint(
                condition=models.Q(GreaterThanOrEqual(Length("row_id"), 1)),
                name="inventory_scope3_row_edits_row_id_check",
            ),
            models.CheckConstraint(
                condition=models.Q(GreaterThanOrEqual(Length(Trim("reason")), 1)),
                name="inventory_scope3_row_edits_reason_check",
            ),
            models.CheckConstraint(
                condition=models.Q(factor_choice__in=FACTOR_CHOICES) | models.Q(factor_choice__isnull=True),
                name="inventory_scope3_row_edits_factor_choice_check",
            ),
            models.CheckConstraint(
                condition=models.Q(factor_rank__gte=FACTOR_RANK_FIRST, factor_rank__lte=FACTOR_RANK_LAST)
                | models.Q(factor_rank__isnull=True),
                name="inventory_scope3_row_edits_factor_rank_check",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    models.Q(factor_choice="recommended", factor_rank__isnull=False)
                    | models.Q(factor_choice="applied", factor_rank__isnull=True)
                    | models.Q(
                        factor_choice="custom",
                        factor_rank__isnull=True,
                        factor_title__isnull=False,
                        factor_value__isnull=False,
                        factor_source__isnull=False,
                    ),
                    kind="factor",
                    factor_choice__isnull=False,  # 없으면 위 비교가 NULL 이라 CHECK 를 지나간다
                )
                | (
                    ~models.Q(kind="factor")  # 모르는 kind 는 kind CHECK 몫이다
                    & models.Q(
                        factor_choice__isnull=True,
                        factor_rank__isnull=True,
                        factor_title__isnull=True,
                        factor_value__isnull=True,
                        factor_source__isnull=True,
                        factor_unit__isnull=True,
                        co2e__isnull=True,
                        biogenic_co2e__isnull=True,
                        ai_factor_title__isnull=True,
                        ai_factor_value__isnull=True,
                        ai_factor_source__isnull=True,
                        ai_co2e__isnull=True,
                    )
                ),
                name="inventory_scope3_row_edits_factor_shape",
            ),
        )

    def __str__(self) -> str:
        return f"{self.run_id} {self.row_id} {self.kind}"
