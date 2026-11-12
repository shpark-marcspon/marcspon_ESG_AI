"""기준정보(배출계수)의 표 넷. esg-lab 의 적재 산출물(`factors.jsonl`)과 조립용 대응표를 담는다.

★ **테넌트 칸이 없다.** 기준정보는 모든 고객사가 같이 읽는 전역 자료다(우리 데이터라 구조가 바뀌지 않는다.
  사용자 결정 2026-10-07). 그래서 RLS 를 걸지 않고, 앱 역할(esg_app)에는 SELECT 만 준다(migrations/0001).
  쓰기는 주인 역할의 관리 명령(`manage.py import_factors`)만 한다.
★ `tenant_id` 라는 이름의 칸을 두지 않는다: 그 이름이 있으면 보안 층의 카탈로그 검사(tests/security/test_owner.py)가
  이 표를 테넌트의 표로 보고 RLS 넷을 요구한다.

이름에 Row 를 붙인 까닭: 조립이 받는 순수 dataclass(`calc/types.py` 의 FactorRecord)와 헷갈리지 않게.
service/selectors/reference.py 가 Row 를 그것으로 바꿔 내보낸다(accounts 와 같은 규칙).

JSON 칸 넷에 붙인 따옴표 주석(`"models.JSONField[list[str]]"`)은 타입 검사기에게만 하는 말이다(실행에는 쓰이지 않는다).
"""

from typing import Any

from django.db import models

from esgapi.core.models import BaseModel
from esgapi.reference.jsonl import LICENSE_STATUSES


class SourceRow(BaseModel):
    """출처 하나: 원자료가 무엇이고 어디서 언제 받았으며 이용 조건이 어떤가.

    값은 jsonl 낱줄의 `source{…}`·`license{…}`·`license_status` 에서 온다. 코드에 문구를 박지 않는다.
    한 출처의 낱줄은 전부 같은 블록을 싣는다(가져오기가 견준다).
    """

    id = models.CharField(primary_key=True, max_length=63)
    name = models.TextField()
    publisher = models.TextField()
    url = models.TextField()
    # 버전, 고시 번호 또는 발행 연도. ★ 고시 별표(kr-ets-*)의 낱줄 id 에는 판이 없다. 판은 이 칸 하나가 말한다.
    version = models.TextField()
    # 원자료를 내려받아 확인한 날(YYYY-MM-DD). 글자 그대로 둔다: 조립이 근거에 그대로 싣는다.
    retrieved = models.CharField(max_length=10)
    file_name = models.TextField()
    file_sha256 = models.CharField(max_length=64)
    license_name = models.TextField()
    license_url = models.TextField()
    license_note = models.TextField(null=True)  # noqa: DJ001  NULL = 출처 등록부에 덧붙인 말이 없다
    # ok: 조건을 확인했고 쓸 수 있다 / unverified: 확인하지 못했다 / disputed: 공식 문면끼리 충돌한다(쓰지 않는다)
    license_status = models.CharField(max_length=20)

    class Meta(BaseModel.Meta):
        db_table = "reference_sources"
        constraints = (
            models.CheckConstraint(
                condition=models.Q(license_status__in=LICENSE_STATUSES), name="reference_sources_license_status_check"
            ),
        )

    def __str__(self) -> str:
        return self.id


class FactorRecordRow(BaseModel):
    """계수 표의 한 줄. 칸은 jsonl(schema_version 0.1)의 칸 그대로다."""

    # `<source_id>:<key>`. 출처 안에서 그 줄을 가리키는 열쇠다.
    id = models.CharField(primary_key=True, max_length=200)
    source = models.ForeignKey(SourceRow, on_delete=models.PROTECT, db_column="source_id", related_name="records")
    source_id: str  # Django 가 외래 키마다 만들어 주는 칸. 타입 검사기가 알도록 적어 둔다
    # 원자료 안의 위치(시트·행, 쪽·표·행). jsonl 에서는 source.locator 다.
    locator = models.TextField()
    schema_version = models.CharField(max_length=10)
    record_type = models.CharField(max_length=30)
    scope = models.CharField(max_length=30)
    scope3_mapping_basis = models.TextField(null=True)  # noqa: DJ001  NULL = scope3 범주의 후보가 아니다
    factor_type = models.CharField(max_length=20)
    name_original = models.TextField()
    name_ko = models.TextField(null=True)  # noqa: DJ001  번역하지 않는다. 출처가 한글이 아니면 NULL
    name_en = models.TextField(null=True)  # noqa: DJ001  번역하지 않는다. 출처가 영문이 아니면 NULL
    category_path: "models.JSONField[list[str]]" = models.JSONField()
    classification = models.JSONField(null=True)
    # ★ 조립은 이 칸을 읽지 않는다. float 라 십진 그대로가 아니다. 보여 주고 견주는 데만 쓴다.
    value = models.FloatField(null=True)
    # 출처 표기 그대로의 글자(「73,200」). 조립이 읽는 것은 이것이다.
    value_raw = models.TextField(null=True)  # noqa: DJ001  NULL 과 "" 를 가른다: NULL 만 「원문에 값이 없다」
    value_status = models.CharField(max_length=40)
    unit = models.TextField()
    unit_numerator = models.TextField()
    unit_denominator = models.TextField()
    gas = models.CharField(max_length=10)
    gas_basis = models.CharField(max_length=20)
    heating_value_basis = models.CharField(max_length=10, null=True)  # noqa: DJ001  NULL = 발열량 낱줄이 아니다
    conditions: "models.JSONField[dict[str, str]]" = models.JSONField()
    region = models.CharField(max_length=20)
    year = models.IntegerField(null=True)
    spend = models.JSONField(null=True)
    adjusted = models.JSONField(null=True)
    synthetic = models.BooleanField()
    extra: "models.JSONField[dict[str, Any]]" = models.JSONField()

    class Meta(BaseModel.Meta):
        db_table = "reference_factor_records"
        indexes = (models.Index(fields=["source", "record_type"], name="reference_factor_src_type_idx"),)

    def __str__(self) -> str:
        return self.id


class FactorScope3CategoryRow(models.Model):
    """낱줄 × Scope 3 범주(1~15). 그 낱줄이 그 범주의 **후보**라는 뜻이다. 확정이 아니다."""

    record = models.ForeignKey(
        FactorRecordRow, on_delete=models.CASCADE, db_column="record_id", related_name="scope3_categories"
    )
    record_id: str
    category = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "reference_factor_scope3_categories"
        constraints = (
            models.UniqueConstraint(fields=["record", "category"], name="reference_scope3_record_category_uniq"),
            models.CheckConstraint(
                condition=models.Q(category__gte=1, category__lte=15), name="reference_scope3_category_range_check"
            ),
        )

    def __str__(self) -> str:
        return f"{self.record_id}#{self.category}"


class MappingRow(BaseModel):
    """조립용 대응표 한 벌(`mappings.kr-ets.json`). 표로 풀지 않고 통째로 둔다: 조립 함수가 통째로 받는다."""

    # 지침의 판(대응표의 guideline.version). 판마다 한 벌이다.
    guideline_version = models.CharField(primary_key=True, max_length=200)
    body: "models.JSONField[dict[str, Any]]" = models.JSONField()

    class Meta(BaseModel.Meta):
        db_table = "reference_mappings"

    def __str__(self) -> str:
        return self.guideline_version
