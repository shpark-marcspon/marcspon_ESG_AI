"""고객사 인덱스 선택(회사 범위 표 둘). 밴드 K1b-2b ①(결정 MARC-ENT-469 3·4, 티켓 MARC-TICK-401).

inventory 의 첫 회사 칸 표다. 되돌리면 표 둘이 지워진다. 데이터 이전 0.

  inventory_years             (company, year) UNIQUE · decimals 0~3 CHECK · year 1990~2100 CHECK
  inventory_index_selections  (inventory_year, facility_node) UNIQUE WHERE 삭제 안 됨 · 숨김은 삭제 안 된 행만 CHECK.
                              facility_node → ghg_index_nodes · factor_version → ghg_factor_versions PROTECT
                              (공통 풀 표라 같은 회사 짝 없음 — 잡은 판은 풀에서 고쳐도 남는다)
  RunSQL                      inventory_years_company_id_uniq                       UNIQUE (company_id, id)
                              inventory_index_selections_inventory_year_id_same_company_fk
                                                                                    (company_id, inventory_year_id)
                                                                                    → inventory_years (company_id, id)
                              inventory_index_selections_company_id_uniq            UNIQUE (company_id, id) — S12a 입력
                                                                                    표의 짝이 가리킬 자리
                              (core/isolation/foreign_keys.py — NOT DEFERRABLE, 남의 회사 해를 가리키면 그 문에서 23503)
  GRANT                       둘 다 SELECT, INSERT, UPDATE(DELETE 없음 — 지우기는 삭제 표시)
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

YEARS = "inventory_years"
SELECTIONS = "inventory_index_selections"


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0001_ghg_pool"),
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="InventoryYear",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("year", models.SmallIntegerField()),
                ("decimals", models.SmallIntegerField(default=2)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
            ],
            options={
                "db_table": YEARS,
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="CompanyIndexSelection",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("hidden", models.BooleanField(default=False)),
                ("deleted_at", models.DateTimeField(null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
                (
                    "facility_node",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="inventory.ghgindexnode"
                    ),
                ),
                (
                    "factor_version",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="inventory.ghgfactorversion"
                    ),
                ),
                (
                    "inventory_year",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        related_name="selections",
                        to="inventory.inventoryyear",
                    ),
                ),
            ],
            options={
                "db_table": SELECTIONS,
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="inventoryyear",
            constraint=models.UniqueConstraint(fields=("company", "year"), name="inventory_years_company_year_unique"),
        ),
        migrations.AddConstraint(
            model_name="inventoryyear",
            constraint=models.CheckConstraint(
                condition=models.Q(("decimals__gte", 0), ("decimals__lte", 3)), name="inventory_years_decimals_range"
            ),
        ),
        migrations.AddConstraint(
            model_name="inventoryyear",
            constraint=models.CheckConstraint(
                condition=models.Q(("year__gte", 1990), ("year__lte", 2100)), name="inventory_years_year_range"
            ),
        ),
        migrations.AddConstraint(
            model_name="companyindexselection",
            constraint=models.UniqueConstraint(
                condition=models.Q(("deleted_at__isnull", True)),
                fields=("inventory_year", "facility_node"),
                name="inventory_selections_node_unique_alive",
            ),
        ),
        migrations.AddConstraint(
            model_name="companyindexselection",
            constraint=models.CheckConstraint(
                condition=models.Q(("deleted_at__isnull", False), ("hidden", True), _negated=True),
                name="inventory_selections_hidden_alive",
            ),
        ),
        company_key(YEARS),
        same_company_foreign_key(table=SELECTIONS, column="inventory_year_id", target=YEARS),
        company_key(SELECTIONS),
        grant(f'"{YEARS}", "{SELECTIONS}"', "SELECT, INSERT, UPDATE"),
    ]
