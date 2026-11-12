"""원고작성의 표 넷(밴드 RP1 ①, 결정 MARC-ENT-501). drafting 의 첫 마이그레이션 — organization 0001 에만 기댄다.

숫자 id(BigAuto)와 회사 칸(company_id — organization 의 company, PROTECT). 되돌리면 표 넷이 지워진다. 데이터 이전 0.

  drafting_projects            CHECK year 2000~2100 · name 1~80자 · outline_revision ≥ 0
  drafting_project_documents   CHECK kind ∈ {prior_report}(2차 갈래는 새 마이그레이션) · document_id 는 외래 키 아님
  drafting_outlines            unique (company, project, revision) · revision ≥ 1 · sha256 16진 64자 · node_count 1~300
  drafting_outline_nodes       unique (company, outline, key)·(company, outline, position) · depth 1~4 · title 1~200자 ·
                               requirement ≤ 2,000자
  RunSQL                       drafting_projects_company_id_uniq · drafting_outlines_company_id_uniq   UNIQUE (company_id, id)
                               drafting_project_documents_project_id_same_company_fk  → drafting_projects (company_id, id)
                               drafting_outlines_project_id_same_company_fk           → drafting_projects (company_id, id)
                               drafting_outline_nodes_outline_id_same_company_fk      → drafting_outlines (company_id, id)
                               (core/isolation/foreign_keys.py — NOT DEFERRABLE, 남의 회사 행을 가리키면 그 문에서 23503)
  GRANT                        넷 다 SELECT, INSERT(불변 행 — DELETE·표 단위 UPDATE 없음). drafting_projects 만 칸 단위
                               UPDATE (outline_revision, updated_at) — 목차 판 번호 매김을 그 행 FOR UPDATE 로 줄 세운다
                               (감독 처분 10-29, materiality 0001 의 칸 단위 UPDATE 꼴). FOR UPDATE 는 칸 하나의 UPDATE
                               권한으로 된다(PostgreSQL).
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
"""

import django.db.models.deletion
import django.db.models.functions.text
import django.db.models.lookups
from django.db import migrations, models

from esgapi.core.isolation.foreign_keys import company_key, same_company_foreign_key
from esgapi.core.isolation.grants import grant

PROJECTS = "drafting_projects"
DOCUMENTS = "drafting_project_documents"
OUTLINES = "drafting_outlines"
NODES = "drafting_outline_nodes"


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("organization", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="DraftingProject",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("year", models.SmallIntegerField()),
                ("name", models.CharField(max_length=80)),
                ("created_by_user_id", models.BigIntegerField()),
                ("outline_revision", models.IntegerField(default=0)),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
            ],
            options={
                "db_table": "drafting_projects",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DraftingOutline",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("revision", models.IntegerField()),
                ("sha256", models.CharField(max_length=64)),
                ("node_count", models.IntegerField()),
                ("created_by_user_id", models.BigIntegerField()),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="drafting.draftingproject"
                    ),
                ),
            ],
            options={
                "db_table": "drafting_outlines",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DraftingProjectDocument",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("document_id", models.BigIntegerField()),
                ("kind", models.CharField(max_length=32)),
                ("attached_by_user_id", models.BigIntegerField()),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
                (
                    "project",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="drafting.draftingproject"
                    ),
                ),
            ],
            options={
                "db_table": "drafting_project_documents",
                "abstract": False,
            },
        ),
        migrations.CreateModel(
            name="DraftingOutlineNode",
            fields=[
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("key", models.CharField(max_length=40)),
                ("parent_key", models.CharField(default="", max_length=40)),
                ("depth", models.SmallIntegerField()),
                ("position", models.IntegerField()),
                ("title", models.CharField(max_length=200)),
                ("requirement", models.TextField(default="")),
                (
                    "company",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="organization.company"
                    ),
                ),
                (
                    "outline",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT, related_name="+", to="drafting.draftingoutline"
                    ),
                ),
            ],
            options={
                "db_table": "drafting_outline_nodes",
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "outline", "key"), name="drafting_outline_nodes_key_unique"
                    ),
                    models.UniqueConstraint(
                        fields=("company", "outline", "position"), name="drafting_outline_nodes_position_unique"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("depth__gte", 1), ("depth__lte", 4)),
                        name="drafting_outline_nodes_depth_range",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("position__gte", 0)), name="drafting_outline_nodes_position_range"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.GreaterThanOrEqual(
                                django.db.models.functions.text.Length("title"), 1
                            ),
                            django.db.models.lookups.LessThanOrEqual(
                                django.db.models.functions.text.Length("title"), 200
                            ),
                        ),
                        name="drafting_outline_nodes_title_length",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.LessThanOrEqual(
                                django.db.models.functions.text.Length("requirement"), 2000
                            )
                        ),
                        name="drafting_outline_nodes_requirement_length",
                    ),
                ],
            },
        ),
        migrations.AddConstraint(
            model_name="draftingproject",
            constraint=models.CheckConstraint(
                condition=models.Q(("year__gte", 2000), ("year__lte", 2100)), name="drafting_projects_year_range"
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingproject",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    django.db.models.lookups.GreaterThanOrEqual(django.db.models.functions.text.Length("name"), 1),
                    django.db.models.lookups.LessThanOrEqual(django.db.models.functions.text.Length("name"), 80),
                ),
                name="drafting_projects_name_length",
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingproject",
            constraint=models.CheckConstraint(
                condition=models.Q(("outline_revision__gte", 0)), name="drafting_projects_outline_revision_range"
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingoutline",
            constraint=models.UniqueConstraint(
                fields=("company", "project", "revision"), name="drafting_outlines_project_revision_unique"
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingoutline",
            constraint=models.CheckConstraint(
                condition=models.Q(("revision__gte", 1)), name="drafting_outlines_revision_range"
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingoutline",
            constraint=models.CheckConstraint(
                condition=models.Q(("sha256__regex", "^[0-9a-f]{64}$")), name="drafting_outlines_sha256"
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingoutline",
            constraint=models.CheckConstraint(
                condition=models.Q(("node_count__gte", 1), ("node_count__lte", 300)),
                name="drafting_outlines_node_count",
            ),
        ),
        migrations.AddConstraint(
            model_name="draftingprojectdocument",
            constraint=models.CheckConstraint(
                condition=models.Q(("kind__in", ("prior_report",))), name="drafting_project_documents_kind"
            ),
        ),
        company_key(PROJECTS),
        company_key(OUTLINES),
        same_company_foreign_key(table=DOCUMENTS, column="project_id", target=PROJECTS),
        same_company_foreign_key(table=OUTLINES, column="project_id", target=PROJECTS),
        same_company_foreign_key(table=NODES, column="outline_id", target=OUTLINES),
        grant(f'"{PROJECTS}", "{DOCUMENTS}", "{OUTLINES}", "{NODES}"', "SELECT, INSERT"),
        grant(f'"{PROJECTS}"', "UPDATE (outline_revision, updated_at)"),
    ]
