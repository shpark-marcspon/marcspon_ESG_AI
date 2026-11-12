"""LLM 호출 기록 core_llm_call_logs 에 단계 칸 하나 — step varchar(100) NULL. 밴드 AD4D ①(MARC-ENT-385 — 단계별 토큰·비용).

  step varchar(100)   실행기가 지은 클라이언트의 호출이면 그 호출이 일어난 단계 이름(runs 의 run_steps.name 과 같은 상한).
                      실행 밖·단계 사이 호출과 이 마이그레이션 앞의 줄은 NULL(메우지 않는다 — 지난 실행은 합계만).
  색인 0(실행 하나의 단계별 합은 core_llm_logs_company_run 으로 좁힌다).

core 의 둘째 마이그레이션이다: 0001 을 다시 쓰지 않는다(MARC-ENT-284 「공유 DB 가 서기 전까지」 — esg-app 이 마크스폰에
나가 있어 받는 쪽 DB 가 있을 수 있다, MARC-ENT-275). GRANT 줄 0: 앱 역할의 권한은 0001 의 표 단위 SELECT, INSERT 라 새
칸도 넣고 읽기만 된다(UPDATE 없음 그대로 — 칸 단위 GRANT 0).
★ 되돌림(0002 → 0001)은 칸을 지우고 행은 남긴다 — **단계 이름은 잃는다**(합계는 그대로).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmcalllogrow",
            name="step",
            field=models.CharField(max_length=100, null=True),
        ),
    ]
