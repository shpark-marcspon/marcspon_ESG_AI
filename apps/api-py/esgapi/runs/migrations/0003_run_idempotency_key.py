"""실행 표 run_runs 에 Idempotency-Key 칸 둘과 제약 둘 — 끊김 뒤 다시 누름 = 실행 한 번. 밴드 IK1(MARC-ISSUE-225).

  idempotency_key       요청 머리 Idempotency-Key(소문자 UUID, 36자). NULL = 열쇠 없이 만든 실행(지금까지의 행 전부)
  idempotency_sha256    그 요청 본문의 정규화 sha256(runs/calc/idempotency.py — 같은 열쇠의 다시 보냄이 같은 요청인지)
  run_runs_idempotency_uniq        (company_id, created_by_user_id, idempotency_key) WHERE idempotency_key IS NOT NULL
                        같은 사람의 같은 열쇠는 실행 하나다. 만료 없음(색인에 시각을 넣지 않는다). 동시 두 요청의 뒤의
                        것은 이 색인에서 23505 → 실행 만들기(runs/service/actions/runs.py)가 앞 실행을 다시 읽는다
  run_runs_idempotency_pair_check  둘 다 NULL 이거나 둘 다 값(열쇠만 있고 본문 sha 가 없는 반쪽 행 0)

AddField 둘(NULL 칸이라 기존 행은 다시 쓰지 않는다)과 AddConstraint 둘. runs 의 셋째 마이그레이션이다: 0001·0002 를 다시
쓰지 않는다(MARC-ENT-284 — 0002 머리말과 같은 까닭). GRANT 줄 0: 0001 이 run_runs 에 표 단위로
`SELECT, INSERT, UPDATE` 를 주었다(칸 단위가 아니다) — 새 칸에 저절로 닿는다.
★ 무효 조건 — 되돌림(0003 → 0002)은 칸 둘과 제약 둘을 지운다: 열쇠 기록이 사라질 뿐 실행 행은 그대로다(되돌린 뒤 같은
  열쇠로 다시 보내면 새 실행이 된다).
"""

from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("runs", "0002_run_document_optional"),
    ]

    operations = [
        migrations.AddField(
            model_name="runrow",
            name="idempotency_key",
            field=models.CharField(max_length=36, null=True),
        ),
        migrations.AddField(
            model_name="runrow",
            name="idempotency_sha256",
            field=models.CharField(max_length=64, null=True),
        ),
        migrations.AddConstraint(
            model_name="runrow",
            constraint=models.UniqueConstraint(
                condition=models.Q(("idempotency_key__isnull", False)),
                fields=("company", "created_by_user_id", "idempotency_key"),
                name="run_runs_idempotency_uniq",
            ),
        ),
        migrations.AddConstraint(
            model_name="runrow",
            constraint=models.CheckConstraint(
                condition=models.Q(
                    models.Q(("idempotency_key__isnull", True), ("idempotency_sha256__isnull", True)),
                    models.Q(("idempotency_key__isnull", False), ("idempotency_sha256__isnull", False)),
                    _connector="OR",
                ),
                name="run_runs_idempotency_pair_check",
            ),
        ),
    ]
