"""쓰기. 실행 묶음(RX1a — runbundle 앱의 import_runs)이 넣는 LLM 호출 기록의 행(표 core_llm_call_logs).

    insert_rows(company_id, rows, run_map)   행마다 하나씩 넣는다. run_id 는 옛 실행 id → run_map 의 새 id
                                             (NULL 은 그대로)

★ 행은 company_id 의 범위로 만든다(LlmCallLogRow.for_company — 생성자 0, 쓰는 자리는 core/llm/sink_db.py 와 여기 둘).
★ 행에 id·company_id·created_at 이 실려 있으면 ValueError 다: 회사는 인자, id 는 DB 가, created_at 은 넣은 때다
  (auto_now_add — 앱 역할에 UPDATE 가 없어 되돌릴 길도 없다).
★ 지도에 없는 실행 id 면 UnknownId 다(묶음 밖을 가리키는 줄을 그대로 넣지 않는다).
부르는 쪽의 durable 블록 안에서 부른다(여기의 블록은 세이브포인트다).
"""

from collections.abc import Mapping, Sequence

from django.db import transaction

from esgapi.core.flows.carriers import UnknownId
from esgapi.core.models import LlmCallLogRow

NOT_CARRIED = frozenset({"id", "company_id", "created_at"})


def insert_rows(*, company_id: int, rows: Sequence[Mapping[str, object]], run_map: Mapping[int, int]) -> int:
    """넣은 행 수. 하나라도 틀리면 던진다(부르는 쪽 블록이 전부 되돌린다)."""
    with transaction.atomic():
        for row in rows:
            carried = NOT_CARRIED & set(row)
            if carried:
                raise ValueError(f"LLM 기록 행에 싣지 않는 칸이 있다: {sorted(carried)}")
            fields = dict(row)
            old = fields.get("run_id")
            if old is not None:
                if not isinstance(old, int) or old not in run_map:
                    raise UnknownId(f"LLM 기록의 실행 {old} 이 묶음의 지도에 없다")
                fields["run_id"] = run_map[old]
            LlmCallLogRow.for_company(company_id).create(company_id=company_id, **fields)
    return len(rows)
