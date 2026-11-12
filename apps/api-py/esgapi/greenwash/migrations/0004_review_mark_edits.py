"""표시 표 greenwash_review_marks 에 검토 고침 칸 아홉 — 등급·판정 사유·수정 방향 × (값·때·사람). 밴드 G1b-3 ①
(결정 MARC-ENT-354 6, 이슈 MARC-ISSUE-245, 꼴 greenwash.review@2 — contracts/review_shapes.py).

  edited_level varchar(8)            level_edited_at timestamptz     level_edited_by_user_id bigint
  edited_reason_bullets jsonb        reasons_edited_at timestamptz   reasons_edited_by_user_id bigint
  edited_fix_paragraph varchar(2000) fix_edited_at timestamptz       fix_edited_by_user_id bigint
  다 NULL 허용. 사람 id 는 외래 키가 아니다(confirmed_by_user_id 와 같은 뜻).
  CHECK greenwash_review_marks_{level,reasons,fix}_edit_check   칸마다 값·때·사람이 다 NULL 이거나 다 값
        greenwash_review_marks_edit_level_check                NULL 또는 High·Mid·Low(models.EDIT_LEVELS)
  값은 문면에 굳힌다(코드 import 0) — 등급이 늘면 새 마이그레이션.

이행: AddField 아홉 + AddConstraint 넷, RunPython 0. 옛 행(@1 때의 표시)은 고침 칸이 NULL = 고침 없음 — 검토 GET 은
edits [] 로 읽는다. GRANT 줄 0: 앱 역할의 권한은 0001 의 표 단위 SELECT, INSERT, UPDATE 라 새 칸도 든다(DELETE 없음 그대로).
★ 되돌림(0004 → 0003)은 칸과 제약을 지우고 행은 남긴다 — **고친 값은 잃는다**(표시·사유는 그대로).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("greenwash", "0003_ai_settings_model_settings"),
    ]

    operations = [
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="edited_fix_paragraph",
            field=models.CharField(max_length=2000, null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="edited_level",
            field=models.CharField(max_length=8, null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="edited_reason_bullets",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="fix_edited_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="fix_edited_by_user_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="level_edited_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="level_edited_by_user_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="reasons_edited_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="reasons_edited_by_user_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("edited_level__isnull", True),
                        ("level_edited_at__isnull", True),
                        ("level_edited_by_user_id__isnull", True),
                    ),
                    models.Q(
                        ("edited_level__isnull", False),
                        ("level_edited_at__isnull", False),
                        ("level_edited_by_user_id__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="greenwash_review_marks_level_edit_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("edited_reason_bullets__isnull", True),
                        ("reasons_edited_at__isnull", True),
                        ("reasons_edited_by_user_id__isnull", True),
                    ),
                    models.Q(
                        ("edited_reason_bullets__isnull", False),
                        ("reasons_edited_at__isnull", False),
                        ("reasons_edited_by_user_id__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="greenwash_review_marks_reasons_edit_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("edited_fix_paragraph__isnull", True),
                        ("fix_edited_at__isnull", True),
                        ("fix_edited_by_user_id__isnull", True),
                    ),
                    models.Q(
                        ("edited_fix_paragraph__isnull", False),
                        ("fix_edited_at__isnull", False),
                        ("fix_edited_by_user_id__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="greenwash_review_marks_fix_edit_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("edited_level__isnull", True),
                    models.Q(("edited_level__in", ("High", "Mid", "Low")), ("edited_level__isnull", False)),
                    _connector="OR",
                ),
                name="greenwash_review_marks_edit_level_check",
            ),
        ),
    ]
