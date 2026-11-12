"""AI 설정 판에 프롬프트 글·판 이름 칸 둘과 크기·이름 CHECK 셋 — 밴드 AS3a-2 ② (결정 MARC-ENT-381·384·387, 이슈
MARC-ISSUE-257).

  prompts jsonb NULL          판의 프롬프트 글 정규형(ai.prompts@1 — core/calc/ai_settings.prompts_input(check_prompts(…)),
                              글 바이트 그대로·칸 메모 strip). NULL = 코드 글(옛 행·prompts 없는 저장 — 지금 길)
  title varchar(40) NULL      판 이름(본문 title, strip 뒤 1~40자). 옛 행은 NULL — 채우지 않는다(MARC-ENT-387 노트:
                              1차 출시 전이라 개발 DB 뿐, 새 저장은 이름 필수)
  CHECK greenwash_ai_settings_prompts_size_check          octet_length(prompts::text) <= 131072(NULL 통과)
        greenwash_ai_settings_model_settings_size_check   octet_length(model_settings::text) <= 4096(257 4번)
        greenwash_ai_settings_title_check                 NULL 또는 char_length(title) 1~40
  받기(core check_prompts 의 ai_prompt_total_size·본문 꼴)가 먼저 막는다 — CHECK 는 마지막 그물(500 0, 발주서 M3).
  값은 문면에 굳힌다(코드 import 0).

이행: AddField 둘 + AddConstraint 셋, RunPython 0. GRANT 줄 0: 앱 역할은 표 단위 SELECT·INSERT(새 칸도 든다)와 칸 단위
UPDATE (applied, applied_at) 뿐이라 새 칸 둘도 UPDATE 권한 밖이다(판은 불변 행, 마이그레이션 0002). 이행은 주인 역할이 돈다.
★ 되돌림(0005 → 0004)은 칸과 제약을 지우고 행은 남긴다 — **저장 글·칸 메모·판 이름을 잃는다**. 운영 DB 에서 하지 않는다.
"""

from django.db import migrations, models
from django.db.models.functions import Cast, Length
from django.db.models.lookups import GreaterThanOrEqual, LessThanOrEqual


def _octets_at_most(field: str, limit: int) -> models.Q:
    return models.Q(
        LessThanOrEqual(
            models.Func(
                Cast(field, output_field=models.TextField()),
                function="octet_length",
                output_field=models.IntegerField(),
            ),
            limit,
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("greenwash", "0004_review_mark_edits"),
    ]

    operations = [
        migrations.AddField(
            model_name="greenwashaisettingrow",
            name="prompts",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashaisettingrow",
            name="title",
            field=models.CharField(max_length=40, null=True),
        ),
        migrations.AddConstraint(
            model_name="greenwashaisettingrow",
            constraint=models.CheckConstraint(
                condition=_octets_at_most("prompts", 131072), name="greenwash_ai_settings_prompts_size_check"
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashaisettingrow",
            constraint=models.CheckConstraint(
                condition=_octets_at_most("model_settings", 4096),
                name="greenwash_ai_settings_model_settings_size_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashaisettingrow",
            constraint=models.CheckConstraint(
                condition=models.Q(title__isnull=True)
                | models.Q(GreaterThanOrEqual(Length("title"), 1), LessThanOrEqual(Length("title"), 40)),
                name="greenwash_ai_settings_title_check",
            ),
        ),
    ]
