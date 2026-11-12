"""영문번역의 첫 표 — 회사별 AI 설정 판(translation_ai_settings). 밴드 TR4 ② (결정 MARC-ENT-399·387).

숫자 id(BigAuto)와 회사 칸(company_id — organization 의 company 를 가리키는 외래 키, PROTECT, 글자 참조).
dependencies 는 organization 0001 하나다.

제약(translation/models.py 의 TranslationAiSettingRow):
  unique (company_id, name)                                   판 번호는 회사 안에서 하나(v1, v2, … — 서버가 매김)
  부분 unique (company_id) WHERE applied                        회사마다 적용 판은 많아야 하나
  CHECK name ~ '^v[1-9][0-9]{0,14}$'                          번호 꼴
  CHECK NOT applied OR applied_at IS NOT NULL                 적용 판은 적용한 때가 있다
  CHECK octet_length(prompts::text) <= 131072                 NULL 통과(core PROMPTS_MAX_OCTETS)
  CHECK octet_length(model_settings::text) <= 4096            어림(칸 셋 정규형 약 330 바이트)
  CHECK char_length(title) 1~40                               판 이름
  받기(core check_prompts·본문 꼴)가 먼저 막는다 — CHECK 는 마지막 그물(500 0). 값은 문면에 굳힌다.
GRANT   : 앱 역할(esg_app)에게 표 단위 SELECT, INSERT 와 **칸 단위 UPDATE (applied, applied_at)** 만. 이름·글·모델·메모
          칸은 앱이 고치지 못하고(판은 불변 행 — 저장 = 새 행), DELETE·TRUNCATE 는 주지 않는다(그린워싱 0002 와 같음).
          FOR UPDATE 잠금은 칸 하나의 UPDATE 권한으로 된다(PostgreSQL — 「적어도 한 칸의 UPDATE」).
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
★ 되돌림(0001 → zero)은 표를 지운다 — **저장한 AI 설정 판을 모두 잃는다**. 운영 DB 에서 하지 않는다.
"""

import django.db.models.deletion
import django.db.models.functions.comparison
import django.db.models.functions.text
import django.db.models.lookups
from django.db import migrations, models

from esgapi.core.isolation.grants import grant

TABLE = "translation_ai_settings"


def _octets_at_most(field: str, limit: int) -> models.Q:
    return models.Q(
        django.db.models.lookups.LessThanOrEqual(
            models.Func(
                django.db.models.functions.comparison.Cast(field, output_field=models.TextField()),
                function="octet_length",
                output_field=models.IntegerField(),
            ),
            limit,
        )
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organization", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="TranslationAiSettingRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=16)),
                ("title", models.CharField(max_length=40)),
                ("model_settings", models.JSONField()),
                ("prompts", models.JSONField(null=True)),
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
                    models.UniqueConstraint(
                        fields=("company", "name"), name="translation_ai_settings_company_name_uniq"
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("applied", True)),
                        fields=("company",),
                        name="translation_ai_settings_one_applied_uniq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("name__regex", "^v[1-9][0-9]{0,14}$")),
                        name="translation_ai_settings_name_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("applied", False), ("applied_at__isnull", False), _connector="OR"),
                        name="translation_ai_settings_applied_check",
                    ),
                    models.CheckConstraint(
                        condition=_octets_at_most("prompts", 131072),
                        name="translation_ai_settings_prompts_size_check",
                    ),
                    models.CheckConstraint(
                        condition=_octets_at_most("model_settings", 4096),
                        name="translation_ai_settings_model_settings_size_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.GreaterThanOrEqual(
                                django.db.models.functions.text.Length("title"), 1
                            ),
                            django.db.models.lookups.LessThanOrEqual(
                                django.db.models.functions.text.Length("title"), 40
                            ),
                        ),
                        name="translation_ai_settings_title_check",
                    ),
                ],
            },
        ),
        grant(f'"{TABLE}"', "SELECT, INSERT"),
        grant(f'"{TABLE}"', "UPDATE (applied, applied_at)"),
    ]
