"""실행의 구획 기록 표 run_segments 하나 — 펼침 단계의 구획마다 한 줄(밴드 RM1a ②, MARC-ENT-618).

  칸      company·run(같은 회사 외래 키) · step · position · kind varchar(32) · key jsonb · key_sha256 · status ·
          attempts · data(done 만) · error_code(failed 만) · started_at·finished_at (뜻은 runs/models.py 의 RunSegmentRow)
  CHECK   status 넷(pending·running·done·failed) · position ≥ 0 · attempts ≥ 0 · key_sha256 꼴(16진 64자) ·
          상태와 칸의 짝(run_segments_status_fields_check) · data 크기(run_segments_data_size_check — 1MiB, 어림.
          runs/models.py 의 RUN_SEGMENT_DATA_MAX_OCTETS 와 같다 — 테스트가 견준다. core 의 앱 상한은 그 절반)
  유일    (run, step, key_sha256) · (run, step, position)
  색인    (company, run)
  same_company_foreign_key(run_segments.run_id → run_runs)   받침 ⑤ — 구획이 남의 회사 실행에 걸리지 못한다(23503)
  GRANT   앱 역할(esg_app)에게 SELECT, INSERT, UPDATE. DELETE·TRUNCATE 없음(실행 표는 지우지 않는다 — MARC-ENT-208)

runs 의 다섯째 마이그레이션이다: 0001~0004 를 다시 쓰지 않는다(MARC-ENT-284 — esg-app 이 마크스폰에 나가 있다,
MARC-ENT-275). 다른 앱은 이 표에 기대지 않는다(MARC-ENT-210 (1)).
★ 되돌림(0005 → 0004)은 표를 지운다 — **구획 기록을 잃는다**. 제품 흐름이 펼침 단계를 쓰지 않는 동안 운영 행은 0이다.
  무효 조건: 펼침 단계를 쓰는 흐름이 제품에 등록된 뒤(RM1c 뒤)에는 되돌리지 말고 새 마이그레이션을 낸다.
  구획 임대·울타리 칸(RM1b)은 0006 으로 더한다(이 파일을 다시 쓰지 않는다).
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할 — 0001 머리말과 같다).
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import same_company_foreign_key
from esgapi.core.isolation.grants import grant

RUNS = "run_runs"
SEGMENTS = "run_segments"
SEGMENT_DATA_MAX_OCTETS = 1024 * 1024  # 어림이다(머리말)


class Migration(migrations.Migration):
    dependencies = [("runs", "0004_run_launch_key"), ("organization", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="RunSegmentRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("step", models.CharField(max_length=100)),
                ("position", models.IntegerField()),
                ("kind", models.CharField(max_length=32)),
                ("key", models.JSONField()),
                ("key_sha256", models.CharField(max_length=64)),
                ("status", models.CharField(max_length=16)),
                ("attempts", models.IntegerField(default=0)),
                ("data", models.JSONField(null=True)),
                ("error_code", models.CharField(max_length=64, null=True)),
                ("started_at", models.DateTimeField(null=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="segments", to="runs.runrow"
                    ),
                ),
            ],
            options={
                "db_table": SEGMENTS,
                "abstract": False,
                "indexes": [models.Index(fields=["company", "run"], name="run_segments_company_run")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("pending", "running", "done", "failed"))),
                        name="run_segments_status_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("position__gte", 0)), name="run_segments_position_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("attempts__gte", 0)), name="run_segments_attempts_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("key_sha256__regex", "^[0-9a-f]{64}$")),
                        name="run_segments_key_sha256_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("data__isnull", False), ("error_code__isnull", True), ("status", "done")),
                            models.Q(("data__isnull", True), ("error_code__isnull", False), ("status", "failed")),
                            models.Q(
                                ("data__isnull", True),
                                ("error_code__isnull", True),
                                ("status__in", ("pending", "running")),
                            ),
                            _connector="OR",
                        ),
                        name="run_segments_status_fields_check",
                    ),
                    models.UniqueConstraint(
                        fields=("run", "step", "key_sha256"), name="run_segments_run_step_sha_uniq"
                    ),
                    models.UniqueConstraint(
                        fields=("run", "step", "position"), name="run_segments_run_step_position_uniq"
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                f'ALTER TABLE "{SEGMENTS}" ADD CONSTRAINT "run_segments_data_size_check" '
                f"CHECK (octet_length(data::text) <= {SEGMENT_DATA_MAX_OCTETS});"
            ),
            reverse_sql=f'ALTER TABLE "{SEGMENTS}" DROP CONSTRAINT "run_segments_data_size_check";',
        ),
        same_company_foreign_key(table=SEGMENTS, column="run_id", target=RUNS),
        grant(f'"{SEGMENTS}"', "SELECT, INSERT, UPDATE"),
    ]
