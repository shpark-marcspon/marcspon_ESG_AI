"""실행 표 run_runs 에 launchKey 칸 하나와 부분 색인 하나 — 같이 시작한 실행의 묶음. 밴드 LK1(MARC-ISSUE-303 ①).

  launch_key            본문 launchKey(소문자 UUID, 36자). 사람 동작 한 번(같이 시작 누름)이 만든 실행 전부가 같은
                        값이다 — 유일이 아니다. NULL = 묶음 없이 만든 실행(지금까지의 행 전부)
  run_runs_launch_key   (company_id, launch_key) WHERE launch_key IS NOT NULL — 운영 관리자 실행 기록이 쪽에 실린
                        줄의 열쇠들로 묶음 전체를 한 번에 읽는 자리(runs/service/selectors/operator.py 의 _launches).
                        유일 아님. 옛 행(NULL)은 색인 밖

AddField 하나(NULL 칸이라 기존 행은 다시 쓰지 않는다)와 AddIndex 하나. runs 의 넷째 마이그레이션이다: 0001~0003 을 다시
쓰지 않는다(MARC-ENT-284 — 0002 머리말과 같은 까닭). GRANT 줄 0: 0001 이 run_runs 에 표 단위로
`SELECT, INSERT, UPDATE` 를 주었다(칸 단위가 아니다) — 새 칸에 저절로 닿는다.
★ 무효 조건 — 되돌림(0004 → 0003)은 칸과 색인을 지운다: 묶음 기록이 사라질 뿐 실행 행은 그대로다(되돌린 뒤 실행 기록의
  묶음 칸은 전부 null).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("runs", "0003_run_idempotency_key"),
    ]

    operations = [
        migrations.AddField(
            model_name="runrow",
            name="launch_key",
            field=models.CharField(max_length=36, null=True),
        ),
        migrations.AddIndex(
            model_name="runrow",
            index=models.Index(
                condition=models.Q(("launch_key__isnull", False)),
                fields=["company", "launch_key"],
                name="run_runs_launch_key",
            ),
        ),
    ]
