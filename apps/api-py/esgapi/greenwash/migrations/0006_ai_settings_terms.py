"""AI 설정 판에 대상 단어 칸 하나와 크기 CHECK 하나 — 밴드 G2d ② (결정 MARC-ENT-394, 이슈 MARC-ISSUE-246).

  terms jsonb NULL     판의 대상 단어 {text, enabled} 목록(flows/terms_e0.accept_terms 를 거친 정규형 — 받은 차례,
                       text strip). NULL = 코드 기본 목록(옛 행·terms 없는 저장 — 지금 길). 의심 낱말 빈도 목록만 바꾼다
  CHECK greenwash_ai_settings_terms_size_check   octet_length(terms::text) <= 16384(NULL 통과)
  받기(100개·글 30자·제어 글자 0 — 최악 약 15,200 바이트, 발주서 K6)가 먼저 막는다 — CHECK 는 마지막 그물(500 0).
  값은 문면에 굳힌다(코드 import 0).

이행: AddField 하나 + AddConstraint 하나, RunPython 0. GRANT 줄 0: 앱 역할은 표 단위 SELECT·INSERT(새 칸도 든다)와 칸
단위 UPDATE (applied, applied_at) 뿐이라 새 칸도 UPDATE 권한 밖이다(판은 불변 행, 마이그레이션 0002). 이행은 주인 역할이
돈다.
★ 되돌림(0006 → 0005)은 칸과 제약을 지우고 행은 남긴다 — **판 단어를 잃는다**. 운영 DB 에서 하지 않는다.
"""

from django.db import migrations, models
from django.db.models.functions import Cast
from django.db.models.lookups import LessThanOrEqual


class Migration(migrations.Migration):
    dependencies = [
        ("greenwash", "0005_ai_settings_prompts"),
    ]

    operations = [
        migrations.AddField(
            model_name="greenwashaisettingrow",
            name="terms",
            field=models.JSONField(null=True),
        ),
        migrations.AddConstraint(
            model_name="greenwashaisettingrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    LessThanOrEqual(
                        models.Func(
                            Cast("terms", output_field=models.TextField()),
                            function="octet_length",
                            output_field=models.IntegerField(),
                        ),
                        16384,
                    )
                ),
                name="greenwash_ai_settings_terms_size_check",
            ),
        ),
    ]
