"""실행 표 run_runs 를 문서 없는 흐름에 연다 — document_id NULL 과 options 의 DB 상한 올림. 밴드 ND1 ①(MARC-ISSUE-287).

  document_id NULL      문서 없는 흐름(입력이 옵션뿐 — 데이터 검증)의 실행. 문서를 요구하는 흐름에 문서가 있는지는
                        실행 만들기(runs/service/actions/runs.py)가 지킨다 — 모듈 목록을 DB 에 굳히지 않는다.
                        같은 회사 외래 키 run_runs_document_id_same_company_fk 는 그대로다: MATCH SIMPLE 이라 NULL 이면
                        비껴가고, 값이 있으면 지금처럼 같은 회사의 문서만 받는다. 하위 셋(단계·결과·파일)의 같은 회사 외래
                        키는 문서와 무관하다.
  run_runs_options_size_check   16KiB → OPTIONS_CEILING_OCTETS(2 × 256KiB + 64)
                        흐름의 앱 상한이 흐름마다다(core/flows/binding.py — 문서 흐름 16KiB, 문서 없는 흐름 많아야
                        256KiB). options 는 감싼 꼴(runs/models.py 의 OrderedJSONField)로 적혀 안쪽 따옴표·역빗금마다
                        역빗금이 붙는다 — 최악 두 배와 껍데기. 문서 흐름의 16KiB 는 이제 앱 층만 잠근다.

AlterField 하나(Django 가 한 칸 FK 를 내렸다 NOT NULL 을 풀고 다시 단다)와 RunSQL 둘(CHECK 를 내리고 같은 이름으로 다시
단다). runs 의 둘째 마이그레이션이다: 0001 을 다시 쓰지 않는다(MARC-ENT-284 「공유 DB 가 서기 전까지」 — esg-app 이
마크스폰에 나가 있어 받는 쪽 DB 가 있을 수 있다, MARC-ENT-275). GRANT 줄 0(칸·제약만 바뀐다).
★ 무효 조건 — 되돌림(0002 → 0001)은 문서가 NULL 인 실행 행이나 options 가 16KiB 를 넘는 행이 하나라도 있으면 실패한다
  (NOT NULL·CHECK 를 다시 걸 수 없다). 그런 행을 지우는 길은 없다(앱 역할에 DELETE 없음 — MARC-ENT-208).
"""

import django.db.models.deletion
from django.db import migrations, models

RUNS = "run_runs"
CHECK = "run_runs_options_size_check"
# runs/models.py 의 RUN_OPTIONS_CEILING_OCTETS 와 같다(테스트가 견준다). 문면에 굳힌다 — 상수가 바뀌면 새 마이그레이션.
OPTIONS_CEILING_OCTETS = 2 * 256 * 1024 + 64
OPTIONS_MAX_OCTETS_0001 = 16 * 1024  # 0001 의 값(되돌림)


def options_check(octets: int) -> str:
    return f'ALTER TABLE "{RUNS}" ADD CONSTRAINT "{CHECK}" CHECK (octet_length(options::text) <= {octets});'


DROP_CHECK = f'ALTER TABLE "{RUNS}" DROP CONSTRAINT "{CHECK}";'


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0002_llm_call_log_step"),
        ("runs", "0001_initial"),
    ]

    operations = [
        migrations.AlterField(
            model_name="runrow",
            name="document",
            field=models.ForeignKey(
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name="runs",
                to="core.documentrow",
            ),
        ),
        migrations.RunSQL(sql=DROP_CHECK, reverse_sql=options_check(OPTIONS_MAX_OCTETS_0001)),
        migrations.RunSQL(sql=options_check(OPTIONS_CEILING_OCTETS), reverse_sql=DROP_CHECK),
    ]
