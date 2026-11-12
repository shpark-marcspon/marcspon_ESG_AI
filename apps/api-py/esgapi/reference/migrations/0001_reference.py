"""기준정보의 표 넷(reference_sources · reference_factor_records · reference_factor_scope3_categories · reference_mappings).

★ **이 표들에는 테넌트 칸(tenant_id)이 없고 RLS 를 걸지 않는다.** 기준정보는 모든 고객사가 같이 읽는 전역 자료다.
  보안 층의 카탈로그 검사(tests/security/test_owner.py)는 `tenants` 와 `tenant_id` 칸이 있는 표만 본다. 그래서
  이 표들은 그 검사(ENABLE·FORCE·POLICY·GRANT 넷)를 건너뛰고, 「정책은 테넌트의 표에만 있다」는 검사와도 맞는다.
  이 표들의 권한은 tests/security/test_reference.py 가 따로 잰다.
★ 앱 역할(esg_app)에는 **SELECT 만** 준다. INSERT·UPDATE·DELETE·TRUNCATE 가 없다 → 요청을 처리하는 프로세스가
  계수를 고칠 길이 DB 에 없다. 쓰기는 주인 역할의 관리 명령(`manage.py import_factors`)만 한다.
  번호열(reference_factor_scope3_categories 의 id)의 권한도 주지 않는다: 읽기에는 필요 없다.
  스키마의 USAGE 는 organization/0001_initial 이 이미 줬다(그래서 그것에 기댄다).
무효 조건: superuser 인 역할에게는 GRANT 가 뜻이 없다(전부 된다). 로컬 compose 의 주인 역할이 그렇다.
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.grants import grant

TABLES = '"reference_sources", "reference_factor_records", "reference_factor_scope3_categories", "reference_mappings"'


class Migration(migrations.Migration):
    initial = True

    dependencies = [("organization", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="MappingRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("guideline_version", models.CharField(max_length=200, primary_key=True, serialize=False)),
                ("body", models.JSONField()),
            ],
            options={
                "db_table": "reference_mappings",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="SourceRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.CharField(max_length=63, primary_key=True, serialize=False)),
                ("name", models.TextField()),
                ("publisher", models.TextField()),
                ("url", models.TextField()),
                ("version", models.TextField()),
                ("retrieved", models.CharField(max_length=10)),
                ("file_name", models.TextField()),
                ("file_sha256", models.CharField(max_length=64)),
                ("license_name", models.TextField()),
                ("license_url", models.TextField()),
                ("license_note", models.TextField(null=True)),
                ("license_status", models.CharField(max_length=20)),
            ],
            options={
                "db_table": "reference_sources",
                "abstract": False,
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("license_status__in", ("ok", "disputed", "unverified"))),
                        name="reference_sources_license_status_check",
                    )
                ],
            },
        ),
        migrations.CreateModel(
            name="FactorRecordRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.CharField(max_length=200, primary_key=True, serialize=False)),
                ("locator", models.TextField()),
                ("schema_version", models.CharField(max_length=10)),
                ("record_type", models.CharField(max_length=30)),
                ("scope", models.CharField(max_length=30)),
                ("scope3_mapping_basis", models.TextField(null=True)),
                ("factor_type", models.CharField(max_length=20)),
                ("name_original", models.TextField()),
                ("name_ko", models.TextField(null=True)),
                ("name_en", models.TextField(null=True)),
                ("category_path", models.JSONField()),
                ("classification", models.JSONField(null=True)),
                ("value", models.FloatField(null=True)),
                ("value_raw", models.TextField(null=True)),
                ("value_status", models.CharField(max_length=40)),
                ("unit", models.TextField()),
                ("unit_numerator", models.TextField()),
                ("unit_denominator", models.TextField()),
                ("gas", models.CharField(max_length=10)),
                ("gas_basis", models.CharField(max_length=20)),
                ("heating_value_basis", models.CharField(max_length=10, null=True)),
                ("conditions", models.JSONField()),
                ("region", models.CharField(max_length=20)),
                ("year", models.IntegerField(null=True)),
                ("spend", models.JSONField(null=True)),
                ("adjusted", models.JSONField(null=True)),
                ("synthetic", models.BooleanField()),
                ("extra", models.JSONField()),
                (
                    "source",
                    models.ForeignKey(
                        db_column="source_id",
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="records",
                        to="reference.sourcerow",
                    ),
                ),
            ],
            options={
                "db_table": "reference_factor_records",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="FactorScope3CategoryRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("category", models.PositiveSmallIntegerField()),
                (
                    "record",
                    models.ForeignKey(
                        db_column="record_id",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="scope3_categories",
                        to="reference.factorrecordrow",
                    ),
                ),
            ],
            options={
                "db_table": "reference_factor_scope3_categories",
                "constraints": [
                    models.UniqueConstraint(
                        fields=("record", "category"), name="reference_scope3_record_category_uniq"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("category__gte", 1), ("category__lte", 15)),
                        name="reference_scope3_category_range_check",
                    ),
                ],
            },
        ),
        migrations.AddIndex(
            model_name="factorrecordrow",
            index=models.Index(fields=["source", "record_type"], name="reference_factor_src_type_idx"),
        ),
        grant(TABLES, "SELECT"),
    ]
