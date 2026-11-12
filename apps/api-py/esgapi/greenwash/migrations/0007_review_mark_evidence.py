"""표시 표 greenwash_review_marks 에 근거 고침·재판단 칸 여섯. 밴드 GRJ1 ①(결정 MARC-ENT-617, 꼴 greenwash.review@3 —
contracts/review_shapes.py).

  evidence_removed jsonb          기준 판단의 confirmedInEvidence 차례 중 지운 것(오름·겹침 없음)
  evidence_added jsonb            더한 조각 [{text, page|null}](받은 차례)
  evidence_edited_at timestamptz  evidence_edited_by_user_id bigint
  evidence_basis_run_id bigint    removed 가 가리키는 기준 판단의 재판단 실행 id(NULL = 첫 판단). 외래 키 아님
  rejudge_run_ids jsonb           이 문장의 재판단 실행 id 목록(만든 차례, 붙이기만). NULL = 재판단 없음
  다 NULL 허용.
  CHECK greenwash_review_marks_evidence_edit_check    removed·added·때·사람이 다 NULL 이거나 다 값
        greenwash_review_marks_evidence_basis_check   basis 는 근거 고침이 있을 때만 값
        greenwash_review_marks_evidence_size_check    octet_length(evidence_added::text) <= 131072(NULL 통과)
        greenwash_review_marks_rejudge_size_check     octet_length(rejudge_run_ids::text) <= 65536(NULL 통과)
  받기(service/actions/review.py — 10개·한 조각 1,000자)가 먼저 막는다 — 크기 CHECK 는 마지막 그물. 값은 문면에 굳힌다.

이행: AddField 여섯 + AddConstraint 넷, RunPython 0. 옛 행은 새 칸이 NULL = 근거 고침·재판단 없음(검토 GET 은 evidence [],
rejudges [] 로 읽는다). GRANT 줄 0: 앱 역할의 권한은 0001 의 표 단위 SELECT, INSERT, UPDATE 라 새 칸도 든다(DELETE 없음
그대로 — 0004 와 같다).
★ 되돌림(0007 → 0006)은 칸과 제약을 지우고 행은 남긴다 — **근거 고침과 재판단 실행 id 를 잃는다**(재판단 실행·결과 행은
  run_runs 에 남지만 문장과의 잇기가 사라진다). 운영 DB 에서 하지 않는다.
"""

from django.db import migrations, models
from django.db.models.functions import Cast
from django.db.models.lookups import LessThanOrEqual


def _octets_at_most(field: str, limit: int) -> models.Q:
    return models.Q(
        LessThanOrEqual(
            models.Func(
                Cast(field, output_field=models.TextField()),
                function="octet_length",
                output_field=models.IntegerField(),
            ),
            limit,
        )
    )


class Migration(migrations.Migration):
    dependencies = [
        ("greenwash", "0006_ai_settings_terms"),
    ]

    operations = [
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="evidence_added",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="evidence_basis_run_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="evidence_edited_at",
            field=models.DateTimeField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="evidence_edited_by_user_id",
            field=models.BigIntegerField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="evidence_removed",
            field=models.JSONField(null=True),
        ),
        migrations.AddField(
            model_name="greenwashreviewmarkrow",
            name="rejudge_run_ids",
            field=models.JSONField(null=True),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(
                        ("evidence_added__isnull", True),
                        ("evidence_edited_at__isnull", True),
                        ("evidence_edited_by_user_id__isnull", True),
                        ("evidence_removed__isnull", True),
                    ),
                    models.Q(
                        ("evidence_added__isnull", False),
                        ("evidence_edited_at__isnull", False),
                        ("evidence_edited_by_user_id__isnull", False),
                        ("evidence_removed__isnull", False),
                    ),
                    _connector="OR",
                ),
                name="greenwash_review_marks_evidence_edit_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    ("evidence_basis_run_id__isnull", True),
                    ("evidence_removed__isnull", False),
                    _connector="OR",
                ),
                name="greenwash_review_marks_evidence_basis_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=_octets_at_most("evidence_added", 131072),
                name="greenwash_review_marks_evidence_size_check",
            ),
        ),
        migrations.AddConstraint(
            model_name="greenwashreviewmarkrow",
            constraint=models.CheckConstraint(
                condition=_octets_at_most("rejudge_run_ids", 65536),
                name="greenwash_review_marks_rejudge_size_check",
            ),
        ),
    ]
