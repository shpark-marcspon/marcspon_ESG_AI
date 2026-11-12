"""온실가스 인덱스 풀 + 시설별 배출계수 풀(공통). 밴드 K1b-2a ①(결정 MARC-ENT-463·469 3, 티켓 MARC-TICK-366).

표 넷 다 회사 칸이 없다(모든 고객사 공통 하나). 되돌리면 표 넷이 지워진다. 데이터 이전 0(씨앗은 명령 seed_ghg_pool).

  ghg_index_nodes      level CHECK · 뿌리 = 범위 CHECK · 잎만 코드·단위 CHECK · (parent, name) UNIQUE WHERE 삭제 안 됨·잎 아님 ·
                       뿌리 이름 UNIQUE WHERE 삭제 안 됨 · (parent, facility_code) UNIQUE WHERE 삭제 안 됨 · seed_key UNIQUE.
                       facility_code → organization_facility_codes PROTECT(공통 표라 같은 회사 짝 없음)
  ghg_factors          (facility_node) UNIQUE WHERE 기본·삭제 안 됨 · 기본은 삭제 안 됨 CHECK · current_version ≥ 1 · seed_key
  ghg_factor_versions  (factor, version) UNIQUE · Tier 1·2·3 · 기준연도 1990~2100 · 순발열량 켬 ↔ 값·단위 · 값 > 0
  ghg_factor_gases     (factor_version, gas) UNIQUE · 가스 일곱 · 켠 줄은 계수·GWP > 0
  GRANT                노드·계수 SELECT, INSERT, UPDATE(지우기는 삭제 표시) · 판·가스 SELECT, INSERT 만(고치지 않는다 —
                       고치기는 새 판. 회사 선택(K1b-2b)이 판을 잡는다)
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.grants import grant


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="GhgFactor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("is_default", models.BooleanField(default=False)),
                ("sort_order", models.IntegerField(default=0)),
                ("current_version", models.IntegerField(default=1)),
                ("seed_key", models.CharField(max_length=300, null=True)),
                ("deleted_at", models.DateTimeField(null=True)),
            ],
            options={
                "db_table": "ghg_factors",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="GhgFactorVersion",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("version", models.IntegerField()),
                ("name", models.CharField(max_length=100)),
                ("source", models.CharField(max_length=200)),
                ("base_year", models.SmallIntegerField()),
                ("tier", models.SmallIntegerField()),
                ("country_code", models.CharField(max_length=20)),
                ("industry_code", models.CharField(max_length=40)),
                ("input_unit_kind", models.CharField(max_length=20)),
                ("input_unit", models.CharField(max_length=20)),
                ("emission_unit_kind", models.CharField(default="mass", max_length=20)),
                ("emission_unit", models.CharField(default="tCO2-eq", max_length=20)),
                ("ncv_enabled", models.BooleanField(default=False)),
                ("ncv", models.DecimalField(decimal_places=12, max_digits=30, null=True)),
                ("ncv_unit_kind", models.CharField(max_length=20, null=True)),
                ("ncv_unit", models.CharField(max_length=20, null=True)),
                ("factor_unit", models.CharField(max_length=30)),
                ("note", models.CharField(blank=True, default="", max_length=1000)),
                ("seed_record_ids", models.JSONField(default=list)),
                ("seed_gwp_set_id", models.CharField(max_length=63, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "factor",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="versions", to="inventory.ghgfactor"
                    ),
                ),
            ],
            options={
                "db_table": "ghg_factor_versions",
            },
        ),
        migrations.CreateModel(
            name="GhgFactorGas",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("gas", models.CharField(max_length=10)),
                ("enabled", models.BooleanField(default=False)),
                ("factor", models.DecimalField(decimal_places=12, max_digits=30, null=True)),
                ("gwp", models.DecimalField(decimal_places=12, max_digits=30, null=True)),
                (
                    "factor_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="gases",
                        to="inventory.ghgfactorversion",
                    ),
                ),
            ],
            options={
                "db_table": "ghg_factor_gases",
            },
        ),
        migrations.CreateModel(
            name="GhgIndexNode",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("level", models.CharField(max_length=20)),
                ("name", models.CharField(blank=True, max_length=100)),
                ("sort_order", models.IntegerField(default=0)),
                ("unit_kind", models.CharField(max_length=20, null=True)),
                ("unit", models.CharField(max_length=20, null=True)),
                ("tooltip", models.CharField(blank=True, default="", max_length=1000)),
                ("seed_key", models.CharField(max_length=300, null=True)),
                ("deleted_at", models.DateTimeField(null=True)),
                (
                    "facility_code",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="+",
                        to="organization.facilitycode",
                    ),
                ),
                (
                    "parent",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="children",
                        to="inventory.ghgindexnode",
                    ),
                ),
            ],
            options={
                "db_table": "ghg_index_nodes",
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="ghgfactor",
            name="facility_node",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="factors", to="inventory.ghgindexnode"
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorversion",
            constraint=models.UniqueConstraint(fields=("factor", "version"), name="ghg_factor_versions_unique"),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("version__gte", 1)), name="ghg_factor_versions_version_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("tier__in", (1, 2, 3))), name="ghg_factor_versions_tier_check"
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("base_year__gte", 1990), ("base_year__lte", 2100)),
                name="ghg_factor_versions_base_year_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorversion",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("ncv__isnull", False),
                        ("ncv_enabled", True),
                        ("ncv_unit__isnull", False),
                        ("ncv_unit_kind__isnull", False),
                    ),
                    models.Q(
                        ("ncv__isnull", True),
                        ("ncv_enabled", False),
                        ("ncv_unit__isnull", True),
                        ("ncv_unit_kind__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="ghg_factor_versions_ncv_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorversion",
            constraint=models.CheckConstraint(
                condition=models.Q(("ncv__isnull", True), ("ncv__gt", 0), _connector="OR"),
                name="ghg_factor_versions_ncv_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorgas",
            constraint=models.UniqueConstraint(fields=("factor_version", "gas"), name="ghg_factor_gases_unique"),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorgas",
            constraint=models.CheckConstraint(
                condition=models.Q(("gas__in", ("CO2", "CH4", "N2O", "HFCs", "PFCs", "SF6", "NF3"))),
                name="ghg_factor_gases_gas_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactorgas",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("enabled", False),
                    models.Q(("factor__gt", 0), ("factor__isnull", False), ("gwp__gt", 0), ("gwp__isnull", False)),
                    _connector="OR",
                ),
                name="ghg_factor_gases_enabled_values",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.CheckConstraint(
                condition=models.Q(("level__in", ("scope", "source_type", "activity", "facility"))),
                name="ghg_nodes_level_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("level", "scope"), ("parent__isnull", True)),
                    models.Q(("level__in", ("source_type", "activity", "facility")), ("parent__isnull", False)),
                    _connector="OR",
                ),
                name="ghg_nodes_root_is_scope",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("facility_code__isnull", False),
                        ("level", "facility"),
                        ("unit__isnull", False),
                        ("unit_kind__isnull", False),
                    ),
                    models.Q(
                        models.Q(("level", "facility"), _negated=True),
                        ("facility_code__isnull", True),
                        ("unit__isnull", True),
                        ("unit_kind__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="ghg_nodes_leaf_fields",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), models.Q(("level", "facility"), _negated=True)),
                fields=("parent", "name"),
                name="ghg_nodes_name_unique_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), ("parent__isnull", True)),
                fields=("name",),
                name="ghg_nodes_root_name_unique_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("parent", "facility_code"),
                name="ghg_nodes_code_unique_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgindexnode",
            constraint=models.UniqueConstraint(
                condition=models.Q(("seed_key__isnull", False)), fields=("seed_key",), name="ghg_nodes_seed_key_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True), ("is_default", True)),
                fields=("facility_node",),
                name="ghg_factors_one_default_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactor",
            constraint=models.CheckConstraint(
                condition=models.Q(("deleted_at__isnull", False), ("is_default", True), _negated=True),
                name="ghg_factors_default_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactor",
            constraint=models.CheckConstraint(
                condition=models.Q(("current_version__gte", 1)), name="ghg_factors_version_positive"
            ),
        ),
        migrations.AddConstraint(
            model_name="ghgfactor",
            constraint=models.UniqueConstraint(
                condition=models.Q(("seed_key__isnull", False)),
                fields=("seed_key",),
                name="ghg_factors_seed_key_unique",
            ),
        ),
        grant('"ghg_index_nodes", "ghg_factors"', "SELECT, INSERT, UPDATE"),
        grant('"ghg_factor_versions", "ghg_factor_gases"', "SELECT, INSERT"),
    ]
