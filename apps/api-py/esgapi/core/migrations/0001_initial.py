"""core 의 표 셋 — LLM 호출 감사 기록(core_llm_call_logs), 올린 문서(core_documents), 감사 기록(core_audit_events —
AU1a 때 같은 판에 더함, MARC-ENT-284) — 과 같은 회사 키, 앱 역할의 권한. core 의 마이그레이션은 이것과 0002(AD4D — 단계 칸)다(K1u-b 때 다시 썼다. 이제 받는 쪽 DB 가 있을 수 있어 고쳐 쓰지 않는다 — MARC-ENT-275, 0002 머리말). 문서에 걸린
일감은 X1a 때 runs 의 0001 로 옮겼다(표 run_jobs)(다시 쓰기 — MARC-ENT-284: 공유 DB 가 서기 전까지).

숫자 id(BigAuto — DB 의 식별 열)와 회사 칸(company_id). 문서의 company 는 organization 의 company 를 가리키는
외래 키(PROTECT)이고, 기록의 company_id 는 외래 키가 아닌 숫자 칸이다(회사가 지워져도 감사 기록은 남는다).
dependencies 는 organization 0001 하나다: company 표와 스키마 public 의 USAGE 가 거기서 선다. core 는 organization 을
import 하지 않는다(.importlinter 계약 가 — 모델의 외래 키는 글자 참조 "organization.Company").

RunSQL 셋:
  company_key("core_documents")   받침 ⑤
    같은 회사 외래 키가 가리킬 자리(UNIQUE (company_id, id)). 일감·실행의 same_company_foreign_key 는 runs 의 0001 이 단다.
  same_company_foreign_key(core_documents.previous_document_id → core_documents)   받침 ⑤ (X1b-1 — 자기 참조)
    수정본 사슬의 앞 판이 남의 회사 문서가 되지 못한다. 쓰는 길은 PATCH 하나(X1b-2a). 갈래 금지(한 문서의 뒤 판은
    하나)는 모델의 부분 UNIQUE core_documents_previous_uniq 가 진다(X1b-2a — 같은 판에 더함, MARC-ENT-284).
  GRANT   : 앱 역할(esg_app)에게 core_documents 는 SELECT, INSERT, UPDATE, core_llm_call_logs·core_audit_events 는
            SELECT, INSERT 만.
            ★ 기록은 덧붙이기만 하는 표다: UPDATE·DELETE·TRUNCATE 를 주지 않는다 → 요청을 처리하는 프로세스는 감사
            기록을 고치거나 지우지 못한다(주인 역할은 된다 — 2차의 보존 정리). 문서에도 DELETE·TRUNCATE 를 주지 않는다(지우기·보존은 아직 정하지 않았다).
            숫자 id 의 식별 열은 표의 INSERT 권한으로 쓰인다(번호열 권한이 따로 없다).

상태·결과 갈래의 CHECK(core_documents_status_check, core_llm_call_logs_result_kind_check, core_audit_events 의 행동·결과·
행위자)는 값을 문면에 굳힌다. esgapi/core/calc/documents.py 의 상태·esgapi/core/llm/types.py 의 LlmResultKind·
esgapi/core/calc/audit.py 의 값을 더하면 새 마이그레이션으로 그 제약을 바꿔야 한다(테스트가 견준다).
기록의 run_id(X1b-1 — 실행 id)도 외래 키가 아니다(runs 로 향하는 다른 앱의 FK 0, MARC-ENT-210 (1)).
감사 기록의 company_id·actor_user_id·target_id 도 외래 키가 아니다(감사 표로 향하는 외래 키도, 감사 표가 다른 표로
향하는 외래 키도 0 — 처분 ②).

무효 조건:
  - superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
  - 없는 회사 id 로도 기록 행이 남는다(외래 키가 아니다). 문서의 uploaded_by 는 글자 칸이라 없는 사용자 id 로도 남는다.
"""

import django.db.models.deletion
import django.db.models.functions.comparison
import django.db.models.lookups
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

LOGS = "core_llm_call_logs"
DOCUMENTS = "core_documents"
AUDIT = "core_audit_events"


class Migration(migrations.Migration):
    initial = True

    dependencies = [("organization", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="LlmCallLogRow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("company_id", models.BigIntegerField()),
                ("module", models.CharField(max_length=100)),
                ("ts", models.DateTimeField()),
                ("call_id", models.CharField(max_length=64)),
                ("attempt", models.IntegerField()),
                ("provider", models.CharField(max_length=64, null=True)),
                ("model", models.CharField(max_length=100, null=True)),
                ("api_model_id", models.CharField(max_length=200, null=True)),
                ("response_model_id", models.CharField(max_length=200, null=True)),
                ("prompt_id", models.CharField(max_length=200)),
                ("prompt_version", models.IntegerField()),
                ("template_hash", models.CharField(max_length=64)),
                ("request_hash", models.CharField(max_length=64)),
                ("input_tokens", models.IntegerField(null=True)),
                ("output_tokens", models.IntegerField(null=True)),
                ("cache_read_tokens", models.IntegerField(null=True)),
                ("cache_write_tokens", models.IntegerField(null=True)),
                ("thinking_tokens", models.IntegerField(null=True)),
                ("cost_usd", models.DecimalField(decimal_places=8, max_digits=18, null=True)),
                ("duration_ms", models.FloatField()),
                ("result_kind", models.CharField(max_length=32)),
                ("warnings", models.JSONField(default=list)),
                ("retry_after_ms", models.IntegerField(null=True)),
                ("provider_retry", models.IntegerField(null=True)),
                ("retry_wait_ms", models.FloatField(null=True)),
                ("has_error_status", models.BooleanField(default=False)),
                ("error_status", models.IntegerField(null=True)),
                ("has_previous_error_status", models.BooleanField(default=False)),
                ("previous_error_status", models.IntegerField(null=True)),
                ("run_id", models.BigIntegerField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={
                "db_table": LOGS,
                "abstract": False,
                "indexes": [
                    models.Index(fields=["company_id", "module"], name="core_llm_logs_company_module"),
                    models.Index(fields=["call_id"], name="core_llm_logs_call_id"),
                    models.Index(fields=["company_id", "run_id"], name="core_llm_logs_company_run"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "result_kind__in",
                                (
                                    "success",
                                    "schema_mismatch",
                                    "refusal",
                                    "truncated",
                                    "provider_error",
                                    "timeout",
                                    "budget_exceeded",
                                ),
                            )
                        ),
                        name="core_llm_call_logs_result_kind_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("attempt__gte", 0)), name="core_llm_call_logs_attempt_check"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="DocumentRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("uploaded_by", models.CharField(max_length=64)),
                ("file_name", models.CharField(max_length=255)),
                ("storage_key", models.CharField(max_length=255, unique=True)),
                ("size_bytes", models.BigIntegerField()),
                ("etag", models.CharField(max_length=255, null=True)),
                ("sha256", models.CharField(max_length=64, null=True)),
                ("status", models.CharField(max_length=32)),
                ("uploaded_at", models.DateTimeField(null=True)),
                ("report_year", models.SmallIntegerField(null=True)),
                ("page_count", models.IntegerField(null=True)),
                ("has_text", models.BooleanField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
                (
                    "previous_document",
                    models.ForeignKey(
                        null=True, on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.documentrow"
                    ),
                ),
            ],
            options={
                "db_table": DOCUMENTS,
                "abstract": False,
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(("status__in", ("awaiting_upload", "uploaded"))),
                        name="core_documents_status_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("size_bytes__gte", 1)), name="core_documents_size_bytes_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            ("report_year__isnull", True),
                            models.Q(("report_year__gte", 1900), ("report_year__lte", 2100)),
                            _connector="OR",
                        ),
                        name="core_documents_report_year_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("page_count__isnull", True), ("page_count__gte", 1), _connector="OR"),
                        name="core_documents_page_count_check",
                    ),
                    models.UniqueConstraint(
                        condition=models.Q(("previous_document__isnull", False)),
                        fields=("company", "previous_document"),
                        name="core_documents_previous_uniq",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="AuditEventRow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("company_id", models.BigIntegerField(null=True)),
                ("at", models.DateTimeField()),
                ("actor_kind", models.CharField(max_length=16)),
                ("actor_user_id", models.BigIntegerField(null=True)),
                ("action", models.CharField(max_length=32)),
                ("event", models.CharField(max_length=40)),
                ("result", models.CharField(max_length=16)),
                ("reason", models.CharField(max_length=40, null=True)),
                ("target_kind", models.CharField(max_length=40, null=True)),
                ("target_id", models.BigIntegerField(null=True)),
                ("target_label", models.CharField(max_length=255, null=True)),
                ("detail", models.JSONField(default=dict)),
                ("request_id", models.CharField(max_length=64, null=True)),
            ],
            options={
                "db_table": AUDIT,
                "abstract": False,
                "indexes": [
                    models.Index(fields=["company_id", "at"], name="core_audit_company_at"),
                    models.Index(fields=["at"], name="core_audit_at"),
                    models.Index(fields=["action", "at"], name="core_audit_action_at"),
                ],
                "constraints": [
                    models.CheckConstraint(
                        condition=models.Q(
                            (
                                "action__in",
                                (
                                    "login",
                                    "logout",
                                    "upload",
                                    "run",
                                    "download",
                                    "setting_change",
                                    "adopt",
                                    "exclude",
                                    "confirm",
                                ),
                            )
                        ),
                        name="core_audit_events_action_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("result__in", ("success", "failure"))),
                        name="core_audit_events_result_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("actor_kind__in", ("admin", "service", "command", "anonymous"))),
                        name="core_audit_events_actor_kind_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.LessThanOrEqual(
                                models.Func(
                                    django.db.models.functions.comparison.Cast(
                                        "detail", output_field=models.TextField()
                                    ),
                                    function="octet_length",
                                    output_field=models.IntegerField(),
                                ),
                                1024,
                            )
                        ),
                        name="core_audit_events_detail_size_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("actor_kind", "service"), ("company_id__isnull", True), _negated=True),
                        name="core_audit_events_service_company_check",
                    ),
                ],
            },
        ),
        company_key(DOCUMENTS),
        same_company_foreign_key(table=DOCUMENTS, column="previous_document_id", target=DOCUMENTS),
        grant(f'"{LOGS}"', "SELECT, INSERT"),
        grant(f'"{DOCUMENTS}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{AUDIT}"', "SELECT, INSERT"),
    ]
