"""문서 산출물의 표 둘(밴드 RP2a ①, 결정 MARC-ENT-514 — 계약 core/documents/contract.py 의 core.doc-artifact@1).
core 의 셋째 마이그레이션이다: 0001·0002 를 다시 쓰지 않는다(MARC-ENT-284). 데이터 이전 0. 되돌리면 표 둘이 지워진다.
  core_document_artifacts       unique (company, contract, source_sha256, layout, epoch) · CHECK status ∈ {ready, too_large}
                                · layout ∈ {1, 2} · epoch ≥ 1 · sha256 16진 64자 · page_count ≥ 1 · body_bytes ≥ 0 ·
                                ready ⇔ 본문 둘 NOT NULL, too_large ⇔ 둘 NULL
  core_document_artifact_uses   unique (company, document, document_etag, contract, layout, epoch)
  RunSQL                        core_document_artifacts_company_id_uniq   UNIQUE (company_id, id)
                                core_document_artifact_uses_document_id_same_company_fk → core_documents (company_id, id)
                                core_document_artifact_uses_artifact_id_same_company_fk → core_document_artifacts
                                (core/isolation/foreign_keys.py — NOT DEFERRABLE, 남의 회사 행을 가리키면 그 문에서 23503)
  GRANT                         둘 다 SELECT, INSERT(불변 행 — UPDATE·DELETE 0, e7 ⑫)
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
★ 번호는 병합 직전 main 의 core 마이그레이션과 감독이 대 본다(e7 ⑨).
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

DOCUMENTS = "core_documents"
ARTIFACTS = "core_document_artifacts"
USES = "core_document_artifact_uses"


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_llm_call_log_step"),
        ("organization", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DocumentArtifactRow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("contract", models.CharField(max_length=40)),
                ("epoch", models.SmallIntegerField()),
                ("source_sha256", models.CharField(max_length=64)),
                ("layout", models.SmallIntegerField()),
                ("parser_name", models.CharField(max_length=40)),
                ("parser_version", models.CharField(max_length=40)),
                ("status", models.CharField(max_length=16)),
                ("page_count", models.IntegerField()),
                ("body_bytes", models.BigIntegerField()),
                ("document", models.JSONField(null=True)),
                ("char_places", models.JSONField(null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
            ],
            options={
                "db_table": "core_document_artifacts",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DocumentArtifactUseRow",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("document_etag", models.CharField(max_length=255)),
                ("contract", models.CharField(max_length=40)),
                ("layout", models.SmallIntegerField()),
                ("epoch", models.SmallIntegerField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "artifact",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.documentartifactrow"
                    ),
                ),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
                (
                    "document",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="core.documentrow"
                    ),
                ),
            ],
            options={
                "db_table": "core_document_artifact_uses",
                "abstract": False,
            },
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.UniqueConstraint(
                fields=("company", "contract", "source_sha256", "layout", "epoch"),
                name="core_document_artifacts_key_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("status__in", ("ready", "too_large"))), name="core_document_artifacts_status_check"
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("layout__in", (1, 2))), name="core_document_artifacts_layout_check"
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("epoch__gte", 1)), name="core_document_artifacts_epoch_check"
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("source_sha256__regex", "^[0-9a-f]{64}$")),
                name="core_document_artifacts_sha256_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(("body_bytes__gte", 0), ("page_count__gte", 1)),
                name="core_document_artifacts_sizes_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("char_places__isnull", False), ("document__isnull", False), ("status", "ready")),
                    models.Q(("char_places__isnull", True), ("document__isnull", True), ("status", "too_large")),
                    _connector="OR",
                ),
                name="core_document_artifacts_body_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="documentartifactuserow",
            constraint=models.UniqueConstraint(
                fields=("company", "document", "document_etag", "contract", "layout", "epoch"),
                name="core_document_artifact_uses_key_uniq",
            ),
        ),
        company_key(ARTIFACTS),
        same_company_foreign_key(table=USES, column="document_id", target=DOCUMENTS),
        same_company_foreign_key(table=USES, column="artifact_id", target=ARTIFACTS),
        grant(f'"{ARTIFACTS}", "{USES}"', "SELECT, INSERT"),
    ]
