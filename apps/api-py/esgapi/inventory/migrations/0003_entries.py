"""Scope 1·2 입력(회사 범위 표 셋 + 선택 행 칸 셋). 밴드 S12a ①(결정 MARC-ENT-463·469, 티켓 MARC-TICK-406).

되돌리면 표 셋과 칸 셋이 지워진다. 데이터 이전 0.

  inventory_index_selections  + memo(빈 글자 기본) · locked_at · locked_by_user_id(외래 키 아님) · CHECK 잠금 짝
  inventory_entry_rows        (selection, site_facility) UNIQUE WHERE 삭제 안 됨 · selection → 선택 · site_facility →
                              site_facilities PROTECT
  inventory_entry_values      (row, slot) UNIQUE · amount ≥ 0 CHECK · slot `YYYY-MM` CHECK
  inventory_entry_history     kind CHECK(value·na_on·na_off) — 고치지 않는 표(updated_at 없음)
  RunSQL                      company_key 셋(입력 표마다 UNIQUE (company_id, id))
                              같은 회사 외래 키 넷(core/isolation/foreign_keys.py — NOT DEFERRABLE):
                                inventory_entry_rows (company_id, selection_id)     → inventory_index_selections
                                inventory_entry_rows (company_id, site_facility_id) → site_facilities
                                inventory_entry_values (company_id, row_id)         → inventory_entry_rows
                                inventory_entry_history (company_id, row_id)        → inventory_entry_rows
  GRANT                       행·값 SELECT, INSERT, UPDATE(지우기는 삭제 표시) · 히스토리 SELECT, INSERT 만
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

ROWS = "inventory_entry_rows"
VALUES = "inventory_entry_values"
HISTORY = "inventory_entry_history"


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0002_index_selections"),
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryEntryHistory",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("kind", models.CharField(max_length=10)),
                ("slot", models.CharField(max_length=7, null=True)),
                ("before", models.CharField(max_length=40, null=True)),
                ("after", models.CharField(max_length=40, null=True)),
                ("unit", models.CharField(max_length=20)),
                ("actor_kind", models.CharField(max_length=16)),
                ("actor_user_id", models.BigIntegerField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": HISTORY,
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="InventoryEntryRow",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("unit", models.CharField(max_length=20)),
                ("na", models.BooleanField(default=False)),
                ("emission", models.DecimalField(decimal_places=12, max_digits=30, null=True)),
                ("emission_problem", models.CharField(max_length=40, null=True)),
                ("deleted_at", models.DateTimeField(null=True)),
            ],
            options={
                "db_table": ROWS,
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="InventoryEntryValue",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("slot", models.CharField(max_length=7)),
                ("amount", models.DecimalField(decimal_places=6, max_digits=24, null=True)),
                ("estimated", models.BooleanField(default=False)),
            ],
            options={
                "db_table": VALUES,
                "abstract": False,
            },
        ),
        migrations.AddField(
            model_name="companyindexselection",
            name="locked_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="companyindexselection",
            name="locked_by_user_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="companyindexselection",
            name="memo",
            field=models.TextField(db_default=""),
        ),
        migrations.AddConstraint(
            model_name="companyindexselection",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("locked_at__isnull", True), ("locked_by_user_id__isnull", True)),
                    models.Q(("locked_at__isnull", False), ("locked_by_user_id__isnull", False)),
                    _connector="OR",
                ),
                name="inventory_selections_lock_pair",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryrow",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryrow",
            name="selection",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT,
                related_name="entry_rows",
                to="inventory.companyindexselection",
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryrow",
            name="site_facility",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.sitefacility"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryhistory",
            name="row",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="history", to="inventory.inventoryentryrow"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryvalue",
            name="company",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
            ),
        ),
        migrations.AddField(
            model_name="inventoryentryvalue",
            name="row",
            field=models.ForeignKey(
                on_delete=django.db.models.deletion.PROTECT, related_name="values", to="inventory.inventoryentryrow"
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryrow",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("selection", "site_facility"),
                name="inventory_entry_rows_unique_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryhistory",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("value", "na_on", "na_off"))),
                name="inventory_entry_history_kind_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryvalue",
            constraint=models.UniqueConstraint(fields=("row", "slot"), name="inventory_entry_values_unique"),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryvalue",
            constraint=models.CheckConstraint(
                condition=models.Q(("amount__isnull", True), ("amount__gte", 0), _connector="OR"),
                name="inventory_entry_values_amount_nonneg",
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryentryvalue",
            constraint=models.CheckConstraint(
                condition=models.Q(("slot__regex", "^[0-9]{4}-(0[1-9]|1[0-2])$")),
                name="inventory_entry_values_slot_format",
            ),
        ),
        company_key(ROWS),
        company_key(VALUES),
        company_key(HISTORY),
        same_company_foreign_key(table=ROWS, column="selection_id", target="inventory_index_selections"),
        same_company_foreign_key(table=ROWS, column="site_facility_id", target="site_facilities"),
        same_company_foreign_key(table=VALUES, column="row_id", target=ROWS),
        same_company_foreign_key(table=HISTORY, column="row_id", target=ROWS),
        grant(f'"{ROWS}", "{VALUES}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{HISTORY}"', "SELECT, INSERT"),
    ]
