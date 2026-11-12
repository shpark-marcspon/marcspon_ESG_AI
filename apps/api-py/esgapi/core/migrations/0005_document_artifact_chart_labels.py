"""문서 산출물 core_document_artifacts 에 셋째 본문 칸 하나 — chart_labels jsonb NULL. 밴드 CHL1 ②(도표 라벨).

  chart_labels jsonb   판 2 산출물에서 파서가 낸 도표 라벨(services/parser chartLabels).
                       EPOCH 1 행·판 1·too_large 는 NULL.
                       데이터 옮김 0(옛 행은 NULL 그대로 — 판이 다르면 새 행이다, contract.py 의 EPOCH 규칙).
  제약 core_document_artifacts_body_check 갈음(지우고 다시): too_large 가지에 chart_labels IS NULL 을
                       더한다.
                       ready 가지는 그대로(ready 행의 chart_labels 는 NULL 일 수 있다).

core 의 다섯째 마이그레이션이다: 앞 마이그레이션을 다시 쓰지 않는다(MARC-ENT-284). GRANT 줄 0: 앱 역할의 권한은 0003 의 표
단위 SELECT, INSERT 라 새 칸도 넣고 읽기만 된다.
★ 되돌림(0005 → 0004)은 제약을 옛 꼴로 되돌리고 칸을 지운다 — EPOCH 2 행의 도표 라벨은 사라진다(다시 짓는 값).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0004_llm_call_log_segment"),
    ]

    operations = [
        migrations.RemoveConstraint(
            model_name="documentartifactrow",
            name="core_document_artifacts_body_check",
        ),
        migrations.AddField(
            model_name="documentartifactrow",
            name="chart_labels",
            field=models.JSONField(null=True),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("char_places__isnull", False), ("document__isnull", False), ("status", "ready")),
                    models.Q(
                        ("char_places__isnull", True),
                        ("chart_labels__isnull", True),
                        ("document__isnull", True),
                        ("status", "too_large"),
                    ),
                    _connector="OR",
                ),
                name="core_document_artifacts_body_check",
            ),
        ),
    ]
