"""사업장 넓힘 + 자산/시설 코드 목록(공통) + 사업장별 자산/시설. 밴드 K1b-1 ①(결정 MARC-ENT-469 3·4, 티켓 MARC-TICK-358).

**더하기만이다**: sites 의 기존 칸(id·company_id·external_id·name·created_at)의 이름·꼴·제약 0 바뀜, 지우는 것 0.
되돌리면(0002 → 0001) 더한 칸·제약·표 둘이 지워지고 sites 의 행은 남는다(더한 칸의 값은 잃는다).
★ 삭제 표시(deleted_at)도 잃는다 — 지운 사업장이 되돌린 뒤 옛 GET /sites 에 다시 보인다(가지 리뷰 L5).

  sites 칸 넷        is_headquarters bool 기본 거짓 · inventory_enabled bool 기본 참 · deleted_at NULL ·
                     updated_at(기존 행은 이행 시각). 넷 다 DB 에도 기본값(db_default) — 칸 넷을 모르는 INSERT 도 선다
  sites 제약 넷      sites_one_headquarters_per_company   UNIQUE (company_id) WHERE is_headquarters
                     sites_name_unique_alive               UNIQUE (company_id, name) WHERE deleted_at IS NULL
                     sites_headquarters_alive              CHECK NOT (is_headquarters AND deleted_at IS NOT NULL)
                     sites_headquarters_inventory_on       CHECK (NOT is_headquarters OR inventory_enabled)
  organization_facility_codes   회사 칸 없음(전 고객사 공통). code UNIQUE · 이름 UNIQUE WHERE deleted_at IS NULL
  site_facilities               회사 칸 표. (site, facility_code, detail_name) UNIQUE WHERE deleted_at IS NULL
  RunSQL             sites_company_id_uniq                         UNIQUE (company_id, id) — 아래 짝이 가리킬 자리
                     site_facilities_site_id_same_company_fk       (company_id, site_id) → sites (company_id, id)
                     site_facilities_company_id_uniq               UNIQUE (company_id, id) — 뒤 밴드의 짝이 가리킬 자리
                     (core/isolation/foreign_keys.py — NOT DEFERRABLE, 남의 회사 사업장을 가리키면 그 문에서 23503)
  GRANT              새 표 둘 SELECT, INSERT, UPDATE(DELETE 없음 — 지우기는 삭제 표시). sites 권한 0 바뀜.

★ 이름 unique 는 배포본 DB 에 같은 회사·같은 이름(삭제 안 된 것) 사업장이 둘 있으면 이 이행이 DB 오류로 멈춘다 —
  조용히 이름을 바꾸지 않는다(병합 전에 배포본에서 겹침 0 을 확인한다).
본사 씨앗(이미 있는 회사마다 본사 하나)은 데이터 이전 0003 이 따로 한다(스키마 왕복과 가르려고).
"""

import django.db.models.deletion
import django.db.models.functions.datetime
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

CODES = "organization_facility_codes"
FACILITIES = "site_facilities"


class Migration(migrations.Migration):
    dependencies = [
        ("organization", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="site",
            name="is_headquarters",
            field=models.BooleanField(db_default=False, default=False),
        ),
        migrations.AddField(
            model_name="site",
            name="inventory_enabled",
            field=models.BooleanField(db_default=True, default=True),
        ),
        migrations.AddField(
            model_name="site",
            name="deleted_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="site",
            name="updated_at",
            field=models.DateTimeField(auto_now=True, db_default=django.db.models.functions.datetime.Now()),
        ),
        migrations.AddConstraint(
            model_name="site",
            constraint=models.UniqueConstraint(
                condition=models.Q(("is_headquarters", True)),
                fields=("company",),
                name="sites_one_headquarters_per_company",
            ),
        ),
        migrations.AddConstraint(
            model_name="site",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("company", "name"),
                name="sites_name_unique_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="site",
            constraint=models.CheckConstraint(
                condition=models.Q(("deleted_at__isnull", False), ("is_headquarters", True), _negated=True),
                name="sites_headquarters_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="site",
            constraint=models.CheckConstraint(
                condition=models.Q(("is_headquarters", False), ("inventory_enabled", True), _connector="OR"),
                name="sites_headquarters_inventory_on",
            ),
        ),
        migrations.CreateModel(
            name="FacilityCode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("code", models.CharField(max_length=10, null=True, unique=True)),
                ("name", models.CharField(max_length=100)),
                ("sort_order", models.IntegerField(default=0)),
                ("deleted_at", models.DateTimeField(null=True)),
            ],
            options={
                "db_table": CODES,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("name",),
                        name="facility_codes_name_unique_alive",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="SiteFacility",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("detail_name", models.CharField(max_length=200)),
                ("deleted_at", models.DateTimeField(null=True)),
                (
                    "company",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company"),
                ),
                (
                    "facility_code",
                    models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.facilitycode"),
                ),
                ("site", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.site")),
            ],
            options={
                "db_table": FACILITIES,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        condition=models.Q(("deleted_at__isnull", True)),
                        fields=("site", "facility_code", "detail_name"),
                        name="site_facilities_unique_alive",
                    )
                ],
            },
        ),
        company_key("sites"),
        same_company_foreign_key(table=FACILITIES, column="site_id", target="sites"),
        company_key(FACILITIES),  # 가지 리뷰 L2: 뒤 밴드(S12a 입력 표)가 같은 회사 외래 키로 가리킬 자리
        grant(f'"{CODES}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{FACILITIES}"', "SELECT, INSERT, UPDATE"),
    ]
