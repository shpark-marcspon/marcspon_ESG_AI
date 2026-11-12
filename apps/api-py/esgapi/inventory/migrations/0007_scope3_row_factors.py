"""Scope 3 줄 계수 수정 — 사건 표 넓힘. 밴드 S3K2b-2 ①(결정 MARC-ENT-570·442, 티켓 MARC-TICK-502). 새 표 0.

되돌림은 0006 까지 함께 간다 — **편집 전부를 잃는다**(kind factor 행이 있으면 kind CHECK 가 되돌림을 막는다).

  kind CHECK     exclude·restore·factor(지우고 다시 — 이름 그대로)
  새 칸          전부 NULL 허용. 고른 계수(choice·rank·title·value·source·unit) · 그때 센 배출량(co2e·biogenic_co2e) ·
                 사건 때 AI 원안(ai_factor_title·value·source·ai_co2e). 수는 repr(float) 글자
  모양 CHECK     kind factor ⇔ 갈래 있음 · recommended ⇔ 순위 있음 · custom ⇒ 제목·값·출처 있음 · 다른 kind 면 새 칸 전부 null
  GRANT·색인     그대로(SELECT, INSERT — 고쳐 쓰기·지우기 0)
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("inventory", "0006_scope3_row_edits"),
        ("organization", "0003_headquarters_seed"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="scope3rowedit",
            name="inventory_scope3_row_edits_kind_check",
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="ai_co2e",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="ai_factor_source",
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="ai_factor_title",
            field=models.CharField(max_length=300, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="ai_factor_value",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="biogenic_co2e",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="co2e",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="factor_choice",
            field=models.CharField(max_length=11, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="factor_rank",
            field=models.SmallIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="factor_source",
            field=models.CharField(max_length=200, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="factor_title",
            field=models.CharField(max_length=300, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="factor_unit",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddField(
            model_name="scope3rowedit",
            name="factor_value",
            field=models.CharField(max_length=32, null=True),
        ),
        migrations.AddConstraint(
            model_name="scope3rowedit",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("exclude", "restore", "factor"))),
                name="inventory_scope3_row_edits_kind_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="scope3rowedit",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("factor_choice__in", ("applied", "recommended", "custom")),
                    ("factor_choice__isnull", True),
                    _connector="OR",
                ),
                name="inventory_scope3_row_edits_factor_choice_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="scope3rowedit",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("factor_rank__gte", 1), ("factor_rank__lte", 4)),
                    ("factor_rank__isnull", True),
                    _connector="OR",
                ),
                name="inventory_scope3_row_edits_factor_rank_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="scope3rowedit",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        models.Q(
                            models.Q(("factor_choice", "recommended"), ("factor_rank__isnull", False)),
                            models.Q(("factor_choice", "applied"), ("factor_rank__isnull", True)),
                            models.Q(
                                ("factor_choice", "custom"),
                                ("factor_rank__isnull", True),
                                ("factor_source__isnull", False),
                                ("factor_title__isnull", False),
                                ("factor_value__isnull", False),
                            ),
                            _connector="OR",
                        ),
                        ("factor_choice__isnull", False),
                        ("kind", "factor"),
                    ),
                    models.Q(
                        models.Q(("kind", "factor"), _negated=True),
                        ("ai_co2e__isnull", True),
                        ("ai_factor_source__isnull", True),
                        ("ai_factor_title__isnull", True),
                        ("ai_factor_value__isnull", True),
                        ("biogenic_co2e__isnull", True),
                        ("co2e__isnull", True),
                        ("factor_choice__isnull", True),
                        ("factor_rank__isnull", True),
                        ("factor_source__isnull", True),
                        ("factor_title__isnull", True),
                        ("factor_unit__isnull", True),
                        ("factor_value__isnull", True),
                    ),
                    _connector="OR",
                ),
                name="inventory_scope3_row_edits_factor_shape",
            ),
        ),
    ]
