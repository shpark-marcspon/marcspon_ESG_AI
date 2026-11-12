"""중대성평가 IRO 결과 글 칸 고침의 표 둘 — 머리(materiality_result_edit_heads)와 고침(materiality_result_edits). 밴드
IRS3 ① (결정 MARC-ENT-561).

숫자 id(BigAuto)와 회사 칸(company_id — organization 의 company 를 가리키는 외래 키, PROTECT, 글자 참조).
run_id 는 외래 키가 아닌 BigInt 다(MARC-ENT-210 (1) — 다른 앱은 runs 로 FK·마이그레이션 의존을 두지 않는다). 그래서
dependencies 는 materiality 0001 하나다(runs·core 0001 에 기대지 않는다).

제약(materiality/models.py 의 MaterialityResultEditHeadRow·MaterialityResultEditRow):
  머리 unique (company_id, run_id)                            실행마다 머리 하나
  머리 CHECK revision >= 0                                    0 = 아직 고침 없음(처음 저장 때 만든 그 자리)
  고침 unique (company_id, run_id, revision, pointer)         한 저장 안에 같은 칸은 하나
  고침 CHECK revision >= 1
  고침 CHECK pointer ~ <허용 꼴>                              contracts/edit_shapes.POINTER_PATTERN(문면에 굳힘)
  고침 CHECK octet_length(value::text) <= 16384               NULL 통과(어림 — 받기의 4,000자가 먼저 막는다)
  받기(outputs/edits.check·본문 꼴)가 먼저 막는다 — CHECK 는 마지막 그물(500 0). 값은 문면에 굳힌다.
RunSQL:
  materiality_result_edits_run_id_same_company_fk   (company_id, run_id) → materiality_result_edit_heads (company_id, run_id)
    고침이 같은 회사의 머리 행 없이 서지 못한다(MARC-ENT-210 「하위 표는 같은 테넌트 복합 FK 짝」 — greenwash 0001 의
    marks → reviews 꼴). NOT DEFERRABLE. 쓰는 길은 저장이 같은 트랜잭션에서 머리 행을 먼저 만든 뒤 고침을 넣는다.
GRANT   : 앱 역할(esg_app)에게 머리는 SELECT, INSERT 와 **칸 단위 UPDATE (revision, updated_at)**(조건부 UPDATE 의 낙관
          잠금), 고침은 SELECT, INSERT 만(불변 행 — 저장 = 새 행). DELETE·TRUNCATE 는 주지 않는다.
★ 되돌림(0002 → 0001, `migrate materiality 0001`)은 표 둘을 지운다 — **고침 전부를 잃는다**(AI 원본 run_results 는
  그대로라 결과 GET·엑셀은 AI 판으로 돌아간다).
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
"""

import django.db.models.deletion
import django.db.models.functions.comparison
import django.db.models.lookups
from django.db import migrations, models

from esgapi.core.isolation.grants import grant

HEADS = "materiality_result_edit_heads"
EDITS = "materiality_result_edits"
EDITS_FK = "materiality_result_edits_run_id_same_company_fk"  # 47자(PostgreSQL 63자 안)
POINTER = (
    "^/part2/topics/(0|[1-9][0-9]{0,5})/subtopics/(0|[1-9][0-9]{0,5})/("
    "(impact|pathway)/rows/(0|[1-9][0-9]{0,5})/impactDefinition"
    "|pathway/rows/(0|[1-9][0-9]{0,5})/(impactDriver|businessImpact|financialImpact)"
    "|(impact|financial|pathway)/rows/(0|[1-9][0-9]{0,5})/context/(regulations|controversies)/(0|[1-9][0-9]{0,5})"
    "/(title|summary|url))$"
)


class Migration(migrations.Migration):
    dependencies = [
        ("materiality", "0001_ai_settings"),
    ]

    operations = [
        migrations.CreateModel(
            name="MaterialityResultEditHeadRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("run_id", models.BigIntegerField()),
                ("revision", models.IntegerField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
            ],
            options={
                "db_table": HEADS,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "run_id"), name="materiality_result_edit_heads_company_run_uniq"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("revision__gte", 0)), name="materiality_result_edit_heads_revision_check"
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="MaterialityResultEditRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("run_id", models.BigIntegerField()),
                ("revision", models.IntegerField()),
                ("pointer", models.CharField(max_length=200)),
                ("value", models.TextField(null=True)),
                ("edited_by_user_id", models.BigIntegerField()),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
            ],
            options={
                "db_table": EDITS,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "run_id", "revision", "pointer"),
                        name="materiality_result_edits_company_run_rev_uniq",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("revision__gte", 1)), name="materiality_result_edits_revision_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("pointer__regex", POINTER)), name="materiality_result_edits_pointer_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            django.db.models.lookups.LessThanOrEqual(
                                models.Func(
                                    django.db.models.functions.comparison.Cast(
                                        "value", output_field=models.TextField()
                                    ),
                                    function="octet_length",
                                    output_field=models.IntegerField(),
                                ),
                                16384,
                            )
                        ),
                        name="materiality_result_edits_value_size_check",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                f'ALTER TABLE "{EDITS}" ADD CONSTRAINT "{EDITS_FK}" '
                f'FOREIGN KEY (company_id, run_id) REFERENCES "{HEADS}" (company_id, run_id) NOT DEFERRABLE;'
            ),
            reverse_sql=f'ALTER TABLE "{EDITS}" DROP CONSTRAINT "{EDITS_FK}";',
        ),
        grant(f'"{HEADS}"', "SELECT, INSERT"),
        grant(f'"{HEADS}"', "UPDATE (revision, updated_at)"),
        grant(f'"{EDITS}"', "SELECT, INSERT"),
    ]
