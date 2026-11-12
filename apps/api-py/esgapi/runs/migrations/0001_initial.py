"""runs 의 표 다섯 — 문서에 걸린 일감(run_jobs)과 흐름의 실행 넷(run_runs·run_steps·run_results·run_files — X1b-1 이
같은 판에 더함) — 과 크기 CHECK·같은 회사 외래 키·앱 역할의 권한. run_jobs 는 X1a 때 core 의 0001 에서 옮기고 이름을
run_ 접두로 바꿨다(다시 쓰기 — MARC-ENT-284: 공유 DB 가 서기 전까지). runs 의 마이그레이션은 0001·0002(ND1 — document NULL·options 상한).

숫자 id(BigAuto — DB 의 식별 열)와 회사 칸(company_id). 일감의 company 는 organization 의 company 를, document 는
core 의 문서를 가리키는 외래 키(PROTECT)다. dependencies 는 core 0001(문서 표와 그 회사 키)과 organization 0001
(company 표) 둘이다. runs 는 organization 을 import 하지 않는다(.importlinter 계약 차 — 회사 외래 키는 글자 참조).
다른 앱은 runs 의 마이그레이션에 기대지 않는다(MARC-ENT-210 (1)).

RunSQL:
  run_jobs_summary_size_check   octet_length(summary::text) <= 4096
    `summary` 는 「작은 요약」이다. 분해 결과의 본문이 들어갈 자리가 아니라는 것을 DB 가 막는다.
    ★ 4096 은 어림이다(잰 값이 아니다). 재는 것은 PostgreSQL 이 jsonb 를 다시 적은 글자의 바이트 수라
      (쌍점·쉼표 뒤에 빈칸이 든다) 파이썬에서 센 JSON 의 길이와 조금 어긋난다.
  run_runs_options_size_check·run_runs_versions_size_check   16KiB · run_steps_data_size_check·
  run_steps_partial_size_check   16MiB · run_results_body_size_check   8MiB   (X1b-1, 같은 재는 법 — 전부 어림.
    값은 runs/models.py 의 RUN_*_MAX_OCTETS 와 같다 — 테스트가 견준다)
  same_company_foreign_key(run_jobs.document_id → core_documents)   받침 ⑤
    일감이 남의 회사 문서에 걸리지 못한다(NOT DEFERRABLE: 그 문에서 23503 — core/isolation/foreign_keys.py).
    가리킬 자리 company_key("core_documents") 는 core 의 0001 이 단다.
  company_key("run_runs") 와 same_company_foreign_key 넷(X1b-1)   받침 ⑤
    run_runs.document_id → core_documents, run_steps·run_results·run_files 의 run_id → run_runs.
    실행이 남의 회사 문서에, 하위 행이 남의 회사 실행에 걸리지 못한다.
  GRANT   : 앱 역할(esg_app)에게 run_jobs·run_runs·run_steps 는 SELECT, INSERT, UPDATE, run_results·run_files 는
            SELECT, INSERT 만(한 번 쓰고 끝 — MARC-ENT-210 (1)). 다섯 다 DELETE·TRUNCATE 를 주지 않는다
            (실행 넷은 지우지 않는다 — MARC-ENT-208. 일감은 지우기·보존을 아직 정하지 않았다).
            숫자 id 의 식별 열은 표의 INSERT 권한으로 쓰인다.

상태의 CHECK(run_jobs_status_check, run_runs·run_steps 의 상태·목적)는 값을 문면에 굳힌다. esgapi/core/calc/documents.py
의 상태·runs/service/schemas/runs.py 의 상태를 더하면 새 마이그레이션으로 그 제약을 바꿔야 한다(테스트가 견준다).
`kind` 에는 CHECK 가 없다.

무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

DOCUMENTS = "core_documents"
JOBS = "run_jobs"
RUNS = "run_runs"
STEPS = "run_steps"
RESULTS = "run_results"
FILES = "run_files"
# 어림이다(머리말).
SUMMARY_MAX_OCTETS = 4096
OPTIONS_MAX_OCTETS = 16 * 1024
VERSIONS_MAX_OCTETS = 16 * 1024
STEP_DATA_MAX_OCTETS = 16 * 1024 * 1024
RESULT_BODY_MAX_OCTETS = 8 * 1024 * 1024


def size_check(table: str, column: str, octets: int) -> migrations.RunSQL:
    """CHECK (octet_length(<칸>::text) <= <바이트>). 이름 "<table>_<column>_size_check". NULL 칸은 지난다."""
    name = f"{table}_{column}_size_check"
    return migrations.RunSQL(
        sql=f'ALTER TABLE "{table}" ADD CONSTRAINT "{name}" CHECK (octet_length({column}::text) <= {octets});',
        reverse_sql=f'ALTER TABLE "{table}" DROP CONSTRAINT "{name}";',
    )


class Migration(migrations.Migration):
    initial = True

    dependencies = [("core", "0001_initial"), ("organization", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="JobRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("kind", models.CharField(max_length=32)),
                ("status", models.CharField(max_length=32)),
                ("attempts", models.IntegerField(default=0)),
                ("error_code", models.CharField(max_length=64, null=True)),
                ("error_message", models.CharField(max_length=500, null=True)),
                ("summary", models.JSONField(default=dict)),
                ("lease_expires_at", models.DateTimeField(null=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="jobs", to="core.documentrow"
                    ),
                ),
            ],
            options={
                "db_table": JOBS,
                "abstract": False,
                "indexes": [models.Index(fields=["document", "created_at"], name="run_jobs_document_created")],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("queued", "processing", "done", "failed"))),
                        name="run_jobs_status_check",
                    ),
                    models.CheckConstraint(condition=models.Q(("attempts__gte", 0)), name="run_jobs_attempts_check"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RunRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("module", models.CharField(max_length=64)),
                ("flow_id", models.CharField(max_length=100)),
                ("options", models.JSONField(default=dict)),
                ("versions", models.JSONField(default=dict)),
                ("purpose", models.CharField(default="service", max_length=16)),
                ("status", models.CharField(max_length=32)),
                ("attempts", models.IntegerField(default=0)),
                ("stalled_attempts", models.SmallIntegerField(default=0)),
                ("progress_attempt", models.IntegerField(null=True)),
                ("lease_expires_at", models.DateTimeField(null=True)),
                ("created_by_user_id", models.BigIntegerField()),
                ("started_at", models.DateTimeField(null=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("failed_step", models.CharField(max_length=100, null=True)),
                ("error_code", models.CharField(max_length=64, null=True)),
                ("error_message", models.CharField(max_length=500, null=True)),
                ("resumed_from_run_id", models.BigIntegerField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="runs", to="core.documentrow"
                    ),
                ),
            ],
            options={
                "db_table": RUNS,
                "abstract": False,
                "indexes": [
                    models.Index(fields=["company", "created_at"], name="run_runs_company_created"),
                    models.Index(fields=["company", "document", "created_at"], name="run_runs_company_doc_created"),
                    models.Index(fields=["created_at"], name="run_runs_created"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("queued", "processing", "done", "failed"))),
                        name="run_runs_status_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("purpose__in", ("service", "test"))), name="run_runs_purpose_check"
                    ),
                    models.CheckConstraint(condition=models.Q(("attempts__gte", 0)), name="run_runs_attempts_check"),
                    models.CheckConstraint(
                        condition=models.Q(("stalled_attempts__gte", 0)), name="run_runs_stalled_attempts_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("progress_attempt__isnull", True), ("progress_attempt__gte", 1), _connector="OR"
                        ),
                        name="run_runs_progress_attempt_check",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="RunStepRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("name", models.CharField(max_length=100)),
                ("position", models.IntegerField()),
                ("status", models.CharField(max_length=16)),
                ("done", models.IntegerField(null=True)),
                ("total", models.IntegerField(null=True)),
                ("data", models.JSONField(null=True)),
                ("partial", models.JSONField(null=True)),
                ("started_at", models.DateTimeField(null=True)),
                ("finished_at", models.DateTimeField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="steps", to="runs.runrow"
                    ),
                ),
            ],
            options={
                "db_table": STEPS,
                "abstract": False,
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("pending", "running", "done", "failed"))),
                        name="run_steps_status_check",
                    ),
                    models.CheckConstraint(condition=models.Q(("position__gte", 0)), name="run_steps_position_check"),
                    models.UniqueConstraint(fields=("run", "name"), name="run_steps_run_name_uniq"),
                    models.UniqueConstraint(fields=("run", "position"), name="run_steps_run_position_uniq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RunResultRow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("position", models.IntegerField()),
                ("schema_version", models.CharField(max_length=100)),
                ("body", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="results", to="runs.runrow"
                    ),
                ),
            ],
            options={
                "db_table": RESULTS,
                "abstract": False,
                "constraints": [
                    models.CheckConstraint(condition=models.Q(("position__gte", 0)), name="run_results_position_check"),
                    models.UniqueConstraint(fields=("run", "position"), name="run_results_run_position_uniq"),
                ],
            },
        ),
        migrations.CreateModel(
            name="RunFileRow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("step", models.CharField(max_length=100, null=True)),
                ("name", models.CharField(max_length=100)),
                ("media_type", models.CharField(max_length=100)),
                ("storage_key", models.CharField(max_length=255, unique=True)),
                ("size_bytes", models.BigIntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "run",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="files", to="runs.runrow"
                    ),
                ),
            ],
            options={
                "db_table": FILES,
                "abstract": False,
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("name__regex", "^[A-Za-z0-9._-]{1,100}$")), name="run_files_name_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("size_bytes__gte", 0)), name="run_files_size_bytes_check"
                    ),
                    models.UniqueConstraint(
                        fields=("run", "step", "name"), name="run_files_run_step_name_uniq", nulls_distinct=False
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                f'ALTER TABLE "{JOBS}" ADD CONSTRAINT "run_jobs_summary_size_check" '
                f"CHECK (octet_length(summary::text) <= {SUMMARY_MAX_OCTETS});"
            ),
            reverse_sql=f'ALTER TABLE "{JOBS}" DROP CONSTRAINT "run_jobs_summary_size_check";',
        ),
        size_check(RUNS, "options", OPTIONS_MAX_OCTETS),
        size_check(RUNS, "versions", VERSIONS_MAX_OCTETS),
        size_check(STEPS, "data", STEP_DATA_MAX_OCTETS),
        size_check(STEPS, "partial", STEP_DATA_MAX_OCTETS),
        size_check(RESULTS, "body", RESULT_BODY_MAX_OCTETS),
        same_company_foreign_key(table=JOBS, column="document_id", target=DOCUMENTS),
        company_key(RUNS),
        same_company_foreign_key(table=RUNS, column="document_id", target=DOCUMENTS),
        same_company_foreign_key(table=STEPS, column="run_id", target=RUNS),
        same_company_foreign_key(table=RESULTS, column="run_id", target=RUNS),
        same_company_foreign_key(table=FILES, column="run_id", target=RUNS),
        grant(f'"{JOBS}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{RUNS}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{STEPS}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{RESULTS}"', "SELECT, INSERT"),
        grant(f'"{FILES}"', "SELECT, INSERT"),
    ]
