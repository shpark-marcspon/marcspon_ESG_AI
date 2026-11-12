"""Scope 3 카테고리 잠금 표(회사 범위 하나). 밴드 S3K2a ①(결정 MARC-ENT-559·469 2, 티켓 MARC-TICK-472).

되돌리면 표가 지워진다. 데이터 이전 0.

  inventory_scope3_categories  (company, year, category) UNIQUE · year CHECK(1990~2100) · category CHECK(C1~C15, C10 뺌)
                               · 잠금 셋(locked_at·locked_by_user_id·pinned_run_id) 다 있거나 다 없음 CHECK
  RunSQL                       company_key(UNIQUE (company_id, id)) — 같은 회사 외래 키 0(회사 FK 하나뿐, runs·inventory_years FK 0)
  GRANT                        SELECT, INSERT, UPDATE(지우기 없음 — 풀기는 칸을 비운다)
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key
from esgapi.core.isolation.grants import grant

STATES = "inventory_scope3_categories"


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0004_entry_periods_factors"),
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="Scope3CategoryState",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("year", models.SmallIntegerField()),
                ("category", models.CharField(max_length=3)),
                ("locked_at", models.DateTimeField(null=True)),
                ("locked_by_user_id", models.BigIntegerField(null=True)),
                ("pinned_run_id", models.BigIntegerField(null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
            ],
            options={
                "db_table": "inventory_scope3_categories",
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "year", "category"), name="inventory_scope3_categories_unique"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("year__gte", 1990), ("year__lte", 2100)),
                        name="inventory_scope3_categories_year_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "category__in",
                                (
                                    "C1",
                                    "C2",
                                    "C3",
                                    "C4",
                                    "C5",
                                    "C6",
                                    "C7",
                                    "C8",
                                    "C9",
                                    "C11",
                                    "C12",
                                    "C13",
                                    "C14",
                                    "C15",
                                ),
                            )
                        ),
                        name="inventory_scope3_categories_category_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("locked_at__isnull", True),
                                ("locked_by_user_id__isnull", True),
                                ("pinned_run_id__isnull", True),
                            ),
                            models.Q(
                                ("locked_at__isnull", False),
                                ("locked_by_user_id__isnull", False),
                                ("pinned_run_id__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        name="inventory_scope3_categories_lock_triple",
                    ),
                ],
            },
        ),
        company_key(STATES),
        grant(f'"{STATES}"', "SELECT, INSERT, UPDATE"),
    ]
