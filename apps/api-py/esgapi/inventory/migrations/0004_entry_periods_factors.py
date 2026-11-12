"""Scope 1·2 입력주기·직접입력 계수·히스토리 칸(회사 범위 표 둘 + 행 칸 둘 + 히스토리 칸 다섯). 밴드 S12a-2 ①
(결정 MARC-ENT-469·517, 티켓 MARC-TICK-421).

되돌리면 표 둘과 칸이 지워지고 CHECK 둘(slot·kind)은 0003 글자로 돌아간다. 데이터 이전 0 — 주기 행이 없는 블록은
month 다(옛 값 그대로).

  inventory_entry_periods    (selection, site) UNIQUE · period CHECK(month·quarter·year)
  inventory_custom_factors   판 표 꼴 CHECK 넷(tier·base_year·ncv 짝·ncv 양수) — 고치지 않는 표(updated_at 없음)
  inventory_entry_rows       + factor_version(풀 판)·custom_factor(직접입력) · CHECK 많아야 하나(one_factor)
  inventory_entry_history    + reason · before/after_version · before/after_custom · CHECK factor_refs ·
                             kind CHECK 넓힘(+unit·period·factor)
  inventory_entry_values     slot CHECK 넓힘(월 · 분기 `YYYY-Qn` · 연 `YYYY`)
  RunSQL                     company_key 둘(새 표마다 UNIQUE (company_id, id))
                             같은 회사 외래 키 다섯(core/isolation/foreign_keys.py — NOT DEFERRABLE):
                               inventory_entry_periods (company_id, selection_id)      → inventory_index_selections
                               inventory_entry_periods (company_id, site_id)           → sites
                               inventory_entry_rows (company_id, custom_factor_id)     → inventory_custom_factors
                               inventory_entry_history (company_id, before_custom_id)  → inventory_custom_factors
                               inventory_entry_history (company_id, after_custom_id)   → inventory_custom_factors
                             (풀 판을 가리키는 칸 셋은 공통 표라 짝이 없다. 직접입력 칸이 NULL 이면 MATCH SIMPLE 로 지난다)
  GRANT                      주기 SELECT, INSERT, UPDATE(지우기 없음) · 직접입력 SELECT, INSERT 만
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

PERIODS = "inventory_entry_periods"
CUSTOM = "inventory_custom_factors"
ROWS = "inventory_entry_rows"
HISTORY = "inventory_entry_history"


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0003_entries"),
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryCustomFactor",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("name", models.CharField(max_length=100)),
                ("source", models.CharField(max_length=200)),
                ("base_year", models.SmallIntegerField()),
                ("tier", models.SmallIntegerField()),
                ("country_code", models.CharField(max_length=20)),
                ("industry_code", models.CharField(max_length=40)),
                ("input_unit_kind", models.CharField(max_length=20)),
                ("input_unit", models.CharField(max_length=20)),
                ("ncv_enabled", models.BooleanField(default=False)),
                ("ncv", models.DecimalField(decimal_places=12, max_digits=30, null=True)),
                ("ncv_unit_kind", models.CharField(max_length=20, null=True)),
                ("ncv_unit", models.CharField(max_length=20, null=True)),
                ("factor_unit", models.CharField(max_length=30)),
                ("note", models.CharField(blank=True, default="", max_length=1000)),
                ("gases", models.JSONField(default=list)),
                ("actor_kind", models.CharField(max_length=16)),
                ("actor_user_id", models.BigIntegerField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": "inventory_custom_factors",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="InventoryEntryPeriod",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("period", models.CharField(max_length=8)),
            ],
            options={
                "db_table": "inventory_entry_periods",
                "abstract": False,
            },
        ),
        migrations.RemoveConstraint(
            model_name="inventoryentryhistory",
            name="inventory_entry_history_kind_check",
        ),
        migrations.RemoveConstraint(
            model_name="inventoryentryvalue",
            name="inventory_entry_values_slot_format",
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="after_version",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventory.ghgfactorversion",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="before_version",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventory.ghgfactorversion",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="reason",
            field=models.CharField(max_length=500, null=True),
        ),
        migrations.AddField(
            model_name="inventoryentryrow",
            name="factor_version",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventory.ghgfactorversion",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryvalue",
            constraint=models.CheckConstraint(
                condition=models.Q(("slot__regex", "^[0-9]{4}(-(0[1-9]|1[0-2]|Q[1-4]))?$")),
                name="inventory_entry_values_slot_format",
            ),
        ),
        migrations.AddField(
            model_name="inventorycustomfactor",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="after_custom",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventory.inventorycustomfactor",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="before_custom",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventory.inventorycustomfactor",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryrow",
            name="custom_factor",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="+",
                to="inventory.inventorycustomfactor",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryhistory",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("value", "na_on", "na_off", "unit", "period", "factor"))),
                name="inventory_entry_history_kind_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryhistory",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        models.Q(("kind", "factor"), _negated=True),
                        ("after_custom__isnull", True),
                        ("after_version__isnull", True),
                        ("before_custom__isnull", True),
                        ("before_version__isnull", True),
                    ),
                    models.Q(
                        ("kind", "factor"),
                        models.Q(
                            models.Q(("before_custom__isnull", True), ("before_version__isnull", False)),
                            models.Q(("before_custom__isnull", False), ("before_version__isnull", True)),
                            _connector="OR",
                        ),
                        models.Q(
                            models.Q(("after_custom__isnull", True), ("after_version__isnull", False)),
                            models.Q(("after_custom__isnull", False), ("after_version__isnull", True)),
                            _connector="OR",
                        ),
                    ),
                    _connector="OR",
                ),
                name="inventory_entry_history_factor_refs",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("factor_version__isnull", True), ("custom_factor__isnull", True), _connector="OR"),
                name="inventory_entry_rows_one_factor",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryperiod",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryperiod",
            name="selection",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="inventory.companyindexselection"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryperiod",
            name="site",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.site"
            ),
        ),
        migrations.AddConstraint(
            model_name="inventorycustomfactor",
            constraint=models.CheckConstraint(
                condition=models.Q(("tier__in", (1, 2, 3))), name="inventory_custom_factors_tier_check"
            ),
        ),
        migrations.AddConstraint(
            model_name="inventorycustomfactor",
            constraint=models.CheckConstraint(
                condition=models.Q(("base_year__gte", 1990), ("base_year__lte", 2100)),
                name="inventory_custom_factors_base_year_range",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventorycustomfactor",
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
                name="inventory_custom_factors_ncv_consistent",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventorycustomfactor",
            constraint=models.CheckConstraint(
                condition=models.Q(("ncv__isnull", True), ("ncv__gt", 0), _connector="OR"),
                name="inventory_custom_factors_ncv_positive",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryperiod",
            constraint=models.UniqueConstraint(fields=("selection", "site"), name="inventory_entry_periods_unique"),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryperiod",
            constraint=models.CheckConstraint(
                condition=models.Q(("period__in", ("month", "quarter", "year"))),
                name="inventory_entry_periods_period_check",
            ),
        ),
        company_key(PERIODS),
        company_key(CUSTOM),
        same_company_foreign_key(table=PERIODS, column="selection_id", target="inventory_index_selections"),
        same_company_foreign_key(table=PERIODS, column="site_id", target="sites"),
        same_company_foreign_key(table=ROWS, column="custom_factor_id", target=CUSTOM),
        same_company_foreign_key(table=HISTORY, column="before_custom_id", target=CUSTOM),
        same_company_foreign_key(table=HISTORY, column="after_custom_id", target=CUSTOM),
        grant(f'"{PERIODS}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{CUSTOM}"', "SELECT, INSERT"),
    ]
