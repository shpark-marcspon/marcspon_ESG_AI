"""LLM 호출 기록 core_llm_call_logs 에 구획 칸 하나 — segment varchar(64) NULL. 밴드 RM1a ②(MARC-ENT-618 — 구획별 비용).

  segment varchar(64)   펼침 단계의 구획 안 호출이면 그 구획 열쇠의 sha256(runs 의 run_segments.key_sha256 과 같은 값).
                        장벽 단계·구획 밖 호출과 이 마이그레이션 앞의 줄은 NULL(메우지 않는다).
  기본값·색인 0(실행 하나의 구획별 합은 core_llm_logs_company_run 으로 좁힌다 — 0002 의 step 과 같은 꼴).

core 의 넷째 마이그레이션이다: 앞 마이그레이션을 다시 쓰지 않는다(MARC-ENT-284 — esg-app 이 마크스폰에 나가 있다,
MARC-ENT-275). GRANT 줄 0: 앱 역할의 권한은 0001 의 표 단위 SELECT, INSERT 라 새 칸도 넣고 읽기만 된다.
★ 되돌림(0004 → 0003)은 칸을 지우고 행은 남긴다 — **구획 귀속은 잃는다**(합계·단계별 합은 그대로).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0003_document_artifacts"),
    ]

    operations = [
        migrations.AddField(
            model_name="llmcalllogrow",
            name="segment",
            field=models.CharField(max_length=64, null=True),
        ),
    ]
