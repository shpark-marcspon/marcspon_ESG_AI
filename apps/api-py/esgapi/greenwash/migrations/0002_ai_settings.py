"""그린워싱의 표 하나 더 — 회사별 AI 설정 판(greenwash_ai_settings). 밴드 G2c2 ① (결정 MARC-ENT-341·244·312).

숫자 id(BigAuto)와 회사 칸(company_id — organization 의 company 를 가리키는 외래 키, PROTECT, 글자 참조).
dependencies 는 greenwash 0001 하나다(0001 이 organization 0001 을 딛는다).

제약(greenwash/models.py 의 GreenwashAiSettingRow):
  unique (company_id, name)                       판 이름은 회사 안에서 하나(v1, v2, … — 서버가 매김)
  부분 unique (company_id) WHERE applied            회사마다 적용 판은 많아야 하나
  CHECK name ~ '^v[1-9][0-9]{0,14}$'              이름 꼴
  CHECK NOT applied OR applied_at IS NOT NULL     적용 판은 적용한 때가 있다
  CHECK sha 는 소문자 16진 64자
  CHECK octet_length(criteria::text) <= 32768     어림(받기 최대 약 29,160 바이트 — MARC-ISSUE-208 의 5)
GRANT   : 앱 역할(esg_app)에게 표 단위 SELECT, INSERT 와 **칸 단위 UPDATE (applied, applied_at)** 만. 기준표·이름·메모·
          sha 칸은 앱이 고치지 못하고(판은 불변 행 — 저장 = 새 행), DELETE·TRUNCATE 는 주지 않는다(발주서 G2c2 Q4).
          FOR UPDATE 잠금은 칸 하나의 UPDATE 권한으로 된다(PostgreSQL — 「적어도 한 칸의 UPDATE」).
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
"""

import django.db.models.deletion
import django.db.models.functions.comparison
import django.db.models.lookups
from django.db import migrations, models

from esgapi.core.isolation.grants import grant

TABLE = "greenwash_ai_settings"


class Migration(migrations.Migration):
    dependencies = [
        ("greenwash", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="GreenwashAiSettingRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=16)),
                ("criteria", models.JSONField()),
                ("eval_prompt_sha256", models.CharField(max_length=64)),
                ("memo", models.CharField(default="", max_length=200)),
                ("created_by_user_id", models.BigIntegerField()),
                ("applied", models.BooleanField(default=False)),
                ("applied_at", models.DateTimeField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
            ],
            options={
                "db_table": TABLE,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(fields=("company", "name"), name="greenwash_ai_settings_company_name_uniq"),
                    models.UniqueConstraint(
                        condition=models.Q(("applied", True)),
                        fields=("company",),
                        name="greenwash_ai_settings_one_applied_uniq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("name__regex", "^v[1-9][0-9]{0,14}$")),
                        name="greenwash_ai_settings_name_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("applied", False), ("applied_at__isnull", False), _connector="OR"),
                        name="greenwash_ai_settings_applied_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("eval_prompt_sha256__regex", "^[0-9a-f]{64}$")),
                        name="greenwash_ai_settings_sha_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.LessThanOrEqual(
                                models.Func(
                                    django.db.models.functions.comparison.Cast(
                                        "criteria", output_field=models.TextField()
                                    ),
                                    function="octet_length",
                                    output_field=models.IntegerField(),
                                ),
                                32768,
                            )
                        ),
                        name="greenwash_ai_settings_criteria_size_check",
                    ),
                ],
            },
        ),
        grant(f'"{TABLE}"', "SELECT, INSERT"),
        grant(f'"{TABLE}"', "UPDATE (applied, applied_at)"),
    ]
