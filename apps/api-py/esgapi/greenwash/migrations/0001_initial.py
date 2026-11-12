"""그린워싱의 표 둘 — 검토(greenwash_reviews)와 문장마다의 표시(greenwash_review_marks). 밴드 G1b ②.

숫자 id(BigAuto)와 회사 칸(company_id — organization 의 company 를 가리키는 외래 키, PROTECT, 글자 참조).
run_id 는 외래 키가 아닌 BigInt 다(MARC-ENT-210 (1) — 다른 앱은 runs 로 FK·마이그레이션 의존을 두지 않는다). 그래서
dependencies 는 organization 0001 하나다(runs·core 0001 에 기대지 않는다).

RunSQL:
  greenwash_review_marks_run_id_same_company_fk   (company_id, run_id) → greenwash_reviews (company_id, run_id)
    표시가 같은 회사의 검토 행 없이 서지 못한다(MARC-ENT-210 「하위 표는 같은 테넌트 복합 FK 짝」). 가리킬 자리는
    greenwash_reviews_company_run_uniq(모델의 UniqueConstraint). NOT DEFERRABLE — 그 문에서 23503
    (core/isolation/foreign_keys.py 와 같은 까닭). core 의 same_company_foreign_key 는 (company_id, id) 만 가리켜서
    직접 적는다. 쓰는 길은 PUT 이 같은 트랜잭션에서 검토 행을 먼저 만들거나 잠근 뒤 표시를 쓴다(service/services/review.py).
  GRANT   : 앱 역할(esg_app)에게 두 표 다 SELECT, INSERT, UPDATE. DELETE·TRUNCATE 는 주지 않는다 — 표시 지우기는
            decision·exclude_reason 을 NULL 로 UPDATE 한다(발주서 G1b 개정 1 B2).

상태·표시의 CHECK 는 값을 문면에 굳힌다. greenwash/models.py 의 REVIEW_STATES·MARK_DECISIONS 를 바꾸면 새 마이그레이션.
무효 조건: superuser 역할에게는 GRANT 가 뜻이 없다(로컬 compose 의 주인 역할. 업무 층의 테스트가 그 역할로 돈다).
"""

import django.db.models.deletion
from django.db import migrations, models

from esgapi.core.isolation.grants import grant

REVIEWS = "greenwash_reviews"
MARKS = "greenwash_review_marks"
MARKS_FK = "greenwash_review_marks_run_id_same_company_fk"  # 45자(PostgreSQL 63자 안)


class Migration(migrations.Migration):
    initial = True

    dependencies = [("organization", "0001_initial")]

    operations = [
        migrations.CreateModel(
            name="GreenwashReviewRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("run_id", models.BigIntegerField()),
                ("state", models.CharField(max_length=16)),
                ("confirmed_at", models.DateTimeField(null=True)),
                ("confirmed_by_user_id", models.BigIntegerField(null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
            ],
            options={
                "db_table": REVIEWS,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(fields=("company", "run_id"), name="greenwash_reviews_company_run_uniq"),
                    models.CheckConstraint(
                        condition=models.Q(("state__in", ("pending", "in_review", "confirmed"))),
                        name="greenwash_reviews_state_check",
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(
                                ("confirmed_at__isnull", False),
                                ("confirmed_by_user_id__isnull", False),
                                ("state", "confirmed"),
                            ),
                            models.Q(
                                models.Q(("state", "confirmed"), _negated=True),
                                ("confirmed_at__isnull", True),
                                ("confirmed_by_user_id__isnull", True),
                            ),
                            _connector="OR",
                        ),
                        name="greenwash_reviews_confirmed_check",
                    ),
                ],
            },
        ),
        migrations.CreateModel(
            name="GreenwashReviewMarkRow",
            fields=[
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("id", models.BigAutoField(primary_key=True, serialize=False)),
                ("run_id", models.BigIntegerField()),
                ("item_index", models.IntegerField()),
                ("decision", models.CharField(max_length=16, null=True)),
                ("exclude_reason", models.CharField(max_length=500, null=True)),
                ("company", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, to="organization.company")),
            ],
            options={
                "db_table": MARKS,
                "abstract": False,
                "constraints": [
                    models.UniqueConstraint(
                        fields=("company", "run_id", "item_index"), name="greenwash_review_marks_company_run_item_uniq"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(("item_index__gte", 0)), name="greenwash_review_marks_item_check"
                    ),
                    models.CheckConstraint(
                        condition=models.Q(
                            models.Q(("decision__isnull", True), ("exclude_reason__isnull", True)),
                            models.Q(
                                ("decision", "adopted"), ("decision__isnull", False), ("exclude_reason__isnull", True)
                            ),
                            models.Q(
                                ("decision", "excluded"), ("decision__isnull", False), ("exclude_reason__isnull", False)
                            ),
                            _connector="OR",
                        ),
                        name="greenwash_review_marks_decision_check",
                    ),
                ],
            },
        ),
        migrations.RunSQL(
            sql=(
                f'ALTER TABLE "{MARKS}" ADD CONSTRAINT "{MARKS_FK}" '
                f'FOREIGN KEY (company_id, run_id) REFERENCES "{REVIEWS}" (company_id, run_id) NOT DEFERRABLE;'
            ),
            reverse_sql=f'ALTER TABLE "{MARKS}" DROP CONSTRAINT "{MARKS_FK}";',
        ),
        grant(f'"{REVIEWS}"', "SELECT, INSERT, UPDATE"),
        grant(f'"{MARKS}"', "SELECT, INSERT, UPDATE"),
    ]
