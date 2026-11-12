"""Scope 3 줄 편집 사건 표(회사 범위 하나). 밴드 S3K2b-1 ①(결정 MARC-ENT-570, 티켓 MARC-TICK-487).

되돌리면 표가 지워진다 — **편집 전부를 잃는다**(AI 원본 run_results 는 그대로라 결과는 원안으로 돌아간다). 데이터 이전 0.

  inventory_scope3_row_edits  불변 사건: 행 = 편집 한 번 · category CHECK(C1~C15, C10 뺌) · kind CHECK(exclude·restore —
                              S3K2b-2 가 0007 로 넓힘) · row_id 길이 ≥ 1 CHECK · reason 걷은 길이 ≥ 1 CHECK(한도는
                              varchar 300) · batch_id NULL 허용 · 색인 셋
  run_id·actor_user_id        외래 키 아님(MARC-ENT-210 — runs 로 FK·마이그레이션 의존을 두지 않는다)
  RunSQL                      company_key(UNIQUE (company_id, id)) — 같은 회사 외래 키 0(회사 FK 하나뿐)
  GRANT                       SELECT, INSERT(고쳐 쓰기·지우기 0 — 복구도 새 사건)
"""

import django.db.models.deletion
import django.db.models.functions.text
import django.db.models.lookups
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key
from esgapi.core.isolation.grants import grant

EDITS = "inventory_scope3_row_edits"


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0005_scope3_categories"),
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.CreateModel(
            name="Scope3RowEdit",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("run_id", models.BigIntegerField()),
                ("category", models.CharField(max_length=3)),
                ("row_id", models.CharField(max_length=64)),
                ("kind", models.CharField(max_length=10)),
                ("reason", models.CharField(max_length=300)),
                ("actor_kind", models.CharField(max_length=16)),
                ("actor_user_id", models.BigIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("batch_id", models.UUIDField(null=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
            ],
            options={
                "db_table": "inventory_scope3_row_edits",
                "abstract": False,
                "indexes": [
                    models.Index(fields=["company", "run_id", "row_id", "id"], name="inv_s3_edits_run_row_idx"),
                    models.Index(fields=["company", "run_id", "category"], name="inv_s3_edits_run_cat_idx"),
                    models.Index(fields=["company", "run_id", "batch_id"], name="inv_s3_edits_run_batch_idx"),
                ],
                "constraints": [
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
                        name="inventory_scope3_row_edits_category_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("kind__in", ("exclude", "restore"))),
                        name="inventory_scope3_row_edits_kind_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.GreaterThanOrEqual(
                                django.db.models.functions.text.Length("row_id"), 1
                            )
                        ),
                        name="inventory_scope3_row_edits_row_id_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.GreaterThanOrEqual(
                                django.db.models.functions.text.Length(django.db.models.functions.text.Trim("reason")),
                                1,
                            )
                        ),
                        name="inventory_scope3_row_edits_reason_check",
                    ),
                ],
            },
        ),
        company_key(EDITS),
        grant(f'"{EDITS}"', "SELECT, INSERT"),
    ]
