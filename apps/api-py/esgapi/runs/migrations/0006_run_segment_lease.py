"""구획 임대·주차 칸(밴드 RM1b ②, MARC-TICK-567 — 펼침 구획을 쪽지 여럿이 나눠 돈다).

  run_runs.parked_at              timestamptz NULL  지휘 시도가 구획을 맡기고 주차한 시각(NULL = 주차 아님)
  run_segments.lease_expires_at   timestamptz NULL  구획 쪽지가 그 구획을 쥔 기한(running 만)
  run_segments.data_octets        int NULL          done 구획 data 의 바이트(병렬 끝냄이 적는다 — 단계 합 검사)
  CHECK  run_segments_lease_running_check     lease_expires_at IS NULL OR status = 'running'(한 방향)
         run_segments_data_octets_check       data_octets IS NULL OR (status = 'done' AND data_octets >= 0)(한 방향 —
                                              RM1a 직렬의 done 행은 NULL 그대로 지난다)

NULL 칸을 더하고 CHECK 둘만 건다. GRANT 0(0001·0005 의 표 권한이 새 칸에도 선다). 0001~0005 를 다시 쓰지 않는다
(MARC-ENT-284). 장벽 흐름·직렬 펼침의 행은 새 칸이 늘 NULL 이다.
★ 되돌림(0006 → 0005)은 칸 셋과 CHECK 둘을 지운다 — 제품 흐름이 펼침 단계를 쓰지 않는 동안 운영 행에 값 0.
  무효 조건: 펼침 단계를 쓰는 흐름이 제품에 등록된 뒤에는 되돌리지 말고 새 마이그레이션을 낸다.
색인 0: 구획 잡기·끝냄의 조회는 (run, step, position)·(run, step, key_sha256) 유일 색인의 앞머리로 선다(보고의 쿼리 계획).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("runs", "0005_run_segments")]

    operations = [
        migrations.AddField(model_name="runrow", name="parked_at", field=models.DateTimeField(null=True)),
        migrations.AddField(model_name="runsegmentrow", name="lease_expires_at", field=models.DateTimeField(null=True)),
        migrations.AddField(model_name="runsegmentrow", name="data_octets", field=models.IntegerField(null=True)),
        migrations.AddConstraint(
            model_name="runsegmentrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("lease_expires_at__isnull", True), ("status", "running"), _connector="OR"),
                name="run_segments_lease_running_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="runsegmentrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("data_octets__isnull", True),
                    models.Q(("data_octets__gte", 0), ("status", "done")),
                    _connector="OR",
                ),
                name="run_segments_data_octets_check",
            ),
        ),
    ]
